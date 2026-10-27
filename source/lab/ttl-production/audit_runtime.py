#!/usr/bin/env python3
"""Independent read-only composition, NEVER a success relabel for failed producers."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'build/ttl-production-runtime-r2'
def need(ok,why):
    if not ok:raise AssertionError(why)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def read(p):return Path(p).read_bytes()
def semantic(reader=read):
    expected=reader(ROOT/'build/ttl-cache-native-r1/expected.tsv')
    original=reader(ROOT/'build/ttl-cache-native-r1/lifecycle.stdout')
    need(len(expected.splitlines())==626,'626 frozen rows')
    props=[x for x in original.splitlines() if x.startswith(b'property\t')]
    need(len(props)==68 and all(x.endswith(b'\t1') for x in props),'68 original lifecycle properties')
    coverage=set()
    for role in ('reference','candidate'):
        for alias in ('ordered','hash'):
            need(reader(OUT/(role+'-'+alias+'.stdout'))==expected,'frozen model '+role+'/'+alias)
            fields=reader(OUT/(role+'-'+alias+'.stderr')).decode().splitlines()[-1].split()
            need(fields[0]=='production-root-counts' and len(fields)==20,'counter schema')
            counts=list(map(int,fields[1:]));need(all(v>=0 for v in counts),'nonnegative counters')
            if role=='reference':need(not any(counts),'native OFF root counters')
            else:coverage.update(i for i,v in enumerate(counts) if v>0)
        need(reader(OUT/(role+'-lifecycle.stdout'))==original,'all four complete lifecycle traces '+role)
        smoke=[x.split(b'\t') for x in reader(OUT/(role+'-real.stdout')).splitlines() if x.startswith(b'real-smoke\t')]
        need(len(smoke)==2 and [x[1] for x in smoke]==[b'ordered',b'hash'] and all(int(x[3])>=int(x[2]) for x in smoke),'actual Time/Random smoke')
    inherited=[x for x in reader(OUT/'candidate-controls.stdout').splitlines() if x.startswith(b'control\t')]
    strict=[x for x in reader(OUT/'strict-canonical-run.stdout').splitlines() if x.startswith(b'control\t')]
    need(len(inherited)==98 and all(x.endswith(b'\t1') for x in inherited),'98 inherited native/protocol/unwind checks')
    need(len(strict)==28 and all(x.endswith(b'\t1') for x in strict),'22 canonical guard + six frozen breadth checks')
    need(b'control\tclear-selected\t1' in inherited,'actual production clear selected')
    for role in ('reference','candidate'):
        need(reader(OUT/(role+'-explicit-clear.stdout'))==reader(OUT/'clear-expected.tsv'),'separate explicit clear API state')
        fields=reader(OUT/(role+'-explicit-clear.stderr')).decode().splitlines()[-1].split()
        need(fields[0]=='production-root-counts' and len(fields)==20,'explicit clear counter schema')
        counts=list(map(int,fields[1:]))
        if role=='reference':need(not any(counts),'explicit clear native OFF')
        else:
            need(counts[17]==1,'isolated actual clear root increment, not a prior synthetic protocol call')
            coverage.update(i for i,v in enumerate(counts) if v>0)
    need(coverage==set(range(19)),'all19 roots across actual API processes, without synthetic protocol noise')
    return dict(rows=626,streams=4,supplementalClearRows=4,supplementalClearBackends=2,propertiesPerBackend=68,completeTracesPerBackend=4,controls=126,rootCoverage=sorted(coverage))

def audit():
    need(sha(ROOT/'build/ttl-cache-native-r1/report.json')=='cba3b3c84acc2128bd043400cabd6ed2ebf35fcdde37e6d36e2a870bc7926674','immutable baseline certificate')
    baseline=load(ROOT/'build/ttl-cache-native-r1/report.json')
    for p in (ROOT/'build/ttl-cache-native-r1/expected.tsv',ROOT/'build/ttl-cache-native-r1/lifecycle.stdout'):
        need(sha(p)==baseline['products'][str(p)],'original product pin')
    spec=importlib.util.spec_from_file_location('frozen_model',ROOT/'source/lab/ttl-cache/model.py');model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
    need(model.expected(model.corpus()).encode()==read(ROOT/'build/ttl-cache-native-r1/expected.tsv'),'independent unchanged model regeneration')
    header=ROOT/'source/core/StarTtlCache.hpp';need(sha(header)=='f5e455a98035ead719fbcd7624711a3c767069c3ad75dbadc5cd5e4248f20ec0','production header pin')
    need(read(OUT/'production-scripted.hpp')==read(header),'exact production header copy; no cloned method adaptation')
    native=read(ROOT/'source/lab/ttl-cache/native.cpp').replace(b'#include "StarTtlCache.original.hpp"',b'#include "production-scripted.hpp"')
    need(read(OUT/'native-derived.cpp')==native,'only native driver include substitution')
    clear_rows=['0 new 10000 0 8 0','1 set 1 23 0 0','2 clear 0 0 0 0','3 snapshot 0 0 0 0']
    need(read(OUT/'clear-case.tsv')==('\n'.join(clear_rows)+'\n').encode() and read(OUT/'clear-expected.tsv')==model.expected(clear_rows).encode(),'separately declared clear case, unchanged model')
    for admission in ('admission.json','supplemental-acquisition-admission.json','strict-canonical-admission.json','clear-case-admission.json'):
        witness=load(OUT/admission)['witness']
        for p,h in witness['files'].items():
            if p==str(ROOT/'source/lab/migration/catalog.json'):
                # Superset admission included inventory metadata, NOT consumed
                # by any compiled TU. Retain its exact original bytes, not a pin waiver.
                need(h=='1c337fd6b8ae53502ea5736b52888c0ed5f01a94dbbc0921fd079828a1f384c5' and sha(OUT/'original-1964-catalog.json')==h,'exact original inventory version')
                for dep in ('reference.d','candidate.d','strict-canonical.d'):
                    need(p not in (OUT/dep).read_text(),'inventory must NOT be consumed C++ input')
            else:need(sha(p)==h,'preadmitted input '+p)
        for p,resolved in witness['aliases'].items():need(str(Path(p).resolve(strict=True))==resolved,'preadmitted alias')
    successful=[];failed=[]
    for p in sorted(OUT.glob('*.receipt.json')):
        name=p.name.removesuffix('.receipt.json');receipt=load(p);plan=load(OUT/(name+'.plan.json'));started=load(OUT/(name+'.started.json'))
        need(type(receipt['pid'])is int and receipt['pid']>0 and receipt['pid']==started['pid']==started['pgid'],'typed actual process binding')
        need(receipt['started']==started['started'] and receipt['ended']>=receipt['started'] and receipt['groupGone']is True and receipt['timedOut']is False,'actual normal reaping/clock')
        for ext in ('stdout','stderr'):need(sha(OUT/(name+'.'+ext))==receipt[ext+'Sha256'],'raw stdio pin')
        need(sha(OUT/(name+'.stdin'))==plan['stdinSha256'],'actual stdin pin')
        if name=='strict-abi-compile':need(receipt['returncode']==1,'failed ambiguity remains failed');failed.append(name)
        else:need(type(receipt['returncode'])is int and receipt['returncode']==0,'successful leaf');successful.append(name)
    need(len(successful)==18 and failed==['strict-abi-compile'],'exact composed leaf membership; no failure relabel')
    for role in ('reference','candidate'):
        argv=load(OUT/(role+'-link.plan.json'))['argv'];cm=ROOT/('build/behavior/ttl-cache-combined-r1/'+role+'/cmake')
        expected={str(p) for d in ('core','extern') for p in (cm/d).rglob('*.o')}
        actual={p for p in argv if p.endswith('.o') and p!=str(OUT/(role+'.o'))}
        need(len(expected)==113 and actual==expected,'exact fresh linked Core/extern provenance')
        if role=='candidate':
            archive=cm/'rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a'
            need(str(archive) in argv and sha(archive)=='65d1a8af9061c7581d5f7bb73a54c6f70f41d34abcba775a7359ab29033cac82','current physical canonical Rust provider')
    result=semantic()
    negatives=[]
    def reject(name,path,data):
        try:semantic(lambda p:data if Path(p)==path else read(p))
        except AssertionError:negatives.append(name)
        else:raise AssertionError('coherent falsifier accepted '+name)
    reject('changed-frozen-result',OUT/'candidate-hash.stdout',read(OUT/'candidate-hash.stdout').replace(b'\t',b'\t999',1))
    reject('missing-clear',OUT/'candidate-controls.stdout',read(OUT/'candidate-controls.stdout').replace(b'clear-selected\t1',b'clear-selected\t0'))
    reject('changed-full-lifetime-trace',OUT/'candidate-lifecycle.stdout',read(OUT/'candidate-lifecycle.stdout')+b'trace\tchanged\tstill-well-formed\n')
    reject('canonical-guard-false',OUT/'strict-canonical-run.stdout',read(OUT/'strict-canonical-run.stdout').replace(b'canonical-stage-capability\t1',b'canonical-stage-capability\t0'))
    counters=read(OUT/'candidate-explicit-clear.stderr').decode().split()
    counters[18]='0'
    reject('actual-clear-route-missing-despite-synthetic-clear-control',OUT/'candidate-explicit-clear.stderr',(' '.join(counters)+'\n').encode())
    need(semantic()==result,'positive replay after isolated semantic falsifiers')
    return dict(status='FINITE_CURRENT_PRODUCTION_RUNTIME_BY_INDEPENDENT_COMPOSITION_NOT_GAME',semantic=result,successfulLeaves=successful,failedLeavesRetained=failed,monolithicProducerR1andR2RemainExit1=True,falsifiers=negatives,verifierSha256=sha(__file__),nonConsumedInventoryOriginalBytesRetained='1c337fd6b8ae53502ea5736b52888c0ed5f01a94dbbc0921fd079828a1f384c5',limitations=['not monolithic whole-run success','not actual game adoption','no performance/platform/OOM/universal/concurrency qualification'])
if __name__=='__main__':
    report=audit()
    if len(sys.argv)==3 and sys.argv[1]=='--report-sha':
        need(sha(OUT/'independent-report-v3.json')==sys.argv[2] and load(OUT/'independent-report-v3.json')==report,'immutable composed report')
    print(json.dumps(report,indent=2,sort_keys=True))
