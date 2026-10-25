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
        require(sha(executable) == receipt['executable_sha256'], 'executed binary drift')
        executed.add(str(executable))
        for stream in ('stdout', 'stderr'):
            require(sha(folder / (name + '.' + stream)) == receipt[stream + '_sha256'], stream + ' drift')
    require({str(Path(p).resolve()) for p in report['binaries']} <= executed,
            'unexecuted binary credited')
    original = (folder / 'original.stdout').read_bytes()
    require(hashlib.sha256(original).hexdigest() == report['ordered_sha256'], 'ordered stream drift')
    records = {}
    for line in original.decode('ascii').splitlines():
        identity, *fields = line.split('|')
        require(identity and identity not in records, 'duplicate record')
        parsed = [value.split('=', 1) for value in fields]
        require(all(len(value) == 2 for value in parsed)
                and len({value[0] for value in parsed}) == len(parsed), 'invalid/duplicate fields')
        records[identity] = parsed
    require(len(records) == report['cases'], 'record count drift')
    for name in ('repeat', 'reference', 'current'):
        require((folder / (name + '.stdout')).read_bytes() == original, 'ordered stream mismatch')
    if synthetic:
        return {'synthetic': True}
    # Independent literal checks use Python integer packing, not native helpers.
    values = {key: dict(fields) for key, fields in records.items()}
    require(values['default']['version'] == '21', 'default literal')
    for key, fields in values.items():
        if key.startswith('write/'):
            _, name, bits, order = key.split('/')
            size = {'char': 1, 'i8': 1, 'u8': 1, 'i16': 2, 'u16': 2,
                    'i32': 4, 'u32': 4, 'i64': 8, 'u64': 8, 'f32': 4, 'f64': 8}[name]
            expected = int(bits).to_bytes(size, 'little' if int(order) in (1, 2) or size == 1 else 'big')
            require(fields['bytes'] == expected.hex(), 'primitive literal')
        if key.startswith('vlqu/write/'):
            value = int(key.rsplit('/', 1)[1])
            encoded = bytes.fromhex(fields['bytes'])
            decoded = 0
            for index, byte in enumerate(encoded):
                require(bool(byte & 128) == (index < len(encoded)-1), 'VLQ continuation literal')
                decoded = decoded * 128 + (byte & 127)
            require(decoded == value, 'VLQ numeric literal')
    require(values['array/late-payload']['bytes'] == '01657870616e646564', 'fresh array literal')
    require(values['isolated/fault/1/0']['value'] == '', 'terminated clear timing')
    require(values['isolated/fault/0/2']['value'] == '6f6c64', 'String assignment timing')
    require(values['isolated/write-before-hook']['bytes'] == '12345678', 'write conversion timing')
    require(values['devices/functions-ignore-count']['value'] == '1:1:51', 'function count behavior')
    require(values['devices/readFull-once']['value'] == '785151:1', 'single-read behavior')
    # A negative counts only after a normal execution and a different stream.
    for name in ('wrong-endian', 'pre-read-order', 'transactional-read', 'skip-empty',
                 'prefetch-array', 'late-clear', 'early-string', 'branch-reread',
                 'vlq-partial', 'reference-class-only'):
        require(name in names and (folder / (name+'.stdout')).read_bytes() != original,
                'unobserved compiled negative ' + name)
    require((folder/'paired-a.stdout').read_bytes() == (folder/'paired-b.stdout').read_bytes()
            != original, 'paired wrong control')
    return {'bindings': len(before), 'binaries': len(report['binaries']),
            'receipts': len(receipts), 'records': len(records)}


def self_test(output):
    output = Path(output).absolute()
    base = Path(__file__).resolve().parents[3] / 'build/data-stream-lab'
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
            (folder / (name + '.stdout')).write_bytes(b'fixture|value=1\n')
        (folder / 'original.stderr').write_bytes(b'')
        receipt = {'name': 'original', 'command': [str(files['binaries'])], 'returncode': 0,
                   'executable_sha256': sha(files['binaries']),
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
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
