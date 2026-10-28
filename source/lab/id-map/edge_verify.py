#!/usr/bin/env python3
"""Pure finite edge replay; native source/model values are never updated from outputs."""
import argparse,hashlib,json,sys
from pathlib import Path
import edge_model
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'build/id-map-edges-r1'
EXPECTED={'compiler-version':0,'link-expand':0,'compile':0,'link':0,'native':0,'repeat':0,'mutant-compile':0,'mutant-link':0,'mutant':1}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def load(p):return json.loads(Path(p).read_bytes())
def semantics(outputs):
    edge_model.verify(outputs['native']);edge_model.verify(outputs['repeat'])
    prefix=edge_model.expected().split('CASE\tordered/partial-metadata-little-endian\t',1)[0]
    need(outputs['mutant']==prefix,'transactional read mutant reaches exact partial-scalar boundary')
    return dict(cases=len(edge_model.case_names),properties=len(edge_model.property_names))
def audit(pin):
    need(sha(OUT/'report.json')==pin,'external report pin');r=load(OUT/'report.json');a=load(OUT/'admission.json');need(sha(OUT/'admission.json')==r['admissionSha256'],'exact admission pin');need(r['commands']==list(EXPECTED),'exact nine-command membership')
    for p,h in r['products'].items():need(sha(p)==h,'product drift '+p)
    for p,h in a['witness']['files'].items():need(sha(p)==h,'fresh preadmitted bytes '+p)
    for p,target in a['witness']['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'alias drift')
    for name,code in EXPECTED.items():
        p=load(OUT/(name+'.plan.json'));e=load(OUT/(name+'.receipt.json'));s=load(OUT/(name+'.started.json'))
        need(p['expected_returncode']==e['returncode']==code and e['reaped']is True and e['group_gone']is True and e['timed_out']is False,'role-specific actual terminal status')
        need(type(e['pid'])is int and e['pid']>0 and e['pid']==e['pgid']==s['pid']==s['pgid'],'actual PID/group')
        need(e['plan_sha256']==sha(OUT/(name+'.plan.json'))and e['stdout_sha256']==sha(OUT/(name+'.stdout'))and e['stderr_sha256']==sha(OUT/(name+'.stderr')),'stdio/plan binding')
        need(p['admission_sha256']==sha(OUT/'admission.json'),'command admission binding')
        for path,h in p['argv_files'].items():need(sha(path)==h,'actual command file input')
    result=semantics({n:(OUT/(n+'.stdout')).read_text()for n in ['native','repeat','mutant']})
    need('partial-metadata-little-endian'in(OUT/'mutant.stderr').read_text(),'exact mutant property failure')
    need(len(r['controls'])==4 and all(r['controls'].values()),'four isolated falsifiers')
    return dict(status='FINITE_NATIVE_IDMAP_EDGES_PASS_NOT_RUST_OR_GAME',reportSha256=pin,commands=9,**result,limits=r['limits'])
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--report-sha',required=True);a=ap.parse_args()
    def guard(event,args):
        if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.exec'}:raise ValueError('read-only edge replay')
    sys.addaudithook(guard);print(json.dumps(audit(a.report_sha),indent=2,sort_keys=True))
if __name__=='__main__':main()
