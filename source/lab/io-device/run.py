#!/usr/bin/env python3
"""Finite whole-compiled-IODevice calibration; native scripted virtual I/O."""
import argparse,hashlib,json,pathlib,re,shlex,subprocess,sys,shutil,collections
ROOT=pathlib.Path(__file__).resolve().parents[3]; HERE=pathlib.Path(__file__).resolve().parent; REV='c233825b'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def adapt(s,ext):
 s=s.replace('namespace Star {','namespace Star { namespace IODeviceReference {',1)
 i=s.rfind('}');s=s[:i]+'} '+s[i:]
 return s.replace('#include "StarIODevice.hpp"','#include "StarIODevice.reference.hpp"',1) if ext=='cpp' else s

def gate(ext,raw,ref):
 frozen=subprocess.check_output(['git','show',REV+':source/core/StarIODevice.'+ext],cwd=ROOT).decode()
 current=(ROOT/f'source/core/StarIODevice.{ext}').read_bytes().decode()
 if (HERE/f'StarIODevice.original.{ext}').read_bytes().decode()!=frozen or (HERE/f'StarIODevice.reference.{ext}').read_bytes().decode()!=adapt(frozen,ext):raise ValueError('raw/reference byte provenance')

 if current!=frozen or raw!=frozen or ref!=adapt(frozen,ext):raise ValueError('source provenance')

