#!/usr/bin/env python3
"""Fresh CPU-only literal PCM and 12 CLI leaves on the current TTL game pair.
Legacy auxiliary sources stay frozen: only their independent literals are reused.
"""
import datetime as dt,hashlib,importlib.util,json,os,shlex,signal,subprocess,sys,time
from pathlib import Path
from game_syntax import unchanged,subset
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'build/ttl-auxiliary-r1';BASE=ROOT/'build/behavior/ttl-cache-combined-r2'
spec=importlib.util.spec_from_file_location('frozen_auxiliary_literals',ROOT/'source/lab/lru-auxiliary/common.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
DEADLINE=dt.datetime(2026,10,27,21,44,tzinfo=dt.timezone.utc).timestamp()
def need(ok,why):
 if not ok:raise AssertionError(why)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def command(name,argv,w,expected=0,cwd=ROOT,env=None):
 unchanged(w);pfx=OUT/name;pfx.parent.mkdir(parents=True,exist_ok=True);env=env or dict(os.environ,PYTHONDONTWRITEBYTECODE='1');need(time.time()<DEADLINE-2,'deadline')
 dump(str(pfx)+'.plan.json',dict(argv=list(map(str,argv)),cwd=str(cwd),env=env,expected=expected));started=dt.datetime.now(dt.timezone.utc).isoformat()
 with open(str(pfx)+'.stdout','wb') as so,open(str(pfx)+'.stderr','wb') as se:
  p=subprocess.Popen(list(map(str,argv)),cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True);dump(str(pfx)+'.started.json',dict(pid=p.pid,pgid=os.getpgid(p.pid),started=started));timed=False
  try:code=p.wait(timeout=min(120 if 'compile' in name or 'link' in name else 15,DEADLINE-time.time()))
  except subprocess.TimeoutExpired:timed=True;os.killpg(p.pid,signal.SIGKILL);code=p.wait()
  try:os.killpg(p.pid,0);gone=False;os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:gone=True
 dump(str(pfx)+'.receipt.json',dict(pid=p.pid,returncode=code,reaped=True,groupGone=gone,timedOut=timed,started=started,ended=dt.datetime.now(dt.timezone.utc).isoformat(),stdoutSha256=sha(str(pfx)+'.stdout'),stderrSha256=sha(str(pfx)+'.stderr')))
 need(code==expected and gone and not timed,'actual command '+name);unchanged(w)
 return Path(str(pfx)+'.stdout').read_bytes(),Path(str(pfx)+'.stderr').read_bytes()
def main():
 need(not OUT.exists(),'fresh output root');OUT.mkdir();old.independent_wave()
 plan=ROOT/'build/ttl-game-build-r3/plan.json';need(sha(plan)=='55a6aa0ee206e4435d57be0cb2f612dc70f4e06ab9af16ee2ed3476280c132ab','source/tool preadmission')
 w=json.loads(plan.read_text())['witness'];recipes=[]
 for role in ['reference','candidate']:
  cm=BASE/role/'cmake';db=json.loads((cm/'compile_commands.json').read_text());entry=next(e for e in db if e['file'].endswith('/StarAudio.cpp'));args=shlex.split(entry['command']);flags=[];skip=False
  for a in args[1:]:
   if skip:skip=False;continue
   if a in ('-o','-MF','-MT'):skip=True
   elif a not in ('-c',entry['file'],'-MD','-MMD'):flags.append(a)
  lines=(cm/'build.ninja').read_text().splitlines();at=next(i for i,l in enumerate(lines) if l.startswith('build ') and '/bin/starbound:' in l)
  objs=[cm/a for a in shlex.split(lines[at].split(': ',1)[1])[1:] if a.endswith('.o') and a.startswith(('core/','extern/'))];need(len(objs)==113,'113 fresh Core/extern')
  libs=shlex.split(next(l.split(' = ',1)[1] for l in lines[at+1:at+20] if l.startswith('  LINK_LIBRARIES = ')));libs=[str(cm/a) if a.endswith('.a') and not Path(a).is_absolute() else a for a in libs]
  obj=OUT/(role+'.o');exe=OUT/role;compile=[args[0],*flags,'-MD','-MF',str(OUT/(role+'.d')),'-c',str(old.AUDIO),'-o',str(obj)];link=[args[0],*flags,str(obj),*map(str,objs),*libs,'-Wl,-dead_strip','-Wl,-map,'+str(OUT/(role+'.map')),'-o',str(exe)]
  for p in [cm/'CMakeCache.txt',cm/'build.ninja',cm/'compile_commands.json',BASE/role/'bin/starbound',BASE/role/'bin/starbound.behavior-build.json',*objs,*map(Path,[a for a in libs if a.endswith('.a')])]:w['files'][str(p.resolve())]=sha(p)
  recipes.append(dict(role=role,compile=compile,link=link,exe=str(exe)))
 for p in [Path(__file__),Path(old.__file__),old.AUDIO,old.CLI]:w['files'][str(p.resolve())]=sha(p)
 dump(OUT/'admission.json',dict(witness=w,recipes=recipes,literals=old.independent_wave(),sourceCheckpoint='e2273459',scope='no GPU/audio device/mixer/ogg/performance claim'))
 results=[]
 for x in recipes:
  role=x['role'];command(role+'-compile',x['compile'],w);deps=shlex.split((OUT/(role+'.d')).read_text().replace('\\\n',' ').split(':',1)[1]);subset(deps,w);w['files'][str((OUT/(role+'.o')).resolve())]=sha(OUT/(role+'.o'))
  command(role+'-link',x['link'],w);w['files'][str(Path(x['exe']).resolve())]=sha(x['exe'])
  for mode in ['decode','repeat','negative']:
   argv=[x['exe']]+(['corrupt-expected-pcm'] if mode=='negative' else []);data,err=command(role+'-'+mode,argv,w,1 if mode=='negative' else 0);need(json.loads(data)==old.pcm_expected(role,mode=='negative') and err==(old.BADERR if mode=='negative' else b''),'literal PCM metadata/seek/counters/error')
  for name in old.NAMES:
   d=OUT/'cli'/role/name;d.mkdir(parents=True);(d/'home').mkdir();(d/'storage').mkdir();(d/'sbinit.config').write_text(json.dumps(old.cli_config(d)))
   env={k:v for k,v in os.environ.items() if k not in ('SteamAppId','SteamGameId','STAR_BEHAVIOR_LAB','SDL_AUDIODRIVER','SDL_VIDEODRIVER')};env.update(HOME=str(d/'home'),XDG_DATA_HOME=str(d/'home/data'),XDG_CONFIG_HOME=str(d/'home/config'),XDG_CACHE_HOME=str(d/'home/cache'),SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PYTHONDONTWRITEBYTECODE='1')
   code,expected,stderr=old.cli_expected(name);a=[str(BASE/role/'bin/starbound'),'-bootconfig',str(d/'sbinit.config'),*old.cli_args(name,d)];data,err=command('cli/'+role+'/'+name+'/run',a,w,code,cwd=d,env=env);need(data==expected and err==stderr,'literal early exit CLI '+role+'/'+name)
  results.append(dict(role=role,pcm=True,corruptPcmRejected=True,cliCases=6,binarySha256=sha(BASE/role/'bin/starbound')))
 dump(OUT/'report.json',dict(status='FRESH_LITERAL_PCM_AND_12_CLI_PASS',results=results,admissionSha256=sha(OUT/'admission.json')));print(json.dumps(results,indent=2))
if __name__=='__main__':main()
