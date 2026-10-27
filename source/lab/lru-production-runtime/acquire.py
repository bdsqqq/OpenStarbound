#!/usr/bin/env python3
"""Fresh production header OFF/ON runtime acquisition, no build-system writes."""
from common import *
import re,shlex
import model,expanded_invocation,archive_identity,object_inventory,link_trace,native_symbols,build_provenance
BUILD=ROOT/'build/behavior/lru-cache-combined-r1'
ARCHIVE=BUILD/'candidate/cmake/rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a'
NINJA='/nix/store/ndfr0d2nizw172ppn99n505ikpsq9727-ninja-1.13.2/bin/ninja'
SDK='/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk'
BASELINE=ROOT/'build/lru-cache-recovery-r4'
BASELINE_SHA='cc628816f80e77ecc592ad386ead816564d5c191c83b1ddb428a9dc219156b61'
LIFETIME=ROOT/'build/lru-production-r1/final-r2/lifetime.cpp'

def recipe(mode):
 cm=BUILD/mode/'cmake';db=json.loads((cm/'compile_commands.json').read_text());lines=(cm/'build.ninja').read_text().splitlines()
 pos=next(i for i,l in enumerate(lines) if l.startswith('build ') and '/bin/starbound:' in l)
 objects=[str(cm/x) for x in shlex.split(lines[pos].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/'))]
 need(len(objects)==113 and len(set(objects))==113,'113 fresh Core/extern objects')
 rows=[next(r for r in db if r['output']==obj) for obj in objects]
 row=next(r for r in rows if r['file']==str(ROOT/'source/core/StarJsonBuilder.cpp'))
 args=shlex.split(row['command']);flags=[];skip=False
 for token in args[1:]:
  if skip:skip=False;continue
  if token=='-o':skip=True
  elif token not in ('-c',row['file']):flags.append(token)
 need('-O3'in flags and '-ffast-math'in flags,'unchanged optimized profile')
 libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[pos+1:pos+18] if x.startswith('  LINK_LIBRARIES = ')))
 libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
 selectors=re.findall(r'^(STAR_USE_RUST[^:]*):BOOL=(.*)$',(cm/'CMakeCache.txt').read_text(),re.M)
 need(len(selectors)==26,'26 selectors')
 need(all(v==('ON' if mode=='candidate' and k!='STAR_USE_RUST_LINE_QUERY' else 'OFF') for k,v in selectors),'evaluated selectors')
 need(len(db)==472 and all(('-DSTAR_USE_RUST_LRU_CACHE' in r['command'])==(mode=='candidate') for r in db),'472 actual production definitions')
 need(sum('star_engine_ffi' in x for x in libs)==(1 if mode=='candidate' else 0),'single configured aggregate')
 return {'cm':str(cm),'compiler':args[0],'flags':flags,'objects':objects,'libraries':libs,'rows':rows,'selectors':selectors}

def proof(mode):
 binary=BUILD/mode/'bin/starbound';p=json.loads(build_provenance.sidecar(binary).read_text())
 expected={'reference':'474bf23fe963e18b493263fb064e788c84c1b2f4432f0b96bec2b9122cbc8c6a','candidate':'053f787a5e03589b5b9dea25b37be8e823cedc2254136b0792cd32baebaa7263'}
 need(sha(binary)==p['binary_sha256']==expected[mode],'fresh game binary identity')
 same(build_provenance.source_snapshot(ROOT),p['source_files'],'fresh source closure without delta waivers')
 need(len(p['source_files'])==1499 and len(p['compile_source_files'])==472,'fresh full source membership')
 same(build_provenance._compile_source_inputs(BUILD/mode/'cmake'),p['compile_source_files'],'configured compilation sources')
 for path,h in p['build_identity']['files'].items():need(sha(path)==h,'configured bytes')
 for t in p['build_identity']['tools'].values():need(sha(t['path'])==t['sha256'],'configured tool bytes')
 return p

def compare(data):
 lines=data.splitlines();actual=b'\n'.join(x for x in lines if not x.startswith(b'@'))+b'\n'
 need(actual==model.expected(),'640-row independent model mismatch')
 props={}
 for line in lines:
  if line.startswith(b'@'):
   key,value=line[1:].decode('ascii').split('\t');need(key not in props,'duplicate property');props[key]=value
 need(set(props)==set(model.PROPERTIES) and all(x=='1' for x in props.values()),'12-property mismatch')

