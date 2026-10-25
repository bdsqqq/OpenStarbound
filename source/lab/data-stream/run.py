#!/usr/bin/env python3
"""Finite whole-compiled-DataStream calibration; native scripted virtual I/O."""
import argparse,hashlib,json,pathlib,re,shlex,subprocess,sys,shutil
ROOT=pathlib.Path(__file__).resolve().parents[3]; HERE=pathlib.Path(__file__).resolve().parent; REV='9f2316a22d5abcb10ff2778b628bc3bef7de5b99'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def adapt(s,ext):
 token=re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b[A-Za-z_]\w*\b')
 s=token.sub(lambda m:{'DataStream':'DataStreamReference','CurrentStreamVersion':'ReferenceCurrentStreamVersion'}.get(m[0],m[0]),s)
 if ext=='cpp':return s.replace('#include "StarDataStream.hpp"','#include "StarDataStream.reference.hpp"',1)
 return s.replace('#pragma once','#pragma once\n#include "StarDataStream.hpp"',1).replace('STAR_EXCEPTION(DataStreamException, IOException);\n','',1)
def native_off_source(source):
 # Retain every byte of the frozen namespace, including comments and spacing.
 # Only a unique outer selector branch may supply the original implementation.
 depth=0; start=None; end=None; close=None; selectors=0
 for match in re.finditer(r'^[ \t]*#[ \t]*(if|ifdef|ifndef|else|elif|endif)\b([^\n]*)\n?',source,re.M):
  kind,tail=match.group(1,2)
  if kind in ('if','ifdef','ifndef'):
   if depth==0 and 'STAR_USE_RUST_DATA_STREAM' in tail: selectors+=1
   depth+=1
  elif kind=='else' and depth==1:
   if start is not None: raise ValueError('multiple outer else branches')
   start=match.end()
  elif kind=='elif' and depth==1: raise ValueError('outer elif unsupported')
  elif kind=='endif':
   depth-=1
   if depth==0 and start is not None:
    if end is not None: raise ValueError('multiple outer selectors')
    end=match.start();close=match.end()
  if depth<0: raise ValueError('unbalanced preprocessor')
 if depth or selectors!=1 or start is None or end is None:
  raise ValueError('unique outer DataStream selector required')
 if source[close:]!='':raise ValueError('unexpected post-selector source')
 branch=source[start:end]
 if not branch.startswith('namespace Star {') or not branch.endswith('\n\n'):raise ValueError('unexpected native wrapper separators')
 # The wrapper owns exactly one newline before #endif; every remaining byte
 # belongs to the frozen namespace. No stripping or whitespace normalization.
 return branch[:-1]

def gate(ext,raw,ref):
 frozen=subprocess.check_output(['git','show',REV+':source/core/StarDataStream.'+ext],cwd=ROOT).decode()
 current=(ROOT/f'source/core/StarDataStream.{ext}').read_text()
 if ext=='cpp' and current!=frozen:
  selector=re.search(r'^#if defined\(STAR_USE_RUST_DATA_STREAM\)\n',current,re.M)
  if not selector or current[:selector.start()]!=frozen[:frozen.index('namespace Star {')]:raise ValueError('native prefix provenance')
  if native_off_source(current)!=frozen[frozen.index('namespace Star {'):]:raise ValueError('native OFF source provenance')
 elif current!=frozen:raise ValueError('source provenance')
 if raw!=frozen or ref!=adapt(frozen,ext):raise ValueError('source provenance')
def rows(data):
 out={}
 for line in data.decode().splitlines():
  key,*fields=line.split('|')
  if key in out:raise ValueError('duplicate record')
  parsed=[f.split('=',1) for f in fields]
  if len({p[0] for p in parsed})!=len(parsed):raise ValueError('duplicate field')
  out[key]=dict(parsed)
 return out
