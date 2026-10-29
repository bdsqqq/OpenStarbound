"""Source-only adapter controls; every process launch remains mocked."""
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('enclosure_runner_test_subject',
                                              Path(__file__).with_name('enclosure_runner.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
fixture = runner._load('_release_runner_fixture', Path(__file__).with_name('test_enclosure_release.py'))
fixture.er = runner.er


class AdapterTests(unittest.TestCase):
    def setUp(self):
        fixture.ReleaseTests.setUp(self)
        self.core_calls = []
        self.core_hook = lambda stem, kwargs: None
        self.result_hook = lambda receipt: None
        self.capture_hook = lambda path: None
        self.core_patch = patch.object(runner.builder, '_supervise_command', side_effect=self.core)
        self.core_patch.start()
        self.addCleanup(self.core_patch.stop)
        self.launch = patch.object(runner.builder.subprocess, 'Popen',
                                  side_effect=AssertionError('actual process forbidden')).start()
        patch.object(runner.time, 'monotonic', side_effect=lambda: self.t).start()
        # Primitive's default clock was captured at definition; explicit patch
        # delegates to the REAL primitive with only its clock supplied.
        primitive = runner.er.release_owned_image
        patch.object(runner.er, 'release_owned_image', side_effect=lambda owner, run:
                     primitive(owner, run, now=lambda: self.t)).start()

    def core(self, argv, cwd, env, output, **kwargs):
        self.core_calls.append((list(argv), cwd, env, output, kwargs))
        kwargs['validate']()
        self.assertGreater(kwargs['remaining_seconds'](), 0)
        self.assertEqual(cwd, runner.ROOT / 'source')
        self.assertEqual(env['PATH'], '/usr/bin:/bin')
        self.assertEqual(kwargs['limits'], runner.LIMITS)
        self.assertEqual(kwargs['scope'], runner.SCOPE)
        self.assertNotIn('originalExperiment', kwargs['witness'])
        kwargs['check_output'](output.with_suffix('.command.json'))
        kwargs['write_record'](output.with_suffix('.command.json'),
                               dict(argv=argv, scope=kwargs['scope'], witness=kwargs['witness']))
        self.core_hook(output.name, kwargs)
        raw = (self.raw if self.raw is not None else plistlib.dumps({'images': self.records})) if output.name == 'info' else b'\xff\x00\r\n'
        streams = {}
        for name, data in (('stdout', raw), ('stderr', b'\x80\r\n')):
            path = output.with_suffix('.' + name)
            kwargs['check_output'](path)
            with path.open('xb') as file:
                file.write(data)
            self.capture_hook(path)
            streams[name] = dict(bytesRead=len(data), bytesWritten=len(data), eof=True, overflow=None)
        if output.name == 'detach':
            self.mounted = False
        kwargs['validate']()
        receipt = dict(outputComplete=True, commandReaped=True, guardianReaped=True,
                       reaped=True, returncode=0, failure=None, cleanupFailure=None,
                       scope=kwargs['scope'], streams=streams)
        self.result_hook(receipt)
        kwargs['write_record'](output.with_suffix('.receipt.json'), receipt)
        return receipt

    def info(self, run, deadline=None):
        return run([runner.er.TOOL, 'info', '-plist'],
                   deadline_monotonic=self.t + 30 if deadline is None else deadline)

    def detach(self, run, deadline=None):
        return run([runner.er.TOOL, 'detach', self.owner['device']],
                   deadline_monotonic=self.t + 30 if deadline is None else deadline)

    def test_public_release_wires_primitive_core_exact_bytes_and_opaque_failure(self):
        original = object()  # deliberately not JSON-safe
        self.owner['originalExperiment'] = original
        result = runner.release(self.owner)
        self.assertIs(result['originalExperiment'], original)
        self.assertEqual(result['scope'], runner.SCOPE)
        self.assertEqual([call[0] for call in self.core_calls],
                         [[runner.er.TOOL, 'info', '-plist'],
                          [runner.er.TOOL, 'detach', self.owner['device']]])
        self.assertEqual(result['deadline_monotonic'], 1030)
        self.assertEqual(result['detach']['stdout'], b'\xff\x00\r\n')
        self.assertEqual(result['detach']['stderr'], b'\x80\r\n')
        root = self.root / 'release-evidence'
        self.assertEqual(len(list(root.iterdir())), 8)
        for path in root.glob('*.json'):
            self.assertLessEqual(path.stat().st_size, runner.RECORD_BYTES)
            self.assertEqual(json.loads(path.read_text())['scope'], runner.SCOPE)
        self.launch.assert_not_called()

    def test_expired_acquisition_does_not_block_separate_release_clock(self):
        with self.assertRaises(runner.er.ReleaseError):
            runner.er.need(self.t < self.owner['originalExperiment']['deadline_monotonic'], 'old acquisition expired')
        result = runner.release(self.owner)
        self.assertEqual(result['originalExperiment']['result'], 'FAIL')
        self.assertEqual(result['deadline_monotonic'], 1030)
        self.assertTrue(result['detach']['reaped'])
        with patch.object(runner.builder.subprocess, 'Popen') as launch:
            with self.assertRaises(ValueError):
                runner.builder.supervise(['/never-executed'], runner.ROOT / 'source', {},
                    self.root / 'info', {})
            launch.assert_not_called()  # release is not a native phase bypass

    def test_factory_requires_info_and_rejects_arbitrary_argv_or_fd(self):
        run = runner.make_runner(self.owner)
        for argv in ([runner.er.TOOL, 'detach', self.owner['device']],
                     [runner.er.TOOL, 'info', '-plist', '--status-fd', '7'],
                     [runner.er.TOOL, 'detach', '-force', self.owner['device']],
                     ['sudo', runner.er.TOOL], ['/bin/sh', '-c', 'true'],
                     (runner.er.TOOL, 'info', '-plist'), [7]):
            with self.subTest(argv=argv), self.assertRaises(runner.er.ReleaseError):
                run(argv, deadline_monotonic=1030)
        self.assertEqual(self.core_calls, [])

    def test_exact_same_absolute_deadline_and_no_clock_renewal(self):
        run = runner.make_runner(self.owner)
        self.info(run, 1029)
        self.t += 1
        with self.assertRaisesRegex(runner.er.ReleaseError, 'deadline changed'):
            self.detach(run, 1030)
        self.detach(run, 1029)
        self.assertEqual(len(self.core_calls), 2)

    def test_invalid_expired_or_extended_deadlines(self):
        run = runner.make_runner(self.owner)
        for deadline in (True, False, float('nan'), float('inf'), 0, 999, 1000, 1031):
            with self.subTest(deadline=deadline), self.assertRaises(runner.er.ReleaseError):
                self.info(run, deadline)
        self.assertEqual(self.core_calls, [])

    def test_unassociated_info_never_allows_detach_even_direct_factory(self):
        self.records[0]['system-entities'][1]['mount-point'] += '-wrong'
        run = runner.make_runner(self.owner)
        with self.assertRaises(runner.er.ReleaseError):
            self.info(run)
        with self.assertRaisesRegex(runner.er.ReleaseError, 'positive info'):
            self.detach(run)
        self.assertEqual(len(self.core_calls), 1)

    def test_owner_numeric_type_drift_rejected_before_launch(self):
        run = runner.make_runner(self.owner)
        self.owner['image']['size'] = float(self.owner['image']['size'])
        with self.assertRaises(runner.er.ReleaseError):
            self.info(run)
        self.assertEqual(self.core_calls, [])

    def test_stream_counter_type_is_exact(self):
        run = runner.make_runner(self.owner)
        def mutate(receipt):
            row = receipt['streams']['stdout']
            row['bytesRead'] = float(row['bytesRead'])
        self.result_hook = mutate
        with self.assertRaises(runner.er.ReleaseError):
            self.info(run)

    def test_receipt_scope_is_exact(self):
        run = runner.make_runner(self.owner)
        self.result_hook = lambda receipt: receipt.update(scope='NATIVE_ADMISSION')
        with self.assertRaises(runner.er.ReleaseError):
            self.info(run)

    def test_mount_rechecked_immediately_before_detach(self):
        run = runner.make_runner(self.owner)
        self.info(run)
        self.mounted = False
        with self.assertRaises(runner.er.ReleaseError):
            self.detach(run)
        self.assertEqual(len(self.core_calls), 1)

    def test_wrong_owner_tool_and_image_rejected_before_evidence(self):
        self.owner['image']['st_ino'] += 1
        with self.assertRaises(runner.er.ReleaseError):
            runner.make_runner(self.owner)
        self.assertFalse((self.root / 'release-evidence').exists())
        self.owner['image']['st_ino'] -= 1
        self.owner['tool']['sha256'] = '0' * 64
        with self.assertRaises(runner.er.ReleaseError):
            runner.make_runner(self.owner)
        self.assertFalse((self.root / 'release-evidence').exists())

    def test_owner_drift_rejected_before_launch(self):
        run = runner.make_runner(self.owner)
        self.owner['device'] = '/dev/disk42'
        with self.assertRaisesRegex(runner.er.ReleaseError, 'owner changed'):
            self.info(run)
        self.assertEqual(self.core_calls, [])

    def test_same_bytes_tool_inode_replacement_rejected(self):
        run = runner.make_runner(self.owner)
        replacement = self.root / 'replacement'
        replacement.write_bytes(self.tool.read_bytes())
        replacement.replace(self.tool)
        with self.assertRaisesRegex(runner.er.ReleaseError, 'input drift'):
            self.info(run)
        self.assertEqual(self.core_calls, [])

    def test_source_drift_rejected_without_touching_real_source(self):
        run = runner.make_runner(self.owner)
        original = runner._fingerprint
        def changed(path):
            fingerprint = original(path)
            return (*fingerprint[:-1], fingerprint[-1] + 1) if path == Path(runner.__file__).resolve() else fingerprint
        with patch.object(runner, '_fingerprint', side_effect=changed):
            with self.assertRaisesRegex(runner.er.ReleaseError, 'input drift'):
                self.info(run)
        self.assertEqual(self.core_calls, [])

    def test_evidence_root_is_fixed_exclusive_and_outside_mount(self):
        run = runner.make_runner(self.owner)
        self.assertTrue(callable(run))
        with self.assertRaises(FileExistsError):
            runner.make_runner(self.owner)
        self.assertFalse((self.root / 'release-evidence').is_relative_to(self.mount))
        self.assertEqual(runner.EVIDENCE_LOGICAL_BYTES,
                         2 * (4 * 256 * 1024 + 1024 * 1024 + 64 * 1024 + 2 * 64 * 1024))

    def test_evidence_alias_and_arbitrary_output_rejected(self):
        def bad_path(stem, kwargs):
            for path in (self.root / 'arbitrary.stdout', self.root / 'release-evidence/other.stdout',
                         self.root / 'release-evidence/info.stdout/../detach.stdout'):
                with self.assertRaises(runner.er.ReleaseError):
                    kwargs['check_output'](path)
        self.core_hook = bad_path
        runner.release(self.owner)

    def test_evidence_under_mount_rejected_before_directory_creation(self):
        owner = dict(self.owner, root=str(self.mount))
        with patch.object(runner.er, 'validate_owner'), \
             patch.object(runner.er, 'mounted_state', return_value=self.host):
            with self.assertRaisesRegex(runner.er.ReleaseError, 'under mount'):
                runner.make_runner(owner)
        self.assertFalse((self.mount / 'release-evidence').exists())

    def test_clock_regression_rejected_before_second_launch(self):
        run = runner.make_runner(self.owner)
        self.info(run)
        self.t -= 1
        with self.assertRaisesRegex(runner.er.ReleaseError, 'regressed'):
            self.detach(run, 1030)
        self.assertEqual(len(self.core_calls), 1)

    def test_failed_partial_blocks_retry_without_new_names(self):
        def fail(stem, kwargs):
            path = self.root / 'release-evidence/.info.receipt.json.partial'
            path.write_bytes(b'partial')
        self.core_hook = fail
        with self.assertRaises(FileExistsError):
            runner.release(self.owner)
        root = self.root / 'release-evidence'
        before = sorted(path.name for path in root.iterdir())
        with self.assertRaises(FileExistsError):
            runner.release(self.owner)
        self.assertEqual(before, sorted(path.name for path in root.iterdir()))

    def test_receipt_no_reaped_nonzero_incomplete_or_overflow_is_not_result(self):
        # One exclusive evidence directory per owner; subfixtures live below the
        # original root but never select arbitrary output destinations for run.
        cases = [('commandReaped', False), ('guardianReaped', False), ('reaped', False),
                 ('returncode', 7), ('returncode', False), ('outputComplete', False),
                 ('failure', 'timeout'), ('cleanupFailure', 'close failed')]
        for index, (key, value) in enumerate(cases):
            child = self.root / ('owner-%d' % index)
            child.mkdir()
            # image/mount remain physically under the original owner root, so
            # each independent fixture changes only evidence's owner root.
            with patch.object(runner.er, 'validate_owner'), patch.object(runner.er, 'mounted_state', return_value=self.host), \
                 patch.object(runner.er, 'image_state'), patch.object(runner.er, 'tool_state'):
                owner = dict(self.owner, root=str(child))
                self.result_hook = lambda receipt, k=key, v=value: receipt.update({k: v})
                with self.subTest(key=key), self.assertRaises(runner.er.ReleaseError):
                    runner.make_runner(owner)([runner.er.TOOL, 'info', '-plist'], deadline_monotonic=1030)
                self.assertTrue((child / 'release-evidence/info.receipt.json').exists())

    def test_stream_overflow_or_incomplete_eof_denied_after_receipt(self):
        self.result_hook = lambda receipt: receipt['streams']['stdout'].update(overflow={'sizeBytes': 1})
        with self.assertRaises(runner.er.ReleaseError):
            runner.release(self.owner)
        self.assertTrue((self.root / 'release-evidence/info.receipt.json').exists())

    def test_oversized_physical_capture_denied_after_receipt(self):
        def enlarge(path):
            if path.suffix == '.stderr':
                with path.open('ab') as file:
                    file.write(b'x' * runner.LIMITS['stderrBytes'])
        self.capture_hook = enlarge
        with self.assertRaisesRegex(runner.er.ReleaseError, 'capture byte limit'):
            runner.release(self.owner)
        self.assertTrue((self.root / 'release-evidence/info.receipt.json').exists())

    def test_capture_symlink_and_hardlink_rejected(self):
        path = self.root / 'capture'
        path.write_bytes(b'tiny')
        alias = self.root / 'alias'
        alias.symlink_to(path)
        with self.assertRaises(runner.er.ReleaseError):
            runner._read_capture(alias, 10)
        alias.unlink()
        os.link(path, alias)
        with self.assertRaises(runner.er.ReleaseError):
            runner._read_capture(path, 10)

    def test_timeout_keeps_receipt_and_original_exception_identity(self):
        error = TimeoutError('release deadline expired')
        def failing(argv, cwd, env, output, **kwargs):
            kwargs['write_record'](output.with_suffix('.receipt.json'),
                dict(scope=runner.SCOPE, outputComplete=False, guardianReaped=True,
                     commandReaped=False, failure=str(error)))
            raise error
        with patch.object(runner.builder, '_supervise_command', side_effect=failing):
            with self.assertRaises(TimeoutError) as caught:
                runner.release(self.owner)
        self.assertIs(caught.exception, error)
        receipt = json.loads((self.root / 'release-evidence/info.receipt.json').read_text())
        self.assertFalse(receipt['commandReaped'])
        self.assertEqual(self.owner['originalExperiment']['result'], 'FAIL')

    def test_caller_can_retain_original_failure_when_release_fails(self):
        original = RuntimeError('original failed acquisition')
        self.result_hook = lambda receipt: receipt.update(returncode=7)
        release_error = None
        try:
            try:
                raise original
            finally:
                try:
                    runner.release(self.owner)
                except Exception as error:
                    release_error = error
        except RuntimeError as caught:
            self.assertIs(caught, original)
        self.assertIsInstance(release_error, runner.er.ReleaseError)
        self.assertEqual(self.owner['originalExperiment']['result'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
