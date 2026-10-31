#include "StarFlatHashSet.hpp"
#include "StarFlatHashMap.hpp"
#include "StarRandom.hpp"
#include "StarVector.hpp"
#include "StarIterator.hpp"

#include "gtest/gtest.h"

#include <cstdio>
#include <functional>
#include <limits>
#include <memory>
#include <new>
#include <set>
#include <string>
#include <type_traits>

#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
#include "StarRustFlatHashTable.h"
#endif

using namespace Star;

TEST(FlatHashSet, Preset) {
  FlatHashSet<int> testSet = {42, 63};
  ASSERT_EQ(testSet.find(41), testSet.end());
  ASSERT_EQ(*testSet.find(42), 42);
  ASSERT_EQ(*testSet.find(63), 63);
  ASSERT_EQ(testSet.find(64), testSet.end());
  ASSERT_EQ(testSet.size(), 2u);

  testSet.erase(testSet.find(42));
  ASSERT_EQ(testSet.find(42), testSet.end());
  ASSERT_EQ(*testSet.find(63), 63);
  ASSERT_EQ(testSet.size(), 1u);

  testSet.erase(testSet.find(63));
  ASSERT_EQ(testSet.find(42), testSet.end());
  ASSERT_EQ(testSet.find(63), testSet.end());
  ASSERT_EQ(testSet.size(), 0u);

  testSet.insert(12);
  testSet.insert(24);
  ASSERT_EQ(*testSet.find(12), 12);
  ASSERT_EQ(testSet.size(), 2u);
  testSet.clear();

  ASSERT_EQ(testSet.find(12), testSet.end());
  ASSERT_EQ(testSet.size(), 0u);

  EXPECT_TRUE(testSet.insert(7).second);
  EXPECT_TRUE(testSet.insert(11).second);
  EXPECT_FALSE(testSet.insert(7).second);

  ASSERT_EQ(testSet.size(), 2u);

  FlatHashSet<int> testSet2(testSet.begin(), testSet.end());
  ASSERT_EQ(testSet, testSet2);

  ASSERT_EQ(testSet.erase(testSet.begin(), testSet.end()), testSet.end());
  ASSERT_EQ(testSet.size(), 0u);

  ASSERT_NE(testSet, testSet2);

  FlatHashSet<int> testSet3(testSet.begin(), testSet.end());
  ASSERT_EQ(testSet3.size(), 0u);

  testSet2 = testSet;
  ASSERT_EQ(testSet, testSet2);
}

TEST(FlatHashSet, Random) {
  List<Vec2I> keys;
  for (unsigned i = 0; i < 100000; ++i)
    keys.append(Vec2I(i * 743202097, i * 205495087));
  Random::shuffle(keys);

  FlatHashSet<Vec2I> testSet;
  for (size_t i = 0; i < keys.size(); ++i)
    testSet.insert(keys[i]);

  Random::shuffle(keys);
  for (size_t i = 0; i < keys.size() / 2; ++i)
    testSet.erase(keys[i]);

  Random::shuffle(keys);
  for (size_t i = 0; i < keys.size() / 3; ++i)
    testSet.insert(keys[i]);

  Random::shuffle(keys);
  for (size_t i = 0; i < keys.size() / 2; ++i)
    testSet.erase(keys[i]);

  Random::shuffle(keys);
  for (auto k : keys) {
    auto i = testSet.find(k);
    if (i != testSet.end()) {
      ASSERT_TRUE(*i == k);
    }
  }

  Random::shuffle(keys);
  for (auto k : keys) {
    testSet.insert(k);
    ASSERT_TRUE(testSet.find(k) != testSet.end());
  }

  List<Vec2I> cmp;
  for (auto const& k : testSet)
    cmp.append(k);
  cmp.sort();
  keys.sort();
  ASSERT_TRUE(cmp == keys);

  Random::shuffle(keys);
  for (auto k : keys) {
    testSet.erase(k);
    ASSERT_TRUE(testSet.find(k) == testSet.end());
  }

  ASSERT_TRUE(testSet.empty());
}

TEST(FlatHashMap, Preset) {
  FlatHashMap<int, int> testMap = {{42, 42}, {63, 63}};
  ASSERT_EQ(testMap.find(41), testMap.end());
  ASSERT_EQ(testMap.find(42)->second, 42);
  ASSERT_EQ(testMap.find(63)->second, 63);
  ASSERT_EQ(testMap.find(64), testMap.end());
  ASSERT_EQ(testMap.size(), 2u);

  testMap.erase(testMap.find(42));
  ASSERT_EQ(testMap.find(42), testMap.end());
  ASSERT_EQ(testMap.find(63)->second, 63);
  ASSERT_EQ(testMap.size(), 1u);

  testMap.erase(testMap.find(63));
  ASSERT_EQ(testMap.find(42), testMap.end());
  ASSERT_EQ(testMap.find(63), testMap.end());
  ASSERT_EQ(testMap.size(), 0u);

  testMap.insert({12, 12});
  testMap.insert({24, 24});
  ASSERT_EQ(testMap.find(12)->second, 12);
  ASSERT_EQ(testMap.size(), 2u);
  testMap.clear();

  ASSERT_EQ(testMap.find(12), testMap.end());
  ASSERT_EQ(testMap.size(), 0u);

  EXPECT_TRUE(testMap.insert({7, 7}).second);
  EXPECT_TRUE(testMap.insert({11, 11}).second);
  EXPECT_FALSE(testMap.insert({7, 7}).second);

  ASSERT_EQ(testMap.size(), 2u);

  FlatHashMap<int, int> testMap2(testMap.begin(), testMap.end());
  ASSERT_EQ(testMap, testMap2);

  ASSERT_EQ(testMap.erase(testMap.begin(), testMap.end()), testMap.end());
  ASSERT_EQ(testMap.size(), 0u);

  ASSERT_NE(testMap, testMap2);

  FlatHashMap<int, int> testMap3(testMap.begin(), testMap.end());
  ASSERT_EQ(testMap3.size(), 0u);

  testMap2 = testMap;
  ASSERT_EQ(testMap, testMap2);
}

TEST(FlatHashMap, Random) {
  List<pair<Vec2I, int>> values;
  for (unsigned i = 0; i < 100000; ++i)
    values.append({Vec2I(i * 743202097, i * 205495087), i});
  Random::shuffle(values);

  FlatHashMap<Vec2I, int> testMap;
  for (auto v : values)
    testMap.insert(v);

  Random::shuffle(values);
  for (size_t i = 0; i < values.size() / 2; ++i)
    testMap.erase(values[i].first);

  Random::shuffle(values);
  for (size_t i = 0; i < values.size() / 3; ++i)
    testMap.insert(values[i]);

  Random::shuffle(values);
  for (size_t i = 0; i < values.size() / 2; ++i)
    testMap.erase(values[i].first);

  Random::shuffle(values);
  for (auto v : values) {
    auto i = testMap.find(v.first);
    if (i != testMap.end()) {
      ASSERT_TRUE(i->second == v.second);
    }
  }

  Random::shuffle(values);
  for (auto v : values) {
    ASSERT_TRUE(testMap.insert(v).first->second == v.second);
    ASSERT_TRUE(testMap.at(v.first) == v.second);
  }

  Random::shuffle(values);
  for (auto v : values) {
    ASSERT_EQ(testMap.erase(v.first), 1u);
    ASSERT_TRUE(testMap.find(v.first) == testMap.end());
  }

  ASSERT_TRUE(testMap.empty());
}

TEST(FlatHashMap, Iterator) {
  List<pair<Vec2I, int>> values;
  for (unsigned i = 0; i < 100000; ++i)
    values.append({Vec2I(i * 743202097, i * 205495087), i});

  FlatHashMap<Vec2I, int> testMap;
  for (auto v : values)
    testMap.insert(v);

  auto it = makeSMutableMapIterator(testMap);
  while (it.hasNext()) {
    if (it.next().second % 3 == 0)
      it.remove();
  }

  auto i = values.begin();
  std::advance(i, values.size());
  ASSERT_EQ(i, values.end());
}

