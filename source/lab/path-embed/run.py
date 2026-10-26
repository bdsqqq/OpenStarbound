#!/usr/bin/env python3
"""Fresh native PathEmbed acquisition, with no project build or production edits."""
import argparse,hashlib,json,shlex,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.dont_write_bytecode=True
import contract,inventory,closure
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
CM=ROOT/'build/behavior/file-combined-r2/reference/cmake'
BASE=ROOT/'build/path-embed-lab/native-worker-r1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def need(ok,msg):
 if not ok:raise ValueError(msg)
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

MUTATIONS={
 'wrong-escape':("*outIt++ = 'c';","*outIt++ = 'x';"),
 'stop-nul':('it < end;','it < end && *it;'),
 'standard-base64':('base64Encode(data,true)','base64Encode(data,false)'),
 'wrong-prefix':('"zlib;"','"gzip;"'),
 'gzip-success':('throw StarException("Compressing data in gzip is unsupported.");','return String("success");')}
VARIANTS=['original','current',*MUTATIONS]
RUNS=['leaf','leaf-repeat','original','original-repeat','current','current-repeat',*MUTATIONS]
def sources(out,rs):
 jobs=[]
 for i,r in enumerate(rs):
  s=HERE/'original/StarPathEmbed.cpp' if Path(r['source']).name=='StarPathEmbed.cpp' else Path(r['source'])
  jobs.append((str(i),r['compiler'],r['flags'],s))
 base=next(r for r in rs if Path(r['source']).name=='StarPathEmbed.cpp')
 jobs += [('current',base['compiler'],base['flags'],ROOT/'source/core/StarPathEmbed.cpp')]
 jobs += [(n,base['compiler'],base['flags'],out/(n+'.cpp')) for n in MUTATIONS]
 jobs += [('driver',base['compiler'],base['flags'],HERE/'lab.cpp'),('leaf-driver',base['compiler'],[*base['flags'],'-DLEAF_ONLY'],HERE/'lab.cpp')]
 return jobs

def archives(libs):return sorted({p for p in libs if p.endswith('.a')})
def plans(out,rs,libs):
 jobs=sources(out,rs);idx=next(i for i,r in enumerate(rs) if Path(r['source']).name=='StarPathEmbed.cpp');base=rs[idx]
 plan=[('deps-'+n,[c,*f,'-M','-MF',out/(n+'.d'),s]) for n,c,f,s in jobs]
 plan += [('compile-'+n,[c,*f,'-c',s,'-o',out/(n+'.o')]) for n,c,f,s in jobs]
 for v in ['leaf',*VARIANTS]:
  objects=[out/(str(i)+'.o') for i in range(113) if i!=idx]
  if v!='leaf':objects.append(out/((str(idx) if v=='original' else v)+'.o'))
  plan.append(('link-'+v,[base['compiler'],*base['flags'],out/('leaf-driver.o' if v=='leaf' else 'driver.o'),*objects,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/(v+'.map')),'-o',out/v]))
 for v in VARIANTS:
  plan.append(('symbols-'+v,['/usr/bin/nm','-gUC',out/((str(idx) if v=='original' else v)+'.o')]))
 plan += [('archive-'+str(i),['/usr/bin/ar','-t',p]) for i,p in enumerate(archives(libs))]
 plan += [(n,[out/n.removesuffix('-repeat')]) for n in RUNS]
 return [(n,list(map(str,a))) for n,a in plan]

def cmd(out,name,args):
 exe=Path(args[0]).resolve();before=sha(exe);stdin=contract.inputs() if name in RUNS else None
 p=subprocess.run(args,cwd=CM,input=stdin,capture_output=True,timeout=120)
 for ext,b in [('stdout',p.stdout),('stderr',p.stderr)]:(out/(name+'.'+ext)).write_bytes(b)
 r=dict(name=name,command=args,executable=str(exe),before=before,after=sha(exe),returncode=p.returncode,exit_type='normal' if p.returncode>=0 else 'signal',stdin={'size':len(stdin),'sha256':hashlib.sha256(stdin).hexdigest()} if stdin is not None else None,stdout=sha(out/(name+'.stdout')),stderr=sha(out/(name+'.stderr')))
 dump(out/(name+'.command.json'),r)
 need(type(p.returncode) is int and p.returncode==0 and r['before']==r['after'],'command failed '+name)
 return r

def initial_paths(out,rs,libs):
 paths={p.resolve() for p in HERE.rglob('*') if p.is_file()}
 paths.update((CM/n).resolve() for n in ('build.ninja','compile_commands.json','CMakeCache.txt'))
 paths.update(Path(r['source']).resolve() for r in rs)
 paths.update(Path(r['compiler']).resolve() for r in rs)
 paths.update(Path(p).resolve() for p in libs if Path(p).is_file())
 paths.update(Path(p).resolve() for p in (sys.executable,'/usr/bin/nm','/usr/bin/ar'))
 paths.update(out/n for n in ['inputs.tsv','recipes.json','libraries.json',*[n+'.cpp' for n in MUTATIONS]])
 return paths

