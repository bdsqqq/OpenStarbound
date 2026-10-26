#!/usr/bin/env python3
"""Independent artifact replay, including exact source-derived wrong controllers."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shlex
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE.parent))
sys.path.insert(0,str(HERE.parent/'behavior'))
import native_artifacts
import build_provenance
import contract


def require(ok,why):
    if not ok:raise ValueError(why)


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def parse(data):
    def pairs(xs):
        d={}
        for k,v in xs:
            require(k not in d,'duplicate key');d[k]=v
        return d
    return json.loads(data,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite')))


def read(p):return parse(Path(p).read_bytes())


def archive_members(data):
    """BSD extended names include their padded name bytes in member size."""
    require(data.startswith(b'!<arch>\n'),'archive signature');offset=8;members=[]
    while offset<len(data):
        h=data[offset:offset+60];require(len(h)==60 and h[58:]==b'`\n','archive header')
        size=int(h[48:58]);require(size>=0 and offset+60+size<=len(data),'archive span')
        body=data[offset+60:offset+60+size];name=h[:16].strip()
        if name.startswith(b'#1/'):
            n=int(name[3:]);require(0<n<=size,'extended name span');name=body[:n].rstrip(b'\0');body=body[n:]
        else:name=name.removesuffix(b'/')
        require(name and b'/' not in name and name not in [x[0] for x in members],'archive member name')
        members.append((name,body));offset+=60+size+(size%2)
    require(offset==len(data),'archive padding')
    if members and members[0][0] in (b'__.SYMDEF',b'__.SYMDEF SORTED',b'__.SYMDEF_64',b'__.SYMDEF_64 SORTED'):members=members[1:]
    return members


def wrong_rows(kind):
    rows=copy.deepcopy(contract.expected())
    for r in rows:
        o=r['options'];action=o['action'];n,p=o['n'],o['p']
        if kind=='growth-control':
            if action=='reserve_growth':r['capacity']=max(n,p,8) if p>n else n
            # Both operations call reserve(p) on the seeded capacity-64 object;
            # filled resize does not bypass the changed allocation decision.
            if action in ('reserve','resize_fill'):r['capacity']=max(64,p,8) if p>64 else 64
        elif kind=='signed-control' and action=='compare':
            a=[x if x<128 else x-256 for x in bytes.fromhex(r['bytes'])]
            b=[x if x<128 else x-256 for x in bytes.fromhex(r['extra'])]
            cmp=(a>b)-(a<b);diff=r['value'].split(',')[0]
            r['value']=f'{diff},{cmp},{int(cmp<0)},{int(cmp==0)},{int(cmp!=0)}'
        elif kind=='iterator-control' and action=='insert_iter':r['value']=str(p)
    return rows


def validate_streams(streams):
    expected=contract.expected();counts={}
    for name,data in streams.items():
        rows=[parse(line) for line in data.splitlines()]
        if name.endswith('-control'):
            wrong=wrong_rows(name);require(contract.strict_equal(rows,wrong),'wrong-controller exact replay '+name)
            count=sum(not contract.strict_equal(a,b) for a,b in zip(rows,expected));require(count>0,'normal semantic discrimination')
            try:contract.check(data)
            except ValueError:pass
            else:raise ValueError('wrong controller accepted')
            counts[name]=count
        else:require(contract.check(data)==987,'native source oracle')
    return counts


def audit(report_path):
    report_path=Path(report_path).resolve();r=read(report_path);a=read(r['acquisition']);base=Path(r['acquisition']).parent
    require(r['status']=='FINITE_NATIVE_BYTEARRAY_CALIBRATION_PASS' and a['status']=='BYTEARRAY_NATIVE_ACQUIRED_NOT_EXECUTED','phase status')
    for q in (a,r):require(type(q['cases']) is int and q['cases']==987 and type(q['definitions']) is int and q['definitions']==33,'finite scope')
    require(type(a['object_count']) is int and a['object_count']==113 and len(a['objects'])==113,'native object scope')
    require(digest(r['acquisition'])==r['acquisition_sha256'],'acquisition hash')
    for bindings in (a['bindings'],a['artifacts'],r['artifacts']):
        for p,h in bindings.items():require(digest(p)==h,'artifact/source drift '+p)
    freeze=read(ROOT/'build/byte-array-lab/source-freeze-r1/freeze.json')
    for p,h in freeze['files'].items():require(digest(p)==h and a['bindings'][p]==h,'precompile source freeze')
    require(freeze['expected_sha256']==a['expected_sha256']=='05258a405c475acc6d46ec78c74ac67270d70d730ab2cf757ab2ef45f9918d8c','independent source oracle identity')
    require((base/'expected.jsonl').read_bytes()==contract.canonical(contract.expected()),'source corpus freeze')
    require(contract.validate_source_map(read(base/'source-map.json'))==56,'complete source-exercise map')
    cpp=(ROOT/'source/core/StarByteArray.cpp').read_text();header=ROOT/'source/core/StarByteArray.hpp'
    require((base/'StarByteArray.original.hpp').read_bytes()==header.read_bytes(),'whole native header')
    patches={'growth-control':('m_capacity * 2','m_capacity'),'signed-control':('unsigned char c','signed char c'),'iterator-control':('return begin() + d + 1;','return begin() + d;')}
    kinds=('original','reference','current',*patches)
    for kind in kinds:
        wanted=cpp.replace(*patches[kind]) if kind in patches else cpp
        require((base/(kind+'.cpp')).read_text()==wanted,'whole source/controller delta '+kind)
        require(not native_artifacts.has_archive_member((base/(kind+'.map')).read_bytes(),b'native-core.a',b'StarByteArray.cpp.o'),'legacy body bypass')
        objs=native_artifacts.link_map_objects((base/(kind+'.map')).read_bytes())
        require(str(base/(kind+'.o')).encode() in objs and str(base/'probe.o').encode() in objs,'actual object route')
    archive=archive_members(Path(a['archive']).read_bytes());require([n.decode() for n,_ in archive]==[Path(p).name for p in a['objects']],'archive configured members')
    for (_,body),p in zip(archive,a['objects']):require(hashlib.sha256(body).hexdigest()==a['bindings'][p],'actual archived object bytes')
    for name in ('body','probe'):
        text=(base/(name+'.d')).read_text().replace('\\\n',' ')
        for p in shlex.split(text.split(':',1)[1]):
            p=Path(p);p=p.resolve() if p.is_absolute() else (ROOT/p).resolve()
            require(str(p) in a['bindings'] or str(p) in a['artifacts'],'dependency closure')
    expected=('original','reference','current','repeat',*patches)
    require([x['name'] for x in r['receipts']]==list(expected),'execution route sequence')
    streams={}
    for x in r['receipts']:
        name=x['name'];exe=base/('current' if name=='repeat' else name)
        require(type(x['returncode']) is int and x['returncode']==0 and x['command']==[str(exe)] and x['executable']==str(exe),'normal executable route')
        require(digest(exe)==x['before']==x['after'],'executed image identity')
        for ext in ('stdout','stderr'):require(digest(report_path.parent/(name+'.'+ext))==x[ext],'execution stdio')
        streams[name]=(report_path.parent/(name+'.stdout')).read_bytes()
    counts=validate_streams(streams)
    require(build_provenance.verify(ROOT/'build/behavior/io-device-combined/reference/bin/starbound')==read(base/'profile.json'),'actual native profile identity')
    return dict(status='AUDITED_FINITE_NATIVE_BYTEARRAY_PASS',cases=987,compiled_definitions=33,header_definitions=23,objects=113,
                normal_control_changed_cases=counts,report=str(report_path),report_sha256=digest(report_path),
                auditor_sha256=digest(__file__),contract_sha256=digest(HERE/'contract.py'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    out=Path(args.output).absolute();require(out.is_relative_to(ROOT/'build/byte-array-lab') and not out.exists(),'fresh audit output')
    result=audit(args.report);out.mkdir(parents=True);(out/'audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
