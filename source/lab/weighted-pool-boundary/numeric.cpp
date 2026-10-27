// Compile-only observation of the ORIGINAL numerical scan under the frozen
// production flags. Dependency-name proxy changes no loop/arithmetic body.
#include "StarSet.hpp"
#include "StarRandom.hpp"
namespace Star {
struct ProxyRandomSource {double target;double randd(){return target;}};
namespace ProxyRandom {double randd();uint64_t randu64();}
double proxyStaticRandomDouble(uint64_t);
}
#include "StarWeightedPool.proxy.hpp"
extern "C" size_t weighted_native_numeric(Star::ProxyWeightedPool<int> const* pool,double target){Star::ProxyRandomSource random{target};return pool->selectIndex(random);}
