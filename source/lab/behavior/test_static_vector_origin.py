"""Pure receipt validation with known-bad clock/phase/argv fixtures."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('_sv_reader_test', Path(__file__).with_name('static_vector_origin.py'))
origin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(origin)
G = origin.ad.build_root()


class ReaderTests(unittest.TestCase):
    def fixture(self, root, role='candidate'):
        start = dt.datetime(2026, 10, 29, 10, 27, tzinfo=dt.timezone.utc)
        plan = dict(buildRoot=str(root), sdk='/SDK', python='/python', tools={'CMAKE_EXECUTABLE': '/cmake'},
                    createdUTC=start.isoformat(), witness={'files': {}, 'aliases': {}})
        side = root / role
        side.mkdir()
        env = origin.builder.environment(plan, role)
        for i, phase in enumerate(origin.builder.phases(role)):
            argv = origin.builder.phase_command(plan, role, phase)
            command = dict(argv=argv, cwd=str(origin.ROOT / 'source'), environment=env,
                startedUTC=(start + dt.timedelta(seconds=i * 3)).isoformat(),
                inputsSha256=origin.code.sha(json.dumps(plan['witness'], sort_keys=True).encode()))
            receipt = dict(argv=argv, returncode=0, failure=None, pid=123, pgid=123, reaped=True,
                elapsedSeconds=1, finishedUTC=(start + dt.timedelta(seconds=i * 3 + 1)).isoformat())
            (side / (phase + '.command.json')).write_text(json.dumps(command))
            (side / (phase + '.receipt.json')).write_text(json.dumps(receipt))
            for suffix in ('.stdout', '.stderr'):
                (side / (phase + suffix)).write_text('')
        record = dict(phases=list(origin.builder.phases(role)), environment=env,
                      archive=dict(sealedUTC=(start + dt.timedelta(seconds=11)).isoformat()) if role == 'candidate' else None)
        return plan, record

    def mutate(self, path, key, value):
        record = json.loads(path.read_text())
        record[key] = value
        path.write_text(json.dumps(record))

    def test_seven_phase_candidate_positive_and_postlink_seal_negative(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            plan, record = self.fixture(Path(temp))
            self.assertEqual(len(origin.phase_bindings(plan, 'candidate', record)), 7)
            record['archive']['sealedUTC'] = '2026-10-29T10:40:00+00:00'
            with self.assertRaises(ValueError):
                origin.phase_bindings(plan, 'candidate', record)

    def test_six_phase_reference_and_original_clock_negative(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            plan, record = self.fixture(root, 'reference')
            self.assertEqual(len(origin.phase_bindings(plan, 'reference', record)), 6)
            self.mutate(root / 'reference/provenance-verify.receipt.json', 'finishedUTC', '2026-10-29T11:03:00+00:00')
            with self.assertRaises(ValueError):
                origin.phase_bindings(plan, 'reference', record)

    def test_wrong_argv_and_unreaped_pgid_detected(self):
        for key, value, suffix in [('argv', ['wrong'], '.command.json'), ('reaped', False, '.receipt.json')]:
            with self.subTest(key=key), tempfile.TemporaryDirectory(dir=G) as temp:
                root = Path(temp)
                plan, record = self.fixture(root)
                self.mutate(root / ('candidate/configure' + suffix), key, value)
                with self.assertRaises(ValueError):
                    origin.phase_bindings(plan, 'candidate', record)

    def test_missing_phase_not_silently_old_six(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            plan, record = self.fixture(Path(temp))
            record['phases'].remove('cargo')
            with self.assertRaises(ValueError):
                origin.phase_bindings(plan, 'candidate', record)

    def test_numeric_dependency_ids_are_type_exact_not_bool_or_float(self):
        expected = dict(schema='static-vector-compile-dependencies-v2',
                        files=[dict(path='/header', sha256='0' * 64, size=1)],
                        objects={'/object': dict(dependency_ids=[0])})
        self.assertTrue(origin.same_json(json.loads(json.dumps(expected)), expected))
        for value in (False, 0.0):
            actual = json.loads(json.dumps(expected))
            actual['objects']['/object']['dependency_ids'][0] = value
            self.assertEqual(actual, expected)  # Demonstrate Python's coercing equality.
            self.assertFalse(origin.same_json(actual, expected))

    def test_physical_binding_size_cannot_be_a_boolean(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            path = Path(temp) / 'one'
            path.write_bytes(b'x')
            record = origin.identity(path)
            self.assertEqual(origin.bound(record, path), record)
            record['size'] = True
            with self.assertRaises(ValueError):
                origin.bound(record, path)

    def test_wrong_path_and_alias_fail_before_any_native_work(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            path = root / 'starbound'
            path.write_text('not a native app')
            with self.assertRaises(ValueError):
                origin.validate_game_origin(path, {})
            alias = root / 'alias'
            alias.symlink_to(path)
            with self.assertRaises(ValueError):
                origin.validate_game_origin(alias, {})


if __name__ == '__main__':
    unittest.main()
