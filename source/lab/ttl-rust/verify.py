#!/usr/bin/env python3
"""Strict read-only reconstruction; no subprocesses, including negative controls.
Coherent read overlays update product hashes to reach deeper semantic barriers.
"""
import copy,re,tarfile
from common import *
import guarded_canonical as canonical
import evidence,model
from acquire import BASE,BASE_SHA,BOUNDARY,recipe,baseline
KERNEL=ROOT/'source/rust/ffi/src/ttl_cache.rs'
KERNEL_SHA='c17c51d6d902558e7b8a0fbed4d5b0282044dbe432775e8b4eea12784b00d6fd'
HEADER=ROOT/'source/core/StarRustTtlCache.h'
HEADER_SHA='254cf12cb2ec798334cf0799b4344f58eb140e657dceb12d0788200cdc17332d'

def semantics(data):
 rows=model.corpus();need(len(rows)==626,'626 frozen model rows')
 expected=model.expected(rows).encode();need(data(OUT/'corpus.tsv')==('\n'.join(rows)+'\n').encode(),'model domain barrier')
 counts=[]
 for a in ('ordered','hash'):
  first=None
  for i in range(2):
   raw=data(OUT/f'{a}-{i}.stdout');need(raw==expected,'model stream barrier')
   need(raw==(BASE/f'{a}-{i}.stdout').read_bytes(),'exact frozen native stream')
   if first is None:first=raw
   else:need(raw==first,'repeat stream')
   route=routes(data(OUT/f'{a}-{i}.stderr'))
   need(all(route[k]>0 for k in ('9:1','15:2','18:3')),'corpus actual values/filter/cleanup Rust stages')
   counts.append(route)
 life=data(OUT/'lifecycle.stdout');need(life==(BASE/'lifecycle.stdout').read_bytes(),'lifetime full native trace barrier')
 lines=life.decode().splitlines();props=[x for x in lines if x.startswith('property\t')]
 need(len(props)==68 and all(x.endswith('\t1') for x in props),'68 lifecycle properties')
 traces={x.split('\t')[1]:x.split('\t')[2].split(',') for x in lines if x.startswith('trace\t')}
 need(len(traces)==4 and all(len(t)==216 for t in traces.values()),'four 216-event traces')
 life_routes=routes(data(OUT/'lifecycle.stderr'));control_routes=routes(data(OUT/'controls.stderr'));real_routes=routes(data(OUT/'real.stderr'))
 alias={}
 for line in data(OUT/'lifecycle.stderr').decode().splitlines():
  if line.startswith('alias-route\t'):
   _,a,m,s,c=line.split('\t');alias.setdefault(a,{})[m+':'+s]=int(c)
 need(set(alias)==set(traces),'all four actual/scripted lifetime route groups')
 for a,rs in alias.items():need(rs.get('9:1',0)>0 and rs.get('15:2',0)>0,'per-alias nested values/filter Rust routes')
 combined={key:sum(r[key] for r in [*counts,life_routes,control_routes,real_routes]) for key in life_routes}
 need(all(combined[str(m)+':0']>0 for m in range(19)),'all nineteen actual Rust root modes')
 need(all(combined[k]>0 for k in ('9:1','15:2','18:3')),'actual nested Rust stages')
 controls=data(OUT/'controls.stdout').decode().splitlines();controls=[x for x in controls if x.startswith('control\t')]
 need(len(controls)>70 and all(x.endswith('\t1') for x in controls),'native ABI/unwind controls')
 for name in ('saved-exception-ptr','nested-values-ordered-exact-unwind-trace','nested-values-hash-exact-unwind-trace','nested-cleanup-saved-exception-ptr','actual-rust-350001-values-no-cap','actual-rust-193-nested-no-cap','actual-rust-invalid-caller-metadata-preserved'):
  need('control\t'+name+'\t1' in controls,'native identity/full-unwind '+name)
 real=data(OUT/'real.stdout').decode();smokes=[x.split('\t')[1] for x in real.splitlines() if x.startswith('real-smoke\t')]
 need(smokes==['ordered','hash','native-original-ordered','native-original-hash'],'actual Time/Random boundary AND original production-class smoke separate')
 images=[x.split('\t') for x in real.splitlines() if x.startswith('loaded-image\t')]
 need(len(images)>2 and all(len(x)==3 and re.fullmatch('[a-f0-9]{32}',x[2]) for x in images),'actual loaded runtime UUIDs')
 need(any('/libc++.' in x[1] for x in images) and any('libSystem.' in x[1] for x in images),'native C++/system runtime')
 return {'rows_per_stream':626,'streams':4,'lifecycle_properties':68,'trace_events':{a:len(t) for a,t in traces.items()},'actual_rust_counters':combined,'lifetime_alias_counters':alias,'native_controls':len(controls),'runtime_images':len(images),'clock_limits':'ordered/hash exact boundary cases are scripted calibration; real mode is actual Time/Random smoke only'}

