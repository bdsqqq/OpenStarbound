#!/usr/bin/env python3
"""Same-deadline isolated protocol mechanism; never relabel failed producers."""
import json,shlex,time
from pathlib import Path
import acquire_frames as a
n=a.native;R=a.ROOT;O=a.OUT;H=a.HERE;B=a.BASE;sha=a.sha;need=a.need;dump=a.dump

def main():
    old=json.loads((O/'admission-r2.json').read_bytes());w=old['witness'];n.unchanged(w);need(old['deadline']==a.DEADLINE and time.time()<a.DEADLINE,'same original deadline');need(json.loads((O/'trace-candidate.receipt.json').read_bytes())['returncode']==1,'failed threshold procedure retained')
    w3=dict(files=dict(w['files']),aliases=dict(w['aliases']))
    for p in [Path(__file__),H/'probe.cpp']:w3['files'][str(p.resolve())]=sha(p)
    n.OUT=O;n.DEADLINE=a.DEADLINE;n.ADMISSION_NAME='admission-probe.json';n.WITNESS=w3;n.COMMANDS=[];n.cap=a.cap
    dump(O/'admission-probe.json',dict(witness=w3,previousAdmissionSha256=sha(O/'admission-r2.json'),deadline=a.DEADLINE,budget=n.budget(),mechanism='isolated protocol-per-request conservation; no arbitrary minimum; old failed threshold fixture untouched',scope='CPP policy MOCK only, no actual Rust/production/game'))
    r=json.loads((O/'recipe.json').read_bytes());c=r['compiler'];flags=['-I'+str(H),*r['flags']];name='probe';n.command('probe-compile',[c,*flags,'-MD','-MF',O/'probe.d','-c',H/'probe.cpp','-o',O/'probe.o']);n.subset(shlex.split((O/'probe.d').read_text().replace('\\\n',' ').split(':',1)[1]),w3)
    link=[c,*r['flags'],*r['objects'],str(O/'probe.o'),str(O/'mock.o'),*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(O/'probe.map'),'-Wl,-t,-trace_implicit_libraries','-o',str(O/'probe')]
    n.command('probe-expand',[c,'-###',*link[1:]]);n.command('probe-link',link);out=n.command('probe',[O/'probe']).decode();need(n.command('probe-repeat',[O/'probe']).decode()==out,'probe repeat identity')
    for name,source,extra in [('lazy-negative',B/'native.cpp',['-DIDMAP_LAZY_NEGATIVE']),('hash-move-only-negative',B/'native.cpp',['-DIDMAP_HASH_MOVE_ONLY_NEGATIVE']),('typed-auto-negative',H/'controls.cpp',['-DIDMAP_BOUNDARY','-DIDMAP_LAZY_AUTO_NEGATIVE'])]:
        n.command(name,[c,*flags,*extra,'-fsyntax-only',source],expected=1);need('deleted'in(O/(name+'.stderr')).read_text(),'expected mapped-copy constraint '+name)
    baseline=a.model.verify((O/'native-r2.stdout').read_text());edges=a.edge_model.verify((O/'edges.stdout').read_text());trace=lambda s:[x for x in s.splitlines()if x.startswith('TRACE\t')];original=trace((O/'trace-reference.stdout').read_text());candidate=trace((O/'trace-candidate.stdout').read_text());need(original==candidate and len(original)==5,'trace-prefix identity from retained failed combined procedure; NOT whole procedure acceptance');controls=[x for x in out.splitlines()if x.startswith('CONTROL\t')];need(len(controls)==6,'six isolated protocol controls')
    falsifiers={}
    for label,reader,text in [('baseline-corruption',a.model.verify,(O/'native-r2.stdout').read_text().replace('0,1','9,1',1)),('edge-corruption',a.edge_model.verify,(O/'edges.stdout').read_text().replace('cursor=10','cursor=11',1))]:
        try:reader(text)
        except ValueError:falsifiers[label]=True
        else:raise ValueError('accepted falsifier '+label)
    n.unchanged(w3);sdk=r['flags'][r['flags'].index('-isysroot')+1];before=json.loads((O/'sdk-before.json').read_bytes());after=n.sdk_witness.capture(sdk,sdk);need(before==after,'same SDK');dump(O/'sdk-after.json',after);roles={}
    for role in ['native-r2','edges','trace-reference','trace-candidate','probe']:roles[role]=n.sdk_witness.reconcile_consumed(before,a.sdk_paths((O/(role+'.map')).read_bytes()),requested_root=sdk,expected_canonical_root=sdk)
    dump(O/'sdk-consumed.json',roles)
    previous=['compiler-version','mock-compile','native-r2-compile','native-r2-expand','native-r2-link','native-r2','native-r2-repeat','edges-compile','edges-expand','edges-link','edges','edges-repeat','trace-reference-compile','trace-reference-expand','trace-reference-link','trace-reference','trace-reference-repeat','trace-candidate-compile','trace-candidate-expand','trace-candidate-link']
    for role in previous:need(json.loads((O/(role+'.receipt.json')).read_bytes())['returncode']==0,'accepted terminal predecessor '+role)
    result=dict(status='FINITE_NATIVE_IDMAP_FRAMES_CPP_MOCK_COMPOSITION',acceptedPredecessorCommands=previous,commands=n.COMMANDS,retainedFailedCommands=['native-compile','trace-candidate'],partialEvidence={'trace-candidate':'five typed-trace stdout records preceding failed aggregate threshold, not whole command accepted'},admissionSha256=sha(O/'admission-probe.json'),baseline=baseline,edges=edges,typedTraces=original,controls=controls,protocolObservation=[x for x in out.splitlines()if x.startswith('OBSERVATION\t')],falsifiers=falsifiers,limits=['native C++ policy double, NOT actual Rust/native archive provider/production/game','finite native domains only; signed overflow/full-small-integer nonprogress unexecuted','failed original compile and combined threshold procedure remain FAILED','113 exact current reference objects reused, not recompiled/newgame-source qualification'])
    result['products']={str(p):sha(p)for p in O.rglob('*')if p.is_file()and p.name!='report.json'};dump(O/'report.json',result);a.cap();print('REPORT',sha(O/'report.json'))
if __name__=='__main__':main()
