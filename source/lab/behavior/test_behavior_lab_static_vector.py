"""Synthetic receipt sensitivity only; no OS/origin/game qualification."""
import copy
import json
import inspect
from pathlib import Path
import time
import unittest
from unittest import mock
from types import SimpleNamespace

from PIL import Image
import behavior_lab_static_vector as lab
import static_vector_capture as producer
import static_vector_capture_protocol as q
from test_static_vector_capture_protocol import namespace, fixture_process
from test_static_vector_proof import fixture as proof_fixture, restoration

r = lab.r
REAL_ORIGIN = lab._check_game_origin


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True))


def fixture(products, role='reference'):
    backend = 'rust' if role == 'candidate' else 'native'
    parent = q.create_owned(products / 'qualification' / lab.SCENARIO / role)
    frames = q.create_owned(parent / 'frames')
    storage = q.create_owned(frames / 'storage')
    binary, assets = products / ('SYNTHETIC-NOT-GAME-' + backend), products / 'synthetic.pak'
    if not binary.exists():
        binary.write_bytes(b'not an executable ' + backend.encode())
    if not assets.exists():
        assets.write_bytes(b'not real assets')
    config = dict(scenario=lab.SCENARIO, outputDirectory=str(frames), storageDirectory=str(storage), maxFrames=1800, platformWrites=False)
    boot = producer.boot_configuration(lab.SCENARIO, str(assets), storage)
    q.write_json(parent / 'scenario.json', config)
    q.write_json(parent / 'sbinit.config', boot)
    proof = dict(schema=1, binary=str(binary), binary_sha256=r.sha(binary), source_files={'synthetic.cpp': 'a' * 64},
                 build_identity={'cache': lab.scenarios.configuration.profiles()['candidate' if backend == 'rust' else 'reference']})
    if not r.build_provenance.sidecar(binary).exists():
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
    command, sandbox = q.sandbox(binary, parent / 'sbinit.config')
    argv = [str(Path(lab.__file__).resolve()), 'capture', '--capture', str(binary), '--assets', str(assets), '--output', str(parent)]
    launch = dict(binary=r.identity(binary), assets=r.identity(assets), buildProvenance=proof,
        gameOrigin=lab._check_game_origin(binary, proof), overlayFiles=lab.scenarios.overlay_identity(lab.SCENARIO),
        configuration=r.identity(parent / 'scenario.json'), bootconfig=r.identity(parent / 'sbinit.config'),
        command=command, nativeSandbox=sandbox, timeoutSeconds=180,
        frontend=dict(identities=lab._frontend_identity(), argv=argv), environment=producer.environment(parent),
        sourceClock=dict(monotonic=time.monotonic(), wall=time.time()),
        processProtocol=dict(cwd=str(parent), stdin='DEVNULL', startNewSession=True,
                             clock='monotonic+wall-v1', binding=q.VERSION))
    end = fixture_process(parent, launch)
    manifest = dict(schema=1, processBinding=q.VERSION, captureId=role, binary=launch['binary'], assets=launch['assets'],
        buildProvenance=proof, overlayFiles=launch['overlayFiles'], semanticConfiguration=producer.semantic_configuration(config),
        semanticBootconfig=producer.semantic_boot(boot), configuration=launch['configuration'], bootconfig=launch['bootconfig'],
        command=command, exitCode=0, processStart=r.identity(parent / 'process-start.json'), processExit=r.identity(parent / 'process-exit.json'),
        elapsedSeconds=end['monotonicFinished'] - launch['sourceClock']['monotonic'], frames=r.inventory(lab.captures(frames, config, backend, 0)))
    q.write_json(frames / 'manifest.json', manifest)
    q.write_json(parent / lab.BINDING, lab._binding(frames, manifest, launch['gameOrigin'], launch))
    return frames


def output(products, kind='comparison'):
    root = products / 'qualification' / lab.SCENARIO / 'compare'
    if not root.exists():
        q.create_owned(root)
    return root / kind


