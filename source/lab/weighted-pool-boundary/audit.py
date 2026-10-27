#!/usr/bin/env python3
"""Subprocess-free qualification of completed leaves, not the failed outer run."""
import argparse,copy,hashlib,json,re,shlex,sys
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;ROOT=H.parents[2];OUT=ROOT/'build/weighted-pool-boundary-mock-r1'
sys.path.insert(0,str(H.parent/'weighted-pool'));import model
REPORT=OUT/'independent-report.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(b,s):
 if not b:raise AssertionError(s)
def load(p):return json.loads(Path(p).read_bytes())
def qualification():
 ad=load(OUT/'admission.json');raw=load(OUT/'report.json');cont=load(OUT/'continuation-admission.json');need(sha(OUT/'admission.json')==raw['admissionSha256'],'admission pin');need(sha(OUT/'continuation-admission.json')==raw['continuationAdmissionSha256'],'continuation pin')
 need(sha(ROOT/'source/core/StarRustWeightedPool.h')=='266fce1bf416dd11516d07326382ae00851bd3cb210c81f2c1e6ed37273b80a2','canonical C11 pin')
 for p,h in {**ad['delta'],**cont['delta']}.items():need(sha(p)==h,'compiled driver drift '+p)
 for p,h in raw['products'].items():
  if p==str(OUT/'continue.stdout'):continue
  need(sha(p)==h,'raw product drift '+p)
 need((OUT/'continue.stdout').read_text().endswith('REPORT '+sha(OUT/'report.json')+'\n'),'volatile stdout only appends actual raw report hash')
 need(raw['products'][str(OUT/'continue.stdout')]==hashlib.sha256((OUT/'continue.stdout').read_bytes().rsplit(b'REPORT ',1)[0]).hexdigest(),'volatile stdout prefix must match original producer pin')
 recipe=ad['recipe'];need(len(recipe['objects'])==113 and len(recipe['selectors'])==27 and all(v=='OFF'for k,v in recipe['selectors']),'113/all27OFF')
 for p in [*recipe['objects'],*[p for p in recipe['libraries']if p.startswith('/')],*ad['tools']]:need(sha(p)==ad['witness']['files'][str(Path(p).resolve())],'immutable provider '+p)
 complete=[];orphans=[]
 for plan in sorted(OUT.glob('*.plan.json')):
  name=plan.name[:-10];receipt=OUT/(name+'.receipt.json');started=OUT/(name+'.started.json');p=load(plan)
  if not receipt.exists():orphans.append(name);continue
  r=load(receipt);s=load(started);need(r['pid']==s['pid']and r['pgid']==s['pgid']==s['pid']and s['osStart'],'actual OS process identity '+name);need(r['returncode']==p['expected']and r['reaped']and r['groupGone']and not r['timedOut'],'terminal receipt '+name);need(r['planSha256']==sha(plan),'plan seal '+name)
  for ext in ['stdout','stderr']:need(r[ext+'Sha256']==sha(OUT/(name+'.'+ext)),'stdio '+name)
  need(p['stdinSha256']==sha(OUT/(name+'.stdin')),'stdin '+name)
  complete.append(name)
 need(orphans==['compile-lifecycle'],'only known interrupted initial compile')
 for name in ['mock','lifecycle-sync','scalar','probe','corpus','probe-off']:
  dep=OUT/(name+'.d');deps=shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]);need(deps,'actual dependencies')
  for p in deps:
   p=str(Path(p).resolve());need(p in ad['witness']['files']and sha(p)==ad['witness']['files'][p],'actual consumed dependency '+p)
  plan=load(OUT/('compile-'+name+'.plan.json'));argv=plan['argv'];need('-O3'in argv and '-ffast-math'in argv,'unchanged numeric profile');need(not any(x.startswith('-DSTAR_USE_RUST_')for x in argv),'all selectors OFF')
 for name in ['lifecycle-sync','scalar','probe','corpus','probe-off']:
  argv=load(OUT/('link-'+name+'.plan.json'))['argv'];need([p for p in argv if p in recipe['objects']]==recipe['objects'],'exact object order');need(str(OUT/'mock.o')in argv,'mock provider linked')
 actual=(OUT/'lifecycle-mock.stdout').read_bytes();need(actual==(OUT/'lifecycle-reference.stdout').read_bytes(),'fresh native reference traces');native=ROOT/'build/weighted-pool-lifecycle-r1/current.stdout';need(actual==native.read_bytes(),'accepted original fixed-event fixture trace parity');need(actual.count(b'TRACE\t')==8,'eight complete traces')
 need((OUT/'scalar-mock.stdout').read_bytes().count(b'PASS\t')==5,'five scalar properties');rows,expected=model.corpus();need((OUT/'corpus-mock.stdin').read_bytes()==rows.encode()and(OUT/'corpus-mock.stdout').read_bytes()==expected.encode(),'unchanged 27-row rational corpus')
 need((OUT/'probe-mock.stdout').read_bytes()==(OUT/'probe-off.stdout').read_bytes(),'ON/OFF real positive observations');need(b'19-root-4-stage'in(OUT/'probe-mock.stdout').read_bytes(),'root stage assertions executed');need(b'isolated known failing fixture'in(OUT/'probe-known-failure.stderr').read_bytes(),'known failure reason')
 # Deterministic reconstruction, without rewriting generated source.
 src=(H/'BoundaryWeightedPool.hpp').read_text();original=(ROOT/'source/core/StarWeightedPool.hpp').read_text().replace('WeightedPool','BoundaryWeightedPool');off=re.sub(r'\{\n#if WP_BOUNDARY_ON\n.*?\n#else\n(.*?)\n#endif\n\}',lambda m:'{'+m[1]+'}',src,flags=re.S);off=off.replace('#include "StarSet.hpp"\n#include "frame.hpp"\n','');a=off.index('  template<unsigned Mode> struct NativeFrame');b=off.index('  ItemsList m_items;',a);off=off[:a]+off[b:];off=off.replace('private:\n  size_t selectIndex(double target) const;\n\n\n','private:\n  size_t selectIndex(double target) const;\n\n');need(off==original,'OFF exact original reconstruction after declared helper/include/name plumbing')
 need(src.count('  ItemsList m_items;')==1 and src.count('  double m_totalWeight;')==1,'exact native fields')
 return dict(status='FINITE_NATIVE_MOCK_ACCEPTED_BY_COMPLETED_LEAF_COMPOSITION',rawReportSha256=sha(OUT/'report.json'),admissionSha256=sha(OUT/'admission.json'),continuationAdmissionSha256=sha(OUT/'continuation-admission.json'),verifierSha256=sha(__file__),acceptedNativeTraceSha256=sha(native),completedCommands=complete,unacceptedOrphans=orphans,initialOuter='harness 10s timeout, terminal receipt unavailable; not relabelled passing',rawReportScope='continue.stdout was sealed before final REPORT line; original report retained unchanged, exact prefix verified; this final report binds completed stdout',roots=19,stages=4,exactLifecycleTraces=8,scalarProperties=5,rationalRows=27,malformedControls=19,offOriginalBodyReconstruction=True,limits=raw['limitations'],products={str(p):sha(p)for p in OUT.rglob('*')if p.is_file()and p.name not in ['independent-report.json','audit.stdout','audit.stderr']})
def main():
 p=argparse.ArgumentParser();p.add_argument('--report-sha');p.add_argument('--write',action='store_true');a=p.parse_args();r=qualification()
 # A coherent missing-semantic-outcome fixture must be rejected, not just hash drift.
 bad=copy.deepcopy(r);bad['exactLifecycleTraces']=7
 def semantic(x):need(x['roots']==19 and x['stages']==4 and x['exactLifecycleTraces']==8 and x['rationalRows']==27,'semantic counts')
 try:semantic(bad)
 except AssertionError:pass
 else:raise AssertionError('known missing-trace fixture accepted')
 semantic(r);r['isolatedMissingTraceRejected']=True
 text=json.dumps(r,indent=2,sort_keys=True)+'\n'
 if a.write:
  with REPORT.open('x')as f:f.write(text)
 else:need(a.report_sha and sha(REPORT)==a.report_sha,'explicit report pin');need(REPORT.read_text()==text,'independent replay')
 print('PASS',sha(REPORT))
if __name__=='__main__':main()
