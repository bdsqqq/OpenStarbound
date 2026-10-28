#!/usr/bin/env python3
"""Fresh DEFAULT-OFF / ON production-header execution, not a game build."""
import datetime as dt,hashlib,json,os,re,shlex,signal,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;R=H.parents[2];S=R/'build/weighted-pool-production-r1';O=S/'acquisition';BOUNDARY=H.parent/'weighted-pool-boundary';INLINE=R/'build/weighted-pool-inline-r1/acquisition';RUST=R/'build/weighted-pool-rust-bridge-r1';DEADLINE=dt.datetime(2026,10,28,1,11,tzinfo=dt.timezone.utc).timestamp();INLINE_PIN='05858f2e19bfb8392bf8ad2a4dfe7803a5c006fcc3bf5fa55a2ab73cbbc06cb3';PROD_VERSIONS='5acdf9a85dbe2110d551341b7bfe6c6390cc0309221ebdeada0719ffb3dcd8bb';INLINE_VERSIONS='673098af777f77e3687f611b4407b6a45ea2880c1433c2367b72f3443ca6eb50'
sys.path[:0]=[str(BOUNDARY),str(H.parent),str(H.parent/'ttl-production'),str(H.parent/'path-embed-replay'),str(H.parent/'weighted-pool')]
from game_syntax import closure,unchanged,subset
import rust_bridge,native_evidence_json as codec,expanded_invocation,archive_identity,model

