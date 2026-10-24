#!/usr/bin/env python3
"""Compare isolated frozen expressions; not a framebuffer-causality test."""
import ctypes as C, json, random, struct
from pathlib import Path
root=Path(__file__).resolve().parents[4]
out=root/'build/lighting-fp'
f=C.c_float;ptr=C.POINTER(f);arr=f*4
libs={m:C.CDLL(str(out/(m+'.dylib'))) for m in ('precise','fast','nofma','contract','policy')}
for m,lib in libs.items():
 for site,args in {'spread':[ptr,ptr,f,ptr],'subtract':[ptr,f,ptr],'distance':[f,f],'diag':[f],'circular':[f,f],'source':[f,f,f,ptr],'direction':[f,f,f,ptr]}.items():
  fn=getattr(lib,m+'_'+site);fn.argtypes=args;fn.restype=f if site in ('distance','diag','circular') else None
libm=C.CDLL(None);fma=libm.fmaf;fma.argtypes=[f,f,f];fma.restype=f
F=lambda x:f(x).value
bits=lambda x:struct.pack('f',x).hex()
rng=random.Random(1592594996)
report={'samples':20000,'counts':{},'first':{},'policy_vs_fast':{},'prediction_mismatches':{'spread_fma':0,'subtract_reciprocal':0}}
for i in range(report['samples']):
 src=[F(rng.uniform(.01,3)) for _ in range(3)];dst=[F(rng.uniform(0,.1)) for _ in range(3)];drop=F(rng.uniform(.001,.9));x=F(rng.uniform(-40,40));y=F(rng.uniform(-40,40));xd=F(rng.random());yd=F(rng.random());att=F(rng.uniform(.01,.3));air=F(rng.uniform(1,100))
 inputs={'spread':src+dst+[drop],'subtract':src+[drop],'distance':[x,y],'diag':[air],'circular':[air,F(rng.uniform(.7072,1))],'source':[xd,yd,att],'direction':[x,y,F((x*x+y*y)**.5)]}
 for site in inputs:
  vals={}
  for m,lib in libs.items():
   fn=getattr(lib,m+'_'+site);a=arr(*src);b=arr(*dst);o=arr()
   if site=='spread':fn(a,b,drop,o);v=list(o)[:3]
   elif site=='subtract':fn(a,drop,o);v=list(o)[:3]
   elif site in ('distance','diag','circular'):v=[fn(*inputs[site])]
   else:fn(*inputs[site],o);v=list(o)[:4 if site=='source' else 2]
   vals[m]=v
  for m in ('fast','nofma','contract'):
   k=site+':'+m;diff=sum(bits(a)!=bits(b) for a,b in zip(vals['precise'],vals[m]));report['counts'][k]=report['counts'].get(k,0)+diff
   if diff and k not in report['first']:report['first'][k]={'input':inputs[site],'precise':vals['precise'],m:vals[m]}
  report['policy_vs_fast'][site]=report['policy_vs_fast'].get(site,0)+sum(bits(a)!=bits(b) for a,b in zip(vals['policy'],vals['fast']))
  if site=='spread':
   ratio=F(drop/max(src));pred=[max(fma(-s,ratio,s),d) for s,d in zip(src,dst)]
   report['prediction_mismatches']['spread_fma']+=sum(bits(a)!=bits(b) for a,b in zip(pred,vals['fast']))
  if site=='subtract':
   recip=F(1/max(src));d=[F(F(drop*s)*recip) for s in src];pred=[F(s-p) if s>p else 0.0 for s,p in zip(src,d)]
   report['prediction_mismatches']['subtract_reciprocal']+=sum(bits(a)!=bits(b) for a,b in zip(pred,vals['fast']))
report['line']={'samples':20000,'counts':{},'first':{}}
for m in ('precise','fast','nofma','contract'):
 fn=getattr(libs[m],m+'_line');fn.argtypes=[f,f,f,f];fn.restype=f
for _ in range(report['line']['samples']):
 args=[F(rng.uniform(3,28)),F(rng.uniform(3,28)),F(rng.uniform(.01,.2)),F(rng.uniform(.5,1))]
 vals={m:getattr(libs[m],m+'_line')(*args) for m in ('precise','fast','nofma','contract')}
 for m in ('fast','nofma','contract'):
  diff=bits(vals[m])!=bits(vals['precise']);report['line']['counts'][m]=report['line']['counts'].get(m,0)+diff
  if diff and m not in report['line']['first']:report['line']['first'][m]={'input':args,'precise':vals['precise'],m:vals[m]}
report['half_cell_line']={'samples':0,'counts':{},'first':{}}
for x in range(3,28):
 for y in range(3,28):
  if x==4 and y==4:continue
  for per in (.05,.1,.2):
   args=[x+.5,y+.5,F(per),1.0];report['half_cell_line']['samples']+=1
   vals={m:getattr(libs[m],m+'_line')(*args) for m in ('precise','fast','nofma','contract')}
   for m in ('fast','nofma','contract'):
    diff=bits(vals[m])!=bits(vals['precise']);report['half_cell_line']['counts'][m]=report['half_cell_line']['counts'].get(m,0)+diff
    if diff and m not in report['half_cell_line']['first']:report['half_cell_line']['first'][m]={'input':args,'precise':vals['precise'],m:vals[m]}
(out/'sites.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='first'},indent=2))
