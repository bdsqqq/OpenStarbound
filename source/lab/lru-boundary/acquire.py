#!/usr/bin/env python3
"""Fresh boundary acquisition; no closed runner imports. --verify is read-only."""
import hashlib,json,os,re,shlex,signal,stat,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
BEFORE='--before' in sys.argv[1:]
OUT=ROOT/'build/lru-boundary-unwind-r1'/('before' if BEFORE else 'after-r3');CM=ROOT/'build/behavior/path-embed-combined-r1/reference/cmake'
SDK='/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk'
NINJA='/nix/store/ndfr0d2nizw172ppn99n505ikpsq9727-ninja-1.13.2/bin/ninja'
sys.path[:0]=[str(HERE.parent),str(HERE.parent/'path-embed-replay'),str(HERE.parent/'lru-cache'),str(HERE.parent/'behavior')]
import native_evidence_json as codec
import model,inventory,sdk_witness,expanded_invocation,archive_identity,object_inventory,link_trace,native_symbols,build_provenance

def need(x,m):
 if not x:raise ValueError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,data):
 with Path(p).open('xb') as f:f.write(data)
def dump(p,obj):write(p,codec.dumps(obj).encode('ascii'))
def load(p):
 raw=Path(p).read_text();obj=json.loads(raw)
 return codec.loads(raw) if type(obj)is dict and obj.get('format')==codec.FORMAT else obj
def hashes(paths):return {str(p):sha(p) for p in sorted(set(map(Path,paths)))}
def witness(path):
 canonical,hops=sdk_witness._resolve(str(path));return {'requested':str(path),'canonical':canonical,'hops':hops,**sdk_witness._digest(canonical)}
