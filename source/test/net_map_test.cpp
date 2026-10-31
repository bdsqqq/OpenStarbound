#include "StarDataStreamDevices.hpp"
#include "StarNetElementContainers.hpp"

#include "gtest/gtest.h"

#include <exception>
#include <functional>
#include <iostream>
#include <string>
#include <vector>

using namespace Star;

namespace {
using TestMap = NetElementMap<int32_t, int32_t>;

void mapSet(DataStream& ds, int32_t key, int32_t value) {
  ds.write<uint8_t>(0); ds.write(key); ds.write(value);
}
void mapRemove(DataStream& ds, int32_t key) {
  ds.write<uint8_t>(1); ds.write(key);
}
void mapClear(DataStream& ds) { ds.write<uint8_t>(2); }
void mapDeltaSet(DataStream& ds, int32_t key, int32_t value) {
  ds.writeVlqU(2); mapSet(ds, key, value);
}
template <typename M> void receiveSet(M& map, int32_t key, int32_t value, float delay) {
  DataStreamBuffer ds; mapDeltaSet(ds, key, value); ds.writeVlqU(0);
  ds.seek(0); map.readNetDelta(ds, delay); EXPECT_TRUE(ds.atEnd());
}
void mapTrace(char const* name, DataStreamBuffer const& ds) {
  static char const hex[] = "0123456789abcdef";
  std::cout << "NET_MAP_TRACE " << name << ' ';
  for (size_t i = 0; i < ds.size(); ++i) {
    auto b = static_cast<unsigned char>(ds.ptr()[i]);
    std::cout << hex[b >> 4] << hex[b & 15];
  }
  std::cout << '\n';
}
template <typename M> ByteArray mapSnapshot(M const& map) {
  DataStreamBuffer ds; map.netStore(ds); return ds.takeData();
}

struct MapMarker : std::exception {};
struct MapDerivedMarker : MapMarker {};
// Only the typed apply primitive is instrumented; storage and iteration remain
// the actual native Map implementation, including all public wrapper mutations.
struct HookMap : Map<int32_t, int32_t> {
  static std::function<void(int32_t, int32_t)> onSet;
  int32_t& set(int32_t key, int32_t value) {
    if (onSet) onSet(key, value);
    return Map<int32_t, int32_t>::set(key, value);
  }
};
std::function<void(int32_t, int32_t)> HookMap::onSet;
struct HookScope {
  HookScope() { HookMap::onSet = {}; }
  ~HookScope() { HookMap::onSet = {}; }
};
using HookNetMap = NetElementMapWrapper<HookMap>;

// Native range-for does not require iterator moves or implicit-bool comparison,
// and iterator destruction may throw before the following pending-store loop.
struct ScopedMap : Map<int32_t, int32_t> {
  using Plain = Map<int32_t, int32_t>;
  static std::vector<int> destroyed;
  static bool throwEnd;
  struct const_iterator {
    Plain::const_iterator inner;
    int tag;
    const_iterator(Plain::const_iterator i, int t) : inner(i), tag(t) {}
    const_iterator(const_iterator const&) = delete;
    const_iterator(const_iterator&&) = delete;
    ~const_iterator() noexcept(false) {
      destroyed.push_back(tag);
      if (tag == 2 && throwEnd) { throwEnd = false; throw 919; }
    }
    struct Comparison { bool value; explicit operator bool() const { return value; } };
    Comparison operator!=(const_iterator const& other) const { return {inner != other.inner}; }
    decltype(auto) operator*() const { return *inner; }
    const_iterator& operator++() { ++inner; return *this; }
  };
  Plain::iterator begin() { return Plain::begin(); }
  Plain::iterator end() { return Plain::end(); }
  const_iterator begin() const { return {Plain::begin(), 1}; }
  const_iterator end() const { return {Plain::end(), 2}; }
};
std::vector<int> ScopedMap::destroyed;
bool ScopedMap::throwEnd = false;

template <typename F> void originalMapException(std::exception_ptr error, F&& f) {
  try { f(); FAIL() << "expected original exception"; }
  catch (...) { EXPECT_EQ(std::current_exception(), error); }
}
}

