#!/usr/bin/env python3
"""Inspect retained compiler artifacts; never retries the closed host producer.

An ABI-set check is not execution or host qualification. In particular this
inspector cannot clear the independently reported post-allocation alias defect.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stage
import audit
import host_stage

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def need(ok,message):
    if not ok:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def symbols(data):
    return {line.split(b' T ',1)[1] for line in data.splitlines() if b' T ' in line}


def required_abi(original,candidate):
    wanted={s for s in symbols(original) if b'Star::ByteArray' in s}
    need(len(wanted)==33,'original compiled ABI scope')
    actual=symbols(candidate)
    need(wanted<=actual,'missing original compiled class ABI definition')
    return dict(required_compiled_abi_symbols=len(wanted),extra_emitted_symbols=len(actual-wanted))


def class_declaration(text):
    start=text.index('class ByteArray {');end=text.index('\n};',start)+3
    block=text[start:end]
    return re.sub(r'^ *friend struct ByteArrayNativeAccess;\n','',block,flags=re.MULTILINE)


def inspect(root):
    root=Path(root).resolve()
    need(root==ROOT/'build/byte-array-lab/host-acquire-r2','retained second acquisition only; no new producer attempt')
    parent=stage.verify_acquisition(host_stage.PARENT)
    before=stage.load(root/'before.json')
    for path,h in before.items():need(sha(path)==h,'current compiler input drift '+path)
    rows=[stage.load(p) for p in root.glob('*.command.json')]
    need(len(rows)==247,'complete dependency/compile/link/C11/tool command scope')
    for row in rows:
        need(type(row['returncode']) is int and row['returncode']==0,'compiler/tool failure '+row['name'])
        need(sha(row['executable'])==row['before']==row['after'],'compiler/tool identity')
        for ext in ('stdout','stderr'):need(sha(root/(row['name']+'.'+ext))==row[ext],'compiler/tool streams')
    compiled=[r for r in rows if r['name'].startswith('compile-')]
    need(len(compiled)==119,'113 configured native objects + six harness/controller objects')
    for row in compiled:
        args=row['command'];i=args.index('-ivfsoverlay')
        need(args[i+1]==str(root/'overlay.json'),'coherent header selection')
    expected_overlay={'version':0,'case-sensitive':'true','use-external-names':False,'roots':[
        {'type':'file','name':str(ROOT/'source/core/StarByteArray.hpp'),'external-contents':str(HERE/'host_header.hpp')},
        {'type':'file','name':str(ROOT/'source/core/StarByteArray.cpp'),'external-contents':str(HERE/'host_body.cpp')}]}
    need(stage.load(root/'overlay.json')==expected_overlay,'exact native header/body selection')
    need(class_declaration((ROOT/'source/core/StarByteArray.hpp').read_text())==class_declaration((HERE/'host_header.hpp').read_text()),'unchanged class declaration/layout fields except friend')
    routes=list(map(int,re.findall(r'execute\((\d+),',(HERE/'host_body.cpp').read_text()+(HERE/'host_header.hpp').read_text())))
    need(sorted(routes)==list(range(56)),'56 source-routed definitions, not runtime coverage')
    members=audit.archive_members((root/'prototype-core.a').read_bytes())
    need([n.decode() for n,_ in members]==[str(i)+'.o' for i in range(113)],'113 configured fresh archive members')
    for name,data in members:need(hashlib.sha256(data).hexdigest()==sha(root/name.decode()),'fresh member bytes')
    for name in ('lab','callback','protocol','growth','signed'):host_stage.check_map(root,name,host_stage.recipes())
    counts=required_abi((host_stage.PARENT.parent/'symbols-current.stdout').read_bytes(),(root/'body-symbols.stdout').read_bytes())
    return dict(status='COMPILER_ARTIFACT_DIAGNOSTIC_NOT_QUALIFIED',compiled_units=119,native_objects=113,
                source_routed_definitions=56,native_executions=0,**counts,
                known_guard_defect='receiver backing-output exclusion not updated after ALLOC',
                producer_approach='closed after host-acquire-r1/r2; do not run a third acquire',
                input_bindings=before,artifact_bindings={str(p):sha(p) for p in root.iterdir() if p.is_file()},
                diagnostic_sha256=sha(__file__))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    out=Path(args.output).absolute();need(out.is_relative_to(ROOT/'build/byte-array-lab') and not out.exists(),'fresh diagnostic output')
    result=inspect(args.root);out.mkdir(parents=True);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('input_bindings','artifact_bindings')}))
