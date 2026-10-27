#!/usr/bin/env python3
"""Declared dependency-name/include/driver substitutions; no oracle changes."""
from pathlib import Path
import re,hashlib,json
H=Path(__file__).resolve().parent;N=H.parent/'weighted-pool'
transforms=[]
def put(name,src,text,description):
 (H/name).write_text(text);transforms.append(dict(output=name,input=str(src),inputSha256=hashlib.sha256(src.read_bytes()).hexdigest(),transformation=description))
p=H/'BoundaryWeightedPool.hpp';s=p.read_text()
proxy=s.replace('BoundaryWeightedPool','ProxyBoundaryWeightedPool').replace('RandomSource','ProxyRandomSource').replace('Random::','ProxyRandom::').replace('staticRandomDouble','proxyStaticRandomDouble')
put('ProxyBoundaryWeightedPool.hpp',p,proxy,'dependency names only, matching frozen native proxy')
p=N/'scalar.cpp';s=p.read_text().replace('#include "StarWeightedPool.hpp"','#include "BoundaryWeightedPool.hpp"').replace('"StarWeightedPool.proxy.hpp"','"ProxyBoundaryWeightedPool.hpp"').replace('ProxyWeightedPool','ProxyBoundaryWeightedPool');put('scalar.cpp',p,s,'header/class names only')
p=N/'lifecycle.cpp';s=p.read_text().replace('#include "StarWeightedPool.hpp"','#include "BoundaryWeightedPool.hpp"').replace('#include "StarWeightedPool.cached-mutant.hpp"','').replace('else if(mode=="mutant")run<CachedWeightedPool>();','');s=re.sub(r'\bWeightedPool\b','BoundaryWeightedPool',s);put('lifecycle.cpp',p,s,'header/class names only; remove unavailable mutant route (original mutant still frozen separately)')
p=H/'scalar.cpp';s=p.read_text().split('int main()')[0]+'''int main(){try{size_t n;while(std::cin>>n){ProxyBoundaryWeightedPool<int> p;for(size_t i=0;i<n;++i){double w;std::cin>>w;p.add(w,int(i));}double target;std::cin>>target;ProxyRandomSource r;r.value=target;auto result=p.selectIndex(r);if(result==NPos)std::cout<<-1;else std::cout<<result;std::cout<<'\\n';}return 0;}catch(std::exception const&e){std::cerr<<e.what()<<'\\n';return 1;}}''';put('corpus.cpp',p,s,'scalar dependency definitions; original native.cpp stdin corpus loop verbatim modulo class name')
(H/'transformations.json').write_text(json.dumps(transforms,indent=2)+'\n')