from model import check as anchors
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=pathlib.Path);ap.add_argument('--identity-manifest',required=True,type=pathlib.Path);a=ap.parse_args();out=a.output.absolute();base=ROOT/'build/io-device-lab'
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
  raw=(HERE/f'StarIODevice.original.{ext}').read_text();ref=(HERE/f'StarIODevice.reference.{ext}').read_text();gate(ext,raw,ref)
  for x,y in ((raw+' ',ref),(raw,ref+' ')):
   try:gate(ext,x,y)
   except ValueError:controls.append('provenance-'+ext+('-raw' if x!=raw else '-reference'))
   else:raise RuntimeError('bad provenance accepted')
 cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarIODevice.cpp'));recipe=shlex.split(entry['command']);flags=[];skip=False
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
 tracked=[pathlib.Path(provenance.__file__),native_binary,provenance.sidecar(native_binary),*[ROOT/p for p in native_closure['source_files']],HERE/'source-map.json',*identity,a.identity_manifest,HERE/'run.py',HERE/'verify_receipts.py',HERE/'README.md',HERE/'scope.json',HERE/'model.py',HERE/'lab.cpp',pathlib.Path(sys.executable).resolve(),pathlib.Path('/usr/bin/ar').resolve(),pathlib.Path('/usr/bin/nm').resolve(),ROOT/'source/core/StarIODevice.cpp',ROOT/'source/core/StarIODevice.hpp',*[HERE/f'StarIODevice.{k}.{e}' for k in ('original','reference') for e in ('cpp','hpp')]]
 for n,s in enumerate([HERE/'lab.cpp',HERE/'StarIODevice.original.cpp',HERE/'StarIODevice.reference.cpp']):
  dep=out/f'{n}.d';run([recipe[0],*flags,'-I'+str(HERE),'-M','-MF',dep,s],f'deps{n}');tracked.extend(pathlib.Path(x) if pathlib.Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]))
 tracked=list(dict.fromkeys(p.resolve() for p in tracked));before={str(p):sha(p) for p in tracked};(out/'before.json').write_text(json.dumps(before,indent=2));archive=out/'native-core.a';run(['/usr/bin/ar','rcs',archive,*objs],'archive');archivehash=sha(archive);generated={};binaries={}
 def compile(name,source,ref=False):
  exe=out/name;generated[str(source)]=sha(source);run([recipe[0],*flags,'-I'+str(HERE),*(['-DLAB_REFERENCE'] if ref else []),HERE/'lab.cpp',source,archive,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/(name+'.map')),'-o',exe],name+'-compile');binaries[str(exe)]=sha(exe);return exe
 obj=out/'io-device-standalone.o';run([recipe[0],*flags,'-c',ROOT/'source/core/StarIODevice.cpp','-o',obj],'standalone-compile');generated[str(obj)]=sha(obj);symbolbytes=run(['/usr/bin/nm','-C','--defined-only',obj],'standalone-symbols');symbols=sorted(set(re.findall(r' T (Star::IODevice::[^\n]+)',symbolbytes.decode())));assert len(symbols)==22, symbols;source_defs=json.loads((HERE/'source-map.json').read_text())['definitions'];name=lambda x:re.search(r'IODevice::(?:operator=|~?[A-Za-z]+)',x)[0];assert collections.Counter(map(name,symbols))==collections.Counter(name(x['definition']) for x in source_defs);(out/'compiled-definitions.json').write_text(json.dumps(symbols,indent=2));generated[str(out/'compiled-definitions.json')]=sha(out/'compiled-definitions.json')
 orig=compile('original',HERE/'StarIODevice.original.cpp');ref=compile('reference',HERE/'StarIODevice.reference.cpp',True);current=compile('current',ROOT/'source/core/StarIODevice.cpp');baseline=run([orig],'original');count=anchors(baseline);scope=json.loads((HERE/'scope.json').read_text());assert count==scope['cases'] and hashlib.sha256(baseline).hexdigest()==scope['ordered_sha256']
 for exe,name in ((orig,'repeat'),(ref,'reference'),(current,'current')):
  got=run([exe],name);anchors(got)
  if got!=baseline:raise ValueError('whole ordered mismatch '+name)
 broken=baseline.replace(b'0:0:0',b'0:0:1',1)
 try:anchors(broken)
 except ValueError:controls.append('known-bad-literal')
 else:raise RuntimeError('bad fixture escaped')
 (out/'known-bad.stdout').write_bytes(broken)
 source=(HERE/'StarIODevice.original.cpp').read_text();mutants={
 'eof-class':source.replace('throw EofException(', 'throw IOException('),
 'size-no-restore':source.replace('    seek(storedPos);','    /* mutation: omit restoration */',1),
 'absolute-no-restore':source.replace('  seek(storedPos);','  /* mutation: omit restoration */'),
 'absolute-offset':source.replace('readPosition += r;','readPosition += 0;').replace('writePosition += r;','writePosition += 0;'),
 'zero-absolute-step':source.replace('while (len > 0)', 'do').replace('    len -= r;\n  }','    len -= r;\n  } while (len > 0);'),
 'eager-name':source.replace('void IODevice::open(IOMode mode) {','void IODevice::open(IOMode mode) {\n  deviceName();')}
 for name,body in mutants.items():
  if body==source:raise RuntimeError('empty mutant '+name)
  p=out/(name+'.cpp');p.write_text(body);exe=compile(name,p);got=run([exe],name)
  if got==baseline:raise RuntimeError('mutant escaped '+name)
  controls.append(name)
 paired=out/'paired.cpp';paired.write_text(mutants['eof-class']);e1=compile('paired-a',paired);e2=compile('paired-b',paired);wrong=run([e1],'paired-a');wrong2=run([e2],'paired-b')
 if wrong!=wrong2:raise RuntimeError('paired wrong differed')
 try:anchors(wrong)
 except ValueError:controls.append('paired-wrong-literal')
 else:raise RuntimeError('paired wrong escaped')
 refbad=out/'reference-class-only.cpp';refbad.write_text(adapt(mutants['eof-class'],'cpp'))
 refexe=compile('reference-class-only',refbad,True);refgot=run([refexe],'reference-class-only')
 if refgot==baseline:raise RuntimeError('renamed reference class bypass')
 controls.append('reference-class-only')
 if b'native-core.a(StarIODevice.cpp.o)' in (out/'current.map').read_bytes():raise RuntimeError('original native Buffer object unexpectedly pulled')
 for p in out.glob('*.map'):generated[str(p)]=sha(p)
 after={str(p):sha(p) for p in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after or archivehash!=sha(archive) or any(sha(p)!=h for p,h in {**generated,**binaries}.items()):raise RuntimeError('artifact drift')
 mapping=json.loads((HERE/'source-map.json').read_text());actual=[dict(definition=l.strip(),line=i) for i,l in enumerate((HERE/'StarIODevice.original.cpp').read_text().splitlines(),1) if re.search(r'\bIODevice::',l) and ('{' in l or l.startswith(('IODevice::IODevice',)))];assert mapping['count']==len(actual)==22 and mapping['definitions']==actual
 if provenance.verify(native_binary)!=native_closure:raise RuntimeError('native compiled closure drift')
 report=dict(native_binary=str(native_binary),native_closure=native_closure,status='FINITE_NATIVE_CALIBRATION_PASS',revision=REV,cases=count,controls=controls,ordered_sha256=hashlib.sha256(baseline).hexdigest(),bindings=before,generated=generated,binaries=binaries,archive_sha256=archivehash,receipts=receipts,link=dict(compiler=recipe[0],flags=flags,libraries=libs,archive=str(archive)),definitions=22,limits=['Native-only, no Rust or application or TCP qualification','Scripted I/O faults are counterfactual, not allocator failures','Preinitialized bounded outputs; nonnull zero spans; size-max read returns zero before arithmetic; no overlap or indeterminate reads','64-bit macOS conversion profile only; no allocator/OOM/performance/platform universality'])
 (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ('status','cases','controls','ordered_sha256')}))
if __name__=='__main__':main()