def historical():
 need(sha(BASELINE/'report.json')==BASELINE_SHA,'authenticated historical native report')
 report=load(BASELINE/'report.json');need(report['native_runs']==20 and report['cases_per_run']==640,'historical calibration')
 paths=[]
 for variant in ('original','current'):
  for alias in ('ordered','hash'):
   for repeat in (1,2):
    path=BASELINE/(variant+'-'+alias+'-'+str(repeat)+'.stdout')
    need(report['artifacts'][str(path)]==sha(path),'authenticated native output');compare(path.read_bytes());paths.append(path)
 return {'report':str(BASELINE/'report.json'),'report_sha256':BASELINE_SHA,'outputs':hashes(paths),'limits':'supplementary historical native bytes only; no old binary or object executed'}

def physical(inv):
 archives={p:archive_identity.arm64_archive_members(Path(p).read_bytes()) for p in inv['file_inputs'] if p.endswith('.a')}
 providers=[]
 if str(ARCHIVE) in archives:
  definitions=[(m,archive_identity.external_definitions(m['body'])) for m in archives[str(ARCHIVE)] if m['body'][:4]==b'\xcf\xfa\xed\xfe']
  for symbol in (b'_sb_lru_run',b'_sb_lru_count',b'_rust_eh_personality'):
   owners=[m for m,names in definitions if symbol in names];need(len(owners)==1,'unique physical Rust provider')
   m=owners[0];providers.append({'symbol':symbol,'archive':str(ARCHIVE).encode(),'name':m['name'],'offset':m['offset'],'sha256':m['sha256']})
 return {'archives':{p:[{k:m[k] for k in ('name','offset','sha256')} for m in ms] for p,ms in archives.items()},'rust_providers':providers}

def origins(name,r,sdk_before,data):
 commands=[shlex.split(x) for x in data(OUT/(name+'-expand.stderr')).decode().splitlines() if x.lstrip().startswith('"')]
 need(len(commands)==1,'single expanded linker');bound=codec.loads(data(OUT/(name+'-expanded.typed')).decode('ascii'))
 expanded_invocation.verify(bound,commands[0]);inv=bound['inventory'];objects=[*r['objects'],str(OUT/(name+'.o'))]
 same([x for x in inv['file_inputs'] if x.endswith('.o')],objects,'fresh standalone object membership')
 same([x for x in inv['file_inputs'] if 'star_engine_ffi' in x],[str(ARCHIVE)] if name!='reference' else [],'one/no Rust aggregate by profile')
 phys=physical(inv);same(phys,codec.loads(data(OUT/(name+'-physical-prelink.typed')).decode('ascii')),'physical prelink origins')
 blobs={x.encode():Path(x).read_bytes() for x in inv['file_inputs'] if x.endswith('.a')}
 tables={p:b''.join(m['name']+b'\n' for m in archive_identity.arm64_archive_members(blob)) for p,blob in blobs.items()}
 trace=link_trace.parse(data(OUT/(name+'-link.stdout')),[p.encode() for p in objects],tables)
 mapped=object_inventory.reconcile(data(OUT/(name+'.map')),[p.encode() for p in objects],tables,blobs)
 sdk=r['flags'][r['flags'].index('-isysroot')+1]
 paths=trace['sdk_paths']+mapped['unresolved_origins']+[x['source'] for x in trace['indirect_declarations']]
 consumed=sdk_witness.reconcile_consumed(sdk_before,[os.fsdecode(x) for x in paths],requested_root=sdk,expected_canonical_root=SDK)
 symbols=native_symbols.live_symbols(data(OUT/(name+'.map')));providers=[]
 for sym in [b'_main']+([b'_lru_native_dispatch_ordered',b'_lru_native_dispatch_hash'] if name in ('reference','candidate') else [])+([b'_sb_lru_run',b'_rust_eh_personality'] if name!='reference' else []):
  s=native_symbols.unique_symbol(symbols,sym)
  if sym in (b'_sb_lru_run',b'_rust_eh_personality'):
   member=next(m for m in phys['rust_providers'] if m['symbol']==sym);expected=str(ARCHIVE).encode()+b'('+member['name']+b')'
  else:expected=str(OUT/(name+'.o')).encode()
  need(s.object_path==expected and s.size>0,'fresh production/controller provider '+repr(sym));providers.append(s.manifest())
 dis=data(OUT/(name+'-disassemble.stdout'))
 def edge(body,target):return any(target in line and (b'\tbl\t'in line or b'\tb\t'in line) for line in body.splitlines())
 if name!='reference':need(edge(dis,b'_sb_lru_run'),'production native host to Rust call edge')
 if name in ('candidate','reference'):
  body=dis.split(b'_main:\n',1)[1].split(b'\n_',1)[0]
  for target in (b'_lru_native_dispatch_ordered',b'_lru_native_dispatch_hash'):need(edge(body,target),'main dispatch edge')
  methods=[s for s in symbols if re.match(rb'^__ZNK?4Star12LruCacheBase',s.name) and b'LruNativeR1' in s.name]
  need(bool(methods),'actual production class methods')
  for s in methods:
   if s.object_path==str(OUT/(name+'.o')).encode():continue
   owners=[x for x in symbols if x.address==s.address and x.object_index!=0 and x.size>0]
   need(s.object_index==0 and s.size==0 and owners and all(x.object_path==str(OUT/(name+'.o')).encode() for x in owners),'exact-address folded production owner')
 else:methods=[]
 return {'providers':providers,'production_methods':[s.manifest() for s in methods],'physical_rust_providers':phys['rust_providers'],'trace':trace,'map':mapped,'consumed_sdk':consumed}

