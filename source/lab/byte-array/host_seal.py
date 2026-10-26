#!/usr/bin/env python3
"""Read-only compiler-artifact validation; a seal never credits native execution.

This module deliberately reconstructs commands without importing the producer.
Hashes detect drift, not malicious fabrication or a signed build attestation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import stage
import audit
import callback_contract
import contract
import host_diagnostic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = ROOT / 'build/byte-array-lab/acquire-r1/acquisition.json'
HOST = ('host_api.h', 'host_native.hpp', 'host_body.cpp', 'host_header.hpp',
        'host_controller.cpp', 'host_protocol.cpp', 'HOST.md')
SCOPE = dict(compiled_units=119, native_objects=113, source_routed_definitions=56,
             required_compiled_abi_symbols=33, native_executions=0)


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equal(a, b, why):
    need(contract.strict_equal(a, b), why)


def rehash(bindings):
    need(type(bindings) is dict, 'hash dictionary')
    for p, h in bindings.items():
        need(type(p) is str and Path(p).is_absolute() and type(h) is str
             and re.fullmatch('[0-9a-f]{64}', h) is not None, 'absolute hash binding')
        need(sha(p) == h, 'current binding drift: ' + p)


def subset(wanted, actual, why):
    need(type(wanted) is dict and type(actual) is dict, why)
    need(all(p in actual and type(actual[p]) is str and actual[p] == h
             for p, h in wanted.items()), why)


def configured_recipes():
    _, _, _, objects = stage.recipe()
    db = stage.load(stage.CM / 'compile_commands.json')
    rows = []
    for obj in objects:
        matches = [e for e in db if Path(e.get('output', '')) == obj]
        need(len(matches) == 1, 'configured object recipe')
        e = matches[0]
        args = shlex.split(e['command'])
        flags = []
        skip = False
        for arg in args[1:]:
            if skip:
                skip = False
            elif arg == '-o':
                skip = True
            elif arg not in ('-c', e['file']):
                flags.append(arg)
        rows.append(dict(object=str(obj), source=e['file'], compiler=args[0], flags=flags))
    need(len(rows) == 113, '113 configured objects')
    return rows


def selection():
    return {'version': 0, 'case-sensitive': 'true', 'use-external-names': False, 'roots': [
        {'type': 'file', 'name': str(ROOT / 'source/core/StarByteArray.hpp'),
         'external-contents': str(HERE / 'host_header.hpp')},
        {'type': 'file', 'name': str(ROOT / 'source/core/StarByteArray.cpp'),
         'external-contents': str(HERE / 'host_body.cpp')}]}


def jobs_and_commands(root, recipes):
    compiler, flags, libs, _ = stage.recipe()
    jobs = [[r['compiler'], r['flags'], r['source'], str(i)] for i, r in enumerate(recipes)]
    for name, source in [('controller', HERE / 'host_controller.cpp'),
                         ('protocol', HERE / 'host_protocol.cpp'),
                         ('lab', root / 'lab-probe.cpp'), ('callback', root / 'callback-probe.cpp'),
                         ('growth', root / 'growth.cpp'), ('signed', root / 'signed.cpp')]:
        jobs.append([str(compiler), flags, str(source), name])
    extra = ['-ivfsoverlay', str(root / 'overlay.json'), '-I' + str(HERE)]
    commands = []
    for c, f, src, name in jobs:
        commands.append(('deps-' + name, [c, *f, *extra, '-M', '-MF', root / (name + '.d'), src]))
    for c, f, src, name in jobs:
        commands.append(('compile-' + name, [c, *f, *extra, '-c', src, '-o', root / (name + '.o')]))
    commands += [('archive', ['/usr/bin/ar', 'qcs', root / 'prototype-core.a',
                               *[root / (str(i) + '.o') for i in range(113)]]),
                 ('archive-table', ['/usr/bin/ar', 't', root / 'prototype-core.a'])]
    for name in ('lab', 'callback', 'protocol', 'growth', 'signed'):
        control = name in ('growth', 'signed')
        commands.append(('link-' + name, [compiler, *flags, *extra,
            root / ('lab.o' if control else name + '.o'),
            root / (name + '.o' if control else 'controller.o'), root / 'prototype-core.a', *libs,
            '-Wl,-dead_strip', '-Wl,-map,' + str(root / (name + '.map')), '-o', root / name]))
    commands.append(('c11', [compiler, '-x', 'c', '-std=c11', '-Wall', '-Wextra', '-Werror',
                             '-pedantic-errors', '-fsyntax-only', root / 'c11.c']))
    bodies = [i for i, r in enumerate(recipes) if r['source'].endswith('/StarByteArray.cpp')]
    need(len(bodies) == 1, 'one configured ByteArray body')
    commands.append(('body-symbols', ['/usr/bin/nm', '-C', '--defined-only', root / (str(bodies[0]) + '.o')]))
    return jobs, [(n, list(map(str, argv))) for n, argv in commands]


def check_commands(root, rows, expected):
    equal([r['name'] for r in rows], [n for n, _ in expected], 'compiler-only command sequence')
    equal({p.name for p in root.glob('*.command.json')},
          {name + '.command.json' for name, _ in expected}, 'compiler-only command mirrors')
    for row, (name, argv) in zip(rows, expected):
        equal(row['command'], argv, 'exact configured command: ' + name)
        need(type(row['returncode']) is int and row['returncode'] == 0, 'integer zero compiler exit')
        need(row['executable'] == str(Path(argv[0]).resolve()), 'compiler/tool executable path')
        need(sha(row['executable']) == row['before'] == row['after'], 'compiler/tool image drift')
        equal(stage.load(root / (name + '.command.json')), row, 'command mirror')
        for ext in ('stdout', 'stderr'):
            need(sha(root / (name + '.' + ext)) == row[ext], 'command stream: ' + name)


def dependency_paths(path):
    words = shlex.split(path.read_text().replace('\\\n', ' ').split(':', 1)[1])
    overlay = {r['name']: r['external-contents'] for r in selection()['roots']}
    paths = []
    for word in words:
        p = Path(word)
        p = p.resolve() if p.is_absolute() else (stage.CM / p).resolve()
        paths.append(overlay.get(str(p), str(p)))
    return paths


def check_dependencies(root, jobs, bindings):
    for _, _, _, name in jobs:
        for p in dependency_paths(root / (name + '.d')):
            need(p in bindings, 'missing transitive dependency binding: ' + p)


def check_routes(header, body, original):
    equal(host_diagnostic.class_declaration(header), host_diagnostic.class_declaration(original),
          'unchanged class declaration except friend')
    modes = list(map(int, re.findall(r'execute\((\d+),', body + header)))
    equal(sorted(modes), list(range(56)), '56 source routes')


def check_archive(root):
    members = audit.archive_members((root / 'prototype-core.a').read_bytes())
    equal([n.decode() for n, _ in members], [str(i) + '.o' for i in range(113)], '113 fresh archive members')
    for name, data in members:
        need(hashlib.sha256(data).hexdigest() == sha(root / name.decode()), 'archive member bytes')
    stage.artifacts.check_archive_members((root / 'archive-table.stdout').read_bytes(),
                                          [n for n, _ in members])


def check_map(root, name):
    objects = stage.artifacts.link_map_objects((root / (name + '.map')).read_bytes())
    control = name in ('growth', 'signed')
    wanted = {str(root / ('lab.o' if control else name + '.o')).encode(),
              str(root / (name + '.o' if control else 'controller.o')).encode()}
    archive = str(root / 'prototype-core.a').encode()
    members = {archive + b'(' + str(i).encode() + b'.o)' for i in range(113)}
    body = next(i for i, r in enumerate(configured_recipes()) if r['source'].endswith('/StarByteArray.cpp'))
    wanted.add(archive + b'(' + str(body).encode() + b'.o)')
    need(wanted <= set(objects), 'actual probe/controller/archive map route')
    _, flags, libs, _ = stage.recipe()
    sdk = Path(flags[flags.index('-isysroot') + 1]) if '-isysroot' in flags else None
    library_prefixes = [str(Path(p)).encode() + b'(' for p in libs if Path(p).is_absolute() and p.endswith('.a')]
    # Only configured third-party libraries may supplement the rebuilt core.
    need(all(p in wanted or p in members or p == b'linker synthesized'
             or any(p.startswith(prefix) and p.endswith(b')') for prefix in library_prefixes)
             or (sdk is not None and p.endswith(b'.tbd') and Path(p.decode()).is_relative_to(sdk))
             for p in objects),
         'unexpected or legacy map object route')


def check_generated(root):
    for name, model in [('expected', contract.expected()), ('callback-expected', callback_contract.expected()),
                        ('growth-expected', audit.wrong_rows('growth-control')),
                        ('signed-expected', audit.wrong_rows('signed-control'))]:
        canonical = callback_contract.canonical if name == 'callback-expected' else contract.canonical
        need((root / (name + '.jsonl')).read_bytes() == canonical(model), 'frozen expected corpus ' + name)
    names = re.findall(r'uint64_t\s+(\w*(?:count|counter)\w*)\s*\(', (HERE / 'host_api.h').read_text())
    need(len(names) == 1, 'one counter accessor')
    count = names[0]
    for name in ('lab', 'callback'):
        expected = ('#define main byte_array_frozen_main\n#include "' + str(HERE / (name + '.cpp')) + '"\n#undef main\n'
            'int main(int argc,char** argv) {\nuint64_t before[56][3];\n'
            f'for(unsigned m=0;m<56;++m)for(unsigned e=0;e<3;++e)before[m][e]={count}(m,e);\n'
            'int rc=byte_array_frozen_main(argc,argv);\nstd::cerr << "COUNTERS";\n'
            f'for(unsigned m=0;m<56;++m)for(unsigned e=0;e<3;++e)std::cerr << " " << ({count}(m,e)-before[m][e]);\n'
            'std::cerr << "\\n";return rc;\n}\n')
        need((root / (name + '-probe.cpp')).read_text() == expected, 'unchanged corpus counter wrapper')
    need((root / 'c11.c').read_text() == '#include "' + str(HERE / 'host_api.h') + '"\nint main(void){return 0;}\n',
         'strict C11 fixture source')
    source = (HERE / 'host_controller.cpp').read_text()
    for name, old, new in [('growth', 'cap*2', 'cap'), ('signed', 'return x<y?UINT64_MAX:x>y?1:0;',
                              'return int8_t(x)<int8_t(y)?UINT64_MAX:int8_t(x)>int8_t(y)?1:0;')]:
        need(source.count(old) == 1 and (root / (name + '.cpp')).read_text() == source.replace(old, new),
             'source-derived control ' + name)


def validate_build(path):
    path = Path(path).resolve()
    need(path.name == 'build.json', 'compiler manifest name')
    root = path.parent
    q = stage.load(path)
    need(q['status'] == 'COMPILED_UNSEALED', 'compiler-only unsealed phase')
    need(q['parent'] == str(PARENT) and q['parent_sha256'] == sha(PARENT), 'native parent identity')
    parent = stage.verify_acquisition(PARENT)
    recipes = configured_recipes()
    equal(q['recipes'], recipes, 'configured complete native recipes')
    equal(q['overlay'], selection(), 'exact two-file overlay')
    equal(stage.load(root / 'overlay.json'), selection(), 'overlay file')
    jobs, commands = jobs_and_commands(root, recipes)
    equal(q['jobs'], jobs, '119 configured translation units')
    equal(q['bindings'], q['after'], 'manifest before/after')
    equal(q['bindings'], stage.load(root / 'before.json'), 'before copy')
    equal(q['bindings'], stage.load(root / 'after.json'), 'after copy')
    required = {**parent['bindings'], **parent['artifacts'], str(PARENT): sha(PARENT)}
    for name in (*HOST, 'host_compile.py', 'lab.cpp', 'callback.cpp', 'contract.py', 'callback_contract.py', 'host_stage.py'):
        required[str(HERE / name)] = sha(HERE / name)
    freeze = stage.load(root / 'precompile-freeze.json')
    subset(required, freeze, 'complete initial source/native parent freeze')
    subset(freeze, q['bindings'], 'precompile freeze subset')
    check_dependencies(root, jobs, q['bindings'])
    need(str(root / 'overlay.json') in q['bindings'], 'overlay binding')
    rehash(q['bindings'])
    rehash(q['artifacts'])
    equal(set(q['artifacts']), {str(p) for p in root.iterdir() if p.is_file() and p != path}, 'all compiler files')
    equal(q['commands'], stage.load(root / 'commands.json'), 'command inventory copy')
    check_commands(root, q['commands'], commands)
    names = {'overlay.json', 'lab-probe.cpp', 'callback-probe.cpp', 'c11.c', 'growth.cpp', 'signed.cpp',
             'expected.jsonl', 'callback-expected.jsonl', 'growth-expected.jsonl', 'signed-expected.jsonl',
             'precompile-freeze.json', 'before.json', 'after.json', 'commands.json', 'prototype-core.a'}
    names.update(n + ext for _, _, _, n in jobs for ext in ('.o', '.d'))
    names.update(n + ext for n, _ in commands for ext in ('.command.json', '.stdout', '.stderr'))
    names.update(n + ext for n in ('lab', 'callback', 'protocol', 'growth', 'signed') for ext in ('', '.map'))
    equal(set(q['artifacts']), {str(root / n) for n in names}, 'exact compiler-only artifact scope')
    check_routes((HERE / 'host_header.hpp').read_text(), (HERE / 'host_body.cpp').read_text(),
                 (ROOT / 'source/core/StarByteArray.hpp').read_text())
    check_archive(root)
    for name in ('lab', 'callback', 'protocol', 'growth', 'signed'):
        need((root / name).is_file(), 'linked executable exists')
        check_map(root, name)
    host_diagnostic.required_abi((PARENT.parent / 'symbols-current.stdout').read_bytes(),
                                 (root / 'body-symbols.stdout').read_bytes())
    check_generated(root)
    return q


def verifier_bindings():
    paths = [HERE / 'host_seal.py', HERE / 'test_host_seal.py', HERE / 'host_diagnostic.py',
             HERE / 'host_stage.py', HERE / 'stage.py', HERE / 'audit.py', HERE / 'contract.py',
             HERE / 'callback_contract.py', Path(stage.artifacts.__file__), Path(stage.provenance.__file__)]
    return {str(p.resolve()): sha(p) for p in paths}


def verify(seal_path):
    seal = stage.load(Path(seal_path).resolve())
    need(seal['status'] == 'SEALED_NATIVE_BYTEARRAY_HOST', 'sealed compiler-artifact phase')
    equal(seal['scope'], SCOPE, 'typed finite compiler scope')
    equal(seal['verifier_bindings'], verifier_bindings(), 'current sealer and test code')
    need(type(seal['build']) is str and Path(seal['build']).is_absolute(), 'absolute build path')
    need(sha(seal['build']) == seal['build_sha256'], 'compiler manifest drift')
    validate_build(seal['build'])
    return seal


def seal(build, output):
    build = Path(build).resolve()
    before = sha(build)
    code = verifier_bindings()
    validate_build(build)
    need(before == sha(build) and code == verifier_bindings(), 'seal acquisition drift')
    out = stage.fresh(output, 'host-seal-')
    result = dict(status='SEALED_NATIVE_BYTEARRAY_HOST', build=str(build), build_sha256=before,
                  scope=SCOPE, verifier_bindings=code)
    stage.dump(out / 'seal.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='phase', required=True)
    create = sub.add_parser('seal')
    create.add_argument('--build', required=True)
    create.add_argument('--output', required=True)
    check = sub.add_parser('verify')
    check.add_argument('--seal', required=True)
    args = parser.parse_args()
    result = seal(args.build, args.output) if args.phase == 'seal' else verify(args.seal)
    print(json.dumps(result))
