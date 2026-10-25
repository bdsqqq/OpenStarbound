#!/usr/bin/env python3
"""Finite native calibration; offline vendor fixtures except numeric localhost."""
import argparse,hashlib,json,pathlib,re,shlex,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[3]; HERE=pathlib.Path(__file__).resolve().parent; REV='77e35ba8'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def adapt(s,ext):
 token=re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\b[A-Za-z_]\w*\b')
 s=token.sub(lambda m:{'HostAddress':'HostAddressReference','HostAddressWithPort':'HostAddressWithPortReference'}.get(m[0],m[0]),s)
 if ext=='cpp':return s.replace('#include "StarHostAddress.hpp"','#include "StarHostAddress.reference.hpp"',1)
 return s.replace('#pragma once','#pragma once\n#include "StarHostAddress.hpp"',1).replace('STAR_EXCEPTION(NetworkException, IOException);\n','',1).replace('enum class NetworkMode {\n  IPv4,\n  IPv6\n};\n','',1)
def gate(ext,raw,ref):
 frozen=subprocess.check_output(['git','show',REV+':source/core/StarHostAddress.'+ext],cwd=ROOT).decode()
 current=(ROOT/f'source/core/StarHostAddress.{ext}').read_text()
 if ext=='cpp' and current!=frozen:
  # The default-OFF production branch remains the original source, byte for
  # byte. A selector must not silently bless a changed native oracle.
  prefix,body=frozen.split('namespace Star {',1)
  marker='\n#else\n';ending='#endif\n'
  if current.count(marker)!=1 or not current.endswith(ending):raise ValueError('native fallback framing')
  selected,native=current.split(marker)
  if not selected.startswith(prefix+'#ifdef STAR_USE_RUST_HOST_ADDRESS\n') or native[:-len(ending)]!='namespace Star {'+body:raise ValueError('native fallback provenance')
 elif current!=frozen:raise ValueError('current source provenance')
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
 mask=(1<<64)-1
 for mode in (0,1):
  for pattern in range(16):
   b=[pattern if pattern<4 else (i*pattern+193)%256 for i in range(16)]
   if pattern==3:
    b=[0]*16;b[3 if mode==0 else 15]=1
    if mode==0:b[0]=127
   if pattern==4 and mode==0:b[:4]=[127,0,0,2]
   b=b[:4 if mode==0 else 16];h=0
   for x in b:h=(h*101+x)&mask
   text='.'.join(map(str,b)) if mode==0 else ':'.join(f'{b[i]:02x}{b[i+1]:02x}' for i in range(0,16,2))
   fields=dict(bytes=bytes(b).hex(),hash=h,text=text.encode().hex(),local=int(b==([127,0,0,1] if mode==0 else [0]*15+[1])),copyeq=1,othereq=0)
   need(f'raw/{mode}/{pattern}',**fields)
   for port in (0,80,65535):
    eh=h^((port*2654435761+0x9e3779b9+((h<<6)&mask)+(h>>2))&mask)
    need(f'endpoint/{mode}/{pattern}/{port}',port=port,ehash=eh,endpoint=(text+':'+str(port)).encode().hex())
 for m in (2,-1,2147483647):
  need(f'null/{m}',mode=m,size=0,zero=0,local=0,hash=0,copyeq=1)
  need(f'localhost/{m}',mode=0,size=4,zero=1,local=0,hash=0)
 for m in (2,-1,2147483647):
  need(f'unknown-initialized/{m}',mode=m,size=0,zero=0,local=1,hash=0,zeroeq=1,octet15=1)
 need('initialized-tail-ipv4',mode=0,size=4,zero=1,local=0,hash=0,zeroeq=1,octet15=1)
 need('endpoint-ctor/313233',port=123,text=b'0.0.0.0'.hex())
 need('endpoint-ctor/3635353336',port=0)
 for h in ('','*','::','[::]','[::1]','[bad','bad]','bad'):
  need('parse/'+h.encode().hex()+'/4',port=0)
 # Padding writes are libc++ mechanics, not one xsputn per insertion. Keep
 # exact chunks in whole-stream comparison; anchor text and late reads here.
 need('stream/1/0/0',text=b'127.0.0.1_____:1bb'.hex(),port=443)
 need('stream/2/0/0',text=b'127.0.0.1_____:1bb'.hex(),port=443)
 for i in range(2):need(f'real-numeric/{i}',text=b'127.0.0.1'.hex(),local=1)
 return len(r)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=pathlib.Path);ap.add_argument('--identity-manifest',required=True,type=pathlib.Path);a=ap.parse_args();out=a.output.absolute();base=ROOT/'build/host-address-lab'
 if out.exists() or not out.is_relative_to(base) or out==base or any(p.is_symlink() for p in [out,*out.parents]):ap.error('fresh owned nonsymlink output required')
 out.mkdir(parents=True);receipts=[];controls=[]
 def run(cmd,name):
  cmd=list(map(str,cmd));r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=75);(out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr);receipts.append(dict(name=name,command=cmd,returncode=r.returncode,executable_sha256=sha(pathlib.Path(cmd[0]).resolve()),stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stderr_sha256=hashlib.sha256(r.stderr).hexdigest()));(out/'receipts.json').write_text(json.dumps(receipts,indent=2))
  if r.returncode:raise RuntimeError(name+' failed, not a successful negative')
  return r.stdout
 for ext in ('cpp','hpp'):
  raw=(HERE/f'StarHostAddress.original.{ext}').read_text();ref=(HERE/f'StarHostAddress.reference.{ext}').read_text();gate(ext,raw,ref)
  for x,y in ((raw+' ',ref),(raw,ref+' ')):
   try:gate(ext,x,y)
   except ValueError:controls.append('provenance-'+ext)
   else:raise RuntimeError('bad provenance accepted')
 cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarHostAddress.cpp'));recipe=shlex.split(entry['command']);flags=[];skip=False
 for x in recipe[1:]:
  if skip:skip=False;continue
  if x=='-o':skip=True
  elif x not in ('-c',entry['file']):flags.append(x)
 if any('STAR_USE_RUST' in f for f in flags):raise RuntimeError('not native')
 lines=(cm/'build.ninja').read_text().splitlines();idx=next(i for i,l in enumerate(lines) if l.startswith('build ') and '/bin/starbound:' in l)
 objs=[cm/x for x in shlex.split(lines[idx].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/')) and not x.endswith('/StarHostAddress.cpp.o')]
 libs=shlex.split(next(l.split(' = ',1)[1] for l in lines[idx+1:idx+15] if l.startswith('  LINK_LIBRARIES = ')));libs=[str(cm/x) if x.endswith('.a') and not pathlib.Path(x).is_absolute() else x for x in libs]
 identity=[db,cm/'build.ninja',pathlib.Path(recipe[0]).resolve(),*objs,*[pathlib.Path(x) for x in libs if x.endswith('.a')]];seal=json.loads(a.identity_manifest.read_text())
 for p in identity:
  if seal.get(str(p.resolve()))!=sha(p):raise RuntimeError('identity drift '+str(p))
 tracked=[*identity,a.identity_manifest,HERE/'run.py',HERE/'lab.cpp',pathlib.Path(sys.executable).resolve(),pathlib.Path('/usr/bin/ar').resolve(),ROOT/'source/core/StarHostAddress.cpp',ROOT/'source/core/StarHostAddress.hpp',*[HERE/f'StarHostAddress.{k}.{e}' for k in ('original','reference') for e in ('cpp','hpp')]]
 for n,s in enumerate([HERE/'lab.cpp',HERE/'StarHostAddress.original.cpp',HERE/'StarHostAddress.reference.cpp']):
  dep=out/f'{n}.d';run([recipe[0],*flags,'-I'+str(HERE),'-M','-MF',dep,s],f'deps{n}');tracked.extend(pathlib.Path(x) if pathlib.Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]))
 tracked=list(dict.fromkeys(p.resolve() for p in tracked));before={str(p):sha(p) for p in tracked};(out/'before.json').write_text(json.dumps(before,indent=2));archive=out/'native-core.a';run(['/usr/bin/ar','rcs',archive,*objs],'archive');archivehash=sha(archive);generated={};binaries={}
 def compile(name,source,ref=False):
  exe=out/name;generated[str(source)]=sha(source);run([recipe[0],*flags,'-I'+str(HERE),*(['-DLAB_REFERENCE'] if ref else []),HERE/'lab.cpp',source,archive,*libs,'-Wl,-dead_strip','-o',exe],name+'-compile');binaries[str(exe)]=sha(exe);return exe
 orig=compile('original',HERE/'StarHostAddress.original.cpp');ref=compile('reference',HERE/'StarHostAddress.reference.cpp',True);current=compile('current',ROOT/'source/core/StarHostAddress.cpp');baseline=run([orig],'original');count=anchors(baseline)
 for exe,name in ((orig,'repeat'),(ref,'reference'),(current,'current')):
  got=run([exe],name);anchors(got)
  if got!=baseline:raise ValueError('whole ordered mismatch '+name)
 broken=baseline.replace(b'127',b'126',1)
 try:anchors(broken)
 except ValueError:controls.append('known-bad-literal')
 else:
  broken=baseline.replace(b'hash=0',b'hash=9',1)
  try:anchors(broken)
  except ValueError:controls.append('known-bad-literal')
  else:raise RuntimeError('bad fixture escaped')
 (out/'known-bad.stdout').write_bytes(broken)
 source=(HERE/'StarHostAddress.original.cpp').read_text();mutants={
 'last-resolver':source.replace('      break;\n    }\n    freeaddrinfo(result);','    }\n    freeaddrinfo(result);'),
 'localhost-range':source.replace('m_address[0] == 127 && m_address[1] == 0 && m_address[2] == 0 && m_address[3] == 1','m_address[0] == 127'),
 'unknown-localhost':source.replace('bool HostAddress::isLocalHost() const {','bool HostAddress::isLocalHost() const {\n  if (m_mode != NetworkMode::IPv4 && m_mode != NetworkMode::IPv6) return false;'),
 'octet-active-only':source.replace('uint8_t HostAddress::octet(size_t i) const {','uint8_t HostAddress::octet(size_t i) const {\n  if (i >= size()) return 0;'),
 'mode-hash':source.replace('PLHasher hash;','PLHasher hash((size_t)address.mode());'),
 'free-omission':source.replace('    freeaddrinfo(result);','    (void)result;'),
 'bracket-require':source.replace('String host = address;','if (!address.beginsWith("[")) return makeLeft(String("brackets required"));\n  String host = address;'),
 'overflow-reject':source.replace('if (!portNum)','if (!portNum || (port.utf8() == "65536"))'),
 'early-port':source.replace('  os << addressWithPort.address() << ":" << addressWithPort.port();','  auto p=addressWithPort.port(); os << addressWithPort.address() << ":" << p;'),
 'giant-endpoint':source.replace('  os << addressWithPort.address() << ":" << addressWithPort.port();','  format(os, "{}:{}", addressWithPort.address(), addressWithPort.port());'),
 'ipv6-compress':source.replace('    case NetworkMode::IPv6:\n      format(os,','    case NetworkMode::IPv6:\n      if (address.isZero()) { os << "::"; break; }\n      format(os,')}
 for name,body in mutants.items():
  if body==source:raise RuntimeError('empty mutant '+name)
  p=out/(name+'.cpp');p.write_text(body);exe=compile(name,p);got=run([exe],name)
  if got==baseline:raise RuntimeError('mutant escaped '+name)
  controls.append(name)
 paired=out/'paired.cpp';paired.write_text(mutants['mode-hash']);e1=compile('paired-a',paired);e2=compile('paired-b',paired);wrong=run([e1],'paired-a');wrong2=run([e2],'paired-b')
 if wrong!=wrong2:raise RuntimeError('paired wrong differed')
 try:anchors(wrong)
 except ValueError:controls.append('paired-wrong-literal')
 else:raise RuntimeError('paired wrong escaped')
 after={str(p):sha(p) for p in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after or archivehash!=sha(archive) or any(sha(p)!=h for p,h in {**generated,**binaries}.items()):raise RuntimeError('artifact drift')
 report=dict(status='FINITE_NATIVE_CALIBRATION_PASS',revision=REV,cases=count,controls=controls,ordered_sha256=hashlib.sha256(baseline).hexdigest(),bindings=before,generated=generated,binaries=binaries,archive_sha256=archivehash,receipts=receipts,link=dict(compiler=recipe[0],flags=flags,libraries=libs,archive=str(archive)),limits=['Native-only, no Rust or application or TCP qualification','Scripted vendor fixtures are counterfactual, not actual DNS behavior','Only real resolver calls are strict canonical 127.0.0.1 with unchanged native hints','No object padding or inactive IPv4 tail reads; unknown modes use null initialization','Finite stream fault and late mutation observations, no allocation/destruction timing claim'])
 (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ('status','cases','controls','ordered_sha256')}))
if __name__=='__main__':main()
