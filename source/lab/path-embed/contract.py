"""Independent byte corpus; codec bytes come only from the separate native leaves."""
import base64
NAMES=('None','Gzip','Zlib','Zstd')
def cases():
    values=[('empty',b'')]+[('byte-'+str(i),bytes([i])) for i in range(256)]
    values += [('all-bytes',bytes(range(256))),('nul-tail',b'a\0%:?;/\xff'),('utf8','café/雪?🙂'.encode()),('mixed',b'%:?;/literal\0\x80\xff')]
    # SSO vicinity, base64 triples, and codec 32 KiB chunk crossings are inputs,
    # never a narrowed acceptance domain or a claim about all allocations.
    for n in (2,3,4,15,16,21,22,23,24,31,32,63,64,127,128,255,256,1023,1024,32767,32768,32769):
        values += [('escapes-'+str(n),(b'%:?;/'*((n+4)//5))[:n]),('plain-'+str(n),b'x'*n)]
    rows=[(name,'E',-1,data) for name,data in values]
    cv=[b'',b'\0',b'\xff\xff',b'\xfb\xff\xff',b'a',b'ab',b'abc',b'abcd',bytes(range(256)),b'a\0b\0%:?;/\xff',b'hello world'*100,b'Z'*32769]
    rows += [('compress-'+str(i)+'-'+str(m),'C',m,b) for i,b in enumerate(cv) for m in range(4)]
    return rows

def inputs():return ''.join(f'{name}\t{op}\t{m}\t{b.hex()}\n' for name,op,m,b in cases()).encode()
def escape(b):
    mapping={37:b'%%',58:b'%c',63:b'%q',59:b'%s',47:b'%b'}
    return b''.join(mapping.get(x,bytes([x])) for x in b)
def expected(leaf):
    rows=leaf.decode().splitlines(); wanted=[(n,m) for n,o,m,b in cases() if o=='C' and m in (2,3)]
    parsed={}
    if len(rows)!=len(wanted):raise ValueError('leaf row count')
    for row,(name,m) in zip(rows,wanted):
        key,code,h=row.split('\t')
        if key!=name or code!='leaf':raise ValueError('leaf order/type')
        parsed[name]=bytes.fromhex(h)
    result=[f'enum-{i}\tok\t{n.encode().hex()}\n' for i,n in enumerate(NAMES)]
    for name,op,m,b in cases():
        code='ok'
        if op=='E':v=escape(b)
        elif m==1:code='StarException';v=b'(StarException) Compressing data in gzip is unsupported.'
        else:
            raw=b if m==0 else parsed[name]
            v=(b'' if m==0 else (b'zlib;' if m==2 else b'zstd;'))+base64.urlsafe_b64encode(raw).rstrip(b'=')
        result.append(f'{name}\t{code}\t{v.hex()}\n')
    return ''.join(result).encode()
def check(actual,wanted):
    if actual!=wanted:
        a=actual.splitlines();b=wanted.splitlines()
        raise ValueError('ordered byte mismatch at '+str(next((i for i,(x,y) in enumerate(zip(a,b)) if x!=y),min(len(a),len(b)))))
