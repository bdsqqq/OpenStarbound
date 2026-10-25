#!/usr/bin/env python3
"""Independent finite artifact/route checks. Metadata corruptions are synthetic."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from run import anchors
from verify_receipts import verify as verify_native

EXPECTED='5ee512e3a91027823f34c47df4d1e056753e0fd61f03a9ad70e65131900763ab'
CONTROLS={'native-bypass','suppressed-receipt','wrong-pending','selected-getter-bypass'}


def need(ok,message):
    if not ok:raise ValueError(message)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def observations(data):
    counts={};routes={};deps={};native=[]
    for line in data.decode().splitlines():
        fields=line.split()
        if not fields:continue
        kind=fields[0]
        if kind in ('count','route','dependency'):
            target={'count':counts,'route':routes,'dependency':deps}[kind]
            nums=list(map(int,fields[1:]));key=nums[0]
            need(key not in target,'duplicate counter')
            target[key]=nums[1:]
        elif kind=='native-observer':native.append(list(map(int,fields[1:])))
        else:need(False,'unrecognized executable stderr')
    need(set(counts)==set(range(51)) and all(len(v)==3 for v in counts.values()),'51x3 counts')
    need(set(routes)==set(range(51)) and all(len(v)==4 for v in routes.values()),'51x4 routes')
    need(set(deps)==set(range(6)) and all(len(v)==2 for v in deps.values()),'dependency shape')
    need(native==[[0,21]],'actual native observer')
    return counts,routes,deps


def qualify(data):
    counts,routes,deps=observations(data)
    for mode,(attempt,success,pending) in counts.items():
        need(attempt>0 and success>0 and attempt==success+pending,'mode balance/coverage '+str(mode))
        need(routes[mode]==[success,pending,0,0],'returned-status route '+str(mode))
    # Source-derived fault reach: explicit partial primitives, bool read fault,
    # malformed/EOF VLQ, write-prefix failures, stdstring/temp/array reads.
    fault_modes={13,22,25,*range(26,34),34,37,38,39,44,47,48,49,50}
    need(all(counts[m][2]>0 for m in fault_modes),'source exception paths absent')
    # Production typed Bytes calls use to-copy=3/from-copy=5. Native VLQ
    # templates route writeU/readU/writeI/readI through operations0/2/3/5.
    need(deps[3][0]>0 and deps[5][0]>0,'directional Bytes route')
    need(all(deps[m][1]>0 for m in (0,2,3,5)),'VLQ lower dependency route')
    # Bool writes, framing, and native function iterators dispatch migrated u8.
    need(counts[13][0]>counts[10][0] and counts[25][0]>counts[37][0], 'child byte dispatch')
    return counts


def _verify(report,folder):
    need(report['status']=='FINITE_ACTUAL_RUST_DATA_STREAM_PASS','status')
    need(report['cases']==683 and report['definitions']==51,'scope')
    verify_native(report['native_report'])
    before=json.loads((folder/'before.json').read_text());after=json.loads((folder/'after.json').read_text())
    need(before==after==report['bindings'],'binding maps disagree')
    for group in ('bindings','generated','binaries'):
        need(bool(report[group]),'empty '+group)
        for p,h in report[group].items():need(sha(p)==h,group+' drift '+p)
    need(sha(report['rust_archive'])==report['rust_archive_sha256'],'Rust archive drift')
    receipts=json.loads((folder/'receipts.json').read_text())
    need(receipts==report['receipts'],'receipt copies disagree')
    names=set();executed=set()
    for r in receipts:
        need(r['name'] not in names and r['returncode']==0,'failed/duplicate execution')
        names.add(r['name']);exe=str(Path(r['command'][0]).resolve());executed.add(exe)
        need(sha(exe)==r['executable_sha256'],'executed binary drift')
        for stream in ('stdout','stderr'):
            need(sha(folder/(r['name']+'.'+stream))==r[stream+'_sha256'],'command output drift')
    need(set(report['binaries'])<=executed,'unexecuted binary')
    data=(folder/'selected.stdout').read_bytes()
    need(hashlib.sha256(data).hexdigest()==report['ordered_sha256']==EXPECTED,'ordered digest')
    need(anchors(data)==683 and (folder/'repeat.stdout').read_bytes()==data,'literal/repeat')
    baseline=qualify((folder/'selected.stderr').read_bytes())
    need(qualify((folder/'repeat.stderr').read_bytes())==baseline,'counter repeat')
    need(set(report['controls'])==CONTROLS,'control scope')
    for control in CONTROLS:
        need(control in names and (folder/(control+'.stdout')).read_bytes()==data,'control value equivalence')
        observed=(folder/(control+'.stderr')).read_bytes()
        observations(observed)
        try:qualify(observed)
        except ValueError:pass
        else:raise ValueError('normally exiting route control escaped '+control)
    need(b'PASS' in (folder/'protocol.stdout').read_bytes()
         and b'OMITTED' in (folder/'protocol.stdout').read_bytes(),'selected private protocol')
    for p in report['generated']:
        if p.endswith('.map'):
            need('StarDataStream.cpp.o)' not in Path(p).read_text(errors='replace'),'original archive bypass')
    return dict(status=report['status'],records=683,definitions=51,
                bindings=len(before),binaries=len(report['binaries']),commands=len(receipts),
                controls=sorted(CONTROLS))


def verify(path):
    p=Path(path).resolve();return _verify(json.loads(p.read_text()),p.parent)


def self_test(path):
    p=Path(path).resolve();report=json.loads(p.read_text());_verify(report,p.parent)
    mutations={
        'scope':lambda r:r.update(cases=682),
        'ordered':lambda r:r.update(ordered_sha256='0'*64),
        'binding':lambda r:r['bindings'].__setitem__(next(iter(r['bindings'])),'0'*64),
        'generated':lambda r:r['generated'].__setitem__(next(iter(r['generated'])),'0'*64),
        'binary':lambda r:r['binaries'].__setitem__(next(iter(r['binaries'])),'0'*64),
        'archive':lambda r:r.update(rust_archive_sha256='0'*64),
        'receipt':lambda r:r['receipts'][0].update(executable_sha256='0'*64),
        'control':lambda r:r['controls'].pop()}
    detected=[]
    for name,mutate in mutations.items():
        bad=deepcopy(report);mutate(bad)
        try:_verify(bad,p.parent)
        except ValueError:detected.append(name)
        else:raise ValueError('synthetic metadata corruption escaped '+name)
    # Isolated in-memory counter corruptions test route decisions separately
    # from hash checks; none is presented as a compiled execution.
    raw=(p.parent/'selected.stderr').read_bytes()
    for name,bad in [('zero-count',raw.replace(b'count 0 ',b'count 99 ',1)),
                     ('unknown-route',raw.replace(b'route 0 ',b'route 99 ',1))]:
        try:qualify(bad)
        except ValueError:detected.append(name)
        else:raise ValueError('synthetic counter corruption escaped '+name)
    return detected


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--report',required=True,type=Path)
    ap.add_argument('--self-test',action='store_true');a=ap.parse_args()
    result=verify(a.report)
    if a.self_test:result['syntheticIntegrityControls']=self_test(a.report)
    print(json.dumps(result,sort_keys=True))
