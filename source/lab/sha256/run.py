#!/usr/bin/env python3
"""Frozen SHA256 oracle; expected values are never regenerated."""
import argparse, hashlib, json, shlex, subprocess, re
from independent import seeded_wrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; HERE=Path(__file__).resolve().parent
SHA='8a4d67bbbd7e6bcc54356dbc59429cf16076064a6b8c4b5427363df79beb5b3b'
HSHA='2f8d6ec062ad777a099ce669a60a313e7d0ffdc865496589b7810033974fec5b'
def sha(x): return hashlib.sha256(x).hexdigest()
def gate(r,h):
    if sha(r)!=SHA or sha(h)!=HSHA: raise ValueError('provenance')
def adapt(r): return r.replace(b'namespace Star {',b'namespace Frozen {\nusing namespace Star;',1).replace(b'#include "StarSha256.hpp"',b'#include "reference.hpp"',1)
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'build/sha256-lab/cpp');p.add_argument('--define',choices=['STAR_USE_RUST_SHA256','STAR_USE_RUST_SHA256=1']);p.add_argument('--archive',type=Path);a=p.parse_args()
 if bool(a.define)!=bool(a.archive):p.error('backend/archive must be paired')
 out=a.output.resolve()
 if not out.is_relative_to((ROOT/'build/sha256-lab').resolve()):p.error('output outside owned lab')
 out.mkdir(parents=True,exist_ok=True)
 raw=(HERE/'StarSha256.original.cpp').read_bytes();header=(HERE/'StarSha256.original.hpp').read_bytes();gate(raw,header)
 for path,data in [('source/core/StarSha256.cpp',raw),('source/core/StarSha256.hpp',header)]:
  if subprocess.check_output(['git','show','19506189:'+path],cwd=ROOT)!=data:raise ValueError('git differs')
 candidate=ROOT/'source/core/StarSha256.cpp'; public=ROOT/'source/core/StarSha256.hpp'
 if public.read_bytes()!=header:raise ValueError('public header drift')
 # These ownership/UTF8 facades are source-preserved, NOT runtime-tested here.
 text=candidate.read_bytes()
 for start,end in [(b'void Sha256Hasher::push(String const& data)',b'ByteArray Sha256Hasher::compute()'),(b'ByteArray sha256(char const* source, size_t length)',b'\n}\n')]:
  old=raw[raw.index(start):] if start.startswith(b'ByteArray sha256(') else raw[raw.index(start):raw.index(end)]
  if old not in text:raise ValueError('allocation/UTF8 facade drift')
 alloc=raw[raw.index(b'ByteArray Sha256Hasher::compute()'):raw.index(b'void Sha256Hasher::compute(char*')]
 if alloc not in text and alloc.replace(b'sha_done(',b'sha_backend_done(') not in text:raise ValueError('allocation-before-mutation facade drift')
 db=ROOT/'build/behavior/reference/cmake/compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarSha256.cpp'));cmd=shlex.split(entry['command']);flags=[];skip=False
 for f in cmd[1:]:
  if skip:skip=False;continue
  if f=='-o':skip=True
  elif f not in ['-c',entry['file']] and not f.startswith('-DSTAR_USE_RUST_SHA256'):flags.append(f)
 tracked=[Path(__file__),HERE/'independent.py',HERE/'published.json',HERE/'lab.cpp',HERE/'StarSha256.original.cpp',HERE/'StarSha256.original.hpp',candidate,public,db]
 if a.archive:tracked += [a.archive.resolve(),ROOT/'source/core/StarRustSha256.h',ROOT/'source/rust/ffi/src/sha256.rs']
 if a.archive:tracked += [ROOT/'source/rust/ffi/src/lib.rs',ROOT/'source/rust/ffi/Cargo.toml',ROOT/'source/rust/Cargo.toml',ROOT/'source/rust/Cargo.lock']
 before={str(f):sha(f.read_bytes()) for f in tracked};(out/'before.json').write_text(json.dumps(before,indent=2))
 (out/'reference.hpp').write_bytes(adapt(header));(out/'reference.cpp').write_bytes(adapt(raw));(out/'candidate.cpp').write_bytes(text)
 recipes=[]
 def run(command,name):
  recipes.append(shlex.join(map(str,command)));r=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=100);(out/(name+'.log')).write_text(recipes[-1]+'\n'+r.stdout+r.stderr);return r
 def compile(name,data,backend):
  (out/'candidate.cpp').write_bytes(data);binary=out/name
  command=[cmd[0],*flags,'-I'+str(out),'-ffunction-sections','-fdata-sections','-Wl,-dead_strip','-fsanitize=undefined','-fno-sanitize-recover=all']
  if backend:command+=['-D'+a.define]
  command += [str(HERE/'lab.cpp')]
  if backend:command += [str(a.archive.resolve())]
  command += ['-o',str(binary)]
  r=run(command,name+'-compile')
  if r.returncode:raise RuntimeError('compile failed '+str(out/(name+'-compile.log')))
  return binary
 binary=compile('calibration',text,bool(a.define));baseline=run([str(binary)],'baseline');repeat=run([str(binary)],'repeat')
 if baseline.returncode or repeat.returncode or baseline.stdout!=repeat.stdout:raise RuntimeError('baseline failed; no mutants counted')
 rows=re.findall(r'VECTOR (\d+) ([0-9a-f]+)',baseline.stdout)
 for (n,d),s in zip(rows,[b'',b'abc',b'abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq',b'a'*1000000]):
  if int(n)!=len(s) or d!=sha(s):raise RuntimeError('independent hashlib comparison')
 if len(rows)!=4:raise RuntimeError('missing vectors')
 for n,d in re.findall(r'HASHLIB (\d+) ([0-9a-f]+)',baseline.stdout):
  n=int(n)
  if d!=sha(bytes((k*131+n*17)&255 for k in range(n))):raise RuntimeError('hashlib generated comparison')
 if len(re.findall(r'HASHLIB ',baseline.stdout))!=257:raise RuntimeError('missing hashlib rows')
 wrap=re.search(r'WRAP ([0-9a-f]+)',baseline.stdout).group(1)
 if wrap!=seeded_wrap(0) or wrap==seeded_wrap(1<<32):raise RuntimeError('legacy overflow/standard counterexample comparison')
 facts=json.loads((HERE/'published.json').read_text())
 if facts['download_sha256']!='8f39f02a57bfd1da15634706724a585766e6223f77ecdaf243cad16cd3a1aa1b':raise RuntimeError('published download identity')
 document=ROOT/'build/sha256-lab/rfc6234.txt'
 if document.exists() and sha(document.read_bytes())!=facts['download_sha256']:raise RuntimeError('published document drift')
 for v in facts['vectors'].values():
  if sha(v['message'].encode())!=v['sha256']:raise RuntimeError('published message/digest inconsistent')
 for n,d in rows[1:3]:
  if d!=facts['vectors'][n]['sha256']:raise RuntimeError('published vector comparison')
 negatives=[]
 for name,cli in [('unauthorized-define',['--define','sha_done=evil']),('unpaired-archive',['--archive','missing.a']),('outside-output',['--output',str(ROOT/'build/not-sha256-lab')])]:
  r=run(['python3',str(Path(__file__).resolve()),*cli],name)
  if r.returncode!=2:raise RuntimeError('CLI restriction escaped '+name)
  negatives.append(name)
 for name in ['byte','state']+(['receipt','count'] if a.define else []):
  r=run([str(binary),name],name)
  if r.returncode!=1 or 'COMPARISON' not in r.stderr:raise RuntimeError('not comparison rejection '+name)
  negatives.append(name)
 for name,old,new in [('round',b'0x428a2f98U',b'0x428a2f99U'),('endian',b'(4 * i) + 0]) << 24',b'(4 * i) + 0]) << 16'),('padding',b'= 0x80;',b'= 0x81;'),('64bit-correction',b'md->buf[i] = 0;\n\n  /* append length */',b'md->buf[i] = (i == 59 && md->length == 0 && md->state[0] != 0x6A09E667U) ? 1 : 0;\n\n  /* append length */'),('cached-finalization',b'void Sha256Hasher::compute(char* hashDestination) {',b'void Sha256Hasher::compute(char* hashDestination) { if (m_finished) return;')]:
  if raw.count(old)!=1:raise ValueError('nonunique mutation')
  mutant=compile(name,raw.replace(old,new,1),False);r=run([str(mutant)],name)
  if r.returncode!=1 or 'COMPARISON' not in r.stderr:raise RuntimeError('not comparison rejection '+name)
  negatives.append(name)
 try:gate(raw+b' ',header)
 except ValueError:negatives.append('provenance')
 else:raise RuntimeError('provenance negative escaped')
 (out/'candidate.cpp').write_bytes(text)
 after={str(f):sha(f.read_bytes()) for f in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after:raise RuntimeError('source/checker/archive drift; rerun required')
 result={'backend':'rust' if a.define else 'cpp','stdout':baseline.stdout,'negative_controls':negatives,'raw_sha256':SHA,'header_sha256':HSHA,'adapted_sha256':sha(adapt(raw)),'inputs':before,'commands':recipes,'binary_sha256':sha(binary.read_bytes())}
 (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('\n'.join(line for line in baseline.stdout.splitlines() if not line.startswith('HASHLIB ')));print('negative controls:',','.join(negatives))
if __name__=='__main__':main()
