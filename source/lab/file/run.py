#!/usr/bin/env python3
"""Fresh native-only source closure build, frozen independent corpus, exact receipts.

No CMake/project build, Rust, game, or historical receipt rebinding. All 113
configured core/extern translation units are materialized locally; the original
File unit is replaced by the byte-identical frozen source, never linked twice.
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
CM=ROOT/'build/behavior/string-view-combined-r1/reference/cmake'
BASE=ROOT/'build/file-lab/native-worker-r1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def need(ok,msg):
 if not ok:raise ValueError(msg)
def cmd(args,name,out,input=None):
 args=list(map(str,args));exe=Path(args[0]).resolve();before=sha(exe)
 p=subprocess.run(args,cwd=CM,input=input,capture_output=True,timeout=120)
 for ext,data in [('stdout',p.stdout),('stderr',p.stderr)]: (out/(name+'.'+ext)).write_bytes(data)
 r=dict(name=name,command=args,executable=str(exe),before=before,after=sha(exe),returncode=p.returncode,stdout=sha(out/(name+'.stdout')),stderr=sha(out/(name+'.stderr')),stdin={'kind':'pipe','sha256':hashlib.sha256(input).hexdigest(),'size':len(input)} if input is not None else {'kind':'inherit'})
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

ORIGINALS={'StarFile.cpp':'401858755ca3694e6ac4f07e44808a268c4b9caa2a75cec7d8db32f2176086c2','StarFile.hpp':'fa034ae7c45748377a00775ac3b4390b4f21d54835e8eac063e44a4e8289e9af','StarFile_unix.cpp':'9e4968e50d51af8006c896c581566bc0d2b69dd97883da5a41980249015f0e12','StarFile_windows.cpp':'554caf9b420f00f8f92f5ac9a978a1ca0b9c3ddbc34acf623b98a70b5b009d6a','StarIODevice.hpp':'f1c7613282fb9314f7445379217d519cfe8f0f66d4fa7a809773b44981706e60'}

def originals():
 for name,digest in ORIGINALS.items():
  need(sha(HERE/name.replace('.', '.original.',1))==sha(ROOT/'source/core'/name)==digest,'frozen original '+name)
 inventory.check()

def compile_jobs(rs):
 base=next(r for r in rs if Path(r['source']).name=='StarFile.cpp')
 return [(str(i),r['compiler'],r['flags'],HERE/'StarFile.original.cpp' if Path(r['source']).name=='StarFile.cpp' else Path(r['source'])) for i,r in enumerate(rs)]+[('driver',base['compiler'],base['flags'],HERE/'lab.cpp')]

def command_plan(out,rs,libs):
 jobs=compile_jobs(rs);base=next(r for r in rs if Path(r['source']).name=='StarFile.cpp');index=next(i for i,r in enumerate(rs) if Path(r['source']).name=='StarFile.cpp')
 plan=[('deps-'+n,[c,*f,'-M','-MF',out/(n+'.d'),s]) for n,c,f,s in jobs]
 plan += [('compile-'+n,[c,*f,'-c',s,'-o',out/(n+'.o')]) for n,c,f,s in jobs]
 plan += [('link',[base['compiler'],*base['flags'],out/'driver.o',*[out/(str(i)+'.o') for i in range(113)],*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/'native.map'),'-o',out/'native']),('symbols',['/usr/bin/nm','-gUC',out/(str(index)+'.o')])]
 plan += [(name,[out/'native',out/(name+'-cases')]) for name in ('native','repeat')]
 return [(name,list(map(str,args))) for name,args in plan]

def initial_bindings(out,rs,libs):
 paths=[p for p in HERE.iterdir() if p.is_file()]+[CM/n for n in ('build.ninja','compile_commands.json','CMakeCache.txt')]+[Path(r['source']) for r in rs]+[Path(r['compiler']).resolve() for r in rs]+[Path(p) for p in libs if Path(p).is_file()]+[Path(sys.executable).resolve(),Path('/usr/bin/nm'),out/'expected.tsv',out/'recipes.json',out/'libraries.json']+list((out/'inputs').iterdir())
 # Resolve and deduplicate BEFORE hashing: repeated compiler/header entries
 # describe one binding, not independent observations. Per-command hashes below
 # remain fresh before/after every invocation.
 return {p:sha(p) for p in sorted({str(p.resolve()) for p in paths})}

def dependency_bindings(out,rs):
 paths=set()
 for n,_,_,_ in compile_jobs(rs):
  for word in shlex.split((out/(n+'.d')).read_text().replace('\\\n',' ').split(':',1)[1]):
   p=Path(word);p=p if p.is_absolute() else CM/p;paths.add(str(p.resolve()))
 return {p:sha(p) for p in sorted(paths)}

def audit(root,expected):
 got={}
 for p in root.rglob('*'):
  need(not p.is_symlink(),'symlink fixture')
  if p.is_file():
   need(p.stat().st_nlink==1,'hardlink fixture');got[str(p.relative_to(root))]=p.read_bytes()
 need(got==expected,'functional fixture bytes differ')
def verify(out):
 import audit as receipts
 return receipts.validate(json.loads((out/'report.json').read_text()),out)

def run(out):
 need(out.is_relative_to(BASE) and out!=BASE and not out.exists(),'fresh output')
 out.mkdir();originals();rs,libs=recipe();dump(out/'recipes.json',rs);dump(out/'libraries.json',libs)
 for n in ['StarFile.cpp','StarFile.hpp','StarFile_unix.cpp','StarFile_windows.cpp','StarIODevice.hpp']:
  frozen=HERE/(n.replace('.', '.original.',1));need(frozen.read_bytes()==(ROOT/'source/core'/n).read_bytes(),'original drift')
 (out/'expected.tsv').write_bytes(contract.expected())
 for name in ['inputs','native-cases','repeat-cases']:
  leaf=out/name;leaf.mkdir()
  for n,b in contract.fixtures().items():
   with (leaf/n).open('xb') as f:f.write(b)
  audit(leaf,contract.fixtures())
 initial=initial_bindings(out,rs,libs);dump(out/'initial.json',initial)
 jobs=compile_jobs(rs);fileindex=next(i for i,r in enumerate(rs) if Path(r['source']).name=='StarFile.cpp');base=rs[fileindex]
 def scan(j):
  n,c,f,s=j;return cmd([c,*f,'-M','-MF',out/(n+'.d'),s],'deps-'+n,out)
 with ThreadPoolExecutor(max_workers=6) as pool:commands=list(pool.map(scan,jobs))
 before={**initial,**dependency_bindings(out,rs)}
 need(all(sha(p)==h for p,h in initial.items()),'scan drift')
 for path,digest in list(before.items()):
  p=Path(path)
  if p.is_relative_to(ROOT/'source'):
   dest=out/'snapshots'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes());need(sha(dest)==digest,'snapshot');before[str(dest)]=digest
 dump(out/'before.json',before)
 def compile(j):
  n,c,f,s=j;return cmd([c,*f,'-c',s,'-o',out/(n+'.o')],'compile-'+n,out)
 with ThreadPoolExecutor(max_workers=6) as pool:commands+=list(pool.map(compile,jobs))
 commands.append(cmd([base['compiler'],*base['flags'],out/'driver.o',*[out/(str(i)+'.o') for i in range(113)],*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/'native.map'),'-o',out/'native'],'link',out))
 commands.append(cmd(['/usr/bin/nm','-gUC',out/(str(fileindex)+'.o')],'symbols',out))
 names=sorted({line.split(' T ',1)[1] for line in (out/'symbols.stdout').read_text().splitlines() if ' T Star::File::' in line})
 need(len(names)==34,'compiled unique File definitions');dump(out/'compiled-symbols.json',names)
 dump(out/'preexecute.json',{str(p):sha(p) for p in out.iterdir() if p.is_file()})
 need(all(sha(p)==h for p,h in before.items()),'preexecute drift')
 for name in ['native','repeat']:
  commands.append(cmd([out/'native',out/(name+'-cases')],name,out,b''));contract.check((out/(name+'.stdout')).read_bytes());audit(out/(name+'-cases'),contract.final_files())
 after={p:sha(p) for p in before};dump(out/'after.json',after);need(before==after,'source drift');dump(out/'commands.json',commands)
 q=dict(status='FINITE_NATIVE_FILE_CALIBRATION_WITH_GAPS',objects=113,source_definitions=34,compiled_symbols=names,observations=len(contract.expected().splitlines()),bindings=before,commands=commands,limitations=['successful deletion UNEXERCISED','platform30 leaves not a migrated boundary','source exercise is not instrumented branch coverage','no OS close-failure injection; virtual throw is native protocol mock','no Rust/application/platform-general claim','SDK implementation binaries unbound','safe reentry and destructor dispatch instrumentation pending'],artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and not p.is_relative_to(out/'snapshots')})
 dump(out/'report.json',q);verify(out);print(q['status'],flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['run','verify']);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output).resolve()
 if a.phase=='run':run(out)
 else:print(verify(out)['status'])
