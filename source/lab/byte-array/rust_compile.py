#!/usr/bin/env python3
"""Compile actual production ByteArray OFF/ON translation units, without executing."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import stage
import host_stage as shared
import contract
import callback_contract

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
CORE=ROOT/'source/core'
BEFORE=ROOT/'build/byte-array-rust/native-before-r1.json'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def protocol_source():
    text=(HERE/'host_protocol.cpp').read_text()
    foreign='static uint32_t throws(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*){throw 17;}\n'
    call=' CHECK(sb_byte_array_run(SB_BA_CTOR,&c,throws)==3);\n'
    stage.need(text.count(foreign)==1 and text.count(call)==1,'prototype-only foreign C++ throw removal')
    return text.replace(foreign,'').replace(call,'').replace('"host_api.h"','"StarRustByteArray.h"').replace('Star::ByteArrayHost','Star::ByteArrayRust').replace('sb_byte_array_run','star_byte_array_run').replace('sb_byte_array_call_count','star_byte_array_call_count')


def probe_source(name):
    return '#include "StarRustByteArray.h"\n#define main byte_array_frozen_main\n#include "'+str(HERE/(name+'.cpp'))+'"\n#undef main\n'+'''int main(int argc,char** argv) {
uint64_t before[56][3];
for(unsigned m=0;m<56;++m)for(unsigned e=0;e<3;++e)before[m][e]=star_byte_array_call_count(m,e);
int rc=byte_array_frozen_main(argc,argv);
std::cerr << "COUNTERS";
for(unsigned m=0;m<56;++m)for(unsigned e=0;e<3;++e)std::cerr << " " << (star_byte_array_call_count(m,e)-before[m][e]);
std::cerr << "\\n";return rc;
}
'''


def compile_only(backend,archive,output):
    archive=Path(archive).resolve();stage.need(archive.is_file(),'fresh aggregate Rust archive required')
    out=Path(output).absolute();base=ROOT/'build/byte-array-rust'
    stage.need(out.is_relative_to(base) and out!=base and not out.exists(),'fresh owned candidate output')
    out.mkdir(parents=True)
    recipes=shared.recipes();compiler,flags,libs,_=stage.recipe();extra=(['-DSTAR_USE_RUST_BYTE_ARRAY'] if backend=='rust' else [])+['-I'+str(CORE)]
    for n in ('lab','callback'):(out/(n+'-probe.cpp')).write_text(probe_source(n))
    if backend=='rust':(out/'protocol.cpp').write_text(protocol_source())
    (out/'expected.jsonl').write_bytes(contract.canonical(contract.expected()))
    (out/'callback-expected.jsonl').write_bytes(callback_contract.canonical(callback_contract.expected()))
    frozen=stage.load(BEFORE)
    initial={p:sha(p) for p in frozen['bindings']}
    for p in (BEFORE,archive,HERE/'rust_compile.py',CORE/'StarByteArray.cpp',CORE/'StarByteArray.hpp',CORE/'StarByteArrayHost.hpp',CORE/'StarRustByteArray.h',ROOT/'source/CMakeLists.txt',ROOT/'source/rust/ffi/src/lib.rs',ROOT/'source/rust/ffi/src/byte_array.rs',HERE/'lab.cpp',HERE/'callback.cpp',HERE/'host_protocol.cpp'):
        initial[str(p)]=sha(p)
    shared.dump(out/'precompile-freeze.json',initial)
    jobs=[(r['compiler'],r['flags'],r['source'],str(i)) for i,r in enumerate(recipes)]
    for n in ('lab','callback'):
        jobs.append((str(compiler),flags,str(out/(n+'-probe.cpp')),n))
    if backend=='rust':jobs.append((str(compiler),flags,str(out/'protocol.cpp'),'protocol'))
    def scan(j):
        c,f,source,n=j
        return shared.command([c,*f,*extra,'-M','-MF',out/(n+'.d'),source],'deps-'+n,out)
    commands=[]
    with ThreadPoolExecutor(max_workers=6) as pool:commands+=list(pool.map(scan,jobs))
    before=dict(initial)
    for _,_,_,n in jobs:
        for p in stage.dependencies(out/(n+'.d')):before[str(p)]=sha(p)
    shared.dump(out/'before.json',before)
    stage.need(all(sha(p)==h for p,h in initial.items()),'source drift during dependency scan')
    def compile_job(j):
        c,f,source,n=j
        return shared.command([c,*f,*extra,'-c',source,'-o',out/(n+'.o')],'compile-'+n,out)
    with ThreadPoolExecutor(max_workers=6) as pool:commands+=list(pool.map(compile_job,jobs))
    commands.append(shared.command(['/usr/bin/ar','qcs',out/'candidate-core.a',*[out/(str(i)+'.o') for i in range(113)]],'archive',out))
    commands.append(shared.command(['/usr/bin/ar','t',out/'candidate-core.a'],'archive-table',out))
    for n in ('lab','callback',*(['protocol'] if backend=='rust' else [])):
        commands.append(shared.command([compiler,*flags,*extra,out/(n+'.o'),out/'candidate-core.a',archive,*libs,
                        '-Wl,-dead_strip','-Wl,-map,'+str(out/(n+'.map')),'-o',out/n],'link-'+n,out))
    index=next(str(i) for i,r in enumerate(recipes) if r['source'].endswith('/StarByteArray.cpp'))
    commands.append(shared.command(['/usr/bin/nm','-C','--defined-only',out/(index+'.o')],'body-symbols',out))
    after={p:sha(p) for p in before};shared.dump(out/'after.json',after);stage.need(before==after,'candidate compile input drift')
    shared.dump(out/'commands.json',commands)
    result=dict(status='COMPILED_BYTEARRAY_CANDIDATE_UNSEALED',backend=backend,archive=str(archive),archive_sha256=sha(archive),before=before,after=after,
                recipes=recipes,jobs=[list(j) for j in jobs],commands=commands,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()})
    shared.dump(out/'build.json',result);print(result['status'],backend,out/'build.json',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--backend',choices=('native','rust'),required=True);p.add_argument('--archive',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();compile_only(a.backend,a.archive,a.output)
