// Compile-only positive: unused resize/copy members must stay lazy.
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

struct MoveOnly {
  int value;
  MoveOnly() = delete;
  explicit MoveOnly(int n) : value(n) {}
  MoveOnly(MoveOnly const&) = delete;
  MoveOnly& operator=(MoveOnly const&) = delete;
  MoveOnly(MoveOnly&&) = default;
  MoveOnly& operator=(MoveOnly&&) = default;
};
void probe() {
  Star::StaticVector<MoveOnly, 2> v;
  v.emplace_back(7);
  v.clear();
}
