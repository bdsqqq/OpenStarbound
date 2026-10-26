"""Compile frozen regression against coherent profile, optionally instrument fill TU."""
import argparse,pathlib,json,shlex,subprocess,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--cmake',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--sanitize',action='store_true');p.add_argument('--expect',choices=['pre-native','pre-rust','post'],required=True);p.add_argument('--leaf',action='store_true');a=p.parse_args()
cm=a.cmake.resolve();out=a.output.resolve()
assert out.is_relative_to(ROOT/'build') and out != ROOT/'build', 'fresh output must be under build/'
out.mkdir(parents=True,exist_ok=False)
source=ROOT/('source/lab/byte-array/empty_fill_leaf.cpp' if a.leaf else 'source/lab/byte-array/empty_fill.cpp')
rows=json.loads((cm/'compile_commands.json').read_text());entry=next(q for q in rows if q['file'].endswith('/StarByteArray.cpp'))
r=shlex.split(entry['command']);flags=[];skip=False
for x in r[1:]:
 if skip:skip=False;continue
 if x=='-o':skip=True
 elif x not in ('-c',entry['file']):flags.append(x)
lines=(cm/'build.ninja').read_text().splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
objects=[cm/x for x in shlex.split(lines[i].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/'))]
libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+18] if x.startswith('  LINK_LIBRARIES = ')))
libs=[str(cm/x) if x.endswith('.a') and not pathlib.Path(x).is_absolute() else x for x in libs]
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
tracked=[pathlib.Path(__file__).resolve(),cm/'compile_commands.json',cm/'build.ninja',pathlib.Path(r[0]).resolve(),source,ROOT/'source/core/StarByteArray.cpp',ROOT/'source/core/StarByteArrayHost.hpp',*objects,*(pathlib.Path(x) for x in libs if x.endswith('.a'))]
before={str(p):sha(p) for p in tracked};commands=[]
def run(argv,label):
 q=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,timeout=60)
 (out/(label+'.stdout')).write_bytes(q.stdout);(out/(label+'.stderr')).write_bytes(q.stderr)
 commands.append(dict(command=list(map(str,argv)),returncode=q.returncode));return q
assert run(['/usr/bin/ar','rcs',out/'core.a',*objects],'archive').returncode==0
extra=[]
if a.sanitize:
 flags+=['-fsanitize=undefined','-fno-sanitize-recover=undefined']
 assert run([r[0],*flags,'-c',entry['file'],'-o',out/'byte-array-instrumented.o'],'instrument').returncode==0
 extra=[out/'byte-array-instrumented.o']
assert run([r[0],*flags,source,*extra,out/'core.a',*libs,'-Wl,-dead_strip','-o',out/'probe'],'compile').returncode==0
results=[]
for case in (['leaf'] if a.leaf else ['default','moved','reserved','buffer','stream']):
 q=run([out/'probe']+([] if a.leaf else [case]),case);results.append(dict(case=case,exitCode=q.returncode))
 expected=0 if a.leaf or a.expect=='post' or case=='reserved' else (10 if a.expect=='pre-rust' else 1)
 assert q.returncode==expected,(case,q.returncode,expected,q.stderr)
 if expected==0:assert q.stdout==(b'EMPTY_FILL_LEAF_GUARDS_PASS\n' if a.leaf else b'EMPTY_FILL_CASE_PASS\n')
 if a.expect=='pre-native' and expected:assert b'null pointer' in q.stderr or b'nonnull' in q.stderr
 if a.expect=='pre-rust' and expected:assert b'ByteArray host protocol failure' in q.stderr
for path,h in before.items():assert sha(path)==h,path
result=dict(status='EMPTY_FILL_EXPECTATION_PASS',expectation=a.expect,cases=results,bindings=before,commands=commands,sanitizer=a.sanitize,limits=['new empty-fill contract; no equivalence to legacy null-memset UB'])
(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'],a.expect,flush=True)
