#!/usr/bin/env python3
"""Supplemental callback acquisition never changes the accepted 987-case gate."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shlex
import sys
import stage
import callback_contract as contract

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PARENT=ROOT/'build/byte-array-lab/acquire-r1/acquisition.json'
BASELINE=('original','reference','current')


def need(value,message):
    if not value:raise ValueError(message)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')


def parse_rows(data):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'duplicate control key');result[key]=value
        return result
    def bad(_):raise ValueError('nonfinite control value')
    return [json.loads(line,object_pairs_hook=pairs,parse_constant=bad) for line in data.splitlines()]


def controls(source):
    # Only the two safe mutation scenarios enter these deliberately wrong free
    # controllers. The real inline class definitions stay identical in all TUs.
    anchor='      return lhs->combineWith(Direct{c}, *rhs, extend);'
    need(source.count(anchor)==1 and source.count('namespace {')==1,'native call source anchor')
    helper='''
template<class F>
ByteArray wrongCombine(ByteArray& lhs, F&& combine, ByteArray const& rhs,
                       bool extend, bool resort) {
  ByteArray const* smaller = &rhs;
  ByteArray const* larger = &lhs;
  if (lhs.size() < rhs.size()) { auto p = smaller; smaller = larger; larger = p; }
  size_t staleTail = larger->size();
  ByteArray res;
  res.resize(smaller->size());
  for (size_t i = 0; i < smaller->size(); ++i)
    res[i] = combine((*smaller)[i], (*larger)[i]);
  if (extend) {
    if (resort && smaller->size() > larger->size()) {
      auto p = smaller; smaller = larger; larger = p;
    }
    size_t end = resort ? larger->size() : staleTail;
    res.resize(end);
    for (size_t i = smaller->size(); i < end; ++i) res[i] = (*larger)[i];
  }
  return res;
}
'''
    variants={}
    for name,case,resort in [('stale-tail-control','grow_large','false'),('resort-control','flip_roles','true')]:
        call=f'      if (name == "{case}") return wrongCombine(*lhs, Direct{{c}}, *rhs, extend, {resort});\n'
        variants[name]=source.replace('namespace {','namespace {\n'+helper,1).replace(anchor,call+anchor)
    return variants


def wrong_expected(name):
    rows=copy.deepcopy(contract.expected())
    case='grow_large' if name=='stale-tail-control' else 'flip_roles'
    selected=[r for r in rows if r['case']==case];need(len(selected)==1,'scoped control case')
    result=selected[0]['result']
    if name=='stale-tail-control':
        # Initial larger size was five; the source callback grows it to seven.
        result['size']=5;result['prefix']=result['prefix'][:5]
    elif name=='resort-control':
        # After the first expression, lhs has one byte and rhs has zero. A
        # forbidden re-sort makes lhs the larger role and copies its first byte.
        result['size']=1;result['prefix']=[10]
    else:raise ValueError('unknown semantic control')
    return rows


def check_control(data,name):
    rows=parse_rows(data)
    contract._typed_equal(rows,wrong_expected(name),'wrong-controller '+name)
    try:contract.check(data)
    except ValueError:pass
    else:raise ValueError('normally exiting semantic control escaped')


def acquire(output):
    parent=stage.verify_acquisition(PARENT);out=stage.fresh(output,'callback-acquire-')
    compiler,flags,libs,_=stage.recipe();receipts=[]
    expected=contract.canonical(contract.expected())
    (out/'expected.jsonl').write_bytes(expected)
    owned=[HERE/n for n in ('callback.cpp','callback_contract.py','test_callback_contract.py','CALLBACKS.md','callback_stage.py')]
    before={str(p):sha(p) for p in owned};dump(out/'precompile-freeze.json',dict(files=before,expected_sha256=hashlib.sha256(expected).hexdigest()))
    variants=controls((HERE/'callback.cpp').read_text())
    for name,source in variants.items():
        (out/(name+'.cpp')).write_text(source)
        (out/(name+'.expected.jsonl')).write_bytes(contract.canonical(wrong_expected(name)))
    stage.command([compiler,*flags,'-M','-MF',out/'callback.d',HERE/'callback.cpp'],'dependencies',out,receipts)
    tracked={**parent['bindings'],**parent['artifacts'],str(PARENT):sha(PARENT),**before}
    for p in stage.dependencies(out/'callback.d'):tracked[str(p)]=sha(p)
    tracked[str(Path(sys.executable).resolve())]=sha(Path(sys.executable).resolve())
    before=tracked;dump(out/'before.json',before)
    stage.command([compiler,*flags,'-c',HERE/'callback.cpp','-o',out/'probe.o'],'compile-probe',out,receipts)
    for name in (*BASELINE,*variants):
        probe=out/'probe.o'
        if name in variants:
            probe=out/(name+'.o')
            stage.command([compiler,*flags,'-I'+str(ROOT/'source/core'),'-c',out/(name+'.cpp'),'-o',probe],'compile-'+name,out,receipts)
        body=PARENT.parent/(name+'.o' if name in BASELINE else 'current.o')
        stage.command([compiler,*flags,probe,body,PARENT.parent/'native-core.a',*libs,'-Wl,-dead_strip',
                       '-Wl,-map,'+str(out/(name+'.map')),'-o',out/name],'link-'+name,out,receipts)
        check_map(out,name,probe,body)
    after={p:sha(p) for p in before};dump(out/'after.json',after);need(before==after,'source/compiler/dependency drift')
    stage.verify_acquisition(PARENT)
    q=dict(status='CALLBACK_NATIVE_ACQUIRED_NOT_EXECUTED',parent=str(PARENT),parent_sha256=sha(PARENT),bindings=before,
           cases=len(contract.expected()),controls=list(variants),receipts=receipts,
           artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()})
    dump(out/'acquisition.json',q);verify(out/'acquisition.json');corruptions(out/'acquisition.json')
    print(q['status'],q['cases'],len(variants),flush=True)


def check_map(root,name,probe,body):
    data=(root/(name+'.map')).read_bytes()
    need(not stage.artifacts.has_archive_member(data,b'native-core.a',b'StarByteArray.cpp.o'),'legacy class body bypass')
    objects=stage.artifacts.link_map_objects(data)
    need(str(probe).encode() in objects and str(body).encode() in objects,'actual probe/body route')


def verify(path,value=None):
    path=Path(path).resolve();root=path.parent;q=stage.load(path) if value is None else value
    need(q['status']=='CALLBACK_NATIVE_ACQUIRED_NOT_EXECUTED','acquisition phase')
    need(q['parent']==str(PARENT) and sha(PARENT)==q['parent_sha256'],'parent artifact identity')
    parent=stage.verify_acquisition(PARENT)
    need(type(q['cases']) is int and q['cases']==len(contract.expected()),'finite callback case count')
    variants=controls((HERE/'callback.cpp').read_text());need(q['controls']==list(variants),'frozen control scope')
    for name,source in variants.items():
        need((root/(name+'.cpp')).read_text()==source,'control source transformation')
        need((root/(name+'.expected.jsonl')).read_bytes()==contract.canonical(wrong_expected(name)),'source-frozen wrong controller')
    need((root/'expected.jsonl').read_bytes()==contract.canonical(contract.expected()),'source-derived expected rows')
    need(q['bindings']==stage.load(root/'before.json')==stage.load(root/'after.json'),'source binding copies')
    need(all(q['bindings'].get(p)==h for p,h in {**parent['bindings'],**parent['artifacts'],str(PARENT):sha(PARENT)}.items()),'whole parent closure')
    freeze=stage.load(root/'precompile-freeze.json')
    need(set(freeze['files'])=={str(HERE/n) for n in ('callback.cpp','callback_contract.py','test_callback_contract.py','CALLBACKS.md','callback_stage.py')},'mandatory source freeze')
    for p,h in freeze['files'].items():need(q['bindings'][p]==h and sha(p)==h,'fixture/builder source freeze')
    need(sha(root/'expected.jsonl')==freeze['expected_sha256'],'frozen corpus digest')
    for group in ('bindings','artifacts'):
        for p,h in q[group].items():need(sha(p)==h,'current artifact drift '+p)
    need(set(q['artifacts'])=={str(p) for p in root.iterdir() if p.is_file() and p.name!='acquisition.json'},'artifact inventory')
    need(all(str(p) in q['bindings'] for p in stage.dependencies(root/'callback.d')),'transitive input closure')
    need(q['receipts']==stage.load(root/'receipts.json'),'compiler receipt copies')
    compiler,_,_,_=stage.recipe();names=['dependencies','compile-probe']
    for name in (*BASELINE,*variants):
        if name in variants:names.append('compile-'+name)
        names.append('link-'+name)
        check_map(root,name,root/(name+'.o' if name in variants else 'probe.o'),PARENT.parent/(name+'.o' if name in BASELINE else 'current.o'))
    need([r['name'] for r in q['receipts']]==names,'compiler-only command scope')
    for r in q['receipts']:
        need(type(r['returncode']) is int and r['returncode']==0 and Path(r['command'][0]).resolve()==compiler.resolve()
             and r['executable']==str(compiler.resolve()) and sha(compiler.resolve())==r['before']==r['after'],'compiler image identity')
        for ext in ('stdout','stderr'):need(sha(root/(r['name']+'.'+ext))==r[ext],'compiler stdio')
    return q


def corruptions(path):
    q=stage.load(path);bad=[]
    for key,val in [('cases',True),('parent_sha256','0'*64),('controls',['invented'])]:
        b=copy.deepcopy(q);b[key]=val;bad.append(b)
    b=copy.deepcopy(q);b['bindings'].pop(str(HERE/'callback.cpp'));bad.append(b)
    for b in bad:
        try:verify(path,b)
        except (ValueError,KeyError):pass
        else:raise ValueError('preexecution corruption escaped')
    return len(bad)


def execute(path,output):
    path=Path(path).resolve();q=verify(path);corruptions(path);out=stage.fresh(output,'callback-execute-');receipts=[]
    for name in (*BASELINE,'repeat',*q['controls']):
        data=stage.command([path.parent/('current' if name=='repeat' else name)],name,out,receipts)
        if name in q['controls']:
            check_control(data,name)
        else:contract.check(data)
    verify(path)
    r=dict(status='FINITE_NATIVE_CALLBACK_TRACE_PASS',acquisition=str(path),acquisition_sha256=sha(path),cases=q['cases'],
           controls=q['controls'],receipts=receipts,preexecution_corruptions=4,
           artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()})
    dump(out/'report.json',r);verify_execution(out/'report.json');print(r['status'],r['cases'],flush=True)


def verify_execution(path):
    path=Path(path).resolve();r=stage.load(path);q=verify(r['acquisition']);root=path.parent
    need(r['status']=='FINITE_NATIVE_CALLBACK_TRACE_PASS' and type(r['cases']) is int and r['cases']==q['cases'],'execution phase/scope')
    need(r['acquisition_sha256']==sha(r['acquisition']) and r['controls']==q['controls'],'acquisition/control identity')
    need(r['receipts']==stage.load(root/'receipts.json'),'execution receipt copies')
    names=(*BASELINE,'repeat',*q['controls']);need([x['name'] for x in r['receipts']]==list(names),'execution route sequence')
    need(set(r['artifacts'])=={str(root/(n+'.'+e)) for n in names for e in ('stdout','stderr')}|{str(root/'receipts.json')},'execution artifact inventory')
    for p,h in r['artifacts'].items():need(sha(p)==h,'execution artifact drift')
    for x in r['receipts']:
        n=x['name'];exe=str(Path(r['acquisition']).parent/('current' if n=='repeat' else n))
        need(x['command']==[exe] and x['executable']==exe and type(x['returncode']) is int and x['returncode']==0
             and sha(exe)==x['before']==x['after'],'normally exiting actual image')
        for e in ('stdout','stderr'):need(sha(root/(n+'.'+e))==x[e],'execution stream identity')
        data=(root/(n+'.stdout')).read_bytes()
        if n in q['controls']:
            check_control(data,n)
        else:contract.check(data)
    return dict(status=r['status'],cases=r['cases'],normal_controls=len(r['controls']))


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='phase',required=True)
    a=s.add_parser('acquire');a.add_argument('--output',required=True)
    a=s.add_parser('execute');a.add_argument('--acquisition',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('verify');a.add_argument('--report',required=True)
    a=p.parse_args()
    if a.phase=='acquire':acquire(a.output)
    elif a.phase=='execute':execute(a.acquisition,a.output)
    else:print(json.dumps(verify_execution(a.report)))
