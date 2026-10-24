#!/usr/bin/env python3
"""Target-bound full semantic MWC oracle; packages existing real native objects only."""
import argparse,hashlib,json,os,re,shlex,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
SEEDS=[0,1,31415926,0xffffffff,0x100000000,0xffffffffffffffff,0x8000000000000000,0x123456789abcdef0,809430660]
MASK=(1<<32)-1
class Model:
 def __init__(self,seed):
  self.d=[seed&MASK,seed>>32]+[0]*254;self.c=seed%809430660;self.i=255
  for n in range(2,256):self.d[n]=(69069*self.d[n-2]+362437)&MASK
  for _ in range(32):self.next()
 def next(self):
  self.i=(self.i+1)%256;t=809430660*self.d[self.i]+self.c;self.c=t>>32;self.d[self.i]=t&MASK;return t&MASK
 def entropy(self,seed):
  seed^=(self.next()<<32)|self.next();self.c=(self.c^seed)%809430660;self.d[0]^=seed&MASK;self.d[1]^=((seed>>32)^seed)&MASK
  for n in range(2,256):self.d[n]^=(69069*self.d[n-2]+362437)&MASK
 def state(self):return self.d+[self.c,self.i]
def python_check(path):
 with path.open() as f:
  count=0
  def check(m):
   nonlocal count
   got=[int(x) for x in next(f).strip().split(',') if x]
   if got!=m.state():raise ValueError('independent Python semantic state mismatch '+str(count))
   count+=1
  for seed in SEEDS:
   m=Model(seed);check(m)
   for n in range(2200):
    if n%127==0:m.entropy((n*0x100000001)^seed)
    else:m.next()
    check(m)
   import copy
   fork=copy.deepcopy(m)
   for n in range(300):fork.next();fork.next();check(fork)
   check(Model(seed))
 return count
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--define',choices=['STAR_USE_RUST_RANDOM_MWC','STAR_USE_RUST_RANDOM_MWC=1']);p.add_argument('--archive',type=Path);p.add_argument('--reference-report',type=Path);a=p.parse_args()
 if bool(a.define)!=bool(a.archive):p.error('selector/archive must pair')
 if a.archive and a.archive.resolve()!=ROOT/'build/random-mwc-rust/target/release/libstar_engine_ffi.a':p.error('canonical owned archive required')
 if a.define and not a.reference_report:p.error('independent CPP report required')
 out=a.output.resolve()
 if not out.is_relative_to(ROOT/'build/random-mwc-lab') or out==ROOT/'build/random-mwc-lab':p.error('owned nested output required')
 out.mkdir(parents=True,exist_ok=True);negative=[]
 for ext in ['cpp','hpp']:
  raw=subprocess.check_output(['git','show','98a07508:source/core/StarRandom.'+ext],cwd=ROOT);expected=raw.replace(b'namespace Star {',b'namespace MwcReference {\nusing namespace Star;')
  if ext=='cpp':expected=expected.replace(b'"StarRandom.hpp"',b'"StarRandom.reference.hpp"')
  def freeze(r,d):
   if r!=raw or d!=expected:raise ValueError('source freeze changed')
  r=(HERE/('StarRandom.original.'+ext)).read_bytes();d=(HERE/('StarRandom.reference.'+ext)).read_bytes();freeze(r,d)
  for name,rr,dd in [('raw-'+ext,r+b' ',d),('adapted-'+ext,r,d+b' ')]:
   try:freeze(rr,dd)
   except ValueError:negative.append(name)
   else:raise RuntimeError('source control escaped')
 if (ROOT/'source/core/StarRandom.hpp').read_bytes()!=(HERE/'StarRandom.original.hpp').read_bytes():raise ValueError('header/layout changed')
 active=(ROOT/'source/core/StarRandom.cpp').read_text().split('namespace Star {',1)[1]
 native=re.sub(r'#ifdef STAR_USE_RUST_RANDOM_MWC\n.*?#else\n(.*?)#endif\n',r'\1',active,flags=re.S)
 if native!=(HERE/'StarRandom.original.cpp').read_text().split('namespace Star {',1)[1]:raise ValueError('fallback/excluded methods drift')
 cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarRandom.cpp'));recipe=shlex.split(entry['command']);flags=[];skip=False
 for f in recipe[1:]:
  if skip:skip=False;continue
  if f=='-o':skip=True
  elif f not in ['-c',entry['file']]:flags.append(f)
 if any('STAR_USE_RUST_' in f for f in flags):raise ValueError('reference recipe contaminated')
 lines=(cm/'build.ninja').read_text().splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
 objects=[cm/x for x in shlex.split(lines[i].split(': ',1)[1])[1:] if x.endswith('.o') and (x.startswith('core/') or x.startswith('extern/')) and not x.endswith('/StarRandom.cpp.o')]
 if not objects or any(not x.is_file() for x in objects):raise RuntimeError('real native objects missing')
 libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+15] if x.startswith('  LINK_LIBRARIES = ')));libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
 tracked=[*HERE.glob('*'),db,cm/'build.ninja',Path(recipe[0]).resolve(),*objects,*[Path(x) for x in libs if x.endswith('.a')]]+[x for x in (ROOT/'source/core').rglob('*') if x.is_file() and x.suffix in ['.h','.hpp','.cpp']]
 if a.archive:tracked += [a.archive.resolve(),*list((ROOT/'source/rust/ffi/src').glob('*.rs'))]
 if a.reference_report:tracked.append(a.reference_report.resolve())
 dep_commands=[]
 for n,src in enumerate([HERE/'lab.cpp',HERE/'StarRandom.reference.cpp',ROOT/'source/core/StarRandom.cpp']):
  dep=out/(str(n)+'.d');cmd=[recipe[0],*flags,'-I'+str(HERE),'-M','-MF',str(dep),str(src)]
  if a.define:cmd+=['-D'+a.define]
  dep_commands.append(shlex.join(cmd));scan=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
  if scan.returncode:raise RuntimeError('dependency scan failed '+scan.stderr)
  tracked += [Path(x) if Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])]
 tracked=list(dict.fromkeys(x.resolve() for x in tracked if x.is_file()));before={str(x):sha(x) for x in tracked};(out/'before.json').write_text(json.dumps(before,indent=2));commands=dep_commands
 def run(cmd,name):
  commands.append(shlex.join(map(str,cmd)));r=subprocess.run(list(map(str,cmd)),cwd=ROOT,text=True,capture_output=True,timeout=100,env=dict(os.environ,LAB_OBSERVATIONS=str(out/(name+'.observations'))));(out/(name+'.log')).write_text(commands[-1]+'\n'+r.stdout+r.stderr);return r
 native=out/'native-core.a'
 if run(['/usr/bin/ar','rcs',native,*objects],'archive').returncode:raise RuntimeError('archive failed')
 def compile(name,mode,source=None,reference=None,lab=None,rust=None):
  fs=[f for f in flags if f!='-ffast-math'];extra={'uncontracted':['-ffp-contract=off'],'default':[],'production':['-ffast-math']}[mode];binary=out/name
  cmd=[recipe[0],*fs,*extra,'-I'+str(HERE),lab or HERE/'lab.cpp',reference or HERE/'StarRandom.reference.cpp',source or ROOT/'source/core/StarRandom.cpp',native,*libs,'-Wl,-dead_strip']
  if rust is None:rust=bool(a.define)
  if rust:cmd+=['-D'+a.define,a.archive.resolve()]
  r=run([*cmd,'-o',binary],name+'-compile')
  if r.returncode:raise RuntimeError('compile failed '+name+' '+r.stderr[-2500:])
  return binary
 result={'modes':{}}
 for mode in ['uncontracted','default','production']:
  binary=compile(mode,mode);r=run([binary],mode);repeat=run([binary],mode+'-repeat')
  if r.returncode or repeat.returncode or r.stdout!=repeat.stdout:raise RuntimeError('baseline failed '+mode+' '+r.stderr)
  obs=out/(mode+'.observations')
  if sha(obs)!=sha(out/(mode+'-repeat.observations')):raise RuntimeError('repeat drift')
  result['modes'][mode]=dict(json.loads(r.stdout),ordered_observations_sha256=sha(obs),python_states=python_check(obs),binary_sha256=sha(binary))
  # Verifier self-test: corrupt a valid initialized state, not a compilation.
  damaged=out/(mode+'-damaged.observations');data=obs.read_bytes();damaged.write_bytes(b'9'+data[1:])
  try:python_check(damaged)
  except ValueError:negative.append('python-state-'+mode)
  else:raise RuntimeError('Python verifier escaped known wrong state')
 if a.reference_report:
  ref=json.loads(a.reference_report.read_text())
  def compare(r):
   if r.get('backend')!='cpp' or r.get('status')!='PASS' or any(r['modes'][m]['ordered_observations_sha256']!=result['modes'][m]['ordered_observations_sha256'] for m in result['modes']):raise ValueError('independent CPP stream mismatch')
  compare(ref)
  bad=dict(ref,modes=dict(ref['modes']));bad['modes']['default']=dict(bad['modes']['default'],ordered_observations_sha256='bad')
  try:compare(bad)
  except ValueError:negative.append('independent-digest')
  else:raise RuntimeError('digest control escaped')
  shared=set(ref['bindings'])&set(before);required={str(x.resolve()) for x in objects}|{str((HERE/'lab.cpp').resolve()),str(Path(recipe[0]).resolve())}
  def bindings(r):
   if not required.issubset(shared) or any(r['bindings'][x]!=before[x] for x in shared):raise ValueError('reference source/object drift; replay CPP')
  bindings(ref)
  bad=dict(ref,bindings=dict(ref['bindings']));bad['bindings'][str((HERE/'lab.cpp').resolve())]='bad'
  try:bindings(bad)
  except ValueError:negative.append('independent-binding')
  else:raise RuntimeError('binding control escaped')
 raw=(HERE/'StarRandom.original.cpp').read_bytes()
 mutants=[('no-warmup',b'RandomInitialSkip = 32',b'RandomInitialSkip = 0'),('post-index',b'm_data[++m_index]',b'm_data[m_index++]'),('entropy-reversed',b'seed ^= randu64();',b'seed ^= (uint64_t(randu32()) | (uint64_t(randu32()) << 32));'),('carry-narrow',b'(m_carry ^ seed) % 809430660',b'uint32_t(m_carry ^ seed) % 809430660'),('old-array-xor',b'm_data[i] ^= 69069 * m_data[i - 2] + 362437;',b'm_data[i] ^= 69069 * oldData[i - 2] + 362437;')]
 for name,old,new in mutants:
  if raw.count(old)!=1:raise RuntimeError('mutant anchor missing')
  src=out/(name+'.cpp');changed=raw.replace(old,new)
  if name=='old-array-xor':changed=changed.replace(b'  m_data[0] ^= seed;',b'  uint32_t oldData[256]; for(size_t j=0;j<256;++j) oldData[j]=m_data[j];\n  m_data[0] ^= seed;')
  src.write_bytes(changed);binary=compile(name,'uncontracted',source=src,rust=False);bad=run([binary],name)
  if bad.returncode!=1 or 'COMPARISON' not in bad.stderr:raise RuntimeError('mutant not detected '+name)
  negative.append(name)
 # Matching wrong facades escape paired equality and Python integer-state checks,
 # but MUST change the independent CPP observation stream.
 old=b'return (int32_t)(randu32());';new=b'return (int32_t)(randu32() ^ 1);'
 paired=out/'paired.cpp';paired.write_bytes(raw.replace(old,new));pairedref=out/'paired-reference.cpp';pairedref.write_bytes((HERE/'StarRandom.reference.cpp').read_bytes().replace(old,new));binary=compile('paired','uncontracted',source=paired,reference=pairedref,rust=False);bad=run([binary],'paired')
 if bad.returncode or sha(out/'paired.observations')==result['modes']['uncontracted']['ordered_observations_sha256']:raise RuntimeError('independent paired control escaped')
 negative.append('paired-wrong-independent-stream')
 if a.define:
  current=(ROOT/'source/core/StarRandom.cpp').read_bytes()
  for name,old,new in [('adapter-seed',b'star_random_mwc_init(m_data, &m_carry, &m_index, seed)',b'star_random_mwc_init(m_data, &m_carry, &m_index, seed ^ 1)'),('adapter-output',b'return result;',b'return result ^ 1;')]:
   if current.count(old)!=1:raise RuntimeError('adapter anchor missing')
   src=out/(name+'.cpp');src.write_bytes(current.replace(old,new));binary=compile(name,'uncontracted',source=src);bad=run([binary],name)
   if bad.returncode!=1 or 'COMPARISON' not in bad.stderr:raise RuntimeError('adapter mutant escaped')
   negative.append(name)
  body=(HERE/'lab.cpp').read_text()
  for name,shim in {
   'zero-receipt':'static uint64_t badcount(uint32_t){return 0;}\n#define star_random_mwc_call_count badcount\n',
   'invalid-success':'static int32_t badnext(uint32_t*d,uint32_t*c,uint8_t*i,uint32_t*o){if(!d)return 0;return star_random_mwc_next(d,c,i,o);}\n#define star_random_mwc_next badnext\n',
   'tls-leak':'static auto owner=std::this_thread::get_id();static uint64_t badcount(uint32_t o){return std::this_thread::get_id()==owner?star_random_mwc_call_count(o):1;}\n#define star_random_mwc_call_count badcount\n'
  }.items():
   lab=out/(name+'-lab.cpp');lab.write_text(body.replace('using namespace Star;',shim+'using namespace Star;',1));binary=compile(name,'uncontracted',lab=lab);bad=run([binary],name)
   if bad.returncode!=1 or 'COMPARISON' not in bad.stderr:raise RuntimeError('ABI self-test escaped '+name)
   negative.append(name)
 after={str(x):sha(x) for x in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after:raise RuntimeError('source/object/archive drift: replay required')
 result.update(status='PASS',backend='rust' if a.define else 'cpp',negative_controls=negative,commands=commands,bindings=before,limits=['target-specific semantic offsets, no padding reads','finite cases only','no injected panic/OOM; no game/performance/platform proof','parent native build seal still required'])
 (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['commands','bindings']}))
if __name__=='__main__':main()
