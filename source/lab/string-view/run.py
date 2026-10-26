#!/usr/bin/env python3
"""Fresh native-only source closure build, frozen independent corpus, exact receipts.

No CMake/project build, Rust, game, or historical receipt rebinding. All 113
configured core/extern translation units are materialized locally; the original
StringView unit is replaced by the byte-identical frozen source, never linked twice.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
sys.dont_write_bytecode=True
import contract
import inventory
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
CM=ROOT/'build/behavior/byte-array-combined-r7/reference/cmake'
BASE=ROOT/'build/string-view-lab/native-worker-r1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def need(ok,msg):
 if not ok:raise ValueError(msg)
def cmd(args,name,out,input=None):
 args=list(map(str,args));exe=Path(args[0]).resolve();before=sha(exe)
 p=subprocess.run(args,cwd=CM,input=input,capture_output=True,timeout=120)
 for ext,data in [('stdout',p.stdout),('stderr',p.stderr)]: (out/(name+'.'+ext)).write_bytes(data)
 r=dict(name=name,command=args,executable=str(exe),before=before,after=sha(exe),returncode=p.returncode,stdout=sha(out/(name+'.stdout')),stderr=sha(out/(name+'.stderr')))
 dump(out/(name+'.command.json'),r)
 need(p.returncode==0 and r['before']==r['after'],'command failed '+name)
 return r

def recipe():
 db=json.loads((CM/'compile_commands.json').read_text());lines=(CM/'build.ninja').read_text().splitlines()
 i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
 objs=[CM/p for p in shlex.split(lines[i].split(': ',1)[1])[1:] if p.endswith('.o') and p.startswith(('core/','extern/'))]
 need(len(objs)==113,'113 native configured objects')
 libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+18] if x.startswith('  LINK_LIBRARIES = ')))
 libs=[str(CM/p) if p.endswith('.a') and not Path(p).is_absolute() else p for p in libs]
 rs=[]
 for obj in objs:
  e=next(e for e in db if Path(e.get('output',''))==obj);args=shlex.split(e['command']);flags=[];skip=False
  for x in args[1:]:
   if skip:skip=False;continue
   if x=='-o':skip=True
   elif x not in ('-c',e['file']):flags.append(x)
  need(not any('STAR_USE_RUST' in x for x in flags),'native selector')
  rs.append(dict(compiler=args[0],flags=flags,source=e['file'],historical_object=str(obj)))
 return rs,libs

def symbols(out):
 recipes=json.loads((out/'recipes.json').read_text());i=next(i for i,r in enumerate(recipes) if Path(r['source']).name=='StarStringView.cpp')
 p=subprocess.run(['/usr/bin/nm','-gUC',str(out/(str(i)+'.o'))],capture_output=True,check=True,text=True)
 names={line.split(' T ',1)[1] for line in p.stdout.splitlines() if ' T ' in line}
 groups={k:[] for k in ('member','string-bridge','free','formatter')}
 for name in names:
  if name.startswith('Star::StringView::'):groups['member'].append(name)
  elif name.startswith(('Star::String::String(', 'Star::String::operator+=(')) and ('Star::StringView' in name or 'basic_string_view<char' in name):groups['string-bridge'].append(name)
  elif name.startswith('Star::operator') and 'Star::StringView' in name:groups['free'].append(name)
  elif 'formatter<Star::StringView' in name and '::format(' in name:groups['formatter'].append(name)
 need({k:len(v) for k,v in groups.items()}==inventory.generate()['counts'],'compiled StringView boundary symbols')
 return {k:sorted(v) for k,v in groups.items()}

def verify(out):
 inventory.check()
 q=json.loads((out/'report.json').read_text())
 need(q['status']=='FINITE_NATIVE_STRINGVIEW_CALIBRATION_PASS','status')
 need(type(q['cases']) is int and q['cases']==len(contract.corpus()[1]) and q['definitions']==58 and q['objects']==113,'finite scope')
 for group in ('bindings','artifacts'):
  for p,h in q[group].items():need(sha(p)==h,'drift '+p)
 need(json.loads((out/'before.json').read_text())==q['bindings']==json.loads((out/'after.json').read_text()),'freeze equality')
 need((out/'expected.jsonl').read_bytes()==contract.canon(contract.corpus()[1]),'oracle drift')
 need(q['compiled_symbols']==symbols(out)==json.loads((out/'compiled-symbols.json').read_text()),'compiled definitions')
 need(q['commands']==json.loads((out/'commands.json').read_text()),'command inventory')
 for command in q['commands']:
  need(command==json.loads((out/(command['name']+'.command.json')).read_text()),'command receipt')
  need(type(command['returncode']) is int and command['returncode']==0,'normal command exit')
  need(sha(command['executable'])==command['before']==command['after'],'command executable')
  for stream in ('stdout','stderr'):need(sha(out/(command['name']+'.'+stream))==command[stream],'command stream')
 for name in ('native','repeat'):contract.check((out/(name+'.stdout')).read_bytes())
 need([x['name'] for x in q['controls']]==['trailing','offsets','empty'],'three controls')
 for name in ('trailing','offsets','empty'):
  expected=contract.corpus()[1];actual=[json.loads(x) for x in (out/(name+'.stdout')).read_bytes().splitlines()]
  need(len(actual)==len(expected) and all(a['id']==b['id'] for a,b in zip(actual,expected)),'control shape')
  need(next(x for x in q['controls'] if x['name']==name)['changed']==sum(a!=b for a,b in zip(actual,expected))>0,'control discrimination')
  try:contract.check((out/(name+'.stdout')).read_bytes())
  except ValueError:pass
  else:raise ValueError('control escaped')
 return q

def run(out):
 need(out.is_relative_to(BASE) and out!=BASE and not out.exists(),'fresh owned path required')
 out.mkdir(parents=True)
 inventory.check()
 rs,libs=recipe();dump(out/'recipes.json',rs);dump(out/'libraries.json',libs)
 for ext in ('cpp','hpp'):need((HERE/('StarStringView.original.'+ext)).read_bytes()==(ROOT/('source/core/StarStringView.'+ext)).read_bytes(),'frozen source mismatch')
 cases,rows=contract.corpus();(out/'expected.jsonl').write_bytes(contract.canon(rows));(out/'input.tsv').write_text(''.join('\t'.join(c)+'\n' for c in cases));dump(out/'source-map.json',contract.source_map())
 need(len(contract.source_map())==58,'definition mapping')
 # Bind closure before scans too, so acquisition cannot silently accept source drift.
 paths=list(HERE.glob('*'));paths=[p for p in paths if p.is_file()]+[CM/n for n in ('build.ninja','compile_commands.json','CMakeCache.txt')]
 paths += [Path(r['source']) for r in rs]+[Path(r['compiler']).resolve() for r in rs]+[Path(p) for p in libs if Path(p).is_file()]
 paths += [Path(sys.executable).resolve(),Path('/usr/bin/ar').resolve(),Path('/usr/bin/nm').resolve(),out/'expected.jsonl',out/'input.tsv',out/'recipes.json',out/'libraries.json',out/'source-map.json']
 initial={str(p.resolve()):sha(p) for p in paths};dump(out/'initial.json',initial)
 jobs=[];sv=None
 for i,r in enumerate(rs):
  source=Path(r['source'])
  if source.name=='StarStringView.cpp':source=HERE/'StarStringView.original.cpp';sv=r
  jobs.append((str(i),r['compiler'],r['flags'],source))
 need(sv is not None,'StringView recipe')
 jobs.append(('driver',sv['compiler'],sv['flags'],HERE/'lab.cpp'))
 for name,macro in [('trailing','CONTROL_TRAILING'),('offsets','CONTROL_OFFSETS'),('empty','CONTROL_EMPTY')]:jobs.append((name,sv['compiler'],[*sv['flags'],'-D'+macro],HERE/'lab.cpp'))
 def scan(j):
  n,c,f,s=j;return cmd([c,*f,'-M','-MF',out/(n+'.d'),s],'deps-'+n,out)
 with ThreadPoolExecutor(max_workers=6) as pool:commands=list(pool.map(scan,jobs))
 before=dict(initial)
 for n,_,_,_ in jobs:
  words=shlex.split((out/(n+'.d')).read_text().replace('\\\n',' ').split(':',1)[1])
  for p in words:
   p=Path(p);p=p if p.is_absolute() else CM/p;key=str(p.resolve())
   if key not in before:before[key]=sha(p)
 need(all(sha(p)==h for p,h in initial.items()),'pre-scan drift')
 # Materialize source snapshots BEFORE execution, with identical bytes verified.
 for path,digest in list(before.items()):
  src=Path(path)
  if src.is_relative_to(ROOT/'source'):
   dst=out/'snapshots'/src.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes())
   need(sha(dst)==digest,'snapshot drift '+path);before[str(dst)]=digest
 dump(out/'before.json',before)
 def compile(j):
  n,c,f,s=j;return cmd([c,*f,'-c',s,'-o',out/(n+'.o')],'compile-'+n,out)
 with ThreadPoolExecutor(max_workers=6) as pool:commands+=list(pool.map(compile,jobs))
 # Direct link fresh materialized native objects: no archive lazy extraction or stale header mix.
 objects=[out/(str(i)+'.o') for i in range(113)]
 for name,driver in [('native','driver'),('trailing','trailing'),('offsets','offsets'),('empty','empty')]:
  commands.append(cmd([sv['compiler'],*sv['flags'],out/(driver+'.o'),*objects,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/(name+'.map')),'-o',out/name],'link-'+name,out))
 compiled_symbols=symbols(out);dump(out/'compiled-symbols.json',compiled_symbols)
 dump(out/'preexecute.json',{str(p):sha(p) for p in out.iterdir() if p.is_file()})
 need(all(sha(p)==h for p,h in before.items()),'pre-execution drift')
 controls=[]
 for name in ('native','repeat','trailing','offsets','empty'):
  exe=out/('native' if name=='repeat' else name);commands.append(cmd([exe],name,out,(out/'input.tsv').read_bytes()));data=(out/(name+'.stdout')).read_bytes()
  if name in ('native','repeat'):contract.check(data)
  else:
   got=[json.loads(x) for x in data.splitlines()];need(len(got)==len(rows) and all(a['id']==b['id'] for a,b in zip(got,rows)),'normal control shape')
   try:contract.check(data)
   except ValueError as e:controls.append(dict(name=name,kind='compiled driver semantic mutant; frozen module unchanged',changed=sum(a!=b for a,b in zip(got,rows)),first_rejection=str(e)))
   else:raise ValueError('control escaped')
 after={p:sha(p) for p in before};dump(out/'after.json',after);need(before==after,'source/tool/dependency drift')
 dump(out/'commands.json',commands)
 q=dict(status='FINITE_NATIVE_STRINGVIEW_CALIBRATION_PASS',compiled_symbols=compiled_symbols,cases=len(rows),definitions=58,bindings=before,controls=controls,commands=commands,expected_sha256=sha(out/'expected.jsonl'),objects=113,
 limitations=['finite native macOS arm64 only; no Rust/application claim','no sanitizer/OOM/arbitrary lifetime proof','SDK framework implementation binaries are platform provenance, not fully transitive linked-byte attestation','at empty0/default null or true-array one-past substr excluded; endpoint substr uses live std::string NUL','private compare otherOffset nonzero unreachable through public corpus; source quirk retained','before/after hashes cannot detect transient edits reverted between snapshots'],
 artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()})
 dump(out/'report.json',q);verify(out);print(q['status'],q['cases'],out/'report.json',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['run','verify']);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output).resolve()
 if a.phase=='run':run(out)
 else:print(verify(out)['status'])
