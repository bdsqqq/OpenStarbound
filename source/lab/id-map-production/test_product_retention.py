"""Isolated sparse fixtures; never invoke cleanup or touch actual game products."""
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

import product_retention as v


class ProductRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # macOS /var is an alias: fixtures use their physical repository spelling.
        self.repo = Path(self.temp.name).resolve()
        for root in v.ROOTS:
            (self.repo / root).mkdir(parents=True)
        self.names = [v.ROOTS[0] + '/native.map', v.ROOTS[1] + '/admission.json']
        for i, name in enumerate(self.names):
            with (self.repo / name).open('wb') as out:
                out.write(bytes([i]))
                out.truncate(v.MIN_BYTES)
        self.small = self.repo / v.ROOTS[0] / 'model.json'
        self.small.write_bytes(b'compact live proof')
        protected = [v.CANONICAL, *v.BINS]
        protected += [v.REFERENCE_OBJECTS + 'Original%d.cpp.o' % i for i in range(113)]
        for name in protected:
            p = self.repo / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(('original:' + name).encode())
        rows = v.inventory(self.repo)
        self.c = dict(version=1, roots=v.ROOTS[:], minBytes=v.MIN_BYTES, archiveRun=v.RUN,
                      inventory=rows, protected={p: v.row(self.repo / p) for p in protected},
                      selected=v.validate_selection(rows), archiveGrowthBound=1024**2,
                      archiveBeforeBytes=0)

    def archive(self):
        """Fixture simulation only: no subprocess and no production archiver call."""
        entries = []
        for name in self.c['selected']:
            r = self.c['inventory'][name]
            p = self.repo / name
            blob = self.blob(r)
            blob.parent.mkdir(parents=True, exist_ok=True)
            blob.write_bytes(gzip.compress(p.read_bytes(), compresslevel=1))
            entries.append(dict(path=name, sha256=r['sha256'], size=r['size'],
                                fingerprint=r['fingerprint'][:],
                                mode=stat.S_IMODE(r['fingerprint'][5]),
                                mtime_ns=r['fingerprint'][3]))
            p.unlink()
        return dict(version=1, status='ARCHIVED_VERIFIED_PRUNED', roots=v.ROOTS[:],
                    min_bytes=v.MIN_BYTES, entries=entries, unique_blobs=2,
                    removed_bytes=2 * v.MIN_BYTES)

    def blob(self, row):
        h = row['sha256']
        return self.repo / v.ARCHIVE / 'blobs' / h[:2] / (h + '.gz')

    def rejected(self, c=None, m=None, match=None):
        context = self.assertRaisesRegex(ValueError, match) if match else self.assertRaises(ValueError)
        with context:
            v.verify(self.repo, c if c is not None else self.c, m)

    def test_before_positive(self):
        r = v.verify(self.repo, self.c)
        self.assertEqual((r['selected'], r['complement'], r['protected']), (2, 1, 116))
        self.assertEqual(r['liveOriginState'], 'LIVE_ORIGINAL')

    def test_after_positive(self):
        r = v.verify(self.repo, self.c, self.archive())
        self.assertEqual(r['liveOriginState'], 'UNAVAILABLE_ARCHIVED')
        self.assertEqual(r['archivedLogicalBytes'], 2 * v.MIN_BYTES)
        self.assertEqual(r['complement'], 1)

    def test_membership_added_before(self):
        (self.repo / v.ROOTS[0] / 'extra.json').write_text('new')
        self.rejected(match='membership')

    def test_membership_omitted_from_closure(self):
        del self.c['inventory'][str(self.small.relative_to(self.repo))]
        self.rejected(match='membership')

    def test_source_changed_same_size(self):
        with (self.repo / self.names[0]).open('r+b') as out:
            out.write(b'x')
        self.rejected(match='unchanged live complement')

    def test_bad_original_hash(self):
        self.c['inventory'][self.names[0]]['sha256'] = '0' * 64
        self.rejected(match='unchanged live complement')

    def test_actual_external_hardlink(self):
        os.link(self.repo / self.names[0], self.repo / 'outside-selection')
        self.c['inventory'] = v.inventory(self.repo)
        self.rejected(match='external hardlink')

    def test_protected_inode_overlap(self):
        self.c['inventory'][self.names[0]]['fingerprint'][:2] = self.c['protected'][v.CANONICAL]['fingerprint'][:2]
        self.rejected(match='protected path/inode overlap')

    def test_modified_protected_bytes(self):
        (self.repo / v.BINS[0]).write_bytes(b'changed')
        self.rejected(match='unchanged protected bytes')

    def test_missing_required_protection(self):
        for name in (v.CANONICAL, v.BINS[0], v.REFERENCE_OBJECTS + 'Original0.cpp.o'):
            c = copy.deepcopy(self.c)
            del c['protected'][name]
            self.rejected(c)

    def test_mixed_core_extern_reference_protection(self):
        old = v.REFERENCE_OBJECTS + 'Original0.cpp.o'
        new = v.REFERENCE_OBJECT_ROOTS[1] + 'CMakeFiles/star_extern.dir/lua/lapi.c.o'
        p = self.repo / new
        p.parent.mkdir(parents=True, exist_ok=True)
        (self.repo / old).rename(p)
        del self.c['protected'][old]
        self.c['protected'][new] = v.row(p)
        self.assertEqual(v.verify(self.repo, self.c)['protected'], 116)

    def test_protection_escape(self):
        self.c['protected']['build/unrelated/file'] = self.c['protected'][v.CANONICAL]
        self.rejected(match='protection scope')

    def test_modified_complement_after(self):
        m = self.archive()
        self.small.write_bytes(b'changed')
        self.rejected(m=m, match='unchanged live complement')

    def test_missing_manifest_entry(self):
        m = self.archive()
        m['entries'].pop()
        self.rejected(m=m, match='exact manifest selection')

    def test_duplicate_manifest_entry(self):
        m = self.archive()
        m['entries'][1] = copy.deepcopy(m['entries'][0])
        self.rejected(m=m, match='exact manifest selection')

    def test_manifest_source_metadata(self):
        m = self.archive()
        for key, value in [('sha256', '0' * 64), ('size', v.MIN_BYTES + 1),
                           ('fingerprint', [0] * 7), ('mode', 0), ('mtime_ns', 0)]:
            bad = copy.deepcopy(m)
            bad['entries'][0][key] = value
            self.rejected(m=bad, match='source pin')

    def test_manifest_wrong_state_scope_total_unique(self):
        m = self.archive()
        for key, value in [('version', 2), ('status', 'PLANNED_NOT_PRUNED'),
                           ('roots', list(reversed(v.ROOTS))), ('min_bytes', 1),
                           ('removed_bytes', 1), ('unique_blobs', 1)]:
            bad = copy.deepcopy(m)
            bad[key] = value
            self.rejected(m=bad)

    def test_symlink_file(self):
        (self.repo / v.ROOTS[0] / 'alias').symlink_to(self.small)
        self.rejected(match='no aliases')

    def test_symlink_directory(self):
        (self.repo / v.ROOTS[0] / 'alias').symlink_to(self.repo / v.ROOTS[1], target_is_directory=True)
        self.rejected(match='no aliases')

    def test_symlink_root(self):
        root = self.repo / v.ROOTS[-1]
        root.rmdir()
        root.symlink_to(self.repo / v.ROOTS[0], target_is_directory=True)
        self.rejected(match='no aliases')

    def test_nonregular_member(self):
        os.mkfifo(self.repo / v.ROOTS[0] / 'fifo')
        self.rejected(match='regular file')

    def test_blob_corrupt_valid_gzip(self):
        m = self.archive()
        self.blob(m['entries'][0]).write_bytes(gzip.compress(b'wrong'))
        self.rejected(m=m, match='exact reconstructed bytes')

    def test_blob_bomb(self):
        m = self.archive()
        self.blob(m['entries'][0]).write_bytes(gzip.compress(b'z' * (v.MIN_BYTES + 1)))
        self.rejected(m=m, match='bounded reconstruction')

    def test_blob_symlink(self):
        m = self.archive()
        blob = self.blob(m['entries'][0])
        blob.unlink()
        blob.symlink_to(self.small)
        self.rejected(m=m, match='no aliases')

    def test_missing_complement_after(self):
        m = self.archive()
        self.small.unlink()
        self.rejected(m=m, match='membership')

    def test_archive_growth_bound_enforced(self):
        m = self.archive()
        self.c['archiveGrowthBound'] = 1
        self.rejected(m=m, match='archive growth accounting')

    def test_selected_shadow_after(self):
        m = self.archive()
        (self.repo / self.names[0]).symlink_to(self.small)
        self.rejected(m=m, match='no aliases')

    def test_unknown_large_product(self):
        c = copy.deepcopy(self.c)
        c['inventory'][v.ROOTS[0] + '/source.cpp'] = c['inventory'].pop(self.names[0])
        self.rejected(c, match='known generated product')

    def test_accounted_special_products_are_exact_path_exceptions(self):
        r = copy.deepcopy(self.c['inventory'][self.names[0]])
        # Neither the actual .typed data nor disassembly stdout needs execute bits.
        for name in v.SPECIAL_PRODUCTS:
            self.assertEqual(v.validate_selection({name: r}), [name])
        for name in (v.ROOTS[0] + '/other.stdout', v.ROOTS[0] + '/other.typed',
                     v.ROOTS[0] + '/not-executable'):
            with self.assertRaisesRegex(ValueError, 'known generated product'):
                v.validate_selection({name: r})
        r['fingerprint'][5] |= 0o100
        name = v.ROOTS[0] + '/native'
        self.assertEqual(v.validate_selection({name: r}), [name])

    def test_exact_threshold_selection_and_bounded_count(self):
        c = copy.deepcopy(self.c)
        c['selected'].pop()
        self.rejected(c, match='exact closure selection')
        with self.assertRaisesRegex(ValueError, 'bounded selected count'):
            v.validate_selection({})
        rows = {v.ROOTS[0] + '/%d.map' % i: self.c['inventory'][self.names[0]] for i in range(65)}
        with self.assertRaisesRegex(ValueError, 'bounded selected count'):
            v.validate_selection(rows)

    def test_closure_bounds(self):
        for key, value in [('archiveGrowthBound', 0), ('archiveGrowthBound', 129 * 1024**2),
                           ('archiveBeforeBytes', v.MAX_ARCHIVE), ('archiveRun', 'other'),
                           ('roots', list(reversed(v.ROOTS))), ('version', 2)]:
            c = copy.deepcopy(self.c)
            c[key] = value
            self.rejected(c)

    def test_external_pins_and_manifest_path(self):
        path = self.repo / 'closure.json'
        data = json.dumps(self.c).encode()
        path.write_bytes(data)
        pin = hashlib.sha256(data).hexdigest()
        self.assertEqual(v.pinned_json(self.repo, str(path), pin), self.c)
        with self.assertRaisesRegex(ValueError, 'external metadata pin'):
            v.pinned_json(self.repo, str(path), '0' * 64)
        with self.assertRaisesRegex(ValueError, 'fixed archive run'):
            v.pinned_json(self.repo, str(path), pin, v.MANIFEST)
        path.write_bytes(b'{"version":1,"version":2}')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON'):
            v.pinned_json(self.repo, str(path), hashlib.sha256(path.read_bytes()).hexdigest())

    def test_cli_after_requires_exact_manifest_and_pin(self):
        m = self.archive()
        closure = self.repo / 'closure.json'
        manifest = self.repo / v.MANIFEST
        manifest.parent.mkdir(parents=True)
        closure.write_text(json.dumps(self.c))
        manifest.write_text(json.dumps(m))
        cp = hashlib.sha256(closure.read_bytes()).hexdigest()
        mp = hashlib.sha256(manifest.read_bytes()).hexdigest()
        args = ['--closure', str(closure), '--closure-sha', cp,
                '--manifest', str(manifest), '--manifest-sha', mp]
        with patch.object(v, 'ROOT', self.repo), patch('builtins.print') as output:
            v.main(args)
            self.assertEqual(json.loads(output.call_args.args[0])['liveOriginState'],
                             'UNAVAILABLE_ARCHIVED')
            args[-1] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'external metadata pin'):
                v.main(args)

    def test_cli_requires_pin_and_does_not_mutate(self):
        p = self.repo / 'closure.json'
        p.write_text(json.dumps(self.c))
        pin = hashlib.sha256(p.read_bytes()).hexdigest()
        with patch.object(v, 'ROOT', self.repo), patch('builtins.print') as output:
            v.main(['--closure', str(p), '--closure-sha', pin])
            self.assertEqual(json.loads(output.call_args.args[0])['selected'], 2)
            with self.assertRaisesRegex(ValueError, 'external metadata pin'):
                v.main(['--closure', str(p), '--closure-sha', '0' * 64])
            with self.assertRaisesRegex(ValueError, 'pin together'):
                v.main(['--closure', str(p), '--closure-sha', pin, '--manifest', v.MANIFEST])
        self.assertEqual(v.inventory(self.repo), self.c['inventory'])


if __name__ == '__main__':
    unittest.main()
