#include "StarOrderedMap.hpp"

#include "gtest/gtest.h"

#include <exception>
#include <functional>
#include <iostream>
#include <iterator>
#include <memory>
#include <string>
#include <type_traits>

#ifdef STAR_USE_RUST_MAP
#include "StarRustMap.h"
#endif

using namespace Star;

TEST(OrderedMap, Insert) {
  OrderedMap<int, int> map;
  map.insert({3, 3});
  map.insert({2, 2});
  map.insert({1, 1});

  {
    List<int> comp = {3, 2, 1};
    EXPECT_EQ(comp, map.keys());
  }

  {
    List<int> comp = {3, 2, 1};
    List<int> keys;
    for (auto i = map.begin(); i != map.end(); ++i)
      keys.append(i->first);
    EXPECT_EQ(comp, keys);
  }

  {
    List<int> comp = {1, 2, 3};
    List<int> keys;
    for (auto i = map.rbegin(); i != map.rend(); ++i)
      keys.append(i->first);
    EXPECT_EQ(comp, keys);
  }
}

TEST(OrderedMap, Getters) {
  OrderedMap<int, int> map;
  map[1] = 1;
  map[2] = 2;
  map[3] = 3;

  EXPECT_EQ(map.get(1), 1);
  EXPECT_EQ(map.get(2), 2);
  EXPECT_EQ(map.get(3), 3);

  EXPECT_EQ(map.ptr(3), &map.get(3));
}

TEST(OrderedMap, ConstGetters) {
  OrderedHashMap<int, int> const map{
    {1, 1},
    {2, 2},
    {3, 3}
  };

  EXPECT_EQ(map.get(1), 1);
  EXPECT_EQ(map.get(2), 2);
  EXPECT_EQ(map.get(3), 3);

  EXPECT_EQ(map.ptr(3), &map.get(3));

  EXPECT_EQ(map.value(4, 4), 4);
  EXPECT_EQ(map.maybe(5), Maybe<int>());
}

TEST(OrderedMap, Sorting) {
  OrderedMap<int, int> map{
    {1, 5},
    {3, 3},
    {2, 4},
    {5, 1},
    {4, 2}
  };

  EXPECT_EQ(map.keys(), List<int>({1, 3, 2, 5, 4}));
  map.sortByKey();
  EXPECT_EQ(map.keys(), List<int>({1, 2, 3, 4, 5}));
  map.sortByValue();
  EXPECT_EQ(map.keys(), List<int>({5, 4, 3, 2, 1}));
}

TEST(OrderedMap, Removing) {
  OrderedHashMap<int, int> map{
    {5, 5},
    {4, 4},
    {3, 3},
    {2, 2},
    {1, 1}
  };

  map.remove(3);
  map.remove(1);
  EXPECT_EQ(map.keys(), List<int>({5, 4, 2}));
}