def artifacts():return hashes(p for p in OUT.rglob('*') if p.is_file() and p!=OUT/'report.typed' and 'audit' not in p.relative_to(OUT).parts)

def semantics(data):
 for mode in ('reference','candidate'):
  for alias in ('ordered','hash'):
   first=data(OUT/(mode+'-'+alias+'-1.stdout'));compare(first)
   same(first,data(OUT/(mode+'-'+alias+'-2.stdout')),'repeat bytes')
   same(first,(BASELINE/('original-'+alias+'-1.stdout')).read_bytes(),'supplementary authenticated native bytes')
   if mode=='candidate':same(first,data(OUT/('reference-'+alias+'-1.stdout')),'fresh OFF/ON bytes')
 need(data(OUT/'controls-run.stdout')==b'controls\t40\nunbounded-positive\t350001 evictions\t193 nested invocations\n','production malformed/unbounded/counter controls')
 lines=data(OUT/'lifetime-run.stdout').splitlines()
 need(lines[-1]==b'NATIVE_UNWIND_CONTROLS_PASS' and b'ITERATOR_UNWIND_CONTROLS_PASS' in lines,'production unwind controls')
 traces=[x.split(b'\t') for x in lines if x.startswith(b'trace\t')]
 need(len(traces)==16,'all eight full lifetime trace pairs')
 for i in range(0,16,2):
  a,b=traces[i:i+2];same(a[:3],b[:3],'trace identity');need(a[3]==b'native' and b[3]==b'mock','trace side');same(a[4:],b[4:],'full production lifetime event/state equality')
 expected=[b'comparison\t'+alias+b'\t'+test+b'\tequal' for alias in (b'ordered',b'hash') for test in (b'success',b'copy-fault',b'copy-fault-reentry')]
 same([x for x in lines if x.startswith(b'comparison\t')],expected,'six alias comparisons')

def verify(report=None,override=None):
 report=report or load(OUT/'report.typed');override=override or {}
 def data(path):return Path(override.get(str(path),path)).read_bytes()
 need(report['status']=='FINITE_FRESH_PRODUCTION_LRU_RUNTIME_PASS','report status')
 same(sorted(report['artifacts']),sorted(artifacts()),'exact artifact membership')
 same(report['inputs'],load(OUT/'inputs-before.typed'),'exact input membership')
 for field in ('inputs','artifacts'):
  for p,h in report[field].items():
   s=Path(p).lstat();need(stat.S_ISREG(s.st_mode) or field=='inputs','regular product');need(field=='inputs' or s.st_nlink==1,'nonaliased product')
   need(hashlib.sha256(data(p)).hexdigest()==h,field+' drift '+p)
 same(hashes(HERE.glob('*.py')),load(OUT/'runner-membership.typed'),'runner membership')
 for mode in ('reference','candidate'):
  same(recipe(mode),load(OUT/(mode+'-recipe.typed')),'evaluated fresh recipe');same(proof(mode),load(OUT/(mode+'-proof.typed')),'fresh game proof')
 same(historical(),load(OUT/'historical.typed'),'historical reference');verify_commands(report,data);semantics(data)
 sdk_before=load(OUT/'sdk-before.typed');same(sdk_before,load(OUT/'sdk-after.typed'),'SDK stable')
 for name in ('reference','candidate','controls','lifetime'):
  r=recipe('reference' if name=='reference' else 'candidate')
  same(origins(name,r,sdk_before,data),codec.loads(data(OUT/(name+'-origin.typed')).decode('ascii')),'reconstructed origins')
 return True

