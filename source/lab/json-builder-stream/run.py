#!/usr/bin/env python3
"""Native-only JsonBuilderStream calibration; verify never writes or compiles."""
import argparse
import copy
import hashlib
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
BASE=ROOT/'build/json-builder-stream-native-r1'
CM=ROOT/'build/behavior/path-embed-combined-r1/reference/cmake'
GAME=CM.parent/'bin/starbound'
PROOF=Path(str(GAME)+'.behavior-build.json')
NINJA='/nix/store/ndfr0d2nizw172ppn99n505ikpsq9727-ninja-1.13.2/bin/ninja'
CANONICAL_SDK='/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk'
HEADER=ROOT/'source/core/StarJsonBuilder.hpp'
SOURCE=ROOT/'source/core/StarJsonBuilder.cpp'
ORIGINAL=HERE/'original/StarJsonBuilder.cpp'
HEADER_SHA='f201d6eab6e60a1bfd82439b0b405c8fffd825339a4b3614604b0cfeb39c6294'
SOURCE_SHA='8fde1f301b9cd47e643ab58145a33fafcc64e6a294040dd242f53c1cd0507591'
sys.path.insert(0,str(HERE.parent/'path-embed-replay'))
sys.path.insert(0,str(HERE.parent/'behavior'))
import sdk_witness,expanded_invocation,archive_identity,object_inventory,link_trace,build_provenance
import model,inventory
MUTATIONS={
 'array-order':('      array.reverse();','      /* mutant: no reverse */'),
 'object-order':('      Json v = pop();\n      String k = pop().toString();','      String k = pop().toString();\n      Json v = pop();'),
 'sentry-take':('    return m_stack.takeLast().take();','    return m_stack.takeLast().value(Json());')}
VARIANTS=['original','current',*MUTATIONS]
MODULES=[sdk_witness,expanded_invocation,archive_identity,object_inventory,link_trace,build_provenance]

def need(ok,msg):
 if not ok:raise ValueError(msg)
def encoded(v):
 def leaf(x):
  if type(x) is bytes:return {'raw_bytes_hex':x.hex()}
  raise TypeError(type(x))
 return json.dumps(v,sort_keys=True,separators=(',',':'),default=leaf)
def equal(a,b,msg):
 if type(a) is bytes and type(b) is bytes:need(a==b,msg)
 else:need(encoded(a)==encoded(b),msg)
def digest(b):return hashlib.sha256(b).hexdigest()
def sha(p):return digest(Path(p).read_bytes())
def put(p,b):
 with Path(p).open('xb') as f:f.write(b)
def dump(p,v):put(p,(json.dumps(v,indent=2)+'\n').encode())
def hashes(paths):return {str(p):sha(p) for p in sorted(set(paths))}
def safe(out,fresh=False):
 need(out.is_absolute() and out==Path(os.path.normpath(out)) and out.parent==BASE,'owned generation')
 need(not any(p.is_symlink() for p in (out,*out.parents)),'ancestor symlink')
 if fresh:need(not out.exists(),'exclusive fresh generation')
 elif out.exists():
  for d,ds,fs in os.walk(out,followlinks=False):
   for n in ds+fs:
    st=(Path(d)/n).lstat();need(stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode) and st.st_nlink==1,'output symlink/hardlink/special file')