TEST(NetMap, NativeImmovableIteratorContextualComparisonAndThrowingDestruction) {
  NetElementMapWrapper<ScopedMap> map;
  map.set(1, 10);
  map.enableNetInterpolation(); receiveSet(map, 2, 20, 0.5f);
  DataStreamBuffer actual, expected;
  expected.writeVlqU(2); mapSet(expected, 1, 10);
  ScopedMap::destroyed.clear(); ScopedMap::throwEnd = true;
  bool caught = false;
  try { map.netStore(actual); }
  catch (int value) { EXPECT_EQ(value, 919); caught = true; }
  EXPECT_TRUE(caught);
  EXPECT_EQ(ScopedMap::destroyed, (std::vector<int>{2, 1}));
  EXPECT_EQ(actual.data(), expected.data()); // pending change not yet emitted.
  mapTrace("iterator_destruction_prefix", actual);
  actual.clear(); map.netStore(actual);
  mapSet(expected, 2, 20);
  EXPECT_EQ(actual.data(), expected.data());
}

TEST(NetMap, StoreCountsBaseAndPendingAndWritesPendingAfterBase) {
  TestMap map; map.set(1, 10); map.set(2, 20); map.pullUpdated();
  map.enableNetInterpolation(); receiveSet(map, 1, 11, 0.5f);
  DataStreamBuffer incoming;
  incoming.writeVlqU(2); mapRemove(incoming, 2);
  incoming.writeVlqU(2); mapClear(incoming);
  mapDeltaSet(incoming, 3, 30); incoming.writeVlqU(0);
  incoming.seek(0); map.readNetDelta(incoming, 0.5f);
  EXPECT_EQ(map.size(), 2u); EXPECT_FALSE(map.pullUpdated());
  DataStreamBuffer actual, expected; map.netStore(actual);
  expected.writeVlqU(6); mapSet(expected, 1, 10); mapSet(expected, 2, 20);
  mapSet(expected, 1, 11); mapRemove(expected, 2); mapClear(expected); mapSet(expected, 3, 30);
  EXPECT_EQ(actual.data(), expected.data()); mapTrace("base_then_pending", actual);
  TestMap loaded; actual.seek(0); loaded.netLoad(actual, {});
  EXPECT_EQ(loaded.size(), 1u); EXPECT_EQ(loaded.get(3), 30);
  EXPECT_TRUE(loaded.pullUpdated()); EXPECT_TRUE(actual.atEnd());
}

TEST(NetMap, HashMapFullAndDeltaSynchronizeTypedKeysAndValues) {
  NetElementHashMap<int32_t, int32_t> source, target;
  NetElementVersion version; source.initNetVersion(&version);
  source.set(-7, -31); source.set(4, 42);
  DataStreamBuffer full; source.netStore(full); full.seek(0); target.netLoad(full, {});
  EXPECT_EQ(target.get(-7), -31); EXPECT_EQ(target.get(4), 42);
  version.increment(); source.remove(-7); source.set(4, -42); source.set(9, 90);
  DataStreamBuffer delta; ASSERT_TRUE(source.writeNetDelta(delta, 1));
  mapTrace("hash_delta", delta); delta.seek(0); target.readNetDelta(delta);
  EXPECT_FALSE(target.contains(-7)); EXPECT_EQ(target.get(4), -42); EXPECT_EQ(target.get(9), 90);
  EXPECT_TRUE(delta.atEnd());
}

TEST(NetMap, InitFlushesPendingBeforeRecordingClearAndCurrentEntries) {
  TestMap map; map.set(1, 10); map.enableNetInterpolation();
  receiveSet(map, 1, 11, 0.5f); receiveSet(map, 2, 20, 0.5f);
  NetElementVersion version; version.increment(); version.increment();
  map.initNetVersion(&version);
  EXPECT_EQ(map.get(1), 11); EXPECT_EQ(map.get(2), 20);
  EXPECT_TRUE(map.pullUpdated()); EXPECT_FALSE(map.pullUpdated());
  DataStreamBuffer actual, expected;
  ASSERT_TRUE(map.writeNetDelta(actual, 2));
  expected.writeVlqU(2); mapClear(expected);
  mapDeltaSet(expected, 1, 11); mapDeltaSet(expected, 2, 20); expected.writeVlqU(0);
  EXPECT_EQ(actual.data(), expected.data()); mapTrace("init_flush_history", actual);
  map.tickNetInterpolation(1.0f); EXPECT_FALSE(map.pullUpdated());
}

TEST(NetMap, DisableTurnsInterpolationOffBeforeApplyingTakenQueue) {
  HookScope scope; HookNetMap map; map.enableNetInterpolation();
  receiveSet(map, 1, 10, 0.5f);
  std::vector<int32_t> order;
  HookMap::onSet = [&](int32_t key, int32_t) {
    order.push_back(key);
    if (key == 1) receiveSet(map, 2, 20, 0.5f);
  };
  map.disableNetInterpolation();
  EXPECT_EQ(order, (std::vector<int32_t>{1, 2}));
  EXPECT_EQ(map.get(1), 10); EXPECT_EQ(map.get(2), 20);
  map.pullUpdated(); map.tickNetInterpolation(1.0f); EXPECT_FALSE(map.pullUpdated());
}

