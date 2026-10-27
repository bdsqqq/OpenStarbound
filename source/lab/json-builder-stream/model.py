"""Independent finite stack semantics, frozen before native observations.

Objects compare unordered members, NOT iteration/serialization order. Native
raw-order traces are separately compared original/current without an oracle.
Numeric acceptance follows StarLexicalCast.hpp and fast_float.h; out-of-range
integer leaves the initialized zero unchanged, rather than throwing.
"""
import itertools
import re
import struct

class Fault(Exception):
    def __init__(self, name, message=''):
        self.name=name
        self.what=('('+name+')'+(' '+message if message else '')).encode().split(b'\0',1)[0]
    def encoded(self):return 'E:Star::'+self.name+':'+self.what.hex()

def string(units):
    return b''.join(chr(c if c<=0x10ffff and not 0xd800<=c<=0xdfff else 0xfffd).encode() for c in units)
def event(op, s=''):
    return (op, tuple(map(ord,s)) if isinstance(s,str) else tuple(s))
def dump(v):
    t,x=v
    if t=='n':return 'n'
    if t=='s':return 's'+x.hex()
    if t=='i':return 'i'+str(x)
    if t=='b':return 'b'+str(int(x))
    if t=='f':return 'f'+x
    if t=='a':return 'a['+','.join(map(dump,x))+']'
    if t=='o':return 'o{'+','.join(k.hex()+':'+dump(x[k]) for k in sorted(x))+'}'
    raise AssertionError(t)

def number(op,units):
    s=string(units).decode('utf8')
    pattern=r'-?[0-9]+' if op=='I' else r'-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?'
    match=re.match(pattern,s)
    if op=='D' and s.lower() in ('inf','-inf','infinity','-infinity','nan','-nan','nan(payload)'):
        bits={'inf':'7ff0000000000000','-inf':'fff0000000000000','infinity':'7ff0000000000000','-infinity':'fff0000000000000','nan':'7ff8000000000000','-nan':'fff8000000000000','nan(payload)':'7ff8000000000000'}[s.lower()]
        return ('f',bits)
    if not match or match.end()!=len(s):
        raise Fault('BadLexicalCast',"Lexical cast failed on '"+s+"'"+(' (invalid argument)' if not match else ''))
    if op=='I':
        n=int(s)
        return ('i',n if -(1<<63)<=n<(1<<63) else 0)
    return ('f',struct.pack('>d',float(s)).hex())

class Builder:
    def __init__(self):self.stack=[]
    def pop(self):
        if not self.stack:raise Fault('OutOfRangeException','last() called on empty list')
        v=self.stack.pop()
        if v is None:raise Fault('InvalidMaybeAccessException')
        return v
    def apply(self,e):
        op,u=e
        if op in ('BO','BA'):self.stack.append(None)
        elif op in ('K','S'):self.stack.append(('s',string(u)))
        elif op in ('I','D'):self.stack.append(number(op,u))
        elif op=='B':self.stack.append(('b',bool(u[0])))
        elif op=='N':self.stack.append(('n',None))
        elif op=='T':return dump(self.pop()) if self.stack else 'n'
        elif op in ('EO','EA'):
            local={} if op=='EO' else []
            while True:
                if self.stack and self.stack[-1] is None:
                    self.stack[-1]=('o',local) if op=='EO' else ('a',list(reversed(local)))
                    break
                v=self.pop()
                if op=='EA':local.append(v)
                else:
                    k=self.pop()
                    if k[0]!='s':
                        names={'n':'null','b':'bool','i':'int','f':'float','a':'array','o':'object'}
                        raise Fault('JsonException','Cannot convert from '+names[k[0]]+' to string')
                    key=k[1]
                    if key in local:raise Fault('JsonParsingException',"Json object contains a duplicate entry for key '"+key.decode()+"'")
                    local[key]=v
        elif op not in ('W','C',',','Z'):raise AssertionError(op)
        return '-'
    def drain(self):
        other=Builder();other.stack=list(self.stack);out=[]
        while other.stack:
            try:out.append(dump(other.pop()))
            except Fault as f:out.append(f.encoded())
        return '|'.join(out)


