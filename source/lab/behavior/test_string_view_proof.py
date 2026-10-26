"""Synthetic unit receipts ONLY: not native, Rust, worker, or application proof."""
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest
from PIL import Image
import string_view_proof as p


def fixture(backend='rust'):
    scopes = []
    for index, method in enumerate(p.METHODS):
        calls = {e: [0] * 58 for e in p.EVENTS}
        if backend == 'rust':
            for mode in p.REQUIRED[index]:
                calls['attempt'][mode] = calls['success'][mode] = 1
        scopes.append(dict(method=method, completed=True, calls=calls))
    q = dict(version=1, backend=backend, active=True, scopeThread='main', captureExcluded=True,
             valid=True, overflow=False, completed=True, scopes=scopes,
             transitions=deepcopy(p.TRANSITIONS), assetPath=p.ASSET_PATH,
             imageRead='normal-assets-cache-permitted', image=deepcopy(p.IMAGE), font=deepcopy(p.FONT))
    aggregate(q)
    return {'stringViewProof': q}


def aggregate(q):
    q['calls'] = {e: [sum(s['calls'][e][m] for s in q['scopes']) for m in range(58)] for e in p.EVENTS}


class StringViewProofTests(unittest.TestCase):
    def test_synthetic_cpp_rust_normalize_without_mutation(self):
        q = fixture(); before = deepcopy(q)
        result = p.validate(q)
        self.assertEqual(result, p.validate(fixture('cpp')))
        result['image']['rgba'][0][0] = 0
        self.assertEqual(q, before)

    def test_each_required_consumer_mode_missing_even_when_balanced(self):
        for scope, modes in enumerate(p.REQUIRED):
            for mode in modes:
                q = fixture()['stringViewProof']
                for e in p.EVENTS: q['scopes'][scope]['calls'][e][mode] = 0
                aggregate(q)
                with self.subTest(scope=scope, mode=mode), self.assertRaisesRegex(ValueError, 'missing consumer mode'):
                    p.validate_fields(q)

    def test_observer_only_getter_traffic_cannot_pass(self):
        for mode in (15, 16):
            q = fixture()['stringViewProof']
            for s in q['scopes']:
                s['calls'] = {e: [0] * 58 for e in p.EVENTS}
                s['calls']['attempt'][mode] = s['calls']['success'][mode] = 100
            aggregate(q)
            with self.assertRaisesRegex(ValueError, 'missing consumer mode'): p.validate_fields(q)

    def test_unrequired_suffix_search_modes_stay_zero(self):
        q = fixture()
        for m in (28, 29, *range(36, 42)):
            self.assertEqual(q['stringViewProof']['calls']['success'][m], 0)
        p.validate(q)

    def test_exception_is_not_success(self):
        q = fixture()['stringViewProof']
        q['scopes'][0]['calls']['success'][32] = 0
        q['scopes'][0]['calls']['exception'][32] = 1
        aggregate(q)
        with self.assertRaisesRegex(ValueError, 'missing consumer mode 32'): p.validate_fields(q)

    def test_cpp_forbids_balanced_rust_traffic(self):
        for scoped in (True, False):
            q = fixture('cpp')['stringViewProof']
            c = q['scopes'][0]['calls'] if scoped else q['calls']
            c['attempt'][15] = c['success'][15] = 1
            with self.assertRaisesRegex(ValueError, 'cpp Rust calls'): p.validate_fields(q)

    def test_wrong_rgb_alpha_dimensions_and_order(self):
        changes = [lambda v: v.update(width=3), lambda v: v.update(height=1),
                   lambda v: v.update(width=True), lambda v: v['rgba'].reverse(),
                   lambda v: v['rgba'].pop()]
        for pixel in range(4):
            for channel in range(4):
                changes.append(lambda v, i=pixel, c=channel: v['rgba'][i].__setitem__(c, 99))
        for change in changes:
            q = fixture(); change(q['stringViewProof']['image'])
            with self.assertRaisesRegex(ValueError, 'actual image'): p.validate(q)

    def test_transition_missing_wrong_or_not_cleared(self):
        changes = [lambda v: v.pop(), lambda v: v.reverse(),
                   lambda v: v[0].update(command='set'),
                   lambda v: v[0].update(rgba=[0,0,0,255]),
                   lambda v: v[1].update(rgba=[18,52,86,255]),
                   lambda v: v[1].update(rgba=[False,0,0,0])]
        for change in changes:
            q = fixture(); change(q['stringViewProof']['transitions'])
            with self.assertRaisesRegex(ValueError, 'state transitions'): p.validate(q)

    def test_separate_font_evidence_required(self):
        changes = [lambda v: v.update(completed=False), lambda v: v.update(valid=False),
                   lambda v: v['glyphs'].pop(), lambda v: v['events'].pop(),
                   lambda v: v.update(input='VIEW'),
                   lambda v: v['glyphs'][0].update(rgba=[18,52,86,255]),
                   lambda v: v['glyphs'][0].update(codepoint=87)]
        for change in changes:
            q = fixture(); change(q['stringViewProof']['font'])
            with self.assertRaisesRegex(ValueError, 'foreground font'): p.validate(q)

    def test_schema_flags_overflow_incomplete(self):
        for key in fixture()['stringViewProof']:
            q = fixture(); q['stringViewProof'].pop(key)
            with self.assertRaises(ValueError): p.validate(q)
        for key, value in [('version', True), ('version', 2), ('active', False), ('active', 1),
            ('valid', False), ('overflow', True), ('overflow', 0), ('completed', False),
            ('captureExcluded', False), ('scopeThread', 'worker'), ('backend', 'native'),
            ('extra', 1), ('imageRead', 'fresh-worker-application'), ('assetPath', '/fake.png')]:
            q = fixture(); q['stringViewProof'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): p.validate(q)

    def test_scope_identity_order_completion_and_count(self):
        changes = [lambda v: v.pop(), lambda v: v.reverse(), lambda v: v.append(deepcopy(v[0])),
                   lambda v: v[0].update(completed=False), lambda v: v[1].update(completed=1),
                   lambda v: v[0].update(method='imageOperationFromString'),
                   lambda v: v[1].update(method='TextPainter::renderText'),
                   lambda v: v[0].update(extra=1)]
        for change in changes:
            q = fixture(); change(q['stringViewProof']['scopes'])
            with self.assertRaises(ValueError): p.validate(q)

    def test_counter_types_shape_bounds_balance(self):
        for scoped in (True, False):
            for event in p.EVENTS:
                for bad in (True, False, -1, 2**64, 1.0, '1', None):
                    q = fixture()['stringViewProof']
                    c = q['scopes'][0]['calls'] if scoped else q['calls']
                    c[event][0] = bad
                    with self.assertRaisesRegex(ValueError, 'typed 58-mode'): p.validate_fields(q)
                for change in (lambda c: c.pop(event), lambda c: c[event].pop(),
                               lambda c: c[event].append(0), lambda c: c.update(extra=[]),
                               lambda c: c[event].__setitem__(0, 1)):
                    q = fixture()['stringViewProof']
                    c = q['scopes'][0]['calls'] if scoped else q['calls']
                    change(c)
                    with self.assertRaises(ValueError): p.validate_fields(q)

    def test_aggregate_cannot_credit_unscoped_observer(self):
        for delta in (-1, 1):
            q = fixture()['stringViewProof']
            for event in ('attempt', 'success'): q['calls'][event][33] += delta
            with self.assertRaisesRegex(ValueError, 'exact source scope sum'): p.validate_fields(q)

    def test_counter_modular_balance_does_not_wrap_scope_sum(self):
        c = {e: [0] * 58 for e in p.EVENTS}
        c['success'][0] = 2**64-1; c['exception'][0] = 1
        p.counters(c, 'rust')
        q = fixture()['stringViewProof']
        for s in q['scopes']:
            s['calls']['attempt'][0] = s['calls']['success'][0] = 2**63
        with self.assertRaisesRegex(ValueError, 'exact source scope sum'): p.validate_fields(q)

    def test_missing_consumer(self):
        for q in (None, {}, {'stringViewProof': None}, {'stringViewProof': []}):
            with self.assertRaises(ValueError): p.validate(q)

    def test_literal_asset_decodes_exactly(self):
        path = Path(__file__).parent / 'string-view-assets/behaviorlab/string-view.png'
        with Image.open(path) as image:
            self.assertEqual(image.mode, 'RGBA')
            self.assertEqual(image.size, (2, 2))
            self.assertEqual([list(v) for v in image.getdata()], p.SEED_RGBA)
            self.assertEqual(hashlib.sha256(image.tobytes()).hexdigest(),
                             'e6d2c6764da8618bd90a972b432a50ab3ff0f8a2a817fa2db69bbcc10bf02904')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), '6cb98f72dbd456f307799fd7216caebc214958d1436bb96999b9af4ab0c3ada3')


if __name__ == '__main__':
    unittest.main()
