"""Finite source-derived oracle. Freeze before running native code; never learn outputs.

Valid Unicode cases use Python scalars only where the inspected native iterator
has the same decoding. Malformed examples have separate literal iterator anchors.
Substring endpoints require std::string live NUL backing; at(empty,0) excluded.
"""
import itertools
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPACE=' \t\n\r\ufeff'
def low(s):return ''.join(chr(ord(c)+32) if 'A'<=c<='Z' else c for c in s)
def hx(s):return (s.encode() if isinstance(s,str) else s).hex()
def ns(n):return 'npos' if n<0 else str(n)
def canon(rows):return ''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows).encode()
def fields(s,p,any=False):
    s=s.encode() if isinstance(s,str) else s;p=p.encode() if isinstance(p,str) else p
    if not p:return []
    out=[];beg=0
    while True:
        end=next((i for i in range(beg,len(s)) if s[i] in p),-1) if any else s.find(p,beg)
        if end<0:out.extend([s[beg:].hex(),str(beg),str(len(s)-beg)]);return out
        out.extend([s[beg:end].hex(),str(beg),str(end-beg)]);beg=end+(1 if any else len(p))
def boundary(s,pos,back):
    if not back and pos==len(s):return pos
    if back:
        if not pos:return 0
        pos-=1
    while s[pos] not in SPACE:
        if back and not pos:return 0
        pos+=-1 if back else 1
        if pos==len(s):return pos
    while s[pos] in SPACE:
        if back and not pos:return 0
        pos+=-1 if back else 1
        if pos==len(s):return pos
    return pos+1 if back and pos!=len(s) else pos

def corpus():
    cases=[];rows=[]
    def add(op,a='',b='',pos=0,ci=False,value=()):
        ident=f'{op}-{len(cases):05d}'
        cases.append([ident,op,hx(a),hx(b),str(pos),str(int(ci))]);rows.append({'id':ident,'value':[str(int(x)) if isinstance(x,bool) else str(x) for x in value]})
    a='a\0éZ'
    for i in range(17):
        v={0:['',True],1:[hx(a),True],2:[hx(a),hx(a),True],3:[hx(a),True],4:[hx('a')],5:[hx(a.encode()[1:-1]),True],6:[hx(a)],7:[hx(a)],8:[hx(a)],9:[hx('ABCD')],10:[hx('ABCDEFGH')],11:[hx(a),True,True],12:[hx(a),True,hx('Z\0éZ')],13:[hx(a)],14:[hx(a)],15:[hx('!'+a),True],16:[hx('!'+a),True]}[i]
        add('ctor',a,pos=i,value=v)
    words=['','a','A','é','É','😀','a\0b','é,,x,','ababa',' \tX\ufeffy\n','\v\fZ']+[''.join(x) for n in (1,2,3) for x in itertools.product('aB,',repeat=n)]
    for s in words:
        add('inspect',s,value=[hx(s),len(s.encode()),len(s),len(s),True,not s,hx(s),True,True,*map(ord,s)])
        # std::string owns a live NUL at data()+size; driver binds raw-pointer iterator.
        add('substr',s,'0',len(s),value=[''])
        add('throw-substr',s,pos=len(s)+1,value=['OutOfRangeException',hx(f'(OutOfRangeException) out of range in StringView::substr({len(s)+1}, 0)')])
        if s:
            for endpos in (len(s),len(s)+1):add('throw-at',s,pos=endpos,value=['OutOfRangeException',hx(f'(OutOfRangeException) Out of range in StringView::at({len(s)-1})')])
        for pos in range(len(s)):
            add('at',s,pos=pos,value=[ord(s[pos]),ord(s[pos])])
            for n in (0,1,len(s)+2):add('substr',s,str(n),pos,value=[hx(s[pos:pos+n])])
        for pos in range(len(s)+1):
            add('substr-default',s,pos=pos,value=[hx(s[pos:])])
            for back in (False,True):add('boundary',s,pos=pos,ci=back,value=[boundary(s,pos,back)])
            for p in ('','a','éB'):
                pred=lambda c: c in (p or SPACE)
                add('of',s,p,pos,value=[ns(next((i for i in range(pos,len(s)) if pred(s[i])),-1)),ns(next((i for i in range(pos,len(s)) if not pred(s[i])),-1))])
        for p in ('','a','B',',','é','aa','aba','😀','\0'):
            for ci in (False,True):
                t,q=(low(s),low(p)) if ci else (s,p)
                for pos in sorted({0,len(s),len(s)+2}):
                    add('search',s,p,pos,ci,[ns(t.find(q,pos) if q else 0),ns(t.rfind(q) if q else 0),q in t,t.startswith(q),t.endswith(q),t==q,low(s)==low(p),(t>q)-(t<q),True])
            for any in (False,True):add('any' if any else 'split',s,p,value=fields(s,p,any))
        for c in ('a','B','é','É',' ','\ufeff','\v','\f','\0'):
            for ci in (False,True):
                t,q=(low(s),low(c)) if ci else (s,c)
                for pos in sorted({0,len(s),len(s)+2}):
                    add('char',s,str(ord(c)),pos,ci,[ns(t.find(q,pos)),ns(t.rfind(q)),t.startswith(q),t.endswith(q),c in s,(c in SPACE if not s else c in s)])
        for p in ('','a',s,'é'):
            add('free',s,p,value=[s==p.split('\0')[0],s==p,s==p,s==p,s!=p,s.encode()<p.encode(),hx(s),True,hx(s)])
    for any in (False,True):
        add('callback','a,b,c,','',0,any,[hx('a'),0,1,hx('b'),2,1,'split-marker',True])
        add('callback','a,b,c,','',1,any,[hx('a'),0,1,*fields('q::r:',':',any),hx('b'),2,1,hx('c'),4,1,'',6,0])
        add('callback','a,b,c,','',2,any,[hx('a'),0,1,hx('X'),2,1,hx('c'),4,1,'',6,0])
        add('callback','a,b,c,','u,v,w,',3,any,[hx('a'),0,1,hx('v'),2,1,hx('w'),4,1,'',6,0])
    # Native iterator consumes each malformed byte separately; validity/length
    # use different helpers. These anchors are traced in StarUnicode.*.
    for raw,length,scalars in [(b'\xff',1,[65533]),(b'\xc3',1,[65533]),(b'\xc0\x80',2,[65533,65533]),(b'\xe2A',2,[65533,65]),(b'\xed\xa0\x80',3,[65533]*3)]:
        add('invalid',raw,value=[False,length,*scalars])
    return cases,rows

