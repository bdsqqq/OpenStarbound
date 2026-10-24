#!/usr/bin/env python3
"""Native-only finite Zstd calibration; no project builds or Rust selectors."""
import argparse,gzip,hashlib,json,os,re,shlex,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; HERE=Path(__file__).resolve().parent; REV='d62f1662'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--backend',choices=['cpp','rust'],default='cpp');p.add_argument('--output',required=True,type=Path);p.add_argument('--values-only',action='store_true',help='unqualified value acquisition for the separate trace verifier');p.add_argument('--fixture-template',type=Path,help='hardlink an existing byte-identical regenerated corpus to avoid repeated disk copies');a=p.parse_args();out=a.output.absolute();base=ROOT/'build/zstd-lab'
 if not out.is_relative_to(base) or out==base or out.exists() or any(x.is_symlink() for x in [out,*out.parents]):p.error('fresh owned nonsymlink output required')
 out.mkdir(parents=True);commands=[];receipts=[];negative=[];generated={};stdout_cache={}
 if not a.values_only:p.error('closed output-only mutants must not run; use --values-only then candidate_trace_run.py')
 rust=ROOT/'build/zstd-rust/target/release/libstar_engine_ffi.a'
 def reconstruct(data):
  data=data.replace(b'#ifdef STAR_USE_RUST_ZSTD\n#include "StarZstdHost.hpp"\n#endif\n',b'')
  return re.sub(rb'#ifdef STAR_USE_RUST_ZSTD\n.*?#else\n(.*?)#endif\n',lambda m:m[1],data,flags=re.S)
 def run(cmd,name,data=None):
  cmd=list(map(str,cmd));commands.append(shlex.join(cmd));exe=Path(cmd[0]);before=sha(exe) if exe.is_file() else None
  env=os.environ.copy();env['ZSTD_RECEIPTS']=str(out/(name+'.tls.tsv'))
  r=subprocess.run(cmd,cwd=ROOT,input=data,capture_output=True,timeout=90,env=env)
  artifact=out/(name+'.stdout.gz');stdout_digest=hashlib.sha256(r.stdout).hexdigest()
  # Preserve every named receipt, sharing storage only for exact byte matches.
  if stdout_digest in stdout_cache:os.link(stdout_cache[stdout_digest],artifact)
  else:
   with gzip.open(artifact,'wb',compresslevel=1) as f:f.write(r.stdout)
   stdout_cache[stdout_digest]=artifact
  (out/(name+'.log')).write_bytes((commands[-1]+'\n').encode()+r.stderr)
  if before and sha(exe)!=before:raise RuntimeError('executable drift')
  receipts.append(dict(name=name,command=cmd,returncode=r.returncode,executable_sha256=before,stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stdout_artifact=str(artifact),stdout_artifact_sha256=sha(artifact),tls_receipt_sha256=sha(out/(name+'.tls.tsv')) if (out/(name+'.tls.tsv')).exists() else None))
  return r
 def gate(ext,raw,ref):
  original=subprocess.check_output(['git','show',REV+':source/core/StarZSTDCompression.'+ext],cwd=ROOT)
  want=original.replace(b'namespace Star {',b'namespace ZstdReference {\nusing namespace Star;')
  if ext=='cpp':want=want.replace(b'"StarZSTDCompression.hpp"',b'"StarZSTDCompression.reference.hpp"')
  if original!=raw or want!=ref or (reconstruct((ROOT/('source/core/StarZSTDCompression.'+ext)).read_bytes()) if ext=='cpp' else (ROOT/('source/core/StarZSTDCompression.'+ext)).read_bytes())!=raw:raise ValueError('freeze drift')
 for ext in ['cpp','hpp']:
  raw=(HERE/('StarZSTDCompression.original.'+ext)).read_bytes();ref=(HERE/('StarZSTDCompression.reference.'+ext)).read_bytes();gate(ext,raw,ref)
  for label,r,d in [('raw',raw+b' ',ref),('reference',raw,ref+b' ')]:
   try:gate(ext,r,d)
   except ValueError:negative.append(label+'-'+ext)
   else:raise RuntimeError('freeze negative escaped')
 cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarZSTDCompression.cpp'));recipe=shlex.split(entry['command']);flags=[];skip=False
 for x in recipe[1:]:
  if skip:skip=False;continue
  if x=='-o':skip=True
  elif x not in ['-c',entry['file']]:flags.append(x)
 if any('STAR_USE_RUST' in x for x in flags):raise RuntimeError('non-native recipe')
 lines=(cm/'build.ninja').read_text().splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
 objs=[cm/x for x in shlex.split(lines[i].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/')) and not x.endswith('/StarZSTDCompression.cpp.o')]
 libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+15] if x.startswith('  LINK_LIBRARIES = ')));libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
 cli=Path('/opt/homebrew/bin/zstd').resolve();cli_version=run([cli,'--version'],'cli-version').stdout.decode();cases=[];anchors={}
 def add(mode,data,facade=0,level=2,group=None,alias=0,expect=None,error=None):
  id='c'+str(len(cases));cases.append((id,group or id,mode,facade,level,alias,data.hex() or '-'))
  if expect is not None or error is not None:anchors[id]=dict(output=None if expect is None else expect.hex(),error=error)
  return id
 literal=bytes.fromhex('28b52ffd2003190000616263')
 for facade in range(4):add(1,literal,facade,expect=b'abc')
 # CLI is an external encoder, not a compressed-byte golden for the vendor.
 for n in [0,3,131071,131072,131073,2097152]:
  for kind in range(2):
   data=(b'A\0B'*((n+2)//3))[:n] if kind==0 else hashlib.shake_256(str(n).encode()).digest(n)
   wire=run([cli,'-q','-c','--content-size'],'encode-'+str(n)+'-'+str(kind),data).stdout
   # A pipe intentionally has unknown content size; use a local file to obtain FCS.
   path=out/('input-'+str(n)+'-'+str(kind));path.write_bytes(data)
   encoded=run([cli,'-q','-c',path],'encode-file-'+str(n)+'-'+str(kind))
   if encoded.returncode:raise RuntimeError('external encoder failure')
   wire=encoded.stdout
   for facade in range(4):
    add(0,data,facade,expect=b'' if n==0 else None)
    add(1,wire,facade,expect=data)
    add(3,wire,facade,expect=(b'\xaa\x55' if facade<2 else b'')+data)
    add(2,data,facade)
   if n<=131073:
    for facade in [0,1]:
     add(2,data,facade,alias=1);add(3,wire,facade,alias=1,expect=wire+data)
   for bad in [wire[:-1],b'garbage',wire+wire,wire+b'trailing']:
    for facade in range(4):add(1,bad,facade);add(3,bad,facade)
 # Persistent contexts retain state over zero-length chunks and corrupt calls.
 for pattern in [[0,1,2],[1,0,2]]:
  for mode,payload in [(2,b'A\0B'),(3,literal)]:
   for facade in range(4):
    group='split-'+str(pattern)+str(mode)+str(facade);pos=0
    for count in [*pattern,len(payload)-sum(pattern)]:add(mode,payload[pos:pos+count],facade,group=group);pos+=count
 for facade in range(4):
  for data in [b'garbage',literal,b'',literal]:add(3,data,facade,group='error-reuse'+str(facade))
  add(1,b'',facade,expect=b'\xaa\x55',error='(IOException) Cannot determine ZSTD decompressed size')
 fixture=out/'cases.tsv'
 if a.fixture_template:
  template=a.fixture_template.absolute()
  if template.is_symlink() or not template.is_file() or not template.resolve().is_relative_to(base):raise ValueError('owned regular fixture template required')
  expected=hashlib.sha256()
  for row in cases:expected.update((' '.join(map(str,row))+'\n').encode())
  # Regenerate and compare EVERY byte before sharing immutable fixture storage;
  # a cached corpus must never become an unchecked replacement for anchors.
  if sha(template)!=expected.hexdigest():raise ValueError('fixture template differs from regenerated corpus')
  os.link(template,fixture)
 else:fixture.write_text('\n'.join(' '.join(map(str,x)) for x in cases)+'\n')
 (out/'anchors.json').write_text(json.dumps(anchors,sort_keys=True))
 sources=[HERE/'lab.cpp',HERE/'StarZSTDCompression.reference.cpp',ROOT/'source/core/StarZSTDCompression.cpp',HERE/'StarZSTDCompression.original.cpp']
 if a.backend=='rust':sources += [ROOT/'source/core/StarZstdHost.hpp',ROOT/'source/core/StarRustZstd.h',ROOT/'source/rust/ffi/src/zstd.rs',ROOT/'source/rust/ffi/src/lib.rs',rust]
 tracked=[Path(sys.executable).resolve(),Path(__file__),cli,db,cm/'build.ninja',Path(recipe[0]).resolve(),fixture,out/'anchors.json',*sources,*[HERE/('StarZSTDCompression.'+k+'.hpp') for k in ['reference','original']],*objs,*[Path(x) for x in libs if x.endswith('.a')],*out.glob('input-*')]
 for n,src in enumerate(sources[:4]):
  dep=out/(str(n)+'.d');r=run([recipe[0],*flags,'-I'+str(HERE),*(['-DSTAR_USE_RUST_ZSTD=1','-DLAB_RUST=1'] if a.backend=='rust' and n in (0,2) else []),'-M','-MF',dep,src],'deps'+str(n))
  if r.returncode:raise RuntimeError('dependency scan failure')
  tracked += [Path(x) if Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])]
 tracked=list(dict.fromkeys(x.resolve() for x in tracked));before={str(x):sha(x) for x in tracked};(out/'before.json').write_text(json.dumps(before,indent=2))
 native=out/'native-core.a'
 if run(['/usr/bin/ar','rcs',native,*objs],'archive').returncode:raise RuntimeError('archive failure')
 archive_sha=sha(native)
 def compile(name,src,ref=False):
  binary=out/name;start=sha(src);r=run([recipe[0],*flags,'-I'+str(HERE),*(['-DLAB_REFERENCE=1'] if ref else []),*(['-DSTAR_USE_RUST_ZSTD=1','-DLAB_RUST=1'] if a.backend=='rust' and name=='candidate' else []),HERE/'lab.cpp',src,native,*([rust] if a.backend=='rust' and name=='candidate' else []),*libs,'-Wl,-dead_strip','-o',binary],name+'-compile')
  if r.returncode:raise RuntimeError('compile failure NOT credited negative '+name)
  if sha(src)!=start:raise RuntimeError('generated source drift')
  generated[str(src)]=start;return binary
 def observe(binary,name):
  r=run([binary,fixture],name)
  if r.returncode:raise RuntimeError('runtime failure '+name)
  return r.stdout
 binary=compile('candidate',ROOT/'source/core/StarZSTDCompression.cpp');baseline=observe(binary,'baseline');ref=observe(compile('reference',HERE/'StarZSTDCompression.reference.cpp',True),'reference');original=observe(compile('original',HERE/'StarZSTDCompression.original.cpp'),'original')
 def check(stream,reference=ref):
  if stream!=reference:raise ValueError('COMPARISON ordered bytes/state')
  rows={x.split(b'\t')[0].decode():x.split(b'\t') for x in stream.splitlines()}
  for id,want in anchors.items():
   row=rows[id];err=bytes.fromhex(row[1].decode()).decode()
   if err!=(want['error'] or '') or (want['output'] is not None and row[2].decode()!=want['output']):raise ValueError('COMPARISON independent literal/CLI '+id)
 check(baseline);check(original);check(observe(binary,'repeat'))
 if a.values_only:
  after={str(x):sha(x) for x in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
  if before!=after or sha(native)!=archive_sha:raise RuntimeError('value-acquisition binding drift')
  version=run([binary,'--version'],'native-version').stdout.decode().strip()
  os.link(stdout_cache[hashlib.sha256(baseline).hexdigest()],out/'observations.tsv.gz')
  report=dict(status='VALUES_ONLY_NOT_QUALIFIED',backend=a.backend,revision=REV,cases=len(cases),anchors=len(anchors),negative_controls=negative,ordered_sha256=hashlib.sha256(baseline).hexdigest(),native_zstd=version,external_cli=cli_version,bindings=before,commands=commands,runtime_receipts=receipts,link=dict(compiler=recipe[0],flags=flags,libraries=libs,archive=str(native)))
  (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['bindings','commands','runtime_receipts','link']}));return
 raw=(HERE/'StarZSTDCompression.original.cpp').read_bytes()
 mutants=[('prefix-clear',b'  size_t written = out.size();',b'  out.clear(); size_t written = out.size();'),('compress-input-only',b'finished = ret == 0 && inBuffer.pos == inBuffer.size;',b'finished = inBuffer.pos == inBuffer.size;'),('drop-full-continue',b'      continue;',b'      /* dropped continue */'),('premature-shrink',b'    written += outBuffer.pos;',b'    out.resize(written); written += outBuffer.pos;')]
 for name,old,new in mutants:
  if old not in raw:raise RuntimeError('mutant missing')
  src=out/(name+'.cpp');src.write_bytes(raw.replace(old,new));bad=observe(compile(name,src),name)
  try:check(bad)
  except ValueError:negative.append(name)
  else:raise RuntimeError('runtime mutant escaped '+name)
 # Paired corruption is checked with equality deliberately neutralized.
 src=out/'paired.cpp';src.write_bytes(raw.replace(b'  out.resize(result);',b'  out.resize(0);'));bad=observe(compile('paired',src),'paired')
 try:check(bad,bad)
 except ValueError as e:
  if 'independent' not in str(e):raise
  negative.append('paired-independent-anchor')
 else:raise RuntimeError('paired corruption escaped')
 for label,stream in [('verifier-prefix',baseline.replace(b'aa55',b'aa54',1)),('verifier-state',baseline+b'bad')]:
  try:check(stream)
  except ValueError:negative.append(label)
  else:raise RuntimeError('verifier escaped')
 after={str(x):sha(x) for x in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after or sha(native)!=archive_sha:raise RuntimeError('bound source/library drift')
 def identity(binding):
  if binding!=before:raise ValueError('provenance')
 try:identity({})
 except ValueError:negative.append('provenance')
 else:raise RuntimeError('provenance escaped')
 version=run([binary,'--version'],'native-version').stdout.decode().strip()
 with gzip.open(out/'observations.tsv.gz','wb',compresslevel=1) as f:f.write(baseline)
 report=dict(status='PASS',revision=REV,cases=len(cases),anchors=len(anchors),negative_controls=negative,ordered_sha256=hashlib.sha256(baseline).hexdigest(),native_zstd=version,external_cli=cli_version,bindings=before,generated_source_bindings=generated,native_archive_sha256=archive_sha,commands=commands,runtime_receipts=receipts,limits=['C++ calibration only; no Rust/game/port completion claim','finite capacity-stable aliases only; no reallocating aliases','no actual OOM, fault injection, or codec call trace','require-ret0/full-output controls not yet demonstrated'])
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['bindings','generated_source_bindings','commands','runtime_receipts']}))
if __name__=='__main__':main()