def env(out):return {'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(out/'home'),'TMPDIR':str(out/'tmp'),'LANG':'C','LC_ALL':'C'}
def tool(p):
 canonical,hops=sdk_witness._resolve(str(p));return {'requested':str(p),'canonical':canonical,'hops':hops,**sdk_witness._digest(canonical)}
def invoke(out,name,argv,stdin=b''):
 argv=list(map(str,argv));before=tool(argv[0]);p=subprocess.run(argv,cwd=CM,env=env(out),input=stdin,capture_output=True,timeout=150)
 put(out/(name+'.stdout'),p.stdout);put(out/(name+'.stderr'),p.stderr)
 q={'name':name,'argv':argv,'cwd':str(CM),'env':env(out),'tool_before':before,'tool_after':tool(argv[0]),'stdin':{'sha256':digest(stdin),'size':len(stdin)},'stdout':digest(p.stdout),'stderr':digest(p.stderr),'exit':p.returncode,'exit_type':'normal' if p.returncode>=0 else 'signal'}
 dump(out/(name+'.command.json'),q);equal(q['tool_before'],q['tool_after'],'tool drift '+name)
 need(type(p.returncode) is int and p.returncode==0,'nonzero command '+name)
 return q

def recipe():
 db=json.loads((CM/'compile_commands.json').read_bytes());lines=(CM/'build.ninja').read_text().splitlines()
 i=next(i for i,l in enumerate(lines) if l.startswith('build ') and '/bin/starbound:' in l)
 objs=[CM/p for p in shlex.split(lines[i].split(': ',1)[1])[1:] if p.endswith('.o') and p.startswith(('core/','extern/'))]
 need(len(objs)==113 and len(set(objs))==113,'113 unique ordered prebound native inputs')
 selected=[p for p in objs if p.name=='StarJsonBuilder.cpp.o'];need(len(selected)==1,'one replaced builder object')
 libs=shlex.split(next(l.split(' = ',1)[1] for l in lines[i+1:i+18] if l.startswith('  LINK_LIBRARIES = ')))
 libs=[str(CM/p) if p.endswith('.a') and not Path(p).is_absolute() else p for p in libs]
 need(not any(Path(p).name=='libstar_engine_ffi.a' for p in libs),'no project Rust archive')
 rows=[next(r for r in db if Path(r['output'])==obj) for obj in objs]
 need(not any('STAR_USE_RUST' in r['command'] for r in rows),'native selectors')
 r=next(r for r in rows if Path(r['file'])==SOURCE);args=shlex.split(r['command']);flags=[];skip=False
 for a in args[1:]:
  if skip:skip=False;continue
  if a=='-o':skip=True
  elif a not in ('-c',r['file']):flags.append(a)
 selectors=re.findall(r'^(STAR_USE_RUST[^:]*):BOOL=(.*)$',(CM/'CMakeCache.txt').read_text(),re.M)
 need(len(selectors)==25 and all(v=='OFF' for _,v in selectors),'25 evaluated OFF flags')
 return {'compiler':args[0],'flags':flags,'objects':list(map(str,objs)),'replaced_object':str(selected[0]),'libraries':libs,'rows':rows,'selectors':selectors}
def source(out,v):return ORIGINAL if v=='original' else SOURCE if v=='current' else out/(v+'.cpp')
def ordered_objects(out,r,v):
 objs=[str(out/(v+'.o')) if p==r['replaced_object'] else p for p in r['objects']]
 need(len(objs)==113 and r['replaced_object'] not in objs and len(set(objs))==113,'exact one ordered object replacement')
 return [str(out/'fixture.o'),*objs]
def link_argv(out,r,v):return [r['compiler'],*r['flags'],*ordered_objects(out,r,v),*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(out/'links'/v/'native.map'),'-o',str(out/'links'/v/'native'),'-Wl,-t,-trace_implicit_libraries']
def plans(out,r):
 pre=[('native-deps',[NINJA,'-t','deps',*[str(Path(p).relative_to(CM)) for p in r['objects']]],b'')]
 pre += [('deps-'+v,[r['compiler'],*r['flags'],'-M','-MT',v+'.o','-MF',str(out/(v+'.d')),str(source(out,v))],b'') for v in VARIANTS]
 pre += [('deps-fixture',[r['compiler'],*r['flags'],'-M','-MT','fixture.o','-MF',str(out/'fixture.d'),str(HERE/'lab.cpp')],b'')]
 ast=[('ast-'+v,[r['compiler'],*r['flags'],'-fsyntax-only','-Xclang','-ast-dump=json','-Xclang','-ast-dump-filter=Star::JsonBuilderStream',str(source(out,v))],b'') for v in ('original','current')]
 ast += [('ast-fixture',[r['compiler'],*r['flags'],'-fsyntax-only','-Xclang','-ast-dump=json','-Xclang','-ast-dump-filter=Star::JsonBuilderStream',str(HERE/'lab.cpp')],b'')]
 comp=[('compile-'+v,[r['compiler'],*r['flags'],'-c',str(source(out,v)),'-o',str(out/(v+'.o'))],b'') for v in VARIANTS]
 comp += [('compile-fixture',[r['compiler'],*r['flags'],'-c',str(HERE/'lab.cpp'),'-o',str(out/'fixture.o')],b'')]
 links=[]
 for v in VARIANTS:
  a=link_argv(out,r,v);links += [('expand-'+v,[a[0],'-###',*a[1:]],b''),('link-'+v,a,b'')]
 runs=[('run-'+v+suffix,[str(out/'links'/v/'native')],model.inputs()) for v in VARIANTS for suffix in ('','-repeat')]
 return [(n,list(map(str,a)),b) for n,a,b in pre+ast+comp+links+runs]
class Evidence:
 def __init__(self,overrides=None):self.overrides=overrides or {}
 def data(self,p):return Path(self.overrides.get(str(p),p)).read_bytes()
 def json(self,p):return json.loads(self.data(p))
 def sha(self,p):return digest(self.data(p))
 def hashes(self,paths):return {str(p):self.sha(p) for p in sorted(set(paths))}
def native_dependencies(out,r,e):
 blocks=e.data(out/'native-deps.stdout').decode().strip().split('\n\n');found={};result=set()
 for block in blocks:
  lines=block.splitlines();m=re.fullmatch(r'(.+): #deps ([0-9]+), deps mtime ([0-9]+) \(VALID\)',lines[0]);need(m is not None,'valid Ninja dependency block')
  p=str(CM/m[1]);need(p not in found,'duplicate dependency job')
  deps=[Path(x.strip()) if Path(x.strip()).is_absolute() else CM/x.strip() for x in lines[1:]]
  need(len(deps)==int(m[2]),'native deps count');need(str(next(z['file'] for z in r['rows'] if z['output']==p)) in set(map(str,deps)),'primary dependency')
  found[p]=deps;result.update(deps)
 equal(list(found),r['objects'],'ordered native deps');return result
def fixture_dependencies(out,e):
 result=set()
 for v in [*VARIANTS,'fixture']:
  a,b=e.data(out/(v+'.d')).decode().replace('\\\n',' ').split(':',1);equal(shlex.split(a),[v+'.o'],'dep target')
  deps={Path(x) if Path(x).is_absolute() else CM/x for x in shlex.split(b)}
  need((HERE/'lab.cpp' if v=='fixture' else source(out,v)) in deps,'fixture/source primary dependency');need(HEADER in deps or HERE/'original/StarJsonBuilder.hpp' in deps,'native header dependency')
  result.update(deps)
 return result
def game_closure():
 q=json.loads(PROOF.read_bytes());equal(build_provenance.source_snapshot(ROOT),q['source_files'],'1495 unchanged production source closure');equal(build_provenance._compile_source_inputs(CM),q['compile_source_files'],'472 configured sources')
 need(len(q['source_files'])==1495 and len(q['compile_source_files'])==472,'source cardinality');need(sha(GAME)==q['binary_sha256'],'game bytes')
 paths={ROOT/p for p in q['source_files']}|{Path(p) for p in q['compile_source_files']}|{PROOF,GAME}
 for p,h in q['build_identity']['files'].items():need(sha(p)==h,'recipe drift');paths.add(Path(p))
 for t in q['build_identity']['tools'].values():need(sha(t['path'])==t['sha256'],'tool drift');paths.add(Path(t['path']))
 return paths
def inputs(out,r,e):
 paths=game_closure()|native_dependencies(out,r,e)|fixture_dependencies(out,e)
 paths.update(HERE/n for n in ('run.py','model.py','inventory.py','lab.cpp','README.md','test_lab.py','original/StarJsonBuilder.cpp','original/StarJsonBuilder.hpp'))
 paths.update(Path(m.__file__).resolve() for m in MODULES)
 paths.add(HERE.parent/'native_artifacts.py')
 paths.update((CM/'CMakeFiles/rules.ninja',CM/'.ninja_deps',CM/'.ninja_log',HEADER,SOURCE,ROOT/'source/lab/migration/catalog.json',Path(sys.executable).resolve(),Path(NINJA)))
 paths.update(map(Path,r['objects']));paths.update(Path(x) for x in r['libraries'] if Path(x).is_file());paths.update(out/(v+'.cpp') for v in MUTATIONS)
 paths.update(out/n for n in ('inputs.tsv','expected.tsv','recipe.json','sdk-before.json'))
 return paths
def snapshots(out,paths):return {out/'snapshots'/p.relative_to(ROOT):p for p in paths if p.is_relative_to(ROOT) and not p.is_relative_to(BASE)}
def expansion(out,v,e):
 a=[shlex.split(l) for l in e.data(out/('expand-'+v+'.stderr')).decode().splitlines() if l.lstrip().startswith('"')];need(len(a)==1,'one linker expansion');return a[0]
def archive_tables(bound):
 blobs={p.encode():Path(p).read_bytes() for p in bound['inventory']['file_inputs'] if p.endswith('.a')}
 tables={p:b''.join(m['name']+b'\n' for m in archive_identity.arm64_archive_members(b)) for p,b in blobs.items()};return blobs,tables
def reconcile_link(out,r,v,e,sdk):
 target=out/'links'/v;ex=expansion(out,v,e);bound=e.json(target/'expanded-before.json');expanded_invocation.verify(bound,ex);inv=expanded_invocation.parse(ex)
 equal(inv['architecture'],'arm64','arch');equal(inv['sdk'],sdk,'SDK');need(inv['platform'][0]=='macos','platform');equal(inv['outputs'],[str(target/'native'),str(target/'native.map')],'output membership')
 objs=[p.encode() for p in inv['file_inputs'] if p.endswith('.o')];equal(objs,[p.encode() for p in ordered_objects(out,r,v)],'ordered replacement identity')
 blobs,tables=archive_tables(bound);equal(e.json(target/'archive-tables.json'),{p.hex():t.hex() for p,t in tables.items()},'physical archive table')
 trace=link_trace.parse(e.data(out/('link-'+v+'.stdout')),objs,tables);mapped=object_inventory.reconcile(e.data(target/'native.map'),objs,tables,blobs)
 paths=trace['sdk_paths']+mapped['unresolved_origins']+[x['source'] for x in trace['indirect_declarations']]
 consumed=sdk_witness.reconcile_consumed(e.json(out/'sdk-before.json'),[os.fsdecode(p) for p in paths],requested_root=sdk,expected_canonical_root=CANONICAL_SDK);equal(consumed,e.json(target/'consumed.json'),'consumed SDK origins')
 return {'objects':len(objs),'loaded_archive_members':len(trace['archive_members']),'map_archive_members':len(mapped['used_archive_members']),'physical_member_identities':[{k:(x.hex() if type(x) is bytes else x) for k,x in row.items()} for row in mapped['physical_member_identities']],'sdk_records':len(consumed)}
def artifacts(out,r):
 paths={out/n for n in ('recipe.json','inputs.tsv','expected.tsv','sdk-before.json','sdk-after.json','before.json','after.json','inventory-original.json','inventory-current.json','implicit-fixture.json','preexecute.json')}
 paths.update(out/(v+ext) for v in [*VARIANTS,'fixture'] for ext in ('.d','.o'));paths.update(out/(v+'.cpp') for v in MUTATIONS)
 for n,_,_ in plans(out,r):paths.update(out/(n+'.'+s) for s in ('stdout','stderr','command.json'))
 for v in VARIANTS:paths.update(out/'links'/v/n for n in ('native','native.map','expanded-before.json','archive-tables.json','consumed.json'))
 return paths
def preexecute(out,r):
 paths=artifacts(out,r)-{out/n for n in ('sdk-after.json','after.json','preexecute.json')}
 for v in VARIANTS:
  for suffix in ('','-repeat'):paths.difference_update(out/('run-'+v+suffix+'.'+s) for s in ('stdout','stderr','command.json'))
 return paths
def semantic(data):
 rows=[]
 for row in data.splitlines():
  fields=row.split(b'\t');need(len(fields)==8,'typed observer row fields');rows.append(b'\t'.join(fields[:6])+b'\n')
 return b''.join(rows)
def verify(out,q=None,e=None):
 safe(out);e=e or Evidence();q=q or e.json(out/'report.json');r=recipe()
 equal(q['status'],'FINITE_NATIVE_JSON_BUILDER_STREAM_PASS','status');need(type(q['definition_count']) is int and q['definition_count']==20,'20 explicit bodies')
 need(e.sha(HEADER)==e.sha(HERE/'original/StarJsonBuilder.hpp')==HEADER_SHA,'header identity');need(e.sha(SOURCE)==e.sha(ORIGINAL)==SOURCE_SHA,'source identity')
 equal(e.json(out/'recipe.json'),r,'independent recipe');model.literal_checks();equal(e.data(out/'inputs.tsv'),model.inputs(),'frozen corpus');equal(e.data(out/'expected.tsv'),model.expected(),'independent expected')
 for v,(a,b) in MUTATIONS.items():equal(e.data(out/(v+'.cpp')),e.data(ORIGINAL).replace(a.encode(),b.encode()),'single mutant edit')
 sdk=r['flags'][r['flags'].index('-isysroot')+1];sdk_witness.verify(e.json(out/'sdk-before.json'),sdk,CANONICAL_SDK);equal(e.json(out/'sdk-before.json'),e.json(out/'sdk-after.json'),'SDK before/after')
 paths=inputs(out,r,e);snap=snapshots(out,paths)
 for dest,src in snap.items():equal(e.data(dest),e.data(src),'source snapshot')
 bindings=e.hashes(paths|set(snap));equal(bindings,e.json(out/'before.json'),'required before bindings');equal(bindings,e.json(out/'after.json'),'required after bindings');equal(bindings,q['bindings'],'report bindings')
 equal(e.hashes(artifacts(out,r)),q['artifacts'],'required artifact membership');equal(e.hashes(preexecute(out,r)),e.json(out/'preexecute.json'),'preexecution freeze')
 for n,a,b in plans(out,r):
  c=e.json(out/(n+'.command.json'));equal(c['name'],n,'name');equal(c['argv'],a,'argv');equal(c['cwd'],str(CM),'cwd');equal(c['env'],env(out),'env');need(type(c['exit']) is int and c['exit']==0 and c['exit_type']=='normal','typed normal exit');equal(c['stdin'],{'sha256':digest(b),'size':len(b)},'stdin');equal(c['tool_before'],tool(a[0]),'before tool');equal(c['tool_after'],tool(a[0]),'after tool')
  for s in ('stdout','stderr'):equal(c[s],e.sha(out/(n+'.'+s)),'stdio')
 for v in ('original','current'):equal(e.json(out/('inventory-'+v+'.json')),inventory.reconcile(source(out,v),e.data(out/('ast-'+v+'.stdout'))),'compiler/manual ranges')
 equal(e.json(out/'implicit-fixture.json'),inventory.specials(e.data(out/'ast-fixture.stdout')),'actually instantiated implicit lifecycle')
 expected=model.expected();links={}
 for v in VARIANTS:
  data=e.data(out/('run-'+v+'.stdout'));equal(data,e.data(out/('run-'+v+'-repeat.stdout')),'repeat '+v);equal(e.data(out/('run-'+v+'.stderr')),b'','runtime stderr')
  if v in ('original','current'):equal(semantic(data),expected,'independent native model '+v)
  else:need(semantic(data)!=expected,'normal semantic mutant escaped '+v)
  links[v]=reconcile_link(out,r,v,e,sdk)
 equal(e.data(out/'run-original.stdout'),e.data(out/'run-current.stdout'),'raw native insertion/order/lifecycle original-current equality');equal(q['links'],links,'link conclusions')
 return q

def run(out):
 safe(out,True);out.mkdir(parents=True);(out/'home').mkdir();(out/'tmp').mkdir();r=recipe();model.literal_checks()
 need(sha(SOURCE)==sha(ORIGINAL)==SOURCE_SHA and sha(HEADER)==sha(HERE/'original/StarJsonBuilder.hpp')==HEADER_SHA,'production/original bytes')
 for v,(a,b) in MUTATIONS.items():
  s=ORIGINAL.read_text();need(s.count(a)==1,'unique mutant anchor');put(out/(v+'.cpp'),s.replace(a,b).encode())
 put(out/'inputs.tsv',model.inputs());put(out/'expected.tsv',model.expected());dump(out/'recipe.json',r)
 sdk=r['flags'][r['flags'].index('-isysroot')+1];dump(out/'sdk-before.json',sdk_witness.capture(sdk,CANONICAL_SDK))
 plan=plans(out,r)
 for p in plan:
  if p[0]=='native-deps' or p[0].startswith('deps-'):invoke(out,*p)
 paths=inputs(out,r,Evidence());snap=snapshots(out,paths)
 for dest,src in snap.items():dest.parent.mkdir(parents=True,exist_ok=True);put(dest,src.read_bytes())
 before=hashes(paths|set(snap));dump(out/'before.json',before);print('FROZEN',len(before),'bindings',len(model.cases()),'cases',len(model.expected().splitlines()),'rows BEFORE compile/native output',flush=True)
 for p in plan:
  if p[0].startswith('ast-'):invoke(out,*p)
 for v in ('original','current'):dump(out/('inventory-'+v+'.json'),inventory.reconcile(source(out,v),(out/('ast-'+v+'.stdout')).read_bytes()))
 dump(out/'implicit-fixture.json',inventory.specials((out/'ast-fixture.stdout').read_bytes()))
 with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda p:invoke(out,*p),[p for p in plan if p[0].startswith('compile-')]))
 print('compiled 5 builder variants + 1 fixture; 113 original objects PREBOUND, one replaced per link',flush=True)
 links={}
 for v in VARIANTS:
  target=out/'links'/v;target.mkdir(parents=True);a=link_argv(out,r,v);invoke(out,'expand-'+v,[a[0],'-###',*a[1:]])
  bound=expanded_invocation.bind(expansion(out,v,Evidence()));dump(target/'expanded-before.json',bound);blobs,tables=archive_tables(bound);dump(target/'archive-tables.json',{p.hex():t.hex() for p,t in tables.items()});invoke(out,'link-'+v,a)
  objs=[p.encode() for p in bound['inventory']['file_inputs'] if p.endswith('.o')];trace=link_trace.parse((out/('link-'+v+'.stdout')).read_bytes(),objs,tables);mapped=object_inventory.reconcile((target/'native.map').read_bytes(),objs,tables,blobs)
  sp=trace['sdk_paths']+mapped['unresolved_origins']+[x['source'] for x in trace['indirect_declarations']]
  dump(target/'consumed.json',sdk_witness.reconcile_consumed(json.loads((out/'sdk-before.json').read_bytes()),[os.fsdecode(p) for p in sp],requested_root=sdk,expected_canonical_root=CANONICAL_SDK));links[v]=reconcile_link(out,r,v,Evidence(),sdk);print('linked/reconciled',v,flush=True)
 equal(hashes(paths|set(snap)),before,'preexecution source drift');dump(out/'preexecute.json',hashes(preexecute(out,r)))
 for p in plan:
  if p[0].startswith('run-'):invoke(out,*p)
 dump(out/'sdk-after.json',sdk_witness.capture(sdk,CANONICAL_SDK));dump(out/'after.json',hashes(paths|set(snap)))
 q={'status':'FINITE_NATIVE_JSON_BUILDER_STREAM_PASS','definition_count':20,'case_count':len(model.cases()),'event_rows':len(model.expected().splitlines()),'bindings':before,'artifacts':hashes(artifacts(out,r)),'links':links,'limits':['native finite calibration ONLY; not Rust, ABI, whole parser/header/module or game','113 original native objects prebound readonly; one replaced per link, 112 reused plus fixture','semantic object members unordered; raw native iteration compared original/current, not independently modeled','actual copy/move destination sharing and virtual deletion exercised; allocation/destructor timing/OOM and arbitrary resources unproved','framework implementation and interpreter/dylib transitive closure, transient edit/revert and other platforms unproved']}
 dump(out/'candidate.json',{**q,'status':'RAW_NATIVE_ACQUISITION_PENDING_VERIFY'})
 verify(out,q)
 controls(out,q)
 # No exclusive acceptance report until normal semantic mutants AND clone controls.
 dump(out/'report.json',q);print(q['status'],flush=True)
