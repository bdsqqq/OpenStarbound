#!/usr/bin/env python3
"""Coherent isolated corruptions must reach the claimed replay barrier."""
import copy,re
import acquire as lab

def controls():
 lab.verify();root=lab.OUT/'audit';lab.need(not root.exists(),'fresh corruption controls');root.mkdir();report=lab.load(lab.OUT/'report.typed');results=[]
 def reject(name,candidate,overrides,expected):
  try:lab.verify(candidate,overrides)
  except ValueError as error:
   lab.need(expected in str(error),'wrong rejection barrier '+name+': '+str(error));results.append({'name':name,'rejected':str(error)})
  else:raise ValueError('known failure escaped '+name)
 def replace(name,path,value,expected,receipt=False):
  bad=copy.deepcopy(report);dest=root/name;lab.write(dest,value);overrides={str(path):str(dest)};bad['artifacts' if str(path) in bad['artifacts'] else 'inputs'][str(path)]=lab.sha(dest)
  if receipt:
   rp=lab.Path(str(path).removesuffix('.stdout')+'.receipt');row=lab.load(rp);row['stdout']=lab.sha(dest);rd=root/(name+'-receipt');lab.dump(rd,row);overrides[str(rp)]=str(rd);bad['artifacts'][str(rp)]=lab.sha(rd)
  reject(name,bad,overrides,expected)
 bad=copy.deepcopy(report);bad['inputs'].pop(str(lab.ROOT/'source/core/StarLruCache.hpp'));reject('omitted-binding',bad,{},'exact input membership')
 path=lab.ROOT/'source/core/StarLruCacheHost.hpp';dest=root/'source-bytes';lab.write(dest,path.read_bytes()+b'corrupt');reject('changed-source',report,{str(path):str(dest)},'inputs drift')
 path=lab.OUT/'candidate.o';dest=root/'object-bytes';lab.write(dest,path.read_bytes()+b'corrupt');reject('changed-object',report,{str(path):str(dest)},'artifacts drift')
 path=lab.OUT/'candidate-ordered-1.receipt'
 for name,key,value,expected in [('bool-status','status',False,'strict command status'),('bool-pid','pid',True,'typed owned group'),('foreign-group','pgid',1,'typed owned group')]:
  row=lab.load(path);row[key]=value;replace(name,path,lab.codec.dumps(row).encode('ascii'),expected)
 for name,path,data,expected in [('model-semantics',lab.OUT/'candidate-ordered-1.stdout',b'wrong\n','640-row independent model mismatch'),('lifetime-semantics',lab.OUT/'lifetime-run.stdout',b'BROKEN\n','production unwind controls'),('protocol-semantics',lab.OUT/'controls-run.stdout',b'controls\t40\n','production malformed/unbounded/counter controls')]:replace(name,path,data,expected,receipt=True)
 path=lab.OUT/'candidate.map';raw=path.read_bytes();line=next(l for l in raw.splitlines() if re.search(rb'\s_sb_lru_run$',l) and b'#' not in l);changed=re.sub(rb'\[\s*[0-9]+\]',b'[  1]',line,count=1);lab.need(changed!=line,'changed controller owner');replace('controller-origin',path,raw.replace(line,changed,1),'fresh production/controller provider')
 lab.verify();lab.dump(root/'controls.typed',{'status':'TEN_COHERENT_CONTROLS_PASS','report_sha256':lab.sha(lab.OUT/'report.typed'),'controls':results});print('TEN_COHERENT_CONTROLS_PASS')

if __name__=='__main__':
 if lab.sys.argv[1:]==['--controls']:controls()
 elif not lab.sys.argv[1:]:lab.verify();print('STRICT_READONLY_PRODUCTION_RUNTIME_REPLAY_PASS')
 else:raise SystemExit('usage: audit.py [--controls]')