def acquire():
 recipes={m:recipe(m) for m in ('reference','candidate')};proofs={m:proof(m) for m in recipes}
 for r in recipes.values():
  sdk_witness._anchors(r['flags'][r['flags'].index('-isysroot')+1],SDK)
 need(not OUT.exists(),'exclusive fresh output root');OUT.mkdir();(OUT/'home').mkdir();(OUT/'tmp').mkdir()
 for m in recipes:dump(OUT/(m+'-recipe.typed'),recipes[m]);dump(OUT/(m+'-proof.typed'),proofs[m])
 dump(OUT/'historical.typed',historical());dump(OUT/'runner-membership.typed',hashes(HERE.glob('*.py')))
 need(model.literal_checks()==6 and len(model.corpus())==640,'unchanged independent model')
 write(OUT/'probe.cpp',(HERE.parent/'lru-cache/native.cpp').read_bytes());write(OUT/'selected.hpp',b'#include "StarLruCache.hpp"\n#define SELECTED Star\n')
 need(sha(LIFETIME)=='d8e0462dac37fef771a466404a0f82d5af061001e92852ee14a88a14c2e8ad9d','frozen production lifetime source')
 write(OUT/'lifetime.cpp',LIFETIME.read_bytes())
 controls=(HERE.parent/'lru-rust/controls.cpp').read_text()
 prefix=LIFETIME.read_text().split('#include <cstdio>',1)[0]
 controls=controls.replace('#include "../lru-boundary/cache.hpp"\n#include "StarLruCache.hpp"\n','',1)
 for n in ('LruCacheBase','LruCache','HashLruCache'):controls=controls.replace('Star::'+n+'<','LruProductionReference::'+n+'<')
 controls=controls.replace('LruBoundary::','Star::');write(OUT/'controls.cpp',(prefix+controls).encode())
 corpus=('\n'.join('\t'.join(map(str,row)) for row in model.corpus())+'\n').encode();write(OUT/'corpus.tsv',corpus);write(OUT/'expected.tsv',model.expected())
 r=recipes['candidate'];sdk=r['flags'][r['flags'].index('-isysroot')+1]
 need(str(Path(sdk).resolve())==SDK,'independent SDK anchor');sdk_before=sdk_witness.capture(sdk,SDK);dump(OUT/'sdk-before.typed',sdk_before)
 deps=set()
 for m,r in recipes.items():
  cm=Path(r['cm']);command(m+'-fresh-deps',[NINJA,'-t','deps',*[str(Path(p).relative_to(cm)) for p in r['objects']]],cwd=cm)
  found=[]
  for block in (OUT/(m+'-fresh-deps.stdout')).read_text().strip().split('\n\n'):
   lines=block.splitlines();match=re.fullmatch(r'(.+): #deps ([0-9]+), deps mtime ([0-9]+) \(VALID\)',lines[0]);need(match is not None,'valid fresh dependencies')
   found.append(str(cm/match[1]));need(len(lines)-1==int(match[2]),'dependency count')
   deps.update(Path(x.strip()) if Path(x.strip()).is_absolute() else cm/x.strip() for x in lines[1:])
  same(found,r['objects'],'new evaluated dependency object membership')
  deps.update(map(Path,r['objects']));deps.update(ROOT/p for p in proofs[m]['source_files']);deps.update(map(Path,proofs[m]['compile_source_files']))
  deps.update(map(Path,proofs[m]['build_identity']['files']));deps.update(Path(t['path']) for t in proofs[m]['build_identity']['tools'].values())
  deps.update(Path(p) for p in r['libraries'] if Path(p).is_file());deps.add(build_provenance.sidecar(BUILD/m/'bin/starbound'));deps.add(BUILD/m/'bin/starbound');deps.add(cm/'.ninja_deps');deps.add(cm/'CMakeFiles/rules.ninja')
 sources={'reference':OUT/'probe.cpp','candidate':OUT/'probe.cpp','controls':OUT/'controls.cpp','lifetime':OUT/'lifetime.cpp'}
 for name,src in sources.items():
  r=recipes['reference' if name=='reference' else 'candidate'];extra=['-I'+str(OUT),'-I'+str(HERE.parent/'lru-cache')]
  command(name+'-deps',[r['compiler'],*r['flags'],*extra,'-M','-MT',name+'.o','-MF',OUT/(name+'.d'),src],cwd=r['cm'])
  _,tail=(OUT/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)
  deps.update(Path(p) if Path(p).is_absolute() else Path(r['cm'])/p for p in shlex.split(tail))
 deps.update(HERE.glob('*.py'));deps.update((HERE.parent/'path-embed-replay').glob('*.py'));deps.update(HERE.parent/p for p in ('native_evidence_json.py','native_symbols.py','native_artifacts.py','behavior/build_provenance.py','lru-cache/model.py','lru-cache/native.cpp','lru-cache/StarLruCache.original.hpp','lru-boundary/unwind.cpp','lru-rust/controls.cpp'))
 deps.update([LIFETIME,Path(NINJA),Path(sys.executable).resolve()]);deps.update(OUT/p for p in ('probe.cpp','selected.hpp','lifetime.cpp','controls.cpp','corpus.tsv','expected.tsv','sdk-before.typed','reference-recipe.typed','candidate-recipe.typed','reference-proof.typed','candidate-proof.typed','historical.typed','runner-membership.typed'))
 deps.update(map(Path,historical()['outputs']));deps.add(BASELINE/'report.json')
 inputs=hashes(deps);dump(OUT/'inputs-before.typed',inputs);print('PRECOMPILE_BOUND',len(inputs),flush=True)
 for name,src in sources.items():
  r=recipes['reference' if name=='reference' else 'candidate'];c=r['compiler'];flags=r['flags'];extra=['-I'+str(OUT),'-I'+str(HERE.parent/'lru-cache')]
  command(name+'-compile',[c,*flags,*extra,'-c',src,'-o',OUT/(name+'.o')],cwd=r['cm']);same(inputs,hashes(deps),'postcompile input drift')
  link=[c,*flags,*r['objects'],OUT/(name+'.o'),*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(OUT/(name+'.map')),'-Wl,-t,-trace_implicit_libraries','-o',OUT/name]
  _,stderr=command(name+'-expand',[c,'-###',*link[1:]],cwd=r['cm'])
  cmds=[shlex.split(x) for x in stderr.decode().splitlines() if x.lstrip().startswith('"')];need(len(cmds)==1,'single expanded invocation')
  bound=expanded_invocation.bind(cmds[0]);dump(OUT/(name+'-expanded.typed'),bound);dump(OUT/(name+'-physical-prelink.typed'),physical(bound['inventory']))
  command(name+'-link',link,cwd=r['cm']);command(name+'-disassemble',['/usr/bin/otool','-tvV',OUT/name],cwd=r['cm'])
  dump(OUT/(name+'-origin.typed'),origins(name,r,sdk_before,lambda p:Path(p).read_bytes()))
 same(inputs,hashes(deps),'preexecution freeze')
 for mode in ('reference','candidate'):
  for alias in ('ordered','hash'):
   for repeat in (1,2):stdout,_=command(mode+'-'+alias+'-'+str(repeat),[OUT/mode,alias],corpus);compare(stdout)
 command('controls-run',[OUT/'controls']);command('lifetime-run',[OUT/'lifetime']);semantics(lambda p:Path(p).read_bytes())
 dump(OUT/'sdk-after.typed',sdk_witness.capture(sdk,SDK));same(inputs,hashes(deps),'final input stability')
 report={'status':'FINITE_FRESH_PRODUCTION_LRU_RUNTIME_PASS','inputs':inputs,'artifacts':artifacts(),'rows_per_run':640,'properties_per_run':12,'runs':8,'trace_pairs':8,'limits':'finite production header runtime/lifetime parity; no game, performance, OOM, arbitrary pointer provenance or universal equivalence claim'}
 dump(OUT/'report.typed',report);verify();print(report['status'],sha(OUT/'report.typed'),flush=True)

if __name__=='__main__':
 if sys.argv[1:]==['--verify']:verify();print('STRICT_READONLY_PRODUCTION_RUNTIME_REPLAY_PASS')
 elif not sys.argv[1:]:acquire()
 else:raise SystemExit('usage: acquire.py [--verify]')
