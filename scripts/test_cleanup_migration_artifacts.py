import gzip
import importlib.util
import json
import os
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('cleanup', Path(__file__).with_name('cleanup-migration-artifacts.py'))
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class AllocationTests(unittest.TestCase):
    @staticmethod
    def reference(root):
        total, seen = 0, set()
        for parent, dirs, files in os.walk(root, followlinks=False):
            paths = [Path(parent)] + [Path(parent) / name for name in files]
            paths += [Path(parent) / name for name in dirs if (Path(parent) / name).is_symlink()]
            for path in paths:
                info = path.lstat()
                key = (info.st_dev, info.st_ino)
                if key not in seen:
                    seen.add(key)
                    total += info.st_blocks * 512
        return total

    def test_matches_reference_sparse_hardlinks_symlinks_and_fifo(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp).resolve()
            root = parent / 'tree'
            (root / 'nested').mkdir(parents=True)
            data = root / 'nested/data'
            data.write_bytes(b'x' * 65536)
            os.link(data, root / 'hardlink')
            sparse = root / 'sparse'
            with sparse.open('wb') as stream:
                stream.seek(4 * 1024**2)
                stream.write(b'x')
            outside = parent / 'outside'
            outside.mkdir()
            (outside / 'not-counted').write_bytes(b'y' * 262144)
            (root / 'directory-alias').symlink_to(outside, target_is_directory=True)
            (root / 'broken-alias').symlink_to(parent / 'missing')
            os.mkfifo(root / 'pipe')
            expected = self.reference(root)
            self.assertEqual(cleanup.allocated_bytes(root), expected)
            self.assertNotEqual(expected, 0)
            # An unsafe zero counter is rejected by this same fixture oracle.
            with self.assertRaises(AssertionError):
                self.assertEqual(0, expected)

    def test_unreadable_nested_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            denied = root / 'denied'
            denied.mkdir()
            original = os.scandir
            def scan(path):
                if os.fspath(path) == str(denied):
                    raise PermissionError('isolated unreadable allocation entry')
                return original(path)
            with patch.object(cleanup.os, 'scandir', side_effect=scan):
                with self.assertRaises(PermissionError):
                    cleanup.allocated_bytes(root)

    def test_root_alias_or_nondirectory_rejected_absence_is_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            alias = root / 'alias'
            alias.symlink_to(root, target_is_directory=True)
            (root / 'child').mkdir()
            file = root / 'file'
            file.write_text('not a traversal root')
            for path in (alias, alias / 'child', alias / 'missing', file):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    cleanup.allocated_bytes(path)
            self.assertEqual(cleanup.allocated_bytes(root / 'missing'), 0)