def hashes(paths):return {str(p):sha(p) for p in sorted(paths)}
def dependency_paths(out,rs):
 paths=set()
 for n,_,flags,source in sources(out,rs):
  paths.update(closure.dependencies((out/(n+'.d')).read_bytes(),source,flags,CM))
 return paths


def snapshot_paths(paths,out):return {out/'snapshots'/p.relative_to(ROOT):p for p in paths if p.is_relative_to(ROOT/'source')}
def materialize(out):
 src=(HERE/'original/StarPathEmbed.cpp').read_text()
 for n,(a,b) in MUTATIONS.items():
  need(src.count(a)==1,'mutant anchor '+n);(out/(n+'.cpp')).write_text(src.replace(a,b))
 (out/'inputs.tsv').write_bytes(contract.inputs())

def run(out):
 need(out.is_relative_to(BASE) and out!=BASE and not out.exists(),'fresh owned output');out.mkdir()
 inventory.check();materialize(out);rs,libs=recipe();dump(out/'recipes.json',rs);dump(out/'libraries.json',libs)
 initial=hashes(initial_paths(out,rs,libs));dump(out/'initial.json',initial)
 plan=plans(out,rs,libs);nj=len(sources(out,rs));commands=[]
 with ThreadPoolExecutor(max_workers=6) as pool:commands+=list(pool.map(lambda p:cmd(out,*p),plan[:nj]))
 paths=initial_paths(out,rs,libs)|dependency_paths(out,rs)
 need(hashes(initial_paths(out,rs,libs))==initial,'scan drift')
 for dest,source in snapshot_paths(paths,out).items():dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(source.read_bytes())
 paths|=set(snapshot_paths(paths,out));before=hashes(paths);dump(out/'before.json',before)
 print('frozen',len(before),'bindings; compiling',nj,'units',flush=True)
 with ThreadPoolExecutor(max_workers=6) as pool:commands+=list(pool.map(lambda p:cmd(out,*p),plan[nj:2*nj]))
 for p in plan[2*nj:-len(RUNS)]:commands.append(cmd(out,*p))
 dump(out/'preexecute.json',hashes({p for p in out.iterdir() if p.is_file()}))
 need(hashes(paths)==before,'preexecution source drift')
 for p in plan[-len(RUNS):]:commands.append(cmd(out,*p))
 leaf=(out/'leaf.stdout').read_bytes();need(leaf==(out/'leaf-repeat.stdout').read_bytes(),'leaf repeat')
 expected=contract.expected(leaf);(out/'expected.tsv').write_bytes(expected)
 for n in ('original','original-repeat','current','current-repeat'):contract.check((out/(n+'.stdout')).read_bytes(),expected)
 for n in MUTATIONS:
  try:contract.check((out/(n+'.stdout')).read_bytes(),expected)
  except ValueError:pass
  else:raise ValueError('semantic mutant escaped '+n)
 after=hashes(paths);dump(out/'after.json',after);need(before==after,'after drift');dump(out/'commands.json',commands)
 q=dict(status='FINITE_NATIVE_PATHEMBED_PASS',objects=113,definitions=2,observations=len(expected.splitlines()),bindings=before,commands=commands,artifacts=hashes(artifact_paths(out,rs,libs)))
 publish(q,out);print(q['status'],flush=True)

def publish(q,out):
 # A producer's byte comparisons are not acceptance: the final closure audit
 # must succeed before a pass-labelled report becomes visible.
 validate(q,out)
 with (out/'report.json').open('x') as report:
  json.dump(q,report,indent=2);report.write('\n')

def artifact_paths(out,rs,libs):
 paths={out/n for n in ('inputs.tsv','recipes.json','libraries.json','initial.json','before.json','after.json','preexecute.json','commands.json','expected.tsv')}
 paths.update(out/(n+'.cpp') for n in MUTATIONS)
 for n,_,_,_ in sources(out,rs):paths.update((out/(n+'.d'),out/(n+'.o')))
 for v in ['leaf',*VARIANTS]:paths.update((out/v,out/(v+'.map')))
 for n,_ in plans(out,rs,libs):paths.update(out/(n+'.'+ext) for ext in ('stdout','stderr','command.json'))
 return paths

