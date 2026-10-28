#!/usr/bin/env python3
"""Continue only unexecuted frame leaves after the retained closure-name repair."""
import hashlib,json,shlex,sys,time
from pathlib import Path
import acquire_frames as a
native=a.native;ROOT=a.ROOT;OUT=a.OUT;HERE=a.HERE;BASE=a.BASE;sha=a.sha;need=a.need;dump=a.dump

def main():
    need(time.time()<a.DEADLINE,'same original deadline');old=json.loads((OUT/'admission.json').read_bytes());w=old['witness'];epoch=json.loads((OUT/'before-repair/manifest.json').read_bytes());changed=epoch['original'];need(sha(epoch['copy'])==epoch['sha256']==w['files'][changed],'externally bound original failed header')
    for p,h in w['files'].items():need(sha(epoch['copy']if p==changed else p)==h,'original source/tool integrity '+p)
    for p,target in w.get('aliases',{}).items():need(str(Path(p).resolve(strict=True))==target,'original alias identity')
    r=json.loads((OUT/'recipe.json').read_bytes());need(sha(OUT/'recipe.json')==old['recipeSha256'],'unchanged recipe');need(old['deadline']==a.DEADLINE,'no deadline renewal')
    # Earlier successful mock compilation never consumed frame.hpp; retain it,
    # rather than pretending its broad admission had different historical bytes.
    dep=shlex.split((OUT/'mock.d').read_text().replace('\\\n',' ').split(':',1)[1]);need(changed not in[str(Path(p).resolve())for p in dep],'mock independent of changed header');native.subset(dep,w)
    need(json.loads((OUT/'mock-compile.receipt.json').read_bytes())['returncode']==0,'accepted mock terminal');need(json.loads((OUT/'native-compile.receipt.json').read_bytes())['returncode']==1,'original failed native compile remains failed')
    w2=dict(files=dict(w['files']),aliases=dict(w['aliases']));w2['files'][changed]=sha(changed)
    for p in [Path(__file__),OUT/'mock.o',OUT/'before-repair/manifest.json',Path(epoch['copy'])]:w2['files'][str(p.resolve())]=sha(p)
    native.OUT=OUT;native.DEADLINE=a.DEADLINE;native.ADMISSION_NAME='admission-r2.json';native.WITNESS=w2;native.COMMANDS=[];native.cap=a.cap
    dump(OUT/'admission-r2.json',dict(witness=w2,originalAdmissionSha256=sha(OUT/'admission.json'),sourceRepair=epoch,deadline=a.DEADLINE,recipeSha256=old['recipeSha256'],scope='same-unit repaired native frame source; existing successful independent mock reused; failed original compile never relabeled',budget=native.budget()))
    c=r['compiler'];candidate=['-I'+str(HERE),*r['flags']];before=json.loads((OUT/'sdk-before.json').read_bytes());sdk=r['flags'][r['flags'].index('-isysroot')+1];selector=json.loads((ROOT/'build/weighted-pool-game-admission-r1/complete-r1/plan.json').read_bytes());outputs={};sdk_roles={}
    for name,source,flags,with_mock in [('native-r2',BASE/'native.cpp',candidate,True),('edges',BASE/'edges.cpp',candidate,True),('trace-reference',HERE/'controls.cpp',r['flags'],False),('trace-candidate',HERE/'controls.cpp',[*candidate,'-DIDMAP_BOUNDARY'],True)]:
        native.command(name+'-compile',[c,*flags,'-MD','-MF',OUT/(name+'.d'),'-c',source,'-o',OUT/(name+'.o')]);deps=shlex.split((OUT/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)[1]);native.subset(deps,w2)
        expected=HERE/'StarIdMap.hpp'if with_mock else BASE/'StarIdMap.original.hpp';need(str(expected.resolve())in[str(Path(p).resolve())for p in deps],'actual selected header '+name)
        link=[c,*r['flags'],*r['objects'],str(OUT/(name+'.o')),*([str(OUT/'mock.o')]if with_mock else[]),*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(OUT/(name+'.map')),'-Wl,-t,-trace_implicit_libraries','-o',str(OUT/name)]
        native.command(name+'-expand',[c,'-###',*link[1:]]);need(str(Path(selector['tools']['CMAKE_LINKER']))in(OUT/(name+'-expand.stderr')).read_text(),'selected actual linker')
        native.command(name+'-link',link);outputs[name]=native.command(name,[OUT/name]).decode();need(native.command(name+'-repeat',[OUT/name]).decode()==outputs[name],'repeat byte identity')
        sdk_roles[name]=native.sdk_witness.reconcile_consumed(before,a.sdk_paths((OUT/(name+'.map')).read_bytes()),requested_root=sdk,expected_canonical_root=sdk)
    for name,source,extra in [('lazy-negative',BASE/'native.cpp',['-DIDMAP_LAZY_NEGATIVE']),('hash-move-only-negative',BASE/'native.cpp',['-DIDMAP_HASH_MOVE_ONLY_NEGATIVE']),('typed-auto-negative',HERE/'controls.cpp',['-DIDMAP_BOUNDARY','-DIDMAP_LAZY_AUTO_NEGATIVE'])]:
        native.command(name,[c,*candidate,*extra,'-fsyntax-only',source],expected=1);need('deleted'in(OUT/(name+'.stderr')).read_text(),'mapped-copy negative '+name)
    baseline=a.model.verify(outputs['native-r2']);edges=a.edge_model.verify(outputs['edges']);trace=lambda s:[x for x in s.splitlines()if x.startswith('TRACE\t')];need(trace(outputs['trace-reference'])==trace(outputs['trace-candidate'])and len(trace(outputs['trace-reference']))==5,'exact typed traces/NRVO/const')
    controls=[x for x in outputs['trace-candidate'].splitlines()if x.startswith('CONTROL\t')];need(len(controls)==6,'six control records');falsifiers={}
    for label,reader,text in [('baseline-corruption',a.model.verify,outputs['native-r2'].replace('0,1','9,1',1)),('edge-corruption',a.edge_model.verify,outputs['edges'].replace('cursor=10','cursor=11',1))]:
        try:reader(text)
        except ValueError:falsifiers[label]=True
        else:raise ValueError('accepted falsifier '+label)
    native.unchanged(w2);after=native.sdk_witness.capture(sdk,sdk);need(before==after,'SDK before/after');dump(OUT/'sdk-after.json',after);dump(OUT/'sdk-consumed.json',sdk_roles)
    result=dict(status='FINITE_NATIVE_IDMAP_FRAMES_CPP_MOCK_PASS',commands=native.COMMANDS,acceptedPredecessorCommands=['compiler-version','mock-compile'],retainedFailedCommands=['native-compile'],admissionSha256=sha(OUT/'admission-r2.json'),originalAdmissionSha256=sha(OUT/'admission.json'),baseline=baseline,edges=edges,typedTraces=trace(outputs['trace-reference']),controls=controls,falsifiers=falsifiers,limits=['C++ policy double, NOT actual Rust/native provider or production/game','finite native domains only; signed overflow/full-small-integer nonprogress unexecuted','113 exact current reference objects reused, not recompiled/newgame-source qualification'])
    result['products']={str(p):sha(p)for p in OUT.rglob('*')if p.is_file()and p.name!='report.json'};dump(OUT/'report.json',result);a.cap();print('REPORT',sha(OUT/'report.json'))
if __name__=='__main__':main()
