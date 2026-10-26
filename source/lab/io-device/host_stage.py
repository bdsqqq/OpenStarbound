#!/usr/bin/env python3
"""Acquire a native-owned controller prototype, then separately execute its gates."""
import argparse
import copy
import json
from pathlib import Path
import re
import audit_stage
import full_stage
import stage
import trace_audit
import trace_contract as contract

HERE=Path(__file__).resolve().parent
ROOT=stage.ROOT
MODES=22
POSITIVE=('full','full-repeat','ledger','ledger-repeat','protocol','c11')


def need(ok,message):stage.need(ok,message)


def native_basis():
    trace_audit.verify(ROOT/'build/io-device-lab/full-execute-r1/report.json',
                       ROOT/'build/io-device-lab/full-audit-r1/report.json')
    a=full_stage.verify_acquisition(ROOT/'build/io-device-lab/full-acquire-r1/acquisition.json')
    witness=stage.load(a['witness']);base=stage.verify_acquisition(witness['acquisition'])
    return a,base


def acquire(output):
    out=stage.fresh(output,'host-acquire-');a,m=native_basis()
    compiler,flags,libs,objects=stage.recipe();receipts=[]
    sources=[HERE/n for n in ('host_contract.hpp','host_contract.cpp','host_contract_test.cpp')]
    need(all(p.is_file() for p in sources),'prototype not frozen')
    header='#include "host_contract.hpp"\n#include <stdint.h>\n'
    header+='static uint32_t cb(void* p,uint32_t op,uint64_t a,uint64_t b,uint64_t c,uint64_t* o) { (void)p;(void)op;(void)a;(void)b;(void)c;(void)o;return 2; }\n'
    header+='int main(void) { return sb_io_device_run(UINT32_MAX,0,cb)==2 ? 0 : 1; }\n'
    (out/'consumer.c').write_text(header)
    tracked=[Path(p) for p in a['bindings']]+[Path(p) for p in a['artifacts']]
    tracked += [Path(__file__).resolve(),*sources,ROOT/'source/core/StarIODevice.hpp',HERE/'trace_audit.py']
    tracked += [ROOT/'build/io-device-lab/full-execute-r1/report.json',ROOT/'build/io-device-lab/full-audit-r1/report.json']
    for name,source in (('host',sources[1]),('protocol',sources[2])):
        stage.command([compiler,*flags,'-I'+str(HERE),'-M','-MF',out/(name+'.d'),source],'deps-'+name,out,receipts)
        tracked += stage.dependencies(out/(name+'.d'))
    tracked=list(dict.fromkeys(p.resolve() for p in tracked));before={str(p):stage.sha(p) for p in tracked}
    stage.dump(out/'before.json',before)
    stage.command([compiler,*flags,'-I'+str(HERE),'-c',sources[1],'-o',out/'host.o'],'compile-host',out,receipts)
    symbols=stage.command(['/usr/bin/nm','-C','--defined-only',out/'host.o'],'symbols-host',out,receipts)
    names=sorted(set(re.findall(rb' T (Star::IODevice::[^\n]+)',symbols)))
    need(len(names)==22,'compiled prototype definition scope')
    stage.dump(out/'definitions.json',[n.decode() for n in names])
    native_full=ROOT/'build/io-device-lab/full-acquire-r1/probe.o'
    native_ledger=Path(m['variants']['original']).parent/'probe.o'
    for name,probe in (('full',native_full),('ledger',native_ledger)):
        stage.command([compiler,*flags,probe,out/'host.o',m['archive'],*libs,
                       '-Wl,-dead_strip','-Wl,-map,'+str(out/(name+'.map')),'-o',out/name],
                      'link-'+name,out,receipts)
        need(not stage.has_archive_member((out/(name+'.map')).read_bytes(),b'native-core.a',b'StarIODevice.cpp.o'),'legacy IODevice archive bypass')
    test=sources[2].read_text()
    need('#include "host_contract.cpp"' in test,'protocol must test actual prototype context')
    stage.command([compiler,*flags,'-I'+str(HERE),sources[2],m['archive'],*libs,
                   '-Wl,-dead_strip','-o',out/'protocol'],'link-protocol',out,receipts)
    stage.command([compiler,'-x','c','-std=c11','-Wall','-Wextra','-Werror','-pedantic-errors','-I'+str(HERE),
                   '-c',out/'consumer.c','-o',out/'consumer.o'],'compile-c11',out,receipts)
    stage.command([compiler,*flags,out/'consumer.o',out/'host.o',m['archive'],*libs,
                   '-Wl,-dead_strip','-o',out/'c11'],'link-c11',out,receipts)
    after={str(p):stage.sha(p) for p in tracked};stage.dump(out/'after.json',after)
    need(before==after,'prototype source/input drift');native_basis()
    q=dict(status='HOST_PROTOTYPE_ACQUIRED_NOT_EXECUTED',definitions=22,cases=8021,
           bindings=before,artifacts={str(p):stage.sha(p) for p in out.iterdir() if p.is_file()},receipts=receipts,
           executables={n:str(out/n) for n in ('full','ledger','protocol','c11')})
    stage.dump(out/'acquisition.json',q);verify_acquisition(out/'acquisition.json');corruptions(out/'acquisition.json')
    print('HOST_PROTOTYPE_ACQUIRED_NOT_EXECUTED',out/'acquisition.json',flush=True)


