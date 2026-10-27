#!/usr/bin/env python3
"""Post-observation read-only audit of a FAILED acquisition, never a pass gate.

This was written after the failure. It preserves the frozen model unchanged and
reports its disagreement, rather than repairing expectations or running native
code a third time. Artifact membership is reconstructed from run.plans/recipe.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import run as r
import model
import inventory


def audit(out,e=None):
    r.safe(out);e=e or r.Evidence();recipe=r.recipe()
    r.need(not (out/'report.json').exists(),'failed acquisition must have no pass report')
    r.equal(e.json(out/'recipe.json'),recipe,'configured recipe')
    r.need(e.sha(r.HEADER)==e.sha(r.ORIGINAL)==r.HEADER_SHA,'original/current exact frozen header')
    model.literal_checks()
    r.equal(e.data(out/'inputs.tsv'),model.inputs(),'unchanged pre-observation corpus')
    r.equal(e.data(out/'expected.tsv'),model.expected(),'unchanged pre-observation model')
    for v,(a,b) in r.MUTATIONS.items():
        r.equal(e.data(out/(v+'.hpp')),e.data(r.ORIGINAL).replace(a.encode(),b.encode()),'one edit source mutant')
    sdk=recipe['flags'][recipe['flags'].index('-isysroot')+1]
    r.sdk_witness.verify(e.json(out/'sdk-before.json'),sdk,r.CANONICAL_SDK)
    r.equal(e.json(out/'sdk-before.json'),e.json(out/'sdk-after.json'),'SDK before/after')
    paths=r.inputs(out,recipe,e);snap=r.snapshots(out,paths)
    for dest,src in snap.items():r.equal(e.data(dest),e.data(src),'copied dependency/source bytes')
    bindings=e.hashes(paths|set(snap))
    r.equal(bindings,e.json(out/'before.json'),'all independently required before bindings')
    r.equal(bindings,e.json(out/'after.json'),'all independently required after bindings')
    r.equal(e.hashes(r.preexecute(out,recipe)),e.json(out/'preexecute.json'),'complete preexecution artifacts')
    commands=[]
    for name,argv,stdin in r.plans(out,recipe):
        c=e.json(out/(name+'.command.json'))
        r.equal(c['name'],name,'command name');r.equal(c['argv'],argv,'derived argv')
        r.equal(c['cwd'],str(r.CM),'cwd');r.equal(c['env'],r.env(out),'environment')
        r.need(type(c['exit']) is int and c['exit']==0 and c['exit_type']=='normal','typed normal zero exit')
        r.equal(c['stdin'],{'sha256':r.digest(stdin),'size':len(stdin)},'stdin')
        r.equal(c['tool_before'],r.tool(argv[0]),'tool requested chain/payload before')
        r.equal(c['tool_after'],r.tool(argv[0]),'tool requested chain/payload after')
        for suffix in ('stdout','stderr'):r.equal(c[suffix],e.sha(out/(name+'.'+suffix)),'command stdio')
        commands.append({'name':name,'receipt':e.sha(out/(name+'.command.json'))})
    inventories={}
    for v in ('original','current'):
        inv=inventory.reconcile(r.header(out,v),e.data(out/('ast-'+v+'.stdout')))
        r.equal(inv,e.json(out/('inventory-'+v+'.json')),'all 21 manual/compiler AST bodies')
        inventories[v]={'explicit':len(inv['definitions']),'implicit':len(inv['implicit_special_members'])}
    links={v:r.reconcile_link(out,recipe,v,e,sdk) for v in r.VARIANTS}
    expected=e.data(out/'expected.tsv').splitlines();native=e.data(out/'run-original.stdout').splitlines()
    current=e.data(out/'run-current.stdout').splitlines()
    r.equal(len(expected),len(native),'observation count');r.equal(native,current,'original/current identical')
    by_mode={}
    mismatches=[]
    for index,(x,y) in enumerate(zip(expected,native)):
        a=x.split(b'\t');b=y.split(b'\t');r.equal(a[:3],b[:3],'event identity')
        mode=a[1].decode();d=by_mode.setdefault(mode,{'observations':0,'matching':0,'mismatching':0})
        d['observations']+=1;d['matching' if x==y else 'mismatching']+=1
        if x!=y:mismatches.append({'row':index,'case':a[0].decode(),'mode':mode,'event':int(a[2]),'expected_sha256':r.digest(x),'actual_sha256':r.digest(y)})
    variants={}
    for v in r.VARIANTS:
        a=e.data(out/('run-'+v+'.stdout'));b=e.data(out/('run-'+v+'-repeat.stdout'))
        r.equal(a,b,'finite repeat '+v)
        variants[v]={'repeat_identical':True,'matches_frozen_model':a==e.data(out/'expected.tsv'),'matches_original':a==e.data(out/'run-original.stdout')}
        if v in r.MUTATIONS:r.need(a!=e.data(out/'run-original.stdout'),'semantic mutant differs from native original '+v)
    r.need(len(mismatches)>0,'this is explicitly the failed acquisition, not requalification')
    return {'status':'PARTIAL_NATIVE_JSON_WRITER_MODEL_MISMATCH_CLOSED_BUDGET',
            'calibration_accepted':False,'attempts_budget_closed':True,
            'audit_timing':'POST_OBSERVATION; NOT acquisition-time oracle or new native run',
            'audit_source':{str(Path(__file__).resolve()):r.sha(__file__)},
            'scope':{'explicit_class_definitions':21,'scenarios':len(model.corpus()),'observations_per_binary':len(expected),'normal_native_runs':14,'retained_native_objects':113},
            'inventory':inventories,'mode_comparisons':by_mode,'mismatches':mismatches,
            'variants':variants,'links':links,'commands':commands,
            'bindings':bindings,'artifacts':e.hashes(r.artifacts(out,recipe)),
            'unmet':['frozen independent model mismatch in instrumented UTF-8 sink','full calibration verifier controls require accepted report and were NOT run','no Rust/ABI/application adoption authorized by this evidence'],
            'limits':['new audit was written after observing failure','before/after snapshots cannot attest transient edit/revert','113 native objects reused read-only, not rebuilt','framework/interpreter/dylib transitive implementations, OOM and universal lifetime/ownership remain unproved','hex8/substr branch is source-inventoried but actually unreachable, NOT runtime covered']}


def verify(out,e=None):
    e=e or r.Evidence();wanted=audit(out,e)
    r.equal(e.json(out/'partial-audit.json'),wanted,'entire partial audit, typed recursively')
    return wanted


def controls(out):
    report=verify(out);dest=out/'audit-controls';r.need(not dest.exists(),'fresh controls');dest.mkdir();results=[]
    tests=[]
    bad=copy.deepcopy(report);bad['calibration_accepted']=0
    tests.append(('false-bool-report',out/'partial-audit.json',json.dumps(bad).encode()))
    bad=copy.deepcopy(report);bad['bindings'].pop(next(iter(bad['bindings'])))
    tests.append(('missing-binding-report',out/'partial-audit.json',json.dumps(bad).encode()))
    bad=json.loads((out/'before.json').read_bytes());bad.pop(next(iter(bad)))
    tests.append(('missing-required-input',out/'before.json',json.dumps(bad).encode()))
    bad=json.loads((out/'run-current.command.json').read_bytes());bad['exit']=False
    tests.extend([('false-exit',out/'run-current.command.json',json.dumps(bad).encode()),
                  ('malformed-receipt',out/'run-current.command.json',b'{'),
                  ('source',r.HEADER,r.HEADER.read_bytes()+b'\n'),
                  ('object',out/'current.o',(out/'current.o').read_bytes()+b'corrupt')])
    for name,path,data in tests:
        clone=dest/(name+'.clone');r.put(clone,data)
        try:verify(out,r.Evidence({str(path):str(clone)}))
        except (ValueError,KeyError,FileNotFoundError) as ex:results.append({'name':name,'rejected':str(ex)[:200]})
        else:raise ValueError('audit control escaped '+name)
    r.dump(dest/'results.json',results)
    return results


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['record','verify','controls']);p.add_argument('--output',required=True);args=p.parse_args();out=Path(args.output)
    if args.phase=='record':
        q=audit(out);r.dump(out/'partial-audit.json',q);print(q['status'],len(q['mismatches']))
    elif args.phase=='controls':print(json.dumps(controls(out)))
    else:print(verify(out)['status'])
