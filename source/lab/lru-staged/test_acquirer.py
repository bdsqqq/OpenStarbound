"""Recovery regressions: retain failed process facts without granting admission."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

import acquirer as a
import native_plan as np

BASE = Path(__file__).resolve().parents[3] / 'build/lru-staged-recovery-r1/tests'
PYTHON = os.fsencode(os.path.realpath(sys.executable))


class AcquirerRecoveryTests(unittest.TestCase):
    def fixture(self, script):
        BASE.mkdir(parents=True, exist_ok=True)
        root = os.fsencode(tempfile.mkdtemp(prefix='case-', dir=BASE))
        for name in (b'work', b'home', b'tmp'):
            os.mkdir(root+b'/'+name)
        program = root+b'/program.py'
        a.write(program, script)
        product = root+b'/object.o'
        stage = np.Stage('fixture', (PYTHON, b'-B', program), (PYTHON, program),
                         (product, root+b'/receipt.typed', root+b'/certificate.typed'),
                         tuple(root+b'/'+name for name in (b'stdout', b'stderr', b'stdin')))
        plan = np.Plan(root, stage.inputs, (stage,))
        command = {'stage_id': 'fixture', 'cwd': root+b'/work',
                   'env': {b'HOME': root+b'/home', b'TMPDIR': root+b'/tmp'},
                   'stdin': b'', 'timeout_ms': 5000, 'failure_action': 'stop-preserve',
                   'validator': 'literal-v1',
                   'rules': {'stdout': b'ok\n', 'stderr': b'',
                             'products': {product: b'object'}}}
        return root, stage, a.contract(plan, (command,), (PYTHON,))

    def test_missing_product_keeps_failed_pid_and_status(self):
        root, stage, frozen = self.fixture(b'import sys\nsys.exit(7)\n')
        with self.assertRaises(a.Rejected):
            a.execute(frozen)
        record = a.load(a.meta(stage)[0])
        self.assertEqual(record['exit_code'], 7)
        self.assertIs(type(record['pid']), int)
        self.assertGreater(record['pid'], 0)
        self.assertIs(record['reaped'], True)
        self.assertIs(record['group_gone'], True)
        self.assertEqual(record['artifacts'][root+b'/object.o']['unavailable'], 'FileNotFoundError')
        self.assertFalse(os.path.lexists(a.meta(stage)[1]))

    def test_zero_exit_missing_product_still_has_no_certificate(self):
        _, stage, frozen = self.fixture(b'print("ok")\n')
        with self.assertRaises(a.Rejected):
            a.execute(frozen)
        self.assertEqual(a.load(a.meta(stage)[0])['exit_code'], 0)
        self.assertFalse(os.path.lexists(a.meta(stage)[1]))

    def test_changed_command_rejected_before_process(self):
        _, stage, frozen = self.fixture(b'print("ok")\n')
        frozen['commands'][0]['stdin'] = b'changed'
        with self.assertRaisesRegex(a.Rejected, 'contract field drift'):
            a.execute(frozen)
        self.assertFalse(os.path.lexists(a.meta(stage)[0]))

    def test_valid_ascii_product_and_readonly_reconstruction(self):
        script = b'with open("../object.o","xb") as f:f.write(b"object")\nprint("ok")\n'
        _, stage, frozen = self.fixture(script)
        self.assertEqual(a.execute(frozen)['stages'], ('fixture',))
        self.assertEqual(a.reconstruct(frozen)['stages'], ('fixture',))
        self.assertTrue(os.path.isfile(a.meta(stage)[1]))


if __name__ == '__main__':
    unittest.main()
