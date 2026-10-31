#include "StarOrderedSet.hpp"

#include "gtest/gtest.h"

#include <algorithm>
#include <functional>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#ifdef STAR_USE_RUST_ORDERED_SET
#include "StarRustOrderedSet.h"
#endif

using namespace Star;

TEST(OrderedSet, Insert) {
  OrderedSet<int> map{5, 4};
  map.insert(3);
  map.insert(2);
  map.insert(1);

  EXPECT_EQ(map.values(), List<int>({5, 4, 3, 2, 1}));
}

TEST(OrderedSet, AssignClear) {
  OrderedHashSet<int> map1{1, 2, 3};
  OrderedHashSet<int> map2 = map1;
  map1.clear();
  EXPECT_EQ(map1.values(), List<int>());
  EXPECT_EQ(map2.values(), List<int>({1, 2, 3}));
}

TEST(OrderedSet, AddReplace) {
  OrderedHashSet<int> map;
  EXPECT_TRUE(map.add(4));
  EXPECT_TRUE(map.add(6));
  EXPECT_TRUE(map.add(1));
  EXPECT_FALSE(map.add(1));
  EXPECT_TRUE(map.add(2));
  EXPECT_TRUE(map.add(3));
  EXPECT_FALSE(map.add(2));
  EXPECT_TRUE(map.replace(4));
  EXPECT_FALSE(map.replace(5));
  EXPECT_FALSE(map.addBack(6));

  EXPECT_EQ(map.values(), List<int>({1, 2, 3, 4, 5, 6}));
}

TEST(OrderedSet, ReverseIterate) {
  OrderedHashSet<int> map{5, 4, 3, 2, 1};

  List<int> vals;
  for (auto i = map.rbegin(); i != map.rend(); ++i)
    vals.append(*i);
  EXPECT_EQ(vals, List<int>({1, 2, 3, 4, 5}));
}

