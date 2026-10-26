#!/usr/bin/env python3
"""Normal-exit controller sensitivity checks, independent of prototype assertions."""
import argparse
import copy
import json
from pathlib import Path
import host_stage
import stage
import trace_audit
import trace_contract as contract

HERE=Path(__file__).resolve().parent
KINDS=('eof-choice','size-no-wrap','skip-zero-full')
PATCHES=(('mode==SB_IO_READ_FULL?(end?1:2):(end?3:4)', 'mode==SB_IO_READ_FULL?2:4'),
         ('if(s.status==1&&c.call(SB_IO_EXCEPTION_KIND)==1)', 'if(false&&s.status==1&&c.call(SB_IO_EXCEPTION_KIND)==1)'),
         ('auto n=c.arg(1);auto r=c.call(mode==SB_IO_READ_FULL?SB_IO_READ:SB_IO_WRITE,0,n);',
          'auto n=c.arg(1);if(!n)break;auto r=c.call(mode==SB_IO_READ_FULL?SB_IO_READ:SB_IO_WRITE,0,n);'))


def need(ok,message):stage.need(ok,message)


def acquire(base,output):
    base=Path(base).resolve();b=host_stage.verify_acquisition(base)
    out=stage.fresh(output,'host-controls-acquire-');receipts=[]
    compiler,flags,libs,objects=stage.recipe();a,m=host_stage.native_basis()
    source=(HERE/'host_contract.cpp').read_text()
    tracked=list(map(Path,b['bindings']))+list(map(Path,b['artifacts']))+[base,Path(__file__).resolve(),HERE/'trace_audit.py',HERE/'host_stage.py']
    for kind,(old,new) in zip(KINDS,PATCHES):
        need(source.count(old)==1,'controller mutation anchor '+kind)
        p=out/(kind+'.cpp');p.write_text(source.replace(old,new))
        stage.command([compiler,*flags,'-I'+str(HERE),'-M','-MF',out/(kind+'.d'),p],
                      'deps-'+kind,out,receipts)
        tracked += [p for p in stage.dependencies(out/(kind+'.d')) if not p.is_relative_to(out)]
    tracked=list(dict.fromkeys(p.resolve() for p in tracked));before={str(p):stage.sha(p) for p in tracked}
    stage.dump(out/'before.json',before)
    for kind in KINDS:
        stage.command([compiler,*flags,'-I'+str(HERE),'-c',out/(kind+'.cpp'),'-o',out/(kind+'.o')],
                      'compile-'+kind,out,receipts)
        stage.command([compiler,*flags,stage.ROOT/'build/io-device-lab/full-acquire-r1/probe.o',out/(kind+'.o'),
                       m['archive'],*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/(kind+'.map')),'-o',out/kind],
                      'link-'+kind,out,receipts)
        need(not stage.has_archive_member((out/(kind+'.map')).read_bytes(),b'native-core.a',b'StarIODevice.cpp.o'),'control archive bypass')
    after={str(p):stage.sha(p) for p in tracked};stage.dump(out/'after.json',after)
    need(before==after,'controller control acquisition drift');host_stage.verify_acquisition(base)
    q=dict(status='CONTROLLER_CONTROLS_ACQUIRED_NOT_EXECUTED',base=str(base),base_sha256=stage.sha(base),
           kinds=list(KINDS),bindings=before,receipts=receipts,
           artifacts={str(p):stage.sha(p) for p in out.iterdir() if p.is_file()})
    stage.dump(out/'acquisition.json',q);verify_acquisition(out/'acquisition.json')
    print('CONTROLLER_CONTROLS_ACQUIRED_NOT_EXECUTED',out/'acquisition.json',flush=True)