namespace {
struct OrderedMarker {};
struct OrderedTrace {
  std::string events;
  std::exception_ptr error;
  int copyFailure = -999, moveFailure = -999, compareFailure = -999;
  bool assignFailure = false;
  int live = 0;
  std::function<void(int)> destroyed;
  void log(std::string const& event) { events += event + ","; }
  [[noreturn]] void raise() {
    try { throw OrderedMarker{}; }
    catch (...) { error = std::current_exception(); throw; }
  }
  void emit(char const* name) const { std::cout << "ORDERED_MAP_TRACE " << name << ' ' << events << '\n'; }
};
template <typename F> void orderedFailure(OrderedTrace& trace, F f) {
  try { f(); FAIL() << "expected nonstandard marker"; }
  catch (OrderedMarker const&) {
    EXPECT_EQ(std::current_exception(), trace.error); trace.log("caught");
  }
}
template <typename F> void orderedMessage(F f, char const* message) {
  try { f(); FAIL() << "expected MapException"; }
  catch (MapException const& e) { EXPECT_STREQ(e.what(), MapException(message, false).what()); }
}
struct OrderedBool { bool value; explicit operator bool() const { return value; } };
struct OrderedValue {
  int n;
  static OrderedTrace* trace;
  explicit OrderedValue(int n = 0) : n(n) {
    if (trace) { ++trace->live; trace->log("N" + std::to_string(n)); }
  }
  OrderedValue(OrderedValue const& v) : n(v.n) {
    if (trace) {
      trace->log("C" + std::to_string(n));
      if (trace->copyFailure == n) trace->raise();
      ++trace->live;
    }
  }
  OrderedValue(OrderedValue&& v) : n(v.n) {
    if (trace) {
      trace->log("M" + std::to_string(n));
      if (trace->moveFailure == n) trace->raise();
      ++trace->live;
    }
    v.n = -n;
  }
  OrderedValue& operator=(OrderedValue const&) = default;
  OrderedValue& operator=(OrderedValue&& v) {
    n = v.n;
    if (trace) { trace->log("A" + std::to_string(n)); if (trace->assignFailure) trace->raise(); }
    v.n = -n; return *this;
  }
  ~OrderedValue() {
    if (trace) {
      --trace->live; trace->log("D" + std::to_string(n));
      if (trace->destroyed) trace->destroyed(n);
    }
  }
  friend bool operator<(OrderedValue const& a, OrderedValue const& b) { return a.n < b.n; }
  friend OrderedBool operator==(OrderedValue const& a, OrderedValue const& b) {
    if (trace) {
      trace->log("E" + std::to_string(a.n));
      if (trace->compareFailure == a.n) trace->raise();
    }
    return {a.n == b.n};
  }
  friend std::ostream& operator<<(std::ostream& out, OrderedValue const& v) { return out << v.n; }
};
OrderedTrace* OrderedValue::trace = nullptr;
struct OrderedTracing {
  OrderedTrace* previous;
  explicit OrderedTracing(OrderedTrace& t) : previous(OrderedValue::trace) { OrderedValue::trace = &t; }
  ~OrderedTracing() { OrderedValue::trace = previous; }
};
struct OrderedMovedKey {
  int n;
  explicit OrderedMovedKey(int n) : n(n) {}
  OrderedMovedKey(OrderedMovedKey const&) = default;
  OrderedMovedKey(OrderedMovedKey&& k) : n(k.n) { k.n = -1; }
  friend bool operator<(OrderedMovedKey const& a, OrderedMovedKey const& b) { return a.n < b.n; }
  friend std::ostream& operator<<(std::ostream& out, OrderedMovedKey const& k) { return out << k.n; }
};
struct OrderedAddress {
  int n;
  OrderedAddress* alternate = nullptr;
  OrderedAddress const* alternateConst = nullptr;
  OrderedAddress* operator&() { return alternate; }
  OrderedAddress const* operator&() const { return alternateConst; }
};

template <typename M> void orderedConstruction(char const* name) {
  OrderedTrace trace; OrderedTracing tracing(trace);
  {
    using Pair = typename M::value_type;
    std::initializer_list<Pair> entries{{3, OrderedValue(11)}, {1, OrderedValue(22)}, {3, OrderedValue(33)}};
    trace.events.clear();
    M list(entries);
    EXPECT_EQ(list.keys(), List<int>({3, 1})); EXPECT_EQ(list.get(3).n, 11);
    // The initializer-list loop copies even a duplicate into its by-value local.
    EXPECT_EQ(trace.events, "C11,C11,D11,C22,C22,D22,C33,D33,");
    EXPECT_EQ(trace.live, 5); trace.emit(name); trace.events.clear();
    M range(entries.begin(), entries.end());
    EXPECT_EQ(trace.events, "C11,C22,"); EXPECT_EQ(range.keys(), list.keys());
    trace.emit("range-construction"); trace.events.clear();
    M copied(list); EXPECT_EQ(trace.events, "C11,C22,");
    EXPECT_NE(std::addressof(copied.get(3)), std::addressof(list.get(3)));
    copied.get(3).n = 44; EXPECT_EQ(list.get(3).n, 11);
    trace.emit("copy-construction");
    auto from = M::from(entries); EXPECT_EQ(from.keys(), list.keys()); EXPECT_EQ(from.get(3).n, 11);
  }
  EXPECT_EQ(trace.live, 0);
}
template <typename M> void orderedAssignment(char const* name) {
  OrderedTrace trace; OrderedTracing tracing(trace);
  {
    M source; source.insert(3, OrderedValue(11)); source.insert(1, OrderedValue(22)); source.insert(2, OrderedValue(33));
    M target; target.insert(9, OrderedValue(99));
    auto* original = std::addressof(source.get(3)); trace.events.clear();
    auto& selfResult = (source = source);
    EXPECT_EQ(std::addressof(selfResult), std::addressof(source));
    EXPECT_EQ(std::addressof(source.get(3)), original); EXPECT_TRUE(trace.events.empty());
    trace.copyFailure = 22;
    orderedFailure(trace, [&] { target = source; });
    EXPECT_EQ(trace.events, "D99,C11,C22,caught,");
    EXPECT_EQ(target.keys(), List<int>({3})); EXPECT_EQ(target.get(3).n, 11);
    EXPECT_EQ(source.keys(), List<int>({3, 1, 2})); EXPECT_EQ(trace.live, 4);
    trace.emit(name); trace.copyFailure = -999; trace.events.clear();
    EXPECT_EQ(std::addressof(target = source), std::addressof(target));
    EXPECT_EQ(target.keys(), source.keys()); EXPECT_EQ(trace.events, "D11,C11,C22,C33,");
    EXPECT_NE(std::addressof(target.get(3)), original); trace.emit("assignment-success");
  }
  EXPECT_EQ(trace.live, 0);
}
template <typename M> void orderedLists(char const* name) {
  M map{{3, 7}, {1, 9}, {2, 7}};
  auto keys = map.keys(), values = map.values();
  EXPECT_EQ(keys, List<int>({3, 1, 2})); EXPECT_EQ(values, List<int>({7, 9, 7}));
  keys[0] = 99; values[0] = 99; EXPECT_EQ(map.firstKey(), 3); EXPECT_EQ(map.firstValue(), 7);
  List<int> reverse;
  auto const& c = map;
  for (auto i = c.rbegin(); i != c.rend(); ++i) reverse.append(i->first);
  EXPECT_EQ(reverse, List<int>({2, 1, 3}));
  std::cout << "ORDERED_MAP_TRACE " << name << ' ' << map << '\n';
}

// Every rebind retains the same state. The first node allocation is std::list's
// order node, the second std::map's index node: fail only AFTER the order insert.
struct OrderedAllocationState {
  OrderedTrace trace;
  int attempt = 0, failAt = 0;
};
OrderedAllocationState* orderedAllocationState = nullptr;
struct OrderedAllocationScope {
  OrderedAllocationState* previous;
  explicit OrderedAllocationScope(OrderedAllocationState& state) : previous(orderedAllocationState) { orderedAllocationState = &state; }
  ~OrderedAllocationScope() { orderedAllocationState = previous; }
};
struct OrderedComparisonState {
  OrderedTrace trace;
  int calls = 0;
  bool fail = false;
};
OrderedComparisonState* orderedComparisonState = nullptr;
struct OrderedComparisonScope {
  OrderedComparisonState* previous;
  explicit OrderedComparisonScope(OrderedComparisonState& state) : previous(orderedComparisonState) { orderedComparisonState = &state; }
  ~OrderedComparisonScope() { orderedComparisonState = previous; }
};
struct OrderedComparator {
  OrderedComparisonState* state = orderedComparisonState;
  bool operator()(int a, int b) const {
    ++state->calls;
    state->trace.log("L" + std::to_string(a) + ":" + std::to_string(b));
    if (state->fail) state->trace.raise();
    return a < b;
  }
};
template <typename T> struct OrderedAllocator {
  using value_type = T;
  using is_always_equal = std::false_type;
  OrderedAllocationState* state;
  OrderedAllocator() : state(orderedAllocationState) {}
  template <typename U> OrderedAllocator(OrderedAllocator<U> const& other) : state(other.state) {}
  T* allocate(size_t n) {
    if (state && state->failAt) {
      ++state->attempt; state->trace.log("allocate" + std::to_string(state->attempt));
      if (state->attempt == state->failAt) state->trace.raise();
    }
    return std::allocator<T>{}.allocate(n);
  }
  void deallocate(T* p, size_t n) { std::allocator<T>{}.deallocate(p, n); }
  template <typename U> bool operator==(OrderedAllocator<U> const& other) const { return state == other.state; }
  template <typename U> bool operator!=(OrderedAllocator<U> const& other) const { return !(*this == other); }
};
}

