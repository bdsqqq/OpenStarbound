"""synthetic producer sensitivity only: no native tools, OS child, or game runs."""
import math
from pathlib import Path
import signal
import subprocess
import unittest
from unittest import mock

import behavior_lab_id_map as lab
import id_map_capture as producer
import test_behavior_lab_id_map as fixtures


class SyntheticCaptureTests(unittest.TestCase):
    def setUp(self):
        self.patch(producer.subprocess, 'run', side_effect=AssertionError('native tools forbidden in synthetic tests'))
        self.fixture = fixtures.SyntheticFrontendTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.source = self.fixture.fixture('SYNTHETIC-source')
        self.runner = lab._legacy
        manifest = self.runner.load(self.source / 'manifest.json')
        self.binary = Path(manifest['binary']['path'])
        self.binary.chmod(0o700)
        self.assets = Path(manifest['assets']['path'])
        self.proof = manifest['buildProvenance']
        # private frozen validator otherwise probes native --version. this fixture
        # has never been compiled and is explicitly not game/build evidence.
        self.patch(self.runner, 'verified_build', return_value=self.proof)
        self.out = self.fixture.build / 'SYNTHETIC-capture'
        self.argv = [str(Path(lab.__file__).resolve()), 'capture', '--capture', str(self.binary),
                     '--assets', str(self.assets), '--output', str(self.out), '--timeout', '30']
        self.process = mock.Mock(pid=45678, returncode=0)
        self.process.poll.side_effect = lambda: self.process.returncode
        self.process.wait.side_effect = self.emit
        self.popen = self.patch(producer.subprocess, 'Popen', return_value=self.process)
        self.patch(self.runner, 'process_identity', return_value=('SYNTHETIC-NOT-OS-START', self.process.pid))
        self.stop = self.patch(self.runner, 'stop_process_group', side_effect=self.reap)

    def patch(self, target, name, **kwargs):
        patcher = mock.patch.object(target, name, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def reap(self, process):
        if process.returncode is None:
            process.returncode = -signal.SIGTERM

    def emit(self, timeout):
        # exercise the real decoder, image checks, restoration, inventory and
        # combined frontend validator on freshly emitted synthetic frame bytes.
        config = self.runner.load(self.out / 'scenario.json')
        frames = self.out / 'frames'
        for name in lab._proof.STAGES:
            envelope = self.runner.load(self.source / (name + '.json'))
            envelope['metadata']['idMapProof']['configuration'] = config
            self.runner.dump(frames / (name + '.json'), envelope)
            (frames / (name + '.png')).write_bytes((self.source / (name + '.png')).read_bytes())
        self.runner.dump(frames / lab.RESTORATION, self.runner.load(self.source / lab.RESTORATION))
        return 0

    def capture(self, **kwargs):
        args = dict(lab=lab, executable=self.binary, assets=self.assets, directory=self.out, timeout=30)
        args.update(kwargs)
        if 'frontend_argv' not in kwargs:
            self.argv = [str(Path(lab.__file__).resolve()), 'capture', '--capture', str(args['executable']),
                         '--assets', str(args['assets']), '--output', str(args['directory']),
                         '--timeout', str(args['timeout'])]
            args['frontend_argv'] = self.argv
        return producer.capture(**args)

    def assert_aborted(self):
        self.assertTrue((self.out / 'failure.json').is_file())
        self.assertFalse((self.out / 'frames/manifest.json').exists())
        self.assertTrue((self.out / 'launch.json').is_file())
        self.assertTrue((self.out / 'process.log').is_file())

    def test_synthetic_normal_seal_real_three_png_decoder_sidecar_and_postvalidate(self):
        real_validated = lab.validated
        with mock.patch.object(lab, 'validated', wraps=real_validated) as checked:
            frames = self.capture()
        checked.assert_called_once_with(frames)
        decoded, manifest = real_validated(frames)
        self.assertEqual(len(decoded), 3)
        self.assertEqual(self.runner.load(self.out / 'launch.json')['frontend']['argv'], self.argv)
        self.assertEqual(self.runner.load(self.out / lab.BINDING)['gameOrigin'], {'syntheticOnly': True})
        self.assertTrue((frames / lab.RESTORATION).is_file())
        self.assertEqual(manifest['exitCode'], 0)
        end = self.runner.load(self.out / 'process-exit.json')
        self.assertEqual(end['osStart'], 'SYNTHETIC-NOT-OS-START')
        self.assertIn('wallFinished', end)
        self.stop.assert_called_once_with(self.process)

    def test_prelaunch_receipt_native_command_and_isolation(self):
        def launch(command, **kwargs):
            receipt = self.runner.load(self.out / 'launch.json')
            self.assertEqual(command, [str(self.binary), '-bootconfig', str(self.out / 'sbinit.config')])
            self.assertEqual(receipt['command'], command)
            self.assertEqual(receipt['buildProvenance'], self.proof)
            self.assertEqual(receipt['gameOrigin'], {'syntheticOnly': True})
            self.assertEqual(receipt['frontend']['identities'], lab._frontend_identity())
            env = kwargs['env']
            self.assertNotIn('SteamAppId', env)
            self.assertNotIn('SteamGameId', env)
            self.assertEqual(env['STAR_BEHAVIOR_LAB'], str(self.out / 'scenario.json'))
            for name in ('HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME'):
                self.assertTrue(Path(env[name]).is_dir())
            self.assertTrue(kwargs['start_new_session'])
            boot = self.runner.load(self.out / 'sbinit.config')
            self.assertEqual(boot['defaultConfiguration']['windowedResolution'], [960, 540])
            self.assertFalse(boot['includeUGC'])
            self.assertEqual(boot['assetSources'][0], str(self.assets))
            return self.process
        self.popen.side_effect = launch
        with mock.patch.dict(producer.os.environ, SteamAppId='BAD', SteamGameId='BAD', STAR_BEHAVIOR_LAB='BAD'):
            self.capture()

    def test_missing_origin_rejected_before_output(self):
        self.fixture.origin.side_effect = lab.LabError('SYNTHETIC origin unavailable')
        with self.assertRaisesRegex(lab.LabError, 'origin unavailable'):
            self.capture()
        self.assertFalse(self.out.exists())
        self.popen.assert_not_called()

    def test_old_or_invalid_frontend_argv_rejected_before_output(self):
        for argv in ([], [str(lab.HERE / 'behavior_lab.py')], ['relative-legacy.py'], [str(lab.__file__), 1]):
            with self.subTest(argv=argv), self.assertRaises(lab.LabError):
                self.capture(frontend_argv=argv)
            self.assertFalse(self.out.exists())
        self.popen.assert_not_called()

    def test_nonfinite_nonpositive_and_overmax_timeout(self):
        for timeout in (math.nan, math.inf, -math.inf, 0, -1, 181, True):
            with self.subTest(timeout=timeout), self.assertRaises(lab.LabError):
                self.capture(timeout=timeout)
            self.assertFalse(self.out.exists())
        self.popen.assert_not_called()

    def test_missing_executable_and_nonexecutable(self):
        with self.assertRaises(lab.LabError):
            self.capture(executable=self.binary.parent / 'missing')
        self.binary.chmod(0o600)
        with self.assertRaisesRegex(lab.LabError, 'not executable'):
            self.capture()
        self.assertFalse(self.out.exists())
        self.popen.assert_not_called()

    def test_changed_asset_after_launch_no_manifest(self):
        def wait(timeout):
            self.emit(timeout)
            self.assets.write_bytes(b'SYNTHETIC changed assets')
            return 0
        self.process.wait.side_effect = wait
        with self.assertRaisesRegex(lab.LabError, 'assets/config/launch changed'):
            self.capture()
        self.assert_aborted()

    def test_nonzero_exit_keeps_reaped_receipt_no_manifest(self):
        self.process.returncode = 7
        self.process.wait.side_effect = lambda timeout: 7
        with self.assertRaisesRegex(lab.LabError, 'client exited 7'):
            self.capture()
        self.assert_aborted()
        self.assertEqual(self.runner.load(self.out / 'process-exit.json')['exitCode'], 7)
        self.stop.assert_called_once_with(self.process)

    def test_timeout_reaps_owned_group_durable_exit_no_manifest(self):
        self.process.returncode = None
        self.process.wait.side_effect = subprocess.TimeoutExpired('SYNTHETIC', 30)
        with self.assertRaises(subprocess.TimeoutExpired):
            self.capture()
        self.assert_aborted()
        self.stop.assert_called_once_with(self.process)
        self.assertEqual(self.runner.load(self.out / 'process-exit.json')['status'], 'reaped')

    def test_sigterm_repeated_during_cleanup_cannot_interrupt_reaping(self):
        previous = signal.getsignal(signal.SIGTERM)
        self.process.returncode = None
        self.process.wait.side_effect = lambda timeout: signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        def reap(process):
            handler = signal.getsignal(signal.SIGTERM)
            handler(signal.SIGTERM, None)
            handler(signal.SIGTERM, None)
            process.returncode = -signal.SIGTERM
        self.stop.side_effect = reap
        with self.assertRaisesRegex(lab.LabError, 'SIGTERM'):
            self.capture()
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)
        self.assert_aborted()
        self.stop.assert_called_once_with(self.process)
        self.assertTrue((self.out / 'process-exit.json').is_file())

    def test_keyboardinterrupt_reaps_owned_group(self):
        self.process.returncode = None
        self.process.wait.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.capture()
        self.assert_aborted()
        self.stop.assert_called_once_with(self.process)

    def test_clock_discontinuity_no_manifest(self):
        self.patch(self.runner, 'validate_capture_clock', side_effect=lab.LabError('clock discontinuity'))
        with self.assertRaisesRegex(lab.LabError, 'clock discontinuity'):
            self.capture()
        self.assert_aborted()

    def test_changed_frontend_origin_overlay_and_build_rejected(self):
        for index, kind in enumerate(('frontend', 'origin', 'overlays', 'proof')):
            self.out = self.fixture.build / ('SYNTHETIC-mutation-' + str(index))
            target, name, first = {
                'frontend': (lab, '_frontend_identity', lab._frontend_identity()),
                'origin': (lab, '_check_game_origin', {'syntheticOnly': True}),
                'overlays': (self.runner, 'overlay_identity', self.runner.overlay_identity(lab.SCENARIO)),
                'proof': (lab, 'verified_build', self.proof),
            }[kind]
            # origin is checked by verified_build as well as directly by producer.
            if kind == 'origin':
                sequence = [first, first, first, {'SYNTHETIC-changed': True}]
            else:
                sequence = [first, {'SYNTHETIC-changed': True}]
            with self.subTest(kind=kind), mock.patch.object(target, name, side_effect=sequence):
                with self.assertRaises(lab.LabError):
                    self.capture()
            self.assert_aborted()

    def test_binary_boot_configuration_and_launch_mutation_no_manifest(self):
        for index, relative in enumerate(('binary', 'sbinit.config', 'scenario.json', 'launch.json')):
            self.out = self.fixture.build / ('SYNTHETIC-file-mutation-' + str(index))
            def wait(timeout):
                self.emit(timeout)
                path = self.binary if relative == 'binary' else self.out / relative
                path.write_bytes(path.read_bytes() + b'\n ')
                return 0
            self.process.wait.side_effect = wait
            with self.subTest(relative=relative), self.assertRaisesRegex(lab.LabError, 'changed while client ran'):
                self.capture()
            self.assert_aborted()
            if relative == 'binary':
                # restore the synthetic fixture, never production data.
                self.binary.write_bytes(self.binary.read_bytes()[:-2])

    def test_corrupt_png_rejected_by_real_image_decoder(self):
        def wait(timeout):
            self.emit(timeout)
            path = self.out / 'frames' / (lab._proof.STAGES[0] + '.png')
            image = self.runner.image(path)
            image.putpixel((320, 240), (1, 2, 3, 255))
            image.save(path)
            return 0
        self.process.wait.side_effect = wait
        with self.assertRaisesRegex(lab.LabError, 'pixels'):
            self.capture()
        self.assert_aborted()

    def test_popen_failure_preserves_launch_log_and_failure_without_fake_process(self):
        previous = signal.getsignal(signal.SIGTERM)
        self.popen.side_effect = OSError('SYNTHETIC Popen failure')
        with self.assertRaisesRegex(OSError, 'Popen failure'):
            self.capture()
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)
        self.assert_aborted()
        self.stop.assert_not_called()
        self.assertFalse((self.out / 'process-start.json').exists())
        self.assertFalse((self.out / 'process-exit.json').exists())

    def test_sigterm_during_popen_is_deferred_until_owned_process_available(self):
        previous = signal.getsignal(signal.SIGTERM)
        self.process.returncode = None
        def launch(*args, **kwargs):
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
            return self.process
        self.popen.side_effect = launch
        with self.assertRaisesRegex(lab.LabError, 'SIGTERM'):
            self.capture()
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)
        self.assert_aborted()
        self.process.wait.assert_not_called()
        self.stop.assert_called_once_with(self.process)
        self.assertTrue((self.out / 'process-start.json').is_file())
        self.assertTrue((self.out / 'process-exit.json').is_file())

    def test_sigint_during_constructor_preserves_owned_child_and_cleanup(self):
        previous = signal.getsignal(signal.SIGINT)
        self.addCleanup(signal.signal, signal.SIGINT, previous)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        self.process.returncode = None
        def launch(*args, **kwargs):
            signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
            return self.process
        self.popen.side_effect = launch
        try:
            self.capture()
        except (lab.LabError, KeyboardInterrupt):
            pass
        self.stop.assert_called_once_with(self.process)
        self.assertTrue((self.out / 'process-start.json').is_file())
        self.assertTrue((self.out / 'process-exit.json').is_file())
        self.assertIs(signal.getsignal(signal.SIGINT), signal.default_int_handler)

    def test_combined_postvalidator_failure_retains_rejected_bytes_not_manifest(self):
        with mock.patch.object(lab, 'validated', side_effect=lab.LabError('SYNTHETIC combined rejection')):
            with self.assertRaisesRegex(lab.LabError, 'combined rejection'):
                self.capture()
        self.assert_aborted()
        self.assertTrue((self.out / 'rejected-manifest.json').is_file())

    def test_invalid_restore_is_not_stubbed(self):
        emit = self.emit
        def bad(timeout):
            emit(timeout)
            path = self.out / 'frames' / lab.RESTORATION
            value = self.runner.load(path)
            value['value'] = True
            path.write_text(__import__('json').dumps(value))
            return 0
        self.process.wait.side_effect = bad
        with self.assertRaisesRegex(lab.LabError, 'restoration'):
            self.capture()
        self.assert_aborted()


if __name__ == '__main__':
    unittest.main()
