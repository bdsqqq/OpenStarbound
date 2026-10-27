#!/usr/bin/env python3
"""Synchronous continuation: initial outer was killed by a 10s harness limit.
No inferred receipt for completed-looking lifecycle.o; compile afresh by new name.
"""
import run as A
from pathlib import Path
import json,re,shlex
H=A.H;OUT=A.OUT;ROOT=A.ROOT

def main():
 ad=json.loads((OUT/'admission.json').read_bytes());w=ad['witness'];r=ad['recipe'];delta={str(Path(__file__).resolve()):A.sha(__file__)};w['files'].update(delta)
 A.dump(OUT/'continuation-admission.json',dict(baseSha256=A.sha(OUT/'admission.json'),delta=delta,initialOuter=dict(pid=91054,status='HARNESS_TIMEOUT_AFTER10S; NO terminal outer receipt; lifecycle compile receipt absent, artifact not accepted'),method='synchronous invocation with 300s harness budget; same policy, fixtures, flags and immutable providers'))
 core={p:h for p,h in w['files'].items()if p in ad['delta'] or p in delta or p in ad['tools'] or p in r['objects'] or p in r['libraries'] or p.endswith('/source/core/StarWeightedPool.hpp')};live=dict(files=core,aliases={p:v for p,v in w['aliases'].items()if p in core})
 c=r['compiler'];flags=[*r['flags'],'-I'+str(H),'-I'+str(H.parent/'weighted-pool')];mock=OUT/'mock.o';live['files'][str(mock)]=A.sha(mock);maps=[]
 def compile(name,src,on=1):
  obj=OUT/(name+'.o');dep=OUT/(name+'.d');A.command('compile-'+name,[c,*flags,'-DWP_BOUNDARY_ON='+str(on),'-MD','-MF',dep,'-c',src,'-o',obj],live);deps=shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]);A.subset(deps,w);A.need(not any(p.endswith('/catalog.json')for p in deps),'catalog not consumed');live['files'][str(obj)]=A.sha(obj);return obj
 def build(name,source,on=1):
  obj=compile(name,H/source,on);exe=OUT/name;mp=OUT/(name+'.map');A.command('link-'+name,[c,*flags,*r['objects'],obj,mock,*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(mp),'-Wl,-t,-trace_implicit_libraries','-o',exe],live);live['files'][str(exe)]=A.sha(exe);maps.append(mp);return exe
 life=build('lifecycle-sync','lifecycle.cpp');A.command('lifecycle-mock',[life,'current'],live);A.command('lifecycle-reference',[life,'reference'],live);A.need((OUT/'lifecycle-mock.stdout').read_bytes()==(OUT/'lifecycle-reference.stdout').read_bytes(),'exact event trace parity')
 scalar=build('scalar','scalar.cpp');A.command('scalar-mock',[scalar],live)
 probe=build('probe','probe.cpp');A.command('probe-mock',[probe],live);A.command('probe-known-failure',[probe,'known-failure'],live,expected=1);A.need(b'isolated known failing fixture'in(OUT/'probe-known-failure.stderr').read_bytes(),'negative fixture reason')
 corpus=build('corpus','corpus.cpp');rows,expected=A.model.corpus();A.command('corpus-mock',[corpus],live,stdin=rows.encode());A.need((OUT/'corpus-mock.stdout').read_bytes()==expected.encode(),'27 unchanged rational rows')
 off=build('probe-off','probe.cpp',0);A.command('probe-off',[off],live)
 sdk=json.loads((A.BASE/'sdk-before.json').read_bytes());paths=[]
 for mp in maps:paths+=re.findall(r'^\[\s*\d+\] (.*\.tbd)$',mp.read_text(errors='surrogateescape'),re.M)
 requested=r['flags'][r['flags'].index('-isysroot')+1];A.dump(OUT/'sdk-consumed.json',A.sdk_witness.reconcile_consumed(sdk,paths,requested_root=requested,expected_canonical_root=requested))
 report=dict(status='NATIVE_MOCK_CONTINUATION_FINITE_PASS; initial outer remains timeout',roots=19,stages=4,lifecycleTraces=8,scalarProperties=5,corpusRows=27,abiSha256=A.sha(ROOT/'source/core/StarRustWeightedPool.h'),admissionSha256=A.sha(OUT/'admission.json'),continuationAdmissionSha256=A.sha(OUT/'continuation-admission.json'),limitations=['not actual Rust, production, game or universal template qualification','generic private-friend-only range lookup remains review obligation; positive public member/custom sentinel/ADL run','OFF bodies reconstructed exactly by generator; no production selector change','optimized finite-domain numerical contract only','initial lifecycle.o has no terminal receipt and is excluded from accepted evidence'],products={str(p):A.sha(p)for p in OUT.rglob('*')if p.is_file()and p.name not in ['report.json','acquire.stdout','acquire.stderr']})
 A.dump(OUT/'report.json',report);print('REPORT',A.sha(OUT/'report.json'),flush=True)
if __name__=='__main__':main()