TEST(NetMap, TickSubtractsEveryTimerBeforeEmittingReadyFifoPrefix) {
  TestMap map; map.enableNetInterpolation();
  receiveSet(map, 1, 10, 0.25f); receiveSet(map, 2, 20, 0.5f);
  map.tickNetInterpolation(0.25f);
  EXPECT_EQ(map.get(1), 10); EXPECT_FALSE(map.contains(2));
  EXPECT_TRUE(map.pullUpdated());
  map.tickNetInterpolation(0.125f); EXPECT_FALSE(map.contains(2)); EXPECT_FALSE(map.pullUpdated());
  map.tickNetInterpolation(0.125f); EXPECT_EQ(map.get(2), 20); EXPECT_TRUE(map.pullUpdated());
}

TEST(NetMap, TickFailureLosesPoppedItemButRetainsAlreadyDecrementedTail) {
  HookScope scope; HookNetMap map; map.enableNetInterpolation();
  receiveSet(map, 1, 10, 0.25f); receiveSet(map, 2, 20, 0.5f);
  auto error = std::make_exception_ptr(MapDerivedMarker{});
  HookMap::onSet = [&](int32_t key, int32_t) { if (key == 1) std::rethrow_exception(error); };
  originalMapException(error, [&] { map.tickNetInterpolation(0.25f); });
  EXPECT_TRUE(map.empty()); EXPECT_FALSE(map.pullUpdated());
  HookMap::onSet = {};
  map.tickNetInterpolation(0.25f);
  EXPECT_FALSE(map.contains(1)); EXPECT_EQ(map.get(2), 20);
  DataStreamBuffer snapshot; map.netStore(snapshot); mapTrace("popped_failure_tail", snapshot);
}

TEST(NetMap, StrictlySmallerDelayFlushesOldQueueBeforeEnqueuingNewChange) {
  TestMap map; map.enableNetInterpolation();
  receiveSet(map, 1, 10, 0.5f); receiveSet(map, 2, 20, 0.75f);
  receiveSet(map, 3, 30, 0.25f);
  EXPECT_EQ(map.get(1), 10); EXPECT_EQ(map.get(2), 20); EXPECT_FALSE(map.contains(3));
  map.tickNetInterpolation(0.25f); EXPECT_EQ(map.get(3), 30);
}

TEST(NetMap, EqualDelayDoesNotFlushAndZeroDelayAppliesImmediately) {
  TestMap map; map.enableNetInterpolation();
  receiveSet(map, 1, 10, 0.5f); receiveSet(map, 2, 20, 0.5f);
  EXPECT_TRUE(map.empty()); EXPECT_FALSE(map.pullUpdated());
  receiveSet(map, 3, 30, 0.0f); EXPECT_EQ(map.get(3), 30);
  EXPECT_FALSE(map.contains(1)); EXPECT_FALSE(map.contains(2));
  map.tickNetInterpolation(0.5f); EXPECT_EQ(map.get(1), 10); EXPECT_EQ(map.get(2), 20);
}

TEST(NetMap, FullCodeContinuesReadingLaterChangesUntilTerminator) {
  TestMap map; map.set(9, 90); map.enableNetInterpolation(); receiveSet(map, 8, 80, 0.5f);
  DataStreamBuffer ds;
  ds.writeVlqU(1); ds.writeVlqU(1); mapSet(ds, 1, 10);
  mapDeltaSet(ds, 2, 20); ds.writeVlqU(0); ds.write<uint8_t>(0x5a);
  ds.seek(0); map.readNetDelta(ds, 0.25f);
  EXPECT_EQ(map.size(), 1u); EXPECT_EQ(map.get(1), 10); EXPECT_FALSE(map.contains(2));
  EXPECT_EQ(ds.read<uint8_t>(), 0x5a); EXPECT_TRUE(ds.atEnd());
  map.tickNetInterpolation(0.25f); EXPECT_EQ(map.get(2), 20); EXPECT_FALSE(map.contains(8));
}

