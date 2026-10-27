#!/usr/bin/env python3
"""Read-only replay, including isolated semantic alternatives and coherent controls.
No subprocess creation. Hashes establish static consistency, not hostile attestation.
"""
import copy,hashlib,json,sys,tarfile
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];OUT=ROOT/'build/ttl-cache-native-r1'
sys.path.insert(0,str(HERE));import model

def need(ok,why):
 if not ok:raise AssertionError(why)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def readj(p):return json.loads(Path(p).read_text())
def compare(actual,expected):need(actual==expected,'independent public-state model')
def controls(rows,actual):
 source=(HERE/'model.py').read_text();mutants={
  'expiry-greater-or-equal':('captured-self.items[key][0]>self.ttl','captured-self.items[key][0]>=self.ttl'),
  'ptr-refresh-even-disabled':('if self.update:self.items[key][0]=self.stamp()','if True:self.items[key][0]=self.stamp()'),
  'get-ignore-zero-sentinel':('if self.items[key][0]==0 or self.update:','if self.update:'),
  'get-no-pre-eviction':('while len(self.items)>=self.limit:','while False:'),
  'cleanup-rereads-clock':('elif captured-self.items[key][0]>self.ttl:','elif self.now-self.items[key][0]>self.ttl:'),
  'cleanup-snapshots-ttl':('if a==4:self.ttl=b','if a==4:pass'),
  'cleanup-refresh-wrong-policy':('refresh=a==1 or (a==2 and key%2==0)','refresh=False'),
  'set-incorrectly-enforces-capacity':('stamp=self.stamp();self.items[key]=[stamp,value];self.items.move_to_end(key)','stamp=self.stamp();self.items[key]=[stamp,value];self.items.move_to_end(key)\n  while len(self.items)>self.limit:self.items.popitem(last=False)'),
 }
 findings={}
 for name,(old,new) in mutants.items():
  need(source.count(old)==1,'unique mutation '+name);ns={};exec(compile(source.replace(old,new),'<isolated-model-control>','exec'),ns)
  try:wrong=ns['expected'](rows)
  except (AssertionError,KeyError):wrong='control diverged before completing the valid frozen corpus'
  need(wrong!=actual,'undiscriminated semantic alternative '+name)
  mismatch=next((i for i,(a,b) in enumerate(zip(actual.splitlines(),wrong.splitlines())) if a!=b),None)
  findings[name]={'rejected':True,'first_differing_row':mismatch,'input':rows[mismatch] if mismatch is not None else None,'kind':'isolated model semantic alternative, NOT a compiled native mutant'}
 # Coherent whole-stream control, not merely a changed hash or a malformed row.
 need(model.expected(rows)==actual,'positive before controls')
 for col,value in ((1,'99999'),(6,'-'),(7,'wrong-result'),(9,'999')):
  parsed=[x.split('\t') for x in actual.splitlines()];parsed[10][col]=value
  wrong='\n'.join('\t'.join(x) for x in parsed)+'\n'
  rejected=False
  try:compare(wrong,model.expected(rows))
  except AssertionError:rejected=True
  need(rejected,'coherent changed stream accepted');findings['changed-column-'+str(col)]={'rejected':True,'kind':'isolated in-memory output control; parser still valid'}
 return findings

def semantic_replay():
 rows=model.corpus();corpus='\n'.join(rows)+'\n';need((OUT/'corpus.tsv').read_text()==corpus,'frozen corpus generation')
 expected=model.expected(rows);need((OUT/'expected.tsv').read_text()==expected,'independent expectation generation')
 actuals=[]
 for alias in ('ordered','hash'):
  for i in range(2):
   actual=(OUT/f'{alias}-{i}.stdout').read_text();compare(actual,expected);actuals.append(actual)
 need(len(set(actuals))==1,'alias/repeat equality')
 lines=(OUT/'lifecycle.stdout').read_text().splitlines();props=[x for x in lines if x.startswith('property\t')];need(len(props)==68 and all(x.endswith('\t1') for x in props),'68 native lifecycle properties')
 traces={x.split('\t')[1]:x.split('\t')[2] for x in lines if x.startswith('trace\t')}
 need(traces['actual-ordered']==traces['scripted-ordered'],'actual/script ordered native lifetimes')
 need(traces['actual-hash']==traces['scripted-hash'],'actual/script hash native lifetimes')
 return {'rows':len(rows),'streams':4,'native_lifecycle_properties':len(props),'controls':controls(rows,actuals[0])}

def verify():
 report=readj(OUT/'report.json');need(sha(OUT/'native')==report['binary']['sha256'],'primary artifact bytes')
 for path,h in report['source'].items():need(sha(path)==h,'source '+path)
 for path,h in readj(OUT/'inputs.json').items():need(sha(path)==h,'input '+path)
 need((HERE/'StarTtlCache.original.hpp').read_bytes()==(ROOT/'source/core/StarTtlCache.hpp').read_bytes(),'full header bytes: no changed method body tokens')
 receipts=list(OUT.glob('*.receipt.json'));need(len(receipts)==report['processes'],'exact command receipt membership')
 for p in receipts:
  r=readj(p);prefix=str(p)[:-len('.receipt.json')];plan=readj(prefix+'.plan.json');start=readj(prefix+'.started.json')
  need(type(r['pid']) is int and r['pid']>0 and r['pid']==r['pgid']==start['pid']==start['pgid'],'PID/PGID')
  need(r['started_ns']==start['started_ns'] and r['ended_ns']>=r['started_ns'],'process time')
  need(r['returncode']==plan['expected'] and not r['timed_out'] and r['group_gone'],'actual exit/group status')
  need(r['argv']==plan['argv'],'planned argv')
  for ext in ('stdout','stderr'):need(sha(prefix+'.'+ext)==r[ext+'_sha256'],'actual stdio '+ext)
  need(sha(prefix+'.stdin')==plan['stdin_sha256'],'actual stdin')
  need(r['tool_before']==r['tool_after']==plan['tool'],'tool identity stability');need(sha(r['tool_before']['resolved'])==r['tool_before']['sha256'],'live tool bytes')
 for path,h in report['products'].items():need(sha(path)==h,'product '+path)
 sem=semantic_replay();need(sem==report['semantic'],'semantic report regeneration')
 a=readj(OUT/'initial-archive.json');need(sha(a['archive'])==a['sha256'],'initial archive bytes')
 with tarfile.open(a['archive'],'r:gz') as t:
  for path,h in a['members'].items():need(hashlib.sha256(t.extractfile(path).read()).hexdigest()==h,'initial exact archive reconstruction')
 return {'status':'PASS read-only finite replay','rows':sem['rows'],'controls':len(sem['controls']),'receipts':len(receipts),'properties':sem['native_lifecycle_properties']}
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))
