// Value characterization only. No StarJson/StarList: those can instantiate a
// second production StaticVector beside the frozen owned definition.
#include <algorithm>
#include <cstddef>
#include <initializer_list>
#include <iostream>
#include <iterator>
#include <new>
#include <set>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>
#ifndef STATIC_VECTOR_TEST_HEADER
#define STATIC_VECTOR_TEST_HEADER "StarStaticVector.original.hpp"
#endif
#include STATIC_VECTOR_TEST_HEADER

namespace {
using Star::StaticVector;
using V = StaticVector<int, 4>;

void json(std::string const& s) {
  std::cout << '"';
  for (unsigned char c : s) {
    if (c == '"' || c == '\\') std::cout << '\\' << char(c);
    else if (c < 32) {
      static char const* digits = "0123456789abcdef";
      std::cout << "\\u00" << digits[c >> 4] << digits[c & 15];
    } else std::cout << char(c);
  }
  std::cout << '"';
}
void json(bool b) { std::cout << (b ? "true" : "false"); }
template <class T, typename std::enable_if<std::is_integral<T>::value && !std::is_same<T, bool>::value, int>::type = 0>
void json(T n) { std::cout << n; }
template <class T> void json(std::vector<T> const& v) {
  std::cout << '[';
  bool first = true;
  for (auto const& n : v) { if (!first) std::cout << ','; first = false; json(n); }
  std::cout << ']';
}
template <class E, size_t N> void json(StaticVector<E, N> const& v) {
  std::cout << '[';
  bool first = true;
  for (auto const& n : v) { if (!first) std::cout << ','; first = false; json(n); }
  std::cout << ']';
}
std::set<std::string> names;
void start(std::string const& name) {
  if (!names.insert(name).second) throw std::logic_error("duplicate case: " + name);
  if (names.size() != 1) std::cout << ',';
  std::cout << "{\"name\":"; json(name); std::cout << ",\"value\":";
}
template <class T> void emit(std::string const& name, T const& value) {
  start(name); json(value); std::cout << '}';
}
template <class E, size_t N, class F>
void error(std::string const& name, StaticVector<E, N>& state, F action) {
  // Exact derived catches, not a generic std::exception message oracle.
  std::string type, what;
  try { action(); }
  catch (Star::StaticVectorSizeException const& e) { type = "StaticVectorSizeException"; what = e.what(); }
  catch (Star::OutOfRangeException const& e) { type = "OutOfRangeException"; what = e.what(); }
  start(name); std::cout << '['; json(type); std::cout << ',';
  json(what); std::cout << ','; json(state); std::cout << "]}";
}
template <size_t N> void defaults() {
  StaticVector<int, N> v;
  auto suffix = std::to_string(N);
  emit("default." + suffix, v);
  emit("meta." + suffix, std::vector<size_t>{v.size(), v.empty(), v.MaximumSize,
      v.ptr() != nullptr, v.begin() == v.end()});
}
// Int values qualify value branches only, not comparator call order/count.
// Comparison JSON must be booleans, not numerically equivalent integers.
void compareBool(std::string const& name, V const& a, V const& b) {
  start("compare." + name); std::cout << '['; json(a == b);
  std::cout << ','; json(a != b); std::cout << ','; json(a < b); std::cout << "]}";
}
template <size_t N> void abi() {
  json("int." + std::to_string(N));
  std::cout << ":{\"sizeof\":" << sizeof(StaticVector<int, N>)
            << ",\"alignof\":" << alignof(StaticVector<int, N>) << '}';
}
}

