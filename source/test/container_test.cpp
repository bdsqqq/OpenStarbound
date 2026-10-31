#include "StarSet.hpp"

#include "gtest/gtest.h"

#include <functional>
#include <iostream>
#include <iterator>
#include <sstream>
#include <string>
#include <type_traits>

using namespace Star;

TEST(SetTest, All) {
  Set<int> a = {1, 2, 3, 4};
  Set<int> b = {2, 4, 5};
  EXPECT_EQ(a.difference(b), Set<int>({1, 3}));
  EXPECT_EQ(a.intersection(b), Set<int>({2, 4}));
  EXPECT_EQ(a.combination(b), Set<int>({1, 2, 3, 4, 5}));
}

namespace {
struct SetMarker { void const* owner; };
struct SetTrace {
  std::string events;
  int convert = -1, advance = -1, copy = -1, active = 0;
  bool hash = false, compare = false, move = false;
  SetMarker const* thrown = nullptr;
  void log(std::string const& event) { events += event + ","; }
  [[noreturn]] void raise() {
    try { throw SetMarker{this}; }
    catch (SetMarker const& m) { thrown = &m; throw; }
  }
  void emit(char const* name) const { std::cout << "SET_TRACE " << name << ' ' << events << '\n'; }
};
template <typename F> void setSameException(SetTrace& t, F f) {
  try { f(); FAIL() << "expected nonstandard marker"; }
  catch (SetMarker const& m) { EXPECT_EQ(&m, t.thrown); EXPECT_EQ(m.owner, &t); t.log("caught"); }
}
struct SetBool { bool value; explicit operator bool() const { return value; } };
struct SetProxy {
  SetTrace* t; int n;
  SetProxy(SetTrace* t, int n) : t(t), n(n) { ++t->active; t->log("P" + std::to_string(n)); }
  SetProxy(SetProxy const& p) : SetProxy(p.t, p.n) {}
  ~SetProxy() { --t->active; t->log("D" + std::to_string(n)); }
  operator int() const {
    EXPECT_GT(t->active, 0); t->log("V" + std::to_string(n));
    if (t->convert == n) t->raise();
    return n;
  }
};
// Original unqualified hash intersection resolves this ADL predicate, NOT membership.
bool contains(SetProxy const& p) { int n = p; return n % 2 == 0; }
struct SetRangeIterator {
  SetTrace* t; int n;
  SetProxy operator*() const { return {t, n}; }
  SetBool operator!=(SetRangeIterator const& end) const { return {n != end.n}; }
  SetRangeIterator& operator++() {
    EXPECT_EQ(t->active, 0); t->log("I" + std::to_string(n));
    if (t->advance == n) t->raise();
    ++n; return *this;
  }
};
// Range-for must use ADL, not std::begin's poisoned member preference.
struct SetAdlRange {
  SetTrace* t;
  void begin() const = delete;
  friend SetRangeIterator begin(SetAdlRange const& r) { return {r.t, 1}; }
  friend SetRangeIterator end(SetAdlRange const& r) { return {r.t, 4}; }
};
// A preset failbit is not a portable later-insertion throw trigger. Fail a real
// separator write instead, so the exception traverses the active Rust host frame.
struct SetThrowBuffer : std::streambuf {
  SetTrace& trace;
  std::string text;
  explicit SetThrowBuffer(SetTrace& trace) : trace(trace) {}
  void put(char c) {
    if (c == ',') trace.raise();
    text.push_back(c);
  }
  std::streamsize xsputn(char const* data, std::streamsize size) override {
    for (std::streamsize i = 0; i < size; ++i) put(data[i]);
    return size;
  }
  int_type overflow(int_type c) override {
    if (!traits_type::eq_int_type(c, traits_type::eof())) put(traits_type::to_char_type(c));
    return traits_type::not_eof(c);
  }
};
template <typename F> void setEmptyMessage(F f, char const* message) {
  try { f(); FAIL() << "expected SetException"; }
  catch (SetException const& e) { EXPECT_STREQ(e.what(), SetException(message, false).what()); }
}
template <typename S> void setIntegerContracts(char const* name) {
  S a{4, 1, 3}, b{3, 2, 4}, empty;
  auto av = a.values(), bv = b.values();
  EXPECT_EQ(av.size(), 3u);
  EXPECT_TRUE(a.hasIntersection(b)); EXPECT_FALSE(a.hasIntersection(empty));
  EXPECT_FALSE(empty.hasIntersection(a));
  // HashSet<int>::intersection is originally ill-formed: its unqualified
  // contains(e) cannot find the dependent-base member or an ADL function for int.
  if constexpr (std::is_same<S, Set<int>>::value) {
    auto intersection = a.intersection(b);
    EXPECT_EQ(intersection.size(), 2u); EXPECT_TRUE(intersection.contains(3)); EXPECT_TRUE(intersection.contains(4));
    std::cout << "SET_TRACE sorted-intersection " << intersection << '\n';
  }
  auto difference = a.difference(b), combined = a.combination(b);
  EXPECT_EQ(difference.size(), 1u); EXPECT_TRUE(difference.contains(1));
  EXPECT_EQ(combined.size(), 4u); EXPECT_TRUE(combined.contains(2));
  // Emit actual native iteration/algebra order, never a guessed hash order.
  std::cout << "SET_TRACE " << name << ' ' << a << ' ' << b << ' ' << difference << ' ' << combined << '\n';
  S copied; copied.addAll(av); EXPECT_EQ(copied.size(), a.size());
  for (int v : av) EXPECT_TRUE(copied.contains(v));
  int remove[] = {1, 4}; copied.removeAll(remove);
  EXPECT_EQ(copied.size(), 1u); EXPECT_TRUE(copied.contains(3));
  EXPECT_EQ(a.first(), av[0]); EXPECT_EQ(*a.maybeFirst(), av[0]);
  S take = a; auto first = take.first(); EXPECT_EQ(take.takeFirst(), first); EXPECT_FALSE(take.contains(first));
  take = a; first = take.first(); EXPECT_EQ(*take.maybeTakeFirst(), first); EXPECT_FALSE(take.contains(first));
  EXPECT_FALSE(empty.maybeFirst()); EXPECT_FALSE(empty.maybeTakeFirst());
  setEmptyMessage([&] { empty.first(); }, "first called on empty set");
  setEmptyMessage([&] { empty.takeFirst(); }, "takeFirst called on empty set");
  // libc++ rejects std::prev(forward_iterator) at instantiation, even when the
  // runtime set is empty. Keep that native boundary instead of repairing it.
  if constexpr (std::is_same<S, Set<int>>::value) {
    EXPECT_FALSE(empty.maybeLast()); EXPECT_FALSE(empty.maybeTakeLast());
    setEmptyMessage([&] { empty.last(); }, "last called on empty set");
    setEmptyMessage([&] { empty.takeLast(); }, "takeLast called on empty set");
  }
  std::ostringstream failed; failed.setstate(std::ios::failbit); failed << a;
  EXPECT_TRUE(failed.fail()); EXPECT_TRUE(failed.str().empty());
  SetTrace streamFailure;
  SetThrowBuffer buffer(streamFailure);
  std::ostream throwing(&buffer); throwing.exceptions(std::ios::badbit);
  setSameException(streamFailure, [&] { throwing << a; });
  EXPECT_EQ(buffer.text, "(" + std::to_string(av[0]));
  EXPECT_TRUE(throwing.bad());
  EXPECT_EQ(a.values(), av); EXPECT_EQ(b.values(), bv);
  for (int failure : {0, 1, 2}) {
    SetTrace t; S source{1, 2, 3}; SetAdlRange range{&t};
    if (failure == 1) t.convert = 2;
    if (failure == 2) t.advance = 2;
    if (failure) setSameException(t, [&] { source.removeAll(range); });
    else source.removeAll(range);
    EXPECT_EQ(t.active, 0);
    EXPECT_FALSE(source.contains(1)); EXPECT_TRUE(failure == 0 || source.contains(3));
    EXPECT_EQ(source.contains(2), failure == 1);
    t.emit(name);
  }
}

struct SetValue {
  int n;
  static SetTrace* trace;
  explicit SetValue(int n) : n(n) {}
  SetValue(SetValue const& v) : n(v.n) {
    if (trace) { trace->log("C" + std::to_string(n)); if (trace->copy == n) trace->raise(); }
  }
  // Keep the key intact: FlatHashSet erases the source after this move.
  SetValue(SetValue&& v) : n(v.n) {
    if (trace) { trace->log("M" + std::to_string(n)); if (trace->move) trace->raise(); }
  }
  SetValue& operator=(SetValue const&) = default;
  SetValue& operator=(SetValue&&) = default;
  ~SetValue() { if (trace) trace->log("D" + std::to_string(n)); }
  friend bool operator<(SetValue const& a, SetValue const& b) {
    if (trace) { trace->log("L"); if (trace->compare) trace->raise(); }
    return a.n < b.n;
  }
  friend bool operator==(SetValue const& a, SetValue const& b) { return a.n == b.n; }
};
SetTrace* SetValue::trace = nullptr;
// Deliberately independent of the left-hand set: preserve original ADL lookup.
bool contains(SetValue const& v) {
  if (SetValue::trace) SetValue::trace->log("ADL" + std::to_string(v.n));
  return v.n % 2 == 0;
}
struct SetValueHash {
  size_t operator()(SetValue const& v) const {
    if (SetValue::trace) {
      SetValue::trace->log("H" + std::to_string(v.n));
      if (SetValue::trace->hash) SetValue::trace->raise();
    }
    return std::hash<int>{}(v.n);
  }
};
// Restore tracing before later container destructors; never retain a stack trace pointer.
struct SetTraceScope {
  SetTrace* previous;
  explicit SetTraceScope(SetTrace& t) : previous(SetValue::trace) { SetValue::trace = &t; }
  ~SetTraceScope() { SetValue::trace = previous; }
};
template <typename S> void setAdlIntersection(char const* name) {
  S emptySelf, other;
  for (int n : {1, 2, 4}) other.add(SetValue(n));
  SetTrace t;
  {
    SetTraceScope scope(t);
    {
      auto result = emptySelf.intersection(other);
      EXPECT_EQ(result.size(), 2u);
      EXPECT_TRUE(result.contains(SetValue(2))); EXPECT_TRUE(result.contains(SetValue(4)));
      EXPECT_FALSE(result.contains(SetValue(1)));
      std::cout << "SET_TRACE " << name << "-values";
      for (auto const& v : result) std::cout << ' ' << v.n;
      std::cout << '\n';
    }
    t.copy = 2;
    setSameException(t, [&] { emptySelf.intersection(other); });
    t.copy = -1;
    EXPECT_TRUE(emptySelf.empty()); EXPECT_EQ(other.size(), 3u);
    for (int n : {1, 2, 4}) EXPECT_TRUE(other.contains(SetValue(n)));
  }
  t.emit(name);
}
template <typename S> void setValueContracts(char const* name, bool mutableIterator) {
  S source; source.add(SetValue(1)); source.add(SetValue(2)); source.add(SetValue(3));
  int first = source.begin()->n;
  SetTrace t;
  {
    SetTraceScope scope(t);
    { auto value = source.maybeFirst(); ASSERT_TRUE(value); EXPECT_EQ(value->n, first); }
    { auto value = source.maybeTakeFirst(); ASSERT_TRUE(value); EXPECT_EQ(value->n, first); }
    EXPECT_EQ(source.size(), 2u);
    { auto value = source.first(); EXPECT_EQ(value.n, source.begin()->n); }
    { int n = source.begin()->n; auto value = source.takeFirst(); EXPECT_EQ(value.n, n); }
  }
  t.emit(name);
  S failing; failing.add(SetValue(1)); failing.add(SetValue(2));
  first = failing.begin()->n;
  SetTrace failure;
  {
    SetTraceScope scope(failure);
    if (mutableIterator) failure.move = true; else failure.copy = first;
    setSameException(failure, [&] { failing.maybeTakeFirst(); });
    failure.move = false; failure.copy = -1;
    EXPECT_EQ(failing.size(), 2u); EXPECT_TRUE(failing.contains(SetValue(first)));
    // values() remains native: record its copied prefix before the failing copy.
    auto it = failing.begin(); ++it; failure.copy = it->n;
    auto start = failure.events.size();
    setSameException(failure, [&] { failing.values(); });
    auto prefix = failure.events.substr(start);
    EXPECT_LT(prefix.find("C" + std::to_string(first) + ","), prefix.find("C" + std::to_string(it->n) + ","));
    failure.copy = -1; EXPECT_EQ(failing.size(), 2u);
  }
  failure.emit(name);
}

// A real std::set backing with a typed forward iterator returning a temporary.
// Intersection's free ADL contains checks parity; difference uses member
// membership. Both must retain the temporary across the predicate and add.
struct SetProxyBase {
  using value_type = int;
  static SetTrace* trace;
  std::set<int> data;
  struct iterator {
    using iterator_category = std::forward_iterator_tag;
    using value_type = int;
    using difference_type = std::ptrdiff_t;
    using reference = SetProxy;
    using pointer = void;
    std::set<int>::const_iterator inner;
    SetProxy operator*() const { return {trace, *inner}; }
    iterator& operator++() { EXPECT_EQ(trace->active, 0); trace->log("I"); ++inner; return *this; }
    iterator operator++(int) { auto old = *this; ++*this; return old; }
    bool operator==(iterator const& rhs) const { return inner == rhs.inner; }
    bool operator!=(iterator const& rhs) const { return inner != rhs.inner; }
  };
  using const_iterator = iterator;
  iterator begin() const { return {data.begin()}; }
  iterator end() const { return {data.end()}; }
  iterator find(int n) const { return {data.find(n)}; }
  std::pair<iterator, bool> insert(int n) { auto p = data.insert(n); return {{p.first}, p.second}; }
};
SetTrace* SetProxyBase::trace = nullptr;
}

