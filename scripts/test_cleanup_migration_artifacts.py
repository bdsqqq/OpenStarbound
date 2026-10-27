import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('cleanup', Path(__file__).with_name('cleanup-migration-artifacts.py'))
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


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
            with self.assertRaises((OSError, EOFError)):
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
            with self.assertRaises(OSError):
                cleanup.archive(repo, ['build/old'], arc, 'corrupt', 1)
            self.assertEqual((tree / 'a').read_bytes(), data)


if __name__ == '__main__':
    unittest.main()
