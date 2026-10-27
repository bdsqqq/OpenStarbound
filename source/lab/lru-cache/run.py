#!/usr/bin/env python3
"""New independent native acquisition; --verify is strictly read-only."""
import copy,hashlib,json,os,re,shlex,stat,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
OUT=ROOT/'build/lru-cache-native-r1';CM=ROOT/'build/behavior/path-embed-combined-r1/reference/cmake'
SDK='/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk'
NINJA='/nix/store/ndfr0d2nizw172ppn99n505ikpsq9727-ninja-1.13.2/bin/ninja'
sys.path[:0]=[str(HERE),str(HERE.parent),str(HERE.parent/'path-embed-replay'),str(HERE.parent/'behavior')]
import model,inventory,sdk_witness,expanded_invocation,archive_identity,object_inventory,link_trace,native_symbols,build_provenance
VARIANTS=['original','current','lookup-before-evict','set-trims','omit-promotion']
ALIASES=['ordered','hash']
SOURCES=['native.cpp','model.py','inventory.py','run.py','CONTRACT.md','StarLruCache.original.hpp']

def need(x,m):
 if not x:raise ValueError(m)
def encoded(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def equal(a,b,m):need(encoded(a)==encoded(b),m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def hashes(ps):return {str(p):sha(p) for p in sorted(set(map(Path,ps)))}
def put(p,b):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(b)
def dump(p,x):put(p,(json.dumps(x,indent=2,ensure_ascii=True)+'\n').encode())
def js(p):return json.loads(Path(p).read_bytes())
def safe(p,fresh=False):
 need(p.is_absolute() and p==Path(os.path.normpath(p)),'absolute normalized path')
 need(not any(x.is_symlink() for x in [p,*p.parents]),'path symlink')
 if fresh:need(not p.exists(),'fresh output required')
 if p.exists():
  for parent,dirs,files in os.walk(p,followlinks=False):
   for n in dirs+files:
    q=Path(parent)/n;s=q.lstat();need(stat.S_ISDIR(s.st_mode) or (stat.S_ISREG(s.st_mode) and s.st_nlink==1),'regular nonaliased owned fixture')
def tool(p):
 c,h=sdk_witness._resolve(str(p));return {'requested':str(p),'canonical':c,'hops':h,**sdk_witness._digest(c)}
def env():return {'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(OUT/'home'),'TMPDIR':str(OUT/'tmp'),'LANG':'C','LC_ALL':'C'}
def invoke(name,args,stdin=b''):
 args=list(map(str,args));before=tool(args[0]);p=subprocess.run(args,cwd=CM,env=env(),input=stdin,capture_output=True,timeout=100)
 for ext,b in [('stdin',stdin),('stdout',p.stdout),('stderr',p.stderr)]:put(OUT/(name+'.'+ext),b)
 q={'argv':args,'cwd':str(CM),'environment':env(),'tool_before':before,'tool_after':tool(args[0]),'exit':p.returncode,'exit_type':'normal' if p.returncode>=0 else 'signal',**{k:hashlib.sha256(b).hexdigest() for k,b in [('stdin',stdin),('stdout',p.stdout),('stderr',p.stderr)]}}
 dump(OUT/(name+'.command.json'),q);equal(before,q['tool_after'],'tool drift');need(type(p.returncode)is int and p.returncode==0,'mechanical command failure '+name);return p

def recipe():
 db=js(CM/'compile_commands.json');lines=(CM/'build.ninja').read_text().splitlines();i=next(i for i,l in enumerate(lines) if l.startswith('build ') and '/bin/starbound:' in l)
 objs=[str(CM/p) for p in shlex.split(lines[i].split(': ',1)[1])[1:] if p.endswith('.o') and p.startswith(('core/','extern/'))]
 need(len(objs)==113 and len(set(objs))==113,'113 unique objects')
 rows=[next(r for r in db if r['output']==p) for p in objs];r=next(r for r in rows if r['file']==str(ROOT/'source/core/StarJsonBuilder.cpp'));a=shlex.split(r['command']);flags=[];skip=False
 for x in a[1:]:
  if skip:skip=False;continue
  if x=='-o':skip=True
  elif x not in ('-c',r['file']):flags.append(x)
 libs=shlex.split(next(l.split(' = ',1)[1] for l in lines[i+1:i+18] if l.startswith('  LINK_LIBRARIES = ')))
 libs=[str(CM/p) if p.endswith('.a') and not Path(p).is_absolute() else p for p in libs]
 selectors=re.findall(r'^(STAR_USE_RUST[^:]*):BOOL=(.*)$',(CM/'CMakeCache.txt').read_text(),re.M)
 need(len(selectors)==25 and all(v=='OFF' for _,v in selectors),'25 all OFF');need(not any('libstar_engine_ffi' in x for x in libs),'no Rust archive')
 return {'compiler':a[0],'flags':flags,'objects':objs,'libraries':libs,'rows':rows,'selectors':selectors}

def make_sources():
 original=(ROOT/'source/core/StarLruCache.hpp').read_bytes();need(hashlib.sha256(original).hexdigest()==inventory.HEADER_SHA,'source header SHA')
 equal((HERE/'StarLruCache.original.hpp').read_bytes().hex(),original.hex(),'full original header bytes')
 changes={
 'lookup-before-evict':('  while (m_map.size() > m_maxSize - 1)','  auto early = m_map.find(key);\n  if (early != m_map.end()) { m_map.toBack(early); return early->second; }\n  while (m_map.size() > m_maxSize - 1)'),
 'set-trims':('    m_map.toBack(i);\n  }\n}','    m_map.toBack(i);\n  }\n  while (m_map.size() > m_maxSize) m_map.removeFirst();\n}'),
 'omit-promotion':('i = m_map.toBack(i);','/* omitted native promotion */;')}
 manifest={}
 for index,v in enumerate(VARIANTS):
  d=OUT/v;d.mkdir();put(d/'probe.cpp',(HERE/'native.cpp').read_bytes())
  if v=='original':header=HERE/'StarLruCache.original.hpp';ns='Star'
  elif v=='current':header=ROOT/'source/core/StarLruCache.hpp';ns='Star'
  else:
   old,new=changes[v];text=original.decode();count=text.count(old);need(count==(2 if v=='omit-promotion' else 1),'exact mutant edit count')
   ns='LruMutant'+str(index);text=text.replace(old,new).replace('namespace Star {','namespace '+ns+' {\nusing namespace Star;',1);header=d/'mutant.hpp';put(header,text.encode());manifest[v]={'from':old,'to':new,'count':count,'class_namespace':ns}
  put(d/'selected.hpp',('#include "'+str(header)+'"\n#define SELECTED '+ns+'\n').encode())
 dump(OUT/'mutations.json',manifest)

def plans(r):
 c=r['compiler'];flags=r['flags'];p={'native-deps':[NINJA,'-t','deps',*[str(Path(x).relative_to(CM)) for x in r['objects']]]}
 for v in VARIANTS:
  d=OUT/v;src=d/'probe.cpp';obj=d/'fixture.o'
  p[v+'-deps']=[c,*flags,'-M','-MT','fixture.o','-MF',str(d/'fixture.d'),str(src)]
  p[v+'-compile']=[c,*flags,'-c',str(src),'-o',str(obj)]
  p[v+'-expand']=[c,'-###',*flags,*r['objects'],str(obj),*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(d/'native.map'),'-Wl,-t,-trace_implicit_libraries','-o',str(d/'native')]
  p[v+'-link']=[c,*p[v+'-expand'][2:]]
  p[v+'-disassembly']=['/usr/bin/otool','-tvV',str(d/'native')]
  for a in ALIASES:
   for n in (1,2):p[v+'-'+a+'-'+str(n)]=[str(d/'native'),a]
 p['ast']=[c,*flags,'-Xclang','-ast-dump=json','-Xclang','-ast-dump-filter=LruCacheBase','-fsyntax-only',str(OUT/'current/probe.cpp')]
 return p

def dep_paths(r):
 paths=set();found=[]
 for block in (OUT/'native-deps.stdout').read_text().strip().split('\n\n'):
  lines=block.splitlines();m=re.fullmatch(r'(.+): #deps ([0-9]+), deps mtime ([0-9]+) \(VALID\)',lines[0]);need(m is not None,'valid retained deps')
  found.append(str(CM/m[1]));items=lines[1:];need(len(items)==int(m[2]),'deps count')
  paths.update(Path(x.strip()) if Path(x.strip()).is_absolute() else CM/x.strip() for x in items)
 equal(found,r['objects'],'ordered retained dependency membership')
 for v in VARIANTS:
  _,s=(OUT/v/'fixture.d').read_text().replace('\\\n',' ').split(':',1)
  paths.update(Path(x) if Path(x).is_absolute() else CM/x for x in shlex.split(s))
 return paths

def expansion(v):
 commands=[shlex.split(l) for l in (OUT/(v+'-expand.stderr')).read_text().splitlines() if l.lstrip().startswith('"')]
 need(len(commands)==1,'one expanded ld');return commands[0]

def reconcile(v,r,sdk_before,sdk):
 d=OUT/v;ex=expansion(v);bound=js(d/'expanded-before.json');expanded_invocation.verify(bound,ex);inv=bound['inventory'];objs=[x.encode() for x in [*r['objects'],str(d/'fixture.o')]]
 equal([x.encode() for x in inv['file_inputs'] if x.endswith('.o')],objs,'expanded actual object membership')
 equal(inv['architecture'],'arm64','architecture');equal(inv['sdk'],sdk,'SDK');equal(inv['outputs'],[str(d/'native'),str(d/'native.map')],'actual output membership')
 blobs={p.encode():Path(p).read_bytes() for p in inv['file_inputs'] if p.endswith('.a')};tables={p:b''.join(m['name']+b'\n' for m in archive_identity.arm64_archive_members(blob)) for p,blob in blobs.items()}
 equal(js(d/'archive-tables.json'),{p.hex():t.hex() for p,t in tables.items()},'physical archive tables')
 trace=link_trace.parse((OUT/(v+'-link.stdout')).read_bytes(),objs,tables);mapped=object_inventory.reconcile((d/'native.map').read_bytes(),objs,tables,blobs)
 paths=trace['sdk_paths']+mapped['unresolved_origins']+[x['source'] for x in trace['indirect_declarations']]
 consumed=sdk_witness.reconcile_consumed(sdk_before,[os.fsdecode(x) for x in paths],requested_root=sdk,expected_canonical_root=SDK)
 symbols=native_symbols.live_symbols((d/'native.map').read_bytes());providers=[]
 for name in (b'_main',b'_lru_native_dispatch_ordered',b'_lru_native_dispatch_hash'):
  row=native_symbols.unique_symbol(symbols,name);equal(row.object_path.hex(),str(d/'fixture.o').encode().hex(),'exact fresh-TU route provider');need(row.size>0,'surviving code size');providers.append(row.manifest())
 # Byte-only symbols: unique key/value identity excludes retained Core instantiations.
 cache_symbols=[s for s in symbols if b'LruNativeR1' in s.name and b'LruCacheBase' in s.name]
 need(cache_symbols and all(s.object_path==str(d/'fixture.o').encode() for s in cache_symbols),'all surviving unique cache code from fresh TU')
 dis=(OUT/(v+'-disassembly.stdout')).read_bytes();main=dis.split(b'_main:\n',1)
 need(len(main)==2,'surviving main disassembly');body=main[1].split(b'\n_',1)[0]
 for target in (b'_lru_native_dispatch_ordered',b'_lru_native_dispatch_hash'):
  need(any((b'\tbl\t' in line or b'\tb\t' in line) and target in line for line in body.splitlines()),'surviving main dispatch edge '+repr(target))
 return {'providers':providers,'cache_symbols':[x.manifest() for x in cache_symbols],'loaded_archive_members':len(trace['archive_members']),'surviving_archive_members':len(mapped['used_archive_members']),'sdk_records':len(consumed),'consumed':consumed}

def compare(data):
 lines=data.splitlines();regular=b'\n'.join(x for x in lines if not x.startswith(b'@'))+b'\n';need(regular==model.expected(),'semantic state/value/order/error/event model mismatch')
 props={};
 for line in lines:
  if line.startswith(b'@'):
   key,value=line[1:].decode().split('\t');need(key not in props,'duplicate property');props[key]=value
 equal(set(props),set(model.PROPERTIES),'exact language property membership');need(all(v=='1' for v in props.values()),'language property mismatch '+repr(props))
 return len(regular.splitlines())

def artifacts(plan,admission=False):
 fixed=['recipe.json','mutations.json','corpus.tsv','expected.tsv','source-map.json','ast-inventory.json','sdk-before.json','sdk-after.json','bindings-before.json','bindings-after.json','commands-plan.json','freeze.json','preexecute.json','retained-proof.json']
 ps={OUT/n for n in fixed}
 if not admission:ps.add(OUT/'verifier-controls.json')
 ps|={OUT/(name+'.'+ext) for name in plan for ext in ('stdin','stdout','stderr','command.json')}
 for v in VARIANTS:
  ps|={OUT/v/n for n in ['probe.cpp','selected.hpp','fixture.d','fixture.o','native','native.map','expanded-before.json','archive-tables.json','origin.json']}
  if v not in ('original','current'):ps.add(OUT/v/'mutant.hpp')
 return ps

def verify(q=None,overrides=None,admission=False):
 safe(OUT);q=q or js(OUT/'report.json');overrides=overrides or {}
 def data(p):return Path(overrides.get(str(p),p)).read_bytes()
 def digest(p):return hashlib.sha256(data(p)).hexdigest()
 r=recipe();equal(r,js(OUT/'recipe.json'),'configured recipe unchanged');plan=plans(r);equal(plan,js(OUT/'commands-plan.json'),'independent exact command membership/argv')
 before=js(OUT/'bindings-before.json');equal(q['bindings'],before,'fixed input bindings membership');equal(q['bindings'],{p:digest(p) for p in before},'source/dependency/tool input drift')
 equal(set(q['artifacts']),set(map(str,artifacts(plan,admission))),'fixed artifact membership');equal(q['artifacts'],{p:digest(p) for p in q['artifacts']},'artifact bytes drift')
 if not admission:
  controls=json.loads(data(OUT/'verifier-controls.json'));equal([x['name'] for x in controls],['source','artifact','omitted-binding','typed-exit'],'required verifier controls');need(all(type(x['rejected'])is str and x['rejected'] for x in controls),'control rejections')
 equal(data(OUT/'corpus.tsv').hex(),('\n'.join('\t'.join(map(str,row)) for row in model.corpus())+'\n').encode().hex(),'independent corpus membership')
 equal(data(OUT/'expected.tsv').hex(),model.expected().hex(),'independent expected model');equal(inventory.reconcile(data(OUT/'ast.stdout'),data(HERE/'StarLruCache.original.hpp')),js(OUT/'ast-inventory.json'),'compiler AST inventory')
 for name,args in plan.items():
  row=json.loads(data(OUT/(name+'.command.json')));equal(row['argv'],args,'command argv');equal(row['cwd'],str(CM),'command cwd');equal(row['environment'],env(),'command env')
  need(type(row['exit'])is int and row['exit']==0 and row['exit_type']=='normal','typed normal exit')
  equal(row['tool_before'],tool(args[0]),'tool before live');equal(row['tool_after'],row['tool_before'],'tool after')
  for ext in ('stdin','stdout','stderr'):equal(row[ext],digest(OUT/(name+'.'+ext)),'command '+ext)
  expected_stdin=data(OUT/'corpus.tsv') if any(name==v+'-'+a+'-'+str(n) for v in VARIANTS for a in ALIASES for n in (1,2)) else b''
  equal(data(OUT/(name+'.stdin')).hex(),expected_stdin.hex(),'exact stdin binding')
 sdk= r['flags'][r['flags'].index('-isysroot')+1];sdk_before=js(OUT/'sdk-before.json');sdk_witness.verify(sdk_before,sdk,SDK);equal(sdk_before,js(OUT/'sdk-after.json'),'SDK after')
 proof=build_provenance.verify(ROOT/'build/behavior/path-embed-combined-r1/reference/bin/starbound');equal(proof,js(OUT/'retained-proof.json'),'retained source/configured proof')
 for v in VARIANTS:
  equal(reconcile(v,r,sdk_before,sdk),js(OUT/v/'origin.json'),'source/artifact origin')
  for a in ALIASES:
   first=data(OUT/(v+'-'+a+'-1.stdout'));equal(first.hex(),data(OUT/(v+'-'+a+'-2.stdout')).hex(),'repeat bytes')
   if v in ('original','current'):compare(first)
   else:
    try:compare(first)
    except ValueError:pass
    else:raise ValueError('normal compiled mutant escaped '+v)
 equal(js(OUT/'bindings-after.json'),before,'after input snapshot');return True

def run():
 safe(OUT,fresh=True);OUT.mkdir(parents=True);(OUT/'home').mkdir();(OUT/'tmp').mkdir();r=recipe();dump(OUT/'recipe.json',r)
 proof=build_provenance.verify(ROOT/'build/behavior/path-embed-combined-r1/reference/bin/starbound');dump(OUT/'retained-proof.json',proof)
 make_sources();need(model.literal_checks()==6 and inventory.selftest()==4,'preobservation units');corpus=('\n'.join('\t'.join(map(str,row)) for row in model.corpus())+'\n').encode();put(OUT/'corpus.tsv',corpus);put(OUT/'expected.tsv',model.expected());dump(OUT/'source-map.json',{'bodies':inventory.BODIES,'aliases':{'LruCache':[54,55],'HashLruCache':[57,58]},'implicit':['destructor','copy constructor','move constructor','copy assignment','move assignment'],'lambda':[121,123],'header_sha256':inventory.HEADER_SHA})
 plan=plans(r);dump(OUT/'commands-plan.json',plan);sdk=r['flags'][r['flags'].index('-isysroot')+1];sdk_before=sdk_witness.capture(sdk,SDK);dump(OUT/'sdk-before.json',sdk_before)
 invoke('native-deps',plan['native-deps'])
 for v in VARIANTS:invoke(v+'-deps',plan[v+'-deps'])
 paths=dep_paths(r)|set(map(Path,r['objects']))|{HERE/n for n in SOURCES}|{Path(sys.executable).resolve(),Path(NINJA),Path(r['compiler']),CM/'compile_commands.json',CM/'build.ninja',CM/'CMakeFiles/rules.ninja',CM/'CMakeCache.txt',CM/'.ninja_deps',OUT/'recipe.json',OUT/'corpus.tsv',OUT/'expected.tsv',OUT/'commands-plan.json',OUT/'sdk-before.json'}
 paths|={p for d in (HERE.parent/'path-embed-replay',) for p in d.glob('*.py')};paths|={HERE.parent/'native_artifacts.py',HERE.parent/'native_symbols.py',HERE.parent/'behavior/build_provenance.py'}
 paths|={Path(x) for x in r['libraries'] if Path(x).is_file()};paths|={ROOT/x for x in proof['source_files']};paths|={Path(x) for x in proof.get('compile_source_files',{})}
 before=hashes(paths);dump(OUT/'bindings-before.json',before);dump(OUT/'freeze.json',{'status':'PRECOMPILE_MODEL_SOURCE_DEPENDENCY_FREEZE','bindings':before,'model_cases':len(model.corpus()),'literal_checks':6,'constructor_units':4,'language_properties':model.PROPERTIES});print('FROZEN',len(before),'bindings',len(model.corpus()),'cases',flush=True)
 invoke('ast',plan['ast']);dump(OUT/'ast-inventory.json',inventory.reconcile((OUT/'ast.stdout').read_bytes(),(HERE/'StarLruCache.original.hpp').read_bytes()))
 for v in VARIANTS:
  invoke(v+'-compile',plan[v+'-compile']);equal(hashes(paths),before,'postcompile inputs');invoke(v+'-expand',plan[v+'-expand']);bound=expanded_invocation.bind(expansion(v));dump(OUT/v/'expanded-before.json',bound)
  blobs={p.encode():Path(p).read_bytes() for p in bound['inventory']['file_inputs'] if p.endswith('.a')};tables={p:b''.join(x['name']+b'\n' for x in archive_identity.arm64_archive_members(b)) for p,b in blobs.items()};dump(OUT/v/'archive-tables.json',{p.hex():t.hex() for p,t in tables.items()})
  invoke(v+'-link',plan[v+'-link']);invoke(v+'-disassembly',plan[v+'-disassembly']);dump(OUT/v/'origin.json',reconcile(v,r,sdk_before,sdk));print('linked/origin',v,flush=True)
 equal(hashes(paths),before,'preexecute source drift');dump(OUT/'preexecute.json',hashes(p for p in OUT.rglob('*') if p.is_file()))
 for v in VARIANTS:
  for a in ALIASES:
   for n in (1,2):
    name=v+'-'+a+'-'+str(n);out=invoke(name,plan[name],corpus).stdout
    if v in ('original','current'):compare(out)
    else:
     try:compare(out)
     except ValueError:pass
     else:raise ValueError('normal compiled mutant escaped '+v)
   equal((OUT/(v+'-'+a+'-1.stdout')).read_bytes().hex(),(OUT/(v+'-'+a+'-2.stdout')).read_bytes().hex(),'native repeat');print('native',v,a,flush=True)
 dump(OUT/'sdk-after.json',sdk_witness.capture(sdk,SDK));equal(sdk_before,js(OUT/'sdk-after.json'),'SDK after drift');equal(hashes(paths),before,'final input drift');dump(OUT/'bindings-after.json',hashes(paths))
 q={'status':'FINITE_LRU_NATIVE_CALIBRATION_PASS','bindings':before,'artifacts':hashes(artifacts(plan,admission=True)),'cases_per_run':len(model.corpus()),'native_runs':20,'aliases':ALIASES,'written_bodies':12,'nested_lambdas':1,'language_properties':model.PROPERTIES,'limits':'no Rust/ABI/production/application or universal equivalence claim'}
 verify(q,admission=True);controls=[]
 def rejected(name,bad,override=None):
  try:verify(bad,override,admission=True)
  except (ValueError,KeyError) as e:controls.append({'name':name,'rejected':str(e)})
  else:raise ValueError('verifier corruption escaped '+name)
 src=HERE/'native.cpp';clone=OUT/'controls/corrupt-source.cpp';put(clone,src.read_bytes()+b'corrupt');rejected('source',q,{str(src):str(clone)})
 artifact=OUT/'current/fixture.o';clone=OUT/'controls/corrupt-artifact.o';put(clone,artifact.read_bytes()+b'corrupt');rejected('artifact',q,{str(artifact):str(clone)})
 bad=copy.deepcopy(q);bad['bindings'].pop(str(src));rejected('omitted-binding',bad)
 receipt=OUT/'current-ordered-1.command.json';row=js(receipt);row['exit']=False;clone=OUT/'controls/typed-exit.json';dump(clone,row);bad=copy.deepcopy(q);bad['artifacts'][str(receipt)]=sha(clone);rejected('typed-exit',bad,{str(receipt):str(clone)})
 dump(OUT/'verifier-controls.json',controls);q['artifacts']=hashes(artifacts(plan));verify(q);dump(OUT/'report.json',q);print(q['status'],flush=True)

if __name__=='__main__':
 if sys.argv[1:]==['--verify']:verify();print('READONLY_REPLAY_PASS')
 elif sys.argv[1:]:raise SystemExit('usage: run.py [--verify]')
 else:
  try:run()
  except Exception as e:
   if OUT.exists() and not (OUT/'STOP.json').exists():dump(OUT/'STOP.json',{'status':'UNPROVED_STOP','cause':str(e),'type':type(e).__name__})
   raise
