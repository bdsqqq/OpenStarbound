"""Independent list/dict state oracle. Frozen before any native observations."""
import copy
MAX=(1<<64)-1
class Cache:
 def __init__(self,n=256):self.limit=max(n,1);self.order=[];self.data={}
 def promote(self,k):self.order.remove(k);self.order.append(k)
 def trim(self,n):
  while len(self.order)>n:del self.data[self.order.pop(0)]
 def set(self,k,v):
  if k in self.data:self.data[k]=v;self.promote(k)
  else:self.order.append(k);self.data[k]=v
 def remove(self,k):
  if k not in self.data:return False
  del self.data[k];self.order.remove(k);return True
 def run(self,op,k,v):
  result='ok';events=[]
  if op=='new':self.__init__(k)
  elif op=='limit':self.limit=max(k,1);self.trim(self.limit)
  elif op=='set':self.set(k,v)
  elif op=='ptr':
   result='null'
   if k in self.data:self.promote(k);result=str(self.data[k])
  elif op=='remove':result=str(int(self.remove(k)))
  elif op=='clear':self.order=[];self.data={}
  elif op=='get':
   self.trim(self.limit-1)
   if k in self.data:self.promote(k);result=str(self.data[k])
   else:
    events.append('produce:'+str(k))
    key=k
    if v==1:self.set(k,700);self.set(k+1,800)
    elif v==2:self.set(k+10,900);self.limit=1;self.trim(1)
    elif v==3:
     self.set(k+10,901);return 'fault:producer',events
    elif v==4:key=k+20 # pair's forwarding constructor copies stable external key AFTER producer
    if key not in self.data:self.order.append(key);self.data[key]=k*10
    result=str(self.data[key])
  elif op=='filter':
   pos=0;once=False
   while pos<len(self.order):
    key=self.order[pos];events.append('filter:'+str(key));self.data[key]+=1
    if k==2 and key==v:return 'fault:filter',events
    if k==3 and key==2 and not once and 1 in self.data:self.promote(1);once=True
    erase=(k==1 or (k==2 and key<v))
    if erase:self.remove(key)
    else:pos=self.order.index(key)+1
  elif op=='assignment-fault':
   # by-value parameter exists before body; mapped assignment mutates then throws, no promotion.
   if k in self.data:self.data[k]=-999;result='fault:assignment'
   else:self.set(k,-99)
  elif op in ('copy','move','copy-assign','move-assign'):
   other=copy.deepcopy(self);self.set(k,v)
   # implicit cache moves COPY native OrderedMapWrapper. Source retains independent nodes.
   result='source:'+','.join(f'{x}:{other.data[x]}' for x in other.order)
  else:raise ValueError(op)
  return result,events
 def row(self,name,result,events):return '\t'.join([name,str(self.limit),str(len(self.order)),','.join(f'{k}:{self.data[k]}' for k in self.order) or '-',result,','.join(events) or '-'])

def corpus():
 rows=[]
 def add(op,k=0,v=0):rows.append((f'c{len(rows):04}',op,k,v))
 for n in (0,1,3,MAX):
  add('new',n);add('ptr',7);add('remove',7)
  for k in (1,2,3):add('set',k,k*100)
  add('ptr',1);add('get',2);add('get',1);add('limit',0);add('get',3);add('limit',MAX);add('clear')
 for mode in range(5):
  add('new',3);add('set',1,100);add('set',2,200);add('get',3,mode);add('ptr',3);add('set',5,500);add('get',5)
 for mode in range(4):
  add('new',8)
  for k in (1,2,3):add('set',k,100*k)
  add('filter',mode,2);add('ptr',3);add('remove',1)
 for op in ('copy','move','copy-assign','move-assign'):
  add('new',4);add('set',1,100);add('set',2,200);add(op,1,111);add('ptr',2)
 add('new',2);add('set',1,100);add('set',2,200);add('assignment-fault',1);add('ptr',1)
 # Deterministic exhaustive short ordinary sequences, no clock/random dependency.
 import itertools
 for seq in itertools.product(('set','ptr','get','remove','limit'),repeat=3):
  add('new',2)
  for j,op in enumerate(seq):add(op,(j%2)+1,10+j)
 return rows

def expected():
 c=Cache();out=[]
 for name,op,k,v in corpus():
  result,events=c.run(op,k,v);out.append(c.row(name,result,events))
 return ('\n'.join(out)+'\n').encode()

def literal_checks():
 c=Cache(1);c.set(1,9);r,e=c.run('get',1,0);assert r=='10' and e==['produce:1']
 c=Cache(2);c.set(1,10);c.set(2,20);c.set(3,30);assert c.order==[1,2,3]
 c.run('ptr',1,0);assert c.order==[2,3,1]
 c.run('get',1,0);assert c.order==[1] and c.data=={1:10}
 c=Cache(3);c.run('get',5,1);assert c.order==[5,6] and c.data[5]==700
 c=Cache(3);c.run('get',5,4);assert c.order==[25] and c.data[25]==50
 c=Cache(9)
 for k in (1,2,3):c.set(k,k)
 r,e=c.run('filter',3,0);assert e==['filter:1','filter:2','filter:3','filter:1'] and c.order==[2,3,1]
 return 6

# Source-derived language assertions, NOT observed-output goldens. Native prints booleans
# for these relations; comparator demands each true and no missing/extra property.
PROPERTIES=['pointer-promotion-identity','reference-promotion-identity','move-ctor-copies-map','move-assign-copies-map','copy-independence','assignment-old-limit-partial-map','producer-byvalue-copy','set-byvalue-before-body','key-copy-after-producer','balanced-native-lifetimes','filter-byvalue-copy','exception-dynamic-type-and-bytes']
if __name__=='__main__':
 literal_checks();print(len(corpus()),len(PROPERTIES))
