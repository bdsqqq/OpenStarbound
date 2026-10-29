"""Pure producer controls. Popen is mocked; no game/probe/server is launched."""
import copy
import inspect
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import static_vector_capture as p
import behavior_lab_static_vector as lab


class ProducerTests(unittest.TestCase):
    def test_birth_reader_darwin_struct_synthetic_and_no_probe_subprocess(self):
        import ctypes
        library = mock.Mock()
        def read(pid, flavor, arg, pointer, size):
            self.assertEqual((pid, flavor, arg, size), (12345, 3, 0, 136))
            pointer._obj.pid = pid
            pointer._obj.pgid = pid
            pointer._obj.startSeconds = 1000
            pointer._obj.startMicroseconds = 123
            return size
        library.proc_pidinfo.side_effect = read
        with mock.patch.object(p.sys, 'platform', 'darwin'), mock.patch.object(ctypes, 'CDLL', return_value=library), \
                mock.patch.object(p.subprocess, 'run', side_effect=AssertionError('unsupervised probe')):
            self.assertEqual(p.process_identity(12345), ('darwin-proc-bsdinfo:1000:123', 12345))
            library.proc_pidinfo.side_effect = None
            library.proc_pidinfo.return_value = 0
            with self.assertRaises(lab.LabError):
                p.process_identity(12345)

    def test_timeout_rejects_bool_nonfinite_and_excess(self):
        for value in (True, False, 0, -1, 181, float('inf'), float('nan'), '180'):
            with self.subTest(value=value), self.assertRaises(lab.LabError):
                p.validate_timeout(value)
        p.validate_timeout(180)

    def test_environment_is_explicit_and_no_loader_or_steam_inheritance(self):
        with mock.patch.dict(os.environ, {'SteamAppId': 'bad', 'SteamGameId': 'bad', 'DYLD_INSERT_LIBRARIES': 'bad',
                                         'LD_PRELOAD': 'bad', 'STAR_BEHAVIOR_LAB': 'bad', 'HOME': '/unsafe'}, clear=True):
            env = p.environment(Path('/synthetic'))
        self.assertEqual(env['STAR_BEHAVIOR_LAB'], '/synthetic/scenario.json')
        self.assertEqual(env['HOME'], '/synthetic/home')
        self.assertFalse(set(env) & {'SteamAppId', 'SteamGameId', 'DYLD_INSERT_LIBRARIES', 'LD_PRELOAD'})

    def test_boot_all26_matches_acquired_special_cases(self):
        for scene in lab.SCENARIOS:
            boot = p.boot_configuration(scene, '/synthetic/assets.pak', Path('/synthetic/storage'))
            self.assertEqual(boot['assetDirectories'], [])
            self.assertFalse(boot['includeUGC'])
            defaults = boot['defaultConfiguration']
            self.assertFalse(defaults['serverAdvertise'])
            self.assertEqual('optionParserProof' in defaults, scene == 'option-parser-room')
            self.assertEqual('safe' in defaults, scene in ('encoding-room', 'vlq-room', 'bytes-room', 'compression-room', 'zstd-room', 'path-embed-room'))
        self.assertEqual(len(p.boot_configuration(lab.SCENARIO, '/assets', Path('/storage'))['assetSources']), 3)

    def test_actual_frontend_argv_all26_and_substitution_rejected(self):
        base = [str(Path(lab.__file__).resolve()), 'capture', '--capture', '/synthetic/binary', '--assets', '/synthetic/assets', '--output', '/synthetic/output']
        for scenario in lab.SCENARIOS:
            lab._capture_arguments([*base, '--scenario', scenario], Path('/synthetic/binary'), Path('/synthetic/assets'), Path('/synthetic/output'), 180, scenario)
        lab._capture_arguments(base, Path('/synthetic/binary'), Path('/synthetic/assets'), Path('/synthetic/output'), 180, lab.SCENARIO)
        for argv in (None, [str(lab.HERE / 'behavior_lab.py'), *base[1:]], [*base, '--scenario', 'id-map-room'], [*base, '--timeout', '90'], [*base, '--unknown']):
            with self.assertRaises(lab.LabError):
                lab._capture_arguments(argv, Path('/synthetic/binary'), Path('/synthetic/assets'), Path('/synthetic/output'), 180, lab.SCENARIO)

    def test_typed_producer_mismatch_stops_before_popen(self):
        request = p.CaptureRequest(Path('/synthetic/binary'), Path('/synthetic/assets'), Path('/synthetic/output'), 180, lab.SCENARIO,
            (str(Path(lab.__file__).resolve()), 'capture', '--capture', '/synthetic/binary', '--assets', '/synthetic/assets', '--output', '/synthetic/output'))
        with mock.patch.object(lab, '_frontend_identity', return_value={'actual': True}), mock.patch.object(p.subprocess, 'Popen') as popen:
            with self.assertRaisesRegex(lab.LabError, 'identities differ'):
                p.capture(request, p.ProducerIdentity({'oldProducer': True}))
            popen.assert_not_called()

    def test_launch_protocol_guards_stdin_clock_and_sanitized_env(self):
        directory = Path('/synthetic/output')
        launch = dict(timeoutSeconds=180, sourceClock=dict(monotonic=100, wall=1000), environment=p.environment(directory),
            processProtocol=dict(cwd=str(directory), stdin='DEVNULL', startNewSession=True, clock='monotonic+wall-v1'))
        start = dict(monotonicStarted=101, wallStarted=1001)
        end = dict(monotonicFinished=102, wallFinished=1002)
        manifest = dict(elapsedSeconds=2)
        with mock.patch.object(p.r, 'load', side_effect=lambda path: start if path.name == 'process-start.json' else end):
            p.validate_launch_protocol(directory, launch, manifest)
            for mutate in (lambda v: v['processProtocol'].update(stdin='INHERIT'),
                           lambda v: v['environment'].update(DYLD_INSERT_LIBRARIES='bad'),
                           lambda v: v['sourceClock'].update(wall=500),
                           lambda v: v.update(timeoutSeconds=True)):
                bad = copy.deepcopy(launch)
                mutate(bad)
                with self.assertRaises(lab.LabError):
                    p.validate_launch_protocol(directory, bad, manifest)

    def test_all26_typed_producer_launch_dispatch_with_only_fake_process_data(self):
        # This tests launch production, NOT native decoding/origin or OS evidence.
        r = p.r
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            build = root / 'build'
            build.mkdir()
            binary, assets = root / 'SYNTHETIC-NEVER-EXECUTED', root / 'synthetic.pak'
            binary.write_bytes(b'not native code')
            binary.chmod(0o700)
            assets.write_bytes(b'fake assets')
            identities = {'syntheticOnly': True}
            opaque = {'schema': 'static-vector-whole-game-origin-v1', 'uninterpretedBinding': ['exact', {'keep': True}]}
            proof = {'build_identity': {'cache': lab.scenarios.configuration.profiles()['reference']}}
            for scenario in lab.SCENARIOS:
                directory = build / scenario
                argv = (str(Path(lab.__file__).resolve()), 'capture', '--capture', str(binary), '--assets', str(assets),
                        '--output', str(directory), '--scenario', scenario)
                request = p.CaptureRequest(binary, assets, directory, 180, scenario, argv)
                def spawn(command, **kwargs):
                    launch = r.load(directory / 'launch.json')
                    self.assertEqual(launch['gameOrigin'], opaque)
                    self.assertEqual(launch['frontend'], {'identities': identities, 'argv': list(argv)})
                    self.assertEqual(launch['command'], command)
                    self.assertEqual(kwargs['stdin'], p.subprocess.DEVNULL)
                    self.assertTrue(kwargs['start_new_session'])
                    self.assertEqual(r.load(directory / 'scenario.json')['scenario'], scenario)
                    # Fake child data, only for the outer binding identity.
                    for name in (lab.RESTORATION, 'idmap-restoration.json'):
                        r.dump(directory / 'frames' / name, {'syntheticOnly': True})
                    child = mock.Mock(pid=12345, returncode=0)
                    child.wait.return_value = 0
                    child.poll.return_value = 0
                    return child
                decoded = {'stage': dict(receipt={'scenario': scenario}, dimensions=[1, 1], pngSha256='fake',
                                         receiptSha256='fake', pixelsSha256='fake')}
                with self.subTest(scenario=scenario), mock.patch.object(r, 'BUILD', build), \
                        mock.patch.object(lab, '_frontend_identity', return_value=identities), \
                        mock.patch.object(lab, 'verified_build', return_value=proof), \
                        mock.patch.object(lab, '_check_game_origin', return_value=opaque), \
                        mock.patch.object(p.subprocess, 'Popen', side_effect=spawn) as popen, \
                        mock.patch.object(p, 'process_identity', return_value=('SYNTHETIC-OS-START', 12345)), \
                        mock.patch.object(r, 'stop_process_group') as stop, \
                        mock.patch.object(lab, 'captures', return_value=decoded) as decode, \
                        mock.patch.object(lab.scenarios, 'bind_old'), \
                        mock.patch.object(lab, 'validated', return_value=(decoded, {})):
                    result = p.capture(request, p.ProducerIdentity(identities))
                    self.assertEqual(result, directory / 'frames')
                    popen.assert_called_once()
                    stop.assert_called_once()
                    decode.assert_called_once()
                    binding = r.load(directory / lab.BINDING)
                    self.assertEqual(binding['gameOrigin'], opaque)
                    self.assertEqual(binding['frontend']['identities'], identities)

    def test_source_ownership_and_failure_protocol_projection(self):
        source = inspect.getsource(p.capture)
        self.assertLess(source.index("r.durable_dump(directory / 'launch.json'"), source.index('subprocess.Popen('))
        self.assertLess(source.index('r.validate_process_binding('), source.index('frontend.captures('))
        self.assertIn('stdin=subprocess.DEVNULL', source)
        self.assertIn('start_new_session=True', source)
        self.assertIn('r.stop_process_group(process)', source)
        self.assertIn("manifest_path.rename(directory / 'rejected-manifest.json')", source)
        self.assertIn('except BaseException as failure:', source)
        for forbidden in ('lab.__file__', '_legacy.', 'verified_build =', 'setattr(', '--version'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
