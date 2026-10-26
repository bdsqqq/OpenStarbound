"""Isolated receipt corruption controls; no native command or fixture is rerun."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import run

OUT = run.BASE / 'parent-final-r1'


@unittest.skipUnless((OUT / 'report.json').exists(), 'host-specific native receipt not present')
class Receipts(unittest.TestCase):
    def reject(self, mutate, diagnostic):
        q = json.loads((OUT / 'report.json').read_text())
        mutate(q)
        original = Path.read_text
        def read(path, *args, **kwargs):
            return json.dumps(q) if path == OUT / 'report.json' else original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', read):
            with self.assertRaisesRegex(ValueError, diagnostic):
                run.verify(OUT)

    def test_scope_bool_rejected(self):
        self.reject(lambda q: q.update(cases=True), 'finite scope')

    def test_unknown_status_rejected(self):
        self.reject(lambda q: q.update(status='RUST_PASS'), 'status')

    def test_artifact_binding_rejected(self):
        def mutate(q):
            q['artifacts'][str(OUT / 'native.stdout')] = '0' * 64
        self.reject(mutate, 'drift')

    def test_compiled_symbol_removal_rejected(self):
        self.reject(lambda q: q['compiled_symbols']['member'].pop(), 'compiled definitions')


if __name__ == '__main__':
    unittest.main()
