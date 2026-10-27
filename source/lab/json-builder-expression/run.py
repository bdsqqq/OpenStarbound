#!/usr/bin/env python3
"""Exclusive native expression acquisition; stop on first unproved boundary."""
import hashlib,json,os,re,shlex,stat,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
OUT=ROOT/'build/json-builder-expression-r1/attempt-2';CM=ROOT/'build/behavior/path-embed-combined-r1/reference/cmake'
OLD=ROOT/'build/json-builder-stream-native-r1/attempt-2'
sys.path.insert(0,str(HERE.parent/'path-embed-replay'))
import sdk_witness,expanded_invocation,archive_identity,object_inventory,link_trace
SDK='/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk'
NINJA='/nix/store/ndfr0d2nizw172ppn99n505ikpsq9727-ninja-1.13.2/bin/ninja'
MODES=['reference','correct','skip-append','substitute','append-after-error','early-release','suppress','pretend-release','mock-failure']
SUCCESS='string-open,lexical,lexical-ok,json-open,append,json-close,string-close'
FAILURE='string-open,lexical,pending,rethrow-live,string-unwind,pending'
MOCK='string-open,lexical,lexical-ok,json-open,pending,rethrow-live,json-unwind,pending,rethrow-live,string-unwind,pending'
def need(x,s):
 if not x:raise ValueError(s)
def enc(x):
 return json.dumps(x,sort_keys=True,separators=(',',':'),default=lambda b:{'bytes':b.hex()} if type(b) is bytes else (_ for _ in ()).throw(TypeError(type(b))))
def equal(a,b,s):need(enc(a)==enc(b),s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,b):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(b)
def dump(p,x):put(p,(json.dumps(x,indent=2,default=lambda b:{'bytes':b.hex()})+'\n').encode())
def hashes(ps):return {str(p):sha(p) for p in sorted(set(map(Path,ps)))}
def tool(p):
 c,h=sdk_witness._resolve(str(p));return {'requested':str(p),'canonical':c,'hops':h,**sdk_witness._digest(c)}
