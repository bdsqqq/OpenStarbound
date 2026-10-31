#include "StarMap.hpp"
#include "gtest/gtest.h"

#include <exception>
#include <iostream>
#include <memory>
#include <new>
#include <sstream>
#include <string>

#ifdef STAR_USE_RUST_MAP
#include "StarRustMap.h"
#endif

using namespace Star;

namespace {
struct MapMarker {};
struct MapTrace {
  std::string events;
  std::exception_ptr error;
  int copyFailure = -1, moveFailure = -1, compareFailure = -1;
  bool assignFailure = false, badAllocation = false;
  int live = 0;
  void log(std::string const& s) { events += s + ","; }
  [[noreturn]] void raise() {
    try { if (badAllocation) throw std::bad_alloc(); throw MapMarker{}; }
    catch (...) { error = std::current_exception(); throw; }
  }
  void emit(char const* name) const { std::cout << "FLAT_MAP_TRACE " << name << ' ' << events << '\n'; }
};
template <typename F> void mapFailure(MapTrace& t, F f) {
  try { f(); FAIL() << "expected marker"; }
  catch (MapMarker const&) { EXPECT_EQ(std::current_exception(), t.error); t.log("caught"); }
  catch (std::bad_alloc const&) { EXPECT_TRUE(t.badAllocation); EXPECT_EQ(std::current_exception(), t.error); t.log("caught-bad-alloc"); }
}
template <typename F> void mapMessage(F f, char const* text) {
  try { f(); FAIL() << "expected MapException"; }
  catch (MapException const& e) { EXPECT_STREQ(e.what(), MapException(text, false).what()); }
}
struct MapBool { bool b; explicit operator bool() const { return b; } };
struct MapValue {
  int n;
  static MapTrace* trace;
  explicit MapValue(int n = 0) : n(n) { if (trace) { ++trace->live; trace->log("N" + std::to_string(n)); } }
  MapValue(MapValue const& v) : n(v.n) {
    if (trace) {
      trace->log("C" + std::to_string(n));
      if (trace->copyFailure == n) trace->raise();
      ++trace->live;
    }
  }
  MapValue(MapValue&& v) : n(v.n) {
    if (trace) {
      trace->log("M" + std::to_string(n));
      if (trace->moveFailure == n) trace->raise();
      ++trace->live;
    }
    v.n = -n;
  }
  MapValue& operator=(MapValue&& v) {
    n = v.n;
    if (trace) { trace->log("A" + std::to_string(n)); if (trace->assignFailure) trace->raise(); }
    v.n = -n; return *this;
  }
  MapValue& operator=(MapValue const&) = default;
  ~MapValue() { if (trace) { --trace->live; trace->log("D" + std::to_string(n)); } }
  friend bool operator<(MapValue const& a, MapValue const& b) { return a.n < b.n; }
  friend MapBool operator==(MapValue const& a, MapValue const& b) {
    if (trace) { trace->log("E" + std::to_string(a.n)); if (trace->compareFailure == a.n) trace->raise(); }
    return {a.n == b.n};
  }
  friend std::ostream& operator<<(std::ostream& os, MapValue const& v) { return os << v.n; }
};
MapTrace* MapValue::trace = nullptr;
struct MapTracing {
  explicit MapTracing(MapTrace& t) { MapValue::trace = &t; }
  ~MapTracing() { MapValue::trace = nullptr; }
};
struct MapCollision { size_t operator()(int) const { return 0; } };

template <typename M> void mapLists(char const* name) {
  M m{{3, 7}, {1, 9}, {2, 7}};
  auto keys = m.keys(), values = m.values(); auto pairs = m.pairs();
  ASSERT_EQ(keys.size(), m.size()); ASSERT_EQ(values.size(), m.size()); ASSERT_EQ(pairs.size(), m.size());
  size_t n = 0;
  for (auto const& p : m) {
    EXPECT_EQ(keys[n], p.first); EXPECT_EQ(values[n], p.second);
    EXPECT_EQ(pairs[n], std::make_pair(p.first, p.second)); ++n;
  }
  EXPECT_EQ(m.keyOf(7), m.keysOf(7)[0]); EXPECT_TRUE(m.hasValue(9)); EXPECT_FALSE(m.hasValue(8));
  EXPECT_EQ(m.keysOf(7).size(), 2u);
  std::cout << "FLAT_MAP_TRACE " << name << ' ' << m << '\n';
  values[0] = 100; EXPECT_NE(m.get(keys[0]), 100);
}

// Only const traversal is wrapped; storage, lookup and erasure remain std::map.
// The postfix temporary makes erase(i++)'s full-expression boundary observable.
struct PrintState { std::string events; int active = 0; };
struct PrintValue { int n; PrintState* state; };
struct PrintProxy {
  std::ostream& os; PrintState* state;
  PrintProxy(std::ostream& os, PrintState* state) : os(os), state(state) { ++state->active; state->events += "proxy,"; }
  ~PrintProxy() { --state->active; state->events += "destroy,"; }
  PrintProxy& operator<<(char const* s) { state->events += "quote,"; os << s; return *this; }
};
PrintProxy operator<<(std::ostream& os, PrintValue const& v) { os << v.n; return {os, v.state}; }
template <typename V> struct ObservedMap : std::map<int, V> {
  using Parent = std::map<int, V>;
  using Parent::Parent;
  PrintState* state = nullptr;
  struct const_iterator {
    typename Parent::const_iterator inner;
    PrintState* state;
    bool postfix = false;
    const_iterator(typename Parent::const_iterator i, PrintState* s) : inner(i), state(s) {}
    ~const_iterator() { if (postfix) state->events += "post-destroy,"; }
    auto const& operator*() const { return *inner; }
    auto operator->() const { return std::addressof(*inner); }
    bool operator!=(const_iterator const& b) const {
      EXPECT_EQ(state->active, 0); state->events += "more,"; return inner != b.inner;
    }
    bool operator==(const_iterator const& b) const { state->events += "first,"; return inner == b.inner; }
    const_iterator& operator++() {
      EXPECT_EQ(state->active, 0); state->events += "advance,"; ++inner; return *this;
    }
    const_iterator operator++(int) { auto old = *this; ++*this; old.postfix = true; return old; }
  };
  const_iterator begin() const { state->events += "begin,"; return {Parent::begin(), state}; }
  const_iterator end() const { return {Parent::end(), state}; }
  using Parent::erase;
  void erase(const_iterator i) { state->events += "erase,"; Parent::erase(i.inner); }
};
// Iterator end temporaries must die before crossing the selection ABI, not
// merely before the selected typed return. The TLS count exposes that boundary.
struct EndScopeState {
  std::string events;
  uint64_t before = 0;
};
struct EndScopeMap : std::map<int, int> {
  EndScopeState* state = nullptr;
  struct const_iterator {
    std::map<int, int>::const_iterator inner;
    EndScopeState* state;
    bool endTemporary;
    ~const_iterator() {
      if (endTemporary) {
        state->events += "end,";
#ifdef STAR_USE_RUST_MAP
        EXPECT_EQ(sb_map_select_count(SB_MAP_SELECT_REQUIRED), state->before);
#endif
      }
    }
    auto operator->() const { return std::addressof(*inner); }
    bool operator==(const_iterator const& b) const { return inner == b.inner; }
  };
  const_iterator find(int k) const { return {std::map<int, int>::find(k), state, false}; }
  const_iterator end() const { return {std::map<int, int>::end(), state, true}; }
};
struct MapThrowBuffer : std::streambuf {
  MapTrace& t; std::string text;
  explicit MapThrowBuffer(MapTrace& t) : t(t) {}
  void put(char c) { if (c == ',') t.raise(); text += c; }
  std::streamsize xsputn(char const* p, std::streamsize n) override {
    for (std::streamsize i = 0; i < n; ++i) put(p[i]); return n;
  }
  int_type overflow(int_type c) override {
    if (!traits_type::eq_int_type(c, traits_type::eof())) put(traits_type::to_char_type(c));
    return traits_type::not_eof(c);
  }
};
struct AddressValue {
  int n;
  AddressValue* alternate = nullptr;
  AddressValue const* alternateConst = nullptr;
  AddressValue* operator&() { return alternate; }
  AddressValue const* operator&() const { return alternateConst; }
};
struct MovedKey {
  int n;
  MapTrace* formatting = nullptr;
  explicit MovedKey(int n) : n(n) {}
  MovedKey(MovedKey const&) = default;
  MovedKey(MovedKey&& k) : n(k.n), formatting(k.formatting) { k.n = -1; }
  friend bool operator<(MovedKey const& a, MovedKey const& b) { return a.n < b.n; }
  friend std::ostream& operator<<(std::ostream& os, MovedKey const& k) {
    if (k.formatting) { EXPECT_EQ(k.formatting->live, 0); k.formatting->log("format-key"); }
    return os << k.n;
  }
};
}

