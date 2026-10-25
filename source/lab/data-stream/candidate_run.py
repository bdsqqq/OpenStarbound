#!/usr/bin/env python3
"""Finite actual compiled-member replay. Requires an explicit parent source freeze."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
from run import anchors, gate
from verify_receipts import verify as verify_native

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
EXPECTED = '5ee512e3a91027823f34c47df4d1e056753e0fd61f03a9ad70e65131900763ab'
CORE = ROOT/'source/core/StarDataStream.cpp'
HEADER = ROOT/'source/core/StarDataStreamHost.hpp'
ABI = ROOT/'source/core/StarRustDataStream.h'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--values', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--source-freeze', required=True, type=Path,
                    help='parent-authorized JSON absolute-path to SHA256 map')
    ap.add_argument('--archive', required=True, type=Path)
    ap.add_argument('--archive-sha256', required=True)
    a = ap.parse_args()
    out = a.output.absolute()
    base = ROOT/'build/data-stream-lab'
    if (not out.is_relative_to(base) or out==base or out.exists()
            or not out.name.startswith('rust-')
            or any(p.is_symlink() for p in [out,*out.parents])):
        ap.error('fresh owned rust-* nonsymlink root required')
    assert shutil.disk_usage(ROOT).free > 1024**3
    frozen=json.loads(a.source_freeze.read_text())
    required=[CORE,HEADER,ABI,ROOT/'source/core/StarDataStream.hpp',
              ROOT/'source/rust/ffi/src/data_stream.rs',ROOT/'source/rust/ffi/src/lib.rs',
              ROOT/'source/CMakeLists.txt',a.archive.resolve()]
    for p in required:
        assert frozen.get(str(p.resolve()))==sha(p), 'parent freeze missing/drift: '+str(p)
    assert sha(a.archive)==a.archive_sha256
    verify_native(a.values/'report.json')
    native=json.loads((a.values/'report.json').read_text())
    for ext in ('cpp','hpp'):
        gate(ext,(HERE/f'StarDataStream.original.{ext}').read_text(),
             (HERE/f'StarDataStream.reference.{ext}').read_text())
    assert native['ordered_sha256']==EXPECTED and native['cases']==683
    link=native['link'];out.mkdir(parents=True)
    bindings=dict(native['bindings']);bindings.update(frozen)
    for p in [a.source_freeze, a.values/'report.json',Path(link['archive']),
              Path(__file__),HERE/'verify_candidate.py',HERE/'host_contract_test.cpp',
              *sorted((ROOT/'source/rust').rglob('*.rs')),
              *sorted((ROOT/'source/rust').rglob('Cargo.*'))]:
        bindings[str(p.resolve())]=sha(p)
    receipts=[];generated={};binaries={}
    def run(cmd,name):
        cmd=list(map(str,cmd));before=sha(Path(cmd[0]).resolve())
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=75)
        assert before==sha(Path(cmd[0]).resolve()),'executed artifact drift'
        for stream in ('stdout','stderr'):(out/(name+'.'+stream)).write_bytes(getattr(r,stream))
        receipts.append(dict(name=name,command=cmd,returncode=r.returncode,
                             executable_sha256=before,
                             stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),
                             stderr_sha256=hashlib.sha256(r.stderr).hexdigest()))
        (out/'receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
        assert r.returncode==0,name+' failed; NO negative credit'
        return r.stdout
    def generate(name,body):
        p=out/name;p.write_text(body);generated[str(p)]=sha(p);return p
    flags=[*link['flags'],'-UNDEBUG','-I'+str(HERE),'-I'+str(ROOT/'source/core')]
    selected=['-DSTAR_USE_RUST_DATA_STREAM','-DSTAR_USE_RUST_BYTES','-DSTAR_USE_RUST_VLQ']
    run([link['compiler'],*flags,'-x','c','-std=c11','-pedantic-errors','-fsyntax-only',ABI],'c11')
    wrapper=generate('observer.cpp',r'''
#include "StarRustDataStream.h"
#include <cstdio>
static uint64_t returned[51][4]{};
extern "C" uint32_t data_stream_observed_run(uint32_t m,void*c,StarDataStreamHost h){
 auto s=star_data_stream_run(m,c,h);
#ifdef WRONG_PENDING
 if(s==1)s=2;
#endif
 if(m<51&&s<4)++returned[m][s];return s;
}
extern "C" void data_stream_dump_routes(){for(unsigned m=0;m<51;++m){
 std::fprintf(stderr,"route %u",m);for(unsigned e=0;e<4;++e)std::fprintf(stderr," %llu",(unsigned long long)returned[m][e]);std::fprintf(stderr,"\n");}}
''')
    driver=generate('driver.cpp',r'''
#include "StarRustDataStream.h"
#include "StarRustBytes.h"
#include "StarRustVlq.h"
#define main data_stream_frozen_main
#include "lab.cpp"
#undef main
extern "C" void data_stream_dump_routes();
int main(){
 uint64_t before[51][3]{};for(unsigned m=0;m<51;++m)for(unsigned e=0;e<3;++e)before[m][e]=star_data_stream_call_count(m,e);
 uint64_t bytesBefore[6]{},vlqBefore[6]{};for(unsigned i=0;i<6;++i){bytesBefore[i]=star_bytes_call_count(i);vlqBefore[i]=star_vlq_call_count(i);}
 int result=data_stream_frozen_main();
 for(unsigned m=0;m<51;++m){std::cerr<<"count "<<m;for(unsigned e=0;e<3;++e){auto n=star_data_stream_call_count(m,e)-before[m][e];
#ifdef SUPPRESS_RECEIPT
 n=0;
#endif
 std::cerr<<" "<<n;}std::cerr<<"\n";}
 data_stream_dump_routes();
 for(unsigned i=0;i<6;++i)std::cerr<<"dependency "<<i<<" "<<(star_bytes_call_count(i)-bytesBefore[i])<<" "<<(star_vlq_call_count(i)-vlqBefore[i])<<"\n";
 Stream nativeObserver;std::cerr<<"native-observer "<<(int)nativeObserver.byteOrder()<<" "<<nativeObserver.streamCompatibilityVersion()<<"\n";
 return result;
}
''')
    # Bind the real private adapter, never the P1 C++ controller or duplicate ABI.
    protocol=(HERE/'host_contract_test.cpp').read_text()
    protocol=protocol.replace('#include "host_contract.cpp"', '#include "StarDataStreamHost.hpp"\nusing data_stream_lab_host=StarDataStreamHost;\nstatic uint32_t data_stream_lab_run(uint32_t m,void*c,StarDataStreamHost h){return star_data_stream_run(m,c,h);}',1)
    protocol=protocol.replace('using namespace Star::DataStreamLab;','using namespace Star::DataStreamRust;')
    line=' assert(data_stream_lab_run(0,nullptr,foreignThrow)==3);'
    assert protocol.count(line)==1
    protocol=protocol.replace(line,' // C++ foreign unwind intentionally excluded from the Rust ABI test.')
    protocol=protocol.replace('cpp-only foreign callback containment: PASS (not Rust proof)', 'C++ foreign callback test OMITTED (no foreign unwind across Rust)')
    protocol_source=generate('protocol.cpp',protocol)
    source_variants={'selected':CORE,'native-bypass':HERE/'StarDataStream.original.cpp',
                     'suppressed-receipt':CORE,'wrong-pending':CORE}
    source=CORE.read_text();needle='execute(DS_GET_ORDER,c);'
    assert source.count(needle)==1,'selected source control needs exact getter contract'
    source_variants['selected-getter-bypass']=generate('selected-getter-bypass.cpp',source.replace(needle,'c.result=uint32_t(m_byteOrder);'))
    def compile(name,source,protocol=False):
        exe=out/name
        defines=selected+([] if protocol else ['-Dstar_data_stream_run=data_stream_observed_run'])
        obj=out/(name+'.o')
        dep=out/(name+'.d')
        run([link['compiler'],*flags,*defines,'-M','-MF',dep,source],name+'-deps')
        for namepath in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):
            p=Path(namepath);p=p if p.is_absolute() else ROOT/p
            key=str(p.resolve())
            if key not in generated:
                digest=sha(p)
                assert key not in bindings or bindings[key]==digest,'dependency drift '+key
                bindings[key]=digest
        run([link['compiler'],*flags,*defines,'-c',source,'-o',obj],name+'-object')
        generated[str(obj)]=sha(obj)
        command=[link['compiler'],*flags,*selected]
        if not protocol:
            command += [driver,wrapper]
            if name=='wrong-pending':command+=['-DWRONG_PENDING']
            if name=='suppressed-receipt':command+=['-DSUPPRESS_RECEIPT']
        command += [obj]
        if protocol:command += [CORE]
        command += [link['archive'],a.archive,*link['libraries'],'-Xlinker','-map','-Xlinker',out/(name+'.map'),'-o',exe]
        run(command,name+'-compile');binaries[str(exe)]=sha(exe)
        maptext=(out/(name+'.map')).read_text(errors='replace')
        assert 'StarDataStream.cpp.o)' not in maptext,'original archive member pulled'
        return exe
    for index,source in enumerate((driver,wrapper,protocol_source)):
        dep=out/f'input-{index}.d'
        run([link['compiler'],*flags,*selected,'-M','-MF',dep,source],f'input-deps-{index}')
        for namepath in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):
            p=Path(namepath);p=p if p.is_absolute() else ROOT/p;key=str(p.resolve())
            if key not in generated:
                digest=sha(p)
                assert key not in bindings or bindings[key]==digest,'input dependency drift '+key
                bindings[key]=digest
    (out/'before.json').write_text(json.dumps(bindings,indent=2)+'\n')
    original=(a.values/'original.stdout').read_bytes();anchors(original)
    for name,path in source_variants.items():
        got=run([compile(name,path)],name)
        assert got==original,'value-equivalent control/candidate stream differs: '+name
        assert anchors(got)==683
        if name=='selected':assert run([out/name],'repeat')==got
    run([compile('protocol',protocol_source,True)],'protocol')
    after={p:sha(p) for p in bindings}
    assert after==bindings,'source drift'
    for p in out.glob('*.map'):generated[str(p)]=sha(p)
    for p in out.glob('*.d'):generated[str(p)]=sha(p)
    assert all(sha(p)==h for p,h in {**generated,**binaries}.items())
    # Persist all transitives discovered before their compilation.
    (out/'before.json').write_text(json.dumps(bindings,indent=2)+'\n')
    (out/'after.json').write_text(json.dumps(after,indent=2)+'\n')
    report=dict(status='FINITE_ACTUAL_RUST_DATA_STREAM_PASS',cases=683,definitions=51,
                ordered_sha256=EXPECTED,bindings=bindings,generated=generated,binaries=binaries,
                receipts=receipts,native_report=str((a.values/'report.json').resolve()),
                rust_archive=str(a.archive.resolve()),rust_archive_sha256=a.archive_sha256,
                controls=['native-bypass','suppressed-receipt','wrong-pending','selected-getter-bypass'],
                limits=['Finite compiled51 boundary; native ownership and header templates retained',
                        'No application, allocator, destructor, platform or whole-engine qualification',
                        'Foreign C++ unwind omitted; no ASan credit'])
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    from verify_candidate import verify
    print(json.dumps(verify(out/'report.json'),sort_keys=True))

if __name__=='__main__':main()
