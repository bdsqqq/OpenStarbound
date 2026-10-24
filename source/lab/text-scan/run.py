#!/usr/bin/env python3
"""Compile complete frozen native Text module; compare only processText behavior."""
import argparse,hashlib,json,os,shlex,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
REV='09f6a9a3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--backend',choices=['cpp','rust'],default='cpp');p.add_argument('--output',required=True,type=Path);p.add_argument('--reference-report',type=Path);a=p.parse_args();out=a.output.resolve();base=ROOT/'build/text-scan-lab'
 if not out.is_relative_to(base) or out==base or out.exists() or any(x.is_symlink() for x in [a.output.absolute(),*a.output.absolute().parents]):p.error('new owned non-symlink nested output required')
 archive=ROOT/'build/text-scan-rust/target/release/libstar_engine_ffi.a';bridge=ROOT/'source/core/StarRustTextScan.h'
 if a.backend=='rust' and (not archive.is_file() or not bridge.is_file()):raise RuntimeError('WAIT: core freeze and canonical Rust archive unavailable; no Cargo run permitted')
 out.mkdir(parents=True);commands=[];negative=[]
 def gate(ext,raw,adapt):
  original=subprocess.check_output(['git','show',REV+':source/core/StarText.'+ext],cwd=ROOT);want=original.replace(b'namespace Star {',b'namespace TextReference {\nusing namespace Star;')
  if ext=='cpp':want=want.replace(b'"StarText.hpp"',b'"StarText.reference.hpp"')
  if raw!=original or adapt!=want:raise ValueError('freeze drift')
 for ext in ['cpp','hpp']:
  raw=(HERE/('StarText.original.'+ext)).read_bytes();adapt=(HERE/('StarText.reference.'+ext)).read_bytes();gate(ext,raw,adapt)
  if ext=='hpp' and (ROOT/'source/core/StarText.hpp').read_bytes()!=raw:raise ValueError('public header drift')
  for label,r,d in [('raw',raw+b' ',adapt),('adapt',raw,adapt+b' ')]:
   try:gate(ext,r,d)
   except ValueError:negative.append(label+'-'+ext)
   else:raise RuntimeError('freeze negative escaped')
 production=(ROOT/'source/core/StarText.cpp').read_bytes();original=(HERE/'StarText.original.cpp').read_bytes()
 if production!=original:
  include=b'#ifdef STAR_USE_RUST_TEXT_SCAN\n#include "StarRustTextScan.h"\n#include <exception>\n#include <stdexcept>\n#endif\n';marker=b'#ifdef STAR_USE_RUST_TEXT_SCAN\n'
  reconstructed=production.replace(include,b'')
  if reconstructed.count(marker)!=1 or reconstructed.count(b'#else\n')!=1 or reconstructed.count(b'#endif\n')!=1:raise ValueError('unexpected selector structure')
  prefix,tail=reconstructed.split(marker);fallback=tail.split(b'#else\n',1)[1];reconstructed=prefix+fallback.replace(b'#endif\n',b'',1)
  if reconstructed!=original:raise ValueError('complete original fallback drift')
 cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarText.cpp'));recipe=shlex.split(entry['command']);flags=[];skip=False
 for f in recipe[1:]:
  if skip:skip=False;continue
  if f=='-o':skip=True
  elif f not in ['-c',entry['file']]:flags.append(f)
 if any('STAR_USE_RUST_' in x for x in flags):raise ValueError('not CPP recipe')
 lines=(cm/'build.ninja').read_text().splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
 objects=[cm/x for x in shlex.split(lines[i].split(': ',1)[1])[1:] if x.endswith('.o') and (x.startswith('core/') or x.startswith('extern/')) and not x.endswith('/StarText.cpp.o')]
 if not objects or any(not x.is_file() for x in objects):raise ValueError('sealed native objects unavailable')
 libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+15] if x.startswith('  LINK_LIBRARIES = ')));libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
 def run(cmd,name):
  commands.append(shlex.join(map(str,cmd)));r=subprocess.run(list(map(str,cmd)),cwd=ROOT,capture_output=True,text=True,timeout=90,env=dict(os.environ,LAB_OBSERVATIONS=str(out/(name+'.observations'))));(out/(name+'.log')).write_text(commands[-1]+'\n'+r.stdout+r.stderr);return r
 sources=[HERE/'lab.cpp',HERE/'StarText.reference.cpp',ROOT/'source/core/StarText.cpp'];extra=[bridge,ROOT/'source/rust/ffi/src/text_scan.rs',ROOT/'source/rust/ffi/src/lib.rs',ROOT/'source/CMakeLists.txt']
 tracked=[*HERE.glob('*'),db,cm/'build.ninja',Path(recipe[0]).resolve(),*objects,*[Path(x) for x in libs if x.endswith('.a')],*[x for x in extra if x.is_file()]]+([archive] if archive.is_file() else [])
 selected=['-DSTAR_USE_RUST_TEXT_SCAN=1','-DLAB_RUST=1'] if a.backend=='rust' else []
 for n,src in enumerate(sources+([HERE/'candidate_abi.cpp'] if a.backend=='rust' else [])):
  dep=out/(str(n)+'.d');r=run([recipe[0],*flags,*selected,'-I'+str(HERE),'-M','-MF',dep,src],'deps-'+str(n))
  if r.returncode:raise RuntimeError('dependency scan failed')
  tracked += [Path(x) if Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])]
 tracked=list(dict.fromkeys(x.resolve() for x in tracked if x.is_file()));before={str(x):sha(x) for x in tracked};(out/'before.json').write_text(json.dumps(before,indent=2))
 native=out/'native-core.a'
 if run(['/usr/bin/ar','rcs',native,*objects],'archive').returncode:raise RuntimeError('archive failure')
 # Archive extraction resolves only actual Text dependencies, not Root setup.
 def compile(name,src=None,ref=None,lab=None,selected_backend=True):
  use=selected_backend and a.backend=='rust';binary=out/name;r=run([recipe[0],*flags,*(selected if use else []),'-I'+str(HERE),lab or HERE/'lab.cpp',ref or HERE/'StarText.reference.cpp',src or ROOT/'source/core/StarText.cpp',native,*([archive] if use else []),*libs,'-Wl,-dead_strip','-o',binary],name+'-compile')
  if r.returncode:raise RuntimeError('compile failure '+name+'; not a credited negative')
  return binary
 binary=compile('calibration');r=run([binary],'baseline');repeat=run([binary],'repeat')
 if r.returncode or repeat.returncode or r.stdout!=repeat.stdout or (out/'baseline.observations').read_bytes()!=(out/'repeat.observations').read_bytes():raise RuntimeError('baseline/repeat comparison failed; inspect logs')
 result=json.loads(r.stdout);independent=compile('independent-cpp',src=HERE/'StarText.original.cpp',selected_backend=False);ind=run([independent],'independent-cpp')
 if ind.returncode or (out/'independent-cpp.observations').read_bytes()!=(out/'baseline.observations').read_bytes():raise RuntimeError('independent complete original stream mismatch')
 def identity(report):
  if report.get('bindings')!=before or report.get('ordered_observations_sha256')!=sha(out/'baseline.observations') or report.get('cases')!=result['cases'] or report.get('backend')!=a.backend or report.get('status')!='PASS':raise ValueError('independent stream/source identity mismatch')
 report=dict(result,bindings=before,backend=a.backend,ordered_observations_sha256=sha(out/'baseline.observations'))
 if a.reference_report:identity(json.loads(a.reference_report.read_text()))
 for name,changes in [('wrong-stream',{'ordered_observations_sha256':'wrong'}),('wrong-source',{'bindings':{}})]:
  try:identity(dict(report,**changes))
  except ValueError:negative.append(name)
  else:raise RuntimeError('identity negative escaped')
 raw=(HERE/'StarText.original.cpp').read_bytes()
 mutants=[('escape-run',b'escape = str.find_first_not_of(AllEsc, escape) - 1;',b'escape = str.find_first_not_of(AllEsc, escape);'),('restart',b'start = end;',b'start = end + 1;'),('empty-command',b'if (!commands.empty() && !commandsFunc(commands))',b'if (!commandsFunc(commands))'),('abort',b'return false;',b'return true;')]
 for name,old,new in mutants:
  if old not in raw:raise RuntimeError('mutant anchor missing '+name)
  src=out/(name+'.cpp');src.write_bytes(raw.replace(old,new));mut=compile(name,src=src,selected_backend=False);bad=run([mut],name)
  if bad.returncode!=1 or 'COMPARISON' not in bad.stderr:raise RuntimeError('mutant must fail clean comparison '+name)
  negative.append(name)
 # Paired candidate/reference corruption must still fail independent literal anchors.
 old=b'if (!commands.empty() && !commandsFunc(commands))';new=b'if (!commandsFunc(commands))';src=out/'paired.cpp';ref=out/'paired-ref.cpp';src.write_bytes(raw.replace(old,new));ref.write_bytes((HERE/'StarText.reference.cpp').read_bytes().replace(old,new));bad=run([compile('paired',src=src,ref=ref,selected_backend=False)],'paired')
 if bad.returncode!=1 or 'COMPARISON independent literal anchor' not in bad.stderr:raise RuntimeError('paired corruption escaped independent anchor')
 negative.append('paired-independent-anchor')
 body=(HERE/'lab.cpp').read_bytes()
 for name,old,new in [('wrong-kind',b'r.events.push_back({kind,',b'r.events.push_back({kind^1,'),('wrong-payload',b'std::string(s)});',b'std::string(s)+"!"});')]:
  if body.count(old)!=1:raise RuntimeError('verifier anchor drift')
  lab=out/(name+'-lab.cpp');lab.write_bytes(body.replace(old,new));bad=run([compile(name,lab=lab)],name)
  if bad.returncode!=1 or 'COMPARISON independent literal anchor' not in bad.stderr:raise RuntimeError('verifier corruption escaped '+name)
  negative.append(name)
 if a.backend=='rust':
  abi=out/'raw-abi';rr=run([recipe[0],*flags,HERE/'candidate_abi.cpp',archive,*libs,'-Wl,-dead_strip','-o',abi],'abi-compile')
  if rr.returncode:raise RuntimeError('raw ABI compile failed')
  rr=run([abi],'raw-abi')
  if rr.returncode:raise RuntimeError('raw ABI comparison failed')
  result['raw_abi']=json.loads(rr.stdout)
  for language,standard,suffix in [('c','c11','c'),('c++','c++17','cpp')]:
   probe=out/('header.'+suffix);probe.write_text('#include "StarRustTextScan.h"\nint main(void){return 0;}\n');rr=run([recipe[0],'-x',language,'-std='+standard,'-pedantic-errors','-I'+str(ROOT/'source/core'),'-fsyntax-only',probe],'header-'+standard)
   if rr.returncode:raise RuntimeError('strict ABI header parse failed '+standard)
  controller=(ROOT/'source/core/StarText.cpp').read_bytes()
  for name,old,new in [('candidate-span',b'context.bytes.substr(static_cast<size_t>(offset), static_cast<size_t>(length))',b'context.bytes.substr(static_cast<size_t>(offset + 1), static_cast<size_t>(length))'),('candidate-abort',b'return result != 0;',b'return true;')]:
   if controller.count(old)!=1:raise RuntimeError('candidate mutant anchor drift '+name)
   src=out/(name+'.cpp');src.write_bytes(controller.replace(old,new));bad=run([compile(name,src=src)],name)
   if bad.returncode!=1 or 'COMPARISON' not in bad.stderr:raise RuntimeError('selected candidate mutant not comparison-detected '+name)
   negative.append(name)
  suppressed=out/'receipt-suppressed.cpp';anchor=b'#include "StarRustTextScan.h"';suppressed.write_bytes(body.replace(anchor,anchor+b'\nstatic uint64_t suppressed(uint32_t){return 0;}\n#define star_text_scan_call_count suppressed'))
  bad=run([compile('receipt-suppressed',lab=suppressed)],'receipt-suppressed')
  if bad.returncode!=1 or 'COMPARISON semantic' not in bad.stderr:raise RuntimeError('receipt suppression escaped')
  negative.append('receipt-suppressed')
 after={str(x):sha(x) for x in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after:raise RuntimeError('source/compiler/dependency/object/archive drift: freeze required')
 result.update(backend=a.backend,bindings=before,commands=commands,negative_controls=negative,ordered_observations_sha256=sha(out/'baseline.observations'),binary_sha256=sha(binary),native_archive_sha256=sha(native),limits=['finite byte corpus; not universal proof','only processText is compared, not TextStyle or stripEscapeCodes','no allocator fault injection or forced Rust panic','native object freshness requires parent seal check','no game, screenshot or performance claim'])
 (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['bindings','commands']}))
if __name__=='__main__':main()
