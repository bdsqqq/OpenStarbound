"""Synthetic receipt sensitivity only: all origin/OS assertions here are fake data."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from PIL import Image
import behavior_lab_static_vector as lab
import static_vector_capture as producer
from test_static_vector_proof import fixture as proof_fixture, restoration

r = lab.r
REAL_ORIGIN = lab._check_game_origin


class FrontendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='static-vector-synthetic-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.build = self.root / 'build'
        self.build.mkdir()
        for patch in (mock.patch.object(r, 'BUILD', self.build),
                      mock.patch.object(lab, '_frontend_identity', return_value={'syntheticOnly': True}),
                      mock.patch.object(lab, '_check_game_origin', return_value={'schema': 'static-vector-whole-game-origin-v1', 'syntheticOnly': True})):
            patch.start()
            self.addCleanup(patch.stop)

    def write(self, path, value):
        path.write_text(json.dumps(value, sort_keys=True))

    def fixture(self, label='ref', backend='native'):
        parent = r.create_owned(self.build / label)
        frames = r.create_owned(parent / 'frames')
        storage = r.create_owned(frames / 'storage')
        binary, assets = parent / 'SYNTHETIC-NOT-GAME', self.build / 'synthetic.pak'
        binary.write_bytes(b'not an executable')
        if not assets.exists():
            assets.write_bytes(b'not real assets')
        config = dict(scenario=lab.SCENARIO, outputDirectory=str(frames), storageDirectory=str(storage), maxFrames=1800, platformWrites=False)
        boot = producer.boot_configuration(lab.SCENARIO, str(assets), storage)
        r.dump(parent / 'scenario.json', config)
        r.dump(parent / 'sbinit.config', boot)
        proof = dict(schema=1, binary=str(binary), binary_sha256=r.sha(binary), source_files={'synthetic.cpp': 'a' * 64},
                     build_identity={'cache': lab.scenarios.configuration.profiles()['candidate' if backend == 'rust' else 'reference']})
        r.dump(r.build_provenance.sidecar(binary), proof)
        for i, stage in enumerate(lab.proof_reader.STAGES):
            receipt = proof_fixture(i, backend, (i + 1) * 10)
            receipt['staticVectorProof']['configuration'] = config
            receipt.update(worldId='synthetic', playerPosition=[12, 4], stabilization={'synthetic': True},
                lightObject='behaviorlabconstantlight', lightEntityId=10, lightPosition=[116.5, 33.5], lightColor=[1, 1, 1],
                lightType='PointAsSpread', changedTileMin=[126, 33], changedTileMax=[2, 59], occluderPresent=i == 1,
                observedOccluderMaterial=1 if i == 1 else 65535, action=('room-populated', 'foreground-occluder-added', 'foreground-occluder-removed')[i],
                seed=42, replicatedSettledUpdates=90, lightingBackend='rust' if backend == 'rust' else 'cpp',
                rustLightingCalls=10 if backend == 'rust' else 0, worldState={'invisible': ['keep', i == 1]})
            Image.new('RGBA', (24, 16), (0, 55, 0, 255) if i == 1 else (22, 0, 0, 255)).save(frames / (stage + '.png'))
            r.dump(frames / (stage + '.json'), dict(name=stage, file=stage + '.png', width=24, height=16,
                capture=dict(source='final-default-framebuffer', stage='after-imgui-before-swap'), metadata=receipt))
        r.dump(frames / lab.RESTORATION, restoration())
        command = [str(binary), '-bootconfig', str(parent / 'sbinit.config')]
        argv = [str(Path(lab.__file__).resolve()), 'capture', '--capture', str(binary), '--assets', str(assets), '--output', str(parent)]
        launch = dict(binary=r.identity(binary), assets=r.identity(assets), buildProvenance=proof,
            gameOrigin=lab._check_game_origin(binary, proof), overlayFiles=lab.scenarios.overlay_identity(lab.SCENARIO),
            configuration=r.identity(parent / 'scenario.json'), bootconfig=r.identity(parent / 'sbinit.config'),
            command=command, timeoutSeconds=180, frontend=dict(identities=lab._frontend_identity(), argv=argv),
            environment=producer.environment(parent), sourceClock=dict(monotonic=100, wall=1000),
            processProtocol=dict(cwd=str(parent), stdin='DEVNULL', startNewSession=True, clock='monotonic+wall-v1'))
        r.dump(parent / 'launch.json', launch)
        start = dict(schema=1, pid=12345, pgid=12345, osStart='SYNTHETIC-OS-IDENTITY', status='started',
            binary=launch['binary'], configuration=launch['configuration'], command=command,
            launch=r.identity(parent / 'launch.json'), wallStarted=1000.5, monotonicStarted=100.5)
        r.dump(parent / 'process-start.json', start)
        r.dump(parent / 'process-exit.json', dict(schema=1, pid=start['pid'], pgid=start['pgid'], osStart=start['osStart'],
            status='reaped', exitCode=0, startReceipt=r.identity(parent / 'process-start.json'), wallFinished=1002, monotonicFinished=102))
        manifest = dict(schema=1, captureId=label, binary=launch['binary'], assets=launch['assets'], buildProvenance=proof,
            overlayFiles=launch['overlayFiles'], semanticConfiguration=producer.semantic_configuration(config),
            semanticBootconfig=producer.semantic_boot(boot), configuration=launch['configuration'], bootconfig=launch['bootconfig'],
            command=command, exitCode=0, processStart=r.identity(parent / 'process-start.json'), processExit=r.identity(parent / 'process-exit.json'),
            elapsedSeconds=2, frames=r.inventory(lab.captures(frames, config, backend, 0)))
        r.dump(frames / 'manifest.json', manifest)
        r.dump(parent / lab.BINDING, lab._binding(frames, manifest, launch['gameOrigin'], launch))
        return frames

    def test_native_rust_and_restoration_equal_baseline(self):
        for backend in ('native', 'rust'):
            frames, manifest = lab.validated(self.fixture(backend, backend))
            self.assertEqual(len(frames), 3)
            state = frames['lit-room']['receipt']['worldState']
            self.assertIn('declared', state)
            self.assertIn('staticVectorProof', state)
            self.assertEqual(frames['lit-room']['pixelsSha256'], frames['occluder-restored']['pixelsSha256'])

    def test_full_rgba_compare_and_repeat(self):
        ref, repeat, cand = self.fixture('ref'), self.fixture('repeat'), self.fixture('candidate', 'rust')
        baseline = lab.pair_compare(ref, repeat, self.build / 'repeat-report', True)
        comparison = lab.pair_compare(ref, cand, self.build / 'candidate-report')
        self.assertTrue(baseline['passed'], baseline)
        self.assertTrue(comparison['passed'], comparison)
        self.assertFalse(comparison['parityCertified'])
        self.assertTrue(comparison['inspectionRequired'])

    def test_resealed_invisible_state_and_alpha_pixels_still_fail_comparison(self):
        reference = self.fixture('ref')
        for label in ('invisible-state', 'alpha-pixel'):
            candidate = self.fixture(label, 'rust')
            if label == 'invisible-state':
                path = candidate / 'lit-room.json'
                envelope = r.load(path)
                envelope['metadata']['worldState']['invisible'].append('corrupted')
                self.write(path, envelope)
            else:
                path = candidate / 'lit-room.png'
                frame = r.image(path)
                frame.putpixel((0, 0), (22, 0, 0, 254))
                frame.save(path)
            # Rebinding test data is deliberate: a stale hash cannot be the
            # only reason this mutant fails the exact state/full-RGBA oracle.
            manifest_path = candidate / 'manifest.json'
            manifest = r.load(manifest_path)
            config = r.load(candidate.parent / 'scenario.json')
            manifest['frames'] = r.inventory(lab.captures(candidate, config, 'rust', 0))
            self.write(manifest_path, manifest)
            launch = r.load(candidate.parent / 'launch.json')
            self.write(candidate.parent / lab.BINDING, lab._binding(candidate, manifest, launch['gameOrigin'], launch))
            result = lab.pair_compare(reference, candidate, self.build / (label + '-report'))
            self.assertFalse(result['passed'])
            errors = result['frames']['lit-room']['errors']
            self.assertIn('worldState differs' if label == 'invisible-state' else 'exact framebuffer gate failed', errors)

    def test_mutations_fail_closed(self):
        mutations = {
            'producer': ('launch.json', lambda v: v['frontend']['identities'].update(producer='old')),
            'argv': ('launch.json', lambda v: v['frontend']['argv'].__setitem__(0, str(lab.HERE / 'behavior_lab.py'))),
            'process': ('process-exit.json', lambda v: v.update(osStart='stale')),
            'stdin': ('launch.json', lambda v: v['processProtocol'].update(stdin='INHERIT')),
            'origin': ('launch.json', lambda v: v.update(gameOrigin={'schema': 'id-map-whole-game-origin-v1'})),
            'clock': ('process-exit.json', lambda v: v.update(wallFinished=1100)),
            'restoration': ('frames/' + lab.RESTORATION, lambda v: v.update(observerDisarmed=False)),
            'state': ('frames/lit-room.json', lambda v: v['metadata'].update(fullbright=True)),
            'counter': ('frames/lit-room.json', lambda v: v['metadata']['staticVectorProof'].update(callsiteCalls=0)),
            'phase-reuse': ('frames/occluder-restored.json', lambda v: v['metadata']['staticVectorProof'].update(frameSequence=10, scopeId=10)),
            'bad-profile': ('SYNTHETIC-NOT-GAME.build-proof.json', lambda v: v['build_identity']['cache'].update(STAR_USE_RUST_LINE_QUERY='ON')),
        }
        for label, (name, mutate) in mutations.items():
            with self.subTest(label=label):
                frames = self.fixture(label)
                path = frames.parent / name
                if label == 'bad-profile':
                    path = r.build_provenance.sidecar(frames.parent / 'SYNTHETIC-NOT-GAME')
                value = r.load(path)
                mutate(value)
                self.write(path, value)
                with self.assertRaises((lab.LabError, ValueError)):
                    lab.validated(frames)

    def test_decoder_rejects_png_restoration_unknown_and_raw_state(self):
        for label in ('PNG', 'unknown', 'dimensions', 'state', 'restoration'):
            frames = self.fixture(label)
            if label == 'PNG':
                (frames / 'lit-room.png').write_bytes(b'not PNG')
            elif label == 'unknown':
                r.dump(frames / 'unknown.json', {})
            else:
                path = frames / (lab.RESTORATION if label == 'restoration' else 'lit-room.json')
                value = r.load(path)
                if label == 'dimensions':
                    value['width'] = 25
                elif label == 'state':
                    value['metadata'].pop('worldId')
                else:
                    value['complete'] = False
                self.write(path, value)
            config = r.load(frames.parent / 'scenario.json')
            with self.subTest(label=label), self.assertRaises((lab.LabError, ValueError, OSError)):
                lab.captures(frames, config, 'native', 0)

    def test_cli_repeatability_failure_never_compares_candidate(self):
        output = self.build / 'cli-report'
        with mock.patch.object(lab, 'pair_compare', return_value={'passed': False}) as compare:
            result = lab.main(['compare', '--reference', '/fake/ref', '--repeat', '/fake/repeat',
                               '--candidate', '/fake/candidate', '--output', str(output)])
            self.assertEqual(result, 1)
            self.assertEqual(compare.call_count, 1)
        self.assertEqual(lab.main(['compare', '--reference', '/fake/ref', '--candidate', '/fake/candidate',
                                  '--output', str(self.build / 'no-repeat')]), 2)

    def test_origin_opaque_exact_binding_and_old_or_empty_schema_refused(self):
        from types import SimpleNamespace
        for binding in ({}, {'schema': 'id-map-whole-game-origin-v1'}, None):
            with mock.patch.object(lab.scenarios, 'load_source', return_value=SimpleNamespace(validate_game_origin=lambda executable, proof: binding)):
                with self.assertRaises(lab.LabError):
                    REAL_ORIGIN(Path('/fake'), {})
        binding = {'schema': 'static-vector-whole-game-origin-v1', 'canonicalArchive': {'actualUnknownUntilSealed': 'opaque'}}
        with mock.patch.object(lab.scenarios, 'load_source', return_value=SimpleNamespace(validate_game_origin=lambda executable, proof: binding)):
            self.assertIs(REAL_ORIGIN(Path('/fake'), {}), binding)

    def test_origin_absent_rejected_not_synthetic_acceptance(self):
        # Explicitly unpatch origin for this negative path; reader execution is
        # replaced by an import failure, never a production stub acceptance.
        with mock.patch.object(lab.scenarios, 'load_source', side_effect=FileNotFoundError('missing current origin')):
            with self.assertRaisesRegex(lab.LabError, 'rejected/unavailable'):
                REAL_ORIGIN(Path('/fake'), {})


if __name__ == '__main__':
    unittest.main()
