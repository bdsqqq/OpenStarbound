#!/usr/bin/env python3
"""Independently rehash production replay, fresh native seal, values and routes."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from candidate_run import CONTROLS, EXPECTED, freeze, observation, qualification, sha
from verify_receipts import verify as verify_native


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _verify(report, folder):
    need(report['status'] == 'FINITE_ACTUAL_RUST_BUFFER_PASS', 'status')
    need(report['cases'] == 583 and report['definitions'] == 50 and report['ordered_sha256'] == EXPECTED, 'scope')
    freeze(Path(report['parent_source_freeze']), Path(report['rust_archive']), report['rust_archive_sha256'])
    verify_native(report['native_report'])
    before = json.loads((folder/'before.json').read_text())
    need(before == json.loads((folder/'after.json').read_text()) == report['bindings'], 'source maps')
    for group in ('bindings', 'generated', 'binaries'):
        need(bool(report[group]), 'empty '+group)
        for name, digest in report[group].items():
            need(sha(name) == digest, group+' drift')
    need(json.loads((folder/'receipts.json').read_text()) == report['receipts'], 'receipt copies')
    names = set(); executed = set()
    for receipt in report['receipts']:
        name = receipt['name']; need(name not in names and receipt['returncode'] == 0, 'failed/duplicate command')
        names.add(name); exe = str(Path(receipt['command'][0]).resolve()); executed.add(exe)
        need(sha(exe) == receipt['executable_sha256_before'] == receipt['executable_sha256'], 'executed artifact')
        for stream in ('stdout', 'stderr'):
            need(sha(folder/(name+'.'+stream)) == receipt[stream+'_sha256'], 'stdio drift')
    need(set(report['binaries']) <= executed, 'unexecuted binary')
    data = (folder/'candidate.stdout').read_bytes()
    observed = observation((folder/'candidate.stderr').read_bytes())
    qualification(data, observed); need(observed == report['observation'], 'reported counts')
    need((folder/'repeat.stdout').read_bytes() == data and observation((folder/'repeat.stderr').read_bytes()) == observed, 'repeat')
    native = Path(report['native_report']).parent
    need(data == (native/'original.stdout').read_bytes(), 'native source corpus')
    definitions = json.loads((folder/'compiled-definitions.json').read_text())
    need(len(definitions) == 50 and definitions == json.loads((native/'compiled-definitions.json').read_text()), 'compiled definitions')
    need((folder/'protocol.stdout').read_bytes() == data and b'buffer native protocol assertions passed' in (folder/'protocol.stderr').read_bytes(), 'native protocol')
    need(set(report['normal_controls']) == set(CONTROLS), 'normal control scope')
    for name in CONTROLS:
        wrong = (folder/(name+'.stdout')).read_bytes()
        need(name in names and wrong == data, 'control values/execution')
        try:
            qualification(wrong, observation((folder/(name+'.stderr')).read_bytes()))
        except ValueError as error:
            need(str(error) == report['normal_controls'][name], 'control reason')
        else:
            raise ValueError('control escaped '+name)
    for name in report['generated']:
        if name.endswith('.map'):
            need(b'native-core.a(StarBuffer.cpp.o)' not in Path(name).read_bytes(), 'native archive bypass')
    return {'cases':583, 'definitions':50, 'bindings':len(before), 'commands':len(names)}


def verify(path):
    path = Path(path).resolve()
    return _verify(json.loads(path.read_text()), path.parent)


def integrity_self_test(path):
    path = Path(path).resolve(); report = json.loads(path.read_text())
    _verify(report, path.parent)
    mutations = {
        'mode-scope':lambda r:r.update(definitions=49),
        'case-scope':lambda r:r.update(cases=582),
        'ordered-digest':lambda r:r.update(ordered_sha256='0'*64),
        'source-binding':lambda r:r['bindings'].__setitem__(next(iter(r['bindings'])), '0'*64),
        'generated':lambda r:r['generated'].__setitem__(next(iter(r['generated'])), '0'*64),
        'binary':lambda r:r['binaries'].__setitem__(next(iter(r['binaries'])), '0'*64),
        'archive':lambda r:r.update(rust_archive_sha256='0'*64),
        'receipt':lambda r:r['receipts'][0].update(executable_sha256='0'*64),
        'normal-control-scope':lambda r:r['normal_controls'].pop('native-bypass'),
        'reported-observation':lambda r:r['observation']['counts'].__setitem__(5,[0,0,0])}
    for name, mutate in mutations.items():
        bad = deepcopy(report); mutate(bad)
        try:
            _verify(bad, path.parent)
        except ValueError:
            continue
        raise ValueError('synthetic integrity corruption escaped '+name)
    return list(mutations)


def shape_self_test():
    # Pure isolated counter fixtures. These do NOT claim compiled execution.
    good = {'counts':[[2,1,1] for _ in range(50)], 'routes':[[1,1,0,0] for _ in range(50)],
            'nativeCaller':dict(mode=3, position=0, size=4, pointerStable=True)}
    for mode in (37, 39):
        good['counts'][mode] = [2,0,2]; good['routes'][mode] = [0,2,0,0]
    good['counts'][0] = [8,7,1]; good['routes'][0] = [7,1,0,0]
    good['counts'][16] = [6,5,1]; good['routes'][16] = [5,1,0,0]
    # Extract only shape/route checking without inventing a native value stream.
    import candidate_run
    old = candidate_run.anchors
    old_expected = candidate_run.EXPECTED
    data = b'synthetic-only'
    try:
        candidate_run.anchors = lambda _:583
        candidate_run.EXPECTED = hashlib.sha256(data).hexdigest()
        qualification(data, good)
        mutations = {
            'mode-scope':lambda r:r['counts'].pop(),
            'zero-mode':lambda r:r['counts'].__setitem__(5,[0,0,0]),
            'pending-route':lambda r:r['routes'].__setitem__(13,[1,0,1,0]),
            'unbalanced':lambda r:r['counts'].__setitem__(0,[3,1,1]),
            'negative':lambda r:r['counts'].__setitem__(0,[-1,1,1]),
            'boolean':lambda r:r['counts'].__setitem__(0,[True,1,0])}
        for name, mutate in mutations.items():
            bad = deepcopy(good); mutate(bad)
            try:
                qualification(data, bad)
            except ValueError:
                continue
            raise ValueError('synthetic shape corruption escaped '+name)
        return list(mutations)
    finally:
        candidate_run.anchors = old
        candidate_run.EXPECTED = old_expected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--shape-self-test', action='store_true')
    parser.add_argument('--self-test', action='store_true', help='requires an actual valid --report')
    args = parser.parse_args()
    result = verify(args.report) if args.report else {}
    if args.self_test:
        need(args.report is not None, '--self-test requires --report')
        result['syntheticIntegrityControls'] = integrity_self_test(args.report)
    if args.shape_self_test:
        result['synthetic_only'] = shape_self_test()
    need(bool(result), '--report or --shape-self-test required')
    print(json.dumps(result, sort_keys=True))