namespace {
struct FlatProbeMarker {};
struct FlatProbeHooks {
  std::string trace;
  std::function<void(int)> onHash;
  std::function<void()> onEquals;
  FlatProbeMarker* thrownMarker = nullptr;
  int throwAt = 0, liveTemps = 0, copies = 0, moves = 0, deaths = 0;
  int const* keyAddress = nullptr;
  void event(char kind, int key) { trace += kind + std::to_string(key) + ";"; }
  void fail(int stage) {
    if (throwAt != stage) return;
    try { throw FlatProbeMarker{}; }
    catch (FlatProbeMarker& marker) { thrownMarker = &marker; throw; }
  }
  void emit(char const* label) const {
    std::printf("FLAT_PROBE_TRACE %s %s\n", label, trace.c_str());
  }
};
struct FlatProbeHash {
  FlatProbeHooks* hooks = nullptr;
  int mode = 0;
  size_t operator()(int key) const {
    if (hooks) {
      hooks->event('h', key);
      hooks->fail(1);
      if (hooks->onHash) hooks->onHash(key);
    }
    if (mode == 1) return std::numeric_limits<size_t>::max() - 1;
    if (mode == 2) return key == 15 || key == 23 ? 7 : size_t(key);
    return size_t(key);
  }
};
struct FlatProbeEquals {
  FlatProbeHooks* hooks = nullptr;
  bool operator()(int const& a, int const& b) const {
    if (hooks) {
      hooks->event('e', a);
      hooks->event('q', b);
      if (hooks->keyAddress) {
        EXPECT_EQ(&a, hooks->keyAddress);
        EXPECT_EQ(hooks->liveTemps, 1);
      }
      hooks->fail(3);
      // A reentrant erase can destroy/change a; never inspect it afterwards.
      if (hooks->onEquals) { hooks->onEquals(); return false; }
    }
    return a == b;
  }
};
struct FlatProbeValue {
  int key;
  FlatProbeHooks* hooks;
  FlatProbeValue(int k, FlatProbeHooks* h) : key(k), hooks(h) {}
  FlatProbeValue(FlatProbeValue const& v) : key(v.key), hooks(v.hooks) { ++hooks->copies; }
  FlatProbeValue(FlatProbeValue&& v) : key(v.key), hooks(v.hooks) { ++hooks->moves; }
  FlatProbeValue& operator=(FlatProbeValue const& v) {
    key = v.key; hooks = v.hooks; ++hooks->copies; return *this;
  }
  FlatProbeValue& operator=(FlatProbeValue&& v) {
    key = v.key; hooks = v.hooks; ++hooks->moves; return *this;
  }
  ~FlatProbeValue() { ++hooks->deaths; }
};
struct FlatProbeTemp {
  int const* key;
  FlatProbeHooks* hooks;
  FlatProbeTemp(int const& k, FlatProbeHooks* h) : key(&k), hooks(h) {
    ++hooks->liveTemps; hooks->trace += "t+;";
  }
  FlatProbeTemp(FlatProbeTemp const&) = delete;
  ~FlatProbeTemp() { --hooks->liveTemps; hooks->trace += "t-;"; }
  operator int const&() const { EXPECT_GT(hooks->liveTemps, 0); return *key; }
};
struct FlatProbeGetKey {
  FlatProbeHooks* hooks;
  FlatProbeTemp operator()(FlatProbeValue const& v) const {
    hooks->event('g', v.key); hooks->fail(2);
    return FlatProbeTemp(v.key, hooks);
  }
};
using FlatProbeTable = FlatHashTable<FlatProbeValue, int, FlatProbeGetKey,
    FlatProbeHash, FlatProbeEquals, std::allocator<FlatProbeValue>>;
}

TEST(FlatHashProbe, WrappedNormalizationAndModel) {
  FlatHashSet<int, FlatProbeHash> wrapped(0, FlatProbeHash{nullptr, 1});
  for (int k : {7, 15, 23, 31, 39}) wrapped.insert(k);
  for (int k : {7, 15, 23, 31, 39}) ASSERT_EQ(*wrapped.find(k), k);
  EXPECT_EQ(wrapped.find(47), wrapped.end());
  wrapped.erase(wrapped.find(23));
  EXPECT_EQ(wrapped.find(23), wrapped.end());
  EXPECT_NE(wrapped.find(39), wrapped.end());

  struct RawHash { size_t operator()(size_t k) const { return k; } };
  FlatHashSet<size_t, RawHash> raw;
  size_t high = size_t(1) << (sizeof(size_t) * 8 - 1);
  for (size_t k : {size_t(0), size_t(1), high, high | 1, ~size_t(0)}) raw.insert(k);
  for (size_t k : {size_t(0), size_t(1), high, high | 1, ~size_t(0)})
    EXPECT_EQ(*raw.find(k), k);
  EXPECT_EQ(raw.find(high | 2), raw.end());

  FlatHashSet<int, FlatProbeHash> set(0, FlatProbeHash{nullptr, 1});
  FlatHashMap<int, int, FlatProbeHash> map(0, FlatProbeHash{nullptr, 1});
  std::set<int> model;
  uint32_t state = 0x13579bdu;
  for (int step = 0; step != 768; ++step) {
    state = state * 1664525u + 1013904223u;
    int key = int((state >> 8) % 97);
    if (state & 1) { model.insert(key); set.insert(key); map.insert({key, key * 3}); }
    else { model.erase(key); set.erase(key); map.erase(key); }
    EXPECT_EQ(set.find(key) != set.end(), model.count(key) != 0);
    EXPECT_EQ(map.find(key) != map.end(), model.count(key) != 0);
    if (step % 16 == 0) {
      std::set<int> actual;
      for (auto const& entry : map) { actual.insert(entry.first); EXPECT_EQ(entry.second, entry.first * 3); }
      EXPECT_EQ(actual, model);
      actual.clear();
      auto const& view = set;
      for (auto i = view.begin(); i != view.end(); i++) actual.insert(*i);
      EXPECT_EQ(actual, model);
    }
  }
}

TEST(FlatHashProbe, ScopedKeysExceptionsAndNoValueCopies) {
  FlatProbeHooks hooks;
  FlatProbeTable table(0, FlatProbeGetKey{&hooks}, FlatProbeHash{&hooks, 1},
      FlatProbeEquals{&hooks}, std::allocator<FlatProbeValue>{});
  table.insert(FlatProbeValue(9, &hooks));
  hooks.emit("insert"); // Includes source-phase GetKey temporaries, not just stored values.
  auto stored = table.begin();
  hooks.keyAddress = &stored->key;
  int copies = hooks.copies, moves = hooks.moves, deaths = hooks.deaths;
  hooks.trace.clear();
  EXPECT_EQ(table.find(9), stored);
  EXPECT_EQ(hooks.trace, "h9;g9;t+;e9;q9;t-;");
  EXPECT_EQ(table.find(17), table.end());
  auto const& view = table;
  EXPECT_NE(view.find(9), view.end());
  ++stored;
  EXPECT_EQ(stored, table.end());
  EXPECT_EQ(view.begin()->key, 9);
  EXPECT_EQ(hooks.liveTemps, 0);
  EXPECT_EQ(hooks.copies, copies);
  EXPECT_EQ(hooks.moves, moves);
  EXPECT_EQ(hooks.deaths, deaths);
  hooks.emit("scoped");
  for (int stage : {1, 2, 3}) {
    hooks.trace.clear(); hooks.throwAt = stage;
    bool caught = false;
    try { table.find(9); }
    catch (FlatProbeMarker& marker) { caught = true; EXPECT_EQ(&marker, hooks.thrownMarker); }
    EXPECT_TRUE(caught);
    EXPECT_EQ(hooks.liveTemps, 0);
    EXPECT_EQ(hooks.trace, stage == 1 ? "h9;" : stage == 2 ? "h9;g9;" : "h9;g9;t+;e9;q9;t-;");
    hooks.emit("throw");
    hooks.throwAt = 0;
  }
  EXPECT_EQ(table.size(), 1u);
  EXPECT_EQ(hooks.copies, copies);
  EXPECT_EQ(hooks.moves, moves);
  EXPECT_EQ(hooks.deaths, deaths);
}

