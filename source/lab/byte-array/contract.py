#!/usr/bin/env python3
"""Independent source-derived finite Apple native contract; never reads native output to model it."""
import argparse
import hashlib
import json
import pathlib

PATTERN = bytes.fromhex('80ff01007f41a510')
BACKING = PATTERN * 8
MASK = (1 << 64) - 1

def corpus():
    rows = []
    def add(action, n=0, p=0, q=0):
        rows.append(dict(case=f'b{len(rows)}', options=dict(action=action,n=n,p=p,q=q)))
    add('default')
    for p in (0,1,7,8,33,65,129,256): add('reserve_first',p=p)
    for n in (1,3,7,64,127):
        for p in (n,n+1,8,17,256): add('reserve_growth',n,p)
    add('empty_move')
    add('cstring')
    for p in (0,1): add('cstring_null',p=p)
    for n in range(9):
        for op in ('access','move_ctor','move_assign','self','reset','clear','resize_write','fill','append_self','append_byte','push','copy_all','hash','stream'): add(op,n)
        if n:
            for op in ('fill_ctor','ptr_ctor','copy_ctor','copy_assign'): add(op,n)
        for p in (0,3,65,129,256): add('reserve',n,p)
        for p in (0,3,12,65): add('resize_fill',n,p)
        for p in (0,3,12): add('fill_size',n,p)
        for p in (0,1,3):
            for op in ('append_ptr','append_array','copy_len'): add(op,n,p)
        for p in (0,2,12):
            for q in (0,3):
                add('copy_range',n,p,q); add('write',n,p,q)
        for p in (0,1,9):
            for op in ('trim_left','trim_right','at'): add(op,n,p)
        for p in (0,n):
            for op in ('insert','insert_iter'): add(op,n,p)
        if n:
            for p in (0,1,n):
                for q in (1,3): add('sub',n,p,q)
            for p in (0,1,n,n+1):
                for op in ('left','right'):
                    if p or op=='right': add(op,n,p)
        for p in (0,1,5):
            for q in (0,1,2): add('compare',n,p,q)
    for n in (0,1,2,5):
        for p in (0,1,2,5):
            for q in (0,1):
                for op in ('and','or','xor'): add(op,n,p,q)
            for q in range(6): add('custom',n,p,q)
    return rows

def grown(cap, request):
    if request <= cap: return cap
    return max(cap*2,request,8) if cap else request

