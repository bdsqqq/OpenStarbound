#!/usr/bin/env python3
"""One selected TU, canonical aggregate, unchanged all-OFF Core dependencies.
Only run after coordinator's explicit dependency-ready message is recorded.
"""
import re,shlex
from common import *
import guarded_canonical as canonical
import guarded_canonical as admission
import evidence,model,expanded_invocation,archive_identity
BASE=ROOT/'build/ttl-cache-native-r1'
BASE_SHA='cba3b3c84acc2128bd043400cabd6ed2ebf35fcdde37e6d36e2a870bc7926674'
BOUNDARY=HERE.parent/'ttl-boundary'
CM=ROOT/'build/behavior/lru-cache-combined-r1/reference/cmake'

def recipe():
 db=json.loads((CM/'compile_commands.json').read_text());lines=(CM/'build.ninja').read_text().splitlines()
 pos=next(i for i,l in enumerate(lines) if l.startswith('build ') and '/bin/starbound:' in l)
 objects=[str(CM/x) for x in shlex.split(lines[pos].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/'))]
 need(len(objects)==len(set(objects))==113,'113 retained Core/extern objects')
 row=next(x for x in db if x['file']==str(ROOT/'source/core/StarJsonBuilder.cpp'));args=shlex.split(row['command']);flags=[];skip=False
 for t in args[1:]:
  if skip:skip=False;continue
  if t=='-o':skip=True
  elif t not in ('-c',row['file']):flags.append(t)
 libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[pos+1:pos+18] if x.startswith('  LINK_LIBRARIES = ')))
 libs=[str(CM/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
 selectors=re.findall(r'^(STAR_USE_RUST[^:]*):BOOL=(.*)$',(CM/'CMakeCache.txt').read_text(),re.M)
 need(len(selectors)==26 and all(v=='OFF' for _,v in selectors),'26 selectors OFF')
 need(len(db)==472 and not any('-DSTAR_USE_RUST' in x['command'] for x in db),'reference profile')
 need('-O3' in flags and '-ffast-math' in flags,'frozen optimization flags')
 return {'compiler':args[0],'flags':flags,'objects':objects,'libraries':libs,'selectors':selectors}

def baseline():
 need(sha(BASE/'report.json')==BASE_SHA,'independently pinned native baseline')
 report=json.loads((BASE/'report.json').read_bytes())
 need(report['rows']==626,'native baseline rows')
 inputs=json.loads((BASE/'inputs.json').read_bytes())
 same(sorted(inputs.items()),sorted(hashes(map(Path,inputs)).items()),'native baseline consumed inputs unchanged')
 selected=['corpus.tsv','expected.tsv','lifecycle.stdout','real.stdout']+[f'{a}-{i}.stdout' for a in ('ordered','hash') for i in range(2)]
 for name in selected:need(report['products'][str(BASE/name)]==sha(BASE/name),'native selected product '+name)
 need((BASE/'corpus.tsv').read_bytes()==('\n'.join(model.corpus())+'\n').encode(),'frozen 626-row domain')
 need((BASE/'expected.tsv').read_text()==model.expected(model.corpus()),'frozen independent model')
 return {'report_sha256':BASE_SHA,'inputs':inputs,'selected':hashes(BASE/x for x in selected)}

def retained_dependencies(r):
 # The smaller 1142-file TTL fixture map is NOT the 113-object source closure.
 # Independent metadata-only admission bound every actual Ninja object dependency
 # against the accepted historical production compilation witness before configure.
 lineage=load(OUT/'guarded-lineage.typed')
 same(lineage['objects'],r['objects'],'retained object dependency membership')
 need(sha(canonical.RUNTIME)==canonical.RUNTIME_SHA,'qualified Core witness pin')
 for path,h in lineage['dependencies'].items():need(sha(path)==h,'qualified retained source/object lineage '+path)
 for path,h in lineage['metadata'].items():need(sha(path)==h,'retained dependency metadata drift')
 return set(map(Path,lineage['dependencies']))

def fixture_source():
 source=(BOUNDARY/'native.cpp').read_text()
 need(source.count('#include "mock.cpp"')==1,'single mock include to REMOVE')
 source=source.replace('#include "mock.cpp"','// Actual controller symbols supplied ONLY by canonical Rust archive.')
 source=source.replace('#include "controls.inc"','#include "'+str(HERE/'controls.inc')+'"')
 source=source.replace('extern "C" void sb_ttl_mock_dump();','void actualRustCounters(){for(unsigned m=0;m<19;++m)for(unsigned s=0;s<4;++s)std::cerr<<"rust-route\\t"<<m<<"\\t"<<s<<"\\t"<<sb_ttl_count(m,s)<<"\\n";}')
 source=source.replace('sb_ttl_mock_dump();','actualRustCounters();')
 source=source.replace('int main(int argc,char** argv){','#include "'+str(HERE/'extra.inc')+'"\nint main(int argc,char** argv){')
 source=source.replace('TtlControls::run();return 0;','TtlControls::run();ActualRustProtocol::run();return 0;')
 need(source.count('runtimeImages();return 0;')==1,'one real-mode runtime witness site')
 source=source.replace('runtimeImages();return 0;','realSmoke<Star::TtlCache<Key,int>>("native-original-ordered");realSmoke<Star::HashTtlCache<Key,int,Hash>>("native-original-hash");runtimeImages();return 0;')
 need('mock' not in source.lower(),'mock controller absent from selected TU')
 return source.encode()

def acquire():
 admission.require_complete();canonical.verify();ready=load(OUT/'dependency-ready.typed')
 need(ready['status']=='DEPENDENCYREADY' and ready['authority']=='parent-reviewed','explicit coordinator release')
 same(ready['source'],hashes(BOUNDARY.glob('*')),'reviewed dependency pins')
 need(not (OUT/'fixture.cpp').exists(),'one fresh selected fixture only')
 r=recipe();dump(OUT/'recipe.typed',r);dump(OUT/'native-baseline.typed',baseline())
 write(OUT/'fixture.cpp',fixture_source());write(OUT/'corpus.tsv',(BASE/'corpus.tsv').read_bytes())
 sdk=r['flags'][r['flags'].index('-isysroot')+1];before=sdk_witness.capture(sdk,canonical.SDK);dump(OUT/'sdk-before.typed',before)
 paths=set(map(Path,baseline()['inputs']));paths.update(canonical.configured_inputs());paths.update(BOUNDARY.glob('*'));paths.update(p for p in HERE.glob('*') if p.is_file())
 paths.update(ROOT/'source/core'/x for x in ('StarTtlCache.hpp','StarRustTtlCache.h'))
 paths.update(Path(x) for x in r['libraries'] if Path(x).is_file());paths.update(map(Path,r['objects']))
 paths.update((OUT/'fixture.cpp',OUT/'corpus.tsv',canonical.ARCHIVE,OUT/'guarded-canonical.typed',OUT/'guarded-lineage.typed',OUT/'dependency-ready.typed'))
 paths.update(p for p in (HERE.parent/'path-embed-replay').glob('*.py'));paths.update((HERE.parent/'native_evidence_json.py',HERE.parent/'native_symbols.py'))
 pre=hashes(paths);dump(OUT/'precompiler-inputs.typed',pre)
 paths.update(retained_dependencies(r));same(pre,hashes(map(Path,pre)),'pre-dependency input stability')
 c=r['compiler'];flags=[*r['flags'],'-I'+str(BOUNDARY),'-I'+str(HERE.parent/'ttl-cache')]
 command('fixture-deps',[c,*flags,'-M','-MT','fixture.o','-MF',OUT/'fixture.d',OUT/'fixture.cpp'],cwd=CM)
 _,tail=(OUT/'fixture.d').read_text().replace('\\\n',' ').split(':',1)
 discovered={Path(p) if Path(p).is_absolute() else CM/p for p in shlex.split(tail)}
 prior_resolved={str(Path(p).resolve()):h for p,h in pre.items()}
 for p in discovered:need(prior_resolved.get(str(p.resolve()))==sha(p),'source was pinned BEFORE dependency compiler action '+str(p))
 paths.update(discovered)
 inputs=hashes(paths);dump(OUT/'inputs-before.typed',inputs)
 command('c11',[c,'-x','c','-std=c11','-isysroot',sdk,'-fsyntax-only','-'],('#include "'+str(ROOT/'source/core/StarRustTtlCache.h')+'"\n#include <stddef.h>\n_Static_assert(sizeof(SbTtlRequest)==24,"request");\n_Static_assert(sizeof(SbTtlReply)==24,"reply");\n_Static_assert(_Alignof(SbTtlRequest)==8,"align");\n_Static_assert(offsetof(SbTtlRequest,arg)==16,"payload");\n_Static_assert(offsetof(SbTtlReply,value)==16,"payload");\n_Static_assert(SB_TTL_ABI_VERSION==1,"version");\n').encode(),cwd=CM)
 same(inputs,hashes(paths),'before selected compiler')
 command('fixture-compile',[c,*flags,'-c',OUT/'fixture.cpp','-o',OUT/'fixture.o'],cwd=CM)
 same(inputs,hashes(paths),'after selected compiler')
 link=[c,*flags,*r['objects'],OUT/'fixture.o',canonical.ARCHIVE,*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(OUT/'fixture.map'),'-Wl,-t,-trace_implicit_libraries','-o',OUT/'fixture']
 _,stderr=command('fixture-expand',[c,'-###',*link[1:]],cwd=CM)
 commands=[shlex.split(x) for x in stderr.decode().splitlines() if x.lstrip().startswith('"')];need(len(commands)==1,'one expanded linker')
 bound=expanded_invocation.bind(commands[0]);dump(OUT/'fixture-expanded.typed',bound)
 physical={path:[{k:m[k] for k in ('name','offset','sha256')} for m in archive_identity.arm64_archive_members(Path(path).read_bytes())] for path in bound['inventory']['file_inputs'] if path.endswith('.a')}
 dump(OUT/'fixture-physical-prelink.typed',{'archives':physical,'rust_providers':evidence.archive_providers()})
 same(inputs,hashes(paths),'before linker');command('fixture-link',link,cwd=CM)
 command('fixture-disassemble',['/usr/bin/otool','-tvV',OUT/'fixture'],cwd=CM)
 dump(OUT/'fixture-origin.typed',evidence.origins('fixture',r,before))
 same(inputs,hashes(paths),'before runtime')
 corpus=(OUT/'corpus.tsv').read_bytes()
 for alias in ('ordered','hash'):
  for repeat in range(2):command(f'{alias}-{repeat}',[OUT/'fixture',alias],corpus,cwd=CM)
 for mode in ('lifecycle','real','controls'):command(mode,[OUT/'fixture',mode],cwd=CM)
 dump(OUT/'sdk-after.typed',sdk_witness.capture(sdk,canonical.SDK));same(before,load(OUT/'sdk-after.typed'),'SDK stable')
 same(inputs,hashes(paths),'final participating inputs stable')
 import verify
 semantics=verify.semantics(lambda p:Path(p).read_bytes());dump(OUT/'semantic.typed',semantics)
 products=hashes(p for p in OUT.rglob('*') if p.is_file() and p.name not in ('report.typed','HANDOFF.md','acquisition.log'))
 need(sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())<128*1024*1024,'128MiB output cap')
 report={'status':'FINITE_ACTUAL_RUST_TTL_BRIDGE_PASS','inputs':inputs,'products':products,'semantics':semantics,'native_baseline_sha256':BASE_SHA,'canonical_archive_sha256':sha(canonical.ARCHIVE),'limits':'one selected laboratory TU, all-OFF native LRU/Core dependencies; not production class selection/game/adoption, not actual-clock boundary proof, not universal equivalence'}
 dump(OUT/'report.typed',report);verify.verify();print(report['status'],sha(OUT/'report.typed'),flush=True)
if __name__=='__main__':acquire()
