#!/usr/bin/env python3
"""Replay actual native Buffer controller ownership; no Rust/game qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from verify_receipts import verify as verify_native
from run import anchors

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
EXPECTED = '08a3143c0f6ad6dd6dbf29a5457e197fcfa05ec85a4cf4f04cde60af0edb7b38'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mutants(source):
    substitutions = {
        'end-sign': ('else if(m==2)n=get(SB_OP_SIZE)-p;', 'else if(m==2)n=get(SB_OP_SIZE)+p;'),
        'mode-before-zero': ('auto len=c.arg(1);if(!len){c.ret(0);break;}\n        if(!(get(SB_OP_MODE)&1))c.raise(0);',
                             'auto len=c.arg(1);if(!(get(SB_OP_MODE)&1))c.raise(0);\n        if(!len){c.ret(0);break;}'),
        'open-order': ('if((m&2)&&(m&8))child(7,0);\n        if(m&4)child(8);break;',
                       'if(m&4)child(8);\n        if((m&2)&&(m&8))child(7,0);break;')}
    result = {}
    for name, (old, new) in substitutions.items():
        assert source.count(old) == 1, 'exact controller mutation contract '+name
        result[name] = source.replace(old, new)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--values', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    native_path = args.values / 'report.json'
    verify_native(native_path)
    native = json.loads(native_path.read_text())
    out = args.output.absolute(); base = ROOT / 'build/buffer-lab'
    if (out == base or not out.is_relative_to(base) or out.exists()
            or any(p.is_symlink() for p in [out, *out.parents])):
        parser.error('fresh owned nonsymlink output required')
    assert shutil.disk_usage(ROOT).free > 1024**3
    out.mkdir(parents=True)
    link = native['link']
    sources = [HERE / ('host_contract' + suffix) for suffix in ('.hpp', '.cpp', '_test.cpp')]
    tracked = dict(native['bindings'])
    for p in [*sources, Path(__file__).resolve(), HERE/'verify_host.py', native_path, Path(link['archive'])]:
        tracked[str(p.resolve())] = sha(p)
    receipts, generated, binaries = [], {}, {}

    def run(command, name):
        command = list(map(str, command)); executable = Path(command[0]).resolve()
        before = sha(executable)
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=75)
        assert before == sha(executable), 'executed artifact drift'
        for stream in ('stdout', 'stderr'):
            (out/(name+'.'+stream)).write_bytes(getattr(result, stream))
        receipts.append({'name': name, 'command': command, 'returncode': result.returncode,
                         'executable_sha256': before,
                         'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(),
                         'stderr_sha256': hashlib.sha256(result.stderr).hexdigest()})
        (out/'receipts.json').write_text(json.dumps(receipts, indent=2)+'\n')
        assert result.returncode == 0, name+' failed; no abnormal negative credit'
        return result.stdout

    flags = [*link['flags'], '-UNDEBUG', '-I'+str(HERE)]
    for index, source in enumerate((sources[1], sources[2])):
        dep = out/f'host{index}.d'
        run([link['compiler'], *flags, '-M', '-MF', dep, source], f'deps-{index}')
        for name in shlex.split(dep.read_text().replace('\\\n', ' ').split(':', 1)[1]):
            path = Path(name); path = path if path.is_absolute() else ROOT/path
            key = str(path.resolve()); digest = sha(path)
            assert key not in tracked or tracked[key] == digest, 'dependency drift'
            tracked[key] = digest
    (out/'before.json').write_text(json.dumps(tracked, indent=2)+'\n')
    run([link['compiler'], *flags, '-x', 'c', '-std=c11', '-pedantic-errors', '-fsyntax-only', sources[0]], 'c11')
    obj = out/'prototype.o'
    run([link['compiler'], *flags, '-c', sources[1], '-o', obj], 'prototype-object')
    generated[str(obj)] = sha(obj)
    symbols = run(['/usr/bin/nm', '-C', '--defined-only', obj], 'prototype-symbols')
    definitions = sorted(set(re.findall(r' T (Star::(?:ExternalBuffer|Buffer)::[^\n]+)', symbols.decode())))
    definitions = [name for name in definitions if '::~' not in name]
    expected_definitions = json.loads((args.values/'compiled-definitions.json').read_text())
    assert len(definitions) == 50 and definitions == expected_definitions, 'actual 50 member symbols'
    definition_path = out/'compiled-definitions.json'
    definition_path.write_text(json.dumps(definitions, indent=2)+'\n')
    generated[str(definition_path)] = sha(definition_path)

    def compile(source, name, test=False):
        binary = out/name
        command = [link['compiler'], *flags]
        if not test:
            command.append(HERE/'lab.cpp')
        command += [source, link['archive'], *link['libraries'], '-Xlinker', '-map',
                    '-Xlinker', out/(name+'.map'), '-o', binary]
        run(command, name+'-compile'); binaries[str(binary)] = sha(binary)
        assert b'native-core.a(StarBuffer.cpp.o)' not in (out/(name+'.map')).read_bytes(), 'original Buffer archive bypass'
        return binary

    data = run([compile(sources[1], 'prototype')], 'prototype')
    assert data == (args.values/'original.stdout').read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXPECTED and anchors(data) == 583
    assert run([out/'prototype'], 'repeat') == data
    run([compile(sources[2], 'protocol', True)], 'protocol')
    controls = {}
    for name, body in mutants(sources[1].read_text()).items():
        path = out/(name+'.cpp'); path.write_text(body); generated[str(path)] = sha(path)
        result = run([compile(path, name)], name)
        original_rows = [json.loads(line) for line in data.splitlines()]
        actual_rows = [json.loads(line) for line in result.splitlines()]
        assert len(actual_rows) == 583 and [r['key'] for r in actual_rows] == [r['key'] for r in original_rows]
        controls[name] = [a['key'] for a,b in zip(original_rows, actual_rows) if a != b]
        assert controls[name], 'normally exiting controller control escaped'
    after = {p: sha(p) for p in tracked}
    assert after == tracked, 'source/input drift'
    for path in [*out.glob('*.map'), *out.glob('*.d')]:
        generated[str(path)] = sha(path)
    assert all(sha(path) == digest for path,digest in {**generated, **binaries}.items())
    (out/'after.json').write_text(json.dumps(after, indent=2)+'\n')
    report = {'status': 'FINITE_NATIVE_BUFFER_HOST_SELECTED_PROTOCOL_PASS', 'cases': 583,
              'definitions': 50, 'ordered_sha256': EXPECTED, 'bindings': tracked,
              'native_report': str(native_path.resolve()), 'generated': generated,
              'binaries': binaries, 'receipts': receipts, 'normal_semantic_controls': controls,
              'limits': ['Native C++ blueprint, not Rust or game qualification',
                         'Selected guards, not exhaustive protocol automaton/pointer validation',
                         'C++ prototype foreign callback catch is NOT Rust unwind proof']}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'status': report['status'], 'records':583, 'definitions':50,
                      'bindings':len(tracked), 'binaries':len(binaries), 'commands':len(receipts)}))


if __name__ == '__main__':
    main()