TEST(MapTest, ListsFollowEachNativeOrder) {
  mapLists<Map<int, int>>("sorted"); mapLists<HashMap<int, int>>("flat");
  mapLists<StableHashMap<int, int>>("stable");
  Map<int, int> empty; EXPECT_TRUE(empty.keys().empty()); EXPECT_TRUE(empty.values().empty()); EXPECT_TRUE(empty.pairs().empty());
  Map<int, int> sorted{{3, 7}, {1, 9}, {2, 7}};
  EXPECT_EQ(sorted.keys(), List<int>({1, 2, 3})); EXPECT_EQ(sorted.values(), List<int>({9, 7, 7}));
}

TEST(MapTest, CollectionCopyFailureKeepsSourceAndDestroysPrefix) {
  for (int mode = 0; mode != 2; ++mode) {
    MapTrace t; MapTracing tracing(t);
    {
      Map<int, MapValue> m; m.emplace(1, MapValue(11)); m.emplace(2, MapValue(22));
      t.events.clear(); t.copyFailure = 22;
      mapFailure(t, [&] { if (mode) m.pairs(); else m.values(); });
      EXPECT_EQ(m.size(), 2u); EXPECT_EQ(m.get(1).n, 11); EXPECT_EQ(m.get(2).n, 22);
      EXPECT_EQ(t.live, 2); EXPECT_NE(t.events.find("C11,"), std::string::npos);
      EXPECT_NE(t.events.find("D11,"), std::string::npos); t.emit(mode ? "pairs-copy" : "values-copy");
    }
    EXPECT_EQ(t.live, 0);
  }
  MapTrace t; MapTracing tracing(t);
  {
    Map<MapValue, int> m; m.emplace(MapValue(11), 1); m.emplace(MapValue(22), 2);
    t.events.clear(); t.copyFailure = 22; t.badAllocation = true;
    mapFailure(t, [&] { m.keys(); });
    EXPECT_EQ(m.size(), 2u); EXPECT_EQ(t.live, 2);
    EXPECT_NE(t.events.find("C11,"), std::string::npos);
    EXPECT_NE(t.events.find("D11,"), std::string::npos); t.emit("keys-copy-bad-alloc");
  }
  EXPECT_EQ(t.live, 0);
}

