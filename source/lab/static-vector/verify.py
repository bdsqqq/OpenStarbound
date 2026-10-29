#!/usr/bin/env python3
"""Read-only replay of a finite native value experiment; never launches tools."""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HEADER_SHA = 'dafbafd5bc45329bab5da1fc02a360bc7c3e8e62323e77e61b496f4a2d0f5832'
STATUS = 'FINITE_NATIVE_STATIC_VECTOR_VALUES_NOT_RUST_OR_GAME'
MUTANTS = {'move-clears-source': 'move.source', 'forward-shift': 'insert.range.overlap',
           'resize-request-only': 'error.resize.quirk'}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


model = load('_static_vector_model', HERE / 'model.py')
syntax = load('_static_vector_syntax', HERE.parent / 'ttl-production/game_syntax.py')
sdk = load('_static_vector_sdk', HERE.parent / 'path-embed-replay/sdk_witness.py')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def stamp(text):
    value = dt.datetime.fromisoformat(text)
    need(value.tzinfo is not None, 'timezone required')
    return value.timestamp()


def window(start, deadline, now=None):
    a, b = stamp(start), stamp(deadline)
    need(0 < b - a <= 2100, 'original unit window must be <=35 minutes')
    if now is not None:
        need(a <= now < b, 'expired input admission; no renewal')
    return a, b


def mutant_headers(raw):
    pairs = {
        'move-clears-source': ('  for (auto& e : other)\n    emplace_back(std::move(e));',
                               '  for (auto& e : other)\n    emplace_back(std::move(e));\n  other.clear();'),
        'forward-shift': ('for (size_t i = toShift; i != 0; --i)',
                          'for (size_t i = 1; i <= toShift; ++i)'),
        'resize-request-only': ('m_size + size, MaxSize);', 'size, MaxSize);'),
    }
    result = {}
    for name, (old, new) in pairs.items():
        need(raw.count(old) == 1, 'unique source-derived mutant: ' + name)
        result[name] = raw.replace(old, new)
    return result


def negative_source():
    return ('#include <algorithm>\n#include <iterator>\n#include <new>\n'
            '#include <type_traits>\n#include <utility>\n'
            '#include "StarStaticVector.original.hpp"\n'
            'int main() { Star::StaticVector<int, 4> v; v = {1, 2}; }\n')


def dependencies(path):
    text = Path(path).read_text().replace('\\\n', ' ')
    need(':' in text, 'dependency rule missing')
    return shlex.split(text.split(':', 1)[1])


def semantic_outputs(outputs):
    first, repeat = (json.loads(outputs[k]) for k in ('baseline-run', 'baseline-repeat'))
    model.validate(first)
    model.validate(repeat)
    need(first == repeat, 'baseline repeat differs, including ABI observations')
    for name, case in MUTANTS.items():
        doc = json.loads(outputs[name + '-run'])
        try:
            model.validate(doc)
        except ValueError:
            pass
        else:
            raise ValueError('actual semantic mutant accepted: ' + name)
        need(set(doc) == {'schema', 'cases', 'abiObservations'} and
             type(doc['schema']) is int and doc['schema'] == 1 and
             doc['abiObservations'] == first['abiObservations'], 'mutant producer schema/ABI drift')
        rows = doc.get('cases', [])
        names = [r['name'] for r in rows]
        need(len(names) == len(set(names)) and set(names) == set(model.EXPECTED),
             'mutant must remain a complete producer')
        actual = {r['name']: r['value'] for r in rows}
        need(not model._exact(actual[case], model.EXPECTED[case]),
             'mutant failed without its specified witness: ' + case)
    return dict(cases=len(model.EXPECTED), baselineRepeatEqual=True,
                rejectedSemanticMutants=list(MUTANTS))


def diagnostic(data):
    # Source-derived dependent list[i] failure, not any arbitrary compile error.
    need(b'initializer_list' in data and b'list[i]' in data and
         (b'does not provide a subscript operator' in data or b'no match for' in data),
         'expected initializer_list subscript diagnostic')


def consumed_map(path):
    # Link maps may contain non-UTF8 symbol names. Only path lines are decoded
    # with filesystem semantics, never lossy replacement of the whole map.
    return [os.fsdecode(p) for p in re.findall(rb'^\[\s*\d+\] (.*\.tbd)\r?$',
                                             Path(path).read_bytes(), re.M)]


def providers(path, role, out, admission):
    data = Path(path).read_bytes()
    objects = [os.fsdecode(p) for p in re.findall(rb'^\[\s*\d+\] (.*)\r?$', data, re.M)]
    fixture = str(out / (role + '.o'))
    need(fixture in objects, 'missing actual fixture object provider')
    need(not any('rust' in p.lower() and '.a(' in p for p in objects), 'unexpected Rust archive provider')
    for name in objects:
        native = name.split('(', 1)[0]
        if native == fixture:
            continue
        if Path(native).is_absolute() and (native.endswith('.o') or native.endswith('.a')):
            syntax.subset([native], admission['witness'])
    return objects


