#include "StarMap.hpp"
#include "StarNetElementGroup.hpp"
#include "StarAllocationProbe.hpp"
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarNetGroupCountCache.hpp"
#endif
#ifdef STAR_NET_GROUP_RUST_COUNT_CACHE
#include "StarRustNetGroupCountCache.h"
#endif
#include "gtest/gtest.h"

#include <array>
#include <cstdint>
#include <iostream>
#include <new>

namespace {
using namespace Star;
// OFF deliberately exercises the real native map, not a model of its buckets.
class FixtureFacade {
public:
  void inc(uint32_t key) {
#ifdef STAR_NET_GROUP_RUST_COUNT_CACHE
    cache.increment(key);
#else
    cache[key]++;
#endif
  }
  Maybe<size_t> maybe(uint32_t key) const { return cache.maybe(key); }
  void clear() { cache.clear(); }
  size_t size() const { return cache.size(); }
private:
#ifdef STAR_NET_GROUP_RUST_COUNT_CACHE
  NetGroupCountCache cache;
#else
  HashMap<VersionNumber, size_t> cache;
#endif
};
struct Digest {
  uint64_t value = UINT64_C(14695981039346656037);
  void add(uint64_t word) {
    for (unsigned i = 0; i != 8; ++i) {
      value ^= (word >> (8 * i)) & 255;
      value *= UINT64_C(1099511628211);
    }
  }
  void emit(char const* name) const {
    std::cout << "NET_GROUP_COUNT_CACHE_TRACE " << name << ' ' << value << '\n';
  }
};
size_t eagerFallback(unsigned& calls) { ++calls; return 73; }
}

TEST(NetGroupCountCache, DefaultMissingAndEagerValueFallback) {
  FixtureFacade cache;
  EXPECT_EQ(cache.size(), 0u);
  EXPECT_FALSE(cache.maybe(0)); EXPECT_FALSE(cache.maybe(UINT32_MAX));
  unsigned calls = 0;
  EXPECT_EQ(cache.maybe(9).value(eagerFallback(calls)), 73u);
  cache.inc(9);
  EXPECT_EQ(cache.maybe(9).value(eagerFallback(calls)), 1u);
  EXPECT_EQ(calls, 2u);
  Digest d; d.add(cache.size()); d.add(calls); d.add(cache.maybe(9).value(0));
  d.emit("default-missing-eager-value");
}

TEST(NetGroupCountCache, AllVersionKeysRepeatedAndFullWidthKeys) {
  FixtureFacade cache;
  Digest d;
  for (uint32_t key = 0; key != 22; ++key)
    for (uint32_t n = 0; n <= key; ++n) cache.inc(key);
  std::array<uint32_t, 4> edges{{UINT32_MAX, UINT32_C(0x80000000), UINT32_MAX - 1, 65536}};
  for (auto key : edges) { cache.inc(key); cache.inc(key); }
  EXPECT_EQ(cache.size(), 26u);
  for (uint32_t key = 0; key != 22; ++key) {
    EXPECT_EQ(cache.maybe(key).value(0), size_t(key + 1));
    d.add(key); d.add(cache.maybe(key).value(0));
  }
  for (auto key : edges) { EXPECT_EQ(cache.maybe(key).value(0), 2u); d.add(key); d.add(cache.maybe(key).value(0)); }
  EXPECT_FALSE(cache.maybe(22)); EXPECT_FALSE(cache.maybe(65537));
  d.add(cache.size()); d.emit("versions-and-fullwidth-keys");
}

TEST(NetGroupCountCache, CollisionsWraparoundAndMissingProbe) {
  FixtureFacade cache;
  // The low bits collide with native integer hash; the last bucket also wraps.
  for (uint32_t i = 0; i != 80; ++i) cache.inc(i * 256 + 255);
  for (uint32_t i = 80; i != 0; --i) cache.inc((i - 1) * 256 + 255);
  Digest d;
  EXPECT_EQ(cache.size(), 80u);
  for (uint32_t i = 0; i != 80; ++i) {
    auto key = i * 256 + 255;
    EXPECT_EQ(cache.maybe(key).value(0), 2u);
    EXPECT_FALSE(cache.maybe(key - 1));
    d.add(key); d.add(cache.maybe(key).value(0));
  }
  EXPECT_FALSE(cache.maybe(80 * 256 + 255));
  d.emit("collisions-and-wraparound");
}

