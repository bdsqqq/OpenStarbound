#!/usr/bin/env python3
"""Six-case source-derived callback witness. Never consumes observations as goldens."""
import argparse,copy,hashlib,json,pathlib,sys
# Frozen before first native execution: source/core/StarIODevice.cpp:75-116.
# Each tuple is (absolute seek, caller-relative pointer, remaining request, count).
SCHEDULE=((-4,0,5,2),(-2,2,3,2),(0,4,1,1))
FINALS={'none':(6,'41414242432e2e2e','6162636465'),'before-second-IO':(-2,'41412e2e2e2e2e2e','6162'),'after-second-IO':(0,'414142422e2e2e2e','61626364')}
def expected():
 rows=[]
 for direction in ('read','write'):
  for fault in FINALS:
   cursor=6;output=bytearray(b'.'*8);sink=bytearray();ordinal=0;events=[]
   def ev(op,phase,ptr=-1,length=0,n=0,arg=0):events.append(dict(op=op,phase=phase,cursor=cursor,ptr=ptr,len=length,n=n,arg=arg,ordinal=ordinal,output=output.hex(),sink=sink.hex()))
   def seek(target):
    nonlocal cursor
    ev('seek','before',arg=target);cursor=target;ev('seek','mutated',arg=target);ev('seek','return',arg=target)
   for target,ptr,length,n in SCHEDULE:
    ev('pos','before');ev('pos','return');seek(target);ordinal+=1;ev(direction,'before',ptr,length)
    if ordinal==2 and fault=='before-second-IO':ev(direction,'throw',ptr,length);break
    # Primitive callback effect, committed BEFORE any possible throw.
    if direction=='read':output[ptr:ptr+n]=bytes([64+ordinal])*n
    else:sink.extend(b'abcdefgh'[ptr:ptr+n])
    cursor+=n;ev(direction,'mutated',ptr,length,n)
    if ordinal==2 and fault=='after-second-IO':ev(direction,'throw',ptr,length,n);break
    ev(direction,'return',ptr,length,n);seek(6)
   final=FINALS[fault]
   assert cursor==final[0] and (output.hex() if direction=='read' else sink.hex())==final[1 if direction=='read' else 2]
   rows.append(dict(case=direction+'/'+fault,result='OK' if fault=='none' else 'IO/same',cursor=cursor,output=output.hex(),sink=sink.hex(),events=events))
 return rows
EXPECTED=expected()
def check(data):
 got=[json.loads(x) for x in data.decode('ascii').splitlines()]
 if len(got)!=6:raise ValueError('six case count')
 for actual,want in zip(got,EXPECTED):
  if actual!=want:
   for field in want:
    if actual.get(field)!=want[field]:raise ValueError(want['case']+': mismatch '+field)
   raise ValueError('extra schema field')
 return 6
def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def verify(directory):
 p=pathlib.Path(directory);r=json.loads((p/'report.json').read_text())
 for group in ('bindings','artifacts'):
  for file,digest in r[group].items():
   if sha(file)!=digest:raise ValueError('artifact binding '+file)
 if json.loads((p/'before.json').read_text())!=json.loads((p/'after.json').read_text()):raise ValueError('before/after drift')
 receipts=json.loads((p/'receipts.json').read_text())
 if receipts!=r['receipts']:raise ValueError('receipt mismatch')
 for receipt in receipts:
  if receipt['returncode']!=0 or receipt['executable_sha256_before']!=receipt['executable_sha256']:raise ValueError('non-normal execution')
  for ext in ('stdout','stderr'):
   if sha(p/(receipt['name']+'.'+ext))!=receipt[ext+'_sha256']:raise ValueError('stdio binding')
 for name in ('original','reference','current','repeat'):check((p/(name+'.stdout')).read_bytes())
 for name in ('pointer-no-advance','failure-restore'):
  try:check((p/(name+'.stdout')).read_bytes())
  except ValueError:pass
  else:raise ValueError('semantic negative escaped '+name)
 return dict(status=r['status'],cases=6,controls=r['controls'])
def main():
 ap=argparse.ArgumentParser();ap.add_argument('directory');a=ap.parse_args();print(json.dumps(verify(a.directory)))
if __name__=='__main__':main()
