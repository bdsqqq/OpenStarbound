#!/usr/bin/env python3
"""Replay the scalar controller through real private OptionParser storage."""
import argparse
import hashlib
import json
import shlex
import subprocess
from pathlib import Path
import run as native
from verify_receipts import verify

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--values', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    values = args.values.absolute()
    verify(values / 'report.json')
    source = json.loads((values / 'report.json').read_text())
    output = args.output.absolute()
    base = ROOT / 'build/option-parser-lab'
    if output == base or not output.is_relative_to(base) or output.exists() or any(p.is_symlink() for p in [output, *output.parents]):
        parser.error('fresh owned nonsymlink output required')
    output.mkdir(parents=True)
    receipts = []
    generated = {}
    binaries = {}

    def execute(command, name, expected=0):
        command = list(map(str, command))
        executable = Path(command[0]).resolve()
        before = sha(executable)
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=80)
        (output / (name + '.stdout')).write_bytes(result.stdout)
        (output / (name + '.stderr')).write_bytes(result.stderr)
        assert sha(executable) == before, 'executable drift'
        receipts.append(dict(name=name, command=command, executable_sha256=before,
                             returncode=result.returncode, stdout_sha256=sha(output / (name + '.stdout')),
                             stderr_sha256=sha(output / (name + '.stderr'))))
        (output / 'receipts.json').write_text(json.dumps(receipts, indent=2))
        assert result.returncode == expected, (name, result.returncode)
        return result.stdout

    link = source['link']
    compiler = link['compiler']
    flags = [*link['flags'], '-I' + str(HERE)]
    tracked = [Path(p) for p in source['bindings']]
    tracked += [Path(__file__), HERE / 'host_contract.hpp', HERE / 'host_contract.cpp', HERE / 'host_contract_test.cpp', HERE / 'verify_receipts.py', values / 'report.json', Path(link['archive'])]
    for index, file in enumerate([HERE / 'host_contract.cpp', HERE / 'host_contract_test.cpp']):
        dependency = output / (str(index) + '.d')
        execute([compiler, *flags, '-M', '-MF', dependency, file], 'dependency' + str(index))
        tracked += [Path(p) if Path(p).is_absolute() else ROOT / p for p in shlex.split(dependency.read_text().replace('\\\n', ' ').split(':', 1)[1])]
    tracked = list(dict.fromkeys(p.resolve() for p in tracked))
    before = {str(p): sha(p) for p in tracked}
    (output / 'before.json').write_text(json.dumps(before, indent=2))

    def compile(name, cpp, fixture, hooks=False):
        binary = output / name
        command = [compiler, *flags, *(['-DSTAR_OPTION_PARSER_LAB_TEST_HOOKS'] if hooks else []), cpp, fixture, link['archive'], *link['libraries'], '-Wl,-dead_strip', '-o', binary]
        execute(command, name + '-compile')
        generated[str(cpp)] = sha(cpp)
        binaries[str(binary)] = sha(binary)
        return binary

    test = compile('host-test', HERE / 'host_contract.cpp', HERE / 'host_contract_test.cpp', True)
    execute([test], 'host-test')
    candidate = compile('candidate', HERE / 'host_contract.cpp', HERE / 'lab.cpp')
    observed = execute([candidate], 'candidate')
    count = native.anchors(observed)
    assert observed == (values / 'original.stdout').read_bytes(), 'complete native observation mismatch'
    controls = []
    text = (HERE / 'host_contract.cpp').read_text()
    old = 'else { d.call(16); if(d.call(15,0)!=2 && d.call(17,0)) d.call(30,18); else {d.call(19);d.call(20);} }'
    assert text.count(old) == 1
    mutants = {'consume': text.replace(old, 'else { if(d.call(15,0)!=2 && d.call(17,0)) d.call(30,18); else {d.call(16);d.call(19);d.call(20);} }')}
    old = 'format(*stream,"{}: {}\\n\\n",name,summary);'
    assert text.count(old) == 1
    mutants['chunk'] = text.replace(old, 'for(char ch:strf("{}: {}\\n\\n",name,summary)) *stream << ch;')
    for name, mutant in mutants.items():
        cpp = output / (name + '.cpp')
        cpp.write_text(mutant)
        binary = compile(name, cpp, HERE / 'lab.cpp')
        wrong = execute([binary], name)
        assert wrong != observed, 'compiled mutant escaped: ' + name
        controls.append(name)
    header = output / 'header.c'
    header.write_text('#include "host_contract.hpp"\n_Static_assert(sizeof(uint64_t)==8,"scalar");\n')
    execute([compiler, '-x', 'c', '-std=c11', '-pedantic', '-Wall', '-Wextra', '-Werror', '-I' + str(HERE), '-fsyntax-only', header], 'strict-c11')
    generated[str(header)] = sha(header)
    after = {str(p): sha(p) for p in tracked}
    assert before == after and all(sha(p) == h for p, h in {**generated, **binaries}.items()), 'artifact drift'
    verify(values / 'report.json')
    (output / 'after.json').write_text(json.dumps(after, indent=2))
    report = dict(status='FINITE_NATIVE_HOST_CONTROLLER_PASS', cases=count,
                  ordered_sha256=hashlib.sha256(observed).hexdigest(), controls=controls,
                  bindings=before, generated=generated, binaries=binaries, receipts=receipts,
                  limits=['C++ scalar blueprint, not Rust or actual application qualification', 'Not exhaustive invalid-phase or allocator/resource/destruction timing proof'])
    (output / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ['status', 'cases', 'ordered_sha256', 'controls']}))


if __name__ == '__main__':
    main()