def verify_acquisition(path):
    path=Path(path).resolve();root=path.parent;q=stage.load(path)
    need(q['status']=='CONTROLLER_CONTROLS_ACQUIRED_NOT_EXECUTED' and q['kinds']==list(KINDS),'controller control scope')
    need(stage.sha(q['base'])==q['base_sha256'],'prototype base acquisition identity')
    host_stage.verify_acquisition(q['base'])
    need(q['bindings']==stage.load(root/'before.json')==stage.load(root/'after.json'),'controller control binding copies')
    need(str(Path(__file__).resolve()) in q['bindings'] and str(HERE/'host_contract.cpp') in q['bindings'],'mandatory control source bindings')
    for group in ('bindings','artifacts'):
        for p,h in q[group].items():need(stage.sha(p)==h,'controller control '+group+' drift')
    need(set(q['artifacts'])=={str(p) for p in root.iterdir() if p.is_file() and p.name!='acquisition.json'},'controller control artifact inventory')
    need(q['receipts']==stage.load(root/'receipts.json'),'controller control receipt copies')
    names=['deps-'+k for k in KINDS]
    for k in KINDS:names.extend(('compile-'+k,'link-'+k))
    need([r['name'] for r in q['receipts']]==names,'complete controller compile routes')
    for r in q['receipts']:
        need(type(r['returncode']) is int and r['returncode']==0 and Path(r['command'][0]).resolve()==Path(r['executable'])
             and Path(r['executable'])==stage.recipe()[0].resolve()
             and stage.sha(r['executable'])==r['executable_before']==r['executable_after'],'compiler-only controller control acquisition')
        for e in ('stdout','stderr'):need(stage.sha(root/(r['name']+'.'+e))==r[e],'controller acquisition stdio')
    for k in KINDS:
        need(all(str(p) in q['bindings'] or str(p) in q['artifacts'] for p in stage.dependencies(root/(k+'.d'))),'controller control transitive closure')
        need(not stage.has_archive_member((root/(k+'.map')).read_bytes(),b'native-core.a',b'StarIODevice.cpp.o'),'controller control native bypass')
    return q


def check(kind,data):
    got=trace_audit.rows(data);wanted=contract.expected()
    need(len(got)==8021,'control must emit all8021 structured observations')
    changed=0
    for actual,expected in zip(got,wanted):
        if contract.strict_equal(actual,expected):continue
        allow=copy.deepcopy(expected)
        if kind=='eof-choice':
            need(allow['outcome']=='EOF/new','EOF control changed unrelated case')
            allow['outcome']='IO/new'
        elif kind=='size-no-wrap':
            need(allow['outcome']=='IO/wrapped','size control changed unrelated case')
            allow['outcome']=allow['options']['tag']+'/same'
        else:
            o=allow['options']
            need(o['length']==0 and o['action'] in ('readfull','writefull','writebytes'),'zero control changed unrelated case')
            allow['events']=[];allow['outcome']='OK'
        need(contract.strict_equal(actual,allow),'controller mutation altered unscoped state')
        changed+=1
    need(changed>0,'controller semantic mutation escaped')
    return changed


def execute(path,output):
    path=Path(path).resolve();verify_acquisition(path)
    out=stage.fresh(output,'host-controls-execute-');receipts=[];changed={}
    for kind in KINDS:
        data=stage.command([path.parent/kind],kind,out,receipts)
        changed[kind]=check(kind,data)
    verify_acquisition(path)
    q=dict(status='NORMAL_CONTROLLER_CONTROLS_PASS',acquisition=str(path),acquisition_sha256=stage.sha(path),
           changed_cases=changed,receipts=receipts,artifacts={str(p):stage.sha(p) for p in out.iterdir() if p.is_file()})
    stage.dump(out/'report.json',q);verify(out/'report.json')
    print('NORMAL_CONTROLLER_CONTROLS_PASS',changed,flush=True)


def verify(path):
    path=Path(path).resolve();root=path.parent;q=stage.load(path)
    need(q['status']=='NORMAL_CONTROLLER_CONTROLS_PASS' and set(q['changed_cases'])==set(KINDS),'controller control result scope')
    need(stage.sha(q['acquisition'])==q['acquisition_sha256'],'controller control acquisition drift')
    verify_acquisition(q['acquisition'])
    need(q['receipts']==stage.load(root/'receipts.json') and [r['name'] for r in q['receipts']]==list(KINDS),'controller execution routes')
    need(set(q['artifacts'])=={str(root/(k+e)) for k in KINDS for e in ('.stdout','.stderr')}|{str(root/'receipts.json')},'controller execution artifact scope')
    for p,h in q['artifacts'].items():need(stage.sha(p)==h,'controller execution artifact drift')
    for r in q['receipts']:
        k=r['name'];exe=str(Path(q['acquisition']).parent/k)
        need(r['command']==[exe] and r['executable']==exe and type(r['returncode']) is int and r['returncode']==0
             and stage.sha(exe)==r['executable_before']==r['executable_after'],'normal controller execution identity')
        for e in ('stdout','stderr'):need(stage.sha(root/(k+'.'+e))==r[e],'controller execution stream')
        need(check(k,(root/(k+'.stdout')).read_bytes())==q['changed_cases'][k],'controller semantic discrimination')
    return dict(status=q['status'],changed_cases=q['changed_cases'])


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='phase',required=True)
    a=s.add_parser('acquire');a.add_argument('--base',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('execute');a.add_argument('--acquisition',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('verify');a.add_argument('--report',required=True)
    a=p.parse_args()
    if a.phase=='acquire':acquire(a.base,a.output)
    elif a.phase=='execute':execute(a.acquisition,a.output)
    else:print(json.dumps(verify(a.report)))
