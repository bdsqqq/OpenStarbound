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


def digest(data):
    return hashlib.sha256(data).hexdigest()


ORIGINAL_SHA='401858755ca3694e6ac4f07e44808a268c4b9caa2a75cec7d8db32f2176086c2'
HEADER_SHA='fa034ae7c45748377a00775ac3b4390b4f21d54835e8eac063e44a4e8289e9af'
WRAPPER_SHA='00e312e46575079e8e997b870e74544e7558b84c7b6badd68c4bc53eff7ee8f3'
SELECTED_RENAMES=(('FilePrototype','FileRust'), ('"native.hpp"','"StarFileHost.hpp"'),
                  ('file_host_run','star_file_run'), ('file_host_count','star_file_call_count'),
                  ('file_host_fn','StarFileHost'))


def definitions(text):
    """Column-zero File definitions only; lexical masking preserves offsets."""
    masked=mask_cpp(text)
    lines=text.splitlines(keepends=True);masked_lines=masked.splitlines(keepends=True)
    offsets=[];offset=0
    for line in lines:offsets.append(offset);offset+=len(line)
    rows=[];consumed=0
    for i,line in enumerate(masked_lines):
        if offsets[i]<consumed:continue
        if not re.match(r'^(?!\s)(?:[^\n]*\s)?File::~?\w+\(',line):continue
        opening=masked.find('{',offsets[i]);semicolon=masked.find(';',offsets[i])
        if opening<0 or 0<=semicolon<opening:continue
        depth=1;end=opening+1
        while end<len(masked) and depth:
            depth+=(masked[end]=='{')-(masked[end]=='}');end+=1
        if depth:raise ValueError('unclosed definition')
        consumed=end
        j=text.count('\n',0,end-1)
        body=''.join(lines[i:j+1])
        rows.append(dict(line=i+1,endLine=j+1,signature=lines[i].strip(),sha256=digest(body.encode())))
    return rows


def conditional(text,root):
    # This is an explicit production envelope, not a general preprocessor.
    # Reject other selectors/nesting rather than granting a source-drift waiver.
    directives=list(re.finditer(r'^\s*#\s*(if\w*|else|elif|endif)\b[^\n]*',mask_cpp(text),re.M))
    if not directives:return None
    expected=['#ifdef STAR_USE_RUST_FILE','#else','#endif']
    if [m.group().strip() for m in directives]!=expected:
        raise ValueError('unsupported File selector branches')
    if not text.startswith(expected[0]+'\n') or not text.endswith('\n#endif\n'):
        raise ValueError('invalid outer File selector')
    # Exactly one separator newline belongs to the envelope, not either input.
    selected,native=text[len(expected[0])+1:-len('#endif\n')].split('#else\n')
    if not selected.endswith('\n') or not native.endswith('\n'):
        raise ValueError('missing branch separator')
    selected=selected[:-1];native=native[:-1]
    lab=root/'source/lab/file'
    original=(lab/'StarFile.original.cpp').read_bytes()
    wrappers=(lab/'host/wrappers.cpp').read_bytes()
    header=(root/'source/core/StarFile.hpp').read_bytes()
    for label,data,pin in [('original',original,ORIGINAL_SHA),('header',header,HEADER_SHA),('qualified wrappers',wrappers,WRAPPER_SHA)]:
        if digest(data)!=pin:raise ValueError(label+' fidelity drift')
    if native.encode()!=original:raise ValueError('native fallback fidelity drift')
    renamed=wrappers.decode()
    for old,new in SELECTED_RENAMES:renamed=renamed.replace(old,new)
    if selected!=renamed:raise ValueError('selected wrapper fidelity drift')
    logical=definitions(original.decode());physical=definitions(text)
    selected_rows=definitions(selected);native_rows=definitions(native)
    if (len(logical),len(physical),len(selected_rows),len(native_rows))!=(34,68,34,34):
        raise ValueError('missing File alternative')
    if [r['signature'] for r in selected_rows]!=[r['signature'] for r in logical]:
        raise ValueError('File mode order drift')
    return logical,dict(
        schemaVersion=1,selector='STAR_USE_RUST_FILE',
        logicalSource='source/lab/file/StarFile.original.cpp',logicalSourceSha256=ORIGINAL_SHA,
        physicalSource='source/core/StarFile.cpp',physicalSourceSha256=digest(text.encode()),
        headerSource='source/core/StarFile.hpp',headerSha256=HEADER_SHA,
        qualifiedWrapperSource='source/lab/file/host/wrappers.cpp',qualifiedWrapperSha256=WRAPPER_SHA,
        physicalDefinitions=68,logicalDefinitions=34,selectedAlternatives=34,
        alternatives=[dict(mode=i,selected=physical[i],native=physical[i+34]) for i in range(34)])


def generate(root=ROOT):
    result={};branches=None
    for name,count in COUNTS.items():
        text=(root/'source/core'/name).read_bytes().decode()
        branch=conditional(text,root) if name=='StarFile.cpp' else None
        if branch:rows,branches=branch
        else:rows=definitions(text)
        if len(rows)!=count:raise ValueError((name,len(rows),count))
        result[name]=rows
    # Legacy keys remain frozen-original coordinates: host/generate.py slices
    # StarFile.original.cpp with them. Physical alternatives must never replace them.
    if branches:result['_conditional']=branches
    return result


def check():
    if json.loads((HERE/'source-map.json').read_text())!=generate():raise ValueError('inventory drift')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--write',action='store_true');mode.add_argument('--check',action='store_true');args=parser.parse_args()
    if args.write:(HERE/'source-map.json').write_text(json.dumps(generate(),indent=2)+'\n')
    else:check()
