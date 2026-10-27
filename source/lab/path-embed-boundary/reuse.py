"""Reconstruct accepted native input membership before borrowing old objects."""
import copy
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'source/lab/path-embed-replay'))
import acquire as a
OLD=ROOT/'build/path-embed-native-witness-r1/generation-2'

def reconstruct():
    rs,libs,jobs,sdk,plan,links=a.recipe(OLD)
    deps=a.dependencies(OLD,jobs)
    paths=a.inputs(OLD,rs,libs)|deps
    paths|=set(a.native.snapshot_paths(paths,OLD))
    paths|=a.artifact_paths(OLD,jobs,plan,links)|{OLD/'report.json'}
    bindings={tuple(a.expanded(OLD,v)):a.expanded_invocation.bind(a.expanded(OLD,v)) for v in links}
    paths|={Path(r[k]) for b in bindings.values() for r in b['files'] for k in ('requested','canonical')}
    return (rs,libs,jobs,sdk,plan,links,deps,paths,bindings)

def verify_reuse(dest):
    a.need(a.sha(OLD/'report.json')=='11a387b7e08758d3715029dcbaf294dc11a9c87528d5397f5a68c37a2b297f5f','accepted core report identity')
    a.need(a.sha(ROOT/'build/path-embed-native-witness-r1/parent-acceptance-r2/report.json')=='e06632fa0e8f32c086ba3ddd57aed6b81756f73f6db859810d630145dfd55595','accepted parent identity')
    state=reconstruct();rs,libs,jobs,sdk,plan,links,deps,paths,bindings=state
    before=a.hashes(paths);sdk_before=a.sdk_witness.capture(sdk,a.CANONICAL_SDK)
    a.write(dest/'reuse-before.json',before);a.write(dest/'reuse-sdk-before.json',sdk_before)
    real_deps,real_capture,real_bind=a.dependencies,a.sdk_witness.capture,a.expanded_invocation.bind
    # Only actual immutable pure reads are memoized; all semantic validation,
    # source-derived membership, command replay and dependency rescans stay live.
    def cached_deps(out,js,evidence=None):
        a.need(out==OLD and js==jobs and not (evidence and evidence.overrides),'cache scope')
        return set(deps)
    a.dependencies=cached_deps
    a.sdk_witness.capture=lambda r,c:copy.deepcopy(sdk_before) if (r,c)==(sdk,a.CANONICAL_SDK) else real_capture(r,c)
    a.expanded_invocation.bind=lambda argv:copy.deepcopy(bindings[tuple(argv)]) if tuple(argv) in bindings else real_bind(argv)
    try:
        a.verify(OLD)
        controls=[]
        for name in ('binding-omission','argv-omission'):
            bad=a.read_json(OLD/'controls'/(name+'.json'))
            try:a.verify(OLD,bad)
            except ValueError as exc:controls.append({'name':name,'rejected':str(exc)})
            else:raise ValueError('reuse control escaped '+name)
        a.write(dest/'reuse-controls.json',controls)
    finally:
        a.dependencies,a.sdk_witness.capture,a.expanded_invocation.bind=real_deps,real_capture,real_bind
    a.equal(a.hashes(paths),before,'reuse byte drift')
    a.equal(a.sdk_witness.capture(sdk,a.CANONICAL_SDK),sdk_before,'reuse SDK drift')
    for argv,b in bindings.items():a.equal(real_bind(list(argv)),b,'reuse expanded drift')
    a.write(dest/'reuse-after.json',a.hashes(paths))
    print('accepted native reuse verified',len(paths),'files',flush=True)
    return state,before,sdk_before
