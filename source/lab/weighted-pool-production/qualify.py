#!/usr/bin/env python3
"""Finite WeightedPool application composition. --compose writes a fresh local certificate.
Normal replay creates no processes or files; Zstd decoder semantics stay at the
original successful acquisition, not a claimed subprocess-free re-execution.
"""
import argparse,copy,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'build/weighted-pool-final-qualification-r1'
def guard(event,args):
 if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.forkpty','os.exec','pty.spawn'}:raise ValueError('qualification is subprocess-free')
sys.addaudithook(guard)
sys.path.insert(0,str(ROOT/'source/lab/behavior'))
import behavior_lab as lab
import audit_auxiliary_v2 as aux
import importlib.util
_spec=importlib.util.spec_from_file_location('weighted_capture_schema',ROOT/'source/lab/ttl-production/capture_schema.py');schema=importlib.util.module_from_spec(_spec);sys.modules[_spec.name]=schema;_spec.loader.exec_module(schema)
from PIL import Image
ROLES=('reference','reference-repeat','candidate')
BASE=ROOT/'build/behavior/weighted-pool-combined-r1'
def need(ok,why):
 if not ok:raise ValueError(why)
def sha(p):return aux.sha(p)
def load(p):return json.loads(Path(p).read_bytes())
def binary(role):return BASE/('candidate' if role=='candidate' else 'reference')/'bin/starbound'
def process(start,end,manifest):
 need(type(start.get('pid'))is int and start['pid']>0 and start['pid']==start.get('pgid')==end.get('pid')==end.get('pgid'),'actual game PID/PGID')
 need(start['status']=='started' and end['status']=='reaped' and end['exitCode']==0,'actual game normal exit')
 need(start['osStart'] and end['osStart']==start['osStart'],'actual OS start identity')
 need(start['binary']==manifest['binary'] and end['startReceipt']==manifest['processStart'],'actual process source binding')
def controls():
 rejected=[]
 def rejects(label,fn):
  try:fn()
  except (ValueError,KeyError):rejected.append(label);return
  raise ValueError('falsifier accepted '+label)
 start=dict(pid=7,pgid=7,status='started',osStart='fixed',binary={'sha256':'fixed'});end=dict(pid=7,pgid=7,status='reaped',exitCode=0,osStart='fixed',startReceipt={'sha256':'fixed'});m=dict(binary=start['binary'],processStart=end['startReceipt']);process(start,end,m)
 for label,key,value in [('abort','exitCode',-6),('unreaped','status','started'),('wrong PID','pid',8),('wrong PGID','pgid',8),('wrong OS identity','osStart','other')]:
  bad=copy.deepcopy(end);bad[key]=value;rejects(label,lambda bad=bad:process(start,bad,m))
 bad=copy.deepcopy(m);bad['binary']['sha256']='wrong';rejects('wrong binary',lambda:process(start,end,bad))
 bad=copy.deepcopy(m);bad['processStart']['sha256']='wrong';rejects('missing launch binding',lambda:process(start,end,bad))
 return rejected
