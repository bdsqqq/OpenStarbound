"""Pure producer controls: guardian execution mocked, no process/game launched."""
import copy
import ctypes
import inspect
import os
from pathlib import Path
import unittest
from unittest import mock

import static_vector_capture as p
import behavior_lab_static_vector as lab
import static_vector_capture_protocol as q
from test_static_vector_capture_protocol import namespace, fake_actor


class ProducerTests(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(p.subprocess, 'Popen', side_effect=AssertionError('NO process launch in Source tests'))
        self.popen = patch.start()
        self.addCleanup(patch.stop)

    def test_birth_reader_darwin_struct_synthetic_and_no_probe_subprocess(self):
        library = mock.Mock()
        def read(pid, flavor, arg, pointer, size):
            self.assertEqual((pid, flavor, arg, size), (12345, 3, 0, 136))
            pointer._obj.pid = pid
            pointer._obj.pgid = 4242
            pointer._obj.startSeconds = 1000
            pointer._obj.startMicroseconds = 123
            return size
        library.proc_pidinfo.side_effect = read
        with mock.patch.object(p.sys, 'platform', 'darwin'), mock.patch.object(ctypes, 'CDLL', return_value=library):
            self.assertEqual(p.process_identity(12345), ('darwin-proc-bsdinfo:1000:123', 4242))
            library.proc_pidinfo.side_effect = None
            library.proc_pidinfo.return_value = 0
            with self.assertRaises(lab.LabError):
                p.process_identity(12345)
        self.popen.assert_not_called()

    def test_timeout_rejects_bool_nonfinite_and_excess(self):
        for value in (True, False, 0, -1, 181, float('inf'), float('nan'), '180'):
            with self.subTest(value=value), self.assertRaises(lab.LabError):
                p.validate_timeout(value)
        p.validate_timeout(180)

    def test_environment_is_explicit_and_tmpdir_never_inherited(self):
        with mock.patch.dict(os.environ, {'SteamAppId': 'bad', 'SteamGameId': 'bad', 'DYLD_INSERT_LIBRARIES': 'bad',
                                         'LD_PRELOAD': 'bad', 'STAR_BEHAVIOR_LAB': 'bad', 'HOME': '/unsafe',
                                         'TMPDIR': '/unsafe', 'LANG': 'en_US.UTF-8'}, clear=True):
            env = p.environment(Path('/synthetic'))
        self.assertEqual(env['STAR_BEHAVIOR_LAB'], '/synthetic/scenario.json')
        self.assertEqual(env['HOME'], '/synthetic/home')
        self.assertEqual(env['TMPDIR'], '/synthetic/home/tmp')
        self.assertEqual(env['LANG'], 'en_US.UTF-8')
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
        for argv in (None, [str(lab.HERE / 'behavior_lab.py'), *base[1:]], [*base, '--scenario', 'id-map-room'],
                     [*base, '--timeout', '90'], [*base, '--unknown'],
                     [*base, '--output', '/synthetic/output'], [*base[:-1], '/synthetic/output/.'],
                     [*base[:-1], '/synthetic//output'], [*base[:-1], '/synthetic/unused/../output']):
            with self.assertRaises(lab.LabError):
                lab._capture_arguments(argv, Path('/synthetic/binary'), Path('/synthetic/assets'), Path('/synthetic/output'), 180, lab.SCENARIO)

    def test_typed_producer_mismatch_stops_before_actor(self):
        request = p.CaptureRequest(Path('/synthetic/binary'), Path('/synthetic/assets'), Path('/synthetic/output'), 180, lab.SCENARIO,
            (str(Path(lab.__file__).resolve()), 'capture', '--capture', '/synthetic/binary', '--assets', '/synthetic/assets', '--output', '/synthetic/output'))
        with mock.patch.object(lab, '_frontend_identity', return_value={'actual': True}), mock.patch.object(q.b, '_supervise_command') as actor:
            with self.assertRaisesRegex(lab.LabError, 'identities differ'):
                p.capture(request, p.ProducerIdentity({'oldProducer': True}))
            actor.assert_not_called()

    @staticmethod
    def inputs(products, scenario, role='reference'):
        binary, assets = products / 'SYNTHETIC-NEVER-EXECUTED', products / 'synthetic.pak'
        if not binary.exists():
            binary.write_bytes(b'not native code')
            binary.chmod(0o700)
            assets.write_bytes(b'fake assets')
        directory = products / 'qualification' / scenario / role
        argv = (str(Path(lab.__file__).resolve()), 'capture', '--capture', str(binary), '--assets', str(assets),
                '--output', str(directory), '--scenario', scenario)
        return p.CaptureRequest(binary, assets, directory, 180, scenario, argv)

    def test_all26_typed_producer_dispatch_with_synthetic_current_actor(self):
        # Native decoding/origin/OS are mocked; protocol files and parsing are real.
        with namespace() as products:
            proof = {'build_identity': {'cache': lab.scenarios.configuration.profiles()['reference']}}
            for scenario in lab.SCENARIOS:
                request = self.inputs(products, scenario)
                def actor(command, directory, env, output, **kwargs):
                    launch = q.load(directory / 'launch.json')
                    self.assertEqual(launch['command'], command)
                    self.assertEqual(command[3:], [str(request.executable), '-bootconfig', str(directory / 'sbinit.config')])
                    self.assertEqual(env['TMPDIR'], str(directory / 'home/tmp'))
                    self.assertTrue((directory / 'home/tmp').is_dir())
                    self.assertEqual(q.load(directory / 'scenario.json')['scenario'], scenario)
                    for name in (lab.RESTORATION, 'idmap-restoration.json'):
                        p.r.dump(directory / 'frames' / name, {'syntheticOnly': True})
                    return fake_actor(command, directory, env, output, **kwargs)
                decoded = {'stage': dict(receipt={'scenario': scenario}, dimensions=[1, 1], pngSha256='fake',
                                         receiptSha256='fake', pixelsSha256='fake')}
                with self.subTest(scenario=scenario), mock.patch.object(lab, 'verified_build', return_value=proof), \
                        mock.patch.object(q.b, '_supervise_command', side_effect=actor) as supervised, \
                        mock.patch.object(p, 'process_identity', return_value=('darwin-proc-bsdinfo:1000:123', 4242)), \
                        mock.patch.object(lab, 'captures', return_value=decoded) as decode, \
                        mock.patch.object(lab.scenarios, 'bind_old'), \
                        mock.patch.object(lab, 'validated', return_value=(decoded, {})):
                    frames = p.capture(request, p.ProducerIdentity(lab._frontend_identity()))
                    self.assertEqual(frames, request.directory / 'frames')
                    supervised.assert_called_once()
                    decode.assert_called_once()
                    self.assertEqual(q.load(request.directory / 'process-start.json')['pid'], 4343)
                    self.assertEqual(q.load(request.directory / 'process-start.json')['pgid'], 4242)
                    q.validate_process_binding(frames, q.load(frames / 'manifest.json'))
            self.popen.assert_not_called()

    def test_actor_failures_never_publish_success_end_or_manifest(self):
        for reason in ('nonzero', 'timeout', 'overflow', 'source', 'callback', 'wrong-group', 'noACK'):
            with self.subTest(reason=reason), namespace() as products:
                request = self.inputs(products, lab.SCENARIO)
                proof = {'build_identity': {'cache': lab.scenarios.configuration.profiles()['reference']}}
                def actor(command, directory, env, output, **kwargs):
                    if reason in ('timeout', 'overflow', 'source'):
                        raise ValueError(reason)
                    receipt = fake_actor(command, directory, env, output, **kwargs)
                    receipt['returncode' if reason == 'nonzero' else 'startAcknowledged'] = 2 if reason == 'nonzero' else False
                    return receipt
                birth = mock.Mock(return_value=('darwin-proc-bsdinfo:1000:123', 4343 if reason == 'wrong-group' else 4242),
                                  side_effect=lab.LabError('birth unavailable') if reason == 'callback' else None)
                with mock.patch.object(lab, 'verified_build', return_value=proof), \
                        mock.patch.object(q.b, '_supervise_command', side_effect=actor), \
                        mock.patch.object(p, 'process_identity', birth), \
                        mock.patch.object(lab, 'captures', side_effect=AssertionError('must not decode')):
                    with self.assertRaises((lab.LabError, ValueError)):
                        p.capture(request, p.ProducerIdentity(lab._frontend_identity()))
                self.assertFalse((request.directory / 'process-exit.json').exists())
                self.assertFalse((request.directory / 'frames/manifest.json').exists())
                failure = q.load(request.directory / 'failure.json')
                self.assertEqual(failure['pid'], None if reason in ('timeout', 'overflow', 'source') else 4343)
                self.assertEqual(failure['scope'], q.SCOPE)

    def test_source_ownership_and_failure_protocol_projection(self):
        source = inspect.getsource(p.capture)
        self.assertLess(source.index("protocol.write_json(directory / 'launch.json'"), source.index('protocol.b._supervise_command('))
        self.assertLess(source.index('protocol.validate_process_binding('), source.index('frontend.captures('))
        self.assertIn('stdin=subprocess.DEVNULL', source)
        self.assertIn('on_command_started=started', source)
        for forbidden in ('subprocess.Popen(', 'stop_process_group', 'signal.signal', 'r.dump(', 'r.durable_dump(',
                          'r.validate_process_binding(', 'process.log', 'setattr(', '--version'):
            self.assertNotIn(forbidden, source)
        lab.scenarios.assert_frozen()


if __name__ == '__main__':
    unittest.main()
