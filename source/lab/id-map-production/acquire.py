#!/usr/bin/env python3
"""Parent-only production OFF/ON finite parity; no new game/Cargo generation."""
import datetime as dt,hashlib,json,re,shlex,sys,time
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'build/id-map-production-r2';B=H.parent/'id-map';FRAME=R/'build/id-map-boundary-r1';BRIDGE=R/'build/id-map-rust-bridge-r1';DEADLINE=dt.datetime(2026,10,28,17,48,tzinfo=dt.timezone.utc).timestamp()
sys.dont_write_bytecode=True;sys.path[:0]=[str(H),str(B),str(H.parent/'id-map-boundary'),str(H.parent),str(H.parent/'path-embed-replay')]
import configuration,run as n,model,edge_model,providers,native_symbols,native_evidence_json as codec
from map_bytes import sdk_paths
sha=n.sha;need=n.need;dump=n.dump

def cap():
 need(time.time()<DEADLINE,'production original command deadline');need(n.cleanup.allocated_bytes(O)<=128*1024**2,'128MiB production cap')
def flags_for(name,r):
 row=next(x for x in json.loads((Path(r['cm'])/'compile_commands.json').read_bytes())if x['file']==str(R/name));args=shlex.split(row['command']);flags=[];skip=False
 for x in args[1:]:
  if skip:skip=False;continue
  if x=='-o':skip=True
  elif x not in('-c',row['file']):flags.append(x)
 return flags

def shards(text):
 points=[x.start()for x in re.finditer(r'^template <typename BaseMap>\n',text,re.M)];need(len(points)==11,'class plus ten definitions');points=points[1:];end=text.rfind('\n}\n');return[text[s:points[i+1]if i+1<len(points)else end]for i,s in enumerate(points)]
