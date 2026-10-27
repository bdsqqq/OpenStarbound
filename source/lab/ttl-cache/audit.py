#!/usr/bin/env python3
"""Pinned supplemental replay. No compiler/native/game/subprocess launches.
The original acquisition files are frozen; this auditor was added afterward.
"""
import hashlib,json,re,sys,tarfile
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];OUT=ROOT/'build/ttl-cache-native-r1'
sys.path.insert(0,str(HERE));import verify
sys.path.insert(0,str(HERE.parent/'path-embed-replay'));import sdk_witness
# Supplied externally to avoid circularly hashing the auditor into its own pin.
REPORT=sys.argv[1] if __name__=='__main__' and len(sys.argv)==2 else None
SDK='/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk'

def need(ok,msg):
 if not ok:raise AssertionError(msg)
def sha(data):return hashlib.sha256(data).hexdigest()
def audit(read=lambda p:Path(p).read_bytes()):
 need(type(REPORT) is str and re.fullmatch('[a-f0-9]{64}',REPORT),'supply independent report sha256 as sole argument')
 report=read(OUT/'report.json');need(sha(report)==REPORT,'independent report pin')
 result=verify.verify()
 for p in OUT.glob('*.receipt.json'):
  r=json.loads(read(p));need(type(r['returncode']) is int and r['returncode']==0,'typed normal exit')
  need(type(r['timed_out']) is bool and not r['timed_out'],'typed timeout')
  need(type(r['group_gone']) is bool and r['group_gone'],'typed group cleanup')
  for k in ('pid','pgid','started_ns','ended_ns'):need(type(r[k]) is int and r[k]>0,'typed '+k)
 source=read(HERE/'native.cpp').decode();defines=re.findall(r'^#define (\w+) (\w+)$',source,re.M)
 need(defines==[('Time','ScriptTime'),('Random','ScriptRandom'),('TtlCacheBase','ScriptTtlCacheBase'),('TtlCache','ScriptTtlCache'),('HashTtlCache','ScriptHashTtlCache')],'only dependency/type name substitution')
 need(source.index('#include "StarTtlCache.hpp"')<source.index('#define Time'),'prerequisite includes before proxies')
 hdr=read(HERE/'StarTtlCache.original.hpp');need(hdr==read(ROOT/'source/core/StarTtlCache.hpp'),'unchanged full class/header/aliases')
 need(hdr.count(b'TtlCacheBase<LruCacheType>::')==19,'all nineteen written definitions retained')
 recipe=json.loads(read(OUT/'recipe.json'));need(len(recipe['objects'])==113 and len(recipe['selectors'])==26 and all(v=='OFF' for _,v in recipe['selectors']),'canonical reference profile')
 sdk=recipe['flags'][recipe['flags'].index('-isysroot')+1];before=json.loads(read(OUT/'sdk-before.json'));after=json.loads(read(OUT/'sdk-after.json'));need(before==after,'SDK before/after exact')
 sdk_witness.verify(before,sdk,SDK)
 native_map=read(OUT/'native.map').decode('utf-8','surrogateescape')
 consumed=re.findall(r'^\[\s*\d+\] (.*\.tbd)$',native_map,re.M)
 need(sdk_witness.reconcile_consumed(before,consumed,requested_root=sdk,expected_canonical_root=SDK)==json.loads(read(OUT/'sdk-consumed.json')),'actual map SDK origins')
 objects={int(i):p for i,p in re.findall(r'^\[\s*(\d+)\] (.+)$',native_map,re.M)}
 providers={}
 for symbol,suffix in [('__ZN4Star4Time21monotonicMillisecondsEv','StarTime.cpp.o'),('__ZN4Star6Random7randIntExx','StarRandom.cpp.o'),('__ZN4Star12RandomSource7randIntExx','StarRandom.cpp.o')]:
  rows=re.findall(r'^0x[0-9A-Fa-f]+\s+0x[0-9A-Fa-f]+\s+\[\s*(\d+)\] '+re.escape(symbol)+r'$',native_map,re.M)
  need(len(rows)==1,'single live provider '+symbol);path=objects[int(rows[0])];need(path.endswith(suffix),'native dependency physical provider');providers[symbol]=path
 real=read(OUT/'real.stdout').decode();images=[x.split('\t') for x in real.splitlines() if x.startswith('loaded-image\t')]
 need(len(images)>2 and all(len(x)==3 and re.fullmatch('[a-f0-9]{32}',x[2]) for x in images),'loaded-image UUIDs')
 need(any('/libc++.' in x[1] for x in images) and any('libSystem.' in x[1] for x in images),'actual loaded C++/system runtime')
 failed=json.loads(read(OUT/'failed-map-archive.json'));need(sha(read(failed['archive']))==failed['sha256'],'failed archive pin')
 with tarfile.open(failed['archive'],'r:gz') as t:
  for p,h in failed['members'].items():need(sha(t.extractfile(p).read())==h,'failed archive exact reconstruction')
 return {**result,'report_sha256':REPORT,'actual_runtime_images':len(images),'actual_native_providers':providers,'sdk_interfaces':len(before['interfaces']),'sdk_consumed_entries':len(consumed)}