def model(o):
    op,n,p,q = (o[k] for k in ('action','n','p','q'))
    a=bytearray(BACKING[:n]); cap=64; value=''; extra=''; calls=0; outcome='ok'
    if op=='default': a=bytearray(); cap=0; value='1,1,1,1,1'
    elif op=='reserve_first': a=bytearray(); cap=p
    elif op=='reserve_growth': a=bytearray(); cap=grown(n,p)
    elif op=='empty_move': a=bytearray(); cap=0; extra='1,1'
    elif op=='cstring': a=bytearray(b'A\x80'); cap=2
    elif op=='cstring_null': a=bytearray(b'A\x80\0' if p else b'\0'); cap=len(a)
    elif op=='access':
        a=bytearray(x^0x11 for x in a); value=a.hex(); extra=f'{n},{n},{int(n==0)}'
    elif op=='fill_ctor': a=bytearray([0xa5]*n); cap=n
    elif op=='ptr_ctor': cap=n
    elif op=='copy_ctor': cap=n; extra=a.hex()
    elif op=='move_ctor': extra='0,0,1'
    elif op=='copy_assign': value='1'; extra=a.hex()
    elif op=='move_assign': value='1'; extra='0,0,1'
    elif op=='self': value='1,1'
    elif op=='reset': a=bytearray(); cap=0
    elif op=='clear': a=bytearray()
    elif op=='reserve': cap=grown(cap,p)
    elif op=='resize_fill':
        a=a[:p]+bytearray([0xa5]*max(0,p-n)); cap=grown(cap,p)
    elif op=='resize_write': a+=b'B'*3
    elif op=='fill': a=bytearray([0xa5]*n)
    elif op=='fill_size': a=bytearray([0xa5]*p)
    elif op=='append_ptr': a+=bytes.fromhex('ff0142')[:p]
    elif op=='append_array': a+=BACKING[:p]
    elif op=='append_self': a+=bytes(a)
    elif op in ('append_byte','push'): a.append(0xfe)
    elif op in ('copy_all','copy_len','copy_range'):
        dest=bytearray(b'Z'*16)
        if op=='copy_all': chunk=a
        elif op=='copy_len': chunk=a[:p]
        else: chunk=a[p:p+q]
        dest[:len(chunk)]=chunk; value=dest.hex()
    elif op=='write':
        a=bytearray(BACKING[:max(n,p+q)]); a[p:p+q]=bytes.fromhex('ff0142')[:q]
    elif op in ('sub','left','right'):
        start=p if op=='sub' else 0 if op=='left' or p>n else n-p
        length=q if op=='sub' else p if op=='left' else n
        count=n if start==0 and length>=n else min(n,start+length)
        assert count>0 and start+count<=64
        a=bytearray(BACKING[start:start+count]); cap=count
    elif op=='trim_left': a=a[p:]
    elif op=='trim_right': a=a[:max(0,n-p)]
    elif op in ('insert','insert_iter'):
        a[p:p]=b'\xfe'
        if op=='insert_iter': value=str(p+1)
    elif op=='at':
        if p>=n: outcome='out_of_range'
        else: value=a[p:p+1].hex()
    elif op=='compare':
        b=bytearray(BACKING[:p])
        if q and p: b[0]=1 if q==1 else 255
        diff=next((i for i,(x,y) in enumerate(zip(a,b)) if x!=y),min(n,p))
        cmp=(a>b)-(a<b)
        value=f'{diff},{cmp},{int(cmp<0)},{int(cmp==0)},{int(cmp!=0)}'; extra=b.hex()
    elif op=='hash':
        h=0
        for x in a: h=(h*101+(x if x<128 else x-256))&MASK
        value=str(h)
    elif op=='stream': value='0x'+a.hex(); extra='1'
    elif op in ('and','or','xor','custom'):
        b=bytearray(x^0x55 for x in BACKING[:p]); lhs=a
        smaller,larger=(a,b) if n<p else (b,a)
        size=min(n,p); result=bytearray(); resultcap=size
        extend=bool(q%2) if op=='custom' else bool(q)
        for i in range(size):
            x,y=smaller[i],larger[i]
            if op=='custom':
                calls+=1; value+=f'{x:02x}/{y:02x};'
                if n: a[0]^=1
                if p: b[0]^=2
                if q//2==calls: outcome='same_token'; break
                z=(x+3*y)&255
            elif op=='and': z=x&y
            elif op=='or': z=x|y
            else: z=x^y
            result.append(z)
        if outcome=='same_token': a=lhs; extra=b.hex()
        else:
            if extend:
                resultcap=grown(resultcap,max(n,p)); result+=larger[size:]
            extra=lhs.hex()+':'+b.hex(); a=result; cap=resultcap
    else: raise ValueError('unknown action '+op)
    return dict(size=len(a),capacity=cap,null=(cap==0),bytes=a.hex(),value=value,extra=extra,calls=calls,outcome=outcome)

def expected(): return [dict(**c,**model(c['options'])) for c in corpus()]
def canonical(rows): return b''.join((json.dumps(r,sort_keys=True,separators=(',',':'))+'\n').encode('ascii') for r in rows)
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
    def bad(x): raise ValueError('nonfinite '+x)
    rows=[json.loads(line,object_pairs_hook=pairs,parse_constant=bad) for line in data.decode('ascii').splitlines()]
    want=expected()
    if len(rows)!=len(want): raise ValueError('case count')
    for actual,target in zip(rows,want):
        if not strict_equal(actual,target): raise ValueError('trace mismatch '+target['case'])
    return len(rows)

