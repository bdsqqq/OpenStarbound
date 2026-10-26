#!/usr/bin/env python3
"""Compiler-only producer. Sealing and execution are deliberately separate phases.

The exhausted host_stage.acquire path is never invoked. This producer publishes
raw command/artifact evidence even though it cannot qualify or execute a host.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import stage
import host_stage as shared
import contract
import callback_contract
import audit

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def compile_only(output):
    parent=stage.verify_acquisition(shared.PARENT)
    out=stage.fresh(output,'host-compile-')
    recipes=shared.recipes();commands=[]
    selection=shared.overlay(out/'overlay.json')
    extra=['-ivfsoverlay',str(out/'overlay.json'),'-I'+str(HERE)]
    for n in ('lab','callback'):shared.probe_source(out/(n+'-probe.cpp'),HERE/(n+'.cpp'))
    (out/'c11.c').write_text('#include "'+str(HERE/'host_api.h')+'"\nint main(void){return 0;}\n')
    (out/'expected.jsonl').write_bytes(contract.canonical(contract.expected()))
    (out/'callback-expected.jsonl').write_bytes(callback_contract.canonical(callback_contract.expected()))
    variants=shared.control_sources((HERE/'host_controller.cpp').read_text())
    for n,source in variants.items():
        (out/(n+'.cpp')).write_text(source)
        (out/(n+'-expected.jsonl')).write_bytes(contract.canonical(audit.wrong_rows('growth-control' if n=='growth' else 'signed-control')))
    initial={**parent['bindings'],**parent['artifacts'],str(shared.PARENT):shared.sha(shared.PARENT)}
    for n in (*shared.SOURCES,'host_stage.py','host_compile.py','lab.cpp','callback.cpp','contract.py','callback_contract.py'):
        initial[str(HERE/n)]=shared.sha(HERE/n)
    shared.dump(out/'precompile-freeze.json',initial)
    compiler,flags,libs,_=stage.recipe()
    jobs=[(r['compiler'],r['flags'],r['source'],str(i)) for i,r in enumerate(recipes)]
    for n,source in [('controller',HERE/'host_controller.cpp'),('protocol',HERE/'host_protocol.cpp'),('lab',out/'lab-probe.cpp'),('callback',out/'callback-probe.cpp')]:
        jobs.append((str(compiler),flags,str(source),n))
    for n in variants:jobs.append((str(compiler),flags,str(out/(n+'.cpp')),n))
    def scan(job):
        c,f,src,n=job
        return shared.command([c,*f,*extra,'-M','-MF',out/(n+'.d'),src],'deps-'+n,out)
    with ThreadPoolExecutor(max_workers=6) as pool:commands+=list(pool.map(scan,jobs))
    before=dict(initial)
    for _,_,_,n in jobs:
        for p in shared.dependencies(out/(n+'.d')):before[str(p)]=shared.sha(p)
    before[str(out/'overlay.json')]=shared.sha(out/'overlay.json')
    shared.dump(out/'before.json',before)
    stage.need(all(shared.sha(p)==h for p,h in initial.items()),'source drift during dependency acquisition')
    def build(job):
        c,f,src,n=job
        return shared.command([c,*f,*extra,'-c',src,'-o',out/(n+'.o')],'compile-'+n,out)
    with ThreadPoolExecutor(max_workers=6) as pool:commands+=list(pool.map(build,jobs))
    objects=[out/(str(i)+'.o') for i in range(113)]
    commands.append(shared.command(['/usr/bin/ar','qcs',out/'prototype-core.a',*objects],'archive',out))
    commands.append(shared.command(['/usr/bin/ar','t',out/'prototype-core.a'],'archive-table',out))
    for n in ('lab','callback','protocol','growth','signed'):
        probe=out/('lab.o' if n in variants else n+'.o')
        controller=out/(n+'.o' if n in variants else 'controller.o')
        commands.append(shared.command([compiler,*flags,*extra,probe,controller,out/'prototype-core.a',*libs,
                        '-Wl,-dead_strip','-Wl,-map,'+str(out/(n+'.map')),'-o',out/n],'link-'+n,out))
    commands.append(shared.command([compiler,'-x','c','-std=c11','-Wall','-Wextra','-Werror','-pedantic-errors','-fsyntax-only',out/'c11.c'],'c11',out))
    index=next(str(i) for i,r in enumerate(recipes) if r['source'].endswith('/StarByteArray.cpp'))
    commands.append(shared.command(['/usr/bin/nm','-C','--defined-only',out/(index+'.o')],'body-symbols',out))
    after={p:shared.sha(p) for p in before};shared.dump(out/'after.json',after)
    stage.need(before==after,'compiled source/tool/dependency drift')
    stage.verify_acquisition(shared.PARENT)
    shared.dump(out/'commands.json',commands)
    result=dict(status='COMPILED_UNSEALED',parent=str(shared.PARENT),parent_sha256=shared.sha(shared.PARENT),
                recipes=recipes,jobs=[list(j) for j in jobs],overlay=selection,bindings=before,after=after,commands=commands,
                artifacts={str(p):shared.sha(p) for p in out.iterdir() if p.is_file()})
    shared.dump(out/'build.json',result)
    print('COMPILED_UNSEALED',out/'build.json',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args();compile_only(args.output)
