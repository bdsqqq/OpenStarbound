#!/usr/bin/env python3
"""Read-only pinned current-revision replay; no subprocess or regeneration."""
import argparse,hashlib,json,re,shlex,sys
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;ROOT=H.parents[2];OUT=ROOT/'build/weighted-pool-boundary-mock-r1'
sys.path.insert(0,str(H.parent/'weighted-pool'));import model

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(b,s):
 if not b:raise AssertionError(s)
def load(p):return json.loads(Path(p).read_bytes())
def traces(data):return [x for x in data.splitlines()if x.startswith(b'TRACE\t')]
def same_trace(actual,expected):need(traces(actual)==traces(expected),'exact fixed-event traces')
def verify(pin):
 report=OUT/'hardening-report.json';need(sha(report)==pin,'explicit report SHA');r=load(report);ha=load(OUT/'hardening-admission.json');ad=load(OUT/'admission.json');need(sha(OUT/'hardening-admission.json')==r['admissionSha256'],'preadmission seal');need(ha['baseSha256']==sha(OUT/'admission.json'),'base admission seal');need(ha['previousReportSha256']==sha(OUT/'independent-report.json'),'previous finite report retained')
 for p,h in r['products'].items():need(sha(p)==h,'artifact drift '+p)
 need(sha(ROOT/'source/core/StarRustWeightedPool.h')=='266fce1bf416dd11516d07326382ae00851bd3cb210c81f2c1e6ed37273b80a2','canonical ABI unchanged')
 old=ha['sourceVersion'];need(sha(old['retained'])==old['oldSha256']==ad['delta'][old['canonical']],'exact old source retained, not rebound')
 current=dict(ad['witness']['files']);current.update(ha['delta'])
 for p,h in ad['delta'].items():
  if p!=old['canonical']:need(sha(p)==h,'unchanged compiled fixture '+p)
 for p,h in ha['delta'].items():need(sha(p)==h,'current source '+p)
 recipe=ad['recipe'];need(len(recipe['objects'])==113 and len(recipe['selectors'])==27 and all(v=='OFF'for k,v in recipe['selectors']),'exact113/all27OFF')
 for p in [*recipe['objects'],*[p for p in recipe['libraries']if p.startswith('/')],*ad['tools']]:need(sha(p)==current[str(Path(p).resolve())],'tool/provider bytes '+p)
 for name in ['compile-combined','link-combined','combined-current','combined-corpus']:
  p=load(OUT/(name+'.plan.json'));rc=load(OUT/(name+'.receipt.json'));s=load(OUT/(name+'.started.json'));need(p['admissionSha256']==sha(OUT/'admission.json'),'base leaf admission');need(rc['planSha256']==sha(OUT/(name+'.plan.json')),'command pin');need(rc['pid']==s['pid']and rc['pgid']==s['pgid']==s['pid']and s['osStart'],'actual OS identity');need(rc['returncode']==p['expected']==0 and rc['reaped']and rc['groupGone']and not rc['timedOut'],'normal terminal leaf');need(s['observation']['reaped']and s['observation']['returncode']==0,'OS-start observation terminal')
  for ext in ['stdout','stderr']:need(rc[ext+'Sha256']==sha(OUT/(name+'.'+ext)),'stdio pin')
  need(p['stdinSha256']==sha(OUT/(name+'.stdin')),'stdin pin')
 argv=load(OUT/'compile-combined.plan.json')['argv'];need('-DWP_BOUNDARY_ON=1'in argv and '-O3'in argv and '-ffast-math'in argv and not any(x.startswith('-DSTAR_USE_RUST_')for x in argv),'actual current original profile')
 deps=shlex.split((OUT/'combined.d').read_text().replace('\\\n',' ').split(':',1)[1]);need(deps,'actual current -MD closure')
 for p in deps:
  p=str(Path(p).resolve());need(p in current and sha(p)==current[p],'current consumed input '+p)
 argv=load(OUT/'link-combined.plan.json')['argv'];need([p for p in argv if p in recipe['objects']]==recipe['objects'],'exact immutable object order');need(str(OUT/'mock.o')in argv and sha(OUT/'mock.o')==r['products'][str(OUT/'mock.o')],'mock provider')
 output=(OUT/'combined-current.stdout').read_bytes();native=(ROOT/'build/weighted-pool-lifecycle-r1/current.stdout').read_bytes();expected=traces(native);need(len(expected)==8,'accepted native eight traces');observed=traces(output);need(observed==expected+expected,'current mock/native reference exact lifecycle parity');need(output.startswith(native+native),'complete observer lines and events, not just summaries')
 for marker in [b'19-malformed-controls-native-pointer-exception',b'19-root-4-stage-real-reference-layout-lazy-custom-containers',b'missing-borrow-capability-rejected']:need(b'PASS\t'+marker+b'\n'in output,'current executed assertion '+repr(marker))
 scalar=(OUT/'scalar-mock.stdout').read_bytes();need(scalar in output and scalar.count(b'PASS\t')==5,'current unchanged five scalar properties');rows,want=model.corpus();need((OUT/'combined-corpus.stdin').read_bytes()==rows.encode()and(OUT/'combined-corpus.stdout').read_bytes()==want.encode(),'current27 unchanged rational rows')
 # Known isolated corruption uses the same trace validator as the positive case.
 same_trace(native,native)
 try:same_trace(b'\n'.join(native.splitlines()[:-2])+b'\n',native)
 except AssertionError:pass
 else:raise AssertionError('missing trace negative fixture accepted')
 # OFF body reconstruction is source-derived and independent of executable output.
 src=(H/'BoundaryWeightedPool.hpp').read_text();original=(ROOT/'source/core/StarWeightedPool.hpp').read_text().replace('WeightedPool','BoundaryWeightedPool');off=re.sub(r'\{\n#if WP_BOUNDARY_ON\n.*?\n#else\n(.*?)\n#endif\n\}',lambda m:'{'+m[1]+'}',src,flags=re.S).replace('#include "StarSet.hpp"\n#include "frame.hpp"\n','');a=off.index('  template<unsigned Mode> struct NativeFrame');b=off.index('  ItemsList m_items;',a);off=off[:a]+off[b:];off=off.replace('private:\n  size_t selectIndex(double target) const;\n\n\n','private:\n  size_t selectIndex(double target) const;\n\n');need(off==original,'exact original OFF definitions and two fields after declared plumbing')
 need(sum(p.stat().st_size for p in OUT.rglob('*')if p.is_file())<=64*1024**2,'fixed64MiB root cap')
 print('PASS current native mock:19roots/4stages/8traces/27rows; missing-trace control rejected; actual Rust/production/game NOT qualified')
def main():
 p=argparse.ArgumentParser();p.add_argument('--report-sha',required=True);a=p.parse_args();verify(a.report_sha)
if __name__=='__main__':main()
