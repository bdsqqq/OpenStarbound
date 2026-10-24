#!/usr/bin/env python3
"""Rehash retained OptionParser evidence without compiling or trusting its producers."""
import argparse
import hashlib
import json
import shlex
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(path):
    path = Path(path)
    report = json.loads(path.read_text())
    require(report['status'] == 'FINITE_NATIVE_CALIBRATION_PASS', 'report status')
    before = json.loads((path.parent / 'before.json').read_text())
    after = json.loads((path.parent / 'after.json').read_text())
    require(before == after == report['bindings'], 'binding map disagreement')
    for group in ('bindings', 'generated', 'binaries'):
        for name, expected in report[group].items():
            require(sha(name) == expected, group + ' drift: ' + name)
    require(sha(report['link']['archive']) == report['archive_sha256'], 'archive drift')
    receipts = json.loads((path.parent / 'receipts.json').read_text())
    require(receipts == report['receipts'], 'receipt copy disagreement')
    require([shlex.join(r['command']) for r in receipts] == report['commands'], 'command disagreement')
    names = set()
    executed = set()
    for receipt in receipts:
        name = receipt['name']
        require(name not in names, 'duplicate receipt')
        names.add(name)
        require(receipt['returncode'] == 0, 'failed command credited')
        executable = Path(receipt['command'][0]).resolve()
        require(sha(executable) == receipt['executable_sha256'], 'executed binary drift')
        executed.add(str(executable))
        for stream in ('stdout', 'stderr'):
            require(sha(path.parent / (name + '.' + stream)) == receipt[stream + '_sha256'], stream + ' drift')
    require(set(map(lambda p: str(Path(p).resolve()), report['binaries'])) <= executed,
            'unexecuted binary credited')
    baseline = (path.parent / 'original.stdout').read_bytes()
    require(hashlib.sha256(baseline).hexdigest() == report['ordered_sha256'], 'ordered stream drift')
    ids = set()
    for row in baseline.decode('ascii').splitlines():
        identity, kind, value = row.split('\t')
        require(bool(identity and kind), 'empty record identity')
        bytes.fromhex(value)
        ids.add(identity)
    require(len(ids) == report['cases'], 'case count drift')
    return {'bindings': len(before), 'generated': len(report['generated']),
            'binaries': len(report['binaries']), 'receipts': len(receipts), 'cases': len(ids)}


def self_test(output):
    # These deliberately non-executable fixtures test integrity checks ONLY;
    # synthetic receipt metadata is not execution evidence.
    output = Path(output).absolute()
    root = Path(__file__).resolve().parents[3] / 'build/option-parser-lab'
    require(output.is_relative_to(root) and output != root and not output.exists()
            and not any(p.is_symlink() for p in [output, *output.parents]), 'fresh owned fixture output required')
    output.mkdir(parents=True)
    detected = []
    for target in ('bound', 'generated', 'binary', 'archive', 'stdout', 'stderr'):
        folder = output / target
        folder.mkdir()
        files = {key: folder / key for key in ('bound', 'generated', 'binary', 'archive')}
        for file in files.values():
            file.write_bytes(b'integrity fixture, not an executable\n')
        (folder / 'original.stdout').write_bytes(b'fixture\tdone\t\n')
        (folder / 'original.stderr').write_bytes(b'')
        receipt = {'name': 'original', 'command': [str(files['binary'])], 'returncode': 0,
                   'executable_sha256': sha(files['binary']),
                   'stdout_sha256': sha(folder / 'original.stdout'),
                   'stderr_sha256': sha(folder / 'original.stderr')}
        bindings = {str(files['bound']): sha(files['bound'])}
        report = {'status': 'FINITE_NATIVE_CALIBRATION_PASS', 'bindings': bindings,
                  'generated': {str(files['generated']): sha(files['generated'])},
                  'binaries': {str(files['binary']): sha(files['binary'])},
                  'link': {'archive': str(files['archive'])}, 'archive_sha256': sha(files['archive']),
                  'receipts': [receipt], 'commands': [shlex.join(receipt['command'])],
                  'ordered_sha256': sha(folder / 'original.stdout'), 'cases': 1}
        for name, value in [('report', report), ('before', bindings), ('after', bindings), ('receipts', [receipt])]:
            (folder / (name + '.json')).write_text(json.dumps(value))
        verify(folder / 'report.json')
        changed = files.get(target, folder / ('original.' + target))
        changed.write_bytes(changed.read_bytes() + b'CORRUPTION')
        try:
            verify(folder / 'report.json')
        except ValueError:
            detected.append(target)
        else:
            raise ValueError('known corruption escaped: ' + target)
    (output / 'result.json').write_text(json.dumps({'synthetic_integrity_controls': detected}, indent=2))
    return detected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--self-test-output', type=Path)
    args = parser.parse_args()
    result = verify(args.report)
    if args.self_test_output:
        result['synthetic_integrity_controls'] = self_test(args.self_test_output)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
