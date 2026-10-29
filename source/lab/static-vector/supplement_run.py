#!/usr/bin/env python3
"""Fresh bounded native supplement admission; reuses current supervisor, never old receipts."""
import argparse
import json
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import supplement_verify as t

v = t.v
base = v.load('_static_vector_supplement_supervisor', HERE / 'run.py')
ROOT = v.ROOT
SCOPE = 'finite native StaticVector bounded mutation and lifetime supplement; no Rust or game'


def plans(out, r):
    flags = [*r['flags'], '-I' + str(HERE), '-DStaticVector=StaticVectorCharacterization']
    result = []
    def add(name, argv, expected=0):
        result.append(dict(name=name, argv=list(map(str, argv)), expected=expected))
    for role in ('baseline', *t.MUTANTS):
        header = HERE / 'StarStaticVector.original.hpp' if role == 'baseline' else out / 'inputs' / (role + '.hpp')
        add(role + '-compile', [r['compiler'], *flags, '-DSTATIC_VECTOR_TEST_HEADER="' + str(header) + '"',
            '-MD', '-MF', out / (role + '.d'), '-c', HERE / 'supplement.cpp', '-o', out / (role + '.o')])
        link = [r['compiler'], *r['flags'], *r['linkFlags'], *r['objects'], out / (role + '.o'),
                *r['libraries'], '-Wl,-dead_strip', '-Wl,-map,' + str(out / (role + '.map')),
                '-Wl,-t,-trace_implicit_libraries', '-o', out / role]
        if role == 'baseline':
            add('link-expand', [r['compiler'], '-###', *link[1:]])
        add(role + '-link', link)
        add(role + '-run', [out / role])
        if role == 'baseline':
            add('baseline-repeat', [out / role])
    v.need(len(result) == len({p['name'] for p in result}) == 14, 'exact14 supplement commands')
    return result


def imports():
    return sorted(set(base.imports()) | {str(Path(p).resolve()) for p in
        (t.__file__, t.model.__file__, __file__, base.__file__)})


def prepare(out, checkpoint, started, deadline):
    v.window(started, deadline, time.time())
    v.need(re.fullmatch('[0-9a-f]{40}', checkpoint) is not None, 'full checkpoint required')
    v.need(out.is_relative_to(ROOT / 'build') and not out.exists(), 'fresh owned root only')
    v.need(v.sha(ROOT / 'source/core/StarStaticVector.hpp') == v.sha(HERE / 'StarStaticVector.original.hpp') == v.HEADER_SHA, 'raw header')
    out.mkdir(parents=True)
    for name in ('inputs', 'home', 'tmp'):
        (out / name).mkdir()
    for name, raw in t.mutant_headers((HERE / 'StarStaticVector.original.hpp').read_text()).items():
        (out / 'inputs' / (name + '.hpp')).write_text(raw)
    base.dump(out / 'inputs/expected-cases.json', t.model.expected_cases())
    r = base.recipe()
    roots = base.roots_for(out, r)
    witness = v.syntax.closure(map(Path, roots))
    usr = Path(r['compiler']).resolve().parent.parent
    tools = [r['compiler'], r['linker'], usr / 'bin/clang', usr / 'lib/libLTO.dylib', usr / 'lib/libtapi.dylib', sys.executable]
    files = [*r['objects'], *[x for x in r['libraries'] if Path(x).is_absolute() and Path(x).is_file()],
             *[Path(r['cm']) / x for x in ('build.ninja', 'CMakeCache.txt', 'compile_commands.json')],
             base.TOOL_PLAN, *imports(), *tools]
    base.pin(witness, files)
    base.dump(out / 'sdk-before.json', v.sdk.capture(r['sdk'], r['sdkCanonical']))
    a = dict(schema=1, scope=SCOPE, output=str(out), checkpoint=checkpoint,
        checkpointRole='BASE_ONLY; current bytes authoritative; prior tree proofs HISTORICAL',
        startedUTC=started, deadlineUTC=deadline, recipe=r, roots=roots, witness=witness,
        tools=list(map(str, tools)), importedFiles=imports(), commands=plans(out, r),
        env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin', HOME=str(out / 'home'), TMPDIR=str(out / 'tmp'), LANG='C', LC_ALL='C'),
        sdkSha256=v.sha(out / 'sdk-before.json'), budgetBefore=base.budget(out),
        toolPlanRole='e890 PATHS ONLY; fresh SDK/source/tool bytes, not old admission')
    base.dump(out / 'admission.json', a)
    base.budget(out)
    check_admission(out, a, executing=True)
    return a


