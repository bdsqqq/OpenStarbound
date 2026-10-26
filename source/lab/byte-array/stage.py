#!/usr/bin/env python3
"""Compiler-only native ByteArray acquisition, then separately gated execution."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE.parent))
sys.path.insert(0,str(HERE.parent/'behavior'))
import native_artifacts as artifacts
import build_provenance as provenance
import contract

CM=ROOT/'build/behavior/io-device-combined/reference/cmake'
GAME=ROOT/'build/behavior/io-device-combined/reference/bin/starbound'
KINDS=('original','reference','current','growth-control','signed-control','iterator-control')
EXECUTIONS=('original','reference','current','repeat','growth-control','signed-control','iterator-control')


def need(ok,message):
    if not ok:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')


def load(path):
    def pairs(items):
        d={}
        for k,v in items:
            need(k not in d,'duplicate JSON key');d[k]=v
        return d
    return json.loads(Path(path).read_text(),object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))


def fresh(path,prefix):
    path=Path(path).absolute();base=ROOT/'build/byte-array-lab'
    need(path.is_relative_to(base) and path!=base and path.name.startswith(prefix) and not path.exists()
         and not any(p.is_symlink() for p in (path,*path.parents)),'fresh owned output')
    path.mkdir(parents=True);return path


def command(args,name,out,receipts):
    args=list(map(str,args));exe=Path(args[0]).resolve();before=sha(exe)
    p=subprocess.run(args,cwd=ROOT,capture_output=True,timeout=65)
    (out/(name+'.stdout')).write_bytes(p.stdout);(out/(name+'.stderr')).write_bytes(p.stderr)
    receipts.append(dict(name=name,command=args,executable=str(exe),before=before,after=sha(exe),returncode=p.returncode,
                         stdout=sha(out/(name+'.stdout')),stderr=sha(out/(name+'.stderr'))))
    dump(out/'receipts.json',receipts);need(type(p.returncode) is int and p.returncode==0 and before==sha(exe),'command failed '+name)
    return p.stdout


def recipe():
    entry=next(e for e in load(CM/'compile_commands.json') if e['file'].endswith('/StarByteArray.cpp'))
    args=shlex.split(entry['command']);flags=[];skip=False
    for arg in args[1:]:
        if skip:skip=False;continue
        if arg=='-o':skip=True
        elif arg not in ('-c',entry['file']):flags.append(arg)
    need(not any('STAR_USE_RUST' in f for f in flags),'native-only recipe')
    lines=(CM/'build.ninja').read_text().splitlines()
    i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
    objects=[CM/p for p in shlex.split(lines[i].split(': ',1)[1])[1:] if p.endswith('.o') and p.startswith(('core/','extern/'))]
    libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+18] if x.startswith('  LINK_LIBRARIES = ')))
    libs=[str(CM/p) if p.endswith('.a') and not Path(p).is_absolute() else p for p in libs]
    return Path(args[0]),flags,libs,objects


def dependencies(path):
    return [Path(p).resolve() if Path(p).is_absolute() else (ROOT/p).resolve() for p in shlex.split(Path(path).read_text().replace('\\\n',' ').split(':',1)[1])]


def frozen_sources():
    for ext in ('cpp','hpp'):
        p=ROOT/('source/core/StarByteArray.'+ext)
        raw=subprocess.check_output(['git','show','8f4caf6a:'+str(p.relative_to(ROOT))],cwd=ROOT)
        need(p.read_bytes()==raw,'production ByteArray mutation')
    return provenance.verify(GAME)


def acquire(output):
    out=fresh(output,'acquire-');profile=frozen_sources();compiler,flags,libs,objects=recipe();receipts=[]
    raw=(ROOT/'source/core/StarByteArray.cpp').read_text();header=ROOT/'source/core/StarByteArray.hpp'
    expected=contract.expected();data=contract.canonical(expected)
    (out/'expected.jsonl').write_bytes(data);dump(out/'source-map.json',contract.source_map())
    dump(out/'profile.json',profile)
    patches={'growth-control':('m_capacity * 2','m_capacity'),
             'signed-control':('unsigned char c','signed char c'),
             'iterator-control':('return begin() + d + 1;','return begin() + d;')}
    for kind in KINDS:
        body=raw
        if kind in patches:
            old,new=patches[kind];need(body.count(old)==(2 if kind=='signed-control' else 1),'control source anchor')
            body=body.replace(old,new)
        (out/(kind+'.cpp')).write_text(body)
    (out/'StarByteArray.original.hpp').write_bytes(header.read_bytes())
    tracked=[Path(__file__).resolve(),HERE/'lab.cpp',HERE/'contract.py',HERE/'test_contract.py',HERE/'CONTRACT.md',GAME,
             Path(str(GAME)+'.behavior-build.json'),compiler.resolve(),Path(sys.executable).resolve(),Path('/usr/bin/ar').resolve(),Path('/usr/bin/nm').resolve(),
             Path(artifacts.__file__).resolve(),Path(provenance.__file__).resolve(),CM/'build.ninja',CM/'compile_commands.json',CM/'CMakeCache.txt',*objects]
    tracked += [ROOT/p for p in profile['source_files']]
    tracked += [Path(p) for p in libs if Path(p).is_file()]
    for name,source in [('probe',HERE/'lab.cpp'),('body',ROOT/'source/core/StarByteArray.cpp')]:
        command([compiler,*flags,'-M','-MF',out/(name+'.d'),source],'deps-'+name,out,receipts)
        tracked+=dependencies(out/(name+'.d'))
    tracked=list(dict.fromkeys(p.resolve() for p in tracked));before={str(p):sha(p) for p in tracked};dump(out/'before.json',before)
    command(['/usr/bin/ar','qcs',out/'native-core.a',*objects],'archive',out,receipts)
    table=command(['/usr/bin/ar','t',out/'native-core.a'],'archive-table',out,receipts)
    artifacts.check_archive_members(table,[p.name.encode() for p in objects])
    for i,obj in enumerate(objects):
        content=command(['/usr/bin/ar','p',out/'native-core.a',obj.name],'member-'+str(i),out,receipts)
        need(hashlib.sha256(content).hexdigest()==sha(obj),'archive member bytes '+obj.name)
    command([compiler,*flags,'-c',HERE/'lab.cpp','-o',out/'probe.o'],'compile-probe',out,receipts)
    for kind in KINDS:
        source=ROOT/'source/core/StarByteArray.cpp' if kind=='current' else out/(kind+'.cpp')
        command([compiler,*flags,'-c',source,'-o',out/(kind+'.o')],'compile-'+kind,out,receipts)
        symbols=command(['/usr/bin/nm','-C','--defined-only',out/(kind+'.o')],'symbols-'+kind,out,receipts)
        definitions=sorted(set(line.split(b' T ',1)[1] for line in symbols.splitlines() if b' T ' in line and b'Star::ByteArray' in line))
        need(len(definitions)==33,'33 actual compiled ByteArray definitions')
        command([compiler,*flags,out/'probe.o',out/(kind+'.o'),out/'native-core.a',*libs,'-Wl,-dead_strip',
                 '-Wl,-map,'+str(out/(kind+'.map')),'-o',out/kind],'link-'+kind,out,receipts)
        need(not artifacts.has_archive_member((out/(kind+'.map')).read_bytes(),b'native-core.a',b'StarByteArray.cpp.o'),'legacy ByteArray archive bypass')
    after={str(p):sha(p) for p in tracked};dump(out/'after.json',after);need(before==after,'compilation input drift')
    need(frozen_sources()==profile,'native profile drift')
    q=dict(status='BYTEARRAY_NATIVE_ACQUIRED_NOT_EXECUTED',definitions=33,cases=len(expected),expected_sha256=hashlib.sha256(data).hexdigest(),
           bindings=before,receipts=receipts,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},object_count=len(objects),
           archive=str(out/'native-core.a'),objects=[str(p) for p in objects])
    dump(out/'acquisition.json',q);verify_acquisition(out/'acquisition.json');corruptions(out/'acquisition.json')
    print(q['status'],len(expected),len(objects),out/'acquisition.json',flush=True)


def verify_acquisition(path,value=None):
    path=Path(path).resolve();root=path.parent;q=load(path) if value is None else value
    need(q['status']=='BYTEARRAY_NATIVE_ACQUIRED_NOT_EXECUTED' and type(q['definitions']) is int and q['definitions']==33,'native scope')
    need(type(q['cases']) is int and q['cases']==len(contract.expected()),'source case scope')
    need((root/'expected.jsonl').read_bytes()==contract.canonical(contract.expected()) and sha(root/'expected.jsonl')==q['expected_sha256'],'source-frozen expected corpus')
    need(load(root/'source-map.json')==contract.source_map(),'source exercise map')
    need(q['bindings']==load(root/'before.json')==load(root/'after.json'),'input binding copies')
    for name in ('lab.cpp','contract.py','test_contract.py','CONTRACT.md','stage.py'):
        need(str(HERE/name) in q['bindings'],'mandatory fixture/builder source')
    for group in ('bindings','artifacts'):
        for p,h in q[group].items():need(sha(p)==h,'drift '+group+' '+p)
    need(set(q['artifacts'])=={str(p) for p in root.iterdir() if p.is_file() and p.name!='acquisition.json'},'artifact inventory')
    need(q['receipts']==load(root/'receipts.json'),'receipt copies')
    compiler,flags,libs,objects=recipe()
    need(q['objects']==[str(p) for p in objects] and type(q['object_count']) is int and q['object_count']==len(objects),'configured object scope')
    expected=['deps-probe','deps-body','archive','archive-table',*['member-'+str(i) for i in range(len(objects))],'compile-probe']
    for k in KINDS:expected+=['compile-'+k,'symbols-'+k,'link-'+k]
    need([r['name'] for r in q['receipts']]==expected,'compiler-only receipt scope')
    allowed=[compiler.resolve(),Path('/usr/bin/ar').resolve(),Path('/usr/bin/nm').resolve()]
    for r in q['receipts']:
        need(type(r['returncode']) is int and r['returncode']==0 and Path(r['command'][0]).resolve()==Path(r['executable'])
             and Path(r['executable']) in allowed and sha(r['executable'])==r['before']==r['after'],'compiler-only executable identity')
        for ext in ('stdout','stderr'):need(sha(root/(r['name']+'.'+ext))==r[ext],'compiler streams')
    need(q['archive']==str(root/'native-core.a'),'archive path')
    artifacts.check_archive_members((root/'archive-table.stdout').read_bytes(),[p.name.encode() for p in objects])
    for i,p in enumerate(objects):need(sha(root/('member-'+str(i)+'.stdout'))==q['bindings'][str(p)],'archive member byte binding')
    for name in ('probe','body'):
        need(all(str(p) in q['bindings'] or str(p) in q['artifacts'] for p in dependencies(root/(name+'.d'))),'transitive dependency scope')
    for k in KINDS:
        symbols=(root/('symbols-'+k+'.stdout')).read_bytes()
        need(len(set(x.split(b' T ',1)[1] for x in symbols.splitlines() if b' T ' in x and b'Star::ByteArray' in x))==33,'compiled definition scope')
        need(not artifacts.has_archive_member((root/(k+'.map')).read_bytes(),b'native-core.a',b'StarByteArray.cpp.o'),'native link bypass')
    need(frozen_sources()==load(root/'profile.json'),'profile binding')
    return q


def corruptions(path):
    q=load(path);bad=[]
    for field,value in [('definitions',32),('cases',True),('object_count',q['object_count']+1),('expected_sha256','0'*64)]:
        b=copy.deepcopy(q);b[field]=value;bad.append(b)
    b=copy.deepcopy(q);b['bindings'].pop(str(HERE/'contract.py'));bad.append(b)
    for b in bad:
        try:verify_acquisition(path,b)
        except ValueError:pass
        else:raise ValueError('pre-execution manifest corruption escaped')
    return len(bad)


def execute(path,output):
    path=Path(path).resolve();q=verify_acquisition(path);corruptions(path);out=fresh(output,'execute-');receipts=[]
    for name in EXECUTIONS:
        exe=path.parent/('current' if name=='repeat' else name)
        data=command([exe],name,out,receipts)
        if name.endswith('-control'):
            # A normally exiting program must still emit the complete ordered
            # case stream. Malformed output is not semantic-negative credit.
            rows=[json.loads(line) for line in data.splitlines()];expected=contract.expected()
            need(len(rows)==len(expected) and all(set(a)==set(b) for a,b in zip(rows,expected)),'control record shape')
            try:contract.check(data)
            except ValueError:pass
            else:raise ValueError('normally exiting semantic control escaped '+name)
        else:contract.check(data)
    verify_acquisition(path)
    r=dict(status='FINITE_NATIVE_BYTEARRAY_CALIBRATION_PASS',definitions=33,cases=q['cases'],acquisition=str(path),
           acquisition_sha256=sha(path),receipts=receipts,preexecution_corruptions=5,
           artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()})
    dump(out/'report.json',r);verify_execution(out/'report.json');print(r['status'],q['cases'],out/'report.json',flush=True)


def verify_execution(path):
    path=Path(path).resolve();root=path.parent;r=load(path)
    need(r['status']=='FINITE_NATIVE_BYTEARRAY_CALIBRATION_PASS' and type(r['definitions']) is int and r['definitions']==33,'execution scope')
    need(sha(r['acquisition'])==r['acquisition_sha256'],'acquisition identity');q=verify_acquisition(r['acquisition'])
    need(r['cases']==q['cases'] and type(r['cases']) is int,'execution cases')
    need(r['receipts']==load(root/'receipts.json') and [x['name'] for x in r['receipts']]==list(EXECUTIONS),'execution routes')
    need(set(r['artifacts'])=={str(root/(n+e)) for n in EXECUTIONS for e in ('.stdout','.stderr')}|{str(root/'receipts.json')},'execution artifact inventory')
    for p,h in r['artifacts'].items():need(sha(p)==h,'execution artifact drift')
    for row in r['receipts']:
        n=row['name'];exe=str(Path(r['acquisition']).parent/('current' if n=='repeat' else n))
        need(row['command']==[exe] and row['executable']==exe and type(row['returncode']) is int and row['returncode']==0
             and sha(exe)==row['before']==row['after'],'executed binary identity')
        for ext in ('stdout','stderr'):need(sha(root/(n+'.'+ext))==row[ext],'execution stream identity')
        data=(root/(n+'.stdout')).read_bytes()
        if n.endswith('-control'):
            rows=[json.loads(line) for line in data.splitlines()];expected=contract.expected()
            need(len(rows)==len(expected) and all(set(a)==set(b) for a,b in zip(rows,expected)),'normally exiting control shape')
            try:contract.check(data)
            except ValueError:pass
            else:raise ValueError('semantic control escaped')
        else:contract.check(data)
    return dict(status=r['status'],definitions=33,cases=r['cases'],normal_controls=3,profile_objects=q['object_count'])


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='phase',required=True)
    a=s.add_parser('acquire');a.add_argument('--output',required=True)
    a=s.add_parser('execute');a.add_argument('--acquisition',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('verify');a.add_argument('--report',required=True)
    a=p.parse_args()
    if a.phase=='acquire':acquire(a.output)
    elif a.phase=='execute':execute(a.acquisition,a.output)
    else:print(json.dumps(verify_execution(a.report)))
