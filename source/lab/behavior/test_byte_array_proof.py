"""Synthetic 56-counter fixtures, not actual application or route evidence."""
from copy import deepcopy
import unittest
import buffer_proof
import io_device_proof
import byte_array_proof as p
from test_io_device_proof import fixture as io_fixture


def fixture(backend='rust', mode=7):
    q = io_fixture(backend)
    scopes = []
    for index, method in enumerate([*buffer_proof.METHODS, io_device_proof.PNG_METHOD]):
        calls = {event: [0] * 56 for event in p.EVENTS}
        if backend == 'rust':
            calls['attempt'][mode] = calls['success'][mode] = 1
            if index < 4:
                calls['attempt'][36] = calls['success'][36] = 1
        scopes.append(dict(method=method, completed=True, calls=calls))
    calls = {event: [sum(s['calls'][event][i] for s in scopes) for i in range(56)]
             for event in p.EVENTS}
    q['bufferProof']['byteArray'] = dict(version=1, backend=backend, scopeThread='main',
        captureExcluded=True, calls=calls, scopes=scopes)
    return q


class ByteArrayProofTests(unittest.TestCase):
    def test_normalizes_only_after_validation_without_mutation(self):
        q = fixture()
        before = deepcopy(q)
        normalized = p.validate(q)
        self.assertEqual(normalized, p.validate(fixture('cpp')))
        self.assertEqual(q, before)
        self.assertEqual(normalized['byteArray'],
                         dict(version=1, scopeThread='main', captureExcluded=True))
        self.assertIn('ioDevice', normalized['consumer'])
        normalized['consumer']['visual']['color'][0] = 0
        self.assertEqual(q, before)

    def test_arbitrary_modes_and_extra_counts_are_not_fixed_coverage(self):
        q = fixture(mode=55)
        for event in ('attempt', 'success'):
            q['bufferProof']['byteArray']['calls'][event][3] = 19
        self.assertEqual(p.validate(q), p.validate(fixture()))

    def test_balanced_scope_suppression_rejected_for_every_scope(self):
        for i in range(14):
            with self.subTest(scope=i):
                q = fixture(); v = q['bufferProof']['byteArray']
                for event in p.EVENTS:
                    v['scopes'][i]['calls'][event] = [0] * 56
                for event in ('attempt', 'success'):
                    v['calls'][event][7] -= 1
                with self.assertRaisesRegex(ValueError, 'actual success absent'):
                    p.validate(q)

    def test_exception_only_scope_is_not_success(self):
        q = fixture(); v = q['bufferProof']['byteArray']
        for mode in (7, 36):
            v['scopes'][0]['calls']['success'][mode] = 0
            v['scopes'][0]['calls']['exception'][mode] = 1
            v['calls']['success'][mode] -= 1
            v['calls']['exception'][mode] += 1
        with self.assertRaisesRegex(ValueError, 'actual success absent'):
            p.validate(q)

    def test_observer_success_cannot_replace_receiver_append(self):
        q=fixture();v=q['bufferProof']['byteArray']
        for event in ('attempt','success'):
            v['scopes'][0]['calls'][event][36]=0
            v['calls'][event][36]-=1
            v['scopes'][0]['calls'][event][41]=1
            v['calls'][event][41]+=1
        with self.assertRaisesRegex(ValueError,'source receiver append'):
            p.validate(q)

    def test_missing_extension_rejected(self):
        for q in (None, {}, {'bufferProof': []}, io_fixture()):
            with self.subTest(receipt=q), self.assertRaises(ValueError):
                p.validate(q)

    def test_exact_schema_and_scope_identity(self):
        changes = [lambda v: v.update(extra=0), lambda v: v.pop('version'),
            lambda v: v.update(version=True), lambda v: v.update(version=1.0),
            lambda v: v.update(version=2), lambda v: v.update(backend='native'),
            lambda v: v.update(backend=True), lambda v: v.update(scopeThread='worker'),
            lambda v: v.update(captureExcluded=False), lambda v: v.update(captureExcluded=1),
            lambda v: v.update(scopes=tuple(v['scopes'])), lambda v: v['scopes'].pop(),
            lambda v: v['scopes'].append(deepcopy(v['scopes'][0])),
            lambda v: v['scopes'][0].update(extra=0),
            lambda v: v['scopes'][0].update(completed=1),
            lambda v: v['scopes'][0].update(completed=False),
            lambda v: v['scopes'][13].update(method='evidence writePng'),
            lambda v: v['scopes'].reverse()]
        for i, change in enumerate(changes):
            with self.subTest(case=i):
                q = fixture(); change(q['bufferProof']['byteArray'])
                with self.assertRaises(ValueError): p.validate(q)

    def test_counter_schema_types_bounds_and_balance(self):
        for scoped in (False, True):
            for event in p.EVENTS:
                changes = [lambda c: c.pop(event), lambda c: c.update(extra=[0]*56),
                    lambda c: c[event].pop(), lambda c: c[event].append(0),
                    lambda c: c.update({event: tuple(c[event])})]
                for bad in (True, False, -1, 2**64, 1.0, '1', None):
                    changes.append(lambda c, bad=bad: c[event].__setitem__(0, bad))
                changes.append(lambda c: c[event].__setitem__(0, 1))
                for i, change in enumerate(changes):
                    with self.subTest(scoped=scoped, event=event, case=i):
                        q = fixture(); v = q['bufferProof']['byteArray']
                        change(v['scopes'][0]['calls'] if scoped else v['calls'])
                        with self.assertRaises(ValueError): p.validate(q)

    def test_native_counts_rejected_even_if_balanced(self):
        for scoped in (False, True):
            q = fixture('cpp'); v = q['bufferProof']['byteArray']
            calls = v['scopes'][0]['calls'] if scoped else v['calls']
            calls['attempt'][0] = calls['success'][0] = 1
            with self.assertRaisesRegex(ValueError, 'native backend'):
                p.validate(q)

    def test_all_events_require_aggregate_containment(self):
        # Each mutation stays balanced; only containment can reject it.
        for event in p.EVENTS:
            q = fixture(); v = q['bufferProof']['byteArray']
            calls = v['scopes'][0]['calls']
            calls['attempt'][7] += 2; calls['exception'][7] += 2
            v['calls']['attempt'][7] += 2; v['calls']['exception'][7] += 2
            if event == 'attempt':
                v['calls']['attempt'][7] -= 1; v['calls']['success'][7] -= 1
            elif event == 'success':
                v['calls']['success'][7] -= 1; v['calls']['exception'][7] += 1
            else:
                v['calls']['exception'][7] -= 1; v['calls']['success'][7] += 1
            with self.subTest(event=event), self.assertRaisesRegex(ValueError, 'scope containment'):
                p.validate(q)

    def test_tls_balance_uses_u64_wrap_but_containment_does_not(self):
        calls = {event: [0]*56 for event in p.EVENTS}
        calls['success'][0] = 2**64 - 1; calls['exception'][0] = 1
        p.counters(calls, 'rust')
        q = fixture(); v = q['bufferProof']['byteArray']
        for scope in v['scopes'][:2]:
            scope['calls']['attempt'][7] = scope['calls']['success'][7] = 2**63
        v['calls']['attempt'][7] = v['calls']['success'][7] = 12
        with self.assertRaisesRegex(ValueError, 'scope containment'): p.validate(q)

    def test_inherited_contracts_stay_strict(self):
        changes = [lambda v: v['network'].update(actualWireHex='00'),
            lambda v: v['save'].update(wireHex='00'),
            lambda v: v['visual'].update(label='fake'),
            lambda v: v['ioDevice'].update(captureExcluded=False),
            lambda v: v.update(unrecognizedExtension={})]
        for i, change in enumerate(changes):
            with self.subTest(case=i):
                q = fixture(); change(q['bufferProof'])
                with self.assertRaises(ValueError): p.validate(q)


if __name__ == '__main__':
    unittest.main()
