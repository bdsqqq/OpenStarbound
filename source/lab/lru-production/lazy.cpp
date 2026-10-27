#include "StarLruCache.hpp"
#include <memory>

// native templates instantiate only used bodies. a read must not acquire the
// assignment/copy requirements of set/get merely by taking a host address.
struct NoAssign {
  int n = 0;
  NoAssign() = default;
  NoAssign(NoAssign const&) = default;
  NoAssign& operator=(NoAssign const&) = delete;
};
template <typename Cache>
void readOnlyBodies() {
  Cache cache;
  cache.currentSize();
  cache.maxSize();
  cache.ptr(0);
  cache.remove(0);
  cache.clear();
}
template void readOnlyBodies<Star::LruCache<int, NoAssign>>();
template void readOnlyBodies<Star::HashLruCache<int, NoAssign>>();
template void readOnlyBodies<Star::LruCache<int, std::unique_ptr<int>>>();
template void readOnlyBodies<Star::HashLruCache<int, std::unique_ptr<int>>>();