def anchors(data):
 r=rows(data)
 def need(key,**fields):
  for k,v in fields.items():
   if r[key].get(k)!=str(v):raise ValueError(f'literal {key} {k}: {r[key].get(k)} != {v}')
 need('default',order=0,null=0,version=21)
 for order in (0,1,2,-1,3,2147483647):
  for name,bits,n in [('char',0xa5,1),('i8',0xa5,1),('u8',0xa5,1),('i16',0xa153,2),('u16',0xa153,2),('i32',0xa1537294,4),('u32',0xa1537294,4),('i64',0xa1537294b6c8d0ef,8),('u64',0xa1537294b6c8d0ef,8)]+[('f32',b,4) for b in (0,0x80000000,0x7f800000,0xff800000,0x7fc12345)]+[('f64',b,8) for b in (0,0x8000000000000000,0x7ff0000000000000,0xfff0000000000000,0x7ff8123456789abc)]:
   wire=bits.to_bytes(n,'little' if order in (1,2) or n==1 else 'big').hex()
   need(f'write/{name}/{bits}/{order}',bytes=wire,identity=1)
   need(f'read/{name}/{bits}/{order}',value=bits.to_bytes(n,'little').hex(),identity=1)
 def vlq(v):
  digits=[v%128];v//=128
  while v:digits.insert(0,v%128);v//=128
  return bytes([x|128 for x in digits[:-1]]+digits[-1:]).hex()
 for key,fields in r.items():
  if key.startswith('vlqu/write/'):
   v=int(key.rsplit('/',1)[1]);need(key,bytes=vlq(v),value=len(bytes.fromhex(vlq(v))))
  if key.startswith('vlqi/write/'):
   v=int(key.rsplit('/',1)[1]);encoded=vlq(2*v if v>=0 else -2*v-1);need(key,bytes=encoded,value=len(bytes.fromhex(encoded)))
  if key.startswith('vlqs/write/'):
   v=int(key.rsplit('/',1)[1]);need(key,bytes=vlq(0 if v==2**64-1 else v+1))
  if key.startswith('strings/write/'):
   _,_,term,ver,h,kind=key.split('/');payload=bytes.fromhex(h)
   if kind=='0':payload=payload.split(b'\0')[0]
   wire=payload+b'\0' if term=='1' and kind!='2' else bytes.fromhex(vlq(len(payload)))+payload
   need(key,bytes=wire.hex(),identity=1)
 need('array/late-payload',bytes='01'+b'expanded'.hex())
 need('string/captured-inplace',bytes='03'+b'aZc'.hex())
 need('strings/branch-snapshot',value=b'abc'.hex(),pos=4)
 need('bool/nonzero',value=1)
 need('bool/fault-result',value=0)
 need('isolated/write-before-hook',bytes='12345678',order=1)
 need('isolated/fault/0/2',value=b'old'.hex())
 need('isolated/fault/1/2',value=b'old'.hex())
 need('isolated/fault/1/0',value='')
 need('devices/functions-ignore-count',value='1:1:51')
 need('devices/readFull-once',value='785151:1')
 for key,fields in r.items():
  if key.startswith('fresh/'):
   name,bits,order=key.split('/')[1:];n=len(bytes.fromhex(fields['value']));need(key,value=bytes(range(0x12,0x12+n)).hex(),order=1)
  if key.startswith('partial/'):
   name,bits,order=key.split('/')[1:];n=len(bytes.fromhex(fields['value']));need(key,value=(b'\x12'+int(bits).to_bytes(n,'little')[1:]).hex())
  if fields['error'].startswith(b'Fault:'.hex()) and not bytes.fromhex(fields['error']).endswith(b':same=1'):raise ValueError('exception identity')
 need('vlqi/extreme/81ffffffffffffffff7f',value='-9223372036854775808:10')
 need('vlqi/extreme/81ffffffffffffffff7e',value='9223372036854775807:10')
 return len(r)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=pathlib.Path);ap.add_argument('--identity-manifest',required=True,type=pathlib.Path);a=ap.parse_args();out=a.output.absolute();base=ROOT/'build/data-stream-lab'
 if out.exists() or not out.is_relative_to(base) or out==base or not out.name.startswith('oracle-') or any(p.is_symlink() for p in [out,*out.parents]):ap.error('fresh owned nonsymlink output required')
 out.mkdir(parents=True);receipts=[];controls=[]
 if shutil.disk_usage(out).free < 1024**3:raise RuntimeError('less than 1 GiB free')
 def run(cmd,name):
  cmd=list(map(str,cmd));r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=75);(out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr);receipts.append(dict(name=name,command=cmd,returncode=r.returncode,executable_sha256=sha(pathlib.Path(cmd[0]).resolve()),stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stderr_sha256=hashlib.sha256(r.stderr).hexdigest()));(out/'receipts.json').write_text(json.dumps(receipts,indent=2))
  if r.returncode:raise RuntimeError(name+' failed, not a successful negative')
  return r.stdout
 for ext in ('cpp','hpp'):
  raw=(HERE/f'StarDataStream.original.{ext}').read_text();ref=(HERE/f'StarDataStream.reference.{ext}').read_text();gate(ext,raw,ref)
  for x,y in ((raw+' ',ref),(raw,ref+' ')):
   try:gate(ext,x,y)
   except ValueError:controls.append('provenance-'+ext+('-raw' if x!=raw else '-reference'))
   else:raise RuntimeError('bad provenance accepted')
 cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarDataStream.cpp'));recipe=shlex.split(entry['command']);flags=[];skip=False
 for x in recipe[1:]:
  if skip:skip=False;continue
  if x=='-o':skip=True
  elif x not in ('-c',entry['file']):flags.append(x)
 if any('STAR_USE_RUST' in f for f in flags):raise RuntimeError('not native')
 lines=(cm/'build.ninja').read_text().splitlines();idx=next(i for i,l in enumerate(lines) if l.startswith('build ') and '/bin/starbound:' in l)
 objs=[cm/x for x in shlex.split(lines[idx].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/'))]
 libs=shlex.split(next(l.split(' = ',1)[1] for l in lines[idx+1:idx+15] if l.startswith('  LINK_LIBRARIES = ')));libs=[str(cm/x) if x.endswith('.a') and not pathlib.Path(x).is_absolute() else x for x in libs]
 identity=[db,cm/'build.ninja',pathlib.Path(recipe[0]).resolve(),*objs,*[pathlib.Path(x) for x in libs if x.endswith('.a')]];seal=json.loads(a.identity_manifest.read_text())
 for p in identity:
  if seal.get(str(p.resolve()))!=sha(p):raise RuntimeError('identity drift '+str(p))
 tracked=[*identity,a.identity_manifest,HERE/'run.py',HERE/'verify_receipts.py',HERE/'README.md',HERE/'lab.cpp',pathlib.Path(sys.executable).resolve(),pathlib.Path('/usr/bin/ar').resolve(),ROOT/'source/core/StarDataStream.cpp',ROOT/'source/core/StarDataStream.hpp',*[HERE/f'StarDataStream.{k}.{e}' for k in ('original','reference') for e in ('cpp','hpp')]]
 for n,s in enumerate([HERE/'lab.cpp',HERE/'StarDataStream.original.cpp',HERE/'StarDataStream.reference.cpp']):
  dep=out/f'{n}.d';run([recipe[0],*flags,'-I'+str(HERE),'-M','-MF',dep,s],f'deps{n}');tracked.extend(pathlib.Path(x) if pathlib.Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]))
 tracked=list(dict.fromkeys(p.resolve() for p in tracked));before={str(p):sha(p) for p in tracked};(out/'before.json').write_text(json.dumps(before,indent=2));archive=out/'native-core.a';run(['/usr/bin/ar','rcs',archive,*objs],'archive');archivehash=sha(archive);generated={};binaries={}
 def compile(name,source,ref=False):
  exe=out/name;generated[str(source)]=sha(source);run([recipe[0],*flags,'-I'+str(HERE),*(['-DLAB_REFERENCE'] if ref else []),'-UNDEBUG',HERE/'lab.cpp',source,archive,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/(name+'.map')),'-o',exe],name+'-compile');binaries[str(exe)]=sha(exe);return exe
 orig=compile('original',HERE/'StarDataStream.original.cpp');ref=compile('reference',HERE/'StarDataStream.reference.cpp',True);current=compile('current',ROOT/'source/core/StarDataStream.cpp');baseline=run([orig],'original');count=anchors(baseline)
 for exe,name in ((orig,'repeat'),(ref,'reference'),(current,'current')):
  got=run([exe],name);anchors(got)
  if got!=baseline:raise ValueError('whole ordered mismatch '+name)
 broken=baseline.replace(b'version=21',b'version=22',1)
 try:anchors(broken)
 except ValueError:controls.append('known-bad-literal')
 else:
  broken=baseline.replace(b'hash=0',b'hash=9',1)
  try:anchors(broken)
  except ValueError:controls.append('known-bad-literal')
  else:raise RuntimeError('bad fixture escaped')
 (out/'known-bad.stdout').write_bytes(broken)
 source=(HERE/'StarDataStream.original.cpp').read_text();mutants={
 'wrong-endian':source.replace('toByteOrder(m_byteOrder, d)','toByteOrder(ByteOrder::LittleEndian, d)'),
 'pre-read-order':source.replace('  readData((char*)&d, sizeof(d));\n  d = fromByteOrder(m_byteOrder, d);','  auto order = m_byteOrder;\n  readData((char*)&d, sizeof(d));\n  d = fromByteOrder(order, d);'),
 'transactional-read':source.replace('  readData((char*)&d, sizeof(d));\n  d = fromByteOrder(m_byteOrder, d);','  std::decay_t<decltype(d)> tmp{};\n  readData((char*)&tmp, sizeof(tmp));\n  d = fromByteOrder(m_byteOrder, tmp);'),
 'skip-empty':source.replace('  writeData(ba.ptr(), ba.size());','  if (ba.size()) writeData(ba.ptr(), ba.size());'),
 'prefetch-array':source.replace('  writeVlqU(d.size());\n  writeData(d.ptr(), d.size());','  auto len=d.size();\n  writeVlqU(len);\n  writeData(d.ptr(), len);'),
 'late-clear':source.replace('    d.clear();','    bool first=true;').replace('      d.push_back(c);','      if(first){d.clear();first=false;}\n      d.push_back(c);'),
 'early-string':source.replace('  std::string string;\n  operator>>(string);','  s = String();\n  std::string string;\n  operator>>(string);'),
 'branch-reread':source.replace("      if (c == '\\0')","      if (c == '\\0' || !m_nullTerminatedStrings)"),
 'vlq-partial':source.replace('  size_t bytesRead = Star::readVlqU(i,','  uint64_t staged = 0;\n  size_t bytesRead = Star::readVlqU(staged,').replace('  return bytesRead;\n}\n\nsize_t DataStream::readVlqI','  i = staged;\n  return bytesRead;\n}\n\nsize_t DataStream::readVlqI')}
 for name,body in mutants.items():
  if body==source:raise RuntimeError('empty mutant '+name)
  p=out/(name+'.cpp');p.write_text(body);exe=compile(name,p);got=run([exe],name)
  if got==baseline:raise RuntimeError('mutant escaped '+name)
  controls.append(name)
 paired=out/'paired.cpp';paired.write_text(mutants['wrong-endian']);e1=compile('paired-a',paired);e2=compile('paired-b',paired);wrong=run([e1],'paired-a');wrong2=run([e2],'paired-b')
 if wrong!=wrong2:raise RuntimeError('paired wrong differed')
 try:anchors(wrong)
 except ValueError:controls.append('paired-wrong-literal')
 else:raise RuntimeError('paired wrong escaped')
 refbad=out/'reference-class-only.cpp';refbad.write_text((HERE/'StarDataStream.reference.cpp').read_text().replace('unsigned const ReferenceCurrentStreamVersion = 21','unsigned const ReferenceCurrentStreamVersion = 22'))
 refexe=compile('reference-class-only',refbad,True);refgot=run([refexe],'reference-class-only')
 if refgot==baseline:raise RuntimeError('renamed reference class bypass')
 controls.append('reference-class-only')
 for p in out.glob('*.map'):generated[str(p)]=sha(p)
 after={str(p):sha(p) for p in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after or archivehash!=sha(archive) or any(sha(p)!=h for p,h in {**generated,**binaries}.items()):raise RuntimeError('artifact drift')
 report=dict(status='FINITE_NATIVE_CALIBRATION_PASS',revision=REV,cases=count,controls=controls,ordered_sha256=hashlib.sha256(baseline).hexdigest(),bindings=before,generated=generated,binaries=binaries,archive_sha256=archivehash,receipts=receipts,link=dict(compiler=recipe[0],flags=flags,libraries=libs,archive=str(archive)),definitions=51,limits=['Native-only, no Rust or application or TCP qualification','Scripted I/O faults are counterfactual, not allocator failures','Initialized primitive partial reads only; ByteArray partial-tail storage preinitialized','Full signed VLQ write boundaries admitted by parent scoped C++17 shift probe; not full Core UB certification','Finite stream fault and late mutation observations, no allocation/destruction timing claim'])
 (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ('status','cases','controls','ordered_sha256')}))
if __name__=='__main__':main()
