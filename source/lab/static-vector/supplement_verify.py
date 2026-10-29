#!/usr/bin/env python3
"""Pure replay of separately admitted native generic supplement; never native launch."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify as v

model = v.load('_static_vector_supplement_model', HERE / 'supplement_model.py')
MUTANTS = {'copy-cache-bound': 'reentry.copy.assign',
           'resize-current-size': 'reentry.resize.grow',
           'clear-cache-count': 'reentry.clear'}
STATUS = 'FINITE_NATIVE_STATIC_VECTOR_SUPPLEMENT_NOT_RUST_OR_GAME'
WITNESSES = {
    'copy-cache-bound': ('state', [1, 2, 9]),
    'resize-current-size': ('state', [0, 9]),
    'clear-cache-count': ('error', ['OutOfRangeException',
        '(OutOfRangeException) StaticVector::pop_back called on empty StaticVector']),
}


def mutant_headers(raw):
    pairs = {
        'copy-cache-bound': (
            '  resize(other.size());\n  for (size_t i = 0; i < m_size; ++i)\n    operator[](i) = other[i];',
            '  resize(other.size());\n  size_t initialSize = m_size;\n  for (size_t i = 0; i < initialSize; ++i)\n    operator[](i) = other[i];'),
        'resize-current-size': (
            '  for (size_t i = m_size; i > size; --i)\n    pop_back();\n  for (size_t i = m_size; i < size; ++i)\n    emplace_back(e);',
            '  while (m_size > size)\n    pop_back();\n  while (m_size < size)\n    emplace_back(e);'),
        'clear-cache-count': (
            '  while (m_size != 0)\n    pop_back();',
            '  for (size_t i = m_size; i != 0; --i)\n    pop_back();'),
    }
    result = {}
    for name, (old, new) in pairs.items():
        v.need(raw.count(old) == 1, 'unique defined-domain mutant ' + name)
        result[name] = raw.replace(old, new)
    return result


def semantic_outputs(outputs):
    first, repeat = [json.loads(outputs[n]) for n in ('baseline-run', 'baseline-repeat')]
    model.validate(first)
    model.validate(repeat)
    v.need(first == repeat, 'native trace repeat drift')
    for name, witness in MUTANTS.items():
        doc = json.loads(outputs[name + '-run'])
        v.need(set(doc) == {'schema', 'cases'} and type(doc['schema']) is int and doc['schema'] == 1,
               'actual mutant schema drift')
        rows = doc['cases']
        v.need(type(rows) is list and all(type(r) is dict and set(r) == {'name', 'value'} for r in rows),
               'malformed mutant case rows')
        names = [r['name'] for r in rows]
        v.need(len(names) == len(set(names)) and set(names) == set(model.EXPECTED), 'incomplete mutant producer')
        actual = {r['name']: r['value'] for r in rows}
        for value in actual.values():
            v.need(type(value) is dict and set(value) == {'events', 'state', 'source', 'result', 'error'}, 'mutant value shape')
            v.need(type(value['result']) is bool, 'mutant boolean result')
            for k in ('events', 'error', 'state', 'source'):
                t = str if k in ('events', 'error') else int
                v.need(type(value[k]) is list and all(type(x) is t for x in value[k]), 'mutant typed list')
        field, expected = WITNESSES[name]
        v.need(model._exact(actual[witness][field], expected), 'actual mutant missed declared witness')
        try:
            model.validate(doc)
        except ValueError:
            pass
        else:
            raise ValueError('actual semantic mutant accepted')
    return dict(cases=len(model.EXPECTED), baselineRepeatEqual=True, rejectedSemanticMutants=list(MUTANTS))


def replay(output, admission_sha):
    out = Path(output).resolve(strict=True)
    v.need(v.sha(out / 'admission.json') == admission_sha, 'external admission pin')
    a = v.read(out / 'admission.json')
    runner = v.load('_static_vector_supplement_runner_replay', HERE / 'supplement_run.py')
    runner.check_admission(out, a, executing=False)
    v.need(not (out / 'failure.json').exists(), 'failed experiment is not a certificate')
    report = v.read(out / 'report.json')
    v.need(report['status'] == STATUS and report['admissionSha256'] == admission_sha, 'report scope/pin')
    plans = a['commands']
    v.need(report['commands'] == [p['name'] for p in plans], 'exact command membership/order')
    products = report['products']
    v.need(products and set(products) == {str(p.relative_to(out)) for p in out.rglob('*') if p.is_file()
           and p.name not in ('report.json', 'acquisition.stdout', 'acquisition.stderr')}, 'exact products')
    for name, digest in products.items():
        p = out / name
        v.need(p.is_relative_to(out) and v.sha(p) == digest, 'changed output: ' + name)
    previous, pids, outputs = v.stamp(a['startedUTC']), set(), {}
    for plan in plans:
        name = plan['name']
        row = v.read(out / (name + '.receipt.json'))
        previous = v.receipt(plan, row, admission_sha, a['startedUTC'], a['deadlineUTC'], previous)
        v.need(v.read(out / (name + '.started.json')) == dict(pid=row['pid'], pgid=row['pgid'],
               startedUTC=row['startedUTC']), 'process start drift')
        v.need(row['pid'] not in pids and row['env'] == a['env'], 'process/environment drift')
        pids.add(row['pid'])
        for channel in ('stdout', 'stderr'):
            v.need(v.sha(out / (name + '.' + channel)) == row[channel + 'Sha256'], 'stdio drift')
        v.need(row['argvFiles'] == v.argv_inputs(plan['argv']), 'actual argv input drift')
        outputs[name] = (out / (name + '.stdout')).read_bytes()
        if name.endswith('-compile'):
            v.syntax.subset(v.dependencies(out / (name.removesuffix('-compile') + '.d')), a['witness'])
    runner.base.check_expansion(out, a)
    for role in ('baseline', *MUTANTS):
        v.providers(out / (role + '.map'), role, out, a)
        paths = v.consumed_map(out / (role + '.map'))
        v.need(paths, 'actual SDK interfaces required')
        value = v.sdk.reconcile_consumed(v.read(out / 'sdk-before.json'), paths,
            requested_root=a['recipe']['sdk'], expected_canonical_root=a['recipe']['sdkCanonical'])
        v.need(value == v.read(out / (role + '.sdk-consumed.json')), 'SDK consumed drift')
    v.need(v.read(out / 'sdk-before.json') == v.read(out / 'sdk-after.json'), 'SDK after drift')
    result = semantic_outputs(outputs)
    v.need(report['semantics'] == result, 'semantic report drift')
    return dict(status=STATUS, **result, commands=len(plans), scope='bounded mutation reentry, lifetimes, explicit-pop throw, runtime alignment only')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--admission-sha256', required=True)
    args = p.parse_args()
    print(json.dumps(replay(args.output, args.admission_sha256), sort_keys=True))