def main():
 need(not O.exists(),'fresh production root');O.mkdir();(O/'home').mkdir();(O/'tmp').mkdir();n.OUT=O;n.DEADLINE=DEADLINE;n.ADMISSION_NAME='admission.json';n.COMMANDS=[];n.cap=cap
 original=(B/'StarIdMap.original.hpp').read_text();current=(R/'source/core/StarIdMap.hpp').read_text();lab=(H.parent/'id-map-boundary/StarIdMap.hpp').read_text()
 for off,on in zip(shards(original),shards(lab)):need('#ifdef STAR_USE_RUST_ID_MAP\n'+on.replace('IdMapBoundary::','RustIdMapDetail::')+'#else\n'+off+'#endif'in current,'exact qualified ON/original OFF method shards')
 need((R/'source/core/StarIdMapHost.hpp').read_text()==(H.parent/'id-map-boundary/frame.hpp').read_text().replace('IdMapBoundary','RustIdMapDetail'),'exact qualified helper, namespace-only promotion')
 fixture=configuration.prepare(O,R);r=n.recipe();dump(O/'recipe.json',r);c=r['compiler'];cm=Path(r['cm']);selector=R/'build/weighted-pool-game-admission-r1/complete-r1/plan.json';need(sha(selector)==n.PIN,'immutable tool-path selector');old=json.loads(selector.read_bytes());T=old['tools'];sdk=r['flags'][r['flags'].index('-isysroot')+1];usr=Path(c).resolve().parent.parent
 cert=BRIDGE/'certificate.json';need(sha(cert)=='9f6b9a534b5cad5c7533ced744767831d587d9a37b1b20f181195c71f373310a','actual Rust bridge external certificate');saved=json.loads(cert.read_bytes());canonical=BRIDGE/'canonical.json';need(sha(canonical)==saved['products'][str(canonical)],'canonical archive producer pin');canon=json.loads(canonical.read_bytes());archive=Path(canon['archive']);need(sha(archive)==canon['sha256'],'same actual canonical archive')
 previous=json.loads((BRIDGE/'admission.json').read_bytes())
 for p,h in previous['witness']['files'].items():
  if p.startswith(str(R/'source/rust')+'/'):need(sha(p)==h,'unchanged Rust archive source '+p)
 roots=[R/'source/core',R/'source/base',R/'source/game',R/'source/extern',H,B,H.parent/'id-map-boundary',H.parent/'path-embed-replay',H.parent/'ttl-production',O,Path(sdk),usr/'include',usr/'lib/clang',Path(T['CMAKE_COMMAND']).resolve().parent.parent]
 consumer=['source/game/StarStatSet.cpp','source/game/StarStatusController.cpp'];consumer_flags={p:flags_for(p,r)for p in consumer}
 for flags in [r['flags'],*consumer_flags.values()]:
  for i,x in enumerate(flags):
   if x in('-isystem','-isysroot'):roots.append(Path(flags[i+1]))
   elif x.startswith('-I'):roots.append(Path(x[2:]))
 w=n.closure(roots);tools=[Path(c),Path(T['CMAKE_COMMAND']),Path(T['CMAKE_MAKE_PROGRAM']),Path(T['STAR_RUSTC_EXECUTABLE']),Path(T['STAR_CARGO_EXECUTABLE']),Path(T['CMAKE_LINKER']),Path(T['CMAKE_AR']),Path(T['CMAKE_RANLIB']),usr/'lib/libLTO.dylib',usr/'lib/libtapi.dylib',Path('/bin/ps'),Path(sys.executable)]
 for p in tools:w['files'][str(p.resolve(strict=True))]=sha(p);w['aliases'][str(p)]=str(p.resolve(strict=True))
 for p in [*map(Path,r['objects']),*[Path(x)for x in r['libraries']if Path(x).is_absolute()and Path(x).is_file()],archive,canonical,cert,selector,R/'source/CMakeLists.txt',R/'cmake/Rust.cmake',cm/'build.ninja',cm/'compile_commands.json',cm/'CMakeCache.txt',Path(n.__file__),Path(n.sdk_witness.__file__),R/'scripts/cleanup-migration-artifacts.py']:w['files'][str(p.resolve())]=sha(p)
 n.WITNESS=w;before=n.sdk_witness.capture(sdk,sdk);dump(O/'sdk-before.json',before);dump(O/'admission.json',dict(witness=w,recipeSha256=sha(O/'recipe.json'),archive=str(archive),archiveSha256=sha(archive),deadline=DEADLINE,budget=n.budget(),consumerFlags=consumer_flags,scope='fresh production OFF/ON/native consumer/CMake selector graph; no full game/application/Cargo or historical source-guard renewal'))
 outputs={};sdk_roles={};owners=providers.physical(archive);live_roles={}
 for backend in ['off','on']:
  flags=[*r['flags']]+(['-DSTAR_USE_RUST_ID_MAP']if backend=='on'else[])
  for role,source in [('native',B/'native.cpp'),('edges',B/'edges.cpp'),('trace',H/'trace.cpp')]:
   name=backend+'-'+role;n.command(name+'-compile',[c,*flags,'-MD','-MF',O/(name+'.d'),'-c',source,'-o',O/(name+'.o')]);deps=shlex.split((O/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)[1]);n.subset(deps,w);resolved=[str(Path(p).resolve())for p in deps];need(str(R/'source/core/StarIdMap.hpp')in resolved and str(H.parent/'id-map-boundary/StarIdMap.hpp')not in resolved,'actual production header, no lab shadow');need((str(R/'source/core/StarIdMapHost.hpp')in resolved)==(backend=='on'),'host included only ON')
   link=[c,*r['flags'],*r['objects'],str(O/(name+'.o')),*([str(archive)]if backend=='on'else[]),*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(O/(name+'.map')),'-Wl,-t,-trace_implicit_libraries','-o',str(O/name)];n.command(name+'-expand',[c,'-###',*link[1:]]);n.command(name+'-link',link);outputs[name]=n.command(name,[O/name]).decode();need(n.command(name+'-repeat',[O/name]).decode()==outputs[name],'repeat identity');symbols=native_symbols.live_symbols((O/(name+'.map')).read_bytes())
   if backend=='on':live_roles[name]=providers.live(symbols,owners,archive,role=='trace')
   else:need(not any(x.name in providers.EXPORTS for x in symbols),'OFF has no Rust run/count/runtime provider')
   sdk_roles[name]=n.sdk_witness.reconcile_consumed(before,sdk_paths((O/(name+'.map')).read_bytes()),requested_root=sdk,expected_canonical_root=sdk)
  for role,source,extra in [('lazy',B/'native.cpp',['-DIDMAP_LAZY_NEGATIVE']),('hash-move',B/'native.cpp',['-DIDMAP_HASH_MOVE_ONLY_NEGATIVE']),('opaque-auto',H/'trace.cpp',['-DIDMAP_LAZY_AUTO_NEGATIVE'])]:
   name=backend+'-'+role+'-negative';n.command(name,[c,*flags,*extra,'-fsyntax-only',source],expected=1);need('deleted'in(O/(name+'.stderr')).read_text(),'same lazy-copy rejection')
  for p in consumer:n.command(backend+'-syntax-'+Path(p).stem,[c,*consumer_flags[p],*(['-DSTAR_USE_RUST_ID_MAP']if backend=='on'else[]),'-fsyntax-only',R/p])
 for role,reader in [('native',model.verify),('edges',edge_model.verify)]:reader(outputs['off-'+role]);reader(outputs['on-'+role]);need(outputs['off-'+role]==outputs['on-'+role],'production exact native streams '+role)
 trace=lambda text:[x for x in text.splitlines()if x.startswith('TRACE\t')];need(trace(outputs['off-trace'])==trace(outputs['on-trace'])==json.loads((FRAME/'report.json').read_bytes())['typedTraces'],'production typed traces');need('PASS\tproduction-ten-rust-roots\n'in outputs['on-trace'],'all ten production roots')
 for backend in ['off','on']:
  build=O/('cmake-'+backend);args=[T['CMAKE_COMMAND'],'-S',fixture,'-B',build,'-G','Ninja','-DCMAKE_MAKE_PROGRAM='+T['CMAKE_MAKE_PROGRAM'],'-DCMAKE_CXX_COMPILER='+c,'-DCMAKE_OSX_SYSROOT='+sdk,'-DCMAKE_OSX_ARCHITECTURES=arm64','-DSTAR_RUSTC_EXECUTABLE='+T['STAR_RUSTC_EXECUTABLE'],'-DSTAR_CARGO_EXECUTABLE='+T['STAR_CARGO_EXECUTABLE']]+(['-DSTAR_USE_RUST_ID_MAP=ON']if backend=='on'else[]);n.command('cmake-'+backend,args)
 config=configuration.check(O/'cmake-off',O/'cmake-on',T['STAR_RUSTC_EXECUTABLE']);n.unchanged(w);after=n.sdk_witness.capture(sdk,sdk);need(before==after,'SDK before/after');dump(O/'sdk-after.json',after);dump(O/'sdk-consumed.json',sdk_roles);(O/'live-providers.typed').write_text(codec.dumps(live_roles)+'\n')
 result=dict(status='FINITE_PRODUCTION_IDMAP_OFF_ON_PARITY',commands=n.COMMANDS,admissionSha256=sha(O/'admission.json'),configuration=config,typedTraces=trace(outputs['off-trace']),limits=['production selector/default OFF and finite actual Rust native parity, not gameplay/application/full39','actual CMake selector blocks/real Rust.cmake graph, no full platform/game or Cargo execution','signed overflow/full-small-integer nonprogress still unexecuted'])
 result['products']={str(p):sha(p)for p in O.rglob('*')if p.is_file()and p.name!='report.json'};dump(O/'report.json',result);cap();print('REPORT',sha(O/'report.json'))
if __name__=='__main__':main()
