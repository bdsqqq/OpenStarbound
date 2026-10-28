#!/usr/bin/env python3
"""Replay finite actual production-header selection/behavior. No subprocesses."""
import argparse,hashlib,json,re,shlex,sys
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;R=H.parents[2];S=R/'build/weighted-pool-production-r1';O=S/'acquisition';B=H.parent/'weighted-pool-boundary';sys.path[:0]=[str(H),str(B),str(H.parent),str(H.parent/'path-embed-replay'),str(H.parent/'weighted-pool')]
import run as A,inline_verify as I,rust_qualify as Q
import native_evidence_json as codec,archive_identity,expanded_invocation,object_inventory,link_trace,native_symbols,sdk_witness,model
REPORT='f3e268ba407fa64264f95ff0913a43ce9a44f5cdb2f9f2df9ce762b1db6a3fe2';CONSUMERS='ec6db0fe042e9032bd4c513cbeba4cf58db54258b0d50c2958af6ffc6939e8d5';META='dd26cf0fbc7df44a8d99f5a613b71f82353488faa75c20ed775299a41e85edaf'
def need(b,s):
 if not b:raise ValueError(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def typed(p):return codec.loads(Path(p).read_text('ascii'))
def metadata():
 need(sha(S/'metadata-retention.json')==META,'pre-refresh metadata pin');m=load(S/'metadata-retention.json');need(m['parentSourceVersionsSha256']==A.PROD_VERSIONS,'metadata/source epoch lineage');allowed={str(R/'source/lab/migration/catalog.json'),str(R/'source/lab/migration/modules.json')};need({r['path']for r in m['sources']}==allowed,'ONLY two noncompiled metadata files')
 for row in m['sources']:need(Path(row['copy']).parent==S/'before'and sha(row['copy'])==row['sha256'],'exact old metadata retained')
 return {r['path']:r for r in m['sources']}
def command(name,ad):
 x=load(O/(name+'.receipt.json'));p=load(O/(name+'.plan.json'));s=load(O/(name+'.started.json'));need(type(x['returncode'])is int and x['returncode']==0 and x['reaped']and x['groupGone']and not x['timedOut'],'strict actual exit '+name);need(x['pid']==x['pgid']==s['pid']==s['pgid']and s['osStart'],'actual native identity');need(x['startedWallNs']==s['startedWallNs']<=x['endedWallNs'],'actual clock');need(p['cwd']==str(R)and p['env']==ad['env']and p['admissionSha256']==sha(O/'admission.json'),'preadmitted native plan');need(x['planSha256']==sha(O/(name+'.plan.json')),'exact plan binding')
 for ext in ['stdout','stderr']:need(x[ext+'Sha256']==sha(O/(name+'.'+ext)),'actual stdio')
 need(p['stdinSha256']==sha(O/(name+'.stdin')),'actual stdin');return p

def verify():
 need(sha(O/'report.json')==REPORT and sha(O/'consumer-report.json')==CONSUMERS,'original completed acquisitions externally pinned');report=load(O/'report.json');
 for p,h in report['products'].items():need(sha(p)==h,'original immutable acquisition '+p)
 history,prior=A.retained();I.same(history,load(O/'historical-retention.json'),'exact historical source/artifact closure');ad=load(O/'admission.json');w=ad['witness'];recipe=ad['recipe'];need(len(recipe['objects'])==113 and len(recipe['selectors'])==27 and all(v=='OFF'for _,v in recipe['selectors']),'same original reference object profile')
 for p,h in w['files'].items():need(sha(p)==h,'current compiled/source/tool input '+p)
 for p,target in w['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'current aliases')
 allnames=['cmake-default','cmake-on','disassemble']+[backend+'-'+action for backend in ['native','rust']for action in ['compile','expand','link','current','corpus']]+['consumer-'+name for name in ['StarTreasure.cpp','StarWeather.cpp','StarCelestialDatabase.cpp']];need(sorted(p.name[:-len('.receipt.json')]for p in O.glob('*.receipt.json'))==sorted(allnames),'exact16 actual commands')
 plans={name:command(name,ad)for name in allnames};need(len(allnames)==16,'bounded exact command count')
 need((O/'cmake-default.stderr').read_text()=='weighted=OFF;aggregate=OFF;definitions=\n'and(O/'cmake-on.stderr').read_text()=='weighted=ON;aggregate=ON;definitions=STAR_USE_RUST_WEIGHTED_POOL\n','actual CMake engine gate evaluation');need(plans['cmake-default']['argv']==[ad['tools']['CMAKE_EXECUTABLE'],'-P',str(O/'selector-contract.cmake')]and plans['cmake-on']['argv']==[ad['tools']['CMAKE_EXECUTABLE'],'-DSTAR_USE_RUST_WEIGHTED_POOL=ON','-P',str(O/'selector-contract.cmake')],'declared evaluated gate, not full project configuration')
 cmake=(R/'source/CMakeLists.txt').read_text();need('option(STAR_USE_RUST_WEIGHTED_POOL "Use experimental Rust WeightedPool controllers" OFF)'in cmake,'default OFF option');need('OR STAR_USE_RUST_WEIGHTED_POOL)\n  include(Rust)'in cmake,'same aggregate selected by sole new feature');need('if(STAR_USE_RUST_WEIGHTED_POOL)\n  add_compile_definitions(STAR_USE_RUST_WEIGHTED_POOL)\nendif()'in cmake,'conditional compile definition')
 qualified=B/'BoundaryWeightedPool.hpp';frame=B/'frame.hpp';inline=load(A.INLINE/'admission.json');need(sha(qualified)==inline['witness']['files'][str(qualified)]and sha(frame)==inline['witness']['files'][str(frame)],'exact qualified native inputs');expected=qualified.read_text().replace('BoundaryWeightedPool','WeightedPool').replace('WpBoundary::','RustWeightedPoolDetail::').replace('using namespace WpBoundary;','using namespace RustWeightedPoolDetail;').replace('#if WP_BOUNDARY_ON','#ifdef STAR_USE_RUST_WEIGHTED_POOL').replace('#include "StarSet.hpp"\n#include "frame.hpp"','#ifdef STAR_USE_RUST_WEIGHTED_POOL\n#include "StarSet.hpp"\n#include "StarWeightedPoolHost.hpp"\n#endif');a=expected.index('  template<unsigned Mode> struct NativeFrame');b=expected.index('  ItemsList m_items;',a);expected=expected[:a]+'#ifdef STAR_USE_RUST_WEIGHTED_POOL\n'+expected[a:b]+'#endif\n'+expected[b:];need((R/'source/core/StarWeightedPool.hpp').read_text()==expected,'exact namespace/selector/include/guard promotion, no policy rewrite');need((R/'source/core/StarWeightedPoolHost.hpp').read_text()==frame.read_text().replace('namespace WpBoundary {','namespace Star::RustWeightedPoolDetail {'),'exact inline native frame promotion')
 archive=Path(ad['archive']);physical=A.rust_bridge.physical(archive);need(sha(archive)==ad['archiveSha256'],'same canonical existing Rust runtime');origins={};rust_symbols=None
 for backend in ['native','rust']:
  flags=[*ad['baseflags'],*(['-DSTAR_USE_RUST_WEIGHTED_POOL','-DWP_BOUNDARY_ON=1']if backend=='rust'else['-DWP_BOUNDARY_ON=0'])];obj=O/(backend+'.o');dep=O/(backend+'.d');need(plans[backend+'-compile']['argv']==[recipe['compiler'],*flags,'-MD','-MF',str(dep),'-c',str(H/'combined.cpp'),'-o',str(obj)],'actual production backend definition '+backend);deps=shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]);need(str(R/'source/core/StarWeightedPool.hpp')in deps,'ACTUAL production header consumed')
  for p in deps:need(str(Path(p).resolve())in w['files'],'consumed C++ source/header preadmitted')
  expanded=[shlex.split(x)for x in(O/(backend+'-expand.stderr')).read_text().splitlines()if x.lstrip().startswith('"')];need(len(expanded)==1,'one expanded ld');bound=typed(O/(backend+'-expanded.typed'));expanded_invocation.verify(bound,expanded[0]);inv=bound['inventory'];objects=[*recipe['objects'],str(obj)];need([p for p in inv['file_inputs']if p.endswith('.o')]==objects,'all113 unchanged native objects');need([p for p in inv['file_inputs']if p.endswith('.a')and('star_engine_ffi'in p or'/rust'in p)]==[str(archive)],'single existing aggregate');need(inv['tool']==ad['tools']['CMAKE_LINKER'],'selected ld');need(plans[backend+'-expand']['argv']==[recipe['compiler'],'-###',*plans[backend+'-link']['argv'][1:]],'actual expansion/link correspondence')
  blobs={p.encode():Path(p).read_bytes()for p in inv['file_inputs']if p.endswith('.a')};tables={p:b''.join(m['name']+b'\n'for m in archive_identity.arm64_archive_members(b))for p,b in blobs.items()};trace=link_trace.parse((O/(backend+'-link.stdout')).read_bytes(),[p.encode()for p in objects],tables);mapped=object_inventory.reconcile((O/(backend+'.map')).read_bytes(),[p.encode()for p in objects],tables,blobs);symbols=native_symbols.live_symbols((O/(backend+'.map')).read_bytes());owners=physical if backend=='rust'else[p for p in physical if p['symbol']!=b'_sb_wp_count'];Q.origins(symbols,owners,archive);requested=recipe['flags'][recipe['flags'].index('-isysroot')+1];paths=trace['sdk_paths']+mapped['unresolved_origins']+[x['source']for x in trace['indirect_declarations']];sdk=sdk_witness.reconcile_consumed(load(A.rust_bridge.BASE/'sdk-before.json'),[__import__('os').fsdecode(p)for p in paths],requested_root=requested,expected_canonical_root=requested);origins[backend]=dict(sdk=sdk,rootCounterCoverage=backend=='rust',nativeObjects=113)
  if backend=='rust':rust_symbols=symbols
  need(plans[backend+'-current']['argv']==[str(O/backend)]and plans[backend+'-corpus']['argv']==[str(O/backend),'corpus'],'actual tested backend binary');need((O/(backend+'-corpus.stdout')).read_text()==model.corpus()[1]and(O/(backend+'-corpus.stdin')).read_text()==model.corpus()[0],'original rational model')
 actual=(O/'rust-current.stdout').read_text();native=(R/'build/weighted-pool-lifecycle-r1/current.stdout').read_text();corpus=(O/'rust-corpus.stdout').read_text();Q.semantics(actual,native,corpus);need(actual==(A.RUST/'current.stdout').read_text(),'all original actual-Rust assertions unchanged');off=(O/'native-current.stdout').read_text();need(off.replace('PASS\tnative-production-header-off-reference-layout-lazy-custom-containers\n','PASS\t19-root-4-stage-real-reference-layout-lazy-custom-containers\n')==actual,'native OFF agrees, root-count label not misattributed');need(plans['disassemble']['argv']==['/usr/bin/otool','-tvV',str(O/'rust')],'actual disassembly');need(any(b'_sb_wp_run'in line and(b'\tbl\t'in line or b'\tb\t'in line)for line in(O/'disassemble.stdout').read_bytes().splitlines()),'surviving actual production/native Rust edge')
 metadata_rows=metadata();consumer=load(O/'consumer-admission.json');need(sha(O/'consumer-admission.json')==load(O/'consumer-report.json')['admissionSha256'],'consumer supplement before typecheck')
 for p,h in consumer['witness']['files'].items():
  if sha(p)==h:continue
  row=metadata_rows.get(p);need(row is not None and row['sha256']==h and sha(row['copy'])==h,'ONLY exact historical noncompiled metadata can resolve '+p)
 for row in consumer['commands']:
  name='consumer-'+row['name'];need(plans[name]['argv']==row['argv'],'exact real game TU syntax command');need(load(O/(name+'.started.json'))['startedWallNs']>consumer['sealedWallNs'],'source admitted BEFORE consumer syntax compile');need('-fsyntax-only'in row['argv']and'-DSTAR_USE_RUST_WEIGHTED_POOL'in row['argv']and'-o'not in row['argv'],'typechecked, no object/game executed');deps=shlex.split((O/(row['name']+'.d')).read_text().replace('\\\n',' ').split(':',1)[1]);need(row['source']in deps and str(R/'source/core/StarWeightedPool.hpp')in deps,'actual real consumer/header dependency')
  for p in deps:need(str(Path(p).resolve())in consumer['witness']['files'],'all actual consumer dependencies preadmitted')
 falsifiers=Q.controls(rust_symbols,physical,archive,actual,native,corpus)
 try:Q.origins([s for s in rust_symbols if s.name!=b'_sb_wp_count'],physical,archive)
 except ValueError:falsifiers.append('production-api-count-export-missing')
 else:raise ValueError('production proof silently downgraded')
 A.budget();return dict(status='FINITE_ACTUAL_PRODUCTION_WEIGHTED_POOL_DEFAULT_OFF_ON_PASS',actualCommands=16,nativeTraces=8,traceStreams=2,rationalRows=27,apiModes=19,stages=4,isolatedFalsifiers=falsifiers,origins=origins,consumerTUs=[r['source']for r in consumer['commands']],historicalRetention=history,metadataRetentionSha256=META,limits=['source-extracted CMake gate EVALUATED, not full project configure/build','Treasure/Weather/Celestial TYPECHECKED only, not executed gameplay','no actual game matrix/PNG/PCM-CLI-TCP-save-BTree or cleanup/full39 completion claim'])
def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--write',action='store_true');g.add_argument('--certificate-sha');a=ap.parse_args();cert=O/'certificate.typed'
 if a.certificate_sha:
  need(sha(cert)==a.certificate_sha,'external production certificate pin');saved=typed(cert);need(saved['verifierSha256']==sha(Path(__file__)),'exact verifier')
  for p,h in saved['products'].items():need(sha(p)==h,'immutable production certificate artifact '+p)
 result=verify()
 if a.write:
  A.dump_typed(cert,dict(result=result,verifierSha256=sha(Path(__file__)),products={str(p):sha(p)for p in O.rglob('*')if p.is_file()},metadataRetentionSha256=META));print('CERTIFICATE',sha(cert))
 else:I.same(result,saved['result'],'exact production replay')
 print(codec.dumps(result))
if __name__=='__main__':main()
