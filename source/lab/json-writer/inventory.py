"""Manual declarations cross-checked against clang's complete class AST."""
import hashlib
import json
from pathlib import Path

DEFINITIONS = [
 ('JsonWriter',563,564),('beginObject',566,570),('objectKey',572,594),
 ('endObject',596,605),('beginArray',607,611),('endArray',613,616),
 ('putString',618,685),('putDouble',687,691),('putInteger',693,697),
 ('putBoolean',699,713),('putNull',715,721),('putWhitespace',723,727),
 ('putColon',729,733),('putComma',735,737),('startValue',749,756),
 ('indent',758,764),('pushState',767,769),('popState',772,782),
 ('currentState',784,789),('write',791,794),('isPrintable',797,799)]


def manual(path):
    data=Path(path).read_bytes();lines=data.splitlines(keepends=True)
    result=[]
    for name,start,end in DEFINITIONS:
        a=sum(map(len,lines[:start-1]))+len(lines[start-1])-len(lines[start-1].lstrip())
        b=sum(map(len,lines[:end-1]))+len(lines[end-1].rstrip())
        chunk=data[a:b]
        assert name.encode()+b'(' in chunk
        result.append({'name':name,'start':start,'end':end,'begin':a,'finish':b,
                       'sha256':hashlib.sha256(chunk).hexdigest()})
    return result


def documents(data):
    decoder=json.JSONDecoder();text=data.decode();pos=0;result=[]
    while pos<len(text):
        while pos<len(text) and text[pos].isspace():pos+=1
        if pos==len(text):break
        value,pos=decoder.raw_decode(text,pos);result.append(value)
    return result


def reconcile(path,ast):
    wanted=manual(path);classes=[]
    def walk(node):
        if node.get('kind') in ('CXXRecordDecl','ClassTemplateSpecializationDecl') and node.get('name')=='JsonWriter' and node.get('completeDefinition'):
            classes.append(node)
        for child in node.get('inner',[]):walk(child)
    for doc in documents(ast):walk(doc)
    # Only the template pattern; specializations additionally prove instantiated
    # special members but must not multiply the declared implementation count.
    patterns=[c for c in classes if not any(x.get('kind')=='TemplateArgument' for x in c.get('inner',[]))]
    if len(patterns)!=1:raise ValueError('one complete writer template pattern')
    methods=[]
    for node in patterns[0].get('inner',[]):
        if node.get('kind') in ('CXXMethodDecl','CXXConstructorDecl','CXXDestructorDecl') and not node.get('isImplicit'):
            if not any(x.get('kind')=='CompoundStmt' for x in node.get('inner',[])):raise ValueError('missing explicit body')
            r=node['range'];a=r['begin']['offset'];b=r['end']['offset']+r['end']['tokLen']
            name='JsonWriter' if node['kind']=='CXXConstructorDecl' else node['name']
            methods.append({'name':name,'begin':a,'finish':b})
    expected=[{k:r[k] for k in ('name','begin','finish')} for r in wanted]
    if methods!=expected:raise ValueError('manual/compiler definition ranges differ: '+repr(methods))
    implicit=[]
    for c in classes:
        for n in c.get('inner',[]):
            if n.get('isImplicit') and n.get('kind') in ('CXXConstructorDecl','CXXMethodDecl','CXXDestructorDecl'):
                implicit.append({'kind':n['kind'],'name':n['name'],'type':n.get('type'),
                                 'defaulted':n.get('explicitlyDefaulted'),'used':n.get('isUsed',False)})
    if not implicit:raise ValueError('no instantiated implicit special members')
    return {'definitions':wanted,'implicit_special_members':implicit,
            'definition_data':patterns[0].get('definitionData'),
            'scope':'only JsonWriter class; parser/base/header/foundation module NOT calibrated'}
