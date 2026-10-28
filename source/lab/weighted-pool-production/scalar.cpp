// Successful scalar-only proxy replay; no Item destructor observer exists here.
#include "StarSet.hpp"
#include "StarWeightedPool.hpp"
#include <iostream>
#include <stdexcept>
namespace Star {
struct ProxyRandomSource {double value=0;size_t calls=0;double randd(){++calls;return value;}};
namespace ProxyRandom {static size_t doubles=0,integers=0;double randd(){++doubles;return .75;}uint64_t randu64(){++integers;return UINT64_MAX;}}
static std::vector<uint64_t> seeds;
double proxyStaticRandomDouble(uint64_t seed){seeds.push_back(seed);return double(seed&7)/8;}
}
#include "ProductionProxyWeightedPool.hpp"
using namespace Star;
static void need(bool b,char const*w){if(!b)throw std::runtime_error(w);}
int main(){try{
 ProductionProxyWeightedPool<int>p;ProxyRandomSource r;
 need(p.select(r)==0&&r.calls==0,"empty select source");need(p.select()==0&&ProxyRandom::doubles==0,"empty select global");need(p.select(uint64_t(0))==0&&seeds.empty(),"empty select static");
 need(p.selectIndex(r)==NPos&&r.calls==1,"empty index source");need(p.selectIndex()==NPos&&ProxyRandom::doubles==1,"empty index global");need(p.selectIndex(uint64_t(3))==NPos&&seeds==std::vector<uint64_t>{3},"empty index static");
 p.selectUniques(0);p.selectUniques(3);need(ProxyRandom::integers==2,"zero and empty unique global seed");
 ProductionProxyWeightedPool<int>duplicates;duplicates.add(1,7);duplicates.add(1,7);auto both=duplicates.selectUniques(8,uint64_t(0));need(both==List<int>{7,7},"uniqueness is by index, not value");
 ProductionProxyWeightedPool<int>four;for(int i=0;i<4;++i)four.add(1,i);seeds.clear();auto all=four.selectUniques(10,UINT64_MAX);need(all==List<int>{0,1,2,3}&&seeds==std::vector<uint64_t>{0,1,2,3,4,5,6,7},"wrap, retry and ordered set");
 std::cout<<"PASS\tempty-select-no-random\nPASS\tempty-index-consumes\nPASS\tunique-zero-and-empty-global-seed\nPASS\tunique-index-not-value\nPASS\tunique-seed-wrap-retry-order\n";return 0;
 }catch(std::exception const&e){std::cerr<<e.what()<<'\n';return 1;}}