LIMITS=['finite darwin arm64 WeightedPool application compatibility, not universal equivalence, sanitizer, performance, OOM or concurrency qualification','24 actual scene matrices, not full39 migration; WeightedPool scene reaches roots9/12/17/18, not all19 roots','literal PCM, not audible playback/mixer/Ogg/device behavior','actual loopbackTCP/save-codec/BTree fixture, not Universe handshake or general player/world/ship save interchange','Zstd semantic decoder result belongs to original successful acquisition; only immutable frame/receipt/pixel bindings replayed here','agent visual inspection via sheets and selected originals, not user human sign-off or fullsize readability of every label','historical lab certificates retain their original sources/epochs; no renewed historical live/inode/source-origin claims','game origin witness is finite entry-code identity and a static native call, not unique historical linker choice or full data-target provenance','original first build driver remains failed101; successful same-generation candidate-only continuation is explicit','local integrity, not signatures or independently reproducible builds']
def audit():
 old=load(ROOT/'build/weighted-pool-game-admission-r1/old23-composed-report.json');need([r['scenario']for r in old['reports']]==list(lab.SCENARIOS[:-1]),'old23 membership/order')
 inputs={};rows=[];pids=set();captures_seen=set();sources={}
 def bind(p):
  p=Path(p);inputs[str(p.relative_to(ROOT))]=sha(p)
 def pin(p,h):need(sha(p)==h,'accepted certificate pin '+str(p));bind(p)
 pins=[('build/weighted-pool-native-composition-r1/report.json','baa67c9bc3ef05faecae2a690c91c5048e397ffef907b4e2920505aef28552b1'),('build/weighted-pool-boundary-integration-r1/report.json','2bd44aa1e0562404b994c61eedc933318d3ce118027ffd7b922e40958d2d6fbd'),('build/weighted-pool-rust-bridge-r1/certificate.typed','039d8ad74ff29512fb9069a18c15a4277906ef10c98810e98c8558e4a1759a42'),('build/weighted-pool-inline-r1/acquisition/certificate.typed','05858f2e19bfb8392bf8ad2a4dfe7803a5c006fcc3bf5fa55a2ab73cbbc06cb3'),('build/weighted-pool-production-r1/acquisition/certificate.typed','767ce920b538c0a44ce2fb3d7642df76c1ec4f28622fe186aa7421f172cf1a14'),('build/weighted-pool-scene-r1/native/report.json','d8b51ab18a196b32767e956aa02bc93d5a7251589ea0078c9066711bf7de672b'),('build/weighted-pool-game-origin-r1/parent-final.stdout','48a9df0de8771f22341a7b5ffee4d846295287e89fa19a986b4d30f7b0abcbe6'),('build/weighted-pool-game-admission-r1/all24-matrices.json','809d8668050ec77b1b294f1a33d773403aaa8d989d970a04f2035af2ccadbb50')]
 for p,h in pins:pin(ROOT/p,h)
 roots=[(r['scenario'],Path(r['path']).parent,r['sha256'])for r in old['reports']]+[('weighted-pool-room',ROOT/'build/behavior/weighted-pool-actual-r1','89b0e630fc909357a2f39163a1a9f15e85ca0b39e9f366046645696dd69e75b0')]
 envelopes={(scene,role):schema.admit(root/role/'frames')for scene,root,_ in roots for role in ROLES}
 for scene,root,report_sha in roots:
  pin(root/'report.json',report_sha);report=load(root/'report.json');need(report['passed'] and report['comparison']['passed'] and report['repeatability']['passed'],'both edges passed')
  role_frames={};starts=[]
  for role in ROLES:
   d=root/role;f=d/'frames';manifest=load(f/'manifest.json');start=load(d/'process-start.json');end=load(d/'process-exit.json');lab.validate_process_binding(f,manifest);process(start,end,manifest)
   identity=(start['pid'],start['osStart']);need(identity not in pids and manifest['captureId']not in captures_seen,'independent actual game identities');pids.add(identity);captures_seen.add(manifest['captureId']);starts.append(start['wallStarted'])
   need(manifest['binary']==lab.identity(binary(role)),'same fresh game binary')
   proof=manifest['buildProvenance'];need(proof['binary_sha256']==sha(binary(role)),'compiled binary binding');cache={k:v for k,v in proof['build_identity']['cache'].items()if k.startswith('STAR_USE_RUST_')and not k.endswith('-ADVANCED')};need(len(cache)==28,'28 selector frame')
   for k,v in cache.items():need(v==('OFF'if role!='candidate'or k=='STAR_USE_RUST_LINE_QUERY'else'ON'),'evaluated selector '+k)
   for field in ['source_files','compile_source_files']:
    for p,h in proof[field].items():
     path=Path(p)if Path(p).is_absolute()else ROOT/p;need(sha(path)==h,'fresh compiled source closure '+p);sources[str(path.relative_to(ROOT))]=h
   if scene!='zstd-room':frames,_=lab.validated(f)
   else:
    # Do not substitute a fake decoder: preserve original semantic acquisition.
    frames={}
    for p in f.glob('*.json'):
     if p.name=='manifest.json':continue
     envelope=envelopes[(scene,role)][p.stem];receipt=copy.deepcopy(envelope.metadata);receipt['worldState']={field:receipt[field] for field in lab.SCENE_FIELDS};png=f/envelope.file;im=lab.image(png);frames[p.stem]=dict(receipt=receipt,png=png,dimensions=list(im.size),pngSha256=sha(png),receiptSha256=sha(p),pixelsSha256=hashlib.sha256(im.tobytes()).hexdigest())
    need(lab.inventory(frames)==manifest['frames'],'Zstd immutable acquired frames')
   need(len(frames)==3 and {v['receipt']['scenario']for v in frames.values()}=={scene},'exact three scene states');role_frames[role]=frames
   for p in d.rglob('*'):
    if p.is_file():bind(p)
  need(starts==sorted(starts)and len(set(starts))==3,'native-repeat before Rust')
  for role in ROLES[1:]:
   a,b=role_frames['reference'],role_frames[role];need(a.keys()==b.keys(),'stage membership')
   for k in a:
    need(a[k]['pixelsSha256']==b[k]['pixelsSha256'] and a[k]['dimensions']==b[k]['dimensions'],'exact rendered pixels')
    for field in ['stage','worldState','inWorld']:need(a[k]['receipt'][field]==b[k]['receipt'][field],'native world state '+field)
  rows.append(dict(scene=scene,actualGames=3,candidateStates=3,pixelEdges=2))
 aux_result=aux.audit();replay=ROOT/'build/weighted-pool-auxiliary-replay-r2.json';need(load(replay)==aux_result,'exact independent fresh auxiliary replay');bind(replay);inputs.update(aux_result['bindings']);inputs.update(aux_result['historicalInventoryMetadata'])
 origin=load(ROOT/'build/weighted-pool-game-origin-r1/parent-final.stdout');need(origin['complete'] and not origin['blockers'] and len(origin['functions'])==3 and origin['native_call_edges'],'actual game finite emitted-code identity')
 need(origin['game_sha256']==sha(binary('candidate')) and origin['archive_sha256']==sha(BASE/'candidate/cmake/rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a'),'game/archive origin identity');bind(BASE/'candidate/cmake/rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a')
 from game_origin import attest
 need(attest(binary('candidate').read_bytes(),(BASE/'candidate/cmake/rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a').read_bytes())==origin,'read-only exact original game identity replay')
 gate=load(ROOT/'build/weighted-pool-buffer-gates-r1/report.json');need(len(gate['rows'])==9 and len(gate['controls'])==3 and all(c['rejected']is True for c in gate['controls']),'finite actual TCP/save/BTree gate');bind(ROOT/'build/weighted-pool-buffer-gates-r1/report.json')
 for p,h in gate['bindings'].items():need(sha(p)==h,'fresh actual TCP/save/BTree binding');bind(p)
 build=ROOT/'build/weighted-pool-game-admission-r1';plan=build/'complete-r1/plan.json';pin(plan,'e890b99b615433d3557629bccd2a503c76e44b79d459bfa162d4ed9f7b0d9eb3')
 for name,expected in [('build',101),('resume',0)]:
  receipt=load(build/(name+'.receipt.json'));started=load(build/(name+'.started.json'));need(receipt['returncode']==expected and receipt['reaped']is True and receipt['groupGone']is True and receipt['stopReason']is None and receipt['pid']==started['pid']==started['pgid'],'actual original/continuation terminal status');need(receipt['planSha256']==sha(build/(name+'.plan.json')),'build plan pin')
  for ext in ['stdout','stderr']:
   p=build/(name+'.'+ext);need(sha(p)==receipt[ext+'Sha256'],'actual build stdio');bind(p)
  for ext in ['receipt.json','started.json','plan.json']:bind(build/(name+'.'+ext))
 resume=load(build/'resume.plan.json');need(resume['previousFailureReceiptSha256']==sha(build/'build.receipt.json') and resume['sourceChange']is False and resume['env']['RUSTC']==load(plan)['tools']['STAR_RUSTC_EXECUTABLE'],'same admitted compiler continuation, not first-attempt success')
 for name in ['primary-inspection.json','old12-inspection.json','old11-inspection.json','old23-composed-report.json','all24-matrices.json']:bind(build/name)
 for p in Path(__file__).parent.glob('*.py'):bind(p)
 bind(Path(schema.__file__))
 for p in (ROOT/'source/lab/behavior').glob('*.py'):bind(p)
 for p in [binary('reference'),binary('candidate')]:bind(p)
 for p,h in sources.items():inputs[p]=h
 need(len(rows)==24 and len(pids)==72,'finite aggregate membership')
 return dict(status='FINITE_WEIGHTED_POOL_APPLICATION_QUALIFICATION',compiledGameCheckpoint='2aa0c6e0',historicalLabCertificates='pinned exact original accepted byte epochs; not renewed live/source guards',matrices=rows,actualGameIdentities=72,pngReceiptPairs=216,comparisonEdges=48,auxiliaryActualCommands=22,tcpSaveBtreeReceipts=9,compositionControls=controls(),schemaControls=schema.controls(),auxiliaryControls=aux_result['negativeControls'],sourceBindings=sources,bindings=dict(sorted(inputs.items())),limits=LIMITS)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--compose',action='store_true');ap.add_argument('--certificate-sha');a=ap.parse_args();result=audit()
 if a.compose:
  need(not OUT.exists(),'fresh certificate only');OUT.mkdir();(OUT/'certificate.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 else:
  need(a.certificate_sha and sha(OUT/'certificate.json')==a.certificate_sha,'explicit certificate pin');need(load(OUT/'certificate.json')==result,'exact composed certificate replay')
 print(json.dumps({k:v for k,v in result.items()if k not in ('bindings','sourceBindings','matrices')},indent=2,sort_keys=True));print('certificateSha256',sha(OUT/'certificate.json'))
if __name__=='__main__':main()