TEST(OrderedMapPolicy, ConstructorOrderDuplicatesAndByValueListLifetimes) {
  orderedConstruction<OrderedMap<int, OrderedValue>>("tree-list-construction");
  orderedConstruction<OrderedHashMap<int, OrderedValue>>("hash-list-construction");
}

TEST(OrderedMapPolicy, AssignmentSelfGuardClearBeforeCopiesAndThrowingPrefix) {
  orderedAssignment<OrderedMap<int, OrderedValue>>("tree-assignment-prefix");
  orderedAssignment<OrderedHashMap<int, OrderedValue>>("hash-assignment-prefix");
}

TEST(OrderedMapPolicy, CollectionsAreOrderedIndependentCopies) {
  orderedLists<OrderedMap<int, int>>("tree-lists");
  orderedLists<OrderedHashMap<int, int>>("hash-lists");
  OrderedMap<int, int> empty; EXPECT_TRUE(empty.keys().empty()); EXPECT_TRUE(empty.values().empty());
}

TEST(OrderedMapPolicy, CollectionCopyExceptionsDestroyPrefixNotSource) {
  OrderedTrace trace; OrderedTracing tracing(trace);
  {
    OrderedMap<int, OrderedValue> map;
    map.insert(3, OrderedValue(11)); map.insert(1, OrderedValue(22));
    trace.events.clear(); trace.copyFailure = 22;
    orderedFailure(trace, [&] { map.values(); });
    EXPECT_EQ(map.keys(), List<int>({3, 1})); EXPECT_EQ(trace.live, 2);
    EXPECT_NE(trace.events.find("C11,"), std::string::npos);
    EXPECT_NE(trace.events.find("C22,"), std::string::npos);
    EXPECT_NE(trace.events.find("D11,"), std::string::npos); trace.emit("values-copy-prefix");
    trace.copyFailure = -999;
  }
  EXPECT_EQ(trace.live, 0);
  {
    OrderedMap<OrderedValue, int> map;
    map.insert(OrderedValue(11), 1); map.insert(OrderedValue(22), 2);
    trace.events.clear(); trace.copyFailure = 22;
    orderedFailure(trace, [&] { map.keys(); });
    EXPECT_EQ(map.size(), 2u); EXPECT_EQ(trace.live, 2);
    EXPECT_NE(trace.events.find("D11,"), std::string::npos); trace.emit("keys-copy-prefix");
    trace.copyFailure = -999;
  }
  EXPECT_EQ(trace.live, 0);
}

