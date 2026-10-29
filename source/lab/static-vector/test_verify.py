"""Hermetic source/reader controls. No native tool or subprocess execution."""
import ast
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import verify as v


class VerifyTests(unittest.TestCase):
    def document(self):
        return dict(schema=1, cases=[dict(name=k, value=x) for k, x in v.model.expected_cases().items()],
            abiObservations={'int.' + str(n): dict(sizeof=8, alignof=8) for n in (0, 1, 2, 4)})

    def outputs(self):
        doc = self.document()
        result = {'baseline-run': json.dumps(doc), 'baseline-repeat': json.dumps(doc)}
        result.update({k + '-run': json.dumps(v.model.semantic_mutant(doc, k)) for k in v.MUTANTS})
        return result

    def test_engine_archive_identity_not_rust_word(self):
        self.assertTrue(v.engine_archive('/tmp/libstar_engine_ffi.a'))
        self.assertTrue(v.engine_archive('/tmp/libstar_engine_ffi.a[4](body.o)'))
        self.assertFalse(v.engine_archive('/tmp/libabsl_demangle_rust.a'))
        self.assertFalse(v.engine_archive('/tmp/libabsl_decode_rust_punycode.a(part.o)'))

    def test_staged_preparation_never_accepts_native_receipts(self):
        runner = v.load('_static_vector_staging_fixture', Path(__file__).with_name('run.py'))
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary).resolve()
            for name in ('inputs', 'home', 'tmp'):
                (out / name).mkdir()
            for name, text in v.mutant_headers((runner.HERE / 'StarStaticVector.original.hpp').read_text()).items():
                (out / 'inputs' / (name + '.hpp')).write_text(text)
            (out / 'inputs/initializer-assignment.cpp').write_text(v.negative_source())
            (out / 'inputs/expected-cases.json').write_text(json.dumps(v.model.expected_cases()))
            runner.staged_inputs(out)
            (out / 'baseline.started.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'pre-native'):
                runner.staged_inputs(out)
            (out / 'baseline.started.json').unlink()
            (out / 'inputs/initializer-assignment.cpp').write_text('// changed')
            with self.assertRaisesRegex(ValueError, 'changed staged'):
                runner.staged_inputs(out)

    def test_actual_disjoint_budget_uses_allocated_bytes(self):
        runner = v.load('_static_vector_budget_fixture', Path(__file__).with_name('run.py'))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            out = root / 'build/native'; out.mkdir(parents=True)
            (out / 'artifact').write_bytes(b'x' * 4096)
            with patch.object(runner, 'ROOT', root):
                result = runner.budget(out)
            self.assertEqual(result['nativeRootBytes'], result['observation']['activeRootBytes'])
            self.assertTrue(result['observation']['complete'])
            self.assertGreater(result['nativeRootBytes'], 0)

    def test_native_cap_denial_retains_observation(self):
        runner = v.load('_static_vector_budget_failure', Path(__file__).with_name('run.py'))
        observed = dict(archiveBytes=0, liveBytes=0, activeRootBytes=128 * 1024**2 + 1)
        with patch.object(runner.allocation, 'measure', return_value=observed):
            with self.assertRaises(runner.allocation.AllocationError) as caught:
                runner.budget(Path('/unused'))
        self.assertIs(caught.exception.observation, observed)

    def test_semantics_positive(self):
        self.assertEqual(v.semantic_outputs(self.outputs())['cases'], 151)

    def test_changed_case(self):
        outputs = self.outputs()
        doc = self.document()
        doc['cases'][0]['value'] = [9]
        outputs['baseline-run'] = json.dumps(doc)
        with self.assertRaises(ValueError):
            v.semantic_outputs(outputs)

    def test_duplicate_case(self):
        doc = self.document()
        doc['cases'].append(doc['cases'][0])
        with self.assertRaises(ValueError):
            v.model.validate(doc)

    def test_mutant_must_fail(self):
        outputs = self.outputs()
        outputs['forward-shift-run'] = outputs['baseline-run']
        with self.assertRaisesRegex(ValueError, 'mutant accepted'):
            v.semantic_outputs(outputs)

    def test_mutant_specific_witness(self):
        outputs = self.outputs()
        doc = self.document()
        doc['cases'][0]['value'] = [7]
        outputs['forward-shift-run'] = json.dumps(doc)
        with self.assertRaisesRegex(ValueError, 'specified witness'):
            v.semantic_outputs(outputs)

    def test_repeat_abi(self):
        outputs = self.outputs()
        doc = self.document()
        doc['abiObservations']['int.0']['sizeof'] = 16
        outputs['baseline-repeat'] = json.dumps(doc)
        with self.assertRaisesRegex(ValueError, 'repeat differs'):
            v.semantic_outputs(outputs)

    def test_expired_input(self):
        with self.assertRaisesRegex(ValueError, 'expired'):
            v.window('2026-10-29T01:54:00+00:00', '2026-10-29T02:29:00+00:00',
                     v.stamp('2026-10-29T02:29:00+00:00'))

    def test_no_renewal(self):
        with self.assertRaisesRegex(ValueError, '35 minutes'):
            v.window('2026-10-29T01:54:00+00:00', '2026-10-29T02:30:00+00:00')

    def test_timezone(self):
        with self.assertRaisesRegex(ValueError, 'timezone'):
            v.stamp('2026-10-29T01:54:00')

    def test_missing_header(self):
        with tempfile.TemporaryDirectory() as temp:
            header = Path(temp) / 'header.hpp'
            header.write_text('header')
            witness = v.syntax.closure([Path(temp)])
            del witness['files'][str(header.resolve())]
            with self.assertRaises(AssertionError):
                v.syntax.subset([header], witness)

    def test_changed_header(self):
        with tempfile.TemporaryDirectory() as temp:
            header = Path(temp) / 'header.hpp'
            header.write_text('header')
            witness = v.syntax.closure([Path(temp)])
            header.write_text('changed')
            with self.assertRaises(AssertionError):
                v.syntax.unchanged(witness)

    def test_raw_map(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'map'
            path.write_bytes(b'bad symbol \x93\n[  4] /SDK/usr/lib/libc.tbd\n')
            self.assertEqual(v.consumed_map(path), ['/SDK/usr/lib/libc.tbd'])

    def test_provider_membership(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp).resolve()
            obj = out / 'core.o'
            obj.write_bytes(b'object')
            witness = v.syntax.closure([out])
            path = out / 'native.map'
            path.write_bytes(('[  1] ' + str(out / 'baseline.o') + '\n[  2] ' + str(obj) + '\n').encode())
            v.providers(path, 'baseline', out, {'witness': witness})
            del witness['files'][str(obj)]
            with self.assertRaises(AssertionError):
                v.providers(path, 'baseline', out, {'witness': witness})

    def test_diagnostic(self):
        v.diagnostic(b'initializer_list<int> does not provide a subscript operator\nlist[i]')
        with self.assertRaises(ValueError):
            v.diagnostic(b'header not found')

    def test_exact_mutants(self):
        raw = (v.HERE / 'StarStaticVector.original.hpp').read_text()
        self.assertEqual(v.sha(v.HERE / 'StarStaticVector.original.hpp'), v.HEADER_SHA)
        mutants = v.mutant_headers(raw)
        self.assertEqual(set(mutants), set(v.MUTANTS))
        self.assertIn('other.clear();', mutants['move-clears-source'])
        self.assertIn('for (size_t i = 1; i <= toShift; ++i)', mutants['forward-shift'])
        self.assertNotIn('m_size + size, MaxSize);', mutants['resize-request-only'])
        with self.assertRaises(ValueError):
            v.mutant_headers(raw + raw)

    def receipt_fixture(self):
        plan = dict(name='baseline-run', argv=['/fixture/native'], expected=0)
        row = dict(name=plan['name'], argv=plan['argv'], admissionSha256='pin', pid=42, pgid=42,
            startedUTC='2026-10-29T02:00:00+00:00', endedUTC='2026-10-29T02:00:01+00:00',
            returncode=0, timedOut=False, reaped=True, groupGone=True,
            timeoutSeconds=180, stdin='DEVNULL', cwd=str(v.ROOT))
        return plan, row

    def check_receipt(self, plan, row):
        return v.receipt(plan, row, 'pin', '2026-10-29T01:54:00+00:00',
                         '2026-10-29T02:29:00+00:00', v.stamp('2026-10-29T01:54:00+00:00'))

    def test_receipt_positive(self):
        self.check_receipt(*self.receipt_fixture())

    def test_receipt_changed(self):
        for key, value in [('returncode', 1), ('reaped', False), ('admissionSha256', 'wrong'),
                           ('pgid', 7), ('timeoutSeconds', 2200), ('endedUTC', '2026-10-29T02:30:00+00:00')]:
            with self.subTest(key=key):
                plan, row = self.receipt_fixture()
                row[key] = value
                with self.assertRaises(ValueError):
                    self.check_receipt(plan, row)

    def test_duplicate_role_receipt(self):
        plan, row = self.receipt_fixture()
        row['name'] = 'baseline-repeat'
        with self.assertRaisesRegex(ValueError, 'role/argv'):
            self.check_receipt(plan, row)

    def test_argv_outputs_not_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            src, obj, dep = [Path(temp) / x for x in ('src.cpp', 'out.o', 'out.d')]
            for p in (src, obj, dep):
                p.write_text(p.name)
            self.assertEqual(set(v.argv_inputs([str(src), '-o', str(obj), '-MF', str(dep)])), {str(src)})

    def test_plans_source_only(self):
        runner = v.load('_static_vector_test_runner', v.HERE / 'run.py')
        out = Path('/fixture/out')
        r = dict(compiler='/fixture/clang++', flags=['-O3', '-ffast-math'], linkFlags=[],
                 objects=['/fixture/old.o'], libraries=['/fixture/libnative.a'])
        plans = runner.plans(out, r)
        self.assertEqual(len(plans), 15)
        self.assertEqual(len(set(p['name'] for p in plans)), 15)
        compiles = [p for p in plans if p['name'].endswith('-compile')]
        self.assertEqual(len(compiles), 4)
        for p in compiles:
            self.assertIn('-DStaticVector=StaticVectorCharacterization', p['argv'])
            self.assertTrue(any(x.startswith('-DSTATIC_VECTOR_TEST_HEADER="/') for x in p['argv']))
        self.assertLess([p['name'] for p in plans].index('link-expand'),
                        [p['name'] for p in plans].index('baseline-link'))
        for path in (v.HERE / 'run.py', v.HERE / 'verify.py', Path(__file__)):
            ast.parse(path.read_text())
        self.assertIn('v = {1, 2}', v.negative_source())


if __name__ == '__main__':
    unittest.main()
