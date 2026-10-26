"""Bounded C++ lexical inventory; source/symbol presence is not branch coverage."""
import hashlib,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
COUNTS={'StarFile.cpp':34,'StarFile_unix.cpp':30,'StarFile_windows.cpp':30}


def mask_cpp(text):
    """Retain offsets/newlines while excluding comments and literal contents."""
    result=list(text);i=0
    while i<len(text):
        end=None
        if text.startswith('//',i):
            end=text.find('\n',i);end=len(text) if end<0 else end
        elif text.startswith('/*',i):
            end=text.find('*/',i+2)
            if end<0:raise ValueError('unterminated comment')
            end+=2
        elif text.startswith('R"',i):
            match=re.match(r'R"([^\s()\\]{0,16})\(',text[i:])
            if not match:raise ValueError('unsupported raw literal')
            closing=')'+match.group(1)+'"';end=text.find(closing,i+match.end())
            if end<0:raise ValueError('unterminated raw literal')
            end+=len(closing)
        elif text[i] in ('"',"'"):
            quote=text[i];end=i+1
            while end<len(text):
                if text[end]=='\\':end+=2
                elif text[end]==quote:end+=1;break
                else:end+=1
            else:raise ValueError('unterminated literal')
        if end is None:i+=1;continue
        for j in range(i,end):
            if result[j]!='\n':result[j]=' '
        i=end
    return ''.join(result)


def generate(root=ROOT):
    result={}
    for name,count in COUNTS.items():
        text=(root/'source/core'/name).read_text();masked=mask_cpp(text)
        lines=text.splitlines(keepends=True);masked_lines=masked.splitlines(keepends=True)
        offsets=[];offset=0
        for line in lines:offsets.append(offset);offset+=len(line)
        rows=[]
        # These frozen TUs use column-zero, non-template File definitions. The
        # compiler-symbol check independently challenges this bounded grammar.
        for i,line in enumerate(masked_lines):
            if not re.match(r'^(?!\s)(?:[^\n]*\s)?File::~?\w+\(',line):continue
            opening=masked.find('{',offsets[i]);semicolon=masked.find(';',offsets[i])
            if opening<0 or 0<=semicolon<opening:continue
            depth=1;end=opening+1
            while end<len(masked) and depth:
                depth+=(masked[end]=='{')-(masked[end]=='}');end+=1
            if depth:raise ValueError('unclosed definition')
            j=text.count('\n',0,end-1)
            body=''.join(lines[i:j+1])
            rows.append(dict(line=i+1,endLine=j+1,signature=lines[i].strip(),sha256=hashlib.sha256(body.encode()).hexdigest()))
        if len(rows)!=count:raise ValueError((name,len(rows),count))
        result[name]=rows
    return result


def check():
    if json.loads((HERE/'source-map.json').read_text())!=generate():raise ValueError('inventory drift')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--write',action='store_true');mode.add_argument('--check',action='store_true');args=parser.parse_args()
    if args.write:(HERE/'source-map.json').write_text(json.dumps(generate(),indent=2)+'\n')
    else:check()