TEST(FlatHashProbe, RobinHoodTerminationAndSparseScans) {
  FlatProbeHooks hooks;
  FlatHashSet<int, FlatProbeHash, FlatProbeEquals> set(0, FlatProbeHash{&hooks}, FlatProbeEquals{&hooks});
  set.insert(0); set.insert(1);
  hooks.trace.clear();
  // raw 8 starts at 0, then meets raw 1 at home: distance 1 > 0.
  EXPECT_EQ(set.find(8), set.end());
  EXPECT_EQ(hooks.trace, "h8;");
  hooks.emit("early-exit");
  set.reserve(100);
  set.insert(99);
  std::set<int> expected{0, 1, 99}, actual;
  for (auto i = set.begin(); i != set.end(); ++i) actual.insert(*i);
  EXPECT_EQ(actual, expected);
  actual.clear();
  auto const& view = set;
  for (auto i = view.begin(); i != view.end(); i++) actual.insert(*i);
  EXPECT_EQ(actual, expected);
  set.clear();
  EXPECT_EQ(set.begin(), set.end());
  EXPECT_EQ(view.begin(), view.end());
}

TEST(FlatHashProbe, HashReentryUsesFreshCapacity) {
  FlatProbeHooks hooks;
  FlatHashSet<int, FlatProbeHash> set(0, FlatProbeHash{&hooks});
  set.insert(33);
  bool armed = true;
  hooks.onHash = [&](int key) {
    if (key == 33 && armed) { armed = false; set.reserve(100); }
  };
  hooks.trace.clear();
  int externalKey = 33;
  auto found = set.find(externalKey);
  ASSERT_NE(found, set.end());
  EXPECT_EQ(*found, 33);
  EXPECT_FALSE(armed);
  EXPECT_EQ(set.size(), 1u);
  EXPECT_EQ(hooks.trace, "h33;h33;");
  hooks.emit("hash-reentry");
}

TEST(FlatHashProbe, EqualsReentryReadsMutatedBucketHash) {
  FlatProbeHooks hooks;
  FlatHashSet<int, FlatProbeHash, FlatProbeEquals> set(0, FlatProbeHash{&hooks, 2}, FlatProbeEquals{&hooks});
  // Capacity 8: raw hashes 7/7/0/1 occupy slots 7/0/1/2.
  for (int key : {7, 15, 0, 1}) set.insert(key);
  auto victim = set.find(15);
  ASSERT_NE(victim, set.end());
  int calls = 0;
  hooks.onEquals = [&] { if (++calls == 2) set.erase(victim); };
  hooks.trace.clear();
  EXPECT_EQ(set.find(23), set.end());
  EXPECT_EQ(calls, 2);
  EXPECT_EQ(hooks.trace, "h23;e7;q23;e15;q23;");
  hooks.emit("equals-reentry");
  hooks.onEquals = {};
  std::set<int> actual;
  for (int key : set) actual.insert(key);
  EXPECT_EQ(actual, (std::set<int>{0, 1, 7}));
  EXPECT_EQ(set.size(), 3u);
  EXPECT_EQ(set.find(15), set.end());
}

#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
TEST(FlatHashProbe, PublicDiagnostics) {
  uint64_t before[2][2];
  for (uint32_t kind = 0; kind != 2; ++kind)
    for (uint32_t mode = 0; mode != 2; ++mode) before[kind][mode] = sb_flat_hash_count(kind, mode);
  FlatHashSet<int> set{2, 97};
  EXPECT_NE(set.find(2), set.end());
  for (auto i = set.begin(); i != set.end(); ++i) EXPECT_TRUE(*i == 2 || *i == 97);
  for (uint32_t kind = 0; kind != 2; ++kind)
    for (uint32_t mode = 0; mode != 2; ++mode) EXPECT_GT(sb_flat_hash_count(kind, mode), before[kind][mode]);
}
#endif

namespace {
struct FlatInsertMarker {};
struct FlatInsertHooks {
  std::string trace;
  FlatInsertMarker* marker = nullptr;
  int failAt = 0, swapFailure = 0, moveFailure = 0;
  int liveTemps = 0, liveValues = 0, moves = 0, copies = 0;
  bool inserting = false;
  void event(char kind, int key) { trace += kind + std::to_string(key) + ";"; }
  void fail(int stage) {
    if (failAt != stage) return;
    try { throw FlatInsertMarker{}; }
    catch (FlatInsertMarker& original) { marker = &original; throw; }
  }
  void emit(char const* label) const {
    std::printf("FLAT_INSERT_TRACE %s %s\n", label, trace.c_str());
  }
};
// The guard also disarms callbacks on a fatal assertion, before bucket cleanup.
struct FlatInsertArm {
  FlatInsertHooks& hooks;
  explicit FlatInsertArm(FlatInsertHooks& h) : hooks(h) { hooks.inserting = true; }
  ~FlatInsertArm() {
    hooks.inserting = false;
    hooks.failAt = hooks.swapFailure = hooks.moveFailure = 0;
  }
};
struct FlatInsertValue {
  int key, payload;
  FlatInsertHooks* hooks;
  FlatInsertValue(int k, FlatInsertHooks* h) : key(k), payload(k * 17), hooks(h) {
    ++hooks->liveValues; hooks->event('N', key);
  }
  FlatInsertValue(FlatInsertValue const& v) : key(v.key), payload(v.payload), hooks(v.hooks) {
    ++hooks->copies; ++hooks->liveValues; hooks->event('C', key);
  }
  FlatInsertValue(FlatInsertValue&& v) : key(v.key), payload(v.payload), hooks(v.hooks) {
    ++hooks->moves; hooks->event('M', key);
    if (hooks->inserting && hooks->moves == hooks->moveFailure) hooks->fail(4);
    ++hooks->liveValues;
  }
  FlatInsertValue& operator=(FlatInsertValue const& v) {
    key = v.key; payload = v.payload; ++hooks->copies; hooks->event('c', key); return *this;
  }
  FlatInsertValue& operator=(FlatInsertValue&& v) {
    key = v.key; payload = v.payload; ++hooks->moves; hooks->event('m', key); return *this;
  }
  ~FlatInsertValue() { --hooks->liveValues; hooks->event('D', key); }
};
void swap(FlatInsertValue& a, FlatInsertValue& b) {
  auto& h = *a.hooks;
  h.event('S', a.key); h.event('s', b.key);
  if (h.inserting && h.swapFailure == 1) h.fail(5);
  // Deliberately only partially mutate before the second failure. Native insert
  // has not exchanged bucket hash metadata yet; repairing it would change behavior.
  int key = a.key; a.key = b.key; b.key = key;
  if (h.inserting && h.swapFailure == 2) h.fail(5);
  int payload = a.payload; a.payload = b.payload; b.payload = payload;
}
struct FlatInsertTemp {
  int const* key;
  FlatInsertHooks* hooks;
  FlatInsertTemp(int const& k, FlatInsertHooks* h) : key(&k), hooks(h) {
    ++hooks->liveTemps; hooks->event('+', *key);
  }
  FlatInsertTemp(FlatInsertTemp const&) = delete;
  ~FlatInsertTemp() { hooks->event('-', *key); --hooks->liveTemps; }
  operator int const&() const { EXPECT_GT(hooks->liveTemps, 0); return *key; }
};
struct FlatInsertGetKey {
  FlatInsertHooks* hooks;
  FlatInsertTemp operator()(FlatInsertValue const& v) const {
    hooks->event('g', v.key); hooks->fail(1); return FlatInsertTemp(v.key, hooks);
  }
};
struct FlatInsertHash {
  FlatInsertHooks* hooks = nullptr;
  size_t operator()(int key) const {
    if (hooks) { hooks->event('h', key); hooks->fail(2); }
    return key == 2 ? 2 : 0;
  }
};
struct FlatInsertEquals {
  FlatInsertHooks* hooks;
  bool operator()(int const& a, int const& b) const {
    hooks->event('e', a); hooks->event('q', b);
    // Both argument temporaries survive into Equals; their construction order
    // is deliberately observed, not prescribed across native compilers.
    EXPECT_EQ(hooks->liveTemps, hooks->inserting ? 2 : 1);
    hooks->fail(3); return a == b;
  }
};
using FlatInsertTable = FlatHashTable<FlatInsertValue, int, FlatInsertGetKey,
    FlatInsertHash, FlatInsertEquals, std::allocator<FlatInsertValue>>;
}

