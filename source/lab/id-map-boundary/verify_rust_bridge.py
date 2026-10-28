#!/usr/bin/env python3
"""Independent read-only provider/input/semantic reconstruction of actual interop."""
import argparse,hashlib,json,os,re,shlex,sys
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'build/id-map-rust-bridge-r1';S=O/'links-r2';FRAME=R/'build/id-map-boundary-r1'
sys.dont_write_bytecode=True;sys.path[:0]=[str(H),str(H.parent),str(H.parent/'id-map'),str(H.parent/'path-embed-replay')]
import providers,native_symbols,native_evidence_json as codec,archive_identity,expanded_invocation,object_inventory,link_trace,sdk_witness,model,edge_model
need=providers.need;sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def typed(p):return codec.loads(Path(p).read_text('ascii'))
def same(a,b,why):need(codec.dumps(a)==codec.dumps(b),why)
PRE=['canonical-cargo','trace-compile','native-expand'];COMMANDS=['native-link','native','native-repeat','edges-expand','edges-link','edges','edges-repeat','trace-expand','trace-link','trace','trace-repeat','disassemble']
def membership(r):need(r['acceptedPredecessorCommands']==PRE and r['commands']==COMMANDS,'exact actual interop role membership')
def audit(pin):
 need(sha(O/'report.json')==pin,'external interop report pin');r=load(O/'report.json');membership(r)
 for p,h in r['products'].items():need(sha(p)==h,'actual product '+p)
 ad=load(O/'admission.json');linkad=load(S/'admission.json');need(sha(S/'admission.json')==r['admissionSha256']and sha(O/'admission.json')==r['originalAdmissionSha256'],'both scoped admission pins');need(ad['deadline']==linkad['deadline'],'no deadline renewal')
 for a in [ad,linkad]:
  for p,h in a['witness']['files'].items():need(sha(p)==h,'preadmitted source/tool/resource '+p)
  for p,target in a['witness']['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'actual tool/input alias')
 frame_admission=load(FRAME/'admission-probe.json')
 for support in linkad['supportTools']:
  physical=str(Path(support['path']).resolve(strict=True));need(support['sha256']==frame_admission['witness']['files'][physical]==linkad['witness']['files'][physical]==sha(physical),'real externally pinned support tool, never a source-copy substitute')
 for name,root in [(x,O)for x in PRE]+[(x,S)for x in COMMANDS]:
  p=load(root/(name+'.plan.json'));e=load(root/(name+'.receipt.json'));s=load(root/(name+'.started.json'));need(e['returncode']==0 and type(e['returncode'])is int and e['reaped']is True and e['groupGone']is True and e['timedOut']is False,'strict actual terminal '+name)
  need(e['pid']>0 and e['pid']==e['pgid']==s['pid']==s['pgid']and s['osStart'],'OS PID/group identity');need(e['startedWallNs']==s['startedWallNs']<=e['endedWallNs']and e['endedWallNs']/1e9<=ad['deadline'],'same original bounded command clock');need(p['admissionSha256']==sha(root/'admission.json')and p['cwd']==str(R)and p['env']==ad['env'],'actual scoped plan binding');need(e['planSha256']==sha(root/(name+'.plan.json')),'exact plan bytes')
  for ext in ['stdout','stderr']:need(e[ext+'Sha256']==sha(root/(name+'.'+ext)),'actual stdio '+name)
 canonical=load(O/'canonical.json');archive=Path(ad['archive']);need(canonical['archive']==str(archive)and canonical['sha256']==sha(archive)and canonical['size']==archive.stat().st_size and canonical['cargoReceiptSha256']==sha(O/'canonical-cargo.receipt.json'),'actual fresh archive producer');owners=providers.physical(archive);same(owners,typed(O/'physical-providers.typed'),'prelink physical unique run/count/EH');need(canonical['providersSha256']==sha(O/'physical-providers.typed'),'physical provider pin')
 cargo=load(O/'canonical-cargo.plan.json')['argv'];need(cargo==[ad['tools']['STAR_CARGO_EXECUTABLE'],'build','--verbose','--offline','--locked','--manifest-path',str(R/'source/rust/ffi/Cargo.toml'),'--target','aarch64-apple-darwin','--target-dir',ad['rustTarget'],'--release','--lib'],'only existing aggregate build');invocations=[shlex.split(x)for x in re.findall(r'Running `([^`]+)`',(O/'canonical-cargo.stderr').read_text())];compiled=[x for x in invocations if '--crate-name'in x and x[x.index('--crate-name')+1]=='star_engine_ffi'];need(len(compiled)==1 and compiled[0][0]==ad['tools']['STAR_RUSTC_EXECUTABLE']and compiled[0][compiled[0].index('--crate-type')+1]=='staticlib','actual selected rustc staticlib compilation')
 recipe=ad['recipe'];need(len(recipe['objects'])==len(set(recipe['objects']))==113 and len(recipe['selectors'])==28 and all(v=='OFF'for _,v in recipe['selectors']),'exact native reference closure');source=(H/'controls.cpp').read_text();shard=source[source.index('#include "StarDataStreamDevices.hpp"'):source.index('#ifdef IDMAP_BOUNDARY\nusing namespace')];need(hashlib.sha256(shard.encode()).hexdigest()==ad['traceShardSha256']and(H/'trace_key.hpp').read_text()=='// Literal pre-protocol trace shard from frozen controls.cpp.\n#pragma once\n'+shard+'\n}\n','unfitted literal typed trace shard')
 need(load(O/'trace-compile.plan.json')['argv']==[recipe['compiler'],'-I'+str(H),*recipe['flags'],'-MD','-MF',str(O/'trace.d'),'-c',str(H/'rust_trace.cpp'),'-o',str(O/'trace.o')],'exact current trace compiler input');deps=shlex.split((O/'trace.d').read_text().replace('\\\n',' ').split(':',1)[1]);need(all(str(Path(p).resolve())in ad['witness']['files']for p in deps),'preadmitted consumed trace headers')
 saved=typed(O/'origins.typed');before=load(O/'sdk-before.json');need(before==load(O/'sdk-after.json'),'SDK before/after witness');outputs={}
 for role,obj in [('native',FRAME/'native-r2.o'),('edges',FRAME/'edges.o'),('trace',O/'trace.o')]:
  link=[recipe['compiler'],*recipe['flags'],*recipe['objects'],str(obj),str(archive),*recipe['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(O/(role+'.map')),'-Wl,-t,-trace_implicit_libraries','-o',str(O/role)];need(load(S/(role+'-link.plan.json'))['argv']==link,'exact actual link '+role);root=O if role=='native'else S;need(load(root/(role+'-expand.plan.json'))['argv']==[recipe['compiler'],'-###',*link[1:]],'exact expansion role')
  rows=[shlex.split(x)for x in(root/(role+'-expand.stderr')).read_text().splitlines()if x.lstrip().startswith('"')];need(len(rows)==1,'one linker command');bound=typed(S/(role+'-expanded.typed'));expanded_invocation.verify(bound,rows[0]);inputs=bound['inventory']['file_inputs'];need(bound['inventory']['tool']==ad['tools']['CMAKE_LINKER']and[p for p in inputs if p.endswith('.o')]==[*recipe['objects'],str(obj)],'no replacement/mock native objects');need([p for p in inputs if p.endswith('.a')and('star_engine_ffi'in p or'/rust'in p)]==[str(archive)],'one runtime aggregate');need(all(str(Path(p).resolve())in linkad['witness']['files']for p in inputs),'link-only input admission closes omitted support tools')
  blobs={p.encode():Path(p).read_bytes()for p in inputs if p.endswith('.a')};tables={p:b''.join(m['name']+b'\n'for m in archive_identity.arm64_archive_members(raw))for p,raw in blobs.items()};same({p:[{k:m[k]for k in ['name','offset','sha256']}for m in archive_identity.arm64_archive_members(raw)]for p,raw in blobs.items()},typed(S/(role+'-prelink.typed')),'physical tables before link')
  objects=[*[p.encode()for p in recipe['objects']],str(obj).encode()];trace=link_trace.parse((S/(role+'-link.stdout')).read_bytes(),objects,tables);mapped=object_inventory.reconcile((O/(role+'.map')).read_bytes(),objects,tables,blobs);live=providers.live(native_symbols.live_symbols((O/(role+'.map')).read_bytes()),owners,archive,role=='trace');paths=trace['sdk_paths']+mapped['unresolved_origins']+[x['source']for x in trace['indirect_declarations']];sdk=recipe['flags'][recipe['flags'].index('-isysroot')+1];s=sdk_witness.reconcile_consumed(before,[os.fsdecode(p)for p in paths],requested_root=sdk,expected_canonical_root=sdk);same(dict(providers=live,sdk=s,trace=trace,map=mapped),saved[role],'independent provider/input/SDK reconstruction')
  for suffix in ['', '-repeat']:need(load(S/(role+suffix+'.plan.json'))['argv']==[str(O/role)],'actual tested image')
  outputs[role]=(S/(role+'.stdout')).read_text();need(outputs[role]==(S/(role+'-repeat.stdout')).read_text(),'actual repeat bytes')
 model.verify(outputs['native']);edge_model.verify(outputs['edges']);need(outputs['native']==(FRAME/'native-r2.stdout').read_text()and outputs['edges']==(FRAME/'edges.stdout').read_text(),'frozen native/mock literal streams');need([x for x in outputs['trace'].splitlines()if x.startswith('TRACE\t')]==r['typedTraces']==load(FRAME/'report.json')['typedTraces'],'five exact typed traces');need([x for x in outputs['trace'].splitlines()if x.startswith('PASS\tactual-rust-')]==r['actualRustMarkers']and len(r['actualRustMarkers'])==3,'actual ten-root/exception/ABI assertions')
 need(load(S/'disassemble.plan.json')['argv']==['/usr/bin/otool','-tvV',str(O/'trace')],'exact disassembled tested image');need(any(b'_sb_idmap_run'in x and(b'\tbl\t'in x or b'\tb\t'in x)for x in(S/'disassemble.stdout').read_bytes().splitlines()),'native to Rust call survives')
 return dict(status='FINITE_ACTUAL_RUST_IDMAP_INTEROP_REPLAY_PASS',reportSha256=pin,commands=15,physicalExports=3,rootModes=10,continuations=2,typedTraces=5,limits=r['limits'])
def main():
 p=argparse.ArgumentParser();p.add_argument('--report-sha',required=True);a=p.parse_args()
 def guard(event,args):
  if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.exec'}:raise ValueError('read-only actual interop verifier')
 sys.addaudithook(guard);print(json.dumps(audit(a.report_sha),indent=2,sort_keys=True))
if __name__=='__main__':main()
