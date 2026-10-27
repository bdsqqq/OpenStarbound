#!/usr/bin/env python3
"""Finite CURRENT-production TTL runtime against frozen native corpus/lifetimes.
No model/domain/flags/golden mutation, Cargo, game-source edit, or game claim.
"""
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import time
from game_syntax import unchanged, subset
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'build/ttl-production-runtime-r2'
DEADLINE = dt.datetime(2026, 10, 27, 20, 14, tzinfo=dt.timezone.utc).timestamp()

def need(ok, why):
    if not ok: raise AssertionError(why)
def providers(actual, expected):
    need(len(expected)==113 and actual==expected,'EXACT fresh 113 Core/extern providers before any compiler')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p, v):
    with Path(p).open('x') as f:
        json.dump(v, f, indent=2, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
def command(name, argv, witness, stdin=b''):
    unchanged(witness)
    prefix=OUT/name
    need(not prefix.with_suffix('.receipt.json').exists(), 'immutable command prefix')
    need(time.time()<DEADLINE-2, 'unit deadline')
    env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin',HOME=str(OUT),TMPDIR=str(OUT),LANG='C',LC_ALL='C',PYTHONDONTWRITEBYTECODE='1')
    Path(str(prefix)+'.stdin').write_bytes(stdin)
    dump(str(prefix)+'.plan.json',dict(argv=argv,env=env,stdinSha256=sha(str(prefix)+'.stdin')))
    started=dt.datetime.now(dt.timezone.utc).isoformat()
    with open(str(prefix)+'.stdin','rb') as inp,open(str(prefix)+'.stdout','wb') as stdout,open(str(prefix)+'.stderr','wb') as stderr:
        child=subprocess.Popen(argv,cwd=ROOT,env=env,stdin=inp,stdout=stdout,stderr=stderr,start_new_session=True)
        dump(str(prefix)+'.started.json',dict(pid=child.pid,pgid=os.getpgid(child.pid),started=started))
        timeout=False
        try: code=child.wait(timeout=min(120,DEADLINE-time.time()))
        except subprocess.TimeoutExpired:
            timeout=True;os.killpg(child.pid,signal.SIGKILL);code=child.wait()
        try:os.killpg(child.pid,0);gone=False;os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:gone=True
    dump(str(prefix)+'.receipt.json',dict(pid=child.pid,returncode=code,timedOut=timeout,groupGone=gone,started=started,ended=dt.datetime.now(dt.timezone.utc).isoformat(),stdoutSha256=sha(str(prefix)+'.stdout'),stderrSha256=sha(str(prefix)+'.stderr')))
    need(code==0 and gone and not timeout, 'native command failed: '+name)
    unchanged(witness)
    return Path(str(prefix)+'.stdout').read_bytes()

def main():
    need(not OUT.exists(), 'fresh finite runtime root')
    OUT.mkdir()
    global_plan=ROOT/'build/ttl-game-build-r2/plan.json'
    need(sha(global_plan)=='4081266de8115175a453dbae83ef0283457315308b76fbf1eca2655490fa7698','accepted full build admission')
    admission=json.loads(global_plan.read_text()); witness=admission['witness']
    spec=importlib.util.spec_from_file_location('frozen_ttl_native_model',ROOT/'source/lab/ttl-cache/model.py')
    model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
    corpus=('\n'.join(model.corpus())+'\n').encode();expected=model.expected(model.corpus()).encode()
    need(corpus==(ROOT/'build/ttl-cache-native-r1/corpus.tsv').read_bytes(),'unchanged corpus')
    need(expected==(ROOT/'build/ttl-cache-native-r1/expected.tsv').read_bytes(),'unchanged independent model')
    native=(ROOT/'source/lab/ttl-cache/native.cpp').read_text()
    need(native.count('#include "StarTtlCache.original.hpp"')==1,'single driver include derivation')
    native=native.replace('#include "StarTtlCache.original.hpp"','#include "production-scripted.hpp"')
    (OUT/'native-derived.cpp').write_text(native)
    (OUT/'production-scripted.hpp').write_bytes((ROOT/'source/core/StarTtlCache.hpp').read_bytes())
    original='''#define TtlCacheBase NativeOriginalTtlCacheBase
#define TtlCache NativeOriginalTtlCache
#define HashTtlCache NativeOriginalHashTtlCache
#include "StarTtlCache.original.hpp"
#undef HashTtlCache
#undef TtlCache
#undef TtlCacheBase
'''
    controls=(ROOT/'source/lab/ttl-rust/controls.inc').read_text()
    controls=controls.replace('TtlBoundaryHost','TtlCacheRust')
    # The production adapter additionally rejects noncanonical incoming native
    # destinations. Keep malformed controls intact; positive/pending requests
    # must use canonical buffers. Root sentinels remain unchanged.
    controls=controls.replace('q.op=SB_TTL_LRU_PTR;out=sentinel;check("native-ptr-bind"','q.op=SB_TTL_LRU_PTR;out=TtlCacheRust::reply();check("native-ptr-bind"')
    controls=controls.replace('q.op=SB_TTL_PAIR_VALUE_BORROW;out=sentinel;check','q.op=SB_TTL_PAIR_VALUE_BORROW;out=TtlCacheRust::reply();check')
    controls=controls.replace('c.pending=saved;out=sentinel;','c.pending=saved;out=TtlCacheRust::reply();auto pendingOriginal=out;')
    controls=controls.replace('C::host(&c,&valid,&out)==1 && !std::memcmp(&out,&sentinel,24)','C::host(&c,&valid,&out)==1 && !std::memcmp(&out,&pendingOriginal,24)')
    controls=controls.replace('valuesUnwind<TtlCache<int,ThrowingValue>>','valuesUnwind<NativeOriginalTtlCache<int,ThrowingValue>>')
    controls=controls.replace('valuesUnwind<HashTtlCache<int,ThrowingValue>>','valuesUnwind<NativeOriginalHashTtlCache<int,ThrowingValue>>')
    controls=controls.replace('BoundaryHashTtlCache','HashTtlCache').replace('BoundaryTtlCache','TtlCache')
    (OUT/'controls-derived.inc').write_text(controls)
    wrapper='''#include <cstring>
#include "StarRustTtlCache.h"
#define main originalTtlMain
#include "native-derived.cpp"
#undef main
'''+original+'''
#ifdef STAR_USE_RUST_TTL_CACHE
#include "controls-derived.inc"
#endif
int main(int argc,char** argv){
#ifdef STAR_USE_RUST_TTL_CACHE
 if(argc==2 && std::string(argv[1])=="controls"){TtlControls::run();return 0;}
#endif
 int result=originalTtlMain(argc,argv);
 std::cerr<<"production-root-counts";
 for(unsigned mode=0;mode<19;++mode){
#ifdef STAR_USE_RUST_TTL_CACHE
 std::cerr<<" "<<sb_ttl_count(mode,0);
#else
 std::cerr<<" 0";
#endif
 }
 std::cerr<<"\\n";return result;
}
'''
    (OUT/'driver.cpp').write_text(wrapper)
    old=json.loads((ROOT/'build/ttl-cache-native-r1/link.plan.json').read_text())['argv']
    first=next(i for i,v in enumerate(old) if v.endswith('.o'))
    template=old[first:]
    plans=[]
    for role in ['reference','candidate']:
        cm=ROOT/('build/behavior/ttl-cache-combined-r1/'+role+'/cmake')
        text=(cm/'build.ninja').read_text()
        block=re.search(r'^build [^ :]*StarRandom\.cpp\.o:[^\n]+\n((?:  [^\n]*\n)+)',text,re.M)[1]
        props=dict(re.findall(r'^  (\w+) = (.*)$',block,re.M))
        flags=shlex.split(props['DEFINES']+' '+props['FLAGS']+' '+props['INCLUDES'])+['-I'+str(ROOT/'source/lab/ttl-cache'),'-I'+str(OUT)]
        compiler=admission['tools']['CMAKE_CXX_COMPILER']
        obj=OUT/(role+'.o');exe=OUT/role
        compile_argv=[compiler,*flags,'-MD','-MF',str(OUT/(role+'.d')),'-c',str(OUT/'driver.cpp'),'-o',str(obj)]
        tail=[]
        for value in template:
            value=value.replace(str(ROOT/'build/behavior/lru-cache-combined-r1/reference/cmake'),str(cm))
            value=value.replace(str(ROOT/'build/ttl-cache-native-r1/native.o'),str(obj))
            value=value.replace(str(ROOT/'build/ttl-cache-native-r1/native.map'),str(OUT/(role+'.map')))
            if value==str(ROOT/'build/ttl-cache-native-r1/native'):value=str(exe)
            tail.append(value)
        if role=='candidate':tail.insert(1,str(cm/'rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a'))
        link_argv=[compiler,*flags,*tail]
        expected_objects={str(p) for directory in ('core','extern') for p in (cm/directory).rglob('*.o')}
        linked_objects={v for v in tail if v.endswith('.o') and v!=str(obj)}
        providers(linked_objects,expected_objects)
        # The failed initial adapter sliced at the fixture object and omitted
        # preceding providers. Reject that coherent plan before execution now.
        missing=set(linked_objects);missing.pop()
        try: providers(missing,expected_objects)
        except AssertionError: pass
        else: raise AssertionError('missing-Core-provider falsifier accepted')
        for path in [cm/'build.ninja',cm/'CMakeCache.txt',*map(Path,[v for v in tail if v.startswith('/') and (v.endswith('.o') or v.endswith('.a')) and v!=str(obj)])]:
            need(path.is_file(),'fresh provider exists '+str(path));witness['files'][str(path.resolve())]=sha(path)
        plans.append(dict(role=role,compile=compile_argv,link=link_argv,exe=str(exe)))
    baseline_inputs=[ROOT/'build/ttl-cache-native-r1'/name for name in ('corpus.tsv','expected.tsv','lifecycle.stdout','link.plan.json')]
    for path in [HERE/'runtime.py',*baseline_inputs,*OUT.glob('*')]:
        if path.is_file():witness['files'][str(path.resolve())]=sha(path)
    dump(OUT/'admission.json',dict(witness=witness,plans=plans,corpusSha256=hashlib.sha256(corpus).hexdigest(),expectedSha256=hashlib.sha256(expected).hexdigest(),scope='actual production methods; exact current header clone only for frozen clock/name proxies; no game claim'))
    results=[]
    baseline_life=(ROOT/'build/ttl-cache-native-r1/lifecycle.stdout').read_bytes()
    for plan in plans:
        role=plan['role'];command(role+'-compile',plan['compile'],witness)
        deps=shlex.split((OUT/(role+'.d')).read_text().replace('\\\n',' ').split(':',1)[1]);subset(deps,witness)
        witness['files'][str((OUT/(role+'.o')).resolve())]=sha(OUT/(role+'.o'))
        command(role+'-link',plan['link'],witness)
        witness['files'][str(Path(plan['exe']).resolve())]=sha(plan['exe'])
        for alias in ['ordered','hash']:
            actual=command(role+'-'+alias,[plan['exe'],alias],witness,corpus)
            need(actual==expected,'production '+role+'/'+alias+' frozen model mismatch')
            counters=(OUT/(role+'-'+alias+'.stderr')).read_text().splitlines()[-1].split()
            need(counters[0]=='production-root-counts' and len(counters)==20,'actual root route counter schema')
            need(all(int(v)>0 for v in counters[1:]) if role=='candidate' else all(int(v)==0 for v in counters[1:]),'all 19 production roots / native OFF')
        life=command(role+'-lifecycle',[plan['exe'],'lifecycle'],witness)
        need(life==baseline_life,'all 68 properties/four full lifecycle traces exact')
        command(role+'-real',[plan['exe'],'real'],witness)
        if role=='candidate':
            checks=command(role+'-controls',[plan['exe'],'controls'],witness)
            rows=[x for x in checks.decode().splitlines() if x.startswith('control\t')]
            need(len(rows)==104 and all(x.endswith('\t1') for x in rows),'104 actual production ABI/unwind controls')
        results.append(dict(role=role,binarySha256=sha(plan['exe']),rows=626,streams=2,properties=68))
    dump(OUT/'report.json',dict(status='PASS_FINITE_CURRENT_PRODUCTION_RUNTIME_NOT_GAME',results=results,admissionSha256=sha(OUT/'admission.json')))
    print(json.dumps(results,indent=2))
if __name__=='__main__':main()
