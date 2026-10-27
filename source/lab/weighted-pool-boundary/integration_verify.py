#!/usr/bin/env python3
"""Subprocess-free native/mock revision replay, never an actual-Rust claim."""
import argparse,hashlib,json,re,shlex,sys
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'build/weighted-pool-boundary-integration-r1'
sys.path.insert(0,str(H.parent/'weighted-pool'));import model

def guard(event,args):
 if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.forkpty','os.exec','pty.spawn'}:raise ValueError('read-only verification')
sys.addaudithook(guard)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def need(b,s):
 if not b:raise ValueError(s)
def semantics(actual,native,corpus):
 need(actual.startswith(native+native),'eight native/reference traces AND observer lines each')
 for marker in ['private-friend-moveonly-cursor-distinct-sentinel-contextual-bool','rust-destination-sentinel-root-tags-status-normalization','pending-native-exception-no-later-mutation','missing-borrow-capability-rejected']:
  need('PASS\t'+marker+'\n'in actual,'observed native assertion '+marker)
 match=re.search(r'^PASS\tactual-frame-bounds-and-cursor-state-attacks\t([0-9]+)$',actual,re.M);need(match and int(match[1])>=12,'actual context attacks')
 need(corpus==model.corpus()[1],'frozen rational corpus');return int(match[1])
def controls(actual,native,corpus):
 rejected=[]
 for name,a,b in [('missing-access-positive',actual.replace('PASS\tprivate-friend-moveonly-cursor-distinct-sentinel-contextual-bool\n',''),corpus),('wrong-lifetime-order',actual.replace('OBS\tappend\t2\t0\t1','OBS\tappend\t2\t1\t0',1),corpus),('no-actual-capability-attacks',re.sub(r'actual-frame-bounds-and-cursor-state-attacks\t[0-9]+','actual-frame-bounds-and-cursor-state-attacks\t0',actual),corpus),('wrong-frozen-row',actual,corpus.replace('0\n','1\n',1))]:
  try:semantics(a,native,b)
  except ValueError:rejected.append(name);continue
  raise ValueError('isolated corruption accepted '+name)
 return rejected

def verify(pin):
 need(sha(O/'report.json')==pin,'explicit report pin');report=load(O/'report.json');need('original preflight remains failed'in report['status'],'failure scope')
 for p,h in report['products'].items():need(sha(p)==h,'preserved byte '+p)
 ad=load(O/'admission.json');need(sha(O/'admission.json')==report['admissionSha256'],'admission');need(sha(O/'before.json')==report['sourceVersionsSha256'],'before source version authority')
 for row in load(O/'before.json')['sources']:need(sha(row['copy'])==row['sha256']and Path(row['copy']).stat().st_size==row['size'],'exact old source retained')
 w=ad['witness'];need(len(ad['recipe']['objects'])==113 and len(ad['recipe']['selectors'])==27 and all(v=='OFF'for _,v in ad['recipe']['selectors']),'frozen current reference profile')
 for p,h in w['files'].items():need(sha(p)==h,'new actual source/tool/object input '+p)
 for p,target in w['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'new alias')
 failed=[];success=[]
 for p in O.glob('*.receipt.json'):
  name=p.name[:-len('.receipt.json')];receipt=load(p);plan=load(O/(name+'.plan.json'));started=load(O/(name+'.started.json'));need(receipt['pid']==receipt['pgid']==started['pid']==started['pgid'] and started['osStart'],'actual process identity');need(receipt['reaped']and receipt['groupGone']and not receipt['timedOut'],'terminal actual process');need(receipt['startedWallNs']==started['startedWallNs']<=receipt['endedWallNs'],'clock');need(sha(O/(name+'.plan.json'))==receipt['planSha256'],'plan binding')
  for ext in ['stdout','stderr']:need(sha(O/(name+'.'+ext))==receipt[ext+'Sha256'],'stdio binding')
  need(sha(O/(name+'.stdin'))==plan['stdinSha256'],'stdin binding')
  if name=='link-expand':need(receipt['returncode']==1 and plan['expected']==0,'original failed driver expansion');failed.append(name)
  else:need(receipt['returncode']==plan['expected'],'successful or expected negative actual leaf');success.append(name)
 need(failed==['link-expand'] and len(success)==11,'exact failed/successful leaf composition')
 for name in ['mock','combined','old-integration']:
  deps=shlex.split((O/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)[1]);need(deps,'actual -MD input closure')
  for p in deps:need(str(Path(p).resolve())in w['files'],'consumed input admitted '+p)
 actual=(O/'current.stdout').read_text();native=(R/'build/weighted-pool-lifecycle-r1/current.stdout').read_text();corpus=(O/'corpus.stdout').read_text();count=semantics(actual,native,corpus)
 for name in ['old-sentinel','old-items']:need((O/(name+'.stderr')).read_text()=='weighted boundary protocol\n','real old integration failure')
 # Reconstruct OFF source without accepting a native body change as plumbing.
 src=(H/'BoundaryWeightedPool.hpp').read_text();original=(R/'source/core/StarWeightedPool.hpp').read_text().replace('WeightedPool','BoundaryWeightedPool');off=re.sub(r'\{\n#if WP_BOUNDARY_ON\n.*?\n#else\n(.*?)\n#endif\n\}',lambda m:'{'+m[1]+'}',src,flags=re.S).replace('#include "StarSet.hpp"\n#include "frame.hpp"\n','');a=off.index('  template<unsigned Mode> struct NativeFrame');b=off.index('  ItemsList m_items;',a);off=off[:a]+off[b:];off=off.replace('private:\n  size_t selectIndex(double target) const;\n\n\n','private:\n  size_t selectIndex(double target) const;\n\n');need(off==original,'OFF body/layout unchanged');need('const_cast'not in src,'true const native storage dispatch')
 proxy=src.replace('BoundaryWeightedPool','ProxyBoundaryWeightedPool').replace('RandomSource','ProxyRandomSource').replace('Random::','ProxyRandom::').replace('staticRandomDouble','proxyStaticRandomDouble');need((H/'ProxyBoundaryWeightedPool.hpp').read_text()==proxy,'exact dependency-only proxy')
 return dict(status=report['status'],successfulLeaves=len(success),failedLeaves=failed,actualRejectedCapabilityRequests=count,isolatedFalsifiers=controls(actual,native,corpus),traceCount=8,corpusRows=27,limits=['Cpp mock ONLY, no actual-Rust/staticlib/game adoption','std::function remains allocating lab scaffolding; production allocation-free frames still required','finite valid Container positives, not universal ill-formed template diagnostic equivalence'])
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--report-sha',required=True);a=ap.parse_args();print(json.dumps(verify(a.report_sha),indent=2,sort_keys=True))
