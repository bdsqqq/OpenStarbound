#!/usr/bin/env python3
"""Orthogonal callback-free acquisition; both monolithic failures stay failed.

No third lifecycle attempt. Reuses immutable existing binary for previously
unexecuted diagnostics; new TU covers independent real dependencies/compile
contracts, not the stopped destructor-observer assertion.
"""
import hashlib,json,sys,time,signal,shlex
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];BASE=ROOT/'build/weighted-pool-native-r1';OLD=BASE/'attempt2';OUT=BASE/'orthogonal'
sys.path.insert(0,str(HERE));import run,model,audit
sha=run.sha;dump=run.dump;need=run.need

def cap():
    need(time.time()<run.DEADLINE,'original hard deadline')
    need(sum(p.stat().st_size for p in BASE.rglob('*') if p.is_file())<64*1024*1024,'original whole-root 64MiB cap')

def main():
    need(not OUT.exists(),'fresh orthogonal root');OUT.mkdir();(OUT/'home').mkdir();(OUT/'tmp').mkdir()
    run.OUT=OUT;run.cap=cap
    witness=json.loads((OLD/'admission.json').read_text())['witness'];run.unchanged(witness)
    r=json.loads((OLD/'recipe.json').read_text());c=r['compiler'];flags=[*r['flags'],'-I'+str(HERE),'-I'+str(OLD)]
    mutant='''#include "StarSet.hpp"
#include "StarWeightedPool.hpp"
#include <iostream>
namespace Star {
struct ProxyRandomSource {double value=0; double randd(){return value;}};
namespace ProxyRandom {double randd(){return 0;} uint64_t randu64(){return 0;}}
double proxyStaticRandomDouble(uint64_t seed){return double(seed&7)/8;}
}
#include "StarWeightedPool.mutant.hpp"
int main(){size_t n;while(std::cin>>n){Star::ProxyWeightedPool<int> p;for(size_t i=0;i<n;++i){double w;std::cin>>w;p.add(w,int(i));}double target;std::cin>>target;Star::ProxyRandomSource r;r.value=target;auto index=p.selectIndex(r);if(index==Star::NPos)std::cout<<-1;else std::cout<<index;std::cout<<'\\n';}}
'''
    (OUT/'mutant.cpp').write_text(mutant)
    sourcefiles=[HERE/'supplement.cpp',HERE/'supplement.py',HERE/'audit.py',OUT/'mutant.cpp']
    delta={str(p):sha(p) for p in sourcefiles}
    dump(OUT/'admission.json',dict(base_admission=str(OLD/'admission.json'),base_admission_sha256=sha(OLD/'admission.json'),delta=delta,scope='new callback-free real/compile contracts plus previously unexecuted immutable-binary diagnostics; NO stopped lifecycle retry',deadline=run.DEADLINE))
    def command(*args,**kwargs):
        run.unchanged(witness)
        for p,h in delta.items():need(sha(p)==h,'new source drift')
        return run.command(*args,**kwargs)
    command('compile',[c,*flags,'-MD','-MF',OUT/'supplement.d','-c',HERE/'supplement.cpp','-o',OUT/'supplement.o'])
    deps=shlex.split((OUT/'supplement.d').read_text().replace('\\\n',' ').split(':',1)[1]);combined=dict(files={**witness['files'],**delta});run.subset(deps,combined)
    # Linker trace/map options are metadata-only and omitted here to stay under
    # the ORIGINAL whole-root cap; actual compiler/native math flags unchanged.
    link=[c,*flags,*r['objects'],str(OUT/'supplement.o'),*r['libraries'],'-Wl,-dead_strip','-o',str(OUT/'supplement')]
    command('link',link);command('real',[OUT/'supplement'])
    command('diagnostics',[OLD/'native','diagnostics'])
    command('nonprogress',[OLD/'native','hang'],expected=-signal.SIGKILL,timeout=.25,expected_timeout=True)
    command('lazy-negative',[c,*flags,'-fsyntax-only',OLD/'lazy-negative.cpp'],expected=1)
    need('deleted' in (OUT/'lazy-negative.stderr').read_text(),'negative compile reason')
    command('mutant-compile',[c,*flags,'-c',OUT/'mutant.cpp','-o',OUT/'mutant.o'])
    mlink=[str(x).replace(str(OUT/'supplement.o'),str(OUT/'mutant.o')) for x in link];mlink[-1]=str(OUT/'mutant');command('mutant-link',mlink)
    command('mutant',[OUT/'mutant'],model.corpus()[0].encode())
    run.unchanged(witness)
    sdk=witness # full actual preadmitted SDK was captured in attempt2
    before=json.loads((OLD/'sdk-before.json').read_text());sdk_after=run.sdk_witness.capture(before['requested_root'],before['canonical_root']);need(before==sdk_after,'SDK drift');dump(OUT/'sdk-after.json',sdk_after)
    controls=audit.controls();dump(OUT/'controls.json',controls)
    paths=run.re.findall(r'^\[\s*\d+\] (.*\.tbd)$',(OLD/'native.map').read_text(),run.re.M)
    need(paths,'actual reference-linked tbd map');dump(OUT/'sdk-consumed.json',run.sdk_witness.reconcile_consumed(before,paths,requested_root=before['requested_root'],expected_canonical_root=before['canonical_root']))
    result=audit.semantics();result.update(status='PARTIAL_NATIVE_BASELINE; stopped lifecycle observer gate UNRESOLVED; both monolithic producers FAILED',commands=run.COMMANDS,base_admission_sha256=sha(OLD/'admission.json'),admission_sha256=sha(OUT/'admission.json'),controls=controls,whole_root_bytes_before_report=sum(p.stat().st_size for p in BASE.rglob('*') if p.is_file()),failed_monolithic_attempts=2)
    # Bind failures and raw outputs too. Never relabel an original process status.
    result['products']={str(p):sha(p) for p in BASE.rglob('*') if p.is_file() and p.name!='report.json'}
    dump(OUT/'report.json',result);cap();print('PARTIAL_REPORT',sha(OUT/'report.json'))
if __name__=='__main__':main()
