"""Publication controls retain fresh owned fixtures; no temporary-tree cleanup."""
import ast
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.dont_write_bytecode = True
import run as producer


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = producer.BASE / ('publication-controls-' + uuid4().hex)
        cls.root.mkdir(parents=True)
        print('retained publication fixtures:', cls.root, flush=True)

    def setUp(self):
        self.out = self.root / self._testMethodName
        self.out.mkdir()

    def test_real_invalid_scope_never_publishes(self):
        q = dict(status='FINITE_NATIVE_PATHEMBED_PASS', objects=112, definitions=2)
        with self.assertRaisesRegex(ValueError, 'scope'):
            producer.publish(q, self.out)
        self.assertFalse((self.out / 'report.json').exists())

    def test_final_audit_failure_never_publishes(self):
        with patch.object(producer, 'validate', side_effect=ValueError('link closure')):
            with self.assertRaisesRegex(ValueError, 'link closure'):
                producer.publish({'status': 'FINITE_NATIVE_PATHEMBED_PASS'}, self.out)
        self.assertFalse((self.out / 'report.json').exists())

    def test_success_publishes_only_after_validation(self):
        q = {'status': 'FINITE_NATIVE_PATHEMBED_PASS'}
        def accepted(value, out):
            self.assertEqual(value, q)
            self.assertFalse((out / 'report.json').exists())
        with patch.object(producer, 'validate', side_effect=accepted) as audit:
            producer.publish(q, self.out)
        audit.assert_called_once_with(q, self.out)
        self.assertEqual(json.loads((self.out / 'report.json').read_text()), q)

    def test_existing_report_is_not_overwritten(self):
        path = self.out / 'report.json'
        path.write_bytes(b'owned pre-existing report\n')
        with patch.object(producer, 'validate'):
            with self.assertRaises(FileExistsError):
                producer.publish({}, self.out)
        self.assertEqual(path.read_bytes(), b'owned pre-existing report\n')

    def test_frozen_former_implementation_exposes_false_pass(self):
        # Exercise the actual former publication statement, not a recreated
        # alternate implementation, against the same rejected scope record.
        frozen = producer.BASE / 'acquisition-r3/snapshots/source/lab/path-embed/run.py'
        if not frozen.is_file():
            self.skipTest('historical r3 acquisition is required for this regression control')
        tree = ast.parse(frozen.read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        statements = function.body[-3:-1]
        self.assertEqual([n.value.func.id for n in statements], ['dump', 'validate'])
        code = compile(ast.Module(body=statements, type_ignores=[]), str(frozen), 'exec')
        q = dict(status='FINITE_NATIVE_PATHEMBED_PASS', objects=112, definitions=2)
        with self.assertRaisesRegex(ValueError, 'scope'):
            exec(code, dict(dump=producer.dump, validate=producer.validate, q=q, out=self.out))
        self.assertEqual(json.loads((self.out / 'report.json').read_text()), q)


if __name__ == '__main__':
    unittest.main()
