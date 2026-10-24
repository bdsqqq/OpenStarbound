#!/usr/bin/env python3
"""Frozen native calibration. No Cargo, game, or production writes."""
import argparse,hashlib,json,os,re,shlex,subprocess,zlib,gzip,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;REV='038b6fd9'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--backend',choices=['cpp','rust'],default='cpp');a=p.parse_args();out=a.output.absolute();base=ROOT/'build/compression-lab'
 rust=a.backend=='rust';rust_archive=ROOT/'build/compression-rust/target/release/libstar_engine_ffi.a'
 if rust and not rust_archive.is_file():p.error('canonical release Rust archive required')
 if not out.is_relative_to(base) or out==base or out.exists() or any(x.is_symlink() for x in [out,*out.parents]):p.error('fresh owned nonsymlink output required')
 out.mkdir(parents=True);commands=[];negative=[];runtime_receipts=[];generated_source_receipts={}
 def gate(ext,raw,adapt):
  orig=subprocess.check_output(['git','show',REV+':source/core/StarCompression.'+ext],cwd=ROOT);want=orig.replace(b'namespace Star {',b'namespace CompressionReference {\nusing namespace Star;')
  if ext=='cpp':want=want.replace(b'"StarCompression.hpp"',b'"StarCompression.reference.hpp"')
  if raw!=orig or adapt!=want:raise ValueError('freeze drift')
 for ext in ['cpp','hpp']:
  raw=(HERE/('StarCompression.original.'+ext)).read_bytes();ref=(HERE/('StarCompression.reference.'+ext)).read_bytes();gate(ext,raw,ref)
  current=(ROOT/('source/core/StarCompression.'+ext)).read_bytes()
  if ext=='cpp' and current!=raw:
   # Reconstruct the COMPLETE OFF translation unit, not selected facade snippets.
   pattern=rb'#if(?:def STAR_USE_RUST_COMPRESSION| STAR_USE_RUST_COMPRESSION)\n(.*?)#else\n(.*?)#endif\n'
   current,includes=re.subn(rb'#if(?:def STAR_USE_RUST_COMPRESSION| STAR_USE_RUST_COMPRESSION)\n(?:#include [^\n]+\n)+#endif\n',b'',current)
   if includes!=1:raise ValueError('expected one guarded include block')
   current,count=re.subn(pattern,lambda m:m[2],current,flags=re.S)
   if count!=3:raise ValueError('expected exactly three guarded controllers')
  if current!=raw:raise ValueError('complete OFF reconstruction/header drift')
  for label,r,d in [('raw',raw+b' ',ref),('adapt',raw,ref+b' ')]:
   try:gate(ext,r,d)
   except ValueError:negative.append(label+'-'+ext)
   else:raise RuntimeError('source negative escaped')
 cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarCompression.cpp'));recipe=shlex.split(entry['command']);flags=[];skip=False
 for x in recipe[1:]:
  if skip:skip=False;continue
  if x=='-o':skip=True
  elif x not in ['-c',entry['file']]:flags.append(x)
 if any('STAR_USE_RUST' in x for x in flags):raise RuntimeError('non-native recipe')
 lines=(cm/'build.ninja').read_text().splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
 objs=[cm/x for x in shlex.split(lines[i].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/')) and not x.endswith('/StarCompression.cpp.o')]
 libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+15] if x.startswith('  LINK_LIBRARIES = ')));libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
 def run(cmd,name):
  executable=Path(cmd[0]);bound=sha(executable) if executable.parent==out and executable.is_file() else None
  commands.append(shlex.join(map(str,cmd)));r=subprocess.run(list(map(str,cmd)),cwd=ROOT,capture_output=True,timeout=90);(out/(name+'.log')).write_bytes((commands[-1]+'\n').encode()+r.stdout+r.stderr)
  if bound is not None:
   if sha(executable)!=bound:raise RuntimeError('executed binary drift '+name)
   runtime_receipts.append(dict(name=name,binary=str(executable),before=bound,after=sha(executable),returncode=r.returncode,stream_sha256=hashlib.sha256(r.stdout).hexdigest()))
  return r
 # Independent producers, not a compressed-byte golden for installed zlib-ng.
 cases=[];anchors={};error_anchors={}
 def add(mode,facade,data,limit=0,level=5,alias=0,length=None,expect=None):
  id='c'+str(len(cases));cases.append((id,mode,facade,level,alias,len(data) if length is None else length,limit,data.hex() or '-'))
  if expect is not None:anchors[id]=expect.hex()
  return id
 for n in [0,5,32767,32768,32769,65536,65537]:
  for kind in range(3):
   data=bytes(n) if kind==0 else (b'abc123'*((n+5)//6))[:n] if kind==1 else hashlib.shake_256(('compression'+str(n)).encode()).digest(n)
   for level in [-2,-1,*range(10),10,99]:
    for facade in [0,1]:
     id=add(0,facade,data,level=level)
     if n and level in [-2,10,99]:error_anchors[id]={'error':'(IOException) Failed to initialise deflate (-2)','output':(b'' if facade==0 else b'sentinel').hex()}
   add(0,0,data,alias=1,expect=b'')
   for mode,wire in [(1,zlib.compress(data)),(2,gzip.compress(data,mtime=0))]:
    for facade in range(4):
     for limit in [0,1,32767,32768,32769,65536]:
      # Independent literal contract: limits are checked ONLY on complete slabs.
      succeeds=not limit or n<32768 or (n//32768)*32768<limit
      id=add(mode,facade,wire,limit,expect=data if succeeds else None)
      if not succeeds:
       full=((limit+32767)//32768)*32768
       name='uncompressData' if mode==1 else 'uncompressDataGzip'
       error_anchors[id]={'error':f'(IOException) hit {name} limit of {limit} bytes','output':(data[:full] if facade in [0,2] else b'sentinel').hex()}
    for malformed in [wire[:-1],wire[:len(wire)//2],wire[:-1]+bytes([wire[-1]^1]),b'garbage',wire+wire,wire+b'trailing']:
     for facade in range(4):add(mode,facade,malformed,expect=data if malformed in [wire+wire,wire+b'trailing'] else None)
    if kind<2 and n<=32768:
     for facade in [0,2]:add(mode,facade,wire,alias=1,expect=data)
    for length in [2**32+len(wire),2**32,2**32+1]:add(mode,0,wire,length=length,expect=data if length==2**32+len(wire) else None)
    damaged=wire[:-1]+bytes([wire[-1]^1]);name='uncompressData' if mode==1 else 'uncompressDataGzip'
    for facade in range(4):
     id=add(mode,facade,damaged)
     error_anchors[id]={'error':f'(IOException) Internal error in {name}, inflate_res is -3','output':(data[:(n//32768)*32768] if facade in [0,2] else b'sentinel').hex()}
    add(3-mode,0,wire)
 hello=bytes.fromhex('789ccb48cdc9c90700062c0215')
 assert zlib.decompress(hello)==b'hello'
 for facade in range(4):add(1,facade,hello,expect=b'hello')
 for mode in [0,1,2]:
  for facade in range(2 if mode==0 else 4):add(mode,facade,b'',expect=b'')
 co=zlib.compressobj(zdict=b'hello dictionary');dictionary=co.compress(b'hello dictionaryhello')+co.flush()
 for facade in range(4):add(1,facade,dictionary)
 fixture=out/'cases.tsv';fixture.write_text('\n'.join(' '.join(map(str,c)) for c in cases)+'\n');(out/'anchors.json').write_text(json.dumps(dict(success=anchors,error=error_anchors),sort_keys=True))
 sources=[HERE/'lab.cpp',HERE/'StarCompression.reference.cpp',ROOT/'source/core/StarCompression.cpp',HERE/'StarCompression.original.cpp']
 tracked=[*([rust_archive,*sorted((ROOT/'source/rust').rglob('*.rs'))] if rust else []),Path(sys.executable).resolve(),Path(zlib.__file__),Path(gzip.__file__),HERE/'run.py',*sources,HERE/'StarCompression.original.hpp',HERE/'StarCompression.reference.hpp',db,cm/'build.ninja',Path(recipe[0]).resolve(),fixture,out/'anchors.json',*objs,*[Path(x) for x in libs if x.endswith('.a')]]
 for n,src in enumerate(sources):
  dep=out/(str(n)+'.d');r=run([recipe[0],*flags,'-I'+str(HERE),*(['-DSTAR_USE_RUST_COMPRESSION=1','-DLAB_RUST=1'] if rust else []),'-M','-MF',dep,src],'deps'+str(n))
  if r.returncode:raise RuntimeError('dependency scan failure')
  tracked += [Path(x) if Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])]
 tracked=list(dict.fromkeys(x.resolve() for x in tracked));before={str(x):sha(x) for x in tracked};(out/'before.json').write_text(json.dumps(before,indent=2))
 native=out/'native-core.a'
 if run(['/usr/bin/ar','rcs',native,*objs],'archive').returncode:raise RuntimeError('private archive failure')
 def compile(name,src,reference=False,lab=None,selected=False):
  extra=['-DSTAR_USE_RUST_COMPRESSION=1','-DLAB_RUST=1'] if selected and rust else []
  binary=out/name;source_before=sha(src);r=run([recipe[0],*flags,'-I'+str(HERE),*extra,*(['-DLAB_REFERENCE=1'] if reference else []),lab or HERE/'lab.cpp',src,native,*([rust_archive] if selected and rust else []),*libs,'-Wl,-dead_strip','-o',binary],name+'-compile')
  if r.returncode:raise RuntimeError('compile failure '+name+' (not a credited negative)')
  if sha(src)!=source_before:raise RuntimeError('compile source drift')
  generated_source_receipts[str(src)]={'before':source_before,'after':sha(src)}
  return binary
 def observe(binary,name):
  before_binary=sha(binary)
  r=run([binary,fixture],name)
  if r.returncode:raise RuntimeError('runtime failure '+name)
  if sha(binary)!=before_binary:raise RuntimeError('executable drift '+name)
  runtime_receipts.append(dict(name=name,binary=str(binary),before=before_binary,after=sha(binary),stream_sha256=hashlib.sha256(r.stdout).hexdigest()))
  return r.stdout
 archive_before=sha(native)
 binary=compile('candidate',ROOT/'source/core/StarCompression.cpp',selected=True);baseline=observe(binary,'baseline');reference=compile('reference',HERE/'StarCompression.reference.cpp',True);ref=observe(reference,'reference');independent=compile('original',HERE/'StarCompression.original.cpp');ind=observe(independent,'original')
 def check(stream):
  if stream!=ref:raise ValueError('COMPARISON ordered native stream')
  rows={x.split(b'\t')[0].decode():x.split(b'\t') for x in stream.splitlines()}
  for id,want in anchors.items():
   if rows[id][1] or rows[id][2].decode()!=want:raise ValueError('COMPARISON independent producer/literal '+id)
  for id,want in error_anchors.items():
   if bytes.fromhex(rows[id][1].decode()).decode()!=want['error'] or rows[id][2].decode()!=want['output']:raise ValueError('COMPARISON independent error/partial anchor '+id)
  for id,mode,facade,level,alias,length,limit,encoded in cases:
   # Compression representation is bound to native reference, not Python version;
   # Python independently checks the native output's actual decompressed bytes.
   if mode==0 and not alias and length and not rows[id][1]:
    if zlib.decompress(bytes.fromhex(rows[id][2].decode()))!=bytes.fromhex(encoded):raise ValueError('COMPARISON independent compressed payload '+id)
 check(baseline);check(ind);check(observe(binary,'repeat'))
 if hashlib.sha256(ind).hexdigest()!='bcf3f6fe8dd2f31fb896743ca555a37bc56222d18c801713b57d5296216d5582':raise RuntimeError('frozen original ordered stream drift')
 if rust:
  # A zeroed receipt must fail at runtime even if byte behavior is unchanged.
  receipt_lab=out/'suppressed-receipt.cpp';receipt_lab.write_bytes((HERE/'lab.cpp').read_bytes().replace(b'star_compression_call_count(k,e)-counters[k][e]',b'uint64_t(0)'))
  bad=compile('suppressed-receipt',ROOT/'source/core/StarCompression.cpp',lab=receipt_lab,selected=True)
  result=run([bad,fixture],'suppressed-receipt-run')
  if result.returncode==0 or b'COMPARISON selected controller TLS receipt' not in result.stderr:raise RuntimeError('receipt suppression not detected at runtime')
  negative.append('selected-receipt-suppression')
  production=(ROOT/'source/core/StarCompression.cpp').read_bytes();host=(ROOT/'source/core/StarCompressionHost.hpp').read_bytes()
  mutations=[('clear',b'x.output.clear();',b'(void)0;'),('errorclass',b'throw IOException(',b'throw StarException('),('hoststatus',b'return SC_OK;',b'return SC_HOST_INVALID;')]
  for name,old,new in mutations:
   if old not in host:raise RuntimeError('selected host mutant anchor missing '+name)
   header=out/(name+'-host.hpp');header.write_bytes(host.replace(old,new));header_before=sha(header)
   source=out/(name+'-selected.cpp');source.write_bytes(production.replace(b'"StarCompressionHost.hpp"',('"'+str(header)+'"').encode()))
   bad=compile(name+'-selected',source,selected=True);result=run([bad,fixture],name+'-selected-run')
   if sha(header)!=header_before:raise RuntimeError('generated host header drift')
   generated_source_receipts[str(header)]={'before':header_before,'after':sha(header)}
   if result.returncode:
    if result.returncode!=1 or b'COMPARISON selected controller TLS receipt' not in result.stderr:raise RuntimeError('selected mutant non-comparison failure '+name)
   else:
    try:check(result.stdout)
    except ValueError:pass
    else:raise RuntimeError('selected host mutant escaped '+name)
   negative.append('selected-host-'+name)
  source=out/'dispatch-selected.cpp';source.write_bytes(production.replace(b'CompressionHost::run(context);',b'context.kind = SC_INFLATE; CompressionHost::run(context);',1))
  # Use an empty first case: wrong dispatch is observed before native input access.
  bad=compile('dispatch-selected',source,selected=True);result=run([bad,fixture],'dispatch-selected-run')
  if result.returncode!=1 or b'COMPARISON selected controller TLS receipt' not in result.stderr:raise RuntimeError('selected dispatch mutant not cleanly detected')
  negative.append('selected-dispatch')
 raw=(HERE/'StarCompression.original.cpp').read_bytes()
 mutants=[('clear-order',b'  out.clear();\n\n  if (in.empty())\n    return;',b'  if (in.empty())\n    return;\n  out.clear();'),('full-limit',b'out.size() >= limit',b'out.size() > limit'),('discard-partial',b'  if (inflate_res != Z_STREAM_END)\n    throw',b'  if (inflate_res != Z_STREAM_END) out.clear();\n  if (inflate_res != Z_STREAM_END)\n    throw'),('final-limit',b'  out.append((char const*)tempBuffer.get(), BUFSIZE - strm.avail_out);',b'  if (limit && out.size() + BUFSIZE - strm.avail_out >= limit) throw IOException("wrong final limit");\n  out.append((char const*)tempBuffer.get(), BUFSIZE - strm.avail_out);')]
 for name,old,new in mutants:
  body=raw
  if name=='final-limit':
   # Only inflate controllers have a limit argument.
   pivot=body.index(b'void uncompressData(');body=body[:pivot]+body[pivot:].replace(old,new)
  else:body=body.replace(old,new)
  if body==raw:raise RuntimeError('mutant anchor missing')
  src=out/(name+'.cpp');src.write_bytes(body);bad=observe(compile(name,src),name)
  try:check(bad)
  except ValueError:negative.append(name)
  else:raise RuntimeError('runtime mutant escaped '+name)
 # Paired corruption bypasses candidate/reference equality but not independent anchors.
 old=b'  out.append((char const*)tempBuffer.get(), BUFSIZE - strm.avail_out);';new=b'  out.append((char const*)tempBuffer.get(), 0);'
 paired=out/'paired.cpp';paired.write_bytes(raw.replace(old,new));bad=observe(compile('paired',paired),'paired');saved=ref;ref=bad
 try:check(bad)
 except ValueError as e:
  if 'independent' not in str(e):raise
  negative.append('paired-independent-anchor')
 else:raise RuntimeError('paired corruption escaped')
 ref=saved
 try:check(baseline+b'corrupt')
 except ValueError:negative.append('verifier-stream-corruption')
 else:raise RuntimeError('checker negative escaped')
 after={str(x):sha(x) for x in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after:raise RuntimeError('bound artifact drift')
 if sha(native)!=archive_before:raise RuntimeError('private archive drift')
 codec_version=run([binary,'--version'],'codec-version').stdout.decode().strip()
 executables={str(x):sha(x) for x in out.iterdir() if x.is_file() and os.access(x,os.X_OK)}
 def identity(binding,stream_hash):
  if binding!=before or stream_hash!=hashlib.sha256(baseline).hexdigest():raise ValueError('source/stream provenance mismatch')
 identity(before,hashlib.sha256(baseline).hexdigest())
 for label,binding,stream_hash in [('wrong-source',{},hashlib.sha256(baseline).hexdigest()),('wrong-stream',before,'wrong')]:
  try:identity(binding,stream_hash)
  except ValueError:negative.append(label)
  else:raise RuntimeError('provenance control escaped')
 report=dict(status='PASS',backend=a.backend,revision=REV,cases=len(cases),independent_anchors=len(anchors)+len(error_anchors),negative_controls=negative,ordered_observations_sha256=hashlib.sha256(baseline).hexdigest(),bindings=before,executables=executables,runtime_receipts=runtime_receipts,generated_source_receipts=generated_source_receipts,native_archive_sha256=sha(native),commands=commands,python_zlib=zlib.ZLIB_RUNTIME_VERSION,native_zlib_ng=codec_version,python_version=sys.version,limits=['selected production controller backend; no game claim','finite corpus, no actual OOM injection or C API call traces','wrong deflate error text is source-only, not forced here','virtual size narrowing probes only raw zlib/gzip void controllers; no 4GiB allocation or returning facades','alias probes only reserved stable allocations, compressed input <= one slab','no CompressedFile methods invoked'])
 (out/'observations.tsv').write_bytes(baseline);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['bindings','commands','executables','runtime_receipts','generated_source_receipts']}))
if __name__=='__main__':main()
