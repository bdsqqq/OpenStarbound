#!/usr/bin/env python3
"""Finite actual production native/Rust comparison, gated by independent seals."""
import argparse
from pathlib import Path
import json
import hashlib
import stage
import contract
import callback_contract
import host_stage as shared
import rust_seal

ROOT=Path(__file__).resolve().parents[3]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check(data,err,backend,name):
    if name=='protocol':
        stage.need(data==b'BYTE_ARRAY_NATIVE_PROTOCOL_PASS\n' and err==b'','actual native-context Rust protocol')
        return None
    (callback_contract if name=='callback' else contract).check(data)
    rows=shared.counters(err)
    if backend=='native':stage.need(all(r==[0,0,0] for r in rows),'actual native-OFF does not execute Rust')
    return rows


def run(native,rust,output):
    seals={b:Path(p).resolve() for b,p in [('native',native),('rust',rust)]}
    validated={b:rust_seal.verify(p) for b,p in seals.items()}
    stage.need(all(validated[b]['backend']==b for b in seals),'native/Rust seal identities')
    out=Path(output).resolve();stage.need(out.parent==ROOT/'build/byte-array-rust' and not out.exists(),'fresh comparison output')
    out.mkdir();commands=[];totals=[[0,0,0] for _ in range(56)]
    for backend in ('native','rust'):
        rust_seal.verify(seals[backend]);root=Path(validated[backend]['build']).parent
        names=['lab','repeat','callback']+(['protocol'] if backend=='rust' else [])
        for name in names:
            label=backend+'-'+name;exe='lab' if name=='repeat' else name
            commands.append(shared.command([root/exe],label,out))
            rows=check((out/(label+'.stdout')).read_bytes(),(out/(label+'.stderr')).read_bytes(),backend,name)
            if backend=='rust' and rows is not None:
                for m in range(56):
                    for e in range(3):totals[m][e]+=rows[m][e]
    # The normal native bypass has identical values, but cannot qualify a Rust
    # route: this gate is independent of whether any individual mode can throw.
    native_rows=shared.counters((out/'native-lab.stderr').read_bytes())
    stage.need(not all(r[0]>0 for r in native_rows),'normally exiting native bypass rejected')
    stage.need(all(a>0 and a==s+p for a,s,p in totals),'all56 actual Rust routes positive and balanced')
    for p in seals.values():rust_seal.verify(p)
    shared.dump(out/'commands.json',commands)
    r=dict(status='FINITE_RUST_BYTEARRAY_CONTROLLER_PASS',seals={b:str(p) for b,p in seals.items()},
           seal_hashes={b:sha(p) for b,p in seals.items()},commands=commands,routes=totals,
           cases=987,callback_cases=14,native_bypass_rejected=True,
           artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()})
    shared.dump(out/'report.json',r);verify(out/'report.json');print(r['status'],out/'report.json',flush=True)


def verify(path):
    path=Path(path).resolve();root=path.parent;r=stage.load(path)
    stage.need(r['status']=='FINITE_RUST_BYTEARRAY_CONTROLLER_PASS' and type(r['cases']) is int and r['cases']==987
               and type(r['callback_cases']) is int and r['callback_cases']==14 and r['native_bypass_rejected'] is True,'finite controller scope')
    sealed={b:rust_seal.verify(p) for b,p in r['seals'].items()}
    stage.need(set(sealed)=={'native','rust'},'both actual backends')
    for b,p in r['seals'].items():stage.need(sha(p)==r['seal_hashes'][b] and sealed[b]['backend']==b,'seal identity')
    expected=[(b,n) for b in ('native','rust') for n in (['lab','repeat','callback']+(['protocol'] if b=='rust' else []))]
    stage.need([q['name'] for q in r['commands']]==[b+'-'+n for b,n in expected] and r['commands']==stage.load(root/'commands.json'),'seven actual process receipts')
    stage.need(set(r['artifacts'])=={str(root/(b+'-'+n+ext)) for b,n in expected for ext in ('.stdout','.stderr','.command.json')}|{str(root/'commands.json')},'all execution artifacts')
    for p,h in r['artifacts'].items():stage.need(sha(p)==h,'execution artifact drift')
    totals=[[0,0,0] for _ in range(56)]
    for q,(b,n) in zip(r['commands'],expected):
        label=b+'-'+n;exe=str(Path(sealed[b]['build']).parent/('lab' if n=='repeat' else n))
        stage.need(q==stage.load(root/(label+'.command.json')) and q['command']==[exe] and q['executable']==exe
                   and type(q['returncode']) is int and q['returncode']==0 and sha(exe)==q['before']==q['after'],'normal actual image')
        for ext in ('stdout','stderr'):stage.need(sha(root/(label+'.'+ext))==q[ext],'actual process streams')
        rows=check((root/(label+'.stdout')).read_bytes(),(root/(label+'.stderr')).read_bytes(),b,n)
        if b=='rust' and rows is not None:
            for m in range(56):
                for e in range(3):totals[m][e]+=rows[m][e]
    stage.need(contract.strict_equal(totals,r['routes']) and all(a>0 and a==s+p for a,s,p in totals),'independent actual56route replay')
    return dict(status=r['status'],modes=56,cases=987,callback_cases=14)


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='phase',required=True)
    a=s.add_parser('run');a.add_argument('--native',required=True);a.add_argument('--rust',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('verify');a.add_argument('--report',required=True);a=p.parse_args()
    if a.phase=='run':run(a.native,a.rust,a.output)
    else:print(json.dumps(verify(a.report)))
