#!/usr/bin/env python3
"""Actual Rust bridge acquisition, using existing pure provenance helpers only."""
import re,shlex
from common import *
import canonical
import model,inventory,expanded_invocation,archive_identity,object_inventory,link_trace,native_symbols,build_provenance
CM=ROOT/'build/behavior/path-embed-combined-r1/reference/cmake'
BOUNDARY=HERE.parent/'lru-boundary'
SDK=canonical.SDK
NINJA=canonical.NINJA
ARCHIVE=canonical.ARCHIVE
BASELINE=ROOT/'build/lru-cache-recovery-r4'
BASELINE_SHA='cc628816f80e77ecc592ad386ead816564d5c191c83b1ddb428a9dc219156b61'

def recipe():
 db=json.loads((CM/'compile_commands.json').read_text());lines=(CM/'build.ninja').read_text().splitlines()
 pos=next(i for i,line in enumerate(lines) if line.startswith('build ') and '/bin/starbound:' in line)
 objects=[str(CM/x) for x in shlex.split(lines[pos].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/'))]
 need(len(objects)==113 and len(set(objects))==113,'113 retained objects')
 rows=[next(r for r in db if r['output']==obj) for obj in objects]
 row=next(r for r in rows if r['file']==str(ROOT/'source/core/StarJsonBuilder.cpp'))
 args=shlex.split(row['command']);flags=[];skip=False
 for token in args[1:]:
  if skip:skip=False;continue
  if token=='-o':skip=True
  elif token not in ('-c',row['file']):flags.append(token)
 need('-O3'in flags and '-ffast-math'in flags,'real optimized profile')
 libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[pos+1:pos+18] if x.startswith('  LINK_LIBRARIES = ')))
 libs=[str(CM/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
 selectors=re.findall(r'^(STAR_USE_RUST[^:]*):BOOL=(.*)$',(CM/'CMakeCache.txt').read_text(),re.M)
 need(len(selectors)==25 and all(v=='OFF' for _,v in selectors),'unchanged all-OFF profile')
 return {'compiler':args[0],'flags':flags,'objects':objects,'libraries':libs,'rows':rows,'selectors':selectors}

def source_delta(historical,live,dependencies):
 # the retained all-OFF C++ objects cannot consume the parent's new Rust module.
 # bind that live membership honestly; do not retag the whole old game receipt.
 allowed={'source/rust/ffi/src/lib.rs','source/rust/ffi/src/lru_cache.rs'}
 changed={p for p in set(historical)|set(live) if historical.get(p)!=live.get(p)}
 need(changed in (set(),allowed),'unexpected retained source delta')
 need(all(str((ROOT/p).resolve()) not in dependencies for p in allowed),'changed Rust consumed by retained compile')
 return {p:{'historical':historical.get(p),'live':live.get(p)} for p in sorted(changed)}

def source_policy_controls():
 lib='source/rust/ffi/src/lib.rs';module='source/rust/ffi/src/lru_cache.rs'
 old={'source/core/example.hpp':'same',lib:'old'}
 live={**old,lib:'new',module:'new-module'}
 need(len(source_delta(old,live,set()))==2,'allowed nonparticipating Rust delta')
 rejected=[]
 for name,candidate,deps in [('changed-core',{**live,'source/core/example.hpp':'wrong'},set()),('removed-core',{lib:'new',module:'new-module'},set()),('third-Rust',{**live,'source/rust/ffi/src/other.rs':'extra'},set()),('consumed-Rust',live,{str((ROOT/lib).resolve())})]:
  try:source_delta(old,candidate,deps)
  except ValueError:rejected.append(name)
  else:raise ValueError('source policy control escaped '+name)
 return rejected

def compare(data):
 lines=data.splitlines();actual=b'\n'.join(x for x in lines if not x.startswith(b'@'))+b'\n'
 need(actual==model.expected(),'640-row independent model mismatch')
 props={}
 for line in lines:
  if line.startswith(b'@'):
   key,value=line[1:].decode('ascii').split('\t');need(key not in props,'duplicate property');props[key]=value
 need(set(props)==set(model.PROPERTIES) and all(x=='1' for x in props.values()),'12-property mismatch')
 return len(actual.splitlines())


def baseline():
 need(sha(BASELINE/'report.json')==BASELINE_SHA,'historical native report identity')
 report=load(BASELINE/'report.json')
 need(report['native_runs']==20 and report['cases_per_run']==640,'complete historical calibration')
 paths=[]
 for variant in ('original','current'):
  for alias in ('ordered','hash'):
   for repeat in (1,2):
    path=BASELINE/(variant+'-'+alias+'-'+str(repeat)+'.stdout')
    need(report['artifacts'][str(path)]==sha(path),'historical native output binding');compare(path.read_bytes());paths.append(path)
 return {'report':str(BASELINE/'report.json'),'report_sha256':BASELINE_SHA,'outputs':hashes(paths),'source_closure':'historical at 42e00298; explicitly NOT rebound to current Rust sources'}

def archive_providers():
 members=archive_identity.members(ARCHIVE.read_bytes());result=[]
 for symbol in (b'_sb_lru_run',b'_sb_lru_count',b'_rust_eh_personality'):
  owners=[]
  for member in members:
   if member['body'][:4]==b'\xcf\xfa\xed\xfe' and symbol in archive_identity.external_definitions(member['body']):owners.append(member)
  need(len(owners)==1,'unique physical aggregate provider '+repr(symbol))
  m=owners[0];result.append({'symbol':symbol,'archive':str(ARCHIVE).encode(),'name':m['name'],'offset':m['offset'],'sha256':m['sha256']})
 return result

def origins(name,r,sdk_before,read_bytes=None):
 data=read_bytes or (lambda path:Path(path).read_bytes())
 def typed(path):return codec.loads(data(path).decode('ascii'))
 objects=[*r['objects'],str(OUT/(name+'.o'))]
 commands=[shlex.split(x) for x in data(OUT/(name+'-expand.stderr')).decode().splitlines() if x.lstrip().startswith('"')]
 need(len(commands)==1,'single expanded linker')
 bound=typed(OUT/(name+'-expanded.typed'));expanded_invocation.verify(bound,commands[0]);inv=bound['inventory']
 same([x for x in inv['file_inputs'] if x.endswith('.o')],objects,'actual object list without mock controller')
 rust_archives=[x for x in inv['file_inputs'] if x.endswith('.a') and ('star_engine_ffi' in x or '/rust' in x)]
 same(rust_archives,[str(ARCHIVE)],'exactly one aggregate archive')
 blobs={x.encode():Path(x).read_bytes() for x in inv['file_inputs'] if x.endswith('.a')}
 tables={p:b''.join(m['name']+b'\n' for m in archive_identity.arm64_archive_members(blob)) for p,blob in blobs.items()}
 trace=link_trace.parse(data(OUT/(name+'-link.stdout')),[p.encode() for p in objects],tables)
 mapped=object_inventory.reconcile(data(OUT/(name+'.map')),[p.encode() for p in objects],tables,blobs)
 sdk=r['flags'][r['flags'].index('-isysroot')+1]
 paths=trace['sdk_paths']+mapped['unresolved_origins']+[x['source'] for x in trace['indirect_declarations']]
 consumed=sdk_witness.reconcile_consumed(sdk_before,[os.fsdecode(x) for x in paths],requested_root=sdk,expected_canonical_root=SDK)
 symbols=native_symbols.live_symbols(data(OUT/(name+'.map')));providers=[]
 physical=archive_providers()
 prelink={os.fsdecode(path):[{k:m[k] for k in ('name','offset','sha256')} for m in archive_identity.arm64_archive_members(blob)] for path,blob in blobs.items()}
 same({'archives':prelink,'rust_providers':physical},typed(OUT/(name+'-physical-prelink.typed')),'prelink physical archive providers')
 for symbol_name in [b'_main',b'_sb_lru_run']+([b'_lru_native_dispatch_ordered',b'_lru_native_dispatch_hash'] if name=='candidate' else []):
  symbol=native_symbols.unique_symbol(symbols,symbol_name)
  if symbol_name==b'_sb_lru_run':
   member=next(m for m in physical if m['symbol']==symbol_name)
   expected=str(ARCHIVE).encode()+b'('+member['name']+b')'
  else:expected=str(OUT/(name+'.o')).encode()
  need(symbol.object_path==expected and symbol.size>0,'fresh symbol provider '+repr(symbol_name));providers.append(symbol.manifest())
 runtime=[s for s in symbols if s.name==b'_rust_eh_personality']
 need(len(runtime)==1 and runtime[0].object_path.startswith(str(ARCHIVE).encode()+b'('),'single aggregate runtime provider')
 providers.append(runtime[0].manifest())
 dis=data(OUT/(name+'-disassemble.stdout'))
 need(any(b'_sb_lru_run' in line and (b'\tbl\t'in line or b'\tb\t'in line) for line in dis.splitlines()),'surviving native to Rust call edge')
 if name=='candidate':
  main=dis.split(b'_main:\n',1);need(len(main)==2,'main disassembly');body=main[1].split(b'\n_',1)[0]
  for target in (b'_lru_native_dispatch_ordered',b'_lru_native_dispatch_hash'):need(any(target in line and (b'\tbl\t'in line or b'\tb\t'in line) for line in body.splitlines()),'fresh dispatch edge')
  methods=[s for s in symbols if re.match(rb'^__ZNK?11LruBoundary12LruCacheBase',s.name) and b'LruNativeR1'in s.name]
  need(bool(methods),'fresh boundary cache methods')
  for s in methods:
   if s.object_path==str(OUT/'candidate.o').encode():continue
   owners=[x for x in symbols if x.address==s.address and x.object_index!=0 and x.size>0]
   need(s.object_index==0 and s.size==0 and owners and all(x.object_path==str(OUT/'candidate.o').encode() for x in owners),'exact-address folded cache owner')
 return {'providers':providers,'physical_rust_providers':physical,'consumed_sdk':consumed,'trace':trace,'map':mapped,'physical_archive_tables':tables}

def artifacts():
 return hashes(p for p in OUT.rglob('*') if p.is_file() and p!=OUT/'report.typed' and 'audit' not in p.relative_to(OUT).parts)

def verify(report=None,override=None):
 report=report or load(OUT/'report.typed');override=override or {}
 need(report['status']=='FINITE_ACTUAL_RUST_LRU_BRIDGE_PARITY_PASS','report status')
 for key,value in (('rows_per_run',640),('properties_per_run',12),('candidate_runs',4)):need(type(report[key])is int and report[key]==value,'typed report '+key)
 def data(path):return Path(override.get(str(path),path)).read_bytes()
 same(sorted(report['artifacts']),sorted(artifacts()),'exact acquisition artifact membership')
 same(report['inputs'],load(OUT/'inputs-before.typed'),'exact precompile input membership')
 for field in ('inputs','artifacts'):
  for p,h in report[field].items():
   s=Path(p).lstat();need(stat.S_ISREG(s.st_mode) or field=='inputs','regular products');need(field=='inputs' or s.st_nlink==1,'nonaliased product')
   need(hashlib.sha256(data(p)).hexdigest()==h,field+' drift '+p)
 canonical.verify();same(recipe(),load(OUT/'recipe.typed'),'retained configured profile')
 closure=load(OUT/'source-closure.typed');same(build_provenance.source_snapshot(ROOT),closure['live'],'live source membership')
 same(hashes(BOUNDARY.glob('*')),load(OUT/'boundary-membership.typed'),'boundary source membership')
 same(hashes(p for p in HERE.glob('*') if p.suffix in ('.py','.cpp')),load(OUT/'runner-membership.typed'),'runner source membership')
 same(source_delta(closure['historical'],closure['live'],set(closure['compile_dependencies'])),closure['delta'],'retained source delta proof')
 same(source_policy_controls(),load(OUT/'source-policy-controls.typed'),'source delta controls')
 same(baseline(),load(OUT/'historical-native.typed'),'historical native reference identity')
 verify_commands(report,data)
 for alias in ('ordered','hash'):
  first=data(OUT/('run-'+alias+'-1.stdout'));need(compare(first)==640,'rows')
  same(first,data(OUT/('run-'+alias+'-2.stdout')),'repeat identity')
  same(first,(BASELINE/('original-'+alias+'-1.stdout')).read_bytes(),'actual Rust versus historical native bytes')
 need(data(OUT/'controls-run.stdout')==b'controls\t40\nunbounded-positive\t350001 evictions\t193 nested invocations\n','native class and unbounded protocol controls')
 lines=data(OUT/'unwind-run.stdout').splitlines()
 need(lines[-1]==b'NATIVE_UNWIND_CONTROLS_PASS' and b'ITERATOR_UNWIND_CONTROLS_PASS'in lines,'native unwind witnesses')
 expected=[b'comparison\t'+alias+b'\t'+test+b'\tequal' for alias in (b'ordered',b'hash') for test in (b'success',b'copy-fault',b'copy-fault-reentry')]
 same([line for line in lines if line.startswith(b'comparison\t')],expected,'real alias copy fault/reentry equality')
 sdk_before=load(OUT/'sdk-before.typed');same(sdk_before,load(OUT/'sdk-after.typed'),'SDK unchanged');r=recipe()
 sdk_witness.verify(sdk_before,r['flags'][r['flags'].index('-isysroot')+1],SDK)
 for name in ('candidate','controls','unwind'):same(origins(name,r,sdk_before,data),codec.loads(data(OUT/(name+'-origin.typed')).decode('ascii')),'reconstructed actual Rust origin')
 return True


def acquire():
 canonical.verify();need(not (OUT/'recipe.typed').exists(),'fresh bridge acquisition only')
 need((OUT/'bridge-ready.typed').is_file(),'parent native unwind readiness notification required')
 ready=load(OUT/'bridge-ready.typed');need(sha(BOUNDARY/'cache.hpp')==ready['cache_sha256'] and sha(ready['native_report'])==ready['native_report_sha256'],'parent-ready dependency bytes')
 r=recipe();dump(OUT/'recipe.typed',r);dump(OUT/'source-policy-controls.typed',source_policy_controls());dump(OUT/'historical-native.typed',baseline())
 need(sha(ROOT/'source/core/StarLruCache.hpp')==inventory.HEADER_SHA,'frozen native header')
 need(model.literal_checks()==6 and len(model.corpus())==640,'frozen model units')
 write(OUT/'probe.cpp',(HERE.parent/'lru-cache/native.cpp').read_bytes())
 write(OUT/'selected.hpp',('#include "'+str(BOUNDARY/'cache.hpp')+'"\n#define SELECTED LruBoundary\n').encode())
 corpus=('\n'.join('\t'.join(map(str,row)) for row in model.corpus())+'\n').encode();write(OUT/'corpus.tsv',corpus);write(OUT/'expected.tsv',model.expected())
 c=r['compiler'];flags=r['flags'];sources={'candidate':OUT/'probe.cpp','controls':HERE/'controls.cpp','unwind':BOUNDARY/'unwind.cpp'}
 sdk=flags[flags.index('-isysroot')+1];sdk_before=sdk_witness.capture(sdk,SDK);dump(OUT/'sdk-before.typed',sdk_before)
 command('retained-deps',[NINJA,'-t','deps',*[str(Path(p).relative_to(CM)) for p in r['objects']]],cwd=CM)
 deps=set();found=[]
 for block in (OUT/'retained-deps.stdout').read_text().strip().split('\n\n'):
  lines=block.splitlines();match=re.fullmatch(r'(.+): #deps ([0-9]+), deps mtime ([0-9]+) \(VALID\)',lines[0]);need(match is not None,'valid retained dependencies')
  found.append(str(CM/match[1]));need(len(lines)-1==int(match[2]),'retained dependency count')
  deps.update(Path(p.strip()) if Path(p.strip()).is_absolute() else CM/p.strip() for p in lines[1:])
 same(found,r['objects'],'retained dependency membership')
 for name,src in sources.items():
  command(name+'-deps',[c,*flags,'-M','-MT',name+'.o','-MF',OUT/(name+'.d'),src],cwd=CM)
  _,tail=(OUT/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)
  deps.update(Path(p) if Path(p).is_absolute() else CM/p for p in shlex.split(tail))
 proof_path=build_provenance.sidecar(ROOT/'build/behavior/path-embed-combined-r1/reference/bin/starbound')
 proof=json.loads(proof_path.read_text());live=build_provenance.source_snapshot(ROOT)
 compile_dependencies={str(p.resolve()) for p in deps}|{str(Path(p).resolve()) for p in proof.get('compile_source_files',{})}
 delta=source_delta(proof['source_files'],live,compile_dependencies)
 dump(OUT/'source-closure.typed',{'historical':proof['source_files'],'live':live,'compile_dependencies':sorted(compile_dependencies),'delta':delta})
 dump(OUT/'boundary-membership.typed',hashes(BOUNDARY.glob('*')))
 dump(OUT/'runner-membership.typed',hashes(p for p in HERE.glob('*') if p.suffix in ('.py','.cpp')))
 for p,h in proof.get('compile_source_files',{}).items():need(sha(p)==h,'retained compiler source '+p)
 for p,h in proof['build_identity']['files'].items():need(sha(p)==h,'retained configured profile '+p)
 deps.update(ROOT/p for p in live);deps.add(proof_path);deps.update(map(Path,proof.get('compile_source_files',{})))
 deps.update(Path(p) for p in r['libraries'] if Path(p).is_file());deps.update(map(Path,r['objects']));deps.update(BOUNDARY.glob('*'));deps.update(p for p in HERE.glob('*') if p.suffix in ('.py','.cpp'))
 deps.update((HERE.parent/'lru-cache'/p) for p in ('native.cpp','model.py','inventory.py','CONTRACT.md','StarLruCache.original.hpp'))
 deps.update((HERE.parent/p) for p in ('native_evidence_json.py','native_symbols.py','native_artifacts.py'))
 deps.update((HERE.parent/'path-embed-replay').glob('*.py'));deps.add(HERE.parent/'behavior/build_provenance.py')
 deps.update(map(Path,canonical.verify()['inputs']));deps.update([ARCHIVE,OUT/'canonical.typed',OUT/'canonical-inputs-before.typed',OUT/'bridge-ready.typed',Path(ready['native_report'])])
 deps.update([Path(c),Path(NINJA),Path(sys.executable).resolve(),CM/'compile_commands.json',CM/'build.ninja',CM/'CMakeFiles/rules.ninja',CM/'CMakeCache.txt',CM/'.ninja_deps'])
 deps.update(OUT/p for p in ('recipe.typed','corpus.tsv','expected.tsv','probe.cpp','selected.hpp','sdk-before.typed','source-closure.typed','boundary-membership.typed','runner-membership.typed','source-policy-controls.typed','historical-native.typed'))
 deps={p for p in deps if p.is_file()};inputs=hashes(deps);dump(OUT/'inputs-before.typed',inputs);print('PRECOMPILE_BOUND',len(inputs),flush=True)
 c11=('#include "'+str(BOUNDARY/'host_api.h')+'"\n_Static_assert(sizeof(SbLruRequest)==16,"request");\n_Static_assert(sizeof(SbLruReply)==16,"reply");\n').encode()
 command('c11',[c,'-x','c','-std=c11','-isysroot',sdk,'-fsyntax-only','-'],c11,cwd=CM)
 for name,src in sources.items():
  command(name+'-compile',[c,*flags,'-c',src,'-o',OUT/(name+'.o')],cwd=CM);same(inputs,hashes(deps),'postcompile input drift')
 for name in sources:
  link=[c,*flags,*r['objects'],OUT/(name+'.o'),ARCHIVE,*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(OUT/(name+'.map')),'-Wl,-t,-trace_implicit_libraries','-o',OUT/name]
  _,stderr=command(name+'-expand',[c,'-###',*link[1:]],cwd=CM)
  commands=[shlex.split(line) for line in stderr.decode().splitlines() if line.lstrip().startswith('"')];need(len(commands)==1,'single expanded linker')
  bound=expanded_invocation.bind(commands[0]);dump(OUT/(name+'-expanded.typed'),bound)
  physical={path:[{k:m[k] for k in ('name','offset','sha256')} for m in archive_identity.arm64_archive_members(Path(path).read_bytes())] for path in bound['inventory']['file_inputs'] if path.endswith('.a')}
  dump(OUT/(name+'-physical-prelink.typed'),{'archives':physical,'rust_providers':archive_providers()})
  command(name+'-link',link,cwd=CM);command(name+'-disassemble',['/usr/bin/otool','-tvV',OUT/name],cwd=CM)
  dump(OUT/(name+'-origin.typed'),origins(name,r,sdk_before));print('ACTUAL_RUST_ORIGIN',name,flush=True)
 same(build_provenance.source_snapshot(ROOT),live,'preexecute source membership');same(inputs,hashes(deps),'preexecute input drift')
 dump(OUT/'preexecute.typed',artifacts())
 for alias in ('ordered','hash'):
  for repeat in (1,2):stdout,_=command('run-'+alias+'-'+str(repeat),[OUT/'candidate',alias],corpus,cwd=CM);compare(stdout)
  print('RUST_NATIVE_MODEL_PASS',alias,640,12,flush=True)
 command('controls-run',[OUT/'controls'],cwd=CM);command('unwind-run',[OUT/'unwind'],cwd=CM)
 dump(OUT/'sdk-after.typed',sdk_witness.capture(sdk,SDK));same(sdk_before,load(OUT/'sdk-after.typed'),'SDK drift');same(inputs,hashes(deps),'final input drift')
 report={'status':'FINITE_ACTUAL_RUST_LRU_BRIDGE_PARITY_PASS','inputs':inputs,'artifacts':artifacts(),'rows_per_run':640,'properties_per_run':12,'candidate_runs':4,'canonical_archive_sha256':sha(ARCHIVE),'baseline':baseline(),'limits':'finite actual Rust/native laboratory parity; no production/default selector/game adoption or universal equivalence'}
 dump(OUT/'report.typed',report);verify();print('FINITE_ACTUAL_RUST_LRU_BRIDGE_PARITY_PASS',sha(OUT/'report.typed'),flush=True)

if __name__=='__main__':
 if sys.argv[1:]==['--verify']:verify();print('STRICT_READONLY_RUST_BRIDGE_REPLAY_PASS')
 elif not sys.argv[1:]:acquire()
 else:raise SystemExit('usage: acquire.py [--verify]')
