#!/usr/bin/env python3
"""Finite TTL application composition. --compose writes a fresh local certificate.
Normal replay creates no processes or files; Zstd decoder semantics stay at the
original successful acquisition, not a claimed subprocess-free re-execution.
"""
import argparse,copy,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'build/ttl-final-qualification-r2'
def guard(event,args):
 if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.forkpty','os.exec','pty.spawn'}:raise ValueError('qualification is subprocess-free')
sys.addaudithook(guard)
sys.path.insert(0,str(ROOT/'source/lab/behavior'))
import behavior_lab as lab
import audit_auxiliary as aux
import capture_schema as schema
from PIL import Image
ROLES=('reference','reference-repeat','candidate')
BASE=ROOT/'build/behavior/ttl-cache-combined-r2'
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
LIMITS=['finite darwin arm64 TTL application compatibility, not universal equivalence, sanitizer, performance, OOM or concurrency qualification','23 actual scene matrices, not full 39-module migration','literal PCM, not audible playback, mixer, Ogg or device behavior','real loopback TCP/save-codec/BTree fixture paths, not Universe handshake or general player/world/ship save interchange','Zstd semantic decoder result belongs to original acquisition; current exact frame/receipt/pixel bindings replayed without a decoder subprocess','agent visual review, not user human sign-off; contact sheets do not establish full-size tiny-label legibility','native/mock/Rust lab and pre-e227 production runtime certificates retain original source/tool identities; post-e227 live runtime guard replay correctly fails on the changed app header, not on the unchanged TTL implementation; no historical closure rebound','local integrity, not signatures or independently reproducible builds']
def audit():
 old=load(ROOT/'build/ttl-game-build-r3/old22-regression-report.json');need([r['scene']for r in old['results']]==list(lab.SCENARIOS[:-1]),'old22 membership/order')
 inputs={};rows=[];pids=set();captures_seen=set();sources={}
 def bind(p):
  p=Path(p);inputs[str(p.relative_to(ROOT))]=sha(p)
 def pin(p,h):need(sha(p)==h,'accepted certificate pin '+str(p));bind(p)
 pin(ROOT/'build/ttl-production-runtime-r2/independent-report-v3.json','b7ed52bfe1451465956ff69f5b167a8d75f8f9f754152924322b975e25efaddc')
 pin(ROOT/'build/ttl-rust-parity-r1/report.typed','4c2e0cae5d61e41141915887b76826e1ad2ee4d916a053740e832894f7b92199')
 pin(ROOT/'build/ttl-cache-native-r1/report.json','cba3b3c84acc2128bd043400cabd6ed2ebf35fcdde37e6d36e2a870bc7926674')
 pin(ROOT/'build/ttl-boundary-r1/report.json','ce0a8e4ff977edd41e2be59a5ec2edd2800138d9b6b113f070198b915c8d76a0')
 roots=[(r['scene'],Path(r['report']).parent,r['sha256'])for r in old['results']]+[('ttl-room',ROOT/'build/behavior/ttl-actual-r2','b03fab572cee167f19997ea8f7869eccec3ddd25113404bbd133ef99b612f2f9')]
 admission=load(ROOT/'build/ttl-game-build-r3/capture-schema-admission.json');need(admission['adapterSha256']==sha(Path(schema.__file__)) and len(admission['rows'])==69,'separate typed schema preflight')
 envelopes={(scene,role):schema.admit(root/role/'frames') for scene,root,_ in roots for role in ROLES}
 for scene,root,report_sha in roots:
  pin(root/'report.json',report_sha);report=load(root/'report.json');need(report['passed'] and report['comparison']['passed'] and report['repeatability']['passed'],'both edges passed')
  role_frames={};starts=[]
  for role in ROLES:
   d=root/role;f=d/'frames';manifest=load(f/'manifest.json');start=load(d/'process-start.json');end=load(d/'process-exit.json');lab.validate_process_binding(f,manifest);process(start,end,manifest)
   need(start['pid']not in pids and manifest['captureId']not in captures_seen,'independent actual game identities');pids.add(start['pid']);captures_seen.add(manifest['captureId']);starts.append(start['wallStarted'])
   need(manifest['binary']==lab.identity(binary(role)),'same fresh game binary')
   proof=manifest['buildProvenance'];need(proof['binary_sha256']==sha(binary(role)),'compiled binary binding');cache={k:v for k,v in proof['build_identity']['cache'].items()if k.startswith('STAR_USE_RUST_')and not k.endswith('-ADVANCED')};need(len(cache)==27,'27 selector frame')
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
 aux_result=aux.audit();pin(ROOT/'build/ttl-game-build-r3/auxiliary-independent-report-v2.json',sha(ROOT/'build/ttl-game-build-r3/auxiliary-independent-report-v2.json'));need(load(ROOT/'build/ttl-game-build-r3/auxiliary-independent-report-v2.json')==aux_result,'independent auxiliary replay');inputs.update(aux_result['bindings']);inputs.update(aux_result['historicalInventoryMetadata']);bind(ROOT/'build/ttl-game-build-r3/capture-schema-admission.json')
 for p in [ROOT/'build/behavior/ttl-actual-r2/agent-visual-inspection.json',ROOT/'build/ttl-game-build-r3/old22-agent-inspection.json',ROOT/'build/ttl-game-build-r3/old22-regression-report.json',ROOT/'build/ttl-game-build-r3/plan.json',ROOT/'build/ttl-game-build-r3/actual-build.receipt.json',ROOT/'build/ttl-game-build-r3/actual-build.plan.json',ROOT/'build/ttl-game-build-r3/actual-build.started.json']:bind(p)
 receipt=load(ROOT/'build/ttl-game-build-r3/actual-build.receipt.json');started=load(ROOT/'build/ttl-game-build-r3/actual-build.started.json');need(receipt['returncode']==0 and receipt['timedOut']is False and receipt['groupGone']is True and receipt['pid']==started['pid']==started['pgid'],'fresh complete build normal status')
 pin(ROOT/'build/ttl-game-build-r3/plan.json','55a6aa0ee206e4435d57be0cb2f612dc70f4e06ab9af16ee2ed3476280c132ab')
 for ext in ['stdout','stderr']:
  p=ROOT/('build/ttl-game-build-r3/actual-build.'+ext);need(sha(p)==receipt[ext+'Sha256'],'actual build stdio');bind(p)
 for p in Path(__file__).parent.glob('*.py'):bind(p)
 for p in (ROOT/'source/lab/behavior').glob('*.py'):bind(p)
 for p in [binary('reference'),binary('candidate')]:bind(p)
 for p,h in sources.items():inputs[p]=h
 need(len(rows)==23 and len(pids)==69,'finite aggregate membership')
 return dict(status='FINITE_TTL_APPLICATION_QUALIFICATION',compiledGameCheckpoint='e2273459',productionRuntimeCertificate='historical accepted 020ff3fe closure before e227 app-only barrier change; TTL/Core implementation unchanged',matrices=rows,actualGameIdentities=69,pngReceiptPairs=207,comparisonEdges=46,auxiliaryActualCommands=22,compositionControls=controls(),schemaControls=schema.controls(),auxiliaryControls=aux_result['negativeControls'],sourceBindings=sources,bindings=dict(sorted(inputs.items())),limits=LIMITS)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--compose',action='store_true');ap.add_argument('--certificate-sha');a=ap.parse_args();result=audit()
 if a.compose:
  need(not OUT.exists(),'fresh certificate only');OUT.mkdir();(OUT/'certificate.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 else:
  need(a.certificate_sha and sha(OUT/'certificate.json')==a.certificate_sha,'explicit certificate pin');need(load(OUT/'certificate.json')==result,'exact composed certificate replay')
 print(json.dumps({k:v for k,v in result.items()if k not in ('bindings','sourceBindings','matrices')},indent=2,sort_keys=True));print('certificateSha256',sha(OUT/'certificate.json'))
if __name__=='__main__':main()
