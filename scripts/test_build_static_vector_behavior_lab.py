"""Builder pure contracts only; no subprocess/compiler/version/server tests."""
from contextlib import contextmanager
import importlib.util
import inspect
import json
import os
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import Mock, patch
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('_sv_builder_test', Path(__file__).with_name('build-static-vector-behavior-lab.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
G = builder.ad.build_root()
TOOL = str(Path(sys.executable).resolve())
TOOLS = {'CMAKE_C_COMPILER': TOOL, 'CMAKE_CXX_COMPILER': TOOL}
fixture = builder.load('_physical_builder_fixture', builder.ROOT / 'source/lab/static-vector-game/test_physical_link_map.py')


@contextmanager
def dependency_fixture(role='candidate', extra_tus=0, shared_headers=0):
    """Real tiny inputs and raw .d files; no mocked dependency verifier."""
    with tempfile.TemporaryDirectory(dir=G) as temp:
        root = Path(temp)
        build = root / role / 'cmake'
        build.mkdir(parents=True)
        sdk = root / 'SDK'
        sdk.mkdir()
        sdk_header = sdk / 'mock.h'
        sdk_header.write_text('synthetic SDK observation fixture')
        shared = [builder.ROOT / 'source/game/StarTileSectorArray.hpp',
                  builder.ROOT / 'source/core/StarTileSectorArrayObserver.hpp',
                  builder.ROOT / 'source/core/StarStaticVector.hpp', sdk_header]
        if role == 'candidate':
            shared += [builder.ROOT / 'source/core/StarRustStaticVector.h',
                       builder.ROOT / 'source/core/StarStaticVectorHost.hpp']
        for index in range(shared_headers):
            header = sdk / ('shared-%03d.h' % index)
            header.write_text('/* shared %d */\n' % index)
            shared.append(header)
        inputs = [
            ('world', builder.ROOT / 'source/game/StarWorldClient.cpp', shared),
            ('client', builder.ROOT / 'source/client/StarClientApplication.cpp',
             [builder.ROOT / builder.ad.HEADER] + shared)]
        for index in range(extra_tus):
            source = root / ('extra-%03d.cpp' % index)
            source.write_text('/* synthetic TU %d */\n' % index)
            inputs.append(('extra-%03d' % index, source, shared))
        rows, objects, files, closures = [], {}, {}, {}
        for label, source, extra in inputs:
            obj = build / (source.name + '.o')
            obj.write_text('synthetic object ' + label)
            deps = [source] + extra
            dep = Path(str(obj) + '.d')
            dep.write_text(str(obj) + ': ' + ' '.join(map(str, deps)) + '\n')
            rows.append(dict(arguments=[TOOL, '-c', str(source), '-o', str(obj)],
                             file=str(source), directory=str(build)))
            objects[label] = dict(object=str(obj))
            files.update({str(path): builder.ad.sha(path) for path in deps})
            closures[str(obj)] = set(map(str, deps))
            newest = max(path.stat().st_mtime_ns for path in deps)
            os.utime(obj, ns=(newest + 1000000, newest + 1000000))
        (build / 'compile_commands.json').write_text(json.dumps(rows))
        plan = dict(buildRoot=str(root), witness={'files': files}, sdk=str(sdk), tools=TOOLS)
        configured = dict(role=role, objects=objects)
        yield plan, configured, {'compile_source_files': {}}, closures


class StreamSelector:
    def __init__(self):
        self.keys = {}
        self.unregistered = []
        self.closed = False
        self.on_select = None

    def register(self, stream, events, data):
        self.keys[stream.fileno()] = SimpleNamespace(fileobj=stream, data=data)

    def unregister(self, stream):
        self.unregistered.append(stream)
        del self.keys[stream.fileno()]

    def select(self, timeout):
        if self.on_select:
            self.on_select(timeout)
        return [(key, builder.selectors.EVENT_READ) for key in list(self.keys.values())]

    def close(self):
        self.closed = True


@contextmanager
def capture_fixture(stdout=(b'',), stderr=(b'',), returncode=0):
    """all process/OS readiness is synthetic; only tiny output files are real."""
    with tempfile.TemporaryDirectory(dir=G) as temp:
        output = Path(temp) / 'reference/compile'
        output.parent.mkdir()
        streams = {name: Mock() for name in ('stdout', 'stderr')}
        streams['stdout'].fileno.return_value = 11
        streams['stderr'].fileno.return_value = 12
        status_pipe = Mock()
        status_pipe.fileno.return_value = 13
        record = dict(schema=builder.GUARDIAN_SCHEMA, token='fixture-token',
            sourceSha256=builder.identity(builder.GUARDIAN)['sha256'],
            guardianPID=4242, guardianPGID=4242, guardianSID=4242,
            commandPID=4343, returncode=returncode, commandReaped=True, launchError=None)
        chunks = {11: list(stdout), 12: list(stderr), 13: [json.dumps(record).encode(), b'']}
        events = []
        proc = Mock(pid=4242, returncode=-builder.signal.SIGKILL, **streams)
        proc.wait.side_effect = lambda: events.append(('wait',)) or proc.returncode
        selector = StreamSelector()
        limits = dict(stdoutBytes=8, stderrBytes=4, readChunkBytes=4, overflowBytes=4)

        def read(fd, size):
            if not chunks[fd]:
                return b''
            data = chunks[fd].pop(0)
            if isinstance(data, BaseException):
                raise data
            assert len(data) <= size, 'fixture exceeds the read request'
            return data

        # Readiness/FDs are synthetic here. Exercise real bounded publication in
        # admission/writer tests, not through these process-IO monkeypatches.
        with patch.object(builder.ad, 'build_root', return_value=Path(temp)), \
             patch.object(builder.ad, 'dump', side_effect=builder.ad.primitives.dump), \
             patch.object(builder.ad, 'validate') as validate, \
             patch.object(builder, 'remaining', return_value=10) as clock, \
             patch.object(builder, 'phase_output_limits', return_value=limits), \
             patch.object(builder.subprocess, 'Popen', return_value=proc) as launch, \
             patch.object(builder.secrets, 'token_hex', return_value='fixture-token'), \
             patch.object(builder.os, 'pipe', return_value=(13, 14)), \
             patch.object(builder.os, 'fdopen', return_value=status_pipe), \
             patch.object(builder.os, 'close') as close_fd, \
             patch.object(builder.selectors, 'DefaultSelector', return_value=selector), \
             patch.object(builder.os, 'set_blocking') as blocking, \
             patch.object(builder.os, 'read', side_effect=read), \
             patch.object(builder.os, 'killpg', side_effect=lambda pid, sig: events.append(('kill', sig))) as kill:
            yield SimpleNamespace(output=output, streams=streams, chunks=chunks, proc=proc,
                status_pipe=status_pipe, record=record, close_fd=close_fd,
                selector=selector, launch=launch, validate=validate,
                clock=clock, blocking=blocking, kill=kill, limits=limits, events=events,
                run=lambda: builder.supervise(['/never-executed'], builder.ROOT / 'source', {}, output, {'witness': {}}),
                receipt=lambda: json.loads(output.with_suffix('.receipt.json').read_text()))


class CaptureTests(unittest.TestCase):
    def test_all_common_provenance_commands_use_bounded_wrapper(self):
        plan = dict(buildRoot=str(G), python=TOOL, sdk='/SDK', tools={'CMAKE_EXECUTABLE': '/cmake'})
        for role in ('reference', 'candidate'):
            for phase in builder.phases(role):
                if phase.startswith('provenance-'):
                    with self.subTest(role=role, phase=phase):
                        command = builder.phase_command(plan, role, phase)
                        self.assertEqual(command[:3], [TOOL, str(builder.ROOT / 'source/lab/static-vector-game/provenance.py'), phase.removeprefix('provenance-')])
                        self.assertNotIn(str(builder.ROOT / 'source/lab/behavior/build_provenance.py'), command)

    def test_undeclared_output_rejected_before_files_or_launch(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            output = Path(temp) / 'compile'
            with patch.object(builder.subprocess, 'Popen') as launch:
                with self.assertRaisesRegex(ValueError, 'undeclared controller'):
                    builder.supervise(['/never-executed'], builder.ROOT / 'source', {}, output, {})
                launch.assert_not_called()
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_declared_limits_and_whole_pair_log_only_bound(self):
        for phase in builder.PHASES:
            limits = builder.phase_output_limits(phase)
            self.assertEqual(limits, dict(stdoutBytes=(64 if phase in ('provenance-seal', 'provenance-verify') else 8) * 1024**2,
                stderrBytes=2 * 1024**2, readChunkBytes=65536, overflowBytes=65536))
        # four full-JSON logs, nine ordinary logs, thirteen stderr logs,
        # twenty-six single-read overflow evidence files. not a metadata bound.
        self.assertEqual(builder.pair_phase_output_bound(), 354 * 1024**2 + 26 * 65536)
        with self.assertRaisesRegex(ValueError, 'undeclared phase'):
            builder.phase_output_limits('mock-phase')

    def test_raw_binary_both_streams_exact_cap_and_eof(self):
        with capture_fixture(stdout=(b'\xff\x00\r\n', b'abcd', b''), stderr=(b'\x80\r\n\x00', b'')) as rig:
            rig.run()
            self.assertEqual(rig.output.with_suffix('.stdout').read_bytes(), b'\xff\x00\r\nabcd')
            self.assertEqual(rig.output.with_suffix('.stderr').read_bytes(), b'\x80\r\n\x00')
            for name, size in (('stdout', 8), ('stderr', 4)):
                self.assertEqual(rig.receipt()['streams'][name], dict(bytesRead=size, bytesWritten=size, eof=True, overflow=None))
            self.assertEqual(rig.blocking.call_count, 3)

    def test_each_stream_overflow_retains_entire_first_read_remainder(self):
        for name in ('stdout', 'stderr'):
            with self.subTest(stream=name), capture_fixture(
                    stdout=(b'1234', b'567', b'89xy') if name == 'stdout' else (b'',),
                    stderr=(b'abc', b'dXYZ') if name == 'stderr' else (b'',)) as rig:
                with self.assertRaisesRegex(ValueError, 'OUTPUT_LIMIT_EXCEEDED'):
                    rig.run()
                receipt = rig.receipt()
                self.assertEqual(receipt['failure'], 'OUTPUT_LIMIT_EXCEEDED')
                self.assertIs(receipt['outputComplete'], False)
                row = receipt['streams'][name]
                self.assertEqual(row['bytesWritten'], rig.limits[name + 'Bytes'])
                raw = rig.output.with_suffix('.' + name).read_bytes()
                overflow = rig.output.with_suffix('.' + name + '-overflow.bin').read_bytes()
                self.assertEqual(overflow, b'9xy' if name == 'stdout' else b'XYZ')
                self.assertEqual(row['bytesRead'], len(raw) + len(overflow))
                self.assertEqual(row['overflow']['sha256'], builder.code.sha(overflow))
                self.assertEqual(row['overflow']['sizeBytes'], len(overflow))
                self.assertLessEqual(len(overflow), rig.limits['overflowBytes'])
                self.assertIs(receipt['reaped'], True)
                self.assertTrue(rig.selector.closed)
                for stream in rig.streams.values():
                    stream.close.assert_called_once()

    def test_known_unsafe_unbounded_writer_mutant_accepts_oversize(self):
        chunks = (b'1234', b'567', b'89xy')
        # the previous direct-file contract has no cap check: this tiny fixture
        # distinguishes it from the production supervisor, without huge files.
        with tempfile.TemporaryDirectory(dir=G) as temp:
            unsafe = Path(temp) / 'unsafe.stdout'
            with unsafe.open('xb') as file:
                for chunk in chunks:
                    file.write(chunk)
            self.assertGreater(unsafe.stat().st_size, 8)
        with capture_fixture(stdout=chunks) as rig:
            with self.assertRaisesRegex(ValueError, 'OUTPUT_LIMIT_EXCEEDED'):
                rig.run()

    def test_launch_failure_has_no_invented_pid_or_reaping(self):
        with capture_fixture() as rig:
            rig.launch.side_effect = OSError('launch failed')
            with self.assertRaisesRegex(OSError, 'launch failed'):
                rig.run()
            row = rig.receipt()
            self.assertIsNone(row['pid'])
            self.assertIsNone(row['pgid'])
            self.assertIsNone(row['returncode'])
            self.assertFalse(row['reaped'])
            self.assertFalse(row['outputComplete'])
            rig.kill.assert_not_called()

    def test_nonzero_and_final_validation_failure_have_failed_receipts(self):
        for case in ('nonzero', 'validation'):
            with self.subTest(case=case), capture_fixture(returncode=7 if case == 'nonzero' else 0) as rig:
                if case == 'validation':
                    rig.validate.side_effect = [None, None, ValueError('final validation')]
                with self.assertRaisesRegex(ValueError, 'native phase failed' if case == 'nonzero' else 'final validation'):
                    rig.run()
                self.assertFalse(rig.receipt()['outputComplete'])
                self.assertTrue(rig.receipt()['reaped'])
                self.assertEqual(rig.events[-1], ('wait',))
                self.assertEqual(rig.events.count(('wait',)), 1)

    def test_original_clock_periodic_validation_and_inherited_pipe_failure(self):
        with capture_fixture(stdout=(BlockingIOError(),) * 4) as rig:
            rig.chunks[13] = [BlockingIOError()] * 4
            # initial prelaunch check plus each loop; no fresh clock is created.
            rig.clock.side_effect = [10, 9, 8, ValueError('original clock expired')]
            rig.selector.on_select = lambda delay: self.assertLessEqual(delay, 0.1)
            with self.assertRaisesRegex(ValueError, 'original clock expired'):
                rig.run()
            self.assertEqual(rig.events, [('kill', builder.signal.SIGKILL), ('wait',)])
            self.assertFalse(rig.receipt()['outputComplete'])
        with capture_fixture(stdout=(BlockingIOError(),)) as rig:
            ticks = iter(range(100))
            with patch.object(builder.time, 'monotonic', side_effect=lambda: next(ticks)):
                rig.validate.side_effect = [None, None, ValueError('periodic validation')]
                with self.assertRaisesRegex(ValueError, 'periodic validation'):
                    rig.run()
            self.assertTrue(rig.receipt()['reaped'])
        with capture_fixture(stdout=(BlockingIOError(),) * 4) as rig:
            # leader exit does not imply EOF: inherited/unread pipe prevents PASS.
            rig.clock.side_effect = [10, 9, 8, 7, ValueError('inherited pipe deadline')]
            with self.assertRaisesRegex(ValueError, 'inherited pipe deadline'):
                rig.run()
            self.assertEqual(rig.events, [('kill', builder.signal.SIGKILL), ('wait',)])
            self.assertFalse(rig.receipt()['streams']['stdout']['eof'])

    def test_eof_before_exit_does_not_kill_running_child(self):
        with capture_fixture() as rig:
            rig.chunks[13] = [BlockingIOError(), json.dumps(rig.record).encode(), b'']
            rig.run()
            self.assertEqual(rig.events, [('kill', builder.signal.SIGKILL), ('wait',)])

    def test_read_selector_and_registration_exceptions_cleanup(self):
        for case in ('read', 'select', 'register', 'status'):
            with self.subTest(case=case), capture_fixture(stdout=(OSError('read failed'),)) as rig:
                if case == 'select':
                    rig.selector.on_select = Mock(side_effect=OSError('select failed'))
                elif case == 'register':
                    rig.selector.register = Mock(side_effect=OSError('register failed'))
                elif case == 'status':
                    rig.chunks[11] = [b'']
                    rig.chunks[13] = [OSError('status failed')]
                with self.assertRaisesRegex(OSError, case + ' failed'):
                    rig.run()
                self.assertTrue(rig.receipt()['reaped'])
                self.assertTrue(rig.selector.closed)
                rig.status_pipe.close.assert_called_once()
                self.assertEqual(rig.events[-1], ('wait',))
                self.assertEqual(rig.proc.wait.call_count, 1)
                for stream in rig.streams.values():
                    stream.close.assert_called_once()

    def test_status_writer_close_failure_still_closes_launched_pipes(self):
        with capture_fixture() as rig:
            rig.close_fd.side_effect = [OSError('status close failed'), None]
            with self.assertRaisesRegex(OSError, 'status close failed'):
                rig.run()
            self.assertEqual(rig.events, [('kill', builder.signal.SIGKILL), ('wait',)])
            for stream in rig.streams.values():
                stream.close.assert_called_once()
            rig.status_pipe.close.assert_called_once()
            self.assertFalse(rig.receipt()['outputComplete'])
            self.assertTrue(rig.receipt()['guardianReaped'])

    def test_cleanup_failure_still_closes_other_fds_and_fails_receipt(self):
        with capture_fixture() as rig:
            rig.selector.close = Mock(side_effect=OSError('selector close failed'))
            with self.assertRaisesRegex(OSError, 'selector close failed'):
                rig.run()
            rig.status_pipe.close.assert_called_once()
            for stream in rig.streams.values():
                stream.close.assert_called_once()
            self.assertFalse(rig.receipt()['outputComplete'])
            self.assertEqual(rig.receipt()['cleanupFailure'], 'selector close failed')
            self.assertTrue(rig.receipt()['reaped'])

    def test_eperm_is_not_silently_accepted_even_after_pipe_eof(self):
        with capture_fixture() as rig:
            rig.kill.side_effect = PermissionError(1, 'Operation not permitted')
            with self.assertRaises(PermissionError):
                rig.run()
            row = rig.receipt()
            self.assertTrue(all(stream['eof'] for stream in row['streams'].values()))
            self.assertTrue(row['reaped'])
            self.assertFalse(row['outputComplete'])
            self.assertIn('Operation not permitted', row['failure'])
            self.assertEqual(rig.kill.call_count, 2)
            rig.proc.wait.assert_called_once()

    def test_before_launch_deadline_and_pipe_setup_failure(self):
        with capture_fixture() as rig:
            rig.clock.side_effect = ValueError('original clock expired')
            with self.assertRaisesRegex(ValueError, 'original clock expired'):
                rig.run()
            rig.launch.assert_not_called()
            self.assertFalse(rig.receipt()['reaped'])
        with capture_fixture() as rig:
            with patch.object(builder.os, 'pipe', side_effect=OSError('setup failed')):
                with self.assertRaisesRegex(OSError, 'setup failed'):
                    rig.run()
            self.assertEqual(rig.events, [])
            self.assertFalse(rig.receipt()['reaped'])

    def test_command_and_receipt_are_exclusive(self):
        with capture_fixture() as rig:
            rig.run()
            command = rig.output.with_suffix('.command.json').read_bytes()
            receipt = rig.output.with_suffix('.receipt.json').read_bytes()
            with self.assertRaises(FileExistsError):
                rig.run()
            self.assertEqual(command, rig.output.with_suffix('.command.json').read_bytes())
            self.assertEqual(receipt, rig.output.with_suffix('.receipt.json').read_bytes())
            self.assertEqual(rig.launch.call_count, 1)


class GuardianTests(unittest.TestCase):
    def test_protocol_rejects_unknown_duplicate_trailing_and_typed_identities(self):
        with capture_fixture() as rig:
            good = rig.record
            cases = [b'', b'\xff', b'{' + b'x' * 4096, json.dumps(good).encode() + b'{}', json.dumps(good).encode() + b'\n',
                     json.dumps(good).encode()[:-1] + b',"token":"fixture-token"}']
            for key, value in [('extra', 1), ('guardianPID', True), ('guardianPGID', 9),
                    ('guardianSID', 9), ('commandPID', True), ('commandPID', 4242),
                    ('commandPID', -1), ('returncode', False), ('commandReaped', 1),
                    ('token', 'wrong'), ('sourceSha256', 'wrong'), ('launchError', 'x' * 513),
                    ('commandReaped', False), ('commandPID', None), ('schema', 'wrong')]:
                cases.append(json.dumps(dict(good, **{key: value})).encode())
            for data in cases:
                with self.subTest(data=data[:100]), self.assertRaises((ValueError, UnicodeError)):
                    builder.guardian_status(data, 4242, 'fixture-token', good['sourceSha256'])

    def test_protocol_eof_oversize_and_launch_failure_never_pass(self):
        for case in ('empty', 'oversize', 'launch', 'mismatch'):
            with self.subTest(case=case), capture_fixture() as rig:
                if case == 'empty':
                    rig.chunks[13] = [b'']
                elif case == 'oversize':
                    rig.chunks[13] = [b'x' * 4097]
                else:
                    row = dict(rig.record)
                    if case == 'launch':
                        row.update(commandPID=None, returncode=None, commandReaped=False, launchError='launch failed')
                    else:
                        row['guardianPGID'] = 9999
                    rig.chunks[13] = [json.dumps(row).encode(), b'']
                with self.assertRaises(ValueError):
                    rig.run()
                self.assertFalse(rig.receipt()['outputComplete'])
                self.assertTrue(rig.receipt()['reaped'])
                self.assertEqual(rig.events[-1], ('wait',))
                self.assertLessEqual(rig.receipt()['guardianStatusBytes'], 4097)

    def test_status_first_preserves_raw_drain_and_actual_returncode(self):
        with capture_fixture(stdout=(b'abcd', b'efgh', b'')) as rig:
            rig.run()
            row = rig.receipt()
            self.assertEqual(row['returncode'], 0)
            self.assertEqual(row['guardianReturncode'], -9)
            self.assertEqual(row['commandPID'], 4343)
            self.assertTrue(row['commandReaped'])
            command = json.loads(rig.output.with_suffix('.command.json').read_text())
            self.assertEqual(command['argv'], ['/never-executed'])
            self.assertEqual(command['launchArgv'][-2:], ['--', '/never-executed'])
            self.assertEqual(rig.launch.call_args.kwargs['pass_fds'], (14,))
            self.assertEqual(command['launcher']['guardian'], builder.identity(builder.GUARDIAN))
            rig.proc.poll.assert_not_called()

    def test_fragmented_status_and_stream_eof_before_report(self):
        with capture_fixture() as rig:
            raw = json.dumps(rig.record).encode()
            rig.chunks[13] = [raw[:3], BlockingIOError(), raw[3:17], raw[17:], b'']
            rig.run()
            self.assertEqual(rig.receipt()['guardianStatusBytes'], len(raw))
            self.assertTrue(rig.receipt()['guardianStatusEOF'])
            self.assertTrue(rig.receipt()['guardianReaped'])
            self.assertEqual(rig.receipt()['reapedScope'], 'DIRECT_GUARDIAN_ONLY')
            self.assertEqual(rig.events, [('kill', builder.signal.SIGKILL), ('wait',)])

    def test_unexpected_guardian_exit_and_pin_drift_fail(self):
        with capture_fixture() as rig:
            rig.proc.returncode = 0
            with self.assertRaisesRegex(ValueError, 'did not remain live'):
                rig.run()
            self.assertFalse(rig.receipt()['outputComplete'])
        with capture_fixture() as rig:
            original = builder.identity
            calls = []
            def drift(path):
                result = original(path)
                calls.append(path)
                if path == builder.GUARDIAN and calls.count(path) > 1:
                    result['sha256'] = '0' * 64
                return result
            with patch.object(builder, 'identity', side_effect=drift):
                with self.assertRaisesRegex(ValueError, 'launcher drift'):
                    rig.run()
            rig.launch.assert_not_called()

    def test_guardian_main_preserves_native_argv_and_declared_environment(self):
        guardian = builder.load('_guardian_main_test', builder.GUARDIAN)
        args = [str(builder.GUARDIAN), '--status-fd', '14', '--token', 'token',
                '--source-sha', 'pin', '--environment-json', '{"EXACT":"value"}',
                '--', '/native', '--source-sha', 'native-argument']
        with patch.object(sys, 'argv', args), patch.object(guardian, 'guard') as guard:
            guardian.main()
        guard.assert_called_once_with(['/native', '--source-sha', 'native-argument'], 14, 'token', 'pin', {'EXACT': 'value'})
        self.assertLessEqual(len(guardian.bounded_error(ValueError('😀' * 1000)).encode('utf-8')), 512)

    def test_guardian_rejects_wrong_session_and_source_before_native_launch(self):
        guardian = builder.load('_guardian_identity_test', builder.GUARDIAN)
        for case in ('session', 'source'):
            with self.subTest(case=case):
                writes = []
                with patch.object(guardian.os, 'getpid', return_value=4242), \
                     patch.object(guardian.os, 'getpgrp', return_value=4242), \
                     patch.object(guardian.os, 'getsid', return_value=9999 if case == 'session' else 4242), \
                     patch.object(guardian.os, 'close'), \
                     patch.object(guardian.os, 'write', side_effect=lambda fd, data: writes.append(data) or len(data)), \
                     patch.object(guardian.subprocess, 'Popen') as spawn, \
                     patch.object(guardian.signal, 'pause', side_effect=RuntimeError('mock idle stop')):
                    with self.assertRaisesRegex(RuntimeError, 'mock idle stop'):
                        guardian.guard(['/never'], 14, 'token', 'wrong-pin', {})
                spawn.assert_not_called()
                row = json.loads(b''.join(writes))
                self.assertFalse(row['commandReaped'])
                self.assertIsNone(row['commandPID'])
                self.assertIsNone(row['returncode'])
                self.assertIn('fresh session' if case == 'session' else 'source pin', row['launchError'])

    def test_guardian_launch_reap_private_fd_and_idle_are_mocked(self):
        guardian = builder.load('_guardian_test', builder.GUARDIAN)
        for failure in (False, True):
            with self.subTest(launchFailure=failure):
                proc = Mock(pid=4343)
                proc.wait.return_value = 7
                writes, closes, events = [], [], []
                def write(fd, data):
                    writes.append(data)
                    events.append('status')
                    return len(data)
                proc.wait.side_effect = lambda: events.append('wait-command') or 7
                with patch.object(guardian.os, 'getpid', return_value=4242), \
                     patch.object(guardian.os, 'getpgrp', return_value=4242), \
                     patch.object(guardian.os, 'getsid', return_value=4242), \
                     patch.object(guardian.os, 'set_inheritable') as private, \
                     patch.object(guardian.os, 'close', side_effect=lambda fd: closes.append(fd)), \
                     patch.object(guardian.os, 'write', side_effect=write), \
                     patch.object(guardian.subprocess, 'Popen', side_effect=OSError('x' * 1000) if failure else None, return_value=proc) as spawn, \
                     patch.object(guardian.signal, 'pause', side_effect=RuntimeError('mock idle stop')):
                    with self.assertRaisesRegex(RuntimeError, 'mock idle stop'):
                        guardian.guard(['/exact', '--flag'], 14, 'fixture-token', builder.identity(builder.GUARDIAN)['sha256'], {'EXACT': 'declared'})
                row = builder.guardian_status(b''.join(writes), 4242, 'fixture-token', builder.identity(builder.GUARDIAN)['sha256'])
                self.assertEqual(row['commandReaped'], not failure)
                self.assertEqual(closes, [1, 2, 14])
                self.assertLessEqual(len(b''.join(writes)), 4096)
                self.assertEqual(spawn.call_args.args, (['/exact', '--flag'],))
                self.assertEqual(spawn.call_args.kwargs, dict(env={'EXACT': 'declared'}, close_fds=True, pass_fds=()))
                private.assert_called_once_with(14, False)
                self.assertEqual(events, ['status'] if failure else ['wait-command', 'status'])


class BuilderTests(unittest.TestCase):
    def test_candidate_cargo_barrier_and_no_reference_cargo(self):
        self.assertEqual(len(builder.phases('candidate')), 7)
        self.assertEqual(len(builder.phases('reference')), 6)
        self.assertLess(builder.phases('candidate').index('cargo'), builder.phases('candidate').index('compile'))
        plan = dict(buildRoot=str(G), sdk='/SDK', python='/python', tools={'CMAKE_EXECUTABLE': '/cmake'})
        with self.assertRaises(ValueError):
            builder.phase_command(plan, 'reference', 'cargo')
        self.assertNotIn('RUSTFLAGS', builder.environment(plan, 'candidate'))

    def test_supervision_owned_group_is_mocked_and_reaped(self):
        with capture_fixture() as rig:
            rig.run()
            self.assertTrue(rig.launch.call_args.kwargs['start_new_session'])
            self.assertEqual(rig.launch.call_args.kwargs['stdout'], builder.subprocess.PIPE)
            self.assertEqual(rig.launch.call_args.kwargs['stderr'], builder.subprocess.PIPE)
            self.assertEqual(rig.events, [('kill', builder.signal.SIGKILL), ('wait',)])
            self.assertIs(rig.receipt()['reaped'], True)
            self.assertIs(rig.receipt()['outputComplete'], True)
            self.assertEqual(rig.receipt()['pgid'], 4242)
            self.assertTrue(rig.selector.closed)
            rig.status_pipe.close.assert_called_once()
            for stream in rig.streams.values():
                stream.close.assert_called_once()
                self.assertTrue(rig.selector.unregistered.count(stream) == 1)

    def test_make_dependency_grammar(self):
        self.assertEqual(builder.make_rule('a.o: source\\ file.hpp path$$name\n'), ('a.o', ['source file.hpp', 'path$name']))
        with self.assertRaises(ValueError):
            builder.make_rule('a.o: first\nb.o: second\n')

    def test_wrong_expanded_cargo_argv_blocks_before_execution(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            build = Path(temp)
            (build / 'build.ninja').write_text('  COMMAND = cd ' + str(build) + ' && /cargo build --package star-engine-ffi --release\n')
            plan = dict(tools={'CMAKE_EXECUTABLE': '/cmake', 'STAR_CARGO_EXECUTABLE': '/cargo', 'STAR_RUSTC_EXECUTABLE': '/rustc'}, witness={'files': {}})
            with self.assertRaises(ValueError):
                builder.cargo_command(plan, build)

    def test_missing_compile_dependencies_rejected(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            build = root / 'candidate/cmake'
            build.mkdir(parents=True)
            obj = build / 'StarWorldClient.cpp.o'
            obj.write_text('object')
            source = builder.ROOT / 'source/game/StarWorldClient.cpp'
            (build / 'compile_commands.json').write_text(json.dumps([dict(arguments=[TOOL, '-c', str(source), '-o', str(obj)], file=str(source), directory=str(build))]))
            plan = dict(buildRoot=str(root), witness={'files': {str(source): builder.ad.sha(source)}}, sdk='/SDK', tools=TOOLS)
            configured = dict(role='candidate', objects={})
            with self.assertRaises(FileNotFoundError):
                builder.dependency_witness(plan, configured, {'compile_source_files': {}})
            Path(str(obj) + '.d').write_text(str(obj) + ': /unavailable/header.hpp\n')
            with self.assertRaises(FileNotFoundError):
                builder.dependency_witness(plan, configured, {'compile_source_files': {}})

    def test_synthetic_current_consumer_dependency_closure(self):
        for role in ('reference', 'candidate'):
            with self.subTest(role=role), dependency_fixture(role=role) as args:
                plan, configured, snapshot, _ = args
                witness = builder.dependency_witness(plan, configured, snapshot)
                self.assertEqual(len(witness['objects']), 2)
                plan['witness']['files'][str(Path(plan['sdk']) / 'mock.h')] = '0' * 64
                with self.assertRaisesRegex(ValueError, 'unadmitted dependency'):
                    builder.dependency_witness(plan, configured, snapshot)

    def test_interned_shared_dependencies_capture_once_and_stable_ids(self):
        with dependency_fixture(extra_tus=6, shared_headers=64) as args:
            plan, configured, snapshot, closures = args
            with patch.object(builder.ad, 'sha', wraps=builder.ad.sha) as hashes:
                witness = builder.dependency_witness(plan, configured, snapshot)
            self.assertEqual(witness['schema'], 'static-vector-compile-dependencies-v2')
            paths = [record['path'] for record in witness['files']]
            self.assertEqual(paths, sorted(set().union(*closures.values())))
            self.assertEqual(len(paths), 79)
            calls = [str(call.args[0]) for call in hashes.call_args_list]
            self.assertTrue(all(calls.count(path) == 1 for path in paths))
            self.assertEqual(calls.count(TOOL), 1)
            self.assertEqual(len(calls), 97)  # 79 dependencies + 8 objects + 8 .d + compiler + database.
            self.assertEqual(len(calls), len(set(calls)))
            self.assertNotIn(TOOL, paths)
            old = dict(schema='static-vector-compile-dependencies-v1', objects={})
            for obj, row in witness['objects'].items():
                ids = row['dependency_ids']
                self.assertEqual(ids, sorted(set(ids)))
                self.assertTrue(all(type(index) is int for index in ids))
                self.assertEqual({paths[index] for index in ids}, closures[obj])
                old['objects'][obj] = dict({key: value for key, value in row.items() if key != 'dependency_ids'},
                    dependencies={paths[index]: witness['files'][index] for index in ids})
            compact_size = len(json.dumps(witness, sort_keys=True).encode())
            repeated_size = len(json.dumps(old, sort_keys=True).encode())
            self.assertLess(compact_size * 3, repeated_size)
            # Reorder rows and repeat an equivalent lexical spelling in a raw
            # depfile: table IDs stay canonical, raw .d identity remains distinct.
            build = Path(plan['buildRoot']) / configured['role'] / 'cmake'
            database = build / 'compile_commands.json'
            database.write_text(json.dumps(list(reversed(json.loads(database.read_text())))))
            obj = configured['objects']['world']['object']
            dep = Path(obj + '.d')
            header = Path(plan['sdk']) / 'mock.h'
            dep.write_text(dep.read_text().rstrip() + ' ' + str(header.parent / 'present/../mock.h') + '\n')
            (header.parent / 'present').mkdir()
            with patch.object(builder.ad, 'sha', wraps=builder.ad.sha) as fresh_hashes:
                again = builder.dependency_witness(plan, configured, snapshot)
            self.assertEqual(len(fresh_hashes.call_args_list), 97)
            self.assertEqual(witness['files'], again['files'])
            self.assertEqual({obj: row['dependency_ids'] for obj, row in witness['objects'].items()},
                             {obj: row['dependency_ids'] for obj, row in again['objects'].items()})
            self.assertNotEqual(witness['objects'][obj]['depfile'], again['objects'][obj]['depfile'])

    def test_dependency_admission_consumer_sdk_and_mtime_negatives(self):
        errors = {'hash': 'unadmitted dependency', 'wrong-sdk': 'actual consumed SDK',
                  'missing-consumer': 'missing required compiled consumer', 'newer': 'dependency newer',
                  'unadmitted': 'unadmitted dependency', 'alias': 'duplicate compiled object',
                  'missing-source': 'source missing', 'on-only': 'ON-only'}
        for case, error in errors.items():
            with self.subTest(case=case), dependency_fixture() as args:
                plan, configured, snapshot, _ = args
                header = Path(plan['sdk']) / 'mock.h'
                obj = Path(configured['objects']['world']['object'])
                if case == 'hash':
                    header.write_text('actual header drift')
                elif case == 'wrong-sdk':
                    plan['sdk'] = str(header.parent / 'other-SDK')
                elif case == 'missing-consumer':
                    Path(configured['objects']['client']['object']).unlink()
                elif case == 'newer':
                    newer = obj.stat().st_mtime_ns + 1
                    os.utime(header, ns=(newer, newer))
                elif case == 'unadmitted':
                    del plan['witness']['files'][str(header)]
                elif case == 'alias':
                    database = obj.parent / 'compile_commands.json'
                    rows = json.loads(database.read_text())
                    alias = dict(rows[0], arguments=list(rows[0]['arguments']))
                    alias['arguments'][-1] = str(obj.parent) + '/./' + obj.name
                    rows.append(alias)
                    database.write_text(json.dumps(rows))
                elif case == 'missing-source':
                    dep = Path(str(obj) + '.d')
                    dep.write_text(dep.read_text().replace(str(builder.ROOT / 'source/game/StarWorldClient.cpp'), ''))
                elif case == 'on-only':
                    configured['role'] = 'reference'
                    # Keep the fixture at its original location while changing
                    # role semantics: the reference must not consume ON headers.
                    original = Path(plan['buildRoot']) / 'candidate'
                    original.rename(original.with_name('reference'))
                    for path in original.with_name('reference').rglob('*'):
                        if path.suffix == '.d' or path.name == 'compile_commands.json':
                            path.write_text(path.read_text().replace('/candidate/', '/reference/'))
                    for row in configured['objects'].values():
                        row['object'] = row['object'].replace('/candidate/', '/reference/')
                with self.assertRaisesRegex(ValueError, error):
                    builder.dependency_witness(plan, configured, snapshot)

    def test_dependency_aliases_require_strict_physical_resolution(self):
        for kind in ('missing-parent', 'symlink-parent'):
            with self.subTest(kind=kind), dependency_fixture() as args:
                plan, configured, snapshot, _ = args
                sdk = Path(plan['sdk'])
                alias = sdk / 'alias'
                obj = configured['objects']['world']['object']
                dep = Path(obj + '.d')
                dep.write_text(dep.read_text().rstrip() + ' ' + str(alias) + '/../mock.h\n')
                if kind == 'missing-parent':
                    with self.assertRaises(FileNotFoundError):
                        builder.dependency_witness(plan, configured, snapshot)
                else:
                    physical = sdk.parent / 'redirect'
                    (physical / 'inner').mkdir(parents=True)
                    (physical / 'mock.h').write_text('not the admitted SDK header')
                    alias.symlink_to(physical / 'inner', target_is_directory=True)
                    with self.assertRaisesRegex(ValueError, 'unadmitted dependency'):
                        builder.dependency_witness(plan, configured, snapshot)

    def test_capture_detects_change_during_hash(self):
        with dependency_fixture() as args:
            plan, configured, snapshot, _ = args
            header = Path(plan['sdk']) / 'mock.h'
            real_sha = builder.ad.sha

            def changing_sha(path):
                digest = real_sha(path)
                if path == header:
                    path.write_text('changed after content read')
                return digest

            with patch.object(builder.ad, 'sha', side_effect=changing_sha), \
                 self.assertRaisesRegex(ValueError, 'changed during capture'):
                builder.dependency_witness(plan, configured, snapshot)

    def test_final_stability_barrier_and_known_unguarded_mutant(self):
        source = inspect.getsource(builder.dependency_witness)
        guard = "ad.need(before == fingerprint(path), 'compile input changed before return: ' + str(path))"
        self.assertEqual(source.count(guard), 1)
        namespace = dict(vars(builder))
        exec(compile(source.replace(guard, 'pass'), '<isolated-no-final-stability-mutant>', 'exec'), namespace)
        for implementation, rejects in [(builder.dependency_witness, True), (namespace['dependency_witness'], False)]:
            with self.subTest(rejects=rejects), dependency_fixture(extra_tus=1) as args:
                plan, configured, snapshot, _ = args
                header = Path(plan['sdk']) / 'mock.h'
                last_obj = Path(configured['objects']['extra-000']['object'])
                real_identity = builder.identity

                def late_change(path):
                    record = real_identity(path)
                    if path == last_obj:
                        header.write_text('late change after shared header capture')
                    return record

                # Mutant has isolated globals; only the capture observer differs.
                if rejects:
                    with patch.object(builder, 'identity', side_effect=late_change), \
                         self.assertRaisesRegex(ValueError, 'changed before return'):
                        implementation(plan, configured, snapshot)
                else:
                    namespace['identity'] = late_change
                    self.assertEqual(implementation(plan, configured, snapshot)['schema'],
                                     'static-vector-compile-dependencies-v2')

    def test_physical_map_closure_and_selected_bytes(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            side = Path(temp)
            (side / 'cmake').mkdir()
            library = side / 'lib.a'
            bodies = [fixture.macho(), fixture.macho((b'_right',))]
            library.write_bytes(fixture.ar(bodies))
            direct = side / 'cmake/direct.o'
            direct.write_bytes(fixture.macho((b'_direct',)))
            data = fixture.linkmap([(4096, 8, 7, b'_right'), (4104, 8, 91, b'_left')],
                                   path=bytes(library))
            data = data.replace(b'# Symbols:', b'[150] ' + bytes(direct) + b'\n# Symbols:')
            (side / 'link.map').write_bytes(data)
            plan = dict(witness={'files': {str(library): builder.ad.sha(library)}})
            deps = {'objects': {str(direct): {}}}
            origins = builder.link_map_closure(plan, side, deps, None)
            self.assertEqual([r['object_index'] for r in origins['objects']], [0, 7, 91, 150])
            link = {'actualOrigins': origins}
            self.assertEqual(builder.link_object_bytes(link), {7: bodies[1], 91: bodies[0], 150: direct.read_bytes()})
            # Wrong recorded offset must reject even when a first-member shortcut is tempting.
            first = origins['objects'][1]
            old = first['member_header_offset']
            first['member_header_offset'] = origins['objects'][2]['member_header_offset']
            with self.assertRaises(ValueError):
                builder.link_object_bytes(link)
            first['member_header_offset'] = old
            original_direct = direct.read_bytes()
            direct.write_bytes(fixture.macho((b'_changed',)))
            with self.assertRaises(ValueError):
                builder.link_object_bytes(link)
            direct.write_bytes(original_direct)
            library.write_bytes(fixture.ar(list(reversed(bodies))))
            with self.assertRaises(ValueError):
                builder.link_object_bytes(link)

    def test_map_aliases_cannot_assign_one_physical_input_twice(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            side = Path(temp); (side / 'cmake').mkdir()
            library = side / 'lib.a'
            library.write_bytes(fixture.ar([fixture.macho()]))
            direct = side / 'cmake/direct.o'
            direct.write_bytes(fixture.macho((b'_direct',)))
            plan = dict(witness={'files': {str(library): builder.ad.sha(library)}})
            deps = {'objects': {str(direct): {}}}
            for first, second in [
                    (bytes(library) + b'(dup\xff.o)', bytes(library.parent) + b'/./lib.a(dup\xff.o)'),
                    (bytes(direct), bytes(direct.parent) + b'/./direct.o')]:
                data = (b'# Object files:\n[0] linker synthesized\n[7] ' + first +
                        b'\n[19] ' + second + b'\n# Symbols:\n')
                (side / 'link.map').write_bytes(data)
                with self.subTest(first=first), self.assertRaisesRegex(ValueError, 'map aliases'):
                    builder.link_map_closure(plan, side, deps, None)

    def test_physical_member_name_sha_and_kind_guards(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            path = Path(temp) / 'lib.a'
            path.write_bytes(fixture.ar([fixture.macho()]))
            member = builder.physical.archive.arm64_archive_members(path.read_bytes())[0]
            row = dict(kind='ARCHIVE_MEMBER', object_index=7, archive=builder.identity(path),
                       member_header_offset=member['offset'], member_name_hex=member['name'].hex(),
                       member_sha256=member['sha256'])
            for field, value in [('member_name_hex', b'wrong.o'.hex()), ('member_sha256', '0' * 64),
                                 ('member_header_offset', member['offset'] + 1)]:
                with self.subTest(field=field), self.assertRaises(ValueError):
                    builder.link_object_bytes({'actualOrigins': {'objects': [dict(row, **{field: value})]}})
            obj = Path(temp) / 'bad.o'
            obj.write_bytes(b'not Mach-O')
            with self.assertRaises(ValueError):
                builder.link_object_bytes({'actualOrigins': {'objects': [dict(kind='COMPILED_OBJECT', object_index=9, object=builder.identity(obj))]}})

    def test_archive_file_state_detects_replacement(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            path = Path(temp) / 'archive.a'
            path.write_bytes(b'unchanged')
            before = builder.ad.file_state(path)
            other = Path(temp) / 'other'
            other.write_bytes(b'unchanged')
            other.replace(path)
            self.assertNotEqual(before, builder.ad.file_state(path))


if __name__ == '__main__':
    unittest.main()
