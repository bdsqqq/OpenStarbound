#!/usr/bin/env python3
"""Finite Rust controller replay; never builds Cargo or a game, never edits goldens."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import stage
import trace_contract as contract

ROOT=stage.ROOT
HERE=Path(__file__).resolve().parent
SEAL=ROOT/'build/io-device-rust/native-before-r1.json'
OWNED=('source/core/StarIODevice.cpp','source/CMakeLists.txt','source/rust/ffi/src/lib.rs')
INPUTS=('source/core/StarIODevice.cpp','source/core/StarIODevice.hpp','source/core/StarIODeviceHost.hpp',
        'source/core/StarRustIODevice.h','source/rust/ffi/src/io_device.rs','source/rust/ffi/src/lib.rs','source/CMakeLists.txt')
RUNS=('native','rust','rust-repeat','ledger','protocol','c11','native-bypass','wrong-pending','wrong-eof')


def need(ok,message):stage.need(ok,message)


def native_seal():
    s=stage.load(SEAL)
    need(s['status']=='PRE_IMPLEMENTATION_NATIVE_CONTROLS_VERIFIED','native acceptance handshake')
    v=json.loads(s['verifier_stdout'])
    need(v=={'status':'NORMAL_CONTROLLER_CONTROLS_PASS','changed_cases':{'eof-choice':8,'size-no-wrap':32,'skip-zero-full':20}},'completed native control verification')
    for group in ('bindings','artifacts'):
        for p,h in s[group].items():
            if p in [str(ROOT/n) for n in OWNED]:continue
            need(stage.sha(p)==h,'unchanged native '+group+' '+p)
    raw=(HERE/'StarIODevice.original.cpp').read_text()
    cpp=(ROOT/OWNED[0]).read_text();prefix,body=raw.split('namespace Star {',1)
    need(cpp.startswith(prefix+'#ifdef STAR_USE_RUST_IO_DEVICE\n') and cpp.endswith('#endif\n'),'native envelope')
    need(cpp.split('\n#else\n',1)[1][:-len('#endif\n')]=='namespace Star {'+body,'byte-exact native OFF namespace')
    # The historical native profile is not relabeled current: only these exact
    # integration changes are permitted, then all candidate inputs are sealed.
    cm=(ROOT/OWNED[1]).read_text()
    cm=cm.replace('\noption(STAR_USE_RUST_IO_DEVICE "Use experimental Rust IODevice controllers" OFF)','')
    cm=cm.replace(' OR STAR_USE_RUST_IO_DEVICE)',')')
    cm=cm.replace('if(STAR_USE_RUST_IO_DEVICE)\n  add_compile_definitions(STAR_USE_RUST_IO_DEVICE)\nendif()\n\n','')
    need(hashlib.sha256(cm.encode()).hexdigest()==s['bindings'][str(ROOT/OWNED[1])],'exact CMake integration delta')
    old=subprocess.check_output(['git','show','2e290ffd:'+OWNED[2]],cwd=ROOT).decode()
    current=(ROOT/OWNED[2]).read_text()
    need(current.startswith(old),'existing aggregate module bytes')
    extra=re.sub(r'\s+','',current[len(old):])
    need(extra in ('modio_device;pubuseio_device::{star_io_device_call_count,star_io_device_run,StarIODeviceHost};',
                   'modio_device;pubuseio_device::{star_io_device_run,star_io_device_call_count,StarIODeviceHost};'),'sole aggregate export delta')
    return s


OBSERVER=r'''
#include "StarRustIODevice.h"
#include <cstdint>
#include <iostream>
static uint64_t routes[22][4]{};
static thread_local StarIODeviceHost leaf=nullptr;
static uint32_t eof_host(void* c,uint32_t op,uint64_t a,uint64_t b,uint64_t d,uint64_t* out){
 if(op==STAR_IO_ERROR){if(a==1)a=2;if(a==3)a=4;}
 return leaf(c,op,a,b,d,out);
}
extern "C" uint32_t io_observed_run(uint32_t m,void* c,StarIODeviceHost h){
#ifdef WRONG_EOF
 auto previous=leaf;leaf=h;auto status=star_io_device_run(m,c,eof_host);leaf=previous;
#else
 auto status=star_io_device_run(m,c,h);
#endif
#ifdef WRONG_PENDING
 if(status==1)status=2;
#endif
 if(m<22&&status<4)++routes[m][status];return status;
}
#define main io_trace_main
#include "trace.cpp"
#undef main
int main(){
 uint64_t before[22][3]{};
 for(unsigned m=0;m<22;++m)for(unsigned e=0;e<3;++e)before[m][e]=star_io_device_call_count(m,e);
 // Renaming main removes its implicit return rule. Never call that helper;
 // execute the unchanged source corpus/case functions instead.
 auto cases=corpus();for(size_t i=0;i<cases.size();++i)run(cases[i],i);
 auto status=0;
 std::cerr<<"IO_DEVICE_COUNTS [";
 for(unsigned m=0;m<22;++m){if(m)std::cerr<<",";std::cerr<<"[";
 for(unsigned e=0;e<3;++e){if(e)std::cerr<<",";std::cerr<<(star_io_device_call_count(m,e)-before[m][e]);}
 for(unsigned e=0;e<4;++e)std::cerr<<","<<routes[m][e];std::cerr<<"]";}
 std::cerr<<"]\n";return status;
}
'''


def counts(data):
    lines=data.decode().splitlines();rows=[x[len('IO_DEVICE_COUNTS '):] for x in lines if x.startswith('IO_DEVICE_COUNTS ')]
    need(len(rows)==1,'one actual controller receipt')
    rows=json.loads(rows[0]);need(len(rows)==22,'controller receipt scope')
    for r in rows:
        need(type(r) is list and len(r)==7 and all(type(v) is int and v>=0 for v in r),'typed controller counts')
        a,s,p,r0,r1,r2,r3=r
        need(a>0 and a==s+p and r0==s and r1==p and not r2 and not r3,'actual Rust and C++ returned routes')
    return rows


def acquire(output,archive,digest):
    archive=Path(archive).resolve();need(stage.sha(archive)==digest,'explicit aggregate identity')
    s=native_seal();out=stage.fresh(output,'rust-acquire-');compiler,flags,libs,_=stage.recipe();receipts=[]
    (out/'observer.cpp').write_text(OBSERVER)
    protocol=(HERE/'host_contract_test.cpp').read_text().replace('#include "host_contract.cpp"','#include "StarIODeviceHost.hpp"')
    protocol=protocol.replace('IODeviceLab','IODeviceRust').replace('SB_IO_','STAR_IO_').replace('sb_io_device_run','star_io_device_run')
    foreign=' assert(star_io_device_run(STAR_IO_SYNC,nullptr,foreign)==3);\n'
    need(protocol.count(foreign)==1,'C++-only foreign throw invocation removal')
    protocol=protocol.replace(foreign,'')
    (out/'protocol.cpp').write_text(protocol)
    (out/'consumer.c').write_text('#include "StarRustIODevice.h"\nstatic uint32_t h(void*p,uint32_t o,uint64_t a,uint64_t b,uint64_t c,uint64_t*r){(void)p;(void)o;(void)a;(void)b;(void)c;*r=0;return 0;}\nint main(void){return star_io_device_run(STAR_IO_SYNC,0,h)!=0 || star_io_device_call_count(STAR_IO_SYNC,1)!=1;}\n')
    tracked=list(map(Path,s['bindings']))+list(map(Path,s['artifacts']))+[SEAL,archive,Path(__file__).resolve()]
    tracked += [ROOT/p for p in INPUTS]
    tracked += list((ROOT/'source/rust').glob('*/src/*.rs'))
    for name,src in [('candidate',ROOT/INPUTS[0]),('protocol',out/'protocol.cpp'),('observer',out/'observer.cpp')]:
        stage.command([compiler,*flags,'-DSTAR_USE_RUST_IO_DEVICE','-I'+str(HERE),'-M','-MF',out/(name+'.d'),src],'deps-'+name,out,receipts)
        tracked += [p for p in stage.dependencies(out/(name+'.d')) if not p.is_relative_to(out)]
    tracked=list(dict.fromkeys(p.resolve() for p in tracked));before={str(p):stage.sha(p) for p in tracked};stage.dump(out/'before.json',before)
    for name,defines in [('native',[]),('candidate',['-DSTAR_USE_RUST_IO_DEVICE','-Dstar_io_device_run=io_observed_run']),('direct',['-DSTAR_USE_RUST_IO_DEVICE'])]:
        stage.command([compiler,*flags,*defines,'-c',ROOT/INPUTS[0],'-o',out/(name+'.o')],'compile-'+name,out,receipts)
        stage.command(['/usr/bin/nm','-C','--defined-only',out/(name+'.o')],'symbols-'+name,out,receipts)
        names=set(re.findall(rb' T (Star::IODevice::[^\n]+)',(out/('symbols-'+name+'.stdout')).read_bytes()))
        need(len(names)==22,'actual compiled definition scope')
    for name,obj,extra,src in [('native','native',[],out/'observer.cpp'),('rust','candidate',[],out/'observer.cpp'),
                              ('ledger','direct',[],ROOT/'build/io-device-lab/staged-acquire-r2/probe.o'),
                              ('protocol','direct',[],out/'protocol.cpp'),('native-bypass','native',[],out/'observer.cpp'),
                              ('wrong-pending','candidate',['-DWRONG_PENDING'],out/'observer.cpp'),
                              ('wrong-eof','candidate',['-DWRONG_EOF'],out/'observer.cpp')]:
        stage.command([compiler,*flags,'-I'+str(HERE),*extra,src,out/(obj+'.o'),
                       ROOT/'build/io-device-lab/oracle-r2/native-core.a',archive,*libs,'-Wl,-dead_strip',
                       '-Wl,-map,'+str(out/(name+'.map')),'-o',out/name],'link-'+name,out,receipts)
        need(not stage.has_archive_member((out/(name+'.map')).read_bytes(),b'native-core.a',b'StarIODevice.cpp.o'),'legacy archive bypass')
    stage.command([compiler,'-x','c','-std=c11','-Wall','-Wextra','-Werror','-pedantic-errors','-I'+str(ROOT/'source/core'),
                   '-c',out/'consumer.c','-o',out/'consumer.o'],'compile-c11',out,receipts)
    stage.command([compiler,*flags,out/'consumer.o',out/'direct.o',ROOT/'build/io-device-lab/oracle-r2/native-core.a',archive,*libs,'-Wl,-dead_strip','-o',out/'c11'],'link-c11',out,receipts)
    after={str(p):stage.sha(p) for p in tracked};stage.dump(out/'after.json',after);need(before==after,'candidate compilation drift');native_seal()
    q=dict(status='RUST_IO_DEVICE_ACQUIRED_NOT_EXECUTED',bindings=before,receipts=receipts,archive=str(archive),archive_sha256=digest,
           artifacts={str(p):stage.sha(p) for p in out.iterdir() if p.is_file()})
    stage.dump(out/'acquisition.json',q);verify_acquisition(out/'acquisition.json')
    print('RUST_IO_DEVICE_ACQUIRED_NOT_EXECUTED',out/'acquisition.json',flush=True)


def verify_acquisition(path,value=None):
    path=Path(path).resolve();root=path.parent;q=stage.load(path) if value is None else value
    need(q['status']=='RUST_IO_DEVICE_ACQUIRED_NOT_EXECUTED','candidate phase');native_seal()
    need(q['bindings']==stage.load(root/'before.json')==stage.load(root/'after.json'),'candidate binding copies')
    for p in (*INPUTS,str(Path(__file__).resolve()),str(SEAL)):
        need(str((ROOT/p).resolve()) in q['bindings'],'mandatory current candidate input')
    need(q['bindings'][q['archive']]==q['archive_sha256'],'aggregate binding')
    for g in ('bindings','artifacts'):
        for p,h in q[g].items():need(stage.sha(p)==h,'candidate '+g+' drift '+p)
    need(set(q['artifacts'])=={str(p) for p in root.iterdir() if p.is_file() and p.name!='acquisition.json'},'candidate artifact inventory')
    need(q['receipts']==stage.load(root/'receipts.json'),'candidate compiler receipt copies')
    expected=['deps-candidate','deps-protocol','deps-observer']
    for n in ('native','candidate','direct'):expected+=['compile-'+n,'symbols-'+n]
    expected+=['link-'+n for n in ('native','rust','ledger','protocol','native-bypass','wrong-pending','wrong-eof')]+['compile-c11','link-c11']
    need([r['name'] for r in q['receipts']]==expected,'candidate compiler-only command scope')
    for r in q['receipts']:
        need(type(r['returncode']) is int and r['returncode']==0 and Path(r['command'][0]).resolve()==Path(r['executable'])
             and Path(r['executable']) in (stage.recipe()[0].resolve(),Path('/usr/bin/nm').resolve())
             and stage.sha(r['executable'])==r['executable_before']==r['executable_after'],'candidate compiler identity')
        for e in ('stdout','stderr'):need(stage.sha(root/(r['name']+'.'+e))==r[e],'candidate compiler stdio')
    for n in ('candidate','protocol','observer'):
        need(all(str(p) in q['bindings'] or str(p) in q['artifacts'] for p in stage.dependencies(root/(n+'.d'))),'candidate dependency closure')
    for n in ('native','rust','ledger','protocol','native-bypass','wrong-pending','wrong-eof'):
        need(not stage.has_archive_member((root/(n+'.map')).read_bytes(),b'native-core.a',b'StarIODevice.cpp.o'),'candidate link-map scope')
    return q


def execute(path,output):
    path=Path(path).resolve();q=verify_acquisition(path);out=stage.fresh(output,'rust-execute-');receipts=[]
    # A copied missing aggregate binding must fail before any native execution.
    import copy
    bad=copy.deepcopy(q);bad['bindings'].pop(q['archive'])
    try:verify_acquisition(path,bad)
    except (ValueError,KeyError):pass
    else:raise ValueError('candidate corruption escaped')
    for n in RUNS:
        exe=path.parent/n.removesuffix('-repeat');data=stage.command([exe],n,out,receipts)
        if n in ('native','rust','rust-repeat','native-bypass','wrong-pending'):contract.check(data)
        if n in ('rust','rust-repeat'):counts((out/(n+'.stderr')).read_bytes())
        if n=='ledger':stage.check_values(data)
        if n in ('native-bypass','wrong-pending'):
            try:counts((out/(n+'.stderr')).read_bytes())
            except ValueError:pass
            else:raise ValueError('normally exiting route control escaped')
        if n=='wrong-eof':
            import host_controls
            need(host_controls.check('eof-choice',data)==8,'defined-domain EOF control scope')
    verify_acquisition(path)
    r=dict(status='FINITE_RUST_IO_DEVICE_CONTROLLER_PASS',acquisition=str(path),acquisition_sha256=stage.sha(path),receipts=receipts,
           artifacts={str(p):stage.sha(p) for p in out.iterdir() if p.is_file()})
    stage.dump(out/'report.json',r);verify_execution(out/'report.json')
    print('FINITE_RUST_IO_DEVICE_CONTROLLER_PASS',out/'report.json',flush=True)


def verify_execution(path):
    path=Path(path).resolve();root=path.parent;r=stage.load(path)
    need(r['status']=='FINITE_RUST_IO_DEVICE_CONTROLLER_PASS','candidate execution phase')
    need(stage.sha(r['acquisition'])==r['acquisition_sha256'],'candidate acquisition identity')
    verify_acquisition(r['acquisition'])
    need(r['receipts']==stage.load(root/'receipts.json') and [x['name'] for x in r['receipts']]==list(RUNS),'candidate execution routes')
    need(set(r['artifacts'])=={str(root/(n+e)) for n in RUNS for e in ('.stdout','.stderr')}|{str(root/'receipts.json')},'candidate execution artifact inventory')
    for p,h in r['artifacts'].items():need(stage.sha(p)==h,'candidate execution drift')
    result={}
    for row in r['receipts']:
        n=row['name'];exe=str(Path(r['acquisition']).parent/n.removesuffix('-repeat'))
        need(row['command']==[exe] and row['executable']==exe and type(row['returncode']) is int and row['returncode']==0
             and stage.sha(exe)==row['executable_before']==row['executable_after'],'actual native execution identity')
        for e in ('stdout','stderr'):need(stage.sha(root/(n+'.'+e))==row[e],'candidate execution streams')
        data=(root/(n+'.stdout')).read_bytes()
        if n in ('native','rust','rust-repeat','native-bypass','wrong-pending'):contract.check(data)
        if n in ('rust','rust-repeat'):result[n]=counts((root/(n+'.stderr')).read_bytes())
        if n=='ledger':stage.check_values(data)
        if n in ('native-bypass','wrong-pending'):
            try:counts((root/(n+'.stderr')).read_bytes())
            except ValueError:pass
            else:raise ValueError('normally exiting route control escaped')
        if n=='wrong-eof':
            import host_controls
            need(host_controls.check('eof-choice',data)==8,'defined-domain EOF control scope')
    return dict(status=r['status'],cases=8021,definitions=22,actual_counts=result,normal_controls=3)


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='phase',required=True)
    a=sub.add_parser('acquire');a.add_argument('--output',required=True);a.add_argument('--archive',required=True);a.add_argument('--archive-sha256',required=True)
    a=sub.add_parser('execute');a.add_argument('--acquisition',required=True);a.add_argument('--output',required=True)
    a=sub.add_parser('verify');a.add_argument('--report',required=True)
    a=p.parse_args()
    if a.phase=='acquire':acquire(a.output,a.archive,a.archive_sha256)
    elif a.phase=='execute':execute(a.acquisition,a.output)
    else:print(json.dumps(verify_execution(a.report)))
