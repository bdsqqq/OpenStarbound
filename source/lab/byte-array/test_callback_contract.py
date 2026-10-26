import json
import unittest

import callback_contract as c


class CallbackContract(unittest.TestCase):
    def reject(self, rows):
        with self.assertRaises(ValueError):
            c.check(c.canonical(rows))

    def test_roundtrip_and_case_order(self):
        rows = c.expected()
        self.assertEqual(tuple(r['case'] for r in rows), c.CASES)
        self.assertEqual(c.check(c.canonical(rows)), 14)
        # Field order/JSON spacing is intentionally irrelevant.
        self.assertEqual(c.check(('\n'.join(json.dumps(r) for r in rows) + '\n').encode()), 14)
        self.reject(rows[::-1])
        self.reject(rows[:-1])

    def test_strict_json_and_types(self):
        raw = c.canonical(c.expected())
        for bad in (raw + b'\n', raw.replace(b'"case":', b'"case":"x","case":', 1),
                    raw.replace(b'"size":3', b'"size":NaN', 1),
                    raw.replace(b'"size":3', b'"size":Infinity', 1),
                    raw.replace(b'"size":3', b'"size":true', 1),
                    raw.replace(b'"size":3', b'"size":3.0', 1)):
            with self.subTest(bad=bad[:50]), self.assertRaises(ValueError):
                c.check(bad)
        for change in ('extra', 'missing', 'status'):
            rows = c.expected()
            if change == 'extra': rows[0]['extra'] = None
            if change == 'missing': del rows[0]['nested']
            if change == 'status': rows[0]['status'] = 'unknown'
            self.reject(rows)

    def test_defined_spans(self):
        for row in c.expected():
            for key in ('lhs', 'rhs', 'result', 'nested'):
                value = row[key]
                if value is None:
                    continue
                self.assertLessEqual(value['size'], 8)
                self.assertLessEqual(len(value['prefix']), value['size'])
                self.assertLessEqual(value['size'], value['capacity'])
                self.assertTrue(all(type(x) is int and 0 <= x <= 255 for x in value['prefix']))
                if row['case'] != 'shrink_noextend' or key != 'result':
                    self.assertEqual(len(value['prefix']), value['size'])
        rows = {r['case']: r for r in c.expected()}
        self.assertEqual(rows['shrink_noextend']['result'], c.receipt(3, 3, [60]))
        self.assertEqual(rows['shrink_extend']['result']['prefix'], [60, 41, 42, 43, 44])
        self.assertEqual(rows['flip_roles']['result'], c.receipt(0, 3, []))
        for name in ('throw_callback', 'throw_convert'):
            self.assertIsNone(rows[name]['result'])

    def test_known_bad_fixed_loop(self):
        rows = c.expected()
        rows[2]['events'] += ['call:2:11:41', 'call:3:12:42']
        rows[2]['result']['prefix'] = [60, 63, 66]
        self.reject(rows)

    def test_known_bad_stale_tail(self):
        rows = c.expected()
        rows[4]['result'] = c.receipt(5, 8, [60, 63, 42, 43, 44])
        self.reject(rows)

    def test_known_bad_proxy_cleanup(self):
        rows = c.expected()
        rows[8]['events'][1:3] = ['dtor:1', 'convert:1']
        self.reject(rows)
        rows = c.expected()
        rows[8]['result'] = c.receipt(5, 8, [60, 63, 66, 43, 44])
        self.reject(rows)

    def test_known_bad_reentry(self):
        rows = c.expected()
        rows[11]['nested'] = None
        self.reject(rows)

    def test_known_bad_dead_object_and_exception_identity(self):
        rows = c.expected()
        rows[13]['lhs'] = c.receipt(5, 64, [10, 11, 12, 13, 14])
        self.reject(rows)
        rows = c.expected()
        rows[10]['status'] = 'throw_other'
        self.reject(rows)


if __name__ == '__main__':
    unittest.main()