def check(data):
    want=corpus()[1]
    try:got=[json.loads(x) for x in data.splitlines()]
    except Exception as e:raise ValueError('invalid JSONL') from e
    if len(got)!=len(want):raise ValueError('record count')
    for a,b in zip(got,want):
        if a!=b:raise ValueError(f'{b["id"]}: expected {b}, observed {a}')
    return len(want)

def source_map():
    # Concrete source definitions, not declarations. Parent inventories independently.
    import re
    lines=(HERE/'StarStringView.original.cpp').read_text().splitlines()
    defs=[(i+1,l) for i,l in enumerate(lines) if re.match(r'^(?:String::String|String& String::operator|StringView::StringView|[\w:&<> *]+ (?:StringView::|operator|fmt::formatter))',l)]
    cases,_=corpus()
    mappings=[]
    for line,s in defs:
        if 'StringView::StringView' in s:op='ctor'
        elif 'String::' in s:op='ctor'
        elif 'Char ' in s and any(x in s for x in ('endsWith(', 'beginsWith(', 'find(', 'findLast(')):op='char'
        elif 'Split' in s:op='split' if 'Any' not in s else 'any'
        elif 'findNextBoundary' in s:op='boundary'
        elif 'findFirst' in s:op='of'
        elif 'substr' in s:op='substr'
        elif 'operator[]' in s or '::at(' in s:op='at'
        elif 'hasChar' in s:op='char'
        elif any(x in s for x in ('find(','findLast(','endsWith(','beginsWith(','contains(','compare(','equals','equalsIgnore')):op='search'
        elif 'operator=' in s and 'StringView::' in s or 'takeUtf8' in s:op='ctor'
        elif 'operator' in s or 'formatter' in s:op='free'
        else:op='inspect'
        mappings.append({'line':line,'definition':s,'evidence_ids':[c[0] for c in cases if c[1]==op]})
    return mappings
