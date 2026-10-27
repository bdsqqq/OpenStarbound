"""Independent public-state model: insertion-ordered records, explicit timestamps.
No C++ parsing or expected-output ingestion. Dependencies are modeled leaves;
T/R operand evaluation order is a compiler-specific observation, not C++ law.
"""
from collections import OrderedDict
import random

class Fault(Exception): pass
class Model:
 def __init__(self):
  self.items=OrderedDict();self.ttl=10000;self.smear=1000;self.limit=(1<<64)-1;self.update=True;self.now=100;self.jitter=0
 def stamp(self):
  self.tc+=1;self.dep.append('T:'+str(self.now))
  if self.ft==self.tc:raise Fault('clock\x01')
  self.rc+=1;self.dep.append(f'R:{-self.smear}:{self.smear}')
  if self.fr==self.rc:raise Fault('random\x02')
  if self.smear<0:raise Fault('STAR')
  assert -self.smear<=self.jitter<=self.smear
  return self.now+self.jitter
 def put(self,key,value):
  stamp=self.stamp();self.items[key]=[stamp,value];self.items.move_to_end(key)
 def ptr(self,key):
  if key not in self.items:return 'null'
  self.items.move_to_end(key)
  if self.update:self.items[key][0]=self.stamp()
  return str(self.items[key][1])
 def state(self):return ','.join(f'{k}:{v[1]}' for k,v in self.items.items()) or '-'
 def apply(self,line):
  sid,op,sa,sb,sd,se=line.split();a,b,d,e=map(int,(sa,sb,sd,se));self.tc=self.rc=0;self.ft=self.fr=0;self.dep=[];ev=[];result='ok'
  try:
   if op=='new':self.items.clear();self.ttl=a;self.smear=b;self.limit=max(d,1);self.update=bool(e)
   elif op=='clock':self.now=a;self.jitter=b
   elif op in ('set','fault-set'):
    if op=='fault-set':self.ft=d;self.fr=e
    self.put(a,b)
   elif op in ('ptr','fault-ptr'):
    if op=='fault-ptr':self.ft=d;self.fr=e
    result=self.ptr(a)
   elif op in ('get','fault-get'):
    if op=='fault-get':self.ft=d;self.fr=e;d=0
    while len(self.items)>=self.limit:self.items.popitem(last=False)
    key=a
    if key not in self.items:
     ev.append('P:'+str(key))
     if d==1:raise Fault('producer\x04')
     if d==2:self.put(a+10,900);raise Fault('producer\x04')
     if d==3:self.put(a,700);self.put(a+1,800)
     if d==4:key+=20
     # std::map insert does not replace a producer-reentered same key.
     if key not in self.items:self.items[key]=[0,b]
    else:self.items.move_to_end(key)
    if self.items[key][0]==0 or self.update:self.items[key][0]=self.stamp()
    result=str(self.items[key][1])
   elif op=='ttl':self.ttl=a
   elif op=='smear':self.smear=a
   elif op=='update':self.update=bool(a)
   elif op=='limit':
    self.limit=max(a,1)
    while len(self.items)>self.limit:self.items.popitem(last=False)
   elif op=='remove':result='1' if self.items.pop(a,None) is not None else '0'
   elif op=='clear':self.items.clear()
   elif op=='cleanup':
    self.tc+=1;self.dep.append('T:'+str(self.now));captured=self.now;count=0
    # Reentry cases restrict promotion to the last entry, so traversal remains valid.
    for key in list(self.items):
     refresh=False
     if a:
      count+=1;ev.append('F:'+str(key))
      if a==3 and count==b:raise Fault('filter\x03')
      if a==4:self.ttl=b
      if a==5:self.now+=b
      if a==6:self.ptr(b)
      refresh=a==1 or (a==2 and key%2==0)
     if refresh:self.items[key][0]=captured
     elif captured-self.items[key][0]>self.ttl:del self.items[key]
   elif op=='filter':
    for key in list(self.items):
     ev.append('F:'+str(key));self.items[key][1]+=1
     if a==2 and key==b:raise Fault('filter\x03')
     if a==3:self.ptr(b)
     if a==1 or (a==2 and key<b):del self.items[key]
   elif op in ('copy','move','assign','move-assign'):
    result='other:'+self.state();self.put(a,b)
   elif op=='snapshot':result=self.state()
   else:raise AssertionError(op)
  except Fault as exc:
   s=str(exc)
   result=('star:'+('(StarException) Maximum bound in randInt must be >= minimum bound!').encode().hex()) if s=='STAR' else 'fault:'+s.encode().hex()
  return '\t'.join(map(str,(sid,self.ttl,self.smear,self.limit,int(self.update),len(self.items),self.state(),result,','.join(ev) or '-',self.tc,self.rc,','.join(self.dep) or '-')))

