#!/usr/bin/env python3
"""Verify finite native blueprint artifacts; metadata corruptions are synthetic."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from run import anchors
from verify_receipts import verify as verify_native

EXPECTED = '08a3143c0f6ad6dd6dbf29a5457e197fcfa05ec85a4cf4f04cde60af0edb7b38'
CONTROLS = {'end-sign', 'mode-before-zero', 'open-order'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _verify(report, folder):
    need(report['status'] == 'FINITE_NATIVE_BUFFER_HOST_SELECTED_PROTOCOL_PASS', 'status')
    need(report['cases'] == 583 and report['definitions'] == 50, 'finite compiled/corpus scope')
    verify_native(report['native_report'])
    before = json.loads((folder/'before.json').read_text())
    after = json.loads((folder/'after.json').read_text())
    need(before == after == report['bindings'], 'input maps disagree')
    for group in ('bindings', 'generated', 'binaries'):
        need(bool(report[group]), 'empty '+group)
        for path, digest in report[group].items():
            need(sha(path) == digest, group+' drift')
    receipts = json.loads((folder/'receipts.json').read_text())
    need(receipts == report['receipts'], 'receipt copies disagree')
    names, executed = set(), set()
    for receipt in receipts:
        name = receipt['name']
        need(name not in names and receipt['returncode'] == 0, 'failed/duplicate command')
        names.add(name); executable = str(Path(receipt['command'][0]).resolve())
        need(sha(executable) == receipt['executable_sha256'], 'executed binary drift')
        executed.add(executable)
        for stream in ('stdout', 'stderr'):
            need(sha(folder/(name+'.'+stream)) == receipt[stream+'_sha256'], 'stdio drift')
    need(set(report['binaries']) <= executed, 'unexecuted binary')
    data = (folder/'prototype.stdout').read_bytes()
    need(hashlib.sha256(data).hexdigest() == report['ordered_sha256'] == EXPECTED, 'ordered digest')
    need(anchors(data) == 583 and (folder/'repeat.stdout').read_bytes() == data, 'repeat/independent literals')
    need(len(json.loads((folder/'compiled-definitions.json').read_text())) == 50, 'actual compiled symbols')
    need((folder/'protocol.stdout').read_bytes() == data
         and b'buffer native protocol assertions passed' in (folder/'protocol.stderr').read_bytes(),
         'assertion-active native protocol/corpus observation')
    need(set(report['normal_semantic_controls']) == CONTROLS, 'normal control scope')
    original_rows = [json.loads(line) for line in data.splitlines()]
    for name in CONTROLS:
        rows = [json.loads(line) for line in (folder/(name+'.stdout')).read_bytes().splitlines()]
        need(name in names and len(rows) == 583, 'control execution/corpus')
        need([r['key'] for r in rows] == [r['key'] for r in original_rows], 'control key alignment')
        changes = [a['key'] for a,b in zip(original_rows, rows) if a != b]
        need(bool(changes) and changes == report['normal_semantic_controls'][name], 'compiled control did not discriminate')
    for path in report['generated']:
        if path.endswith('.map'):
            need(b'native-core.a(StarBuffer.cpp.o)' not in Path(path).read_bytes(), 'original Buffer archive bypass')
    return {'records':583, 'definitions':50, 'bindings':len(before),
            'binaries':len(report['binaries']), 'commands':len(receipts)}


def verify(path):
    path = Path(path).resolve()
    return _verify(json.loads(path.read_text()), path.parent)


def self_test(path):
    path = Path(path).resolve(); report = json.loads(path.read_text())
    _verify(report, path.parent)
    mutations = {
        'definition-scope': lambda r:r.update(definitions=49),
        'record-scope': lambda r:r.update(cases=582),
        'ordered': lambda r:r.update(ordered_sha256='0'*64),
        'binding': lambda r:r['bindings'].__setitem__(next(iter(r['bindings'])), '0'*64),
        'generated': lambda r:r['generated'].__setitem__(next(iter(r['generated'])), '0'*64),
        'binary': lambda r:r['binaries'].__setitem__(next(iter(r['binaries'])), '0'*64),
        'receipt': lambda r:r['receipts'][0].update(executable_sha256='0'*64),
        'control': lambda r:r['normal_semantic_controls'].pop('end-sign')}
    for name, mutate in mutations.items():
        bad = deepcopy(report); mutate(bad)
        try:
            _verify(bad, path.parent)
        except ValueError:
            continue
        raise ValueError('synthetic corruption escaped '+name)
    return list(mutations)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args(); result = verify(args.report)
    if args.self_test:
        result['syntheticIntegrityControls'] = self_test(args.report)
    print(json.dumps(result, sort_keys=True))