def need(b,s):
 if not b:raise ValueError(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def typed(p):return codec.loads(Path(p).read_text('ascii'))
def dump(p,v):
 with Path(p).open('x')as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def dump_typed(p,v):
 with Path(p).open('x')as f:f.write(codec.dumps(v));f.write('\n');f.flush();os.fsync(f.fileno())
def retained():
 need(sha(INLINE/'certificate.typed')==INLINE_PIN,'qualified inline epoch');certificate=typed(INLINE/'certificate.typed');need(certificate['verifierSha256']==sha(BOUNDARY/'inline_verify.py'),'unchanged prior qualifier');copies={}
 for manifest,pin in [(S/'source-versions.json',PROD_VERSIONS),(INLINE.parent/'source-versions.json',INLINE_VERSIONS)]:
  need(sha(manifest)==pin,'pre-edit explicit source versions')
  for row in load(manifest)['sources']:
   p=Path(row['path']);copy=Path(row['copy']);need((str(p).startswith(str(R/'source')+'/')or p==R/'scripts/build-behavior-lab.sh')and copy.parent==manifest.parent/'before','SOURCE-ONLY retention, never tools');need(sha(copy)==row['sha256']and copy.stat().st_size==row['size'],'exact retained source bytes');copies.setdefault(str(p),{})[row['sha256']]=str(copy)
 for p,h in certificate['products'].items():need(sha(p)==h,'prior immutable inline artifact '+p)
 resolved=[]
 for epoch in [RUST,INLINE]:
  ad=load(epoch/'admission.json')
  for p,h in ad['witness']['files'].items():
   if sha(p)==h:continue
   copy=copies.get(p,{}).get(h);need(copy is not None and sha(copy)==h,'no rebinding missing historical source '+p);resolved.append(dict(epoch=str(epoch),original=p,copy=copy,sha256=h))
  for p,target in ad['witness']['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'historical aliases, no tool replacement')
 archive=Path(load(RUST/'canonical.json')['archive']);need(sha(archive)==load(RUST/'canonical.json')['sha256'],'unchanged single Rust aggregate');need(codec.dumps(rust_bridge.physical(archive))==codec.dumps(typed(RUST/'canonical-providers.typed')),'unchanged physical Rust exports')
 return dict(status='EXACT_HISTORICAL_SOURCE_VERSIONS_AND_ARTIFACTS; old global live/inode replay unavailable',inlineCertificateSha256=INLINE_PIN,productionSourceVersionsSha256=PROD_VERSIONS,inlineSourceVersionsSha256=INLINE_VERSIONS,resolved=resolved,archive=str(archive),archiveSha256=sha(archive)),load(RUST/'admission.json')
def budget():need(sum(p.stat().st_size for p in S.rglob('*')if p.is_file())<=128*1024**2,'128MiB production lab cap')
def command(name,argv,w,env,stdin=b''):
 unchanged(w);need(time.time()<DEADLINE-1,'deadline');argv=list(map(str,argv));(O/(name+'.stdin')).write_bytes(stdin);dump(O/(name+'.plan.json'),dict(argv=argv,cwd=str(R),env=env,stdinSha256=sha(O/(name+'.stdin')),admissionSha256=sha(O/'admission.json')));start=time.time_ns();p=subprocess.Popen(argv,cwd=R,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);osstart=subprocess.run(['/bin/ps','-p',str(p.pid),'-o','lstart=,pid=,pgid='],capture_output=True,timeout=5).stdout.decode().strip();dump(O/(name+'.started.json'),dict(pid=p.pid,pgid=os.getpgid(p.pid),osStart=osstart,startedWallNs=start));timed=False
 try:out,err=p.communicate(stdin,timeout=min(90,DEADLINE-time.time()))
 except subprocess.TimeoutExpired:timed=True;os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate(timeout=5)
 try:os.killpg(p.pid,0);gone=False;os.killpg(p.pid,signal.SIGKILL)
 except ProcessLookupError:gone=True
 (O/(name+'.stdout')).write_bytes(out);(O/(name+'.stderr')).write_bytes(err);dump(O/(name+'.receipt.json'),dict(pid=p.pid,pgid=p.pid,returncode=p.returncode,reaped=True,groupGone=gone,timedOut=timed,startedWallNs=start,endedWallNs=time.time_ns(),planSha256=sha(O/(name+'.plan.json')),stdoutSha256=sha(O/(name+'.stdout')),stderrSha256=sha(O/(name+'.stderr'))));need(p.returncode==0 and gone and not timed,'actual production leaf '+name);unchanged(w);budget();print(name,p.pid,p.returncode,flush=True)
def main():
 O.mkdir();(O/'home').mkdir();(O/'tmp').mkdir();history,old=retained();dump(O/'historical-retention.json',history);recipe=old['recipe'];archive=Path(history['archive']);c=recipe['compiler'];cmake=old['tools']['CMAKE_EXECUTABLE'];flags=[*recipe['flags'],'-DWP_BOUNDARY_ATTACKS=0','-I'+str(H),'-I'+str(H.parent/'weighted-pool')];env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin',HOME=str(O/'home'),TMPDIR=str(O/'tmp'),LANG='C',LC_ALL='C')
 source=(R/'source/CMakeLists.txt').read_text();options=re.findall(r'^option\(STAR_USE_RUST_[^\n]+$',source,re.M);need(len(options)==28,'28 default-OFF selector definitions');aggregate=re.search(r'if\(STAR_USE_RUST_LIGHTING OR[^\n]+\)\n  include\(Rust\)\nendif\(\)',source).group();definition='if(STAR_USE_RUST_WEIGHTED_POOL)\n  add_compile_definitions(STAR_USE_RUST_WEIGHTED_POOL)\nendif()';need(definition in source,'production conditional definition')
 script='cmake_minimum_required(VERSION 3.20)\nset(aggregate OFF)\nset(observed_defs "")\nmacro(include module)\n if(NOT "${module}" STREQUAL "Rust")\n message(FATAL_ERROR "unexpected include")\n endif()\n set(aggregate ON)\nendmacro()\nmacro(add_compile_definitions)\n list(APPEND observed_defs ${ARGV})\nendmacro()\n'+'\n'.join(options)+'\n'+aggregate+'\n'+definition+'\nmessage("weighted=${STAR_USE_RUST_WEIGHTED_POOL};aggregate=${aggregate};definitions=${observed_defs}")\n';(O/'selector-contract.cmake').write_text(script)
 roots=[R/'source/core',R/'source/extern',H,BOUNDARY,H.parent/'weighted-pool',H.parent/'path-embed-replay',H.parent/'ttl-production',Path(c).parent.parent/'lib/clang']
 for i,x in enumerate(recipe['flags']):
  if x in('-isystem','-isysroot'):roots.append(Path(recipe['flags'][i+1]))
  elif x.startswith('-I'):roots.append(Path(x[2:]))
 w=closure(roots)
 for p,h in old['witness']['files'].items():
  if p.startswith('/Applications/Xcode.app/'):need(sha(p)==h,'selected driver support');w['files'][str(Path(p).resolve())]=h
 for p in [*old['tools'].values(),*recipe['objects'],*[x for x in recipe['libraries']if x.startswith('/')],str(archive),str(R/'source/CMakeLists.txt'),str(R/'scripts/build-behavior-lab.sh'),str(S/'source-versions.json'),str(O/'selector-contract.cmake'),str(H.parent/'native_symbols.py'),str(H.parent/'native_artifacts.py'),str(H.parent/'native_evidence_json.py')]:p=Path(p);w['files'][str(p.resolve())]=sha(p)
 dump(O/'admission.json',dict(witness=w,recipe=recipe,baseflags=flags,env=env,tools=old['tools'],archive=str(archive),archiveSha256=sha(archive),historySha256=sha(O/'historical-retention.json'),productionSourceVersionsSha256=PROD_VERSIONS,deadline=DEADLINE,stageCapBytes=128*1024**2,limits='CMake source-extracted selector GATE evaluation, not full project configure; two actual production-header runtime images, not game'))
 command('cmake-default',[cmake,'-P',O/'selector-contract.cmake'],w,env);command('cmake-on',[cmake,'-DSTAR_USE_RUST_WEIGHTED_POOL=ON','-P',O/'selector-contract.cmake'],w,env);need((O/'cmake-default.stderr').read_text()=='weighted=OFF;aggregate=OFF;definitions=\n','CMake actual default-OFF gate');need((O/'cmake-on.stderr').read_text()=='weighted=ON;aggregate=ON;definitions=STAR_USE_RUST_WEIGHTED_POOL\n','CMake actual ON gate')
 for backend in ['native','rust']:
  chosen=[*flags,*(['-DSTAR_USE_RUST_WEIGHTED_POOL','-DWP_BOUNDARY_ON=1']if backend=='rust'else['-DWP_BOUNDARY_ON=0'])];obj=O/(backend+'.o');dep=O/(backend+'.d');command(backend+'-compile',[c,*chosen,'-MD','-MF',dep,'-c',H/'combined.cpp','-o',obj],w,env);subset(shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]),w);w['files'][str(obj)]=sha(obj);link=[c,*chosen,*recipe['objects'],obj,archive,*recipe['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(O/(backend+'.map')),'-Wl,-t,-trace_implicit_libraries','-o',O/backend];command(backend+'-expand',[c,'-###',*link[1:]],w,env);cmds=[shlex.split(x)for x in(O/(backend+'-expand.stderr')).read_text().splitlines()if x.lstrip().startswith('"')];need(len(cmds)==1,'one expanded ld');bound=expanded_invocation.bind(cmds[0]);subset(bound['inventory']['file_inputs'],w);need(bound['inventory']['tool']==old['tools']['CMAKE_LINKER'],'selected ld');dump_typed(O/(backend+'-expanded.typed'),bound);command(backend+'-link',link,w,env);expanded_invocation.verify(bound,cmds[0]);w['files'][str(O/backend)]=sha(O/backend);command(backend+'-current',[O/backend],w,env);rows,want=model.corpus();command(backend+'-corpus',[O/backend,'corpus'],w,env,stdin=rows.encode());need((O/(backend+'-corpus.stdout')).read_text()==want,'original27row model '+backend)
 actual=(O/'rust-current.stdout').read_bytes();need(actual==(RUST/'current.stdout').read_bytes(),'actual production Rust matches original qualified assertions');native=(O/'native-current.stdout').read_bytes().replace(b'PASS\tnative-production-header-off-reference-layout-lazy-custom-containers\n',b'PASS\t19-root-4-stage-real-reference-layout-lazy-custom-containers\n');need(native==actual,'default-OFF production header agrees, label preserves no root counter claim');command('disassemble',['/usr/bin/otool','-tvV',O/'rust'],w,env);budget();dump(O/'report.json',dict(status='PRODUCTION_HEADER_DEFAULT_OFF_ON_ACQUIRED; independent replay pending; NO GAME/FULL_CONFIGURE CLAIM',admissionSha256=sha(O/'admission.json'),products={str(p):sha(p)for p in O.rglob('*')if p.is_file()and p.name!='report.json'}));print('REPORT',sha(O/'report.json'))
if __name__=='__main__':main()
