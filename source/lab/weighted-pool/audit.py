#!/usr/bin/env python3
"""Read-only partial-baseline replay: no subprocess, compiler, or acquisition.

A successful replay explicitly keeps both monolithic producers FAILED and the
callback/full-expression/NRVO/reentry gate unresolved. No port is accepted.
"""
import argparse,copy,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];BASE=ROOT/'build/weighted-pool-native-r1';OLD=BASE/'attempt2';OUT=BASE/'orthogonal'
sys.path.insert(0,str(HERE));import model
REAL_PROPERTIES=['real-source-empty-consumption','real-global-empty-consumption',
 'real-global-unique-empty-consumption','real-static-empty','real-container-accessors',
 'real-static-128-quarter-model','real-reference-128-parity-and-uniques',
 'real-source-32-index-and-select','real-global-nonempty-routes','real-copy-move-clear-reuse',
 'real-native-range-type-message','real-nondefault-moveonly-lazy',
 'real-add-throw-identity-reuse','real-select-copy-throw-identity','real-value-balanced-destruction']

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def need(b,s):
    if not b:raise AssertionError(s)
def data():
    return dict(corpus=(OLD/'corpus.stdout').read_text(),repeat=(OLD/'corpus-repeat.stdout').read_text(),
      real=(OUT/'real.stdout').read_text(),partial=(OLD/'properties.stdout').read_text(),
      mutant=(OUT/'mutant.stdout').read_text(),first=json.loads((BASE/'properties.receipt.json').read_text()),
      second=json.loads((OLD/'properties.receipt.json').read_text()))
def evaluate(d):
    expected=model.corpus()[1];need(d['corpus']==expected and d['repeat']==expected,'literal/dyadic model')
    props=[x.split('\t',1)[1] for x in d['real'].splitlines() if x.startswith('PASS\t')]
    need(props==REAL_PROPERTIES,'orthogonal real property coverage')
    partial=[x.split('\t',1)[1] for x in d['partial'].splitlines() if x.startswith('PASS\t')]
    need(partial==model.PROPERTIES[:8],'partial failed properties: ONLY eight accepted')
    need(d['first']['returncode']==-11 and d['second']['returncode']==1,'original failed process truth')
    rows=[x.split('\t') for x in d['real'].splitlines() if x.startswith('SEED\t')]
    need(len(rows)==128 and [int(x[1]) for x in rows]==list(range(128)),'all128 real seeds')
    for _,s,t,i in rows:
        target=float.fromhex(t);want=0 if target<=.25 else 1 if target<=.5 else 2 if target<=.75 else 3
        need(int(i)==want,'independent quarter thresholds')
    ranges=[x for x in d['real'].splitlines() if x.startswith('RANGE\t')]
    need(len(ranges)==3 and len(set(ranges))==1,'three actual range leaves')
    need(ranges[0].endswith('\t(OutOfRangeException) out of range list::at(999)') and 'OutOfRangeException' in ranges[0],'native exception identity/what')
    counters=[x.split('\t')[1:] for x in d['real'].splitlines() if x.startswith('COUNTS\t')]
    need(len(counters)==1,'native lifecycle counters');c=list(map(int,counters[0]));need(c[0]>=3 and c[1]>=3 and c[2]>=3 and c[3]==2,'callback-free native unwind accounting')
    need(d['mutant']!=expected,'compiled strict-< mutant must fail literal model')
    return dict(literal_rows=27,literal_streams=2,partial_properties=8,real_properties=15,real_static_seeds=128,source_draws=64,range_leaves=3,original_definition_inventory=19,fields=2,lifecycle_observer_gate='UNRESOLVED; no third attempt')
