#!/usr/bin/env python3
"""Standalone frozen StarBytes differential oracle, using native compiler recipe."""
import argparse, hashlib, json, shlex, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
REV='d4a0fc3e'
SHA='02f0e5f52b9970d5348b70a5b165bedec881fec90d1256e25dac8a365702923b'
def sha(b):return hashlib.sha256(b).hexdigest()
def adapt(raw):return raw.replace(b'namespace Star {',b'namespace FrozenReference {\nusing namespace Star;',1)
def gate(raw,ad):
    if sha(raw)!=SHA:raise ValueError('source hash corruption')
    if ad!=adapt(raw):raise ValueError('unauthorized adaptation')
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'build/bytes-lab/cpp');p.add_argument('--define',choices=['STAR_USE_RUST_BYTES','STAR_USE_RUST_BYTES=1']);p.add_argument('--archive',type=Path);a=p.parse_args()
    if bool(a.define)!=bool(a.archive):p.error('backend/archive must be paired')
    if a.archive and a.archive.resolve()!=ROOT/'build/bytes-rust/target/release/libstar_engine_ffi.a':p.error('archive must be isolated bytes-rust release archive')
    out=a.output.resolve()
    if not out.is_relative_to(ROOT/'build/bytes-lab') or out==ROOT/'build/bytes-lab':p.error('output must be nested in build/bytes-lab')
    out.mkdir(parents=True,exist_ok=True)
    raw=(HERE/'StarBytes.original.hpp').read_bytes();ad=adapt(raw);gate(raw,ad)
    if subprocess.check_output(['git','show',REV+':source/core/StarBytes.hpp'],cwd=ROOT)!=raw:raise ValueError('git snapshot mismatch')
    negative=[]
    for name,r,x in [('source-corruption',raw+b' ',ad),('adaptation-corruption',raw,ad+b' ')]:
        try:gate(r,x)
        except ValueError:negative.append(name)
        else:raise RuntimeError('provenance escaped')
    (out/'reference.hpp').write_bytes(ad)
    db=ROOT/'build/behavior/reference/cmake/compile_commands.json'
    entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarDataStream.cpp'))
    recipe=shlex.split(entry['command']);flags=[];skip=False
    for f in recipe[1:]:
        if skip:skip=False;continue
        if f=='-o':skip=True
        elif f not in ['-c',entry['file']]:flags.append(f)
    commands=[]
    def run(cmd,name):
        commands.append(shlex.join(map(str,cmd)));r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=90);(out/(name+'.log')).write_text(commands[-1]+'\n'+r.stdout+r.stderr);return r
    base=[recipe[0],*flags,'-I'+str(out)]
    if a.define:base+=['-D'+a.define]
    deps=run([*base,'-MM',str(HERE/'lab.cpp')],'dependencies')
    if deps.returncode:raise RuntimeError('dependency query failed')
    tracked=[Path(__file__).resolve(),HERE/'lab.cpp',HERE/'StarBytes.original.hpp',out/'reference.hpp',db,Path(recipe[0]).resolve()]
    if a.archive:tracked.append(a.archive.resolve())
    for token in shlex.split(deps.stdout.replace('\\\n',' ')):
        path=Path(token)
        if path.is_file():tracked.append(path.resolve())
    tracked=list(dict.fromkeys(tracked));primitives=[]
    for path in tracked:
        if path.is_relative_to(ROOT/'source/core') and path.name not in ['StarBytes.hpp','StarRustBytes.h']:
            rel=path.relative_to(ROOT).as_posix()
            frozen=subprocess.check_output(['git','show',REV+':'+rel],cwd=ROOT)
            if path.read_bytes()!=frozen:raise ValueError('primitive drift: '+rel)
            primitives.append(rel)
    before={str(x):sha(x.read_bytes()) for x in tracked};(out/'before.json').write_text(json.dumps(before,indent=2))
    for name,cli in [('arbitrary-define',['--define','STAR_LITTLE_ENDIAN=0']),('unpaired-archive',['--archive','missing.a']),('unpaired-selector',['--define','STAR_USE_RUST_BYTES']),('wrong-archive',['--define','STAR_USE_RUST_BYTES','--archive','wrong.a']),('outside-output',['--output',str(ROOT/'build/not-bytes')])]:
        r=run(['python3',str(Path(__file__).resolve()),*cli],name)
        if r.returncode!=2:raise RuntimeError('CLI gate escaped '+name)
        negative.append(name)
    def compile_one(name,include=None,backend=True):
        # Native flags remain untouched, including the actual platform macro.
        cmd=[recipe[0],*(['-I'+str(include)] if include else []),*flags,'-I'+str(out),'-ffunction-sections','-fdata-sections','-Wl,-dead_strip','-fsanitize=undefined','-fno-sanitize-recover=all']
        if backend and a.define:cmd+=['-D'+a.define]
        cmd+=[str(HERE/'lab.cpp')]
        if backend and a.archive:cmd+=[str(a.archive.resolve())]
        binary=out/name;cmd+=['-o',str(binary)]
        if run(cmd,name+'-compile').returncode:raise RuntimeError('compile failure '+name)
        return binary
    binary=compile_one('calibration')
    baseline=run([str(binary)],'baseline');repeat=run([str(binary)],'repeat')
    if baseline.returncode or repeat.returncode or baseline.stdout!=repeat.stdout:raise RuntimeError('baseline failed; mutants NOT counted')
    result=json.loads(baseline.stdout)
    r=run([str(binary),'receipt-corrupt'],'receipt-corrupt')
    if r.returncode!=1 or 'COMPARISON receipt comparison corruption' not in r.stderr:raise RuntimeError('comparison corruption escaped')
    negative.append('receipt-comparison-corruption')
    for name,old,new in [
        ('wrong-copy-direction',b'destdata[len - 1 - i] = srcdata[i];',b'destdata[i] = srcdata[i];'),
        ('snapshot-not-sequential',b'  for (size_t i = 0; i < len; ++i)\n    destdata[len - 1 - i] = srcdata[i];',b'  std::vector<uint8_t> snapshot(srcdata, srcdata + len);\n  for (size_t i = 0; i < len; ++i)\n    destdata[len - 1 - i] = snapshot[i];'),
        ('unknown-enum-ignored',b'order != ByteOrder::NoConversion && platformByteOrder() != order',b'(order == ByteOrder::BigEndian || order == ByteOrder::LittleEndian) && platformByteOrder() != order')]:
        if old not in raw:raise ValueError('mutation anchor missing')
        directory=out/name;directory.mkdir(exist_ok=True)
        altered=raw.replace(old,new)
        if name=='snapshot-not-sequential':altered=altered.replace(b'#pragma once',b'#pragma once\n#include <vector>')
        (directory/'StarBytes.hpp').write_bytes(altered)
        broken=compile_one(name+'-mutant',directory,False)
        r=run([str(broken)],name)
        if r.returncode!=1 or 'COMPARISON' not in r.stderr:raise RuntimeError('algorithm mutant not comparison failure '+name)
        negative.append(name)
    after={str(x):sha(x.read_bytes()) for x in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
    if before!=after:raise RuntimeError('source/checker/compiler/archive drift; invalid evidence')
    result.update(negative_controls=negative,raw_sha256=SHA,adapted_sha256=sha(ad),binary_sha256=sha(binary.read_bytes()),inputs=before,commands=commands,backend='rust' if a.define else 'cpp',primitive_snapshot=primitives,compiler_version=subprocess.check_output([recipe[0],'--version'],text=True))
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['inputs','commands','compiler_version']}))
if __name__=='__main__':main()
