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
from unittest.mock import Mock, call, patch
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('_sv_builder_test', Path(__file__).with_name('build-static-vector-behavior-lab.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
G = builder.ad.allocation_root()
TOOL = str(Path(sys.executable).resolve())
TOOLS = {'CMAKE_C_COMPILER': TOOL, 'CMAKE_CXX_COMPILER': TOOL}
fixture = builder.load('_physical_builder_fixture', builder.ROOT / 'source/lab/static-vector-game/test_physical_link_map.py')


def native_plan(root):
    owner = dict(root=str(root.parent), mount=dict(path=str(root), st_dev=123),
                 device='/dev/disk41', volumeDevice='/dev/disk41s1')
    return dict(buildRoot=str(root), enclosure=dict(owner=owner),
                nativeSandbox=builder.ad.policy.binding(owner, dict(path=builder.ad.policy.TOOL, sha256='a' * 64, size=123)),
                python=TOOL, sdk='/SDK', tools={'CMAKE_EXECUTABLE': '/cmake'}, witness={})


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
        plan = native_plan(Path(temp))
        with patch.object(builder.ad, 'build_root', return_value=Path(temp)), \
             patch.object(builder.ad, 'enclosure_root', return_value=Path(temp).parent):
            argv = builder.phase_command(plan, 'reference', 'compile')
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
             patch.object(builder.ad, 'enclosure_root', return_value=Path(temp).parent), \
             patch.object(builder.ad, 'dump', side_effect=builder.ad.primitives.dump), \
             patch.object(builder.ad, 'validate') as validate, \
             patch.object(builder, 'remaining', return_value=10) as clock, \
             patch.object(builder, 'phase_output_limits', return_value=limits), \
             patch.object(builder.subprocess, 'Popen', return_value=proc) as launch, \
             patch.object(builder.secrets, 'token_hex', return_value='fixture-token'), \
             patch.object(builder.os, 'pipe', side_effect=[(13, 14), (15, 16)]), \
             patch.object(builder.os, 'fdopen', return_value=status_pipe), \
             patch.object(builder.os, 'close') as close_fd, \
             patch.object(builder.selectors, 'DefaultSelector', return_value=selector), \
             patch.object(builder.os, 'set_blocking') as blocking, \
             patch.object(builder.os, 'read', side_effect=read), \
             patch.object(builder.os, 'write', side_effect=lambda fd, data: len(data)) as write_fd, \
             patch.object(builder.os, 'killpg', side_effect=lambda pid, sig: events.append(('kill', sig))) as kill:
            yield SimpleNamespace(output=output, streams=streams, chunks=chunks, proc=proc,
                status_pipe=status_pipe, record=record, close_fd=close_fd,
                selector=selector, launch=launch, validate=validate,
                clock=clock, blocking=blocking, kill=kill, limits=limits, events=events, write_fd=write_fd,
                argv=argv, plan=plan,
                run=lambda: builder.supervise(argv, builder.ROOT / 'source', {}, output, plan),
                receipt=lambda: json.loads(output.with_suffix('.receipt.json').read_text()))


class NativeSandboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=G)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'current30-enclosure/products'
        self.root.mkdir(parents=True)
        self.plan = native_plan(self.root)
        original_open = Path.open
        def no_capture(path, mode='r', *args, **kwargs):
            if 'x' in mode or 'w' in mode or 'a' in mode:
                raise AssertionError('stdio opened')
            return original_open(path, mode, *args, **kwargs)
        self.no_capture = no_capture
        for patcher in (patch.object(builder.ad, 'build_root', return_value=self.root),
                        patch.object(builder.ad, 'enclosure_root', return_value=self.root.parent),
                        patch.object(builder.subprocess, 'Popen', side_effect=AssertionError('NO Native launch'))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_all_thirteen_phases_share_exact_profile_and_inner_selectors(self):
        commands = []
        for role in ('reference', 'candidate'):
            for phase in builder.phases(role):
                argv = builder.phase_command(self.plan, role, phase)
                commands.append(argv)
                builder.ad.policy.validate_command(str(self.root), argv)
                self.assertEqual(argv[:3], [builder.ad.policy.TOOL, '-p', self.plan['nativeSandbox']['profile']])
                if phase == 'configure':
                    inner = argv[3:]
                    for selector, value in builder.ad.profiles()[role].items():
                        self.assertIn('-D' + selector + '=' + value, inner)
                    self.assertEqual(len(builder.ad.SELECTORS), 30)
                    self.assertIn('-DSTAR_USE_RUST_LINE_QUERY=OFF', inner)
                    self.assertIn('-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON', inner)
                    self.assertNotIn('-Dsandbox-exec=', ' '.join(inner))
                if phase == 'cargo':
                    self.assertEqual(argv[3:], ['/cmake', '--build', str(self.root / role / 'cmake'),
                        '--target', 'star_rust_engine_ffi_build', '--parallel', '6', '--', '-d', 'keepdepfile'])
                if phase.startswith('provenance-'):
                    self.assertEqual(argv[3], TOOL)
        self.assertEqual(len(commands), 13)

    def test_native_prefix_rejected_before_stdio_or_process_even_with_old_admission_guard(self):
        argv = builder.phase_command(self.plan, 'reference', 'compile')
        output = self.root / 'reference/compile'
        bad = [argv[3:], [*argv[:3], *argv], ['/other/sandbox-exec', *argv[1:]],
               [argv[0], '-f', *argv[2:]], [argv[0], '-p', '(version 1)(allow default)', *argv[3:]],
               [argv[0], '-p', builder.ad.policy.profile(str(self.root.parent)), *argv[3:]],
               [*argv[:3], '/python', True], [*argv[:3], '/python', 1.0],
               [*argv[:3], '/python', '\x00'], [*argv[:3], '/wrong-command']]
        with patch.object(builder.ad, 'validate'), \
             patch.object(Path, 'open', new=self.no_capture), \
             patch.object(builder, '_supervise_command') as core:
            for command in bad:
                with self.subTest(command=command), self.assertRaises((ValueError, KeyError)):
                    builder.supervise(command, builder.ROOT / 'source', {}, output, self.plan)
            core.assert_not_called()
            # The same admission/core stubs accept the legitimate wrapped phase.
            builder.supervise(argv, builder.ROOT / 'source', {}, output, self.plan)
            core.assert_called_once()
            self.assertEqual(core.call_args.args[0], argv)

    def test_native_binding_missing_numeric_alias_and_tool_profile_drift_prelaunch(self):
        argv = builder.phase_command(self.plan, 'reference', 'compile')
        for field, value in [('version', True), ('version', 1.0), ('profile', '(allow default)'),
                             ('profileSha256', '0' * 64), ('root', str(G))]:
            plan = dict(self.plan, nativeSandbox=dict(self.plan['nativeSandbox'], **{field: value}))
            with self.subTest(field=field, value=value), patch.object(builder.ad, 'validate'), \
                 patch.object(Path, 'open', new=self.no_capture), \
                 self.assertRaises(ValueError):
                builder.supervise(argv, builder.ROOT / 'source', {}, self.root / 'reference/compile', plan)
        for field in ('nativeSandbox', 'enclosure'):
            plan = dict(self.plan)
            del plan[field]
            with patch.object(builder.ad, 'validate'), \
                 patch.object(Path, 'open', new=self.no_capture), \
                 self.assertRaises(KeyError):
                builder.supervise(argv, builder.ROOT / 'source', {}, self.root / 'reference/compile', plan)
        for root in (str(G), 'products', str(self.root) + '/../products'):
            with self.subTest(root=root), self.assertRaises(ValueError):
                builder.ad.sandbox_command(dict(self.plan, buildRoot=root), ['/a'])

    def test_known_unsafe_raw_public_contract_mutant_is_distinguished(self):
        wrapped = builder.phase_command(self.plan, 'reference', 'compile')
        raw = wrapped[3:]
        output = self.root / 'reference/compile'
        with patch.object(builder.ad, 'validate'), \
             patch.object(Path, 'open', new=self.no_capture), \
             patch.object(builder, '_supervise_command') as core:
            with self.assertRaisesRegex(ValueError, 'sandbox prefix'):
                builder.supervise(raw, builder.ROOT / 'source', {}, output, self.plan)
            core.assert_not_called()
            # Deliberately restore the old raw public-command contract. The
            # same unsafe argv now reaches the mock core, NEVER a process.
            with patch.object(builder.ad.policy, 'validate_command'), \
                 patch.object(builder, 'phase_command', return_value=raw):
                builder.supervise(raw, builder.ROOT / 'source', {}, output, self.plan)
            core.assert_called_once()
            self.assertEqual(core.call_args.args[0], raw)

    def test_current_inputs_rederives_tool_and_typed_binding_before_other_probes(self):
        for field, value in [('version', True), ('version', 1.0), ('tool', dict(self.plan['nativeSandbox']['tool'], sha256='b' * 64)),
                             ('mount', dict(path=str(self.root), st_dev=123.0))]:
            plan = dict(self.plan, nativeSandbox=dict(self.plan['nativeSandbox'], **{field: value}))
            with patch.object(builder.ad, 'enclosure_state', return_value=plan['enclosure']), \
                 patch.object(builder.ad.primitives, '_require_pin') as pin, \
                 patch.object(builder.ad, 'identity', return_value=self.plan['nativeSandbox']['tool']), \
                 patch.object(builder.ad.config, 'validate_source', side_effect=AssertionError('later source probe')), \
                 self.assertRaisesRegex(ValueError, 'sandbox current binding drift'):
                builder.ad.current_inputs(plan)
            pin.assert_called_once_with(plan['witness'], builder.ad.policy.TOOL, 'Native sandbox tool')


class CaptureTests(unittest.TestCase):
    def test_all_common_provenance_commands_use_bounded_wrapper(self):
        physical = patch.object(builder.ad.policy, 'physical_path', side_effect=Path)
        physical.start()
        self.addCleanup(physical.stop)
        plan = native_plan(builder.ad.build_root())
        for role in ('reference', 'candidate'):
            for phase in builder.phases(role):
                if phase.startswith('provenance-'):
                    with self.subTest(role=role, phase=phase):
                        command = builder.phase_command(plan, role, phase)
                        self.assertEqual(command[3:6], [TOOL, str(builder.ROOT / 'source/lab/static-vector-game/provenance.py'), phase.removeprefix('provenance-')])
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


class SharedCoreTests(unittest.TestCase):
    def test_credential_environment_rejected_before_logs_or_launch(self):
        keys = ('T3_MCP_BEARER_TOKEN', 'GITHUB_TOKEN', 'AWS_SECRET_ACCESS_KEY',
                'password', 'APIKEY', 'PRIVATE_KEY', 'COOKIE', 'AUTHORIZATION')
        for key in keys:
            with self.subTest(key=key), capture_fixture() as rig:
                sentinel = 'private-value-must-not-be-published'
                with self.assertRaisesRegex(ValueError, 'credential-like environment') as caught:
                    builder._supervise_command(['/never-executed'], builder.ROOT / 'source',
                        {key: sentinel}, rig.output, limits=rig.limits,
                        validate=lambda: None, remaining_seconds=lambda: 10,
                        python=Path(sys.executable).resolve(), witness={},
                        write_record=builder.ad.primitives.dump, check_output=lambda path: None)
                self.assertNotIn(sentinel, str(caught.exception))
                self.assertNotIn(key, str(caught.exception))
                rig.launch.assert_not_called()
                self.assertEqual(list(rig.output.parent.iterdir()), [])

    def test_environment_snapshot_cannot_be_changed_by_validation_callback(self):
        with capture_fixture() as rig:
            env = {'EXACT': 'value'}
            builder._supervise_command(['/never-executed'], builder.ROOT / 'source', env,
                rig.output, limits=rig.limits,
                validate=lambda: env.update(TOKEN='private-sentinel'),
                remaining_seconds=lambda: 10, python=Path(sys.executable).resolve(),
                witness={}, write_record=builder.ad.primitives.dump, check_output=lambda path: None)
            command = json.loads(rig.output.with_suffix('.command.json').read_text())
            self.assertEqual(command['environment'], {'EXACT': 'value'})
            self.assertEqual(rig.launch.call_args.kwargs['env'], {'EXACT': 'value'})
            self.assertNotIn('private-sentinel', rig.output.with_suffix('.receipt.json').read_text())

    def test_stdin_is_optin_strict_and_preserves_default_popen_kwargs(self):
        for stdin in (None, builder.subprocess.DEVNULL):
            for observing in (False, True):
                with self.subTest(stdin=stdin, observing=observing), capture_fixture() as rig:
                    if observing:
                        start = CommandStartTests.start_row(rig)
                        rig.chunks[13] = [json.dumps(start).encode() + b'\n' + json.dumps(rig.record).encode(), b'']
                    receipt = builder._supervise_command(['/never-executed'], builder.ROOT / 'source', {},
                        rig.output, limits=rig.limits, validate=lambda: None, remaining_seconds=lambda: 10,
                        python=Path(sys.executable).resolve(), witness={}, write_record=builder.ad.primitives.dump,
                        check_output=lambda path: None, on_command_started=(lambda frame: None) if observing else None,
                        stdin=stdin)
                    kwargs = rig.launch.call_args.kwargs
                    expected = {'cwd', 'env', 'stdout', 'stderr', 'start_new_session', 'pass_fds'}
                    if stdin is not None:
                        expected.add('stdin')
                        self.assertEqual(kwargs['stdin'], builder.subprocess.DEVNULL)
                        self.assertEqual(receipt['stdin'], 'DEVNULL')
                    else:
                        self.assertNotIn('stdin', receipt)
                    self.assertEqual(set(kwargs), expected)
                    self.assertEqual(kwargs['pass_fds'], (14, 15) if observing else (14,))
                    command = json.loads(rig.output.with_suffix('.command.json').read_text())
                    self.assertEqual('stdin' in command, stdin is not None)
        for stdin in (True, False, -3.0, 'DEVNULL', 0, -1, [], {}):
            with self.subTest(stdin=stdin), capture_fixture() as rig:
                with self.assertRaisesRegex(ValueError, 'explicit DEVNULL'):
                    builder._supervise_command([], builder.ROOT, {}, rig.output, limits=rig.limits,
                        validate=lambda: None, remaining_seconds=lambda: 10, python=Path(sys.executable),
                        witness={}, write_record=builder.ad.primitives.dump, check_output=lambda path: None,
                        stdin=stdin)
                rig.launch.assert_not_called()
                self.assertEqual(list(rig.output.parent.iterdir()), [])

    def test_core_returns_receipt_only_after_cleanup_without_native_clock(self):
        with capture_fixture(stdout=(b'\xff\x00', b''), stderr=(b'\x80', b'')) as rig:
            validate = Mock()
            clock = Mock(return_value=10)
            receipt = builder._supervise_command(['/never-executed'], builder.ROOT / 'source', {},
                rig.output, limits=rig.limits, validate=validate, remaining_seconds=clock,
                python=Path(sys.executable).resolve(), witness={'release': 'only'},
                write_record=builder.ad.primitives.dump, check_output=lambda path: None,
                scope='RESOURCE_RELEASE_ONLY_NOT_ADMISSION')
            self.assertEqual(receipt, rig.receipt())
            self.assertTrue(rig.selector.closed)
            self.assertTrue(receipt['guardianReaped'])
            self.assertTrue(receipt['commandReaped'])
            self.assertEqual(receipt['scope'], 'RESOURCE_RELEASE_ONLY_NOT_ADMISSION')
            self.assertEqual(rig.output.with_suffix('.stdout').read_bytes(), b'\xff\x00')
            rig.validate.assert_not_called()
            rig.clock.assert_not_called()
            self.assertEqual(validate.call_count, 2)

    def test_core_unknown_command_reaping_survives_cancel(self):
        with capture_fixture() as rig:
            rig.chunks[13] = [BlockingIOError()] * 3
            clock = Mock(side_effect=[10, ValueError('release clock expired')])
            with self.assertRaisesRegex(ValueError, 'release clock expired'):
                builder._supervise_command(['/never-executed'], builder.ROOT / 'source', {},
                    rig.output, limits=rig.limits, validate=lambda: None,
                    remaining_seconds=clock, python=Path(sys.executable).resolve(), witness={},
                    write_record=builder.ad.primitives.dump, check_output=lambda path: None,
                    scope='RESOURCE_RELEASE_ONLY_NOT_ADMISSION')
            receipt = rig.receipt()
            self.assertTrue(receipt['guardianReaped'])
            self.assertFalse(receipt['commandReaped'])
            self.assertIsNone(receipt['guardianStatus'])
            self.assertFalse(receipt['outputComplete'])

    def test_native_return_and_schema_do_not_gain_release_scope(self):
        with capture_fixture() as rig:
            self.assertIsNone(rig.run())
            self.assertNotIn('scope', rig.receipt())
            command = json.loads(rig.output.with_suffix('.command.json').read_text())
            self.assertNotIn('scope', command)


class CommandStartTests(unittest.TestCase):
    @staticmethod
    def start_row(rig):
        return {key: (builder.COMMAND_START_SCHEMA if key == 'schema' else value)
                for key, value in rig.record.items()
                if key not in ('returncode', 'commandReaped', 'launchError')}

    @staticmethod
    def run_core(rig, callback):
        return builder._supervise_command(['/never-executed'], builder.ROOT / 'source', {},
            rig.output, limits=rig.limits, validate=lambda: None,
            remaining_seconds=lambda: 10, python=Path(sys.executable).resolve(), witness={},
            write_record=builder.ad.primitives.dump, check_output=lambda path: None,
            on_command_started=callback)

    def test_strict_start_payload_schema_identity_and_types(self):
        with capture_fixture() as rig:
            good = self.start_row(rig)
            raw = json.dumps(good).encode()
            self.assertEqual(builder.command_start_status(raw, 4242, 'fixture-token', good['sourceSha256']), good)
            cases = [b'', b'\xff', b'x' * 4096, b'[]', b'null', raw + b'\n', raw + b'{}',
                     raw[:-1] + b',"commandPID":4343}', raw.replace(b'"schema"', b'"extra"')]
            for key, value in [('extra', 0), ('schema', builder.GUARDIAN_SCHEMA),
                    ('token', 'wrong'), ('sourceSha256', 'wrong'), ('guardianPID', True),
                    ('guardianPID', 4242.0), ('guardianPGID', 4343), ('guardianSID', 1),
                    ('commandPID', True), ('commandPID', 4343.0), ('commandPID', 4242),
                    ('commandPID', 0), ('commandPID', -1), ('commandPID', 2**31), ('commandPID', None)]:
                cases.append(json.dumps(dict(good, **{key: value})).encode())
            for key in good:
                cases.append(json.dumps({k: v for k, v in good.items() if k != key}).encode())
            for data in cases:
                with self.subTest(data=data[:100]), self.assertRaises((ValueError, UnicodeError)):
                    builder.command_start_status(data, 4242, 'fixture-token', good['sourceSha256'])

    def test_observer_type_rejected_before_output_or_launch(self):
        for callback in (False, True, 0, 1, 'callback', [], {}):
            with self.subTest(callback=callback), capture_fixture() as rig:
                with self.assertRaisesRegex(ValueError, 'callable or None'):
                    self.run_core(rig, callback)
                rig.launch.assert_not_called()
                self.assertEqual(list(rig.output.parent.iterdir()), [])

    def test_partial_and_coalesced_start_before_wait_and_publication(self):
        for fragmented in (False, True):
            with self.subTest(fragmented=fragmented), capture_fixture() as rig:
                start = self.start_row(rig)
                frame = json.dumps(start).encode() + b'\n'
                final = json.dumps(rig.record).encode()
                wire = frame + final
                rig.chunks[13] = ([wire[:4], BlockingIOError(), wire[4:len(frame)-1],
                                   wire[len(frame)-1:]] if fragmented else [wire]) + [b'']
                def observed(row):
                    self.assertEqual(row, start)
                    rig.proc.wait.assert_not_called()
                    rig.kill.assert_not_called()
                    self.assertFalse(rig.output.with_suffix('.receipt.json').exists())
                    rig.events.append(('callback',))
                    row['commandPID'] = 9999  # consumer cannot mutate authoritative state
                callback = Mock(side_effect=observed)
                receipt = self.run_core(rig, callback)
                callback.assert_called_once()
                self.assertEqual(rig.events, [('callback',), ('kill', builder.signal.SIGKILL), ('wait',)])
                self.assertTrue(receipt['startConsumed'])
                self.assertTrue(receipt['callbackCompleted'])
                self.assertTrue(receipt['outputComplete'])
                self.assertEqual(receipt['commandStart'], start)
                self.assertEqual(bytes.fromhex(receipt['commandStartFrameHex']), frame[:-1])
                self.assertEqual(bytes.fromhex(receipt['guardianProtocolHex']), wire)
                self.assertEqual(receipt['guardianStatusBytes'], len(wire))
                self.assertEqual(receipt['commandPID'], 4343)
                command = json.loads(rig.output.with_suffix('.command.json').read_text())
                self.assertEqual(command['observer'], 'on_command_started')
                self.assertEqual(command['startSchema'], builder.COMMAND_START_SCHEMA)
                argv = rig.launch.call_args.args[0]
                self.assertEqual(argv[argv.index('--notify-start'):], ['--notify-start', '--start-ack-fd', '15', '--', '/never-executed'])
                self.assertTrue(receipt['startAcknowledged'])
                rig.write_fd.assert_called_once_with(16, b'fixture-token\n')
                self.assertEqual(rig.launch.call_args.kwargs['pass_fds'], (14, 15))
                rig.proc.poll.assert_not_called()

    def test_missing_late_duplicate_malformed_and_final_pid_drift_cancel(self):
        for case in ('missing', 'empty', 'late', 'duplicate', 'duplicate-partial',
                     'final-empty', 'start-partial', 'newline-final', 'malformed', 'duplicate-key',
                     'nonce', 'source', 'guardian', 'pid', 'float', 'bool', 'final-pid', 'oversize'):
            with self.subTest(case=case), capture_fixture() as rig:
                start = self.start_row(rig)
                final = json.dumps(rig.record).encode()
                if case in ('nonce', 'source', 'guardian', 'pid', 'float', 'bool'):
                    key, value = {'nonce': ('token', 'wrong'), 'source': ('sourceSha256', 'wrong'),
                        'guardian': ('guardianPGID', 4343), 'pid': ('commandPID', 4242),
                        'float': ('commandPID', 4343.0), 'bool': ('commandPID', True)}[case]
                    start[key] = value
                frame = json.dumps(start).encode() + b'\n'
                wire = frame + final
                if case == 'missing':
                    wire = final
                elif case == 'empty':
                    wire = b''
                elif case == 'late':
                    wire = final + frame
                elif case in ('duplicate', 'duplicate-partial'):
                    wire = frame + frame + final
                elif case == 'duplicate-key':
                    wire = frame[:-2] + b',"token":"fixture-token"}\n' + final
                elif case == 'final-empty':
                    wire = frame
                elif case == 'start-partial':
                    wire = frame[:-1]
                elif case == 'newline-final':
                    wire += b'\n'
                elif case == 'malformed':
                    wire = b'{bad}\n' + final
                elif case == 'final-pid':
                    wire = frame + json.dumps(dict(rig.record, commandPID=4444)).encode()
                elif case == 'oversize':
                    # Both pieces alone fit; the aggregate must not reset at start.
                    wire = frame + b'x' * (4097 - len(frame))
                rig.chunks[13] = ([frame, frame[:3], frame[3:] + final] if case == 'duplicate-partial' else [wire]) + [b'']
                callback = Mock()
                with self.assertRaises(ValueError):
                    self.run_core(rig, callback)
                receipt = rig.receipt()
                self.assertFalse(receipt['outputComplete'])
                self.assertTrue(receipt['guardianReaped'])
                self.assertIsNotNone(receipt['failure'])
                self.assertEqual(bytes.fromhex(receipt['guardianProtocolHex']), wire)
                self.assertLessEqual(callback.call_count, 1)
                if case == 'final-pid':
                    self.assertEqual(receipt['commandStart']['commandPID'], 4343)
                    self.assertEqual(receipt['guardianStatus']['commandPID'], 4444)
                    self.assertTrue(receipt['commandReaped'])
                if case in ('missing', 'empty', 'late', 'malformed', 'duplicate-key', 'start-partial', 'nonce', 'source',
                            'guardian', 'pid', 'float', 'bool', 'oversize'):
                    callback.assert_not_called()
                self.assertEqual(rig.events[-2:], [('kill', builder.signal.SIGKILL), ('wait',)])
                rig.proc.wait.assert_called_once()

    def test_cumulative_cap_after_frame_removed(self):
        with capture_fixture() as rig:
            frame = json.dumps(self.start_row(rig)).encode() + b'\n'
            rig.chunks[13] = [frame, b'x' * (4097 - len(frame)), b'']
            callback = Mock()
            with self.assertRaisesRegex(ValueError, 'status size'):
                self.run_core(rig, callback)
            callback.assert_called_once()
            self.assertEqual(rig.receipt()['guardianStatusBytes'], 4097)
            self.assertTrue(rig.receipt()['callbackCompleted'])

    def test_callback_error_does_not_invent_reaping_from_coalesced_final(self):
        with capture_fixture() as rig:
            frame = json.dumps(self.start_row(rig)).encode() + b'\n'
            rig.chunks[13] = [frame + json.dumps(rig.record).encode(), b'']
            callback = Mock(side_effect=RuntimeError('OS birth unavailable'))
            with self.assertRaisesRegex(RuntimeError, 'OS birth unavailable'):
                self.run_core(rig, callback)
            callback.assert_called_once()
            row = rig.receipt()
            self.assertTrue(row['startConsumed'])
            self.assertFalse(row['callbackCompleted'])
            self.assertFalse(row['startAcknowledged'])
            rig.write_fd.assert_not_called()
            self.assertEqual(row['commandStart']['commandPID'], 4343)
            self.assertFalse(row['commandReaped'])
            self.assertIsNone(row['returncode'])
            self.assertIsNone(row['guardianStatus'])
            self.assertTrue(row['guardianReaped'])
            self.assertEqual(rig.events, [('kill', builder.signal.SIGKILL), ('wait',)])

    def test_default_mode_has_no_observer_fields_and_rejects_start_wire(self):
        with capture_fixture() as rig:
            self.run_core(rig, None)
            receipt = rig.receipt()
            command = json.loads(rig.output.with_suffix('.command.json').read_text())
            for key in ('commandStart', 'startConsumed', 'callbackCompleted', 'startAcknowledged', 'commandStartFrameHex', 'guardianProtocolHex'):
                self.assertNotIn(key, receipt)
            for key in ('observer', 'startSchema', 'startAcknowledgment'):
                self.assertNotIn(key, command)
            self.assertNotIn('--notify-start', command['launchArgv'])
        with capture_fixture() as rig:
            rig.chunks[13] = [json.dumps(self.start_row(rig)).encode() + b'\n' + json.dumps(rig.record).encode(), b'']
            with self.assertRaises(ValueError):
                self.run_core(rig, None)

    def test_unsafe_start_identity_bypass_control(self):
        # Isolated mutant: skipping the start validator admits a wrong nonce.
        # The matching normal-path rejection is exercised above.
        with capture_fixture() as rig:
            wrong = dict(self.start_row(rig), token='wrong')
            rig.chunks[13] = [json.dumps(wrong).encode() + b'\n' + json.dumps(rig.record).encode(), b'']
            with patch.object(builder, 'command_start_status', return_value=wrong):
                receipt = self.run_core(rig, Mock())
            self.assertTrue(receipt['outputComplete'])
            self.assertEqual(receipt['commandStart']['token'], 'wrong')


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
            self.assertEqual(command['argv'], rig.argv)
            self.assertEqual(command['launchArgv'][-len(rig.argv)-1:], ['--', *rig.argv])
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

    def test_ack_reader_requires_exact_nonce_and_eof(self):
        guardian = builder.load('_guardian_ack_test', builder.GUARDIAN)
        for chunks in ([b'fixture-token\n', b''], [b'fixture-', b'token\n', b'']):
            with patch.object(guardian.os, 'read', side_effect=chunks):
                guardian.await_start_ack(15, 'fixture-token')
        for chunks in ([b''], [b'wrong\n', b''], [b'fixture-token', b''],
                       [b'fixture-token\nx'], [OSError('read failed')]):
            with self.subTest(chunks=chunks), patch.object(guardian.os, 'read', side_effect=chunks):
                with self.assertRaises((ValueError, OSError)):
                    guardian.await_start_ack(15, 'fixture-token')

    def test_ack_descriptor_invalid_before_child_launch(self):
        guardian = builder.load('_guardian_ack_fd_test', builder.GUARDIAN)
        for fd in (None, True, 2, 14):
            with self.subTest(fd=fd), \
                 patch.object(guardian.os, 'getpid', return_value=4242), \
                 patch.object(guardian.os, 'getpgrp', return_value=4242), \
                 patch.object(guardian.os, 'getsid', return_value=4242), \
                 patch.object(guardian.os, 'set_inheritable'), \
                 patch.object(guardian.os, 'close'), \
                 patch.object(guardian.os, 'write', side_effect=lambda fd, data: len(data)), \
                 patch.object(guardian.subprocess, 'Popen') as launch, \
                 patch.object(guardian.signal, 'pause', side_effect=RuntimeError('mock idle stop')):
                with self.assertRaisesRegex(RuntimeError, 'mock idle stop'):
                    guardian.guard(['/never'], 14, 'fixture-token',
                        builder.identity(builder.GUARDIAN)['sha256'], {},
                        notify_start=True, start_ack_fd=fd)
                launch.assert_not_called()

    def test_guardian_main_opt_in_flag_stays_before_native_separator(self):
        guardian = builder.load('_guardian_main_start_test', builder.GUARDIAN)
        args = [str(builder.GUARDIAN), '--status-fd', '14', '--token', 'token',
                '--source-sha', 'pin', '--environment-json', '{}', '--notify-start', '--start-ack-fd', '15',
                '--', '/never', '--notify-start']
        with patch.object(sys, 'argv', args), patch.object(guardian, 'guard') as guard:
            guardian.main()
        guard.assert_called_once_with(['/never', '--notify-start'], 14, 'token', 'pin', {}, notify_start=True, start_ack_fd=15)

    def test_guardian_start_precedes_wait_and_retains_child_on_write_failure(self):
        guardian = builder.load('_guardian_notify_test', builder.GUARDIAN)
        for failure in (None, 'start', 'final', 'both'):
            with self.subTest(writeFailure=failure):
                proc = Mock(pid=4343)
                writes, events, closes = [], [], []
                def write(fd, data):
                    kind = 'start' if data.endswith(b'\n') else 'final'
                    events.append(kind)
                    if failure in (kind, 'both'):
                        raise BrokenPipeError('mock private write failed')
                    writes.append(data)
                    return len(data)
                proc.wait.side_effect = lambda: events.append('wait-command') or 7
                acknowledgment = iter([b'fixture-token\n', b''])
                def read_ack(fd, size):
                    self.assertEqual(fd, 15)
                    data = next(acknowledgment)
                    self.assertLessEqual(len(data), size)
                    events.append('ack')
                    return data
                def close(fd):
                    closes.append(fd)
                    events.append(('close', fd))
                with patch.object(guardian.os, 'getpid', return_value=4242), \
                     patch.object(guardian.os, 'getpgrp', return_value=4242), \
                     patch.object(guardian.os, 'getsid', return_value=4242), \
                     patch.object(guardian.os, 'set_inheritable') as private, \
                     patch.object(guardian.os, 'close', side_effect=close), \
                     patch.object(guardian.os, 'write', side_effect=write), \
                     patch.object(guardian.os, 'read', side_effect=read_ack), \
                     patch.object(guardian.subprocess, 'Popen', return_value=proc) as spawn, \
                     patch.object(guardian.signal, 'pause', side_effect=RuntimeError('mock idle stop')) as pause:
                    with self.assertRaisesRegex(RuntimeError, 'mock idle stop'):
                        guardian.guard(['/never'], 14, 'fixture-token', builder.identity(builder.GUARDIAN)['sha256'],
                                       {'EXACT': 'declared'}, notify_start=True, start_ack_fd=15)
                if failure in ('start', 'both'):
                    proc.wait.assert_not_called()
                else:
                    proc.wait.assert_called_once()
                self.assertEqual(private.call_args_list, [call(14, False), call(15, False)])
                pause.assert_called_once()
                self.assertEqual(closes, [15, 1, 2, 14])
                expected = ['start'] + ([] if failure in ('start', 'both') else ['ack', 'ack'])
                expected += [('close', 15), ('close', 1), ('close', 2)]
                if failure not in ('start', 'both'):
                    expected += ['wait-command']
                self.assertEqual(events, expected + ['final', ('close', 14)])
                self.assertEqual(spawn.call_args.kwargs, dict(env={'EXACT': 'declared'}, close_fds=True, pass_fds=()))
                self.assertLessEqual(sum(map(len, writes)), builder.STATUS_BYTES)
                if failure is None:
                    frame, final = b''.join(writes).split(b'\n')
                    start = builder.command_start_status(frame, 4242, 'fixture-token', builder.identity(builder.GUARDIAN)['sha256'])
                    row = builder.guardian_status(final, 4242, 'fixture-token', builder.identity(builder.GUARDIAN)['sha256'])
                    self.assertEqual(start['commandPID'], 4343)
                    self.assertEqual(row['commandPID'], 4343)
                    self.assertEqual(row['returncode'], 7)
                    self.assertTrue(row['commandReaped'])
                elif failure == 'start':
                    # A failed start write must not reset proc=None and forge
                    # a launch failure for a successfully spawned command.
                    row = builder.guardian_status(b''.join(writes), 4242, 'fixture-token', builder.identity(builder.GUARDIAN)['sha256'])
                    self.assertFalse(row['commandReaped'])
                    self.assertEqual(row['commandPID'], 4343)
                    self.assertIn('mock private write failed', row['launchError'])

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
                expected = dict(schema=guardian.SCHEMA, token='fixture-token',
                    sourceSha256=builder.identity(builder.GUARDIAN)['sha256'], guardianPID=4242,
                    guardianPGID=4242, guardianSID=4242, commandPID=None if failure else 4343,
                    returncode=None if failure else 7, commandReaped=not failure,
                    launchError=guardian.bounded_error(OSError('x' * 1000)) if failure else None)
                self.assertEqual(b''.join(writes), json.dumps(expected, sort_keys=True, separators=(',', ':')).encode())
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
