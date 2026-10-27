"""Independent finite event/state model. Integers are raw 32-bit codepoints.

No native observation is an expected value. The event grammar deliberately
permits non-JSON streams, because the writer is not a structural validator.
"""
import copy
import json

# Each tuple is (name, pretty, failure, failure-index, callback, callback-index,
# mutation-index, events). Failure and callback indices are zero-based attempts.
def corpus():
    rows = []
    def add(name, pretty, events, fail='-', at=-1, cb='-', cat=-1, mi=1):
        rows.append((name, pretty, fail, at, cb, cat, mi, events))
    nested = ['B','K:61','C','A','S:78','Q','B','K:62','C','T','Q','K:63','C','N','E','Z','Q','K:64','C','F','E']
    for p in (0,1,2,7):
        add('nested-'+str(p),p,nested)
        add('empty-'+str(p),p,['B','E','A','Z','S:','K:','E','Z'])
        add('quirks-'+str(p),p,['Z','E','K:22,5c,0,61','C','D:2d,30,2e','Q','I:2b,30,30,37','W:0,9,feff','A','B','K:61','C','A','N','E','Z','E','Z'])
        add('copy-'+str(p),p,['A','T','COPY','Q','T','USE1','Q','F','Z','USE0','Q','N','Z','MOVE','USE1','E'])
        add('assign-'+str(p),p,['B','K:61','COPY','USE1','A','USE0','ASSIGN','Z','USE1','E'])
    add('uintmax',4294967295,['A','N','Q','T','Z','B','E','C','S:'])
    controls=list(range(0x20))+[0x20,0x21,0x22,0x23,0x2f,0x5b,0x5c,0x5d,0x7f,0x80,0x7ff,0x800,0xd7ff,0xd800,0xdbff,0xdc00,0xdfff,0xe000,0xffff,0x10000,0x10ffff]
    for i,c in enumerate(controls+[0x110000,0x7fffffff,0xffffffff]):
        for op in ('S','K','D','I','W'):
            add('cp-%s-%x'%(op,c),0,[op+':%x,61'%c,'N','E','Z'])
    for f in ('a','i','d'):
        for at in (0,1,2,3,5,8,13,21):
            add('throw-%s-%d'%(f,at),2,nested,fail=f,at=at)
            add('hex-throw-%s-%d'%(f,at),0,['S:0,1,22,5c,61','N','S:62'],fail=f,at=at)
    for op in ('S','K','D','I','W'):
        for cat in (0,1,2):
            add('mutate-%s-%d'%(op,cat),0,[op+':61,62,63','N'],cb='m',cat=cat)
    for cb in ('r','n','e','b','x'):
        for cat in (0,1,2,3,5):
            add('callback-%s-%d'%(cb,cat),2,nested,cb=cb,cat=cat)
        for cat in (1,2,3,8):
            add('live-indent-%s-%d'%(cb,cat),2,['B','K:61','E','A','N','Z'],cb=cb,cat=cat)
    return rows


def inputs():
    return ''.join('\t'.join(map(str,r[:7]))+'\t'+';'.join(r[7])+'\n' for r in corpus()).encode()


def units(c):
    # StarUnicode.hpp: Utf8OutputIterator::push, NOT utf8EncodeChar.
    # It passes surrogate values through and substitutes only >0x10ffff.
    if c>0x10ffff: c=0xfffd
    if c<0x80:return [c]
    if c<0x800:return [0xc0+(c>>6),0x80+(c&63)]
    if c<0x10000:return [0xe0+(c>>12),0x80+((c>>6)&63),0x80+(c&63)]
    return [0xf0+(c>>18),0x80+((c>>12)&63),0x80+((c>>6)&63),0x80+(c&63)]


class Stop(Exception):
    pass


class Sink:
    def __init__(self,row,mode):
        self.row=row; self.mode=mode; self.out=[]; self.log=[]
        self.a=0; self.i=0; self.failed=False; self.called=False
        self.active=None; self.data=[]
    def emit(self,w,c):
        if self.mode in ('u8','p8'):
            for b in units(c): self.assign(w,b,post=True)
        else:
            self.assign(w,c,post=False)
            if self.mode=='p32':self.increment(w)
    def increment(self,w):
        self.log.append('I:%d'%w.pos)
        n=self.i; self.i+=1
        if self.row[2]=='i' and n==self.row[3] and not self.failed:
            self.failed=True; raise Stop('increment')
        w.pos+=1
    def assign(self,w,c,post):
        probe=self.mode.startswith('p')
        # Utf8OutputIterator uses *m_position++ = byte. Postincrement precedes
        # assignment and a throwing increment prevents that byte's assignment.
        old=w.pos
        if probe and post:self.increment(w)
        if probe:
            self.log.append('A:%x:%d'%(c,old))
            n=self.a; self.a+=1
            if self.row[2]=='a' and n==self.row[3] and not self.failed:
                self.failed=True; raise Stop('assignment')
        else:n=-1
        try:
            self.out.append(c)
            if probe and not self.called and self.row[4]!='-' and n==self.row[5]:
                self.called=True
                self.log.append('CB:'+self.row[4])
                if self.row[4]=='m':
                    if self.row[6]<len(self.data):self.data[self.row[6]]=0x5a
                elif self.row[4]=='r': self.active.event('F',[])
                elif self.row[4]=='n': Writer(self,self.active.pretty).event('N',[])
                elif self.row[4]=='e': self.active.event('Z',[])
                elif self.row[4]=='b': self.active.event('B',[])
                elif self.row[4]=='x':
                    self.active.stack=[];self.active.pretty=7;self.active.pos=0
        finally:
            if probe and self.row[2]=='d':
                self.log.append('D:%d'%old)
                if n==self.row[3] and not self.failed:
                    self.failed=True;raise Stop('destructor')


