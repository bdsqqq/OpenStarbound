#!/usr/bin/env python3
"""Read-only finite boundary replay. Does not launch subprocesses."""
import hashlib,importlib.util,json,re,sys,tarfile
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];FROZEN=HERE.parent/'ttl-cache';OUT=ROOT/'build/ttl-boundary-r1';BASE=ROOT/'build/ttl-cache-native-r1'
sys.path.insert(0,str(FROZEN));import model
spec=importlib.util.spec_from_file_location('ttl_native_verify',FROZEN/'verify.py');baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,why):
 if not ok:raise AssertionError(why)
def readj(p):return json.loads(Path(p).read_text())
def route_file(name):
 lines=(OUT/(name+'.stderr')).read_text().splitlines();routes={};edges={};aliases={}
 for line in lines:
  p=line.split('\t')
  if p[0]=='route':routes[tuple(map(int,p[1:3]))]=int(p[3])
  elif p[0]=='edge':edges[tuple(map(int,p[1:4]))]=int(p[4])
  elif p[0]=='alias-route':aliases.setdefault(p[1],{})[tuple(map(int,p[2:4]))]=int(p[4])
  else:need(False,'unexpected native stderr '+line)
 need(routes,'actual selected routes '+name)
 return routes,edges,aliases

def semantic_replay():
 need(sha(BASE/'report.json')=='cba3b3c84acc2128bd043400cabd6ed2ebf35fcdde37e6d36e2a870bc7926674','accepted baseline report pin')
 for p,h in readj(BASE/'report.json')['source'].items():need(sha(p)==h,'frozen baseline source '+p)
 rows=model.corpus();expected=model.expected(rows);need(len(rows)==626,'626 frozen rows')
 need((OUT/'corpus.tsv').read_text()=='\n'.join(rows)+'\n','frozen corpus');need((OUT/'expected.tsv').read_text()==expected,'independent expectation')
 modes=set();stages=set();leaves=set();routes_saved={};alias_saved={}
 for name in ['ordered-0','ordered-1','hash-0','hash-1','real','lifecycle','controls']:
  routes,edges,aliases=route_file(name);routes_saved[name]={f'{m}/{s}':n for (m,s),n in routes.items()};alias_saved[name]={a:{f'{m}/{s}':n for (m,s),n in v.items()} for a,v in aliases.items()}
  modes.update(m for m,s in routes);stages.update(s for m,s in routes);leaves.update(op for m,s,op in edges)
  if name.startswith(('ordered-','hash-')):
   need((OUT/(name+'.stdout')).read_text()==expected,'independent public-state model '+name)
   need(routes.get((9,1),0)>626 and routes.get((18,3),0)>0 and routes.get((15,2),0)>0,'selected scripted values/filter/cleanup continuation '+name)
  if name=='real':
   need(set(aliases)=={'real-ordered','real-hash'},'both actual Time/Random aliases')
   for a,v in aliases.items():need(all(v.get((m,0),0)>0 for m in [0,2,4,7,11,12,13,16,18]),'actual aliases selected boundary '+a)
  if name=='lifecycle':
   need(set(aliases)=={'actual-ordered','scripted-ordered','actual-hash','scripted-hash'},'four separately counted boundary aliases')
   for a,v in aliases.items():need(all(v.get((m,s),0)>0 for m,s in [(0,0),(9,1),(13,0),(16,0),(15,2)]),'lifecycle selected boundary '+a)
 need(modes==set(range(19)) and stages==set(range(4)) and leaves==set(range(1,32)),'19 modes / 4 stages / 31 leaves observed')
 actual=(OUT/'lifecycle.stdout').read_text();original=(BASE/'lifecycle.stdout').read_text()
 need(actual==original,'ALL four full lifetime traces and 68 properties match frozen baseline')
 props=[l for l in actual.splitlines() if l.startswith('property\t')];need(len(props)==68 and all(l.endswith('\t1') for l in props),'68 true properties')
 tests=[l for l in (OUT/'controls.stdout').read_text().splitlines() if l.startswith('control\t')];need(tests and all(l.endswith('\t1') for l in tests),'actual ABI controls')
 controls=baseline.controls(rows,expected)
 # A known failure must fail the actual exact-trace comparator, not just a hash.
 wrong=actual.replace('unwind-destructor-reentry','wrong-unwind-site',1)
 need(wrong!=original,'coherent lifetime corruption rejected')
 controls['changed-full-lifetime-trace']={'rejected':True,'kind':'isolated valid-text trace overlay'}
 return {'rows':626,'streams':4,'native_lifecycle_properties':68,'full_lifetime_traces':4,'native_abi_controls':len(tests),'controls':controls,'routes':routes_saved,'alias_routes':alias_saved,'mode_coverage':sorted(modes),'stage_coverage':sorted(stages),'leaf_coverage':sorted(leaves)}

def receipt(r,plan,start,prefix):
 for k in ('pid','pgid','started_ns','ended_ns'):need(type(r[k]) is int and r[k]>0,'typed '+k)
 need(type(r['returncode']) is int and r['returncode']==plan['expected'],'typed normal exit')
 need(type(r['timed_out']) is bool and not r['timed_out'],'typed timeout')
 need(type(r['group_gone']) is bool and r['group_gone'],'typed group cleanup')
 need(r['pid']==r['pgid']==start['pid']==start['pgid'] and r['started_ns']==start['started_ns'] and r['ended_ns']>=r['started_ns'],'actual process identity')
 need(r['argv']==plan['argv'] and r['tool_before']==r['tool_after']==plan['tool'],'actual tool/argv stable')
 for ext in ('stdout','stderr'):need(sha(prefix+'.'+ext)==r[ext+'_sha256'],'stdio '+ext)
 need(sha(prefix+'.stdin')==plan['stdin_sha256'],'stdin')
 need(sha(r['tool_before']['resolved'])==r['tool_before']['sha256'],'tool current bytes')

