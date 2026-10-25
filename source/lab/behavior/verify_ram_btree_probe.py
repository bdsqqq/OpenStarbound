"""Independent artifact verification; in-memory corruptions are synthetic."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import btree_padding
import build_provenance


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(report, folder):
    assert report['status'] == 'PASS' and report['sequences'] == 12
    assert report['cases'] == 3 and report['runs'] == 4 and report['guard_assertions_per_run'] == 7
    assert report['normal_poison_zero_padding_rejected'] and report['logical_crossfill_equal'] and report['physical_repeat_equal']
    assert report['bindings'] == json.loads((folder/'before.json').read_text()) == json.loads((folder/'after.json').read_text())
    for group in ('bindings', 'artifacts', 'source_sha256'):
        for path, digest in report[group].items():
            assert sha(path) == digest, (group, path)
    assert sha(report['native_binary']) == report['native_binary_sha256']
    build_provenance.verify(Path(report['native_binary']))
    commands = json.loads((folder/'commands.json').read_text())
    assert commands == report['commands'] and len(commands) == 7
    for command in commands:
        assert command['returncode'] == 0 and sha(command['executable']) == command['executable_sha256']
        for stream in ('stdout', 'stderr'):
            assert sha(folder/(command['name']+'.'+stream)) == command[stream+'_sha256']
    zero = json.loads((folder/'zero.stdout').read_text())
    poison = json.loads((folder/'poison.stdout').read_text())
    assert zero == json.loads((folder/'zero-repeat.stdout').read_text())
    assert poison == json.loads((folder/'poison-repeat.stdout').read_text())
    assert zero['guards'] == poison['guards'] == 7
    for kind in ('sha', 'vlq', 'bytes'):
        expected = ['616c706861006f6e65', '626574610074776f', '626574610074776f'] if kind == 'sha' else [bytes((i+s)&255 for i in range(n)).hex() for s,n in enumerate((127,128,700))]
        assert zero[kind]['found'] == poison[kind]['found'] == expected
        good, bad = (bytes.fromhex(row[kind]['pagesHex']) for row in (zero, poison))
        for data in (good, bad):
            assert 1024 <= len(data) <= 8192 and len(data) % 512 == 0
            assert data[:12] == b'BTreeDB5\x00\x00\x02\x00' and data[28:32] == b'\x00\x00\x00\x20'
        btree_padding.validate_pages(good)
        try:
            btree_padding.validate_pages(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('normally exiting poison accepted')
        assert len(good) == len(bad)
        assert [i for i, (a, b) in enumerate(zip(good, bad)) if a != b] == list(range(67, 512))
        assert report['differing_ranges'][kind] == [[67, 512]]
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    report = json.loads(args.report.read_text()); folder = args.report.parent
    verify(report, folder)
    if args.self_test:
        mutations = [lambda r: r.update(sequences=11),
                     lambda r: r['artifacts'].__setitem__(next(iter(r['artifacts'])), '0'*64),
                     lambda r: r['bindings'].__setitem__(next(iter(r['bindings'])), '0'*64),
                     lambda r: r['commands'][0].update(returncode=1),
                     lambda r: r['differing_ranges'].__setitem__('sha', [])]
        for mutate in mutations:
            bad = deepcopy(report); mutate(bad)
            try:
                verify(bad, folder)
            except AssertionError:
                pass
            else:
                raise AssertionError('synthetic corruption escaped')
    print(json.dumps({'status':'PASS', 'nativeSequences':12, 'syntheticControls':5 if args.self_test else 0}))


if __name__ == '__main__':
    main()
