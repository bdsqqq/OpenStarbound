"""SYNTHETIC byte receipts only: no native admission, process or game claim."""
import datetime as dt
import importlib.util
import json
import sys
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
        python = str(Path(sys.executable).resolve(strict=True))
        helper = origin.identity(origin.builder.GUARDIAN)
        plan = dict(buildRoot=str(root), sdk='/SDK', python=python, tools={'CMAKE_EXECUTABLE': '/cmake'},
                    createdUTC=start.isoformat(), witness={'files': {python: origin.ad.sha(python),
                        helper['path']: helper['sha256']}, 'aliases': {python: python}})
        side = root / role
        side.mkdir()
        env = origin.builder.environment(plan, role)
        for i, phase in enumerate(origin.builder.phases(role)):
            argv = origin.builder.phase_command(plan, role, phase)
            launcher = dict(python=origin.identity(python), guardian=helper)
            token = 'ab' * 32
            launch = [python, '-B', helper['path'], '--status-fd', '4', '--token', token,
                '--source-sha', helper['sha256'], '--environment-json', json.dumps(env, sort_keys=True), '--'] + argv
            status = dict(schema=origin.builder.GUARDIAN_SCHEMA, token=token, sourceSha256=helper['sha256'],
                guardianPID=123, guardianPGID=123, guardianSID=123, commandPID=124,
                returncode=0, commandReaped=True, launchError=None)
            limits = origin.builder.phase_output_limits(phase)
            command = dict(argv=argv, launchArgv=launch, launcher=launcher, phase=phase, outputLimits=limits,
                guardianSchema=origin.builder.GUARDIAN_SCHEMA, statusBytes=origin.builder.STATUS_BYTES,
                cwd=str(origin.ROOT / 'source'), environment=env,
                startedUTC=(start + dt.timedelta(seconds=i * 3)).isoformat(),
                inputsSha256=origin.code.sha(json.dumps(plan['witness'], sort_keys=True).encode()))
            (side / (phase + '.command.json')).write_text(json.dumps(command))
            receipt = dict(argv=argv, launchArgv=launch, launcher=launcher, phase=phase, outputLimits=limits,
                command=origin.identity(side / (phase + '.command.json')), guardianStatus=status,
                guardianStatusBytes=len(json.dumps(status, sort_keys=True, separators=(',', ':')).encode()),
                guardianStatusEOF=True, commandPID=124, commandReaped=True, guardianReturncode=-9,
                guardianReaped=True, reapedScope='DIRECT_GUARDIAN_ONLY', cleanupFailure=None,
                outputComplete=True, streams={name: dict(bytesRead=0, bytesWritten=0, eof=True, overflow=None)
                    for name in ('stdout', 'stderr')},
                returncode=0, failure=None, pid=123, pgid=123, reaped=True,
                elapsedSeconds=1, finishedUTC=(start + dt.timedelta(seconds=i * 3 + 1)).isoformat())
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

    def test_duplicate_receipt_completion_key_rejected(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            plan, record = self.fixture(root, 'reference')
            path = root / 'reference/configure.receipt.json'
            raw = path.read_text()
            # A last-wins decoder would hide the first incomplete declaration.
            path.write_text('{"outputComplete": false,' + raw[1:])
            with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
                origin.phase_bindings(plan, 'reference', record)

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

    def test_guardian_and_stream_mutations_fail_closed(self):
        cases = [
            ('outputComplete', False), ('cleanupFailure', 'close failed'), ('failure', 'failed'),
            ('pid', True), ('pid', 123.0), ('pid', 125), ('pgid', True), ('pgid', 123.0),
            ('guardianStatus.guardianPID', 125), ('guardianStatus.guardianPGID', True),
            ('guardianStatus.guardianSID', 123.0), ('guardianStatus.commandPID', 123),
            ('guardianStatus.commandPID', 0), ('guardianStatus.commandPID', 2**31),
            ('guardianStatus.commandPID', True), ('guardianStatus.commandPID', 124.0),
            ('commandPID', 125), ('commandPID', True), ('commandPID', 124.0),
            ('guardianStatus.sourceSha256', '0' * 64), ('guardianStatus.token', '0' * 64),
            ('guardianStatus.schema', 'old'), ('guardianStatus.launchError', 'failed'),
            ('guardianStatus.extra', None), ('guardianStatus.commandReaped', False),
            ('guardianStatus.returncode', False), ('guardianStatus.returncode', 0.0),
            ('guardianStatus.returncode', 1), ('returncode', False), ('returncode', 0.0),
            ('guardianStatusEOF', False), ('guardianStatusEOF', 1),
            ('guardianStatusBytes', True), ('guardianStatusBytes', 4097),
            ('launcher.guardian.sha256', '0' * 64), ('launcher.python.size', True),
            ('launchArgv', []), ('command.size', True),
            ('guardianReturncode', 0), ('guardianReturncode', -9.0),
            ('commandReaped', False), ('guardianReaped', False), ('reaped', 1),
            ('reapedScope', 'ALL_DESCENDANTS'), ('phase', 'cargo'),
            ('outputLimits.stdoutBytes', True), ('outputLimits.stderrBytes', 2097152.0),
            ('streams.stdout.bytesRead', True), ('streams.stdout.bytesWritten', 0.0),
            ('streams.stderr.bytesRead', -1), ('streams.stdout.bytesWritten', 1),
            ('streams.stdout.eof', 1), ('streams.stderr.eof', False),
            ('streams.stdout.overflow', {}), ('streams.stderr.extra', 0),
            ('streams.extra', {}), ('elapsedSeconds', True), ('elapsedSeconds', float('inf')),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory(dir=G) as temp:
                root = Path(temp)
                plan, record = self.fixture(root, 'reference')
                path = root / 'reference/configure.receipt.json'
                receipt = json.loads(path.read_text())
                target = receipt
                parts = key.split('.')
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = value
                path.write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):
                    origin.phase_bindings(plan, 'reference', record)

    def test_launch_mutations_even_with_rebound_command_fail(self):
        def change_arg(index, value):
            return lambda row: row['launchArgv'].__setitem__(index, value)
        mutations = [change_arg(0, '/other-python'), change_arg(1, '-I'),
            change_arg(2, '/other-helper'), change_arg(3, '--token'),
            change_arg(4, '2'), change_arg(4, '04'), change_arg(4, '4.0'),
            change_arg(4, True), change_arg(6, 'not-a-nonce'), change_arg(8, '0' * 64),
            change_arg(10, '{}'), change_arg(10, ' '), change_arg(11, '--extra'),
            lambda row: row['launchArgv'].extend(['--token', 'a' * 64]),
            lambda row: row['launcher']['guardian'].__setitem__('size', True),
            lambda row: row['launcher']['python'].__setitem__('sha256', '0' * 64),
            lambda row: row.__setitem__('guardianSchema', 'old'),
            lambda row: row.__setitem__('statusBytes', 4096.0),
            lambda row: row.__setitem__('cwd', '/elsewhere'),
            lambda row: row['environment'].__setitem__('EXTRA', '1'),
            lambda row: row.__setitem__('inputsSha256', '0' * 64),
            lambda row: row.__setitem__('phase', 'cargo'),
            lambda row: row['outputLimits'].__setitem__('readChunkBytes', 65536.0),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index), tempfile.TemporaryDirectory(dir=G) as temp:
                root = Path(temp)
                plan, record = self.fixture(root, 'reference')
                command_path = root / 'reference/configure.command.json'
                receipt_path = root / 'reference/configure.receipt.json'
                command = json.loads(command_path.read_text())
                mutate(command)
                command_path.write_text(json.dumps(command))
                receipt = json.loads(receipt_path.read_text())
                receipt.update(command=origin.identity(command_path), launchArgv=command['launchArgv'],
                               launcher=command['launcher'])
                receipt_path.write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):
                    origin.phase_bindings(plan, 'reference', record)

    def test_raw_size_binding_alias_overflow_and_phase_membership(self):
        for attack in ('bytes', 'large', 'alias', 'overflow', 'extra-command', 'missing-receipt', 'binding'):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory(dir=G) as temp:
                root = Path(temp)
                plan, record = self.fixture(root, 'reference')
                side = root / 'reference'
                raw = side / 'configure.stdout'
                if attack == 'bytes':
                    raw.write_bytes(b'\x00\xff')
                elif attack == 'large':
                    with raw.open('wb') as stream:
                        stream.truncate(origin.builder.phase_output_limits('configure')['stdoutBytes'] + 1)
                elif attack == 'alias':
                    raw.unlink()
                    raw.symlink_to(side / 'configure.stderr')
                elif attack == 'overflow':
                    (side / 'cargo.stderr-overflow.bin').write_bytes(b'overflow')
                elif attack == 'extra-command':
                    (side / 'cargo.command.json').write_text('{}')
                elif attack == 'missing-receipt':
                    (side / 'configure.receipt.json').unlink()
                else:
                    self.mutate(side / 'configure.command.json', 'startedUTC', '2026-10-29T10:27:02+00:00')
                real_identity = origin.identity
                def bounded_identity(path):
                    if attack == 'large' and Path(path) == raw:
                        self.fail('oversized raw stream was hashed before its size check')
                    return real_identity(path)
                with patch.object(origin, 'identity', side_effect=bounded_identity):
                    with self.assertRaises(ValueError):
                        origin.phase_bindings(plan, 'reference', record)

    def test_known_unsafe_skip_protocol_mutant_accepts_bad_fixture(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            plan, record = self.fixture(root, 'reference')
            self.mutate(root / 'reference/configure.receipt.json', 'outputComplete', False)
            with self.assertRaises(ValueError):
                origin.phase_bindings(plan, 'reference', record)
            # Deliberately unsafe old-reader equivalent: dropping the NEW
            # protocol/stream contract must be distinguished by this fixture.
            with patch.object(origin, 'phase_protocol', return_value={}):
                self.assertEqual(len(origin.phase_bindings(plan, 'reference', record)), 6)

    def test_status_byte_count_float_and_launcher_witness_without_hash_masking(self):
        for attack in ('float-count', 'python', 'helper-witness'):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory(dir=G) as temp:
                root = Path(temp)
                plan, record = self.fixture(root, 'reference')
                side = root / 'reference'
                if attack == 'float-count':
                    path = side / 'configure.receipt.json'
                    receipt = json.loads(path.read_text())
                    receipt['guardianStatusBytes'] = float(receipt['guardianStatusBytes'])
                    path.write_text(json.dumps(receipt))
                else:
                    if attack == 'python':
                        plan['python'] = str(origin.builder.GUARDIAN)
                    else:
                        plan['witness']['files'][str(origin.builder.GUARDIAN)] = '0' * 64
                    # Rebind ALL ordinary input/argv/command receipts so the
                    # launcher-witness check, not an incidental digest, rejects.
                    for phase in origin.builder.phases('reference'):
                        path = side / (phase + '.command.json')
                        command = json.loads(path.read_text())
                        command['inputsSha256'] = origin.code.sha(json.dumps(plan['witness'], sort_keys=True).encode())
                        command['argv'] = origin.builder.phase_command(plan, 'reference', phase)
                        path.write_text(json.dumps(command))
                        rp = side / (phase + '.receipt.json')
                        receipt = json.loads(rp.read_text())
                        receipt.update(command=origin.identity(path), argv=command['argv'])
                        rp.write_text(json.dumps(receipt))
                with self.assertRaisesRegex(ValueError, 'canonical guardian status|admitted Python|launcher source witness'):
                    origin.phase_bindings(plan, 'reference', record)

    def test_positive_raw_binary_counts_and_source_witness(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            plan, record = self.fixture(root, 'reference')
            side = root / 'reference'
            (side / 'configure.stdout').write_bytes(b'\x00\xff\n')
            path = side / 'configure.receipt.json'
            receipt = json.loads(path.read_text())
            receipt['streams']['stdout'].update(bytesRead=3, bytesWritten=3)
            path.write_text(json.dumps(receipt))
            result = origin.phase_bindings(plan, 'reference', record)
            self.assertEqual(result['configure']['stdout']['size'], 3)
            plan['witness']['files'][str(origin.builder.GUARDIAN)] = '0' * 64
            with self.assertRaises(ValueError):
                origin.phase_bindings(plan, 'reference', record)

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
