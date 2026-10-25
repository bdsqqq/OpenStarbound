#!/usr/bin/env python3
"""Finite whole-compiled-Buffer calibration; native scripted virtual I/O."""
import argparse,hashlib,json,pathlib,re,shlex,subprocess,sys,shutil,collections
ROOT=pathlib.Path(__file__).resolve().parents[3]; HERE=pathlib.Path(__file__).resolve().parent; REV='021fc9eb2ba7d48b0432dd73d9777cd6d57f9822'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def adapt(s,ext):
 token=re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b[A-Za-z_]\w*\b')
 s=token.sub(lambda m:{'Buffer':'BufferReference','ExternalBuffer':'ExternalBufferReference'}.get(m[0],m[0]),s)
 return s.replace('#include "StarBuffer.hpp"','#include "StarBuffer.reference.hpp"',1) if ext=='cpp' else s

def gate(ext,raw,ref):
 frozen=subprocess.check_output(['git','show',REV+':source/core/StarBuffer.'+ext],cwd=ROOT).decode()
 if (ROOT/f'source/core/StarBuffer.{ext}').read_text()!=frozen or raw!=frozen or ref!=adapt(frozen,ext):raise ValueError('source provenance')

def rows(data):
 result={}
 for line in data.decode('ascii').splitlines():
  r=json.loads(line)
  if set(r)!={'key','value'} or r['key'] in result:raise ValueError('record schema/duplicate')
  result[r['key']]=r['value']
 return result