TEST(NetGroupCountCache, HundredThousandMixedOperationsFullCountOracle) {
  FixtureFacade cache;
  std::array<size_t, 512> expected{};
  size_t present = 0;
  uint32_t random = UINT32_C(0x6d2b79f5);
  Digest d;
  for (unsigned step = 0; step != 100000; ++step) {
    random = random * UINT32_C(1664525) + UINT32_C(1013904223);
    unsigned key = (random >> 12) & 511;
    if (step && step % 17011 == 0) {
      cache.clear(); expected.fill(0); present = 0;
    } else if ((random & 7) < 5) {
      if (!expected[key]) ++present;
      ++expected[key]; cache.inc(key);
    } else {
      auto value = cache.maybe(key);
      EXPECT_EQ(bool(value), expected[key] != 0) << step;
      EXPECT_EQ(value.value(0), expected[key]) << step;
      d.add(key); d.add(value.value(0));
    }
    EXPECT_EQ(cache.size(), present) << step;
    d.add(cache.size());
  }
  for (unsigned key = 0; key != expected.size(); ++key) {
    EXPECT_EQ(cache.maybe(key).value(0), expected[key]);
    d.add(key); d.add(expected[key]);
  }
  d.emit("100000-mixed-full-counts");
}

TEST(NetGroupCountCache, ClearMissingAndRefillCountsRestartAtOne) {
  FixtureFacade cache;
  for (uint32_t key = 0; key != 22; ++key) { cache.inc(key); cache.inc(key); }
  cache.clear(); cache.clear();
  EXPECT_EQ(cache.size(), 0u);
  for (uint32_t key = 0; key != 22; ++key) EXPECT_FALSE(cache.maybe(key));
  for (uint32_t key = 22; key != 0; --key) cache.inc(key - 1);
  Digest d;
  for (uint32_t key = 0; key != 22; ++key) {
    EXPECT_EQ(cache.maybe(key).value(0), 1u); d.add(cache.maybe(key).value(0));
  }
  d.add(cache.size()); d.emit("clear-and-reverse-refill");
}

namespace {
struct CountChild : NetElement {
  uint8_t byte = 0;
  mutable unsigned writes = 0;
  unsigned initializations = 0;
  unsigned enables = 0;
  void initNetVersion(NetElementVersion const*) override { ++initializations; }
  void enableNetInterpolation(float) override { ++enables; }
  void netStore(DataStream& stream, NetCompatibilityRules) const override { stream.write(byte); }
  void netLoad(DataStream& stream, NetCompatibilityRules) override { byte = stream.read<uint8_t>(); }
  bool writeNetDelta(DataStream& stream, uint64_t, NetCompatibilityRules) const override {
    ++writes; stream.write(byte); return true;
  }
  void readNetDelta(DataStream& stream, float, NetCompatibilityRules) override { byte = stream.read<uint8_t>(); }
};
void expectWire(DataStreamBuffer const& stream, std::initializer_list<uint8_t> expected, Digest& digest) {
  ASSERT_EQ(stream.size(), expected.size());
  size_t offset = 0;
  for (auto byte : expected) {
    EXPECT_EQ(uint8_t(stream.ptr()[offset++]), byte); digest.add(byte);
  }
}
}
TEST(NetGroupCountCache, ParentFilteredDirectIndexedMissingVersionAndClearReuse) {
  CountChild first, second;
  first.byte = 41; second.byte = 59;
  second.setCompatibilityVersion(1);
  NetElementGroup group;
  group.addNetElement(&first); group.addNetElement(&second);
  Digest d;
  DataStreamBuffer direct, indexed, missing, reused;
  EXPECT_TRUE(group.writeNetDelta(direct, 1, NetCompatibilityRules(LegacyVersion)));
  expectWire(direct, {41}, d);
  EXPECT_TRUE(group.writeNetDelta(indexed, 1, NetCompatibilityRules(VersionNumber(1))));
  expectWire(indexed, {1, 41, 2, 59, 0}, d);
  // Outside the cached 0..CurrentStreamVersion range: use eager element size.
  EXPECT_TRUE(group.writeNetDelta(missing, 1, NetCompatibilityRules(UINT32_MAX)));
  expectWire(missing, {1, 41, 2, 59, 0}, d);
  group.clearNetElements();
  DataStreamBuffer empty;
  EXPECT_FALSE(group.writeNetDelta(empty, 1, NetCompatibilityRules(LegacyVersion)));
  EXPECT_EQ(empty.size(), 0u);
  group.addNetElement(&first);
  EXPECT_TRUE(group.writeNetDelta(reused, 1, NetCompatibilityRules(LegacyVersion)));
  expectWire(reused, {41}, d);
  EXPECT_EQ(first.writes, 4u); EXPECT_EQ(second.writes, 2u);
  d.emit("parent-filter-direct-index-fallback-clear");
}

