#include "StarFlatHashSet.hpp"
#include "StarFlatHashMap.hpp"
#include "StarRandom.hpp"
#include "StarVector.hpp"
#include "StarIterator.hpp"

#include "gtest/gtest.h"

#include <cstdio>
#include <functional>
#include <limits>
#include <set>
#include <string>

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
