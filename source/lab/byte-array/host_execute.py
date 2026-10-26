#!/usr/bin/env python3
"""Execute only independently sealed native host artifacts; no compiler path."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import contract
import callback_contract
import audit
import stage
import host_stage as shared
import host_seal

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ROUTES=(('lab','lab'),('callback','callback'),('repeat','lab'),('protocol','protocol'),('growth','growth'),('signed','signed'))


def need(ok,message):
    if not ok:raise ValueError(message)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check(name,stdout,stderr):
    if name=='protocol':
        need(stdout==b'BYTE_ARRAY_NATIVE_PROTOCOL_PASS\n' and stderr==b'','assertion-active native protocol')
        return None
    if name in ('growth','signed'):
        rows=[audit.parse(line) for line in stdout.splitlines()]
        need(contract.strict_equal(rows,audit.wrong_rows('growth-control' if name=='growth' else 'signed-control')),'exact wrong native controller')
        try:contract.check(stdout)
        except ValueError:pass
        else:raise ValueError('normal semantic control accepted')
    else:(callback_contract if name=='callback' else contract).check(stdout)
    return shared.counters(stderr)


def execute(seal_path,output):
    seal_path=Path(seal_path).resolve();sealed=host_seal.verify(seal_path)
    build=Path(sealed['build']).resolve();root=build.parent
    out=stage.fresh(output,'host-run-');commands=[];routes=[]
    # Seal verification precedes every process and follows the completed run.
    for name,binary in ROUTES:
        host_seal.verify(seal_path)
        commands.append(shared.command([root/binary],name,out))
        values=check(name,(out/(name+'.stdout')).read_bytes(),(out/(name+'.stderr')).read_bytes())
        if name in ('lab','callback','repeat'):routes.append(values)
    totals=[[sum(row[m][e] for row in routes) for e in range(3)] for m in range(56)]
    need(all(row[0]>0 for row in totals),'every actual compiled/header mode exercised')
    need(all(a==s+p for a,s,p in totals),'56x3 attempts match success/native-pending')
    host_seal.verify(seal_path)
    shared.dump(out/'commands.json',commands)
    report=dict(status='FINITE_NATIVE_BYTEARRAY_HOST_PASS',seal=str(seal_path),seal_sha256=sha(seal_path),
                build=str(build),commands=commands,routes=totals,correct_cases=987,callback_cases=14,normal_controls=2,
                verifier_files={str(HERE/n):sha(HERE/n) for n in ('host_execute.py','host_seal.py','contract.py','callback_contract.py','host_stage.py')},
                artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()})
    shared.dump(out/'report.json',report);verify(out/'report.json')
    print(report['status'],out/'report.json',flush=True)


def verify(path):
    path=Path(path).resolve();r=stage.load(path);root=path.parent
    need(r['status']=='FINITE_NATIVE_BYTEARRAY_HOST_PASS','native host phase')
    need(type(r['correct_cases']) is int and r['correct_cases']==987 and type(r['callback_cases']) is int and r['callback_cases']==14,'frozen source corpora')
    need(type(r['normal_controls']) is int and r['normal_controls']==2,'normal controller scope')
    need(sha(r['seal'])==r['seal_sha256'],'independent seal identity')
    sealed=host_seal.verify(r['seal']);need(sealed['build']==r['build'],'sealed build association')
    build=Path(r['build']).parent
    for p,h in r['verifier_files'].items():need(sha(p)==h,'execution verifier source drift')
    need(set(r['verifier_files'])=={str(HERE/n) for n in ('host_execute.py','host_seal.py','contract.py','callback_contract.py','host_stage.py')},'mandatory execution verifier sources')
    need(r['commands']==stage.load(root/'commands.json') and [q['name'] for q in r['commands']]==[n for n,_ in ROUTES],'six execution route copies')
    need(set(r['artifacts'])=={str(root/(n+e)) for n,_ in ROUTES for e in ('.stdout','.stderr','.command.json')}|{str(root/'commands.json')},'complete execution artifact inventory')
    for p,h in r['artifacts'].items():need(sha(p)==h,'actual execution artifact drift')
    totals=[[0,0,0] for _ in range(56)]
    for q,(name,binary) in zip(r['commands'],ROUTES):
        exe=str(build/binary)
        need(q==stage.load(root/(name+'.command.json')) and q['command']==[exe] and q['executable']==exe,'actual source-route image')
        need(type(q['returncode']) is int and q['returncode']==0 and sha(exe)==q['before']==q['after'],'normal execution binary identity')
        for ext in ('stdout','stderr'):need(sha(root/(name+'.'+ext))==q[ext],'actual execution streams')
        values=check(name,(root/(name+'.stdout')).read_bytes(),(root/(name+'.stderr')).read_bytes())
        if name in ('lab','callback','repeat'):
            for m in range(56):
                for e in range(3):totals[m][e]+=values[m][e]
    need(contract.strict_equal(totals,r['routes']) and all(a>0 and a==s+p for a,s,p in totals),'independently replayed 56 routes')
    return dict(status=r['status'],modes=56,cases=987,callback_cases=14,normal_controls=2)


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='phase',required=True)
    a=s.add_parser('run');a.add_argument('--seal',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('verify');a.add_argument('--report',required=True);args=p.parse_args()
    if args.phase=='run':execute(args.seal,args.output)
    else:print(json.dumps(verify(args.report)))