def semantics():return evaluate(data())
def controls():
    good=data();evaluate(good);out={}
    cases={
      'wrong_literal':dict(good,corpus=good['corpus'].replace('0\n','1\n',1)),
      'missing_real_property':dict(good,real=good['real'].replace('PASS\treal-static-empty\n','')),
      'failed_producer_relabel':dict(good,second=dict(good['second'],returncode=0)),
      'wrong_native_exception':dict(good,real=good['real'].replace('out of range list::at(999)','range changed')),
      'compiled_semantic_mutant':dict(good,corpus=good['mutant'])}
    for name,bad in cases.items():
        try:evaluate(bad)
        except AssertionError:out[name+'_rejected']=True
        else:raise AssertionError('falsifier accepted: '+name)
    w=json.loads((OLD/'admission.json').read_text())['witness']['files'];header=str(ROOT/'source/core/StarWeightedPool.hpp');bad=dict(w);del bad[header]
    try:need(header in bad,'missing consumed header')
    except AssertionError:out['missing_consumed_header_rejected']=True
    else:raise AssertionError('missing header accepted')
    return out

def replay(pin):
    need(sha(OUT/'report.json')==pin,'external report SHA required')
    r=json.loads((OUT/'report.json').read_text());need(r['status'].startswith('PARTIAL_NATIVE_BASELINE'),'truthful partial status')
    for p,h in r['products'].items():need(sha(p)==h,'product drift: '+p)
    admission=json.loads((OUT/'admission.json').read_text());need(sha(admission['base_admission'])==admission['base_admission_sha256'],'base admission pin')
    for p,h in admission['delta'].items():need(sha(p)==h,'supplement source drift: '+p)
    w=json.loads((OLD/'admission.json').read_text())['witness']
    for p,h in w['files'].items():need(sha(p)==h,'original input drift: '+p)
    for p,target in w['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'alias drift: '+p)
    header=(ROOT/'source/core/StarWeightedPool.hpp').read_text();need(header.count('WeightedPool<Item>::')==19,'all19 definition inventory')
    need((BASE/'StarWeightedPool.raw.hpp').read_text()==header,'original exact raw copy')
    need((HERE/'StarWeightedPool.original.hpp').read_text()==header.replace('WeightedPool','ReferenceWeightedPool'),'name-only original clone')
    proxy=header
    for a,b in [('WeightedPool','ProxyWeightedPool'),('RandomSource','ProxyRandomSource'),('Random::','ProxyRandom::'),('staticRandomDouble','proxyStaticRandomDouble')]:proxy=proxy.replace(a,b)
    need((HERE/'StarWeightedPool.proxy.hpp').read_text()==proxy,'exact mechanical dependency proxy')
    commands=[]
    for directory in [BASE,OLD,OUT]:
        for p in directory.glob('*.receipt.json'):
            q=json.loads(p.read_text());name=p.name[:-len('.receipt.json')]
            need(q['reaped'] and q['group_gone'] and q['pgid']==q['pid'],'process terminal: '+str(p))
            need(q['stdout_sha256']==sha(directory/(name+'.stdout')) and q['stderr_sha256']==sha(directory/(name+'.stderr')),'raw stdio drift')
            need(q['plan_sha256']==sha(directory/(name+'.plan.json')),'process plan drift')
            plan=json.loads((directory/(name+'.plan.json')).read_text());need(plan['stdin_sha256']==sha(directory/(name+'.stdin')),'stdin pin')
            if name=='properties' and directory in [BASE,OLD]:need(q['returncode']==(-11 if directory==BASE else 1),'failed producer relabel')
            else:need(q['returncode']==q['expected_returncode'] and q['timed_out']==q['expected_timeout'],'command expectation')
            commands.append(str(p))
    need(len(commands)==23,'exact7+7+9 actual command receipts')
    nonprogress=json.loads((OUT/'nonprogress.receipt.json').read_text());need(nonprogress['timed_out'] and nonprogress['returncode']==-9,'nontermination diagnostic expected timeout')
    need('deleted' in (OUT/'lazy-negative.stderr').read_text(),'actual negative lazy compile')
    result=semantics();need(controls()==r['controls'],'isolated verifier controls')
    size=sum(p.stat().st_size for p in BASE.rglob('*') if p.is_file());need(size<=64*1024*1024,'original whole-root cap')
    return dict(result,receipts=len(commands),controls=r['controls'],whole_root_bytes=size,status=r['status'])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report-sha',required=True);a=p.parse_args();print(json.dumps(replay(a.report_sha),sort_keys=True,indent=2))