TEST(MapTest, ContextualBoolSearchStopsAtFirstMatch) {
  MapTrace t; MapTracing tracing(t);
  Map<int, MapValue> m; m.emplace(1, MapValue(7)); m.emplace(2, MapValue(8)); m.emplace(3, MapValue(7));
  MapValue query(7); t.events.clear(); t.compareFailure = 8;
  EXPECT_EQ(m.keyOf(query), 1); EXPECT_TRUE(m.hasValue(query));
  EXPECT_EQ(t.events, "E7,E7,");
  mapFailure(t, [&] { m.keysOf(query); }); t.emit("search-prefix");
  t.compareFailure = -1; EXPECT_EQ(m.keysOf(query), List<int>({1, 3}));
}

TEST(MapTest, RemovalPreservesPostfixAndFlatShiftQuirk) {
  Map<int, int> m{{1, 7}, {2, 7}, {3, 7}, {4, 9}};
  EXPECT_TRUE(m.removeValues(7)); EXPECT_EQ(m.keys(), List<int>({4})); EXPECT_FALSE(m.removeValues(7));
  HashMap<int, int, MapCollision> flat; flat.reserve(16);
  flat.insert(1, 7); flat.insert(2, 7); flat.insert(3, 7);
  // Erasure shifts key 2 into the old bucket, but i++ already points beyond it.
  EXPECT_TRUE(flat.removeValues(7)); EXPECT_EQ(flat.size(), 1u); EXPECT_TRUE(flat.contains(2));
  std::cout << "FLAT_MAP_TRACE remove-shift " << flat << '\n';
  PrintState state; MapMixin<ObservedMap<int>> observed; observed.state = &state;
  observed.emplace(1, 7); observed.emplace(2, 7);
  EXPECT_TRUE(observed.removeValues(7)); EXPECT_TRUE(observed.empty());
  EXPECT_NE(state.events.find("advance,erase,post-destroy,more,"), std::string::npos);
  std::cout << "FLAT_MAP_TRACE erase-postfix " << state.events << '\n';
  MapTrace t; MapTracing tracing(t);
  Map<int, MapValue> partial;
  partial.emplace(1, MapValue(7)); partial.emplace(2, MapValue(8)); partial.emplace(3, MapValue(7));
  MapValue query(7); t.events.clear(); t.compareFailure = 8;
  mapFailure(t, [&] { partial.removeValues(query); });
  EXPECT_FALSE(partial.contains(1)); EXPECT_TRUE(partial.contains(2)); EXPECT_TRUE(partial.contains(3));
  EXPECT_EQ(t.live, 3); t.emit("remove-match-failure-prefix");
}