TEST(OrderedMapPolicy, LookupReferencesDefaultsOverloadedAddressAndExactErrors) {
  OrderedMap<int, int> map{{3, 7}, {1, 9}}; auto const& c = map;
  EXPECT_TRUE(map.contains(3)); EXPECT_FALSE(c.contains(8));
  EXPECT_EQ(map.find(3), map.begin()); EXPECT_EQ(c.find(3), c.begin());
  EXPECT_EQ(map.find(8), map.end()); EXPECT_EQ(c.find(8), c.end());
  EXPECT_EQ(std::addressof(map.get(3)), std::addressof(map.begin()->second));
  EXPECT_EQ(std::addressof(c.get(3)), std::addressof(map.get(3)));
  EXPECT_EQ(map.ptr(3), std::addressof(map.get(3))); EXPECT_EQ(c.ptr(3), map.ptr(3));
  EXPECT_EQ(map.ptr(8), nullptr); EXPECT_EQ(c.ptr(8), nullptr);
  EXPECT_EQ(c.value(3, 99), 7); EXPECT_EQ(c.value(8, 99), 99); EXPECT_EQ(c.value(8), 0);
  EXPECT_EQ(*c.maybe(3), 7); EXPECT_FALSE(c.maybe(8)); EXPECT_FALSE(map.maybeTake(8));
  orderedMessage([&] { map.get(8); }, "Key '8' not found in OrderedMap::get()");
  orderedMessage([&] { c.get(8); }, "Key '8' not found in OrderedMap::get()");
  orderedMessage([&] { c.keyOf(8); }, "Value '8' not found in OrderedMap::keyOf()");
  orderedMessage([&] { map.toFront(8); }, "Key not found in OrderedMap::toFront('8')");
  orderedMessage([&] { map.toBack(8); }, "Key not found in OrderedMap::toBack('8')");
  OrderedMap<int, int> empty;
  orderedMessage([&] { empty.first(); }, "OrderedMap::takeFirst() called on empty OrderedMap");
  OrderedMap<int, OrderedAddress> addresses; addresses.insert(1, OrderedAddress{7}); OrderedAddress other{9};
  addresses.get(1).alternate = std::addressof(other); addresses.get(1).alternateConst = std::addressof(other);
  EXPECT_EQ(addresses.ptr(1), std::addressof(other));
  EXPECT_EQ(static_cast<decltype(addresses) const&>(addresses).ptr(1), std::addressof(other));
  std::cout << "ORDERED_MAP_TRACE lookup references,defaults,missing,overloaded-address,\n";
}