def reseal(frames):
    """Deliberately reseal synthetic identities so deeper validators see mutants."""
    parent = frames.parent
    start = q.load(parent / 'process-start.json')
    start['commandSource'] = r.identity(parent / 'process.command.json')
    start['launch'] = r.identity(parent / 'launch.json')
    write(parent / 'process-start.json', start)
    actor = q.load(parent / 'process.receipt.json')
    actor['command'] = start['commandSource']
    write(parent / 'process.receipt.json', actor)
    end = q.load(parent / 'process-exit.json')
    end['actorReceipt'] = r.identity(parent / 'process.receipt.json')
    end['startReceipt'] = r.identity(parent / 'process-start.json')
    write(parent / 'process-exit.json', end)
    manifest = q.load(frames / 'manifest.json')
    manifest.update(processStart=r.identity(parent / 'process-start.json'), processExit=r.identity(parent / 'process-exit.json'))
    write(frames / 'manifest.json', manifest)
    launch = q.load(parent / 'launch.json')
    write(parent / lab.BINDING, lab._binding(frames, manifest, launch['gameOrigin'], launch))


class FrontendTests(unittest.TestCase):
    def test_acquired_semantic_and_full_pixel_projection_is_exact(self):
        old = inspect.getsource(r.pair_compare)
        new = inspect.getsource(lab.pair_compare)
        start, stop = '        for name, ref in expected.items():', '        report["passed"] ='
        old = old[old.index(start):old.index(stop)]
        new = new[new.index(start):new.index(stop)]
        first = new.index('            if ref_meta["scenario"] in ("static-vector-room", "id-map-room"):')
        last = new.index('            elif ref_meta["scenario"] == "buffer-room":')
        new = new[:first] + '            if ref_meta["scenario"] == "buffer-room":' + new[last + len('            elif ref_meta["scenario"] == "buffer-room":'):]
        for variable, kind in (('a', 'expected'), ('b', 'candidate'), ('visual', 'diff')):
            new = new.replace('protocol.write_png(output / f"{name}-' + kind + '.png", ' + variable + ')',
                              variable + '.save(output / f"{name}-' + kind + '.png")')
        self.assertEqual(old, new)

    def test_pid_binding_verifier_detects_isolated_noop_validator_mutant(self):
        with namespace() as products:
            frames = fixture(products)
            start = q.load(frames.parent / 'process-start.json')
            start['pid'] = start['pgid']
            write(frames.parent / 'process-start.json', start)
            reseal(frames)
            manifest = q.load(frames / 'manifest.json')
            class Control(unittest.TestCase):
                def runTest(control):
                    with control.assertRaises(lab.LabError):
                        q.validate_process_binding(frames, manifest)
            good = unittest.TestResult()
            Control().run(good)
            self.assertTrue(good.wasSuccessful())
            mutant = unittest.TestResult()
            with mock.patch.object(q, 'validate_process_binding', return_value=None):
                Control().run(mutant)
            self.assertEqual(len(mutant.failures), 1)
            self.assertIn('not raised', mutant.failures[0][1])

    def test_native_rust_and_restoration_equal_baseline(self):
        with namespace() as products:
            for role in ('reference', 'candidate'):
                frames, manifest = lab.validated(fixture(products, role))
                self.assertEqual(len(frames), 3)
                state = frames['lit-room']['receipt']['worldState']
                self.assertIn('declared', state)
                self.assertIn('staticVectorProof', state)
                self.assertEqual(frames['lit-room']['pixelsSha256'], frames['occluder-restored']['pixelsSha256'])

    def test_all26_scoped_comparator_positive_and_wrong_backend_dispatch(self):
        # Decoder/origin are deliberately mocked here: semantic branch controls ONLY.
        routes = {
            'encoding-room': ('encodingProof',), 'sha256-room': ('sha256Proof', 'assets'),
            'vlq-room': ('vlqProof', 'assets'), 'bytes-room': ('bytesProof', 'assets'),
            'unicode-room': ('unicodeProof', 'assets'), 'shell-room': ('shellProof',),
            'jsonpath-room': ('jsonPathProof', 'assets'), 'assetpath-room': ('assetPathProof', 'assets'),
            'random-room': ('randomMwcProof',), 'jsonpatch-room': ('jsonPatchProof', 'assets'),
            'text-room': ('textScanProof',), 'zstd-room': ('zstdProof',),
            'option-parser-room': ('optionParserProof',), 'host-address-room': ('hostAddressProof',),
            'datastream-room': ('dataStreamProof',), 'buffer-room': ('bufferProof',),
            'stringview-room': ('stringViewProof',), 'path-embed-room': ('pathEmbedProof',),
            'lru-room': ('lruProof',), 'ttl-room': ('ttlProof',), 'weighted-pool-room': ('weightedPoolProof',),
            'id-map-room': ('idMapProof',), lab.SCENARIO: ('staticVectorProof',)}
        native = {'path-embed-room', 'lru-room', 'ttl-room', 'weighted-pool-room', 'id-map-room', lab.SCENARIO}
        def metadata(scene, candidate):
            wanted = 'rust' if candidate else 'native' if scene in native else 'cpp'
            row = dict(scenario=scene, inWorld=True, stage='synthetic', worldState={'invisible': True},
                       lightingBackend='rust' if candidate and scene == 'lighting-room' else 'cpp')
            if scene in routes:
                node = row
                for key in routes[scene]:
                    node[key] = {}
                    node = node[key]
                node['backend'] = wanted
            elif scene == 'raycast-room':
                row['raycastState'] = {side: {'backend': wanted} for side in ('client', 'server')}
            elif scene == 'compression-room':
                row['compressionProof'] = {'operations': {key: {'backend': wanted} for key in ('embed', 'zlib', 'gzip')}}
            if scene == 'buffer-room':
                row['bufferProof'].update(ioDevice={'backend': wanted}, byteArray={'backend': wanted})
                row['fileProof'] = {'backend': wanted}
            return row
        for scene in lab.SCENARIOS:
            for candidate_backend in (True, False):
                with self.subTest(scene=scene, correct=candidate_backend), namespace() as products:
                    base = products / 'qualification' / scene
                    paths = []
                    for role in ('reference', 'candidate'):
                        parent = q.create_owned(base / role)
                        frames = q.create_owned(parent / 'frames')
                        Image.new('RGBA', (1, 1), (10, 20, 30, 255)).save(frames / 'lit-room.png')
                        paths.append(frames)
                    def decoded(path):
                        candidate = path == paths[1]
                        meta = metadata(scene, candidate and candidate_backend)
                        return ({'lit-room': dict(receipt=meta, png=path / 'lit-room.png', dimensions=[1, 1])},
                                dict(captureId='candidate' if candidate else 'reference', assets={'sha256': 'fake'},
                                     binary={'sha256': 'fake'}, overlayFiles={}, semanticBootconfig={},
                                     semanticConfiguration={'scenario': scene}))
                    q.create_owned(base / 'compare')
                    with mock.patch.object(lab, 'validated', side_effect=decoded):
                        report = lab.pair_compare(paths[0], paths[1], base / 'compare/comparison')
                    self.assertEqual(report['passed'], candidate_backend, report)

    def test_full_rgba_compare_and_repeat(self):
        with namespace() as products:
            ref, repeat, cand = (fixture(products, role) for role in ('reference', 'repeat', 'candidate'))
            baseline = lab.pair_compare(ref, repeat, output(products, 'repeatability'), True)
            comparison = lab.pair_compare(ref, cand, output(products))
            self.assertTrue(baseline['passed'], baseline)
            self.assertTrue(comparison['passed'], comparison)
            self.assertFalse(comparison['parityCertified'])
            self.assertTrue(comparison['inspectionRequired'])

    def test_resealed_invisible_state_and_alpha_pixels_still_fail_comparison(self):
        for mutant in ('invisible-state', 'alpha-pixel'):
            with self.subTest(mutant=mutant), namespace() as products:
                reference, candidate = fixture(products), fixture(products, 'candidate')
                if mutant == 'invisible-state':
                    path = candidate / 'lit-room.json'
                    envelope = r.load(path)
                    envelope['metadata']['worldState']['invisible'].append('corrupted')
                    write(path, envelope)
                else:
                    path = candidate / 'lit-room.png'
                    frame = r.image(path)
                    frame.putpixel((0, 0), (22, 0, 0, 254))
                    frame.save(path)
                manifest = r.load(candidate / 'manifest.json')
                config = r.load(candidate.parent / 'scenario.json')
                manifest['frames'] = r.inventory(lab.captures(candidate, config, 'rust', 0))
                write(candidate / 'manifest.json', manifest)
                launch = r.load(candidate.parent / 'launch.json')
                write(candidate.parent / lab.BINDING, lab._binding(candidate, manifest, launch['gameOrigin'], launch))
                result = lab.pair_compare(reference, candidate, output(products))
                self.assertFalse(result['passed'])
                self.assertIn('worldState differs' if mutant == 'invisible-state' else 'exact framebuffer gate failed',
                              result['frames']['lit-room']['errors'])

    def test_resealed_process_protocol_mutations_fail_before_png(self):
        mutations = [
            ('process-start.json', lambda v: v.update(pid=4242)),
            ('process-start.json', lambda v: v.update(schema=1)),
            ('process-start.json', lambda v: v.update(pid=4343.0)),
            ('process-start.json', lambda v: v.update(pgid=True)),
            ('process-start.json', lambda v: v.update(extra=True)),
            ('process-start.json', lambda v: v.update(osStart='')),
            ('process-exit.json', lambda v: v.update(exitCode=True)),
            ('process-exit.json', lambda v: v.update(wallFinished=time.time() + 1000)),
            ('launch.json', lambda v: v['environment'].update(TMPDIR='/outside')),
            ('launch.json', lambda v: v['processProtocol'].update(stdin='INHERIT')),
            ('launch.json', lambda v: v['frontend']['identities'].update(producer='old')),
            ('launch.json', lambda v: v.update(command=v['command'][3:])),
            ('launch.json', lambda v: v.update(sourceClock=dict(monotonic=True, wall=1))),
            ('process.command.json', lambda v: v.update(stdin='INHERIT')),
            ('process.command.json', lambda v: v['launcher']['python'].update(size=float(v['launcher']['python']['size']))),
            ('process.receipt.json', lambda v: v['launcher']['guardian'].update(size=float(v['launcher']['guardian']['size']))),
            ('process.command.json', lambda v: v['launchArgv'].__setitem__(13, v['launchArgv'][4])),
            ('process.receipt.json', lambda v: v.update(startAcknowledged=False)),
            ('process.receipt.json', lambda v: v.update(callbackCompleted=False)),
            ('process.receipt.json', lambda v: v.update(commandReaped=False)),
            ('process.receipt.json', lambda v: v.update(guardianReaped=1)),
            ('process.receipt.json', lambda v: v.update(guardianReturncode=0)),
            ('process.receipt.json', lambda v: v.update(returncode=1)),
            ('process.receipt.json', lambda v: v.update(returncode=0.0)),
            ('process.receipt.json', lambda v: v.update(outputComplete=False)),
            ('process.receipt.json', lambda v: v.update(guardianStatusEOF=False)),
            ('process.receipt.json', lambda v: v['streams']['stdout'].update(overflow={})),
            ('process.receipt.json', lambda v: v.update(commandPID=4242)),
            ('process.receipt.json', lambda v: v.update(guardianStatusBytes=True)),
            ('process.receipt.json', lambda v: v.update(guardianProtocolHex=(bytes.fromhex(v['guardianProtocolHex']).replace(b'"commandPID": 4343', b'"commandPID": 4343,"commandPID": 4343', 1)).hex())),
            ('process.receipt.json', lambda v: v.update(guardianProtocolHex=(bytes.fromhex(v['guardianProtocolHex']).replace(b'"commandPID": 4343', b'"commandPID": true', 1)).hex())),
            ('process.receipt.json', lambda v: v.update(guardianProtocolHex=(bytes.fromhex(v['guardianProtocolHex']).replace(b'"sourceSha256": "', b'"sourceSha256": "0', 1)).hex())),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name, mutate=mutate), namespace() as products:
                frames = fixture(products)
                path = frames.parent / name
                value = r.load(path)
                mutate(value)
                write(path, value)
                reseal(frames)
                with mock.patch.object(lab, 'captures', side_effect=AssertionError('PNG admission reached')):
                    with self.assertRaises((lab.LabError, ValueError, KeyError, TypeError)):
                        lab.validated(frames)

    def test_identity_numeric_alias_control_rejects_plain_equality_mutant(self):
        with namespace() as products:
            frames = fixture(products)
            path = frames.parent / 'process.command.json'
            command = q.load(path)
            command['launcher']['python']['size'] = float(command['launcher']['python']['size'])
            write(path, command)
            reseal(frames)
            manifest = q.load(frames / 'manifest.json')
            with self.assertRaisesRegex(lab.LabError, 'launcher identity'):
                q.validate_process_binding(frames, manifest)
            # Isolated old-style equality accepts the same float alias. This is
            # DATA-only: no process, PNG admission or current game is qualified.
            with mock.patch.object(q.ad.policy, 'same', side_effect=lambda left, right: left == right):
                q.validate_process_binding(frames, manifest)

    def test_decoder_rejects_png_restoration_unknown_dimensions_state(self):
        for mutant in ('PNG', 'unknown', 'dimensions', 'state', 'restoration'):
            with self.subTest(mutant=mutant), namespace() as products:
                frames = fixture(products)
                if mutant == 'PNG':
                    (frames / 'lit-room.png').write_bytes(b'not PNG')
                elif mutant == 'unknown':
                    r.dump(frames / 'unknown.json', {})
                else:
                    path = frames / (lab.RESTORATION if mutant == 'restoration' else 'lit-room.json')
                    value = r.load(path)
                    if mutant == 'dimensions':
                        value['width'] = 25
                    elif mutant == 'state':
                        value['metadata'].pop('worldId')
                    else:
                        value['complete'] = False
                    write(path, value)
                with self.assertRaises((lab.LabError, ValueError, OSError)):
                    lab.captures(frames, r.load(frames.parent / 'scenario.json'), 'native', 0)

    def test_missing_start_old_binding_failed_capture_and_duplicate_records_rejected(self):
        for mutant in ('missing', 'old', 'failure', 'duplicate'):
            with self.subTest(mutant=mutant), namespace() as products:
                frames = fixture(products)
                if mutant == 'missing':
                    (frames.parent / 'process-start.json').unlink()
                elif mutant == 'old':
                    value = r.load(frames / 'manifest.json')
                    value.pop('processBinding')
                    write(frames / 'manifest.json', value)
                elif mutant == 'failure':
                    q.write_json(frames.parent / 'failure.json', {'reason': 'failed'})
                else:
                    path = frames.parent / 'process-start.json'
                    path.write_bytes(path.read_bytes()[:-1] + b',"pid":4343}')
                with self.assertRaises((lab.LabError, ValueError, OSError)):
                    lab.validated(frames)

    def test_compare_finite_namespace_and_scenario_mismatch_fail(self):
        with namespace() as products:
            reference, candidate = fixture(products), fixture(products, 'candidate')
            with self.assertRaises(lab.LabError):
                lab.pair_compare(reference, candidate, products / 'arbitrary')
            other = q.create_owned(products / 'qualification' / 'id-map-room' / 'compare')
            report = lab.pair_compare(reference, candidate, other / 'comparison')
            self.assertFalse(report['passed'])
            self.assertIn('scenario mismatch', report['errors'][0])

    def test_cli_repeatability_failure_never_compares_candidate(self):
        with namespace() as products:
            root = products / 'qualification' / lab.SCENARIO / 'compare'
            with mock.patch.object(lab, 'pair_compare', return_value={'passed': False}) as compare:
                result = lab.main(['compare', '--reference', '/fake/ref', '--repeat', '/fake/repeat',
                                   '--candidate', '/fake/candidate', '--output', str(root)])
                self.assertEqual(result, 1)
                self.assertEqual(compare.call_count, 1)
            self.assertEqual(lab.main(['compare', '--reference', '/fake/ref', '--candidate', '/fake/candidate',
                                      '--output', str(root)]), 2)

    def test_origin_opaque_exact_binding_and_old_or_empty_schema_refused(self):
        for binding in ({}, {'schema': 'id-map-whole-game-origin-v1'}, None):
            with mock.patch.object(lab.scenarios, 'load_source', return_value=SimpleNamespace(validate_game_origin=lambda executable, proof: binding)):
                with self.assertRaises(lab.LabError):
                    REAL_ORIGIN(Path('/fake'), {})
        binding = {'schema': 'static-vector-whole-game-origin-v1', 'canonicalArchive': {'actualUnknownUntilSealed': 'opaque'}}
        with mock.patch.object(lab.scenarios, 'load_source', return_value=SimpleNamespace(validate_game_origin=lambda executable, proof: binding)):
            self.assertIs(REAL_ORIGIN(Path('/fake'), {}), binding)

    def test_origin_absent_rejected_not_synthetic_acceptance(self):
        with mock.patch.object(lab.scenarios, 'load_source', side_effect=FileNotFoundError('missing current origin')):
            with self.assertRaisesRegex(lab.LabError, 'rejected/unavailable'):
                REAL_ORIGIN(Path('/fake'), {})


if __name__ == '__main__':
    unittest.main()