namespace {
struct Marker { void const* identity; int tag; };
struct Trace {
  std::vector<std::string> events;
  int convert = -1, advance = -1, copy = -1;
  bool compare = false, print = false;
  Marker marker{this, 731};
  Marker const* thrown = nullptr;
  [[noreturn]] void raise() {
    try { throw marker; }
    catch (Marker const& m) { thrown = &m; throw; }
  }
  void log(std::string s) { events.push_back(std::move(s)); }
  void emit(char const* name) const {
    std::cout << "ORDERED_SET_TRACE " << name;
    for (auto const& e : events) std::cout << ' ' << e;
    std::cout << '\n';
  }
};
template <typename F> void sameException(Trace& t, F f) {
  try { f(); FAIL() << "expected Marker"; }
  catch (Marker const& m) {
    EXPECT_EQ(&m, t.thrown);
    EXPECT_EQ(m.identity, t.marker.identity);
    EXPECT_EQ(m.tag, t.marker.tag);
    t.log("caught");
  }
}
struct BoolProxy {
  bool value;
  explicit operator bool() const { return value; }
};
struct Value;
struct Proxy {
  Trace* t; int n;
  Proxy(Trace* t, int n) : t(t), n(n) { t->log("proxy+" + std::to_string(n)); }
  Proxy(Proxy const& p) : Proxy(p.t, p.n) { t->log("proxy-copy"); }
  ~Proxy() { t->log("proxy-" + std::to_string(n)); }
  operator Value() const;
  operator int() const {
    t->log("convert" + std::to_string(n));
    if (t->convert == n) t->raise();
    return n;
  }
};
struct ProbeIterator {
  Trace* t; int n; char role;
  ProbeIterator(Trace* t, int n, char role) : t(t), n(n), role(role) { t->log(std::string("iter+") + role); }
  ProbeIterator(ProbeIterator const& i) : t(i.t), n(i.n), role(i.role) { t->log(std::string("iter-copy") + role); }
  ~ProbeIterator() { t->log(std::string("iter-") + role); }
  Proxy operator*() const { return Proxy(t, n); }
  BoolProxy operator!=(ProbeIterator const& end) const {
    t->log("more" + std::to_string(n)); return {n != end.n};
  }
  ProbeIterator& operator++() {
    t->log("advance" + std::to_string(n));
    if (t->advance == n) t->raise();
    ++n; return *this;
  }
};
// A lone poisoned member begin must NOT suppress range-for's ADL pair.
struct AdlRange {
  Trace* t;
  void begin() const = delete;
  friend ProbeIterator begin(AdlRange const& r) { r.t->log("begin"); return {r.t, 1, 'b'}; }
  friend ProbeIterator end(AdlRange const& r) { r.t->log("end"); return {r.t, 4, 'e'}; }
};
struct MemberRange {
  Trace* t;
  ProbeIterator begin() const { t->log("begin"); return {t, 1, 'b'}; }
  ProbeIterator end() const { t->log("end"); return {t, 4, 'e'}; }
};
template <typename Set> void integerLoops(char const* name) {
  int input[] = {4, 2, 4, 1};
  Set a(std::begin(input), std::end(input)), b{1, 4, 3, 2}, empty;
  EXPECT_EQ(a.values(), List<int>({4, 2, 1}));
  Set copy(a), assigned{99}; assigned = a;
  EXPECT_EQ(copy.values(), a.values()); EXPECT_EQ(assigned.values(), a.values());
  Set const& alias = assigned; assigned = alias;
  Set const& emptyAlias = empty; empty = emptyAlias;
  EXPECT_TRUE(empty.empty()); EXPECT_EQ(assigned.values(), a.values());
  EXPECT_EQ(a.intersection(b).values(), List<int>({1, 4, 2}));
  EXPECT_EQ(b.difference(a).values(), List<int>({3}));
  EXPECT_EQ(a.difference(Set{2}).values(), List<int>({4, 1}));
  EXPECT_TRUE(a.intersection(empty).empty());
  assigned = empty; EXPECT_TRUE(assigned.empty());
  a.addAll(input); a.removeAll(input); EXPECT_TRUE(a.empty());
  for (auto const& item : std::vector<std::pair<Set, std::string>>{{Set{}, "()"}, {Set{7}, "(7)"}, {b, "(1, 4, 3, 2)"}}) {
    std::ostringstream out; EXPECT_EQ(&(out << item.first), &out); EXPECT_EQ(out.str(), item.second);
  }
  std::ostringstream failed; failed.setstate(std::ios::failbit); failed << b;
  EXPECT_TRUE(failed.fail()); EXPECT_TRUE(failed.str().empty());
  std::cout << "ORDERED_SET_TRACE " << name << ' ' << copy << ' ' << b << '\n';
}
template <typename Set> void proxyLoops(char const* name) {
  Trace t;
  {
    Set set; AdlRange range{&t}; set.addAll(range);
    EXPECT_EQ(set.values(), List<int>({1, 2, 3}));
    t.log("added"); set.removeAll(range); EXPECT_TRUE(set.empty());
  }
  t.emit(name);
  Trace member;
  { MemberRange const range{&member}; Set set; set.addAll(range); EXPECT_EQ(set.size(), 3u); }
  member.emit("const-member");
  Trace iter;
  {
    ProbeIterator first(&iter, 1, 'b'), last(&iter, 4, 'e');
    Set set(first, last); EXPECT_EQ(set.values(), List<int>({1, 2, 3}));
  }
  iter.emit("iterator-constructor");
  for (bool increment : {false, true}) {
    Trace failure; if (increment) failure.advance = 2; else failure.convert = 2;
    Set set; AdlRange range{&failure};
    sameException(failure, [&] { set.addAll(range); });
    EXPECT_EQ(set.values(), increment ? List<int>({1, 2}) : List<int>({1}));
    EXPECT_EQ(failure.events.back(), "caught");
    if (!increment)
      EXPECT_EQ(std::count(failure.events.begin(), failure.events.end(), "advance2"), 0);
    EXPECT_EQ(std::count(failure.events.begin(), failure.events.end(), "more3"), 0);
    failure.emit(increment ? "increment-throw" : "conversion-throw");
    Trace removal; if (increment) removal.advance = 2; else removal.convert = 2;
    Set remaining{1, 2, 3}; AdlRange removeRange{&removal};
    sameException(removal, [&] { remaining.removeAll(removeRange); });
    EXPECT_EQ(remaining.values(), increment ? List<int>({3}) : List<int>({2, 3}));
    EXPECT_EQ(std::count(removal.events.begin(), removal.events.end(), "more3"), 0);
    removal.emit(increment ? "remove-increment-throw" : "remove-conversion-throw");
  }
  Trace ctorFailure; ctorFailure.convert = 2;
  sameException(ctorFailure, [&] {
    ProbeIterator first(&ctorFailure, 1, 'b'), last(&ctorFailure, 4, 'e'); Set set(first, last);
  });
  EXPECT_EQ(std::count(ctorFailure.events.begin(), ctorFailure.events.end(), "advance2"), 0);
  ctorFailure.emit("iterator-constructor-throw");
}
struct Value {
  int n;
  static Trace* trace;
  static std::function<void()> onDestroy;
  static std::function<void()> onCopy;
  explicit Value(int n) : n(n) {}
  Value(Value const& v) : n(v.n) {
    if (trace) {
      trace->log("copy" + std::to_string(n));
      if (trace->copy == n) trace->raise();
    }
    if (onCopy) onCopy();
  }
  Value(Value&& v) noexcept : n(v.n) { if (trace) trace->log("move" + std::to_string(n)); }
  ~Value() {
    if (trace) trace->log("destroy" + std::to_string(n));
    if (n == 99 && onDestroy) { auto hook = std::move(onDestroy); onDestroy = {}; hook(); }
  }
  bool operator<(Value const& v) const {
    if (trace) { trace->log("compare"); if (trace->compare) trace->raise(); }
    return n < v.n;
  }
  bool operator==(Value const& v) const { return n == v.n; }
  friend std::ostream& operator<<(std::ostream& out, Value const& v) {
    if (trace) { trace->log("print" + std::to_string(v.n)); if (trace->print && v.n == 2) trace->raise(); }
    return out << v.n;
  }
};
Proxy::operator Value() const { return Value(static_cast<int>(*this)); }
Trace* Value::trace = nullptr;
std::function<void()> Value::onDestroy;
std::function<void()> Value::onCopy;
struct ValueHash { size_t operator()(Value const& v) const { return std::hash<int>{}(v.n); } };
// Reset instrumentation before fixture destruction, including on a failed ASSERT.
struct ValueTrace {
  Trace trace;
  ValueTrace() { Value::trace = &trace; }
  ~ValueTrace() { Value::trace = nullptr; Value::onDestroy = {}; Value::onCopy = {}; }
};
template <typename Set> void valueLoops(char const* name) {
  Set source, dest; dest.add(Value(99));
  ValueTrace scope; Trace& t = scope.trace;
  // An initially empty source makes an iterator cached before clear observably stale.
  Value::onDestroy = [&] {
    t.log("source-populate"); source.add(Value(1)); source.add(Value(2)); source.add(Value(3));
  };
  dest = source;
  EXPECT_EQ(dest.size(), 3u); EXPECT_EQ(dest.last().n, 3);
  t.log("self"); auto before = t.events.size(); Set const& alias = dest; dest = alias;
  EXPECT_EQ(t.events.size(), before);
  Set empty; Set const& emptyAlias = empty; empty = emptyAlias;
  EXPECT_EQ(t.events.size(), before);
  t.log("values");
  { auto values = source.values(); EXPECT_EQ(values.size(), 3u); EXPECT_EQ(values[1].n, 2); }
  t.log("copy-failure"); t.copy = 2;
  sameException(t, [&] { auto values = source.values(); (void)values; });
  EXPECT_EQ(source.size(), 3u);
  dest.clear();
  sameException(t, [&] { dest = source; });
  EXPECT_EQ(dest.size(), 1u); EXPECT_EQ(dest.first().n, 1);
  t.copy = -1; t.log("stream-failure"); t.print = true;
  std::ostringstream out;
  sameException(t, [&] { out << source; }); EXPECT_EQ(out.str(), "(1, ");
  EXPECT_EQ(std::count(t.events.begin(), t.events.end(), "print3"), 0);
  t.print = false;
  std::ostringstream failed; failed.setstate(std::ios::failbit); failed << source;
  EXPECT_TRUE(failed.str().empty());
  // Even failed streams still visit each user-defined value inserter.
  EXPECT_EQ(t.events.back(), "print3");
  t.emit(name);
}
}

