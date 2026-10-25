#!/usr/bin/env python3
"""Verify native blueprint artifacts; synthetic corruptions are not executions."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from run import anchors

EXPECTED = '5ee512e3a91027823f34c47df4d1e056753e0fd61f03a9ad70e65131900763ab'
CONTROLS = {'early-order', 'skip-zero', 'reread-string-branch'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _verify(report, folder):
    need(report['status'] == 'FINITE_NATIVE_HOST_SELECTED_PROTOCOL_PASS', 'status')
    need(report['cases'] == 683 and report['definitions'] == 51, 'finite scope')
    before = json.loads((folder/'before.json').read_text())
    after = json.loads((folder/'after.json').read_text())
    need(before == after == report['bindings'], 'input maps disagree')
    for group in ('bindings', 'generated', 'binaries'):
        for name, expected in report[group].items():
            need(sha(name) == expected, group+' drift')
    receipts = json.loads((folder/'receipts.json').read_text())
    need(receipts == report['receipts'], 'receipt copies disagree')
    executed, names = set(), set()
    for receipt in receipts:
        name = receipt['name']
        need(name not in names and receipt['returncode'] == 0, 'failed/duplicate execution')
        names.add(name)
        exe = Path(receipt['command'][0]).resolve()
        need(sha(exe) == receipt['executable_sha256'], 'executed binary drift')
        executed.add(str(exe))
        for stream in ('stdout', 'stderr'):
            need(sha(folder/(name+'.'+stream)) == receipt[stream+'_sha256'], 'command output drift')
    need({str(Path(p).resolve()) for p in report['binaries']} <= executed, 'unexecuted binary')
    data = (folder/'prototype.stdout').read_bytes()
    need(report['ordered_sha256'] == EXPECTED == hashlib.sha256(data).hexdigest(), 'ordered digest')
    need(anchors(data) == 683 and (folder/'repeat.stdout').read_bytes() == data, 'native repeat/anchors')
    need(b'PASS' in (folder/'protocol.stdout').read_bytes(), 'protocol observation')
    need(set(report['normal_semantic_controls']) == CONTROLS, 'control scope')
    for name in CONTROLS:
        changed = report['normal_semantic_controls'][name]
        result = (folder/(name+'.stdout')).read_bytes()
        actual = [a.split(b'|')[0].decode() for a, b in zip(data.splitlines(), result.splitlines()) if a != b]
        need(name in names and len(result.splitlines()) == 683 and changed == actual and actual,
             'compiled control did not discriminate')
    for path in report['generated']:
        if path.endswith('.map'):
            need('StarDataStream.cpp.o)' not in Path(path).read_text(errors='replace'), 'original archive bypass')
    return {'records': 683, 'definitions': 51, 'bindings': len(before),
            'binaries': len(report['binaries']), 'commands': len(receipts)}


def verify(path):
    path = Path(path).resolve()
    return _verify(json.loads(path.read_text()), path.parent)


def self_test(path):
    """Corrupt metadata copies only; actual sources/binaries remain untouched."""
    path = Path(path).resolve()
    report = json.loads(path.read_text())
    _verify(report, path.parent)
    mutations = {
        'scope': lambda r: r.update(cases=682),
        'ordered': lambda r: r.update(ordered_sha256='0'*64),
        'binding': lambda r: r['bindings'].__setitem__(next(iter(r['bindings'])), '0'*64),
        'generated': lambda r: r['generated'].__setitem__(next(iter(r['generated'])), '0'*64),
        'binary': lambda r: r['binaries'].__setitem__(next(iter(r['binaries'])), '0'*64),
        'receipt': lambda r: r['receipts'][0].update(executable_sha256='0'*64),
        'control': lambda r: r['normal_semantic_controls'].pop('skip-zero')}
    for name, mutate in mutations.items():
        copy = deepcopy(report)
        mutate(copy)
        try:
            _verify(copy, path.parent)
        except ValueError:
            continue
        raise ValueError('synthetic corruption escaped: '+name)
    return list(mutations)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    result = verify(args.report)
    if args.self_test:
        result['syntheticIntegrityControls'] = self_test(args.report)
    print(json.dumps(result, sort_keys=True))
