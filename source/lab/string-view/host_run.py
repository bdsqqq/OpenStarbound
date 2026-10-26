#!/usr/bin/env python3
"""Fresh native-only host qualification against the unchanged 8332-row oracle."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
sys.dont_write_bytecode=True
import run as native
import contract
import inventory
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=ROOT/'build/string-view-lab/host-prototype-r1'
PARENT=ROOT/'build/string-view-lab/native-worker-r1/parent-final-r1'
OWNED=['host_api.h','host_controller.cpp','host_header.hpp','host_body.cpp','host_wrapper.cpp','host_run.py','host_test.cpp','HOST.md']
sha=native.sha
dump=native.dump
need=native.need

def counts(path,positive):
 rows=[list(map(int,l.split()[1:])) for l in path.read_text().splitlines() if l.startswith('SV_COUNT ')]
 need(len(rows)==58 and [r[0] for r in rows]==list(range(58)),'58 counter rows')
 need(all(0<=v<2**64 for row in rows for v in row),'unsigned counters')
 need(all(a==s+p for _,a,s,p in rows),'balanced counters')
 if positive:need(all(a>0 and s>0 for _,a,s,p in rows),'all 58 positive controller slots')
 else:need(all(a==s==p==0 for _,a,s,p in rows),'normal native bypass has no controller work')
 return rows

def verify(out):
 q=json.loads((out/'report.json').read_text());need(q['status']=='FINITE_NATIVE_STRINGVIEW_HOST_PASS','status')
 for group in ['bindings','artifacts']:
  for p,h in q[group].items():need(sha(p)==h,'drift '+p)
 need(q['bindings']==json.loads((out/'before.json').read_text())==json.loads((out/'after.json').read_text()),'before/after')
 for n in ['candidate','repeat','bypass']:contract.check((out/(n+'.stdout')).read_bytes())
 need((out/'candidate.stdout').read_bytes()==(out/'repeat.stdout').read_bytes()==(out/'bypass.stdout').read_bytes(),'exact repeat and value-identical bypass')
 counts(out/'candidate.stderr',True);counts(out/'repeat.stderr',True);counts(out/'bypass.stderr',False)
 need((out/'candidate.stderr').read_bytes()==(out/'repeat.stderr').read_bytes(),'exact counter repeat')
 names={line.split(' T ',1)[1] for line in (out/'wrapper-symbols.stdout').read_text().splitlines() if ' T ' in line}
 need(all(name in names for group in json.loads((out/'compiled-symbols.json').read_text()).values() for name in group),'58 symbol replay')
 need((out/'protocol.stdout').read_text()=='NATIVE_STRINGVIEW_PROTOCOL_PASS\n','protocol')
 for c in q['commands']:
  need(c==json.loads((out/(c['name']+'.command.json')).read_text()),'command receipt')
  need(c['returncode']==0 and sha(c['executable'])==c['before']==c['after'],'command identity')
  for s in ['stdout','stderr']:need(sha(out/(c['name']+'.'+s))==c[s],'command output')
 return q

def run(out):
 need(out.is_relative_to(BASE) and out!=BASE and not out.exists(),'fresh owned output required')
 out.mkdir(parents=True)
 inventory.check();native.verify(PARENT)
 rs,libs=native.recipe();need(rs==json.loads((PARENT/'recipes.json').read_text()),'identical native flags')
 need(libs==json.loads((PARENT/'libraries.json').read_text()),'identical native libraries')
 r=rs[92];need(Path(r['source']).name=='StarStringView.cpp','replacement index92')
 need(not any('star_rust' in x or 'libstar_core' in x for x in libs),'no Rust/core archive')
 for ext in ['cpp','hpp']:need((HERE/('StarStringView.original.'+ext)).read_bytes()==(ROOT/('source/core/StarStringView.'+ext)).read_bytes(),'unchanged production')
 cases,rows=contract.corpus();(out/'input.tsv').write_bytes((PARENT/'input.tsv').read_bytes());(out/'expected.jsonl').write_bytes(contract.canon(rows))
 # Bind exactly the original qualified closure, all 113 native objects and
 # participating host files. Parent's separate supplement is not an input.
 paths=[HERE/n for n in OWNED]+[HERE/n for n in ['lab.cpp','contract.py','inventory.py','source-map.json','run.py']]
 parent=json.loads((PARENT/'report.json').read_text())
 bindings=dict(parent['bindings'])
 for p in [*paths,*[PARENT/(str(i)+'.o') for i in range(113)],PARENT/'driver.o',PARENT/'report.json',out/'input.tsv',out/'expected.jsonl']:
  bindings[str(p.resolve())]=sha(p)
 dump(out/'initial.json',bindings)
 commands=[]
 def cmd(args,name,input=None):
  receipt=native.cmd(args,name,out,input);commands.append(receipt);return receipt
 jobs=[('controller',HERE/'host_controller.cpp',[]),('body',HERE/'host_body.cpp',[]),('wrapper',HERE/'host_wrapper.cpp',[]),('audit',HERE/'host_test.cpp',['-DSV_CORPUS_AUDIT']),('protocol-driver',HERE/'host_test.cpp',[])]
 for name,src,extra in jobs:
  cmd([r['compiler'],*r['flags'],*extra,'-M','-MF',out/(name+'.d'),src],'deps-'+name)
  for word in shlex.split((out/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)[1]):
   p=Path(word);p=p if p.is_absolute() else native.CM/p;p=p.resolve()
   if str(p) not in bindings:bindings[str(p)]=sha(p)
 need(all(sha(p)==h for p,h in bindings.items()),'precompile drift')
 # Preserve the owned source and inputs before the first actual trial.
 for p in paths:
  dest=out/'snapshots'/p.name;dest.parent.mkdir(exist_ok=True);dest.write_bytes(p.read_bytes());bindings[str(dest)]=sha(dest)
 dump(out/'before.json',bindings)
 for name,src,extra in jobs:cmd([r['compiler'],*r['flags'],*extra,'-c',src,'-o',out/(name+'.o')],'compile-'+name)
 cmd(['/usr/bin/nm','-gUC',out/'wrapper.o'],'wrapper-symbols')
 names={line.split(' T ',1)[1] for line in (out/'wrapper-symbols.stdout').read_text().splitlines() if ' T ' in line}
 expected=json.loads((PARENT/'compiled-symbols.json').read_text())
 need(all(name in names for group in expected.values() for name in group),'all 58 original compiled symbol groups')
 dump(out/'compiled-symbols.json',expected)
 # Strict C ABI parsing, without importing any C++ header.
 cmd([r['compiler'],'-x','c','-std=c11','-pedantic-errors','-fsyntax-only',HERE/'host_api.h'],'c-api')
 objects=[PARENT/(str(i)+'.o') for i in range(113) if i!=92]
 host=[out/(n+'.o') for n in ['wrapper','body','controller']]
 for name,inputs in [('candidate',[PARENT/'driver.o',out/'audit.o',*host,*objects]),('protocol',[out/'protocol-driver.o',*host,*objects]),('bypass',[PARENT/'driver.o',out/'audit.o',out/'controller.o',*[PARENT/(str(i)+'.o') for i in range(113)]])]:
  cmd([r['compiler'],*r['flags'],*inputs,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/(name+'.map')),'-o',out/name],'link-'+name)
 dump(out/'preexecute.json',{str(p):sha(p) for p in out.iterdir() if p.is_file()})
 need(all(sha(p)==h for p,h in bindings.items()),'preexecution drift')
 for name in ['candidate','repeat','bypass','protocol']:
  cmd([out/('candidate' if name=='repeat' else name)],name,None if name=='protocol' else (out/'input.tsv').read_bytes())
  if name!='protocol':contract.check((out/(name+'.stdout')).read_bytes())
 counts(out/'candidate.stderr',True);counts(out/'repeat.stderr',True);counts(out/'bypass.stderr',False)
 need((out/'candidate.stderr').read_bytes()==(out/'repeat.stderr').read_bytes(),'exact counter repeat')
 # An ordinary native link produces identical values and must fail this gate.
 try:counts(out/'bypass.stderr',True)
 except ValueError as e:rejection=str(e)
 else:raise ValueError('native bypass escaped')
 after={p:sha(p) for p in bindings};dump(out/'after.json',after);need(bindings==after,'postexecution drift')
 dump(out/'commands.json',commands)
 q=dict(status='FINITE_NATIVE_STRINGVIEW_HOST_PASS',cases=len(rows),modes=58,bindings=bindings,commands=commands,bypass_rejection=rejection,
 artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},limitations=['native macOS only; no Rust or application claim','parent owns independent callback deletion supplement and full-expression review','no arbitrary pointers/lifetimes/OOM/platform/performance proof','reused exact fresh parent 113-object closure; SDK binary attestation remains parent scoped'])
 dump(out/'report.json',q);verify(out);print(q['status'],out/'report.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['run','verify']);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output).resolve()
 if a.phase=='run':run(out)
 else:print(verify(out)['status'])
