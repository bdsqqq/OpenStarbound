#!/usr/bin/env python3
"""Event-only lifecycle acquisition; failed monoliths are never rerun or edited."""
import datetime as dt,hashlib,json,os,re,shlex,signal,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];OUT=ROOT/'build/weighted-pool-lifecycle-r1';BASE=ROOT/'build/weighted-pool-native-r1/attempt2'
sys.path.insert(0,str(HERE.parent/'ttl-production'));from game_syntax import unchanged,subset
sys.path.insert(0,str(HERE.parent/'path-embed-replay'));import sdk_witness
DEADLINE=dt.datetime(2026,10,27,22,37,30,tzinfo=dt.timezone.utc).timestamp()
def need(b,s):
 if not b:raise AssertionError(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
 with Path(p).open('x')as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def command(name,argv,w,expected=0):
 need(time.time()<DEADLINE-1,'deadline');unchanged(w);argv=list(map(str,argv));prefix=OUT/name;stdin=b'';env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin',HOME=str(OUT/'home'),TMPDIR=str(OUT/'tmp'),LANG='C',LC_ALL='C');(OUT/(name+'.stdin')).write_bytes(stdin)
 plan=dict(argv=argv,cwd=str(ROOT),env=env,expected=expected,stdinSha256=hashlib.sha256(stdin).hexdigest(),admissionSha256=sha(OUT/'admission.json'));dump(str(prefix)+'.plan.json',plan);started=time.time_ns()
 with open(str(prefix)+'.stdout','xb')as so,open(str(prefix)+'.stderr','xb')as se:
  p=subprocess.Popen(argv,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True);pgid=os.getpgid(p.pid);osstart=subprocess.run(['/bin/ps','-p',str(p.pid),'-o','lstart=,pid=,pgid='],capture_output=True,timeout=5).stdout.decode().strip();dump(str(prefix)+'.started.json',dict(pid=p.pid,pgid=pgid,osStart=osstart,startedWallNs=started));timed=False
  try:code=p.wait(timeout=min(90,DEADLINE-time.time()))
  except subprocess.TimeoutExpired:timed=True;os.killpg(p.pid,signal.SIGKILL);code=p.wait(timeout=5)
  try:os.killpg(p.pid,0);gone=False;os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:gone=True
 dump(str(prefix)+'.receipt.json',dict(pid=p.pid,pgid=pgid,returncode=code,reaped=True,groupGone=gone,timedOut=timed,startedWallNs=started,endedWallNs=time.time_ns(),stdoutSha256=sha(str(prefix)+'.stdout'),stderrSha256=sha(str(prefix)+'.stderr'),planSha256=sha(str(prefix)+'.plan.json')));need(gone and not timed and code==expected,'actual leaf '+name);unchanged(w);need(sum(p.stat().st_size for p in OUT.rglob('*')if p.is_file())<=16*1024**2,'16MiB stage cap');print(name,p.pid,code,flush=True)
def main():
 need(not OUT.exists(),'fresh acquisition');OUT.mkdir();(OUT/'home').mkdir();(OUT/'tmp').mkdir();base=BASE/'admission.json';ad=json.loads(base.read_bytes());w=ad['witness'];r=json.loads((BASE/'recipe.json').read_bytes());header=(ROOT/'source/core/StarWeightedPool.hpp').read_text();needle='  m_items.append({weight, std::move(item)});\n  m_totalWeight += weight;';need(header.count(needle)==1,'mutant exact source patch');mutant=header.replace('WeightedPool','CachedWeightedPool').replace(needle,'  double prior = m_totalWeight;\n  m_items.append({weight, std::move(item)});\n  m_totalWeight = prior + weight;');(OUT/'StarWeightedPool.cached-mutant.hpp').write_text(mutant)
 delta={str(p.resolve()):sha(p)for p in [HERE/'lifecycle.cpp',Path(__file__),OUT/'StarWeightedPool.cached-mutant.hpp',BASE/'recipe.json']};w['files'].update(delta);dump(OUT/'admission.json',dict(basePath=str(base),baseSha256=sha(base),delta=delta,deadline=DEADLINE,mechanism='nonallocating event log, scalar-only selectIndex observers, stable reserved vector, defined cross-pool reentry; NOT another selected-Item-destructor observer'))
 c=r['compiler'];flags=[*r['flags'],'-I'+str(HERE),'-I'+str(OUT)];obj=OUT/'lifecycle.o';exe=OUT/'lifecycle';link=[c,*flags,*r['objects'],str(obj),*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(OUT/'lifecycle.map'),'-Wl,-t,-trace_implicit_libraries','-o',str(exe)]
 command('link-expand',[c,'-###',*[str(x).replace(str(obj),str(HERE/'lifecycle.cpp'))for x in link[1:]]],w)
 selected=[p for p in ad['tools']if p.endswith('/ld')];need(selected and selected[0]in(OUT/'link-expand.stderr').read_text(),'actual ld still preadmitted')
 command('compile',[c,*flags,'-MD','-MF',OUT/'lifecycle.d','-c',HERE/'lifecycle.cpp','-o',obj],w);deps=shlex.split((OUT/'lifecycle.d').read_text().replace('\\\n',' ').split(':',1)[1]);subset(deps,w);w['files'][str(obj)]=sha(obj);command('link',link,w);w['files'][str(exe)]=sha(exe)
 command('current',[exe,'current'],w);command('reference',[exe,'reference'],w);command('mutant',[exe,'mutant'],w,expected=1)
 need((OUT/'current.stdout').read_bytes()==(OUT/'reference.stdout').read_bytes(),'exact current/reference event traces');need(b'post-callback total must be read, not cached'in(OUT/'mutant.stderr').read_bytes(),'compiled callback-state mutant rejected')
 paths=re.findall(r'^\[\s*\d+\] (.*\.tbd)$',(OUT/'lifecycle.map').read_text(errors='surrogateescape'),re.M);need(paths,'actual SDK interfaces');sdk=json.loads((BASE/'sdk-before.json').read_bytes());requested=r['flags'][r['flags'].index('-isysroot')+1];dump(OUT/'sdk-consumed.json',sdk_witness.reconcile_consumed(sdk,paths,requested_root=requested,expected_canonical_root=requested));need((ROOT/'source/core/StarWeightedPool.hpp').read_text()==header,'native header unchanged')
 report=dict(status='EVENT_ONLY_NATIVE_LIFECYCLE_PARITY; prior monoliths remain failed',baseAdmissionSha256=sha(base),admissionSha256=sha(OUT/'admission.json'),commands=6,traces=8,compiledCachedTotalMutantRejected=True,limits=['finite current native profile only','named-result eligibility source-traced; native Item/caller lifetimes observed, not an assertion of measurable List NRVO constructor count','no Rust/game/adoption/full39/performance/oom claim'],products={str(p):sha(p)for p in OUT.rglob('*')if p.is_file()and p.name not in ['report.json','acquire.stdout','acquire.stderr']})
 dump(OUT/'report.json',report);print('REPORT',sha(OUT/'report.json'))
if __name__=='__main__':main()
