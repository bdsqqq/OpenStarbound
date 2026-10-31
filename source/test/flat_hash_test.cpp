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