def controls(out,q=None):
 safe(out);q=verify(out,q);dest=out/'controls';need(not dest.exists(),'exclusive controls');dest.mkdir();results=[]
 for name,mutate in [('missing-binding',lambda x:x['bindings'].pop(str(SOURCE))),('missing-artifact',lambda x:x['artifacts'].pop(str(out/'current.o'))),('false-count',lambda x:x.update(definition_count=True))]:
  bad=copy.deepcopy(q);mutate(bad);dump(dest/(name+'.json'),bad)
  try:verify(out,bad)
  except (ValueError,KeyError,FileNotFoundError) as ex:results.append({'name':name,'rejected':str(ex)})
  else:raise ValueError('control escaped '+name)
 for name,path,data in [('malformed-command',out/'compile-current.command.json',b'{'),('bool-exit',out/'run-current.command.json',json.dumps({**json.loads((out/'run-current.command.json').read_bytes()),'exit':False}).encode()),('source-drift',SOURCE,SOURCE.read_bytes()+b'\n'),('artifact-corrupt',out/'current.o',(out/'current.o').read_bytes()+b'bad'),('expected-corrupt',out/'expected.tsv',(out/'expected.tsv').read_bytes()+b'bad\n')]:
  clone=dest/(name+'.clone');put(clone,data);bad=copy.deepcopy(q)
  if str(path) in bad['artifacts']:bad['artifacts'][str(path)]=digest(data)
  if str(path) in bad['bindings']:bad['bindings'][str(path)]=digest(data)
  dump(dest/(name+'.json'),bad)
  try:verify(out,bad,Evidence({str(path):str(clone)}))
  except (ValueError,KeyError,FileNotFoundError) as ex:results.append({'name':name,'rejected':str(ex)})
  else:raise ValueError('clone control escaped '+name)
 dump(dest/'results.json',results);print(len(results),'corrupt fixtures rejected',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['run','verify','controls']);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output)
 if a.phase=='run':run(out)
 elif a.phase=='controls':controls(out)
 else:print(verify(out)['status'])
