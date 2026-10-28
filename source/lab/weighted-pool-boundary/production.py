#!/usr/bin/env python3
"""Promote the exact qualified inline continuation; no policy/body refitting."""
import hashlib,json,re
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];F=H.parent/'weighted-pool-production';F.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ad=json.loads((R/'build/weighted-pool-inline-r1/acquisition/admission.json').read_bytes())
for name in ['BoundaryWeightedPool.hpp','frame.hpp']:
 p=H/name;assert sha(p)==ad['witness']['files'][str(p)],name
native=(H.parent/'weighted-pool/StarWeightedPool.original.hpp').read_text().replace('ReferenceWeightedPool','WeightedPool')
core=(H/'BoundaryWeightedPool.hpp').read_text().replace('BoundaryWeightedPool','WeightedPool').replace('WpBoundary::','RustWeightedPoolDetail::').replace('using namespace WpBoundary;','using namespace RustWeightedPoolDetail;').replace('#if WP_BOUNDARY_ON','#ifdef STAR_USE_RUST_WEIGHTED_POOL')
core=core.replace('#include "StarSet.hpp"\n#include "frame.hpp"','#ifdef STAR_USE_RUST_WEIGHTED_POOL\n#include "StarSet.hpp"\n#include "StarWeightedPoolHost.hpp"\n#endif')
a=core.index('  template<unsigned Mode> struct NativeFrame');b=core.index('  ItemsList m_items;',a);core=core[:a]+'#ifdef STAR_USE_RUST_WEIGHTED_POOL\n'+core[a:b]+'#endif\n'+core[b:]
host=(H/'frame.hpp').read_text().replace('namespace WpBoundary {','namespace Star::RustWeightedPoolDetail {')
p=R/'source/core/StarWeightedPool.hpp';assert p.read_text()in[native,core],'unrelated core edit';p.write_text(core);(R/'source/core/StarWeightedPoolHost.hpp').write_text(host)
transforms=[]
def put(name,input,text,why):
 (F/name).write_text(text);transforms.append(dict(output=name,input=str(input),inputSha256=sha(input),transformation=why))
# A proxy changes dependency spellings only; actual production-header int/Value
# fixtures separately retain native Random and all19 real method routes.
proxy=re.sub(r'\bWeightedPool\b','ProductionProxyWeightedPool',core).replace('RandomSource','ProxyRandomSource').replace('Random::','ProxyRandom::').replace('staticRandomDouble','proxyStaticRandomDouble')
put('ProductionProxyWeightedPool.hpp',p,proxy,'class and Random dependency names only; original selector preserved')
for name in ['lifecycle.cpp','scalar.cpp','probe.cpp','integration.cpp','combined.cpp']:
 source=H/name;s=source.read_text().replace('"BoundaryWeightedPool.hpp"','"StarWeightedPool.hpp"').replace('"ProxyBoundaryWeightedPool.hpp"','"ProductionProxyWeightedPool.hpp"').replace('ProxyBoundaryWeightedPool','ProductionProxyWeightedPool')
 # Existing native/current comparison class becomes the frozen reference;
 # candidate class becomes the ACTUAL production class, not another adapter.
 s=s.replace('BoundaryWeightedPool','CandidatePlaceholder');s=re.sub(r'\bWeightedPool\b','ReferenceWeightedPool',s);s=s.replace('CandidatePlaceholder','WeightedPool').replace('WpBoundary::','Star::RustWeightedPoolDetail::').replace('using namespace WpBoundary;','using namespace Star::RustWeightedPoolDetail;')
 if name in ['probe.cpp','integration.cpp']:s='#include "StarWeightedPoolHost.hpp"\n#include "StarWeightedPool.original.hpp"\n'+s
 if name=='probe.cpp':s=s.replace(' std::cout<<"PASS\\t19-root-4-stage-real-reference-layout-lazy-custom-containers\\n";','#if WP_BOUNDARY_ON\n std::cout<<"PASS\\t19-root-4-stage-real-reference-layout-lazy-custom-containers\\n";\n#else\n std::cout<<"PASS\\tnative-production-header-off-reference-layout-lazy-custom-containers\\n";\n#endif')
 put(name,source,s,'actual production class/header; previous native comparison renamed frozen ReferenceWeightedPool; same drivers/assertions')
(F/'transformations.json').write_text(json.dumps(transforms,indent=2)+'\n')
print('production selector/core/host and declared fixture transformations generated')
