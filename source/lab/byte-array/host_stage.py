#!/usr/bin/env python3
"""Fresh coherent-header native core build, isolated from qualified artifacts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import stage
import contract
import callback_contract
import audit as native_audit

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PARENT=ROOT/'build/byte-array-lab/acquire-r1/acquisition.json'
SOURCES=('host_api.h','host_native.hpp','host_body.cpp','host_header.hpp','host_controller.cpp','host_protocol.cpp','HOST.md')


def need(ok,message):
    if not ok:raise ValueError(message)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')


def effective(path):
    path=Path(path).resolve()
    return {ROOT/'source/core/StarByteArray.hpp':HERE/'host_header.hpp',ROOT/'source/core/StarByteArray.cpp':HERE/'host_body.cpp'}.get(path,path)


def command(args,name,out):
    args=list(map(str,args));exe=Path(args[0]).resolve();before=sha(exe)
    p=subprocess.run(args,cwd=stage.CM,capture_output=True,timeout=90)
    (out/(name+'.stdout')).write_bytes(p.stdout);(out/(name+'.stderr')).write_bytes(p.stderr)
    row=dict(name=name,command=args,executable=str(exe),before=before,after=sha(exe),returncode=p.returncode,
             stdout=sha(out/(name+'.stdout')),stderr=sha(out/(name+'.stderr')))
    dump(out/(name+'.command.json'),row)
    need(type(p.returncode) is int and p.returncode==0 and row['before']==row['after'],'command failed '+name)
    return row


def recipes():
    _,_,_,objects=stage.recipe();db=stage.load(stage.CM/'compile_commands.json');result=[]
    for obj in objects:
        matches=[e for e in db if Path(e.get('output',''))==obj]
        need(len(matches)==1,'configured compile DB object '+str(obj))
        entry=matches[0];args=shlex.split(entry['command']);flags=[];skip=False
        for x in args[1:]:
            if skip:skip=False;continue
            if x=='-o':skip=True
            elif x not in ('-c',entry['file']):flags.append(x)
        result.append(dict(object=str(obj),source=entry['file'],compiler=args[0],flags=flags))
    need(len(result)==113,'configured complete native object scope')
    return result


def dependencies(path):
    words=shlex.split(Path(path).read_text().replace('\\\n',' ').split(':',1)[1])
    return [effective(p if Path(p).is_absolute() else stage.CM/p) for p in words]


def overlay(path):
    value={'version':0,'case-sensitive':'true','use-external-names':False,'roots':[
        {'type':'file','name':str(ROOT/'source/core/StarByteArray.hpp'),'external-contents':str(HERE/'host_header.hpp')},
        {'type':'file','name':str(ROOT/'source/core/StarByteArray.cpp'),'external-contents':str(HERE/'host_body.cpp')}]}
    dump(path,value);return value


def counter_name():
    text=(HERE/'host_api.h').read_text()
    names=re.findall(r'uint64_t\s+(\w*(?:count|counter)\w*)\s*\(',text)
    need(len(names)==1,'one C11 counter accessor');return names[0]


def probe_source(path,original):
    count=counter_name()
    path.write_text('#define main byte_array_frozen_main\n#include "'+str(original)+'"\n#undef main\n'
        'int main(int argc,char** argv) {\nuint64_t before[56][3];\n'
        f'for(unsigned m=0;m<56;++m)for(unsigned e=0;e<3;++e)before[m][e]={count}(m,e);\n'
        'int rc=byte_array_frozen_main(argc,argv);\nstd::cerr << "COUNTERS";\n'
        f'for(unsigned m=0;m<56;++m)for(unsigned e=0;e<3;++e)std::cerr << " " << ({count}(m,e)-before[m][e]);\n'
        'std::cerr << "\\n";return rc;\n}\n')


def control_sources(source):
    patches={'growth':('cap*2','cap'),'signed':('return x<y?UINT64_MAX:x>y?1:0;',
               'return int8_t(x)<int8_t(y)?UINT64_MAX:int8_t(x)>int8_t(y)?1:0;')}
    result={}
    for name,(old,new) in patches.items():
        need(source.count(old)==1,'source-derived controller mutation anchor '+name)
        result[name]=source.replace(old,new)
    return result


def acquire(output):
    parent=stage.verify_acquisition(PARENT);out=stage.fresh(output,'host-acquire-');rs=recipes();receipts=[]
    selection=overlay(out/'overlay.json');extra=['-ivfsoverlay',str(out/'overlay.json'),'-I'+str(HERE)]
    for n in ('lab','callback'):probe_source(out/(n+'-probe.cpp'),HERE/(n+'.cpp'))
    (out/'c11.c').write_text('#include "'+str(HERE/'host_api.h')+'"\nint main(void){return 0;}\n')
    (out/'expected.jsonl').write_bytes(contract.canonical(contract.expected()))
    (out/'callback-expected.jsonl').write_bytes(callback_contract.canonical(callback_contract.expected()))
    variants=control_sources((HERE/'host_controller.cpp').read_text())
    for name,source in variants.items():
        (out/(name+'.cpp')).write_text(source)
        (out/(name+'-expected.jsonl')).write_bytes(contract.canonical(native_audit.wrong_rows('growth-control' if name=='growth' else 'signed-control')))
    initial={**parent['bindings'],**parent['artifacts'],str(PARENT):sha(PARENT)}
    for name in (*SOURCES,'host_stage.py','lab.cpp','callback.cpp','contract.py','callback_contract.py'):
        initial[str(HERE/name)]=sha(HERE/name)
    dump(out/'precompile-freeze.json',initial)
    compiler,flags,libs,_=stage.recipe()
    jobs=[]
    for i,r in enumerate(rs):jobs.append((r['compiler'],r['flags'],r['source'],str(i)))
    for name,source in [('controller',HERE/'host_controller.cpp'),('protocol',HERE/'host_protocol.cpp'),('lab',out/'lab-probe.cpp'),('callback',out/'callback-probe.cpp')]:
        jobs.append((str(compiler),flags,str(source),name))
    for name in variants:jobs.append((str(compiler),flags,str(out/(name+'.cpp')),name))
    def scan(job):
        c,f,src,n=job
        return command([c,*f,*extra,'-M','-MF',out/(n+'.d'),src],'deps-'+n,out)
    with ThreadPoolExecutor(max_workers=6) as pool:receipts+=list(pool.map(scan,jobs))
    before=dict(initial)
    for _,_,_,n in jobs:
        for p in dependencies(out/(n+'.d')):before[str(p)]=sha(p)
    before[str(out/'overlay.json')]=sha(out/'overlay.json')
    dump(out/'before.json',before)
    need(all(sha(p)==h for p,h in initial.items()),'source drift during dependency acquisition')
    def compile_job(job):
        c,f,src,n=job
        return command([c,*f,*extra,'-c',src,'-o',out/(n+'.o')],'compile-'+n,out)
    with ThreadPoolExecutor(max_workers=6) as pool:receipts+=list(pool.map(compile_job,jobs))
    objects=[out/(str(i)+'.o') for i in range(113)]
    receipts.append(command(['/usr/bin/ar','qcs',out/'prototype-core.a',*objects],'archive',out))
    receipts.append(command(['/usr/bin/ar','t',out/'prototype-core.a'],'archive-table',out))
    stage.artifacts.check_archive_members((out/'archive-table.stdout').read_bytes(),[p.name.encode() for p in objects])
    for name in ('lab','callback','protocol','growth','signed'):
        probe=out/('lab.o' if name in variants else name+'.o')
        controller=out/(name+'.o' if name in variants else 'controller.o')
        receipts.append(command([compiler,*flags,*extra,probe,controller,out/'prototype-core.a',*libs,
                                 '-Wl,-dead_strip','-Wl,-map,'+str(out/(name+'.map')),'-o',out/name],'link-'+name,out))
        check_map(out,name,rs)
    receipts.append(command([compiler,'-x','c','-std=c11','-Wall','-Wextra','-Werror','-pedantic-errors','-fsyntax-only',out/'c11.c'],'c11',out))
    body=next(str(i) for i,r in enumerate(rs) if r['source'].endswith('/StarByteArray.cpp'))
    receipts.append(command(['/usr/bin/nm','-C','--defined-only',out/(body+'.o')],'body-symbols',out))
    symbols=(out/'body-symbols.stdout').read_bytes()
    need(len(set(x.split(b' T ',1)[1] for x in symbols.splitlines() if b' T ' in x and b'Star::ByteArray' in x))==33,'33 actual compiled definitions')
    after={p:sha(p) for p in before};dump(out/'after.json',after);need(before==after,'source dependency drift')
    stage.verify_acquisition(PARENT);dump(out/'receipts.json',receipts)
    q=dict(status='NATIVE_BYTEARRAY_HOST_ACQUIRED_NOT_EXECUTED',parent=str(PARENT),parent_sha256=sha(PARENT),bindings=before,
           recipes=rs,overlay=selection,jobs=[list(j) for j in jobs],receipts=receipts,
           artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()})
    dump(out/'acquisition.json',q);verify(out/'acquisition.json');print(q['status'],flush=True)


def check_map(root,name,rs):
    data=(root/(name+'.map')).read_bytes();objects=stage.artifacts.link_map_objects(data)
    control=name in ('growth','signed')
    need(str(root/('lab.o' if control else name+'.o')).encode() in objects
         and str(root/(name+'.o' if control else 'controller.o')).encode() in objects,'actual probe/controller routes')
    need(any(x.startswith(str(root/'prototype-core.a').encode()+b'(') for x in objects),'fresh complete native archive route')
    need(not any(b'/native-core.a(' in x for x in objects),'original archive mixed with changed inline definitions')


def verify(path):
    path=Path(path).resolve();root=path.parent;q=stage.load(path)
    need(q['status']=='NATIVE_BYTEARRAY_HOST_ACQUIRED_NOT_EXECUTED','compiler-only phase')
    parent=stage.verify_acquisition(PARENT)
    need(q['parent']==str(PARENT) and q['parent_sha256']==sha(PARENT),'original calibration identity')
    need(q['recipes']==recipes(),'configured complete native recipe')
    need(q['overlay']==stage.load(root/'overlay.json'),'header/body overlay copies')
    expected={'version':0,'case-sensitive':'true','use-external-names':False,'roots':[
        {'type':'file','name':str(ROOT/'source/core/StarByteArray.hpp'),'external-contents':str(HERE/'host_header.hpp')},
        {'type':'file','name':str(ROOT/'source/core/StarByteArray.cpp'),'external-contents':str(HERE/'host_body.cpp')}]}
    need(q['overlay']==expected,'exact two-file native selection')
    need(q['bindings']==stage.load(root/'before.json')==stage.load(root/'after.json'),'before/after input copies')
    for p,h in stage.load(root/'precompile-freeze.json').items():need(q['bindings'][p]==h,'source freeze')
    need(all(q['bindings'].get(p)==h for p,h in {**parent['bindings'],**parent['artifacts'],str(PARENT):sha(PARENT)}.items()),'complete original closure')
    for group in ('bindings','artifacts'):
        for p,h in q[group].items():need(sha(p)==h,'current source/artifact drift '+p)
    need(set(q['artifacts'])=={str(p) for p in root.iterdir() if p.is_file() and p.name!='acquisition.json'},'full compiler artifact inventory')
    need(q['receipts']==stage.load(root/'receipts.json'),'command receipt copies')
    for r in q['receipts']:
        need(type(r['returncode']) is int and r['returncode']==0 and Path(r['command'][0]).resolve()==Path(r['executable'])
             and sha(r['executable'])==r['before']==r['after'],'compiler image/exit identity')
        for e in ('stdout','stderr'):need(sha(root/(r['name']+'.'+e))==r[e],'compiler streams')
    for name,source in control_sources((HERE/'host_controller.cpp').read_text()).items():
        need((root/(name+'.cpp')).read_text()==source,'native controller source delta')
        need((root/(name+'-expected.jsonl')).read_bytes()==contract.canonical(native_audit.wrong_rows('growth-control' if name=='growth' else 'signed-control')),'frozen wrong-controller expectation')
    expected_names=['deps-'+j[3] for j in q['jobs']]+['compile-'+j[3] for j in q['jobs']]+['archive','archive-table','link-lab','link-callback','link-protocol','link-growth','link-signed','c11','body-symbols']
    need([r['name'] for r in q['receipts']]==expected_names,'complete compiler command scope')
    for row in q['receipts']:
        if row['name'].startswith(('deps-','compile-','link-')):
            args=row['command'];i=args.index('-ivfsoverlay');need(args[i+1]==str(root/'overlay.json'),'all TUs share same header selection')
    for _,_,_,n in q['jobs']:need(all(str(p) in q['bindings'] or str(p) in q['artifacts'] for p in dependencies(root/(n+'.d'))),'full new dependency closure')
    members=native_audit.archive_members((root/'prototype-core.a').read_bytes())
    need([n.decode() for n,_ in members]==[str(i)+'.o' for i in range(113)],'113 fresh archive members')
    for (name,data) in members:need(hashlib.sha256(data).hexdigest()==sha(root/name.decode()),'fresh member bytes')
    for n in ('lab','callback','protocol','growth','signed'):check_map(root,n,q['recipes'])
    need((root/'expected.jsonl').read_bytes()==contract.canonical(contract.expected()) and (root/'callback-expected.jsonl').read_bytes()==callback_contract.canonical(callback_contract.expected()),'unchanged source oracles')
    return q


def counters(data):
    match=re.fullmatch(rb'COUNTERS((?: [0-9]+){168})\n',data)
    need(match is not None,'actual 56x3 route counters')
    values=list(map(int,match[1].split()));rows=[values[i:i+3] for i in range(0,len(values),3)]
    need(all(a==s+p for a,s,p in rows),'valid attempts balance success/pending')
    return rows


def execute(path,output):
    path=Path(path).resolve();q=verify(path);out=stage.fresh(output,'host-execute-');receipts=[];routes=[]
    for name,exe in [('lab','lab'),('callback','callback'),('repeat','lab'),('protocol','protocol'),('growth','growth'),('signed','signed')]:
        receipts.append(command([path.parent/exe],name,out))
        data=(out/(name+'.stdout')).read_bytes()
        if name=='protocol':continue
        if name in ('growth','signed'):
            rows=[native_audit.parse(line) for line in data.splitlines()]
            need(contract.strict_equal(rows,native_audit.wrong_rows('growth-control' if name=='growth' else 'signed-control')),'normally exiting exact wrong controller')
            try:contract.check(data)
            except ValueError:pass
            else:raise ValueError('native semantic control escaped')
            counters((out/(name+'.stderr')).read_bytes())
        else:
            (callback_contract if name=='callback' else contract).check(data)
            routes.append(counters((out/(name+'.stderr')).read_bytes()))
    totals=[[sum(t[m][e] for t in routes) for e in range(3)] for m in range(56)]
    need(all(t[0]>0 for t in totals),'all 56 actual routes covered')
    verify(path);dump(out/'receipts.json',receipts)
    r=dict(status='FINITE_NATIVE_BYTEARRAY_HOST_TRACE_PASS',acquisition=str(path),acquisition_sha256=sha(path),receipts=receipts,routes=totals,
           artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()})
    dump(out/'report.json',r);print(r['status'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='phase',required=True)
    a=s.add_parser('acquire');a.add_argument('--output',required=True)
    a=s.add_parser('verify');a.add_argument('--acquisition',required=True)
    a=s.add_parser('execute');a.add_argument('--acquisition',required=True);a.add_argument('--output',required=True)
    args=p.parse_args()
    if args.phase=='acquire':acquire(args.output)
    elif args.phase=='execute':execute(args.acquisition,args.output)
    else:print(verify(args.acquisition)['status'])
