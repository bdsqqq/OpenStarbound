#!/usr/bin/env python3
"""Independent integrity and backend qualification for actual Rust replay."""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def counters(data):
    result = {}
    for line in data.decode('ascii').splitlines():
        if not line.startswith('COUNTER '):
            continue
        _, mode, attempt, success, pending = line.split()
        mode = int(mode)
        require(mode not in result, 'duplicate counter mode')
        result[mode] = tuple(map(int, (attempt, success, pending)))
    require(set(result) == set(range(27)), 'missing counter mode')
    return result


def qualify(data):
    values = counters(data)
    routes = {}
    for line in data.decode('ascii').splitlines():
        if line.startswith('ROUTE '):
            _, mode, *events = line.split()
            require(int(mode) not in routes and len(events) == 4, 'route shape')
            routes[int(mode)] = tuple(map(int, events))
    require(set(routes) == set(range(27)), 'missing actual dispatch routes')
    for mode, (attempt, success, pending) in values.items():
        require(attempt > 0 and success > 0, 'unexecuted Rust mode ' + str(mode))
        require(attempt == success + pending, 'unbalanced Rust mode ' + str(mode))
        require(routes[mode] == (attempt, success, pending, 0), 'dispatch return status mismatch ' + str(mode))
    require(values[11][2] > 0 and values[3][2] > 0, 'missing native pending path')
    return values


def verify(path):
    path = Path(path).resolve()
    folder = path.parent
    report = json.loads(path.read_text())
    require(report['status'] == 'FINITE_ACTUAL_RUST_HOST_ADDRESS_PASS', 'status')
    before = json.loads((folder / 'before.json').read_text())
    after = json.loads((folder / 'after.json').read_text())
    require(before == after == report['bindings'], 'binding maps disagree')
    for group in ('bindings', 'generated', 'binaries'):
        for name, expected in report[group].items():
            require(sha(name) == expected, group + ' drift ' + name)
    require(sha(report['rust_archive']) == report['rust_archive_sha256'], 'archive drift')
    receipts = json.loads((folder / 'receipts.json').read_text())
    require(receipts == report['receipts'], 'receipt copies disagree')
    names, executed = set(), set()
    for receipt in receipts:
        name = receipt['name']
        require(name not in names, 'duplicate command')
        names.add(name)
        require(receipt['returncode'] == 0, 'failed execution credited')
        executable = Path(receipt['command'][0]).resolve()
        require(sha(executable) == receipt['executable_sha256'], 'executed binary drift')
        executed.add(str(executable))
        for stream in ('stdout', 'stderr'):
            require(sha(folder / (name + '.' + stream)) == receipt[stream + '_sha256'], stream + ' drift')
    require({str(Path(p).resolve()) for p in report['binaries']} <= executed, 'unexecuted binary')
    baseline = (folder / 'original.stdout').read_bytes()
    require(sha(folder / 'original.stdout') == report['ordered_sha256'], 'ordered stream drift')
    require(report['ordered_sha256'] == 'e9a14b9a678ad9819b4f17043ef08ccc901270dd1510d9bfcd516083454aa9b1', 'frozen stream identity')
    require(report['cases'] == len(baseline.splitlines()) == 430, 'record count')
    for name in ('reference', 'candidate', 'repeat', *report['controls']):
        require((folder / (name + '.stdout')).read_bytes() == baseline, name + ' whole stream mismatch')
    observations = qualify((folder / 'candidate.stderr').read_bytes())
    require(qualify((folder / 'repeat.stderr').read_bytes()) == observations, 'counter repeat mismatch')
    require(set(report['controls']) == {'native-bypass', 'suppressed-receipt', 'pending-route'}, 'controls missing')
    native_lines = [line for line in (folder / 'native-bypass.stderr').read_text().splitlines() if line.startswith('NATIVE ')]
    require(len(native_lines) == 1 and int(native_lines[0].split()[1]) > 0, 'native bypass observer absent')
    for name in report['controls']:
        try:
            qualify((folder / (name + '.stderr')).read_bytes())
        except ValueError:
            pass
        else:
            raise ValueError('backend control escaped: ' + name)
    require(b'PASS' in (folder / 'protocol.stdout').read_bytes(), 'protocol result absent')
    return dict(status=report['status'], records=430, bindings=len(before),
                binaries=len(report['binaries']), commands=len(receipts),
                controls=report['controls'], counters=observations)


def self_test(path, output):
    """Corrupt isolated copies of a real report, never the real evidence."""
    path, output = Path(path).resolve(), Path(output).absolute()
    base = Path(__file__).resolve().parents[3] / 'build/host-address-lab'
    require(not output.exists() and output != base and output.is_relative_to(base)
            and not any(p.is_symlink() for p in [output, *output.parents]), 'fresh owned fixtures required')
    verify(path)
    output.mkdir(parents=True)
    original = json.loads(path.read_text())
    detected = []
    for target in ('after-map', 'archive', 'binding', 'binary', 'execution', 'stdout', 'counter'):
        folder = output / target
        folder.mkdir()
        report = copy.deepcopy(original)
        # Streams and metadata are isolated; source/binary bindings remain read-only.
        for file in path.parent.iterdir():
            if file.suffix in ('.stdout', '.stderr', '.json'):
                (folder / file.name).write_bytes(file.read_bytes())
        if target == 'after-map':
            (folder / 'after.json').write_text('{}')
        elif target == 'archive':
            report['rust_archive_sha256'] = '0' * 64
        elif target in ('binding', 'binary'):
            group = 'bindings' if target == 'binding' else 'binaries'
            report[group][next(iter(report[group]))] = '0' * 64
        elif target == 'execution':
            report['receipts'][0]['executable_sha256'] = '0' * 64
            (folder / 'receipts.json').write_text(json.dumps(report['receipts']))
        else:
            stream = folder / ('candidate.stderr' if target == 'counter' else 'candidate.stdout')
            stream.write_bytes(b'CORRUPTION\n')
            if target == 'counter':
                # Preserve the stream's receipt so this probes semantic counter
                # validation independently of the artifact hash check.
                receipt = next(r for r in report['receipts'] if r['name'] == 'candidate')
                receipt['stderr_sha256'] = sha(stream)
                (folder / 'receipts.json').write_text(json.dumps(report['receipts']))
        (folder / 'report.json').write_text(json.dumps(report))
        try:
            verify(folder / 'report.json')
        except ValueError:
            detected.append(target)
        else:
            raise ValueError('known corruption escaped: ' + target)
    (output / 'result.json').write_text(json.dumps(detected, indent=2))
    return detected


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--self-test-output', type=Path)
    args = parser.parse_args()
    result = verify(args.report)
    if args.self_test_output:
        result['integrityCorruptionsDetected'] = self_test(args.report, args.self_test_output)
    print(json.dumps(result, sort_keys=True))
