#!/usr/bin/env python3
"""Stage the new full trace against an already audited native artifact bundle."""
import argparse
import copy
import json
from pathlib import Path
import sys
import audit_stage
import stage
import trace_contract as contract

EXPECTED_SHA='02fb99395f74f0fdd7dd7f7e68073bb098eccb4e6afda05f6672405dcece43b8'
SOURCE_SHA={'trace.cpp':'5662d0ce50c6dc2e7d0ee5f9d1cd4fc26fc4ad14aef2c1aee89dc91595644a98',
            'trace_contract.py':'4a269f80282b352b5d9b0062811f6a4dc9b454153cb585006efa7e64bf66e104'}
NAMES=('original','reference','current','reference-eof')
HERE=Path(__file__).resolve().parent


def need(ok,message):stage.need(ok,message)

def freeze():
    need(all(stage.sha(HERE/n)==h for n,h in SOURCE_SHA.items()),'full trace source freeze')
    data=contract.canonical(contract.expected())
    need(len(contract.corpus())==8021 and len(contract.source_map())==22
         and stage.hashlib.sha256(data).hexdigest()==EXPECTED_SHA,'full synthetic contract freeze')
    return data


def acquire(witness,output):
    witness=Path(witness).resolve()
    audit_stage.verify(witness)
    w=stage.load(witness);parent=Path(w['acquisition']);m=stage.verify_acquisition(parent)
    expected=freeze()
    out=stage.fresh(output,'full-acquire-');receipts=[]
    compiler,flags,libs,objects=stage.recipe()
    (out/'expected.jsonl').write_bytes(expected)
    stage.dump(out/'source-exercise-map.json',contract.source_map())
    raw=(HERE/'StarIODevice.reference.cpp').read_text()
    need(raw.count('throw EofException(')==2,'reference control anchors')
    (out/'reference-eof.cpp').write_text(raw.replace('throw EofException(','throw IOException('))
    tracked=[Path(p) for p in m['bindings']]+[Path(p) for p in m['artifacts']]
    tracked += [witness,parent,Path(__file__).resolve(),HERE/'audit_stage.py',HERE/'trace.cpp',HERE/'trace_contract.py']
    for name in ('probe','probe-ref','reference-eof'):
        source=out/'reference-eof.cpp' if name=='reference-eof' else HERE/'trace.cpp'
        dep=out/(name+'.d')
        stage.command([compiler,*flags,'-I'+str(HERE),*(['-DLAB_REFERENCE'] if name=='probe-ref' else []),
                       '-M','-MF',dep,source],'deps-'+name,out,receipts)
        tracked += [p for p in stage.dependencies(dep) if not p.is_relative_to(out)]
    tracked=list(dict.fromkeys(p.resolve() for p in tracked))
    before={str(p):stage.sha(p) for p in tracked};stage.dump(out/'before.json',before)
    for name in ('probe','probe-ref','reference-eof'):
        source=out/'reference-eof.cpp' if name=='reference-eof' else HERE/'trace.cpp'
        stage.command([compiler,*flags,'-I'+str(HERE),*(['-DLAB_REFERENCE'] if name=='probe-ref' else []),
                       '-c',source,'-o',out/(name+'.o')],'compile-'+name,out,receipts)
    for name in NAMES:
        reference=name.startswith('reference')
        body=out/'reference-eof.o' if name=='reference-eof' else parent.parent/('body-'+name+'.o')
        stage.command([compiler,*flags,out/('probe-ref.o' if reference else 'probe.o'),body,m['archive'],
                       *libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/(name+'.map')),'-o',out/name],
                      'link-'+name,out,receipts)
        symbols=stage.command(['/usr/bin/nm','-C',out/name],'symbols-'+name,out,receipts)
        if reference:need(b'Star::IODeviceReference::IODevice::readFullAbsolute' in symbols,'full reference namespace')
        else:need(not stage.has_archive_member((out/(name+'.map')).read_bytes(),b'native-core.a',b'StarIODevice.cpp.o'),'full archive bypass')
    after={str(p):stage.sha(p) for p in tracked};stage.dump(out/'after.json',after)
    need(before==after,'full acquisition input drift');audit_stage.verify(witness)
    a=dict(status='FULL_TRACE_ACQUIRED_NOT_EXECUTED',cases=8021,definitions=22,witness=str(witness),
           witness_sha256=stage.sha(witness),bindings=before,receipts=receipts,
           artifacts={str(p):stage.sha(p) for p in out.iterdir() if p.is_file()},
           variants={n:str(out/n) for n in NAMES})
    stage.dump(out/'acquisition.json',a);verify_acquisition(out/'acquisition.json');gate_tests(out/'acquisition.json')
    print('FULL_TRACE_ACQUIRED_NOT_EXECUTED',out/'acquisition.json',flush=True)