// Reuse the one fixed-storage allocator interceptor; observers must not allocate.
#if defined(__APPLE__) && defined(_LIBCPP_VERSION) && _LIBCPP_VERSION == 220106 && !defined(STAR_USE_RPMALLOC)
namespace {
using NetGroupStorageHook::State;
struct CacheArm {
  State* previous;
  explicit CacheArm(State& state) noexcept : previous(NetGroupStorageHook::armed) { NetGroupStorageHook::armed = &state; }
  ~CacheArm() noexcept { NetGroupStorageHook::armed = previous; }
};
size_t allocations(State const& state) {
  size_t count = 0;
  for (size_t i = 0; i != state.count; ++i) count += state.events[i].allocation;
  return count;
}
void observeCache(State& state) noexcept {
  auto const& cache = *static_cast<FixtureFacade const*>(state.owner);
  ++state.observations;
  state.observedSize = cache.size();
  bool correct = !cache.maybe(5);
  for (uint32_t key = 0; key != 5; ++key) correct = correct && cache.maybe(key).value(0) == size_t(key + 1);
  state.observedFlag = correct;
}
}

TEST(NetGroupCountCache, NativeAllocationBytesDefaultExistingIncrementClearReuseAndDrop) {
  State defaults;
  { CacheArm arm(defaults); FixtureFacade cache; cache.clear(); (void)cache.size(); (void)cache.maybe(0); }
  EXPECT_EQ(defaults.count, 0u);
  State history, reuse;
  Digest d;
  {
    CacheArm arm(history);
    FixtureFacade cache;
    for (uint32_t key = 0; key != 22; ++key) cache.inc(key);
    {
      CacheArm nested(reuse);
      for (unsigned n = 0; n != 100; ++n) cache.inc(n % 22);
      cache.clear();
      for (uint32_t key = 0; key != 22; ++key) cache.inc(key);
    }
    EXPECT_EQ(cache.size(), 22u);
  }
  EXPECT_FALSE(history.overflow); EXPECT_FALSE(reuse.overflow);
  EXPECT_EQ(reuse.count, 0u);
  EXPECT_GT(allocations(history), 0u);
  EXPECT_EQ(history.count, 2 * allocations(history));
  // Emit actual OFF allocation observations before selecting any byte golden.
  std::cout << "NET_GROUP_COUNT_CACHE_TRACE native-allocation-bytes";
  for (size_t i = 0; i != history.count; ++i) {
    auto const& event = history.events[i];
    d.add(event.allocation); d.add(event.bytes);
    if (event.allocation) {
      std::cout << ' ' << event.bytes;
      EXPECT_EQ(event.bytes % 24, 0u);
      size_t length = event.bytes / 24;
      ASSERT_GE(length, 9u);
      EXPECT_EQ((length - 1) & (length - 2), 0u);
      size_t matchingFrees = 0;
      for (size_t j = i + 1; j != history.count; ++j)
        matchingFrees += !history.events[j].allocation && history.events[j].pointer == event.pointer;
      EXPECT_EQ(matchingFrees, 1u);
    }
  }
  std::cout << '\n';
  d.emit("allocation-clear-reuse-drop");
}

TEST(NetGroupCountCache, OldFreeObserverSeesReinsertedCountsBeforeRequestedKey) {
  FixtureFacade cache;
  State initial;
  {
    CacheArm arm(initial);
    for (uint32_t key = 0; key != 5; ++key)
      for (uint32_t n = 0; n <= key; ++n) cache.inc(key);
  }
  ASSERT_EQ(allocations(initial), 1u);
  ASSERT_GT(initial.count, 0u);
  State growth;
  growth.owner = &cache; growth.watched = initial.events[0].pointer; growth.observe = observeCache;
  { CacheArm arm(growth); cache.inc(5); }
  EXPECT_EQ(growth.observations, 1u); EXPECT_EQ(growth.observedSize, 5u);
  EXPECT_TRUE(growth.observedFlag);
  EXPECT_EQ(cache.size(), 6u); EXPECT_EQ(cache.maybe(5).value(0), 1u);
  EXPECT_EQ(allocations(growth), 1u); EXPECT_EQ(growth.count, 2u);
  Digest d; d.add(growth.observations); d.add(growth.observedSize); d.add(growth.observedFlag);
  d.add(cache.size()); d.add(cache.maybe(5).value(0)); d.emit("old-free-observer-before-outer-insert");
}