def verify_acquisition(path,value=None):
    path=Path(path).resolve();root=path.parent;q=stage.load(path) if value is None else value
    need(q['status']=='HOST_PROTOTYPE_ACQUIRED_NOT_EXECUTED' and type(q['definitions']) is int and q['definitions']==22
         and type(q['cases']) is int and q['cases']==8021,'prototype acquisition scope')
    need(q['bindings']==stage.load(root/'before.json')==stage.load(root/'after.json'),'prototype binding copies')
    for n in ('host_contract.hpp','host_contract.cpp','host_contract_test.cpp'):
        need(str(HERE/n) in q['bindings'],'mandatory prototype source')
    need(str(Path(__file__).resolve()) in q['bindings'],'builder source binding')
    for group in ('bindings','artifacts'):
        for p,h in q[group].items():need(stage.sha(p)==h,'prototype '+group+' drift '+p)
    need(set(q['artifacts'])=={str(p) for p in root.iterdir() if p.is_file() and p.name!='acquisition.json'},'prototype artifact inventory')
    need(q['executables']=={n:str(root/n) for n in ('full','ledger','protocol','c11')},'prototype executable scope')
    need(all(p in q['artifacts'] for p in q['executables'].values()),'prototype missing executable binding')
    need(q['receipts']==stage.load(root/'receipts.json'),'prototype acquisition receipt copies')
    need([r['name'] for r in q['receipts']]==['deps-host','deps-protocol','compile-host','symbols-host','link-full','link-ledger','link-protocol','compile-c11','link-c11'],'prototype acquisition command scope')
    compiler=stage.recipe()[0].resolve()
    for r in q['receipts']:
        need(type(r['returncode']) is int and r['returncode']==0
             and Path(r['command'][0]).resolve()==Path(r['executable'])
             and Path(r['executable']) in (compiler,Path('/usr/bin/nm').resolve())
             and stage.sha(r['executable'])==r['executable_before']==r['executable_after'],'compiler-only prototype acquisition')
        for ext in ('stdout','stderr'):need(stage.sha(root/(r['name']+'.'+ext))==r[ext],'prototype acquisition stdio')
    for n in ('host','protocol'):
        need(all(str(p) in q['bindings'] or str(p) in q['artifacts'] for p in stage.dependencies(root/(n+'.d'))),'prototype transitive dependency closure')
    symbols=sorted(set(re.findall(rb' T (Star::IODevice::[^\n]+)',(root/'symbols-host.stdout').read_bytes())))
    need(len(symbols)==22 and stage.load(root/'definitions.json')==[n.decode() for n in symbols], 'compiled22 manifest')
    for n in ('full','ledger'):
        need(not stage.has_archive_member((root/(n+'.map')).read_bytes(),b'native-core.a',b'StarIODevice.cpp.o'),'prototype map bypass')
    native_basis()
    return q


