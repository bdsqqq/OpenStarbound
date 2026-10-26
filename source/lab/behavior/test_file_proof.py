"""Synthetic schema controls ONLY; no native File or application execution."""
import unittest
from copy import deepcopy
import file_proof as f


def synthetic(backend):
    def counts():
        return {e: [0] * f.MODE_COUNT for e in f.EVENTS}
    p = dict(version=1, backend=backend, scopeThread='main', mainThread=True,
             captureExcluded=True, valid=True, overflow=False, completed=True,
             calls=counts(), scopes=[], saveFile='buffer-save.sbvj',
             databaseFile='buffer-payload.btree', saveHex=f.SAVE_HEX, foundHex=f.SAVE_HEX)
    for i, method in enumerate(f.METHODS):
        c = counts()
        if backend == 'rust':
            for m in f.REQUIRED[i]:
                c['attempt'][m] = c['success'][m] = 1
        p['scopes'].append(dict(method=method, started=True, completed=True, mainThread=True, calls=c))
    totals(p)
    return p


def totals(p):
    for e in f.EVENTS:
        p['calls'][e] = [sum(s['calls'][e][m] for s in p['scopes']) % f.U64 for m in range(34)]


class SyntheticFileProofTests(unittest.TestCase):
    def test_good_cpp_rust_synthetic(self):
        for backend in ('cpp', 'rust'):
            p = synthetic(backend)
            f.validate({'fileProof': p})
            f.validate_snapshots([deepcopy(p) for _ in range(3)])

    def test_corruptions(self):
        def change(path, value):
            def mutate(p):
                for k in path[:-1]:
                    p = p[k]
                p[path[-1]] = value
            return mutate
        cases = {
            'unknown': change(['extra'], 1),
            'missing': lambda p: p.pop('foundHex'),
            'version-bool': change(['version'], True),
            'bool-int': change(['mainThread'], 1),
            'counter-bool': change(['calls', 'attempt', 0], False),
            'unbalanced': change(['scopes', 0, 'calls', 'attempt', 10], 2),
            'partial': change(['scopes', 2, 'completed'], False),
            'unstarted': change(['scopes', 2, 'started'], False),
            'order': lambda p: p['scopes'].reverse(),
            'main': change(['mainThread'], False),
            'scope-main': change(['scopes', 3, 'mainThread'], False),
            'observer-active': change(['captureExcluded'], False),
            'save-corruption': change(['saveHex'], '00' + f.SAVE_HEX[2:]),
            'found-corruption': change(['foundHex'], f.SAVE_HEX[:-2] + 'ff'),
            'scope-extra': change(['scopes', 0, 'extra'], False),
            'totals': change(['calls', 'success', 3], 200),
            'mode-count': lambda p: p['calls']['attempt'].append(0),
            'negative': change(['calls', 'attempt', 0], -1),
            'overflow': change(['calls', 'attempt', 0], f.U64),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                p = synthetic('rust'); mutate(p)
                with self.assertRaises(ValueError): f.validate_fields(p)

    def test_every_required_mode_zero(self):
        for i, modes in enumerate(f.REQUIRED):
            for mode in modes:
                with self.subTest(scope=i, mode=mode):
                    p = synthetic('rust')
                    for e in f.EVENTS: p['scopes'][i]['calls'][e][mode] = 0
                    totals(p)
                    with self.assertRaises(ValueError): f.validate_fields(p)

    def test_cpp_nonzero(self):
        p = synthetic('cpp')
        p['scopes'][0]['calls']['attempt'][0] = p['scopes'][0]['calls']['success'][0] = 1
        totals(p)
        with self.assertRaises(ValueError): f.validate_fields(p)

    def test_wrapping_balance_and_sum(self):
        p = synthetic('rust')
        for i in (0, 1):
            c = p['scopes'][i]['calls']
            c['attempt'][0], c['success'][0], c['exception'][0] = 0, f.U64-1, 1
        totals(p)
        f.validate_fields(p)

    def test_snapshot_drift_individually_valid(self):
        p = synthetic('rust'); q = deepcopy(p)
        q['scopes'][0]['calls']['attempt'][0] = q['scopes'][0]['calls']['success'][0] = 1
        totals(q); f.validate_fields(q)
        with self.assertRaises(ValueError): f.validate_snapshots([p, q, p])


class FilePipelineTests(unittest.TestCase):
    def receipt(self, backend='rust'):
        import behavior_lab as lab
        from test_buffer_proof import fixture
        value = dict.fromkeys(lab.SCENE_FIELDS, 0)
        for key in ('playerOutsideView', 'uiHidden', 'lightingCompleted', 'lightEntityReplicated'):
            value[key] = True
        value.update(fullbright=False, replicatedSettledUpdates=90, scenario='buffer-room')
        value.update(fixture(backend))
        value['fileProof'] = synthetic(backend)
        return value

    def test_semantic_pipeline_checks_before_projection(self):
        import behavior_lab as lab
        receipt = self.receipt()
        self.assertEqual(lab.semantic_world_state(receipt)['fileProof'], f.validate(receipt))
        receipt['fileProof']['captureExcluded'] = False
        with self.assertRaises(lab.LabError): lab.semantic_world_state(receipt)

    def test_legacy_absence_and_explicit_null_differ(self):
        import behavior_lab as lab
        receipt = self.receipt('cpp'); del receipt['fileProof']
        self.assertNotIn('fileProof', lab.semantic_world_state(receipt))
        lab.validate_file_sequence({str(i): {'receipt': deepcopy(receipt)} for i in range(3)})
        receipt['fileProof'] = None
        with self.assertRaises(lab.LabError): lab.semantic_world_state(receipt)
        with self.assertRaises(lab.LabError):
            lab.validate_file_sequence({str(i): {'receipt': deepcopy(receipt)} for i in range(3)})

    def test_frozen_sequence_pipeline_rejects_partial_and_valid_drift(self):
        import behavior_lab as lab
        frames = {str(i): {'receipt': self.receipt()} for i in range(3)}
        lab.validate_file_sequence(frames)
        del frames['1']['receipt']['fileProof']
        with self.assertRaises(lab.LabError): lab.validate_file_sequence(frames)
        frames['1']['receipt']['fileProof'] = synthetic('rust')
        p = frames['1']['receipt']['fileProof']
        p['scopes'][0]['calls']['attempt'][0] = p['scopes'][0]['calls']['success'][0] = 1
        totals(p); f.validate_fields(p)
        with self.assertRaises(lab.LabError): lab.validate_file_sequence(frames)


if __name__ == '__main__':
    unittest.main()
