#!/usr/bin/env python3
"""Frozen complete JsonPath grammar oracle using real native allocating dependencies."""
import argparse,hashlib,json,re,shlex,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
REV='356eeb9bc92cc0c20259b06918aade0c43326d67'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--define',choices=['STAR_USE_RUST_JSON_PATH','STAR_USE_RUST_JSON_PATH=1']);p.add_argument('--archive',type=Path);p.add_argument('--reference-report',type=Path);a=p.parse_args()
 if bool(a.define)!=bool(a.archive):p.error('archive and selector must pair')
 if a.archive and a.archive.resolve()!=ROOT/'build/jsonpath-rust/target/release/libstar_engine_ffi.a':p.error('only jsonpath-owned archive accepted')
 out=a.output.resolve();base=ROOT/'build/json-path-lab'
 if not out.is_relative_to(base) or out==base:p.error('output strictly nested in build/json-path-lab required')
 if a.define and not a.reference_report:p.error('independent CPP report required')
 out.mkdir(parents=True,exist_ok=True);negative=[]
 def gate(ext,raw,adapted):
  original=subprocess.check_output(['git','show',REV+':source/core/StarJsonPath.'+ext],cwd=ROOT)
  expected=original.replace(b'namespace Star {',b'namespace JsonPathReference {\nusing namespace Star;')
  if ext=='cpp':expected=expected.replace(b'"StarJsonPath.hpp"',b'"StarJsonPath.reference.hpp"')
  if raw!=original or adapted!=expected:raise ValueError('source/adaptation drift')
 for ext in ['cpp','hpp']:
  raw=(HERE/('StarJsonPath.original.'+ext)).read_bytes();adapted=(HERE/('StarJsonPath.reference.'+ext)).read_bytes();gate(ext,raw,adapted)
  for name,r,d in [('raw-'+ext,raw+b' ',adapted),('adapted-'+ext,raw,adapted+b' ')]:
   try:gate(ext,r,d)
   except ValueError:negative.append(name)
   else:raise RuntimeError('freeze negative escaped')
 if (ROOT/'source/core/StarJsonPath.hpp').read_bytes()!=(HERE/'StarJsonPath.original.hpp').read_bytes():raise ValueError('public/private layout header changed')
 # Both original fallback bodies remain byte-for-byte frozen after adapter guards.
 active=(ROOT/'source/core/StarJsonPath.cpp').read_text().split('namespace Star {',1)[1]
 native=re.sub(r'#ifdef STAR_USE_RUST_JSON_PATH\n.*?#else\n(.*?)#endif\n',r'\1',active,flags=re.S)
 original=(HERE/'StarJsonPath.original.cpp').read_text().split('namespace Star {',1)[1]
 if native!=original:raise ValueError('native fallback bodies changed')
 # Real allocating/String/Unicode/Encode dependencies MUST remain native original.
 for name in ['StarUnicode.cpp','StarUnicode.hpp','StarEncode.cpp','StarEncode.hpp','StarString.cpp','StarString.hpp','StarMaybe.hpp','StarBytes.hpp']:
  if (ROOT/'source/core'/name).read_bytes()!=subprocess.check_output(['git','show',REV+':source/core/'+name],cwd=ROOT):raise ValueError('dependency changed '+name)
 cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarJsonPath.cpp'));recipe=shlex.split(entry['command']);flags=[];skip=False
 for f in recipe[1:]:
  if skip:skip=False;continue
  if f=='-o':skip=True
  elif f not in ['-c',entry['file']]:flags.append(f)
 if any('STAR_USE_RUST_' in f for f in flags):raise ValueError('CPP dependency recipe contaminated')
 lines=(cm/'build.ninja').read_text().splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
 objects=[cm/x for x in shlex.split(lines[i].split(': ',1)[1])[1:] if x.endswith('.o') and (x.startswith('core/') or x.startswith('extern/')) and not x.endswith('/StarJsonPath.cpp.o')]
 if not objects or any(not x.is_file() for x in objects):raise RuntimeError('existing native objects missing; no rebuild')
 libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+15] if x.startswith('  LINK_LIBRARIES = ')));libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
 tracked=[*HERE.glob('*'),db,cm/'build.ninja',Path(recipe[0]).resolve(),*objects,*[Path(x) for x in libs if x.endswith('.a')]]
 tracked += [x for x in (ROOT/'source/core').rglob('*') if x.is_file() and x.suffix in ['.h','.hpp','.cpp']]
 commands=[]
 def run(cmd,name):
  commands.append(shlex.join(map(str,cmd)));r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=75,env=dict(os.environ,LAB_OBSERVATIONS=str(out/(name+'.observations'))));(out/(name+'.log')).write_text(commands[-1]+'\n'+r.stdout+r.stderr);return r
 for num,src in enumerate([HERE/'lab.cpp',HERE/'StarJsonPath.reference.cpp',ROOT/'source/core/StarJsonPath.cpp']):
  dep=out/(str(num)+'.d');cmd=[recipe[0],*flags,'-I'+str(HERE),'-M','-MF',str(dep),str(src)]
  if a.define:cmd+=['-D'+a.define]
  if run(cmd,'deps-'+str(num)).returncode:raise RuntimeError('dependency scan failed')
  tracked += [Path(x) if Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])]
 if a.archive:tracked += [a.archive.resolve(),*list((ROOT/'source/rust/ffi/src').glob('*.rs'))]
 if a.reference_report:tracked.append(a.reference_report.resolve())
 tracked=list(dict.fromkeys(x.resolve() for x in tracked if x.is_file()));before={str(x):sha(x) for x in tracked};(out/'before.json').write_text(json.dumps(before,indent=2))
 native=out/'native-core.a'
 if run(['/usr/bin/ar','rcs',str(native),*map(str,objects)],'archive').returncode:raise RuntimeError('archive failure')
 def compile(src,name,rust=False,reference=None,lab=None):
  binary=out/name;cmd=[recipe[0],*flags,'-I'+str(HERE),str(lab or HERE/'lab.cpp'),str(reference or HERE/'StarJsonPath.reference.cpp'),str(src),str(native),*libs,'-Wl,-dead_strip']
  if rust:cmd+=['-D'+a.define,str(a.archive.resolve())]
  cmd+=['-o',str(binary)]
  if run(cmd,name+'-compile').returncode:raise RuntimeError('compile failure '+name)
  return binary
 for name,args in [('define',['--define','evil']),('archive',['--archive','missing']),('output',['--output',str(ROOT/'build/elsewhere')])]:
  if run(['python3',str(Path(__file__).resolve()),'--output',str(out/'cli'),*args],'cli-'+name).returncode!=2:raise RuntimeError('CLI negative escaped')
  negative.append('cli-'+name)
 binary=compile(ROOT/'source/core/StarJsonPath.cpp','calibration',bool(a.define));r=run([str(binary)],'baseline');repeat=run([str(binary)],'repeat')
 if r.returncode or repeat.returncode or r.stdout!=repeat.stdout:raise RuntimeError('baseline failed; no controls credited')
 result=json.loads(r.stdout)
 if (out/'baseline.observations').read_bytes()!=(out/'repeat.observations').read_bytes():raise RuntimeError('ordered observations not repeatable')
 result['ordered_observations_sha256']=sha(out/'baseline.observations')
 if a.reference_report:
  ref=json.loads(a.reference_report.read_text())
  def compare(ref):
   if ref.get('backend')!='cpp' or ref.get('status')!='PASS' or ref.get('cases')!=result['cases'] or ref.get('observation_digest')!=result['observation_digest'] or ref.get('ordered_observations_sha256')!=result['ordered_observations_sha256']:raise ValueError('independent observation mismatch')
  compare(ref)
  try:compare(dict(ref,observation_digest='corrupt'))
  except ValueError:negative.append('independent-digest-corrupt')
  else:raise RuntimeError('independent comparison negative escaped')
 if a.define:
  bad=run([str(binary),'missing-receipt'],'missing-receipt')
  if bad.returncode!=1 or 'COMPARISON receipt missing' not in bad.stderr:raise RuntimeError('receipt negative escaped')
  negative.append('missing-receipt')
 # Exercise the known verifier blind spot in an isolated harness mutant.
 truncated=out/'truncated-error-lab.cpp';body=(HERE/'lab.cpp').read_bytes()
 if body.count(b'error=printException(e,false);')!=1:raise RuntimeError('full-error control anchor missing')
 truncated.write_bytes(body.replace(b'error=printException(e,false);',b'error=e.what();'))
 broken=compile(ROOT/'source/core/StarJsonPath.cpp','truncated-error-harness',lab=truncated)
 bad=run([str(broken)],'truncated-error-harness')
 if bad.returncode!=1 or 'COMPARISON literal full exception bytes include NUL' not in bad.stderr:raise RuntimeError('full-error verifier negative escaped')
 negative.append('truncated-error-harness')
 raw=(HERE/'StarJsonPath.original.cpp').read_bytes()
 for name,old,new in [
 ('escape-zero',b"buffer.append('~');",b"buffer.append('!');"),
 ('escape-one',b"buffer.append('/');",b"buffer.append('!');"),
 ('dash-hint',b'buffer == "-"',b'buffer == "!"'),
 ('query-empty-bracket',b"return TypeHint::Array;\n\n    } else {",b"return TypeHint::Object;\n\n    } else {"),
 ('numeric-hint',b'if (index.isValid() ||',b'if (false ||'),
 ('query-digit',b"*iterator <= '9'",b"*iterator <= '8'"),
 ('wrong-error',b'Incomplete escape sequence',b'WRONG escape sequence')]:
  if raw.count(old)!=1:raise RuntimeError('mutant anchor missing '+name)
  src=out/(name+'.cpp');src.write_bytes(raw.replace(old,new,1));mutant=compile(src,name);bad=run([str(mutant)],name)
  if bad.returncode!=1 or 'COMPARISON' not in bad.stderr:raise RuntimeError('mutant not clean comparison failure '+name)
  negative.append(name)
 # Paired error corruption can fool an in-process differential check, but not
 # the independently emitted native-only ordered observation stream.
 src=out/'paired-error.cpp';src.write_bytes(raw.replace(b'Incomplete escape sequence',b'WRONG escape sequence'))
 refsrc=out/'paired-reference.cpp';refsrc.write_bytes((HERE/'StarJsonPath.reference.cpp').read_bytes().replace(b'Incomplete escape sequence',b'WRONG escape sequence'))
 paired=compile(src,'paired-error',reference=refsrc);bad=run([str(paired)],'paired-error')
 if bad.returncode or sha(out/'paired-error.observations')==result['ordered_observations_sha256']:raise RuntimeError('paired-error independence negative escaped')
 negative.append('paired-wrong-errors-independent-stream')
 after={str(x):sha(x) for x in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after:raise RuntimeError('source/compiler/objects/archive/dependency drift; rerun required')
 result.update(status='PASS',backend='rust' if a.define else 'cpp',negative_controls=negative,commands=commands,bindings=before,binary_sha256=sha(binary),native_archive_sha256=sha(native),limits=['ordered observation stream uses SHA256; finite tests are NOT universal equivalence proof','native source freshness requires parent build seal','allocation faults, error-allocation timing and C++ callback exception identity not injected','no game/performance/screenshot/platform claim'])
 (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['bindings','commands']}))
if __name__=='__main__':main()
