#!/usr/bin/env python3
"""Read-only, subprocess-free replay. It never runs an acquisition procedure."""
import argparse, hashlib, json, sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=ROOT/'build/weighted-pool-native-r1/attempt2'
import model

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def need(b,s):
    if not b:raise AssertionError(s)

def semantics(outputs):
    corpus,expected=model.corpus()
    need(outputs['corpus']==expected,'literal/dyadic model mismatch')
    need(outputs['corpus-repeat']==expected,'repeat mismatch')
    rows=outputs['properties'].splitlines()
    props=[x.split('\t',1)[1] for x in rows if x.startswith('PASS\t')]
    need(props==model.PROPERTIES,'structural/lifecycle property list')
    ranges=[x for x in rows if x.startswith('RANGE\t')]
    need(len(ranges)==3 and len(set(ranges))==1,'native range exception identity/message')
    need('out of range list::at(999)' in ranges[0] and 'OutOfRangeException' in ranges[0],'native exception text/type')
    traces=[x for x in rows if x.startswith('TRACE\t')]
    need(len(traces)==6,'complete raw native lifecycle traces')
    need(any('\tmove:30\tdtor:30' in x and x.startswith('TRACE\tthrow-move\t') for x in traces),'throw move unwind trace')
    need(any(x.startswith('TRACE\tthrow-copy\tcopy:') for x in traces),'select copy trace')
    return {'literal_rows':len(expected.splitlines()),'properties':len(props),'traces':len(traces),'range_leaves':len(ranges)}

def replay(pin):
    need(sha(OUT/'report.json')==pin,'external report pin')
    r=json.loads((OUT/'report.json').read_text())
    for p,h in r['products'].items():need(sha(p)==h,'product drift: '+p)
    admission=json.loads((OUT/'admission.json').read_text())
    for p,h in admission['witness']['files'].items():need(sha(p)==h,'input drift: '+p)
    for p,target in admission['witness']['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'alias drift: '+p)
    need((HERE/'StarWeightedPool.original.hpp').read_text()==(ROOT/'source/core/StarWeightedPool.hpp').read_text().replace('WeightedPool','ReferenceWeightedPool'),'type-only original clone')
    expected=(ROOT/'source/core/StarWeightedPool.hpp').read_text()
    for old,new in [('WeightedPool','ProxyWeightedPool'),('RandomSource','ProxyRandomSource'),('Random::','ProxyRandom::'),('staticRandomDouble','proxyStaticRandomDouble')]:expected=expected.replace(old,new)
    need((HERE/'StarWeightedPool.proxy.hpp').read_text()==expected,'proxy transformation')
    outputs={x:(OUT/(x+'.stdout')).read_text() for x in ['corpus','corpus-repeat','properties']}
    result=semantics(outputs)
    need((OUT/'corpus.tsv').read_text()==model.corpus()[0],'predeclared corpus')
    need((OUT/'expected.tsv').read_text()==model.corpus()[1],'independent expected literals')
    receipts=[]
    for p in OUT.glob('*.receipt.json'):
        q=json.loads(p.read_text());name=p.name[:-len('.receipt.json')]
        need(q['reaped'] and q['group_gone'] and q['pgid']==q['pid'],'terminal process: '+name)
        need(q['returncode']==q['expected_returncode'] and q['timed_out']==q['expected_timeout'],'process expectation: '+name)
        need(q['stdout_sha256']==sha(OUT/(name+'.stdout')) and q['stderr_sha256']==sha(OUT/(name+'.stderr')),'process stdio')
        need(q['plan_sha256']==sha(OUT/(name+'.plan.json')),'process plan')
        receipts.append(name)
    need(set(receipts)==set(r['commands']),'complete exact command set')
    need((OUT/'mutant.stdout').read_text()!=model.corpus()[1],'compiled strict-boundary mutant must differ')
    controls=json.loads((OUT/'controls.json').read_text());need(all(controls.values()),'falsifiers')
    need(sum(p.stat().st_size for p in OUT.parent.rglob('*') if p.is_file())<=64*1024*1024,'cap')
    return dict(result,commands=len(receipts),controls=controls,status='PASS finite native-only calibration; no Rust/game/adoption claim')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report-sha',required=True);a=p.parse_args()
    print(json.dumps(replay(a.report_sha),sort_keys=True,indent=2))
