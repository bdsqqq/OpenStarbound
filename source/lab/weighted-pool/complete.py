#!/usr/bin/env python3
"""Read-only independent native composition. Original failed producers stay failed.

The original inventory metadata is retained explicitly; this does not renew its
old live/global source guard. Event conservation is independent of trace parity.
"""
import argparse,copy,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];BASE=ROOT/'build/weighted-pool-native-r1';OLD=BASE/'attempt2';LIFE=ROOT/'build/weighted-pool-lifecycle-r1';SCALAR=ROOT/'build/weighted-pool-scalar-r1';OUT=ROOT/'build/weighted-pool-native-composition-r1'
def guard(event,args):
 if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.forkpty','os.exec','pty.spawn'}:raise ValueError('native composition cannot create processes')
sys.addaudithook(guard)
sys.path.insert(0,str(HERE));import audit as partial
PINS={str(BASE/'orthogonal/report.json'):'25f7cbae4e10559bca0464593d046299920aeb0fc6ae374211062484ab3213e3',str(LIFE/'report.json'):'489903308955b5ddd58e0c2d14d2258ead8bbf5101402ad10b0e86f83504a2eb',str(SCALAR/'report.json'):'4d7df1023a8cbf15720a1dca218cc1f89a4379209c59e8d68e5efce189bead74'}
TRACE_NAMES=['append-full-expression','same-pool-mutation','by-value-container','throw-parameter-move','throw-storage-move','throw-return-copy','clear-cross-pool-reentry','named-result-return-lifetime']
OBS=['OBS\tappend\t2\t0\t1','OBS\tmutation\t2\t2\t0','OBS\treentry\t2\t2','OBS\tresult\t2\t4']
def need(b,s):
 if not b:raise ValueError(s)
def sha(p):return partial.sha(p)
def load(p):return json.loads(Path(p).read_bytes())
def events(text):
 rows=[x.split('\t')for x in text.splitlines()if x.startswith('TRACE\t')];need([r[1]for r in rows]==TRACE_NAMES,'eight complete native traces');need([x for x in text.splitlines()if x.startswith('OBS\t')]==OBS,'full expression, mutation, reentry and result observations');need(text.splitlines()[-1]=='PASS\tevent-only-complete','successful event-only gate');counts=[]
 for row in rows:
  seq=[e.split(':')for e in row[2:]];live={};ever=set();i=0;throws=0
  while i<len(seq):
   kind,identifier,source,value=seq[i];identifier,source,value=map(int,[identifier,source,value]);need(kind in 'CKMD'and identifier>0,'event schema')
   if kind=='D':need(identifier in live and live.pop(identifier)==value,'destructor identity/value/lifetime')
   else:
    need(identifier not in ever,'object identity reused');ever.add(identifier)
    if kind=='C':need(source==0,'direct constructor source')
    else:need(source in live and live[source]==value,'copy/move live source')
    if i+1<len(seq)and seq[i+1][0]=='X':
     need(kind in 'KM'and seq[i+1][1:]==seq[i][1:],'failed construction event');throws+=1;i+=1
    else:
     live[identifier]=value
     if kind=='M':live[source]=-1
   i+=1
  need(not live,'native objects leaked');need(throws==(1 if row[1].startswith('throw-')else 0),'exact native throw stages');counts.append(dict(trace=row[1],events=len(seq),nativeThrows=throws))
 return counts

def controls():
 good=(LIFE/'current.stdout').read_text();events(good);out=[]
 cases={'wrong-phase':good.replace('OBS\tappend\t2\t0\t1','OBS\tappend\t2\t1\t0'),'cached-total':good.replace('OBS\tmutation\t2\t2\t0','OBS\tmutation\t2\t2\t1'),'missing-reentry':good.replace('OBS\treentry\t2\t2\n',''),'double-dtor':good.replace('D:2:0:-1','D:2:0:-1\tD:2:0:-1',1),'wrong-move-source':good.replace('M:2:1:10','M:2:99:10',1),'destroy-failed-object':good.replace('X:5:4:30','X:5:4:30\tD:5:0:30',1),'missing-trace':good.replace('TRACE\tappend-full-expression','OMITTED\tappend-full-expression',1),'compiled-cached-state-mutant':(LIFE/'mutant.stdout').read_text()}
 for name,bad in cases.items():
  try:events(bad)
  except (ValueError,KeyError):out.append(name);continue
  raise ValueError('known failure accepted '+name)
 return out