TEST(NetMap, InvalidDeltaAndChangeCodesThrowExactNativeMessagePrefixes) {
  TestMap map;
  auto check = [&](DataStreamBuffer& ds, char const* message) {
    ds.seek(0);
    try { map.readNetDelta(ds); FAIL() << "expected IOException"; }
    catch (IOException const& e) { EXPECT_NE(std::string(e.what()).find(message), std::string::npos); }
  };
  DataStreamBuffer badDelta; mapDeltaSet(badDelta, 1, 10); badDelta.writeVlqU(3);
  check(badDelta, "Improper delta code received in NetElementMapWrapper::readNetDelta");
  EXPECT_EQ(map.get(1), 10); EXPECT_TRUE(map.pullUpdated());
  DataStreamBuffer badChange; badChange.writeVlqU(2); badChange.write<uint8_t>(3);
  check(badChange, "Improper type code received in NetElementMapWrapper::readChange");
  EXPECT_FALSE(map.pullUpdated());
}

TEST(NetMap, FailedFullLoadRecordsCopiedHistoryBeforeApplyAndPreservesPrefix) {
  HookScope scope; HookNetMap map; map.set(9, 90); map.pullUpdated();
  auto error = std::make_exception_ptr(73);
  HookMap::onSet = [&](int32_t key, int32_t) { if (key == 2) std::rethrow_exception(error); };
  DataStreamBuffer full; full.writeVlqU(3); mapSet(full, 1, 10); mapSet(full, 2, 20); mapSet(full, 3, 30);
  full.seek(0); originalMapException(error, [&] { map.netLoad(full, {}); });
  EXPECT_FALSE(map.contains(9)); EXPECT_EQ(map.get(1), 10); EXPECT_FALSE(map.contains(2));
  EXPECT_TRUE(map.pullUpdated()); EXPECT_FALSE(map.pullUpdated());
  DataStreamBuffer actual, expected; ASSERT_TRUE(map.writeNetDelta(actual, 0));
  expected.writeVlqU(2); mapClear(expected); mapDeltaSet(expected, 1, 10); mapDeltaSet(expected, 2, 20); expected.writeVlqU(0);
  EXPECT_EQ(actual.data(), expected.data()); mapTrace("failed_full_copied_history", actual);
  // A first-item failure clears old state but cannot reach the final updated=true.
  DataStreamBuffer first; first.writeVlqU(1); mapSet(first, 2, 20); first.seek(0);
  originalMapException(error, [&] { map.netLoad(first, {}); });
  EXPECT_TRUE(map.empty()); EXPECT_FALSE(map.pullUpdated());
}

TEST(NetMap, HistoryFloorIsStrictAtOneHundredAndOneHundredOne) {
  TestMap map; NetElementVersion version; map.initNetVersion(&version);
  for (unsigned i = 0; i < 100; ++i) version.increment();
  map.set(1, 100); EXPECT_EQ(map.changeDataLastVersion(), 0u);
  DataStreamBuffer at100; ASSERT_TRUE(map.writeNetDelta(at100, 0)); at100.seek(0);
  EXPECT_EQ(at100.readVlqU(), 2u); // The version-zero initial clear is still retained.
  version.increment(); map.set(1, 101); EXPECT_EQ(map.changeDataLastVersion(), 1u);
  DataStreamBuffer old, boundary; ASSERT_TRUE(map.writeNetDelta(old, 0)); ASSERT_TRUE(map.writeNetDelta(boundary, 1));
  mapTrace("history_fallback", old); mapTrace("history_boundary", boundary);
  old.seek(0); boundary.seek(0); EXPECT_EQ(old.readVlqU(), 1u); EXPECT_EQ(boundary.readVlqU(), 2u);
  EXPECT_TRUE(map.shouldWriteNetDelta(0)); EXPECT_TRUE(map.shouldWriteNetDelta(1));
}

TEST(NetMap, VersionCutsAreInclusiveAndEmptyWriteAddsNoTerminator) {
  TestMap map; NetElementVersion version; map.initNetVersion(&version);
  version.increment(); map.set(1, 10); version.increment(); map.set(2, 20);
  DataStreamBuffer actual, expected; ASSERT_TRUE(map.writeNetDelta(actual, 2));
  mapDeltaSet(expected, 2, 20); expected.writeVlqU(0);
  EXPECT_EQ(actual.data(), expected.data()); EXPECT_TRUE(map.shouldWriteNetDelta(2));
  EXPECT_FALSE(map.shouldWriteNetDelta(3));
  DataStreamBuffer empty; empty.write<uint8_t>(0x7e);
  EXPECT_FALSE(map.writeNetDelta(empty, 3)); EXPECT_EQ(empty.size(), 1u);
  EXPECT_EQ(static_cast<unsigned char>(empty.ptr()[0]), 0x7e);
  mapTrace("inclusive_cut", actual); mapTrace("empty_no_terminator", empty);
}

