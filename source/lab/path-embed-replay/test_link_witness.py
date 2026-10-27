"""Preflight rejects output escape before invoking any compiler or linker."""
from pathlib import Path
import unittest
from uuid import uuid4
from link_witness import observe


class LinkWitnessPreflightTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(__file__).resolve().parents[3] / 'build/path-embed-link-witness-r1' / ('preflight-' + uuid4().hex)
        self.base.mkdir(parents=True)
        self.out = self.base / 'fresh'
        self.argv = ['/not-invoked-compiler', '-o', str(self.out / 'native'),
                     '-Wl,-map,' + str(self.out / 'native.map'), '-Wl,-t,-trace_implicit_libraries']

    def call(self):
        return observe(self.argv, self.base, self.out, '/not-read-sdk', '/not-read-sdk')

    def test_output_escape_rejected_without_creating_directory(self):
        self.argv[2] = str(self.base / 'outside-native')
        with self.assertRaisesRegex(ValueError, 'fresh output'):
            self.call()
        self.assertFalse(self.out.exists())

    def test_existing_output_tree_preserved(self):
        self.out.mkdir();sentinel = self.out / 'sentinel';sentinel.write_bytes(b'preserve')
        with self.assertRaisesRegex(ValueError, 'fresh non-symlink'):
            self.call()
        self.assertEqual(sentinel.read_bytes(), b'preserve')

    def test_symlink_output_rejected(self):
        target = self.base / 'target';target.mkdir();self.out.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'non-symlink'):
            self.call()
        self.assertEqual(list(target.iterdir()), [])

    def test_missing_trace_and_ambiguous_output_rejected(self):
        for changed in [self.argv[:-1], self.argv + ['-o', str(self.base / 'other')]]:
            self.argv = changed
            with self.assertRaises(ValueError):
                self.call()
            self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
