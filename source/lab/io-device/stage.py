#!/usr/bin/env python3
"""Compiler-only acquisition and separately gated execution of frozen native traces.

The old monolithic runners are never imported or invoked. This pipeline consumes
only the frozen six-case expectation, not the rejected whole-device model.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / 'behavior'))
from native_artifacts import has_archive_member, check_archive_members
import build_provenance as provenance
from ledger_verify import EXPECTED

VARIANTS = ('original', 'reference', 'current', 'pointer-no-advance', 'failure-restore')
POSITIVES = ('original', 'reference', 'current', 'repeat')
CONTROLS = VARIANTS[3:]
CANON = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'))


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def fresh(path, prefix):
    path = Path(path).absolute()
    base = ROOT / 'build/io-device-lab'
    need(path.is_relative_to(base) and path != base and path.name.startswith(prefix)
         and not path.exists() and not any(p.is_symlink() for p in (path, *path.parents)), 'fresh owned output')
    path.mkdir(parents=True)
    return path


def command(cmd, name, out, receipts):
    cmd = list(map(str, cmd))
    exe = Path(cmd[0]).resolve()
    before = sha(exe)
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=65)
    (out / (name + '.stdout')).write_bytes(result.stdout)
    (out / (name + '.stderr')).write_bytes(result.stderr)
    receipts.append(dict(name=name, command=cmd, executable=str(exe), returncode=result.returncode,
        executable_before=before, executable_after=sha(exe),
        stdout=sha(out / (name + '.stdout')), stderr=sha(out / (name + '.stderr'))))
    dump(out / 'receipts.json', receipts)
    need(result.returncode == 0 and before == sha(exe), 'command did not exit normally: ' + name)
    return result.stdout


def adapt(source, cpp):
    source = source.replace('namespace Star {', 'namespace Star { namespace IODeviceReference {', 1)
    i = source.rfind('}')
    source = source[:i] + '} ' + source[i:]
    return source.replace('#include "StarIODevice.hpp"', '#include "StarIODevice.reference.hpp"', 1) if cpp else source


def source_gate():
    for ext in ('cpp', 'hpp'):
        frozen = subprocess.check_output(['git', 'show', 'c233825b:source/core/StarIODevice.' + ext], cwd=ROOT).decode()
        need((ROOT / ('source/core/StarIODevice.' + ext)).read_text() == frozen, 'production source drift')
        need((HERE / ('StarIODevice.original.' + ext)).read_text() == frozen, 'raw source drift')
        need((HERE / ('StarIODevice.reference.' + ext)).read_text() == adapt(frozen, ext == 'cpp'), 'namespace adaptation drift')


def recipe():
    cm = ROOT / 'build/behavior/reference/cmake'
    db = cm / 'compile_commands.json'
    entry = next(e for e in load(db) if e['file'].endswith('/StarIODevice.cpp'))
    args = shlex.split(entry['command'])
    flags, skip = [], False
    for arg in args[1:]:
        if skip:
            skip = False
            continue
        if arg == '-o':
            skip = True
        elif arg not in ('-c', entry['file']):
            flags.append(arg)
    need(not any('STAR_USE_RUST' in x for x in flags), 'not a native recipe')
    lines = (cm / 'build.ninja').read_text().splitlines()
    i = next(i for i, line in enumerate(lines) if line.startswith('build ') and '/bin/starbound:' in line)
    objects = [cm / p for p in shlex.split(lines[i].split(': ', 1)[1])[1:]
               if p.endswith('.o') and p.startswith(('core/', 'extern/'))]
    libraries = shlex.split(next(line.split(' = ', 1)[1] for line in lines[i+1:i+15] if line.startswith('  LINK_LIBRARIES = ')))
    libraries = [str(cm / p) if p.endswith('.a') and not Path(p).is_absolute() else p for p in libraries]
    # clang++ can resolve to clang: keep argv[0]'s C++ driver mode for object-only
    # linking, while fingerprints below still bind the resolved executable bytes.
    return Path(args[0]), flags, libraries, objects


def dependencies(path):
    return [Path(p).resolve() if Path(p).is_absolute() else (ROOT / p).resolve()
            for p in shlex.split(Path(path).read_text().replace('\\\n', ' ').split(':', 1)[1])]


def required_inputs(compiler, archive):
    return [Path(__file__).resolve(), HERE.parent / 'native_artifacts.py', HERE / 'ledger.cpp', HERE / 'ledger_verify.py',
        *[HERE / ('StarIODevice.' + kind + '.' + ext) for kind in ('original', 'reference') for ext in ('cpp', 'hpp')],
        ROOT / 'source/core/StarIODevice.cpp', ROOT / 'source/core/StarIODevice.hpp',
        ROOT / 'build/buffer-lab/native-identity-r1/manifest.json', archive, compiler,
        Path(sys.executable).resolve(), Path('/usr/bin/ar').resolve(), Path('/usr/bin/nm').resolve(),
        Path(provenance.__file__).resolve(), ROOT / 'build/behavior/reference/cmake/build.ninja',
        ROOT / 'build/behavior/reference/cmake/compile_commands.json']


def acquire(output):
    out = fresh(output, 'staged-acquire-')
    source_gate()
    receipts = []
    game = ROOT / 'build/behavior/reference/bin/starbound'
    closure = provenance.verify(game)
    compiler, flags, libs, objects = recipe()
    archive = ROOT / 'build/io-device-lab/oracle-r2/native-core.a'
    identity_path = ROOT / 'build/buffer-lab/native-identity-r1/manifest.json'
    identity = load(identity_path)
    need(all(sha(p) == h for p, h in identity.items()), 'native profile drift')
    table = command(['/usr/bin/ar', 't', archive], 'archive-table', out, receipts)
    check_archive_members(table, [p.name.encode() for p in objects])
    # A manifest's 202 input bindings are not its 113 object members.
    for index, obj in enumerate(objects):
        body = command(['/usr/bin/ar', 'p', archive, obj.name], 'member-' + str(index), out, receipts)
        need(hashlib.sha256(body).hexdigest() == sha(obj), 'archive member bytes: ' + obj.name)
    dump(out / 'expected.json', EXPECTED)
    source = (HERE / 'StarIODevice.original.cpp').read_text()
    pointer = source
    for name, following in (('readFullAbsolute', 'writeFullAbsolute'), ('writeFullAbsolute', 'readBytes')):
        begin = pointer.index('void IODevice::' + name + '(')
        end = pointer.index('IODevice::' + following + '(', begin + 1)
        part = pointer[begin:end]
        need(part.count('data += r;') == 1, 'pointer control anchor')
        pointer = pointer[:begin] + part.replace('data += r;', 'data += 0;') + pointer[end:]
    restore = source
    for operation in ('read', 'write'):
        old = '  size_t ret = ' + operation + '(data, len);'
        need(restore.count(old) == 1, 'restore control anchor')
        restore = restore.replace(old, '  size_t ret;\n  try { ret = ' + operation + '(data, len); } catch (...) { seek(storedPos); throw; }')
    (out / 'pointer-no-advance.cpp').write_text(pointer)
    (out / 'failure-restore.cpp').write_text(restore)
    bodies = dict(original=HERE / 'StarIODevice.original.cpp', reference=HERE / 'StarIODevice.reference.cpp',
                  current=ROOT / 'source/core/StarIODevice.cpp', **{n: out / (n + '.cpp') for n in CONTROLS})
    tracked = required_inputs(compiler, archive) + list(map(Path, identity)) + [game, provenance.sidecar(game)]
    tracked += [ROOT / p for p in closure['source_files']]
    for index, (name, body) in enumerate([('probe', HERE / 'ledger.cpp'), ('probe-ref', HERE / 'ledger.cpp'), *bodies.items()]):
        dep = out / (name + '.d')
        command([compiler, *flags, '-I' + str(HERE), *(['-DLAB_REFERENCE'] if name == 'probe-ref' else []),
                 '-M', '-MF', dep, body], 'deps-' + name, out, receipts)
        tracked += [p for p in dependencies(dep) if not p.is_relative_to(out)]
    tracked = list(dict.fromkeys(p.resolve() for p in tracked))
    before = {str(p): sha(p) for p in tracked}
    dump(out / 'before.json', before)
    for name in ('probe', 'probe-ref'):
        command([compiler, *flags, '-I' + str(HERE), *(['-DLAB_REFERENCE'] if name == 'probe-ref' else []),
                 '-c', HERE / 'ledger.cpp', '-o', out / (name + '.o')], 'compile-' + name, out, receipts)
    for name, body in bodies.items():
        obj = out / ('body-' + name + '.o')
        command([compiler, *flags, '-I' + str(HERE), '-c', body, '-o', obj], 'compile-' + name, out, receipts)
        command([compiler, *flags, out / ('probe-ref.o' if name == 'reference' else 'probe.o'), obj, archive,
                 *libs, '-Wl,-dead_strip', '-Wl,-map,' + str(out / (name + '.map')), '-o', out / name],
                'link-' + name, out, receipts)
        symbols = command(['/usr/bin/nm', '-C', out / name], 'symbols-' + name, out, receipts)
        if name == 'reference':
            need(b'Star::IODeviceReference::IODevice::readFullAbsolute' in symbols, 'reference namespace absent')
        else:
            need(not has_archive_member((out / (name + '.map')).read_bytes(), b'native-core.a', b'StarIODevice.cpp.o'), 'legacy archive object pulled')
    after = {str(p): sha(p) for p in tracked}
    dump(out / 'after.json', after)
    need(before == after and provenance.verify(game) == closure, 'acquisition input drift')
    artifacts = {str(p): sha(p) for p in out.iterdir() if p.is_file()}
    manifest = dict(status='ACQUIRED_NOT_EXECUTED', schema=1, scope='six-frozen-cases',
        native_binary=str(game), native_closure=closure, compiler=str(compiler), archive=str(archive),
        bindings=before, artifacts=artifacts, receipts=receipts,
        variants={n: str(out / n) for n in VARIANTS})
    dump(out / 'acquisition.json', manifest)
    verify_acquisition(out / 'acquisition.json')
    gate_tests(out / 'acquisition.json')
    print('ACQUIRED_NOT_EXECUTED', out / 'acquisition.json', flush=True)


def verify_acquisition(path, value=None):
    path = Path(path).resolve()
    root = path.parent
    m = load(path) if value is None else value
    need(set(m) == set('status schema scope native_binary native_closure compiler archive bindings artifacts receipts variants'.split()), 'acquisition schema')
    need(m['status'] == 'ACQUIRED_NOT_EXECUTED' and type(m['schema']) is int and m['schema'] == 1
         and m['scope'] == 'six-frozen-cases', 'acquisition status/scope')
    need(set(m['variants']) == set(VARIANTS), 'variant scope')
    need(m['bindings'] == load(root / 'before.json') == load(root / 'after.json'), 'binding maps disagree')
    need(all(str(p.resolve()) in m['bindings'] for p in required_inputs(Path(m['compiler']), Path(m['archive']))), 'mandatory source binding absent')
    required = ['expected.json', 'before.json', 'after.json', 'receipts.json', 'archive-table.stdout']
    required += [n + ext for n in VARIANTS for ext in ('', '.map')]
    required += [n + '.d' for n in ('probe', 'probe-ref', *VARIANTS)]
    need(all(str(root / n) in m['artifacts'] for n in required), 'mandatory artifact absent')
    need(set(m['artifacts']) == {str(p) for p in root.iterdir() if p.is_file() and p.name != 'acquisition.json'}, 'acquisition artifact inventory')
    for group in ('bindings', 'artifacts'):
        for name, digest in m[group].items():
            need(Path(name).is_absolute() and sha(name) == digest, group + ' drift: ' + name)
    need(CANON(load(root / 'expected.json')) == CANON(EXPECTED), 'frozen expected contract changed')
    need(m['receipts'] == load(root / 'receipts.json'), 'acquisition receipt copies')
    names = set()
    for r in m['receipts']:
        need(r['name'] not in names, 'duplicate acquisition command')
        names.add(r['name'])
        need(r['returncode'] == 0 and sha(r['executable']) == r['executable_before'] == r['executable_after'], 'acquisition command identity')
        need(Path(r['command'][0]).resolve() == Path(r['executable']), 'acquisition executable route')
        # No generated native probe is allowed to run during acquisition.
        need(Path(r['executable']) in (Path(m['compiler']).resolve(), Path('/usr/bin/ar').resolve(), Path('/usr/bin/nm').resolve()), 'native execution during acquisition')
        for ext in ('stdout', 'stderr'):
            need(sha(root / (r['name'] + '.' + ext)) == r[ext], 'acquisition stdio')
    need({'compile-' + n for n in ('probe', 'probe-ref', *VARIANTS)} <= names
         and {'link-' + n for n in VARIANTS} <= names, 'uncompiled variant credited')
    for name, exe in m['variants'].items():
        need(exe == str(root / name) and exe in m['artifacts'], 'variant executable binding')
        if name != 'reference':
            need(not has_archive_member((root / (name + '.map')).read_bytes(), b'native-core.a', b'StarIODevice.cpp.o'), 'archive bypass')
    for n in ('probe', 'probe-ref', *VARIANTS):
        need(all(str(p) in m['bindings'] or str(p) in m['artifacts'] for p in dependencies(root / (n + '.d'))), 'dependency closure gap')
    need(provenance.verify(Path(m['native_binary'])) == m['native_closure'], 'native compiled closure drift')
    source_gate()
    return m


def gate_tests(path):
    m = load(path)
    variants = [copy.deepcopy(m) for _ in range(5)]
    variants[0]['bindings'].pop(str(HERE / 'ledger.cpp'))
    variants[1]['artifacts'][m['variants']['original']] = '0' * 64
    variants[2]['status'] = 'PASS'
    variants[3]['variants'].pop('reference')
    variants[4]['artifacts'].pop(str(Path(path).parent / 'expected.json'))
    for i, bad in enumerate(variants):
        try:
            verify_acquisition(path, bad)
        except ValueError:
            continue
        raise ValueError('pre-execution corruption escaped: ' + str(i))
    return len(variants)


def check_values(data):
    rows = [json.loads(line) for line in data.decode('ascii').splitlines()]
    need(CANON(rows) == CANON(EXPECTED), 'source-derived six-case callback ledger mismatch')


def execute(path, output):
    m = verify_acquisition(path)
    need(gate_tests(path) == 5, 'pre-execution integrity controls')
    out = fresh(output, 'staged-execute-')
    receipts = []
    rejections = {}
    for name in (*POSITIVES, *CONTROLS):
        exe = m['variants']['original' if name == 'repeat' else name]
        data = command([exe], name, out, receipts)
        if name in POSITIVES:
            check_values(data)
        else:
            try:
                check_values(data)
            except ValueError as error:
                rejections[name] = str(error)
            else:
                raise ValueError('normal semantic control escaped: ' + name)
    verify_acquisition(path)
    artifacts = {str(p): sha(p) for p in out.iterdir() if p.is_file()}
    report = dict(status='FINITE_NATIVE_SIX_CASE_WITNESS_PASS', scope='six-frozen-cases', cases=6,
        acquisition=str(Path(path).resolve()), acquisition_sha256=sha(path),
        controls=rejections, receipts=receipts, artifacts=artifacts, preexecution_corruptions=5)
    dump(out / 'report.json', report)
    verify_execution(out / 'report.json')
    print('FINITE_NATIVE_SIX_CASE_WITNESS_PASS', out / 'report.json', flush=True)


def verify_execution(path):
    path = Path(path).resolve()
    r = load(path)
    need(r['status'] == 'FINITE_NATIVE_SIX_CASE_WITNESS_PASS' and r['scope'] == 'six-frozen-cases'
         and type(r['cases']) is int and r['cases'] == 6, 'execution scope')
    need(sha(r['acquisition']) == r['acquisition_sha256'], 'acquisition manifest drift')
    m = verify_acquisition(r['acquisition'])
    need(set(r['controls']) == set(CONTROLS) and r['preexecution_corruptions'] == 5, 'control scope')
    need(r['receipts'] == load(path.parent / 'receipts.json') and [x['name'] for x in r['receipts']] == [*POSITIVES, *CONTROLS], 'execution command scope')
    need(set(r['artifacts']) == {str(path.parent / (n + ext)) for n in (*POSITIVES, *CONTROLS) for ext in ('.stdout', '.stderr')} | {str(path.parent / 'receipts.json')}, 'execution artifact scope')
    for name, digest in r['artifacts'].items():
        need(sha(name) == digest, 'execution artifact drift')
    for row in r['receipts']:
        name = row['name']
        exe = m['variants']['original' if name == 'repeat' else name]
        need(row['command'] == [exe] and row['executable'] == exe and row['returncode'] == 0
             and sha(exe) == row['executable_before'] == row['executable_after'], 'executed native route/identity')
        for ext in ('stdout', 'stderr'):
            need(sha(path.parent / (name + '.' + ext)) == row[ext], 'execution stream binding')
        data = (path.parent / (name + '.stdout')).read_bytes()
        if name in POSITIVES:
            check_values(data)
        else:
            try:
                check_values(data)
            except ValueError:
                pass
            else:
                raise ValueError('semantic control not detected')
    return dict(cases=6, positive_executions=4, normal_semantic_controls=2, preexecution_corruptions=5)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='phase', required=True)
    a = sub.add_parser('acquire'); a.add_argument('--output', required=True)
    a = sub.add_parser('execute'); a.add_argument('--acquisition', required=True); a.add_argument('--output', required=True)
    a = sub.add_parser('verify'); a.add_argument('--report', required=True)
    args = parser.parse_args()
    if args.phase == 'acquire': acquire(args.output)
    elif args.phase == 'execute': execute(args.acquisition, args.output)
    else: print(json.dumps(verify_execution(args.report)))

if __name__ == '__main__':
    main()
