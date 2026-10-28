#!/usr/bin/env python3
"""Read-only replay of fresh WeightedPool PCM/CLI artifacts, never launches native code."""
import hashlib,importlib.util,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'build/weighted-pool-auxiliary-r1'
def guard(event,args):
 if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.forkpty','os.exec','pty.spawn'}:raise ValueError('read-only verifier forbids process creation')
sys.addaudithook(guard)
spec=importlib.util.spec_from_file_location('frozen_literal_contracts',ROOT/'source/lab/lru-auxiliary/common.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def need(ok,why):
 if not ok:raise ValueError(why)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def check_status(start,end,plan,out,err):
 need(type(start.get('pid'))is int and start['pid']>0 and start['pid']==start.get('pgid')==end.get('pid'),'actual PID/PGID')
 need(start.get('started')==end.get('started') and end['ended']>=end['started'],'clock')
 need(end['reaped']is True and end['groupGone']is True and end['timedOut']is False and end['returncode']==plan['expected'],'normal actual status')
 need(hashlib.sha256(out).hexdigest()==end['stdoutSha256'] and hashlib.sha256(err).hexdigest()==end['stderrSha256'],'stdio byte binding')
def check_pcm(role,mode,out,err):
 old.exact(json.loads(out),old.pcm_expected(role,mode=='negative'),'independent literal PCM/metadata/eof/seek/counters');old.exact(err,old.BADERR if mode=='negative' else b'','literal PCM error')
def check_cli(name,out,err):
 _,a,b=old.cli_expected(name);old.exact(out,a,'literal CLI stdout');old.exact(err,b,'literal CLI stderr')
def retained_catalog(original,expected):
 manifest=ROOT/'build/weighted-pool-game-origin-r1/catalog-retention.json';need(sha(manifest)=='5dd5bf05e02404fdb18b20033e4047feade751cb3665eb5f6f2a00eae3e173be','explicit historical metadata manifest pin');m=load(manifest)
 need(original==str(ROOT/'source/lab/migration/catalog.json')==m['originalPath'] and expected==m['sha256'],'only exact original inventory metadata may be versioned')
 p=Path(m['retainedPath']);need(p==ROOT/'build/weighted-pool-game-origin-r1/catalog-before.json' and not p.is_symlink() and p.is_file() and p.stat().st_nlink==1 and p.stat().st_size==m['size'] and sha(p)==expected,'exact retained catalog bytes')
 return {str(manifest.relative_to(ROOT)):sha(manifest),str(p.relative_to(ROOT)):sha(p)}
def controls():
 import copy
 failures=[]
 def rejects(label,fn):
  try:fn()
  except (ValueError,KeyError):failures.append(label);return
  raise ValueError('negative control accepted: '+label)
 pcm=old.pcm_expected('candidate');bad=copy.deepcopy(pcm);bad['pcm'][1]+=1;rejects('wrong PCM',lambda:check_pcm('candidate','decode',json.dumps(bad),b''))
 bad=copy.deepcopy(pcm);bad['receipts'][4]=0;rejects('lost Rust byte route',lambda:check_pcm('candidate','decode',json.dumps(bad),b''))
 bad=copy.deepcopy(pcm);bad['seek_verified']=False;rejects('seek regression',lambda:check_pcm('candidate','decode',json.dumps(bad),b''))
 rejects('negative missing error',lambda:check_pcm('candidate','negative',json.dumps(old.pcm_expected('candidate',True)),b''))
 _,out,err=old.cli_expected('help');rejects('coherently rehashed wrong help',lambda:check_cli('help',out+b'x',err));rejects('CLI unexpected stderr',lambda:check_cli('help',out,b'x'))
 start=dict(pid=42,pgid=42,started='a');end=dict(pid=42,started='a',ended='b',reaped=True,groupGone=True,timedOut=False,returncode=0,stdoutSha256=hashlib.sha256(b'').hexdigest(),stderrSha256=hashlib.sha256(b'').hexdigest());plan=dict(expected=0)
 bad=copy.deepcopy(start);bad.pop('pid');rejects('missing PID',lambda:check_status(bad,end,plan,b'',b''));bad=copy.deepcopy(end);bad['returncode']=-6;rejects('aborted process',lambda:check_status(start,bad,plan,b'',b''));bad=copy.deepcopy(end);bad['reaped']=False;rejects('unreaped',lambda:check_status(start,bad,plan,b'',b''))
 check_status(start,end,plan,b'',b'')
 m=load(ROOT/'build/weighted-pool-game-origin-r1/catalog-retention.json');retained_catalog(m['originalPath'],m['sha256']);rejects('versioning tool forbidden',lambda:retained_catalog('/usr/bin/clang',m['sha256']));rejects('versioning compiled source forbidden',lambda:retained_catalog(str(ROOT/'source/core/StarTtlCache.hpp'),m['sha256']));rejects('wrong retained metadata hash',lambda:retained_catalog(m['originalPath'],'0'*64));return failures
def audit():
 admission=load(OUT/'admission.json');report=load(OUT/'report.json');need(report['admissionSha256']==sha(OUT/'admission.json'),'admission pin');old.independent_wave()
 # Includes the original preselected tools/SDK/source closure and all 226 newly
 # built Core/extern objects: never replaces these with historical lab objects.
 m=load(ROOT/'build/weighted-pool-game-origin-r1/catalog-retention.json');metadata=retained_catalog(m['originalPath'],m['sha256']);old.exact(admission['historicalInventoryMetadata'],metadata,'only independently pinned metadata retention')
 for p,h in admission['witness']['files'].items():
  if p==str(ROOT/'source/lab/migration/catalog.json'):metadata.update(retained_catalog(p,h))
  else:need(sha(p)==h,'preadmitted file drift '+p)
 count=0
 for recipe in admission['recipes']:
  role=recipe['role'];need(role in ('reference','candidate'),'backend');need(recipe['compile'][recipe['compile'].index('-c')+1]==str(old.AUDIO),'unchanged real Audio fixture')
  for p in [Path(a) for a in recipe['link'] if a.endswith('.o') and not a.startswith(str(OUT))]:need(str(p.resolve())in admission['witness']['files'],'fresh object admitted')
  for name,argv in [(role+'-compile',recipe['compile']),(role+'-link',recipe['link'])]+[(role+'-'+mode,[recipe['exe']]+(['corrupt-expected-pcm'] if mode=='negative' else [])) for mode in ['decode','repeat','negative']]+[('cli/'+role+'/'+name+'/run',None) for name in old.NAMES]:
   prefix=OUT/name;plan=load(str(prefix)+'.plan.json');start=load(str(prefix)+'.started.json');end=load(str(prefix)+'.receipt.json');out=Path(str(prefix)+'.stdout').read_bytes();err=Path(str(prefix)+'.stderr').read_bytes();check_status(start,end,plan,out,err);count+=1
   if argv is not None:old.exact(plan['argv'],argv,'exact acquired argv')
   if name.startswith('cli/'):
    cli=name.split('/')[2];d=OUT/'cli'/role/cli;expected=[str(ROOT/'build/behavior/weighted-pool-combined-r1'/role/'bin/starbound'),'-bootconfig',str(d/'sbinit.config'),*old.cli_args(cli,d)];old.exact(plan['argv'],expected,'CLI exact argv');old.exact(plan['expected'],old.cli_expected(cli)[0],'CLI exit oracle');old.exact(load(d/'sbinit.config'),old.cli_config(d),'sandbox config');check_cli(cli,out,err)
   elif name.rsplit('-',1)[-1]in ('decode','repeat','negative'):check_pcm(role,name.rsplit('-',1)[-1],out,err)
 need(count==22,'finite command membership')
 return dict(status='FINITE_FRESH_WEIGHTED_POOL_PCM_12CLI_REPLAY_PASS',actualCommands=count,historicalInventoryMetadata=metadata,negativeControls=controls(),limits=['literal WAV only, not mixer/device/Ogg','no full player/world/ship save interchange','not full 39-module migration','inventory catalog bytes retained explicitly; no renewal of original live/global guard closure'],bindings={str(p.relative_to(ROOT)):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()})
if __name__=='__main__':
 result=audit()
 if len(sys.argv)==3 and sys.argv[1]=='--report-sha':
  p=ROOT/'build/weighted-pool-auxiliary-replay-r1.json';need(sha(p)==sys.argv[2] and load(p)==result,'immutable independent report')
 print(json.dumps(result,indent=2,sort_keys=True))
