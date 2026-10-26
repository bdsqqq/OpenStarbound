"""Independent literal/script model; no native output is used as a golden."""
import json
OPS=('read','write','readabs','writeabs','fullabsread','fullabswrite','size','end','bytes','bytesabs','writebytes','writebytesabs','resize','sync','open-equal','open-different')
def expected():
 rows={}
 for m in range(256):rows[f'mode/{m}']=f'{m}:{m}:{m}';rows[f'close/{m}']='0'
 def case(op,n,c,e,fault=0,after=0,other=0):
  pos=3;buf=bytearray(b'Q'*8);events=[];step=0
  class Fault(Exception):pass
  def call(kind,arg=None):
   nonlocal pos,step
   text=kind if arg is None else kind+'/'+('/'.join(map(str,arg)) if isinstance(arg,tuple) else str(arg))
   events.append(text);step+=1
   if fault==step and not after:raise Fault()
   if kind=='seek':pos=9 if arg[1]==2 else arg[0];v=None
   elif kind in ('read','write'):
    v=min(arg,c);pos+=v
    if kind=='read':buf[:v]=b'R'*v
   elif kind=='pos':v=pos
   elif kind=='end':v=e
   else:v=None
   if fault==step and after:raise Fault()
   return v
  def full(write=False):
   r=call('write' if write else 'read',n)
   if r<n:return 'EOF' if call('end') else 'IO/new/plain'
   return 'OK'
  def absolute(write=False,offset=-2,count=n,idx=0):
   saved=call('pos');call('seek',(offset,0));r=call('write' if write else 'read',count)
   # Reads at later full-absolute iterations target an advanced output pointer.
   if not write and idx:buf[:idx]=b'R'*idx;buf[idx:idx+r]=b'R'*r
   call('seek',(saved,0));return r
  try:
   if op in ('read','write'):v=full(op=='write')
   elif op in ('readabs','writeabs'):v=str(absolute(op=='writeabs'))
   elif op in ('fullabsread','fullabswrite','bytesabs','writebytesabs'):
    left=n;offset=-2;idx=0;v='OK'
    while left:
     r=absolute(op in ('fullabswrite','writebytesabs'),offset,left,idx)
     if not r:v='IO/new/plain';break
     left-=r;offset+=r;idx+=r
    if op=='bytesabs' and v=='OK':v='52'*n
   elif op in ('bytes','writebytes'):
    v='OK' if op=='bytes' and not n else full(op=='writebytes')
    if op=='bytes' and v=='OK':v='52'*n
   elif op in ('size','end'):
    first=call('pos') if op=='end' else None;saved=call('pos');call('seek',(0,2));v=call('pos');call('seek',(saved,0));v=str(int(first>=v)) if op=='end' else str(v)
   elif op=='resize':v='IO/new/plain'
   elif op=='open-different':call('name');v='IO/new/plain'
   else:v='OK'
  except Fault:v='OTHER' if other else ('IO/new/cause' if op=='size' else 'IO/same/cause')
  if op in ('bytes','bytesabs'):buf=bytearray(b'Q'*8)
  return f'{v}:{pos}:{buf.hex()}:'+''.join(x+';' for x in events)
 for op in OPS:
  for n in (0,4):
   for c in (0,2,4):
    for e in (0,1):rows[f'{op}/{n}/{c}/{e}']=case(op,n,c,e)
 for op in ('size','readabs','writeabs','read','write','fullabsread','fullabswrite','open-different'):
  for f in range(1,10):
   for a in (0,1):
    for o in (0,1):rows[f'fault/{op}/{f}/{a}/{o}']=case(op,4,2,False,f,a,o)
 rows['virtual-bytes/0']='WF/0;WA/0;::'
 rows['virtual-bytes/4']='RF/4;RA/4;WF/4;WA/4;:52525252:52525252'
 rows['reentry']='9:255:reenter;pos;seek/0/2;pos;seek/3/0;'
 rows['owner-name']='1';rows['destructor']='';rows['huge-zero']='IO/new/plain:read/18446744073709551615;end;'
 return rows
EXPECTED=expected()
def check(data):
 got={}
 for line in data.decode('ascii').splitlines():
  r=json.loads(line)
  if set(r)!={'key','value'} or r['key'] in got:raise ValueError('schema/duplicate')
  got[r['key']]=r['value']
 if got.keys()!=EXPECTED.keys():raise ValueError('case keys')
 for k,v in EXPECTED.items():
  if got[k]!=v:raise ValueError(f'literal {k}: {got[k]} != {v}')
 return len(got)
