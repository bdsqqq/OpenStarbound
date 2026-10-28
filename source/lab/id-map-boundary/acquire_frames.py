#!/usr/bin/env python3
"""Fresh finite native-frame/mock gate. Parent alone runs compiler/linker."""
import datetime as dt,hashlib,json,re,shlex,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];OUT=ROOT/'build/id-map-boundary-r1';BASE=HERE.parent/'id-map'
sys.dont_write_bytecode=True;sys.path.insert(0,str(BASE))
import run as native
import model,edge_model
from map_bytes import sdk_paths
sha=native.sha;need=native.need;dump=native.dump
DEADLINE=dt.datetime(2026,10,28,16,17,tzinfo=dt.timezone.utc).timestamp()
def cap():
    need(time.time()<DEADLINE,'native-frame unit hard deadline');need(native.cleanup.allocated_bytes(OUT)<=128*1024**2,'128MiB frame root cap')
def main():
    need(not OUT.exists(),'fresh one-shot frame root');OUT.mkdir();(OUT/'home').mkdir();(OUT/'tmp').mkdir()
    native.OUT=OUT;native.DEADLINE=DEADLINE;native.COMMANDS=[];native.ADMISSION_NAME='admission.json';native.cap=cap
    need(sha(ROOT/'source/core/StarIdMap.hpp')==sha(BASE/'StarIdMap.original.hpp')=='ff8b48f3931efedf8e5b19bc074b84a04f04329aedabbfd3eeb7b7b6ffeaad62','unchanged original header')
    r=native.recipe();dump(OUT/'recipe.json',r);cm=Path(r['cm']);c=r['compiler'];selector=ROOT/'build/weighted-pool-game-admission-r1/complete-r1/plan.json';need(sha(selector)==native.PIN,'immutable tool-path selector');old=json.loads(selector.read_bytes());sdk=r['flags'][r['flags'].index('-isysroot')+1];need(sdk==old['sdk'],'selected SDK');usr=Path(c).resolve().parent.parent
    roots=[ROOT/'source/core',ROOT/'source/extern',HERE,BASE,OUT,Path(sdk),usr/'include',usr/'lib/clang']
    for i,x in enumerate(r['flags']):
        if x in ('-isystem','-isysroot'):roots.append(Path(r['flags'][i+1]))
        elif x.startswith('-I'):roots.append(Path(x[2:]))
    w=native.closure(roots);tools=[Path(c),usr/'bin/clang',Path(old['tools']['CMAKE_LINKER']),usr/'lib/libLTO.dylib',usr/'lib/libtapi.dylib',Path('/bin/ps'),Path(sys.executable)]
    for p in tools:w['files'][str(p.resolve(strict=True))]=sha(p);w['aliases'][str(p)]=str(p.resolve(strict=True))
    extra=[*map(Path,r['objects']),*[Path(x)for x in r['libraries']if Path(x).is_absolute()and Path(x).is_file()],cm/'CMakeCache.txt',cm/'compile_commands.json',cm/'build.ninja',selector,Path(native.__file__),Path(model.__file__),Path(edge_model.__file__),Path(sys.modules['game_syntax'].__file__),Path(native.sdk_witness.__file__),ROOT/'scripts/cleanup-migration-artifacts.py']
    for p in extra:w['files'][str(p.resolve())]=sha(p)
    native.WITNESS=w;before=native.sdk_witness.capture(sdk,sdk);dump(OUT/'sdk-before.json',before)
    dump(OUT/'admission.json',dict(witness=w,recipeSha256=sha(OUT/'recipe.json'),sdkSha256=sha(OUT/'sdk-before.json'),deadline=DEADLINE,budget=native.budget(),scope='native per-method IdMap frames with C++ policy MOCK, original corpora and typed traces; NOT actual Rust/native provider/production/game',oldPlanRole='immutable tool/SDK path selection only, no expired source admission renewal'))
    def command(name,args,**kw):return native.command(name,args,**kw)
    command('compiler-version',[c,'--version'])
    candidate=['-I'+str(HERE),*r['flags']]
    command('mock-compile',[c,*candidate,'-MD','-MF',OUT/'mock.d','-c',HERE/'mock.cpp','-o',OUT/'mock.o'])
    native.subset(shlex.split((OUT/'mock.d').read_text().replace('\\\n',' ').split(':',1)[1]),w)
    outputs={};sdk_roles={}
    for name,source,flags,with_mock in [('native',BASE/'native.cpp',candidate,True),('edges',BASE/'edges.cpp',candidate,True),('trace-reference',HERE/'controls.cpp',r['flags'],False),('trace-candidate',HERE/'controls.cpp',[*candidate,'-DIDMAP_BOUNDARY'],True)]:
        command(name+'-compile',[c,*flags,'-MD','-MF',OUT/(name+'.d'),'-c',source,'-o',OUT/(name+'.o')])
        deps=shlex.split((OUT/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)[1]);native.subset(deps,w)
        expected=HERE/'StarIdMap.hpp'if with_mock else BASE/'StarIdMap.original.hpp';need(str(expected.resolve())in[str(Path(p).resolve())for p in deps],'actual selected IdMap header '+name)
        link=[c,*r['flags'],*r['objects'],str(OUT/(name+'.o')),*([str(OUT/'mock.o')]if with_mock else[]),*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(OUT/(name+'.map')),'-Wl,-t,-trace_implicit_libraries','-o',str(OUT/name)]
        command(name+'-expand',[c,'-###',*link[1:]]);need(str(Path(old['tools']['CMAKE_LINKER']))in(OUT/(name+'-expand.stderr')).read_text(),'selected linker expansion')
        command(name+'-link',link);outputs[name]=command(name,[OUT/name]).decode();need(command(name+'-repeat',[OUT/name]).decode()==outputs[name],'repeat byte identity '+name)
        sdk_roles[name]=native.sdk_witness.reconcile_consumed(before,sdk_paths((OUT/(name+'.map')).read_bytes()),requested_root=sdk,expected_canonical_root=sdk)
    command('lazy-negative',[c,*candidate,'-DIDMAP_LAZY_NEGATIVE','-fsyntax-only',BASE/'native.cpp'],expected=1)
    command('hash-move-only-negative',[c,*candidate,'-DIDMAP_HASH_MOVE_ONLY_NEGATIVE','-fsyntax-only',BASE/'native.cpp'],expected=1)
    command('typed-auto-negative',[c,*candidate,'-DIDMAP_BOUNDARY','-DIDMAP_LAZY_AUTO_NEGATIVE','-fsyntax-only',HERE/'controls.cpp'],expected=1)
    for role in ['lazy-negative','hash-move-only-negative','typed-auto-negative']:need('deleted'in(OUT/(role+'.stderr')).read_text(),'expected mapped-copy constraint '+role)
    baseline=model.verify(outputs['native']);edges=edge_model.verify(outputs['edges']);trace=lambda s:[x for x in s.splitlines()if x.startswith('TRACE\t')];need(trace(outputs['trace-reference'])==trace(outputs['trace-candidate'])and len(trace(outputs['trace-reference']))==5,'exact typed key/NRVO/const/reference traces')
    controls=[x for x in outputs['trace-candidate'].splitlines()if x.startswith('CONTROL\t')];need(len(controls)==6,'all six protocol/control records')
    # Pure falsifiers change captured data, never source/domain/flags/expected values.
    falsifiers={}
    for label,reader,text in [('baseline-corruption',model.verify,outputs['native'].replace('0,1','9,1',1)),('edge-corruption',edge_model.verify,outputs['edges'].replace('cursor=10','cursor=11',1))]:
        try:reader(text)
        except ValueError:falsifiers[label]=True
        else:raise ValueError('accepted falsifier '+label)
    native.unchanged(w);after=native.sdk_witness.capture(sdk,sdk);need(before==after,'SDK before/after');dump(OUT/'sdk-after.json',after);dump(OUT/'sdk-consumed.json',sdk_roles)
    result=dict(status='FINITE_NATIVE_IDMAP_FRAMES_CPP_MOCK_PASS',commands=native.COMMANDS,admissionSha256=sha(OUT/'admission.json'),baseline=baseline,edges=edges,typedTraces=trace(outputs['trace-reference']),controls=controls,falsifiers=falsifiers,limits=['C++ policy double, NOT actual Rust ABI/provider or production/game','finite native domains; signed overflow/full-small-integer nonprogress still unexecuted','113 current reference objects reused exactly, not recompiled/new-game-source proof'])
    result['products']={str(p):sha(p)for p in OUT.rglob('*')if p.is_file()and p.name!='report.json'};dump(OUT/'report.json',result);cap();print('REPORT',sha(OUT/'report.json'),flush=True)
if __name__=='__main__':main()
