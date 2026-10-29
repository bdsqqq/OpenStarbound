// Compile-only NEGATIVE: copy construction calls insert -> resize's Element().
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

struct NoDefault {
  int value;
  NoDefault() = delete;
  explicit NoDefault(int n) : value(n) {}
  NoDefault(NoDefault const&) = default;
  NoDefault(NoDefault&&) = default;
  NoDefault& operator=(NoDefault const&) = default;
  NoDefault& operator=(NoDefault&&) = default;
};
void probe() {
  Star::StaticVector<NoDefault, 2> source;
  source.emplace_back(7);
  Star::StaticVector<NoDefault, 2> copied(source);
}