TEST(OrderedSet, LoopFamilyPublicContracts) {
  integerLoops<OrderedSet<int>>("ordered-int");
  integerLoops<OrderedHashSet<int>>("hash-int");
}
TEST(OrderedSet, LoopFamilyProxyLifetimesAndExceptions) {
  proxyLoops<OrderedSet<int>>("ordered-proxy");
  proxyLoops<OrderedHashSet<int>>("hash-proxy");
}
TEST(OrderedSet, LoopFamilyValueLifetimesAndExceptions) {
  valueLoops<OrderedSet<Value>>("ordered-value");
  valueLoops<OrderedHashSet<Value, ValueHash>>("hash-value");
  OrderedSet<Value> set;
  ValueTrace scope; scope.trace.compare = true; AdlRange range{&scope.trace};
  sameException(scope.trace, [&] { set.addAll(range); });
  EXPECT_EQ(set.size(), 1u); EXPECT_EQ(set.first().n, 1);
  EXPECT_EQ(std::count(scope.trace.events.begin(), scope.trace.events.end(), "advance2"), 0);
  EXPECT_EQ(std::count(scope.trace.events.begin(), scope.trace.events.end(), "more3"), 0);
  scope.trace.emit("comparator-throw");
}
namespace {
template <typename Set> void selectionContracts() {
  Set set;
  auto inserted = set.insert(2);
  EXPECT_TRUE(inserted.second);
  EXPECT_FALSE(set.insert(2).second);
  EXPECT_EQ(&*inserted.first, &set.first());
  EXPECT_TRUE(set.addFront(1)); EXPECT_FALSE(set.addFront(2));
  EXPECT_TRUE(set.addBack(3)); EXPECT_FALSE(set.addBack(2));
  EXPECT_EQ(set.values(), List<int>({1, 3, 2}));
  EXPECT_EQ(&set.first(), &*set.begin());
  EXPECT_EQ(&set.last(), &*std::prev(set.end()));
  ASSERT_TRUE(set.indexOf(3)); EXPECT_EQ(*set.indexOf(3), 1u);
  EXPECT_FALSE(set.indexOf(99));
  EXPECT_TRUE(set.remove(3)); EXPECT_FALSE(set.remove(3));
  EXPECT_EQ(set.takeFirst(), 1); EXPECT_EQ(set.takeLast(), 2);
  set.add(4); set.removeFirst(); set.add(5); set.removeLast();
  EXPECT_TRUE(set.empty());
  std::function<void()> calls[] = {
    [&] { (void)set.first(); }, [&] { (void)set.last(); },
    [&] { set.removeFirst(); }, [&] { set.removeLast(); },
    [&] { (void)set.takeFirst(); }, [&] { (void)set.takeLast(); }
  };
  char const* messages[] = {
    "(SetException) first() called on empty OrderedSet",
    "(SetException) last() called on empty OrderedSet",
    "(SetException) OrderedSet::removeFirst() called on empty OrderedSet",
    "(SetException) OrderedSet::removeLast() called on empty OrderedSet",
    "(SetException) OrderedSet::takeFirst() called on empty OrderedSet",
    "(SetException) OrderedSet::takeLast() called on empty OrderedSet"
  };
  for (size_t i = 0; i != 6; ++i) {
    try { calls[i](); FAIL() << "expected SetException " << i; }
    catch (SetException const& e) { EXPECT_STREQ(e.what(), messages[i]); }
  }
}
template <typename Set> void takeCopyFailure() {
  for (bool front : {true, false}) {
    Set set; set.add(Value(1)); set.add(Value(2));
    ValueTrace scope; auto& t = scope.trace; t.copy = front ? 1 : 2;
    sameException(t, [&] { if (front) (void)set.takeFirst(); else (void)set.takeLast(); });
    // Native take erases the map entry BEFORE copying: the list orphan stays.
    t.copy = -1;
    EXPECT_EQ(set.size(), 1u); EXPECT_FALSE(set.contains(Value(front ? 1 : 2)));
    auto values = set.values(); ASSERT_EQ(values.size(), 2u);
    EXPECT_EQ(values[0].n, 1); EXPECT_EQ(values[1].n, 2);
  }
}
}
TEST(OrderedSet, SelectionPublicContracts) {
  selectionContracts<OrderedSet<int>>();
  selectionContracts<OrderedHashSet<int>>();
}
TEST(OrderedSet, SelectionPreservesNativePartialMutation) {
  takeCopyFailure<OrderedSet<Value>>();
  takeCopyFailure<OrderedHashSet<Value, ValueHash>>();
  for (int operation = 0; operation != 3; ++operation) {
    OrderedSet<Value> set; set.add(Value(1));
    ValueTrace scope; auto& t = scope.trace;
    // find succeeds first; copying the new list node arms map-insert failure.
    Value::onCopy = [&] { t.compare = true; };
    sameException(t, [&] {
      if (operation == 0) set.insert(Value(2));
      else if (operation == 1) set.addFront(Value(2));
      else set.addBack(Value(2));
    });
    Value::onCopy = {}; t.compare = false;
    EXPECT_EQ(set.size(), 1u); EXPECT_FALSE(set.contains(Value(2)));
    auto values = set.values(); ASSERT_EQ(values.size(), 2u);
    EXPECT_EQ(values[operation == 1 ? 0 : 1].n, 2);
  }
}
#ifdef STAR_USE_RUST_ORDERED_SET
TEST(OrderedSet, SelectionAllRustModesReachedThroughPublicApis) {
  uint64_t before[SB_ORDERED_SET_SELECT_COUNT];
  for (uint32_t i = 0; i != SB_ORDERED_SET_SELECT_COUNT; ++i)
    before[i] = sb_ordered_set_select_count(i);
  selectionContracts<OrderedSet<int>>();
  for (uint32_t i = 0; i != SB_ORDERED_SET_SELECT_COUNT; ++i)
    EXPECT_GT(sb_ordered_set_select_count(i) - before[i], 0u) << "selection mode " << i;
}
TEST(OrderedSet, LoopFamilyAllRustModesReachedThroughPublicApis) {
  uint64_t before[SB_ORDERED_SET_COUNT];
  for (uint32_t i = 0; i != SB_ORDERED_SET_COUNT; ++i) before[i] = sb_ordered_set_count(i);
  OrderedSet<int> a{1, 2}, b{2, 3};
  a.addAll(b); a.removeAll(std::vector<int>{3}); auto values = a.values();
  auto intersection = a.intersection(b); auto difference = a.difference(b);
  std::ostringstream out; out << a; a = b;
  for (uint32_t i = 0; i != SB_ORDERED_SET_COUNT; ++i)
    EXPECT_GT(sb_ordered_set_count(i) - before[i], 0u) << "mode " << i;
}
#endif
