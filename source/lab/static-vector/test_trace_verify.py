"""Hermetic verifier/controller contracts; no native execution or tool probes."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import trace_verify as t
r = t.v.load('_trace_runner_tests', HERE / 'trace_run.py')


def document():
    return dict(schema=1, cases=[dict(name=n, value=v) for n, v in t.model.expected_cases().items()])


def outputs():
    doc = document()
    return {'baseline-run': json.dumps(doc), 'baseline-repeat': json.dumps(doc),
            **{n + '-run': json.dumps(t.model.semantic_mutant(doc, n)) for n in t.MUTANTS}}


class TraceContracts(unittest.TestCase):
    def test_complete_rejection_composition(self):
        result = t.semantic_outputs(outputs())
        self.assertEqual(result['cases'], 18)
        self.assertEqual(result['rejectedSemanticMutants'], list(t.MUTANTS))

    def test_accepted_actual_mutant_rejected(self):
        for n in t.MUTANTS:
            data = outputs()
            data[n + '-run'] = data['baseline-run']
            with self.assertRaisesRegex(ValueError, 'witness'):
                t.semantic_outputs(data)

    def test_missing_mutant_case_is_not_semantic_evidence(self):
        data = outputs()
        n = next(iter(t.MUTANTS))
        doc = json.loads(data[n + '-run'])
        doc['cases'].pop()
        data[n + '-run'] = json.dumps(doc)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            t.semantic_outputs(data)

    def test_repeat_drift_rejected(self):
        data = outputs()
        data['baseline-repeat'] = data[next(iter(t.MUTANTS)) + '-run']
        with self.assertRaises(ValueError):
            t.semantic_outputs(data)

    def test_mutant_typed_data(self):
        data = outputs()
        n = next(iter(t.MUTANTS))
        doc = json.loads(data[n + '-run'])
        doc['cases'][0]['value']['result'] = 0
        data[n + '-run'] = json.dumps(doc)
        with self.assertRaisesRegex(ValueError, 'boolean'):
            t.semantic_outputs(data)

    def test_unique_source_mutations_and_correct_slot_addresses(self):
        raw = (HERE / 'StarStaticVector.original.hpp').read_text()
        mutants = t.mutant_headers(raw)
        self.assertEqual(set(mutants), set(t.MUTANTS))
        self.assertIn('new (ptr() + m_size) Element', mutants['emplace-publish-after'])
        self.assertIn('(ptr() + m_size - 1)->~Element();', mutants['pop-publish-after'])
        self.assertIn('resize(m_size + toAdd);\n  if (toAdd == 0) return pos;', mutants['empty-insert-return-after-resize'])
        with self.assertRaises(ValueError):
            t.mutant_headers(raw + raw)

    def test_specific_diagnostic(self):
        t.diagnostic(b'call to deleted constructor of NoDefault; Element(); resize insert')
        for data in (b'file not found', b'deleted constructor NoDefault Element() resize'):
            with self.assertRaises(ValueError):
                t.diagnostic(data)

    def test_future_plans(self):
        fake = dict(flags=['-O3', '-ffast-math'], compiler='/fixture/clang++',
                    linkFlags=[], objects=['/fixture/a.o'], libraries=['/fixture/a.a'])
        plans = r.plans(Path('/owned/out'), fake)
        self.assertEqual(len(plans), 17)
        self.assertEqual(sum(p['expected'] == 1 for p in plans), 1)
        self.assertEqual(plans[-2]['name'], 'no-default-copy-negative')
        self.assertTrue(all('-DStaticVector=StaticVectorCharacterization' in p['argv']
                            for p in plans if p['name'].endswith('-compile')))
        self.assertLess([p['name'] for p in plans].index('baseline-repeat'),
                        [p['name'] for p in plans].index('emplace-publish-after-compile'))
        self.assertTrue(all('trace.cpp' in ' '.join(p['argv'])
                            for p in plans if p['name'].endswith('-compile')))


if __name__ == '__main__':
    unittest.main()
