#!/usr/bin/env python3
"""Read-only finite C++-mock frame evidence replay, including retained failures."""
import argparse,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'build/id-map-boundary-r1'
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'id-map'));import model,edge_model
PRE=['compiler-version','mock-compile','native-r2-compile','native-r2-expand','native-r2-link','native-r2','native-r2-repeat','edges-compile','edges-expand','edges-link','edges','edges-repeat','trace-reference-compile','trace-reference-expand','trace-reference-link','trace-reference','trace-reference-repeat','trace-candidate-compile','trace-candidate-expand','trace-candidate-link']
NEW=['probe-compile','probe-expand','probe-link','probe','probe-repeat','lazy-negative','hash-move-only-negative','typed-auto-negative']
FAILED=['native-compile','trace-candidate']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(b,s):
    if not b:raise ValueError(s)
def load(p):return json.loads(Path(p).read_bytes())
def membership(r):
    need(r['acceptedPredecessorCommands']==PRE and r['commands']==NEW and r['retainedFailedCommands']==FAILED,'exact accepted/failed role membership')
def audit(pin):
    need(sha(OUT/'report.json')==pin,'external frame report pin');r=load(OUT/'report.json');membership(r)
    for p,h in r['products'].items():need(sha(p)==h,'product '+p)
    epoch=load(OUT/'before-repair/manifest.json');need(sha(epoch['copy'])==epoch['sha256'],'original failed source epoch')
    for name in ['admission.json','admission-r2.json','admission-probe.json']:
        a=load(OUT/name)
        for p,h in a['witness']['files'].items():
            q=epoch['copy']if name=='admission.json'and p==epoch['original']else p
            need(sha(q)==h,'exact admitted source/tool bytes '+p)
        for p,target in a['witness']['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'alias integrity')
    need(sha(OUT/'admission-probe.json')==r['admissionSha256'],'current scoped admission pin')
    for name in PRE+NEW+FAILED:
        e=load(OUT/(name+'.receipt.json'));p=load(OUT/(name+'.plan.json'));s=load(OUT/(name+'.started.json'));code=1 if name in FAILED or name.endswith('-negative')else 0
        need(e['returncode']==code and e['reaped']is True and e['group_gone']is True and e['timed_out']is False,'actual terminal role '+name)
        need(e['pid']>0 and e['pid']==e['pgid']==s['pid']==s['pgid'],'PID/group')
        need(e['plan_sha256']==sha(OUT/(name+'.plan.json'))and e['stdout_sha256']==sha(OUT/(name+'.stdout'))and e['stderr_sha256']==sha(OUT/(name+'.stderr')),'stdio/plan binding')
        need(p['admission_sha256']in{sha(OUT/n)for n in ['admission.json','admission-r2.json','admission-probe.json']},'bound admission epoch')
        for path,h in p['argv_files'].items():need(sha(path)==h,'actual command file bytes')
    for name,reader in [('native-r2',model.verify),('edges',edge_model.verify)]:
        text=(OUT/(name+'.stdout')).read_text();reader(text);need(text==(OUT/(name+'-repeat.stdout')).read_text(),'actual native repeat')
    trace=lambda text:[x for x in text.splitlines()if x.startswith('TRACE\t')]
    need(trace((OUT/'trace-reference.stdout').read_text())==r['typedTraces']==trace((OUT/'trace-candidate.stdout').read_text())and len(r['typedTraces'])==5,'five prefix-only typed traces')
    need('actual frame denied-op/pending barrier/root coverage'in(OUT/'trace-candidate.stderr').read_text(),'retained threshold failure truth')
    text=(OUT/'probe.stdout').read_text();need(text==(OUT/'probe-repeat.stdout').read_text(),'isolated probe repeat');m=re.search(r'^OBSERVATION\tdenials=(\d+) expected=(\d+) barriers=(\d+) expectedBarriers=(\d+) roots=(\d+) failed=(\d+)$',text,re.M);need(m is not None,'structural observation');v=list(map(int,m.groups()));need(v[0]==v[1]and v[2]==v[3]==44 and v[4]==1023 and v[5]==0,'per-request conservation/all ten roots')
    need([x for x in text.splitlines()if x.startswith('CONTROL\t')]==r['controls']and len(r['controls'])==6,'six isolated protocol controls')
    return dict(status='FINITE_NATIVE_IDMAP_CPP_MOCK_REPLAY_PASS',reportSha256=pin,acceptedCommands=len(PRE+NEW),retainedFailures=FAILED,deniedActualFrameRequests=v[0],pendingBarrierRequests=v[2],limits=r['limits'])
def main():
    p=argparse.ArgumentParser();p.add_argument('--report-sha',required=True);a=p.parse_args()
    def guard(event,args):
        if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.exec'}:raise ValueError('read-only frame verifier')
    sys.addaudithook(guard);print(json.dumps(audit(a.report_sha),indent=2,sort_keys=True))
if __name__=='__main__':main()