def corruptions(path):
    q=stage.load(path);bad=[]
    b=copy.deepcopy(q);b['definitions']=21;bad.append(b)
    b=copy.deepcopy(q);b['cases']=8020;bad.append(b)
    b=copy.deepcopy(q);b['bindings'].pop(str(HERE/'host_contract.cpp'));bad.append(b)
    b=copy.deepcopy(q);b['artifacts'][q['executables']['full']]='0'*64;bad.append(b)
    for b in bad:
        try:verify_acquisition(path,b)
        except ValueError:pass
        else:raise ValueError('prototype preexecution corruption escaped')
    return 4


def execute(path,output):
    path=Path(path).resolve();q=verify_acquisition(path);corruptions(path)
    out=stage.fresh(output,'host-execute-');receipts=[]
    for name in POSITIVE:
        exe=q['executables'][name.removesuffix('-repeat')]
        data=stage.command([exe],name,out,receipts)
        if name.startswith('full'):contract.check(data)
        elif name.startswith('ledger'):stage.check_values(data)
    verify_acquisition(path)
    r=dict(status='FINITE_NATIVE_IODEVICE_HOST_PROTOTYPE_PASS',definitions=22,cases=8021,
           acquisition=str(path),acquisition_sha256=stage.sha(path),receipts=receipts,
           preexecution_corruptions=4,artifacts={str(p):stage.sha(p) for p in out.iterdir() if p.is_file()})
    stage.dump(out/'report.json',r);verify_execution(out/'report.json')
    print('FINITE_NATIVE_IODEVICE_HOST_PROTOTYPE_PASS',out/'report.json',flush=True)


def verify_execution(path):
    path=Path(path).resolve();r=stage.load(path);root=path.parent
    need(r['status']=='FINITE_NATIVE_IODEVICE_HOST_PROTOTYPE_PASS' and type(r['definitions']) is int and r['definitions']==22
         and type(r['cases']) is int and r['cases']==8021,'prototype execution scope')
    need(stage.sha(r['acquisition'])==r['acquisition_sha256'],'prototype acquisition identity')
    q=verify_acquisition(r['acquisition'])
    need(r['receipts']==stage.load(root/'receipts.json') and [x['name'] for x in r['receipts']]==list(POSITIVE),'prototype execution route scope')
    need(set(r['artifacts'])=={str(root/(n+e)) for n in POSITIVE for e in ('.stdout','.stderr')}|{str(root/'receipts.json')},'prototype execution artifact scope')
    for p,h in r['artifacts'].items():need(stage.sha(p)==h,'prototype execution artifact drift')
    for row in r['receipts']:
        name=row['name'];exe=q['executables'][name.removesuffix('-repeat')]
        need(row['command']==[exe] and row['executable']==exe and type(row['returncode']) is int
             and row['returncode']==0 and stage.sha(exe)==row['executable_before']==row['executable_after'],'prototype executed binary identity')
        for ext in ('stdout','stderr'):need(stage.sha(root/(name+'.'+ext))==row[ext],'prototype execution streams')
        data=(root/(name+'.stdout')).read_bytes()
        if name.startswith('full'):contract.check(data)
        elif name.startswith('ledger'):stage.check_values(data)
    return dict(definitions=22,cases=8021,full_executions=2,ledger_executions=2,protocol_executions=1,c11_executions=1)


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='phase',required=True)
    a=s.add_parser('acquire');a.add_argument('--output',required=True)
    a=s.add_parser('execute');a.add_argument('--acquisition',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('verify');a.add_argument('--report',required=True)
    a=p.parse_args()
    if a.phase=='acquire':acquire(a.output)
    elif a.phase=='execute':execute(a.acquisition,a.output)
    else:print(json.dumps(verify_execution(a.report)))
