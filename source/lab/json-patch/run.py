#!/usr/bin/env python3
"""Frozen native JsonPatch oracle with independently selected production backend."""
import argparse,hashlib,json,shlex,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
REV='b07cae00'
OWN=['run.py','lab.cpp','candidate_abi.cpp','candidate_host.cpp','StarJsonPatch.original.cpp','StarJsonPatch.original.hpp','StarJsonPatch.reference.cpp','StarJsonPatch.reference.hpp']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--reference-report',type=Path);p.add_argument('--backend',choices=['cpp','rust'],default='cpp');a=p.parse_args();out=a.output.resolve();base=ROOT/'build/json-patch-lab'
 if not out.is_relative_to(base) or out==base or out.is_relative_to(base/'host-prototype') or out.exists() or any(x.is_symlink() for x in [a.output.absolute(),*a.output.absolute().parents]):p.error('new owned non-symlink nested lab output required')
 out.mkdir(parents=True,exist_ok=True);negative=[];commands=[]
 def gate(ext,raw,adapt):
  orig=subprocess.check_output(['git','show',REV+':source/core/StarJsonPatch.'+ext],cwd=ROOT);want=orig.replace(b'namespace Star {',b'namespace JsonPatchReference {\nusing namespace Star;')
  if ext=='cpp':want=want.replace(b'"StarJsonPatch.hpp"',b'"StarJsonPatch.reference.hpp"')
  if raw!=orig or adapt!=want:raise ValueError('freeze drift')
 for ext in ['cpp','hpp']:
  raw=(HERE/('StarJsonPatch.original.'+ext)).read_bytes();adapt=(HERE/('StarJsonPatch.reference.'+ext)).read_bytes();gate(ext,raw,adapt)
  if ext=='hpp' and (ROOT/('source/core/StarJsonPatch.'+ext)).read_bytes()!=raw:raise ValueError('public header drift')
  if ext=='cpp':
   production=(ROOT/'source/core/StarJsonPatch.cpp').read_bytes()
   if production!=raw:
    # The bridge must retain a verbatim complete fallback, not an edited clone.
    marker=b'#ifdef STAR_USE_RUST_JSON_PATCH\n'
    if production.count(marker)!=1 or production.count(b'#else\n')!=1 or not production.endswith(b'#endif\n'):raise ValueError('unexpected selector structure')
    reconstructed=production.split(marker,1)[0]+production.split(b'#else\n',1)[1][:-len(b'#endif\n')]
    if reconstructed!=raw:raise ValueError('complete original fallback is not byte-exact')
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
 rust_archive=ROOT/'build/json-patch-rust/target/release/libstar_engine_ffi.a'
 extra_sources=[ROOT/'source/core/StarRustJsonPatch.h',ROOT/'source/core/StarJsonPatchHost.hpp',ROOT/'source/rust/ffi/src/json_patch.rs',ROOT/'source/rust/ffi/src/lib.rs']
 if a.backend=='rust' and (not rust_archive.is_file() or any(not x.is_file() for x in extra_sources)):raise ValueError('Rust bridge/archive not ready')
 tracked=[HERE/x for x in OWN]+[db,cm/'build.ninja',Path(recipe[0]).resolve(),*objects,*[Path(x) for x in libs if x.endswith('.a')]]+[x for x in extra_sources if x.is_file()]+([rust_archive] if rust_archive.is_file() else [])
 for n,src in enumerate([HERE/'lab.cpp',HERE/'StarJsonPatch.reference.cpp',ROOT/'source/core/StarJsonPatch.cpp']+([HERE/'candidate_abi.cpp',HERE/'candidate_host.cpp'] if a.backend=='rust' else [])):
  dep=out/(str(n)+'.d');r=run([recipe[0],*flags,'-I'+str(HERE),'-M','-MF',str(dep),str(src)],'deps-'+str(n))
  if r.returncode:raise RuntimeError('dependency scan failed')
  tracked += [Path(x) if Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])]
 tracked=list(dict.fromkeys(x.resolve() for x in tracked if x.is_file()));before={str(x):sha(x) for x in tracked};(out/'before.json').write_text(json.dumps(before,indent=2))
 native=out/'native-core.a'
 if run(['/usr/bin/ar','rcs',str(native),*map(str,objects)],'archive').returncode:raise RuntimeError('archive failure')
 def compile(name,src=None,lab=None,ref=None,extra=None,selected=False):
  selected_flags=['-DSTAR_USE_RUST_JSON_PATCH=1'] if selected and a.backend=='rust' else []
  selected_libs=[str(rust_archive)] if selected and a.backend=='rust' else []
  binary=out/name;r=run([recipe[0],*flags,*selected_flags,'-I'+str(HERE),str(lab or HERE/'lab.cpp'),str(ref or HERE/'StarJsonPatch.reference.cpp'),str(src or ROOT/'source/core/StarJsonPatch.cpp'),*([str(extra)] if extra else []),str(native),*selected_libs,*libs,'-Wl,-dead_strip','-o',str(binary)],name+'-compile')
  if r.returncode:raise RuntimeError('compile failure '+name)
  return binary
 binary=compile('calibration',selected=True);r=run([str(binary)],'baseline');repeat=run([str(binary)],'repeat')
 if r.returncode or repeat.returncode or r.stdout!=repeat.stdout or (out/'baseline.observations').read_bytes()!=(out/'repeat.observations').read_bytes():raise RuntimeError('baseline/repeat failed')
 result=json.loads(r.stdout)
 if a.backend=='rust':
  abi=out/'candidate-abi';rr=run([recipe[0],*flags,HERE/'candidate_abi.cpp',rust_archive,*libs,'-Wl,-dead_strip','-o',abi],'candidate-abi-compile')
  if rr.returncode:raise RuntimeError('candidate ABI compile failed')
  rr=run([abi],'candidate-abi')
  if rr.returncode:raise RuntimeError('candidate ABI behavior failed')
  result['raw_abi']=json.loads(rr.stdout)
  host_binary=out/'candidate-host';rr=run([recipe[0],*flags,'-I'+str(HERE),HERE/'candidate_host.cpp',HERE/'StarJsonPatch.reference.cpp',native,rust_archive,*libs,'-Wl,-dead_strip','-o',host_binary],'candidate-host-compile')
  if rr.returncode:raise RuntimeError('candidate retained-native host compile failed')
  rr=run([host_binary],'candidate-host');rep=run([host_binary],'candidate-host-repeat')
  if rr.returncode or rep.returncode or rr.stdout!=rep.stdout:raise RuntimeError('candidate retained-native host behavior failed')
  result['native_host']=json.loads(rr.stdout)
  bad=run([host_binary,'known-fault'],'candidate-host-known-fault')
  if bad.returncode!=1 or 'COMPARISON deliberate wrong typed handler' not in bad.stderr:raise RuntimeError('native host known fault escaped')
  negative.append('candidate-native-host-known-fault')
  for mutant in ['receipt','order']:
   bad=run([abi,mutant],'candidate-abi-'+mutant)
   if bad.returncode!=1 or 'COMPARISON' not in bad.stderr:raise RuntimeError('candidate ABI known failure escaped')
   negative.append('candidate-abi-'+mutant)
 independent=compile('independent-cpp',src=HERE/'StarJsonPatch.original.cpp');ind=run([str(independent)],'independent-cpp')
 if ind.returncode or (out/'independent-cpp.observations').read_bytes()!=(out/'baseline.observations').read_bytes():raise RuntimeError('independent complete CPP ordered stream mismatch')
 def compare(ref):
  if ref.get('backend')!=a.backend or ref.get('status')!='PASS' or ref.get('cases')!=result['cases'] or ref.get('ordered_observations_sha256')!=sha(out/'baseline.observations') or ref.get('bindings')!=before:raise ValueError('independent stream/source identity mismatch')
 native_identity=dict(result,backend=a.backend,status='PASS',ordered_observations_sha256=sha(out/'baseline.observations'),bindings=before)
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
 if a.backend=='rust':
  suppressed=out/'receipt-suppressed-lab.cpp';body=(HERE/'lab.cpp').read_bytes();anchor=b'#include "StarRustJsonPatch.h"';suppressed.write_bytes(body.replace(anchor,anchor+b'\nstatic uint64_t suppressed_receipt(uint32_t,uint32_t){return 0;}\n#define star_json_patch_call_count suppressed_receipt'))
  mut=compile('rust-receipt-suppressed',lab=suppressed,selected=True);bad=run([str(mut)],'rust-receipt-suppressed')
  if bad.returncode!=1 or 'COMPARISON semantic attempt count' not in bad.stderr:raise RuntimeError('suppressed Rust receipts escaped')
  negative.append('rust-receipt-suppressed')
  bridge=(ROOT/'source/core/StarJsonPatchHost.hpp').read_bytes();controller=(ROOT/'source/core/StarJsonPatch.cpp').read_bytes()
  for name,old,new in [('rust-host-inverse',b'*out=c.Op->getBool("inverse",false);',b'*out=!c.Op->getBool("inverse",false);'),('rust-host-pending',b'catch(JsonException const&) {return JP_JSON;}',b'catch(JsonException const&) {return JP_OTHER;}'),('rust-adapter-dispatch',b'operation(JP_ADD, base, op)',b'operation(JP_REMOVE, base, op)')]:
   scope=controller if name=='rust-adapter-dispatch' else bridge
   if scope.count(old)!=1:raise RuntimeError('Rust-selected mutant anchor drift '+name)
   mutant_dir=out/name;mutant_dir.mkdir();src=mutant_dir/'StarJsonPatch.cpp';src.write_bytes(scope.replace(old,new) if name=='rust-adapter-dispatch' else controller);(mutant_dir/'StarJsonPatchHost.hpp').write_bytes(bridge if name=='rust-adapter-dispatch' else bridge.replace(old,new))
   mut=compile(name+'-binary',src=src,selected=True);bad=run([str(mut)],name)
   if bad.returncode!=1 or 'COMPARISON' not in bad.stderr:raise RuntimeError('Rust selected mutant not comparison-detected '+name)
   negative.append(name)
 after={str(x):sha(x) for x in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after:raise RuntimeError('source/compiler/dependency/object drift')
 result.update(status='PASS',backend=a.backend,negative_controls=negative,ordered_observations_sha256=sha(out/'baseline.observations'),binary_sha256=sha(binary),native_archive_sha256=sha(native),bindings=before,commands=commands,limits=['finite calibration, not universal equivalence','sibling operand order is observed for this Apple clang recipe only','no allocation fault injection, runtime game, screenshot or performance claim','sealed native object freshness requires parent seal validation','jsonPartialMatch recursion is a real native dependency, not changed by this complete JsonPatch module freeze'])
 (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['bindings','commands']}))
if __name__=='__main__':main()
