#!/usr/bin/env python3
"""Parent-only actual same-aggregate IdMap interop, not production/game proof."""
import datetime as dt,hashlib,json,os,re,shlex,signal,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'build/id-map-rust-bridge-r1';TEST=R/'build/id-map-rust-r1';FRAME=R/'build/id-map-boundary-r1';DEADLINE=dt.datetime(2026,10,28,16,49,tzinfo=dt.timezone.utc).timestamp()
sys.path[:0]=[str(H),str(H.parent),str(H.parent/'id-map'),str(H.parent/'ttl-production'),str(H.parent/'path-embed-replay')]
import providers,native_symbols,native_evidence_json as codec,expanded_invocation,archive_identity,object_inventory,link_trace,sdk_witness,model,edge_model
from game_syntax import closure,unchanged,subset
import run as native
need=providers.need
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
 with Path(p).open('x')as f:json.dump(v,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def typed(p,v):
 with Path(p).open('x')as f:f.write(codec.dumps(v));f.write('\n');f.flush();os.fsync(f.fileno())
def budget():
 a=native.cleanup.allocated_bytes(R/'build/migration-evidence-archive');b=native.cleanup.allocated_bytes(R/'build')-a
 need(a<=16*1024**3 and b<=4*1024**3,'fixed4/16GiB limits')
 for root in [O,TEST]:need(native.cleanup.allocated_bytes(root)<=128*1024**2,'fixed128MiB root '+str(root))
 return dict(archive=a,live=b,bridge=native.cleanup.allocated_bytes(O),rust=native.cleanup.allocated_bytes(TEST))
COMMANDS=[]
def command(name,args,w,env,timeout=120):
 need(time.time()<DEADLINE-1,'same bridge deadline');unchanged(w);args=list(map(str,args));prefix=O/name;dump(str(prefix)+'.plan.json',dict(argv=args,env=env,cwd=str(R),admissionSha256=sha(O/'admission.json'),budget=budget()));started=time.time_ns()
 with(O/(name+'.stdout')).open('xb')as so,(O/(name+'.stderr')).open('xb')as se:
  p=subprocess.Popen(args,cwd=R,env=env,stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True);ps=subprocess.run(['/bin/ps','-p',str(p.pid),'-o','lstart=,pid=,pgid='],capture_output=True,timeout=5).stdout.decode().strip();dump(str(prefix)+'.started.json',dict(pid=p.pid,pgid=os.getpgid(p.pid),startedWallNs=started,osStart=ps));timed=False
  try:code=p.wait(timeout=min(timeout,DEADLINE-time.time()))
  except subprocess.TimeoutExpired:timed=True;os.killpg(p.pid,signal.SIGKILL);code=p.wait()
  try:os.killpg(p.pid,0);gone=False;os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:gone=True
 dump(str(prefix)+'.receipt.json',dict(pid=p.pid,pgid=p.pid,returncode=code,reaped=True,groupGone=gone,timedOut=timed,startedWallNs=started,endedWallNs=time.time_ns(),stdoutSha256=sha(O/(name+'.stdout')),stderrSha256=sha(O/(name+'.stderr')),planSha256=sha(str(prefix)+'.plan.json')));COMMANDS.append(name);need(code==0 and gone and not timed,'actual command '+name);unchanged(w);budget();print(name,p.pid,code,flush=True)
def main():
 need(not O.exists(),'fresh bridge root');O.mkdir();(O/'home').mkdir();(O/'tmp').mkdir();budget()
 need(sha(FRAME/'report.json')=='3cec725688d0326431084014c4619a2c0ca9bb64ec92a13108b46899a1f96d0a','external native frame gate');frame=json.loads((FRAME/'report.json').read_bytes());oldw=json.loads((FRAME/'admission-probe.json').read_bytes())['witness'];unchanged(oldw)
 prior=R/'build/id-map-abi-r1/admission.json'
 for p,h in json.loads(prior.read_bytes())['files'].items():need(sha(p)==h,'previous actual Rust test source/tool epoch '+p)
 selector=R/'build/weighted-pool-game-admission-r1/complete-r1/plan.json';need(sha(selector)==native.PIN,'immutable tool-path selector');old=json.loads(selector.read_bytes());T=old['tools'];r=native.recipe();c=r['compiler'];cargo=Path(T['STAR_CARGO_EXECUTABLE']);rustc=Path(T['STAR_RUSTC_EXECUTABLE']);sdk=r['flags'][r['flags'].index('-isysroot')+1];need(sdk==old['sdk'],'SDK selection');archive=TEST/'target/aarch64-apple-darwin/release/libstar_engine_ffi.a';need(not archive.exists(),'new canonical archive, never replace current game archive')
 source=(H/'controls.cpp').read_text();shard=source[source.index('#include "StarDataStreamDevices.hpp"'):source.index('#ifdef IDMAP_BOUNDARY\nusing namespace')];need((H/'trace_key.hpp').read_text()=='// Literal pre-protocol trace shard from frozen controls.cpp.\n#pragma once\n'+shard+'\n}\n','literal original trace shard, no expectation fitting')
 roots=[R/'source/core',R/'source/extern',R/'source/rust',H,H.parent/'id-map',H.parent/'path-embed-replay',H.parent/'ttl-production',rustc.resolve().parent.parent/'lib',Path(c).resolve().parent.parent/'include',Path(c).resolve().parent.parent/'lib/clang',Path(sdk)]
 for i,x in enumerate(r['flags']):
  if x in ('-isystem','-isysroot'):roots.append(Path(r['flags'][i+1]))
  elif x.startswith('-I'):roots.append(Path(x[2:]))
 w=closure(roots);tools=[Path(c),cargo,rustc,Path(T['CMAKE_LINKER']),Path(T['CMAKE_AR']),Path(T['CMAKE_RANLIB']),Path('/usr/bin/otool'),Path('/bin/ps'),Path(sys.executable)]
 for p in tools:w['files'][str(p.resolve(strict=True))]=sha(p);w['aliases'][str(p)]=str(p.resolve(strict=True))
 for p in [*map(Path,r['objects']),*[Path(x)for x in r['libraries']if Path(x).is_absolute()and Path(x).is_file()],FRAME/'native-r2.o',FRAME/'edges.o',FRAME/'report.json',FRAME/'admission-probe.json',prior,selector,H.parent/'native_symbols.py',H.parent/'native_artifacts.py',H.parent/'native_evidence_json.py',R/'scripts/cleanup-migration-artifacts.py']:
  w['files'][str(p.resolve())]=sha(p)
 for name in ['native-r2.o','edges.o']:need(sha(FRAME/name)==frame['products'][str(FRAME/name)],'exact successful C++ frame object '+name)
 before=sdk_witness.capture(sdk,sdk);dump(O/'sdk-before.json',before)
 env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin',HOME=str(O/'home'),TMPDIR=str(O/'tmp'),CARGO_HOME=str(TEST/'cargo-home'),CARGO_NET_OFFLINE='true',RUSTC=str(rustc),CARGO_TARGET_AARCH64_APPLE_DARWIN_LINKER=str(c),SDKROOT=sdk,LANG='C',LC_ALL='C')
 dump(O/'admission.json',dict(witness=w,env=env,recipe=r,tools={k:T[k]for k in ['STAR_CARGO_EXECUTABLE','STAR_RUSTC_EXECUTABLE','CMAKE_LINKER']},archive=str(archive),rustTarget=str(TEST/'target'),deadline=DEADLINE,budget=budget(),nativeFrameReportSha256=sha(FRAME/'report.json'),traceShardSha256=hashlib.sha256(shard.encode()).hexdigest(),scope='actual existing Rust aggregate/staticlib/native interop, NOT production/game/general machine code provenance'))
 command('canonical-cargo',[cargo,'build','--verbose','--offline','--locked','--manifest-path',R/'source/rust/ffi/Cargo.toml','--target','aarch64-apple-darwin','--target-dir',TEST/'target','--release','--lib'],w,env,180);need(archive.is_file(),'canonical archive exists');owners=providers.physical(archive);typed(O/'physical-providers.typed',owners);dump(O/'canonical.json',dict(archive=str(archive),sha256=sha(archive),size=archive.stat().st_size,cargoReceiptSha256=sha(O/'canonical-cargo.receipt.json'),providersSha256=sha(O/'physical-providers.typed')))
 flags=['-I'+str(H),*r['flags']];command('trace-compile',[c,*flags,'-MD','-MF',O/'trace.d','-c',H/'rust_trace.cpp','-o',O/'trace.o'],w,env);subset(shlex.split((O/'trace.d').read_text().replace('\\\n',' ').split(':',1)[1]),w)
 outputs={};origins={}
 for role,obj in [('native',FRAME/'native-r2.o'),('edges',FRAME/'edges.o'),('trace',O/'trace.o')]:
  link=[c,*r['flags'],*r['objects'],obj,archive,*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(O/(role+'.map')),'-Wl,-t,-trace_implicit_libraries','-o',O/role]
  command(role+'-expand',[c,'-###',*link[1:]],w,env);rows=[shlex.split(x)for x in(O/(role+'-expand.stderr')).read_text().splitlines()if x.lstrip().startswith('"')];need(len(rows)==1,'one actual ld expansion');bound=expanded_invocation.bind(rows[0]);need(bound['inventory']['tool']==T['CMAKE_LINKER'],'preselected actual linker');inputs=bound['inventory']['file_inputs'];need([p for p in inputs if p.endswith('.o')]==[*r['objects'],str(obj)],'exact native inputs, no mock.o');need([p for p in inputs if p.endswith('.a')and('star_engine_ffi'in p or'/rust'in p)]==[str(archive)],'single Rust aggregate/runtime')
  for p in inputs:need(str(Path(p).resolve())in w['files']or p in[str(archive),str(O/'trace.o')],'preadmitted or prior-command-product link input '+p)
  typed(O/(role+'-expanded.typed'),bound);blobs={p.encode():Path(p).read_bytes()for p in inputs if p.endswith('.a')};tables={p:b''.join(m['name']+b'\n'for m in archive_identity.arm64_archive_members(b))for p,b in blobs.items()};typed(O/(role+'-prelink.typed'),{p:[{k:m[k]for k in ['name','offset','sha256']}for m in archive_identity.arm64_archive_members(b)]for p,b in blobs.items()})
  command(role+'-link',link,w,env);expanded_invocation.verify(bound,rows[0]);objects=[*[p.encode()for p in r['objects']],str(obj).encode()];trace=link_trace.parse((O/(role+'-link.stdout')).read_bytes(),objects,tables);mapped=object_inventory.reconcile((O/(role+'.map')).read_bytes(),objects,tables,blobs);live=providers.live(native_symbols.live_symbols((O/(role+'.map')).read_bytes()),owners,archive,role=='trace');paths=trace['sdk_paths']+mapped['unresolved_origins']+[x['source']for x in trace['indirect_declarations']];sdkroles=sdk_witness.reconcile_consumed(before,[os.fsdecode(p)for p in paths],requested_root=sdk,expected_canonical_root=sdk);origins[role]=dict(providers=live,sdk=sdkroles,trace=trace,map=mapped)
  command(role,[O/role],w,env);command(role+'-repeat',[O/role],w,env);outputs[role]=(O/(role+'.stdout')).read_text();need(outputs[role]==(O/(role+'-repeat.stdout')).read_text(),'repeat identity')
 command('disassemble',['/usr/bin/otool','-tvV',O/'trace'],w,env);dis=(O/'disassemble.stdout').read_bytes();need(any(b'_sb_idmap_run'in x and(b'\tbl\t'in x or b'\tb\t'in x)for x in dis.splitlines()),'surviving native to Rust call edge')
 model.verify(outputs['native']);edge_model.verify(outputs['edges']);need(outputs['native']==(FRAME/'native-r2.stdout').read_text()and outputs['edges']==(FRAME/'edges.stdout').read_text(),'literal original/mock streams unchanged');traces=[x for x in outputs['trace'].splitlines()if x.startswith('TRACE\t')];need(traces==frame['typedTraces'],'same five native key/const/NRVO traces');need(len([x for x in outputs['trace'].splitlines()if x.startswith('PASS\tactual-rust-')])==3,'three actual aggregate interop/ABI controls')
 unchanged(w);after=sdk_witness.capture(sdk,sdk);need(before==after,'SDK before/after identity');dump(O/'sdk-after.json',after);typed(O/'origins.typed',origins);report=dict(status='FINITE_ACTUAL_RUST_IDMAP_INTEROP_ACQUIRED',commands=COMMANDS,admissionSha256=sha(O/'admission.json'),canonicalSha256=sha(O/'canonical.json'),typedTraces=traces,limits=['actual single-aggregate native interop/provider declarations, NOT production/game/full39','finite domains, not signed overflow/full-small-integer nonprogress','map providers/call edge, NOT complete surviving-code/data-target provenance']);report['products']={str(p):sha(p)for p in O.rglob('*')if p.is_file()and p.name!='report.json'};dump(O/'report.json',report);budget();print('REPORT',sha(O/'report.json'))
if __name__=='__main__':main()
