"""Small independent integer SHA-256 compression for seeded counter examples.
Round constants derive from prime cube roots, not copied from the frozen source.
Ordinary whole-message results are additionally checked with hashlib in run.py.
"""
from math import isqrt

def root3(x):
 lo,hi=0,1 << ((x.bit_length()+2)//3)
 while lo+1<hi:
  mid=(lo+hi)//2
  if mid**3<=x:lo=mid
  else:hi=mid
 return lo
P=[]
n=2
while len(P)<64:
 if all(n%d for d in range(2,isqrt(n)+1)):P.append(n)
 n+=1
MASK=(1<<32)-1
K=[root3(p<<96)&MASK for p in P]
IV=[isqrt(p<<64)&MASK for p in P[:8]]
def r(x,n):return ((x>>n)|(x<<(32-n)))&MASK
def compress(s,block):
 w=[int.from_bytes(block[i:i+4],'big') for i in range(0,64,4)]
 for i in range(16,64):w.append((w[i-16]+(r(w[i-15],7)^r(w[i-15],18)^(w[i-15]>>3))+w[i-7]+(r(w[i-2],17)^r(w[i-2],19)^(w[i-2]>>10)))&MASK)
 a,b,c,d,e,f,g,h=s
 for k,x in zip(K,w):
  t=(h+(r(e,6)^r(e,11)^r(e,25))+((e&f)^((~e)&g))+k+x)&MASK
  u=((r(a,2)^r(a,13)^r(a,22))+((a&b)^(a&c)^(b&c)))&MASK
  a,b,c,d,e,f,g,h=(t+u)&MASK,a,b,c,(d+t)&MASK,e,f,g
 return [(x+y)&MASK for x,y in zip(s,[a,b,c,d,e,f,g,h])]
def seeded_wrap(bits):
 state=compress(IV,b'a'*64)
 state=compress(state,b'\x80'+b'\0'*55+bits.to_bytes(8,'big'))
 return b''.join(n.to_bytes(4,'big') for n in state).hex()
