#!/usr/bin/env python3
"""Frozen six-body VLQ oracle; isolated standalone compiler, no native build."""
import argparse,hashlib,json,shlex,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
SHA='0f4cd849bf4931f1dbb8cabf02dc62083e11b48cc4b0595ec1d8ea39534159b8'
def sha(b):return hashlib.sha256(b).hexdigest()
def adapt(raw):return raw.replace(b'namespace Star {',b'namespace FrozenReference {\nusing namespace Star;',1)
def gate(raw,ad):
    if sha(raw)!=SHA:raise ValueError('source hash corruption')
    if ad!=adapt(raw):raise ValueError('unauthorized adaptation')
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'build/vlq-lab/cpp');p.add_argument('--define',choices=['STAR_USE_RUST_VLQ','STAR_USE_RUST_VLQ=1']);p.add_argument('--archive',type=Path);a=p.parse_args()
    if bool(a.define)!=bool(a.archive):p.error('backend/archive must be paired')
    out=a.output.resolve()
    if not out.is_relative_to((ROOT/'build/vlq-lab').resolve()) or out==(ROOT/'build/vlq-lab').resolve():p.error('output must be nested in build/vlq-lab')
    out.mkdir(parents=True,exist_ok=True)
    raw=(HERE/'StarVlqEncoding.original.hpp').read_bytes();ad=adapt(raw);gate(raw,ad)
    if subprocess.check_output(['git','show','dfc36000:source/core/StarVlqEncoding.hpp'],cwd=ROOT)!=raw:raise ValueError('frozen git snapshot mismatch')
    negative=[]
    for name,r,x in [('source-corruption',raw+b' ',ad),('unauthorized-adaptation',raw,ad.replace(b'i + 1',b'i + 2',1))]:
        try:gate(r,x)
        except ValueError:negative.append(name)
        else:raise ValueError('provenance control escaped')
    (out/'reference.hpp').write_bytes(ad)
    db=ROOT/'build/behavior/reference/cmake/compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarDataStream.cpp'));command=shlex.split(entry['command']);flags=[];skip=False
    for f in command[1:]:
        if skip:skip=False;continue
        if f=='-o':skip=True
        elif f not in ['-c',entry['file']] and not f.startswith('-DSTAR_USE_RUST_VLQ'):flags.append(f)
    # Dependency files are snapshots by identity, not replacement mock primitives.
    deps=[ROOT/'source/core'/x for x in ['StarVlqEncoding.hpp','StarAlgorithm.hpp','StarMemory.hpp','StarConfig.hpp']]
    tracked=[Path(__file__).resolve(),HERE/'lab.cpp',HERE/'forwarding_regression.cpp',HERE/'StarVlqEncoding.original.hpp',db,*deps]
    if a.archive:tracked += [a.archive.resolve(),ROOT/'source/core/StarRustVlq.h']
    # Query compiler preprocessing dependencies before calibration, so every
    # actual local primitive header participates in the before/after binding.
    dependency_cmd=[command[0],*flags,'-I'+str(out),'-MM',str(HERE/'lab.cpp')]
    if a.define:dependency_cmd.insert(1,'-D'+a.define)
    dependency_text=subprocess.check_output(dependency_cmd,cwd=ROOT,text=True)
    (out/'dependencies.txt').write_text(dependency_text)
    for token in shlex.split(dependency_text.replace('\\\n',' ')):
        path=Path(token)
        if path.is_file():tracked.append(path.resolve())
    tracked=list(dict.fromkeys(x for x in tracked if x.exists()))
    primitive_snapshot=[]
    for path in tracked:
        if path.is_relative_to(ROOT/'source/core') and path.name not in ['StarVlqEncoding.hpp','StarRustVlq.h']:
            relative=path.relative_to(ROOT).as_posix()
            frozen=subprocess.check_output(['git','show','dfc36000:'+relative],cwd=ROOT)
            if path.read_bytes()!=frozen:raise ValueError('primitive differs from frozen source snapshot: '+relative)
            primitive_snapshot.append(relative)
    before={str(x):sha(x.read_bytes()) for x in tracked};(out/'before.json').write_text(json.dumps(before,indent=2))
    commands=[]
    def run(cmd,name):
        commands.append(shlex.join(map(str,cmd)));r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=90);(out/(name+'.log')).write_text(commands[-1]+'\n'+r.stdout+r.stderr);return r
    for name,cli in [('arbitrary-define',['--define','readVlqU=evil']),('unpaired-archive',['--archive','missing.a']),('outside-output',['--output',str(ROOT/'build/not-vlq')])]:
        r=run(['python3',str(Path(__file__).resolve()),*cli],name)
        if r.returncode!=2:raise RuntimeError('CLI control escaped '+name)
        negative.append(name)
    cmd=[command[0],*flags,'-I'+str(out),'-ffunction-sections','-fdata-sections','-Wl,-dead_strip','-fsanitize=undefined','-fno-sanitize-recover=all']
    if a.define:cmd+=['-D'+a.define]
    cmd += [str(HERE/'lab.cpp')]
    if a.archive:cmd += [str(a.archive.resolve())]
    binary=out/'calibration';cmd+=['-o',str(binary)]
    if run(cmd,'compile').returncode:raise RuntimeError('compile failure: '+str(out/'compile.log'))
    baseline=run([str(binary)],'baseline');repeat=run([str(binary)],'repeat')
    if baseline.returncode or repeat.returncode or baseline.stdout!=repeat.stdout:raise RuntimeError('baseline failed; mutants NOT counted')
    result=json.loads(baseline.stdout)
    # Signed forwarding must preserve copy-initialization overload selection and
    # destruction BEFORE assigning the signed destination, not just byte I/O.
    def forwarding_compile(name, include=None):
        extra=[command[0], *(['-I'+str(include)] if include else []), *cmd[1:]]
        extra[extra.index(str(HERE/'lab.cpp'))]=str(HERE/'forwarding_regression.cpp')
        extra[-1]=str(out/name)
        if run(extra,name+'-compile').returncode:raise RuntimeError('forwarding fixture compile failed '+name)
        return out/name
    forwarding=forwarding_compile('forwarding')
    if run([str(forwarding)],'forwarding').returncode:raise RuntimeError('forwarding behavior differs')
    if a.define:
        live=(ROOT/'source/core/StarVlqEncoding.hpp').read_text()
        for name,mode,old,new in [
            ('forward-copy-init','copy','OutputIterator forwarded = out;','OutputIterator forwarded(out);'),
            ('forward-destruction','destructor',
             '''  int64_t decoded;
  uint32_t consumed;
  int32_t status;
  {
    // The original unsigned callee's parameter is copy-initialized and destroyed
    // BEFORE assigning v. Its destructor may mutate v or throw.
    InputIterator forwarded = in;
    VlqDetail::Reader<InputIterator> context{forwarded, {}};
    status = star_vlq_read_i(&decoded, &decltype(context)::read, &context, maxBytes, &consumed);
    VlqDetail::check(status, context.exception);
  }
  if (status == 0)
    v = decoded;''',
             '''  InputIterator forwarded = in;
  VlqDetail::Reader<InputIterator> context{forwarded, {}};
  uint32_t consumed;
  auto status = star_vlq_read_i(&v, &decltype(context)::read, &context, maxBytes, &consumed);
  VlqDetail::check(status, context.exception);''')]:
            if live.count(old)!=1:raise ValueError('forwarding mutation no longer unique')
            directory=out/name;directory.mkdir(exist_ok=True)
            (directory/'StarVlqEncoding.hpp').write_text(live.replace(old,new,1))
            broken=forwarding_compile(name+'-mutant',directory)
            failure=run([str(broken),mode],name)
            if failure.returncode!=1 or 'COMPARISON' not in failure.stderr:raise RuntimeError('forwarding negative escaped '+name)
            negative.append(name)
    for name in ['group-order','zigzag','overflow-rejection','greedy-read','success-only','swallowed-exception','replaced-exception','copy-events']+(['receipt'] if a.define else []):
        r=run([str(binary),name],name)
        if r.returncode!=1 or 'COMPARISON' not in r.stderr:raise RuntimeError('negative not comparison rejection '+name)
        negative.append(name)
    # Compile genuine candidate algorithm faults, never touching the frozen
    # reference or active production header. They must fail a comparison.
    for name,old,new in [
        ('algorithm-group-order',b'x >> ((i - j) * 7)',b'x >> (j * 7)'),
        ('algorithm-zigzag',b'(-(v + 1))',b'(-(v + 0))'),
        ('algorithm-overflow-rejection',b'x = (x << 7) | (uint64_t)(oct & 127);',b'if (i == 9 && x > UINT64_MAX / 128) return NPos;\n    x = (x << 7) | (uint64_t)(oct & 127);')]:
        mutant_dir=out/name;mutant_dir.mkdir(exist_ok=True);(mutant_dir/'StarVlqEncoding.hpp').write_bytes(raw.replace(old,new))
        mutant_bin=mutant_dir/'calibration'
        mutant_cmd=[command[0],'-I'+str(mutant_dir),*flags,'-I'+str(out),'-ffunction-sections','-fdata-sections','-Wl,-dead_strip','-fsanitize=undefined','-fno-sanitize-recover=all',str(HERE/'lab.cpp'),'-o',str(mutant_bin)]
        if run(mutant_cmd,name+'-compile').returncode:raise RuntimeError('mutant compile not evidence '+name)
        r=run([str(mutant_bin)],name)
        if r.returncode!=1 or 'COMPARISON' not in r.stderr:raise RuntimeError('algorithm fault not comparison rejection '+name)
        negative.append(name)
    after={str(x):sha(x.read_bytes()) for x in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
    if before!=after:raise RuntimeError('source/archive/checker drift during run; evidence invalid')
    result.update(negative_controls=negative,raw_sha256=SHA,adapted_sha256=sha(ad),binary_sha256=sha(binary.read_bytes()),inputs=before,commands=commands,backend='rust' if a.define else 'cpp',primitive_snapshot=primitive_snapshot)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['inputs','commands']}))
if __name__=='__main__':main()