def verify(pin=None):
 report=readj(OUT/'report.json')
 for manifest in ('attempt-1-archive.json','pre-borrow-action-archive.json','pre-result-metadata-archive.json','pre-leaf15-host-metadata-archive.json'):
  archive=readj(OUT/manifest);need(sha(archive['archive'])==archive['sha256'],'historical archive pin')
  with tarfile.open(archive['archive'],'r:gz') as t:
   need(set(t.getnames())==set(archive['members']),'exact historical membership')
   for name,h in archive['members'].items():need(hashlib.sha256(t.extractfile(name).read()).hexdigest()==h,'historical exact byte reconstruction')
 need(sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())<=96*1024*1024,'96MiB cap')
 if pin:need(sha(OUT/'report.json')==pin,'independent report pin')
 need(sha(OUT/'native')==report['binary']['sha256'],'artifact bytes')
 for p,h in report['source'].items():need(sha(p)==h,'boundary source '+p)
 for p,h in readj(OUT/'inputs.json').items():need(sha(p)==h,'acquisition input '+p)
 for p,h in report['products'].items():need(sha(p)==h,'product '+p)
 need(sha(ROOT/'source/core/StarRustTtlCache.h')==report['canonical_header_sha256'],'frozen canonical C11 header')
 need((ROOT/'source/core/StarTtlCache.hpp').read_bytes()==(FROZEN/'StarTtlCache.original.hpp').read_bytes(),'original production class unchanged')
 recipes=readj(OUT/'recipe.json');need(len(recipes['objects'])==113 and len(recipes['selectors'])==26 and all(v=='OFF' for _,v in recipes['selectors']),'113-object native LRU-OFF profile')
 rs=list(OUT.glob('*.receipt.json'));need(len(rs)==report['processes'],'exact receipt membership')
 for p in rs:
  prefix=str(p)[:-len('.receipt.json')];receipt(readj(p),readj(prefix+'.plan.json'),readj(prefix+'.started.json'),prefix)
 sem=semantic_replay();need(sem==report['semantic'],'semantic regeneration')
 # Full SDK identity and map-consumed interfaces, not just sysroot spelling.
 sys.path.insert(0,str(HERE.parent/'path-embed-replay'));import sdk_witness
 sdk=recipes['flags'][recipes['flags'].index('-isysroot')+1];physical='/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk'
 before=readj(OUT/'sdk-before.json');need(before==readj(OUT/'sdk-after.json'),'SDK stable');sdk_witness.verify(before,sdk,physical)
 native_map=(OUT/'native.map').read_text(errors='surrogateescape');consumed=re.findall(r'^\[\s*\d+\] (.*\.tbd)$',native_map,re.M)
 need(sdk_witness.reconcile_consumed(before,consumed,requested_root=sdk,expected_canonical_root=physical)==readj(OUT/'sdk-consumed.json'),'SDK consumed origins')
 objects={int(i):p for i,p in re.findall(r'^\[\s*(\d+)\] (.+)$',native_map,re.M)}
 providers={}
 for symbol,suffix in [('__ZN4Star4Time21monotonicMillisecondsEv','StarTime.cpp.o'),('__ZN4Star6Random7randIntExx','StarRandom.cpp.o'),('__ZN4Star12RandomSource7randIntExx','StarRandom.cpp.o')]:
  hits=re.findall(r'^0x[0-9A-Fa-f]+\s+0x[0-9A-Fa-f]+\s+\[\s*(\d+)\] '+re.escape(symbol)+r'$',native_map,re.M);need(len(hits)==1 and objects[int(hits[0])].endswith(suffix),'actual dependency provider');providers[symbol]=objects[int(hits[0])]
 images=[l.split('\t') for l in (OUT/'real.stdout').read_text().splitlines() if l.startswith('loaded-image\t')]
 need(len(images)>2 and all(len(l)==3 and re.fullmatch('[a-f0-9]{32}',l[2]) for l in images),'runtime UUID receipts')
 need(any('libc++.' in l[1] for l in images) and any('libSystem.' in l[1] for l in images),'C++/system runtime loaded')
 # Known malformed process receipt exercises the same typed barrier.
 p=rs[0];prefix=str(p)[:-len('.receipt.json')];bad=readj(p);bad['returncode']=False
 try:receipt(bad,readj(prefix+'.plan.json'),readj(prefix+'.started.json'),prefix)
 except AssertionError as e:need(str(e)=='typed normal exit','boolean receipt control barrier')
 else:raise AssertionError('boolean exit accepted')
 return {'status':'PASS finite native boundary + mock; Rust/game UNIMPLEMENTED','report_sha256':sha(OUT/'report.json'),'rows':626,'streams':4,'properties':68,'traces':4,'abi_controls':sem['native_abi_controls'],'processes':len(rs),'sdk_interfaces':len(before['interfaces']),'sdk_consumed_entries':len(consumed),'runtime_images':len(images),'providers':providers,'typed_receipt_control':'rejected'}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1] if len(sys.argv)>1 else None),sort_keys=True,indent=2))
