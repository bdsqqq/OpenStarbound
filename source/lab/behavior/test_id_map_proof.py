"""Read-only synthetic verifier tests, NOT captures or application evidence."""
from copy import deepcopy
from pathlib import Path
import unittest
from PIL import Image, ImageDraw
import id_map_proof as proof


def fixture(phase=0, backend='native'):
    before = [['0000000000000000'] * 2 for _ in range(10)]
    if backend == 'rust':
        before = [[f'{100:016x}'] * 2 for _ in range(10)]
    after = deepcopy(before)
    if backend == 'rust':
        for mode in (2, 4):
            for stage in (0, 1):
                after[mode][stage] = f'{100 + proof.MINIMA[phase]:016x}'
    value = proof.VALUES[phase]
    color = [value * 4, 40, (phase+1) * 60, 255]
    p = dict(version=1, backend=backend, selector=proof.SELECTOR, scopeThread='lua-calling-thread',
             phase=phase, countersBefore=before, countersAfter=after,
             consumer=proof.CONSUMER, imageConsumer='normal-Assets-WorldPainter',
             labelConsumer='normal-Font-TextPainter', configuration=dict(scenario='id-map-room'),
             visual=dict(phase=phase, observations=list(proof.READS[phase]), value=value, color=color,
                         label=f'IdMap {phase+1}/3 stat={value}',
                         imagePath='/behaviorlab/id-map-white.png?multiply=' + bytes(color).hex()))
    return dict(idMapProof=p, stageIndex=phase, stage=proof.STAGES[phase], action=proof.ACTIONS[phase],
                occluderPresent=phase == 1, materialId=7, observedOccluderMaterial=7 if phase == 1 else 0,
                cameraPosition=[64, 48], cameraPixelRatio=2)


def image(receipt):
    frame = Image.new('RGBA', (640, 480), (0, 0, 0, 255))
    draw = ImageDraw.Draw(frame)
    draw.rectangle((288, 208, 351, 271), fill=tuple(receipt['idMapProof']['visual']['color']))
    draw.rectangle((220, 140, 227, 140), fill='white')
    return frame


def frames():
    return {stage: dict(receipt=fixture(i), pixelsSha256=str(i)) for i, stage in enumerate(proof.STAGES)}


