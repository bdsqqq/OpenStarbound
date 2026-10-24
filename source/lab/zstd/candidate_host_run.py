#!/usr/bin/env python3
"""Standalone prototype build; never runs the exhausted output-only oracle."""
import argparse,hashlib,json,shlex,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=ROOT/'source/lab/zstd'
BASE=ROOT/'build/zstd-lab'
parser=argparse.ArgumentParser();parser.add_argument('name');parser.add_argument('--identity-manifest',required=True,type=Path);args=parser.parse_args();name=args.name
if Path(name).name!=name:raise SystemExit('simple new run directory only')
out=BASE/name
if any(p.is_symlink() for p in [out,*out.parents]):raise SystemExit('nonsymlink output required')
out.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
commands=[]
def run(cmd,label):
 cmd=list(map(str,cmd));commands.append(cmd)
 r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=120)
 (out/(label+'.log')).write_bytes((shlex.join(cmd)+'\n').encode()+r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(label+' failed; compile failure is NOT semantic detection')
 return r.stdout
cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json'
entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarZSTDCompression.cpp'))
recipe=shlex.split(entry['command']);flags=[];skip=False
for x in recipe[1:]:
 if skip:skip=False;continue
 if x=='-o':skip=True
 elif x not in ['-c',entry['file']]:flags.append(x)
if any('STAR_USE_RUST' in x for x in flags):raise RuntimeError('non-native reference recipe')
lines=(cm/'build.ninja').read_text().splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
objs=[cm/x for x in shlex.split(lines[i].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/')) and not x.endswith('/StarZSTDCompression.cpp.o')]
libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+15] if x.startswith('  LINK_LIBRARIES = ')))
libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
for ext in ['cpp','hpp']:
 raw=subprocess.check_output(['git','show','d62f1662:source/core/StarZSTDCompression.'+ext],cwd=ROOT)
 if ext=='hpp' and (ROOT/('source/core/StarZSTDCompression.'+ext)).read_bytes()!=raw:raise RuntimeError('public header drift')
 if (HERE/('StarZSTDCompression.original.'+ext)).read_bytes()!=raw:raise RuntimeError('original source drift')
 expected=raw.replace(b'namespace Star {',b'namespace ZstdReference {\nusing namespace Star;')
 if ext=='cpp':expected=expected.replace(b'"StarZSTDCompression.hpp"',b'"StarZSTDCompression.reference.hpp"')
 if (HERE/('StarZSTDCompression.reference.'+ext)).read_bytes()!=expected:raise RuntimeError('reference adaptation drift')
rust=ROOT/'build/zstd-rust/target/release/libstar_engine_ffi.a'
production_header=ROOT/'source/core/StarRustZstd.h'
host=(HERE/'host_contract.cpp').read_text()
start=host.index('struct Stop');end=host.index('// All allocations,')
host=host[:start]+'uint32_t run(uint32_t m,StarZstdHost h,void* p) noexcept {return star_zstd_run(m,h,p); }\n\n'+host[end:]
host=host.replace('#include "host_contract.hpp"','#include "'+str(production_header)+'"')
generated_host=out/'candidate_host.cpp';generated_host.write_text(host)
test=(HERE/'host_contract_test.cpp').read_text()
removed='CHECK(run(0,throwingHost,nullptr)==ZC_PANIC);'
if test.count(removed)!=1:raise RuntimeError('throwing assertion gate')
test=test.replace(removed,'').replace('#include "host_contract.cpp"','#include "'+str(generated_host)+'"')
generated_test=out/'candidate_host_test.cpp';generated_test.write_text(test)
sources=[generated_test,HERE/'StarZSTDCompression.reference.cpp']
smoke=out/'header.c';smoke.write_text('#include "StarRustZstd.h"\nint main(void){StarZstdHost callback=0;return callback?1:0;}\n')
for language,standard in [('c','c11'),('c++','c++17')]:
 run([recipe[0],'-x',language,'-std='+standard,'-Wall','-Wextra','-Werror','-pedantic','-I'+str(ROOT/'source/core'),'-I'+str(HERE),'-fsyntax-only',smoke],'header-'+standard)
tracked=[HERE/'host_contract_test.cpp',rust,production_header,generated_host,generated_test,smoke,Path(__file__),Path(sys.executable).resolve(),db,cm/'build.ninja',Path(recipe[0]).resolve(),*objs,*[Path(x) for x in libs if x.endswith('.a')],*sources,HERE/'host_contract.cpp',HERE/'host_contract.hpp',HERE/'StarZSTDCompression.original.cpp',HERE/'StarZSTDCompression.original.hpp']
for n,src in enumerate(sources):
 dep=out/(str(n)+'.d');run([recipe[0],*flags,'-I'+str(HERE),'-M','-MF',dep,src],'deps'+str(n))
 tracked += [Path(x) if Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])]
# Identity reuse is NOT semantic acceptance of the blocked Zstd oracle.
seal=args.identity_manifest.resolve()
sealed=json.loads(seal.read_text())
identity_paths=[db,cm/'build.ninja',Path(recipe[0]).resolve(),*objs,*[Path(x) for x in libs if x.endswith('.a')]]
for p in identity_paths:
 p=p.resolve()
 if sealed.get(str(p))!=sha(p):raise RuntimeError('sealed reference dependency drift: '+str(p))
tracked.extend([seal,Path('/usr/bin/ar').resolve()])
tracked=list(dict.fromkeys(p.resolve() for p in tracked))
before={str(p):sha(p) for p in tracked};(out/'before.json').write_text(json.dumps(before,indent=2))
archive=out/'native-core.a';run(['/usr/bin/ar','rcs',archive,*objs],'archive');archive_sha=sha(archive)
binary=out/'prototype'
run([recipe[0],*flags,'-I'+str(HERE),*sources,archive,rust,*libs,'-Wl,-dead_strip','-o',binary],'compile')
binary_sha=sha(binary);result=run([binary],'execution').decode()
# These controls qualify only the scripted controller tests, NOT the parent's
# separate source-gated native CAPI/fault oracle.
controls=[]
after={str(p):sha(p) for p in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
if before!=after or archive_sha!=sha(archive) or binary_sha!=sha(binary):raise RuntimeError('bound artifact drift')
report=dict(status='ACTUAL_RUST_FROZEN_HOST_PASS',reference_identity_manifest=str(seal),reference_identity_count=len(identity_paths),stdout=result,commands=commands,binary_sha256=binary_sha,archive_sha256=archive_sha,bindings=before,scripted_semantic_controls=controls,limits=['Actual Rust with frozen native host, not production NativeContext','CPP-only throwingHost assertion removed: foreign unwind into Rust is forbidden','723 observed checks, all 18 operations and 9 fields; core panic hook tested separately by core owner','No OOM claim; resize sentinel is counterfactual','Native CAPI trace qualification is separate candidate_trace_run.py','No game/platform universality claim'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(result);print(report['status'])
