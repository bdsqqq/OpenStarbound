#!/usr/bin/env python3
"""Fresh typed-frame C++ acquisition; reuse the pinned single Rust aggregate.
Historical source bytes resolve ONLY through an explicit pre-edit manifest.
"""
import datetime as dt,hashlib,json,os,shlex,signal,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;R=H.parents[2];S=R/'build/weighted-pool-inline-r1';O=S/'acquisition';OLD=R/'build/weighted-pool-rust-bridge-r1';DEADLINE=dt.datetime(2026,10,28,0,43,tzinfo=dt.timezone.utc).timestamp();CERT='039d8ad74ff29512fb9069a18c15a4277906ef10c98810e98c8558e4a1759a42';VERSIONS='673098af777f77e3687f611b4407b6a45ea2880c1433c2367b72f3443ca6eb50'
sys.path[:0]=[str(H),str(H.parent),str(H.parent/'ttl-production'),str(H.parent/'path-embed-replay'),str(H.parent/'weighted-pool')]
from game_syntax import closure,unchanged,subset
import rust_bridge,archive_identity,expanded_invocation,object_inventory,link_trace,native_symbols,native_evidence_json as codec,sdk_witness,model

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
 need(sha(OLD/'certificate.typed')==CERT,'original externally pinned certificate');cert=typed(OLD/'certificate.typed');need(cert['verifierSha256']==sha(H/'rust_qualify.py'),'immutable original qualifier');need(sha(S/'source-versions.json')==VERSIONS,'pre-edit source versions');version=load(S/'source-versions.json');need(version['originalCertificateSha256']==CERT,'exact source version authority');copies={}
 for row in version['sources']:
  p=Path(row['path']);copy=Path(row['copy']);need(p.parent==H and copy.parent==S/'before'and copy.name==p.name,'source-only exact retention');need(sha(copy)==row['sha256']and copy.stat().st_size==row['size'],'old source bytes');copies[str(p)]=row
 for p,h in cert['products'].items():need(sha(p)==h,'immutable old acquisition product '+p)
 ad=load(OLD/'admission.json')
 for p,h in ad['witness']['files'].items():need(sha(copies[p]['copy']if p in copies else p)==h,'historical closure (no tool substitution) '+p)
 for p,target in ad['witness']['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'historical aliases unchanged')
 canonical=load(OLD/'canonical.json');archive=Path(canonical['archive']);need(sha(archive)==canonical['sha256'],'same qualified canonical archive');need(codec.dumps(rust_bridge.physical(archive))==codec.dumps(typed(OLD/'canonical-providers.typed')),'physical canonical exports unchanged')
 return dict(status='EXACT_HISTORICAL_BYTES_RETAINED; old source-live/inode replay unavailable',certificateSha256=CERT,sourceVersionsSha256=VERSIONS,sourceCopies=len(copies),originalBindings=len(ad['witness']['files']),canonical=canonical),ad

def budget():need(sum(p.stat().st_size for p in S.rglob('*')if p.is_file())<=128*1024**2,'128MiB typed-frame stage cap')
def command(name,argv,w,env,expected=0,stdin=b''):
 unchanged(w);need(time.time()<DEADLINE-1,'deadline');argv=list(map(str,argv));(O/(name+'.stdin')).write_bytes(stdin);dump(O/(name+'.plan.json'),dict(argv=argv,env=env,cwd=str(R),expected=expected,admissionSha256=sha(O/'admission.json'),stdinSha256=sha(O/(name+'.stdin'))));started=time.time_ns();p=subprocess.Popen(argv,cwd=R,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);probe=subprocess.run(['/bin/ps','-p',str(p.pid),'-o','lstart=,pid=,pgid='],capture_output=True,timeout=5).stdout.decode().strip();dump(O/(name+'.started.json'),dict(pid=p.pid,pgid=os.getpgid(p.pid),osStart=probe,startedWallNs=started));timed=False
 try:out,err=p.communicate(stdin,timeout=min(90,DEADLINE-time.time()))
 except subprocess.TimeoutExpired:timed=True;os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate(timeout=5)
 try:os.killpg(p.pid,0);gone=False;os.killpg(p.pid,signal.SIGKILL)
 except ProcessLookupError:gone=True
 (O/(name+'.stdout')).write_bytes(out);(O/(name+'.stderr')).write_bytes(err);dump(O/(name+'.receipt.json'),dict(pid=p.pid,pgid=p.pid,returncode=p.returncode,reaped=True,groupGone=gone,timedOut=timed,startedWallNs=started,endedWallNs=time.time_ns(),planSha256=sha(O/(name+'.plan.json')),stdoutSha256=sha(O/(name+'.stdout')),stderrSha256=sha(O/(name+'.stderr'))));need(gone and not timed and p.returncode==expected,'actual leaf '+name);unchanged(w);budget();print(name,p.pid,p.returncode,flush=True)
def main():
 O.mkdir();(O/'home').mkdir();(O/'tmp').mkdir();history,old=retained();dump(O/'historical-retention.json',history);recipe=old['recipe'];archive=Path(old['archive']);c=recipe['compiler'];baseflags=[*recipe['flags'],'-DWP_BOUNDARY_ON=1','-I'+str(H),'-I'+str(H.parent/'weighted-pool')];env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin',HOME=str(O/'home'),TMPDIR=str(O/'tmp'),LANG='C',LC_ALL='C');roots=[R/'source/core',R/'source/extern',H,H.parent/'weighted-pool',H.parent/'path-embed-replay',H.parent/'ttl-production',S/'before',Path(c).parent.parent/'lib/clang']
 for i,x in enumerate(recipe['flags']):
  if x in('-isystem','-isysroot'):roots.append(Path(recipe['flags'][i+1]))
  elif x.startswith('-I'):roots.append(Path(x[2:]))
 w=closure(roots)
 for p in [*old['tools'].values(),*recipe['objects'],*[x for x in recipe['libraries']if x.startswith('/')],str(archive),str(OLD/'certificate.typed'),str(S/'source-versions.json'),str(H.parent/'native_symbols.py'),str(H.parent/'native_artifacts.py'),str(H.parent/'native_evidence_json.py')]:
  p=Path(p);w['files'][str(p.resolve())]=sha(p)
 dump(O/'admission.json',dict(witness=w,recipe=recipe,baseflags=baseflags,env=env,tools=old['tools'],archive=str(archive),archiveSha256=sha(archive),sourceVersionsSha256=VERSIONS,oldCertificateSha256=CERT,stageBytesCap=128*1024**2,deadline=DEADLINE,purpose='fresh inline native frames, no Cargo or production changes'))
 specs=[('combined',H/'combined.cpp',['-DWP_BOUNDARY_ATTACKS=0']),('combined-mock',H/'combined.cpp',['-DWP_BOUNDARY_ATTACKS=1']),('mock',H/'mock.cpp',[]),('allocation',H/'allocation.cpp',[]),('allocation-legacy',H/'allocation.cpp',['-DWP_ALLOCATION_HEADER="'+str(S/'before/BoundaryWeightedPool.hpp')+'"'])]
 for name,src,extra in specs:
  obj=O/(name+'.o');dep=O/(name+'.d');command('compile-'+name,[c,*baseflags,*extra,'-MD','-MF',dep,'-c',src,'-o',obj],w,env);subset(shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]),w);w['files'][str(obj)]=sha(obj)
 for name in ['combined','allocation','allocation-legacy','combined-mock']:
  objects=[O/(name+'.o')]+([O/'mock.o']if name=='combined-mock'else[]);link=[c,*baseflags,*recipe['objects'],*objects,*([]if name=='combined-mock'else[archive]),*recipe['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(O/(name+'.map')),'-Wl,-t,-trace_implicit_libraries','-o',O/name]
  command('expand-'+name,[c,'-###',*link[1:]],w,env);cmds=[shlex.split(s)for s in(O/('expand-'+name+'.stderr')).read_text().splitlines()if s.lstrip().startswith('"')];need(len(cmds)==1,'one selected ld');bound=expanded_invocation.bind(cmds[0]);need(bound['inventory']['tool']==old['tools']['CMAKE_LINKER'],'preselected ld');subset(bound['inventory']['file_inputs'],w);dump_typed(O/(name+'-expanded.typed'),bound);command('link-'+name,link,w,env);expanded_invocation.verify(bound,cmds[0]);w['files'][str(O/name)]=sha(O/name)
 command('disassemble',['/usr/bin/otool','-tvV',O/'combined'],w,env);command('current',[O/'combined'],w,env);rows,want=model.corpus();command('corpus',[O/'combined','corpus'],w,env,stdin=rows.encode());need((O/'corpus.stdout').read_text()==want,'unchanged rational corpus');need((O/'current.stdout').read_bytes()==(OLD/'current.stdout').read_bytes(),'all previous actual-Rust native assertions unchanged');command('allocation-current',[O/'allocation'],w,env);command('allocation-old-known-failure',[O/'allocation-legacy'],w,env,expected=1);need((O/'allocation-old-known-failure.stderr').read_text()=='FAIL\tboundary empty-container construction allocated native C++ storage\n','old allocating prototype fails honestly');command('mock-current',[O/'combined-mock'],w,env);need(b'PASS\tactual-frame-bounds-and-cursor-state-attacks\t5382\n'in(O/'mock-current.stdout').read_bytes(),'same actual capability rejection coverage');budget();dump(O/'report.json',dict(status='FINITE_TYPED_FRAME_ACTUAL_RUST_ACQUIRED; independent replay required',historicalRetentionSha256=sha(O/'historical-retention.json'),admissionSha256=sha(O/'admission.json'),products={str(p):sha(p)for p in O.rglob('*')if p.is_file()and p.name not in ['report.json']}));print('REPORT',sha(O/'report.json'))
if __name__=='__main__':main()