TEST(FlatHashInsert, DisplacementDuplicateAndScopedArguments) {
  FlatInsertHooks h;
  {
    FlatInsertTable table(3, FlatInsertGetKey{&h}, FlatInsertHash{&h}, FlatInsertEquals{&h}, {});
    FlatInsertArm arm(h);
    for (int key : {0, 1, 2}) table.insert(FlatInsertValue(key, &h));
    auto base = table.begin().current;
    h.trace.clear();
    auto added = table.insert(FlatInsertValue(3, &h));
    ASSERT_TRUE(added.second);
    EXPECT_EQ(added.first.current - base, 2);
    EXPECT_EQ(added.first->key, 3);
    EXPECT_EQ(added.first->payload, 51);
    EXPECT_EQ((base + 3)->valuePtr()->key, 2);
    EXPECT_EQ(h.liveTemps, 0);
    h.emit("displace"); h.trace.clear();
    auto duplicate = table.insert(FlatInsertValue(3, &h));
    EXPECT_FALSE(duplicate.second);
    EXPECT_EQ(duplicate.first, added.first);
    EXPECT_EQ(table.size(), 4u);
    EXPECT_EQ(h.liveValues, 4);
    EXPECT_EQ(h.liveTemps, 0);
    h.emit("duplicate"); h.trace.clear();
    table.reserve(40);
    EXPECT_EQ(table.size(), 4u);
    EXPECT_EQ(h.liveValues, 4); EXPECT_EQ(h.liveTemps, 0);
    for (auto const& value : table) EXPECT_EQ(value.payload, value.key * 17);
    h.event('C', h.copies); h.event('M', h.moves);
    h.emit("reserve-reinsert"); h.trace.clear();
  }
  EXPECT_EQ(h.liveValues, 0); h.emit("displace-cleanup");
}

TEST(FlatHashInsert, CallbackExceptionsKeepOriginalObjectAndParameterLifetime) {
  for (int stage : {1, 2, 3}) {
    FlatInsertHooks h;
    {
      FlatInsertTable table(3, FlatInsertGetKey{&h}, FlatInsertHash{&h}, FlatInsertEquals{&h}, {});
      table.insert(FlatInsertValue(0, &h));
      FlatInsertValue caller(3, &h);
      h.trace.clear();
      {
        FlatInsertArm arm(h); h.failAt = stage;
        bool caught = false;
        try { table.insert(caller); }
        catch (FlatInsertMarker& original) { caught = true; EXPECT_EQ(&original, h.marker); }
        EXPECT_TRUE(caught);
        EXPECT_EQ(table.size(), 1u);
        EXPECT_EQ(h.liveTemps, 0);
        EXPECT_EQ(h.liveValues, 2); // Only stored key and the caller remain alive.
        EXPECT_EQ(caller.key, 3); EXPECT_EQ(caller.payload, 51);
      }
      h.event('F', stage); h.emit("callback-throw"); h.trace.clear();
    }
    EXPECT_EQ(h.liveValues, 0); h.emit("callback-cleanup");
  }
}

TEST(FlatHashInsert, AdlSwapExceptionsPreserveNativePartialMutation) {
  for (int stage : {1, 2}) {
    FlatInsertHooks h;
    {
      FlatInsertTable table(3, FlatInsertGetKey{&h}, FlatInsertHash{&h}, FlatInsertEquals{&h}, {});
      {
        FlatInsertArm arm(h);
        for (int key : {0, 1, 2}) table.insert(FlatInsertValue(key, &h));
      }
      h.trace.clear();
      {
        FlatInsertArm arm(h); h.swapFailure = stage; h.failAt = 5;
        bool caught = false;
        try { table.insert(FlatInsertValue(3, &h)); }
        catch (FlatInsertMarker& original) { caught = true; EXPECT_EQ(&original, h.marker); }
        EXPECT_TRUE(caught);
        EXPECT_EQ(h.liveTemps, 0); EXPECT_EQ(h.liveValues, 3);
      }
      EXPECT_EQ(table.size(), 3u);
      std::set<int> keys;
      for (auto const& value : table) keys.insert(value.key);
      EXPECT_EQ(keys, stage == 1 ? (std::set<int>{0, 1, 2}) : (std::set<int>{0, 1, 3}));
      // At stage two slot 2 still carries hash 2, not key 3's hash 0.
      EXPECT_EQ(table.find(3), table.end());
      h.event('F', stage); h.emit("swap-throw"); h.trace.clear();
    }
    EXPECT_EQ(h.liveValues, 0); h.emit("swap-cleanup");
  }
}

TEST(FlatHashInsert, SetFilledMoveFailuresNeverDestroyUnconstructedValue) {
  for (int stage : {1, 2}) {
    FlatInsertHooks h;
    {
      FlatInsertTable table(3, FlatInsertGetKey{&h}, FlatInsertHash{&h}, FlatInsertEquals{&h}, {});
      FlatInsertValue caller(9, &h);
      h.trace.clear(); h.moves = h.copies = 0;
      {
        FlatInsertArm arm(h); h.moveFailure = stage; h.failAt = 4;
        bool caught = false;
        try { table.insert(caller); }
        catch (FlatInsertMarker& original) { caught = true; EXPECT_EQ(&original, h.marker); }
        EXPECT_TRUE(caught);
        EXPECT_EQ(table.size(), 0u); EXPECT_EQ(table.begin(), table.end());
        EXPECT_EQ(h.liveTemps, 0); EXPECT_EQ(h.liveValues, 1);
        EXPECT_EQ(h.copies, 1); EXPECT_EQ(h.moves, stage);
        EXPECT_EQ(caller.key, 9); EXPECT_EQ(caller.payload, 153);
      }
      h.event('F', stage); h.emit("set-filled-throw"); h.trace.clear();
    }
    EXPECT_EQ(h.liveValues, 0); h.emit("set-filled-cleanup");
  }
}

TEST(FlatHashInsert, GrowthAndReserveReinsertActualMapFields) {
  FlatHashMap<int, int, FlatInsertHash> map(0, FlatInsertHash{});
  for (int key = 0; key != 192; ++key) {
    auto added = map.insert({key, key * 17});
    EXPECT_TRUE(added.second); EXPECT_EQ(added.first->first, key);
    EXPECT_EQ(added.first->second, key * 17);
    if (key == 23 || key == 95) map.reserve(size_t(key + 100));
  }
  EXPECT_EQ(map.size(), 192u);
  for (int key = 0; key != 192; ++key) {
    auto duplicate = map.insert({key, -1});
    EXPECT_FALSE(duplicate.second); EXPECT_EQ(duplicate.first->second, key * 17);
    EXPECT_EQ(map.at(key), key * 17);
  }
}

#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
TEST(FlatHashInsert, PublicInsertDiagnostics) {
  uint64_t before[2];
  FlatHashSet<int> set;
  for (uint32_t kind = 0; kind != 2; ++kind) before[kind] = sb_flat_hash_count(kind, SB_FLAT_HASH_INSERT);
  EXPECT_TRUE(set.insert(3).second);
  EXPECT_FALSE(set.insert(3).second);
  for (uint32_t kind = 0; kind != 2; ++kind)
    EXPECT_GT(sb_flat_hash_count(kind, SB_FLAT_HASH_INSERT), before[kind]);
  EXPECT_EQ(sb_flat_hash_count(0, SB_FLAT_HASH_COUNT), 0u);
  EXPECT_EQ(sb_flat_hash_count(1, SB_FLAT_HASH_COUNT), 0u);
}
#endif

