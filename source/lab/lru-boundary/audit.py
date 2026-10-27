#!/usr/bin/env python3
"""Strict read-only replay, including manifest membership; --controls records tests."""
import copy,hashlib,stat,sys
from pathlib import Path
sys.dont_write_bytecode=True
import acquire as lab

def verify(report=None,overrides=None):
 report=report or lab.load(lab.OUT/'report.typed')
 lab.same(report['inputs'],lab.load(lab.OUT/'inputs-before.typed'),'exact precompile input membership')
 paths={str(p) for p in lab.OUT.rglob('*') if p.is_file() and p!=lab.OUT/'report.typed' and 'audit' not in p.relative_to(lab.OUT).parts}
 lab.need(set(report['artifacts'])==paths,'exact acquisition artifact membership')
 for path in paths:
  s=Path(path).lstat();lab.need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'nonaliased acquisition product')
 for receipt_path in lab.OUT.glob('*.receipt'):
  row=lab.load(receipt_path);started=lab.load(str(receipt_path)[:-8]+'.started')
  lab.need(row['started_ns']==started['started_ns'] and type(row['started_ns'])is int and type(row['ended_ns'])is int and row['ended_ns']>=row['started_ns'],'command timestamps')
  lab.need(type(row['pgid'])is int and type(started['pid'])is int and type(started['pgid'])is int,'typed process identity')
 return lab.verify(report,overrides)

def controls():
 verify();root=lab.OUT/'audit';lab.need(not root.exists(),'fresh audit controls');root.mkdir()
 report=lab.load(lab.OUT/'report.typed');results=[]
 def reject(name,candidate,overrides=None):
  try:verify(candidate,overrides)
  except ValueError as error:results.append({'name':name,'rejected':str(error)})
  else:raise ValueError('known failure escaped '+name)
 bad=copy.deepcopy(report);bad['inputs'].pop(str(lab.HERE/'cache.hpp'));reject('omitted-input',bad)
 bad=copy.deepcopy(report);bad['artifacts'].pop(str(lab.OUT/'candidate.o'));reject('omitted-artifact',bad)
 reject('source-bytes',report,{str(lab.HERE/'cache.hpp'):str(lab.OUT/'corrupt-source')})
 reject('artifact-bytes',report,{str(lab.OUT/'candidate.o'):str(lab.OUT/'corrupt-artifact')})
 receipt=lab.OUT/'run-ordered-1.receipt';bad=copy.deepcopy(report);bad['artifacts'][str(receipt)]=lab.sha(lab.OUT/'corrupt-status')
 reject('bool-status',bad,{str(receipt):str(lab.OUT/'corrupt-status')})
 witness=lab.OUT/'unwind-run.stdout';receipt=lab.OUT/'unwind-run.receipt'
 bad=copy.deepcopy(report);bad['artifacts'][str(witness)]=lab.sha(lab.OUT/'corrupt-unwind-output');bad['artifacts'][str(receipt)]=lab.sha(lab.OUT/'corrupt-unwind-receipt')
 reject('coherent-unwind-output',bad,{str(witness):str(lab.OUT/'corrupt-unwind-output'),str(receipt):str(lab.OUT/'corrupt-unwind-receipt')})
 verify();lab.dump(root/'controls.typed',{'status':'STRICT_BOUNDARY_REPLAY_AND_SIX_CONTROLS_PASS','report_sha256':lab.sha(lab.OUT/'report.typed'),'audit_source_sha256':lab.sha(__file__),'controls':results})
 print('STRICT_BOUNDARY_REPLAY_AND_SIX_CONTROLS_PASS')

if __name__=='__main__':
 if sys.argv[1:]==['--controls']:controls()
 elif not sys.argv[1:]:verify();print('STRICT_READONLY_BOUNDARY_REPLAY_PASS')
 else:raise SystemExit('usage: audit.py [--controls]')
