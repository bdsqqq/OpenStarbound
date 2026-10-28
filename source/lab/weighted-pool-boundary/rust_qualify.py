#!/usr/bin/env python3
"""Read-only, role-aware actual Rust composition, independent of failed producer.
Only --write seals a new certificate; no subprocess/native execution occurs.
"""
import argparse,dataclasses,hashlib,json,re,shlex,sys
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'build/weighted-pool-rust-bridge-r1';MOCK=R/'build/weighted-pool-boundary-integration-r1';MOCK_PIN='2bd44aa1e0562404b994c61eedc933318d3ce118027ffd7b922e40958d2d6fbd'
sys.path[:0]=[str(H),str(H.parent),str(H.parent/'path-embed-replay'),str(H.parent/'weighted-pool')]
import rust_bridge as acquire
import native_evidence_json as codec,archive_identity,expanded_invocation,object_inventory,link_trace,native_symbols,sdk_witness,model

def guard(event,args):
 if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.forkpty','os.exec','pty.spawn'}:raise ValueError('verification cannot execute native tools')
sys.addaudithook(guard)
def need(b,s):
 if not b:raise ValueError(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def typed(p):return codec.loads(Path(p).read_text('ascii'))
def same(a,b,s):need(codec.dumps(a)==codec.dumps(b),s)
def origins(symbols,physical,archive):
 result=[]
 for owner in physical:
  symbol=native_symbols.unique_symbol(symbols,owner['symbol']);need(symbol.object_path==str(archive).encode()+b'('+owner['name']+b')'and symbol.size>0,'live canonical physical owner '+repr(owner['symbol']));result.append(symbol.manifest())
 # A map data label may contain 'mock' (the native negative-control diagnostic
 # actually does). Reject controller functions/origins, not English literals.
 need(not any(s.name.startswith(b'_sb_wp_mock_')or s.object_path.endswith(b'/mock.o')for s in symbols),'linked mock controller origin/export')
 return result
def semantics(actual,native,corpus):
 need(actual.startswith(native+native),'eight original exact traces twice')
 for marker in ['empty-select-no-random','empty-index-consumes','unique-zero-and-empty-global-seed','unique-index-not-value','unique-seed-wrap-retry-order','19-malformed-controls-native-pointer-exception','19-root-4-stage-real-reference-layout-lazy-custom-containers','private-friend-moveonly-cursor-distinct-sentinel-contextual-bool','rust-destination-sentinel-root-tags-status-normalization','pending-native-exception-no-later-mutation','missing-borrow-capability-rejected']:
  need('PASS\t'+marker+'\n'in actual,'actual assertion '+marker)
 need(corpus==model.corpus()[1],'original 27-row rational model')
def controls(symbols,physical,archive,actual,native,corpus):
 run=native_symbols.unique_symbol(symbols,b'_sb_wp_run');personality=native_symbols.unique_symbol(symbols,b'_rust_eh_personality');checks=[('cpp-spoofed-run-provider',lambda:origins([dataclasses.replace(s,object_path=b'/tmp/mock.o')if s is run else s for s in symbols],physical,archive)),('extra-mock-controller-export',lambda:origins([*symbols,dataclasses.replace(run,name=b'_sb_wp_mock_attacks')],physical,archive)),('duplicate-runtime-provider',lambda:origins([*symbols,dataclasses.replace(personality,object_path=b'/tmp/other-rust-runtime.o')],physical,archive)),('native-lifetime-order',lambda:semantics(actual.replace('OBS\tappend\t2\t0\t1','OBS\tappend\t2\t1\t0',1),native,corpus)),('missing-private-positive',lambda:semantics(actual.replace('PASS\tprivate-friend-moveonly-cursor-distinct-sentinel-contextual-bool\n',''),native,corpus)),('rational-row-drift',lambda:semantics(actual,native,corpus.replace('0\n','1\n',1)))]
 rejected=[]
 for name,fn in checks:
  try:fn()
  except ValueError:rejected.append(name);continue
  raise ValueError('known failure accepted '+name)
 need(any(s.name==b'literal string: mock malformed accepted'for s in symbols),'original false-positive diagnostic still present');origins(symbols,physical,archive)
 return rejected

def verify():
 ad=load(O/'admission.json');w=ad['witness'];recipe=ad['recipe'];need(len(recipe['objects'])==113 and len(set(recipe['objects']))==113,'exact113 object membership');need(len(recipe['selectors'])==27 and all(v=='OFF'for _,v in recipe['selectors']),'original native reference selectors');need('-DWP_BOUNDARY_ON=1'in ad['flags']and'-DWP_BOUNDARY_ATTACKS=0'in ad['flags'],'real Rust, no Cppmock API dependency')
 for p,h in w['files'].items():need(sha(p)==h,'preadmitted input '+p)
 for p,target in w['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'original input alias')
 names=['canonical-cargo','compile','expand','link','disassemble','current','corpus'];need(sorted(p.name[:-len('.receipt.json')]for p in O.glob('*.receipt.json'))==sorted(names),'exact command composition')
 for name in names:
  p=load(O/(name+'.plan.json'));x=load(O/(name+'.receipt.json'));s=load(O/(name+'.started.json'));need(x['returncode']==0 and type(x['returncode'])is int and x['reaped']and x['groupGone']and not x['timedOut'],'strict actual exit '+name);need(x['pid']==x['pgid']==s['pid']==s['pgid']and s['osStart'],'actual PID/PGID/OS identity');need(x['startedWallNs']==s['startedWallNs']<=x['endedWallNs'],'actual terminal clock');need(p['admissionSha256']==sha(O/'admission.json')and p['env']==ad['env']and p['cwd']==str(R),'pre-execution binding');need(x['planSha256']==sha(O/(name+'.plan.json')),'exact argv plan')
  for ext in ['stdout','stderr']:need(x[ext+'Sha256']==sha(O/(name+'.'+ext)),'actual stdio '+name)
  need(p['stdinSha256']==sha(O/(name+'.stdin')),'actual stdin '+name)
 canonical=load(O/'canonical.json');archive=Path(ad['archive']);need(canonical['archive']==str(archive)and canonical['sha256']==sha(archive)and canonical['bytes']==archive.stat().st_size,'actual canonical archive');need(canonical['cargoReceiptSha256']==sha(O/'canonical-cargo.receipt.json'),'actual Cargo producer');need(canonical['providersSha256']==sha(O/'canonical-providers.typed'),'canonical physical prelink pins');physical=acquire.physical(archive);same(physical,typed(O/'canonical-providers.typed'),'exact physical archive exports')
 cargo=load(O/'canonical-cargo.plan.json')['argv'];need(cargo==[ad['tools']['STAR_CARGO_EXECUTABLE'],'build','--verbose','--offline','--locked','--manifest-path',str(R/'source/rust/ffi/Cargo.toml'),'--target','aarch64-apple-darwin','--target-dir',str(acquire.TEST/'target'),'--release','--lib'],'only existing single Rust aggregate built');rustlog=(O/'canonical-cargo.stderr').read_text();invocations=[shlex.split(x)for x in re.findall(r'Running `([^`]+)`',rustlog)];compiled=[x for x in invocations if '--crate-name'in x and x[x.index('--crate-name')+1]=='star_engine_ffi'];need(len(compiled)==1 and compiled[0][0]==ad['tools']['STAR_RUSTC_EXECUTABLE']and compiled[0][compiled[0].index('--crate-type')+1]=='staticlib','actual fresh selected rustc staticlib invocation')
 obj=O/'combined.o';need(load(O/'compile.plan.json')['argv']==[recipe['compiler'],*ad['flags'],'-MD','-MF',str(O/'combined.d'),'-c',str(H/'combined.cpp'),'-o',str(obj)],'exact current C++ native adapter compile');deps=shlex.split((O/'combined.d').read_text().replace('\\\n',' ').split(':',1)[1]);need(deps,'actual consumed header closure')
 for p in deps:need(str(Path(p).resolve())in w['files'],'consumed preadmitted input '+p)
 commands=[shlex.split(s)for s in(O/'expand.stderr').read_text().splitlines()if s.lstrip().startswith('"')];need(len(commands)==1,'one actual expanded ld');bound=typed(O/'expanded.typed');expanded_invocation.verify(bound,commands[0]);inv=bound['inventory'];need(inv['tool']==ad['tools']['CMAKE_LINKER'],'actual selected linker');need([p for p in inv['file_inputs']if p.endswith('.o')]==[*recipe['objects'],str(obj)],'exact native objects with no mock');need([p for p in inv['file_inputs']if p.endswith('.a')and('star_engine_ffi'in p or'/rust'in p)]==[str(archive)],'one Rust runtime aggregate')
 blobs={p.encode():Path(p).read_bytes()for p in inv['file_inputs']if p.endswith('.a')};prelink={p:[{k:m[k]for k in('name','offset','sha256')}for m in archive_identity.arm64_archive_members(b)]for p,b in blobs.items()};same(prelink,typed(O/'physical-prelink.typed'),'physical archive tables unchanged since BEFORE link');tables={p:b''.join(m['name']+b'\n'for m in archive_identity.arm64_archive_members(b))for p,b in blobs.items()};objects=[*[str(p).encode()for p in recipe['objects']],str(obj).encode()];trace=link_trace.parse((O/'link.stdout').read_bytes(),objects,tables);mapped=object_inventory.reconcile((O/'combined.map').read_bytes(),objects,tables,blobs);symbols=native_symbols.live_symbols((O/'combined.map').read_bytes());live=origins(symbols,physical,archive)
 expected_link=[recipe['compiler'],*ad['flags'],*recipe['objects'],str(obj),str(archive),*recipe['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(O/'combined.map'),'-Wl,-t,-trace_implicit_libraries','-o',str(O/'combined')];need(load(O/'link.plan.json')['argv']==expected_link,'actual link equals fixed source/tool/archive profile');need(load(O/'expand.plan.json')['argv']==[recipe['compiler'],'-###',*expected_link[1:]],'actual pre-link expansion matches actual link');need(load(O/'disassemble.plan.json')['argv']==['/usr/bin/otool','-tvV',str(O/'combined')],'actual call-edge artifact producer');dis=(O/'disassemble.stdout').read_bytes();need(any(b'_sb_wp_run'in s and(b'\tbl\t'in s or b'\tb\t'in s)for s in dis.splitlines()),'native/Rust call survives linking')
 for name,args in [('current',[]),('corpus',['corpus'])]:need(load(O/(name+'.plan.json'))['argv']==[str(O/'combined'),*args],'actual tested binary '+name)
 actual=(O/'current.stdout').read_text();native=(R/'build/weighted-pool-lifecycle-r1/current.stdout').read_text();corpus=(O/'corpus.stdout').read_text();semantics(actual,native,corpus);need((O/'corpus.stdin').read_text()==model.corpus()[0],'literal frozen model input');need(sha(MOCK/'report.json')==MOCK_PIN,'explicit earlier repaired mock comparison authority');mock=load(MOCK/'report.json');need(mock['products'][str(MOCK/'current.stdout')]==sha(MOCK/'current.stdout'),'prior comparison bytes');expected=re.sub(r'^PASS\tactual-frame-bounds-and-cursor-state-attacks\t[0-9]+\n','',(MOCK/'current.stdout').read_text(),flags=re.M);need(actual==expected,'all native/mock assertion output identical except mock-only attack hook')
 paths=trace['sdk_paths']+mapped['unresolved_origins']+[x['source']for x in trace['indirect_declarations']];requested=recipe['flags'][recipe['flags'].index('-isysroot')+1];sdk=sdk_witness.reconcile_consumed(load(acquire.BASE/'sdk-before.json'),[__import__('os').fsdecode(p)for p in paths],requested_root=requested,expected_canonical_root=requested);acquire.budget();falsifiers=controls(symbols,physical,archive,actual,native,corpus)
 return dict(status='FINITE_ACTUAL_RUST_NATIVE_INTEROP_PASS_BY_INDEPENDENT_COMPOSITION',originalProducer='FAILED_AT_OVERBROAD_MOCK_SUBSTRING_FILTER; literal data is not controller code; no native rerun',actualCommands=7,modes=19,stages=4,malformedControls=19,nativeExactTraces=8,nativeTraceStreams=2,rationalRows=27,falsifiers=falsifiers,providers=live,sdk=sdk,physicalExports=physical,limits=['laboratory std::function scaffolding only; no allocation/OOM/production claim','no actual game matrix/production adoption/full migration claim','captured native arm64 profile and finite values, not universal nonfinite/platform equivalence'])

def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--write',action='store_true');g.add_argument('--certificate-sha');a=ap.parse_args();cert=O/'certificate.typed'
 if a.certificate_sha:
  need(sha(cert)==a.certificate_sha,'external certificate pin');saved=typed(cert);need(saved['verifierSha256']==sha(Path(__file__)),'exact qualifier');
  for p,h in saved['products'].items():need(sha(p)==h,'immutable certificate product '+p)
 result=verify()
 if a.write:
  products={str(p):sha(p)for p in O.rglob('*')if p.is_file()};products.update({str(R/'build/weighted-pool-rust-bridge-r1.acquire.stderr'):sha(R/'build/weighted-pool-rust-bridge-r1.acquire.stderr'),str(R/'build/weighted-pool-rust-bridge-r1.acquire.stdout'):sha(R/'build/weighted-pool-rust-bridge-r1.acquire.stdout')});body=dict(result=result,verifierSha256=sha(Path(__file__)),products=products);acquire.typed(cert,body);print('CERTIFICATE',sha(cert))
 else:same(result,saved['result'],'reconstructed qualification result')
 print(codec.dumps(result))
if __name__=='__main__':main()