def anchors(data):
 r=rows(data)
 def need(k,v):
  if r[k]!=v:raise ValueError(f'literal {k}: {r[k]} != {v}')
 need('default','0:0:3:');need('size-ctor','0:4:3:00000000')
 need('growth','3:8:3:'+'51'*8);need('end','6:8:3:'+'51'*8);need('relative','5:8:3:'+'51'*8);need('unknown-seek','5:8:3:'+'51'*8)
 need('copy','5:8:1:'+'51'*8+':1');need('copy-deep','51515151:58515151');need('clone','1:1:0:1:1');need('clone-deep','61626364');need('clone-base','1:0')
 need('self-move','0:0:1:');need('device-name','1');need('external-name','1');need('external-default','0:0:1:1:1:1')
 need('reset-size','0:3:3:000000');need('reset-bytes','0:2:3:7879');need('clear','0:0:3::1');need('external-reset','0:0:1::1:1:1')
 need('external-clone-log','');need('external-clone-quiet','1:1:5:1');need('external-clone-shared','5a59636465666768');need('spy/identity','1:0:0:10:');need('absolute-partial','1:515a5a5a:2:4:3:51515151');need('absolute-gap','2:2:9:3:515151515151517879');need('external-eof','0:1:51');need('external-negative','0:8')
 if not r['external-clone'].startswith('Format:'):raise ValueError('native missing-format-argument')
 # Independent source model: all arithmetic bounded, complete initialized storage.
 for mode in range(16):
  for n in (0,1,4,8):
   k=f'matrix/{mode}/{n}/';n=0 if mode&2 and mode&8 else n;pos=n if mode&4 else 1;payload=bytearray(b'Q'*n)
   st=lambda:f'{pos}:{len(payload)}:{mode}:'+payload.hex()
   need(k+'open',st());need(k+'read-zero','0');need(k+'write-zero','0')
   if mode&1:
    count=min(max(n-pos,0),3);v=str(count)+':'+(b'Q'*count+b'Z'*(3-count)).hex();pos+=count
   else:v='IO:'+('(IOException) Error, read called on non-readable Buffer').encode().hex()+':5a5a5a'
   need(k+'read',v+':'+st())
   if mode&2:
    payload.extend(b'Q'*max(pos+3-len(payload),0));payload[pos:pos+3]=b'abc';pos+=3;v='3'
   else:v='Eof:'+('(EofException) Error, write called on non-writable Buffer').encode().hex()
   need(k+'write',v+':'+st())
   v='0' if mode&1 else 'IO:'+('(IOException) Error, read called on non-readable Buffer').encode().hex()
   need(k+'absolute',v+':'+str(pos));need(k+'absolute-zero','0:'+str(pos))
 return len(r)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=pathlib.Path);ap.add_argument('--identity-manifest',required=True,type=pathlib.Path);a=ap.parse_args();out=a.output.absolute();base=ROOT/'build/buffer-lab'
 if out.exists() or not out.is_relative_to(base) or out==base or not out.name.startswith('oracle-') or any(p.is_symlink() for p in [out,*out.parents]):ap.error('fresh owned nonsymlink output required')
 out.mkdir(parents=True);receipts=[];controls=[]
 sys.path.insert(0,str(ROOT/'source/lab/behavior'));import build_provenance as provenance
 native_binary=ROOT/'build/behavior/reference/bin/starbound';native_closure=provenance.verify(native_binary)
 if shutil.disk_usage(out).free < 1024**3:raise RuntimeError('less than 1 GiB free')
 def run(cmd,name):
  cmd=list(map(str,cmd));exe_before=sha(pathlib.Path(cmd[0]).resolve());r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=75);(out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr);receipts.append(dict(name=name,command=cmd,returncode=r.returncode,executable_sha256_before=exe_before,executable_sha256=sha(pathlib.Path(cmd[0]).resolve()),stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stderr_sha256=hashlib.sha256(r.stderr).hexdigest()));(out/'receipts.json').write_text(json.dumps(receipts,indent=2))
  if exe_before!=sha(pathlib.Path(cmd[0]).resolve()):raise RuntimeError('executable changed during command')
  if r.returncode:raise RuntimeError(name+' failed, not a successful negative')
  return r.stdout
 for ext in ('cpp','hpp'):
  raw=(HERE/f'StarBuffer.original.{ext}').read_text();ref=(HERE/f'StarBuffer.reference.{ext}').read_text();gate(ext,raw,ref)
  for x,y in ((raw+' ',ref),(raw,ref+' ')):
   try:gate(ext,x,y)
   except ValueError:controls.append('provenance-'+ext+('-raw' if x!=raw else '-reference'))
   else:raise RuntimeError('bad provenance accepted')
 cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarBuffer.cpp'));recipe=shlex.split(entry['command']);flags=[];skip=False
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
 tracked=[pathlib.Path(provenance.__file__),native_binary,provenance.sidecar(native_binary),*[ROOT/p for p in native_closure['source_files']],HERE/'source-map.json',*identity,a.identity_manifest,HERE/'run.py',HERE/'verify_receipts.py',HERE/'README.md',HERE/'lab.cpp',pathlib.Path(sys.executable).resolve(),pathlib.Path('/usr/bin/ar').resolve(),pathlib.Path('/usr/bin/nm').resolve(),ROOT/'source/core/StarBuffer.cpp',ROOT/'source/core/StarBuffer.hpp',*[HERE/f'StarBuffer.{k}.{e}' for k in ('original','reference') for e in ('cpp','hpp')]]
 for n,s in enumerate([HERE/'lab.cpp',HERE/'StarBuffer.original.cpp',HERE/'StarBuffer.reference.cpp']):
  dep=out/f'{n}.d';run([recipe[0],*flags,'-I'+str(HERE),'-M','-MF',dep,s],f'deps{n}');tracked.extend(pathlib.Path(x) if pathlib.Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]))
 tracked=list(dict.fromkeys(p.resolve() for p in tracked));before={str(p):sha(p) for p in tracked};(out/'before.json').write_text(json.dumps(before,indent=2));archive=out/'native-core.a';run(['/usr/bin/ar','rcs',archive,*objs],'archive');archivehash=sha(archive);generated={};binaries={}
 def compile(name,source,ref=False):
  exe=out/name;generated[str(source)]=sha(source);run([recipe[0],*flags,'-I'+str(HERE),*(['-DLAB_REFERENCE'] if ref else []),HERE/'lab.cpp',source,archive,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/(name+'.map')),'-o',exe],name+'-compile');binaries[str(exe)]=sha(exe);return exe
 obj=out/'buffer-standalone.o';run([recipe[0],*flags,'-c',ROOT/'source/core/StarBuffer.cpp','-o',obj],'standalone-compile');generated[str(obj)]=sha(obj);symbolbytes=run(['/usr/bin/nm','-C','--defined-only',obj],'standalone-symbols');symbols=sorted(set(re.findall(r' T (Star::(?:ExternalBuffer|Buffer)::[^\n]+)',symbolbytes.decode())));symbols=[x for x in symbols if '::~' not in x];assert len(symbols)==50;source_defs=json.loads((HERE/'source-map.json').read_text())['definitions'];name=lambda x:re.search(r'(?:Buffer|ExternalBuffer)::(?:operator bool|operator=|[A-Za-z]+)',x)[0];assert collections.Counter(map(name,symbols))==collections.Counter(name(x['definition']) for x in source_defs);(out/'compiled-definitions.json').write_text(json.dumps(symbols,indent=2));generated[str(out/'compiled-definitions.json')]=sha(out/'compiled-definitions.json')
 orig=compile('original',HERE/'StarBuffer.original.cpp');ref=compile('reference',HERE/'StarBuffer.reference.cpp',True);current=compile('current',ROOT/'source/core/StarBuffer.cpp');baseline=run([orig],'original');count=anchors(baseline)
 for exe,name in ((orig,'repeat'),(ref,'reference'),(current,'current')):
  got=run([exe],name);anchors(got)
  if got!=baseline:raise ValueError('whole ordered mismatch '+name)
 broken=baseline.replace(b'0:0:3:',b'0:0:2:',1)
 try:anchors(broken)
 except ValueError:controls.append('known-bad-literal')
 else:raise RuntimeError('bad fixture escaped')
 (out/'known-bad.stdout').write_bytes(broken)
 source=(HERE/'StarBuffer.original.cpp').read_text();mutants={
 'end-sign':source.replace('m_bytes.size() - pos','m_bytes.size() + pos'),
 'zero-mode-order':source.replace('  if (len == 0)\n    return 0;\n\n  if (!isReadable())','  if (len == 0 && isReadable())\n    return 0;\n\n  if (!isReadable())'),
 'eof-mode-order':source.replace('  if (!isReadable())','  if (pos >= '+ 'm_bytes.size()'+') return 0;\n  if (!isReadable())',1),
 'clone-position':source.replace('  cloned->seek(0);','  cloned->seek(pos());'),
 'inverted-bool':source.replace('ExternalBuffer::operator bool() const {\n  return m_size == 0;','ExternalBuffer::operator bool() const {\n  return m_size != 0;'),
 'reset-not-zero':source.replace('m_bytes.fill(newSize, 0)','m_bytes.fill(newSize, 1)')}
 for name,body in mutants.items():
  if body==source:raise RuntimeError('empty mutant '+name)
  p=out/(name+'.cpp');p.write_text(body);exe=compile(name,p);got=run([exe],name)
  if got==baseline:raise RuntimeError('mutant escaped '+name)
  controls.append(name)
 paired=out/'paired.cpp';paired.write_text(mutants['end-sign']);e1=compile('paired-a',paired);e2=compile('paired-b',paired);wrong=run([e1],'paired-a');wrong2=run([e2],'paired-b')
 if wrong!=wrong2:raise RuntimeError('paired wrong differed')
 try:anchors(wrong)
 except ValueError:controls.append('paired-wrong-literal')
 else:raise RuntimeError('paired wrong escaped')
 refbad=out/'reference-class-only.cpp';refbad.write_text(adapt(mutants['end-sign'],'cpp'))
 refexe=compile('reference-class-only',refbad,True);refgot=run([refexe],'reference-class-only')
 if refgot==baseline:raise RuntimeError('renamed reference class bypass')
 controls.append('reference-class-only')
 if b'native-core.a(StarBuffer.cpp.o)' in (out/'current.map').read_bytes():raise RuntimeError('original native Buffer object unexpectedly pulled')
 for p in out.glob('*.map'):generated[str(p)]=sha(p)
 after={str(p):sha(p) for p in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after or archivehash!=sha(archive) or any(sha(p)!=h for p,h in {**generated,**binaries}.items()):raise RuntimeError('artifact drift')
 mapping=json.loads((HERE/'source-map.json').read_text());actual=[dict(definition=l.strip(),line=i) for i,l in enumerate((HERE/'StarBuffer.original.cpp').read_text().splitlines(),1) if re.search(r'\b(?:Buffer|ExternalBuffer)::',l) and ('{' in l or l.startswith(('Buffer::Buffer','ExternalBuffer::ExternalBuffer')))];assert mapping['count']==len(actual)==50 and mapping['definitions']==actual
 if provenance.verify(native_binary)!=native_closure:raise RuntimeError('native compiled closure drift')
 report=dict(native_binary=str(native_binary),native_closure=native_closure,status='FINITE_NATIVE_CALIBRATION_PASS',revision=REV,cases=count,controls=controls,ordered_sha256=hashlib.sha256(baseline).hexdigest(),bindings=before,generated=generated,binaries=binaries,archive_sha256=archivehash,receipts=receipts,link=dict(compiler=recipe[0],flags=flags,libraries=libs,archive=str(archive)),definitions=50,limits=['Native-only, no Rust or application or TCP qualification','Scripted I/O faults are counterfactual, not allocator failures','All growth observations within 256 initialized bytes; no nonzero extreme writes, overlap, dangling or indeterminate reads','64-bit macOS conversion profile only; no allocator/OOM/performance/platform universality'])
 (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ('status','cases','controls','ordered_sha256')}))
if __name__=='__main__':main()
