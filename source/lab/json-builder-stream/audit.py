#!/usr/bin/env python3
"""AFTER-observation read-only partial audit; NEVER native acceptance or repair.

This tool does not compile, execute a native binary, change expected values,
write acquisition files, or call the closed run/verify acceptance approaches.
Its stdout is a diagnostic supplement, not a reclassification of either attempt.
"""
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import run
import model
import inventory


def audit(out):
    run.safe(out)
    run.need(not (out/'report.json').exists(),'failed acquisition has no acceptance report')
    e=run.Evidence();q=e.json(out/'candidate.json');r=run.recipe()
    run.equal(q['status'],'RAW_NATIVE_ACQUISITION_PENDING_VERIFY','raw candidate status')
    run.equal(q['definition_count'],20,'explicit class body count')
    run.equal(e.json(out/'recipe.json'),r,'actual native recipe')
    run.need(e.sha(run.SOURCE)==e.sha(run.ORIGINAL)==run.SOURCE_SHA,'original/current cpp source')
    run.need(e.sha(run.HEADER)==e.sha(run.HERE/'original/StarJsonBuilder.hpp')==run.HEADER_SHA,'original/current public header')
    paths=run.inputs(out,r,e);snap=run.snapshots(out,paths)
    for dest,src in snap.items():run.equal(e.data(dest),e.data(src),'snapshot unchanged')
    bindings=e.hashes(paths|set(snap))
    for frozen in (e.json(out/'before.json'),e.json(out/'after.json'),q['bindings']):run.equal(bindings,frozen,'required source/tool/dependency bindings')
    artifacts=run.artifacts(out,r)
    run.equal(e.hashes(artifacts),q['artifacts'],'required artifacts')
    run.equal(e.hashes(run.preexecute(out,r)),e.json(out/'preexecute.json'),'preexecution artifact freeze')
    model.literal_checks()
    run.equal(e.data(out/'inputs.tsv'),model.inputs(),'frozen independent input corpus')
    run.equal(e.data(out/'expected.tsv'),model.expected(),'frozen independent model')
    old=run.BASE/'attempt-1/snapshots/source/lab/json-builder-stream/model.py'
    run.equal(e.data(old),e.data(run.HERE/'model.py'),'NO model repair between failed attempts')
    sdk=r['flags'][r['flags'].index('-isysroot')+1]
    run.sdk_witness.verify(e.json(out/'sdk-before.json'),sdk,run.CANONICAL_SDK)
    run.equal(e.json(out/'sdk-before.json'),e.json(out/'sdk-after.json'),'whole sdk before/after')
    commands=[]
    for name,argv,stdin in run.plans(out,r):
        c=e.json(out/(name+'.command.json'))
        for key,value in [('name',name),('argv',argv),('cwd',str(run.CM)),('env',run.env(out)),('stdin',{'sha256':run.digest(stdin),'size':len(stdin)})]:run.equal(c[key],value,'command '+key)
        run.need(type(c['exit']) is int and c['exit']==0 and c['exit_type']=='normal','normal command exit')
        for key in ('tool_before','tool_after'):run.equal(c[key],run.tool(argv[0]),'executable alias/payload')
        for key in ('stdout','stderr'):run.equal(c[key],e.sha(out/(name+'.'+key)),'command bytes')
        commands.append({'name':name,'exit':c['exit'],'stdout':c['stdout'],'stderr':c['stderr']})
    inventories={}
    for v in ('original','current'):
        inv=inventory.reconcile(run.source(out,v),e.data(out/('ast-'+v+'.stdout')))
        run.equal(inv,e.json(out/('inventory-'+v+'.json')),'compiler/manual all-body ranges')
        inventories[v]=inv
    specials=inventory.specials(e.data(out/'ast-fixture.stdout'))
    run.equal(specials,e.json(out/'implicit-fixture.json'),'six actual implicit lifecycle operations')
    links={v:run.reconcile_link(out,r,v,e,sdk) for v in run.VARIANTS}
    run.equal(links,q['links'],'expanded/runtime/archive/trace/map identities')
    cpp=e.data(run.ORIGINAL)
    for v,(a,b) in run.MUTATIONS.items():
        data=e.data(out/(v+'.cpp'));run.equal(data,cpp.replace(a.encode(),b.encode()),'one selected native mutation')
        run.equal(data.split(b'void JsonStreamer<Json>::toJsonStream',1)[1],cpp.split(b'void JsonStreamer<Json>::toJsonStream',1)[1],'unselected adjacent streamer unchanged')
    expected=model.expected().splitlines();original=e.data(out/'run-original.stdout')
    run.equal(original,e.data(out/'run-current.stdout'),'entire original/current native raw order/errors/lifecycle output')
    variants={};mismatches=[]
    for v in run.VARIANTS:
        data=e.data(out/('run-'+v+'.stdout'))
        run.equal(data,e.data(out/('run-'+v+'-repeat.stdout')),'native raw repeat')
        for suffix in ('','-repeat'):run.equal(e.data(out/('run-'+v+suffix+'.stderr')),b'','native stderr')
        actual=run.semantic(data).splitlines();run.need(len(actual)==len(expected),'complete native event rows')
        unequal=[i for i,(x,y) in enumerate(zip(actual,expected)) if x!=y]
        native_unequal=[i for i,(x,y) in enumerate(zip(actual,run.semantic(original).splitlines())) if x!=y]
        if v in run.MUTATIONS:run.need(bool(native_unequal),'NORMAL semantic mutant differs from native reference')
        variants[v]={'exit':0,'repeat_exit':0,'rows':len(actual),'raw_repeat_equal':True,'expected_mismatch_rows':unequal,'native_reference_mismatch_rows':native_unequal,'stdout_sha256':run.digest(data)}
        if v=='original':
            mismatches=[{'row':i,'native':actual[i].decode(),'expected':expected[i].decode()} for i in unequal]
    run.need(len(mismatches)>0,'retain actual model mismatch, NEVER accept')
    return {'status':'PARTIAL_DIAGNOSTIC_BUDGET_CLOSED_NOT_ACCEPTED','after_observation_supplement':True,
        'tested_head':'990981bdb5e440ee35ed89b54b5f462f7af9e156','source_cpp_sha256':run.SOURCE_SHA,'source_header_sha256':run.HEADER_SHA,
        'model_sha256':e.sha(run.HERE/'model.py'),'input_sha256':e.sha(out/'inputs.tsv'),'expected_sha256':e.sha(out/'expected.tsv'),
        'audit_sha256':run.sha(Path(__file__).resolve()),'bindings':len(bindings),'required_artifacts':len(artifacts),'commands':commands,
        'case_count':len(model.cases()),'event_rows':len(expected),'definition_count':20,'inventories':inventories,'implicit_fixture':specials,
        'links':links,'variants':variants,'mismatches':mismatches,
        'closed_attempts':[{'attempt':1,'stage':'first-link reconciliation; nested bytes-list JSON encoding TypeError; no runtime observations'},
                           {'attempt':2,'stage':'all native variants/repeats acquired; frozen independent original model comparison rejected'}],
        'unexecuted':['acceptance verifier corruption controls (blocked before reaching controls)','private ABI/ownership qualification','Rust','actual application behavior'],
        'limits':q['limits'],'next_action':'parent review preserved partial evidence; NO retry/model repair/domain restriction under this closed approach'}

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: audit.py ABSOLUTE_ATTEMPT_2')
    print(json.dumps(audit(Path(sys.argv[1])),indent=2))