def verify_acquisition(path,value=None):
    path=Path(path).resolve();root=path.parent;a=stage.load(path) if value is None else value
    need(a['status']=='FULL_TRACE_ACQUIRED_NOT_EXECUTED' and type(a['cases']) is int and a['cases']==8021
         and type(a['definitions']) is int and a['definitions']==22,'full acquisition scope')
    need(set(a['variants'])==set(NAMES),'full variant scope')
    need(a['bindings']==stage.load(root/'before.json')==stage.load(root/'after.json'),'full binding copies')
    required=[Path(__file__).resolve(),HERE/'trace.cpp',HERE/'trace_contract.py',HERE/'audit_stage.py',Path(a['witness'])]
    need(all(str(p.resolve()) in a['bindings'] for p in required),'full mandatory inputs')
    for group in ('bindings','artifacts'):
        for p,h in a[group].items():need(stage.sha(p)==h,'full '+group+' drift '+p)
    need(set(a['artifacts'])=={str(p) for p in root.iterdir() if p.is_file() and p.name!='acquisition.json'},'full artifact inventory')
    need((root/'expected.jsonl').read_bytes()==freeze(),'frozen full expected bytes')
    contract.validate_source_map(stage.load(root/'source-exercise-map.json'))
    need(stage.sha(a['witness'])==a['witness_sha256'],'audited witness identity')
    audit_stage.verify(a['witness'])
    need(a['receipts']==stage.load(root/'receipts.json'),'full receipt copies')
    names=['deps-probe','deps-probe-ref','deps-reference-eof','compile-probe','compile-probe-ref','compile-reference-eof']
    for n in NAMES:names.extend(('link-'+n,'symbols-'+n))
    need([r['name'] for r in a['receipts']]==names,'complete full acquisition commands')
    compiler=stage.recipe()[0].resolve()
    for r in a['receipts']:
        need(type(r['returncode']) is int and r['returncode']==0
             and Path(r['command'][0]).resolve()==Path(r['executable'])
             and Path(r['executable']) in (compiler,Path('/usr/bin/nm').resolve())
             and stage.sha(r['executable'])==r['executable_before']==r['executable_after'],'full compiler-only route')
        for ext in ('stdout','stderr'):need(stage.sha(root/(r['name']+'.'+ext))==r[ext],'full acquisition streams')
    for n in ('probe','probe-ref','reference-eof'):
        need(all(str(p) in a['bindings'] or str(p) in a['artifacts'] for p in stage.dependencies(root/(n+'.d'))),'full transitive closure')
    for n,p in a['variants'].items():
        need(p==str(root/n) and p in a['artifacts'],'full executable identity')
        if n.startswith('reference'):need(b'Star::IODeviceReference::IODevice::readFullAbsolute' in (root/('symbols-'+n+'.stdout')).read_bytes(),'reference symbol evidence')
        else:need(not stage.has_archive_member((root/(n+'.map')).read_bytes(),b'native-core.a',b'StarIODevice.cpp.o'),'full original archive pulled')
    return a


def gate_tests(path):
    a=stage.load(path);bad=[]
    b=copy.deepcopy(a);b['cases']=8020;bad.append(b)
    b=copy.deepcopy(a);b['bindings'].pop(str(HERE/'trace.cpp'));bad.append(b)
    b=copy.deepcopy(a);b['artifacts'][a['variants']['reference']]='0'*64;bad.append(b)
    for b in bad:
        try:verify_acquisition(path,b)
        except ValueError:pass
        else:raise ValueError('full pre-execution corruption escaped')
    return 3