int main() {
  std::cout << "{\"schema\":1,\"cases\":[";
  defaults<0>(); defaults<1>(); defaults<2>(); defaults<4>();
  emit("fill.default", V(size_t(2))); emit("fill.value", V(size_t(4), 7));
  emit("fill.zero", StaticVector<int, 0>(size_t(0)));
  emit("list.empty", V{}); emit("list.one", StaticVector<int, 1>{9});
  emit("list.full", V{1, 2, 3, 4});
  int input[] = {1, 2, 3, 4};
  emit("range", V(input + 1, input + 3)); emit("range.empty", V(input, input));
  V source{1, 2}; V copied(source); emit("copy", copied); emit("copy.source", source);
  V empty; emit("copy.empty", V(empty));
  V moved(std::move(source)); emit("move", moved); emit("move.source", source);
  emit("move.empty", V(std::move(empty)));
  StaticVector<short, 2> shorts{3, 4}; emit("convert", V(shorts));
  StaticVector<short, 0> noShorts; emit("convert.empty", V(noShorts));
  V a{9}, b{1, 2, 3};
  bool same = &(a = b) == &a; emit("assign.copy.grow", a); emit("assign.copy.return", same);
  V small{8}; a = small; emit("assign.copy.shrink", a);
  a = empty; emit("assign.copy.empty", a);
  same = &(a = std::move(b)) == &a;
  emit("assign.move.grow", a); emit("assign.move.return", same); emit("assign.move.source", b);
  a = std::move(small); emit("assign.move.shrink", a); emit("assign.move.shrink.source", small);
  a = std::move(empty); emit("assign.move.empty", a);
  V self{1, 2}; auto& alias = self;
  same = &(self = alias) == &self; emit("assign.self.copy", self); emit("assign.self.copy.return", same);
  same = &(self = std::move(alias)) == &self;
  emit("assign.self.move", self); emit("assign.self.move.return", same);
  V access{1, 2, 3, 4}; V const& ca = access;
  emit("access.const", std::vector<int>{ca.at(0), ca[1], ca.ptr()[2], *(ca.end() - 1)});
  access.at(0) = 11; access[1] = 22; access.ptr()[2] = 33; *(access.begin() + 3) = 44;
  emit("access.mutable", access);
  emit("access.reverse", std::vector<int>(access.rbegin(), access.rend()));
  emit("access.const.reverse", std::vector<int>(ca.rbegin(), ca.rend()));
  emit("access.links", std::vector<int>{access.begin() == access.ptr(), ca.begin() == ca.ptr(),
      int(access.end() - access.begin()), int(ca.end() - ca.begin())});
  StaticVector<int, 2> push; push.push_back(5); emit("push.one", push);
  push.push_back(6); emit("push.full", push); push.pop_back(); emit("pop", push);
  push.pop_back(); emit("pop.empty", push);
  V resizing; resizing.emplace_back(8); emit("emplace.back", resizing);
  resizing.resize(4, 6); emit("resize.grow", resizing);
  resizing.resize(4, 99); emit("resize.same", resizing);
  resizing.resize(2); emit("resize.shrink", resizing);
  resizing.resize(4); emit("resize.default", resizing);
  resizing.resize(0); emit("resize.zero", resizing);
  resizing.push_back(1); resizing.clear(); emit("clear", resizing);
  resizing.clear(); emit("clear.again", resizing);
  for (int i = 0; i <= 3; ++i) {
    V v{1, 2, 3}; auto ret = v.insert(v.begin() + i, 9);
    auto name = "insert.single." + std::to_string(i);
    emit(name, v); emit(name + ".return", ret - v.begin());
    V e{1, 2, 3}; e.emplace(e.begin() + i, 9); emit("emplace." + std::to_string(i), e);
  }
  { V v; auto ret = v.insert(v.begin(), 9); emit("insert.empty.vector", v); emit("insert.empty.vector.return", ret - v.begin()); }
  int more[] = {8, 9};
  { V v{1, 2, 3}; auto ret = v.insert(v.begin(), more, more + 1); emit("insert.range.overlap", v); emit("insert.range.overlap.return", ret - v.begin()); }
  for (int i = 0; i <= 2; ++i) {
    V v{1, 2}; auto ret = v.insert(v.begin() + i, more, more + 2);
    auto name = "insert.range." + std::to_string(i);
    emit(name, v); emit(name + ".return", ret - v.begin());
    V e{1, 2}; ret = e.insert(e.begin() + i, more, more);
    name = "insert.empty." + std::to_string(i);
    emit(name, e); emit(name + ".return", ret - e.begin());
  }
  { V v{1, 2}; auto ret = v.insert(v.begin() + 1, {8, 9}); emit("insert.list", v); emit("insert.list.return", ret - v.begin()); }
  { StaticVector<int, 0> v; auto ret = v.insert(v.begin(), more, more); emit("insert.empty.zero", v); emit("insert.empty.zero.return", ret - v.begin()); }
  for (int i = 0; i < 4; ++i) {
    V v{1, 2, 3, 4}; auto ret = v.erase(v.begin() + i);
    auto name = "erase.single." + std::to_string(i);
    emit(name, v); emit(name + ".return", ret - v.begin());
  }
  { StaticVector<int, 1> v{7}; auto ret = v.erase(v.begin()); emit("erase.only", v); emit("erase.only.return", ret - v.begin()); }
  for (int i = 0; i <= 4; ++i) for (int j = i; j <= 4; ++j) {
    V v{1, 2, 3, 4}; auto ret = v.erase(v.begin() + i, v.begin() + j);
    auto name = "erase.range." + std::to_string(i) + "." + std::to_string(j);
    emit(name, v); emit(name + ".return", ret - v.begin());
  }
  { StaticVector<int, 0> v; auto ret = v.erase(v.begin(), v.end()); emit("erase.empty", v); emit("erase.empty.return", ret - v.begin()); }
  V cmp{1, 2}; compareBool("self", cmp, cmp);
  compareBool("empty", V{}, V{}); compareBool("equal", V{1, 2}, V{1, 2});
  compareBool("short", V{1}, V{1, 2}); compareBool("long", V{1, 2}, V{1});
  compareBool("first.less", V{1, 9}, V{2, 0}); compareBool("first.greater", V{2, 0}, V{1, 9});
  compareBool("later.less", V{1, 2}, V{1, 3}); compareBool("later.greater", V{1, 3}, V{1, 2});
  compareBool("empty.left", V{}, V{1}); compareBool("empty.right", V{1}, V{});
  V at{1, 2}; V const& cat = at;
  error("error.at.mutable", at, [&] { (void)at.at(2); });
  error("error.at.const", at, [&] { (void)cat.at(3); });
  error("error.pop", empty, [&] { empty.pop_back(); });
  StaticVector<int, 0> zero;
  error("error.resize.0", zero, [&] { zero.resize(1); });
  error("error.resize.quirk", at, [&] { at.resize(5); });
  error("error.push.0", zero, [&] { zero.push_back(1); });
  StaticVector<int, 1> one{1};
  error("error.push.1", one, [&] { one.push_back(2); });
  StaticVector<int, 2> two{1, 2};
  error("error.emplace.back", two, [&] { two.emplace_back(3); });
  error("error.insert.single", two, [&] { two.insert(two.begin(), 3); });
  error("error.insert.range", two, [&] { two.insert(two.begin(), more, more + 2); });
  error("error.emplace", two, [&] { two.emplace(two.begin(), 3); });
  std::cout << "],\"abiObservations\":{";
  abi<0>(); std::cout << ','; abi<1>(); std::cout << ','; abi<2>(); std::cout << ','; abi<4>();
  std::cout << "}}\n";
}
