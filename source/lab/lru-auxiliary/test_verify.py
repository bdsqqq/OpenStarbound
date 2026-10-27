#!/usr/bin/env python3
"""actual isolated receipt/byte fixtures exercise the same read-only verifier."""
import copy
import json
import os
import sys
from pathlib import Path
sys.dont_write_bytecode=True
import common as c

def relocate(value,old,new):
    if isinstance(value,str): return value.replace(str(old),str(new))
    if isinstance(value,list): return [relocate(v,old,new) for v in value]
    if isinstance(value,dict): return {relocate(k,old,new):relocate(v,old,new) for k,v in value.items()}
    return value

def fixture(source,dest):
    dest.mkdir(parents=True)
    for p in source.rglob('*'):
        rel=p.relative_to(source); q=dest/rel
        if p.is_dir(): q.mkdir(exist_ok=True)
        elif p.suffix=='.json': q.write_text(json.dumps(relocate(c.read(p),source,dest),sort_keys=True,indent=2))
        elif p.suffix in ('.a','.o') or p.name=='audio': q.symlink_to(p)
        else:
            b=p.read_bytes()
            if p.suffix in ('.map','.stderr','.stdout','.d'): b=b.replace(str(source).encode(),str(dest).encode())
            q.write_bytes(b)
    # Relocated driver/map bytes and receipt hashes are coherent, not stale-hash negatives.
    for q in dest.rglob('*.json'):
        if q.name.endswith('.start.json') or q.name=='inputs.json': continue
        v=c.read(q)
        if 'stdoutSha256' in v:
            stem=q.name.removesuffix('.status.json').removesuffix('.json')
            v['stdoutSha256']=c.sha(q.parent/(stem+'.stdout'));v['stderrSha256']=c.sha(q.parent/(stem+'.stderr'))
            for key in list(v.get('products',{})): v['products'][key]=c.sha(key)
        if q.name=='before-link.json': v['expandedDriverSha256']=c.sha(q.parent/'link-driver.stderr')
        q.write_text(json.dumps(v,indent=2,sort_keys=True))

def dump(p,v): p.write_text(json.dumps(v,indent=2,sort_keys=True))
def coherent_output(d,name,body):
    p=d/(name+'.stdout');p.write_bytes(body)
    for suffix in ('.json','.status.json'):
        q=d/(name+suffix);v=c.read(q);v['stdoutSha256']=c.sha(p);dump(q,v)

def main():
    source=c.OUT; controls=source.parent/'controls'; controls.mkdir(exist_ok=True); outcomes=[]
    def run(name,mutator,diagnostic=None):
        dest=controls/name; fixture(source,dest); c.OUT=dest
        try:
            if mutator: mutator(dest)
            c.verify()
            c.need(diagnostic is None,'known failure escaped: '+name)
            outcomes.append(dict(name=name,status='ACCEPTED_POSITIVE'))
        except (ValueError,FileNotFoundError) as e:
            if diagnostic is None: raise
            c.need(diagnostic in str(e),'wrong rejection '+name+': '+str(e)); outcomes.append(dict(name=name,status='REJECTED',reason=str(e)))
        finally: c.OUT=source
    run('positive',None)
    def omit(d):
        f=c.read(d/'inputs.json');f['bindings'].pop(str(c.AUDIO));dump(d/'inputs.json',f)
    run('omitted-source-binding',omit,'omitted mandatory input binding')
    def source_corrupt(d):
        f=c.read(d/'inputs.json');f['bindings'][str(c.AUDIO)]='0'*64;dump(d/'inputs.json',f)
    run('source-bytes',source_corrupt,'frozen source/artifact')
    def artifact(d):
        p=d/'acquisition/reference/compile.json';v=c.read(p);v['products'][str(d/'acquisition/reference/audio.o')]='0'*64;dump(p,v)
    run('artifact-products',artifact,'immediate produced products')
    def status(d):
        for suffix in ('.json','.status.json'):
            p=d/('acquisition/candidate/decode'+suffix);v=c.read(p);v['exitCode']=1;dump(p,v)
    run('coherent-status',status,'normal exit')
    def pcm(d):
        p=d/'acquisition/candidate';v=c.read(p/'decode.stdout');v['pcm'][1]+=1;coherent_output(p,'decode',json.dumps(v).encode())
    run('coherent-pcm',pcm,'literal PCM metadata/seek/end/counters')
    def help_bad(d):
        p=d/'cli/candidate/help';coherent_output(p,'run',(p/'run.stdout').read_bytes().replace(b'Show help text',b'Show WRONG text'))
    run('coherent-help',help_bad,'literal HELP/error stdout')
    def pid(d):
        p=d/'cli/reference/help/run.start.json';v=c.read(p);v['pid']=0;dump(p,v)
        for suffix in ('.json','.status.json'):
            p=d/('cli/reference/help/run'+suffix);r=c.read(p);r['start']=v;dump(p,r)
    run('coherent-missing-pid',pid,'actual PID/PGID')
    c.write(controls/'report.json',dict(status='PASS',cases=outcomes));print(json.dumps(outcomes,sort_keys=True))

if __name__=='__main__': main()
