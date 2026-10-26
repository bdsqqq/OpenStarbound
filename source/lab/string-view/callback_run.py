#!/usr/bin/env python3
"""Native callback deletion calibration, using already source-qualified objects."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
sys.dont_write_bytecode=True
import run
import callback_contract as model
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
NATIVE=run.BASE/'parent-final-r1'
BASE=ROOT/'build/string-view-lab'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def need(ok,msg):
    if not ok:raise ValueError(msg)


def verify(out):
    q=json.loads((out/'report.json').read_text())
    need(q['status']=='FINITE_NATIVE_STRINGVIEW_TERMINAL_CALLBACK_PASS' and type(q['cases']) is int and q['cases']==14,'scope')
    for group in ('bindings','artifacts'):
        for p,h in q[group].items():need(sha(p)==h,'drift '+p)
    need(q['commands']==json.loads((out/'commands.json').read_text()),'commands')
    for c in q['commands']:
        need(type(c['returncode']) is int and c['returncode']==0,'normal command')
        need(c==json.loads((out/(c['name']+'.command.json')).read_text()),'receipt')
        need(c['before']==c['after']==sha(c['executable']),'executable')
        for stream in ('stdout','stderr'):need(c[stream]==sha(out/(c['name']+'.'+stream)),'stream')
    need((out/'expected.jsonl').read_bytes()==model.canon(model.expected()),'oracle')
    for name in ('native','repeat'):model.check((out/(name+'.stdout')).read_bytes())
    return q


def acquire(out):
    need(out.parent==BASE and not out.exists(),'fresh owned output')
    out.mkdir(parents=True)
    baseline=run.verify(NATIVE)
    recipes=json.loads((NATIVE/'recipes.json').read_text())
    recipe=next(r for r in recipes if r['source'].endswith('/StarStringView.cpp'))
    objects=[NATIVE/(str(i)+'.o') for i in range(113)]
    libs=json.loads((NATIVE/'libraries.json').read_text())
    (out/'expected.jsonl').write_bytes(model.canon(model.expected()))
    tracked=[HERE/'callback.cpp',HERE/'callback_contract.py',Path(__file__).resolve(),NATIVE/'report.json',NATIVE/'recipes.json',NATIVE/'libraries.json',*objects,out/'expected.jsonl']
    bindings={**baseline['bindings'],**baseline['artifacts'],**{str(p):sha(p) for p in tracked}}
    dump(out/'before.json',bindings)
    commands=[]
    def command(args,name):
        args=list(map(str,args));exe=Path(args[0]).resolve();before=sha(exe)
        result=subprocess.run(args,cwd=run.CM,capture_output=True,timeout=90)
        for stream,data in [('stdout',result.stdout),('stderr',result.stderr)]: (out/(name+'.'+stream)).write_bytes(data)
        c=dict(name=name,command=args,executable=str(exe),before=before,after=sha(exe),returncode=result.returncode,stdout=sha(out/(name+'.stdout')),stderr=sha(out/(name+'.stderr')))
        dump(out/(name+'.command.json'),c);commands.append(c)
        need(result.returncode==0,'command failed '+name)
    c=recipe['compiler'];flags=recipe['flags']
    command([c,*flags,'-c',HERE/'callback.cpp','-o',out/'callback.o'],'compile')
    command([c,*flags,out/'callback.o',*objects,*libs,'-Wl,-dead_strip','-o',out/'native'],'link')
    for p,h in bindings.items():need(sha(p)==h,'before execution drift '+p)
    dump(out/'preexecute.json',{str(p):sha(p) for p in out.iterdir() if p.is_file()})
    for name in ('native','repeat'):
        command([out/'native'],name);model.check((out/(name+'.stdout')).read_bytes())
    for p,h in bindings.items():need(sha(p)==h,'execution drift '+p)
    dump(out/'commands.json',commands)
    q=dict(status='FINITE_NATIVE_STRINGVIEW_TERMINAL_CALLBACK_PASS',cases=14,bindings=bindings,commands=commands,expectedSha256=sha(out/'expected.jsonl'),artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},limits=['backing remains alive; no arbitrary pointer/lifetime claim','no Rust or application completion','base native profile provenance limitations retained'])
    dump(out/'report.json',q);verify(out);print(q['status'],out/'report.json',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['run','verify']);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();out=args.output.resolve()
    if args.phase=='run':acquire(out)
    else:print(verify(out)['status'])
