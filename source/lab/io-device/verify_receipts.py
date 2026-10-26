#!/usr/bin/env python3
"""Independent artifact/command integrity checks; synthetic receipts are not execution."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def scope(report):
    require(report['definitions']==22 and report['cases']==998, 'compiled/corpus scope')
    require(report['ordered_sha256']=='3bb08408a1f6d8f5ce4733730f31fa7b1e90eb02043322df6ff628bf1da1ab9f', 'sealed independent corpus')

def verify(path, *, synthetic=False):
    path = Path(path).resolve()
    report = json.loads(path.read_text())
    folder = path.parent
    require(report['status'] == 'FINITE_NATIVE_CALIBRATION_PASS', 'status')
    before = json.loads((folder / 'before.json').read_text())
    after = json.loads((folder / 'after.json').read_text())
    require(before == after == report['bindings'], 'binding maps disagree')
    for group in ('bindings', 'generated', 'binaries'):
        for name, expected in report[group].items():
            require(sha(name) == expected, group + ' drift: ' + name)
    require(sha(report['link']['archive']) == report['archive_sha256'], 'archive drift')
    receipts = json.loads((folder / 'receipts.json').read_text())
    require(receipts == report['receipts'], 'receipt copies disagree')
    names, executed = set(), set()
    for receipt in receipts:
        name = receipt['name']
        require(name not in names, 'duplicate command receipt')
        names.add(name)
        require(receipt['returncode'] == 0, 'failed execution credited')
        executable = Path(receipt['command'][0]).resolve()
        require(sha(executable) == receipt['executable_sha256'] == receipt['executable_sha256_before'], 'executed binary drift')
        executed.add(str(executable))
        for stream in ('stdout', 'stderr'):
            require(sha(folder / (name + '.' + stream)) == receipt[stream + '_sha256'], stream + ' drift')
    require({str(Path(p).resolve()) for p in report['binaries']} <= executed,
            'unexecuted binary credited')
    original = (folder / 'original.stdout').read_bytes()
    require(hashlib.sha256(original).hexdigest() == report['ordered_sha256'], 'ordered stream drift')
    records = {}
    for line in original.decode('ascii').splitlines():
        record=json.loads(line)
        require(set(record)=={'key','value'} and record['key'] not in records,'record schema')
        records[record['key']]=record['value']
    require(len(records)==report['cases'],'record count drift')
    for name in ('repeat','reference','current'):
        require((folder/(name+'.stdout')).read_bytes()==original,'ordered stream mismatch')
    if synthetic:
        return {'synthetic': True}
    scope(report)
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'behavior'))
    import build_provenance
    require(build_provenance.verify(Path(report['native_binary']))==report['native_closure'],'native closure drift')
    from model import check
    require(check(original)==report['cases'], 'independent literal model')
    for name in ('eof-class','size-no-restore','absolute-no-restore','absolute-offset','zero-absolute-step','eager-name','reference-class-only'):
        require(name in names and (folder/(name+'.stdout')).read_bytes()!=original, 'semantic negative '+name)
    require((folder/'paired-a.stdout').read_bytes()==(folder/'paired-b.stdout').read_bytes()!=original, 'paired wrong')
    try:check((folder/'paired-a.stdout').read_bytes())
    except ValueError:pass
    else:raise ValueError('paired wrong literal escaped')
    return {'bindings':len(before),'binaries':len(report['binaries']),'receipts':len(receipts),'records':len(records)}


def self_test(output):
    output = Path(output).absolute()
    base = Path(__file__).resolve().parents[3] / 'build/io-device-lab'
    require(not output.exists() and output != base and output.is_relative_to(base)
            and not any(p.is_symlink() for p in [output, *output.parents]), 'fresh owned fixture required')
    output.mkdir(parents=True)
    detected = []
    for target in ('bindings', 'generated', 'binaries', 'archive', 'stdout', 'stderr',
                   'executable-receipt', 'after-map'):
        folder = output / target
        folder.mkdir()
        files = {name: folder / name for name in ('bindings', 'generated', 'binaries', 'archive')}
        for file in files.values():
            file.write_bytes(b'synthetic integrity fixture, NOT an executable\n')
        for name in ('original', 'repeat', 'reference', 'current'):
            (folder / (name + '.stdout')).write_bytes(b'{"key":"fixture","value":"1"}\n')
        (folder / 'original.stderr').write_bytes(b'')
        receipt = {'name': 'original', 'command': [str(files['binaries'])], 'returncode': 0,
                   'executable_sha256': sha(files['binaries']), 'executable_sha256_before':sha(files['binaries']),
                   'stdout_sha256': sha(folder / 'original.stdout'),
                   'stderr_sha256': sha(folder / 'original.stderr')}
        bindings = {str(files['bindings']): sha(files['bindings'])}
        report = {'status': 'FINITE_NATIVE_CALIBRATION_PASS', 'cases': 1,
                  'bindings': bindings, 'generated': {str(files['generated']): sha(files['generated'])},
                  'binaries': {str(files['binaries']): sha(files['binaries'])},
                  'link': {'archive': str(files['archive'])}, 'archive_sha256': sha(files['archive']),
                  'receipts': [receipt], 'ordered_sha256': sha(folder / 'original.stdout')}
        for name, value in [('before', bindings), ('after', bindings), ('receipts', [receipt]), ('report', report)]:
            (folder / (name + '.json')).write_text(json.dumps(value))
        verify(folder / 'report.json', synthetic=True)
        if target == 'after-map':
            (folder / 'after.json').write_text('{}')
        elif target == 'executable-receipt':
            receipt['executable_sha256'] = '0' * 64
            (folder / 'report.json').write_text(json.dumps(report))
            (folder / 'receipts.json').write_text(json.dumps([receipt]))
        else:
            file = files.get(target, folder / ('original.' + target))
            file.write_bytes(file.read_bytes() + b'CORRUPTION')
        try:
            verify(folder / 'report.json', synthetic=True)
        except ValueError:
            detected.append(target)
        else:
            raise ValueError('known corruption escaped: ' + target)
    (output / 'result.json').write_text(json.dumps({'syntheticIntegrityControls': detected}, indent=2))
    return detected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--self-test-output', type=Path)
    args = parser.parse_args()
    result = verify(args.report)
    if args.self_test_output:
        result['syntheticIntegrityControls'] = self_test(args.self_test_output)
        # Scope checks use the actual report shape, separately from the tiny
        # synthetic artifact fixtures above. Neither mutation is execution.
        actual = json.loads(args.report.read_text())
        for field, wrong in (('definitions', 49), ('cases', 582), ('ordered_sha256', '0' * 64)):
            bad = dict(actual); bad[field] = wrong
            try:
                scope(bad)
            except ValueError:
                pass
            else:
                raise ValueError('scope corruption escaped: ' + field)
        result['syntheticScopeControls'] = 3
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