namespace {
struct FlatEraseMarker {};
struct FlatEraseHooks {
  std::string trace;
  std::function<void()> beforeAssign;
  FlatEraseMarker* marker = nullptr;
  int failure = 0, throwCompare = 0, comparisons = 0;
  int live = 0, copies = 0, moves = 0, proxies = 0;
  void event(char kind, int key) { trace += kind + std::to_string(key) + ";"; }
  void fail() {
    try { throw FlatEraseMarker{}; }
    catch (FlatEraseMarker& original) { marker = &original; throw; }
  }
  void emit(char const* label) const {
    std::printf("FLAT_ERASE_TRACE %s %s\n", label, trace.c_str());
  }
};
struct FlatEraseValue {
  int key;
  FlatEraseHooks* hooks;
  FlatEraseValue(int k, FlatEraseHooks* h) : key(k), hooks(h) { ++hooks->live; hooks->event('N', key); }
  FlatEraseValue(FlatEraseValue const& v) : key(v.key), hooks(v.hooks) {
    ++hooks->live; ++hooks->copies; hooks->event('C', key);
  }
  FlatEraseValue(FlatEraseValue&& v) : key(v.key), hooks(v.hooks) {
    ++hooks->live; ++hooks->moves; hooks->event('M', key);
  }
  FlatEraseValue& operator=(FlatEraseValue const& v) {
    key = v.key; ++hooks->copies; hooks->event('c', key); return *this;
  }
  FlatEraseValue& operator=(FlatEraseValue&& v) {
    hooks->event('A', v.key);
    if (hooks->beforeAssign) hooks->beforeAssign();
    if (hooks->failure == 1) hooks->fail();
    key = v.key;
    if (hooks->failure == 2) hooks->fail();
    return *this;
  }
  ~FlatEraseValue() { --hooks->live; hooks->event('D', key); }
};
struct FlatEraseContextBool {
  bool different;
  FlatEraseHooks* hooks;
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  uint64_t scans = sb_flat_hash_count(0, SB_FLAT_HASH_SCAN);
#endif
  FlatEraseContextBool(bool d, FlatEraseHooks* h) : different(d), hooks(h) { ++hooks->proxies; }
  FlatEraseContextBool(FlatEraseContextBool const&) = delete;
  explicit operator bool() const { hooks->event('B', different); return different; }
  ~FlatEraseContextBool() {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
    EXPECT_EQ(sb_flat_hash_count(0, SB_FLAT_HASH_SCAN), scans); // No ++i/++j before proxy destruction.
#endif
    --hooks->proxies; hooks->event('P', different);
  }
};
FlatEraseContextBool operator!=(FlatEraseValue const& a, FlatEraseValue const& b) {
  auto& h = *a.hooks;
  EXPECT_EQ(h.proxies, 0); // The preceding full expression must already have ended.
  h.event('q', a.key); h.event('r', b.key);
  if (++h.comparisons == h.throwCompare) h.fail();
  return FlatEraseContextBool(a.key != b.key, &h);
}
struct FlatEraseGetKey {
  int const& operator()(FlatEraseValue const& value) const { return value.key; }
};
struct FlatEraseHash {
  int mode = 0;
  size_t operator()(int key) const {
    return mode == 1 ? 0 : mode == 2 ? std::numeric_limits<size_t>::max() - 1 : size_t(key);
  }
};
using FlatEraseTable = FlatHashTable<FlatEraseValue, int, FlatEraseGetKey,
    FlatEraseHash, std::equal_to<int>, std::allocator<FlatEraseValue>>;
}

TEST(FlatHashErase, ShiftHomeStopAndWrappedReturn) {
  FlatEraseHooks h;
  {
    FlatEraseTable table(3, {}, {}, {}, {});
    for (int key : {0, 8, 16, 24}) table.insert(FlatEraseValue(key, &h));
    h.emit("shift-seed");
    auto base = table.begin().current;
    ASSERT_EQ(table.end().current - base, 8);
    auto victim = table.find(8);
    ASSERT_EQ(victim.current - base, 1);
    h.trace.clear();
    auto next = table.erase(victim);
    ASSERT_NE(next, table.end());
    EXPECT_EQ(next.current, base + 1); EXPECT_EQ(next->key, 16);
    EXPECT_EQ(table.size(), 3u); EXPECT_EQ(h.live, 3);
    EXPECT_EQ(h.trace, "A16;A24;D24;"); h.emit("shift");
    EXPECT_EQ(table.find(8), table.end());
    EXPECT_NE(table.find(0), table.end()); EXPECT_NE(table.find(24), table.end());
    h.trace.clear();
    auto rootNext = table.erase(table.begin());
    ASSERT_NE(rootNext, table.end());
    EXPECT_EQ(rootNext.current, base); EXPECT_EQ(rootNext->key, 16);
    EXPECT_EQ(table.size(), 2u); EXPECT_NE(table.find(24), table.end());
    EXPECT_EQ(h.trace, "A16;A24;D24;"); h.emit("root-shift");
    h.trace.clear(); table.clear(); h.emit("shift-cleanup");
    for (int key : {0, 1}) table.insert(FlatEraseValue(key, &h));
    h.trace.clear();
    auto home = table.erase(table.begin());
    ASSERT_NE(home, table.end());
    EXPECT_EQ(home->key, 1); EXPECT_EQ(h.trace, "D0;"); h.emit("home-stop");
    h.trace.clear(); table.clear(); h.emit("home-cleanup");
  }
  EXPECT_EQ(h.live, 0);
  {
    FlatEraseTable table(3, {}, FlatEraseHash{2}, {}, {});
    h.trace.clear();
    for (int key : {1, 2, 3}) table.insert(FlatEraseValue(key, &h));
    h.emit("wrap-seed");
    auto victim = table.find(1);
    auto source = table.find(2);
    ASSERT_EQ(source.current - victim.current, 1);
    h.trace.clear();
    auto next = table.erase(victim);
    ASSERT_NE(next, table.end());
    EXPECT_EQ(next.current, victim.current); EXPECT_EQ(next->key, 2);
    EXPECT_EQ(source->key, 3); // Old source slot now contains the following value.
    EXPECT_EQ(table.size(), 2u); EXPECT_EQ(h.trace, "A2;A3;D3;"); h.emit("wrap");
    EXPECT_NE(table.find(2), table.end()); EXPECT_NE(table.find(3), table.end());
    h.trace.clear(); table.clear(); h.emit("wrap-cleanup");
  }
  EXPECT_EQ(h.live, 0);
}

TEST(FlatHashErase, AssignmentFailurePreservesNativeHashAndLiveObjects) {
  for (int stage : {1, 2}) {
    FlatEraseHooks h;
    FlatEraseTable table(3, {}, {}, {}, {});
    for (int key : {0, 8, 2}) table.insert(FlatEraseValue(key, &h));
    h.emit("failure-seed");
    auto victim = table.begin();
    auto source = table.find(8);
    auto tail = table.find(2);
    h.beforeAssign = [&] {
      EXPECT_EQ(victim.current->hash, size_t(8) | (size_t(1) << (sizeof(size_t) * 8 - 1)));
      EXPECT_EQ(victim->key, 0); EXPECT_EQ(source->key, 8);
      EXPECT_EQ(table.size(), 3u); EXPECT_EQ(h.live, 3);
    };
    h.failure = stage; h.trace.clear();
    bool caught = false;
    try { table.erase(victim); }
    catch (FlatEraseMarker& original) { caught = true; EXPECT_EQ(&original, h.marker); }
    h.failure = 0; h.beforeAssign = {};
    EXPECT_TRUE(caught); EXPECT_EQ(table.size(), 3u); EXPECT_EQ(h.live, 3);
    EXPECT_EQ(victim->key, stage == 1 ? 0 : 8);
    EXPECT_EQ(source->key, 8); EXPECT_EQ(tail->key, 2);
    EXPECT_EQ(h.trace, "A8;"); h.event('F', stage); h.emit("assignment-throw");
    // Both duplicate-key objects remain live; do not find/repair the corrupted table.
    h.trace.clear(); table.clear();
    EXPECT_EQ(h.live, 0); EXPECT_EQ(table.size(), 0u);
    EXPECT_EQ(h.trace, stage == 1 ? "D0;D8;D2;" : "D8;D8;D2;"); h.emit("failure-clear");
  }
}