TEST(NetMap, MissingRemoteRemoveAndEmptyFullLoadStillMarkUpdated) {
  TestMap map; EXPECT_FALSE(map.remove(7)); EXPECT_FALSE(map.pullUpdated());
  DataStreamBuffer delta; delta.writeVlqU(2); mapRemove(delta, 7); delta.writeVlqU(0);
  delta.seek(0); map.readNetDelta(delta); EXPECT_TRUE(map.empty()); EXPECT_TRUE(map.pullUpdated());
  EXPECT_FALSE(map.pullUpdated());
  DataStreamBuffer full; full.writeVlqU(0); full.seek(0); map.netLoad(full, {});
  EXPECT_TRUE(map.pullUpdated()); EXPECT_FALSE(map.pullUpdated());
  DataStreamBuffer history, expected; ASSERT_TRUE(map.writeNetDelta(history, 0));
  expected.writeVlqU(2); mapClear(expected); expected.writeVlqU(0);
  EXPECT_EQ(history.data(), expected.data());
}

TEST(NetMap, PublicSetNoChangeAndValidMutationsRetainHistory) {
  TestMap map; NetElementVersion version; map.initNetVersion(&version);
  map.set(1, 10); map.pullUpdated(); version.increment();
  map.set(1, 10); EXPECT_FALSE(map.pullUpdated()); EXPECT_FALSE(map.shouldWriteNetDelta(1));
  map.set(1, 11); EXPECT_TRUE(map.pullUpdated()); EXPECT_TRUE(map.shouldWriteNetDelta(1));
  EXPECT_FALSE(map.insert(1, 99).second); EXPECT_FALSE(map.pullUpdated());
  EXPECT_TRUE(map.insert(2, 20).second); EXPECT_TRUE(map.pullUpdated());
  EXPECT_EQ(map.get(2), 20); EXPECT_TRUE(map.remove(2)); EXPECT_FALSE(map.remove(2));
  Map<int32_t, int32_t> replacement; replacement.set(3, 30); map.reset(std::move(replacement));
  EXPECT_FALSE(map.contains(1)); EXPECT_EQ(map.get(3), 30);
  DataStreamBuffer delta; ASSERT_TRUE(map.writeNetDelta(delta, 1)); mapTrace("public_mutations", delta);
  TestMap replica; replica.set(1, 10); delta.seek(0); replica.readNetDelta(delta);
  EXPECT_EQ(mapSnapshot(map), mapSnapshot(replica));
}

TEST(NetMap, TakenPendingFlushReentryAppendsToNewMemberQueueBeforeNewChange) {
  HookScope scope; HookNetMap map; map.enableNetInterpolation();
  receiveSet(map, 1, 10, 0.5f);
  HookMap::onSet = [&](int32_t key, int32_t) {
    if (key == 1) receiveSet(map, 2, 20, 0.125f);
  };
  receiveSet(map, 3, 30, 0.25f);
  EXPECT_EQ(map.get(1), 10); EXPECT_FALSE(map.contains(2)); EXPECT_FALSE(map.contains(3));
  DataStreamBuffer snapshot, expected; map.netStore(snapshot);
  expected.writeVlqU(3); mapSet(expected, 1, 10); mapSet(expected, 2, 20); mapSet(expected, 3, 30);
  EXPECT_EQ(snapshot.data(), expected.data()); mapTrace("reentrant_new_queue", snapshot);
  map.tickNetInterpolation(0.125f); EXPECT_EQ(map.get(2), 20); EXPECT_FALSE(map.contains(3));
  map.tickNetInterpolation(0.125f); EXPECT_EQ(map.get(3), 30);
}

// Native C++17 aggregate parenthesized construction makes these public methods
// uninstantiable. Preserve that domain instead of silently repairing the port.
#ifdef STAR_NET_MAP_PUSH_NEGATIVE
void netMapPushNegative() { TestMap map; map.push(1, 2); }
#endif
#ifdef STAR_NET_MAP_ERASE_NEGATIVE
void netMapEraseNegative() { TestMap map; map.set(1, 2); map.erase(map.begin()); }
#endif
#ifdef STAR_NET_MAP_TAKE_NEGATIVE
void netMapTakeNegative() { TestMap map; map.set(1, 2); map.take(1); }
#endif
#ifdef STAR_NET_MAP_MAYBE_TAKE_NEGATIVE
void netMapMaybeTakeNegative() { TestMap map; map.set(1, 2); map.maybeTake(1); }
#endif
