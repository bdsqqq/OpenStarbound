#!/usr/bin/env python3
"""CPP-only frozen JsonPatch calibration. No shared native rebuilds or Rust."""
import argparse,hashlib,json,shlex,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
REV='b07cae00'
OWN=['run.py','lab.cpp','StarJsonPatch.original.cpp','StarJsonPatch.original.hpp','StarJsonPatch.reference.cpp','StarJsonPatch.reference.hpp']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--reference-report',type=Path);a=p.parse_args();out=a.output.resolve();base=ROOT/'build/json-patch-lab'
 if not out.is_relative_to(base) or out==base or out.is_relative_to(base/'host-prototype'):p.error('owned nested lab output required')
 out.mkdir(parents=True,exist_ok=True);negative=[];commands=[]
 def gate(ext,raw,adapt):
  orig=subprocess.check_output(['git','show',REV+':source/core/StarJsonPatch.'+ext],cwd=ROOT);want=orig.replace(b'namespace Star {',b'namespace JsonPatchReference {\nusing namespace Star;')
  if ext=='cpp':want=want.replace(b'"StarJsonPatch.hpp"',b'"StarJsonPatch.reference.hpp"')
  if raw!=orig or adapt!=want:raise ValueError('freeze drift')
 for ext in ['cpp','hpp']:
  raw=(HERE/('StarJsonPatch.original.'+ext)).read_bytes();adapt=(HERE/('StarJsonPatch.reference.'+ext)).read_bytes();gate(ext,raw,adapt)
  if (ROOT/('source/core/StarJsonPatch.'+ext)).read_bytes()!=raw:raise ValueError('production changed during CPP phase')
  for label,r,d in [('raw',raw+b' ',adapt),('adapt',raw,adapt+b' ')]:
   try:gate(ext,r,d)
   except ValueError:negative.append(label+'-'+ext)
   else:raise RuntimeError('freeze control escaped')
 cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarJsonPatch.cpp'));recipe=shlex.split(entry['command']);flags=[];skip=False
 for f in recipe[1:]:
  if skip:skip=False;continue
  if f=='-o':skip=True
  elif f not in ['-c',entry['file']]:flags.append(f)
 if any('STAR_USE_RUST_' in x for x in flags):raise ValueError('not CPP recipe')
 lines=(cm/'build.ninja').read_text().splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
 objects=[cm/x for x in shlex.split(lines[i].split(': ',1)[1])[1:] if x.endswith('.o') and (x.startswith('core/') or x.startswith('extern/')) and not x.endswith('/StarJsonPatch.cpp.o')]
 if not objects or any(not x.is_file() for x in objects):raise ValueError('sealed objects unavailable')
 libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+15] if x.startswith('  LINK_LIBRARIES = ')));libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
 def run(cmd,name):
  commands.append(shlex.join(map(str,cmd)));r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=90,env=dict(os.environ,LAB_OBSERVATIONS=str(out/(name+'.observations'))));(out/(name+'.log')).write_text(commands[-1]+'\n'+r.stdout+r.stderr);return r
 tracked=[HERE/x for x in OWN]+[db,cm/'build.ninja',Path(recipe[0]).resolve(),*objects,*[Path(x) for x in libs if x.endswith('.a')]]
 for n,src in enumerate([HERE/'lab.cpp',HERE/'StarJsonPatch.reference.cpp',ROOT/'source/core/StarJsonPatch.cpp']):
  dep=out/(str(n)+'.d');r=run([recipe[0],*flags,'-I'+str(HERE),'-M','-MF',str(dep),str(src)],'deps-'+str(n))
  if r.returncode:raise RuntimeError('dependency scan failed')
  tracked += [Path(x) if Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])]
 tracked=list(dict.fromkeys(x.resolve() for x in tracked if x.is_file()));before={str(x):sha(x) for x in tracked};(out/'before.json').write_text(json.dumps(before,indent=2))
 native=out/'native-core.a'
 if run(['/usr/bin/ar','rcs',str(native),*map(str,objects)],'archive').returncode:raise RuntimeError('archive failure')
 def compile(name,src=None,lab=None,ref=None,extra=None):
  binary=out/name;r=run([recipe[0],*flags,'-I'+str(HERE),str(lab or HERE/'lab.cpp'),str(ref or HERE/'StarJsonPatch.reference.cpp'),str(src or ROOT/'source/core/StarJsonPatch.cpp'),*([str(extra)] if extra else []),str(native),*libs,'-Wl,-dead_strip','-o',str(binary)],name+'-compile')
  if r.returncode:raise RuntimeError('compile failure '+name)
  return binary
 binary=compile('calibration');r=run([str(binary)],'baseline');repeat=run([str(binary)],'repeat')
 if r.returncode or repeat.returncode or r.stdout!=repeat.stdout or (out/'baseline.observations').read_bytes()!=(out/'repeat.observations').read_bytes():raise RuntimeError('baseline/repeat failed')
 result=json.loads(r.stdout)
 def compare(ref):
  if ref.get('backend')!='cpp' or ref.get('status')!='PASS' or ref.get('cases')!=result['cases'] or ref.get('ordered_observations_sha256')!=sha(out/'baseline.observations') or ref.get('bindings')!=before:raise ValueError('independent stream/source identity mismatch')
 native_identity=dict(result,backend='cpp',status='PASS',ordered_observations_sha256=sha(out/'baseline.observations'),bindings=before)
 if a.reference_report:compare(json.loads(a.reference_report.read_text()))
 for name,changes in [('wrong-stream-provenance',{'ordered_observations_sha256':'corrupt'}),('wrong-source-provenance',{'bindings':{}})]:
  try:compare(dict(native_identity,**changes))
  except ValueError:negative.append(name)
  else:raise RuntimeError('independent provenance negative escaped')
 raw=(HERE/'StarJsonPatch.original.cpp').read_bytes()
 mutants=[('inverse',b'auto inverseTest = op.getBool("inverse", false);',b'auto inverseTest = !op.getBool("inverse", false);'),('search-first',b'return i + 1;',b'return i;'),('explicit-null',b'auto value = op.opt("value");',b'auto value = Maybe<Json>(op.get("value"));'),('replace-order',b'return pointer.add(pointer.remove(base), value);',b'return pointer.add(base, value);'),('move-overlap',b'auto result = toPointer.add(base, searchable.get(index - 1));',b'auto result = toPointer.add(fromPointer.remove(base), searchable.get(index - 1));'),('value-access',b'auto value = op.get("value");',b'auto value = op.get("value", Json());')]
 for name,old,new in mutants:
  if old not in raw:raise RuntimeError('mutant anchor missing')
  src=out/(name+'.cpp');src.write_bytes(raw.replace(old,new));mut=compile(name,src=src);bad=run([str(mut)],name)
  if bad.returncode!=1 or 'COMPARISON' not in bad.stderr:raise RuntimeError('mutant not comparison-detected '+name)
  negative.append(name)
 # A paired corruption passes in-process differential comparison but must alter
 # independent ordered native-only stream identity.
 old=b'Invalid operation: {}';new=b'WRONG operation: {}';src=out/'paired.cpp';src.write_bytes(raw.replace(old,new));ref=out/'paired-ref.cpp';ref.write_bytes((HERE/'StarJsonPatch.reference.cpp').read_bytes().replace(old,new));paired=compile('paired',src=src,ref=ref);bad=run([str(paired)],'paired')
 if bad.returncode or sha(out/'paired.observations')==sha(out/'baseline.observations'):raise RuntimeError('independent paired corruption escaped')
 negative.append('paired-error-independent-stream')
 # Exercise actual dependency recursion; both controller copies share it, so
 # only an independent legacy anchor can detect this mutation.
 jsonsrc=ROOT/'source/core/StarJson.cpp';rawjson=jsonsrc.read_bytes();old=b'jsonPartialMatch(c, b)';new=b'jsonPartialMatch(b, c)'
 if rawjson.count(old)!=1:raise RuntimeError('recursion dependency anchor missing')
 dependency=out/'partial-recursion.cpp';dependency.write_bytes(rawjson.replace(old,new));mut=compile('partial-recursion',extra=dependency);bad=run([str(mut)],'partial-recursion')
 if bad.returncode!=1 or 'COMPARISON independent literal' not in bad.stderr:raise RuntimeError('recursion control escaped')
 negative.append('reversed-partial-recursion-independent-anchor')
 body=(HERE/'lab.cpp').read_bytes()
 for name,old,new in [('truncated-error',b'r.error=printException(e,false);',b'r.error=e.what();'),('wrong-type',b'r.value=typed(v);',b'r.value=v.repr().utf8();'),('wrong-category',b'r.category=1;',b'r.category=3;'),('wrong-state',b'check(typed(b)==before,',b'const_cast<Json&>(b)=Json();check(typed(b)==before,')]:
  lab=out/(name+'-lab.cpp');lab.write_bytes(body.replace(old,new));mut=compile(name,lab=lab);bad=run([str(mut)],name)
  if bad.returncode!=1 or 'COMPARISON' not in bad.stderr:raise RuntimeError('verifier control escaped '+name)
  negative.append(name)
 after={str(x):sha(x) for x in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after:raise RuntimeError('source/compiler/dependency/object drift')
 result.update(status='PASS',backend='cpp',negative_controls=negative,ordered_observations_sha256=sha(out/'baseline.observations'),binary_sha256=sha(binary),native_archive_sha256=sha(native),bindings=before,commands=commands,limits=['finite calibration, not universal equivalence','sibling operand order is observed for this Apple clang recipe only','no allocation fault injection, Rust backend, production changes, runtime game, screenshot or performance claim','sealed native object freshness requires parent seal validation','jsonPartialMatch recursion is a real native dependency, not changed by this complete JsonPatch module freeze'])
 (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['bindings','commands']}))
if __name__=='__main__':main()