def check_control(data):
    # This scoped control changes exception classification only. Every other
    # field must remain identical, so malformed/missing observations earn no credit.
    actual=[json.loads(line) for line in data.decode('ascii').splitlines()]
    wanted=contract.expected();need(len(actual)==len(wanted),'full control case count')
    changed=0
    for row,target in zip(actual,wanted):
        if not contract.strict_equal(row,target):
            expected=copy.deepcopy(target)
            need(expected['outcome']=='EOF/new','control changed an unscoped outcome')
            expected['outcome']='IO/new'
            need(contract.strict_equal(row,expected),'control changed an unscoped field')
            changed+=1
    need(changed>0,'reference-only semantic control escaped')
    return changed


def execute(path,output):
    path=Path(path).resolve();a=verify_acquisition(path);gate_tests(path)
    out=stage.fresh(output,'full-execute-');receipts=[]
    for name in ('original','reference','current','repeat','reference-eof','reference-eof-repeat'):
        variant='original' if name=='repeat' else 'reference-eof' if name=='reference-eof-repeat' else name
        data=stage.command([a['variants'][variant]],name,out,receipts)
        if name.startswith('reference-eof'):check_control(data)
        else:contract.check(data)
    verify_acquisition(path)
    r=dict(status='FINITE_NATIVE_FULL_TRACE_PASS',cases=8021,definitions=22,acquisition=str(path),
           acquisition_sha256=stage.sha(path),controls=['reference-eof','paired-reference-eof'],receipts=receipts,
           artifacts={str(p):stage.sha(p) for p in out.iterdir() if p.is_file()})
    stage.dump(out/'report.json',r);verify_execution(out/'report.json')
    print('FINITE_NATIVE_FULL_TRACE_PASS',out/'report.json',flush=True)


def verify_execution(path):
    path=Path(path).resolve();r=stage.load(path)
    need(r['status']=='FINITE_NATIVE_FULL_TRACE_PASS' and type(r['cases']) is int and r['cases']==8021
         and type(r['definitions']) is int and r['definitions']==22,'full execution scope')
    need(stage.sha(r['acquisition'])==r['acquisition_sha256'],'full acquisition binding')
    a=verify_acquisition(r['acquisition']);root=path.parent
    need(r['receipts']==stage.load(root/'receipts.json'),'full execution receipt copies')
    names=['original','reference','current','repeat','reference-eof','reference-eof-repeat']
    need([row['name'] for row in r['receipts']]==names,'full execution routes')
    need(set(r['artifacts'])=={str(root/(n+e)) for n in names for e in ('.stdout','.stderr')}|{str(root/'receipts.json')},'full execution artifact scope')
    for p,h in r['artifacts'].items():need(stage.sha(p)==h,'full execution artifact drift')
    for row in r['receipts']:
        n=row['name'];v='original' if n=='repeat' else 'reference-eof' if n=='reference-eof-repeat' else n;exe=a['variants'][v]
        need(row['command']==[exe] and row['executable']==exe and type(row['returncode']) is int
             and row['returncode']==0 and stage.sha(exe)==row['executable_before']==row['executable_after'],'full native execution identity')
        for ext in ('stdout','stderr'):need(stage.sha(root/(n+'.'+ext))==row[ext],'full execution stdio')
        data=(root/(n+'.stdout')).read_bytes()
        if n.startswith('reference-eof'):check_control(data)
        else:contract.check(data)
    need((root/'reference-eof.stdout').read_bytes()==(root/'reference-eof-repeat.stdout').read_bytes(),'paired wrong consistency')
    return dict(cases=8021,definitions=22,positive_executions=4,normal_semantic_controls=1,
                bounded_six_case_semantic_controls=2)


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='phase',required=True)
    a=s.add_parser('acquire');a.add_argument('--witness-report',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('execute');a.add_argument('--acquisition',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('verify');a.add_argument('--report',required=True)
    a=p.parse_args()
    if a.phase=='acquire':acquire(a.witness_report,a.output)
    elif a.phase=='execute':execute(a.acquisition,a.output)
    else:print(json.dumps(verify_execution(a.report)))
