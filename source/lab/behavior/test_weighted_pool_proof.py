"""Isolated logical/source contracts only. None of these fixtures ran the game."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest import mock
from PIL import Image, ImageDraw
import weighted_pool_proof as proof
import build_provenance as provenance

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / 'source/lab/behavior/weighted-pool-assets'


def fixture(phase=0, backend='native'):
    # Synthetic descriptor with deliberately extra fields: never a runtime golden.
    d = dict(name='behaviorweightedtoken', count=1, parameters=dict(tag='kept', syntheticExtra={'retain': [17]}))
    repeat = [deepcopy(d), deepcopy(d)]
    results = [dict(pool=proof.POOLS[0], descriptors=deepcopy(repeat)) for _ in range(1 if phase == 1 else 2)]
    results += [dict(pool=proof.POOLS[1], descriptors=[deepcopy(d)]), dict(pool=proof.POOLS[2], descriptors=[])]
    selected = results[-2]['descriptors'] if phase == 1 else repeat
    color = [len(selected)*70, 80, (phase+1)*70, 255]
    before = [[f'{0:016x}'] * 4 for _ in range(19)]
    after = deepcopy(before)
    if backend == 'rust':
        # Deliberately start above zero: warm startup is not phase coverage.
        before = [[f'{100:016x}'] * 4 for _ in range(19)]
        after = deepcopy(before)
        for mode, count in ((9, 3 if phase == 1 else 4), (12, 6 if phase == 1 else 9),
                            (17, 6 if phase == 1 else 9), (18, 6 if phase == 1 else 9)):
            after[mode][0] = f'{100 + count:016x}'
    p = dict(version=1, backend=backend, selector=proof.SELECTOR, scopeThread='lua-calling-thread',
             phase=phase, countersBefore=before, countersAfter=after,
             consumer=proof.CONSUMER, imageConsumer='normal-Assets-WorldPainter',
             labelConsumer='normal-Font-TextPainter', configuration=dict(scenario='weighted-pool-room'),
             visual=dict(phase=phase, results=results, selected=deepcopy(selected), selectedCount=len(selected),
                         uniqueCount=1, color=color, label=f'Weighted {phase+1}/3 count={len(selected)} tag=kept',
                         imagePath='/behaviorlab/weighted-white.png?multiply=' + bytes(color).hex()))
    return dict(weightedPoolProof=p, stageIndex=phase, stage=proof.STAGES[phase], action=proof.ACTIONS[phase],
                occluderPresent=phase == 1, materialId=7, observedOccluderMaterial=7 if phase == 1 else 0,
                cameraPosition=[64, 48], cameraPixelRatio=2)


def image(receipt):
    frame = Image.new('RGBA', (640, 480), (0, 0, 0, 255))
    draw = ImageDraw.Draw(frame)
    draw.rectangle((288, 208, 351, 271), fill=tuple(receipt['weightedPoolProof']['visual']['color']))
    draw.rectangle((220, 140, 227, 140), fill='white')
    return frame


def prepared_barriers(source):
    required = (
        'return weightedPoolConsumer().stage == int(stage);',
        'lruRequire(weightedPoolFramePrepared(stage), "BehaviorLab: WeightedPool overlay not prepared");',
        '&& BehaviorLab::weightedPoolFramePrepared(m_behaviorStage))\n        BehaviorLab::renderWeightedPoolLabel',
        'if (BehaviorLab::weightedPoolScene() && !BehaviorLab::weightedPoolFramePrepared(m_behaviorStage))\n    return;',
    )
    if not all(s in source for s in required):
        raise ValueError('WeightedPool prepared barrier missing')


class ProofTests(unittest.TestCase):
    def test_both_backends_all_phases(self):
        for backend in ('native', 'rust'):
            receipts = [fixture(i, backend) for i in range(3)]
            self.assertTrue(proof.validate_snapshots(receipts))
            for r in receipts:
                proof.visible(image(r), r)
                self.assertIn('syntheticExtra', proof.observation(r)['visual']['selected'][0]['parameters'])
        self.assertEqual(proof.observation(fixture()), proof.observation(fixture(backend='rust')))

    def test_descriptor_corruptions(self):
        for field, value in (('name', 'perfectlygenericitem'), ('name', 'wrong'), ('count', 2), ('count', True),
                             ('parameters', {'tag': 'zero'}), ('parameters', {'tag': 'negative'})):
            with self.subTest(field=field, value=value):
                r = fixture()
                r['weightedPoolProof']['visual']['results'][0]['descriptors'][0][field] = value
                with self.assertRaises(ValueError): proof.validate(r)
        r = fixture()
        r['weightedPoolProof']['visual']['results'][-1]['descriptors'] = [{}]
        with self.assertRaises(ValueError): proof.validate(r)
        r = fixture()
        r['weightedPoolProof']['visual']['results'][1]['descriptors'][0]['parameters']['extra'] = 'changed'
        with self.assertRaises(ValueError): proof.validate(r)

    def test_raw_unknown_fields_remain_comparable(self):
        a, b = fixture(), fixture()
        for result in b['weightedPoolProof']['visual']['results']:
            for d in result['descriptors']: d['parameters']['unmasked'] = 42
        for d in b['weightedPoolProof']['visual']['selected']: d['parameters']['unmasked'] = 42
        proof.validate(b)
        self.assertNotEqual(proof.observation(a), proof.observation(b))

    def test_counter_minima_each_mode_and_phase(self):
        for phase in range(3):
            for mode in (9, 12, 17, 18):
                r = fixture(phase, 'rust')
                p = r['weightedPoolProof']
                p['countersAfter'][mode][0] = f'{int(p["countersAfter"][mode][0], 16)-1:016x}'
                with self.subTest(phase=phase, mode=mode), self.assertRaises(ValueError): proof.validate(r)
        r = fixture()
        r['weightedPoolProof']['countersBefore'][0][0] = '0000000000000001'
        with self.assertRaises(ValueError): proof.validate(r)
        r = fixture(backend='rust')
        r['weightedPoolProof']['countersAfter'][0][0] = 'ABCDEF0000000000'
        with self.assertRaises(ValueError): proof.validate(r)

    def test_scope_stage_config_color_and_backend_corruptions(self):
        for field, value in (('phase', 1), ('backend', 'cpp'), ('selector', 'wrong'),
                             ('scopeThread', 'worker'), ('configuration', {'scenario': 'ttl-room'})):
            r = fixture()
            r['weightedPoolProof'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): proof.validate(r)
        for field, value in (('color', [0, 0, 0, 255]), ('selectedCount', 99), ('uniqueCount', 2),
                             ('label', 'fabricated'), ('imagePath', '/fake.png')):
            r = fixture()
            r['weightedPoolProof']['visual'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): proof.validate(r)
        rs = [fixture(0), fixture(2), fixture(1)]
        with self.assertRaises(ValueError): proof.validate_snapshots(rs)
        rs = [fixture(i) for i in range(3)]
        rs[1]['weightedPoolProof']['configuration']['changed'] = True
        with self.assertRaises(ValueError): proof.validate_snapshots(rs)

    def test_pixels_and_font_corruptions(self):
        r = fixture()
        frame = image(r)
        frame.putpixel((320, 240), (1, 2, 3, 255))
        with self.assertRaisesRegex(ValueError, 'WorldPainter pixels'): proof.visible(frame, r)
        frame = image(r)
        ImageDraw.Draw(frame).rectangle((220, 140, 227, 140), fill='black')
        with self.assertRaisesRegex(ValueError, 'Font label absent'): proof.visible(frame, r)

    def test_sequence_and_world_restoration(self):
        frames = {name: dict(receipt=fixture(i), pixelsSha256=str(i)) for i, name in enumerate(proof.STAGES)}
        proof.validate_sequence(frames, ('cameraPosition', 'cameraPixelRatio'))
        frames[proof.STAGES[2]]['receipt']['cameraPosition'] = [65, 48]
        with self.assertRaisesRegex(ValueError, 'restoration'): proof.validate_sequence(frames, ('cameraPosition',))

    def test_literal_assets(self):
        pools = json.loads((ASSETS / 'weighted.treasurepools').read_text())
        self.assertEqual(set(pools), set(proof.POOLS))
        for index, name in enumerate(proof.POOLS):
            envelope = pools[name]
            self.assertEqual(len(envelope), 1)
            self.assertEqual(envelope[0][0], 0)
            config = envelope[0][1]
            self.assertEqual(config['poolRounds'], 2)
            self.assertIs(config['allowDuplication'], index != 1)
            self.assertEqual([e['weight'] for e in config['pool']], [0, -1] if index == 2 else [0, -1, 1])
            self.assertEqual([e['item'][2]['tag'] for e in config['pool']], ['zero', 'negative'] if index == 2 else ['zero', 'negative', 'kept'])
        item = json.loads((ASSETS / 'items/behaviorweightedtoken.item').read_text())
        self.assertEqual(item['itemName'], 'behaviorweightedtoken')
        self.assertNotIn('builder', item)
        self.assertNotIn('scripts', item)
        with Image.open(ASSETS / 'behaviorlab/weighted-white.png') as png:
            self.assertEqual(png.size, (16, 16))
            self.assertEqual(png.convert('RGBA').tobytes(), bytes([255]*4)*256)
        lua = (ASSETS / 'behaviorlab/weighted-consumer.lua').read_text()
        self.assertIn('root.createTreasure(pools[index], 1, 17)', lua)

    def test_prepared_barrier_source_and_isolated_removals(self):
        source = (ROOT / 'source/client/StarClientApplication.cpp').read_text()
        prepared_barriers(source)
        for token in ('return weightedPoolConsumer().stage == int(stage);',
                      'lruRequire(weightedPoolFramePrepared(stage),',
                      '&& BehaviorLab::weightedPoolFramePrepared(m_behaviorStage))',
                      '!BehaviorLab::weightedPoolFramePrepared(m_behaviorStage)'):
            with self.subTest(token=token), self.assertRaises(ValueError):
                prepared_barriers(source.replace(token, 'REMOVED', 1))

    def test_registration_is_scoped(self):
        import behavior_lab as lab
        self.assertEqual(lab.SCENARIOS[23], 'weighted-pool-room')
        overlay = ASSETS
        self.assertEqual(lab.asset_overlays('weighted-pool-room')['weighted-pool-fixture'], overlay)
        for scenario in lab.SCENARIOS[:23]: self.assertNotIn(overlay, lab.asset_overlays(scenario).values())

    def test_complete_selector_and_source_binary_origins(self):
        self.assertEqual(len(provenance.WEIGHTED_POOL_SELECTORS), 28)
        p = dict(schema=1, binary='/synthetic/client', binary_sha256='a'*64,
                 source_files={key: 'b'*64 for key in provenance.WEIGHTED_POOL_SOURCES},
                 build_identity=dict(cache={key: 'OFF' for key in provenance.WEIGHTED_POOL_SELECTORS}))
        provenance.validate_weighted_pool_origin(p, 'native')
        for key in provenance.WEIGHTED_POOL_SELECTORS:
            bad = deepcopy(p)
            del bad['build_identity']['cache'][key]
            with self.assertRaises(provenance.ProvenanceError): provenance.validate_weighted_pool_origin(bad, 'native')
        for key in provenance.WEIGHTED_POOL_SOURCES:
            bad = deepcopy(p)
            del bad['source_files'][key]
            with self.assertRaises(provenance.ProvenanceError): provenance.validate_weighted_pool_origin(bad, 'native')
        with self.assertRaises(provenance.ProvenanceError): provenance.validate_weighted_pool_origin(p, 'rust')
        candidate = deepcopy(p)
        candidate['build_identity']['cache'] = {key: ('OFF' if key == 'STAR_USE_RUST_LINE_QUERY' else 'ON')
                                              for key in provenance.WEIGHTED_POOL_SELECTORS}
        provenance.validate_weighted_pool_origin(candidate, 'rust')
        for key in provenance.WEIGHTED_POOL_SELECTORS:
            for baseline, backend in ((p, 'native'), (candidate, 'rust')):
                bad = deepcopy(baseline)
                cache = bad['build_identity']['cache']
                cache[key] = 'OFF' if cache[key] == 'ON' else 'ON'
                with self.subTest(backend=backend, key=key), self.assertRaises(provenance.ProvenanceError):
                    provenance.validate_weighted_pool_origin(bad, backend)
        for key in ('binary', 'binary_sha256'):
            bad = deepcopy(p)
            del bad[key]
            with self.assertRaises(provenance.ProvenanceError): provenance.validate_weighted_pool_origin(bad, 'native')


class IntegrationTests(unittest.TestCase):
    """Actual Python consumer plumbing, entirely synthetic frames/receipts."""
    def frames(self, backend, mutate=None):
        import behavior_lab as lab
        directory = mock.Mock()
        pngs = [Path('/synthetic') / (name + '.png') for name in proof.STAGES]
        paths = [p.with_suffix('.json') for p in pngs]
        directory.glob.side_effect = lambda pattern: pngs if pattern == '*.png' else paths
        envelopes, images = {}, {}
        for phase, path in enumerate(paths):
            r = {key: 'synthetic-stable-state' for key in lab.SCENE_FIELDS}
            r.update(fixture(phase, backend))
            r.update(scenario='weighted-pool-room', inWorld=True, playerOutsideView=True,
                     uiHidden=True, lightingCompleted=True, lightEntityReplicated=True,
                     fullbright=False, replicatedSettledUpdates=90, lightingBackend='cpp', rustLightingCalls=0)
            images[pngs[phase]] = image(r)
            if mutate: mutate(r, phase)
            envelopes[path] = dict(name=proof.STAGES[phase], file=pngs[phase].name, width=640, height=480,
                                   metadata=r, capture=dict(source='final-default-framebuffer', stage='after-imgui-before-swap'))
        with mock.patch.object(lab, 'check_owned', side_effect=lambda p: p), \
             mock.patch.object(lab, 'load', side_effect=envelopes.__getitem__), \
             mock.patch.object(lab, 'image', side_effect=images.__getitem__), \
             mock.patch.object(lab, 'sha', return_value='0'*64):
            return lab.captures(directory)

    def compare(self, reference, candidate, same=False):
        import behavior_lab as lab
        def manifest(identity):
            return dict(captureId=identity, assets=dict(sha256='0'*64), binary=dict(sha256='0'*64),
                        overlayFiles={}, semanticBootconfig={}, semanticConfiguration={})
        with mock.patch.object(lab, 'create_owned', side_effect=lambda p: p), \
             mock.patch.object(lab, 'check_owned', side_effect=lambda p: p), \
             mock.patch.object(lab, 'validated', side_effect=[(reference, manifest('ref')), (candidate, manifest('cand'))]), \
             mock.patch.object(lab, 'dump'), \
             mock.patch.object(lab, 'image', return_value=Image.new('RGBA', (640, 480))), \
             mock.patch.object(Image.Image, 'save'):
            return lab.pair_compare(Path('/synthetic/ref'), Path('/synthetic/cand'), Path('/synthetic/report'), same_backend=same)

    def test_normalization_repeat_and_candidate(self):
        native, rust = self.frames('native'), self.frames('rust')
        self.assertTrue(self.compare(native, native, True)['passed'])
        self.assertTrue(self.compare(native, rust)['passed'])
        for ref, cand, same in ((native, native, False), (rust, rust, False), (native, rust, True)):
            with self.subTest(same=same):
                result = self.compare(ref, cand, same)
                self.assertFalse(result['passed'])
                self.assertIn('WeightedPool backend', str(result))

    def test_captures_reject_missing_proof_and_occluder(self):
        import behavior_lab as lab
        with self.assertRaises(lab.LabError):
            self.frames('rust', lambda r, phase: r.pop('weightedPoolProof'))
        with self.assertRaises(lab.LabError):
            self.frames('rust', lambda r, phase: r.update(occluderPresent=False))


if __name__ == '__main__':
    unittest.main()