TEST(SetTest, PolicyProxyBaseScopeLifetime) {
  SetTrace t;
  struct Scope {
    SetTrace* previous;
    explicit Scope(SetTrace& t) : previous(SetProxyBase::trace) { SetProxyBase::trace = &t; }
    ~Scope() { SetProxyBase::trace = previous; }
  } scope(t);
  HashSetMixin<SetProxyBase> a, b;
  a.add(1); a.add(2); b.add(2); b.add(3);
  auto intersection = a.intersection(b), difference = a.difference(b);
  EXPECT_EQ(intersection.data, std::set<int>({2}));
  EXPECT_EQ(difference.data, std::set<int>({1}));
  EXPECT_EQ(t.active, 0);
  EXPECT_EQ(t.events, "P2,V2,V2,D2,I,P3,V3,D3,I,P1,V1,V1,D1,I,P2,V2,D2,I,");
  t.emit("scopeLifetime");
}

TEST(SetTest, PolicyIntegerContracts) {
  setIntegerContracts<Set<int>>("sorted");
  setIntegerContracts<HashSet<int>>("flat");
  setIntegerContracts<StableHashSet<int>>("stable");
  Set<int> a{1, 2, 3};
  EXPECT_EQ(a.last(), 3); EXPECT_EQ(*a.maybeLast(), 3);
  EXPECT_EQ(a.takeLast(), 3); EXPECT_EQ(*a.maybeTakeLast(), 2);
  EXPECT_EQ(a.values(), List<int>({1}));
  EXPECT_EQ(a.intersection(Set<int>{1}, std::less<int>()), Set<int>({1}));
  EXPECT_TRUE(a.difference(Set<int>{1}, std::less<int>()).empty());
}

