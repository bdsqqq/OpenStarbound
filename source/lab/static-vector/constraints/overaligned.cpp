// Compile-only positive; not a runtime address or cross-platform ABI claim.
#include <cstddef>
#include <initializer_list>
#include <iterator>
#include <new>
#include <type_traits>
#include <utility>
#ifndef STATIC_VECTOR_TEST_HEADER
#define STATIC_VECTOR_TEST_HEADER "../StarStaticVector.original.hpp"
#endif
#include STATIC_VECTOR_TEST_HEADER

struct alignas(64) Aligned { int value; explicit Aligned(int n) : value(n) {} };
using V = Star::StaticVector<Aligned, 2>;
static_assert(alignof(V) >= alignof(Aligned), "element storage loses alignment");
void probe() {
  V v;
  v.emplace_back(7);
  v.clear();
}
