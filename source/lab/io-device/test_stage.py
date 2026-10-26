"""Synthetic contract sensitivity; native evidence needs the separate stage CLI."""
import copy
import unittest
import stage
import audit_stage


def encoded(rows):
    return ('\n'.join(stage.CANON(r) for r in rows) + '\n').encode()


class ContractTests(unittest.TestCase):
    def test_frozen_contract(self):
        stage.check_values(encoded(stage.EXPECTED))
        self.assertEqual(len(stage.EXPECTED), 6)
        self.assertEqual([r['cursor'] for r in stage.EXPECTED], [6,-2,0,6,-2,0])
        self.assertEqual(stage.EXPECTED[2]['output'], '414142422e2e2e2e')
        self.assertEqual(stage.EXPECTED[5]['sink'], '61626364')

    def test_wrong_typed_numbers_cannot_equal_booleans(self):
        rows=copy.deepcopy(stage.EXPECTED)
        rows[0]['events'][0]['ordinal']=False
        with self.assertRaises(ValueError):stage.check_values(encoded(rows))

    def test_known_bad_effect_and_phase_are_detected(self):
        for mutate in (lambda r:r[2].update(output='41412e2e2e2e2e2e'),
                       lambda r:r[2].update(cursor=6),
                       lambda r:r[2]['events'][-1].update(phase='return'),
                       lambda r:r[0]['events'].pop(),
                       lambda r:r.reverse(),lambda r:r.pop()):
            rows=copy.deepcopy(stage.EXPECTED);mutate(rows)
            with self.assertRaises(ValueError):stage.check_values(encoded(rows))

    def test_schema_extra_field_is_not_ignored(self):
        rows=copy.deepcopy(stage.EXPECTED);rows[0]['ignored']=True
        with self.assertRaises(ValueError):stage.check_values(encoded(rows))

    def test_control_credit_requires_well_formed_six_rows(self):
        audit_stage.observations(encoded(stage.EXPECTED))
        for data in (b'', b'{', b'{}\n', b'\xff'):
            with self.subTest(data=data),self.assertRaises(ValueError):audit_stage.observations(data)
        rows=copy.deepcopy(stage.EXPECTED);rows[0]['events'][0]['ordinal']=False
        with self.assertRaises(ValueError):audit_stage.observations(encoded(rows))

    def test_namespace_adaptation_does_not_edit_method_literals(self):
        raw='#include "StarIODevice.hpp"\nnamespace Star {\nvoid f(){print("IODevice");}\n}\n'
        expected='#include "StarIODevice.reference.hpp"\nnamespace Star { namespace IODeviceReference {\nvoid f(){print("IODevice");}\n} }\n'
        self.assertEqual(stage.adapt(raw, True), expected)


if __name__=='__main__':unittest.main()
