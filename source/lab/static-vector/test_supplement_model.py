"""Hermetic oracle/rejection tests; no compiler, native output or old imports."""
import ast
import copy
import json
from pathlib import Path
import re
import unittest

import supplement_model as model


class SupplementModelTests(unittest.TestCase):
    def document(self):
        return {'schema': 1, 'cases': [
            {'name': name, 'value': value}
            for name, value in model.expected_cases().items()]}

    def reject(self, document):
        with self.assertRaises(ValueError):
            model.validate(document)

    def test_complete_seventeen_cases(self):
        self.assertEqual(len(model.EXPECTED), 17)
        self.assertEqual(model.validate(self.document()), model.EXPECTED)

    def test_json_roundtrip(self):
        model.validate(json.loads(json.dumps(self.document())))

    def test_case_order_is_immaterial(self):
        doc = self.document()
        doc['cases'].reverse()
        model.validate(doc)

    def test_source_case_membership(self):
        source = Path(__file__).with_name('supplement.cpp').read_text()
        names = re.findall(r'emit\("([^"]+)"', source)
        self.assertEqual(len(names), 17)
        self.assertEqual(len(set(names)), 17)
        self.assertEqual(set(names), set(model.EXPECTED))

    def test_literal_table_not_computed_from_producer(self):
        source = Path(model.__file__).read_text()
        tree = ast.parse(source)
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'EXPECTED'
                                  for t in n.targets))
        self.assertEqual(ast.literal_eval(assignment.value), model.EXPECTED)
        self.assertEqual([n.names[0].name for n in tree.body if isinstance(n, ast.Import)], ['copy'])

    def test_expected_copy_is_independent(self):
        expected = model.expected_cases()
        expected['reentry.copy.assign']['state'].append(999)
        self.assertEqual(model.EXPECTED['reentry.copy.assign']['state'], [1, 2, 8])

    def test_synthetic_controls_rejected(self):
        for name in ('copy-cache-bound', 'resize-current-size', 'clear-cache-count'):
            with self.subTest(name=name):
                document = self.document()
                changed = model.semantic_mutant(document, name)
                self.reject(changed)
                model.validate(document)

    def test_control_requires_witness(self):
        with self.assertRaises(ValueError):
            model.semantic_mutant({'schema': 1, 'cases': []}, 'copy-cache-bound')

    def test_unknown_control_rejected(self):
        with self.assertRaises(KeyError):
            model.semantic_mutant(self.document(), 'not-a-mutant')

    def test_missing_each_case(self):
        for index in range(17):
            with self.subTest(index=index):
                doc = self.document()
                del doc['cases'][index]
                self.reject(doc)

    def test_duplicate_case(self):
        doc = self.document()
        doc['cases'].append(copy.deepcopy(doc['cases'][0]))
        self.reject(doc)

    def test_unknown_case(self):
        doc = self.document()
        doc['cases'][0]['name'] = 'unknown'
        self.reject(doc)

    def test_document_fields(self):
        for doc in (None, [], {}, {'schema': 1}, {'cases': []},
                    dict(self.document(), extra=0)):
            with self.subTest(doc=doc):
                self.reject(doc)

    def test_schema_exact_type_and_value(self):
        for value in (True, False, 1.0, '1', 0, 2, None):
            with self.subTest(value=value):
                doc = self.document()
                doc['schema'] = value
                self.reject(doc)

    def test_cases_exact_list(self):
        for value in ({}, (), None, 'cases'):
            doc = self.document()
            doc['cases'] = value
            self.reject(doc)

    def test_case_structure(self):
        for value in (None, [], {}, {'name': 1, 'value': {}},
                      {'name': 'reentry.clear'},
                      dict(self.document()['cases'][0], extra=1)):
            doc = self.document()
            doc['cases'][0] = value
            self.reject(doc)

    def test_value_fields_exact(self):
        for field in ('events', 'state', 'source', 'result', 'error'):
            doc = self.document()
            del doc['cases'][0]['value'][field]
            self.reject(doc)
        doc = self.document()
        doc['cases'][0]['value']['extra'] = 0
        self.reject(doc)

    def test_value_types_exact(self):
        for field, value in (('events', ()), ('state', ()), ('source', {}),
                             ('result', 1), ('error', ''), ('state', [True, 2, 8]),
                             ('state', [1.0, 2, 8]), ('events', [1]),
                             ('error', [1, 2])):
            with self.subTest(field=field, value=value):
                doc = self.document()
                doc['cases'][0]['value'][field] = value
                self.reject(doc)

    def test_event_order_rejected(self):
        for index in range(17):
            doc = self.document()
            events = doc['cases'][index]['value']['events']
            different = next((i for i, event in enumerate(events) if event != events[0]), None)
            if different is None:
                # Swapping identical fill-copy events is not a mutation.
                self.assertEqual(doc['cases'][index]['name'], 'ctor.fill.explicit')
                continue
            events[0], events[different] = events[different], events[0]
            self.reject(doc)

    def test_event_missing_and_extra(self):
        for append in (False, True):
            doc = self.document()
            events = doc['cases'][0]['value']['events']
            if append:
                events.append('unexpected:size=3')
            else:
                events.pop()
            self.reject(doc)

    def test_error_type_text_and_order(self):
        for error in ([], ['SupplementFailure'], ['wrong', 'copy assignment #2'],
                      ['SupplementFailure', 'wrong'], ['copy assignment #2', 'SupplementFailure']):
            doc = self.document()
            case = next(c for c in doc['cases'] if c['name'] == 'ctor.copy.unwind')
            case['value']['error'] = error
            self.reject(doc)

    def test_reentry_witnesses(self):
        expected = model.expected_cases()
        self.assertEqual(expected['reentry.resize.shrink']['state'], [0])
        self.assertEqual(expected['reentry.resize.grow']['events'][1:3],
                         ['ctor:9:size=2', 'copy.ctor:0:size=1'])
        self.assertEqual(expected['reentry.clear']['error'], [])

    def test_alias_witnesses(self):
        self.assertEqual(model.EXPECTED['alias.emplace.reference']['state'], [1, 2, 2, 3])
        self.assertEqual(model.EXPECTED['alias.insert.value']['state'], [1, 3, 2, 3])

    def test_unwind_reverse_cleanup(self):
        self.assertEqual(model.EXPECTED['ctor.copy.unwind']['events'][-2:],
                         ['dtor:0:size=2', 'dtor:1:size=2'])

    def test_no_old_trace_case_repeated(self):
        old_source = Path(__file__).with_name('trace_model.py').read_text()
        tree = ast.parse(old_source)
        table = next(ast.literal_eval(n.value) for n in tree.body
                     if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'EXPECTED' for t in n.targets))
        self.assertEqual(len(table), 18)
        self.assertFalse(set(table) & set(model.EXPECTED))


if __name__ == '__main__':
    unittest.main()