TEST(SetTest, PolicyOriginalAdlIntersection) {
  setAdlIntersection<HashSet<SetValue, SetValueHash>>("flat-adl-intersection");
  setAdlIntersection<StableHashSet<SetValue, SetValueHash>>("stable-adl-intersection");
}

TEST(SetTest, PolicyValueLifetimeAndFailureIdentity) {
  setValueContracts<Set<SetValue>>("sorted-value", false);
  setValueContracts<HashSet<SetValue, SetValueHash>>("flat-value", true);
  setValueContracts<StableHashSet<SetValue, SetValueHash>>("stable-value", false);
  Set<SetValue> sorted; sorted.add(SetValue(1));
  HashSet<SetValue, SetValueHash> flat; flat.add(SetValue(1));
  StableHashSet<SetValue, SetValueHash> stable; stable.add(SetValue(1));
  SetTrace t;
  {
    SetTraceScope scope(t); t.compare = true;
    setSameException(t, [&] { sorted.hasIntersection(sorted); }); t.compare = false;
    t.hash = true;
    setSameException(t, [&] { flat.hasIntersection(flat); });
    setSameException(t, [&] { stable.hasIntersection(stable); }); t.hash = false;
    { auto value = sorted.maybeLast(); ASSERT_TRUE(value); EXPECT_EQ(value->n, 1); }
    { auto value = sorted.maybeTakeLast(); ASSERT_TRUE(value); EXPECT_EQ(value->n, 1); }
    EXPECT_TRUE(sorted.empty());
  }
  t.emit("lookup-errors");
}

