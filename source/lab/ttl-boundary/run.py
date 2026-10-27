#!/usr/bin/env python3
"""Bounded one-executable native calibration. No closed acquisition runner imports."""
import hashlib,json,os,re,shlex,signal,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];OUT=ROOT/'build/ttl-boundary-r1'
FROZEN=HERE.parent/'ttl-cache'
sys.path.insert(0,str(FROZEN));import model
sys.path.insert(0,str(HERE.parent/'path-embed-replay'));import sdk_witness
SDK='/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj):Path(p).write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n')
def need(b,msg):
 if not b:raise AssertionError(msg)
def witness(p):
 p=Path(p);r=p.resolve();s=r.stat();return {'requested':str(p),'resolved':str(r),'sha256':sha(r),'size':s.st_size}
def command(name,args,stdin=b'',timeout=90,cwd=ROOT,expected=0):
 prefix=OUT/name;args=list(map(str,args));env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(OUT/'home'),'TMPDIR':str(OUT/'tmp'),'LANG':'C','LC_ALL':'C'}
 tool=witness(args[0]);start=time.time_ns();(OUT/(name+'.stdin')).write_bytes(stdin)
 dump(str(prefix)+'.plan.json',{'argv':args,'cwd':str(cwd),'env':env,'tool':tool,'stdin_sha256':hashlib.sha256(stdin).hexdigest(),'timeout':timeout,'expected':expected})
 p=subprocess.Popen(args,cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
 dump(str(prefix)+'.started.json',{'pid':p.pid,'pgid':os.getpgid(p.pid),'started_ns':start})
 timed=False
 try:o,e=p.communicate(stdin,timeout=timeout)
 except subprocess.TimeoutExpired:timed=True;os.killpg(p.pid,signal.SIGKILL);o,e=p.communicate(timeout=10)
 try:os.killpg(p.pid,0);alive=True
 except ProcessLookupError:alive=False
 if alive:os.killpg(p.pid,signal.SIGKILL)
 (OUT/(name+'.stdout')).write_bytes(o);(OUT/(name+'.stderr')).write_bytes(e)
 dump(str(prefix)+'.receipt.json',{'pid':p.pid,'pgid':p.pid,'started_ns':start,'ended_ns':time.time_ns(),'argv':args,'returncode':p.returncode,'timed_out':timed,'group_gone':not alive,'stdout_sha256':hashlib.sha256(o).hexdigest(),'stderr_sha256':hashlib.sha256(e).hexdigest(),'tool_before':tool,'tool_after':witness(args[0])})
 print(name,'pid',p.pid,'exit',p.returncode,flush=True)
 need(not timed and not alive and p.returncode==expected,'command '+name)
 return o

def recipe():
 cm=ROOT/'build/behavior/lru-cache-combined-r1/reference/cmake';db=json.loads((cm/'compile_commands.json').read_text());lines=(cm/'build.ninja').read_text().splitlines()
 pos=next(i for i,l in enumerate(lines) if l.startswith('build ') and '/bin/starbound:' in l)
 objects=[str(cm/x) for x in shlex.split(lines[pos].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/'))]
 need(len(objects)==len(set(objects))==113,'canonical 113 object closure')
 row=next(r for r in db if r['file']==str(ROOT/'source/core/StarJsonBuilder.cpp'));args=shlex.split(row['command']);flags=[];skip=False
 for t in args[1:]:
  if skip:skip=False;continue
  if t=='-o':skip=True
  elif t not in ('-c',row['file']):flags.append(t)
 libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[pos+1:pos+18] if x.startswith('  LINK_LIBRARIES = ')))
 libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
 selectors=re.findall(r'^(STAR_USE_RUST[^:]*):BOOL=(.*)$',(cm/'CMakeCache.txt').read_text(),re.M)
 need(len(selectors)==26 and all(v=='OFF' for _,v in selectors),'26 selectors default OFF')
 need(len(db)==472 and not any('-DSTAR_USE_RUST' in x['command'] for x in db),'reference configured profile')
 need('-O3' in flags and '-ffast-math' in flags,'unchanged profile')
 return {'cm':str(cm),'compiler':args[0],'flags':flags,'objects':objects,'libraries':libs,'selectors':selectors}

def main():
 OUT.mkdir(exist_ok=True);(OUT/'home').mkdir(exist_ok=True);(OUT/'tmp').mkdir(exist_ok=True)
 need(not (OUT/'report.json').exists(),'do not overwrite accepted run')
 header=ROOT/'source/core/StarTtlCache.hpp';frozen=FROZEN/'StarTtlCache.original.hpp'
 need(frozen.read_bytes()==header.read_bytes(),'original header EXACT bytes')
 r=recipe();dump(OUT/'recipe.json',r);c=r['compiler'];flags=r['flags'];cm=Path(r['cm']);src=HERE/'native.cpp'
 sdk=flags[flags.index('-isysroot')+1];sdk_before=sdk_witness.capture(sdk,SDK);dump(OUT/'sdk-before.json',sdk_before)
 command('compiler-version',[c,'--version'])
 command('sdk-version',['/usr/bin/xcrun','--show-sdk-version'])
 command('platform',['/usr/bin/sw_vers'])
 command('uname',['/usr/bin/uname','-a'])
 command('deps',[c,*flags,'-I'+str(HERE),'-M','-MT','native.o','-MF',OUT/'native.d',src],cwd=cm)
 deptext=(OUT/'native.d').read_text().replace('\\\n',' ');deps=shlex.split(deptext.split(':',1)[1])
 files=set(map(Path,deps));files.update(map(Path,r['objects']));files.update(Path(x) for x in r['libraries'] if Path(x).is_absolute() and Path(x).is_file())
 files.update([p for p in HERE.glob('*') if p.is_file()]);files.update(p for p in FROZEN.glob('*') if p.is_file());files.add(ROOT/'build/ttl-cache-native-r1/report.json');files.add(ROOT/'build/ttl-cache-native-r1/lifecycle.stdout');files.update([Path(sdk_witness.__file__),cm/'CMakeCache.txt',cm/'build.ninja',cm/'compile_commands.json',Path(c).resolve()])
 before={str(p):sha(p) for p in sorted(files)};dump(OUT/'inputs.json',before)
 command('compile',[c,*flags,'-I'+str(HERE),'-c',src,'-o',OUT/'native.o'],cwd=cm)
 link=[c,*flags,*r['objects'],OUT/'native.o',*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(OUT/'native.map'),'-Wl,-t,-trace_implicit_libraries','-o',OUT/'native']
 command('link-expand',[c,'-###',*link[1:]],cwd=cm)
 command('link',link,cwd=cm)
 command('runtime',['/usr/bin/otool','-L',OUT/'native'])
 command('symbols',['/usr/bin/nm','-nm',OUT/'native'])
 command('c11',[c,'-x','c','-std=c11','-I'+str(ROOT/'source/core'),'-fsyntax-only',HERE/'c11.c'])
 command('lazy',[c,*flags,'-I'+str(HERE),'-fsyntax-only',HERE/'lazy.cpp'],cwd=cm)
 command('controls',[OUT/'native','controls'])
 command('real',[OUT/'native','real'])
 command('lifecycle',[OUT/'native','lifecycle'])
 sdk_after=sdk_witness.capture(sdk,SDK);dump(OUT/'sdk-after.json',sdk_after);need(sdk_before==sdk_after,'full SDK stable')
 paths=re.findall(r'^\[\s*\d+\] (.*\.tbd)$',(OUT/'native.map').read_text(errors='surrogateescape'),re.M)
 need(paths,'actual linker SDK interfaces')
 dump(OUT/'sdk-consumed.json',sdk_witness.reconcile_consumed(sdk_before,paths,requested_root=sdk,expected_canonical_root=SDK))
 rows=model.corpus();corpus=('\n'.join(rows)+'\n').encode();(OUT/'corpus.tsv').write_bytes(corpus);expected=model.expected(rows);(OUT/'expected.tsv').write_text(expected)
 checks={}
 for alias in ('ordered','hash'):
  for repeat in range(2):
   actual=command(f'{alias}-{repeat}',[OUT/'native',alias],corpus).decode()
   if actual!=expected:
    aa=actual.splitlines();ee=expected.splitlines();bad=[{'row':i,'input':rows[i] if i<len(rows) else None,'expected':y,'actual':x} for i,(x,y) in enumerate(zip(aa,ee)) if x!=y]
    dump(OUT/f'{alias}-{repeat}-mismatch.json',{'actual_rows':len(aa),'expected_rows':len(ee),'mismatches':bad});raise AssertionError('native/model mismatch '+alias)
   checks[f'{alias}-{repeat}']=len(rows)
 need(before=={str(p):sha(p) for p in sorted(files)},'source/object/SDK inputs stable')
 sys.path.insert(0,str(HERE));import verify
 semantic=verify.semantic_replay();dump(OUT/'semantic.json',semantic)
 total=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file());need(total<=96*1024*1024,'96MiB output cap')
 report={'status':'PASS finite native boundary + mock only; Rust/production integration NOT implemented','rows':len(rows),'checks':checks,'header_sha256':sha(header),'binary':witness(OUT/'native'),'source':{str(p):sha(p) for p in HERE.glob('*') if p.is_file()},'inputs':len(before),'output_bytes':total,'processes':len(list(OUT.glob('*.receipt.json'))),'canonical_header_sha256':sha(ROOT/'source/core/StarRustTtlCache.h'),'meaning':'ALL aliases select boundary + mock. Real mode actual Time/Random; ordered/hash scripted proxies. No Rust/game qualification.'}
 report['semantic']=semantic
 report['products']={str(p):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name not in ('report.json','acquisition.log')}
 dump(OUT/'report.json',report);print('FINITE_NATIVE_PASS',len(rows),'rows x4;',semantic['native_lifecycle_properties'],'properties;',len(semantic['controls']),'controls; report SHA',sha(OUT/'report.json'))
if __name__=='__main__':main()