TEST(FlatHashErase, RangePhysicalBoundaryAndClearOrder) {
  FlatEraseHooks h;
  FlatEraseTable table(3, {}, {}, {}, {});
  for (int key : {0, 1, 2, 3}) table.insert(FlatEraseValue(key, &h));
  auto first = table.begin(); auto last = table.find(2);
  h.trace.clear();
  auto next = table.erase(first, last);
  EXPECT_EQ(next, last); EXPECT_EQ(next->key, 2); EXPECT_EQ(table.size(), 2u);
  EXPECT_EQ(h.trace, "D0;D1;"); h.emit("range-subset");
  auto empty = table.erase(next, next); EXPECT_EQ(empty, next);
  h.trace.clear();
  EXPECT_EQ(table.erase(table.begin(), table.end()), table.end());
  EXPECT_EQ(h.trace, "D2;D3;"); h.emit("range-whole");
  FlatEraseTable wrapped(3, {}, FlatEraseHash{2}, {}, {});
  for (int key : {1, 2, 3}) wrapped.insert(FlatEraseValue(key, &h));
  int copies = h.copies, moves = h.moves;
  h.trace.clear(); wrapped.clear();
  EXPECT_EQ(h.trace, "D3;D1;D2;"); h.emit("clear-order");
  EXPECT_EQ(h.copies, copies); EXPECT_EQ(h.moves, moves); EXPECT_EQ(h.live, 0);
  EXPECT_EQ(wrapped.begin(), wrapped.end());
  h.trace.clear(); wrapped.clear(); EXPECT_TRUE(h.trace.empty());
  wrapped.insert(FlatEraseValue(4, &h)); EXPECT_EQ(wrapped.begin()->key, 4);
}

TEST(FlatHashErase, EqualityIsOrderedAndProxyExpressionsFinish) {
  FlatEraseHooks h;
  FlatEraseTable a(3, {}, FlatEraseHash{1}, {}, {}), b(3, {}, FlatEraseHash{1}, {}, {});
  for (int key : {1, 2}) a.insert(FlatEraseValue(key, &h));
  for (int key : {2, 1}) b.insert(FlatEraseValue(key, &h));
  h.trace.clear(); EXPECT_FALSE(a == b);
  EXPECT_EQ(h.trace, "q1;r2;B1;P1;"); h.emit("ordered-unequal");
  h.trace.clear(); auto copy = a; h.emit("equality-copy");
  int copies = h.copies, moves = h.moves;
  h.trace.clear(); h.comparisons = 0;
  EXPECT_TRUE(a == copy);
  EXPECT_EQ(h.trace, "q1;r1;B0;P0;q2;r2;B0;P0;"); h.emit("copy-equal");
  h.trace.clear(); h.comparisons = 0; h.throwCompare = 2;
  bool caught = false;
  try { (void)(a == copy); }
  catch (FlatEraseMarker& original) { caught = true; EXPECT_EQ(&original, h.marker); }
  h.throwCompare = 0;
  EXPECT_TRUE(caught); EXPECT_EQ(h.comparisons, 2); EXPECT_EQ(h.proxies, 0);
  EXPECT_EQ(h.trace, "q1;r1;B0;P0;q2;r2;"); h.emit("compare-throw");
  EXPECT_EQ(h.copies, copies); EXPECT_EQ(h.moves, moves);
  b.erase(b.begin()); h.trace.clear();
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  auto scans = sb_flat_hash_count(0, SB_FLAT_HASH_SCAN);
#endif
  EXPECT_FALSE(a == b); EXPECT_TRUE(h.trace.empty());
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  EXPECT_EQ(sb_flat_hash_count(0, SB_FLAT_HASH_SCAN), scans);
#endif
}

TEST(FlatHashErase, PublicMapAndSetMutationAndEquality) {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  uint64_t before[2][5];
  for (uint32_t kind = 0; kind != 2; ++kind)
    for (uint32_t mode = 3; mode != 8; ++mode) before[kind][mode - 3] = sb_flat_hash_count(kind, mode);
#endif
  FlatHashMap<int, int, FlatEraseHash> map(3, FlatEraseHash{1});
  FlatHashSet<int, FlatEraseHash> set(3, FlatEraseHash{1});
  for (int key : {1, 2, 3}) { map.insert({key, key * 17}); set.insert(key); }
  auto mapCopy = map; auto setCopy = set;
  EXPECT_TRUE(map == mapCopy); EXPECT_TRUE(set == setCopy);
  auto mi = map.erase(map.begin()); auto si = set.erase(set.begin());
  ASSERT_NE(mi, map.end()); ASSERT_NE(si, set.end());
  EXPECT_EQ(mi->first, 2); EXPECT_EQ(mi->second, 34); EXPECT_EQ(*si, 2);
  EXPECT_EQ(map.erase(mi, map.end()), map.end()); EXPECT_EQ(set.erase(si, set.end()), set.end());
  EXPECT_TRUE(map.empty()); EXPECT_TRUE(set.empty());
  EXPECT_FALSE(map == mapCopy); EXPECT_FALSE(set == setCopy);
  mapCopy.clear(); setCopy.clear();
  EXPECT_TRUE(map == mapCopy); EXPECT_TRUE(set == setCopy);
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  for (uint32_t kind = 0; kind != 2; ++kind)
    for (uint32_t mode = 3; mode != 8; ++mode)
      EXPECT_GT(sb_flat_hash_count(kind, mode), before[kind][mode - 3]);
#endif
}