def check_admission(out, a, executing):
    v.need(a['schema'] == 1 and a['scope'] == SCOPE and a['output'] == str(out), 'trace admission scope')
    v.window(a['startedUTC'], a['deadlineUTC'], time.time() if executing else None)
    v.need(a['recipe'] == base.recipe() and a['commands'] == plans(out, a['recipe']), 'recipe/argv drift')
    v.need(a['roots'] == base.roots_for(out, a['recipe']), 'root scope drift')
    v.need(a['env'] == dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin', HOME=str(out / 'home'), TMPDIR=str(out / 'tmp'), LANG='C', LC_ALL='C'), 'environment drift')
    v.need(all(p in a['witness']['files'] for p in a['importedFiles']), 'import closure')
    v.need(v.sha(ROOT / 'source/core/StarStaticVector.hpp') == v.sha(HERE / 'StarStaticVector.original.hpp') == v.HEADER_SHA, 'raw identity drift')
    v.need(v.read(out / 'inputs/expected-cases.json') == t.model.expected_cases(), 'event literal drift')
    expected = t.mutant_headers((HERE / 'StarStaticVector.original.hpp').read_text())
    v.need({p.name for p in (out / 'inputs').iterdir()} == {*(n + '.hpp' for n in expected), 'expected-cases.json'}, 'exact staged membership')
    for n, raw in expected.items():
        v.need((out / 'inputs' / (n + '.hpp')).read_text() == raw, 'mutant drift')
    tree = v.syntax.closure(map(Path, a['roots']))
    for k in ('files', 'aliases'):
        v.need(all(a['witness'][k].get(p) == h for p, h in tree[k].items()), 'unadmitted root ' + k)
    v.syntax.unchanged(a['witness'])
    v.syntax.subset([HERE / 'supplement.cpp', HERE / 'supplement_model.py', *imports(), *a['tools'], *a['recipe']['objects']], a['witness'])
    v.need(v.sha(out / 'sdk-before.json') == a['sdkSha256'], 'SDK baseline drift')
    v.sdk.verify(v.read(out / 'sdk-before.json'), a['recipe']['sdk'], a['recipe']['sdkCanonical'])


def execute(out, a, pin):
    v.need(v.sha(out / 'admission.json') == pin, 'external admission pin required')
    v.need(not (out / 'report.json').exists() and not (out / 'failure.json').exists()
           and not list(out.glob('*.started.json')), 'fresh native execution only')
    try:
        check_admission(out, a, executing=True)
        for plan in a['commands']:
            base.command(out, a, plan)
            name = plan['name']
            if name == 'link-expand':
                base.check_expansion(out, a)
            elif name.endswith('-compile'):
                v.syntax.subset(v.dependencies(out / (name.removesuffix('-compile') + '.d')), a['witness'])
            elif name == 'baseline-repeat':
                first, repeat = [v.read(out / (n + '.stdout')) for n in ('baseline-run', 'baseline-repeat')]
                t.model.validate(first)
                t.model.validate(repeat)
                v.need(first == repeat, 'baseline repeat gate BEFORE mutant acquisitions')
        outputs = {p['name']: (out / (p['name'] + '.stdout')).read_bytes() for p in a['commands']}
        semantics = t.semantic_outputs(outputs)
        check_admission(out, a, executing=True)
        base.dump(out / 'sdk-after.json', v.sdk.capture(a['recipe']['sdk'], a['recipe']['sdkCanonical']))
        v.need(v.read(out / 'sdk-before.json') == v.read(out / 'sdk-after.json'), 'SDK after drift')
        for role in ('baseline', *t.MUTANTS):
            v.providers(out / (role + '.map'), role, out, a)
            paths = v.consumed_map(out / (role + '.map'))
            v.need(paths, 'actual SDK map paths required')
            base.dump(out / (role + '.sdk-consumed.json'), v.sdk.reconcile_consumed(v.read(out / 'sdk-before.json'), paths,
                requested_root=a['recipe']['sdk'], expected_canonical_root=a['recipe']['sdkCanonical']))
        base.dump(out / 'report.json', dict(status=t.STATUS, admissionSha256=pin, semantics=semantics,
            commands=[p['name'] for p in a['commands']], limits=['17 finite bounded mutation/lifetime traces only; no Rust or game',
                'current-ABI alignment and defined explicit-pop throw only; no exhaustive generic or platform claim',
                'original113 native object providers; old game/source-tree evidence HISTORICAL, not rebound'],
            products={str(p.relative_to(out)): v.sha(p) for p in out.rglob('*') if p.is_file()
                and p.name not in ('report.json', 'acquisition.stdout', 'acquisition.stderr')}))
        base.budget(out)
        print('report', v.sha(out / 'report.json'), flush=True)
    except BaseException as error:
        base.dump(out / 'failure.json', dict(status='FAILED_NOT_RESUMABLE', error=str(error),
            admissionSha256=pin, allocationObservation=getattr(error, 'observation', None),
            finishedUTC=base.utc(), recordedReceipts=sorted(p.name for p in out.glob('*.receipt.json'))))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--checkpoint', required=True)
    p.add_argument('--started', required=True)
    p.add_argument('--deadline', required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', action='store_true')
    group.add_argument('--execute', action='store_true')
    p.add_argument('--admission-sha256')
    args = p.parse_args()
    out = Path(args.output).absolute()
    v.need(out.resolve() == out, 'physical owned output path')
    if args.prepare:
        prepare(out, args.checkpoint, args.started, args.deadline)
        print('admission', v.sha(out / 'admission.json'), flush=True)
    else:
        a = v.read(out / 'admission.json')
        v.need((a['checkpoint'], a['startedUTC'], a['deadlineUTC']) == (args.checkpoint, args.started, args.deadline), 'no window/checkpoint renewal')
        execute(out, a, args.admission_sha256)