def routes(raw):
 rows=[line.split('\t') for line in raw.decode().splitlines() if line.startswith('rust-route\t')]
 need(len(rows)==76,'76 actual Rust counters')
 out={}
 for _,m,s,n in rows:
  need(m.isdecimal() and s.isdecimal() and n.isdecimal(),'typed Rust counters')
  key=m+':'+s;need(key not in out and 0<=int(m)<19 and 0<=int(s)<4,'unique counter coordinates');out[key]=int(n)
 return out

def verify(report=None,data=None):
 report=report or load(OUT/'report.typed');data=data or (lambda p:Path(p).read_bytes())
 def typed(p):return codec.loads(data(p).decode('ascii'))
 need(report['status']=='FINITE_ACTUAL_RUST_TTL_BRIDGE_PASS','typed report status')
 # Frozen independent source pins remain meaningful even for coherently rehashed overlays.
 need(hashlib.sha256(data(KERNEL)).hexdigest()==KERNEL_SHA,'frozen kernel source barrier')
 need(hashlib.sha256(data(HEADER)).hexdigest()==HEADER_SHA,'frozen C11 header source barrier')
 need(report['native_baseline_sha256']==BASE_SHA,'frozen native report pin')
 same(report['inputs'],typed(OUT/'inputs-before.typed'),'precompiler input binding')
 for field in ('inputs','products'):
  for p,h in report[field].items():need(hashlib.sha256(data(p)).hexdigest()==h,field+' byte barrier '+p)
 actual={str(p) for p in OUT.rglob('*') if p.is_file() and p.name not in ('report.typed','HANDOFF.md','acquisition.log') and 'audit' not in p.relative_to(OUT).parts}
 same(sorted(actual),sorted(report['products']),'exact retained product membership')
 for p in report['products']:
  s=Path(p).lstat();need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'regular unaliased retained product')
 canonical.verify();same(recipe(),typed(OUT/'recipe.typed'),'frozen all-OFF Core profile')
 same(baseline(),typed(OUT/'native-baseline.typed'),'native calibration source/object lineage')
 ready=typed(OUT/'dependency-ready.typed');same(ready['source'],hashes(BOUNDARY.glob('*')),'parent reviewed boundary source')
 need(b'mock.cpp' not in data(OUT/'fixture.cpp') and b'sb_ttl_mock' not in data(OUT/'fixture.cpp'),'actual Rust fixture no mock controller')
 expected_commands={'sealed-canonical-configure','sealed-canonical-build','guarded-object-deps','guarded-canonical-configure','guarded-canonical-build','fixture-deps','c11','fixture-compile','fixture-expand','fixture-link','fixture-disassemble','ordered-0','ordered-1','hash-0','hash-1','lifecycle','real','controls'}
 same(sorted(p.name[:-8] for p in OUT.glob('*.receipt')),sorted(expected_commands),'exact historical preparation plus admitted bridge command receipts')
 verify_commands(report,data)
 for stem in ('provisional-canonical','provisional-toolchain'):
  retained=json.loads(data(OUT/(stem+'.json')))
  need(hashlib.sha256(data(OUT/(stem+'.tar.gz'))).hexdigest()==retained['archive_sha256'],'provisional archive pin')
  with tarfile.open(OUT/(stem+'.tar.gz'),'r:gz') as archive:
   same(sorted(archive.getnames()),sorted(retained['members']),'exact provisional archive membership')
   for name,row in retained['members'].items():
    b=archive.extractfile(name).read();need(len(b)==row['size'] and hashlib.sha256(b).hexdigest()==row['sha256'],'exact provisional byte retention')
 before=typed(OUT/'sdk-before.typed');same(before,typed(OUT/'sdk-after.typed'),'SDK witness stability')
 sdk=recipe()['flags'][recipe()['flags'].index('-isysroot')+1];sdk_witness.verify(before,sdk,canonical.SDK)
 same(evidence.origins('fixture',recipe(),before,data),typed(OUT/'fixture-origin.typed'),'physical actual Rust provider barrier')
 same(semantics(data),report['semantics'],'reconstructed finite semantics')
 return {'status':'STRICT_READONLY_ACTUAL_RUST_TTL_PASS','report_sha256':sha(OUT/'report.typed'),'processes':len(list(OUT.glob('*.receipt'))),'semantics':report['semantics']}