def env():return {'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(OUT/'home'),'TMPDIR':str(OUT/'tmp'),'LANG':'C','LC_ALL':'C'}
def invoke(name,args,stdin=b''):
 args=list(map(str,args));t=tool(args[0]);p=subprocess.run(args,cwd=CM,env=env(),input=stdin,capture_output=True,timeout=100)
 for k,b in [('stdin',stdin),('stdout',p.stdout),('stderr',p.stderr)]:put(OUT/(name+'.'+k),b)
 q={'name':name,'argv':args,'cwd':str(CM),'env':env(),'tool_before':t,'tool_after':tool(args[0]),'exit':p.returncode,'exit_type':'normal' if p.returncode>=0 else 'signal','stdin':hashlib.sha256(stdin).hexdigest(),'stdout':hashlib.sha256(p.stdout).hexdigest(),'stderr':hashlib.sha256(p.stderr).hexdigest()}
 dump(OUT/(name+'.command.json'),q);equal(t,q['tool_after'],'tool drift');need(type(p.returncode) is int and p.returncode==0,'command failed '+name);return p

def recipe():
 db=json.loads((CM/'compile_commands.json').read_bytes());lines=(CM/'build.ninja').read_text().splitlines();i=next(i for i,l in enumerate(lines) if l.startswith('build ') and '/bin/starbound:' in l)
 objs=[str(CM/p) for p in shlex.split(lines[i].split(': ',1)[1])[1:] if p.endswith('.o') and p.startswith(('core/','extern/'))]
 need(len(objs)==113 and len(set(objs))==113,'113 distinct prebound objects')
 rows=[next(r for r in db if r['output']==p) for p in objs];r=next(r for r in rows if r['file']==str(ROOT/'source/core/StarJsonBuilder.cpp'));a=shlex.split(r['command']);flags=[];skip=False
 for x in a[1:]:
  if skip:skip=False;continue
  if x=='-o':skip=True
  elif x not in ('-c',r['file']):flags.append(x)
 libs=shlex.split(next(l.split(' = ',1)[1] for l in lines[i+1:i+18] if l.startswith('  LINK_LIBRARIES = ')))
 libs=[str(CM/p) if p.endswith('.a') and not Path(p).is_absolute() else p for p in libs]
 sel=re.findall(r'^(STAR_USE_RUST[^:]*):BOOL=(.*)$',(CM/'CMakeCache.txt').read_text(),re.M)
 need(len(sel)==25 and all(v=='OFF' for _,v in sel),'25 all OFF selectors');need(not any('libstar_engine_ffi' in p for p in libs),'no Rust archive')
 return {'compiler':a[0],'flags':flags,'objects':objs,'libraries':libs,'rows':rows,'selectors':sel}

def corpus():
 data=(OLD/'inputs.tsv').read_text();rows=[]
 for line in data.splitlines():
  name,index,op,payload=line.split('\t')
  if op in ('I','D'):rows.append((name+'-'+index,op,payload))
 extras=[[],[0],[49,0,50],[0xd800],[0xffffffff],[0x110000],[0x1f600],[0x7f,0x80,0x7ff,0x800,0xd7ff,0xd800,0xdfff,0xe000,0xffff,0x10000,0x10ffff,0x110000,0xffffffff]]
 for op in ('I','D'):
  for i,u in enumerate(extras):rows.append(('supplement-'+op+'-'+str(i),op,','.join(format(x,'x') for x in u) or '-'))
 need(len(set(x[0] for x in rows))==len(rows),'unique input IDs')
 return ''.join('\t'.join(x)+'\n' for x in rows).encode()

def parse(data):
 rows=[]
 for line in data.decode().splitlines():
  p=line.split('\t');need(len(p)==5,'five typed fields');need(p[1] in ('0','1'),'stage');rows.append(p)
 return rows

def compare(ref,data,protocol=True):
 a=parse(ref);b=parse(data);need(len(a)==len(b),'same event membership')
 for x,y in zip(a,b):
  equal(x[:4],y[:4],'reference value/error/partial-stack/continuation mismatch '+y[0]+':'+y[1])
  if protocol:need(y[4] in ([SUCCESS] if y[2]=='ok' else [FAILURE,'pending']),'scope protocol mismatch '+y[0]+':'+y[1])
 return len(a)

def required_commands():return ['native-deps','fixture-deps','expand','compile','link','disassembly','fixture-relocations','native-relocations']+['run-'+m for m in MODES]
def evidence_members():
 fixed=['recipe.json','corpus.tsv','sdk-before.json','sdk-after.json','bindings-before.json','bindings-after.json','expanded-before.json','expanded-complete.json','code-origin.json','archive-tables.json','consumed.json','origin.json','preexecute.json','fixture.d','fixture.o','native','native.map','commands-plan.json','freeze.json','compile-bindings-before.json']
 return {OUT/n for n in fixed}|{OUT/(n+'.'+s) for n in required_commands() for s in ('stdin','stdout','stderr','command.json')}
def verify(q,override=None):
 override=override or {}
 def digest(p):return sha(override.get(str(p),p))
 equal(q['bindings'],json.loads((OUT/'bindings-before.json').read_bytes()),'fixed source binding membership')
 equal(q['bindings'],{p:digest(p) for p in q['bindings']},'source binding drift')
 equal(set(q['artifacts']),set(map(str,evidence_members())),'required artifact membership')
 equal(q['artifacts'],{p:digest(p) for p in q['artifacts']},'artifact bytes drift')
 plan=json.loads((OUT/'commands-plan.json').read_bytes())
 for name in required_commands():
  receipt=json.loads((OUT/(name+'.command.json')).read_bytes());equal(receipt['argv'],plan[name],'exact argv')
  need(type(receipt['exit']) is int and receipt['exit']==0 and receipt['exit_type']=='normal','typed normal command exit')
  equal(receipt['cwd'],str(CM),'cwd');equal(receipt['env'],env(),'environment')
  equal(receipt['tool_before'],tool(receipt['argv'][0]),'tool before');equal(receipt['tool_after'],receipt['tool_before'],'tool after')
  for s in ('stdin','stdout','stderr'):equal(receipt[s],sha(OUT/(name+'.'+s)),'exact command '+s)
 compare((OUT/'run-reference.stdout').read_bytes(),(OUT/'run-correct.stdout').read_bytes())
 return True

def call_edges(disassembly,fragment):
 lines=disassembly.splitlines();starts=[i for i,l in enumerate(lines) if l.endswith(':') and fragment in l]
 need(len(starts)==1,'one surviving code owner '+fragment)
 start=starts[0];end=next((i for i in range(start+1,len(lines)) if lines[i].endswith(':')),len(lines))
 body='\n'.join(lines[start:end]);calls=re.findall(r'\bbl\s+([^\n]+)',body)
 return {'label':lines[start],'body_sha256':hashlib.sha256(body.encode()).hexdigest(),'calls':calls,'body':body}

def run():
 need(not OUT.exists(),'new exclusive output');OUT.mkdir(parents=True);(OUT/'home').mkdir();(OUT/'tmp').mkdir()
 r=recipe();dump(OUT/'recipe.json',r);put(OUT/'corpus.tsv',corpus());sdk=r['flags'][r['flags'].index('-isysroot')+1];dump(OUT/'sdk-before.json',sdk_witness.capture(sdk,SDK))
 c=r['compiler'];flags=r['flags'];fixture=HERE/'fixture.cpp'
 compile_cmd=[c,*flags,'-c',str(fixture),'-o',str(OUT/'fixture.o')]
 link_cmd=[c,*flags,*r['objects'],str(OUT/'fixture.o'),*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(OUT/'native.map'),'-Wl,-t,-trace_implicit_libraries','-o',str(OUT/'native')]
 plans={'native-deps':[NINJA,'-t','deps',*[str(Path(p).relative_to(CM)) for p in r['objects']]],'fixture-deps':[c,*flags,'-M','-MT','fixture.o','-MF',str(OUT/'fixture.d'),str(fixture)],'expand':[c,'-###',*link_cmd[1:]],'compile':compile_cmd,'link':link_cmd,'disassembly':['/usr/bin/otool','-tvV',str(OUT/'native')],'fixture-relocations':['/usr/bin/otool','-tvV',str(OUT/'fixture.o')],'native-relocations':['/usr/bin/otool','-tvV',next(p for p in r['objects'] if p.endswith('/StarJsonBuilder.cpp.o'))]}
 for m in MODES:plans['run-'+m]=[str(OUT/'native'),m]
 dump(OUT/'commands-plan.json',plans)
 for n in ['native-deps','fixture-deps']:invoke(n,plans[n])
 prepaths=set(HERE.iterdir())|set(map(Path,r['objects']))|{Path(c),Path(sys.executable).resolve(),Path(NINJA),CM/'compile_commands.json',CM/'build.ninja',CM/'CMakeFiles/rules.ninja',CM/'CMakeCache.txt',OUT/'sdk-before.json',OUT/'recipe.json',OUT/'commands-plan.json',OUT/'corpus.tsv'}|{Path(x) for x in r['libraries'] if Path(x).is_file()}
 for block in (OUT/'native-deps.stdout').read_text().strip().split('\n\n'):
  lines=block.splitlines();need(lines[0].endswith('(VALID)'),'precompile valid dependency block')
  prepaths.update(Path(x.strip()) if Path(x.strip()).is_absolute() else CM/x.strip() for x in lines[1:])
 _,d=(OUT/'fixture.d').read_text().replace('\\\n',' ').split(':',1);prepaths.update(Path(x) if Path(x).is_absolute() else CM/x for x in shlex.split(d))
 historical=json.loads((OLD/'before.json').read_bytes())
 for p in prepaths:
  if str(p) in historical:need(sha(p)==historical[str(p)],'precompile retained input drift '+str(p))
 prehash=hashes(prepaths);dump(OUT/'compile-bindings-before.json',prehash)
 invoke('compile',plans['compile']);equal(hashes(prepaths),prehash,'compile source/dependency drift');invoke('expand',plans['expand'])
 expansion=[shlex.split(l) for l in (OUT/'expand.stderr').read_text().splitlines() if l.lstrip().startswith('"')];need(len(expansion)==1,'one expanded ld');inventory=expanded_invocation.parse(expansion[0]);filebind=[]
 for p in sorted(set(inventory['file_inputs'])):
  if p!=str(OUT/'fixture.o'):
   t=tool(p);filebind.append({'requested':t['requested'],'canonical':t['canonical'],'hops':t['hops'],'size':t['size'],'sha256':t['sha256']})
 bound={'inventory':inventory,'files':filebind};dump(OUT/'expanded-before.json',bound)
 blobs={p.encode():Path(p).read_bytes() for p in bound['inventory']['file_inputs'] if p.endswith('.a')};tables={p:b''.join(x['name']+b'\n' for x in archive_identity.arm64_archive_members(b)) for p,b in blobs.items()};dump(OUT/'archive-tables.json',{p.hex():t.hex() for p,t in tables.items()})
 deps=set();found=[]
 for block in (OUT/'native-deps.stdout').read_text().strip().split('\n\n'):
  lines=block.splitlines();m=re.fullmatch(r'(.+): #deps ([0-9]+), deps mtime ([0-9]+) \(VALID\)',lines[0]);need(m is not None,'valid native deps');found.append(str(CM/m[1]));paths=[Path(x.strip()) if Path(x.strip()).is_absolute() else CM/x.strip() for x in lines[1:]];need(len(paths)==int(m[2]),'dep count');deps.update(paths)
 equal(found,r['objects'],'ordered113 dependency recipes')
 _,d=(OUT/'fixture.d').read_text().replace('\\\n',' ').split(':',1);deps.update(Path(x) if Path(x).is_absolute() else CM/x for x in shlex.split(d))
 proof=Path(str(CM.parent/'bin/starbound')+'.behavior-build.json');game=json.loads(proof.read_bytes())
 for p,h in game['source_files'].items():need(sha(ROOT/p)==h,'source1495 drift '+p);deps.add(ROOT/p)
 for p,h in game['compile_source_files'].items():need(sha(p)==h,'configured source472 drift '+p);deps.add(Path(p))
 need(len(game['source_files'])==1495 and len(game['compile_source_files'])==472,'source closure cardinality')
 old=json.loads((OLD/'before.json').read_bytes())
 for p in deps|set(map(Path,r['objects'])):
  if str(p) in old:need(sha(p)==old[str(p)],'prebound input drift '+str(p))
 paths=deps|{proof,CM/'compile_commands.json',CM/'build.ninja',CM/'CMakeCache.txt',CM/'CMakeFiles/rules.ninja',CM/'.ninja_deps',CM/'.ninja_log',Path(sys.executable).resolve(),Path(NINJA),Path(c),Path('/usr/bin/otool'),OLD/'before.json',OLD/'inputs.tsv'}|set(HERE.iterdir())|set(map(Path,r['objects']))|{Path(m.__file__).resolve() for m in (sdk_witness,expanded_invocation,archive_identity,object_inventory,link_trace)}|{HERE.parent/'native_artifacts.py'}|{Path(x['canonical']) for x in bound['files']}
 paths={p for p in paths if p.is_file()};paths.add(OUT/'compile-bindings-before.json');paths.update(OUT/n for n in ['recipe.json','corpus.tsv','commands-plan.json','sdk-before.json','expanded-before.json','archive-tables.json'])
 before=hashes(paths);dump(OUT/'bindings-before.json',before);dump(OUT/'freeze.json',{'hypothesis':sha(HERE/'CONTRACT.md'),'sources':hashes(HERE.iterdir()),'bindings':before,'predictions':{'success':SUCCESS,'lexical_failure':FAILURE,'mock':MOCK,'negative_modes':MODES[2:-1]},'parent_dedupe':'live parent 2026-10-27T05:30:23Z all three completed/nochildren; sole compiler writer','head':'8ec8976f4c8c94bb64053d3cec65f84c58c2612d'})
 print('FROZEN',len(before),'bindings',len(corpus().splitlines()),'tokens',flush=True)
 complete=expanded_invocation.bind(expansion[0]);equal([x for x in complete['files'] if x['requested']!=str(OUT/'fixture.o')],bound['files'],'expanded prebound runtime drift');dump(OUT/'expanded-complete.json',complete);invoke('link',plans['link'])
 objs=[p.encode() for p in [*r['objects'],str(OUT/'fixture.o')]];trace=link_trace.parse((OUT/'link.stdout').read_bytes(),objs,tables);mapped=object_inventory.reconcile((OUT/'native.map').read_bytes(),objs,tables,blobs)
 sp=trace['sdk_paths']+mapped['unresolved_origins']+[x['source'] for x in trace['indirect_declarations']];dump(OUT/'consumed.json',sdk_witness.reconcile_consumed(json.loads((OUT/'sdk-before.json').read_bytes()),[os.fsdecode(p) for p in sp],requested_root=sdk,expected_canonical_root=SDK))
 for n in ['disassembly','fixture-relocations','native-relocations']:invoke(n,plans[n])
 # Origin is deliberately fail-closed. Physical symbol provider alone does not
 # establish candidate inlined wrappers; record disassembly for human review.
 text=(OUT/'native.map').read_text();objects={int(i):p for i,p in re.findall(r'^\[\s*(\d+)\]\s+(.+)$',text,re.M)};providers=[]
 for line in text.splitlines():
  if line.startswith('0x') and any(k in line for k in ('from_chars_advancedIdc','parse_infnanIdc','from_charsIxci','JsonBuilderStream9putDouble','JsonBuilderStream10putInteger')):
   m=re.search(r'\[\s*(\d+)\]\s+(\S+)$',line);need(m is not None,'symbol provider parse');providers.append({'line':line,'object':objects[int(m[1])]})
 dump(OUT/'origin.json',{'providers':providers,'status':'UNPROVED_PENDING_SURVIVING_CODE_TRACE','objects':len(objs),'physical_members':len(mapped['used_archive_members']),'trace_members':len(trace['archive_members'])})
 need(providers and all(p['object']!=str(OUT/'fixture.o') for p in providers),'candidate weak parser replaced retained native provider')
 equal(hashes(paths),before,'preexecution input drift');dump(OUT/'preexecute.json',hashes(p for p in OUT.iterdir() if p.is_file()))
 # Require actual surviving call edges, not merely a weak symbol provider map.
 dis=(OUT/'disassembly.stdout').read_text();edges={k:call_edges(dis,k) for k in ['JsonBuilderStream9putDouble','JsonBuilderStream10putInteger','dispatch']}
 double='from_chars_advancedIdc';integer='from_charsIxci'
 for owner,helper in [('JsonBuilderStream9putDouble',double),('JsonBuilderStream10putInteger',integer),('dispatch',double),('dispatch',integer)]:
  need(any(helper in call for call in edges[owner]['calls']),'UNPROVED_BOUNDARY: no surviving native parser call '+owner+' -> '+helper)
 dump(OUT/'code-origin.json',edges)
 # Reconcile maps with the same exact physical retained Core provider.
 need(any(double in p['line'] for p in providers) and any(integer in p['line'] for p in providers),'both actual parse helpers mapped')
 outputs={}
 for m in MODES:
  outputs[m]=invoke('run-'+m,plans['run-'+m],corpus()).stdout
  if m=='correct':compare(outputs['reference'],outputs[m])
  elif m not in ('reference','mock-failure'):
   try:compare(outputs['reference'],outputs[m])
   except ValueError:pass
   else:raise ValueError('normal negative escaped actual comparator '+m)
  elif m=='mock-failure':
   for row in parse(outputs[m]):
    if row[1]=='0' and 'lexical-ok' in row[4]:need(row[3]=='n' and row[4]==MOCK,'mock failure partial-state/scope mismatch')
 dump(OUT/'sdk-after.json',sdk_witness.capture(sdk,SDK));equal(json.loads((OUT/'sdk-before.json').read_bytes()),json.loads((OUT/'sdk-after.json').read_bytes()),'SDK after drift')
 equal(hashes(paths),before,'after input drift');dump(OUT/'bindings-after.json',hashes(paths))
 q={'status':'finite NUMERICEXPRESSION_WITNESS','bindings':before,'artifacts':hashes(evidence_members()),'events':compare(outputs['reference'],outputs['correct'])}
 verify(q);controls=[]
 for label,mut in [('missing-artifact',lambda x:x['artifacts'].pop(str(OUT/'fixture.o'))),('missing-source',lambda x:x['bindings'].pop(str(fixture)))]:
  bad=json.loads(json.dumps(q));mut(bad)
  try:verify(bad)
  except ValueError as e:controls.append({'name':label,'rejected':str(e)})
  else:raise ValueError('verifier negative escaped '+label)
 clone=OUT/'controls/source-corrupt.cpp';put(clone,fixture.read_bytes()+b'corrupt')
 try:verify(q,{str(fixture):str(clone)})
 except ValueError as e:controls.append({'name':'source-drift','rejected':str(e)})
 else:raise ValueError('source drift control escaped')
 dump(OUT/'verifier-controls.json',controls);dump(OUT/'report.json',q);print(q['status'],flush=True)

if __name__=='__main__':
 try:run()
 except Exception as e:
  if OUT.exists():
   p=OUT/'STOP.json'
   if not p.exists():dump(p,{'status':'UNPROVED','cause':str(e),'type':type(e).__name__})
  raise