namespace {
struct FlatGrowMarker : std::bad_alloc {};
struct FlatGrowHooks {
  std::string trace;
  FlatGrowMarker* marker = nullptr;
  bool armed = true, failAllocation = false, failMove = false;
  int failHash = -1, liveValues = 0, liveTemps = 0, buffers = 0;
  int copies = 0, moves = 0, hashes = 0, allocatorCtors = 0, allocations = 0;
  size_t allocatedBuckets = 0;
  void event(char kind, int key) { trace += kind + std::to_string(key) + ";"; }
  [[noreturn]] void fail() {
    try { throw FlatGrowMarker{}; }
    catch (FlatGrowMarker& original) { marker = &original; throw; }
  }
  void emit(char const* label) const {
    std::printf("FLAT_GROW_TRACE %s %s live=%d temps=%d buffers=%d copies=%d moves=%d hashes=%d\n",
        label, trace.c_str(), liveValues, liveTemps, buffers, copies, moves, hashes);
  }
};
// One identity for every allocator rebind, including the private Bucket type.
FlatGrowHooks* flatGrowHooks = nullptr;
struct FlatGrowArm {
  FlatGrowHooks* previous;
  explicit FlatGrowArm(FlatGrowHooks& h) : previous(flatGrowHooks) { flatGrowHooks = &h; }
  ~FlatGrowArm() { flatGrowHooks = previous; }
};
template <typename T>
struct FlatGrowAllocator {
  using value_type = T;
  using is_always_equal = std::true_type;
  template <typename U> struct rebind { using other = FlatGrowAllocator<U>; };
  FlatGrowAllocator() noexcept {
    if (flatGrowHooks && flatGrowHooks->armed) {
      ++flatGrowHooks->allocatorCtors; flatGrowHooks->event('a', 0);
    }
  }
  template <typename U> FlatGrowAllocator(FlatGrowAllocator<U> const&) noexcept {}
  T* allocate(size_t count) {
    auto& h = *flatGrowHooks;
    h.event('A', int(count));
    if (h.failAllocation) { h.failAllocation = false; h.fail(); }
    T* result = std::allocator<T>{}.allocate(count);
    ++h.buffers; ++h.allocations; h.allocatedBuckets = count;
    return result;
  }
  void deallocate(T* storage, size_t count) noexcept {
    auto& h = *flatGrowHooks;
    h.event('Z', int(count)); --h.buffers;
    std::allocator<T>{}.deallocate(storage, count);
  }
};
template <typename T, typename U>
bool operator==(FlatGrowAllocator<T> const&, FlatGrowAllocator<U> const&) { return true; }
template <typename T, typename U>
bool operator!=(FlatGrowAllocator<T> const&, FlatGrowAllocator<U> const&) { return false; }
struct FlatGrowValue {
  int key, payload;
  FlatGrowHooks* hooks;
  FlatGrowValue(int k, FlatGrowHooks* h) : key(k), payload(k * 17), hooks(h) {
    EXPECT_EQ(hooks, flatGrowHooks); ++hooks->liveValues; hooks->event('N', key);
  }
  FlatGrowValue(FlatGrowValue const& v) : key(v.key), payload(v.payload), hooks(v.hooks) {
    ++hooks->copies; ++hooks->liveValues; hooks->event('C', key);
  }
  FlatGrowValue(FlatGrowValue&& v) : key(v.key), payload(v.payload), hooks(v.hooks) {
    EXPECT_EQ(hooks, flatGrowHooks); ++hooks->moves; hooks->event('M', key);
    // Observe moved-from old buckets and parameters, including a failed move.
    v.key = -v.key - 1; v.payload = -1;
    if (hooks->failMove) { hooks->failMove = false; hooks->fail(); }
    ++hooks->liveValues;
  }
  FlatGrowValue& operator=(FlatGrowValue const& v) {
    key = v.key; payload = v.payload; ++hooks->copies; hooks->event('c', key); return *this;
  }
  FlatGrowValue& operator=(FlatGrowValue&& v) {
    key = v.key; payload = v.payload; ++hooks->moves; hooks->event('m', key);
    v.key = -v.key - 1; v.payload = -1; return *this;
  }
  ~FlatGrowValue() noexcept {
    EXPECT_EQ(hooks, flatGrowHooks); --hooks->liveValues;
    hooks->event('D', key); hooks->event('p', payload);
  }
};
struct FlatGrowTemp {
  int const* key;
  FlatGrowHooks* hooks;
  FlatGrowTemp(int const& k, FlatGrowHooks* h) : key(&k), hooks(h) {
    ++hooks->liveTemps; hooks->event('+', *key);
  }
  FlatGrowTemp(FlatGrowTemp const&) = delete;
  ~FlatGrowTemp() noexcept { hooks->event('-', *key); --hooks->liveTemps; }
  operator int const&() const { EXPECT_GT(hooks->liveTemps, 0); return *key; }
};
struct FlatGrowGetKey {
  FlatGrowHooks* hooks;
  FlatGrowTemp operator()(FlatGrowValue const& v) const {
    EXPECT_EQ(v.hooks, hooks); EXPECT_EQ(hooks, flatGrowHooks);
    hooks->event('g', v.key); return FlatGrowTemp(v.key, hooks);
  }
};
struct FlatGrowHash {
  FlatGrowHooks* hooks;
  size_t operator()(int key) const {
    EXPECT_EQ(hooks, flatGrowHooks); EXPECT_EQ(hooks->liveTemps, 1);
    ++hooks->hashes; hooks->event('h', key);
    if (key == hooks->failHash) hooks->fail();
    return size_t(key);
  }
};
using FlatGrowTable = FlatHashTable<FlatGrowValue, int, FlatGrowGetKey,
    FlatGrowHash, std::equal_to<int>, FlatGrowAllocator<FlatGrowValue>>;
}

TEST(FlatHashGrow, ZeroAndNativeLoadThresholds) {
  size_t const requests[] = {0, 1, 5, 6, 8, 11, 12, 22};
  size_t const buckets[] = {0, 9, 9, 17, 17, 17, 33, 33};
  for (bool constructor : {false, true}) {
    for (size_t i = 0; i != 8; ++i) {
      FlatGrowHooks h;
      FlatGrowArm arm(h);
      {
        FlatGrowTable table(constructor ? requests[i] : 0, FlatGrowGetKey{&h},
            FlatGrowHash{&h}, {}, {});
        if (!constructor) table.reserve(requests[i]);
        EXPECT_EQ(h.allocatedBuckets, buckets[i]);
        EXPECT_EQ(h.allocations, requests[i] ? 1 : 0);
        EXPECT_EQ(h.buffers, requests[i] ? 1 : 0);
        EXPECT_EQ(h.hashes, 0); EXPECT_EQ(h.moves, 0); EXPECT_EQ(h.copies, 0);
        EXPECT_EQ(table.size(), 0u); EXPECT_EQ(table.begin(), table.end());
        auto const& view = table;
        EXPECT_EQ(view.begin(), view.end());
        h.event('r', int(requests[i])); h.emit(constructor ? "ctor-threshold" : "reserve-threshold");
        h.trace.clear();
      }
      EXPECT_EQ(h.liveValues, 0); EXPECT_EQ(h.liveTemps, 0); EXPECT_EQ(h.buffers, 0);
      h.emit("threshold-cleanup");
    }
  }
}

TEST(FlatHashGrow, NoGrowthSkipsOldAllocatorAndReinsertPreservesFields) {
  FlatGrowHooks h;
  FlatGrowArm arm(h);
  {
    FlatGrowTable table(3, FlatGrowGetKey{&h}, FlatGrowHash{&h}, {}, {});
    for (int key : {0, 8, 16}) table.insert(FlatGrowValue(key, &h));
    EXPECT_EQ(h.liveValues, 3);
    int ctors = h.allocatorCtors, allocations = h.allocations;
    int hashes = h.hashes, moves = h.moves, copies = h.copies;
    h.trace.clear();
    for (size_t request : {0u, 1u, 3u, 4u, 5u}) table.reserve(request);
    EXPECT_TRUE(h.trace.empty()); EXPECT_EQ(h.allocatorCtors, ctors);
    EXPECT_EQ(h.allocations, allocations); EXPECT_EQ(h.hashes, hashes);
    EXPECT_EQ(h.moves, moves); EXPECT_EQ(h.copies, copies);
    h.emit("no-growth");
    table.reserve(6);
    EXPECT_EQ(h.allocatorCtors, ctors + 1); EXPECT_EQ(h.allocations, allocations + 1);
    EXPECT_EQ(h.allocatedBuckets, 17u); EXPECT_EQ(h.buffers, 1);
    EXPECT_EQ(h.liveValues, 3); EXPECT_EQ(h.liveTemps, 0);
    EXPECT_EQ(h.hashes, hashes + 3); EXPECT_EQ(h.copies, copies);
    EXPECT_GT(h.moves, moves); EXPECT_EQ(table.size(), 3u);
    h.emit("reserve-reinsert"); h.trace.clear();
    std::set<int> actual;
    for (auto const& value : table) {
      EXPECT_EQ(value.hooks, &h); EXPECT_EQ(value.payload, value.key * 17);
      actual.insert(value.key);
    }
    EXPECT_EQ(actual, (std::set<int>{0, 8, 16}));
    EXPECT_EQ(table.begin()->key, 0);
    auto const& view = table;
    EXPECT_EQ(view.begin()->payload, 0);
    EXPECT_TRUE(h.trace.empty());
  }
  EXPECT_EQ(h.buffers, 0); EXPECT_EQ(h.liveValues, 0); EXPECT_EQ(h.liveTemps, 0);
  h.emit("reinsert-cleanup");
}

