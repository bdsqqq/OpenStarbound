#!/usr/bin/env python3
"""SOURCE-ONLY DRAFT. Independent callback effects + source call continuations."""
import argparse
import copy
import hashlib
import json
import pathlib

ACTIONS = ('construct', 'destruct', 'resize', 'readfull', 'writefull', 'open',
           'close', 'sync', 'name', 'atEnd', 'size', 'readabs', 'writeabs',
           'readfullabs', 'writefullabs', 'readbytes', 'writebytes',
           'readbytesabs', 'writebytesabs', 'set', 'copy', 'assign')
LINES = (7,11,15,19,31,43,48,52,54,58,62,74,82,90,101,112,122,126,136,140,144,148)
CALLBACKS = ('pos','seek','read','write','end','name','absoluteRead','absoluteWrite',
             'fullRead','fullWrite','fullReadAbs','fullWriteAbs','size')
MAX = (1 << 64)-1  # native Apple 64-bit profile, not a portable size_t claim

def options(action, **kw):
    o = dict(action=action, mode=3, length=5, chunk=2, eof=False, null=False,
             dispatch='base', faultOp='', faultIndex=0, phase='', tag='IO', reentry=False)
    o.update(kw)
    return o

def corpus():
    rows=[]
    def add(o): rows.append(dict(case=f't{len(rows):05d}', options=o))
    for m in range(256):
        for a in ('construct','copy','assign','self','set','close','open'):
            add(options(a,mode=m))
    for a in ACTIONS:
        add(options(a))
    for a in ('readfull','writefull','readfullabs','writefullabs',
              'readbytes','writebytes','readbytesabs','writebytesabs'):
        for length in (0,4):
            for chunk in (0,2,4):
                for eof in (False,True): add(options(a,length=length,chunk=chunk,eof=eof))
    for a in ('readfull','writefull','readfullabs','writefullabs','readabs','writeabs'):
        add(options(a,length=0,null=True))
        add(options(a,length=MAX,chunk=0))
    for a in ('readfullabs','writefullabs','readbytesabs','writebytesabs'):
        add(options(a,dispatch='absolute'))
    for a in ('readbytes','writebytes','readbytesabs','writebytesabs'):
        for n in (0,4): add(options(a,length=n,dispatch='full',chunk=4))
    add(options('atEnd',dispatch='size'))
    add(options('open',dispatch='unequal'))
    add(options('open',dispatch='unequal',reentry=True))
    # Fixed over-approximation: unused fault sites remain intentional no-fault cases.
    for a in ('size','atEnd','readfull','writefull','readabs','writeabs','readfullabs','writefullabs',
              'readbytes','readbytesabs','writebytes','writebytesabs','open'):
        for op in CALLBACKS:
            for index in (1,2,3,4,5,6):
                for phase in ('before','after'):
                    for tag in ('IO','EOF','OTHER'):
                        dispatch=('unequal' if a=='open' else 'absolute' if op.startswith('absolute') and a not in ('readabs','writeabs') else 'full' if op.startswith('full') and 'bytes' in a else 'size' if op=='size' and a=='atEnd' else 'base')
                        add(options(a,dispatch=dispatch,
                                    faultOp=op,faultIndex=index,phase=phase,tag=tag,
                                    chunk=5 if dispatch=='full' else 2))
    return rows

class Fault(Exception):
    def __init__(self, tag, identity='same'): self.tag,self.identity=tag,identity

class Primitive:
    """Only callbacks mutate storage. A thrown callback still commits its effects."""
    def __init__(self,o):
        self.o=o; self.cursor=6; self.mode=o['mode']; self.output=bytearray(b'Q'*8)
        self.sink=bytearray(); self.writes=[]; self.events=[]; self.counts={}; self.io=0
    def snapshot(self):
        return dict(mode=self.mode,cursor=self.cursor,output=self.output.hex(),
                    sink=self.sink.hex(),writes=copy.deepcopy(self.writes))
    def call(self,op,kind='none',ptr=-1,length=0,arg=0,seekmode=0):
        index=self.counts.get(op,0)+1; self.counts[op]=index
        def ev(phase,n=0,value=0):
            self.events.append(dict(op=op,index=index,phase=phase,kind=kind,ptr=ptr,
                len=length,n=n,arg=arg,seekmode=seekmode,value=value,**self.snapshot()))
        def fails(phase):
            return (self.o['faultOp'],self.o['faultIndex'],self.o['phase'])==(op,index,phase)
        ev('before')
        if fails('before'): ev('throw'); raise Fault(self.o['tag'])
        n=0; value=0
        if op=='seek': self.cursor=(8+arg if seekmode==2 else arg)
        elif op=='pos': value=self.cursor
        elif op=='end': value=int(self.o['eof'])
        elif op=='size': value=8
        elif op=='name':
            if self.o['reentry']: self.mode=4
        elif op in ('read','write','absoluteRead','absoluteWrite',
                    'fullRead','fullWrite','fullReadAbs','fullWriteAbs'):
            self.io+=1
            n=min(length,self.o['chunk'])
            if n:
                if not 0<=ptr<=8 or n>8-ptr: raise ValueError('fixture byte bound')
                if op in ('read','absoluteRead','fullRead','fullReadAbs'):
                    data=bytes([64+self.io])*n
                    # Caller offset is used NOW, before any throwing return path.
                    if kind=='caller': self.output[ptr:ptr+n]=data
                    self.writes.append(f'{kind}/{ptr}/{data.hex()}')
                else: self.sink.extend(b'abcdefgh'[ptr:ptr+n])
            self.cursor+=n; value=n
        ev('mutated',n,value)
        if fails('after'): ev('throw',n,value); raise Fault(self.o['tag'])
        ev('return',n,value)
        return value