# Definition starts, not declarations. Every member overload is a separate entry.
CPP = (
 (6,'fromCString',('cstring',)),(10,'fromCStringWithNull',('cstring_null',)),(17,'withReserve',('reserve_first',)),
 (23,'default constructor',('default',)),(29,'fill constructor',('fill_ctor',)),(34,'pointer constructor',('ptr_ctor',)),
 (39,'copy constructor',('copy_ctor',)),(44,'move constructor',('move_ctor',)),(49,'destructor',('*',)),
 (53,'copy assignment',('copy_assign','self','default')),(62,'move assignment',('move_assign','self','default')),
 (74,'reset',('reset','default')),(83,'reserve',('reserve','reserve_first','reserve_growth')),(102,'resize filled',('resize_fill',)),
 (112,'fill sized',('fill_size','fill_ctor')),(119,'fill current',('fill',)),(123,'sub',('sub',)),
 (131,'left',('left',)),(135,'right',('right',)),(144,'trimLeft',('trim_left',)),(153,'trimRight',('trim_right',)),
 (160,'diffChar',('compare',)),(173,'compare',('compare',)),(210,'andWith',('and',)),(214,'orWith',('or',)),
 (218,'xorWith',('xor',)),(222,'insert index',('insert','insert_iter')),(230,'insert iterator',('insert_iter',)),
 (236,'push_back',('push',)),(241,'operator<',('compare',)),(245,'operator==',('compare',)),
 (249,'operator!=',('compare',)),(253,'ostream',('stream',)))
HPP = (
 (126,'clear',('clear','default')),(130,'resize raw',('resize_write',)),(135,'append array',('append_array','append_self')),
 (139,'append pointer',('append_ptr',)),(144,'appendByte',('append_byte',)),(149,'empty',('access','default')),
 (153,'ptr const',('*',)),(157,'ptr mutable',('ptr_ctor','write')),(161,'size',('*',)),(165,'capacity',('*',)),
 (169,'copyTo length',('copy_len',)),(174,'copyTo all',('copy_all',)),(178,'copyTo range',('copy_range',)),
 (186,'writeFrom',('write',)),(194,'combineWith',('custom','and','or','xor')),(216,'begin mutable',('access','insert_iter')),
 (220,'end mutable',('access','default')),(224,'begin const',('access','default')),(228,'end const',('access','default')),
 (232,'index mutable',('access',)),(237,'index const',('access','hash')),(242,'at',('at','access')),
 (249,'hash',('hash',)))
def source_map():
    cases=corpus(); mapping={}
    for path,defs in (('source/core/StarByteArray.cpp',CPP),('source/core/StarByteArray.hpp',HPP)):
        for line,name,actions in defs:
            mapping[f'{path}:{line}']=dict(definition=name,actions=list(actions),cases=[c['case'] for c in cases if '*' in actions or c['options']['action'] in actions])
    return mapping

def validate_source_map(mapping):
    if not strict_equal(mapping,source_map()): raise ValueError('source exercise map')
    return len(mapping)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('command',choices=('freeze','expected','check','map')); ap.add_argument('path',nargs='?'); args=ap.parse_args()
    if args.command=='expected': print(canonical(expected()).decode('ascii'),end='')
    elif args.command=='map': print(json.dumps(source_map(),sort_keys=True))
    elif args.command=='check':
        if not args.path: ap.error('check requires a JSONL path')
        print(json.dumps(dict(status='FINITE_TRACE_MATCH_ONLY',cases=check(pathlib.Path(args.path).read_bytes()))))
    else:
        data=canonical(expected()); print(json.dumps(dict(status='SOURCE_ONLY_FROZEN_CANDIDATE',cases=len(corpus()),compiled_definitions=len(CPP),header_definitions=len(HPP),expected_sha256=hashlib.sha256(data).hexdigest())))
if __name__=='__main__': main()
