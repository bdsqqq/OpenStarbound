#!/usr/bin/env python3
"""Default-OFF no-Rust-link runtime + current client native/cumulative syntax.
No Cargo, game execution, replacement pair, or archive mutation.
"""
import datetime as dt,hashlib,json,os,re,shlex,signal,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;R=H.parents[2];S=R/'build/weighted-pool-scene-r1';O=S/'native';DEADLINE=dt.datetime(2026,10,28,1,35,tzinfo=dt.timezone.utc).timestamp();sys.path[:0]=[str(H.parent),str(H.parent/'ttl-production'),str(H.parent/'path-embed-replay')]
from game_syntax import closure,unchanged,subset
import expanded_invocation,archive_identity,object_inventory,link_trace,native_symbols,sdk_witness,native_evidence_json as codec

def need(b,s):
 if not b:raise ValueError(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def dump(p,v):
 with Path(p).open('x')as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def dump_typed(p,v):
 with Path(p).open('x')as f:f.write(codec.dumps(v));f.write('\n');f.flush();os.fsync(f.fileno())
def budget():need(sum(p.stat().st_size for p in S.rglob('*')if p.is_file())<=128*1024**2,'128MiB scene-stage cap')
def command(name,argv,w,env):
 unchanged(w);need(time.time()<DEADLINE-1,'deadline');argv=list(map(str,argv));dump(O/(name+'.plan.json'),dict(argv=argv,env=env,cwd=str(R),admissionSha256=sha(O/'admission.json')));start=time.time_ns();p=subprocess.Popen(argv,cwd=R,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);probe=subprocess.run(['/bin/ps','-p',str(p.pid),'-o','lstart=,pid=,pgid='],capture_output=True,timeout=5).stdout.decode().strip();dump(O/(name+'.started.json'),dict(pid=p.pid,pgid=os.getpgid(p.pid),osStart=probe,startedWallNs=start));timed=False
 try:out,err=p.communicate(timeout=min(90,DEADLINE-time.time()))
 except subprocess.TimeoutExpired:timed=True;os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate(timeout=5)
 try:os.killpg(p.pid,0);gone=False;os.killpg(p.pid,signal.SIGKILL)
 except ProcessLookupError:gone=True
 (O/(name+'.stdout')).write_bytes(out);(O/(name+'.stderr')).write_bytes(err);dump(O/(name+'.receipt.json'),dict(pid=p.pid,pgid=p.pid,returncode=p.returncode,reaped=True,groupGone=gone,timedOut=timed,startedWallNs=start,endedWallNs=time.time_ns(),planSha256=sha(O/(name+'.plan.json')),stdoutSha256=sha(O/(name+'.stdout')),stderrSha256=sha(O/(name+'.stderr'))));need(p.returncode==0 and gone and not timed,'actual native leaf '+name);unchanged(w);budget();print(name,p.pid,p.returncode,flush=True)
def main():
 O.mkdir();(O/'home').mkdir();(O/'tmp').mkdir();base=load(R/'build/weighted-pool-rust-bridge-r1/admission.json');recipe=base['recipe'];c=recipe['compiler'];env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin',HOME=str(O/'home'),TMPDIR=str(O/'tmp'),LANG='C',LC_ALL='C');roots=[R/'source'/d for d in ['core','extern','game','base','client','frontend','rendering','windowing','application','platform']];roots.append(Path(c).parent.parent/'lib/clang');plans=[];selectors=set(re.findall(r'option\((STAR_USE_RUST_\w+)',(R/'source/CMakeLists.txt').read_text()));need(len(selectors)==28,'exact28 selectors')
 for backend in ['reference','candidate']:
  path=R/('build/behavior/ttl-cache-combined-r2/'+backend+'/cmake/compile_commands.json');rows=load(path);row=next(r for r in rows if Path(r['file']).name=='StarClientApplication.cpp');argv=shlex.split(row['command']);need(argv[0]==c,'same selected C++ compiler');need(not any('cmake_pch'in x for x in argv),'PCH already disabled in admitted native profile');i=argv.index('-o');del argv[i:i+2];argv[argv.index('-c')]='-fsyntax-only';
  if backend=='candidate':argv.append('-DSTAR_USE_RUST_WEIGHTED_POOL')
  enabled={x[2:]for x in argv if x.startswith('-DSTAR_USE_RUST_')};need(enabled==(selectors-{'STAR_USE_RUST_LINE_QUERY'}if backend=='candidate'else set()),'actual28OFF/27ONexceptLINE flag vector');argv+=['-MD','-MF',str(O/(backend+'.d'))];plans.append(dict(name=backend,argv=argv,originalCompileCommand=row,flagsSource=str(path),flagsSourceSha256=sha(path)))
 for argv in [recipe['flags'],*[p['argv']for p in plans]]:
  for i,x in enumerate(argv):
   if x in('-isystem','-isysroot'):roots.append(Path(argv[i+1]))
   elif x.startswith('-I'):roots.append(Path(x[2:]))
 w=closure(roots)
 for p,h in base['witness']['files'].items():
  if p.startswith('/Applications/Xcode.app/'):need(sha(p)==h,'same driver support');w['files'][str(Path(p).resolve())]=h
 for p in [*base['tools'].values(),*recipe['objects'],*[x for x in recipe['libraries']if x.startswith('/')],str(H/'native_link.cpp'),str(Path(__file__).resolve()),str(R/'source/CMakeLists.txt'),str(S/'source-versions.json'),*[p['flagsSource']for p in plans]]:p=Path(p);w['files'][str(p.resolve())]=sha(p)
 dump(O/'admission.json',dict(witness=w,recipe=recipe,tools=base['tools'],env=env,plans=plans,sourceVersionsSha256=sha(S/'source-versions.json'),deadline=DEADLINE,stageCapBytes=128*1024**2,scope='no-Rust-link native production execution; current client syntax only'))
 for plan in plans:
  command('syntax-'+plan['name'],plan['argv'],w,env);subset(shlex.split((O/(plan['name']+'.d')).read_text().replace('\\\n',' ').split(':',1)[1]),w)
 obj=O/'native-link.o';dep=O/'native-link.d';command('compile',[c,*recipe['flags'],'-MD','-MF',dep,'-c',H/'native_link.cpp','-o',obj],w,env);subset(shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]),w);w['files'][str(obj)]=sha(obj);link=[c,*recipe['flags'],*recipe['objects'],obj,*recipe['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(O/'native-link.map'),'-Wl,-t,-trace_implicit_libraries','-o',O/'native-link'];command('expand',[c,'-###',*link[1:]],w,env);cmds=[shlex.split(s)for s in(O/'expand.stderr').read_text().splitlines()if s.lstrip().startswith('"')];need(len(cmds)==1,'single expanded linker');bound=expanded_invocation.bind(cmds[0]);subset(bound['inventory']['file_inputs'],w);need(not any('star_engine_ffi'in p or'/rust'in p for p in bound['inventory']['file_inputs']),'NO Rust archive');dump_typed(O/'expanded.typed',bound);command('link',link,w,env);expanded_invocation.verify(bound,cmds[0]);w['files'][str(O/'native-link')]=sha(O/'native-link');command('native-runtime',[O/'native-link'],w,env);need((O/'native-runtime.stdout').read_text()=='PASS\tactual-production-default-off-without-rust-link\n','actual native OFF result');symbols=native_symbols.live_symbols((O/'native-link.map').read_bytes());need(not any(s.name in [b'_sb_wp_run',b'_sb_wp_count',b'_rust_eh_personality']for s in symbols),'no linked Rust/WeightedPool exports');budget();dump(O/'report.json',dict(status='NATIVE_DEFAULT_OFF_NO_RUST_LINK_RUNTIME_AND_CURRENT_CLIENT_TWO_PROFILES_SYNTAX_PASS',admissionSha256=sha(O/'admission.json'),products={str(p):sha(p)for p in O.rglob('*')if p.is_file()and p.name!='report.json'}));print('REPORT',sha(O/'report.json'))
if __name__=='__main__':main()
