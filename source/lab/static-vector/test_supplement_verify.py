"""No native launch: declared witness, complete-producer and future argv checks."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import supplement_verify as t
r = t.v.load('_supplement_runner_tests', HERE / 'supplement_run.py')


def document():
    return dict(schema=1, cases=[dict(name=n, value=v) for n, v in t.model.expected_cases().items()])


def outputs():
    doc = document()
    return {'baseline-run': json.dumps(doc), 'baseline-repeat': json.dumps(doc),
            **{n + '-run': json.dumps(t.model.semantic_mutant(doc, n)) for n in t.MUTANTS}}


class SupplementContracts(unittest.TestCase):
    def test_complete_rejection_composition(self):
        result = t.semantic_outputs(outputs())
        self.assertEqual(result['cases'], 17)
        self.assertEqual(result['rejectedSemanticMutants'], list(t.MUTANTS))

    def test_baseline_is_not_a_negative_control(self):
        for n in t.MUTANTS:
            data = outputs(); data[n + '-run'] = data['baseline-run']
            with self.assertRaisesRegex(ValueError, 'witness'):
                t.semantic_outputs(data)

    def test_arbitrary_mismatch_is_not_declared_witness(self):
        data = outputs(); n = 'copy-cache-bound'
        doc = json.loads(data[n + '-run'])
        next(row for row in doc['cases'] if row['name'] == t.MUTANTS[n])['value']['state'] = [99]
        data[n + '-run'] = json.dumps(doc)
        with self.assertRaisesRegex(ValueError, 'witness'):
            t.semantic_outputs(data)

    def test_missing_case_not_semantic_evidence(self):
        data = outputs(); n = next(iter(t.MUTANTS))
        doc = json.loads(data[n + '-run']); doc['cases'].pop()
        data[n + '-run'] = json.dumps(doc)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            t.semantic_outputs(data)

    def test_repeat_drift(self):
        data = outputs(); data['baseline-repeat'] = data['resize-current-size-run']
        with self.assertRaises(ValueError): t.semantic_outputs(data)

    def test_mutant_types(self):
        data = outputs(); n = next(iter(t.MUTANTS))
        doc = json.loads(data[n + '-run']); doc['cases'][0]['value']['result'] = 0
        data[n + '-run'] = json.dumps(doc)
        with self.assertRaisesRegex(ValueError, 'boolean'): t.semantic_outputs(data)

    def test_exact_header_mutations(self):
        raw = (HERE / 'StarStaticVector.original.hpp').read_text()
        headers = t.mutant_headers(raw)
        self.assertEqual(set(headers), set(t.MUTANTS))
        self.assertIn('size_t initialSize = m_size;', headers['copy-cache-bound'])
        self.assertIn('while (m_size > size)', headers['resize-current-size'])
        self.assertIn('for (size_t i = m_size; i != 0; --i)', headers['clear-cache-count'])
        for text in headers.values():
            self.assertIn('  m_size += 1;\n  new (ptr() + m_size - 1)', text)
        with self.assertRaises(ValueError): t.mutant_headers(raw + raw)

    def test_future_argv(self):
        fake = dict(flags=['-O3', '-ffast-math'], compiler='/fixture/clang++',
                    linkFlags=[], objects=['/fixture/a.o'], libraries=['/fixture/a.a'])
        plans = r.plans(Path('/owned/out'), fake)
        self.assertEqual(len(plans), 14)
        self.assertTrue(all(p['expected'] == 0 for p in plans))
        names = [p['name'] for p in plans]
        self.assertLess(names.index('baseline-repeat'), names.index('copy-cache-bound-compile'))
        for p in plans:
            if p['name'].endswith('-compile'):
                self.assertIn('-DStaticVector=StaticVectorCharacterization', p['argv'])
                self.assertIn(str(HERE / 'supplement.cpp'), p['argv'])


if __name__ == '__main__': unittest.main()