def controls():
 # Read overlays are isolated fixtures; originals stay byte-identical.
 base=(OUT/'report.json').read_bytes();wrong=json.loads(base);wrong['rows']+=1;wrong=json.dumps(wrong).encode()
 rejected=False
 try:audit(lambda p:wrong if Path(p)==OUT/'report.json' else Path(p).read_bytes())
 except AssertionError as e:need(str(e)=='independent report pin','control reached expected barrier');rejected=True
 need(rejected,'coherently modified report accepted')
 original=verify.sha
 try:
  verify.sha=lambda p:('0'*64 if Path(p)==OUT/'native' else original(p))
  rejected=False
  try:verify.verify()
  except AssertionError as e:need(str(e)=='primary artifact bytes','artifact control barrier');rejected=True
  need(rejected,'wrong native bytes accepted')
 finally:verify.sha=original
 receipt=next(OUT.glob('*.receipt.json'));bad=json.loads(receipt.read_bytes());bad['returncode']=False
 rejected=False
 try:audit(lambda p:json.dumps(bad).encode() if Path(p)==receipt else Path(p).read_bytes())
 except AssertionError as e:need(str(e)=='typed normal exit','boolean exit control barrier');rejected=True
 need(rejected,'boolean exit accepted')
 # Preserve the filter setter side effect, but incorrectly snapshot ttl before it.
 # Unlike the earlier omission alternative, this discriminates the expiry read.
 source=(HERE/'model.py').read_text();old='self.tc+=1;self.dep.append(\'T:\'+str(self.now));captured=self.now;count=0'
 need(source.count(old)==1,'unique ttl control insertion')
 source=source.replace(old,old+';ttlAtStart=self.ttl')
 old='elif captured-self.items[key][0]>self.ttl:';need(source.count(old)==1,'unique dynamic read control')
 source=source.replace(old,'elif captured-self.items[key][0]>ttlAtStart:')
 ns={};exec(compile(source,'<isolated-dynamic-ttl-control>','exec'),ns)
 rows=verify.model.corpus();wrong=ns['expected'](rows).splitlines();actual=(OUT/'ordered-0.stdout').read_text().splitlines()
 index=next(i for i,(a,b) in enumerate(zip(actual,wrong)) if a!=b)
 need(actual[index].split('\t')[1]==wrong[index].split('\t')[1],'ttl setter side effect retained by control')
 need(actual[index].split('\t')[6]!=wrong[index].split('\t')[6],'dynamic ttl controls expiry state')
 return {'changed-report':'rejected at independent report pin','changed-native':'rejected at primary artifact bytes','boolean-exit':'rejected at typed normal exit','dynamic-ttl-snapshot':{'first_differing_row':index,'input':rows[index],'same_observed_ttl':actual[index].split('\t')[1],'native_state':actual[index].split('\t')[6],'wrong_state':wrong[index].split('\t')[6]},'kind':'isolated in-memory read/hash/model overlays, not on-disk acquisition'}
if __name__=='__main__':print(json.dumps({'audit':audit(),'controls':controls()},sort_keys=True,indent=2))
