#!/usr/bin/env python3
"""Frozen byte calibration; never rewrites expected data to fit a candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
SHA='75271b7d7db92682250259ceed417f714a9f55f1d428d37b354398ad808cec0c'
HSHA='3610df48913a01098c9846d363182ce994b1726ab66ea66ec062205f95b90723'
ADAPTED_SHA='0b24920f26d6eae1a44b6756b1ff68bdff3b5a9b64a25aae5d273cac37971a3d'
BOUNDARY=b'String hexEncode(char const* data, size_t len) {'
def sha(b): return hashlib.sha256(b).hexdigest()
def adapt(raw):
    # Full five primitive definitions, including alphabet/helper definitions;
    # only the six allocating facades after this exact boundary are excluded.
    return raw[:raw.index(BOUNDARY)].replace(b'namespace Star {',b'namespace FrozenReference {\nusing namespace Star;',1)+b'}\n'
def gate(raw,header,adapted):
    if sha(raw)!=SHA or sha(header)!=HSHA: raise ValueError('provenance corruption')
    if adapted!=adapt(raw) or sha(adapted)!=ADAPTED_SHA: raise ValueError('unauthorized adaptation')
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=ROOT/'build/encode-lab/cpp')
    p.add_argument('--define',choices=['STAR_USE_RUST_ENCODE','STAR_USE_RUST_ENCODE=1'])
    p.add_argument('--archive',type=Path)
    a=p.parse_args()
    if bool(a.define)!=bool(a.archive):p.error('backend define and archive must be paired')
    out=a.output.resolve()
    if not out.is_relative_to((ROOT/'build/encode-lab').resolve()):p.error('output outside build/encode-lab')
    out.mkdir(parents=True,exist_ok=True)
    raw=(HERE/'StarEncode.original.cpp').read_bytes(); header=(HERE/'StarEncode.original.hpp').read_bytes()
    adapted=adapt(raw);gate(raw,header,adapted)
    # All eleven public declarations and all six ownership/allocation facades
    # stay byte-identical. The executable comparison covers the five kernels;
    # this gate does not pretend to runtime-test String/ByteArray allocation.
    def facade_gate(candidate, candidate_header):
        if candidate_header!=header or candidate[candidate.index(BOUNDARY):]!=raw[raw.index(BOUNDARY):]:
            raise ValueError('public declarations or allocation facades changed')
    facade_gate((ROOT/'source/core/StarEncode.cpp').read_bytes(),(ROOT/'source/core/StarEncode.hpp').read_bytes())
    for path,data in [('source/core/StarEncode.cpp',raw),('source/core/StarEncode.hpp',header)]:
        if subprocess.check_output(['git','show','b36026ec:'+path],cwd=ROOT)!=data:raise ValueError('git snapshot differs')
    negative=[]
    try:facade_gate(raw.replace(b'encodedData.size() / 2',b'encodedData.utf8Size() / 2'),header)
    except ValueError:negative.append('facade-size-contract')
    else:raise ValueError('facade mutation escaped')
    for name,r,h,ad in [('provenance-corruption',raw+b' ',header,adapted),('unauthorized-adaptation',raw,header,adapted.replace(b'len * 2',b'len * 3',1))]:
        try:gate(r,h,ad)
        except ValueError:negative.append(name)
        else:raise ValueError('gate negative escaped')
    (out/'reference.cpp').write_bytes(adapted)
    db=ROOT/'build/behavior/reference/cmake/compile_commands.json'
    entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarEncode.cpp'))
    command=shlex.split(entry['command']);flags=[];skip=False
    for f in command[1:]:
        if skip:skip=False;continue
        if f=='-o':skip=True
        elif f not in ['-c',entry['file']] and not f.startswith('-DSTAR_USE_RUST_ENCODE'):flags.append(f)
    tracked=[Path(__file__),HERE/'lab.cpp',HERE/'StarEncode.original.cpp',HERE/'StarEncode.original.hpp',ROOT/'source/core/StarEncode.cpp',ROOT/'source/core/StarEncode.hpp',db]
    if a.archive:tracked += [a.archive.resolve(),ROOT/'source/core/StarRustEncode.h']
    before={str(f):sha(f.read_bytes()) for f in tracked}
    (out/'before.json').write_text(json.dumps(before,indent=2))
    recipes=[]
    def run(cmd,name):
        recipes.append(shlex.join(map(str,cmd)))
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=90)
        (out/(name+'.log')).write_text(recipes[-1]+'\n'+r.stdout+r.stderr)
        return r
    def compile_candidate(source,name,backend=False):
        binary=out/name
        cmd=[command[0],*flags,'-I'+str(out),'-ffunction-sections','-fdata-sections','-Wl,-dead_strip','-fsanitize=undefined','-fno-sanitize-recover=all']
        if backend:cmd+=['-D'+a.define]
        cmd += [str(HERE/'lab.cpp'),str(source)]
        if backend:cmd += [str(a.archive.resolve())]
        cmd += ['-o',str(binary)]
        r=run(cmd,name+'-compile')
        if r.returncode:raise RuntimeError('compile failed: '+str(out/(name+'-compile.log')))
        return binary
    for name,cli in [('unauthorized-define',['--define','hexEncode=evil']),('unpaired-archive',['--archive','missing.a']),('outside-output',['--output',str(ROOT/'build/not-encode-lab')])]:
        r=run(['python3',str(Path(__file__).resolve()),*cli],name)
        if r.returncode!=2:raise RuntimeError('CLI restriction escaped '+name)
        negative.append(name)
    binary=compile_candidate(ROOT/'source/core/StarEncode.cpp','calibration',bool(a.define))
    baseline=run([str(binary)],'baseline');repeat=run([str(binary)],'repeat')
    if baseline.returncode or repeat.returncode or baseline.stdout!=repeat.stdout:raise RuntimeError('baseline failed; mutants NOT counted')
    result=json.loads(baseline.stdout)
    for name in ['byte','count','canary']+(['receipt'] if a.define else []):
        r=run([str(binary),name],name)
        if r.returncode!=1 or 'COMPARISON' not in r.stderr:raise RuntimeError('comparison negative escaped '+name)
        negative.append(name)
    # Isolated algorithm mutants retain frozen primitive bodies otherwise. No
    # build macro can redefine a formula or change the oracle.
    for name,old,new in [
        ('invalid-hex',b'uint8_t b1 = 0;',b'uint8_t b1 = 1;'),
        ('url-padding',b'if (useUrl)\n',b'if (false)\n'),
        ('whitespace-skipping',b'while (in_len-- && (src[in_] !=',b"while (in_len-- && ((src[in_] == ' ' && (++in_, --in_len, true)) || true) && (src[in_] !=")]:
        if raw.count(old)!=1:raise ValueError('nonunique mutant '+name)
        source=out/(name+'.cpp');source.write_bytes(raw.replace(old,new,1))
        mutant=compile_candidate(source,name)
        r=run([str(mutant)],name)
        if r.returncode!=1 or 'COMPARISON' not in r.stderr:raise RuntimeError('algorithm negative not comparison rejection '+name)
        negative.append(name)
    after={str(f):sha(f.read_bytes()) for f in tracked}
    (out/'after.json').write_text(json.dumps(after,indent=2))
    if before!=after:raise RuntimeError('input drift during calibration; rerun required')
    result.update(negative_controls=negative,raw_sha256=SHA,header_sha256=HSHA,adapted_sha256=sha(adapted),binary_sha256=sha(binary.read_bytes()),inputs=before,commands=recipes,backend='rust' if a.define else 'cpp')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['inputs','commands']}))
if __name__=='__main__':main()