class Writer:
    def __init__(self,sink,pretty):self.sink=sink; self.pretty=pretty; self.stack=[]; self.pos=0
    def clone(self):
        w=Writer(self.sink,self.pretty);w.stack=self.stack[:];w.pos=self.pos;return w
    def state(self):return self.stack[-1] if self.stack else 'top'
    def emit(self,c):self.sink.emit(self,c)
    def text(self,s):
        for c in s:self.emit(ord(c))
    def start(self):
        if self.state()=='ae':
            if self.pretty:self.emit(32)
        elif self.state()=='a':self.stack.append('ae')
    def indent(self):
        # Iteration consults live stack/pretty after each foreign assignment.
        i=0
        while i<len(self.stack)//2:
            j=0
            while j<self.pretty:self.emit(32);j+=1
            i+=1
    def pop(self,target):
        while self.stack:
            if self.stack.pop()==target:return
    def event(self,op,data):
        if op=='B':self.start();self.stack.append('o');self.emit(123)
        elif op=='A':self.start();self.stack.append('a');self.emit(91)
        elif op=='Z':self.pop('a');self.emit(93)
        elif op=='E':
            nonempty=self.state()=='oe';self.pop('o')
            if nonempty:
                if self.pretty:self.emit(10)
                self.indent()
            self.emit(125)
        elif op=='K':
            if self.state()!='oe':self.stack.append('oe')
            if self.pretty:self.emit(10)
            self.indent();self.emit(34)
            index=0;c=data[0];remain=len(data)-1
            while c and remain:
                self.emit(c);index+=1;c=data[index];remain-=1
            self.emit(34)
            if self.pretty:self.emit(32)
        elif op=='S':
            self.start();self.emit(34)
            index=0;c=data[0];remain=len(data)-1
            while remain:
                if (0x20<=c<=0x21) or (0x23<=c<=0x5b) or (0x5d<=c<=0x10ffff):self.emit(c)
                elif c in (34,92):self.emit(92);self.emit(c)
                elif c in {8:98,12:102,10:110,13:114,9:116}:self.emit(92);self.emit({8:98,12:102,10:110,13:114,9:116}[c])
                else:
                    if c>0x10ffff:raise Stop('unicode')
                    self.text('\\u%04x'%c)
                index+=1;c=data[index];remain-=1
            self.emit(34)
        elif op in ('D','I','W'):
            if op!='W':self.start()
            for i in range(len(data)-1):self.emit(data[i])
        elif op in ('T','F','N'):self.start();self.text({'T':'true','F':'false','N':'null'}[op])
        elif op=='C':
            self.emit(58)
            if self.pretty:self.emit(32)
        elif op=='Q':self.emit(44)
        else:raise ValueError(op)


def output_hex(data,mode):return ''.join(('%02x' if mode in ('u8','p8') else '%08x')%c for c in data)


def expected():
    result=[]
    for row in corpus():
        for mode in ('u32','u8','p32','p8'):
            sink=Sink(row,mode);ws=[Writer(sink,row[1]),None];active=0
            for i,event in enumerate(row[7]):
                error='-';what='-'
                try:
                    if event=='COPY':ws[1]=ws[active].clone()
                    elif event=='MOVE':ws[1]=ws[0].clone();ws[0].stack=[]
                    elif event=='ASSIGN':ws[0]=ws[1].clone()
                    elif event.startswith('USE'):active=int(event[-1])
                    else:
                        op,_,arg=event.partition(':')
                        sink.data=([int(x,16) for x in arg.split(',')] if arg else [])+[0xabc]
                        sink.active=ws[active];ws[active].event(op,sink.data)
                except Stop as exc:
                    kind=str(exc)
                    error='Star::UnicodeException' if kind=='unicode' else 'ProbeError'
                    what='(UnicodeException) Codepoint too big in hexStringFromUtf32' if kind=='unicode' else kind
                result.append('\t'.join([row[0],mode,str(i),output_hex(sink.out,mode),','.join(sink.log),error,what.encode().hex() if what!='-' else '-']))
    return ('\n'.join(result)+'\n').encode()


def literal_checks():
    assert units(0xd800)==[0xed,0xa0,0x80]
    assert units(0x110000)==[0xef,0xbf,0xbd]
    s=Sink(('literal',2,'-',-1,'-',-1,1,[]),'u32');w=Writer(s,2)
    for op,data in [('B',[]),('K',[97,0xabc]),('C',[]),('A',[]),('T',[]),('Q',[]),('F',[]),('Z',[]),('E',[])]:w.event(op,data)
    assert ''.join(map(chr,s.out))=='{\n  "a" : [true, false]\n}'
    s=Sink(('literal',0,'-',-1,'-',-1,1,[]),'u32');w=Writer(s,0)
    w.event('K',[34,92,0,97,0xabc]);w.event('S',[0,34,92,0xabc])
    assert s.out==[34,34,92,34,34,92,117,48,48,48,48,92,34,92,92,34]
    return True

if __name__=='__main__':
    literal_checks();print(json.dumps({'scenarios':len(corpus()),'observations':len(expected().splitlines())}))
