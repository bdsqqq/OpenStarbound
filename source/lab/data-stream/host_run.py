#!/usr/bin/env python3
"""Replay the actual C++ ownership blueprint, not a Rust/game qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
from verify_receipts import verify

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
EXPECTED = '5ee512e3a91027823f34c47df4d1e056753e0fd61f03a9ad70e65131900763ab'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--values', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    verify(args.values / 'report.json')
    native = json.loads((args.values / 'report.json').read_text())
    link = native['link']
    out = args.output.absolute()
    base = ROOT / 'build/data-stream-lab'
    if (out == base or not out.is_relative_to(base) or out.exists()
            or any(p.is_symlink() for p in [out, *out.parents])):
        ap.error('fresh owned nonsymlink output required')
    assert shutil.disk_usage(ROOT).free > 1024**3
    out.mkdir(parents=True)
    sources = [HERE / ('host_contract' + suffix) for suffix in ('.hpp', '.cpp', '_test.cpp')]
    tracked = dict(native['bindings'])
    for p in [*sources, Path(__file__).resolve(), HERE / 'verify_host.py', Path(link['archive'])]:
        tracked[str(p.resolve())] = sha(p)
    receipts, generated, binaries = [], {}, {}

    def run(command, name):
        command = list(map(str, command))
        executable = Path(command[0]).resolve()
        before = sha(executable)
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=75)
        assert before == sha(executable), 'executed binary changed'
        for stream in ('stdout', 'stderr'):
            (out / (name + '.' + stream)).write_bytes(getattr(result, stream))
        receipts.append({'name': name, 'command': command, 'returncode': result.returncode,
                         'executable_sha256': before,
                         'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(),
                         'stderr_sha256': hashlib.sha256(result.stderr).hexdigest()})
        (out / 'receipts.json').write_text(json.dumps(receipts, indent=2)+'\n')
        assert result.returncode == 0, name + ' failed, not a normal semantic control'
        return result.stdout

    flags = link['flags'] + ['-UNDEBUG', '-I'+str(HERE)]
    for index, source in enumerate((sources[1], sources[2])):
        dep = out / f'host{index}.d'
        run([link['compiler'], *flags, '-M', '-MF', dep, source], f'deps-{index}')
        paths = shlex.split(dep.read_text().replace('\\\n', ' ').split(':', 1)[1])
        for name in paths:
            p = Path(name)
            p = p if p.is_absolute() else ROOT / p
            tracked[str(p.resolve())] = sha(p)
    (out / 'before.json').write_text(json.dumps(tracked, indent=2)+'\n')
    run([link['compiler'], *flags, '-x', 'c', '-std=c11', '-pedantic-errors',
         '-fsyntax-only', sources[0]], 'c11')

    def compile(source, name, test=False):
        binary = out / name
        command = [link['compiler'], *flags]
        if not test:
            command.append(HERE / 'lab.cpp')
        command += [source, link['archive'], *link['libraries'], '-Xlinker', '-map',
                    '-Xlinker', out / (name+'.map'), '-o', binary]
        run(command, name+'-compile')
        binaries[str(binary)] = sha(binary)
        # The blueprint supplies all actual DataStream symbols; pulling the
        # original member would let a missing implementation hide in the archive.
        text = (out / (name+'.map')).read_text(errors='replace')
        assert 'StarDataStream.cpp.o)' not in text, 'original DataStream archive member pulled'
        return binary

    exe = compile(sources[1], 'prototype')
    original = (args.values / 'original.stdout').read_bytes()
    data = run([exe], 'prototype')
    assert data == original and hashlib.sha256(data).hexdigest() == EXPECTED
    assert run([exe], 'repeat') == data
    test = compile(sources[2], 'protocol', test=True)
    run([test], 'protocol')
    source = sources[1].read_text()
    early = source.replace('else if(m>=DS_READ_BOOL&&m<=DS_READ_F64){\n   call(DS_SCALAR_IO);',
        'else if(m>=DS_READ_BOOL&&m<=DS_READ_F64){\n   auto earlyOrder=m>=DS_READ_I16?call(DS_CONFIG_GET,0):0;\n   call(DS_SCALAR_IO);')
    early = early.replace('else if(m>=DS_READ_I16){auto order=call(DS_CONFIG_GET,0);',
                          'else if(m>=DS_READ_I16){auto order=earlyOrder;')
    mutants = {
        'early-order': early,
        'skip-zero': source.replace('call(DS_RESIZE,0,call(DS_ARGUMENT));call(DS_CAPTURE);call(DS_VIEW_IO);',
                                    'call(DS_RESIZE,0,call(DS_ARGUMENT));if(call(DS_CAPTURE))call(DS_VIEW_IO);'),
        'reread-string-branch': source.replace('if(!c)break;call(DS_APPEND,0,c);',
                                    'if(!c)break;if(!call(DS_CONFIG_GET,1))break;call(DS_APPEND,0,c);')}
    controls = {}
    for name, body in mutants.items():
        assert body != source, 'empty mutation'
        path = out / (name+'.cpp')
        path.write_text(body)
        generated[str(path)] = sha(path)
        result = run([compile(path, name)], name)
        assert len(result.splitlines()) == 683 and result != data, 'control escaped'
        controls[name] = [a.split(b'|')[0].decode() for a, b in zip(data.splitlines(), result.splitlines()) if a != b]
        assert controls[name]
    after = {p: sha(p) for p in tracked}
    assert after == tracked and all(sha(p) == h for p, h in {**binaries, **generated}.items())
    (out / 'after.json').write_text(json.dumps(after, indent=2)+'\n')
    for path in out.glob('*.map'):
        generated[str(path)] = sha(path)
    report = {'status': 'FINITE_NATIVE_HOST_SELECTED_PROTOCOL_PASS', 'cases': 683,
              'definitions': 51, 'ordered_sha256': EXPECTED, 'bindings': tracked,
              'generated': generated, 'binaries': binaries, 'receipts': receipts,
              'normal_semantic_controls': controls,
              'limits': ['C++ controller only, no Rust/game qualification',
                         'selected protocol guards, not exhaustive automaton',
                         'C++ foreign-callback catch is NOT a Rust unwind guarantee']}
    (out / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'status': report['status'], 'records': 683, 'bindings': len(tracked),
                      'binaries': len(binaries), 'commands': len(receipts), 'controls': list(controls)}))


if __name__ == '__main__':
    main()
