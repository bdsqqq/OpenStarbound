#!/usr/bin/env python3
"""Rehash production OptionParser evidence and recheck counter negative controls."""
import argparse
import hashlib
import json
from pathlib import Path
from verify_receipts import verify as verify_native


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(path):
    # Import is deferred to avoid a runner/verifier initialization cycle.
    from candidate_run import validate_counts
    path = Path(path).resolve()
    output = path.parent
    report = json.loads(path.read_text())
    require(report['status'] == 'FINITE_PRODUCTION_RUST_OPTION_PARSER_PASS', 'status')
    require(report['cases'] == 295, 'case count')
    require(set(report['controls']) == {'native-bypass', 'suppressed-receipt', 'pending-route', 'selected-dispatch'}, 'controls')
    verify_native(report['native_report'])
    native = json.loads(Path(report['native_report']).read_text())
    require(report['ordered_sha256'] == native['ordered_sha256'] ==
            '056b5d907385bcb6266b86623b249c1deaa862263fd2ff4bf8232864ff290e4b', 'native digest disagreement')
    before = json.loads((output / 'before.json').read_text())
    after = json.loads((output / 'after.json').read_text())
    require(before == after == report['bindings'], 'binding disagreement')
    for group in ('bindings', 'generated', 'binaries', 'counts'):
        for name, expected in report[group].items():
            require(sha(name) == expected, group + ' drift: ' + name)
    receipts = json.loads((output / 'receipts.json').read_text())
    require(receipts == report['receipts'], 'receipt disagreement')
    executed, names = set(), set()
    for receipt in receipts:
        name = receipt['name']
        require(name not in names, 'duplicate receipt')
        names.add(name)
        require(receipt['returncode'] == 0, 'failed execution credited')
        exe = Path(receipt['command'][0]).resolve()
        require(sha(exe) == receipt['executable_sha256'], 'executable drift')
        executed.add(str(exe))
        for stream in ('stdout', 'stderr'):
            require(sha(output / (name + '.' + stream)) == receipt[stream + '_sha256'], 'output drift')
    require(set(report['binaries']) <= executed, 'unexecuted binary credited')
    for name in ('rust-values', 'native-bypass', 'suppressed-receipt', 'pending-route'):
        require(name in names and name + '-compile' in names, 'missing execution: ' + name)
        require(sha(output / (name + '.stdout')) == report['ordered_sha256'], 'whole stream drift')
        require(str(output / (name + '.counts')) in report['counts'], 'unbound counts')
    require({'rust-host', 'rust-host-compile', 'strict-c11'} <= names, 'host/header execution missing')
    validate_counts((output / 'rust-values.counts').read_bytes())
    validate_counts((output / 'native-bypass.counts').read_bytes(), 'cpp')
    require({'selected-dispatch', 'selected-dispatch-compile'} <= names, 'dispatch execution missing')
    require(sha(output / 'selected-dispatch.stdout') != report['ordered_sha256'], 'dispatch mutant escaped')
    require(str(output / 'selected-dispatch.counts') in report['counts'], 'unbound dispatch counts')
    for name in ('native-bypass', 'suppressed-receipt', 'pending-route'):
        try:
            validate_counts((output / (name + '.counts')).read_bytes())
        except ValueError:
            pass
        else:
            raise ValueError('counter control escaped: ' + name)
    return dict(status=report['status'], cases=295, bindings=len(before),
                binaries=len(report['binaries']), receipts=len(receipts), controls=report['controls'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.report), sort_keys=True))


if __name__ == '__main__':
    main()
