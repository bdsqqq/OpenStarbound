#!/usr/bin/env python3
"""Fresh finite mock integration after source/versioned protocol repairs.
No old acquisition is rerun; no Rust or production acceptance is claimed here.
"""
import datetime as dt,hashlib,json,os,re,shlex,signal,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'build/weighted-pool-boundary-integration-r1';BASE=R/'build/weighted-pool-native-r1/attempt2';DEADLINE=dt.datetime(2026,10,27,23,49,tzinfo=dt.timezone.utc).timestamp()
sys.path.insert(0,str(H.parent/'ttl-production'));from game_syntax import closure,unchanged,subset
sys.path.insert(0,str(H.parent/'path-embed-replay'));import sdk_witness
sys.path.insert(0,str(H.parent/'weighted-pool'));import model

def need(b,s):
 if not b:raise AssertionError(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
 with Path(p).open('x')as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def command(name,argv,w,expected=0,stdin=b''):
 need(time.time()<DEADLINE-1,'deadline');unchanged(w);argv=list(map(str,argv));prefix=O/name;env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin',HOME=str(O/'home'),TMPDIR=str(O/'tmp'),LANG='C',LC_ALL='C');(O/(name+'.stdin')).write_bytes(stdin);dump(str(prefix)+'.plan.json',dict(argv=argv,env=env,cwd=str(R),expected=expected,stdinSha256=hashlib.sha256(stdin).hexdigest(),admissionSha256=sha(O/'admission.json')))
 started=time.time_ns();p=subprocess.Popen(argv,cwd=R,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);osstart=subprocess.run(['/bin/ps','-p',str(p.pid),'-o','lstart=,pid=,pgid='],capture_output=True,timeout=5).stdout.decode().strip();dump(str(prefix)+'.started.json',dict(pid=p.pid,pgid=os.getpgid(p.pid),osStart=osstart,startedWallNs=started));timed=False
 try:out,err=p.communicate(stdin,timeout=min(90,DEADLINE-time.time()))
 except subprocess.TimeoutExpired:timed=True;os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate(timeout=5)
 try:os.killpg(p.pid,0);gone=False;os.killpg(p.pid,signal.SIGKILL)
 except ProcessLookupError:gone=True
 (O/(name+'.stdout')).write_bytes(out);(O/(name+'.stderr')).write_bytes(err);dump(str(prefix)+'.receipt.json',dict(pid=p.pid,pgid=p.pid,returncode=p.returncode,reaped=True,groupGone=gone,timedOut=timed,startedWallNs=started,endedWallNs=time.time_ns(),planSha256=sha(str(prefix)+'.plan.json'),stdoutSha256=sha(O/(name+'.stdout')),stderrSha256=sha(O/(name+'.stderr'))));need(gone and not timed and p.returncode==expected,'leaf '+name);unchanged(w);need(sum(p.stat().st_size for p in O.rglob('*')if p.is_file())<=64*1024**2,'64MiB stage cap');print(name,p.pid,p.returncode,flush=True)
def main():
 need(not(O/'admission.json').exists(),'fresh acquisition');(O/'home').mkdir();(O/'tmp').mkdir();recipe=json.loads((BASE/'recipe.json').read_bytes());old=json.loads((BASE/'admission.json').read_bytes());c=recipe['compiler'];flags=[*recipe['flags'],'-DWP_BOUNDARY_ON=1','-DWP_BOUNDARY_ATTACKS=1','-I'+str(H),'-I'+str(H.parent/'weighted-pool')]
 oldsource=O/'old-integration.cpp';oldsource.write_text('#include "before/BoundaryWeightedPool.hpp"\n#include <iostream>\nint main(int argc,char**){try{Star::BoundaryWeightedPool<int> p;if(argc>1){p.items();}else{p.add(1,7);}return 0;}catch(std::exception const&e){std::cerr<<e.what()<<"\\n";return 1;}}\n')
 roots=[R/'source/core',R/'source/extern',H,H.parent/'weighted-pool',Path(recipe['flags'][recipe['flags'].index('-isysroot')+1]),Path(c).parent.parent/'lib/clang']
 for i,x in enumerate(recipe['flags']):
  if x in ('-isystem','-isysroot'):roots.append(Path(recipe['flags'][i+1]))
  elif x.startswith('-I'):roots.append(Path(x[2:]))
 w=closure(roots)
 for p in [*old['tools'],*recipe['objects'],*[x for x in recipe['libraries']if x.startswith('/')],str(BASE/'recipe.json'),str(BASE/'sdk-before.json'),str(oldsource),*[str(p)for p in(O/'before').iterdir()]]:
  p=Path(p);w['files'][str(p.resolve())]=sha(p)
 dump(O/'admission.json',dict(witness=w,recipe=recipe,flags=flags,oldSourceVersionsSha256=sha(O/'before.json'),purpose='new native/mock protocol/capability/private-access revision, not old source-origin rebinding',deadline=DEADLINE))
 link=lambda obj,out:[c,*flags,*recipe['objects'],str(obj),str(O/'mock.o'),*recipe['libraries'],'-Wl,-dead_strip','-Wl,-t,-trace_implicit_libraries','-o',str(out)]
 command('link-expand',[c,'-###',*[str(x).replace(str(O/'combined.o'),str(H/'combined.cpp'))for x in link(O/'combined.o',O/'combined')]],w);selected=[p for p in old['tools']if p.endswith('/ld')];need(selected and selected[0]in(O/'link-expand.stderr').read_text(),'actual ld preselected')
 for name,src in [('mock',H/'mock.cpp'),('combined',H/'combined.cpp'),('old-integration',oldsource)]:
  dep=O/(name+'.d');obj=O/(name+'.o');command('compile-'+name,[c,*flags,'-MD','-MF',dep,'-c',src,'-o',obj],w);subset(shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]),w);w['files'][str(obj)]=sha(obj)
 for name in ['combined','old-integration']:
  command('link-'+name,link(O/(name+'.o'),O/name),w);w['files'][str(O/name)]=sha(O/name)
 command('current',[O/'combined'],w);corpus,expected=model.corpus();command('corpus',[O/'combined','corpus'],w,stdin=corpus.encode());need((O/'corpus.stdout').read_text()==expected,'unchanged corpus')
 command('old-sentinel',[O/'old-integration'],w,expected=1);command('old-items',[O/'old-integration','items'],w,expected=1)
 for name in ['old-sentinel','old-items']:need((O/(name+'.stderr')).read_text()=='weighted boundary protocol\n','old actual mismatch reproduced '+name)
 command('private-friend-positive',[c,*flags,'-DWP_FRIEND_ORIGINAL=0','-fsyntax-only',H/'friend.cpp'],w)
 native=(R/'build/weighted-pool-lifecycle-r1/current.stdout').read_bytes();actual=(O/'current.stdout').read_bytes();need(actual.startswith(native+native),'eight native/reference traces each identical');need(b'PASS\tactual-frame-bounds-and-cursor-state-attacks\t'in actual,'actual frame adversarial controls');need(b'PASS\tprivate-friend-moveonly-cursor-distinct-sentinel-contextual-bool\n'in actual,'access and contextual-bool evidence')
 paths=[p for p in(O/'link-combined.stdout').read_text(errors='surrogateescape').splitlines()if p.startswith('/')and p.endswith('.tbd')];sdk=json.loads((BASE/'sdk-before.json').read_bytes());requested=recipe['flags'][recipe['flags'].index('-isysroot')+1];dump(O/'sdk-consumed.json',sdk_witness.reconcile_consumed(sdk,paths,requested_root=requested,expected_canonical_root=requested))
 dump(O/'report.json',dict(status='FINITE_MOCK_INTEGRATION_REPAIRS_PASS; actual Rust and allocation-free production pending',originalAbiSha256=sha(R/'source/core/StarRustWeightedPool.h'),nativeTraceCount=8,unchangedCorpusRows=27,knownOldSentinelAndItemsFailuresReproduced=True,privateFriendPositive=True,sourceVersionsSha256=sha(O/'before.json'),admissionSha256=sha(O/'admission.json'),products={str(p):sha(p)for p in O.rglob('*')if p.is_file()and p.name not in ['report.json','acquire.stdout','acquire.stderr']}));print('REPORT',sha(O/'report.json'))
if __name__=='__main__':main()
