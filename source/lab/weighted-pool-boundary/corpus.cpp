// Successful scalar-only proxy replay; no Item destructor observer exists here.
#include "StarSet.hpp"
#include "BoundaryWeightedPool.hpp"
#include <iostream>
#include <stdexcept>
namespace Star {
struct ProxyRandomSource {double value=0;size_t calls=0;double randd(){++calls;return value;}};
namespace ProxyRandom {static size_t doubles=0,integers=0;double randd(){++doubles;return .75;}uint64_t randu64(){++integers;return UINT64_MAX;}}
static std::vector<uint64_t> seeds;
double proxyStaticRandomDouble(uint64_t seed){seeds.push_back(seed);return double(seed&7)/8;}
}
#include "ProxyBoundaryWeightedPool.hpp"
using namespace Star;
static void need(bool b,char const*w){if(!b)throw std::runtime_error(w);}
int main(){try{size_t n;while(std::cin>>n){ProxyBoundaryWeightedPool<int> p;for(size_t i=0;i<n;++i){double w;std::cin>>w;p.add(w,int(i));}double target;std::cin>>target;ProxyRandomSource r;r.value=target;auto result=p.selectIndex(r);if(result==NPos)std::cout<<-1;else std::cout<<result;std::cout<<'\n';}return 0;}catch(std::exception const&e){std::cerr<<e.what()<<'\n';return 1;}}