def argv_inputs(argv):
    outputs = {argv[i + 1] for i, x in enumerate(argv[:-1]) if x in ('-o', '-MF')}
    return {arg: sha(arg) for arg in argv if arg not in outputs and
            Path(arg).is_absolute() and Path(arg).is_file()}


def receipt(plan, row, admission_sha, start, deadline, previous):
    a, b = window(start, deadline)
    need(row['name'] == plan['name'] and row['argv'] == plan['argv'], 'receipt role/argv drift')
    need(row['admissionSha256'] == admission_sha, 'receipt admission drift')
    need(type(row['pid']) is int and row['pid'] > 0 and row['pgid'] == row['pid'], 'owned group required')
    began, ended = stamp(row['startedUTC']), stamp(row['endedUTC'])
    need(a <= previous <= began <= ended < b, 'receipt outside original window/order')
    need(type(row['returncode']) is int and row['returncode'] == plan['expected'] and row['timedOut'] is False and
         row['reaped'] is True and row['groupGone'] is True, 'failed process receipt')
    need(type(row['timeoutSeconds']) in (int, float) and
         0 < row['timeoutSeconds'] <= min(180, b - began), 'timeout exceeds original remaining')
    need(row['stdin'] == 'DEVNULL' and row['cwd'] == str(ROOT), 'stdin/cwd drift')
    return ended


def replay(output, admission_sha):
    out = Path(output).resolve(strict=True)
    need(sha(out / 'admission.json') == admission_sha, 'external admission pin mismatch')
    admission = read(out / 'admission.json')
    # Load only current source primitives; reconstruct argv from independently
    # selected current recipe, never execute an old controller.
    runner = load('_static_vector_runner_replay', HERE / 'run.py')
    runner.check_admission(out, admission, executing=False)
    report = read(out / 'report.json')
    need(report['status'] == STATUS and report['admissionSha256'] == admission_sha, 'report scope/pin')
    plans = admission['commands']
    need(report['commands'] == [p['name'] for p in plans], 'exact command membership/order')
    previous = stamp(admission['startedUTC'])
    pids, outputs = set(), {}
    products = report['products']
    need(products and set(products) == {str(p.relative_to(out)) for p in out.rglob('*')
        if p.is_file() and p.name not in ('report.json', 'acquisition.stdout', 'acquisition.stderr')},
        'exact output membership')
    for name, digest in products.items():
        path = out / name
        need(path.is_relative_to(out) and sha(path) == digest, 'changed output: ' + name)
    for plan in plans:
        name = plan['name']
        row = read(out / (name + '.receipt.json'))
        previous = receipt(plan, row, admission_sha, admission['startedUTC'],
                           admission['deadlineUTC'], previous)
        need(read(out / (name + '.started.json')) == dict(pid=row['pid'], pgid=row['pgid'],
             startedUTC=row['startedUTC']), 'process start receipt drift')
        need(row['pid'] not in pids, 'duplicate process receipt')
        pids.add(row['pid'])
        need(row['env'] == admission['env'], 'receipt environment drift')
        for channel in ('stdout', 'stderr'):
            need(sha(out / (name + '.' + channel)) == row[channel + 'Sha256'], 'stdio receipt drift')
        for path, digest in row['argvFiles'].items():
            need(sha(path) == digest, 'actual argv file drift')
        expected_files = argv_inputs(plan['argv'])
        need(row['argvFiles'] == expected_files, 'actual argv files membership')
        outputs[name] = (out / (name + '.stdout')).read_bytes()
        if name.endswith('-compile'):
            syntax.subset(dependencies(out / (name.removesuffix('-compile') + '.d')), admission['witness'])
    diagnostic((out / 'initializer-assignment-negative.stderr').read_bytes())
    runner.check_expansion(out, admission)
    for name in ('baseline', *MUTANTS):
        providers(out / (name + '.map'), name, out, admission)
        paths = consumed_map(out / (name + '.map'))
        need(paths, 'missing actual SDK interfaces')
        value = sdk.reconcile_consumed(read(out / 'sdk-before.json'), paths,
            requested_root=admission['recipe']['sdk'], expected_canonical_root=admission['recipe']['sdkCanonical'])
        need(value == read(out / (name + '.sdk-consumed.json')), 'SDK consumed reconciliation drift')
    need(read(out / 'sdk-before.json') == read(out / 'sdk-after.json'), 'SDK before/after drift')
    result = semantic_outputs(outputs)
    need(report['semantics'] == result, 'semantic report drift')
    return dict(status=STATUS, **result, commands=len(plans))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--admission-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(replay(args.output, args.admission_sha256), sort_keys=True))