namespace {
template <typename S> void setShortCircuit(char const* name) {
  S target, source;
  source.add(SetValue(1)); source.add(SetValue(2)); target.add(*source.begin());
  SetTrace t;
  {
    SetTraceScope scope(t);
    EXPECT_TRUE(target.hasIntersection(source));
  }
  // Compare directly with the first native lookup: no second element is visited.
  SetTrace first;
  { SetTraceScope scope(first); EXPECT_TRUE(target.contains(*source.begin())); }
  EXPECT_EQ(t.events, first.events);
  t.emit(name);
}
}
TEST(SetTest, PolicyIntersectionShortCircuit) {
  setShortCircuit<Set<SetValue>>("sorted-any");
  setShortCircuit<HashSet<SetValue, SetValueHash>>("flat-any");
  setShortCircuit<StableHashSet<SetValue, SetValueHash>>("stable-any");
}

#ifdef STAR_USE_RUST_SET
TEST(SetTest, PolicyOrdinaryApiCounters) {
  uint64_t loops[SB_SET_COUNT], selections[SB_SET_SELECT_COUNT];
  for (uint32_t i = 0; i < SB_SET_COUNT; ++i) loops[i] = sb_set_count(i);
  for (uint32_t i = 0; i < SB_SET_SELECT_COUNT; ++i) selections[i] = sb_set_select_count(i);
  HashSet<int> a{1, 2}, b{2, 3}; int remove[] = {1};
  a.removeAll(remove); EXPECT_TRUE(a.hasIntersection(b));
  std::ostringstream out; out << a;
  EXPECT_EQ(a.first(), 2); EXPECT_TRUE(a.maybeFirst());
  HashSet<SetValue, SetValueHash> emptySelf, other;
  other.add(SetValue(2));
  EXPECT_EQ(emptySelf.intersection(other).size(), 1u);
  EXPECT_TRUE(a.difference(b).empty());
  for (auto mode : {SB_SET_REMOVE_RANGE, SB_SET_PRINT, SB_SET_ANY, SB_SET_SCOPED_RANGE})
    EXPECT_GT(sb_set_count(mode), loops[mode]);
  for (auto mode : {SB_SET_SELECT_NONEMPTY, SB_SET_SELECT_OPTIONAL, SB_SET_SELECT_FILTER_INTERSECTION, SB_SET_SELECT_FILTER_DIFFERENCE})
    EXPECT_GT(sb_set_select_count(mode), selections[mode]);
  EXPECT_EQ(sb_set_count(SB_SET_COUNT), 0u);
  EXPECT_EQ(sb_set_select_count(SB_SET_SELECT_COUNT), 0u);
}
#endif
