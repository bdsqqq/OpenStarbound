#!/usr/bin/env python3
"""Replay callback receipts independently of the supplemental producer/verifier."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shlex
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import audit as original_audit
import callback_contract as contract

ROOT=HERE.parents[2]
PARENT=ROOT/'build/byte-array-lab/acquire-r1/acquisition.json'
BASELINE=('original','reference','current','repeat')
CONTROLS=('stale-tail-control','resort-control')


def need(ok,message):
    if not ok:raise ValueError(message)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p):return original_audit.read(p)


def expected_control(name):
    rows=copy.deepcopy(contract.expected())
    for row in rows:
        if name=='stale-tail-control' and row['case']=='grow_large':
            row['result']={'size':5,'capacity':8,'prefix':[60,63,42,43,44]}
        elif name=='resort-control' and row['case']=='flip_roles':
            row['result']={'size':1,'capacity':3,'prefix':[10]}
    return rows


def check_stream(data,name):
    if name in BASELINE:return contract.check(data)
    need(name in CONTROLS,'known native control')
    rows=[original_audit.parse(line) for line in data.splitlines()]
    contract._typed_equal(rows,expected_control(name),'independent wrong-controller trace')
    try:contract.check(data)
    except ValueError:pass
    else:raise ValueError('correct oracle accepted wrong controller')
    return len(rows)


def replay(path):
    path=Path(path).resolve();r=load(path);acq=Path(r['acquisition']);q=load(acq);root=acq.parent
    need(r['status']=='FINITE_NATIVE_CALLBACK_TRACE_PASS' and q['status']=='CALLBACK_NATIVE_ACQUIRED_NOT_EXECUTED','phase separation')
    for value in (r['cases'],q['cases']):need(type(value) is int and value==14,'finite trace scope')
    need(q['parent']==str(PARENT) and q['parent_sha256']==sha(PARENT) and r['acquisition_sha256']==sha(acq),'parent/acquisition identity')
    parent=load(PARENT)
    for p,h in {**parent['bindings'],**parent['artifacts'],str(PARENT):sha(PARENT)}.items():
        need(q['bindings'].get(p)==h,'complete native parent closure')
    # This retains the original independent BSD archive/member/source validation,
    # rather than trusting only the supplemental producer's manifest copies.
    native=original_audit.audit(ROOT/'build/byte-array-lab/execute-r1/report.json')
    need(native['status']=='AUDITED_FINITE_NATIVE_BYTEARRAY_PASS','accepted original native surface')
    for bindings in (q['bindings'],q['artifacts'],r['artifacts']):
        for p,h in bindings.items():need(sha(p)==h,'source/artifact drift '+p)
    need(q['bindings']==load(root/'before.json')==load(root/'after.json'),'before/after sources')
    freeze=load(root/'precompile-freeze.json')
    required={str(HERE/n) for n in ('callback.cpp','callback_contract.py','test_callback_contract.py','CALLBACKS.md','callback_stage.py')}
    need(set(freeze['files'])==required,'mandatory precompile source freeze')
    for p,h in freeze['files'].items():need(q['bindings'][p]==h and sha(p)==h,'precompile source identity')
    need(freeze['expected_sha256']=='c44665b0ef232eda3e689de2cc9d736bec83d330aeb079511652a9a11f3c7464','independent frozen oracle')
    need((root/'expected.jsonl').read_bytes()==contract.canonical(contract.expected()) and sha(root/'expected.jsonl')==freeze['expected_sha256'],'precompiled expected rows')
    need(q['controls']==list(CONTROLS)==r['controls'],'normal control scope')
    for name in CONTROLS:
        need((root/(name+'.expected.jsonl')).read_bytes()==contract.canonical(expected_control(name)),'precompiled wrong-controller oracle')
        source=(root/(name+'.cpp')).read_text()
        need(source.count('#include "StarByteArray.hpp"')==1 and 'ByteArray wrongCombine' in source,'unchanged-header control')
    for p in shlex.split((root/'callback.d').read_text().replace('\\\n',' ').split(':',1)[1]):
        p=Path(p);p=p.resolve() if p.is_absolute() else (ROOT/p).resolve()
        need(str(p) in q['bindings'],'new probe dependency closure')
    need(r['receipts']==load(path.parent/'receipts.json') and q['receipts']==load(root/'receipts.json'),'command receipt copies')
    names=(*BASELINE,*CONTROLS);need([x['name'] for x in r['receipts']]==list(names),'six actual executions')
    need(set(r['artifacts'])=={str(path.parent/(n+'.'+e)) for n in names for e in ('stdout','stderr')}|{str(path.parent/'receipts.json')},'execution artifact inventory')
    for row in r['receipts']:
        name=row['name'];exe=str(root/('current' if name=='repeat' else name))
        need(row['command']==[exe] and row['executable']==exe and type(row['returncode']) is int and row['returncode']==0,'normal actual route')
        need(sha(exe)==row['before']==row['after'],'executed image identity')
        for ext in ('stdout','stderr'):need(sha(path.parent/(name+'.'+ext))==row[ext],'execution stdio identity')
        need(check_stream((path.parent/(name+'.stdout')).read_bytes(),name)==14,'complete typed trace')
    for name in ('original','reference','current',*CONTROLS):
        data=(root/(name+'.map')).read_bytes();objects=original_audit.native_artifacts.link_map_objects(data)
        probe=root/(name+'.o' if name in CONTROLS else 'probe.o')
        body=PARENT.parent/(name+'.o' if name in ('original','reference','current') else 'current.o')
        need(str(probe).encode() in objects and str(body).encode() in objects,'actual linked native object routes')
        need(not original_audit.native_artifacts.has_archive_member(data,b'native-core.a',b'StarByteArray.cpp.o'),'old native body bypass')
    return dict(status='AUDITED_FINITE_NATIVE_CALLBACK_PASS',cases=14,positive_streams=4,normal_controls=2,
                report=str(path),report_sha256=sha(path),auditor_sha256=sha(__file__),parent_cases=987)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    out=Path(args.output).absolute();need(out.is_relative_to(ROOT/'build/byte-array-lab') and not out.exists(),'fresh owned audit output')
    result=replay(args.report);out.mkdir(parents=True);(out/'audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