TEST(FlatHashGrow, SixthInsertGrowsAndKeepsCopiedCaller) {
  FlatGrowHooks h;
  FlatGrowArm arm(h);
  {
    FlatGrowTable table(0, FlatGrowGetKey{&h}, FlatGrowHash{&h}, {}, {});
    for (int key : {0, 8, 16, 24, 32}) table.insert(FlatGrowValue(key, &h));
    EXPECT_EQ(h.allocatedBuckets, 9u); EXPECT_EQ(h.liveValues, 5);
    int ctors = h.allocatorCtors, allocations = h.allocations;
    int copies = h.copies, hashes = h.hashes;
    h.trace.clear();
    {
      FlatGrowValue caller(40, &h);
      auto added = table.insert(caller);
      ASSERT_TRUE(added.second); EXPECT_EQ(added.first->key, 40);
      EXPECT_EQ(added.first->payload, 680);
      EXPECT_EQ(caller.key, 40); EXPECT_EQ(caller.payload, 680);
      EXPECT_EQ(h.liveValues, 7); EXPECT_EQ(h.copies, copies + 1);
      EXPECT_EQ(h.hashes, hashes + 6); EXPECT_EQ(h.liveTemps, 0);
      EXPECT_EQ(h.allocatorCtors, ctors + 1); EXPECT_EQ(h.allocations, allocations + 1);
      EXPECT_EQ(h.allocatedBuckets, 17u); EXPECT_EQ(h.buffers, 1);
      EXPECT_EQ(table.size(), 6u);
      std::set<int> actual;
      for (auto const& value : table) {
        actual.insert(value.key); EXPECT_EQ(value.payload, value.key * 17);
      }
      EXPECT_EQ(actual, (std::set<int>{0, 8, 16, 24, 32, 40}));
      h.emit("sixth-insert"); h.trace.clear();
    }
    EXPECT_EQ(h.liveValues, 6); h.emit("copied-caller-cleanup"); h.trace.clear();
  }
  EXPECT_EQ(h.liveValues, 0); EXPECT_EQ(h.buffers, 0); h.emit("sixth-insert-cleanup");
}

TEST(FlatHashGrow, AllocationFailureKeepsNativeStaleSizeWithoutRollback) {
  FlatGrowHooks h;
  FlatGrowArm arm(h);
  {
    FlatGrowTable table(3, FlatGrowGetKey{&h}, FlatGrowHash{&h}, {}, {});
    for (int key : {0, 8, 16}) table.insert(FlatGrowValue(key, &h));
    h.trace.clear(); h.failAllocation = true;
    bool caught = false;
    try { table.reserve(6); }
    catch (FlatGrowMarker& original) { caught = true; EXPECT_EQ(&original, h.marker); }
    EXPECT_TRUE(caught); EXPECT_FALSE(h.failAllocation);
    EXPECT_EQ(table.size(), 3u); // Reset was never reached after storage swap.
    EXPECT_EQ(h.liveValues, 0); EXPECT_EQ(h.liveTemps, 0); EXPECT_EQ(h.buffers, 0);
    h.emit("allocation-throw"); h.trace.clear();
    // Do not iterate/find/clear the stale-size table. Its empty vector is safe to destroy.
  }
  EXPECT_EQ(h.liveValues, 0); EXPECT_EQ(h.buffers, 0);
  EXPECT_TRUE(h.trace.empty()); h.emit("allocation-cleanup");
}

TEST(FlatHashGrow, HashFailureRetainsOnlySuccessfulReinsertPrefix) {
  FlatGrowHooks h;
  FlatGrowArm arm(h);
  {
    FlatGrowTable table(3, FlatGrowGetKey{&h}, FlatGrowHash{&h}, {}, {});
    for (int key : {0, 8, 16}) table.insert(FlatGrowValue(key, &h));
    h.trace.clear(); h.failHash = 8;
    bool caught = false;
    try { table.reserve(6); }
    catch (FlatGrowMarker& original) { caught = true; EXPECT_EQ(&original, h.marker); }
    h.failHash = -1;
    EXPECT_TRUE(caught); EXPECT_EQ(table.size(), 1u);
    EXPECT_EQ(h.liveValues, 1); EXPECT_EQ(h.liveTemps, 0); EXPECT_EQ(h.buffers, 1);
    EXPECT_EQ(h.allocatedBuckets, 17u);
    h.emit("hash-prefix-throw"); h.trace.clear();
    auto first = table.begin(); ASSERT_NE(first, table.end());
    EXPECT_EQ(first->key, 0); EXPECT_EQ(first->payload, 0); EXPECT_EQ(first->hooks, &h);
    EXPECT_EQ(++first, table.end());
    // Inspect public values, avoiding a raw-key find that would not create a GetKey temporary.
  }
  EXPECT_EQ(h.liveValues, 0); EXPECT_EQ(h.liveTemps, 0); EXPECT_EQ(h.buffers, 0);
  h.emit("hash-prefix-cleanup");
}

TEST(FlatHashGrow, FirstOldValueMoveFailureNeverConstructsInsertParameter) {
  FlatGrowHooks h;
  FlatGrowArm arm(h);
  {
    FlatGrowTable table(3, FlatGrowGetKey{&h}, FlatGrowHash{&h}, {}, {});
    for (int key : {0, 8, 16}) table.insert(FlatGrowValue(key, &h));
    int hashes = h.hashes, moves = h.moves, copies = h.copies;
    h.trace.clear(); h.failMove = true;
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
    auto inserts = sb_flat_hash_count(0, SB_FLAT_HASH_INSERT);
#endif
    bool caught = false;
    try { table.reserve(6); }
    catch (FlatGrowMarker& original) { caught = true; EXPECT_EQ(&original, h.marker); }
    EXPECT_TRUE(caught); EXPECT_FALSE(h.failMove);
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
    EXPECT_EQ(sb_flat_hash_count(0, SB_FLAT_HASH_INSERT), inserts);
#endif
    EXPECT_EQ(h.hashes, hashes); EXPECT_EQ(h.moves, moves + 1); EXPECT_EQ(h.copies, copies);
    EXPECT_EQ(table.size(), 0u); EXPECT_EQ(h.liveValues, 0); EXPECT_EQ(h.liveTemps, 0);
    EXPECT_EQ(h.buffers, 1); EXPECT_EQ(h.allocatedBuckets, 17u);
    EXPECT_EQ(table.begin(), table.end());
    h.emit("first-move-throw"); h.trace.clear();
  }
  EXPECT_EQ(h.liveValues, 0); EXPECT_EQ(h.buffers, 0); h.emit("first-move-cleanup");
}

#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
TEST(FlatHashGrow, PublicGrowthDiagnostics) {
  uint64_t before[2][5];
  for (uint32_t kind = 0; kind != 2; ++kind)
    for (uint32_t mode = 8; mode != 13; ++mode) before[kind][mode - 8] = sb_flat_hash_count(kind, mode);
  FlatHashMap<int, int> map(0);
  EXPECT_EQ(map.begin(), map.end());
  map.reserve(0); map.reserve(5);
  for (int key = 0; key != 6; ++key) map.insert({key, key * 17});
  map.reserve(22);
  auto const& view = map;
  ASSERT_NE(view.begin(), view.end());
  for (auto const& value : view) EXPECT_EQ(value.second, value.first * 17);
  for (uint32_t kind = 0; kind != 2; ++kind)
    for (uint32_t mode = 8; mode != 13; ++mode)
      EXPECT_GT(sb_flat_hash_count(kind, mode), before[kind][mode - 8]);
  EXPECT_EQ(SB_FLAT_HASH_RESERVE, 8); EXPECT_EQ(SB_FLAT_HASH_GROW_PLAN, 9);
  EXPECT_EQ(SB_FLAT_HASH_GROW_WORK, 10); EXPECT_EQ(SB_FLAT_HASH_REINSERT, 11);
  EXPECT_EQ(SB_FLAT_HASH_BEGIN, 12); EXPECT_EQ(SB_FLAT_HASH_COUNT, 13);
}
#endif