TEST(NetGroupCountCache, FailedGrowthFreesOldAllocationAndRetainsStaleSizeOnly) {
  State failure, initial;
  bool caught = false, identity = false;
  size_t staleSize = 0;
  {
    CacheArm observeThroughDestructor(failure);
    FixtureFacade cache;
    { CacheArm arm(initial); for (uint32_t key = 0; key != 5; ++key) cache.inc(key); }
    failure.failAny = true;
    try { cache.inc(5); }
    catch (std::bad_alloc const& error) { caught = true; identity = &error == failure.lastRaised; }
    // Native has swapped out its buckets but has NOT reset filledCount. Never
    // find/iterate/refill this invalid failed native map. Destruction is safe.
    staleSize = cache.size();
  }
  ASSERT_EQ(allocations(initial), 1u);
  ASSERT_EQ(failure.count, 1u);
  EXPECT_FALSE(failure.events[0].allocation);
  EXPECT_EQ(failure.events[0].pointer, initial.events[0].pointer);
  EXPECT_TRUE(caught); EXPECT_TRUE(identity); EXPECT_EQ(failure.failures, 1u);
  EXPECT_EQ(staleSize, 5u); EXPECT_EQ(failure.count, 1u);
  Digest d; d.add(caught); d.add(identity); d.add(failure.failures); d.add(staleSize); d.add(failure.count);
  d.emit("failed-growth-stale-size-old-free");
}
TEST(NetGroupCountCache, ParentCacheFailureKeepsAppendedChildAndInitEnablePrefix) {
  std::array<CountChild, 3> incompatible;
  CountChild accepted;
  accepted.byte = 91;
  NetElementGroup group;
  group.enableNetInterpolation(0.5f);
  // Three rejected children prewarm the qualified vector's four-slot capacity
  // without ever allocating the count map. The fourth append fits; its FIRST
  // cache allocation then fails. Wire assertions below detect a wrong premise.
  for (auto& child : incompatible) {
    child.setCompatibilityVersion(VersionNumber(CurrentStreamVersion + 1));
    group.addNetElement(&child);
  }
  struct Operation { NetElementGroup* group; CountChild* child; } operation{&group, &accepted};
  auto result = StarTest::failNextAllocation(&operation, [](void* pointer) {
    auto& op = *static_cast<Operation*>(pointer);
    op.group->addNetElement(op.child);
  });
  EXPECT_TRUE(result.caught); EXPECT_TRUE(result.originalIdentity); EXPECT_EQ(result.failures, 1u);
  EXPECT_EQ(accepted.initializations, 1u); EXPECT_EQ(accepted.enables, 1u);
  DataStreamBuffer stored, delta;
  group.netStore(stored, NetCompatibilityRules(LegacyVersion));
  EXPECT_TRUE(group.writeNetDelta(delta, 1, NetCompatibilityRules(LegacyVersion)));
  Digest d;
  expectWire(stored, {91}, d);
  // Appended child survives. Missing cache entry falls back to FOUR slots, so
  // framing is indexed even though only one child passes these rules.
  expectWire(delta, {1, 91, 0}, d);
  d.add(result.caught); d.add(result.originalIdentity); d.add(result.failures);
  d.add(accepted.initializations); d.add(accepted.enables);
  d.emit("parent-cache-failure-append-and-init-enable-prefix");
}
#endif

#ifdef STAR_NET_GROUP_RUST_COUNT_CACHE
TEST(NetGroupCountCache, AbiInvalidModeAndKeyPreserveOutputBeforeCounting) {
  SbNetGroupCountCacheStorage storage{};
  SbNetGroupCountCacheReply out{123, 45, 67};
  auto before = sb_net_group_count_cache_count(0, 4);
  EXPECT_EQ(sb_net_group_count_cache_run(5, &storage, nullptr, 0, &out), 1u);
  EXPECT_EQ(sb_net_group_count_cache_run(4, &storage, nullptr, 1, &out), 1u);
  EXPECT_EQ(out.value, 123u); EXPECT_EQ(out.found, 45u); EXPECT_EQ(out.reserved, 67u);
  EXPECT_EQ(sb_net_group_count_cache_count(0, 4), before);
  EXPECT_EQ(sb_net_group_count_cache_run(4, &storage, nullptr, 0, &out), 0u);
  EXPECT_EQ(out.value, 0u); EXPECT_EQ(out.found, 0u); EXPECT_EQ(out.reserved, 0u);
  EXPECT_EQ(sb_net_group_count_cache_count(0, 4), before + 1);
  EXPECT_EQ(sb_net_group_count_cache_count(0, 5), 0u);
  EXPECT_EQ(sb_net_group_count_cache_count(2, 0), 0u);
  std::cout << "NET_GROUP_COUNT_CACHE_DIAGNOSTIC abi-invalid-before-count-size-ok\n";
}
#endif
