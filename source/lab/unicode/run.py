#!/usr/bin/env python3
"""Full compiled Unicode oracle; exact comparison, isolated native dependencies."""
import argparse,hashlib,json,shlex,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
REV='b136ed4ba23e59edac204c0a18377a13ae267c24'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--define',choices=['STAR_USE_RUST_UNICODE','STAR_USE_RUST_UNICODE=1']);p.add_argument('--archive',type=Path);p.add_argument('--reference-report',type=Path);a=p.parse_args()
 if bool(a.define)!=bool(a.archive):p.error('archive and selector must be paired')
 out=a.output.resolve();base=(ROOT/'build/unicode-lab').resolve()
 if not out.is_relative_to(base) or out==base:p.error('output must be strictly nested in build/unicode-lab')
 if a.archive and not a.archive.resolve().is_file():p.error('archive missing')
 if a.define and not a.reference_report:p.error('Rust requires independent CPP observation report')
 out.mkdir(parents=True,exist_ok=True);neg=[]
 def gate(ext,raw,adapted):
  expected=subprocess.check_output(['git','show',REV+':source/core/StarUnicode.'+ext],cwd=ROOT)
  if raw!=expected:raise ValueError('snapshot corruption')
  want=raw.replace(b'namespace Star {',b'namespace UnicodeReference {\nusing namespace Star;')
  if ext=='cpp':want=want.replace(b'"StarUnicode.hpp"',b'"StarUnicode.reference.hpp"')
  if adapted!=want:raise ValueError('unauthorized adaptation')
 for ext in ['cpp','hpp']:
  raw=(HERE/('StarUnicode.original.'+ext)).read_bytes();ad=(HERE/('StarUnicode.reference.'+ext)).read_bytes();gate(ext,raw,ad)
  for name,r,d in [('raw-drift-'+ext,raw+b' ',ad),('adaptation-drift-'+ext,raw,ad+b' ')]:
   try:gate(ext,r,d)
   except ValueError:neg.append(name)
   else:raise RuntimeError('provenance negative escaped')
 if (ROOT/'source/core/StarUnicode.hpp').read_bytes()!=(HERE/'StarUnicode.original.hpp').read_bytes():raise ValueError('public header/generic iterators changed')
 cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarUnicode.cpp'))
 recipe=shlex.split(entry['command']);flags=[];skip=False
 for f in recipe[1:]:
  if skip:skip=False;continue
  if f=='-o':skip=True
  elif f not in ['-c',entry['file']]:flags.append(f)
 lines=(cm/'build.ninja').read_text().splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
 objects=[cm/x for x in shlex.split(lines[i].split(': ',1)[1])[1:] if x.endswith('.o') and (x.startswith('core/') or x.startswith('extern/')) and not x.endswith('/StarUnicode.cpp.o')]
 if not objects or any(not x.is_file() for x in objects):raise RuntimeError('existing native objects unavailable; NO rebuild/fake replacement')
 libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+15] if x.startswith('  LINK_LIBRARIES = ')))
 libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
 # Seal all actual transitive headers, not simplified stand-ins. Native object
 # source freshness is a separate parent build-seal responsibility.
 tracked=[*HERE.glob('*'),db,cm/'build.ninja',Path(recipe[0]).resolve(),*objects,*(Path(x) for x in libs if x.endswith('.a')),*[x for x in (ROOT/'source/core').rglob('*') if x.suffix in ['.hpp','.h','.cpp'] and x.is_file()]]
 tracked += [x for x in (ROOT/'source/extern').rglob('*') if x.is_file() and x.suffix in ['.h','.hpp']]
 # Pin real allocating/hex/ownership/platform dependencies to the entry commit.
 for name in ['StarEncode.cpp','StarEncode.hpp','StarByteArray.cpp','StarByteArray.hpp','StarString.cpp','StarString.hpp','StarMaybe.hpp','StarConfig.hpp','StarBytes.hpp']:
  path=ROOT/'source/core'/name
  if path.read_bytes()!=subprocess.check_output(['git','show',REV+':source/core/'+name],cwd=ROOT):raise ValueError('frozen dependency changed '+name)
 # Compiler dependency output includes SDK, standard library and vcpkg headers;
 # broad source-directory hashes alone would miss those actual transitive inputs.
 for num,src in enumerate([HERE/'lab.cpp',HERE/'StarUnicode.reference.cpp',ROOT/'source/core/StarUnicode.cpp']):
  dep=out/('deps-'+str(num)+'.d');cmd=[recipe[0],*flags,'-I'+str(HERE),'-M','-MF',str(dep),str(src)]
  if a.define:cmd+=['-D'+a.define]
  r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=30)
  (out/('deps-'+str(num)+'.log')).write_text(shlex.join(cmd)+'\n'+r.stdout+r.stderr)
  if r.returncode:raise RuntimeError('transitive dependency scan failed')
  deps=shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]);tracked += [Path(x) if Path(x).is_absolute() else ROOT/x for x in deps]
 if a.archive:tracked += [a.archive.resolve(),*list((ROOT/'source/rust/ffi/src').glob('*.rs'))]
 if a.reference_report:tracked.append(a.reference_report.resolve())
 tracked=list(dict.fromkeys(x.resolve() for x in tracked if x.is_file()));before={str(x):sha(x) for x in tracked};(out/'before.json').write_text(json.dumps(before,indent=2));commands=[]
 def run(cmd,name):
  commands.append(shlex.join(map(str,cmd)));r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=100);(out/(name+'.log')).write_text(commands[-1]+'\n'+r.stdout+r.stderr);return r
 native=out/'native-core.a';r=run(['/usr/bin/ar','rcs',str(native),*map(str,objects)],'archive')
 if r.returncode:raise RuntimeError('archive failure')
 def compile(source,name,rust=False):
  binary=out/name;cmd=[recipe[0],*flags,'-I'+str(HERE),str(HERE/'lab.cpp'),str(HERE/'StarUnicode.reference.cpp'),str(source),str(native),*libs,'-Wl,-dead_strip']
  if rust:cmd+=['-D'+a.define,str(a.archive.resolve())]
  cmd+=['-o',str(binary)];r=run(cmd,name+'-compile')
  if r.returncode:raise RuntimeError('compile/link failure '+str(out/(name+'-compile.log')))
  return binary
 for name,args in [('define',['--define','evil=1']),('archive',['--archive','missing']),('output',['--output',str(ROOT/'build/not-unicode-lab')])]:
  r=run(['python3',str(Path(__file__).resolve()),'--output',str(out/'cli'),*args],'cli-'+name)
  if r.returncode!=2:raise RuntimeError('CLI negative escaped')
  neg.append('cli-'+name)
 binary=compile(ROOT/'source/core/StarUnicode.cpp','calibration',bool(a.define));r=run([str(binary)],'baseline');rr=run([str(binary)],'repeat')
 if r.returncode or rr.returncode or r.stdout!=rr.stdout:raise RuntimeError('baseline failed; no negative controls credited')
 result=json.loads(r.stdout)
 # Both frozen C++ and Rust must count an unreadable two-byte tail without
 # touching byte two. A child signal is a comparison FAILURE, not a pass.
 guard=out/'short-tail';guardcmd=[recipe[0],*flags,str(HERE/'short_tail.cpp')]
 if a.define:guardcmd+=['-D'+a.define,str(a.archive.resolve())]
 else:guardcmd += [str(HERE/'StarUnicode.original.cpp'),str(native),*libs,'-Wl,-dead_strip']
 guardcmd += ['-o',str(guard)]
 if run(guardcmd,'short-tail-compile').returncode:raise RuntimeError('short-tail fixture compile failed')
 if run([str(guard)],'short-tail').returncode:raise RuntimeError('legacy length skipped-tail regression')
 if a.reference_report:
  ref=json.loads(a.reference_report.read_text())
  def independent(reference,actual):
   if reference.get('status')!='PASS' or reference.get('backend')!='cpp' or reference.get('cases')!=actual['cases'] or reference.get('observation_digest')!=actual['observation_digest']:raise ValueError('independent CPP observation comparison failed')
  independent(ref,result)
  try:independent(dict(ref,observation_digest='CORRUPTED'),result)
  except ValueError:neg.append('independent-observation-corruption')
  else:raise RuntimeError('independent comparison negative escaped')
 if a.define:
  bad=run([str(binary),'missing-receipt'],'missing-receipt')
  if bad.returncode!=1 or 'COMPARISON receipt missing' not in bad.stderr:raise RuntimeError('missing receipt negative escaped')
  neg.append('missing-receipt')
 raw=(HERE/'StarUnicode.original.cpp').read_bytes()
 for name,old,new in [
  ('NUL-policy',b'bool stopOnNull = remain == NPos;',b'bool stopOnNull = true;'),
  ('replacement-consumption',b'return utf8 - start + 1;\n    }\n\n    if ((utf8[0] & 0xe0)',b'return utf8 - start;\n    }\n\n    if ((utf8[0] & 0xe0)'),
  ('capacity-partial-write',b'if (len < 4)\n      return 0;',b'if (len < 4) { utf8[0] = 0x44; return 0; }'),
  ('pair-arithmetic',b'(lead << 10) + trail + MIN_PAIR',b'(lead << 10) + trail + MIN_PAIR + 1')]:
  if old not in raw:raise ValueError('mutant anchor missing '+name)
  source=out/(name+'.cpp');source.write_bytes(raw.replace(old,new,1));m=compile(source,name);bad=run([str(m)],name)
  if bad.returncode!=1 or 'COMPARISON' not in bad.stderr:raise RuntimeError('algorithm mutant not cleanly rejected '+name)
  neg.append(name)
 # Actual Encode dependency mutant: use real full implementation, alter only
 # invalid nibble initialization, and replace its prebuilt object in lab archive.
 enc=(ROOT/'source/core/StarEncode.cpp').read_bytes();old=b'uint8_t b1 = 0;'
 if enc.count(old)!=1:raise ValueError('hex mutant anchor missing')
 mutant=out/'hex-invalid.cpp';mutant.write_bytes(enc.replace(old,b'uint8_t b1 = 1;',1))
 # Both candidate/reference share this dependency, so independent literal anchor
 # (not differential equality) must reject it.
 encobj=out/'hex-invalid.o';cr=run([recipe[0],*flags,'-c',str(mutant),'-o',str(encobj)],'hex-invalid-object')
 if cr.returncode:raise RuntimeError('hex mutant compile failure')
 alt=out/'mutant-native-core.a';cr=run(['/usr/bin/ar','rcs',str(alt),*map(str,[x for x in objects if not str(x).endswith('/StarEncode.cpp.o')]),str(encobj)],'hex-invalid-archive')
 if cr.returncode:raise RuntimeError('hex mutant archive failure')
 oldnative=native;native=alt;m=compile(HERE/'StarUnicode.original.cpp','hex-invalid');native=oldnative;bad=run([str(m)],'hex-invalid')
 if bad.returncode!=1 or 'COMPARISON invalid nibble/odd tail' not in bad.stderr:raise RuntimeError('hex algorithm mutant not comparison rejection')
 neg.append('hex-invalid-nibble')
 after={str(x):sha(x) for x in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after:raise RuntimeError('source/archive/compiler/dependency drift: rerun required')
 result.update(status='PASS',backend='rust' if a.define else 'cpp',negative_controls=neg,commands=commands,bindings=before,binary_sha256=sha(binary),native_archive_sha256=sha(native),limits=['native object source freshness requires parent build seal','no game/screenshots/performance/platform claim','generic iterator bodies unchanged, not ported'])
 (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['bindings','commands']}))
if __name__=='__main__':main()
