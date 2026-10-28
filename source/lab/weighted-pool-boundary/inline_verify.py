#!/usr/bin/env python3
"""Subprocess-free inline-frame/native allocator evidence reconstruction."""
import argparse,hashlib,json,re,shlex,sys
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;R=H.parents[2];S=R/'build/weighted-pool-inline-r1';O=S/'acquisition'
sys.path[:0]=[str(H),str(H.parent),str(H.parent/'path-embed-replay'),str(H.parent/'weighted-pool')]
import inline_run as A,rust_qualify as Q
# Q installs its fail-closed process-execution audit hook.
import native_evidence_json as codec,archive_identity,expanded_invocation,object_inventory,link_trace,native_symbols,sdk_witness,model

def need(b,s):
 if not b:raise ValueError(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def typed(p):return codec.loads(Path(p).read_text('ascii'))
def same(a,b,s):
 def normalized(v):
  if type(v)is dict:return ('dict',tuple(sorted((codec.dumps(k),normalized(x))for k,x in v.items())))
  if type(v)in(list,tuple):return (type(v).__name__,tuple(normalized(x)for x in v))
  return codec.dumps(v)
 need(normalized(a)==normalized(b),s)
def expected_objects(name,recipe):
 if name=='combined':return [*recipe['objects'],str(O/'combined.o')]
 if name=='combined-mock':return [*recipe['objects'],str(O/'combined-mock.o'),str(O/'mock.o')]
 return [*[p for p in recipe['objects']if not p.endswith('/StarMemory.cpp.o')],str(O/(name+'.o')),str(O/'native-memory.o')]
def object_roles(name,actual,recipe):same(actual,expected_objects(name,recipe),'actual objects/diagnostic role '+name)
def role_providers(name,symbols,physical,archive):
 # Full API proof calls the count export. The allocation-only probes do not;
 # dead stripping that unused function is expected, NOT renewed API evidence.
 required={b'_sb_wp_run',b'_rust_eh_personality'}
 if name=='combined':required.add(b'_sb_wp_count')
 else:need(name in ['allocation-native','allocation-legacy-native'],'declared Rust image role')
 owners=[p for p in physical if p['symbol']in required]
 need(len(owners)==len(required),'complete role-specific physical providers')
 Q.origins(symbols,owners,archive)
 return sorted(s.decode('ascii')for s in required)
def allocations(positive,negative,exitcode):
 need(positive=='PASS\tnative-empty-allocation-parity\toriginal=0\tboundary=0\nPASS\tnative-closure-allocation-denied\tempty-container-and-seeded-zero-uniques\n','ordinary native new-route parity')
 need(negative=='FAIL\tboundary empty-container construction allocated native C++ storage\n'and type(exitcode)is int and exitcode==1,'known old allocating header actually rejected')
def verify(pin):
 need(sha(O/'report.json')==pin,'external typed-frame report pin');report=load(O/'report.json');need('original procedures FAILED'in report['status'],'original failed-producer truth')
 for p,h in report['products'].items():need(sha(p)==h,'immutable actual product '+p)
 history,old=A.retained();same(history,load(O/'historical-retention.json'),'literal historical source closure');ad=load(O/'admission.json');recipe=ad['recipe'];w=ad['witness'];need(len(recipe['objects'])==113 and len(recipe['selectors'])==27 and all(v=='OFF'for _,v in recipe['selectors']),'same native reference profile');need(ad['archive']==old['archive']and sha(ad['archive'])==ad['archiveSha256'],'same already qualified Rust aggregate')
 for p,h in w['files'].items():need(sha(p)==h,'new actual-source/tool input '+p)
 for p,target in w['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'new exact aliases')
 support=load(O/'prelink-supplement.json');need(sha(O/'prelink-supplement.json')==report['prelinkSupplementSha256'],'actual prelink support admission');need(support['originalAdmissionSha256']==sha(O/'admission.json')and support['originalCertificateSha256']==A.CERT,'same selected prior plugin authority');need(len(support['selectedDriverSupport'])==1,'one omitted prelink plugin')
 for p,h in support['selectedDriverSupport'].items():need(p.endswith('/usr/lib/libLTO.dylib')and h==old['witness']['files'][p]==sha(p),'no changed or substituted tool')
 rev=load(O/'native-allocator-admission.json');need(sha(O/'native-allocator-admission.json')==report['nativeAllocatorAdmissionSha256'],'different native-allocator diagnostic mechanism');need(rev['prelinkSupplementSha256']==sha(O/'prelink-supplement.json'),'prelink lineage')
 for p,h in rev['newSourcePins'].items():need(sha(p)==h,'actual revised allocator source/procedure')
 need('unadmitted dependency:'in(S/'acquire.stderr').read_text()and'libLTO.dylib'in(S/'acquire.stderr').read_text(),'original omitted-plugin failure retained');need('duplicate symbol'in(O/'link-allocation.stderr').read_text()and'StarMemory.cpp.o'in(O/'link-allocation.stderr').read_text(),'original conflicting-global-new failure retained')
 failed=[];accepted=[]
 for p in sorted(O.glob('*.receipt.json')):
  name=p.name[:-len('.receipt.json')];x=load(p);plan=load(O/(name+'.plan.json'));start=load(O/(name+'.started.json'));need(x['pid']==x['pgid']==start['pid']==start['pgid']and start['osStart'],'actual PID/PGID/OS start');need(x['reaped']and x['groupGone']and not x['timedOut'],'terminal actual leaf');need(x['startedWallNs']==start['startedWallNs']<=x['endedWallNs'],'actual terminal clock');need(x['planSha256']==sha(O/(name+'.plan.json')),'exact actual plan');need(plan['admissionSha256']==sha(O/'admission.json')and plan['cwd']==str(R)and plan['env']==ad['env'],'preadmitted native process environment')
  for ext in ['stdout','stderr']:need(x[ext+'Sha256']==sha(O/(name+'.'+ext)),'actual stdout/stderr')
  need(plan['stdinSha256']==sha(O/(name+'.stdin')),'actual stdin')
  if name=='link-allocation':need(x['returncode']==1 and plan['expected']==0,'failed duplicate-global-new link remains failed');failed.append(name)
  else:need(type(x['returncode'])is int and x['returncode']==plan['expected'],'successful or expected-negative actual leaf '+name);accepted.append(name)
 need(failed==['link-allocation']and len(accepted)==23,'one failed native leaf plus23 accepted leaves; original producer failure separate')
 for name in ['combined','combined-mock','mock','allocation','allocation-legacy','native-memory','allocation-native','allocation-legacy-native']:
  plan=load(O/('compile-'+name+'.plan.json'));argv=plan['argv'];need(argv[0]==recipe['compiler']and argv[1:1+len(ad['baseflags'])]==ad['baseflags'],'unchanged production compile profile');dep=O/(name+'.d');need(argv[-6:]==['-MF',str(dep),'-c',argv[-3],'-o',str(O/(name+'.o'))],'actual -MD source/object contract');source=argv[argv.index('-c')+1];deps=shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]);need(deps and source in deps,'actual source consumed')
  for q in deps:need(str(Path(q).resolve())in w['files']or str(Path(q).resolve())in rev['newSourcePins'],'actual consumed source preadmitted '+q)
  if name in ['native-memory','allocation-native','allocation-legacy-native']:need(load(O/('compile-'+name+'.started.json'))['startedWallNs']>rev['sealedWallNs'],'new source admission BEFORE revised compile')
 archive=Path(ad['archive']);physical=A.rust_bridge.physical(archive);origins={};main_symbols=None
 for name in ['combined','allocation-native','allocation-legacy-native','combined-mock']:
  commands=[shlex.split(x)for x in(O/('expand-'+name+'.stderr')).read_text().splitlines()if x.lstrip().startswith('"')];need(len(commands)==1,'one actual expanded ld');bound=typed(O/(name+'-expanded.typed'));expanded_invocation.verify(bound,commands[0]);inv=bound['inventory'];need(inv['tool']==ad['tools']['CMAKE_LINKER'],'selected native linker');objects=[p for p in inv['file_inputs']if p.endswith('.o')];object_roles(name,objects,recipe);rust=[p for p in inv['file_inputs']if p.endswith('.a')and('star_engine_ffi'in p or'/rust'in p)];need(rust==([]if name=='combined-mock'else[str(archive)]),'actual one-or-no Rust aggregate per role');linkplan=load(O/('link-'+name+'.plan.json'));need(load(O/('expand-'+name+'.plan.json'))['argv']==[recipe['compiler'],'-###',*linkplan['argv'][1:]],'expanded argv equals actual link')
  blobs={p.encode():Path(p).read_bytes()for p in inv['file_inputs']if p.endswith('.a')};tables={p:b''.join(m['name']+b'\n'for m in archive_identity.arm64_archive_members(b))for p,b in blobs.items()};trace=link_trace.parse((O/('link-'+name+'.stdout')).read_bytes(),[p.encode()for p in objects],tables);mapped=object_inventory.reconcile((O/(name+'.map')).read_bytes(),[p.encode()for p in objects],tables,blobs);symbols=native_symbols.live_symbols((O/(name+'.map')).read_bytes());requested=recipe['flags'][recipe['flags'].index('-isysroot')+1];paths=trace['sdk_paths']+mapped['unresolved_origins']+[x['source']for x in trace['indirect_declarations']];sdk=sdk_witness.reconcile_consumed(load(A.rust_bridge.BASE/'sdk-before.json'),[__import__('os').fsdecode(p)for p in paths],requested_root=requested,expected_canonical_root=requested)
  if name!='combined-mock':role_providers(name,symbols,physical,archive)
  if name in ['combined','allocation-native','allocation-legacy-native']:
   new=native_symbols.unique_symbol(symbols,b'__Znwm');expected=next(p for p in recipe['objects']if p.endswith('/StarMemory.cpp.o'))if name=='combined'else str(O/'native-memory.o');need(new.object_path==expected.encode()and new.size>0,'native allocator provider distinguished from diagnostic')
  if name=='combined':main_symbols=symbols
  origins[name]=dict(sdk=sdk,objectCount=len(objects),role='Cppmock attack probe'if name=='combined-mock'else'UNMODIFIED113 actual Rust interop'if name=='combined'else'native StarMemory source observer, original object omitted ONLY here')
 need(load(O/'current.plan.json')['argv']==[str(O/'combined')]and load(O/'corpus.plan.json')['argv']==[str(O/'combined'),'corpus'],'actual tested native Rust binary');need((O/'current.stdout').read_bytes()==(A.OLD/'current.stdout').read_bytes(),'all old actual-Rust assertions preserved');actual=(O/'current.stdout').read_text();native=(R/'build/weighted-pool-lifecycle-r1/current.stdout').read_text();corpus=(O/'corpus.stdout').read_text();Q.semantics(actual,native,corpus);need((O/'corpus.stdin').read_text()==model.corpus()[0],'original literal corpus input');need(sha(O/'mock-current.stdout')==sha(R/'build/weighted-pool-boundary-integration-r1/current.stdout'),'exact5382 capability rejection/native assertion output');alloc=(O/'allocation-current-native.stdout').read_text();negative=(O/'allocation-old-native-known-failure.stderr').read_text();allocations(alloc,negative,load(O/'allocation-old-native-known-failure.receipt.json')['returncode'])
 for leaf,binary in [('allocation-current-native','allocation-native'),('allocation-old-native-known-failure','allocation-legacy-native'),('mock-current','combined-mock')]:need(load(O/(leaf+'.plan.json'))['argv']==[str(O/binary)],'actual diagnostic producer '+leaf)
 dis=(O/'disassemble.stdout').read_bytes();need(any(b'_sb_wp_run'in line and(b'\tbl\t'in line or b'\tb\t'in line)for line in dis.splitlines()),'surviving native/Rust edge')
 src=(H/'BoundaryWeightedPool.hpp').read_text();off=re.sub(r'\{\n#if WP_BOUNDARY_ON\n.*?\n#else\n(.*?)\n#endif\n\}',lambda m:'{'+m[1]+'}',src,flags=re.S).replace('#include "StarSet.hpp"\n#include "frame.hpp"\n','');a=off.index('  template<unsigned Mode> struct NativeFrame');b=off.index('  ItemsList m_items;',a);off=off[:a]+off[b:];off=off.replace('private:\n  size_t selectIndex(double target) const;\n\n\n','private:\n  size_t selectIndex(double target) const;\n\n');need(off==(R/'source/core/StarWeightedPool.hpp').read_text().replace('WeightedPool','BoundaryWeightedPool'),'exact original OFF method bodies/layout');frame=(H/'frame.hpp').read_text();need('std::function'not in frame+src and'const_cast'not in src,'inline true-const callback implementation');need('Frame(Frame const&)=delete;'in frame and'Frame(Frame&&)=delete;'in frame and'payload=this;'in frame,'stable inline callback context');proxy=src.replace('BoundaryWeightedPool','ProxyBoundaryWeightedPool').replace('RandomSource','ProxyRandomSource').replace('Random::','ProxyRandom::').replace('staticRandomDouble','proxyStaticRandomDouble');need((H/'ProxyBoundaryWeightedPool.hpp').read_text()==proxy,'exact dependency-only proxy')
 falsifiers=Q.controls(main_symbols,physical,archive,actual,native,corpus)
 try:role_providers('combined',[s for s in main_symbols if s.name!=b'_sb_wp_count'],physical,archive)
 except ValueError:falsifiers.append('full-api-role-missing-count')
 else:raise ValueError('full API proof silently downgraded to diagnostic')
 for name,fn in [('allocation-extra-call',lambda:allocations(alloc.replace('boundary=0','boundary=1'),negative,1)),('old-closure-failure-missing',lambda:allocations(alloc,negative,0)),('diagnostic-substitution-hidden',lambda:object_roles('combined',expected_objects('allocation-native',recipe),recipe))]:
  try:fn()
  except ValueError:falsifiers.append(name);continue
  raise ValueError('known failure accepted '+name)
 A.budget();return dict(status='FINITE_INLINE_FRAME_ACTUAL_RUST_AND_NATIVE_NEW_ROUTE_PARITY_PASS',historicalRetention=history,acceptedNativeLeaves=len(accepted),failedNativeLeaves=failed,failedOriginalProcedures=['missing-prelink-LTO-admission','duplicate-global-new-observer'],nativeTraces=8,traceStreams=2,rationalRows=27,modes=19,stages=4,capabilityRequestsRejected=5382,isolatedFalsifiers=falsifiers,origins=origins,limits=['allocation observer diagnostics replace ONLY StarMemory.cpp.o; normal interop113 objects untouched','ordinary native C++ new-route evidence, not universal OOM/Rust/runtime/performance/platform equivalence','no production selector/header adoption/game qualification/full39 completion'])
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--report-sha',required=True);g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--write',action='store_true');g.add_argument('--certificate-sha');a=ap.parse_args();cert=O/'certificate.typed'
 if a.certificate_sha:
  need(sha(cert)==a.certificate_sha,'external certificate pin');saved=typed(cert);need(saved['verifierSha256']==sha(Path(__file__)),'exact verifier source')
  for p,h in saved['products'].items():need(sha(p)==h,'immutable source/product '+p)
 result=verify(a.report_sha)
 if a.write:
  paths=[p for p in O.rglob('*')if p.is_file()]+[S/p for p in ['acquire.stdout','acquire.stderr','continuation.stdout','continuation.stderr','native-allocator.stdout','native-allocator.stderr','source-versions.json']];A.dump_typed(cert,dict(verifierSha256=sha(Path(__file__)),reportSha256=a.report_sha,products={str(p):sha(p)for p in paths},result=result));print('CERTIFICATE',sha(cert))
 else:same(result,saved['result'],'exact reconstructed certificate')
 print(codec.dumps(result))
if __name__=='__main__':main()
