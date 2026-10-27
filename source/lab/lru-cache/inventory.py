"""AST reconciliation, not a regex completeness claim; read-only on replay."""
import hashlib,json
HEADER_SHA='b0ca8540168e7c90d375c9f7b327c568bd2e3d1d9c5df99febaee9f5658cadd7'
BODIES={'LruCacheBase':(62,64),'maxSize':(67,69),'setMaxSize':(72,77),'currentSize':(80,82),'keys':(85,87),'values':(90,92),'ptr':(95,101),'set':(104,112),'remove':(115,117),'removeWhere':(120,124),'get':(128,139),'clear':(142,144)}
def roots(data):
 text=data.decode();decoder=json.JSONDecoder();pos=0;out=[]
 while pos<len(text):
  while pos<len(text) and text[pos].isspace():pos+=1
  if pos==len(text):break
  obj,pos=decoder.raw_decode(text,pos);out.append(obj)
 return out

def logical(n):
 name=n.get('name','')
 if n.get('kind')=='CXXConstructorDecl':return name.split('<',1)[0]
 return name

def reconcile(data,header):
 if hashlib.sha256(header).hexdigest()!=HEADER_SHA:raise ValueError('original header SHA')
 lines=header.splitlines(keepends=True);offsets=[0]
 for line in lines:offsets.append(offsets[-1]+len(line))
 found={};implicit=[];lambdas=set()
 def walk(n):
  kind=n.get('kind');name=logical(n);inner=n.get('inner',[])
  if kind in ('CXXMethodDecl','CXXConstructorDecl','CXXDestructorDecl'):
   if n.get('isImplicit') and ('LruCacheBase' in n.get('name','') or name=='operator='):
    implicit.append({'kind':kind,'name':name,'type':n.get('type'),'isUsed':n.get('isUsed',False),'defaulted':n.get('explicitlyDefaulted')})
   if name in BODIES and not n.get('isImplicit'):
    body=next((x for x in inner if x.get('kind')=='CompoundStmt'),None)
    if body:
     start=body['range']['begin'].get('offset');end=body['range']['end'].get('offset');a,b=BODIES[name]
     if start is not None and offsets[a-1]<=start<offsets[b]:
      if not offsets[a-1]<=end<offsets[b]:raise ValueError('AST body end '+name)
      found.setdefault(name,set()).add((start,end))
  if kind=='LambdaExpr':
   begin=n.get('range',{}).get('begin',{}).get('offset')
   if begin is not None and offsets[119]<=begin<offsets[124]:lambdas.add(begin)
  for child in inner:walk(child)
 for root in roots(data):walk(root)
 if set(found)!=set(BODIES) or any(len(x)!=1 for x in found.values()):raise ValueError('12 AST written-body reconciliation '+repr(found))
 if len(lambdas)!=1:raise ValueError('one nested filter lambda')
 return {'written_bodies':{k:{'lines':BODIES[k],'body_offsets':list(next(iter(found[k])))} for k in BODIES},'nested_filter_lambdas':len(lambdas),'implicit_declarations':implicit,'retained_dependencies':['OrderedMapWrapper','std::map','FlatHashMap','LinkedList','BlockAllocator','Star::function','native key/value/comparator/hash/allocator lifetimes'],'source_sha256':HEADER_SHA}

def selftest():
 assert logical({'kind':'CXXConstructorDecl','name':'LruCacheBase<OrderedMapType>'})=='LruCacheBase'
 assert logical({'kind':'CXXConstructorDecl','name':'LruCacheBase'})=='LruCacheBase'
 assert logical({'kind':'CXXMethodDecl','name':'get'})=='get'
 assert logical({'kind':'CXXConstructorDecl','name':'NearLruCacheBase<X>'})!='LruCacheBase'
 return 4
