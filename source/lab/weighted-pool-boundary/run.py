#!/usr/bin/env python3
"""One-shot native mock acquisition. Never invokes Cargo, game, or old producers."""
import datetime as dt,hashlib,json,os,re,shlex,signal,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;ROOT=H.parents[2];OUT=ROOT/'build/weighted-pool-boundary-mock-r1';BASE=ROOT/'build/weighted-pool-native-r1/attempt2'
sys.path.insert(0,str(H.parent/'ttl-production'));from game_syntax import unchanged,subset
sys.path.insert(0,str(H.parent/'path-embed-replay'));import sdk_witness
sys.path.insert(0,str(H.parent/'weighted-pool'));import model
DEADLINE=dt.datetime(2026,10,27,23,6,30,tzinfo=dt.timezone.utc).timestamp()
def need(b,s):
 if not b:raise AssertionError(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
 with Path(p).open('x')as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def command(name,argv,w,expected=0,stdin=b''):
 need(time.time()<DEADLINE-2,'deadline');unchanged(w);argv=list(map(str,argv));prefix=OUT/name;env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin',HOME=str(OUT/'home'),TMPDIR=str(OUT/'tmp'),LANG='C',LC_ALL='C');(OUT/(name+'.stdin')).write_bytes(stdin)
 dump(str(prefix)+'.plan.json',dict(argv=argv,cwd=str(ROOT),env=env,expected=expected,stdinSha256=hashlib.sha256(stdin).hexdigest(),admissionSha256=sha(OUT/'admission.json')));started=time.time_ns()
 with open(str(prefix)+'.stdout','xb')as so,open(str(prefix)+'.stderr','xb')as se,open(OUT/(name+'.stdin'),'rb')as si:
  p=subprocess.Popen(argv,cwd=ROOT,env=env,stdin=si,stdout=so,stderr=se,start_new_session=True);pgid=os.getpgid(p.pid);obs=subprocess.Popen(['/bin/ps','-p',str(p.pid),'-o','lstart=,pid=,pgid='],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);obso,obse=obs.communicate(timeout=5);dump(str(prefix)+'.started.json',dict(pid=p.pid,pgid=pgid,osStart=obso.decode().strip(),startedWallNs=started,observation=dict(pid=obs.pid,returncode=obs.returncode,reaped=True,stderr=obse.decode())));timed=False
  try:code=p.wait(timeout=min(90,DEADLINE-time.time()))
  except subprocess.TimeoutExpired:timed=True;os.killpg(p.pid,signal.SIGKILL);code=p.wait(timeout=5)
  try:os.killpg(p.pid,0);gone=False;os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:gone=True
 dump(str(prefix)+'.receipt.json',dict(pid=p.pid,pgid=pgid,returncode=code,reaped=True,groupGone=gone,timedOut=timed,startedWallNs=started,endedWallNs=time.time_ns(),stdoutSha256=sha(str(prefix)+'.stdout'),stderrSha256=sha(str(prefix)+'.stderr'),planSha256=sha(str(prefix)+'.plan.json')));need(gone and not timed and code==expected,'actual leaf '+name);unchanged(w);need(sum(p.stat().st_size for p in OUT.rglob('*')if p.is_file())<=64*1024**2,'64MiB cap');print(name,p.pid,code,flush=True)
def main():
 need(not OUT.exists(),'fresh output root');OUT.mkdir();(OUT/'home').mkdir();(OUT/'tmp').mkdir();ad=json.loads((BASE/'admission.json').read_bytes());r=json.loads((BASE/'recipe.json').read_bytes());need(len(r['objects'])==113 and all(v=='OFF'for k,v in r['selectors']),'exact fresh113/all27OFF');need(sha(ROOT/'source/core/StarRustWeightedPool.h')=='266fce1bf416dd11516d07326382ae00851bd3cb210c81f2c1e6ed37273b80a2','canonical ABI pin')
 # Reuse immutable compiler/header/SDK pins; catalog is NOT a consumed C++ input.
 w=ad['witness'];excluded={p:w['files'].pop(p)for p in list(w['files'])if p.endswith('/source/lab/migration/catalog.json')};
 own=[p for p in H.rglob('*')if p.is_file()];new={str(p.resolve()):sha(p)for p in own+[ROOT/'source/core/StarRustWeightedPool.h',BASE/'recipe.json',H.parent/'weighted-pool/model.py',H.parent/'weighted-pool/StarWeightedPool.original.hpp']};w['files'].update(new)
 unchanged(w)
 dump(OUT/'admission.json',dict(witness=w,basePath=str(BASE/'admission.json'),baseSha256=sha(BASE/'admission.json'),tools=ad['tools'],recipe=r,delta=new,excludedUnconsumedHistoricalMetadata=excluded,scope='native mock only; not source/Rust global freeze',deadline=DEADLINE))
 # Every possible compile input is preadmitted above. Before each leaf recheck
 # actual known source/tools/provider closure; -MD closes actual header subset.
 core={p:h for p,h in w['files'].items()if p in new or p in ad['tools'] or p in r['objects'] or p in r['libraries'] or p.endswith('/source/core/StarWeightedPool.hpp')}
 live=dict(files=core,aliases={p:v for p,v in w['aliases'].items()if p in core})
 c=r['compiler'];flags=[*r['flags'],'-I'+str(H),'-I'+str(H.parent/'weighted-pool')];mock=OUT/'mock.o'
 command('link-expand',[c,*flags,'-###',*r['objects'],H/'probe.cpp',*r['libraries'],'-o',OUT/'expand'],live);need(any(p.endswith('/ld')and p in(OUT/'link-expand.stderr').read_text()for p in ad['tools']),'preadmitted linker selected')
 def compile(name,src,on=1):
  obj=OUT/(name+'.o');dep=OUT/(name+'.d');command('compile-'+name,[c,*flags,'-DWP_BOUNDARY_ON='+str(on),'-MD','-MF',dep,'-c',src,'-o',obj],live);deps=shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]);subset(deps,w);need(not any(p.endswith('/catalog.json')for p in deps),'catalog not consumed');live['files'][str(obj)]=sha(obj);return obj
 mock=compile('mock',H/'mock.cpp')
 maps=[]
 def build(name,source,on=1):
  obj=compile(name,H/source,on);exe=OUT/name;mp=OUT/(name+'.map');command('link-'+name,[c,*flags,*r['objects'],obj,mock,*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(mp),'-Wl,-t,-trace_implicit_libraries','-o',exe],live);live['files'][str(exe)]=sha(exe);maps.append(mp);return exe
 life=build('lifecycle','lifecycle.cpp');command('lifecycle-mock',[life,'current'],live);command('lifecycle-reference',[life,'reference'],live);need((OUT/'lifecycle-mock.stdout').read_bytes()==(OUT/'lifecycle-reference.stdout').read_bytes(),'exact event trace parity')
 scalar=build('scalar','scalar.cpp');command('scalar-mock',[scalar],live)
 probe=build('probe','probe.cpp');command('probe-mock',[probe],live);command('probe-known-failure',[probe,'known-failure'],live,expected=1);need(b'isolated known failing fixture'in(OUT/'probe-known-failure.stderr').read_bytes(),'negative fixture reason')
 corpus=build('corpus','corpus.cpp');rows,expected=model.corpus();command('corpus-mock',[corpus],live,stdin=rows.encode());need((OUT/'corpus-mock.stdout').read_bytes()==expected.encode(),'27 unchanged rational rows')
 off=build('probe-off','probe.cpp',0);command('probe-off',[off],live)
 sdk=json.loads((BASE/'sdk-before.json').read_bytes());paths=[]
 for mp in maps:paths+=re.findall(r'^\[\s*\d+\] (.*\.tbd)$',mp.read_text(errors='surrogateescape'),re.M)
 requested=r['flags'][r['flags'].index('-isysroot')+1];dump(OUT/'sdk-consumed.json',sdk_witness.reconcile_consumed(sdk,paths,requested_root=requested,expected_canonical_root=requested))
 report=dict(status='NATIVE_MOCK_CONTINUATION_FINITE_PASS',roots=19,stages=4,lifecycleTraces=8,scalarProperties=5,corpusRows=27,abiSha256=sha(ROOT/'source/core/StarRustWeightedPool.h'),admissionSha256=sha(OUT/'admission.json'),limitations=['not actual Rust, production, game or universal template qualification','generic private-friend-only range lookup remains review obligation; positive public member/custom sentinel/ADL run','OFF bodies reconstructed exactly by generator; no production selector change','optimized finite-domain numerical contract only'],products={str(p):sha(p)for p in OUT.rglob('*')if p.is_file()and p.name not in ['report.json','acquire.stdout','acquire.stderr']})
 dump(OUT/'report.json',report);print('REPORT',sha(OUT/'report.json'),flush=True)
if __name__=='__main__':main()
