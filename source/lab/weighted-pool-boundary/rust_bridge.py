#!/usr/bin/env python3
"""One-shot actual Rust acquisition, isolated target, same existing aggregate.
The native prototype is still laboratory-only: std::function may allocate.
"""
import datetime as dt,hashlib,json,os,re,shlex,signal,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'build/weighted-pool-rust-bridge-r1';TEST=R/'build/weighted-pool-rust-r1';BASE=R/'build/weighted-pool-native-r1/attempt2';DEADLINE=dt.datetime(2026,10,28,0,23,tzinfo=dt.timezone.utc).timestamp()
sys.path[:0]=[str(H.parent),str(H.parent/'ttl-production'),str(H.parent/'path-embed-replay'),str(H.parent/'weighted-pool')]
from game_syntax import closure,unchanged,subset
import model,sdk_witness,archive_identity,expanded_invocation,object_inventory,link_trace,native_symbols,native_evidence_json as codec

def need(b,s):
 if not b:raise ValueError(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
 with Path(p).open('x')as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def typed(p,v):
 with Path(p).open('x')as f:f.write(codec.dumps(v));f.write('\n');f.flush();os.fsync(f.fileno())
def budget():
 for root,cap in [(O,128*1024**2),(TEST,256*1024**2)]:need(sum(p.stat().st_size for p in root.rglob('*')if p.is_file())<=cap,'unchanged declared cap '+str(root))
def command(name,argv,w,env,stdin=b'',timeout=100):
 unchanged(w);need(time.time()<DEADLINE-1,'deadline');argv=list(map(str,argv));pre=O/name;(O/(name+'.stdin')).write_bytes(stdin);dump(str(pre)+'.plan.json',dict(argv=argv,env=env,cwd=str(R),timeout=timeout,admissionSha256=sha(O/'admission.json'),stdinSha256=sha(O/(name+'.stdin'))));started=time.time_ns();p=subprocess.Popen(argv,cwd=R,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);probe=subprocess.run(['/bin/ps','-p',str(p.pid),'-o','lstart=,pid=,pgid='],capture_output=True,timeout=5).stdout.decode().strip();dump(str(pre)+'.started.json',dict(pid=p.pid,pgid=os.getpgid(p.pid),osStart=probe,startedWallNs=started));timed=False
 try:out,err=p.communicate(stdin,timeout=min(timeout,DEADLINE-time.time()))
 except subprocess.TimeoutExpired:timed=True;os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate(timeout=5)
 try:os.killpg(p.pid,0);gone=False;os.killpg(p.pid,signal.SIGKILL)
 except ProcessLookupError:gone=True
 (O/(name+'.stdout')).write_bytes(out);(O/(name+'.stderr')).write_bytes(err);dump(str(pre)+'.receipt.json',dict(pid=p.pid,pgid=p.pid,returncode=p.returncode,reaped=True,groupGone=gone,timedOut=timed,startedWallNs=started,endedWallNs=time.time_ns(),planSha256=sha(str(pre)+'.plan.json'),stdoutSha256=sha(O/(name+'.stdout')),stderrSha256=sha(O/(name+'.stderr'))));need(gone and not timed and p.returncode==0,'actual leaf '+name);unchanged(w);budget();print(name,p.pid,p.returncode,flush=True)
def physical(archive):
 members=archive_identity.members(Path(archive).read_bytes());exports=[b'_sb_wp_run',b'_sb_wp_count',b'_rust_eh_personality'];owners={s:[]for s in exports}
 for m in members:
  if m['body'][:4]!=b'\xcf\xfa\xed\xfe':continue
  definitions=archive_identity.external_definitions(m['body'])
  for s in exports:
   if s in definitions:owners[s].append(dict(symbol=s,archive=str(archive).encode(),name=m['name'],offset=m['offset'],sha256=m['sha256']))
 for s,rows in owners.items():need(len(rows)==1,'unique physical aggregate provider '+repr(s))
 return [owners[s][0]for s in exports]
def main():
 O.mkdir();(O/'home').mkdir();(O/'tmp').mkdir();native=json.loads((BASE/'admission.json').read_bytes());recipe=json.loads((BASE/'recipe.json').read_bytes());prior=json.loads((TEST/'admission.json').read_bytes());P=json.loads((R/'build/ttl-game-build-r3/plan.json').read_bytes());T=P['tools'];cargo=Path(T['STAR_CARGO_EXECUTABLE']);rustc=Path(T['STAR_RUSTC_EXECUTABLE']);c=recipe['compiler'];archive=TEST/'target/aarch64-apple-darwin/release/libstar_engine_ffi.a';need(not archive.exists(),'new canonical archive, not an old target replacement')
 flags=[*recipe['flags'],'-DWP_BOUNDARY_ON=1','-DWP_BOUNDARY_ATTACKS=0','-I'+str(H),'-I'+str(H.parent/'weighted-pool')]
 env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin',HOME=str(O/'home'),TMPDIR=str(O/'tmp'),CARGO_HOME=str(TEST/'cargo-home'),CARGO_NET_OFFLINE='true',RUSTC=str(rustc),CARGO_TARGET_AARCH64_APPLE_DARWIN_LINKER=str(c),SDKROOT=P['sdk'],LANG='C',LC_ALL='C')
 # Include only declared source/tool/resource trees, never storage or a home scan.
 roots=[R/'source/core',R/'source/extern',R/'source/rust',H,H.parent/'weighted-pool',H.parent/'path-embed-replay',H.parent/'ttl-production',rustc.parent.parent/'lib',Path(c).parent.parent/'lib/clang']
 for i,x in enumerate(recipe['flags']):
  if x in ('-isystem','-isysroot'):roots.append(Path(recipe['flags'][i+1]))
  elif x.startswith('-I'):roots.append(Path(x[2:]))
 w=closure(roots)
 for p,h in prior['files'].items():need(sha(p)==h,'previous actual Rust source/tool identity '+p);w['files'][str(Path(p).resolve())]=h
 tools={**T,'NATIVE_DISASSEMBLER':'/usr/bin/otool','PROCESS_IDENTITY_PROBE':'/bin/ps'}
 for p in [*tools.values(),*native['tools'],*recipe['objects'],*[x for x in recipe['libraries']if x.startswith('/')],str(BASE/'recipe.json'),str(BASE/'sdk-before.json'),str(TEST/'admission.json'),str(H.parent/'native_symbols.py'),str(H.parent/'native_artifacts.py'),str(H.parent/'native_evidence_json.py')]:
  p=Path(p);need(p.is_file(),'selected dependency '+str(p));w['files'][str(p.resolve())]=sha(p)
 sdk_roots=[Path(TEST/'cargo-home'),R/'.cargo',R/'source/.cargo',R/'source/rust/.cargo']
 for p in sdk_roots:
  if p.exists():
   for f in p.rglob('*'):
    if f.is_file():w['files'][str(f.resolve())]=sha(f)
 dump(O/'admission.json',dict(witness=w,recipe=recipe,flags=flags,env=env,tools=tools,archive=str(archive),existingAggregate='source/rust/ffi/Cargo.toml',protectedCurrentGamePair='build/behavior/ttl-cache-combined-r2',previousRustTestsAdmissionSha256=sha(TEST/'admission.json'),deadline=DEADLINE,stageBytesCap=128*1024**2,rustStageBytesCap=256*1024**2))
 command('canonical-cargo',[cargo,'build','--verbose','--offline','--locked','--manifest-path',R/'source/rust/ffi/Cargo.toml','--target','aarch64-apple-darwin','--target-dir',TEST/'target','--release','--lib'],w,env,timeout=150);need(archive.is_file(),'canonical existing aggregate');w['files'][str(archive)]=sha(archive);providers=physical(archive);typed(O/'canonical-providers.typed',providers);dump(O/'canonical.json',dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,cargoReceiptSha256=sha(O/'canonical-cargo.receipt.json'),providersSha256=sha(O/'canonical-providers.typed')))
 dep=O/'combined.d';obj=O/'combined.o';command('compile',[c,*flags,'-MD','-MF',dep,'-c',H/'combined.cpp','-o',obj],w,env);subset(shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]),w);w['files'][str(obj)]=sha(obj)
 link=[c,*flags,*recipe['objects'],obj,archive,*recipe['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(O/'combined.map'),'-Wl,-t,-trace_implicit_libraries','-o',O/'combined']
 command('expand',[c,'-###',*link[1:]],w,env);commands=[shlex.split(s)for s in(O/'expand.stderr').read_text().splitlines()if s.lstrip().startswith('"')];need(len(commands)==1,'one expanded ld');bound=expanded_invocation.bind(commands[0]);need(bound['inventory']['tool']==T['CMAKE_LINKER'],'preselected ld');need([x for x in bound['inventory']['file_inputs']if x.endswith('.o')]==[*recipe['objects'],str(obj)],'exact objects, no mock');need([x for x in bound['inventory']['file_inputs']if x.endswith('.a')and('star_engine_ffi'in x or '/rust'in x)]==[str(archive)],'one Rust aggregate');subset(bound['inventory']['file_inputs'],w);typed(O/'expanded.typed',bound)
 blobs={p.encode():Path(p).read_bytes()for p in bound['inventory']['file_inputs']if p.endswith('.a')};typed(O/'physical-prelink.typed',{p:[{k:m[k]for k in('name','offset','sha256')}for m in archive_identity.arm64_archive_members(b)]for p,b in blobs.items()})
 command('link',link,w,env);expanded_invocation.verify(bound,commands[0]);w['files'][str(O/'combined')]=sha(O/'combined');command('disassemble',['/usr/bin/otool','-tvV',O/'combined'],w,env)
 command('current',[O/'combined'],w,env);corpus,want=model.corpus();command('corpus',[O/'combined','corpus'],w,env,stdin=corpus.encode());need((O/'corpus.stdout').read_text()==want,'original rational corpus');original=(R/'build/weighted-pool-lifecycle-r1/current.stdout').read_bytes();actual=(O/'current.stdout').read_bytes();need(actual.startswith(original+original),'original eight exact lifecycle traces twice')
 for marker in ['19-root-4-stage-real-reference-layout-lazy-custom-containers','private-friend-moveonly-cursor-distinct-sentinel-contextual-bool','rust-destination-sentinel-root-tags-status-normalization','pending-native-exception-no-later-mutation']:need(('PASS\t'+marker+'\n').encode()in actual,'actual Rust native assertion '+marker)
 tables={p:b''.join(m['name']+b'\n'for m in archive_identity.arm64_archive_members(b))for p,b in blobs.items()};objects=[*[str(p).encode()for p in recipe['objects']],str(obj).encode()];trace=link_trace.parse((O/'link.stdout').read_bytes(),objects,tables);mapped=object_inventory.reconcile((O/'combined.map').read_bytes(),objects,tables,blobs);symbols=native_symbols.live_symbols((O/'combined.map').read_bytes());live=[]
 for owner in providers:
  symbol=native_symbols.unique_symbol(symbols,owner['symbol']);need(symbol.object_path==str(archive).encode()+b'('+owner['name']+b')'and symbol.size>0,'live physical canonical provider '+repr(owner['symbol']));live.append(symbol.manifest())
 need(not any(b'mock'in s.name.lower()for s in symbols),'no live mock controller');dis=(O/'disassemble.stdout').read_bytes();need(any(b'_sb_wp_run'in s and(b'\tbl\t'in s or b'\tb\t'in s)for s in dis.splitlines()),'surviving native/Rust call edge')
 paths=trace['sdk_paths']+mapped['unresolved_origins']+[x['source']for x in trace['indirect_declarations']];requested=recipe['flags'][recipe['flags'].index('-isysroot')+1];sdk=sdk_witness.reconcile_consumed(json.loads((BASE/'sdk-before.json').read_bytes()),[os.fsdecode(p)for p in paths],requested_root=requested,expected_canonical_root=requested);typed(O/'origins.typed',dict(providers=live,trace=trace,map=mapped,sdk=sdk));budget();dump(O/'report.json',dict(status='FINITE_ACTUAL_RUST_INTEROP_ACQUIRED; independent replay required; no production/game/OOM claim',admissionSha256=sha(O/'admission.json'),canonicalSha256=sha(O/'canonical.json'),nativeTraces=8,corpusRows=27,products={str(p):sha(p)for p in O.rglob('*')if p.is_file()and p.name not in ['report.json','acquire.stdout','acquire.stderr']}));print('REPORT',sha(O/'report.json'))
if __name__=='__main__':main()