TEST(OrderedMapPolicy, ValueSlotsAndKeyOfShortCircuitPreserveNativeCopies) {
  OrderedTrace trace; OrderedTracing tracing(trace);
  {
    OrderedMap<int, OrderedValue> map;
    map.insert(3, OrderedValue(7)); map.insert(1, OrderedValue(8)); map.insert(2, OrderedValue(7));
    OrderedValue query(7); trace.events.clear(); trace.compareFailure = 8;
    EXPECT_EQ(map.keyOf(query), 3); EXPECT_EQ(trace.events, "E7,"); trace.emit("key-of-short-circuit");
    query.n = 9; trace.events.clear();
    orderedFailure(trace, [&] { map.keyOf(query); });
    EXPECT_EQ(trace.events, "E7,E8,caught,"); trace.emit("key-of-throw-prefix"); trace.compareFailure = -999;
    trace.events.clear();
    { auto value = map.value(3, OrderedValue(23)); EXPECT_EQ(value.n, 7); EXPECT_EQ(trace.live, 5); }
    trace.emit("value-found"); trace.events.clear();
    { auto value = map.value(8, OrderedValue(23)); EXPECT_EQ(value.n, 23); EXPECT_EQ(trace.live, 5); }
    trace.emit("value-default"); trace.events.clear();
    { auto value = map.maybe(3); ASSERT_TRUE(value); EXPECT_EQ(value->n, 7); EXPECT_EQ(trace.live, 5); }
    EXPECT_EQ(trace.events, "C7,D7,"); trace.emit("maybe-copy");
  }
  EXPECT_EQ(trace.live, 0);
}

TEST(OrderedMapPolicy, DuplicateInsertAndFrontDoNotCopyOrReorderStoredValues) {
  OrderedTrace trace; OrderedTracing tracing(trace);
  {
    OrderedMap<int, OrderedValue> map;
    map.insert(3, OrderedValue(11)); map.insert(1, OrderedValue(22));
    decltype(map)::value_type duplicate(3, OrderedValue(99));
    auto original = map.begin(); trace.events.clear();
    auto back = map.insert(duplicate); auto front = map.insertFront(duplicate);
    EXPECT_FALSE(back.second); EXPECT_FALSE(front.second);
    EXPECT_EQ(back.first, original); EXPECT_EQ(front.first, original);
    EXPECT_TRUE(trace.events.empty()); EXPECT_EQ(map.keys(), List<int>({3, 1}));
    decltype(map)::value_type fresh(2, OrderedValue(33)); trace.events.clear();
    EXPECT_TRUE(map.insertFront(fresh).second); EXPECT_EQ(trace.events, "C33,");
    EXPECT_EQ(map.keys(), List<int>({2, 3, 1})); trace.emit("front-and-duplicate");
  }
  EXPECT_EQ(trace.live, 0);
}

