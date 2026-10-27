"""Owned command receipts; identity is durable before products are inspected."""
import hashlib,json,os,signal,stat,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=ROOT/'build/ttl-rust-parity-r1'
sys.path[:0]=[str(HERE.parent),str(HERE.parent/'path-embed-replay'),str(HERE.parent/'ttl-cache'),str(HERE.parent/'behavior')]
import native_evidence_json as codec
import sdk_witness

def need(value,message):
 if not value:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,data):
 with Path(path).open('xb') as stream:stream.write(data)
def dump(path,value):write(path,codec.dumps(value).encode('ascii'))
def load(path):return codec.loads(Path(path).read_text('ascii'))
def hashes(paths):return {str(p):sha(p) for p in sorted(set(map(Path,paths))) if p.is_file()}
def same(a,b,message):need(codec.dumps(a)==codec.dumps(b),message)
def witness(path):
 canonical,hops=sdk_witness._resolve(str(path));return {'requested':str(path),'canonical':canonical,'hops':hops,**sdk_witness._digest(canonical)}
def environment():
 return {'PATH':'/usr/bin:/bin:/usr/sbin:/sbin:/Users/bdsqqq/.rustup/toolchains/stable-aarch64-apple-darwin/bin','HOME':str(OUT/'home'),'TMPDIR':str(OUT/'tmp'),'LANG':'C','LC_ALL':'C','VCPKG_ROOT':'/Users/bdsqqq/.cache/openstarbound-vcpkg','CARGO_NET_OFFLINE':'true'}
def group_exists(pgid):
 try:os.killpg(pgid,0);return True
 except ProcessLookupError:return False

def command(name,argv,stdin=b'',timeout=120,cwd=None):
 argv=list(map(str,argv));prefix=OUT/name;cwd=str(cwd or ROOT)
 before=witness(argv[0]);started=time.time_ns();env=environment()
 write(str(prefix)+'.stdin',stdin)
 dump(str(prefix)+'.plan',{'argv':argv,'cwd':cwd,'env':env,'stdin':hashlib.sha256(stdin).hexdigest(),'timeout_seconds':timeout,'tool':before,'cleanup':'SIGKILL owned process group on timeout or lingering descendant'})
 p=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
 dump(str(prefix)+'.started',{'pid':p.pid,'pgid':os.getpgid(p.pid),'started_ns':started})
 timed_out=False
 try:stdout,stderr=p.communicate(stdin,timeout=timeout)
 except subprocess.TimeoutExpired:
  timed_out=True;os.killpg(p.pid,signal.SIGKILL);stdout,stderr=p.communicate(timeout=10)
 cleanup=group_exists(p.pid)
 if cleanup:os.killpg(p.pid,signal.SIGKILL)
 gone=not group_exists(p.pid)
 write(str(prefix)+'.stdout',stdout);write(str(prefix)+'.stderr',stderr)
 receipt={'argv':argv,'cwd':cwd,'env':env,'pid':p.pid,'pgid':p.pid,'status':p.returncode,'status_kind':'normal' if p.returncode>=0 else 'signal','timed_out':timed_out,'cleanup_sent':cleanup,'owned_group_gone':gone,'timeout_seconds':timeout,'started_ns':started,'ended_ns':time.time_ns(),'stdin':sha(str(prefix)+'.stdin'),'stdout':sha(str(prefix)+'.stdout'),'stderr':sha(str(prefix)+'.stderr'),'tool_before':before,'tool_after':witness(argv[0])}
 dump(str(prefix)+'.receipt',receipt)
 need(not timed_out and type(p.returncode)is int and p.returncode==0 and gone,'command failed '+name)
 same(before,receipt['tool_after'],'tool changed '+name)
 return stdout,stderr

def verify_commands(report,data):
 for path in sorted(OUT.glob('*.receipt')):
  row=codec.loads(data(path).decode('ascii'));base=str(path)[:-8]
  plan=codec.loads(data(base+'.plan').decode('ascii'));start=codec.loads(data(base+'.started').decode('ascii'))
  need(type(row['status'])is int and row['status']==0 and row['status_kind']=='normal' and row['timed_out']is False and row['owned_group_gone']is True,'strict command status')
  for obj in (row,start):
   need(type(obj['pid'])is int and type(obj['pgid'])is int and obj['pid']>0 and obj['pid']==obj['pgid'],'typed owned group')
  same((row['pid'],row['pgid'],row['started_ns']),(start['pid'],start['pgid'],start['started_ns']),'started identity')
  need(type(row['started_ns'])is int and type(row['ended_ns'])is int and row['ended_ns']>=row['started_ns'],'timestamps')
  for key in ('argv','cwd','env','timeout_seconds'):same(row[key],plan[key],'command plan '+key)
  same(row['tool_before'],row['tool_after'],'tool stability');same(row['tool_before'],witness(row['argv'][0]),'live tool')
  for ext in ('stdin','stdout','stderr'):need(hashlib.sha256(data(base+'.'+ext)).hexdigest()==row[ext],'stdio bytes')
