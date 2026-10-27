"""Reviewed complete class body list cross-checked against compiler AST offsets."""
import hashlib
import json
from pathlib import Path

DEFINITIONS=[('beginObject',6,8),('objectKey',10,12),('endObject',14,27),('beginArray',29,31),('endArray',33,44),('putString',46,48),('putDouble',50,52),('putInteger',54,56),('putBoolean',58,60),('putNull',62,64),('putWhitespace',66,66),('putColon',68,68),('putComma',70,70),('stackSize',72,74),('takeTop',76,81),('push',83,85),('pop',87,89),('set',91,93),('pushSentry',95,97),('isSentry',99,101)]

def documents(data):
    decoder=json.JSONDecoder();s=data.decode();pos=0;out=[]
    while pos<len(s):
        while pos<len(s) and s[pos].isspace():pos+=1
        if pos==len(s):break
        node,pos=decoder.raw_decode(s,pos);out.append(node)
    return out

def manual(path):
    data=Path(path).read_bytes();lines=data.splitlines(keepends=True);out=[]
    for name,start,end in DEFINITIONS:
        a=sum(map(len,lines[:start-1]));b=sum(map(len,lines[:end]))
        while data[b-1:b] in (b'\n',b'\r'):b-=1
        chunk=data[a:b]
        if b'JsonBuilderStream::'+name.encode()+b'(' not in chunk:raise ValueError('manual body anchor '+name)
        out.append({'name':name,'start':start,'end':end,'begin':a,'finish':b,'sha256':hashlib.sha256(chunk).hexdigest()})
    return out

def specials(ast):
    records=[]
    def walk(n):
        if n.get('kind')=='CXXRecordDecl' and n.get('name')=='JsonBuilderStream' and n.get('completeDefinition'):records.append(n)
        for c in n.get('inner',[]):walk(c)
    for doc in documents(ast):walk(doc)
    if len(records)!=1:raise ValueError('one fixture class record')
    nodes=[{'name':n['name'],'kind':n['kind'],'type':n.get('type'),'used':n.get('isUsed',False),'defaulted':n.get('explicitlyDefaulted')} for n in records[0].get('inner',[]) if n.get('isImplicit') and n.get('kind') in ('CXXConstructorDecl','CXXMethodDecl','CXXDestructorDecl')]
    # Names come from compiler nodes; do not infer constructors by stripping
    # template/type spellings. All six actual lifecycle operations are expected.
    if len(nodes)!=6 or not all(n['used'] for n in nodes):raise ValueError('six used implicit lifecycle operations: '+repr(nodes))
    return nodes

def reconcile(path,ast):
    wanted=manual(path);methods=[];classes=[]
    def walk(n):
        if n.get('kind')=='CXXRecordDecl' and n.get('name')=='JsonBuilderStream' and n.get('completeDefinition'):classes.append(n)
        if n.get('kind')=='CXXMethodDecl' and not n.get('isImplicit') and any(x.get('kind')=='CompoundStmt' for x in n.get('inner',[])):
            r=n['range'];methods.append({'name':n['name'],'begin':r['begin']['offset'],'finish':r['end']['offset']+r['end']['tokLen']})
        for c in n.get('inner',[]):walk(c)
    for doc in documents(ast):walk(doc)
    expected=[{k:r[k] for k in ('name','begin','finish')} for r in wanted]
    if methods!=expected:raise ValueError('compiler/manual class bodies differ: '+repr(methods))
    if len(classes)!=1:raise ValueError('one complete native class')
    implicit=[]
    for n in classes[0].get('inner',[]):
        if n.get('isImplicit') and n.get('kind') in ('CXXConstructorDecl','CXXMethodDecl','CXXDestructorDecl'):
            implicit.append({'name':n['name'],'kind':n['kind'],'type':n.get('type'),'defaulted':n.get('explicitlyDefaulted'),'used':n.get('isUsed',False)})
    if not any(n['kind']=='CXXDestructorDecl' for n in implicit):raise ValueError('implicit destructor missing')
    return {'definitions':wanted,'implicit_special_members':implicit,'definition_data':classes[0].get('definitionData'),'scope':'only 20 JsonBuilderStream bodies; adjacent JsonStreamer and parser NOT selected'}