def corpus():
 rows=[]
 def add(op,a=0,b=0,d=0,e=0):rows.append(f'{len(rows)} {op} {a} {b} {d} {e}')
 # Exact strict boundary, no refresh on disabled ptr, zero timestamp get sentinel.
 for update in (0,1):
  add('new',10,0,4,update);add('clock',100);add('set',1,11);add('clock',110);add('cleanup');add('snapshot');add('clock',111);add('cleanup')
  add('clock',0);add('get',2,22);add('clock',50);add('get',2,99);add('ptr',2);add('cleanup')
 # All cleanup policies, dynamic ttl, captured time, exception partial erasure.
 for mode in range(7):
  add('new',10,0,8,0);add('clock',100)
  for k in range(1,5):add('set',k,k*10)
  add('clock',111);add('cleanup',mode,2 if mode in (3,4) else (4 if mode==6 else 100));add('snapshot');add('cleanup')
 # Discriminate captured-time reuse and dynamic ttl reads before expiry.
 for mode in (4,5):
  add('new',10,0,8,0);add('clock',100)
  for k in range(1,5):add('set',k,k*10)
  add('clock',105);add('cleanup',mode,2 if mode==4 else 100);add('snapshot')
 # Limit clamp, set may exceed limit, get pre-evicts EVEN ON HIT.
 add('new',100,0,0,0);add('clock',200);add('set',1,10);add('set',2,20);add('get',2,999);add('limit',0);add('get',2,999)
 # Producer reentry / key mutation / exact faults.
 for behavior in range(5):
  add('new',10,0,2,0);add('clock',100);add('set',1,10);add('set',2,20);add('get',3,30,behavior);add('snapshot')
 # Dependency failures: get inserts zero timestamp, ptr promotes, set untouched.
 for op in ('fault-set','fault-get','fault-ptr'):
  for leaf in ('clock','random'):
   add('new',10,0,3,1);add('clock',100);add('set',1,10);add('set',2,20);add(op,1 if op=='fault-ptr' else 3,30,int(leaf=='clock'),int(leaf=='random'));add('update',0);add('get',3,33);add('snapshot')
 # Negative smear is a real native exception domain (INT_MIN excluded).
 add('new',10,-2,4,1);add('clock',100);add('set',1,10);add('get',2,20);add('ptr',2);add('smear',0);add('update',0);add('get',2,99)
 for mode in (0,1,2,3):
  add('new',100,0,8,0);add('clock',100)
  for k in range(1,5):add('set',k,k*10)
  add('filter',mode,3 if mode==2 else 4);add('snapshot')
 for op in ('copy','move','assign','move-assign'):
  add('new',10,0,5,0);add('clock',100);add('set',1,10);add(op,2,20);add('clock',111);add('cleanup')
 # Deterministic finite breadth, no undefined signed arithmetic or unsafe reentry.
 rng=random.Random(22027)
 add('new',13,3,5,1)
 for i in range(180):
  add('clock',300+i,rng.randint(-3,3))
  op=rng.choice(('set','ptr','get','remove','cleanup','limit','ttl','update','snapshot'))
  if op in ('set','get'):add(op,rng.randrange(7),rng.randrange(100))
  elif op in ('ptr','remove'):add(op,rng.randrange(7))
  elif op=='limit':add(op,rng.randrange(7))
  elif op=='ttl':add(op,rng.randint(-3,20))
  elif op=='update':add(op,rng.randrange(2))
  else:add(op)
 return rows

def expected(rows):
 m=Model();return '\n'.join(m.apply(x) for x in rows)+'\n'