TEST(OrderedMapPolicy, PositionalInsertAssignsBeforeSpliceAndRetainsThrowMutation) {
  OrderedTrace trace; OrderedTracing tracing(trace);
  {
    OrderedMap<int, OrderedValue> map;
    map.insert(1, OrderedValue(11)); map.insert(2, OrderedValue(22)); map.insert(3, OrderedValue(33));
    auto* identity = std::addressof(map.get(3)); trace.events.clear(); trace.assignFailure = true;
    orderedFailure(trace, [&] { map.insert(map.begin(), {3, OrderedValue(44)}); });
    EXPECT_EQ(map.keys(), List<int>({1, 2, 3})); EXPECT_EQ(map.get(3).n, 44);
    EXPECT_EQ(std::addressof(map.get(3)), identity); EXPECT_EQ(trace.live, 3);
    EXPECT_NE(trace.events.find("A44,"), std::string::npos); trace.emit("positional-assignment-prefix");
    trace.assignFailure = false; trace.events.clear();
    auto moved = map.insert(map.begin(), {3, OrderedValue(55)});
    EXPECT_EQ(std::addressof(moved->second), identity); EXPECT_EQ(map.keys(), List<int>({3, 1, 2}));
    auto pos = map.find(2); map.insert(pos, {4, OrderedValue(66)});
    EXPECT_EQ(map.keys(), List<int>({3, 1, 4, 2})); trace.emit("positional-insert");
  }
  EXPECT_EQ(trace.live, 0);
}

TEST(OrderedMapPolicy, SubscriptOnlyDefaultConstructsMissingAndAddUsesMovedKey) {
  OrderedTrace trace; OrderedTracing tracing(trace);
  {
    OrderedMap<int, OrderedValue> map; map.insert(1, OrderedValue(11)); trace.events.clear();
    EXPECT_EQ(map[1].n, 11); EXPECT_TRUE(trace.events.empty());
    auto& added = map[2]; EXPECT_EQ(added.n, 0); EXPECT_EQ(std::addressof(added), std::addressof(map.get(2)));
    EXPECT_EQ(trace.events, "N0,M0,M0,D0,D0,"); trace.emit("subscript-default");
    trace.events.clear(); trace.assignFailure = true;
    orderedFailure(trace, [&] { map.set(1, OrderedValue(33)); });
    EXPECT_EQ(map.get(1).n, 33); EXPECT_EQ(map.keys(), List<int>({1, 2})); trace.emit("set-assignment-prefix");
    trace.assignFailure = false;
    EXPECT_EQ(std::addressof(map.set(1, OrderedValue(44))), std::addressof(map.get(1)));
    EXPECT_EQ(map.set(3, OrderedValue(55)).n, 55);
  }
  EXPECT_EQ(trace.live, 0);
  OrderedMap<OrderedMovedKey, int> map;
  auto& stored = map.add(OrderedMovedKey(7), 11);
  EXPECT_EQ(std::addressof(stored), std::addressof(map.begin()->second));
  orderedMessage([&] { map.add(OrderedMovedKey(7), 22); }, "Entry with key '-1' already present.");
  EXPECT_EQ(stored, 11); EXPECT_EQ(map.size(), 1u);
}

TEST(OrderedMapPolicy, RemovalErasesIndexBeforeMappedDestructor) {
  OrderedTrace trace; OrderedTracing tracing(trace);
  {
    OrderedMap<int, OrderedValue> map;
    map.insert(1, OrderedValue(17)); map.insert(2, OrderedValue(22));
    trace.events.clear();
    trace.destroyed = [&](int n) {
      if (n == 17) { EXPECT_EQ(map.size(), 1u); EXPECT_FALSE(map.contains(1)); trace.log("index-gone"); }
    };
    EXPECT_TRUE(map.remove(1)); EXPECT_FALSE(map.remove(1));
    EXPECT_EQ(trace.events, "D17,index-gone,"); trace.emit("remove-index-first");
    trace.destroyed = {};
    map.insert(3, OrderedValue(33)); auto next = map.erase(map.begin());
    EXPECT_EQ(next, map.begin()); EXPECT_EQ(next->first, 3);
    EXPECT_EQ(map.erase(3), 1u); EXPECT_EQ(map.erase(3), 0u); EXPECT_TRUE(map.empty());
  }
  EXPECT_EQ(trace.live, 0);
}

