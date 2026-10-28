#!/usr/bin/env python3
"""Role-aware replay of accepted leaves, not success relabeling of failed producers."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import model
import verify
from map_bytes import sdk_paths
ROOT=verify.ROOT;OUT=verify.OUT;sha=verify.sha;need=verify.need;load=verify.load
EXPECTED={'compiler-version':0,'link-expand':0,'compile-r2':0,'link':0,'native':0,'repeat':0,'lazy-negative':1,'hash-move-only-negative':1,'mutant-compile':0,'mutant-link':0,'mutant':1}
NEW=list(EXPECTED)[2:]

def status(name,p,r,s):
    need(name in EXPECTED and p['expected_returncode']==r['returncode']==EXPECTED[name],'role-specific return code '+name)
    need(type(r['pid'])is int and r['pid']>0 and r['pid']==s['pid']==s['pgid']==r['pgid'],'actual PID/group')
    need(r['reaped']is True and r['group_gone']is True and r['timed_out']is False,'terminal owned group')

def audit(pin):
    base=verify.audit(pin);report=load(OUT/'report.json')
    need(report['commands']==NEW and report['priorAcceptedCommands']==list(EXPECTED)[:2],'exact accepted command membership')
    epochs=report['sourceEpochs']
    def retained(path,h):
        if sha(path)==h:return
        row=epochs.get(path);need(row is not None and row['sha256']==h,'only explicit historical fixture source epoch')
        original=Path(path);copy=Path(row['copy']);need(original.parent==ROOT/'source/lab/id-map' and copy==OUT/'source-before-repair'/original.name and copy.resolve()==copy and copy.stat().st_nlink==1 and sha(copy)==h,'exact retained fixture source only')
    old=load(OUT/'admission.json')
    for path,h in old['witness']['files'].items():retained(path,h)
    for path,target in old['witness']['aliases'].items():need(str(Path(path).resolve(strict=True))==target,'old pointer alias unchanged')
    for name in EXPECTED:
        p=load(OUT/(name+'.plan.json'));r=load(OUT/(name+'.receipt.json'));s=load(OUT/(name+'.started.json'));status(name,p,r,s)
        need(sha(OUT/(name+'.plan.json'))==r['plan_sha256']and sha(OUT/(name+'.stdout'))==r['stdout_sha256']and sha(OUT/(name+'.stderr'))==r['stderr_sha256'],'exact terminal receipt hashes')
        for path,h in p['argv_files'].items():retained(path,h)
        expected_admission='admission.json'if name in report['priorAcceptedCommands']else report['admissionFile']
        need(p['admission_sha256']==sha(OUT/expected_admission),'command admission epoch')
    need(load(OUT/'compile.receipt.json')['returncode']==1,'original failed compile stays failed')
    need('FlatHashTable'in(OUT/'compile.stderr').read_text(),'retained concrete native lazy wall')
    recipe=load(OUT/'recipe.json');need(len(recipe['objects'])==len(set(recipe['objects']))==113 and len(recipe['selectors'])==28 and all(v=='OFF'for _,v in recipe['selectors']),'native profile/providers')
    deps=(OUT/'native-r2.d').read_text().replace('\\\n',' ');need(str(ROOT/'source/core/StarIdMap.hpp')in deps,'actual production header consumed')
    spec=importlib.util.spec_from_file_location('original_idmap_model',OUT/'source-before-repair/model.py');original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
    need(original.CASE_ROWS==model.CASE_ROWS,'all 44 literal case values unchanged by fixture-constraint repair')
    for p,h in report['postprocessorSources'].items():need(sha(p)==h,'postprocessor bytes')
    base.update(status='FINITE_NATIVE_IDMAP_11_TERMINAL_LEAVES_COMPOSED',commands=11,oldFixtureSourceEpochs=True,limits=report['limits'])
    return base

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--report-sha',required=True);a=ap.parse_args()
    def guard(event,args):
        if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.exec'}:raise ValueError('read-only replay forbids process creation')
    sys.addaudithook(guard);print(json.dumps(audit(a.report_sha),indent=2,sort_keys=True))
if __name__=='__main__':main()