def controls():
 original=load(OUT/'report.typed');results={}
 def reject(name,overlay,barrier):
  r=copy.deepcopy(original)
  for p,b in overlay.items():
   for field in ('inputs','products'):
    if str(p) in r[field]:r[field][str(p)]=hashlib.sha256(b).hexdigest()
  if r['inputs']!=original['inputs']:
   overlay[OUT/'inputs-before.typed']=codec.dumps(r['inputs']).encode('ascii')
   r['products'][str(OUT/'inputs-before.typed')]=hashlib.sha256(overlay[OUT/'inputs-before.typed']).hexdigest()
  def read(p):return overlay.get(Path(p),Path(p).read_bytes())
  try:verify(r,read)
  except (ValueError,AssertionError) as e:
   need(barrier in str(e),'control '+name+' reached wrong barrier: '+str(e));results[name]=str(e)
  else:raise ValueError('coherent negative escaped '+name)
 p=OUT/'ordered-0.stdout';raw=p.read_bytes().splitlines();cols=raw[10].split(b'\t');cols[7]=b'wrong-result';raw[10]=b'\t'.join(cols)
 reject('coherent-model-stream',{p:b'\n'.join(raw)+b'\n'},'model stream barrier')
 p=OUT/'lifecycle.stdout';reject('coherent-native-trace',{p:p.read_bytes().replace(b'producer-call',b'producer-wrong',1)},'lifetime full native trace barrier')
 p=OUT/'ordered-0.receipt';r=load(p);r['pid']=True;r['pgid']=True
 started=OUT/'ordered-0.started';s=load(started);s['pid']=True;s['pgid']=True
 reject('coherent-boolean-pid',{p:codec.dumps(r).encode(),started:codec.dumps(s).encode()},'typed owned group')
 p=OUT/'fixture.map';raw=p.read_bytes();lines=raw.splitlines();hit=[i for i,l in enumerate(lines) if l.endswith(b' _sb_ttl_run')];need(len(hit)==1,'unique provider control target')
 i=hit[0];lines[i]=re.sub(rb'\[\s*\d+\]',b'[  1]',lines[i]);reject('coherent-map-provider',{p:b'\n'.join(lines)+b'\n'},'provider')
 reject('coherent-kernel-source',{KERNEL:KERNEL.read_bytes()+b'\n// wrong source\n'},'frozen kernel source barrier')
 return results

if __name__=='__main__':
 def forbidden(*args,**kwargs):raise AssertionError('read-only replay forbids subprocess creation')
 subprocess.Popen=forbidden;os.system=forbidden
 for name in ('fork','forkpty','posix_spawn','posix_spawnp'):
  if hasattr(os,name):setattr(os,name,forbidden)
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--report-sha',required=True);p.add_argument('--controls',action='store_true');args=p.parse_args()
 need(sha(OUT/'report.typed')==args.report_sha,'external report pin')
 result=verify()
 if args.controls:result['controls']=controls()
 print(codec.dumps(result))
