#!/usr/bin/env python3
"""Final native-only acceptance: strict control parsing and paired implementation proof."""
import argparse
import json
from pathlib import Path
import full_stage
import stage
import trace_contract as contract


def rows(data):
    def pairs(items):
        out={}
        for key,value in items:
            stage.need(key not in out,'duplicate native observation key')
            out[key]=value
        return out
    def invalid(value):raise ValueError('nonfinite observation '+value)
    return [json.loads(line,object_pairs_hook=pairs,parse_constant=invalid)
            for line in data.decode('ascii').splitlines()]


def verify(report,paired):
    report=Path(report).resolve();paired=Path(paired).resolve()
    result=full_stage.verify_execution(report)
    r=stage.load(report);q=stage.load(paired)
    stage.need(r['controls']==['reference-eof','paired-reference-eof'],'full control labels')
    stage.need(q['status']=='FINITE_NATIVE_IODEVICE_CALIBRATION_PASS' and type(q['cases']) is int
               and q['cases']==8021 and type(q['definitions']) is int and q['definitions']==22
               and q['canonical_expected_sha256']==full_stage.EXPECTED_SHA
               and q['paired_wrong_original_reference'] is True,'paired audit scope')
    for group in ('bindings','generated'):
        for path,digest in q[group].items():stage.need(stage.sha(path)==digest,'paired audit binding '+path)
    stage.need(q['receipts']==stage.load(paired.parent/'receipts.json'),'paired audit receipt copies')
    stage.need([x['name'] for x in q['receipts']]==['compile','link','original-eof'],'paired command scope')
    for receipt in q['receipts']:
        stage.need(type(receipt['returncode']) is int and receipt['returncode']==0
                   and stage.sha(receipt['executable'])==receipt['executable_before']==receipt['executable_after'],'paired executed identity')
        for ext in ('stdout','stderr'):
            stage.need(stage.sha(paired.parent/(receipt['name']+'.'+ext))==receipt[ext],'paired stdio')
    for name in ('original','reference','current','repeat','reference-eof','reference-eof-repeat'):
        parsed=rows((report.parent/(name+'.stdout')).read_bytes())
        stage.need(len(parsed)==8021,'strict observation count')
    wrong=(paired.parent/'original-eof.stdout').read_bytes()
    stage.need(len(rows(wrong))==8021 and wrong==(report.parent/'reference-eof.stdout').read_bytes(),'paired wrong native/reference output')
    full_stage.check_control(wrong)
    for bad in (b'{"x":1,"x":1}\n',b'{"x":NaN}\n'):
        try:rows(bad)
        except ValueError:pass
        else:raise ValueError('strict parser known failure escaped')
    result.update(status='AUDITED_FINITE_NATIVE_IODEVICE_CALIBRATION_PASS',
        paired_wrong_original_reference=True,synthetic_strict_parser_controls=2,
        report=str(report),paired_report=str(paired),
        bindings={str(report):stage.sha(report),str(paired):stage.sha(paired),
                  str(Path(__file__).resolve()):stage.sha(__file__)})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--paired',required=True);p.add_argument('--write',action='store_true')
    a=p.parse_args();result=verify(a.report,a.paired)
    if a.write:stage.dump(Path(a.paired).resolve().parent/'audit.json',result)
    print(json.dumps(result))