def replay():
 bindings={};headers=[]
 def bind(p,h=None):
  p=Path(p);actual=sha(p);need(h is None or actual==h,'physical byte binding '+str(p));bindings[str(p)]=actual
 for name,pin in PINS.items():
  bind(name,pin)
  for p,h in load(name)['products'].items():bind(p,h)
 # The partial semantic result authenticates history, not an acceptance of its
 # eight printed assertions from a process that later segfaulted/failed.
 partial.evaluate(partial.data());need(len(partial.controls())==6,'original falsifiers');need(load(BASE/'properties.receipt.json')['returncode']==-11 and load(OLD/'properties.receipt.json')['returncode']==1,'failed original producer truth')
 base=OLD/'admission.json';w=load(base)['witness'];bind(base)
 for p,h in w['files'].items():
  if p==str(ROOT/'source/lab/migration/catalog.json'):
   retained=BASE/'original-1972-catalog.json';bind(retained,h)
  else:bind(p,h)
 for p,target in w['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'original alias changed')
 header=(ROOT/'source/core/StarWeightedPool.hpp').read_text();need(header.count('WeightedPool<Item>::')==19,'whole definition inventory');need((HERE/'StarWeightedPool.original.hpp').read_text()==header.replace('WeightedPool','ReferenceWeightedPool'),'name-only reference body');proxy=header
 for a,b in [('WeightedPool','ProxyWeightedPool'),('RandomSource','ProxyRandomSource'),('Random::','ProxyRandom::'),('staticRandomDouble','proxyStaticRandomDouble')]:proxy=proxy.replace(a,b)
 need((HERE/'StarWeightedPool.proxy.hpp').read_text()==proxy,'proxy exact body transformation')
 for directory in [LIFE,SCALAR]:
  ad=load(directory/'admission.json');bind(ad['basePath'],ad['baseSha256'])
  for p,h in ad['delta'].items():bind(p,h)
  for p in directory.glob('*.receipt.json'):
   row=load(p);name=p.name[:-len('.receipt.json')];plan=load(directory/(name+'.plan.json'));start=load(directory/(name+'.started.json'));need(row['pid']==row['pgid']==start['pid']==start['pgid'] and row['reaped']is True and row['groupGone']is True and row['timedOut']is False,'normal actual native process');need(row['returncode']==plan['expected'] and row['startedWallNs']==start['startedWallNs']<=row['endedWallNs'],'status/start timing');need(start['osStart'],'OS process identity')
   bind(directory/(name+'.plan.json'),row['planSha256'])
   for ext in ['stdout','stderr']:bind(directory/(name+'.'+ext),row[ext+'Sha256'])
 need(len(list(LIFE.glob('*.receipt.json')))==6 and len(list(SCALAR.glob('*.receipt.json')))==3,'exact event/scalar leaves')
 current=(LIFE/'current.stdout').read_text();need(current==(LIFE/'reference.stdout').read_text(),'current/reference exact traces');e=events(current);need((LIFE/'mutant.stderr').read_text()=='post-callback total must be read, not cached\n','compiled semantic mutant native error')
 want='PASS\tempty-select-no-random\nPASS\tempty-index-consumes\nPASS\tunique-zero-and-empty-global-seed\nPASS\tunique-index-not-value\nPASS\tunique-seed-wrap-retry-order\n';need((SCALAR/'scalar.stdout').read_text()==want,'successful scalar-only properties')
 for p in HERE.iterdir():
  if p.is_file():bind(p)
 return dict(status='FINITE_NATIVE_WEIGHTED_POOL_BY_INDEPENDENT_COMPOSITION',definitions=19,fields=2,literalRows=27,literalStreams=2,realProperties=15,realStaticSeeds=128,sourceDraws=64,scalarProxyProperties=5,eventTraces=e,controls=controls(),originalProducersRemainFailed=True,failedProcessPrintedAssertionsNotAcceptance=True,bindings=bindings,limits=['native only, no Rust/game/adoption/all39','original optimization flags retained; nonfinite/subnormal/overflow diagnostic only, not IEEE expectations','named-result NRVO eligibility source-traced; native Item/caller lifetimes measured, no claim of observable List elision constructor counts','original source/ctime/global-origin guard historical for explicitly retained inventory metadata','finite cases, not arbitrary allocator/OOM/concurrency/exception universality'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--compose',action='store_true');p.add_argument('--report-sha');a=p.parse_args();result=replay()
 if a.compose:
  need(not OUT.exists(),'fresh composition');OUT.mkdir();(OUT/'report.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 else:need(a.report_sha and sha(OUT/'report.json')==a.report_sha and load(OUT/'report.json')==result,'immutable composition report')
 print(json.dumps({k:v for k,v in result.items()if k!='bindings'},indent=2,sort_keys=True));print('REPORT',sha(OUT/'report.json'))
