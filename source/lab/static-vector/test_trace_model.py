"""Hermetic checks of the literal oracle, NOT native trace evidence."""
import copy
import json
from pathlib import Path
import re
import unittest

import trace_model as model


def document():
    return {'schema': 1, 'cases': [
        {'name': name, 'value': value} for name, value in model.expected_cases().items()]}


class TraceModelTests(unittest.TestCase):
    def rejected(self, changed):
        with self.assertRaises(ValueError):
            model.validate(changed)

    def test_literal_membership(self):
        self.assertEqual(len(model.EXPECTED), 18)
        self.assertEqual(model.validate(document()), model.EXPECTED)

    def test_producer_case_names_match_literals(self):
        source = Path(__file__).with_name('trace.cpp').read_text()
        names = re.findall(r'emit\("([^"]+)"', source)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(model.EXPECTED))

    def test_json_roundtrip(self):
        self.assertEqual(model.validate(json.loads(json.dumps(document()))), model.EXPECTED)

    def test_expected_copy_is_isolated(self):
        expected = model.expected_cases()
        expected['emplace.back.publish']['events'].clear()
        self.assertEqual(model.EXPECTED['emplace.back.publish']['events'], ['ctor:7:size=1'])

    def test_all_cases_are_required(self):
        for i in range(len(model.EXPECTED)):
            with self.subTest(i=i):
                changed = document()
                del changed['cases'][i]
                self.rejected(changed)

    def test_duplicate_case(self):
        changed = document()
        changed['cases'].append(copy.deepcopy(changed['cases'][0]))
        self.rejected(changed)

    def test_unknown_case(self):
        changed = document()
        changed['cases'][0]['name'] = 'unknown'
        self.rejected(changed)

    def test_case_order_is_not_event_order(self):
        changed = document()
        changed['cases'].reverse()
        self.assertEqual(model.validate(changed), model.EXPECTED)

    def test_each_event_is_required(self):
        for i, case in enumerate(document()['cases']):
            for j in range(len(case['value']['events'])):
                with self.subTest(name=case['name'], event=j):
                    changed = document()
                    del changed['cases'][i]['value']['events'][j]
                    self.rejected(changed)

    def test_event_order(self):
        changed = document()
        events = changed['cases'][6]['value']['events']
        events[2], events[3] = events[3], events[2]
        self.rejected(changed)

    def test_each_snapshot_is_required(self):
        for i, case in enumerate(document()['cases']):
            for field in ('state', 'source'):
                if case['value'][field]:
                    with self.subTest(name=case['name'], field=field):
                        changed = document()
                        changed['cases'][i]['value'][field][0] += 1
                        self.rejected(changed)

    def test_result_bool_not_integer(self):
        for i in range(len(model.EXPECTED)):
            changed = document()
            changed['cases'][i]['value']['result'] = int(changed['cases'][i]['value']['result'])
            self.rejected(changed)

    def test_state_int_not_bool(self):
        changed = document()
        changed['cases'][0]['value']['state'][0] = True
        self.rejected(changed)

    def test_exact_typed_throw_and_message(self):
        for i, case in enumerate(document()['cases']):
            if case['value']['error']:
                for field in (0, 1):
                    changed = document()
                    changed['cases'][i]['value']['error'][field] += '!'
                    self.rejected(changed)

    def test_no_extra_fields(self):
        for level in ('document', 'case', 'value'):
            changed = document()
            target = (changed if level == 'document' else changed['cases'][0]
                      if level == 'case' else changed['cases'][0]['value'])
            target['extra'] = 0
            self.rejected(changed)

    def test_missing_fields(self):
        for field in ('events', 'state', 'source', 'result', 'error'):
            changed = document()
            del changed['cases'][0]['value'][field]
            self.rejected(changed)

    def test_bad_schema(self):
        for schema in (True, 0, 2, '1', None):
            changed = document()
            changed['schema'] = schema
            self.rejected(changed)

    def test_bad_shapes(self):
        for changed in (None, [], {}, {'schema': 1, 'cases': {}},
                        {'schema': 1, 'cases': [None]},
                        {'schema': 1, 'cases': [{'name': [], 'value': {}}]}):
            self.rejected(changed)

    def test_three_proposed_semantic_mutants(self):
        original = document()
        for name in ('emplace-publish-after', 'pop-publish-after',
                     'empty-insert-return-after-resize'):
            with self.subTest(name=name):
                self.rejected(model.semantic_mutant(original, name))
        self.assertEqual(model.validate(original), model.EXPECTED)

    def test_mutant_requires_witness(self):
        with self.assertRaises(ValueError):
            model.semantic_mutant({'schema': 1, 'cases': []}, 'emplace-publish-after')


if __name__ == '__main__':
    unittest.main()