def cases():
    out=[]
    def add(name,seq):out.append((name,[event(*e) if isinstance(e,tuple) else event(e) for e in seq]))
    add('empty',['T','EO','EA','T','W','C',',','Z'])
    add('containers',['BO','EO','BA','EA','T','T','T'])
    add('nested',['BA',('I','1'),'BO',('K','alpha'),'BA',('B',[1]),'N',('S','x'),'EA','EO',('I','2'),'EA','T'])
    add('duplicate',['BO',('K','z'),('I','11'),('K','x'),('I','22'),('K','z'),('I','33'),'EO','Z','T','EO','T'])
    add('duplicate-continuation',['BA',('I','7'),'BO',('K','a'),('I','1'),('K','a'),('I','2'),'EO',('I','9'),'EA','T','EA','T'])
    for key in [('I','1'),'N',('B',[0]),'BA','BO']:
        seq=['BO',key,('I','5'),'EO','T','EA','T']
        add('nonstring-'+str(len(out)),seq)
    units=[[],[0],[65,0,66],[0x7f,0x80,0x7ff,0x800,0xd7ff,0xd800,0xdfff,0xe000,0xffff,0x10000,0x10ffff,0x110000,0xffffffff],[0x1f600],[10,13,9,34,92]]
    for i,u in enumerate(units):
        add('unicode-'+str(i),[('S',u),'T','BO',('K',u),('S',u),'EO','T'])
    ints=['0','-0','1','-1','00012','9223372036854775807','-9223372036854775808','9223372036854775808','-9223372036854775809','18446744073709551616','','x','+1',' 1','1 ','1x','1.5','-','1\x00','\x00','12\x003']
    doubles=['0','-0','1','-1','0.5','1e3','1e-3','4.9406564584124654e-324','2.2250738585072014e-308','1.7976931348623157e308','1e309','-1e309','1e-400','-1e-400','inf','-inf','nan','-nan','nan(payload)','','x','+1',' 1','1 ','1x','-','1\x00','\x00','12\x003']
    for op,tokens in [('I',ints),('D',doubles)]:
        for i,s in enumerate(tokens):add(op+'-'+str(i),['BA',(op,s),('I','17'),'EA','T'])
    # Exhaustive finite short sequences explore destructive errors, no-op methods,
    # cross-kind sentries, and multiple independently queued values.
    alphabet=['BO','BA','EO','EA','T','N',('S','key'),('I','3'),'C']
    for n in (1,2,3):
        for seq in itertools.product(alphabet,repeat=n):add('short-'+str(len(out)),[*seq,'Z','T'])
    add('object-order',['BO',('K','first'),('I','1'),('K','second'),('I','2'),('K','third'),('I','3'),'EO','T'])
    for depth in (1,8,64):add('depth-'+str(depth),['BA']*depth+[('I','4')]+['EA']*depth+['T'])
    return out

def inputs():
    return ''.join(name+'\t'+str(i)+'\t'+op+'\t'+(','.join(format(x,'x') for x in units) or '-')+'\n' for name,seq in cases() for i,(op,units) in enumerate(seq)).encode()
def expected():
    rows=[]
    for name,seq in cases():
        b=Builder()
        for i,e in enumerate(seq):
            try:r=b.apply(e)
            except Fault as f:r=f.encoded()
            rows.append('\t'.join((name,str(i),r,str(len(b.stack)),b.drain(),'1'))+'\n')
    return ''.join(rows).encode()
def literal_checks():
    assert string([0xd800,0x110000,0,65]).hex()=='efbfbdefbfbd0041'
    assert number('I',tuple(map(ord,'9223372036854775808')))==('i',0)
    assert number('D',tuple(map(ord,'-0')))==('f','8000000000000000')
    b=Builder();b.apply(event('BO'));b.apply(event('K','a'));b.apply(event('I','1'));b.apply(event('K','a'));b.apply(event('I','2'))
    try:b.apply(event('EO'))
    except Fault as f:assert f.name=='JsonParsingException' and b.stack==[None]
    else:raise AssertionError('duplicate not rejected')
    try:b.apply(event('T'))
    except Fault as f:assert f.name=='InvalidMaybeAccessException' and b.stack==[]
    else:raise AssertionError('sentry take')
    b.apply(event('BA'));b.apply(event('I','1'));b.apply(event('I','2'));b.apply(event('EA'));assert b.drain()=='a[i1,i2]'

if __name__=='__main__':
    literal_checks();print(len(cases()),'cases',len(expected().splitlines()),'event rows')
