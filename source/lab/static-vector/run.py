#!/usr/bin/env python3
"""One-shot native acquisition. Explicit original unit deadline; no Cargo/game.

--prepare writes a fresh immutable admission without launching native code.
--execute consumes that admission (requires its external hash), never renews it.
Without either option, prepare then execute once. No successful leaf reruns.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import verify as v

admitter = v.load('_static_vector_object_selection', HERE.parent / 'id-map-production/game_build_admission.py')
allocation = admitter._allocation
TOOL_PLAN = ROOT / admitter.TOOL_PLAN
PIN = admitter.TOOL_PLAN_SHA
SCOPE = 'finite native StaticVector value characterization; no Rust, game, generic lifetime or RTTI parity'
need, sha, read = v.need, v.sha, v.read


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, sort_keys=True, separators=(',', ':'))
        stream.write('\n')


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def budget(out):
    observation = allocation.measure(ROOT, out)
    archive, live, size = (observation[k] for k in ('archiveBytes', 'liveBytes', 'activeRootBytes'))
    if not (archive <= 16 * 1024**3 and live <= 4 * 1024**3 and size <= 128 * 1024**2):
        raise allocation.AllocationError('fixed 4GiB live/16GiB archive/128MiB native-root caps', observation)
    return dict(archiveBytes=archive, liveBytes=live, nativeRootBytes=size, observation=observation)


def recipe():
    need(sha(TOOL_PLAN) == PIN, 'external e890 path-selection pin')
    old = read(TOOL_PLAN)
    cm = ROOT / 'build/behavior/id-map-combined-r2/reference/cmake'
    db = read(cm / 'compile_commands.json')
    rows = [r for r in db if r['file'] == str(ROOT / 'source/core/StarAudio.cpp')]
    need(len(rows) == 1, 'unique actual StarAudio.cpp flags')
    args = shlex.split(rows[0]['command'])
    need(args[0] == old['tools']['CMAKE_CXX_COMPILER'], 'selected compiler path')
    flags, skip = [], False
    for arg in args[1:]:
        if skip:
            skip = False
        elif arg in ('-o', '-MF', '-MT'):
            skip = True
        elif arg not in ('-c', rows[0]['file'], '-MD', '-MMD'):
            flags.append(arg)
    lines = (cm / 'build.ninja').read_text().splitlines()
    edges = [i for i, line in enumerate(lines) if line.startswith('build ') and '/bin/starbound:' in line]
    need(len(edges) == 1, 'unique actual starbound link edge')
    block = []
    for line in lines[edges[0] + 1:]:
        if not line.startswith('  '):
            break
        block.append(line)
    props = dict(line.strip().split(' = ', 1) for line in block if ' = ' in line)
    libs = shlex.split(props['LINK_LIBRARIES'])
    libs = [str((cm / x).resolve()) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
    selectors = re.findall(r'^(STAR_USE_RUST[^:]*):BOOL=(.*)$', (cm / 'CMakeCache.txt').read_text(), re.M)
    need(len(selectors) == len(dict(selectors)) == 29 and all(x == 'OFF' for _, x in selectors), 'exact all29OFF')
    need('-O3' in flags and '-ffast-math' in flags and not any('STAR_USE_RUST' in x for x in flags), 'optimized native flags')
    need(not any('rust' in x.lower() for x in libs), 'no Rust archive')
    sdk = flags[flags.index('-isysroot') + 1]
    need(sdk == old['sdk'], 'selected requested SDK')
    return dict(cm=str(cm), compiler=args[0], flags=flags, libraries=libs,
                objects=admitter.retained_objects(), selectors=[list(x) for x in selectors],
                sdk=sdk, sdkCanonical=old['sdkPhysical'], linker=old['tools']['CMAKE_LINKER'],
                linkFlags=shlex.split(props.get('LINK_FLAGS', '')))


def plans(out, r):
    flags = [*r['flags'], '-I' + str(HERE), '-DStaticVector=StaticVectorCharacterization']
    commands = []
    def add(name, argv, expected=0):
        commands.append(dict(name=name, argv=list(map(str, argv)), expected=expected))
    for role in ('baseline', *v.MUTANTS):
        header = HERE / 'StarStaticVector.original.hpp' if role == 'baseline' else out / 'inputs' / (role + '.hpp')
        add(role + '-compile', [r['compiler'], *flags, '-DSTATIC_VECTOR_TEST_HEADER="' + str(header) + '"',
            '-MD', '-MF', out / (role + '.d'), '-c', HERE / 'native.cpp', '-o', out / (role + '.o')])
        link = [r['compiler'], *r['flags'], *r['linkFlags'], *r['objects'], out / (role + '.o'),
                *r['libraries'], '-Wl,-dead_strip', '-Wl,-map,' + str(out / (role + '.map')),
                '-Wl,-t,-trace_implicit_libraries', '-o', out / role]
        if role == 'baseline':
            add('link-expand', [r['compiler'], '-###', *link[1:]])
        add(role + '-link', link)
        add(role + '-run', [out / role])
        if role == 'baseline':
            add('baseline-repeat', [out / role])
    add('initializer-assignment-negative', [r['compiler'], *flags, '-fsyntax-only', out / 'inputs/initializer-assignment.cpp'], 1)
    need(len(commands) == len({x['name'] for x in commands}) == 15, 'exact15 future commands')
    return commands


def roots_for(out, r):
    usr = Path(r['compiler']).resolve().parent.parent
    roots = [ROOT / 'source/core', ROOT / 'source/extern', HERE, out / 'inputs',
             Path(r['sdk']), usr / 'include', usr / 'lib/clang']
    for i, flag in enumerate(r['flags']):
        if flag in ('-isystem', '-isysroot'):
            roots.append(Path(r['flags'][i + 1]))
        elif flag.startswith('-I'):
            roots.append(Path(flag[2:]))
    return list(dict.fromkeys(map(str, roots)))


def pin(witness, paths):
    for path in map(Path, paths):
        physical = str(path.resolve(strict=True))
        witness['files'][physical] = sha(path)
        witness['aliases'][str(path)] = physical


def imports():
    # Modules loaded via spec are not necessarily registered in sys.modules.
    modules = [v, v.model, v.syntax, v.sdk, admitter, admitter._generic,
               admitter._retention, allocation, *list(sys.modules.values())]
    return sorted({str(Path(m.__file__).resolve()) for m in modules
        if getattr(m, '__file__', None) and Path(m.__file__).is_file()})


def prepare(out, checkpoint, started, deadline):
    v.window(started, deadline, time.time())
    need(re.fullmatch('[0-9a-f]{40}', checkpoint) is not None, 'full base checkpoint')
    need(not out.exists() and out.is_relative_to(ROOT / 'build'), 'fresh owned build output only')
    out.mkdir(parents=True)
    (out / 'inputs').mkdir()
    (out / 'home').mkdir()
    (out / 'tmp').mkdir()
    need(sha(ROOT / 'source/core/StarStaticVector.hpp') == sha(HERE / 'StarStaticVector.original.hpp') == v.HEADER_SHA, 'raw header identity')
    raw = (HERE / 'StarStaticVector.original.hpp').read_text()
    for name, text in v.mutant_headers(raw).items():
        (out / 'inputs' / (name + '.hpp')).write_text(text)
    (out / 'inputs/initializer-assignment.cpp').write_text(v.negative_source())
    dump(out / 'inputs/expected-cases.json', v.model.expected_cases())
    r = recipe()
    roots = roots_for(out, r)
    witness = v.syntax.closure(map(Path, roots))
    usr = Path(r['compiler']).resolve().parent.parent
    tools = [r['compiler'], r['linker'], usr / 'bin/clang', usr / 'lib/libLTO.dylib',
             usr / 'lib/libtapi.dylib', sys.executable]
    files = [*r['objects'], *[x for x in r['libraries'] if Path(x).is_absolute() and Path(x).is_file()],
             *[Path(r['cm']) / x for x in ('build.ninja', 'CMakeCache.txt', 'compile_commands.json')],
             TOOL_PLAN, Path(__file__), *imports(), *tools]
    pin(witness, files)
    manifest = v.sdk.capture(r['sdk'], r['sdkCanonical'])
    dump(out / 'sdk-before.json', manifest)
    admission = dict(schema=1, scope=SCOPE, output=str(out), checkpoint=checkpoint,
        checkpointRole='BASE_ONLY; current bytes authoritative; prior c7 whole-tree proof HISTORICAL',
        startedUTC=started, deadlineUTC=deadline, recipe=r, roots=roots, witness=witness,
        tools=list(map(str, tools)), importedFiles=imports(), commands=plans(out, r),
        env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin', HOME=str(out / 'home'),
                 TMPDIR=str(out / 'tmp'), LANG='C', LC_ALL='C'),
        sdkSha256=sha(out / 'sdk-before.json'), budgetBefore=budget(out),
        toolPlanRole='e890 PATHS ONLY; fresh bytes; not historical source admission')
    dump(out / 'admission.json', admission)
    budget(out)  # Include the full witness itself BEFORE any native launch.
    check_admission(out, admission, executing=True)
    return admission


def check_admission(out, a, executing):
    need(a['schema'] == 1 and a['scope'] == SCOPE and a['output'] == str(out), 'admission schema/scope/output')
    v.window(a['startedUTC'], a['deadlineUTC'], time.time() if executing else None)
    need(a['recipe'] == recipe(), 'current recipe differs')
    need(a['commands'] == plans(out, a['recipe']), 'exact future command prefixes/roles/argv')
    need(a['roots'] == roots_for(out, a['recipe']), 'root scope differs')
    need(all(p in a['witness']['files'] for p in a['importedFiles']), 'import closure missing')
    need(a['env'] == dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin', HOME=str(out / 'home'),
         TMPDIR=str(out / 'tmp'), LANG='C', LC_ALL='C'), 'environment drift')
    need(sha(ROOT / 'source/core/StarStaticVector.hpp') == sha(HERE / 'StarStaticVector.original.hpp') == v.HEADER_SHA, 'current header mismatch')
    need(read(out / 'inputs/expected-cases.json') == v.model.expected_cases(), 'changed frozen case literals')
    for name, text in v.mutant_headers((HERE / 'StarStaticVector.original.hpp').read_text()).items():
        need((out / 'inputs' / (name + '.hpp')).read_text() == text, 'mutant source drift')
    need((out / 'inputs/initializer-assignment.cpp').read_text() == v.negative_source(), 'negative source drift')
    # Exact directory membership is replayed, not just existing hashes.
    tree = v.syntax.closure(map(Path, a['roots']))
    need(all(a['witness']['files'].get(p) == h for p, h in tree['files'].items()), 'unadmitted root file')
    need(all(a['witness']['aliases'].get(p) == h for p, h in tree['aliases'].items()), 'unadmitted alias')
    v.syntax.unchanged(a['witness'])
    v.syntax.subset([HERE / 'native.cpp', HERE / 'model.py', HERE / 'verify.py', HERE / 'run.py',
        ROOT / 'source/core/StarStaticVector.hpp', *a['importedFiles'], *a['tools'],
        *a['recipe']['objects']], a['witness'])
    need(sha(out / 'sdk-before.json') == a['sdkSha256'], 'SDK baseline changed')
    v.sdk.verify(read(out / 'sdk-before.json'), a['recipe']['sdk'], a['recipe']['sdkCanonical'])


def check_expansion(out, a):
    data = (out / 'link-expand.stderr').read_bytes()
    r = a['recipe']
    usr = Path(r['compiler']).resolve().parent.parent
    for path in (r['linker'], usr / 'lib/libLTO.dylib'):
        need(os.fsencode(str(path)) in data, 'actual expanded driver missing admitted linker/libLTO')
        v.syntax.subset([path], a['witness'])
    v.syntax.subset([usr / 'lib/libtapi.dylib'], a['witness'])


def command(out, a, plan):
    v.window(a['startedUTC'], a['deadlineUTC'], time.time())
    budget(out)
    v.syntax.unchanged(a['witness'])
    prefix = out / plan['name']
    need(not Path(str(prefix) + '.receipt.json').exists(), 'no reruns')
    argv = plan['argv']
    argv_files = v.argv_inputs(argv)
    began = utc()
    remaining = v.stamp(a['deadlineUTC']) - v.stamp(began)
    timeout = min(180, remaining)
    need(timeout > 0, 'original deadline')
    pending = []
    handlers = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    def defer(sig, frame):
        pending.append(sig)
    child = None
    timed = False
    with Path(str(prefix) + '.stdout').open('xb') as stdout, Path(str(prefix) + '.stderr').open('xb') as stderr:
        for sig in handlers:
            signal.signal(sig, defer)
        try:
            child = subprocess.Popen(argv, cwd=ROOT, env=a['env'], stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, start_new_session=True)
            dump(str(prefix) + '.started.json', dict(pid=child.pid, pgid=child.pid, startedUTC=began))
            stop = time.monotonic() + timeout
            next_cap = time.monotonic()
            while child.poll() is None:
                if time.monotonic() >= next_cap:
                    budget(out)
                    next_cap = time.monotonic() + 2
                if pending or time.monotonic() >= stop or time.time() >= v.stamp(a['deadlineUTC']):
                    timed = True
                    os.killpg(child.pid, signal.SIGKILL)
                    break
                time.sleep(0.05)
            child.wait()
        finally:
            if child is not None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
    try:
        os.killpg(child.pid, 0)
        gone = False
    except ProcessLookupError:
        gone = True
    row = dict(name=plan['name'], argv=argv, argvFiles=argv_files, cwd=str(ROOT), env=a['env'],
        stdin='DEVNULL', pid=child.pid, pgid=child.pid, startedUTC=began, endedUTC=utc(),
        timeoutSeconds=timeout, returncode=child.returncode, timedOut=timed, reaped=True, groupGone=gone,
        admissionSha256=sha(out / 'admission.json'), stdoutSha256=sha(str(prefix) + '.stdout'),
        stderrSha256=sha(str(prefix) + '.stderr'), budgetAfter=budget(out))
    dump(str(prefix) + '.receipt.json', row)
    v.receipt(plan, row, sha(out / 'admission.json'), a['startedUTC'], a['deadlineUTC'], v.stamp(a['startedUTC']))
    v.syntax.unchanged(a['witness'])
    print(plan['name'], child.pid, child.returncode, flush=True)
    if pending:
        raise InterruptedError('termination requested after owned child reaped')


def _execute_admitted(out, a, external_pin):
    need(sha(out / 'admission.json') == external_pin, 'external admission pin required')
    need(not (out / 'report.json').exists() and not list(out.glob('*.started.json')), 'fresh execution only')
    check_admission(out, a, executing=True)
    for plan in a['commands']:
        command(out, a, plan)
        name = plan['name']
        if name == 'link-expand':
            check_expansion(out, a)
        elif name.endswith('-compile'):
            v.syntax.subset(v.dependencies(out / (name.removesuffix('-compile') + '.d')), a['witness'])
        elif name == 'baseline-repeat':
            baseline = read(out / 'baseline-run.stdout')
            repeat = read(out / 'baseline-repeat.stdout')
            v.model.validate(baseline)
            v.model.validate(repeat)
            need(baseline == repeat, 'baseline repeat mismatch')
    v.diagnostic((out / 'initializer-assignment-negative.stderr').read_bytes())
    outputs = {p['name']: (out / (p['name'] + '.stdout')).read_bytes() for p in a['commands']}
    semantics = v.semantic_outputs(outputs)
    check_admission(out, a, executing=True)
    dump(out / 'sdk-after.json', v.sdk.capture(a['recipe']['sdk'], a['recipe']['sdkCanonical']))
    need(read(out / 'sdk-after.json') == read(out / 'sdk-before.json'), 'SDK after drift')
    for name in ('baseline', *v.MUTANTS):
        v.providers(out / (name + '.map'), name, out, a)
        paths = v.consumed_map(out / (name + '.map'))
        need(paths, 'actual link map SDK interfaces required')
        dump(out / (name + '.sdk-consumed.json'), v.sdk.reconcile_consumed(read(out / 'sdk-before.json'), paths,
             requested_root=a['recipe']['sdk'], expected_canonical_root=a['recipe']['sdkCanonical']))
    report = dict(status=v.STATUS, admissionSha256=external_pin, semantics=semantics,
        commands=[p['name'] for p in a['commands']],
        limits=['151 finite value cases only', 'generic lifetimes/events/reentry/ABI promotion pending',
                'original113 retained native objects; NOT current-game-source qualification',
                'prior c7 closed whole-tree epoch HISTORICAL, not waived or rebound'],
        products={str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()
                  and p.name not in ('report.json', 'acquisition.stdout', 'acquisition.stderr')})
    dump(out / 'report.json', report)
    budget(out)
    print('report', sha(out / 'report.json'), flush=True)


def execute(out, a, external_pin):
    need(sha(out / 'admission.json') == external_pin, 'external admission pin required')
    need(not (out / 'report.json').exists() and not list(out.glob('*.started.json')), 'fresh execution only')
    try:
        return _execute_admitted(out, a, external_pin)
    except BaseException as error:
        if not (out / 'failure.json').exists():
            dump(out / 'failure.json', dict(status='FAILED_NOT_RESUMABLE', error=str(error),
                allocationObservation=getattr(error, 'observation', None), admissionSha256=external_pin,
                finishedUTC=utc(), recordedReceipts=sorted(p.name for p in out.glob('*.receipt.json'))))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--started', required=True, help='original unit UTC start, not controller launch')
    parser.add_argument('--deadline', required=True, help='explicit original UTC deadline, <=35m from --started')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--prepare', action='store_true')
    group.add_argument('--execute', action='store_true')
    parser.add_argument('--admission-sha256')
    args = parser.parse_args()
    out = Path(args.output).absolute()
    need(out.resolve() == out, 'no output aliases')
    if args.execute:
        a = read(out / 'admission.json')
        need((a['checkpoint'], a['startedUTC'], a['deadlineUTC']) ==
             (args.checkpoint, args.started, args.deadline), 'no checkpoint/window renewal')
        execute(out, a, args.admission_sha256)
    else:
        a = prepare(out, args.checkpoint, args.started, args.deadline)
        print('admission', sha(out / 'admission.json'), flush=True)
        if not args.prepare:
            execute(out, a, sha(out / 'admission.json'))


if __name__ == '__main__':
    main()