class CleanupTests(unittest.TestCase):
    def test_deduplicates_verifies_and_preserves_small_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            tree = repo / 'build/old'
            tree.mkdir(parents=True)
            payload = b'original failed output\x00\xff' * 100
            (tree / 'a').write_bytes(payload)
            (tree / 'b').write_bytes(payload)
            (tree / 'report.json').write_text('{}')
            outside = repo / 'save'
            outside.write_bytes(payload)
            (tree / 'link').symlink_to(outside)
            arc = repo / 'build/migration-evidence-archive'
            cleanup.archive(repo, ['build/old'], arc, 'test', 100)
            m = json.loads((arc / 'runs/test/manifest.json').read_bytes())
            self.assertEqual(m['unique_blobs'], 1)
            self.assertEqual(m['removed_bytes'], 2 * len(payload))
            self.assertFalse((tree / 'a').exists())
            self.assertTrue((tree / 'report.json').exists())
            self.assertEqual(outside.read_bytes(), payload)
            self.assertTrue((tree / 'link').is_symlink())
            cleanup.verify(arc, arc / 'runs/test/manifest.json')
            blob = next((arc / 'blobs').rglob('*.gz'))
            with gzip.open(blob) as stream:
                self.assertEqual(stream.read(), payload)
            blob.write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'suffix/magic mismatch'):
                cleanup.verify(arc, arc / 'runs/test/manifest.json')

    def test_rejects_outside_alias_overlap_and_preserves_external_hardlinks(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            tree = repo / 'build/old'
            tree.mkdir(parents=True)
            (repo / 'build/alias').symlink_to(tree, target_is_directory=True)
            for root in ['storage', '../outside', str(tree), 'build/alias', 'build/migration-evidence-archive']:
                with self.assertRaises(ValueError):
                    cleanup.validate_root(repo, root)
            (tree / 'a').write_bytes(b'xxx')
            os.link(tree / 'a', tree / 'b')
            outside = repo / 'save'
            os.link(tree / 'a', outside)
            with self.assertRaises(ValueError):
                cleanup.archive(repo, ['build/old', 'build/old'], repo / 'build/migration-evidence-archive', 'overlap', 1)
            self.assertEqual((tree / 'a').read_bytes(), b'xxx')
            cleanup.archive(repo, ['build/old'], repo / 'build/migration-evidence-archive', 'hardlink', 1)
            self.assertFalse((tree / 'a').exists())
            self.assertFalse((tree / 'b').exists())
            self.assertEqual(outside.read_bytes(), b'xxx')

    def test_zero_byte_logs_archive_and_budget_rejects_growth(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            tree = repo / 'build/old'
            tree.mkdir(parents=True)
            (tree / 'empty.log').write_bytes(b'')
            (tree / 'data').write_bytes(b'x' * 8192)
            self.assertFalse(cleanup.budget(repo, 0, 0))
            arc = repo / 'build/migration-evidence-archive'
            cleanup.archive(repo, ['build/old'], arc, 'empty', 0)
            manifest = json.loads((arc / 'runs/empty/manifest.json').read_bytes())
            self.assertEqual(len(manifest['entries']), 2)
            self.assertFalse((tree / 'empty.log').exists())
            cleanup.verify(arc, arc / 'runs/empty/manifest.json')
            self.assertTrue(cleanup.budget(repo, 1, 1))
            self.assertFalse(cleanup.budget(repo, 1, 0))

    def test_reuses_existing_xz_and_verifies_before_pruning(self):
        import hashlib
        import lzma
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            tree = repo / 'build/old'
            tree.mkdir(parents=True)
            data = b'previously archived raw bytes' * 100
            (tree / 'a').write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            arc = repo / 'build/migration-evidence-archive'
            blob = arc / 'blobs' / sha[:2] / (sha + '.xz')
            blob.parent.mkdir(parents=True)
            blob.write_bytes(lzma.compress(data))
            before = blob.read_bytes()
            cleanup.archive(repo, ['build/old'], arc, 'reuse-xz', 1)
            self.assertFalse((tree / 'a').exists())
            self.assertFalse(blob.with_suffix('.gz').exists())
            self.assertEqual(blob.read_bytes(), before)
            cleanup.verify(arc, arc / 'runs/reuse-xz/manifest.json')
            with self.assertRaisesRegex(ValueError, 'missing/aliased'):
                cleanup.plan_repack_blob(repo, 'build/migration-evidence-archive/runs/reuse-xz/manifest.json', sha)

    def test_xz_corruption_or_codec_ambiguity_retains_original(self):
        import hashlib
        import lzma
        for mode in ('wrong-raw', 'ambiguous'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                repo = Path(temp).resolve()
                tree = repo / 'build/old'
                tree.mkdir(parents=True)
                data = b'original must survive'
                (tree / 'a').write_bytes(data)
                sha = hashlib.sha256(data).hexdigest()
                arc = repo / 'build/migration-evidence-archive'
                blob = arc / 'blobs' / sha[:2] / (sha + '.xz')
                blob.parent.mkdir(parents=True)
                blob.write_bytes(lzma.compress(data if mode == 'ambiguous' else b'wrong'))
                if mode == 'ambiguous':
                    blob.with_suffix('.gz').write_bytes(gzip.compress(data))
                with self.assertRaises(ValueError):
                    cleanup.archive(repo, ['build/old'], arc, 'reject', 1)
                self.assertEqual((tree / 'a').read_bytes(), data)

    def test_corrupt_existing_blob_never_prunes_new_input(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            tree = repo / 'build/old'
            tree.mkdir(parents=True)
            data = b'must not be lost'
            (tree / 'a').write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            arc = repo / 'build/migration-evidence-archive'
            blob = arc / 'blobs' / sha[:2] / (sha + '.gz')
            blob.parent.mkdir(parents=True)
            blob.write_bytes(b'invalid')
            with self.assertRaisesRegex(ValueError, 'suffix/magic mismatch'):
                cleanup.archive(repo, ['build/old'], arc, 'corrupt', 1)
            self.assertEqual((tree / 'a').read_bytes(), data)


class RepackTests(unittest.TestCase):
    def fixture(self, repo):
        tree = repo / 'build/old'
        tree.mkdir(parents=True)
        (tree / 'payload').write_bytes(b'repeated archived bytes\x00\xff' * 100000)
        arc = repo / 'build/migration-evidence-archive'
        cleanup.archive(repo, ['build/old'], arc, 'repack-test', 0)
        manifest = arc / 'runs/repack-test/manifest.json'
        sha = json.loads(manifest.read_bytes())['entries'][0]['sha256']
        blob = arc / 'blobs' / sha[:2] / (sha + '.gz')
        row = cleanup.plan_repack_blob(repo, str(manifest.relative_to(repo)), sha)
        self.assertIsNotNone(row)
        return arc, manifest, blob, row

    def test_repack_preserves_raw_manifest_and_proves_old_encoding_reconstructable(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            arc, manifest, blob, row = self.fixture(repo)
            before_manifest = manifest.read_bytes()
            old = blob.read_bytes()
            result = cleanup.repack_blob(repo, row)
            self.assertLess(blob.stat().st_size, len(old))
            self.assertEqual(manifest.read_bytes(), before_manifest)
            cleanup.verify(arc, manifest)
            regenerated = cleanup.EncodedDigest()
            cleanup._repack_stream(blob, row['sha256'], row['rawSize'], 1, regenerated)
            import hashlib
            self.assertEqual(regenerated.hash.hexdigest(), hashlib.sha256(old).hexdigest())
            self.assertEqual(result['status'], 'RAW_RECONSTRUCTED_BEFORE_ATOMIC_REPACK')
            self.assertNotEqual(result['fingerprintAfter'], row['fingerprint'])
            self.assertLessEqual(result['temporaryPeakAllocatedBytes'], cleanup.REPACK_TEMPORARY_RESERVATION_BYTES)

    def test_wrong_temporary_hash_never_replaces_original(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            _, _, blob, row = self.fixture(repo)
            before = blob.read_bytes()
            row['newEncodedSha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'temporary encoded bytes mismatch'):
                cleanup.repack_blob(repo, row)
            self.assertEqual(blob.read_bytes(), before)
            self.assertTrue(blob.with_suffix('.repack.tmp').exists())

    def test_manifest_old_encoding_and_codec_drift_reject_before_temp(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            _, _, blob, row = self.fixture(repo)
            before = blob.read_bytes()
            for key in ('manifestSha256', 'oldEncodedSha256', 'python', 'zlib'):
                bad = dict(row, **{key: 'wrong'})
                with self.assertRaisesRegex(ValueError, 'plan/input/codec drift'):
                    cleanup.repack_blob(repo, bad)
                self.assertFalse(blob.with_suffix('.repack.tmp').exists())
                self.assertEqual(blob.read_bytes(), before)

    def test_corrupt_payload_and_manifest_size_reject_without_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            _, manifest, blob, row = self.fixture(repo)
            data = json.loads(manifest.read_bytes())
            data['entries'][0]['size'] -= 1
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'exceeds manifest size'):
                cleanup.plan_repack_blob(repo, str(manifest.relative_to(repo)), row['sha256'])
            blob.write_bytes(b'corrupt')
            with self.assertRaises(OSError):
                cleanup.plan_repack_blob(repo, str(manifest.relative_to(repo)), row['sha256'])
            self.assertEqual(blob.read_bytes(), b'corrupt')

    def test_path_alias_traversal_and_external_hardlinks_rejected(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            _, manifest, blob, row = self.fixture(repo)
            for name in ('../manifest.json', str(manifest), 'storage/manifest.json'):
                with self.assertRaises(ValueError):
                    cleanup.plan_repack_blob(repo, name, row['sha256'])
            alias = manifest.with_name('alias.json')
            alias.symlink_to(manifest)
            with self.assertRaises(ValueError):
                cleanup.plan_repack_blob(repo, str(alias.relative_to(repo)), row['sha256'])
            os.link(blob, repo / 'external')
            with self.assertRaisesRegex(ValueError, 'external hardlink'):
                cleanup.repack_blob(repo, row)

    def test_temporary_capacity_and_oversize_plan_reject_without_writing(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            _, _, blob, row = self.fixture(repo)
            before = blob.read_bytes()
            with patch.object(cleanup, 'allocated_bytes', return_value=16 * 1024**3):
                with self.assertRaisesRegex(ValueError, 'fixed archive cap'):
                    cleanup.repack_blob(repo, row)
            bad = dict(row, newEncodedSize=20 * cleanup.CHUNK)
            with self.assertRaises(ValueError):
                cleanup.repack_blob(repo, bad)
            self.assertFalse(blob.with_suffix('.repack.tmp').exists())
            self.assertEqual(blob.read_bytes(), before)

    def test_encoded_size_does_not_admit_insufficient_physical_scratch(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            _, _, blob, row = self.fixture(repo)
            before = blob.read_bytes()
            # The old encoded-size+16KiB assumption would admit this state.
            with patch.object(cleanup, 'allocated_bytes', return_value=16 * 1024**3 - 1024**2):
                with self.assertRaisesRegex(ValueError, 'fixed archive cap'):
                    cleanup.repack_blob(repo, row)
            self.assertFalse(blob.with_suffix('.repack.tmp').exists())
            self.assertEqual(blob.read_bytes(), before)

    def test_actual_physical_scratch_overrun_retains_original(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            _, _, blob, row = self.fixture(repo)
            before = blob.read_bytes()
            allocation = SimpleNamespace(st_blocks=cleanup.REPACK_TEMPORARY_RESERVATION_BYTES // 512 + 1)
            with patch.object(cleanup.os, 'fstat', return_value=allocation):
                with self.assertRaisesRegex(ValueError, 'physical allocation exceeds reservation'):
                    cleanup.repack_blob(repo, row)
            self.assertEqual(blob.read_bytes(), before)
            self.assertTrue(blob.with_suffix('.repack.tmp').exists())

    def test_understated_size_is_enforced_before_write_and_original_is_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            _, _, blob, row = self.fixture(repo)
            original = blob.read_bytes()
            row['newEncodedSize'] = 1
            with self.assertRaisesRegex(ValueError, 'exceeds admitted size'):
                cleanup.repack_blob(repo, row)
            self.assertLessEqual(blob.with_suffix('.repack.tmp').stat().st_size, 1)
            self.assertEqual(blob.read_bytes(), original)

    def test_forged_noncanonical_old_encoding_rejected_at_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            _, _, blob, row = self.fixture(repo)
            with gzip.open(blob, 'rb') as source:
                payload = source.read()
            with blob.open('wb') as stream:
                with gzip.GzipFile(filename='', mode='wb', fileobj=stream, compresslevel=1, mtime=17) as out:
                    out.write(payload)
            original = blob.read_bytes()
            row['fingerprint'] = cleanup.fingerprint(blob)
            row['oldEncodedSha256'], row['oldEncodedSize'] = cleanup.file_digest(blob)
            with self.assertRaisesRegex(ValueError, 'not exactly reconstructable'):
                cleanup.repack_blob(repo, row)
            self.assertFalse(blob.with_suffix('.repack.tmp').exists())
            self.assertEqual(blob.read_bytes(), original)

    def test_unfinished_manifest_and_wrong_raw_hash_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve()
            _, manifest, blob, row = self.fixture(repo)
            data = json.loads(manifest.read_bytes())
            data['status'] = 'PLANNED_NOT_PRUNED'
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'only completed'):
                cleanup.plan_repack_blob(repo, str(manifest.relative_to(repo)), row['sha256'])
            with self.assertRaisesRegex(ValueError, 'raw payload mismatch'):
                cleanup._repack_stream(blob, '0' * 64, row['rawSize'], 9, cleanup.EncodedDigest())


if __name__ == '__main__':
    unittest.main()
