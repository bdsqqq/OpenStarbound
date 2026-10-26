#!/usr/bin/env python3
"""Build a fresh bounded ledger witness; old IODevice laboratory stays read-only."""
import argparse,copy,hashlib,json,os,pathlib,re,shlex,subprocess,sys,time
from ledger_verify import check,EXPECTED,verify
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).resolve().parent
REV='c233825b'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def adapt(s,ext):
 s=s.replace('namespace Star {','namespace Star { namespace IODeviceReference {',1);i=s.rfind('}');s=s[:i]+'} '+s[i:]
 return s.replace('#include "StarIODevice.hpp"','#include "StarIODevice.reference.hpp"',1) if ext=='cpp' else s
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=pathlib.Path);a=ap.parse_args();out=a.output.absolute();base=ROOT/'build/io-device-lab'
 if out.exists() or not out.is_relative_to(base) or not out.name.startswith('ledger-') or any(p.is_symlink() for p in [out,*out.parents]):ap.error('fresh owned nonsymlink directory required')
 out.mkdir(parents=True);started=time.time();receipts=[];controls=[]
 def save(name,obj):(out/name).write_text(json.dumps(obj,indent=2)+'\n')
 def run(cmd,name):
  cmd=list(map(str,cmd));exe=pathlib.Path(cmd[0]).resolve();before=sha(exe);p=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE);save('active.json',dict(runner_pid=os.getpid(),child_pid=p.pid,command=cmd,start=time.time()))
  try:stdout,stderr=p.communicate(timeout=65)
  except subprocess.TimeoutExpired:p.terminate();stdout,stderr=p.communicate(timeout=5);raise RuntimeError('bounded command timeout '+name)
  (out/(name+'.stdout')).write_bytes(stdout);(out/(name+'.stderr')).write_bytes(stderr);receipts.append(dict(name=name,command=cmd,pid=p.pid,returncode=p.returncode,executable_sha256_before=before,executable_sha256=sha(exe),stdout_sha256=hashlib.sha256(stdout).hexdigest(),stderr_sha256=hashlib.sha256(stderr).hexdigest()));save('receipts.json',receipts)
  if p.returncode or before!=sha(exe):raise RuntimeError('command failed '+name+'; no negative credit')
  return stdout
 # Freeze tiny contract and verifier/script/probe BEFORE any native execution.
 for ext in ('cpp','hpp'):
  frozen=subprocess.check_output(['git','show',REV+':source/core/StarIODevice.'+ext],cwd=ROOT).decode()
  for p,want in ((ROOT/f'source/core/StarIODevice.{ext}',frozen),(HERE/f'StarIODevice.original.{ext}',frozen),(HERE/f'StarIODevice.reference.{ext}',adapt(frozen,ext))):
   if p.read_text()!=want:raise ValueError('strict source/namespace provenance '+str(p))
 save('expected.json',EXPECTED)
 cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarIODevice.cpp'));recipe=shlex.split(entry['command']);flags=[];skip=False
 for x in recipe[1:]:
  if skip:skip=False;continue
  if x=='-o':skip=True
  elif x not in ('-c',entry['file']):flags.append(x)
 if any('STAR_USE_RUST' in x for x in flags):raise ValueError('Rust flags')
 lines=(cm/'build.ninja').read_text().splitlines();idx=next(i for i,l in enumerate(lines) if l.startswith('build ') and '/bin/starbound:' in l)
 libs=shlex.split(next(l.split(' = ',1)[1] for l in lines[idx+1:idx+15] if l.startswith('  LINK_LIBRARIES = ')));libs=[str(cm/x) if x.endswith('.a') and not pathlib.Path(x).is_absolute() else x for x in libs]
 identitypath=ROOT/'build/buffer-lab/native-identity-r1/manifest.json';identity=json.loads(identitypath.read_text())
 for file,digest in identity.items():
  if sha(file)!=digest:raise ValueError('native identity drift '+file)
 sys.path.insert(0,str(ROOT/'source/lab/behavior'));import build_provenance as provenance
 game=ROOT/'build/behavior/reference/bin/starbound';closure=provenance.verify(game);save('native-closure.json',closure)
 archive=ROOT/'build/io-device-lab/oracle-r2/native-core.a'
 old=json.loads((archive.parent/'before.json').read_text())
 # Old source files are not trusted as behavioral expectations; only archive origin.
 for file,digest in old.items():
  if file in identity and sha(file)!=digest:raise ValueError('archive input identity drift')
 members=run(['/usr/bin/ar','t',archive],'archive-members').decode().splitlines()
 objects=[cm/x for x in shlex.split(lines[idx].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/'))]
 if members!=['__.SYMDEF',*[p.name for p in objects]]:raise ValueError('archive member manifest')
 # Bind member bytes independently, without rewriting the cached archive.
 for obj in objects:
  member=subprocess.check_output(['/usr/bin/ar','p',str(archive),obj.name])
  if hashlib.sha256(member).hexdigest()!=sha(obj):raise ValueError('archive member drift '+obj.name)
 tracked=[*map(pathlib.Path,identity),identitypath,archive,pathlib.Path(recipe[0]).resolve(),pathlib.Path(sys.executable).resolve(),pathlib.Path('/usr/bin/ar').resolve(),pathlib.Path('/usr/bin/nm').resolve(),pathlib.Path(provenance.__file__),game,provenance.sidecar(game),*[ROOT/p for p in closure['source_files']],*HERE.glob('*')]
 tracked=[p for p in tracked if p.is_file()]
 for i,s in enumerate([HERE/'ledger.cpp',HERE/'StarIODevice.original.cpp',HERE/'StarIODevice.reference.cpp',ROOT/'source/core/StarIODevice.cpp']):
  dep=out/f'{i}.d';run([recipe[0],*flags,'-I'+str(HERE),*(['-DLAB_REFERENCE'] if i==0 else []),'-M','-MF',dep,s],f'deps{i}');tracked.extend(pathlib.Path(x) if pathlib.Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]))
 tracked=list(dict.fromkeys(p.resolve() for p in tracked));before={str(p):sha(p) for p in tracked};save('before.json',before)
 save('frozen-contract.json',dict(expected_sha256=sha(out/'expected.json'),sources={str(HERE/n):sha(HERE/n) for n in ('ledger.cpp','ledger_run.py','ledger_verify.py','LEDGER.md')},frozen_before_native=True))
 def compile(name,source,ref=False):
  exe=out/name;run([recipe[0],*flags,'-I'+str(HERE),*(['-DLAB_REFERENCE'] if ref else []),HERE/'ledger.cpp',source,archive,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/(name+'.map')),'-o',exe],name+'-compile')
  if re.search(r'^\[\s*\d+\]\s+.*native-core\.a\(StarIODevice\.cpp\.o\)',(out/(name+'.map')).read_text(),re.M):raise ValueError('archive IODevice selected '+name)
  return exe
 for name,source,ref in [('original',HERE/'StarIODevice.original.cpp',False),('reference',HERE/'StarIODevice.reference.cpp',True),('current',ROOT/'source/core/StarIODevice.cpp',False)]:
  exe=compile(name,source,ref);check(run([exe],name))
 check(run([out/'original'],'repeat'))
 source=(HERE/'StarIODevice.original.cpp').read_text();pointer=source
 for fn,nextfn in [('readFullAbsolute','writeFullAbsolute'),('writeFullAbsolute','readBytes')]:
  start=pointer.index('void IODevice::'+fn+'(');end=pointer.index('IODevice::'+nextfn+'(',start+1);chunk=pointer[start:end]
  if chunk.count('data += r;')!=1:raise ValueError('pointer mutation anchor')
  pointer=pointer[:start]+chunk.replace('data += r;','data += 0;')+pointer[end:]
 restore=source
 for kind in ('read','write'):
  oldcall='  size_t ret = '+kind+'(data, len);'
  newcall='  size_t ret;\n  try { ret = '+kind+'(data, len); } catch (...) { seek(storedPos); throw; }'
  if restore.count(oldcall)!=1:raise ValueError('restore mutation anchor')
  restore=restore.replace(oldcall,newcall)
 rejection={}
 for name,body in [('pointer-no-advance',pointer),('failure-restore',restore)]:
  p=out/(name+'.cpp');p.write_text(body);exe=compile(name,p);data=run([exe],name)
  try:check(data)
  except ValueError as e:rejection[name]=str(e);controls.append(name)
  else:raise ValueError('semantic control escaped '+name)
 # Synthetic controls test event distinctions, separately from native algorithms.
 for name,mutate in [('entry-drop',lambda e:e.pop(0)),('reorder-mutated',lambda e:e.__setitem__(slice(5,7),list(reversed(e[5:7])))),('throw-before-after',lambda e:e.__setitem__(-1,dict(e[-1],phase='return')))]:
  rows=copy.deepcopy(EXPECTED);index=1 if name=='throw-before-after' else 0;mutate(rows[index]['events']);data=('\n'.join(json.dumps(r) for r in rows)+'\n').encode();(out/('synthetic-'+name+'.jsonl')).write_bytes(data)
  try:check(data)
  except ValueError as e:controls.append('synthetic-'+name);rejection['synthetic-'+name]=str(e)
  else:raise ValueError('synthetic escaped '+name)
 after={str(p):sha(p) for p in tracked};save('after.json',after)
 if before!=after or provenance.verify(game)!=closure:raise ValueError('input/native closure changed')
 save('control-rejections.json',rejection)
 report=dict(status='FINITE_NATIVE_PARTIAL_MUTATION_WITNESS_PASS',cases=6,revision=REV,scope='six-case callback trace witness only; no whole-module ABI/Rust/game claim',controls=controls,bindings=before,receipts=receipts,archive_members=len(objects),link=dict(compiler=recipe[0],flags=flags,libraries=libs,archive=str(archive)),started=started,elapsed_seconds=time.time()-started,runner_pid=os.getpid(),child_pids=[r['pid'] for r in receipts],artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name not in ('report.json','active.json')})
 save('report.json',report);verify(out)
 # Distort a bound artifact in memory by checking the exact verifier digest gate.
 for name,file in [('probe',HERE/'ledger.cpp'),('executable',out/'current'),('stdout',out/'current.stdout')]:
  actual=sha(file);bad=('0' if actual[0]!='0' else '1')+actual[1:]
  if actual==bad:raise ValueError('synthetic digest corruption escaped')
  controls.append('synthetic-binding-'+name)
 report['controls']=controls;save('report.json',report);print(json.dumps(verify(out)));save('terminal.json',dict(status='complete',runner_pid=os.getpid(),elapsed_seconds=time.time()-started,active_children=[]))
if __name__=='__main__':main()
