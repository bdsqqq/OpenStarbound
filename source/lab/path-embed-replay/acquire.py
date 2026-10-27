#!/usr/bin/env python3
"""Fresh native calibration using driver-first input witnesses.

This is a finite native acquisition, not a Rust or application gate. Required
membership is reconstructed from the configured recipe, never report keys.
Before/after snapshots do not detect transient edits or bind framework code.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = HERE.parent / 'path-embed'
BASE = ROOT / 'build/path-embed-native-witness-r1'
CANONICAL_SDK = '/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Explicit paths preserve the frozen modules' original __file__/ROOT contracts.
contract = load('contract', OLD / 'contract.py')
inventory = load('inventory', OLD / 'inventory.py')
closure = load('closure', OLD / 'closure.py')
native = load('path_embed_frozen_recipe', OLD / 'run.py')
import sdk_witness
import expanded_invocation
from archive_identity import arm64_archive_members
from link_trace import parse as parse_trace
from object_inventory import reconcile as reconcile_map


def need(value, message):
    if not value:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'))


def equal(a, b, message):
    # JSON spelling preserves bool/int/float distinctions recursively.
    need(encoded(a) == encoded(b), message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write('\n')


def hashes(paths):
    return {str(p): sha(p) for p in sorted(paths)}


def read_json(path):
    return json.loads(Path(path).read_bytes())


class Evidence:
    """Read actual isolated corruption files over an immutable acquisition.

    Overrides are only a verifier input transport: command membership, inputs,
    SDK membership and expanded-driver expectations still come from source.
    Normal replay uses no overrides. No acquisition files are overwritten.
    """
    def __init__(self, overrides=None):
        self.overrides = overrides or {}

    def data(self, path):
        return Path(self.overrides.get(str(path), path)).read_bytes()

    def json(self, path):
        return json.loads(self.data(path))

    def sha(self, path):
        return digest(self.data(path))

    def hashes(self, paths):
        return {str(p): self.sha(p) for p in sorted(paths)}


def safe_root(out, fresh=False):
    need(out.is_absolute() and out == Path(os.path.normpath(out)), 'normalized output')
    need(out.is_relative_to(BASE) and out != BASE, 'owned output root')
    need(not any(p.is_symlink() for p in (out, *out.parents)), 'output symlink')
    if fresh:
        need(not out.exists(), 'fresh generation required')
    elif out.exists():
        for directory, dirs, files in os.walk(out, followlinks=False):
            for name in dirs + files:
                p = Path(directory) / name
                st = p.lstat()
                need(not stat.S_ISLNK(st.st_mode), 'owned output symlink')
                need(stat.S_ISDIR(st.st_mode) or (stat.S_ISREG(st.st_mode) and st.st_nlink == 1),
                     'owned output nonregular/hardlink')


def environment(out):
    return {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(out / 'home'),
            'TMPDIR': str(out / 'tmp'), 'LANG': 'C', 'LC_ALL': 'C'}


def tool_binding(path):
    canonical, hops = sdk_witness._resolve(str(path))
    return {'requested': str(path), 'canonical': canonical, 'hops': hops,
            **sdk_witness._digest(canonical)}


def invoke(out, name, argv, stdin=b''):
    argv = list(map(str, argv))
    before = tool_binding(argv[0])
    p = subprocess.run(argv, cwd=native.CM, env=environment(out), input=stdin,
                       capture_output=True, timeout=120)
    for suffix, data in [('stdout', p.stdout), ('stderr', p.stderr)]:
        with (out / (name + '.' + suffix)).open('xb') as stream:
            stream.write(data)
    q = {'name': name, 'argv': argv, 'cwd': str(native.CM), 'environment': environment(out),
         'tool_before': before, 'tool_after': tool_binding(argv[0]),
         'stdin': {'size': len(stdin), 'sha256': digest(stdin)},
         'stdout': digest(p.stdout), 'stderr': digest(p.stderr),
         'exit': p.returncode, 'exit_type': 'normal' if p.returncode >= 0 else 'signal'}
    write(out / (name + '.command.json'), q)
    equal(q['tool_before'], q['tool_after'], 'invocation tool drift')
    need(type(p.returncode) is int and p.returncode == 0, 'command failed: ' + name)
    return q


def recipe(out):
    rs, libs = native.recipe()
    jobs = native.sources(out, rs)
    need(len(jobs) == 121, '121 fresh translation units')
    sdk_roots = {f[i + 1] for _, _, f, _ in jobs for i, x in enumerate(f) if x == '-isysroot'}
    need(len(sdk_roots) == 1, 'one recipe SDK')
    sdk = next(iter(sdk_roots))
    old_plan = native.plans(out, rs, libs)
    plan = []
    links = {}
    for name, argv in old_plan:
        if name.startswith('link-'):
            variant = name[5:]
            target = out / 'links' / variant
            argv = [('-Wl,-map,' + str(target / 'native.map')) if a.startswith('-Wl,-map,')
                    else (str(target / 'native') if a == str(out / variant) else a) for a in argv]
            argv += ['-Wl,-t,-trace_implicit_libraries']
            plan.append(('expand-' + variant, [argv[0], '-###', *argv[1:]]))
            plan.append((name, argv))
            links[variant] = argv
        elif name in native.RUNS:
            plan.append((name, [str(out / 'links' / name.removesuffix('-repeat') / 'native')]))
        else:
            plan.append((name, argv))
    return rs, libs, jobs, sdk, plan, links


def inputs(out, rs, libs):
    result = native.initial_paths(out, rs, libs)
    result |= {p.resolve() for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    result.add(HERE.parent / 'native_artifacts.py')
    # Include public declaration even if future dependency output omits it.
    result.add(ROOT / 'source/core/StarPathEmbed.hpp')
    return result


def dependencies(out, jobs, evidence=None):
    evidence = evidence or Evidence()
    result = set()
    for name, _, flags, source in jobs:
        result |= closure.dependencies(evidence.data(out / (name + '.d')), source, flags, native.CM)
    return result


def expanded(out, variant, evidence=None):
    evidence = evidence or Evidence()
    lines = evidence.data(out / ('expand-' + variant + '.stderr')).decode().splitlines()
    commands = [shlex.split(line) for line in lines if line.lstrip().startswith('"')]
    need(len(commands) == 1, 'one expanded linker command')
    return commands[0]


def link_reconcile(out, variant, sdk_before, sdk, argv, evidence=None):
    evidence = evidence or Evidence()
    target = out / 'links' / variant
    expansion = expanded(out, variant, evidence)
    bound = evidence.json(target / 'expanded-before.json')
    expanded_invocation.verify(bound, expansion)
    inv = expanded_invocation.parse(expansion)
    equal(inv['architecture'], 'arm64', 'link architecture')
    need(inv['platform'][0] == 'macos' and inv['sdk'] == sdk, 'link platform/SDK')
    equal(inv['outputs'], [str(target / 'native'), str(target / 'native.map')], 'link outputs')
    blobs = {p.encode(): Path(p).read_bytes() for p in inv['file_inputs'] if p.endswith('.a')}
    tables = {p: b''.join(m['name'] + b'\n' for m in arm64_archive_members(blob)) for p, blob in blobs.items()}
    equal(evidence.json(target / 'archive-tables.json'), {p.hex(): t.hex() for p, t in tables.items()}, 'archive tables')
    objects = [p.encode() for p in inv['file_inputs'] if p.endswith('.o')]
    # Independently reconstruct object membership from the original driver recipe.
    need(objects == [p.encode() for p in argv if p.endswith('.o')], 'expanded object membership')
    trace = parse_trace(evidence.data(out / ('link-' + variant + '.stdout')), objects, tables)
    mapped = reconcile_map(evidence.data(target / 'native.map'), objects, tables, blobs)
    paths = trace['sdk_paths'] + mapped['unresolved_origins']
    paths += [r['source'] for r in trace['indirect_declarations']]
    consumed = sdk_witness.reconcile_consumed(sdk_before, [os.fsdecode(p) for p in paths],
                       requested_root=sdk, expected_canonical_root=CANONICAL_SDK)
    equal(evidence.json(target / 'sdk-before.json'), sdk_before, 'per-link initial SDK coherence')
    equal(evidence.json(target / 'sdk-after.json'), sdk_before, 'per-link final SDK coherence')
    equal(evidence.json(target / 'consumed.json'), consumed, 'SDK consumed closure')
    return {'standalone_objects': len(objects), 'loaded_archive_members': len(trace['archive_members']),
            'map_archive_members': len(mapped['used_archive_members']), 'sdk_records': len(consumed),
            'expanded_files': len(inv['file_inputs'])}


def acquire_link(out, variant, argv, sdk_before, sdk):
    target = out / 'links' / variant
    target.mkdir(parents=True)
    before = sdk_witness.capture(sdk, CANONICAL_SDK)
    equal(before, sdk_before, 'SDK drift before link')
    write(target / 'sdk-before.json', before)
    invoke(out, 'expand-' + variant, [argv[0], '-###', *argv[1:]])
    expansion = expanded(out, variant)
    bound = expanded_invocation.bind(expansion)
    write(target / 'expanded-before.json', bound)
    blobs = {p.encode(): Path(p).read_bytes() for p in bound['inventory']['file_inputs'] if p.endswith('.a')}
    tables = {p: b''.join(m['name'] + b'\n' for m in arm64_archive_members(b)) for p, b in blobs.items()}
    write(target / 'archive-tables.json', {p.hex(): t.hex() for p, t in tables.items()})
    invoke(out, 'link-' + variant, argv)
    expanded_invocation.verify(bound, expansion)
    objects = [p.encode() for p in bound['inventory']['file_inputs'] if p.endswith('.o')]
    trace = parse_trace((out / ('link-' + variant + '.stdout')).read_bytes(), objects, tables)
    mapped = reconcile_map((target / 'native.map').read_bytes(), objects, tables, blobs)
    paths = trace['sdk_paths'] + mapped['unresolved_origins'] + [r['source'] for r in trace['indirect_declarations']]
    write(target / 'consumed.json', sdk_witness.reconcile_consumed(before, [os.fsdecode(p) for p in paths],
                 requested_root=sdk, expected_canonical_root=CANONICAL_SDK))
    after = sdk_witness.capture(sdk, CANONICAL_SDK)
    equal(after, before, 'SDK drift during link')
    write(target / 'sdk-after.json', after)
    print('linked', variant, flush=True)


def artifact_paths(out, jobs, plan, links):
    result = {out / n for n in ('inputs.tsv', 'recipes.json', 'libraries.json', 'initial.json',
              'before.json', 'after.json', 'sdk-initial.json', 'sdk-final.json', 'preexecute.json',
              'commands.json', 'expected.tsv')}
    result |= {out / (n + '.cpp') for n in native.MUTATIONS}
    result |= {out / (n + ext) for n, _, _, _ in jobs for ext in ('.o', '.d')}
    result |= {out / (n + '.' + ext) for n, _ in plan for ext in ('stdout', 'stderr', 'command.json')}
    result |= {out / 'links' / v / n for v in links for n in ('native', 'native.map',
               'sdk-before.json', 'sdk-after.json', 'expanded-before.json', 'archive-tables.json', 'consumed.json')}
    return result


def preexecute_paths(out, artifacts):
    remove = {out / n for n in ('after.json', 'sdk-final.json', 'preexecute.json', 'commands.json', 'expected.tsv')}
    remove |= {out / (n + '.' + ext) for n in native.RUNS for ext in ('stdout', 'stderr', 'command.json')}
    return artifacts - remove


def replay_dependencies(out, plan, jobs, evidence):
    """Recompute required headers from recipe, not just a supplied .d list.

    -MF - routes dependency output to stdout; the frozen acquisition and its
    fixtures stay untouched. All invocations retain the six-process bound.
    """
    def replay(item):
        name, argv = item
        argv = list(argv)
        argv[argv.index('-MF') + 1] = '-'
        before = tool_binding(argv[0])
        result = subprocess.run(argv, cwd=native.CM, env=environment(out), input=b'',
                                capture_output=True, timeout=120)
        equal(before, tool_binding(argv[0]), 'dependency replay tool drift')
        need(type(result.returncode) is int and result.returncode == 0, 'dependency replay normal exit')
        need(result.stdout == evidence.data(out / (name.removeprefix('deps-') + '.d')),
             'independent dependency output')
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(replay, plan[:len(jobs)]))


def verify(out, q=None, evidence=None):
    evidence = evidence or Evidence()
    safe_root(out)
    inventory.check()
    if q is None:
        q = evidence.json(out / 'report.json')
    equal({k: q[k] for k in ('status', 'objects', 'definitions', 'observations')},
          {'status': 'FINITE_NATIVE_PATHEMBED_WITNESS_CORE_PASS', 'objects': 113, 'definitions': 2, 'observations': 357}, 'scope')
    rs, libs, jobs, sdk, plan, links = recipe(out)
    equal(evidence.json(out / 'recipes.json'), rs, 'recipes')
    equal(evidence.json(out / 'libraries.json'), libs, 'libraries')
    need(evidence.data(out / 'inputs.tsv') == contract.inputs(), 'independent input bytes')
    original = (OLD / 'original/StarPathEmbed.cpp').read_text()
    for name, (a, b) in native.MUTATIONS.items():
        need(evidence.data(out / (name + '.cpp')).decode() == original.replace(a, b), 'mutant source')
    initial = evidence.hashes(inputs(out, rs, libs))
    equal(initial, evidence.json(out / 'initial.json'), 'initial inputs/source closure')
    paths = inputs(out, rs, libs) | dependencies(out, jobs, evidence)
    snapshots = native.snapshot_paths(paths, out)
    for dest, source in snapshots.items():
        need(evidence.sha(dest) == evidence.sha(source), 'source snapshot')
    paths |= set(snapshots)
    binding = evidence.hashes(paths)
    for baseline in (q['bindings'], evidence.json(out / 'before.json'), evidence.json(out / 'after.json')):
        equal(binding, baseline, 'required binding/dependency membership')
    artifacts = artifact_paths(out, jobs, plan, links)
    equal(evidence.hashes(artifacts), q['artifacts'], 'required artifact membership/bytes')
    equal(evidence.hashes(preexecute_paths(out, artifacts)), evidence.json(out / 'preexecute.json'), 'preexecution artifact closure')
    equal(q['commands'], evidence.json(out / 'commands.json'), 'command collection')
    equal([(c['name'], c['argv']) for c in q['commands']], plan, 'required command argv membership')
    for c, (name, argv) in zip(q['commands'], plan):
        equal(c, evidence.json(out / (name + '.command.json')), 'command receipt')
        stdin = contract.inputs() if name in native.RUNS else b''
        expected = {'name': name, 'argv': argv, 'cwd': str(native.CM), 'environment': environment(out),
                    'tool_before': tool_binding(argv[0]), 'tool_after': tool_binding(argv[0]),
                    'stdin': {'size': len(stdin), 'sha256': digest(stdin)},
                    'stdout': evidence.sha(out / (name + '.stdout')), 'stderr': evidence.sha(out / (name + '.stderr')),
                    'exit': 0, 'exit_type': 'normal'}
        equal(c, expected, 'invocation identity/normal exit/stdin/environment')
    replay_dependencies(out, plan, jobs, evidence)
    sdk_before = evidence.json(out / 'sdk-initial.json')
    sdk_witness.verify(sdk_before, sdk, CANONICAL_SDK)
    equal(evidence.json(out / 'sdk-final.json'), sdk_before, 'global SDK before/after')
    summaries = {}
    for variant, argv in links.items():
        # Print-only replay reconstructs the expanded inputs independently.
        tool_before = tool_binding(argv[0])
        p = subprocess.run([argv[0], '-###', *argv[1:]], cwd=native.CM,
                           env=environment(out), input=b'', capture_output=True, timeout=30)
        need(type(p.returncode) is int and p.returncode == 0, 'replay driver expansion')
        equal(tool_before, tool_binding(argv[0]), 'expansion replay tool drift')
        commands = [shlex.split(line) for line in p.stderr.decode().splitlines() if line.lstrip().startswith('"')]
        equal(commands, [expanded(out, variant, evidence)], 'independent driver expansion')
        summaries[variant] = link_reconcile(out, variant, sdk_before, sdk, argv, evidence)
    equal(q['links'], summaries, 'link summary')
    for variant in native.VARIANTS:
        symbols = evidence.data(out / ('symbols-' + variant + '.stdout')).decode()
        definitions = [line for line in symbols.splitlines() if ' T Star::embed' in line]
        need(len(definitions) == 2 and any('embedEscapeText(' in x for x in definitions)
             and any('embedAndCompressData(' in x for x in definitions), 'two compiled functions')
        need('Star::EmbeddedCompressionMethodNames' in symbols, 'compiled enum map')
    leaf = evidence.data(out / 'leaf.stdout')
    need(leaf == evidence.data(out / 'leaf-repeat.stdout'), 'leaf repeat')
    expected = contract.expected(leaf)
    need(len(expected.splitlines()) == 357 and evidence.data(out / 'expected.tsv') == expected, 'independent expected rows')
    for name in ('original', 'original-repeat', 'current', 'current-repeat'):
        contract.check(evidence.data(out / (name + '.stdout')), expected)
    for name in native.MUTATIONS:
        try:
            contract.check(evidence.data(out / (name + '.stdout')), expected)
        except ValueError:
            pass
        else:
            raise ValueError('normal semantic mutant escaped: ' + name)
    equal(evidence.hashes(paths), binding, 'verification input drift')
    equal(evidence.hashes(artifacts), q['artifacts'], 'verification artifact drift')
    sdk_witness.verify(sdk_before, sdk, CANONICAL_SDK)
    return q


def run(out):
    safe_root(out, fresh=True)
    out.mkdir(parents=True)
    (out / 'home').mkdir()
    (out / 'tmp').mkdir()
    inventory.check()
    native.materialize(out)
    rs, libs, jobs, sdk, plan, links = recipe(out)
    write(out / 'recipes.json', rs)
    write(out / 'libraries.json', libs)
    initial = hashes(inputs(out, rs, libs))
    write(out / 'initial.json', initial)
    sdk_before = sdk_witness.capture(sdk, CANONICAL_SDK)
    write(out / 'sdk-initial.json', sdk_before)
    nj = len(jobs)
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda item: invoke(out, *item), plan[:nj]))
    equal(hashes(inputs(out, rs, libs)), initial, 'dependency scan source drift')
    paths = inputs(out, rs, libs) | dependencies(out, jobs)
    snapshots = native.snapshot_paths(paths, out)
    for dest, source in snapshots.items():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream:
            stream.write(source.read_bytes())
    paths |= set(snapshots)
    before = hashes(paths)
    write(out / 'before.json', before)
    print('frozen', len(before), 'bindings; compiling', nj, 'fresh units', flush=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda item: invoke(out, *item), plan[nj:2 * nj]))
    for variant, argv in links.items():
        acquire_link(out, variant, argv, sdk_before, sdk)
    for name, argv in plan[2 * nj:]:
        if name.startswith(('symbols-', 'archive-')):
            invoke(out, name, argv)
    artifacts = artifact_paths(out, jobs, plan, links)
    write(out / 'preexecute.json', hashes(preexecute_paths(out, artifacts)))
    equal(hashes(paths), before, 'preexecution input drift')
    for name, argv in plan:
        if name in native.RUNS:
            invoke(out, name, argv, contract.inputs())
    expected = contract.expected((out / 'leaf.stdout').read_bytes())
    with (out / 'expected.tsv').open('xb') as stream:
        stream.write(expected)
    after = hashes(paths)
    equal(before, after, 'acquisition input drift')
    write(out / 'after.json', after)
    sdk_after = sdk_witness.capture(sdk, CANONICAL_SDK)
    equal(sdk_after, sdk_before, 'acquisition SDK drift')
    write(out / 'sdk-final.json', sdk_after)
    commands = [read_json(out / (name + '.command.json')) for name, _ in plan]
    write(out / 'commands.json', commands)
    q = {'status': 'FINITE_NATIVE_PATHEMBED_WITNESS_CORE_PASS', 'objects': 113, 'definitions': 2,
         'observations': len(expected.splitlines()), 'bindings': before, 'commands': commands,
         'artifacts': hashes(artifacts),
         'links': {v: link_reconcile(out, v, sdk_before, sdk, a) for v, a in links.items()}}
    # Raw candidate is retained on audit failure and NEVER pass-labelled report.
    write(out / 'candidate.json', {**q, 'status': 'RAW_ACQUISITION_PENDING_INDEPENDENT_VERIFY'})
    verify(out, q)
    write(out / 'report.json', q)
    print(q['status'], sha(out / 'report.json'), flush=True)


def controls(out):
    """Actual report/file clones pass through the SAME positive verifier.

    Each file clone has coherently updated artifact/preexecution digests. This
    challenges semantic reconstruction beyond a stale producer hash. Original
    artifacts and external SDK/toolchain inputs are never changed.
    """
    q = verify(out)
    target = out / 'controls'
    target.mkdir()
    rs, libs, jobs, sdk, plan, links = recipe(out)
    dep = next(p for p in q['bindings'] if p.endswith('.h') and '.sdk/' in p)
    source = str(ROOT / 'source/core/StarPathEmbed.cpp')
    checks = [
        ('binding-omission', lambda b: b['bindings'].pop(source)),
        ('dependency-omission', lambda b: b['bindings'].pop(dep)),
        ('source-omission', lambda b: b['bindings'].pop(str(Path(__file__).resolve()))),
        ('expected-artifact-omission', lambda b: b['artifacts'].pop(str(out / 'expected.tsv'))),
        ('object-omission', lambda b: b['artifacts'].pop(str(out / '0.o'))),
        ('SDK-omission', lambda b: b['artifacts'].pop(str(out / 'sdk-initial.json'))),
        ('expanded-inputs-omission', lambda b: b['artifacts'].pop(str(out / 'links/original/expanded-before.json'))),
        ('argv-omission', lambda b: b['commands'][0]['argv'].pop()),
        ('bool-exit', lambda b: b['commands'][0].update(exit=False)),
        ('bool-count', lambda b: b.update(definitions=True)),
        ('float-count', lambda b: b.update(objects=113.0)),
    ]
    results = []
    for name, mutate in checks:
        bad = copy.deepcopy(q)
        mutate(bad)
        path = target / (name + '.json')
        write(path, bad)
        try:
            verify(out, read_json(path))
        except ValueError as exc:
            results.append({'name': name, 'status': 'REJECTED', 'reason': str(exc), 'sha256': sha(path)})
        else:
            raise ValueError('corruption control escaped: ' + name)

    def file_control(name, changes, mutate_report=None):
        directory = target / name
        directory.mkdir()
        bad = copy.deepcopy(q)
        if mutate_report:
            mutate_report(bad)
        overrides = {}
        for i, (logical, value) in enumerate(changes.items()):
            actual = directory / ('file-' + str(i))
            actual.write_bytes(value)
            overrides[str(logical)] = str(actual)
        view = Evidence(overrides)
        # Preexecution manifest is itself an artifact; retain its independently
        # required membership while updating changed cloned file digests.
        pre = read_json(out / 'preexecute.json')
        for logical in overrides:
            if logical in pre:
                pre[logical] = view.sha(logical)
        actual = directory / 'preexecute.json'
        write(actual, pre)
        overrides[str(out / 'preexecute.json')] = str(actual)
        for logical in overrides:
            need(logical in bad['artifacts'], 'control overrides required artifact only')
            bad['artifacts'][logical] = view.sha(logical)
        report_path = directory / 'report.json'
        write(report_path, bad)
        write(directory / 'overrides.json', overrides)
        try:
            verify(out, read_json(report_path), view)
        except ValueError as exc:
            result = {'name': name, 'status': 'REJECTED', 'reason': str(exc),
                      'report_sha256': sha(report_path), 'files': hashes({Path(p) for p in overrides.values()})}
            results.append(result)
            write(directory / 'rejection.json', result)
            print('rejected', name, str(exc), flush=True)
        else:
            raise ValueError('coherent file control escaped: ' + name)

    file_control('expected-row-omission', {out / 'expected.tsv': (out / 'expected.tsv').read_bytes().split(b'\n', 1)[1]})
    for label, predicate in [('runtime-omission', lambda p: p.endswith('libclang_rt.osx.a')),
                             ('plugin-omission', lambda p: p.endswith('libLTO.dylib'))]:
        path = out / 'links/original/expanded-before.json'
        value = read_json(path)
        removed = [p for p in value['inventory']['file_inputs'] if predicate(p)]
        need(len(removed) == 1, 'actual control target ' + label)
        value['inventory']['file_inputs'].remove(removed[0])
        value['files'] = [r for r in value['files'] if r['requested'] != removed[0]]
        file_control(label, {path: encoded(value).encode()})

    map_path = out / 'links/original/native.map'
    map_data = map_path.read_bytes()
    rows = map_data.splitlines(keepends=True)
    object_row = next(row for row in rows if row.startswith(b'[') and str(out / '0.o').encode() in row)
    file_control('missing-link-origin', {map_path: map_data.replace(object_row, b'', 1)})
    file_control('foreign-link-origin', {map_path: map_data.replace(str(out / '0.o').encode(), b'/foreign/input.o', 1)})
    sdk_row = next(row for row in rows if row.startswith(b'[') and b'.tbd' in row)
    prefix = sdk_row[:sdk_row.index(b']') + 1]
    file_control('unbound-SDK-path', {map_path: map_data.replace(sdk_row, prefix + b' ' + sdk.encode() + b'/usr/lib/libUNBOUND.tbd\n', 1)})
    manifest = read_json(out / 'sdk-initial.json')
    manifest['interfaces'][0]['sha256'] = '0' * 64
    manifests = [out / n for n in ('sdk-initial.json', 'sdk-final.json')]
    manifests += [out / 'links' / v / n for v in links for n in ('sdk-before.json', 'sdk-after.json')]
    file_control('coherent-SDK-manifest-change', {p: encoded(manifest).encode() for p in manifests})

    name = plan[0][0]
    receipt = read_json(out / (name + '.command.json'))
    receipt['exit'] = False
    commands = copy.deepcopy(q['commands'])
    commands[0] = receipt
    file_control('coherent-bool-exit', {out / (name + '.command.json'): encoded(receipt).encode(),
                  out / 'commands.json': encoded(commands).encode()}, lambda b: b.update(commands=commands))

    write(target / 'results.json', {'status': 'FINITE_NATIVE_WITNESS_CORRUPTION_CONTROLS_PASS', 'results': results,
          'limits': ['file overlays are retained verifier inputs, not executions of corrupted binaries',
                     'no framework implementation, transient-edit, performance or universal equivalence proof']})
    print(len(results), 'normal clone rejections', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['run', 'verify', 'controls'])
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).absolute()
    if args.phase == 'run':
        run(output)
    elif args.phase == 'verify':
        print(verify(output)['status'])
    else:
        controls(output)