TEST(MapTest, MaybeTakeCopiesConstThenErasesBeforeConversion) {
  for (int failure = 0; failure != 3; ++failure) {
    MapTrace t; MapTracing tracing(t);
    {
      Map<int, MapValue> m; m.emplace(1, MapValue(17)); t.events.clear();
      if (failure == 1) t.copyFailure = 17;
      if (failure == 2) t.moveFailure = 17;
      if (failure) mapFailure(t, [&] { m.maybeTake(1); });
      else { auto value = m.maybeTake(1); ASSERT_TRUE(value); EXPECT_EQ(value->n, 17); }
      EXPECT_EQ(m.contains(1), failure == 1);
      EXPECT_EQ(t.live, failure == 1 ? 1 : 0);
      EXPECT_EQ(t.events.substr(0, 4), "C17,");
      if (failure != 1) EXPECT_EQ(t.events.substr(0, 8), "C17,D17,");
      t.emit(failure == 0 ? "maybe-take" : failure == 1 ? "take-copy-fail" : "take-convert-fail");
    }
    EXPECT_EQ(t.live, 0);
  }
}

TEST(MapTest, AccessReferenceIdentityDefaultsAndExactMissingMessages) {
  Map<int, int> m{{1, 7}}; auto const& c = m;
  EXPECT_EQ(std::addressof(m.get(1)), std::addressof(m.begin()->second));
  EXPECT_EQ(std::addressof(c.get(1)), std::addressof(m.get(1)));
  EXPECT_EQ(m.ptr(1), std::addressof(m.get(1))); EXPECT_EQ(c.ptr(1), m.ptr(1));
  EXPECT_EQ(m.ptr(2), nullptr); EXPECT_EQ(c.ptr(2), nullptr);
  EXPECT_EQ(c.value(1, 9), 7); EXPECT_EQ(c.value(2, 9), 9); EXPECT_EQ(c.value(2), 0);
  EXPECT_EQ(*c.maybe(1), 7); EXPECT_FALSE(c.maybe(2)); EXPECT_FALSE(m.maybeTake(2));
  EXPECT_EQ(m.take(1), 7); EXPECT_TRUE(m.empty());
  mapMessage([&] { m.get(2); }, "Key '2' not found in Map::get()");
  mapMessage([&] { c.get(2); }, "Key '2' not found in Map::get()");
  mapMessage([&] { m.take(2); }, "Key '2' not found in Map::take()");
  mapMessage([&] { c.keyOf(7); }, "Value '7' not found in Map::keyOf()");
  Map<int, AddressValue> addresses; addresses.emplace(1, AddressValue{7}); AddressValue other{9};
  addresses.get(1).alternate = std::addressof(other); addresses.get(1).alternateConst = std::addressof(other);
  EXPECT_EQ(addresses.ptr(1), std::addressof(other));
  EXPECT_EQ(static_cast<decltype(addresses) const&>(addresses).ptr(1), std::addressof(other));
}

