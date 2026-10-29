import copy
import importlib.util
from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('static_vector_proof', HERE / 'static_vector_proof.py')
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)
CONFIG = {'scenario': proof.SCENARIO, 'seed': 42, 'maxFrames': 1800, 'platformWrites': False}


def fixture(stage=0, backend='native', sequence=10):
    before = [['0000000000000000', '0000000000000000'] for _ in range(26)]
    after = copy.deepcopy(before)
    if backend == 'rust':
        for mode, delta in [(0, 1), (13, 2), (19, 2)]:
            after[mode][0] = f'{delta:016x}'
    positions = [(x, y) for x in (126, 2) for y in range(33, 60)] + [(116, 48), (12, 48)]
    samples = []
    for x, y in positions:
        foreground = 1 if stage == 1 and x in (126, 2) else proof.EMPTY_MATERIAL
        samples.append(dict(world=[x, y], renderIndex=[(x + 48) % 128, y - 16],
                            worldForeground=foreground, worldBackground=1,
                            renderedForeground=foreground, renderedBackground=1))
    p = dict(version=1, scenario=proof.SCENARIO, stage=stage, backend=backend, selector=proof.SELECTOR,
             frameSequence=sequence, scopeId=sequence, identityNotParity={'array': '0x1234', 'thread': '987'},
             route=proof.ROUTE, worldSize=[128, 96], clientWindow=[-32, 32, 32, 64],
             tileRange=[-48, 16, 48, 80], bufferTiles=16, callsiteCalls=1, splitCalls=1, returnedRects=2,
             splits=[{'rect': [80, 16, 128, 80], 'xOffset': -128}, {'rect': [0, 16, 48, 80], 'xOffset': 0}],
             countersBefore=before, countersAfter=after, tileMinPosition=[-48, 16], samples=samples,
             occluderColumns=[126, 2], painterSubmitted=True, configuration=copy.deepcopy(CONFIG))
    return dict(scenario=proof.SCENARIO, stage=proof.STAGES[stage], stageIndex=stage,
                staticVectorProof=p, worldSize=[128, 96], lightingCompleted=True, fullbright=False,
                inWorld=True, lightEntityReplicated=True, playerOutsideView=True, uiHidden=True,
                cameraPosition=[0, 48], cameraPixelRatio=2.0, materialId=1, material='smoothmetal')


def restoration(sequence=30):
    return dict(version=1, scenario=proof.SCENARIO, complete=True, ownedOccludersAbsent=True,
                occluderColumns=[126, 2], yRange=[33, 59], observerDisarmed=True,
                lastStage=2, lastCapturedFrameSequence=sequence, capture=proof.STAGES[2])


