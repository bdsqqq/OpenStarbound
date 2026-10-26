"""Finite live guard replay; VFS trials remain separate from application seals."""
import argparse,hashlib,json,pathlib,shlex,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--cmake',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--archive',type=pathlib.Path);p.add_argument('--expect-counts',type=int,choices=[0,1],default=0);a=p.parse_args();cm=a.cmake.resolve();out=a.output.resolve();assert out.is_relative_to(ROOT/'build');out.mkdir(exist_ok=False)
rows=json.loads((cm/'compile_commands.json').read_text());entry=next(q for q in rows if q['file'].endswith('/StarByteArray.cpp'));r=shlex.split(entry['command']);flags=[];skip=False
for x in r[1:]:
 if skip:skip=False;continue
 if x=='-o':skip=True
 elif x not in ('-c',entry['file']):flags.append(x)
lines=(cm/'build.ninja').read_text().splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
objects=[cm/x for x in shlex.split(lines[i].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/'))]
libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+18] if x.startswith('  LINK_LIBRARIES = ')));libs=[str(cm/x) if x.endswith('.a') and not pathlib.Path(x).is_absolute() else x for x in libs]
if a.archive:libs=[str(a.archive.resolve()) if x.endswith('libstar_engine_ffi.a') else x for x in libs]
source=ROOT/'source/lab/byte-array/guard_ranges.cpp'
tracked=[pathlib.Path(__file__).resolve(),source,cm/'compile_commands.json',cm/'build.ninja',ROOT/'source/core/StarByteArray.hpp',ROOT/'source/core/StarByteArrayHost.hpp',ROOT/'source/core/StarBufferHost.hpp',*objects,*(pathlib.Path(x) for x in libs if x.endswith('.a'))]
if '-ivfsoverlay' in flags:
 overlay=pathlib.Path(flags[flags.index('-ivfsoverlay')+1]);tracked.append(overlay)
 document=json.loads(overlay.read_text())
 for root in document['roots']:
  assert root['type']=='file', 'only explicit file overlays supported'
  tracked.extend([pathlib.Path(root['name']),pathlib.Path(root['external-contents'])])
 # Every C++ TU must see the same inline header, not an old core/new header mix.
 assert all('-ivfsoverlay '+str(overlay) in q['command'] for q in rows if q['file'].endswith('.cpp'))
tracked.append(pathlib.Path(r[0]).resolve())
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
before={str(p):sha(p) for p in tracked};commands=[]
def run(argv,label):
 q=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,timeout=60);(out/(label+'.stdout')).write_bytes(q.stdout);(out/(label+'.stderr')).write_bytes(q.stderr);commands.append(dict(command=list(map(str,argv)),exitCode=q.returncode));return q
assert run(['/usr/bin/ar','rcs',out/'core.a',*objects],'archive').returncode==0
assert run([r[0],*flags,source,out/'core.a',*libs,'-Wl,-dead_strip','-o',out/'probe'],'compile').returncode==0
results=[]
for case,expected in [('guards',0),('counts',a.expect_counts)]:
 q=run([out/'probe',case],case);assert q.returncode==expected,(case,q.returncode,expected,q.stderr);results.append(dict(case=case,exitCode=q.returncode))
assert all(sha(p)==h for p,h in before.items())
(out/'report.json').write_text(json.dumps(dict(status='FINITE_LIVE_BUFFER_GUARD_EXPECTATIONS_PASS',bindings=before,commands=commands,results=results,limits=['known live contexts only','not application or arbitrary-pointer qualification']),indent=2)+'\n');print(json.dumps(results))
