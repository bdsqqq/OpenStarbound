#!/usr/bin/env python3
"""Finite synthetic CAS tests only; never open the actual evidence archive."""
import gzip
import hashlib
import importlib.util
import io
import json
import lzma
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zlib
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source/lab'))
sys.path.insert(0, str(ROOT / 'source/lab/id-map-production'))
from migration import archive_blobs as blobs
import product_retention

RAW = b'finite archive identity fixture\x00\xff' * 4096
SHA = hashlib.sha256(RAW).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class BlobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='archive-codec-test-')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        self.archive = self.repo / 'build/migration-evidence-archive'
        self.fanout = self.archive / 'blobs' / SHA[:2]
        self.fanout.mkdir(parents=True)

    def put(self, codec='xz', raw=RAW):
        path = self.fanout / (SHA + '.' + codec)
        path.write_bytes(gzip.compress(raw, mtime=0) if codec == 'gz' else lzma.compress(raw))
        return path

    def decoded(self):
        with blobs.open_blob(self.archive, SHA) as stream:
            result = io.BytesIO()
            while chunk := stream.read(137):
                result.write(chunk)
            return result.getvalue()

    def test_gzip_and_xz_same_raw_identity(self):
        for codec in ('gz', 'xz'):
            with self.subTest(codec=codec):
                path = self.put(codec)
                self.assertEqual(blobs.resolve_blob(self.archive, SHA), path)
                self.assertEqual(hashlib.sha256(self.decoded()).hexdigest(), SHA)
                path.unlink()

    def test_missing(self):
        with self.assertRaises(FileNotFoundError):
            blobs.resolve_blob(self.archive, SHA)

    def test_sha_schema(self):
        for sha in (None, 3, b'a' * 64, SHA.upper(), SHA[:-1], SHA + '\n', '../' + SHA):
            with self.subTest(sha=sha), self.assertRaises(ValueError):
                blobs.resolve_blob(self.archive, sha)

    def test_ambiguous_and_known_unsafe_mutant(self):
        self.put('gz')
        self.put('xz')
        # Isolated mutant: accepting the first suffix hides physical ambiguity.
        unsafe = lambda root, sha: root / 'blobs' / sha[:2] / (sha + '.gz')
        self.assertEqual(unsafe(self.archive, SHA).read_bytes()[:2], b'\x1f\x8b')
        with self.assertRaises(ValueError):
            blobs.resolve_blob(self.archive, SHA)
        with mock.patch.object(blobs, 'resolve_blob', unsafe):
            self.assertEqual(self.decoded(), RAW)
        with self.assertRaises(ValueError):
            self.decoded()

    def test_bad_entry_types(self):
        for kind in ('symlink', 'broken', 'hardlink', 'directory'):
            with self.subTest(kind=kind):
                path = self.fanout / (SHA + '.xz')
                other = self.repo / 'other'
                other.write_bytes(lzma.compress(RAW))
                if kind in ('symlink', 'broken'):
                    path.symlink_to(other if kind == 'symlink' else self.repo / 'absent')
                elif kind == 'hardlink':
                    os.link(other, path)
                else:
                    path.mkdir()
                with self.assertRaises(ValueError):
                    blobs.resolve_blob(self.archive, SHA)
                if kind == 'directory':
                    path.rmdir()
                else:
                    path.unlink()
                other.unlink()

    def test_invalid_other_suffix_does_not_fallback(self):
        self.put('gz')
        (self.fanout / (SHA + '.xz')).symlink_to(self.repo / 'absent')
        with self.assertRaises(ValueError):
            self.decoded()

    def test_root_alias_and_relative_root(self):
        self.put()
        alias = self.repo / 'alias'
        alias.symlink_to(self.archive, target_is_directory=True)
        for root in (alias, Path('relative')):
            with self.subTest(root=root), self.assertRaises(ValueError):
                blobs.resolve_blob(root, SHA)

    def test_parent_aliases(self):
        for directory in (self.archive / 'blobs', self.fanout):
            with self.subTest(directory=directory):
                moved = directory.with_name(directory.name + '-physical')
                directory.rename(moved)
                directory.symlink_to(moved, target_is_directory=True)
                with self.assertRaises(ValueError):
                    blobs.resolve_blob(self.archive, SHA)
                directory.unlink()
                moved.rename(directory)

    def test_magic_mismatch(self):
        for codec in ('gz', 'xz'):
            with self.subTest(codec=codec):
                path = self.put(codec)
                path.write_bytes(lzma.compress(RAW) if codec == 'gz' else gzip.compress(RAW))
                with self.assertRaises(ValueError):
                    self.decoded()
                path.unlink()

    def test_corruption_truncation_trailing_junk(self):
        for codec in ('gz', 'xz'):
            for damage in ('crc', 'truncated', 'trailing'):
                with self.subTest(codec=codec, damage=damage):
                    path = self.put(codec)
                    raw = bytearray(path.read_bytes())
                    if damage == 'crc':
                        raw[-9] ^= 0xff
                    elif damage == 'truncated':
                        del raw[-8:]
                    else:
                        raw.extend(b'not another stream')
                    path.write_bytes(raw)
                    with self.assertRaises((ValueError, OSError, EOFError, lzma.LZMAError)):
                        self.decoded()
                    path.unlink()

    def test_concatenated_xz_and_padding(self):
        path = self.put()
        path.write_bytes(lzma.compress(RAW[:11]) + b'\0' * 4 + lzma.compress(RAW[11:]) + b'\0' * 8)
        self.assertEqual(self.decoded(), RAW)
        path.write_bytes(lzma.compress(RAW) + b'\0')
        with self.assertRaises(lzma.LZMAError):
            self.decoded()

    def test_xz_requires_crc64_on_every_stream(self):
        path = self.put()
        for check in (lzma.CHECK_NONE, lzma.CHECK_CRC32, lzma.CHECK_SHA256):
            for prefix in (b'', lzma.compress(b'valid first stream')):
                with self.subTest(check=check, concatenated=bool(prefix)):
                    path.write_bytes(prefix + lzma.compress(RAW, check=check))
                    with self.assertRaisesRegex(lzma.LZMAError, 'requires CRC64'):
                        self.decoded()

    def test_xz_dictionary_memory_limit(self):
        path = self.put()
        # A small stream with a declared 128 MiB dictionary must not allocate it.
        encoded = bytearray(lzma.compress(b'a'))
        header_size = (encoded[12] + 1) * 4
        self.assertEqual(encoded[14:16], b'\x21\x01')
        encoded[16] = 28  # LZMA2 dictionary property: 128 MiB.
        crc_start = 12 + header_size - 4
        encoded[crc_start:crc_start + 4] = zlib.crc32(encoded[12:crc_start]).to_bytes(4, 'little')
        path.write_bytes(encoded)
        with self.assertRaises(lzma.LZMAError):
            self.decoded()

    def test_readonly_and_closed_after_exception(self):
        self.put()
        held = None
        with self.assertRaises(RuntimeError):
            with blobs.open_blob(self.archive, SHA) as stream:
                held = stream
                with self.assertRaises(io.UnsupportedOperation):
                    stream.write(b'not permitted')
                raise RuntimeError('caller failure')
        self.assertTrue(held.closed)

    def test_open_rejects_late_hardlink(self):
        path = self.put()
        resolve = blobs.resolve_blob
        def late_link(root, sha):
            result = resolve(root, sha)
            os.link(path, self.repo / 'late-hardlink')
            return result
        with mock.patch.object(blobs, 'resolve_blob', late_link):
            with self.assertRaises(ValueError):
                self.decoded()

    def test_open_rechecks_codec_ambiguity(self):
        path = self.put()
        real_open = os.open
        def add_other_codec(name, flags, *args, **kwargs):
            if name == path.name:
                self.put('gz')
            return real_open(name, flags, *args, **kwargs)
        with mock.patch.object(blobs.os, 'open', add_other_codec):
            with self.assertRaisesRegex(ValueError, 'ambiguous archive codec'):
                self.decoded()

    def test_open_fstat_rejects_swapped_file(self):
        path = self.put()
        real_open = os.open
        def swap(name, flags, *args, **kwargs):
            if name == path.name:
                replacement = path.with_suffix('.replacement')
                replacement.write_bytes(path.read_bytes())
                replacement.replace(path)
            return real_open(name, flags, *args, **kwargs)
        with mock.patch.object(blobs.os, 'open', swap):
            with self.assertRaisesRegex(ValueError, 'changed before open'):
                self.decoded()

    def test_product_consumer_xz_positive_tamper_negative(self):
        path = self.put()
        expected = dict(sha256=SHA, size=len(RAW))
        product_retention.reconstructed(self.repo, expected)
        path.write_bytes(lzma.compress(b'wrong identity'))
        with self.assertRaisesRegex(ValueError, 'exact reconstructed bytes'):
            product_retention.reconstructed(self.repo, expected)

    def test_ttl_consumer_snapshot_read_xz_and_tamper(self):
        ttl = module('test_ttl_codec', 'scripts/verify-ttl-retention.py')
        path = self.put()
        original = 'build/old-fixture/result.json'
        resolver = ttl.Resolver([])
        resolver.index[str(self.repo / original)] = (dict(sha256=SHA, size=len(RAW)), 'fake-pin')
        with mock.patch.object(ttl, 'ROOT', self.repo):
            self.assertEqual(resolver.read(original, SHA), RAW)
            path.write_bytes(lzma.compress(b'wrong identity'))
            # A new resolver has no invocation-local decoded-byte memo.
            bad = ttl.Resolver([])
            bad.index = resolver.index
            with self.assertRaisesRegex(ValueError, 'reconstructed byte integrity'):
                bad.read(original, SHA)

    def test_cache_consumer_xz_and_tamper(self):
        import cache_retention as cache
        raw = b'cache synthetic bytes\0' * (3 * 1024**2 // 21 + 1)
        sha = hashlib.sha256(raw).hexdigest()
        fanout = self.archive / 'blobs' / sha[:2]
        fanout.mkdir(exist_ok=True)
        path = fanout / (sha + '.xz')
        path.write_bytes(lzma.compress(raw))
        for root in (cache.SESSION, cache.DEPS):
            (self.repo / root).mkdir(parents=True)
        rows = {name: dict(sha256=sha, size=len(raw),
                          fingerprint=[1, i, len(raw), 0, 0, 0o100644, 1])
                for i, name in enumerate(cache.SELECTED)}
        closure = dict(version=1, roots=[cache.SESSION, cache.DEPS],
                       minBytes=cache.THRESHOLD, archiveRun=cache.RUN,
                       inventory=rows, protected={})
        manifest = dict(status='ARCHIVED_VERIFIED_PRUNED', roots=closure['roots'],
                        min_bytes=cache.THRESHOLD,
                        entries=[dict(path=name, **r) for name, r in rows.items()])
        self.assertEqual(cache.verify(self.repo, closure, manifest)['selected'], 3)
        path.write_bytes(lzma.compress(b'tampered'))
        with self.assertRaisesRegex(ValueError, 'reconstructed cache bytes'):
            cache.verify(self.repo, closure, manifest)

    def test_weighted_consumer_xz_and_tamper(self):
        weighted = module('test_weighted_codec', 'scripts/verify-weighted-pool-retention.py')
        raw = b'finite weighted product\0' * (2 * 1024**2 // 24 + 1)
        sha = hashlib.sha256(raw).hexdigest()
        fanout = self.archive / 'blobs' / sha[:2]
        fanout.mkdir(exist_ok=True)
        path = fanout / (sha + '.xz')
        path.write_bytes(lzma.compress(raw))
        names = ['build/behavior/weighted-pool-combined-r1/' + backend + '/bin/starbound'
                 for backend in ('reference', 'candidate')]
        for name in names:
            (self.repo / name).parent.mkdir(parents=True)
        manifest = self.archive / 'runs/finite-fixture/manifest.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps(dict(version=1, status='ARCHIVED_VERIFIED_PRUNED',
            roots=[str(Path(name).parent) for name in names], min_bytes=weighted.MIN_BYTES,
            removed_bytes=2 * len(raw), entries=[dict(path=name, sha256=sha, size=len(raw),
                fingerprint=[1, i, len(raw), 0, 0, 0o100644, 1]) for i, name in enumerate(names)])))
        specification = (manifest, hashlib.sha256(manifest.read_bytes()).hexdigest())
        protected = {self.repo / name: sha for name in names}
        self.assertEqual(len(weighted.retired_product_bindings(self.repo, specification, protected)[0]), 2)
        path.write_bytes(lzma.compress(b'tampered'))
        with self.assertRaisesRegex(ValueError, 'reconstructed bytes mismatch'):
            weighted.retired_product_bindings(self.repo, specification, protected)

    def test_lru_consumer_xz_and_tamper(self):
        lru = module('test_lru_codec', 'scripts/verify-lru-retention.py')
        path = self.put()
        original = 'build/old-fixture/result.json'
        manifest = self.archive / 'runs/fixture/manifest.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps(dict(status='ARCHIVED_VERIFIED_PRUNED', entries=[
            dict(path=original, sha256=SHA, size=len(RAW))])))
        verifier = self.repo / 'source/lab/lru-qualification/verify.py'
        verifier.parent.mkdir(parents=True)
        verifier.write_bytes(b'finite fixture, never executed')
        certificate = self.repo / 'certificate.json'
        certificate.write_text(json.dumps(dict(archiveManifestPins={'fixture': hashlib.sha256(manifest.read_bytes()).hexdigest()},
            physicalBindings={str(self.repo / original): dict(sha256=SHA, size=len(RAW), kind='current-regular')},
            productTrees=[], products={})))
        with mock.patch.multiple(lru, ROOT=self.repo, ARCHIVE=self.archive, CERTIFICATE=certificate,
                                 CERT_SHA=hashlib.sha256(certificate.read_bytes()).hexdigest(),
                                 VERIFIER_SHA=hashlib.sha256(verifier.read_bytes()).hexdigest()):
            self.assertEqual(len(lru.verify([])['archivedBindings']), 1)
            path.write_bytes(lzma.compress(b'wrong identity'))
            with self.assertRaisesRegex(ValueError, 'reconstructed byte integrity'):
                lru.verify([])


if __name__ == '__main__':
    unittest.main()
