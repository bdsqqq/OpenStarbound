#!/usr/bin/env python3
"""Pure replay of the finite native IdMap acquisition; never launches native code."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import model
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'build/id-map-native-r1'

def need(ok,why):
    if not ok:raise ValueError(why)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_bytes())
def semantics(outputs):
    model.verify(outputs['native']);model.verify(outputs['repeat'])
    prefix=model.expected().split('CASE\tordered/fill-last-slot\t',1)[0]
    need(outputs['mutant']==prefix,'fullness mutant must reach exactly the last-slot boundary')
    return dict(literalCases=len(model.case_names),properties=len(model.property_names),backends=list(model.BACKENDS))

def audit(pin):
    need(sha(OUT/'report.json')==pin,'external report pin')
    report=load(OUT/'report.json');admission=load(OUT/report['admissionFile'])
    for p,h in report['products'].items():need(sha(p)==h,'product byte drift '+p)
    need(sha(OUT/report['admissionFile'])==report['admissionSha256'],'admission pin')
    for p,h in admission['witness']['files'].items():need(sha(p)==h,'preadmitted input drift '+p)
    for p,target in admission['witness']['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'alias drift')
    for name in report['commands']:
        prefix=OUT/name;p=load(str(prefix)+'.plan.json');r=load(str(prefix)+'.receipt.json');s=load(str(prefix)+'.started.json')
        need(r['pid']==s['pid']==s['pgid'] and r['reaped'] and r['group_gone'] and not r['timed_out'] and r['returncode']==p['expected_returncode'],'actual command terminal '+name)
        for path,h in p['argv_files'].items():need(sha(path)==h,'actual command file argument drift '+path)
        need(r['plan_sha256']==sha(str(prefix)+'.plan.json') and r['stdout_sha256']==sha(str(prefix)+'.stdout') and r['stderr_sha256']==sha(str(prefix)+'.stderr'),'receipt byte binding '+name)
    need(len(report['commands'])==report['acceptedCommandCount'] and len(set(report['commands']))==len(report['commands']),'unique terminal commands')
    result=semantics({n:(OUT/(n+'.stdout')).read_text()for n in ['native','repeat','mutant']})
    need((OUT/'mutant.stderr').read_text()=='FAIL\t(IdMapException) No id space left in IdMapWrapper\n','exact early-full mutant error')
    need('deleted' in (OUT/'lazy-negative.stderr').read_text(),'native lazy-copy constraint diagnosed')
    need('deleted' in (OUT/'hash-move-only-negative.stderr').read_text(),'native hash-base copy constraint diagnosed')
    need(all(report['controls'].values()) and len(report['controls'])==4,'four isolated falsifiers')
    return dict(status='FINITE_NATIVE_IDMAP_REPLAY_PASS_NOT_RUST_OR_GAME',reportSha256=pin,**result,commands=len(report['commands']),limits=report['limits'])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--report-sha',required=True);a=ap.parse_args()
    def guard(event,args):
        if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.exec'}:raise ValueError('read-only verifier forbids process creation')
    sys.addaudithook(guard)
    print(json.dumps(audit(a.report_sha),indent=2,sort_keys=True))
if __name__=='__main__':main()