class Controller:
    """Source call plans. Continuations run only after a primitive returns."""
    def __init__(self,o): self.p=Primitive(o); self.o=o
    def size(self):
        p=self.p
        try:
            saved=p.call('pos'); p.call('seek',arg=0,seekmode=2)
            value=p.call('pos'); p.call('seek',arg=saved); return value
        except Fault as e:
            if e.tag in ('IO','EOF'): raise Fault('IO','wrapped') from e
            raise
    def absolute(self,read,ptr,n,kind,offset):
        p=self.p
        if self.o['dispatch']=='absolute':
            return p.call('absoluteRead' if read else 'absoluteWrite',kind,ptr,n,offset)
        saved=p.call('pos'); p.call('seek',arg=offset)
        r=p.call('read' if read else 'write',kind,ptr,n)
        p.call('seek',arg=saved)
        return r
    def full(self,read,absolute,ptr,n,kind):
        p=self.p
        if self.o['dispatch']=='full':
            p.call(('fullRead' if read else 'fullWrite')+('Abs' if absolute else ''),kind,ptr,n,-4 if absolute else 0)
            return
        if not absolute:
            r=p.call('read' if read else 'write',kind,ptr,n)
            if r<n: raise Fault('EOF' if p.call('end') else 'IO','new')
            return
        offset=-4
        while n:
            r=self.absolute(read,ptr,n,kind,offset)
            if r==0: raise Fault('IO','new')
            offset+=r; ptr+=r; n-=r
    def run(self):
        o=self.o; p=self.p; a=o['action']; value=None; outcome='OK'
        try:
            if a in ('construct','copy','assign','self'): pass
            elif a=='set': p.mode=o['mode']
            elif a=='close': p.mode=0
            elif a=='destruct': value=0 # external derived-close counter; no dead-field reads
            elif a=='sync': pass
            elif a=='resize': raise Fault('IO','new')
            elif a=='name': value='IODevice <SELF>'
            elif a=='open':
                if o['dispatch']=='unequal':
                    p.call('name'); raise Fault('IO','new')
            elif a=='size': value=self.size()
            elif a=='atEnd':
                # Narrow Apple compiler profile only: left operand first.
                pos=p.call('pos')
                size=p.call('size') if o['dispatch']=='size' else self.size()
                value=int(pos>=size)
            else:
                read=a.startswith('read'); absolute=a.endswith('abs'); n=o['length']
                bytewrapper='bytes' in a
                kind='temp' if read and bytewrapper else ('input' if not read else 'caller')
                if o['null'] or (bytewrapper and n==0): kind='null'
                ptr=0
                if a in ('readabs','writeabs'): value=self.absolute(read,ptr,n,kind,-4)
                elif bytewrapper and read and n==0: value=''
                else:
                    self.full(read,absolute,ptr,n,kind)
                    if bytewrapper and read:
                        data=bytearray(n); initialized=set()
                        for w in p.writes:
                            k,start,h=w.split('/'); start=int(start); chunk=bytes.fromhex(h)
                            if k=='temp': data[start:start+len(chunk)]=chunk; initialized.update(range(start,start+len(chunk)))
                        # No attempt to observe an uninitialized successful temporary.
                        if initialized!=set(range(n)): raise ValueError('undefined successful temporary')
                        value=data.hex()
        except Fault as e: outcome=e.tag+'/'+e.identity
        return dict(outcome=outcome,value=value,**p.snapshot(),events=p.events)

def expected():
    return [dict(**c,**Controller(c['options']).run()) for c in corpus()]

def canonical(rows): return b''.join((json.dumps(r,sort_keys=True,separators=(',',':'))+'\n').encode('ascii') for r in rows)
def source_map():
    cases=corpus()
    return {str(line):dict(action=a,cases=[c['case'] for c in cases if c['options']['action']==a]) for line,a in zip(LINES,ACTIONS)}
def validate_source_map(mapping):
    if not strict_equal(mapping,source_map()): raise ValueError('source exercise map')
    return 22

def strict_equal(a,b):
    if type(a) is not type(b): return False
    if isinstance(a,dict): return a.keys()==b.keys() and all(strict_equal(a[k],b[k]) for k in a)
    if isinstance(a,list): return len(a)==len(b) and all(strict_equal(x,y) for x,y in zip(a,b))
    return a==b

def check(data):
    def pairs(xs):
        d={}
        for k,v in xs:
            if k in d: raise ValueError('duplicate JSON key')
            d[k]=v
        return d
    rows=[json.loads(line,object_pairs_hook=pairs,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x))) for line in data.decode('ascii').splitlines()]
    want=expected()
    if len(rows)!=len(want): raise ValueError('case count')
    for actual,target in zip(rows,want):
        if not strict_equal(actual,target): raise ValueError('trace mismatch '+target['case'])
    return len(rows)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('command',choices=('freeze','expected','check','map')); ap.add_argument('path',nargs='?'); args=ap.parse_args()
    if args.command=='expected': print(canonical(expected()).decode('ascii'),end='')
    elif args.command=='map': print(json.dumps(source_map(),sort_keys=True))
    elif args.command=='check': print(json.dumps(dict(status='TRACE_MATCH_ONLY',cases=check(pathlib.Path(args.path).read_bytes()))))
    else:
        data=canonical(expected()); print(json.dumps(dict(status='SOURCE_ONLY_DRAFT',cases=len(corpus()),definitions=len(source_map()),expected_sha256=hashlib.sha256(data).hexdigest())))
if __name__=='__main__': main()
