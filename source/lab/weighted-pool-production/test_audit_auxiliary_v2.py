"""Hermetic membership controls; the duplicate-reference omission must fail."""
import unittest
from unittest.mock import patch
import audit_auxiliary_v2 as a


class AuxiliaryMembershipTests(unittest.TestCase):
    def test_exact_pair_has_22_unique_prefixes(self):
        prefixes = a.membership([dict(role='reference'), dict(role='candidate')])
        self.assertEqual(len(prefixes), 22)
        self.assertEqual(len(set(prefixes)), 22)
        self.assertEqual(sum(p.startswith('cli/candidate/') for p in prefixes), 6)

    def test_known_duplicate_reference_omission_detected_before_replay(self):
        recipes = [dict(role='reference'), dict(role='reference')]
        with patch.object(a.original, 'load', return_value=dict(recipes=recipes)), patch.object(a.original, 'audit') as replay:
            with self.assertRaisesRegex(ValueError, 'one reference and one candidate'):
                a.audit()
            replay.assert_not_called()

    def test_all_four_membership_falsifiers_rejected(self):
        self.assertEqual(a.membership_controls(), ['duplicate-reference', 'duplicate-candidate', 'missing-candidate', 'extra-candidate'])

    def test_swapped_or_missing_roles_rejected(self):
        with self.assertRaises(ValueError):
            a.membership([dict(role='candidate'), dict(role='reference')])
        with self.assertRaises(KeyError):
            a.membership([dict(role='reference'), dict()])


if __name__ == '__main__':
    unittest.main()