class ProofTests(unittest.TestCase):
    def test_backends_phases_and_float_readbacks(self):
        for backend in ('native', 'rust'):
            self.assertTrue(proof.validate_snapshots([fixture(i, backend) for i in range(3)]))
            for phase in range(3):
                r = fixture(phase, backend)
                proof.visible(image(r), r)
                v = r['idMapProof']['visual']
                v['observations'] = [float(n) for n in v['observations']]
                v['value'] = float(v['value'])
                proof.validate(r)
        self.assertEqual(proof.observation(fixture()), proof.observation(fixture(backend='rust')))

    def test_literal_stat_schedule(self):
        self.assertEqual(proof.READS, ((8, 12, 16, 18), (2,), (34,)))
        for phase in range(3):
            for value in (True, False, None, '18', float('nan'), float('inf'), -1, 18.000001):
                for field in ('observations', 'value'):
                    r = fixture(phase)
                    v = r['idMapProof']['visual']
                    if field == 'observations':
                        v[field][0] = value
                    else:
                        v[field] = value
                    with self.subTest(phase=phase, value=value, field=field), self.assertRaises(ValueError):
                        proof.validate(r)
        r = fixture()
        r['idMapProof']['visual']['observations'].pop()
        with self.assertRaises(ValueError): proof.validate(r)

    def test_missing_root_or_continue_each_mode(self):
        for phase in (0, 2):
            for mode in (2, 4):
                for stage in (0, 1):
                    r = fixture(phase, 'rust')
                    p = r['idMapProof']
                    p['countersAfter'][mode][stage] = p['countersBefore'][mode][stage]
                    with self.subTest(phase=phase, mode=mode, stage=stage), self.assertRaises(ValueError):
                        proof.validate(r)
        # Category removal is native BaseMap::remove; no new IdMap root is required.
        proof.validate(fixture(1, 'rust'))

    def test_counter_schema_and_native_zero(self):
        for invalid in ('0', '000000000000000A', 'g000000000000000', 0, True):
            r = fixture()
            r['idMapProof']['countersAfter'][0][0] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError): proof.validate(r)
        for field in ('countersBefore', 'countersAfter'):
            for invalid in ([], [['0000000000000000'] * 4 for _ in range(10)]):
                r = fixture()
                r['idMapProof'][field] = invalid
                with self.assertRaises(ValueError): proof.validate(r)
            r = fixture()
            r['idMapProof'][field][0][0] = '0000000000000001'
            with self.assertRaises(ValueError): proof.validate(r)

    def test_proof_and_visual_members_are_strict(self):
        for target in ('proof', 'visual'):
            for key in ('cleanup', 'extra'):
                r = fixture()
                p = r['idMapProof']
                (p if target == 'proof' else p['visual'])[key] = 0
                with self.assertRaises(ValueError): proof.validate(r)
        for key in fixture()['idMapProof']:
            r = fixture()
            del r['idMapProof'][key]
            with self.subTest(key=key), self.assertRaises(ValueError): proof.validate(r)
        for key in fixture()['idMapProof']['visual']:
            r = fixture()
            del r['idMapProof']['visual'][key]
            with self.subTest(key=key), self.assertRaises(ValueError): proof.validate(r)
        for r in (None, [], {}, dict(idMapProof=None)):
            with self.assertRaises(ValueError): proof.validate(r)

    def test_metadata_and_visual_corruption(self):
        for key, value in (('phase', True), ('backend', []), ('version', True), ('consumer', 'mock'),
                           ('selector', 'wrong'), ('scopeThread', 'worker'),
                           ('imageConsumer', 'fake'), ('labelConsumer', 'fake'),
                           ('configuration', {'scenario': 'weighted-pool-room'})):
            r = fixture()
            r['idMapProof'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): proof.validate(r)
        for key, value in (('phase', 1), ('color', [72.0, 40, 60, 255]), ('label', 'wrong'), ('imagePath', '/fake')):
            r = fixture()
            r['idMapProof']['visual'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): proof.validate(r)

    def test_sequence_restoration_and_order(self):
        proof.validate_sequence(frames(), ('cameraPosition', 'cameraPixelRatio'))
        for mutate in (
            lambda f: f.pop(proof.STAGES[1]),
            lambda f: f[proof.STAGES[2]]['receipt'].update(cameraPosition=[65, 48]),
            lambda f: f[proof.STAGES[1]]['receipt'].update(action='wrong'),
            lambda f: f[proof.STAGES[1]]['receipt'].update(observedOccluderMaterial=0),
            lambda f: f[proof.STAGES[2]].update(pixelsSha256='0'),
            lambda f: f[proof.STAGES[1]]['receipt']['idMapProof'].update(backend='rust'),
            lambda f: f[proof.STAGES[1]]['receipt']['idMapProof']['configuration'].update(extra=True),
        ):
            f = frames()
            mutate(f)
            with self.assertRaises(ValueError): proof.validate_sequence(f, ('cameraPosition',))
        with self.assertRaises(ValueError): proof.validate_snapshots([fixture(0), fixture(2), fixture(1)])
        with self.assertRaises(ValueError): proof.validate_sequence(frames(), ('absent',))

    def test_visible_negative_controls(self):
        r = fixture()
        f = image(r)
        f.putpixel((320, 240), (1, 2, 3, 255))
        with self.assertRaisesRegex(ValueError, 'WorldPainter pixels'): proof.visible(f, r)
        f = image(r)
        ImageDraw.Draw(f).rectangle((220, 140, 227, 140), fill='black')
        with self.assertRaisesRegex(ValueError, 'Font label absent'): proof.visible(f, r)
        for field, value in (('cameraPosition', [65, 48]), ('cameraPixelRatio', True)):
            r = fixture()
            r[field] = value
            with self.assertRaises(ValueError): proof.visible(image(r), r)

    def test_lua_owned_restore_and_literal_operations(self):
        lua = (Path(__file__).parent / 'id-map-assets/behaviorlab/id-map-consumer.lua').read_text()
        self.assertNotIn('clearAllPersistentEffects', lua)
        self.assertNotIn('storage', lua)
        for literal in ('local stat = "behaviorLabIdMap"',
                        'local a, b = "behaviorLabIdMapA", "behaviorLabIdMapB"',
                        'status.addPersistentEffects(a, effect(8))',
                        'status.addPersistentEffects(a, effect(4))',
                        'status.setPersistentEffects(a, effect(16))',
                        'status.addPersistentEffects(b, effect(2))',
                        'status.addPersistentEffects(a, effect(32))',
                        'observations[#observations + 1] = actual'):
            self.assertIn(literal, lua)
        for literal in ('read(8)', 'read(12)', 'read(16)', 'read(18)', 'read(2)', 'read(34)',
                        'status.stat(stat)', 'actual == expected', 'value == 0'):
            self.assertIn(literal, lua)
        restore = lua.split('function restore()', 1)[1]
        self.assertEqual(restore.count('status.clearPersistentEffects('), 2)
        self.assertIn('status.clearPersistentEffects(a)', restore)
        self.assertIn('status.clearPersistentEffects(b)', restore)
        self.assertIn('return 0', restore)
        self.assertLess(lua.index('value = read(34)'), lua.index('math.floor(value * 4)'))


if __name__ == '__main__':
    unittest.main()
