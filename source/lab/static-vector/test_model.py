"""Hermetic source-only oracle tests; no subprocesses, native files or ABI goldens."""
import copy
import unittest

from model import EXPECTED, expected_cases, semantic_mutant, validate


def fixture():
    # Deliberately synthetic positive shape, NOT a native execution receipt.
    return {
        'schema': 1,
        'cases': [{'name': n, 'value': v} for n, v in expected_cases().items()],
        'abiObservations': {n: {'sizeof': 123, 'alignof': 7}
                            for n in ('int.0', 'int.1', 'int.2', 'int.4')},
    }


class ModelTests(unittest.TestCase):
    def reject(self, change):
        doc = fixture()
        change(doc)
        with self.assertRaises(ValueError):
            validate(doc)

    def test_positive_literal_membership(self):
        self.assertEqual(validate(fixture()), EXPECTED)

    def test_literals_are_isolated(self):
        values = expected_cases()
        values['move.source'].clear()
        self.assertEqual(EXPECTED['move.source'], [1, 2])

    def test_semantic_mutants(self):
        for name in ('move-clears-source', 'forward-shift', 'resize-request-only'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate(semantic_mutant(fixture(), name))

    def test_wrong_return(self):
        self.reject(lambda d: next(c for c in d['cases'] if c['name'] ==
                    'erase.single.3.return').update(value=2))

    def test_wrong_state(self):
        self.reject(lambda d: next(c for c in d['cases'] if c['name'] ==
                    'error.insert.range')['value'][2].append(3))

    def test_wrong_exception_type(self):
        self.reject(lambda d: next(c for c in d['cases'] if c['name'] ==
                    'error.at.const')['value'].__setitem__(0, 'StaticVectorSizeException'))

    def test_wrong_exception_prefix(self):
        self.reject(lambda d: next(c for c in d['cases'] if c['name'] ==
                    'error.at.const')['value'].__setitem__(1, 'out of range in StaticVector::at(3)'))

    def test_missing_case(self):
        self.reject(lambda d: d['cases'].pop())

    def test_duplicate_case(self):
        self.reject(lambda d: d['cases'].append(copy.deepcopy(d['cases'][0])))

    def test_unknown_case(self):
        self.reject(lambda d: d['cases'].append({'name': 'unknown', 'value': []}))

    def test_bool_not_int(self):
        self.reject(lambda d: next(c for c in d['cases'] if c['name'] ==
                    'compare.self')['value'].__setitem__(0, 1))

    def test_schema_not_bool(self):
        self.reject(lambda d: d.update(schema=True))

    def test_extra_document_fields(self):
        self.reject(lambda d: d.update(unexpected=1))

    def test_extra_case_fields(self):
        self.reject(lambda d: d['cases'][0].update(unexpected=1))

    def test_abi_is_not_calibrated(self):
        doc = fixture()
        doc['abiObservations']['int.0'] = {'sizeof': 999999, 'alignof': 128}
        self.assertEqual(validate(doc), EXPECTED)

    def test_abi_names(self):
        self.reject(lambda d: d['abiObservations'].pop('int.0'))

    def test_abi_shape(self):
        self.reject(lambda d: d['abiObservations']['int.0'].update(sizeof=True))
        self.reject(lambda d: d['abiObservations']['int.0'].update(alignof=0))

    def test_order_not_contract(self):
        doc = fixture()
        doc['cases'].reverse()
        self.assertEqual(validate(doc), EXPECTED)


if __name__ == '__main__':
    unittest.main()