TEST(OrderedMapPolicy, MaybeTakeCopiesBeforeEraseAndConversionCanThrowAfterErase) {
  for (int failure = 0; failure != 3; ++failure) {
    OrderedTrace trace; OrderedTracing tracing(trace);
    {
      OrderedMap<int, OrderedValue> map; map.insert(1, OrderedValue(17)); trace.events.clear();
      if (failure == 1) trace.copyFailure = 17;
      if (failure == 2) trace.moveFailure = 17;
      if (failure) orderedFailure(trace, [&] { map.maybeTake(1); });
      else { auto value = map.maybeTake(1); ASSERT_TRUE(value); EXPECT_EQ(value->first, 1); EXPECT_EQ(value->second.n, 17); }
      EXPECT_EQ(map.contains(1), failure == 1); EXPECT_EQ(trace.live, failure == 1 ? 1 : 0);
      EXPECT_EQ(trace.events.substr(0, 4), "C17,");
      if (failure != 1) EXPECT_EQ(trace.events.substr(0, 8), "C17,D17,");
      trace.emit(failure == 0 ? "maybe-take" : failure == 1 ? "maybe-take-copy-fail" : "maybe-take-convert-fail");
    }
    EXPECT_EQ(trace.live, 0);
  }
}

TEST(OrderedMapPolicy, IndexAtFirstSpliceAndSortKeepUnaffectedNodeIdentity) {
  OrderedMap<int, int> map{{3, 30}, {1, 10}, {2, 20}, {4, 40}}; auto const& c = map;
  auto neighbor = map.find(1); auto* identity = std::addressof(neighbor->second);
  EXPECT_EQ(*c.indexOf(3), 0u); EXPECT_EQ(*c.indexOf(2), 2u); EXPECT_FALSE(c.indexOf(9));
  EXPECT_EQ(c.keyAt(2), 2); EXPECT_EQ(c.valueAt(2), 20);
  EXPECT_EQ(std::addressof(map.valueAt(1)), identity); EXPECT_EQ(std::addressof(c.valueAt(1)), identity);
  EXPECT_EQ(std::addressof(c.first()), std::addressof(*c.begin()));
  EXPECT_EQ(c.firstKey(), 3); EXPECT_EQ(c.firstValue(), 30); map.firstValue() = 31;
  orderedMessage([&] { c.keyAt(4); }, "index 4 out of range in OrderedMap::at()");
  orderedMessage([&] { c.valueAt(4); }, "index 4 out of range in OrderedMap::valueAt()");
  auto moved = map.toFront(map.find(2)); EXPECT_EQ(moved, map.begin());
  EXPECT_EQ(map.toBack(moved)->first, 2); map.toFront(4); map.toBack(3);
  EXPECT_EQ(map.keys(), List<int>({4, 1, 2, 3}));
  EXPECT_EQ(std::addressof(map.find(1)->second), identity); EXPECT_EQ(neighbor->first, 1);
  map.sortByKey(); EXPECT_EQ(map.keys(), List<int>({1, 2, 3, 4}));
  map.sortByValue(); EXPECT_EQ(map.keys(), List<int>({1, 2, 3, 4}));
  map.sort([](auto const& a, auto const& b) { return a.first > b.first; });
  EXPECT_EQ(map.keys(), List<int>({4, 3, 2, 1})); EXPECT_EQ(std::addressof(map.find(1)->second), identity);
  map.removeFirst(); EXPECT_EQ(map.keys(), List<int>({3, 2, 1}));
  std::cout << "ORDERED_MAP_TRACE splice-sort " << map << '\n';
}

