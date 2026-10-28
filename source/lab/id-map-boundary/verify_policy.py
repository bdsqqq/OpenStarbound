#!/usr/bin/env python3
"""Pure replay of C ABI syntax and existing-aggregate mock-policy tests only."""
import argparse,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'build/id-map-abi-r1'
EXPECTED=['c11','cpp17','debug','release']
def need(ok,why):
    if not ok:raise ValueError(why)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def audit(pin):
    need(sha(OUT/'report.json')==pin,'external policy report pin');r=load(OUT/'report.json');need(r['commands']==EXPECTED,'exact four-command membership');a=load(OUT/'admission.json');need(sha(OUT/'admission.json')==r['admissionSha256'],'admission pin')
    for path,h in r['products'].items():need(sha(path)==h,'product bytes '+path)
    for path,h in a['files'].items():need(sha(path)==h,'preadmitted source/tool/resource '+path)
    for name in EXPECTED:
        p=load(OUT/(name+'.plan.json'));e=load(OUT/(name+'.receipt.json'));s=load(OUT/(name+'.started.json'))
        need(e['returncode']==0 and e['reaped']is True and e['groupGone']is True and e['timedOut']is False,'successful owned command')
        need(type(e['pid'])is int and e['pid']>0 and e['pid']==s['pid']==s['pgid'],'actual PID/group')
        need(e['planSha256']==sha(OUT/(name+'.plan.json'))and e['stdoutSha256']==sha(OUT/(name+'.stdout'))and e['stderrSha256']==sha(OUT/(name+'.stderr')),'receipt stdio/plan hashes')
        need(p['admissionSha256']==r['admissionSha256'],'command admission')
        tool=str(Path(p['argv'][0]).resolve(strict=True));need(tool in a['files']and sha(tool)==a['files'][tool],'selected actual executable')
        if name in ('debug','release'):
            text=(OUT/(name+'.stdout')).read_text();need('running 201 tests'in text and '201 passed; 0 failed; 0 ignored'in text,'actual aggregate unit result')
            tests=re.findall(r'^test (id_map::tests::\S+) \.\.\. ok$',text,re.M);need(len(tests)==len(set(tests))==29,'29 unique idmap mock tests')
    return dict(status='C11_CPP17_AND_RUST_POLICY_MOCK_REPLAY_PASS',reportSha256=pin,aggregateTestsPerProfile=201,idMapTestsPerProfile=29,commands=EXPECTED,limits=r['limits'])
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--report-sha',required=True);a=ap.parse_args()
    def guard(event,args):
        if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.exec'}:raise ValueError('read-only policy verifier')
    sys.addaudithook(guard);print(json.dumps(audit(a.report_sha),indent=2,sort_keys=True))
if __name__=='__main__':main()