def validate(q,out):
 inventory.check()
 need(q['status']=='FINITE_NATIVE_PATHEMBED_PASS','status')
 need(type(q['objects']) is int and q['objects']==113 and type(q['definitions']) is int and q['definitions']==2,'scope')
 rs,libs=recipe()
 need(json.loads((out/'recipes.json').read_text())==rs and json.loads((out/'libraries.json').read_text())==libs,'recipes')
 need((out/'inputs.tsv').read_bytes()==contract.inputs(),'independent inputs')
 src=(HERE/'original/StarPathEmbed.cpp').read_text()
 for n,(a,b) in MUTATIONS.items():need((out/(n+'.cpp')).read_text()==src.replace(a,b),'mutant source')
 initial=hashes(initial_paths(out,rs,libs));need(initial==json.loads((out/'initial.json').read_text()),'initial closure')
 paths=initial_paths(out,rs,libs)|dependency_paths(out,rs)
 for dest,source in snapshot_paths(paths,out).items():need(sha(dest)==sha(source),'snapshot')
 paths|=set(snapshot_paths(paths,out));bindings=hashes(paths)
 need(bindings==q['bindings']==json.loads((out/'before.json').read_text())==json.loads((out/'after.json').read_text()),'binding closure')
 artifacts=artifact_paths(out,rs,libs);artifact_hashes=hashes(artifacts);need(artifact_hashes==q['artifacts'],'artifact closure');current_bytes={**bindings,**artifact_hashes}
 plan=plans(out,rs,libs);commands=q['commands']
 need([(c['name'],c['command']) for c in commands]==plan,'command argv closure')
 need(commands==json.loads((out/'commands.json').read_text()),'commands mirror')
 for c in commands:
  n=c['name'];need(c==json.loads((out/(n+'.command.json')).read_text()),'command mirror')
  need(type(c['returncode']) is int and c['returncode']==0 and c['exit_type']=='normal','normal exit')
  exe=Path(c['command'][0]).resolve();need(str(exe)==c['executable'] and current_bytes[str(exe)]==c['before']==c['after'],'invocation executable')
  wanted={'size':len(contract.inputs()),'sha256':hashlib.sha256(contract.inputs()).hexdigest()} if n in RUNS else None
  need(c['stdin']==wanted,'stdin')
  for ext in ('stdout','stderr'):need(sha(out/(n+'.'+ext))==c[ext],'stdio')
 prepaths={p for p in artifacts if p.parent==out}-{out/n for n in ('after.json','commands.json','expected.tsv','preexecute.json')}
 prepaths-={out/(n+'.'+ext) for n in RUNS for ext in ('stdout','stderr','command.json')}
 need(hashes(prepaths)==json.loads((out/'preexecute.json').read_text()),'preexecution closure')
 for v in VARIANTS:
  symbols=(out/('symbols-'+v+'.stdout')).read_text()
  definitions=[line for line in symbols.splitlines() if ' T Star::embed' in line]
  need(len(definitions)==2 and any('embedEscapeText(' in x for x in definitions) and any('embedAndCompressData(' in x for x in definitions),'compiled two definitions')
  need('Star::EmbeddedCompressionMethodNames' in symbols,'native enum data')
  linkmap=(out/(v+'.map')).read_bytes();idx=next(i for i,r in enumerate(rs) if Path(r['source']).name=='StarPathEmbed.cpp')
  target=out/((str(idx) if v=='original' else v)+'.o');need(str(target).encode() in linkmap,'actual linked object')
 tables={p:(out/('archive-'+str(i)+'.stdout')).read_bytes() for i,p in enumerate(archives(libs))}
 for n,args in plan:
  if n.startswith('link-'):closure.link((out/(n[5:]+'.map')).read_bytes(),args,tables)
 leaf=(out/'leaf.stdout').read_bytes();need(leaf==(out/'leaf-repeat.stdout').read_bytes(),'leaf repeat')
 expected=contract.expected(leaf);need((out/'expected.tsv').read_bytes()==expected,'independent expected')
 need(type(q['observations']) is int and q['observations']==len(expected.splitlines()),'observations')
 for n in ('original','original-repeat','current','current-repeat'):contract.check((out/(n+'.stdout')).read_bytes(),expected)
 for n in MUTATIONS:need((out/(n+'.stdout')).read_bytes()!=expected,'normal semantic rejection '+n)
 return q

def controls(out):
 import copy
 q=json.loads((out/'report.json').read_text());validate(q,out);dest=out/'controls';dest.mkdir();results=[]
 mutations=[('binding-omission',lambda x:x['bindings'].pop(next(iter(x['bindings'])))),('expected-artifact-omission',lambda x:x['artifacts'].pop(str(out/'expected.tsv'))),('object-omission',lambda x:x['artifacts'].pop(str(out/'0.o'))),('argv-omission',lambda x:x['commands'][0]['command'].pop()),('bool-exit',lambda x:x['commands'][0].update(returncode=False))]
 for name,mutate in mutations:
  bad=copy.deepcopy(q);mutate(bad);dump(dest/(name+'.json'),bad)
  try:validate(bad,out)
  except ValueError as e:results.append({'name':name,'rejected':str(e)})
  else:raise ValueError('receipt control escaped '+name)
 bad=(out/'expected.tsv').read_bytes().split(b'\n',1)[1];(dest/'omitted-expected-row.tsv').write_bytes(bad)
 try:contract.check(bad,contract.expected((out/'leaf.stdout').read_bytes()))
 except ValueError as e:results.append({'name':'omitted-expected-row','rejected':str(e)})
 else:raise ValueError('expected control escaped')
 dump(dest/'results.json',results);print(json.dumps(results))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['run','verify','controls']);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output).resolve()
 if a.phase=='run':run(out)
 elif a.phase=='controls':controls(out)
 else:print(validate(json.loads((out/'report.json').read_text()),out)['status'])
