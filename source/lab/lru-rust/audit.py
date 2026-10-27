#!/usr/bin/env python3
"""Read-only positive replay; isolated coherent failures use the same checker."""
import copy
import acquire as lab

def controls():
 lab.verify();root=lab.OUT/'audit';lab.need(not root.exists(),'fresh corruption controls');root.mkdir()
 report=lab.load(lab.OUT/'report.typed');results=[]
 def reject(name,candidate,overrides=None):
  try:lab.verify(candidate,overrides)
  except ValueError as error:results.append({'name':name,'rejected':str(error)})
  else:raise ValueError('known failure escaped '+name)
 bad=copy.deepcopy(report);bad['inputs'].pop(str(lab.BOUNDARY/'cache.hpp'));reject('omitted-input',bad)
 bad=copy.deepcopy(report);bad['artifacts'].pop(str(lab.OUT/'candidate.o'));reject('omitted-artifact',bad)
 for name,path in [('source',lab.BOUNDARY/'cache.hpp'),('artifact',lab.OUT/'candidate.o')]:
  corrupt=root/('corrupt-'+name);lab.write(corrupt,path.read_bytes()+b'corrupt');reject(name+'-bytes',report,{str(path):str(corrupt)})
 receipt=lab.OUT/'run-ordered-1.receipt'
 for name,key,value in [('bool-status','status',False),('bool-pid','pid',True),('foreign-group','pgid',1)]:
  row=lab.load(receipt);row[key]=value;corrupt=root/name;lab.dump(corrupt,row)
  bad=copy.deepcopy(report);bad['artifacts'][str(receipt)]=lab.sha(corrupt);reject(name,bad,{str(receipt):str(corrupt)})
 for name,path,data in [('semantic-output',lab.OUT/'run-ordered-1.stdout',b'wrong\n'),('unwind-output',lab.OUT/'unwind-run.stdout',b'BROKEN_UNWIND_CONTROLS_PASS\n'),('unbounded-output',lab.OUT/'controls-run.stdout',b'controls\t40\n')]:
  corrupt=root/name;lab.write(corrupt,data);bad=copy.deepcopy(report);bad['artifacts'][str(path)]=lab.sha(corrupt);reject('coherent-'+name,bad,{str(path):str(corrupt)})
 path=lab.OUT/'candidate.map';raw=path.read_bytes();symbol=lab.native_symbols.unique_symbol(lab.native_symbols.live_symbols(raw),b'_sb_lru_run')
 import re
 line=next(line for line in raw.splitlines() if re.search(rb'\s_sb_lru_run$',line) and b'#' not in line)
 # a plausible same-sized row with a native, not Rust, owner must fail origin replay.
 changed=re.sub(rb'\[\s*[0-9]+\]',b'[  1]',line,count=1)
 lab.need(changed!=line,'map negative actually changes owner')
 corrupt=root/'foreign-controller-map';lab.write(corrupt,raw.replace(line,changed,1));bad=copy.deepcopy(report);bad['artifacts'][str(path)]=lab.sha(corrupt)
 reject('coherent-foreign-controller-map',bad,{str(path):str(corrupt)})
 lab.verify();lab.dump(root/'controls.typed',{'status':'STRICT_REPLAY_ELEVEN_CORRUPTIONS_PASS','report_sha256':lab.sha(lab.OUT/'report.typed'),'controls':results})
 print('STRICT_REPLAY_ELEVEN_CORRUPTIONS_PASS')

if __name__=='__main__':
 if lab.sys.argv[1:]==['--controls']:controls()
 elif not lab.sys.argv[1:]:lab.verify();print('STRICT_READONLY_RUST_BRIDGE_REPLAY_PASS')
 else:raise SystemExit('usage: audit.py [--controls]')
