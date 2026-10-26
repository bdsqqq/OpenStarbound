import copy
from pathlib import Path
import unittest
import callback_contract as contract
import callback_stage as stage


class CallbackStageTests(unittest.TestCase):
    def test_source_anchors_and_header_coherence(self):
        source=(Path(__file__).parent/'callback.cpp').read_text()
        variants=stage.controls(source)
        self.assertEqual(set(variants),{'stale-tail-control','resort-control'})
        for body in variants.values():
            self.assertEqual(body.count('#include "StarByteArray.hpp"'),1)
            self.assertIn('ByteArray wrongCombine',body)
            self.assertIn('return lhs->combineWith(Direct{c}, *rhs, extend);',body)
        with self.assertRaises(ValueError):stage.controls('missing native source anchor')

    def test_exact_normally_exiting_control_models(self):
        correct=contract.expected()
        for name,case in [('stale-tail-control','grow_large'),('resort-control','flip_roles')]:
            wrong=stage.wrong_expected(name)
            changed=[]
            for a,b in zip(correct,wrong):
                try:contract._typed_equal(a,b,'row')
                except ValueError:changed.append(a['case'])
            self.assertEqual(changed,[case])
            data=contract.canonical(wrong)
            stage.check_control(data,name)
            with self.assertRaises(ValueError):contract.check(data)

    def test_control_requires_all_fields_and_types(self):
        for mutate in ('bool','missing','extra-case'):
            rows=stage.wrong_expected('stale-tail-control')
            if mutate=='bool':rows[0]['result']['size']=True
            elif mutate=='missing':rows[0].pop('events')
            else:rows.append(copy.deepcopy(rows[-1]))
            with self.assertRaises(ValueError):stage.check_control(contract.canonical(rows),'stale-tail-control')

    def test_json_parser_sensitivity(self):
        for data in (b'{"case":"x","case":"x"}',b'{"x":Infinity}',b'not JSON'):
            with self.assertRaises(ValueError):stage.parse_rows(data)


if __name__=='__main__':unittest.main()
