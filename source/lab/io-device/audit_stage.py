#!/usr/bin/env python3
"""Independent acceptance audit for staged evidence; never executes native code."""
import argparse
import copy
import json
import re
from pathlib import Path
import stage
from native_artifacts import check_archive_members


def require(ok, message):
    if not ok:
        raise ValueError(message)


def observations(data):
    """A semantic mismatch earns credit only for six well-formed observations."""
    rows = [json.loads(line) for line in data.decode('ascii').splitlines()]
    require(len(rows) == 6, 'six valid observations required')
    event_keys = set(stage.EXPECTED[0]['events'][0])
    for row, expected in zip(rows, stage.EXPECTED):
        require(type(row) is dict and set(row) == set(expected), 'observation schema')
        require(row['case'] == expected['case'] and row['result'] == expected['result'], 'control case/result route')
        require(type(row['cursor']) is int and -4 <= row['cursor'] <= 6, 'cursor type/range')
        for name, length in (('output', 16), ('sink', None)):
            text = row[name]
            require(type(text) is str and re.fullmatch(r'(?:[0-9a-f]{2})*', text) is not None
                    and (len(text) == length if length else len(text) <= 10), 'initialized byte schema')
        require(type(row['events']) is list and 0 < len(row['events']) <= 40, 'event list')
        for event in row['events']:
            require(type(event) is dict and set(event) == event_keys, 'event schema')
            require(event['op'] in ('pos','seek','read','write') and event['phase'] in ('before','mutated','return','throw'), 'event kind')
            for name in ('cursor','ptr','len','n','arg','ordinal'):
                require(type(event[name]) is int, 'event integer type')
            require(-4 <= event['cursor'] <= 6 and -1 <= event['ptr'] <= 4
                    and 0 <= event['len'] <= 5 and 0 <= event['n'] <= 2
                    and -4 <= event['arg'] <= 6 and 0 <= event['ordinal'] <= 3, 'event value range')
            require(type(event['output']) is str and re.fullmatch(r'[0-9a-f]{16}', event['output']) is not None
                    and type(event['sink']) is str and re.fullmatch(r'(?:[0-9a-f]{2}){0,5}', event['sink']) is not None, 'event initialized bytes')
    return rows


def extra(acquisition, execution, reader=lambda p: Path(p).read_bytes()):
    """Supplement the frozen builder's verifier with independently required facts."""
    compiler, flags, libraries, objects = stage.recipe()
    identity = stage.load(stage.ROOT / 'build/buffer-lab/native-identity-r1/manifest.json')
    require(all(acquisition['bindings'].get(path) == digest for path,digest in identity.items()), 'complete native-profile bindings')
    names = ['archive-table', *('member-'+str(i) for i in range(len(objects))),
             *('deps-'+n for n in ('probe','probe-ref',*stage.VARIANTS)),
             'compile-probe', 'compile-probe-ref']
    for name in stage.VARIANTS:
        names.extend(('compile-'+name, 'link-'+name, 'symbols-'+name))
    require([row['name'] for row in acquisition['receipts']] == names, 'complete acquisition receipt routes')
    require(all(type(row['returncode']) is int and row['returncode']==0
                for row in acquisition['receipts']+execution['receipts']), 'normal integer exit codes')
    root = Path(acquisition['variants']['original']).parent
    check_archive_members(reader(root/'archive-table.stdout'), [p.name.encode() for p in objects])
    for i,obj in enumerate(objects):
        digest = identity[str(obj.resolve())]
        require(stage.hashlib.sha256(reader(root/('member-'+str(i)+'.stdout'))).hexdigest() == digest, 'extracted native object bytes')
    symbols = reader(root/'symbols-reference.stdout')
    require(b'Star::IODeviceReference::IODevice::readFullAbsolute' in symbols
            and b'Star::IODeviceReference::IODevice::writeFullAbsolute' in symbols, 'reference namespace symbol routes')
    # The executable receipts carry exact stream paths through their execution
    # directory; callers supply that directory explicitly below.
    for row in execution['receipts']:
        data = reader(Path(execution['_directory']) / (row['name']+'.stdout'))
        observations(data)
        if row['name'] in stage.POSITIVES:
            stage.check_values(data)
        else:
            require(stage.CANON(observations(data)) != stage.CANON(stage.EXPECTED), 'well-formed semantic control escaped')
    return dict(cases=6, native_profile_inputs=len(identity), archive_objects=len(objects),
                positive_executions=4, normal_semantic_controls=2)


def corruption_tests(acquisition, execution):
    tests=[]
    bad=copy.deepcopy(acquisition)
    identity=stage.load(stage.ROOT/'build/buffer-lab/native-identity-r1/manifest.json')
    object_key=next(k for k in identity if k.endswith('.o'))
    bad['bindings'].pop(object_key)
    tests.append(('missing-native-object-binding',bad,execution,{}))
    for name in ('archive-table','member-0','deps-original','symbols-reference'):
        bad=copy.deepcopy(acquisition)
        bad['receipts']=[r for r in bad['receipts'] if r['name']!=name]
        tests.append(('missing-'+name,bad,execution,{}))
    path=str(Path(execution['_directory'])/'pointer-no-advance.stdout')
    for name,data in (('empty-control',b''),('malformed-control',b'{'),('wrong-case-count',b'{}\n')):
        tests.append((name,acquisition,execution,{path:data}))
    detected=[]
    for name,a,e,overrides in tests:
        try:
            extra(a,e,lambda p:overrides.get(str(p),None) if str(p) in overrides else Path(p).read_bytes())
        except (ValueError, UnicodeDecodeError):
            detected.append(name)
        else:
            raise ValueError('audit corruption escaped '+name)
    return detected


def verify(path, write=False):
    path=Path(path).resolve()
    base=stage.verify_execution(path)
    e=stage.load(path);e['_directory']=str(path.parent)
    a=stage.load(e['acquisition'])
    result=extra(a,e)
    detected=corruption_tests(a,e)
    result.update(status='AUDITED_FINITE_NATIVE_SIX_CASE_WITNESS_PASS',
                  synthetic_audit_controls=detected, execution_report=str(path),
                  bindings={str(path):stage.sha(path),str(Path(e['acquisition'])):stage.sha(e['acquisition']),
                            str(Path(__file__).resolve()):stage.sha(__file__),
                            str(Path(stage.__file__).resolve()):stage.sha(stage.__file__)})
    if write:stage.dump(path.parent/'audit.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',required=True);parser.add_argument('--write',action='store_true')
    args=parser.parse_args();print(json.dumps(verify(args.report,args.write)))
