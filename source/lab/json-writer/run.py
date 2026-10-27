#!/usr/bin/env python3
"""Finite native-only calibration; verify is read-only and never compiles."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=ROOT/'build/json-writer-native-r1'
CM=ROOT/'build/behavior/path-embed-combined-r1/reference/cmake'
GAME=CM.parent/'bin/starbound'
PROOF=Path(str(GAME)+'.behavior-build.json')
NINJA='/nix/store/ndfr0d2nizw172ppn99n505ikpsq9727-ninja-1.13.2/bin/ninja'
CANONICAL_SDK='/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk'
HEADER=ROOT/'source/core/StarJsonParser.hpp'
ORIGINAL=HERE/'original/StarJsonParser.hpp'
HEADER_SHA='ab19bf44ac9d72041b7c3563fca57d846bc15c5cf459a4cd868d4163af33bec4'
sys.path.insert(0,str(HERE.parent/'path-embed-replay'))
sys.path.insert(0,str(HERE.parent/'behavior'))
import sdk_witness,expanded_invocation,archive_identity,object_inventory,link_trace,build_provenance
import model,inventory
MUTATIONS={
 'key-nul':('while (c && len) {','while (len) {'),
 'escape':("case '\\n':\n            write('\\\\');\n            write('n');", "case '\\n':\n            write('\\\\');\n            write('x');"),
 'array-pretty':("if (currentState() == ArrayElement) {\n      if (m_pretty)\n        write(' ');", "if (currentState() == ArrayElement) {\n      if (m_pretty)\n        write('_');"),
 'indent':('i < m_state.size() / 2','i < m_state.size() / 3'),
 'container-pop':('if (last == state)\n        return;', 'if (last != state)\n        return;')}
VARIANTS=['original','current',*MUTATIONS]
MODULES=[sdk_witness,expanded_invocation,archive_identity,object_inventory,link_trace,build_provenance]

def need(ok,msg):
 if not ok:raise ValueError(msg)
def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),default=lambda x:{'bytes':x.hex()} if type(x) is bytes else (_ for _ in ()).throw(TypeError(type(x))))
def equal(a,b,msg):need(encoded(a)==encoded(b),msg)
def digest(data):return hashlib.sha256(data).hexdigest()
def sha(p):return digest(Path(p).read_bytes())
def dump(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def put(p,data):
 with Path(p).open('xb') as f:f.write(data)
def hashes(paths):return {str(p):sha(p) for p in sorted(set(paths))}
def safe(out,fresh=False):
 need(out.is_absolute() and out==Path(os.path.normpath(out)) and out.parent==BASE,'owned generation path')
 need(not any(p.is_symlink() for p in (out,*out.parents)),'output ancestor symlink')
 if fresh:need(not out.exists(),'exclusive fresh generation')
 elif out.exists():
  for d,dirs,files in os.walk(out,followlinks=False):
   for n in dirs+files:
    st=(Path(d)/n).lstat();need(stat.S_ISDIR(st.st_mode) or (stat.S_ISREG(st.st_mode) and st.st_nlink==1),'owned symlink/hardlink/nonregular')
def env(out):return {'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(out/'home'),'TMPDIR':str(out/'tmp'),'LANG':'C','LC_ALL':'C'}
def tool(p):
 canonical,hops=sdk_witness._resolve(str(p));return {'requested':str(p),'canonical':canonical,'hops':hops,**sdk_witness._digest(canonical)}
def invoke(out,name,argv,stdin=b''):
 argv=list(map(str,argv));before=tool(argv[0])
 p=subprocess.run(argv,cwd=CM,env=env(out),input=stdin,capture_output=True,timeout=150)
 put(out/(name+'.stdout'),p.stdout);put(out/(name+'.stderr'),p.stderr)
 q={'name':name,'argv':argv,'cwd':str(CM),'env':env(out),'tool_before':before,'tool_after':tool(argv[0]),'stdin':{'sha256':digest(stdin),'size':len(stdin)},'stdout':digest(p.stdout),'stderr':digest(p.stderr),'exit':p.returncode,'exit_type':'normal' if p.returncode>=0 else 'signal'}
 dump(out/(name+'.command.json'),q)
 equal(q['tool_before'],q['tool_after'],'tool drift '+name)
 need(type(p.returncode) is int and p.returncode==0,'nonzero command '+name)
 return q

def recipe():
 db=json.loads((CM/'compile_commands.json').read_bytes());lines=(CM/'build.ninja').read_text().splitlines()
 i=next(i for i,l in enumerate(lines) if l.startswith('build ') and '/bin/starbound:' in l)
 objs=[CM/p for p in shlex.split(lines[i].split(': ',1)[1])[1:] if p.endswith('.o') and p.startswith(('core/','extern/'))]
 need(len(objs)==113,'113 ordered prebound native inputs')
 libs=shlex.split(next(l.split(' = ',1)[1] for l in lines[i+1:i+18] if l.startswith('  LINK_LIBRARIES = ')))
 libs=[str(CM/p) if p.endswith('.a') and not Path(p).is_absolute() else p for p in libs]
 need(not any(Path(p).name=='libstar_engine_ffi.a' for p in libs),'no project Rust aggregate archive')
 rows=[next(r for r in db if Path(r['output'])==obj) for obj in objs]
 need(not any('STAR_USE_RUST' in r['command'] for r in rows),'native compile selectors')
 r=next(r for r in rows if Path(r['file']).name=='StarUnicode.cpp');args=shlex.split(r['command']);flags=[];skip=False
 for a in args[1:]:
  if skip:skip=False;continue
  if a=='-o':skip=True
  elif a not in ('-c',r['file']):flags.append(a)
 cache=(CM/'CMakeCache.txt').read_text();selectors=re.findall(r'^(STAR_USE_RUST[^:]*):BOOL=(.*)$',cache,re.M)
 need(len(selectors)==25 and all(v=='OFF' for _,v in selectors),'25 OFF CMake selectors')
 return {'compiler':args[0],'flags':flags,'objects':list(map(str,objs)),'libraries':libs,'rows':rows,'selectors':selectors}

def header(out,v):return ORIGINAL if v=='original' else HEADER if v=='current' else out/(v+'.hpp')
def compile_argv(out,r,v):return [r['compiler'],*r['flags'],'-DLAB_HEADER="'+str(header(out,v))+'"']
def link_argv(out,r,v):return [r['compiler'],*r['flags'],str(out/(v+'.o')),*r['objects'],*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(out/'links'/v/'native.map'),'-o',str(out/'links'/v/'native'),'-Wl,-t,-trace_implicit_libraries']
def plans(out,r):
 plan=[('native-deps',[NINJA,'-t','deps',*[str(Path(p).relative_to(CM)) for p in r['objects']]],b'')]
 plan += [('deps-'+v,[*compile_argv(out,r,v),'-M','-MF',str(out/(v+'.d')),str(HERE/'lab.cpp')],b'') for v in VARIANTS]
 plan += [('ast-'+v,[*compile_argv(out,r,v),'-fsyntax-only','-Xclang','-ast-dump=json','-Xclang','-ast-dump-filter=Star::JsonWriter',str(HERE/'lab.cpp')],b'') for v in ('original','current')]
 plan += [('compile-'+v,[*compile_argv(out,r,v),'-c',str(HERE/'lab.cpp'),'-o',str(out/(v+'.o'))],b'') for v in VARIANTS]
 for v in VARIANTS:
  a=link_argv(out,r,v);plan += [('expand-'+v,[a[0],'-###',*a[1:]],b''),('link-'+v,a,b'')]
 plan += [('run-'+v+suffix,[str(out/'links'/v/'native')],model.inputs()) for v in VARIANTS for suffix in ('','-repeat')]
 return [(n,list(map(str,a)),b) for n,a,b in plan]

class Evidence:
 def __init__(self,overrides=None):self.overrides=overrides or {}
 def data(self,p):return Path(self.overrides.get(str(p),p)).read_bytes()
 def json(self,p):return json.loads(self.data(p))
 def sha(self,p):return digest(self.data(p))
 def hashes(self,paths):return {str(p):self.sha(p) for p in sorted(set(paths))}

def native_dependencies(out,r,e):
 text=e.data(out/'native-deps.stdout').decode();blocks=text.strip().split('\n\n');found={};result=set()
 for block in blocks:
  lines=block.splitlines();m=re.fullmatch(r'(.+): #deps ([0-9]+), deps mtime ([0-9]+) \(VALID\)',lines[0])
  need(m is not None,'valid native Ninja dependency row')
  p=str(CM/m[1]);need(p not in found,'duplicate native dependency job')
  deps=[Path(x.strip()) if Path(x.strip()).is_absolute() else CM/x.strip() for x in lines[1:]]
  need(len(deps)==int(m[2]),'native dependency count')
  need(str(next(z['file'] for z in r['rows'] if z['output']==p)) in set(map(str,deps)),'native primary source dependency')
  found[p]=deps;result.update(deps)
 equal(list(found),r['objects'],'ordered dependency jobs')
 return result

def fixture_dependencies(out,e):
 result=set()
 for v in VARIANTS:
  text=e.data(out/(v+'.d')).decode().replace('\\\n',' ')
  a,b=text.split(':',1);need(shlex.split(a)==['lab.o'],'fixture dep target')
  deps={Path(x) if Path(x).is_absolute() else CM/x for x in shlex.split(b)}
  need(HERE/'lab.cpp' in deps and header(out,v) in deps,'fixture primary/header dependencies')
  result.update(deps)
 return result

def game_closure():
 q=json.loads(PROOF.read_bytes())
 equal(build_provenance.source_snapshot(ROOT),q['source_files'],'1495 current source closure vs sealed native game')
 equal(build_provenance._compile_source_inputs(CM),q['compile_source_files'],'472 configured sources')
 need(len(q['source_files'])==1495 and len(q['compile_source_files'])==472,'source scope')
 paths={ROOT/p for p in q['source_files']}|{Path(p) for p in q['compile_source_files']}|{PROOF,GAME}
 need(sha(GAME)==q['binary_sha256'],'sealed game bytes')
 for p,h in q['build_identity']['files'].items():need(sha(p)==h,'native build recipe drift');paths.add(Path(p))
 for t in q['build_identity']['tools'].values():need(sha(t['path'])==t['sha256'],'historical tool bytes drift');paths.add(Path(t['path']))
 return paths

def inputs(out,r,e):
 paths=game_closure()|native_dependencies(out,r,e)|fixture_dependencies(out,e)
 paths.update(HERE/n for n in ('run.py','model.py','inventory.py','lab.cpp','README.md','original/StarJsonParser.hpp'))
 paths.update(Path(m.__file__).resolve() for m in MODULES)
 paths.add(HERE.parent/'native_artifacts.py')
 paths.update((CM/'CMakeFiles/rules.ninja',CM/'.ninja_deps',CM/'.ninja_log',HEADER,ROOT/'source/core/StarJsonBuilder.hpp',ROOT/'source/lab/migration/catalog.json',Path(sys.executable).resolve(),Path(NINJA)))
 paths.update(map(Path,r['objects']));paths.update(Path(x) for x in r['libraries'] if Path(x).is_file())
 paths.update(out/(v+'.hpp') for v in MUTATIONS)
 paths.update(out/n for n in ('inputs.tsv','expected.tsv','recipe.json','sdk-before.json'))
 return paths

def expansion(out,v,e):
 lines=e.data(out/('expand-'+v+'.stderr')).decode().splitlines();a=[shlex.split(l) for l in lines if l.lstrip().startswith('"')]
 need(len(a)==1,'one expanded driver linker');return a[0]
def archive_tables(bound):
 blobs={p.encode():Path(p).read_bytes() for p in bound['inventory']['file_inputs'] if p.endswith('.a')}
 tables={p:b''.join(m['name']+b'\n' for m in archive_identity.arm64_archive_members(b)) for p,b in blobs.items()}
 return blobs,tables

def reconcile_link(out,r,v,e,sdk):
 target=out/'links'/v;ex=expansion(out,v,e);bound=e.json(target/'expanded-before.json')
 expanded_invocation.verify(bound,ex);inv=expanded_invocation.parse(ex)
 equal(inv['architecture'],'arm64','architecture');equal(inv['sdk'],sdk,'configured SDK')
 need(inv['platform'][0]=='macos','macOS platform')
 equal(inv['outputs'],[str(target/'native'),str(target/'native.map')],'link output membership')
 objs=[p.encode() for p in inv['file_inputs'] if p.endswith('.o')]
 equal(objs,[p.encode() for p in link_argv(out,r,v) if p.endswith('.o')],'driver-first ordered object membership')
 blobs,tables=archive_tables(bound)
 equal(e.json(target/'archive-tables.json'),{p.hex():t.hex() for p,t in tables.items()},'physical archive table')
 trace=link_trace.parse(e.data(out/('link-'+v+'.stdout')),objs,tables)
 mapped=object_inventory.reconcile(e.data(target/'native.map'),objs,tables,blobs)
 paths=trace['sdk_paths']+mapped['unresolved_origins']+[x['source'] for x in trace['indirect_declarations']]
 consumed=sdk_witness.reconcile_consumed(e.json(out/'sdk-before.json'),[os.fsdecode(p) for p in paths],requested_root=sdk,expected_canonical_root=CANONICAL_SDK)
 equal(consumed,e.json(target/'consumed.json'),'consumed SDK origins')
 return {'objects':len(objs),'loaded_archive_members':len(trace['archive_members']),'map_archive_members':len(mapped['used_archive_members']),'physical_duplicate_witnesses':[{k:(x.hex() if type(x) is bytes else x) for k,x in row.items()} for row in mapped['physical_member_identities']],'sdk_records':len(consumed)}

def artifacts(out,r):
 paths={out/n for n in ('recipe.json','inputs.tsv','expected.tsv','sdk-before.json','sdk-after.json','before.json','after.json','inventory-original.json','inventory-current.json','preexecute.json')}
 paths.update(out/(v+'.d') for v in VARIANTS);paths.update(out/(v+'.o') for v in VARIANTS)
 paths.update(out/(v+'.hpp') for v in MUTATIONS)
 for n,_,_ in plans(out,r):paths.update(out/(n+'.'+s) for s in ('stdout','stderr','command.json'))
 for v in VARIANTS:paths.update(out/'links'/v/n for n in ('native','native.map','expanded-before.json','archive-tables.json','consumed.json'))
 return paths

def preexecute(out,r):
 paths=artifacts(out,r)-{out/n for n in ('sdk-after.json','after.json','preexecute.json')}
 for v in VARIANTS:
  for suffix in ('','-repeat'):
   paths.difference_update(out/('run-'+v+suffix+'.'+s) for s in ('stdout','stderr','command.json'))
 return paths

def snapshots(out,paths):return {out/'snapshots'/p.relative_to(ROOT):p for p in paths if p.is_relative_to(ROOT) and not p.is_relative_to(BASE)}

def verify(out,q=None,e=None):
 safe(out);e=e or Evidence();q=q or e.json(out/'report.json');r=recipe()
 equal(q['status'],'FINITE_NATIVE_JSON_WRITER_PASS','status')
 equal(q['definition_count'],21,'class definition scope');need(type(q['definition_count']) is int,'typed scope')
 equal(e.json(out/'recipe.json'),r,'independent configured recipe')
 need(e.sha(HEADER)==e.sha(ORIGINAL)==HEADER_SHA,'frozen original/current source witness')
 model.literal_checks();equal(e.data(out/'inputs.tsv'),model.inputs(),'independent event corpus')
 equal(e.data(out/'expected.tsv'),model.expected(),'independent expected model')
 for v,(a,b) in MUTATIONS.items():equal(e.data(out/(v+'.hpp')),e.data(ORIGINAL).replace(a.encode(),b.encode()),'one-edit native mutant')
 sdk=r['flags'][r['flags'].index('-isysroot')+1]
 sdk_witness.verify(e.json(out/'sdk-before.json'),sdk,CANONICAL_SDK)
 equal(e.json(out/'sdk-before.json'),e.json(out/'sdk-after.json'),'before/after SDK')
 paths=inputs(out,r,e);snap=snapshots(out,paths)
 for dest,src in snap.items():equal(e.data(dest),e.data(src),'frozen source/dependency snapshot')
 bindings=e.hashes(paths|set(snap))
 equal(bindings,e.json(out/'before.json'),'complete required before bindings')
 equal(bindings,e.json(out/'after.json'),'complete required after bindings')
 equal(bindings,q['bindings'],'report required binding set')
 equal(e.hashes(artifacts(out,r)),q['artifacts'],'complete actual artifact membership')
 equal(e.hashes(preexecute(out,r)),e.json(out/'preexecute.json'),'preexecution artifact freeze')
 for n,a,b in plans(out,r):
  c=e.json(out/(n+'.command.json'))
  equal(c['name'],n,'receipt command name');equal(c['argv'],a,'frozen argv');equal(c['cwd'],str(CM),'cwd');equal(c['env'],env(out),'environment')
  need(type(c['exit']) is int and c['exit']==0 and c['exit_type']=='normal','typed normal exit')
  equal(c['stdin'],{'sha256':digest(b),'size':len(b)},'stdin')
  equal(c['tool_before'],tool(a[0]),'command executable before');equal(c['tool_after'],tool(a[0]),'command executable after')
  for s in ('stdout','stderr'):equal(c[s],e.sha(out/(n+'.'+s)),'stdio hash')
 for v in ('original','current'):
  equal(e.json(out/('inventory-'+v+'.json')),inventory.reconcile(header(out,v),e.data(out/('ast-'+v+'.stdout'))),'compiler/manual all-body reconciliation')
 expected=model.expected();comparisons={}
 for v in VARIANTS:
  first=e.data(out/('run-'+v+'.stdout'));equal(first,e.data(out/('run-'+v+'-repeat.stdout')),'repeat trace '+v)
  if v in ('original','current'):equal(first,expected,'independent native model '+v)
  else:need(first!=expected,'normally exiting semantic mutant escaped '+v)
  comparisons[v]=reconcile_link(out,r,v,e,sdk)
 equal(q['links'],comparisons,'link conclusions')
 return q

def run(out):
 safe(out,True);out.mkdir(parents=True);(out/'home').mkdir();(out/'tmp').mkdir()
 r=recipe();model.literal_checks()
 need(sha(HEADER)==sha(ORIGINAL)==HEADER_SHA,'original/current header bytes')
 for v,(a,b) in MUTATIONS.items():
  source=ORIGINAL.read_text();need(source.count(a)==1,'unique mutant anchor '+v);put(out/(v+'.hpp'),source.replace(a,b).encode())
 put(out/'inputs.tsv',model.inputs());put(out/'expected.tsv',model.expected());dump(out/'recipe.json',r)
 sdk=r['flags'][r['flags'].index('-isysroot')+1]
 dump(out/'sdk-before.json',sdk_witness.capture(sdk,CANONICAL_SDK))
 plan=plans(out,r);invoke(out,*plan[0])
 with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda p:invoke(out,*p),[p for p in plan if p[0].startswith('deps-')]))
 paths=inputs(out,r,Evidence());snap=snapshots(out,paths)
 for dest,src in snap.items():dest.parent.mkdir(parents=True,exist_ok=True);put(dest,src.read_bytes())
 before=hashes(paths|set(snap));dump(out/'before.json',before)
 print('FROZEN',len(before),'bindings; expected',len(model.expected().splitlines()),'observations BEFORE AST/compile/run',flush=True)
 for p in plan:
  if p[0].startswith('ast-'):invoke(out,*p)
 for v in ('original','current'):dump(out/('inventory-'+v+'.json'),inventory.reconcile(header(out,v),(out/('ast-'+v+'.stdout')).read_bytes()))
 with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda p:invoke(out,*p),[p for p in plan if p[0].startswith('compile-')]))
 print('compiled 7 native fixtures; 113 existing objects are PREBOUND not rebuilt',flush=True)
 links={}
 for v in VARIANTS:
  target=out/'links'/v;target.mkdir(parents=True)
  invoke(out,'expand-'+v,[r['compiler'],'-###',*link_argv(out,r,v)[1:]])
  bound=expanded_invocation.bind(expansion(out,v,Evidence()));dump(target/'expanded-before.json',bound)
  blobs,tables=archive_tables(bound);dump(target/'archive-tables.json',{p.hex():t.hex() for p,t in tables.items()})
  invoke(out,'link-'+v,link_argv(out,r,v));expanded_invocation.verify(bound,expansion(out,v,Evidence()))
  inv=bound['inventory'];objs=[p.encode() for p in inv['file_inputs'] if p.endswith('.o')]
  trace=link_trace.parse((out/('link-'+v+'.stdout')).read_bytes(),objs,tables)
  mapped=object_inventory.reconcile((target/'native.map').read_bytes(),objs,tables,blobs)
  sp=trace['sdk_paths']+mapped['unresolved_origins']+[x['source'] for x in trace['indirect_declarations']]
  dump(target/'consumed.json',sdk_witness.reconcile_consumed(json.loads((out/'sdk-before.json').read_bytes()),[os.fsdecode(p) for p in sp],requested_root=sdk,expected_canonical_root=CANONICAL_SDK))
  links[v]=reconcile_link(out,r,v,Evidence(),sdk)
  print('linked/reconciled',v,flush=True)
 equal(hashes(paths|set(snap)),before,'before execution source/input drift')
 dump(out/'preexecute.json',hashes(preexecute(out,r)))
 for p in plan:
  if p[0].startswith('run-'):invoke(out,*p)
 dump(out/'sdk-after.json',sdk_witness.capture(sdk,CANONICAL_SDK));after=hashes(paths|set(snap));dump(out/'after.json',after)
 q={'status':'FINITE_NATIVE_JSON_WRITER_PASS','definition_count':21,'bindings':before,'artifacts':hashes(artifacts(out,r)),'links':links,
    'limits':['finite corpus only; NOT Rust, ABI or application qualification','113 retained native objects prebound, NOT freshly rebuilt','OOM, arbitrary pointers and native allocation/destructor fault timing unproved','framework implementations/interpreter/dylib transitive closure and transient edit/revert unproved','hex-8/substr branches unreachable under actual isPrintable/helper domain; not runtime-covered']}
 verify(out,q)
 # Exclusive publication AFTER every claimed required verification gate.
 dump(out/'report.json',q);print(q['status'],flush=True)

def controls(out):
 safe(out);q=verify(out);dest=out/'controls';need(not dest.exists(),'exclusive controls');dest.mkdir();results=[]
 tests=[('missing-binding',lambda x:x['bindings'].pop(next(iter(x['bindings'])))),('missing-artifact',lambda x:x['artifacts'].pop(str(out/'current.o'))),('false-count',lambda x:x.update(definition_count=True))]
 for name,mutate in tests:
  bad=copy.deepcopy(q);mutate(bad);dump(dest/(name+'.json'),bad)
  try:verify(out,bad)
  except (ValueError,KeyError,FileNotFoundError) as ex:results.append({'name':name,'rejected':str(ex)[:200]})
  else:raise ValueError('control escaped '+name)
 # Actual malformed/false-bool command files and corrupted source/artifact
 # clones are read through the same verifier, without touching acquisitions.
 for name,path,data in [('malformed',out/'compile-current.command.json',b'{'),('false-exit',out/'run-current.command.json',json.dumps({**json.loads((out/'run-current.command.json').read_bytes()),'exit':False}).encode()),('source',HEADER,HEADER.read_bytes()+b'\n'),('artifact',out/'current.o',(out/'current.o').read_bytes()+b'bad')]:
  clone=dest/(name+'.clone');put(clone,data);bad=copy.deepcopy(q)
  if str(path) in bad['artifacts']:bad['artifacts'][str(path)]=digest(data)
  if str(path) in bad['bindings']:bad['bindings'][str(path)]=digest(data)
  try:verify(out,bad,Evidence({str(path):str(clone)}))
  except (ValueError,KeyError,FileNotFoundError) as ex:results.append({'name':name,'rejected':str(ex)[:200]})
  else:raise ValueError('clone control escaped '+name)
 dump(dest/'results.json',results);print(json.dumps(results))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['run','verify','controls']);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output)
 if a.phase=='run':run(out)
 elif a.phase=='controls':controls(out)
 else:print(verify(out)['status'])
