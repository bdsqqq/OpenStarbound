"""Portable non-writing drift checks; no native build/execution."""
import json
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
import inventory as inv


class Inventory(unittest.TestCase):
    def test_complete_real_source_boundary(self):
        q = inv.generate()
        self.assertEqual(len(q['definitions']), 58)
        self.assertEqual(q['counts'], {'member': 46, 'string-bridge': 4, 'free': 7, 'formatter': 1})
        signatures = [r['signature'] for r in q['definitions']]
        self.assertEqual(len(set(signatures)), 58)
        self.assertTrue(any('otherOffset' in s and 'otherLen' in s for s in signatures))
        self.assertTrue(any('operator[]' in s for s in signatures))
        self.assertTrue(any('formatter<Star::StringView>' in s for s in signatures))
        inv.check()

    def test_declarations_literals_comments_nested_bodies(self):
        source = '''// StringView::notAFunction() {}
"StringView::literal() {}";
StringView::StringView();
StringView::StringView() {}
bool StringView::empty() const {
 auto local = [] { return 7; };
 return local() == 0;
}
bool operator==(StringView a, StringView b) { return true; }
'''
        q = inv.definitions(source)
        self.assertEqual(len(q), 3)
        self.assertEqual([r['kind'] for r in q], ['member', 'member', 'free'])
        self.assertEqual(q[1]['endLine'], 8)

    def test_missing_corrupt_and_input_drift_do_not_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'map.json'
            with self.assertRaisesRegex(ValueError, 'missing/stale'):
                inv.check(p)
            self.assertFalse(p.exists())
            good = json.dumps(inv.generate(), indent=2) + '\n'
            p.write_text(good)
            inv.check(p)
            p.write_text(good.replace('"id": 1,', '"id": 999,', 1))
            before = p.read_bytes()
            with self.assertRaisesRegex(ValueError, 'missing/stale'):
                inv.check(p)
            self.assertEqual(p.read_bytes(), before)
            p.write_text(good)
            changed = inv.generate()
            changed['sources']['source/core/StarStringView.hpp'] = '0' * 64
            with patch.object(inv, 'generate', return_value=changed):
                with self.assertRaisesRegex(ValueError, 'missing/stale'):
                    inv.check(p)
            self.assertEqual(p.read_text(), good)

    def test_cli_drift_gate_in_isolated_source_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lab = root / 'source/lab/string-view'
            core = root / 'source/core'
            lab.mkdir(parents=True)
            core.mkdir(parents=True)
            shutil.copy2(inv.HERE / 'inventory.py', lab / 'inventory.py')
            for p in (inv.CPP, inv.HPP):
                shutil.copy2(p, core / p.name)
            command = [sys.executable, '-B', str(lab / 'inventory.py')]
            def run(mode):
                return subprocess.run([*command, mode], capture_output=True)
            self.assertNotEqual(run('--check').returncode, 0)
            self.assertFalse((lab / 'source-map.json').exists())
            self.assertEqual(run('--write').returncode, 0)
            good = (lab / 'source-map.json').read_bytes()
            self.assertEqual(run('--write').returncode, 0)
            self.assertEqual(good, (lab / 'source-map.json').read_bytes())
            (lab / 'source-map.json').write_bytes(good + b' ')
            self.assertNotEqual(run('--check').returncode, 0)
            self.assertEqual((lab / 'source-map.json').read_bytes(), good + b' ')
            (lab / 'source-map.json').write_bytes(good)
            with (core / 'StarStringView.hpp').open('a') as f:
                f.write('\n// isolated input drift\n')
            self.assertNotEqual(run('--check').returncode, 0)
            self.assertEqual((lab / 'source-map.json').read_bytes(), good)

    def test_generation_is_deterministic_and_source_change_detected(self):
        first = inv.generate()
        self.assertEqual(first, inv.generate())
        altered = inv.generate(inv.CPP.read_bytes() + b'\n// known source drift\n')
        self.assertNotEqual(first['sources'], altered['sources'])
        self.assertEqual(first['definitions'], altered['definitions'])
        with self.assertRaisesRegex(ValueError, 'compiled boundary changed'):
            inv.generate(inv.CPP.read_bytes() + b'\nbool StringView::newMember() { return true; }\n')


if __name__ == '__main__':
    unittest.main()