TEST(MapTest, LookupEndTemporaryDiesBeforeSelectionEntry) {
  EndScopeState state;
  MapMixin<EndScopeMap> m; m.state = &state; m.emplace(1, 7);
  auto const& c = m;
#ifdef STAR_USE_RUST_MAP
  state.before = sb_map_select_count(SB_MAP_SELECT_REQUIRED);
#endif
  EXPECT_EQ(c.get(1), 7);
#ifdef STAR_USE_RUST_MAP
  state.before = sb_map_select_count(SB_MAP_SELECT_REQUIRED);
#endif
  mapMessage([&] { c.get(2); }, "Key '2' not found in Map::get()");
  EXPECT_EQ(state.events, "end,end,");
  std::cout << "FLAT_MAP_TRACE selection-end-scope " << state.events << '\n';
}

TEST(MapTest, ValueAndTakeKeepNativeValueSlotsAndReturnLifetimes) {
  MapTrace t; MapTracing tracing(t);
  {
    Map<int, MapValue> m; m.emplace(1, MapValue(19)); t.events.clear();
    { auto v = m.value(1, MapValue(23)); EXPECT_EQ(v.n, 19); EXPECT_EQ(t.live, 2); }
    t.emit("value-found"); t.events.clear();
    { auto v = m.value(2, MapValue(23)); EXPECT_EQ(v.n, 23); EXPECT_EQ(t.live, 2); }
    t.emit("value-default"); t.events.clear();
    { auto v = m.maybe(1); ASSERT_TRUE(v); EXPECT_EQ(v->n, 19); EXPECT_EQ(t.live, 2); }
    t.emit("maybe-copy"); t.events.clear();
    { auto v = m.take(1); EXPECT_EQ(v.n, 19); EXPECT_EQ(t.live, 1); }
    EXPECT_EQ(t.live, 0); t.emit("take-prvalue");
    t.events.clear(); Map<MovedKey, MapValue> empty; MovedKey missing(99); missing.formatting = &t;
    // An empty Maybe has no mapped destructor to hook; formatting must still
    // observe no materialized/default mapped slot after the missing branch.
    mapMessage([&] { empty.take(missing); }, "Key '99' not found in Map::take()");
    EXPECT_EQ(t.live, 0); EXPECT_EQ(t.events, "format-key,"); t.emit("take-missing-format");
  }
  EXPECT_EQ(t.live, 0);
}

TEST(MapTest, AddDuplicateUsesAlreadyMovedKeyAndReturnsStoredReference) {
  Map<MovedKey, int> m;
  auto& v = m.add(MovedKey(7), 11); EXPECT_EQ(std::addressof(v), std::addressof(m.begin()->second));
  mapMessage([&] { m.add(MovedKey(7), 22); }, "Entry with key '-1' already present.");
  EXPECT_EQ(m.size(), 1u); EXPECT_EQ(v, 11);
  auto result = m.insert(MovedKey(7), 33); EXPECT_FALSE(result.second); EXPECT_EQ(result.first, m.begin());
}

