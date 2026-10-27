"""Retained isolated fixtures: no cleanup, compiler, linker, or native acquisition."""
import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import unittest
import uuid

from sdk_witness import capture, verify, reconcile_consumed, WitnessError

OUTPUT = Path(__file__).resolve().parents[3] / 'build/path-embed-sdk-witness-r1'


class SDKWitnessTests(unittest.TestCase):
    def setUp(self):
        self.base = OUTPUT / ('fixture-' + uuid.uuid4().hex)
        self.root = self.base / 'SDK.sdk'
        self.root.mkdir(parents=True)
        self.alias = self.base / 'SDK27.sdk'
        self.alias.symlink_to('SDK.sdk')
        self.write('usr/lib/libSystem.B.tbd', b'opaque\0interface\xff')
        self.write('usr/lib/libc++.1.tbd', b'not parsed as TAPI')
        self.write('System/Library/Frameworks/F.framework/Versions/A/F.tbd', b'framework')
        self.write('SDKSettings.json', b'{"Version":"fixture"}')
        self.write('SDKSettings.plist', b'opaque plist bytes')
        self.write('usr/include/ignored.h', b'headers outside byte witness')
        self.link('usr/lib/libSystem.tbd', 'libSystem.B.tbd')
        self.link('usr/lib/libm.tbd', 'libSystem.tbd')
        self.link('usr/lib/libdl.tbd', 'libSystem.tbd')
        self.link('usr/lib/libc++.tbd', 'libc++.1.tbd')
        self.link('System/Library/Frameworks/F.framework/Versions/Current', 'A')
        self.link('System/Library/Frameworks/F.framework/F.tbd', 'Versions/Current/F.tbd')
        # These must be recorded but never dereferenced during inventory.
        self.link('unused-escape', '/outside-sdk-not-read')
        self.link('unused-dangling', 'missing')
        self.link('unused-cycle', 'unused-cycle')
        self.manifest = self.capture()
        (self.base / 'frozen.json').write_text(json.dumps(self.manifest, ensure_ascii=True, sort_keys=True))

    def write(self, path, data):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def link(self, path, target):
        (self.root / path).symlink_to(target)

    def capture(self):
        return capture(str(self.alias), str(self.root))

    def verify(self, manifest=None):
        verify(self.manifest if manifest is None else manifest, str(self.alias), str(self.root))

    def consume(self, paths, manifest=None):
        return reconcile_consumed(self.manifest if manifest is None else manifest, paths,
                                  requested_root=str(self.alias), expected_canonical_root=str(self.root))

    def test_positive_full_hops_and_determinism(self):
        self.assertEqual(self.manifest, self.capture())
        self.verify(json.loads(json.dumps(self.manifest, ensure_ascii=True)))
        paths = [str(self.alias / p) for p in ('usr/lib/libm.tbd', 'usr/lib/libdl.tbd',
                 'usr/lib/libc++.tbd', 'System/Library/Frameworks/F.framework/F.tbd')]
        records = self.consume(paths)
        self.assertEqual([len(r['hops']) for r in records], [3, 3, 2, 3])
        self.assertEqual([h['target'] for h in records[-1]['hops']],
                         ['SDK.sdk', 'Versions/Current/F.tbd', 'A'])
        self.assertEqual(records[0]['canonical'], str(self.root / 'usr/lib/libSystem.B.tbd'))
        self.assertEqual(records[0]['sha256'], hashlib.sha256(b'opaque\0interface\xff').hexdigest())
        self.assertEqual(len(self.manifest['interfaces']), 3)
        self.assertEqual(len(self.manifest['settings']), 2)
        self.assertEqual(len(self.manifest['symlinks']), 9)
        self.assertEqual(self.consume(paths + paths)[4:], records)
        direct = self.consume([str(self.root / 'usr/lib/libSystem.B.tbd')])[0]
        self.assertEqual(direct['hops'], [])

    def test_omitted_extra_duplicate_and_reordered_entries(self):
        for group in ('interfaces', 'symlinks', 'settings'):
            for mode in ('omitted', 'duplicate', 'reordered'):
                bad = copy.deepcopy(self.manifest)
                if mode == 'omitted':
                    bad[group].pop()
                elif mode == 'duplicate':
                    bad[group].append(copy.deepcopy(bad[group][0]))
                else:
                    bad[group].reverse()
                with self.subTest(group=group, mode=mode), self.assertRaises(WitnessError):
                    self.verify(bad)
        self.write('usr/lib/new.tbd', b'extra')
        with self.assertRaises(WitnessError):
            self.verify()

    def test_rehashed_current_does_not_replace_frozen_baseline(self):
        self.write('usr/lib/libSystem.B.tbd', b'changed')
        rehashed = self.capture()
        verify(rehashed, str(self.alias), str(self.root))
        self.assertNotEqual(rehashed, self.manifest)
        with self.assertRaises(WitnessError):
            self.verify()
        with self.assertRaises(WitnessError):
            self.consume([str(self.alias / 'usr/lib/libm.tbd')])

    def test_settings_changed_and_missing(self):
        self.write('SDKSettings.json', b'changed')
        with self.assertRaises(WitnessError):
            self.verify()
        (self.root / 'SDKSettings.plist').rename(self.base / 'retained-settings.plist')
        with self.assertRaises(WitnessError):
            self.verify()

    def test_wrong_roots_and_prefix_sibling(self):
        sibling = self.base / 'SDK.sdk-sibling'
        sibling.mkdir()
        for requested, canonical in [(str(self.alias), str(sibling)), (str(sibling), str(self.root)),
                                      (str(self.alias), str(self.alias))]:
            with self.subTest(requested=requested, canonical=canonical), self.assertRaises(WitnessError):
                verify(self.manifest, requested, canonical)
        for path in (str(sibling / 'a.tbd'), '/foreign/a.tbd', 'relative.tbd'):
            with self.subTest(path=path), self.assertRaises(WitnessError):
                self.consume([path])

    def test_unused_links_recorded_consumed_escape_cycle_dangling_rejected(self):
        self.verify()
        for path in ('unused-escape/a.tbd', 'unused-dangling/a.tbd', 'unused-cycle/a.tbd',
                     '../SDK.sdk-sibling/a.tbd', 'usr/include/ignored.h', 'usr/lib/absent.tbd'):
            with self.subTest(path=path), self.assertRaises(WitnessError):
                self.consume([str(self.alias / path)])

    def test_intermediate_changed_and_alias_replaced(self):
        link = self.root / 'System/Library/Frameworks/F.framework/Versions/Current'
        link.rename(self.base / 'retained-Current')
        link.symlink_to('B')
        with self.assertRaises(WitnessError):
            self.verify()
        self.alias.rename(self.base / 'retained-root-alias')
        self.alias.mkdir()
        with self.assertRaises(WitnessError):
            self.verify()

    def test_file_replaced_by_alias_rejected(self):
        file = self.root / 'usr/lib/libSystem.B.tbd'
        file.rename(self.base / 'retained-interface.tbd')
        file.symlink_to('libc++.1.tbd')
        with self.assertRaises(WitnessError):
            self.verify()

    def test_strict_json_types_and_fields(self):
        mutations = []
        for field, value in [('version', True), ('version', 1.0), ('interfaces', {}),
                             ('requested_root', False), ('root_hops', ())]:
            bad = copy.deepcopy(self.manifest)
            bad[field] = value
            mutations.append(bad)
        for value in (True, 1.0, '1', -1):
            bad = copy.deepcopy(self.manifest)
            bad['interfaces'][0]['size'] = value
            mutations.append(bad)
        bad = copy.deepcopy(self.manifest)
        bad['interfaces'][0]['unexpected'] = 1
        mutations.append(bad)
        bad = copy.deepcopy(self.manifest)
        bad['symlinks'][0]['target'] = False
        mutations.append(bad)
        for index, bad in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(WitnessError):
                self.verify(bad)

    def test_non_utf8_symlink_target_and_interface_roundtrip(self):
        raw = os.fsencode(self.root) + b'/usr/lib/raw-\xff.tbd'
        # APFS may reject non-UTF8 names; still exercise lossless JSON transport.
        self.assertEqual(os.fsencode(json.loads(json.dumps(os.fsdecode(raw), ensure_ascii=True))), raw)
        try:
            with open(raw, 'wb') as stream:
                stream.write(b'opaque')
        except OSError as exc:
            if exc.errno == errno.EILSEQ:
                self.skipTest('host filesystem rejects non-UTF8 names; JSON byte roundtrip passed')
            raise
        os.symlink(b'raw-\xff.tbd', os.fsencode(self.root) + b'/usr/lib/raw-alias.tbd')
        current = self.capture()
        decoded = json.loads(json.dumps(current, ensure_ascii=True))
        verify(decoded, str(self.alias), str(self.root))
        result = self.consume([str(self.alias / 'usr/lib/raw-alias.tbd')], decoded)
        self.assertEqual(os.fsencode(result[0]['canonical']), raw)

    def test_absolute_internal_alias_and_settings_alias(self):
        self.link('absolute.tbd', str(self.root / 'usr/lib/libSystem.B.tbd'))
        (self.root / 'SDKSettings.json').rename(self.root / 'settings-bytes')
        self.link('SDKSettings.json', 'settings-bytes')
        current = self.capture()
        self.consume([str(self.alias / 'absolute.tbd')], current)
        self.assertEqual(current['settings'][0]['canonical'], 'settings-bytes')

    def test_root_intermediate_directory_alias_chain(self):
        anchor = self.base / 'sdkRoot'
        anchor.symlink_to('SDK.sdk', target_is_directory=True)
        container = self.base / 'container'
        container.mkdir()
        (container / 'SDK27.sdk').symlink_to('../sdkRoot')
        outer = self.base / 'outer'
        outer.symlink_to('container', target_is_directory=True)
        requested = str(outer / 'SDK27.sdk')
        current = capture(requested, str(self.root))
        self.assertEqual([h['target'] for h in current['root_hops']],
                         ['container', '../sdkRoot', 'SDK.sdk'])
        result = reconcile_consumed(current, [requested + '/usr/lib/libm.tbd'],
                                    requested_root=requested, expected_canonical_root=str(self.root))
        self.assertEqual(len(result[0]['hops']), 5)

    def test_nonregular_settings_and_interface_rejected_without_blocking(self):
        (self.root / 'SDKSettings.json').rename(self.base / 'retained-settings.json')
        os.mkfifo(self.root / 'SDKSettings.json')
        with self.assertRaisesRegex(WitnessError, 'not regular'):
            self.capture()
        os.mkfifo(self.root / 'usr/lib/fifo.tbd')
        with self.assertRaisesRegex(WitnessError, 'nonregular interface'):
            self.capture()

    def test_escape_then_return_is_rejected(self):
        self.link('escape-return.tbd', '../SDK.sdk/usr/lib/libSystem.B.tbd')
        current = self.capture()
        with self.assertRaises(WitnessError):
            self.consume([str(self.alias / 'escape-return.tbd')], current)


if __name__ == '__main__':
    print('pid=' + str(os.getpid()), flush=True)
    unittest.main(verbosity=2)