def same(a,b,message):need(codec.dumps(a)==codec.dumps(b),message)
def environment():return {'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(OUT/'home'),'TMPDIR':str(OUT/'tmp'),'LANG':'C','LC_ALL':'C'}
def command(name,argv,stdin=b'',timeout=120):
 argv=list(map(str,argv));prefix=OUT/name
 before=witness(argv[0]);started=time.time_ns()
 write(str(prefix)+'.stdin',stdin)
 dump(str(prefix)+'.plan',{'argv':argv,'cwd':str(CM),'env':environment(),'stdin':hashlib.sha256(stdin).hexdigest(),'timeout_seconds':timeout,'tool':before})
 p=subprocess.Popen(argv,cwd=CM,env=environment(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
 # Persist identity BEFORE waiting or validating a single output product.
 dump(str(prefix)+'.started',{'pid':p.pid,'pgid':os.getpgid(p.pid),'started_ns':started})
 timed_out=False
 try:stdout,stderr=p.communicate(stdin,timeout=timeout)
 except subprocess.TimeoutExpired:
  timed_out=True;os.killpg(p.pid,signal.SIGKILL);stdout,stderr=p.communicate(timeout=10)
 write(str(prefix)+'.stdout',stdout);write(str(prefix)+'.stderr',stderr)
 receipt={'argv':argv,'cwd':str(CM),'env':environment(),'pid':p.pid,'pgid':p.pid,'status':p.returncode,'status_kind':'normal' if p.returncode>=0 else 'signal','timed_out':timed_out,'timeout_seconds':timeout,'started_ns':started,'ended_ns':time.time_ns(),'stdin':sha(str(prefix)+'.stdin'),'stdout':sha(str(prefix)+'.stdout'),'stderr':sha(str(prefix)+'.stderr'),'tool_before':before,'tool_after':witness(argv[0])}
 dump(str(prefix)+'.receipt',receipt)
 need(not timed_out and type(p.returncode)is int and p.returncode==0,'command failed '+name)
 same(before,receipt['tool_after'],'tool changed '+name)
 return stdout,stderr

def recipe():
 db=json.loads((CM/'compile_commands.json').read_text());lines=(CM/'build.ninja').read_text().splitlines()
 pos=next(i for i,line in enumerate(lines) if line.startswith('build ') and '/bin/starbound:' in line)
 objects=[str(CM/x) for x in shlex.split(lines[pos].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/'))]
 need(len(objects)==113 and len(set(objects))==113,'113 retained objects')
 rows=[next(r for r in db if r['output']==obj) for obj in objects]
 row=next(r for r in rows if r['file']==str(ROOT/'source/core/StarJsonBuilder.cpp'))
 args=shlex.split(row['command']);flags=[];skip=False
 for token in args[1:]:
  if skip:skip=False;continue
  if token=='-o':skip=True
  elif token not in ('-c',row['file']):flags.append(token)
 need('-O3'in flags and '-ffast-math'in flags,'real optimized profile')
 libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[pos+1:pos+18] if x.startswith('  LINK_LIBRARIES = ')))
 libs=[str(CM/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
 selectors=re.findall(r'^(STAR_USE_RUST[^:]*):BOOL=(.*)$',(CM/'CMakeCache.txt').read_text(),re.M)
 need(len(selectors)==25 and all(v=='OFF' for _,v in selectors),'unchanged all-OFF profile')
 return {'compiler':args[0],'flags':flags,'objects':objects,'libraries':libs,'rows':rows,'selectors':selectors}

def source_delta(historical,live,dependencies):
 # the retained all-OFF C++ objects cannot consume the parent's new Rust module.
 # bind that live membership honestly; do not retag the whole old game receipt.
 allowed={'source/rust/ffi/src/lib.rs','source/rust/ffi/src/lru_cache.rs'}
 changed={p for p in set(historical)|set(live) if historical.get(p)!=live.get(p)}
 need(changed in (set(),allowed),'unexpected retained source delta')
 need(all(str((ROOT/p).resolve()) not in dependencies for p in allowed),'changed Rust consumed by retained compile')
 return {p:{'historical':historical.get(p),'live':live.get(p)} for p in sorted(changed)}

def source_policy_controls():
 lib='source/rust/ffi/src/lib.rs';module='source/rust/ffi/src/lru_cache.rs'
 old={'source/core/example.hpp':'same',lib:'old'}
 live={**old,lib:'new',module:'new-module'}
 need(len(source_delta(old,live,set()))==2,'allowed nonparticipating Rust delta')
 rejected=[]
 for name,candidate,deps in [('changed-core',{**live,'source/core/example.hpp':'wrong'},set()),('removed-core',{lib:'new',module:'new-module'},set()),('third-Rust',{**live,'source/rust/ffi/src/other.rs':'extra'},set()),('consumed-Rust',live,{str((ROOT/lib).resolve())})]:
  try:source_delta(old,candidate,deps)
  except ValueError:rejected.append(name)
  else:raise ValueError('source policy control escaped '+name)
 return rejected

def compare(data):
 lines=data.splitlines();actual=b'\n'.join(x for x in lines if not x.startswith(b'@'))+b'\n'
 need(actual==model.expected(),'640-row independent model mismatch')
 props={}
 for line in lines:
  if line.startswith(b'@'):
   key,value=line[1:].decode('ascii').split('\t');need(key not in props,'duplicate property');props[key]=value
 need(set(props)==set(model.PROPERTIES) and all(x=='1' for x in props.values()),'12-property mismatch')
 return len(actual.splitlines())

def origins(name,r,sdk_before):
 objects=[*r['objects'],str(OUT/'controller.o'),str(OUT/(name+'.o'))]
 commands=[shlex.split(x) for x in (OUT/(name+'-expand.stderr')).read_text().splitlines() if x.lstrip().startswith('"')]
 need(len(commands)==1,'single expanded linker')
 bound=load(OUT/(name+'-expanded.typed'));expanded_invocation.verify(bound,commands[0])
 inv=bound['inventory'];same([x for x in inv['file_inputs'] if x.endswith('.o')],objects,'actual object list')
 blobs={x.encode():Path(x).read_bytes() for x in inv['file_inputs'] if x.endswith('.a')}
 tables={p:b''.join(m['name']+b'\n' for m in archive_identity.arm64_archive_members(blob)) for p,blob in blobs.items()}
 trace=link_trace.parse((OUT/(name+'-link.stdout')).read_bytes(),[p.encode() for p in objects],tables)
 mapped=object_inventory.reconcile((OUT/(name+'.map')).read_bytes(),[p.encode() for p in objects],tables,blobs)
 sdk= r['flags'][r['flags'].index('-isysroot')+1]
 paths=trace['sdk_paths']+mapped['unresolved_origins']+[x['source'] for x in trace['indirect_declarations']]
 consumed=sdk_witness.reconcile_consumed(sdk_before,[os.fsdecode(x) for x in paths],requested_root=sdk,expected_canonical_root=SDK)
 symbols=native_symbols.live_symbols((OUT/(name+'.map')).read_bytes())
 names=[b'_main',b'_sb_lru_run']+([b'_lru_native_dispatch_ordered',b'_lru_native_dispatch_hash'] if name=='candidate' else [])
 providers=[]
 for symbol_name in names:
  symbol=native_symbols.unique_symbol(symbols,symbol_name)
  expected=OUT/('controller.o' if symbol_name==b'_sb_lru_run' else name+'.o')
  need(symbol.object_path==str(expected).encode() and symbol.size>0,'fresh symbol provider '+repr(symbol_name));providers.append(symbol.manifest())
 dis=(OUT/(name+'-disassemble.stdout')).read_bytes()
 need(any(b'_sb_lru_run' in line and (b'\tbl\t'in line or b'\tb\t'in line) for line in dis.splitlines()),'surviving boundary call edge')
 if name=='candidate':
  main=dis.split(b'_main:\n',1);need(len(main)==2,'main disassembly')
  body=main[1].split(b'\n_',1)[0]
  for target in names[2:]:need(any(target in line and (b'\tbl\t'in line or b'\tb\t'in line) for line in body.splitlines()),'dispatch edge')
  methods=[s for s in symbols if re.match(rb'^__ZNK?11LruBoundary12LruCacheBase',s.name) and b'LruNativeR1'in s.name]
  need(bool(methods),'fresh cache methods')
  for s in methods:
   if s.object_path==str(OUT/'candidate.o').encode():continue
   owners=[x for x in symbols if x.address==s.address and x.object_index!=0 and x.size>0]
   need(s.object_index==0 and s.size==0 and owners and all(x.object_path==str(OUT/'candidate.o').encode() for x in owners),'folded cache owner')
 return {'providers':providers,'consumed_sdk':consumed,'trace':trace,'map':mapped,'physical_archive_tables':tables}

def verify(report=None,override=None):
 report=report or load(OUT/'report.typed');override=override or {}
 def data(p):return Path(override.get(str(p),p)).read_bytes()
 for field in ('inputs','artifacts'):
  for p,h in report[field].items():need(hashlib.sha256(data(p)).hexdigest()==h,field+' drift '+p)
 same(recipe(),load(OUT/'recipe.typed'),'profile drift')
 closure=load(OUT/'source-closure.typed')
 same(build_provenance.source_snapshot(ROOT),closure['live'],'complete live source membership')
 same(hashes(HERE.glob('*')),load(OUT/'boundary-membership.typed'),'complete boundary source membership')
 same(source_delta(closure['historical'],closure['live'],set(closure['compile_dependencies'])),closure['delta'],'retained source delta policy')
 same(source_policy_controls(),load(OUT/'source-policy-controls.typed'),'source policy controls')
 for receipt_path in sorted(OUT.glob('*.receipt')):
  receipt=codec.loads(data(receipt_path).decode('ascii'));base=str(receipt_path)[:-8]
  plan=load(base+'.plan');started=load(base+'.started')
  need(type(receipt['status'])is int and receipt['status']==0 and receipt['status_kind']=='normal' and receipt['timed_out']is False,'strict command status')
  need(type(receipt['pid'])is int and receipt['pid']>0 and receipt['pid']==receipt['pgid']==started['pid']==started['pgid'],'process identity')
  for key in ('argv','cwd','env','timeout_seconds'):same(receipt[key],plan[key],'exact command plan '+key)
  same(receipt['tool_before'],receipt['tool_after'],'stable command tool');same(receipt['tool_before'],witness(receipt['argv'][0]),'live tool')
  for ext in ('stdin','stdout','stderr'):need(hashlib.sha256(data(base+'.'+ext)).hexdigest()==receipt[ext],'stdio bytes')
 for alias in ('ordered','hash'):
  first=data(OUT/('run-'+alias+'-1.stdout'));need(compare(first)==640,'row count')
  same(first,data(OUT/('run-'+alias+'-2.stdout')),'repeat identity')
 need(data(OUT/'controls-run.stdout')==b'controls\t39\n','39 existing focused controls')
 sdk_before=load(OUT/'sdk-before.typed');same(sdk_before,load(OUT/'sdk-after.typed'),'SDK unchanged')
 sdk=r['flags'][r['flags'].index('-isysroot')+1] if (r:=recipe()) else None
 sdk_witness.verify(sdk_before,sdk,SDK)
 for name in ('candidate','controls','unwind'):same(origins(name,r,sdk_before),load(OUT/(name+'-origin.typed')),'reconstructed origins')
 unwind_lines=data(OUT/'unwind-run.stdout').splitlines()
 need(unwind_lines[-1]==(b'EXPECTED_NATIVE_UNWIND_MISMATCH' if BEFORE else b'NATIVE_UNWIND_CONTROLS_PASS'),'unwind witness marker')
 comparisons=[line for line in unwind_lines if line.startswith(b'comparison\t')]
 expected=[b'comparison\t'+alias+b'\t'+test+b'\t'+(b'DIFFERENT' if BEFORE and test!=b'success' else b'equal') for alias in (b'ordered',b'hash') for test in (b'success',b'copy-fault',b'copy-fault-reentry')]
 same(comparisons,expected,'exact real-alias unwind comparisons')
 if not BEFORE:need(b'ITERATOR_UNWIND_CONTROLS_PASS' in unwind_lines,'find/filter iterator controls')
 return True

def acquire():
 need(not OUT.exists(),'fresh acquisition only');OUT.mkdir(parents=True);(OUT/'home').mkdir();(OUT/'tmp').mkdir()
 r=recipe();dump(OUT/'recipe.typed',r);dump(OUT/'source-policy-controls.typed',source_policy_controls())
 need(sha(ROOT/'source/core/StarLruCache.hpp')==inventory.HEADER_SHA,'frozen native header')
 need(model.literal_checks()==6 and len(model.corpus())==640,'frozen model units')
 write(OUT/'probe.cpp',(HERE.parent/'lru-cache/native.cpp').read_bytes())
 write(OUT/'selected.hpp',('#include "'+str(HERE/'cache.hpp')+'"\n#define SELECTED LruBoundary\n').encode())
 corpus=('\n'.join('\t'.join(map(str,row)) for row in model.corpus())+'\n').encode();write(OUT/'corpus.tsv',corpus);write(OUT/'expected.tsv',model.expected())
 c=r['compiler'];flags=r['flags'];sources={'candidate':OUT/'probe.cpp','controller':HERE/'host_controller.cpp','controls':HERE/'controls.cpp','unwind':HERE/'unwind.cpp'}
 sdk=flags[flags.index('-isysroot')+1];sdk_before=sdk_witness.capture(sdk,SDK);dump(OUT/'sdk-before.typed',sdk_before)
 command('retained-deps',[NINJA,'-t','deps',*[str(Path(p).relative_to(CM)) for p in r['objects']]])
 deps=set()
 blocks=(OUT/'retained-deps.stdout').read_text().strip().split('\n\n');found=[]
 for block in blocks:
  lines=block.splitlines();match=re.fullmatch(r'(.+): #deps ([0-9]+), deps mtime ([0-9]+) \(VALID\)',lines[0]);need(match is not None,'valid retained dependencies')
  found.append(str(CM/match[1]));need(len(lines)-1==int(match[2]),'retained dep count')
  deps.update(Path(p.strip()) if Path(p.strip()).is_absolute() else CM/p.strip() for p in lines[1:])
 same(found,r['objects'],'retained dependency membership')
 for name,src in sources.items():
  command(name+'-deps',[c,*flags,'-M','-MT',name+'.o','-MF',OUT/(name+'.d'),src])
  _,tail=(OUT/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)
  deps.update(Path(p) if Path(p).is_absolute() else CM/p for p in shlex.split(tail))
 proof_path=build_provenance.sidecar(ROOT/'build/behavior/path-embed-combined-r1/reference/bin/starbound')
 proof=json.loads(proof_path.read_text());live_sources=build_provenance.source_snapshot(ROOT)
 compile_dependencies={str(p.resolve()) for p in deps}|{str(Path(p).resolve()) for p in proof.get('compile_source_files',{})}
 delta=source_delta(proof['source_files'],live_sources,compile_dependencies)
 dump(OUT/'source-closure.typed',{'historical':proof['source_files'],'live':live_sources,'compile_dependencies':sorted(compile_dependencies),'delta':delta})
 dump(OUT/'boundary-membership.typed',hashes(HERE.glob('*')))
 for p,h in proof.get('compile_source_files',{}).items():need(sha(p)==h,'retained compiler source '+p)
 for p,h in proof['build_identity']['files'].items():need(sha(p)==h,'retained configured profile '+p)
 deps.update(ROOT/p for p in live_sources);deps.add(proof_path);deps.update(map(Path,proof.get('compile_source_files',{})))
 deps.update(Path(p) for p in r['libraries'] if Path(p).is_file());deps.update(map(Path,r['objects']))
 deps.update(HERE.glob('*'));deps={p for p in deps if p.is_file()}
 deps.update((HERE.parent/'lru-cache'/p) for p in ('native.cpp','model.py','inventory.py','CONTRACT.md','StarLruCache.original.hpp'))
 deps.update((HERE.parent/p) for p in ('native_evidence_json.py','native_symbols.py','native_artifacts.py'))
 deps.update((HERE.parent/'path-embed-replay').glob('*.py'));deps.add(HERE.parent/'behavior/build_provenance.py')
 deps.update([Path(c),Path(NINJA),Path(sys.executable).resolve(),CM/'compile_commands.json',CM/'build.ninja',CM/'CMakeFiles/rules.ninja',CM/'CMakeCache.txt',CM/'.ninja_deps',OUT/'recipe.typed',OUT/'corpus.tsv',OUT/'expected.tsv',OUT/'probe.cpp',OUT/'selected.hpp',OUT/'sdk-before.typed',OUT/'source-closure.typed',OUT/'boundary-membership.typed',OUT/'source-policy-controls.typed'])
 inputs=hashes(deps);dump(OUT/'inputs-before.typed',inputs);print('PRECOMPILE_BOUND',len(inputs),flush=True)
 c11=('#include "'+str(HERE/'host_api.h')+'"\n_Static_assert(sizeof(SbLruRequest)==16,"request");\n_Static_assert(sizeof(SbLruReply)==16,"reply");\n').encode()
 command('c11',[c,'-x','c','-std=c11','-isysroot',sdk,'-fsyntax-only','-'],c11)
 for name,src in sources.items():command(name+'-compile',[c,*flags,*(['-DLRU_EXPECT_DIFFERENCE=1'] if BEFORE and name=='unwind' else []),'-c',src,'-o',OUT/(name+'.o')]);same(inputs,hashes(deps),'postcompile input drift')
 for name in ('candidate','controls','unwind'):
  link=[c,*flags,*r['objects'],OUT/'controller.o',OUT/(name+'.o'),*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(OUT/(name+'.map')),'-Wl,-t,-trace_implicit_libraries','-o',OUT/name]
  _,stderr=command(name+'-expand',[c,'-###',*link[1:]])
  commands=[shlex.split(line) for line in stderr.decode().splitlines() if line.lstrip().startswith('"')];need(len(commands)==1,'expanded linker count')
  dump(OUT/(name+'-expanded.typed'),expanded_invocation.bind(commands[0]))
  command(name+'-link',link);command(name+'-disassemble',['/usr/bin/otool','-tvV',OUT/name])
  dump(OUT/(name+'-origin.typed'),origins(name,r,sdk_before));print('BOUND_ORIGIN',name,flush=True)
 same(build_provenance.source_snapshot(ROOT),live_sources,'preexecute complete source membership')
 same(hashes(HERE.glob('*')),load(OUT/'boundary-membership.typed'),'preexecute boundary source membership')
 same(inputs,hashes(deps),'preexecute input drift');dump(OUT/'preexecute.typed',hashes(p for p in OUT.rglob('*') if p.is_file()))
 for alias in ('ordered','hash'):
  for repeat in (1,2):stdout,_=command('run-'+alias+'-'+str(repeat),[OUT/'candidate',alias],corpus);compare(stdout)
  print('MODEL_PASS',alias,640,12,flush=True)
 command('controls-run',[OUT/'controls'])
 command('unwind-run',[OUT/'unwind'])
 dump(OUT/'sdk-after.typed',sdk_witness.capture(sdk,SDK));same(sdk_before,load(OUT/'sdk-after.typed'),'SDK drift');same(inputs,hashes(deps),'final input drift')
 report={'status':'DEMONSTRATED_NATIVE_UNWIND_MISMATCH' if BEFORE else 'FINITE_LRU_MOCK_UNWIND_REPAIR_PASS','inputs':inputs,'artifacts':hashes(p for p in OUT.rglob('*') if p.is_file()),'rows_per_run':640,'properties_per_run':12,'candidate_runs':4,'limits':'native/mock only; no Rust/production/game qualification'}
 verify(report)
 controls=[]
 for name,target in [('source',HERE/'cache.hpp'),('artifact',OUT/'candidate.o')]:
  corrupt=OUT/('corrupt-'+name);write(corrupt,target.read_bytes()+b'corrupt')
  try:verify(report,{str(target):str(corrupt)})
  except ValueError as error:controls.append((name,str(error)))
  else:raise ValueError('corruption escaped '+name)
 receipt=OUT/'run-ordered-1.receipt';bad=load(receipt);bad['status']=False;corrupt=OUT/'corrupt-status';dump(corrupt,bad)
 altered=dict(report);altered['artifacts']=dict(report['artifacts']);altered['artifacts'][str(receipt)]=sha(corrupt)
 try:verify(altered,{str(receipt):str(corrupt)})
 except ValueError as error:controls.append(('typed-status',str(error)))
 else:raise ValueError('bool status escaped')
 witness_path=OUT/'unwind-run.stdout';corrupt=OUT/'corrupt-unwind-output'
 write(corrupt,witness_path.read_bytes().replace(b'NATIVE_UNWIND_CONTROLS_PASS',b'BROKEN_UNWIND_CONTROLS_PASS').replace(b'EXPECTED_NATIVE_UNWIND_MISMATCH',b'BROKEN_NATIVE_UNWIND_MISMATCH'))
 witness_receipt=OUT/'unwind-run.receipt';bad_receipt=load(witness_receipt);bad_receipt['stdout']=sha(corrupt)
 corrupt_receipt=OUT/'corrupt-unwind-receipt';dump(corrupt_receipt,bad_receipt)
 altered=dict(report);altered['artifacts']=dict(report['artifacts']);altered['artifacts'][str(witness_path)]=sha(corrupt);altered['artifacts'][str(witness_receipt)]=sha(corrupt_receipt)
 try:verify(altered,{str(witness_path):str(corrupt),str(witness_receipt):str(corrupt_receipt)})
 except ValueError as error:controls.append(('coherent-unwind-output',str(error)))
 else:raise ValueError('corrupt unwind marker escaped')
 dump(OUT/'verifier-controls.typed',controls);report['artifacts']=hashes(p for p in OUT.rglob('*') if p.is_file());verify(report);dump(OUT/'report.typed',report);print(report['status'],flush=True)

if __name__=='__main__':
 if sys.argv[1:] in (['--verify'],['--before','--verify']):verify();print('READONLY_BOUNDARY_REPLAY_PASS')
 elif sys.argv[1:] not in ([],['--before']):raise SystemExit('usage: acquire.py [--before] [--verify]')
 else:
  try:acquire()
  except Exception as error:
   if OUT.exists() and not (OUT/'STOP.typed').exists():dump(OUT/'STOP.typed',{'status':'UNPROVED','error':str(error),'type':type(error).__name__})
   raise