TEST(MapTest, SetRetainsAssignmentPrefixAndInsertTemporaryLifetimes) {
  MapTrace t; MapTracing tracing(t);
  {
    Map<int, MapValue> m; m.emplace(1, MapValue(11));
    auto* original = std::addressof(m.get(1)); t.events.clear(); t.assignFailure = true;
    mapFailure(t, [&] { m.set(1, MapValue(22)); });
    EXPECT_EQ(std::addressof(m.get(1)), original); EXPECT_EQ(m.get(1).n, 22); EXPECT_EQ(m.size(), 1u);
    EXPECT_EQ(t.live, 1); t.emit("set-partial-assignment"); t.assignFailure = false;
    EXPECT_EQ(std::addressof(m.set(1, MapValue(33))), original);
    t.events.clear(); t.moveFailure = 44;
    mapFailure(t, [&] { m.set(2, MapValue(44)); });
    EXPECT_FALSE(m.contains(2)); EXPECT_EQ(t.live, 1); t.emit("set-insert-failure");
    t.moveFailure = -1; t.events.clear();
    auto& added = m.set(2, MapValue(44)); EXPECT_EQ(std::addressof(added), std::addressof(m.find(2)->second));
    EXPECT_EQ(added.n, 44); EXPECT_EQ(t.live, 2); t.emit("set-insert");
  }
  EXPECT_EQ(t.live, 0);
}

TEST(MapTest, PrintRechecksBeginAndDestroysWholeInsertionProxy) {
  PrintState state; ObservedMap<PrintValue> m; m.state = &state;
  m.emplace(1, PrintValue{7, &state}); m.emplace(2, PrintValue{8, &state});
  std::ostringstream out; printMap(out, m);
  EXPECT_EQ(out.str(), "{ \"1\" : \"7\", \"2\" : \"8\" }");
  EXPECT_EQ(state.events, "begin,more,begin,first,proxy,quote,destroy,advance,more,begin,first,proxy,quote,destroy,advance,more,");
  EXPECT_EQ(state.active, 0); std::cout << "FLAT_MAP_TRACE print-proxy " << state.events << '\n';
  Map<int, int> empty; std::ostringstream e; e << empty; EXPECT_EQ(e.str(), "{  }");
}

TEST(MapTest, PrintRealSeparatorWriteFailurePreservesExceptionIdentity) {
  Map<int, int> m{{1, 7}, {2, 8}}; MapTrace t; MapThrowBuffer buffer(t);
  std::ostream os(&buffer); os.exceptions(std::ios::badbit);
  mapFailure(t, [&] { os << m; }); EXPECT_TRUE(os.bad());
  EXPECT_EQ(buffer.text, "{ \"1\" : \"7\""); EXPECT_EQ(m.size(), 2u); t.emit("print-separator-failure");
}

#ifdef STAR_USE_RUST_MAP
TEST(MapTest, RustCountersObserveAllFiveLoopAndSelectionModes) {
  uint64_t loops[SB_MAP_COUNT], selects[SB_MAP_SELECT_COUNT];
  for (uint32_t i = 0; i < SB_MAP_COUNT; ++i) loops[i] = sb_map_count(i);
  for (uint32_t i = 0; i < SB_MAP_SELECT_COUNT; ++i) selects[i] = sb_map_select_count(i);
  Map<int, int> m{{1, 7}, {2, 8}};
  m.keys(); m.hasValue(7); m.keysOf(8); m.removeValues(8); std::ostringstream out; out << m;
  m.get(1); m.maybe(1); m.value(1); m.set(1, 9); m.add(3, 10);
  for (uint32_t i = 0; i < SB_MAP_COUNT; ++i) EXPECT_GT(sb_map_count(i), loops[i]);
  for (uint32_t i = 0; i < SB_MAP_SELECT_COUNT; ++i) EXPECT_GT(sb_map_select_count(i), selects[i]);
}
#endif