TEST(OrderedMapPolicy, FailedIndexAllocationRetainsOrderNodeWithoutRollback) {
  {
    OrderedComparisonState comparison; OrderedComparisonScope scope(comparison);
    OrderedMap<int, int, OrderedComparator> map;
    map.insert(1, 11); comparison.trace.events.clear(); comparison.calls = 0; comparison.fail = true;
    orderedFailure(comparison.trace, [&] { map.insert(2, 22); });
    // Throw in the pre-find, before there can be an order node allocation.
    // Comparator operand direction belongs to the STL lookup implementation;
    // compare the complete emitted OFF/ON trace rather than guessing that order.
    EXPECT_EQ(comparison.calls, 1);
    EXPECT_EQ(comparison.trace.events.find("L"), 0u);
    EXPECT_EQ(comparison.trace.events.substr(comparison.trace.events.size() - 7), "caught,");
    EXPECT_EQ(map.size(), 1u); EXPECT_EQ(std::distance(map.begin(), map.end()), 1);
    comparison.trace.emit("pre-find-comparator-failure"); comparison.fail = false;
  }
  OrderedAllocationState state; OrderedAllocationScope scope(state);
  {
    using Alloc = OrderedAllocator<std::pair<int const, int>>;
    OrderedMap<int, int, std::less<int>, Alloc> map;
    map.insert(1, 11); state.failAt = 2;
    orderedFailure(state.trace, [&] { map.insert(2, 22); });
    EXPECT_EQ(state.trace.events, "allocate1,allocate2,caught,");
    // size() is INDEX size, while traversal exposes the retained orphan. Do not
    // perform further indexed lookups/mutations on this partially indexed map.
    EXPECT_EQ(map.size(), 1u);
    auto i = map.begin(); ASSERT_NE(i, map.end()); EXPECT_EQ(i->first, 1);
    ++i; ASSERT_NE(i, map.end()); EXPECT_EQ(i->first, 2); EXPECT_EQ(i->second, 22);
    ++i; EXPECT_EQ(i, map.end()); state.trace.emit("index-allocation-orphan");
    state.failAt = 0;
  }
}

#ifdef STAR_USE_RUST_MAP
TEST(OrderedMapPolicy, RustCountersUseOnlyNewAssignmentInsertRemoveModes) {
  auto assign = sb_map_count(9);
  auto insert = sb_map_select_count(5), remove = sb_map_select_count(6);
  OrderedMap<int, int> source{{1, 11}}, target;
  target = source; target.insertFront(2, 22); EXPECT_TRUE(target.remove(1));
  EXPECT_GT(sb_map_count(9), assign);
  EXPECT_GT(sb_map_select_count(5), insert); EXPECT_GT(sb_map_select_count(6), remove);
  // COLLECT stays mode zero; old modes do not all apply to OrderedMap.
  auto collect = sb_map_count(0); target.keys(); EXPECT_GT(sb_map_count(0), collect);
  EXPECT_EQ(sb_map_count(10), 0u); EXPECT_EQ(sb_map_select_count(7), 0u);
}
#endif

// These are native-invalid instantiations, not runtime tests or repair requests.
// Keep all three boundaries rejected in BOTH selector configurations.
#ifdef STAR_ORDERED_MAP_PAIRS_NEGATIVE
void orderedPairsMustNotCompile() {
  OrderedMap<int, int> tree; tree.pairs();
  OrderedHashMap<int, int> hash; hash.pairs();
}
#endif
#ifdef STAR_ORDERED_MAP_KEYS_NEGATIVE
void orderedKeysMustNotCompile() {
  OrderedMap<int, int> const tree; tree.keysOf(1);
  OrderedHashMap<int, int> const hash; hash.keysOf(1);
}
#endif
#ifdef STAR_ORDERED_MAP_FIRST_TAKE_NEGATIVE
void orderedFirstTakeMustNotCompile() {
  OrderedMap<int, int> tree; tree.takeFirst();
  OrderedHashMap<int, int> hash; hash.takeFirst();
}
#endif