class ProofTests(unittest.TestCase):
    def validate(self, row, stage=0, backend='native'):
        return proof.validate(row, stage=stage, backend=backend, configuration=CONFIG)

    def sequence(self, rows, receipt, backend='native', code=0):
        return proof.validate_sequence(rows, receipt, backend=backend, configuration=CONFIG, process_exit_code=code)

    def test_positive_native_and_rust_three_state_sequences(self):
        observations = []
        for backend in ('native', 'rust'):
            rows = [fixture(i, backend, (i + 1) * 10) for i in range(3)]
            observations.append(self.sequence(rows, restoration(), backend))
        self.assertEqual(observations[0], observations[1])

    def test_uint64_constructor_counter_wrap_is_preserved(self):
        row = fixture(backend='rust')
        p = row['staticVectorProof']
        for mode, delta in [(0, 1), (13, 2), (19, 2)]:
            p['countersBefore'][mode][0] = f'{(1 << 64) - delta:016x}'
            p['countersAfter'][mode][0] = '0000000000000000'
        self.validate(row, backend='rust')

    def test_physical_camera_equivalent_wrap_representation(self):
        row = fixture()
        row['cameraPosition'][0] = 128
        self.validate(row)

    def test_empty_material_contract_matches_current_cpp(self):
        text = (HERE.parents[1] / 'game/StarMaterialTypes.hpp').read_text()
        value = re.search(r'EmptyMaterialId\s*=\s*(\d+);', text)
        self.assertEqual(int(value[1]), proof.EMPTY_MATERIAL)

    def test_frame_mutants_rejected(self):
        mutations = [
            ('missing schema', lambda r, p: p.pop('samples')),
            ('unknown schema', lambda r, p: p.update(extra=True)),
            ('global counts without callsite', lambda r, p: p.update(callsiteCalls=0)),
            ('wrong route', lambda r, p: p.update(route='proxy-vector')),
            ('wrong selector', lambda r, p: p.update(selector='STAR_USE_RUST_ID_MAP')),
            ('wrong backend', lambda r, p: p.update(backend='rust')),
            ('wrong configuration', lambda r, p: p['configuration'].update(seed=43)),
            ('configuration bool is not integer', lambda r, p: p['configuration'].update(platformWrites=0)),
            ('unassociated scope', lambda r, p: p.update(scopeId=11)),
            ('null array', lambda r, p: p['identityNotParity'].update(array='0x0')),
            ('wrong offset', lambda r, p: p['splits'][0].update(xOffset=-127)),
            ('reordered rectangles', lambda r, p: p['splits'].reverse()),
            ('gap', lambda r, p: p['splits'][0]['rect'].__setitem__(2, 127)),
            ('float coordinate', lambda r, p: p['splits'][1]['rect'].__setitem__(0, 0.0)),
            ('one rectangle', lambda r, p: p.update(returnedRects=1)),
            ('unpad window', lambda r, p: p.update(bufferTiles=15)),
            ('interior camera', lambda r, p: r.update(cameraPosition=[64, 48])),
            ('large width', lambda r, p: (p.update(clientWindow=[-48, 32, 48, 64], tileRange=[-64, 16, 64, 80]))),
            ('fake render index', lambda r, p: p['samples'][0]['renderIndex'].__setitem__(0, 0)),
            ('fake rendered foreground', lambda r, p: p['samples'][0].update(renderedForeground=1)),
            ('missing side', lambda r, p: p['samples'].pop()),
            ('duplicate tile', lambda r, p: p['samples'].__setitem__(1, copy.deepcopy(p['samples'][0]))),
            ('fake background', lambda r, p: p['samples'][-1].update(worldBackground=proof.EMPTY_MATERIAL)),
            ('bool sample', lambda r, p: p['samples'][-1].update(renderedBackground=True)),
            ('no painter', lambda r, p: p.update(painterSubmitted=False)),
            ('bool stage', lambda r, p: r.update(stageIndex=False)),
            ('no lighting', lambda r, p: r.update(lightingCompleted=False)),
            ('fullbright', lambda r, p: r.update(fullbright=True)),
            ('unreplicated lamp', lambda r, p: r.update(lightEntityReplicated=False)),
        ]
        for name, mutate in mutations:
            row = fixture()
            mutate(row, row['staticVectorProof'])
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.validate(row)

    def test_counter_mutants_rejected(self):
        cases = [('no actual constructor', lambda p: p['countersAfter'][0].__setitem__(0, '0000000000000000')),
                 ('unexpected continuation', lambda p: p['countersAfter'][1].__setitem__(1, '0000000000000001')),
                 ('bad mode shape', lambda p: p['countersAfter'].pop()),
                 ('noncanonical hex', lambda p: p['countersBefore'][0].__setitem__(0, '000000000000000A')),
                 ('numeric loss', lambda p: p['countersBefore'][0].__setitem__(0, 0))]
        for name, mutate in cases:
            row = fixture(backend='rust')
            mutate(row['staticVectorProof'])
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.validate(row, backend='rust')
        row = fixture()
        row['staticVectorProof']['countersBefore'][0][0] = '0000000000000001'
        with self.assertRaises(ValueError):
            self.validate(row)

    def test_sequence_and_restoration_mutants_rejected(self):
        rows = [fixture(i, sequence=(i + 1) * 10) for i in range(3)]
        for key, value in [('complete', False), ('observerDisarmed', False), ('ownedOccludersAbsent', False),
                           ('lastStage', 1), ('lastCapturedFrameSequence', 29), ('capture', proof.STAGES[1]),
                           ('complete', 1)]:
            receipt = restoration()
            receipt[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.sequence(rows, receipt)
        stale = copy.deepcopy(rows)
        stale[1]['staticVectorProof'].update(frameSequence=10, scopeId=10)
        with self.assertRaises(ValueError):
            self.sequence(stale, restoration())
        wrong_thread = copy.deepcopy(rows)
        wrong_thread[1]['staticVectorProof']['identityNotParity']['thread'] = '123'
        with self.assertRaises(ValueError):
            self.sequence(wrong_thread, restoration())
        for code in (1, -9, False):
            with self.subTest(code=code), self.assertRaises(ValueError):
                self.sequence(rows, restoration(), code=code)
        with self.assertRaises(ValueError):
            self.sequence(rows, None)


if __name__ == '__main__':
    unittest.main(verbosity=2)
