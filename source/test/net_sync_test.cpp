#include "StarNetElementSyncGroup.hpp"

#include "gtest/gtest.h"

#include <exception>
#include <functional>
#include <iostream>
#include <string>
#include <vector>

#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetSync.h"
#endif

using namespace Star;

namespace {
struct SyncMarker : std::exception {};
struct DerivedSyncMarker : SyncMarker {};
struct NonStdSyncMarker { int value = 17; };

struct SyncTrace {
  std::string events;
  std::exception_ptr error = std::make_exception_ptr(DerivedSyncMarker{});
  void log(std::string const& s) { events += s + ","; }
  void emit(char const* name) const {
    std::cout << "NET_SYNC_TRACE " << name << ' ' << events << '\n';
  }
};

// All time arguments are exact binary fractions; the trace records quarters,
// not addresses or implementation-specific floating-point formatting.
std::string quarters(float f) { return std::to_string(static_cast<int>(f * 4)); }

struct TestDerivedSync : NetElementSyncGroup {
  SyncTrace& trace;
  std::vector<bool> loads;
  size_t stores = 0;
  std::function<void(bool)> loadHook;
  std::function<void()> storeHook;
  explicit TestDerivedSync(SyncTrace& t) : trace(t) {}
  std::string flags() const {
    return std::string(netInterpolationEnabled() ? "on/" : "off/")
        + quarters(netExtrapolationHint());
  }
  void netElementsNeedLoad(bool full) override {
    loads.push_back(full);
    trace.log(std::string("load/") + (full ? "full/" : "delta/") + flags());
    if (loadHook) loadHook(full);
  }
  void netElementsNeedStore() override {
    ++stores;
    trace.log("store/" + flags());
    if (storeHook) storeHook();
  }
};

// One compatible uint8 child makes delta reads DIRECT: there is no index
// header. Every wire is produced by a qualified native base-group write.
struct FakeBaseChild : NetElement {
  TestDerivedSync& owner;
  SyncTrace& trace;
  int id;
  uint8_t byte = 7;
  std::string fail;
  NetElementVersion const* version = nullptr;
  explicit FakeBaseChild(TestDerivedSync& g, int i = 1) : owner(g), trace(g.trace), id(i) {}
  void call(char const* op, std::string args = {}) const {
    trace.log(std::to_string(id) + op + args + "/" + owner.flags());
    if (fail == op) std::rethrow_exception(trace.error);
  }
  void initNetVersion(NetElementVersion const* v) override {
    version = v;
    call("I", v ? std::to_string(v->current()) : "null");
  }
  void enableNetInterpolation(float hint) override { call("E", quarters(hint)); }
  void disableNetInterpolation() override { call("D"); }
  void tickNetInterpolation(float dt) override { call("T", quarters(dt)); }
  void blankNetDelta(float time) override { call("B", quarters(time)); }
  void netStore(DataStream& ds, NetCompatibilityRules rules) const override {
    ds.write(byte); call("S", std::to_string(rules.version()));
  }
  void netLoad(DataStream& ds, NetCompatibilityRules rules) override {
    byte = ds.read<uint8_t>(); call("L", std::to_string(rules.version()));
  }
  bool writeNetDelta(DataStream& ds, uint64_t from, NetCompatibilityRules rules) const override {
    ds.write(byte); call("W", std::to_string(from) + "/" + std::to_string(rules.version()));
    return true;
  }
  void readNetDelta(DataStream& ds, float time, NetCompatibilityRules rules) override {
    byte = ds.read<uint8_t>(); call("R", quarters(time) + "/" + std::to_string(rules.version()));
  }
};

struct SyncFixture {
  SyncTrace trace;
  TestDerivedSync group{trace};
  FakeBaseChild child{group};
  SyncFixture() { group.addNetElement(&child); trace.events.clear(); }
  ByteArray wire(uint8_t value = 19) {
    child.byte = value;
    DataStreamBuffer ds;
    EXPECT_TRUE(group.NetElementGroup::writeNetDelta(ds, 9));
    EXPECT_EQ(ds.size(), 1u);
    trace.events.clear();
    return ds.takeData();
  }
  void read(float time = 0.5f, uint8_t value = 19) {
    DataStreamBuffer ds(wire(value));
    group.readNetDelta(ds, time);
    EXPECT_EQ(child.byte, value);
    EXPECT_TRUE(ds.atEnd());
  }
};

template <typename F> void syncFailure(SyncTrace& t, F f, bool nonstd = false) {
  bool caught = false;
  try { f(); }
  catch (DerivedSyncMarker const&) {
    caught = true; EXPECT_FALSE(nonstd); EXPECT_EQ(std::current_exception(), t.error);
  } catch (NonStdSyncMarker const& marker) {
    caught = true; EXPECT_TRUE(nonstd); EXPECT_EQ(marker.value, 17);
    EXPECT_EQ(std::current_exception(), t.error);
  }
  EXPECT_TRUE(caught);
  t.log("caught");
}
}

TEST(NetSync, BaseOrderHooksAndDirectWire) {
  SyncFixture f;
  NetElementVersion version; version.increment();
  f.group.initNetVersion(&version);
  EXPECT_EQ(f.child.version, &version);
  f.read(0.5f, 37);
  EXPECT_EQ(f.group.loads, std::vector<bool>({false}));
  f.trace.events.clear();
  f.group.enableNetInterpolation(0.25f);
  f.group.tickNetInterpolation(0.25f);
  f.group.blankNetDelta(0.5f);
  f.group.disableNetInterpolation();
  EXPECT_EQ(f.trace.events,
      "1E1/on/1,load/delta/on/1,1T1/on/1,load/delta/on/1,"
      "1B2/on/1,load/delta/on/1,1D/off/0,load/delta/off/0,");
  DataStreamBuffer full;
  NetElementSyncGroup const& constGroup = f.group;
  constGroup.netStore(full);
  EXPECT_EQ(full.data(), DataStreamBuffer::serialize(uint8_t(37)));
  full.seek(0); f.group.netLoad(full, {});
  EXPECT_TRUE(f.group.loads.back());
  f.trace.emit("base-order");
}

TEST(NetSync, ReadWithoutBlankNeverExpiresAndNegativeDtExtendsBlank) {
  SyncFixture f;
  f.read(0.0f);
  f.group.tickNetInterpolation(1.0f); // Disabled still decrements the recent timer.
  f.group.enableNetInterpolation(0.5f);
  f.group.tickNetInterpolation(1.0f);
  f.group.disableNetInterpolation();
  EXPECT_EQ(f.group.loads.size(), 4u); // No blank: negative time never expires.
  f.group.blankNetDelta(0.25f);
  f.group.tickNetInterpolation(-0.5f);
  f.group.tickNetInterpolation(0.5f);
  size_t before = f.group.loads.size();
  f.group.enableNetInterpolation(0.25f);
  EXPECT_EQ(f.group.loads.size(), before + 1);
  f.group.tickNetInterpolation(0.5f); // .25 - .5 is strictly negative.
  before = f.group.loads.size();
  f.group.disableNetInterpolation();
  EXPECT_EQ(f.group.loads.size(), before);
  f.trace.emit("negative-dt");
}

TEST(NetSync, StrictZeroExpiryAndRepeatedBlankDoesNotResetTime) {
  SyncFixture f;
  f.read(); f.group.enableNetInterpolation(0.5f);
  f.group.blankNetDelta(0.5f);
  f.group.tickNetInterpolation(0.5f); // Exactly zero remains recent.
  size_t before = f.group.loads.size();
  f.group.disableNetInterpolation();
  EXPECT_EQ(f.group.loads.size(), before + 1);
  f.group.blankNetDelta(1.0f); // Already blank: must not replace zero with one.
  f.group.tickNetInterpolation(0.25f);
  before = f.group.loads.size();
  f.group.enableNetInterpolation(0.25f);
  EXPECT_EQ(f.group.loads.size(), before);
  f.trace.emit("zero-repeat-blank");
}

TEST(NetSync, FullLoadNeitherMarksRecentNorRefreshesPendingBlank) {
  SyncFixture f;
  DataStreamBuffer first(f.wire(21));
  f.group.netLoad(first, {});
  EXPECT_EQ(f.group.loads, std::vector<bool>({true}));
  f.group.enableNetInterpolation(0.5f);
  f.group.disableNetInterpolation();
  EXPECT_EQ(f.group.loads.size(), 1u);
  f.read(); f.group.blankNetDelta(0.25f);
  DataStreamBuffer second(f.wire(22));
  f.group.netLoad(second, {});
  size_t pending = f.group.loads.size();
  f.group.disableNetInterpolation();
  EXPECT_EQ(f.group.loads.size(), pending + 1); // Full load did not clear recent.
  f.group.tickNetInterpolation(0.5f);
  size_t before = f.group.loads.size();
  f.group.enableNetInterpolation(0.25f);
  EXPECT_EQ(f.group.loads.size(), before); // Full load did not clear blank or reset delta.
  EXPECT_EQ(f.child.byte, 22);
  f.trace.emit("full-load-pending");
}

TEST(NetSync, BaseReadFailureDoesNotMarkButHookFailureKeepsMark) {
  for (bool nonstd : {false, true}) {
    SyncFixture f;
    if (nonstd) f.trace.error = std::make_exception_ptr(NonStdSyncMarker{});
    DataStreamBuffer ds(f.wire(43)); f.child.fail = "R";
    syncFailure(f.trace, [&] { f.group.readNetDelta(ds, 0.5f); }, nonstd);
    EXPECT_EQ(ds.pos(), 1u); EXPECT_EQ(f.child.byte, 43);
    EXPECT_TRUE(f.group.loads.empty());
    f.child.fail.clear(); f.group.enableNetInterpolation(0.25f);
    EXPECT_TRUE(f.group.loads.empty());
    f.group.loadHook = [&](bool) { std::rethrow_exception(f.trace.error); };
    ds.seek(0);
    syncFailure(f.trace, [&] { f.group.readNetDelta(ds, 0.0f); }, nonstd);
    f.group.loadHook = {};
    f.group.tickNetInterpolation(1.0f);
    size_t before = f.group.loads.size();
    f.group.disableNetInterpolation();
    EXPECT_EQ(f.group.loads.size(), before + 1); // Throwing hook ran AFTER the mark.
    f.trace.emit(nonstd ? "nonstd-read-failures" : "std-read-failures");
  }
}

TEST(NetSync, TickChecksFreshTimeAndBlankAfterReentrantHook) {
  SyncFixture f;
  f.read(0.0f); f.group.enableNetInterpolation(0.5f);
  bool entered = false;
  f.group.loadHook = [&](bool full) {
    EXPECT_FALSE(full);
    if (entered) return;
    entered = true;
    f.group.blankNetDelta(0.5f); // Replaces negative time with positive time.
    f.group.disableNetInterpolation(); // Fresh interpolation flag changes too.
  };
  f.group.tickNetInterpolation(0.25f);
  EXPECT_TRUE(entered); EXPECT_FALSE(f.group.netInterpolationEnabled());
  f.group.loadHook = {};
  size_t before = f.group.loads.size();
  f.group.enableNetInterpolation(0.25f);
  EXPECT_EQ(f.group.loads.size(), before + 1); // Cached pre-hook negative would wrongly expire.
  f.group.tickNetInterpolation(0.5f);
  before = f.group.loads.size(); f.group.disableNetInterpolation();
  EXPECT_EQ(f.group.loads.size(), before + 1); // Hook's fresh .5 reached exact zero.
  f.group.tickNetInterpolation(0.25f);
  before = f.group.loads.size(); f.group.enableNetInterpolation(0.5f);
  EXPECT_EQ(f.group.loads.size(), before);
  f.trace.emit("fresh-after-hook");
}

TEST(NetSync, ClearElementsPreservesPendingRecentAndBlankState) {
  SyncFixture f;
  f.read(); f.group.blankNetDelta(0.25f);
  f.group.clearNetElements();
  f.group.tickNetInterpolation(0.25f);
  size_t before = f.group.loads.size();
  f.group.enableNetInterpolation(0.25f);
  EXPECT_EQ(f.group.loads.size(), before + 1);
  f.group.tickNetInterpolation(0.25f);
  before = f.group.loads.size(); f.group.disableNetInterpolation();
  EXPECT_EQ(f.group.loads.size(), before);
  f.group.addNetElement(&f.child);
  DataStreamBuffer ds;
  EXPECT_TRUE(f.group.writeNetDelta(ds, 9));
  EXPECT_EQ(ds.data(), DataStreamBuffer::serialize(uint8_t(19)));
  f.trace.emit("clear-pending");
}

TEST(NetSync, RulesGuardBeforeHooksAndBaseRechecksAfterStoreHook) {
  SyncFixture f;
  NetCompatibilityRules legacy(LegacyVersion);
  f.group.setCompatibilityVersion(OpenProtocolVersion);
  DataStreamBuffer rejected(f.wire());
  f.group.netStore(rejected, legacy); f.group.netLoad(rejected, legacy);
  EXPECT_FALSE(f.group.writeNetDelta(rejected, 9, legacy));
  f.group.readNetDelta(rejected, 0.5f, legacy);
  EXPECT_EQ(rejected.pos(), 0u); EXPECT_TRUE(f.group.loads.empty());
  EXPECT_EQ(f.group.stores, 0u); EXPECT_TRUE(f.trace.events.empty());
  f.group.enableNetInterpolation(0.25f);
  EXPECT_TRUE(f.group.loads.empty());
  f.group.setCompatibilityVersion(LegacyVersion);
  f.group.storeHook = [&] { f.group.setCompatibilityVersion(OpenProtocolVersion); };
  DataStreamBuffer ds;
  NetElementSyncGroup const& constGroup = f.group;
  constGroup.netStore(ds, legacy); EXPECT_TRUE(ds.empty());
  EXPECT_EQ(f.group.stores, 1u);
  f.group.setCompatibilityVersion(LegacyVersion);
  EXPECT_FALSE(constGroup.writeNetDelta(ds, 9, legacy)); EXPECT_TRUE(ds.empty());
  EXPECT_EQ(f.group.stores, 2u);
  f.trace.emit("rules-recheck");
}

TEST(NetSync, BaseTickAndBlankFailuresPreventWrapperStateUpdates) {
  SyncFixture f;
  f.read(); f.group.enableNetInterpolation(0.5f); f.group.blankNetDelta(0.25f);
  size_t before = f.group.loads.size();
  f.child.fail = "T";
  syncFailure(f.trace, [&] { f.group.tickNetInterpolation(1.0f); });
  EXPECT_EQ(f.group.loads.size(), before);
  f.child.fail.clear(); f.group.disableNetInterpolation();
  EXPECT_EQ(f.group.loads.size(), before + 1); // Failed tick did not decrement/expire.
  f.group.enableNetInterpolation(0.5f);
  f.read(0.0f);
  f.child.fail = "B"; before = f.group.loads.size();
  syncFailure(f.trace, [&] { f.group.blankNetDelta(0.0f); });
  EXPECT_EQ(f.group.loads.size(), before);
  f.child.fail.clear(); f.group.tickNetInterpolation(1.0f);
  before = f.group.loads.size(); f.group.disableNetInterpolation();
  EXPECT_EQ(f.group.loads.size(), before + 1); // Failed blank did not set blank state.
  before = f.group.loads.size(); f.child.fail = "E";
  syncFailure(f.trace, [&] { f.group.enableNetInterpolation(0.25f); });
  EXPECT_TRUE(f.group.netInterpolationEnabled());
  EXPECT_EQ(f.group.loads.size(), before); // Base flag changes, but wrapper hook is skipped.
  f.child.fail = "D";
  syncFailure(f.trace, [&] { f.group.disableNetInterpolation(); });
  EXPECT_FALSE(f.group.netInterpolationEnabled());
  EXPECT_EQ(f.group.loads.size(), before);
  f.child.fail.clear();
  f.trace.emit("base-failure-prefix");
}

TEST(NetSync, StoreLoadWriteFailuresKeepExactNativePrefixes) {
  SyncFixture f;
  for (char const* operation : {"S", "L", "W"}) {
    DataStreamBuffer ds(f.wire(61));
    ds.seek(0); f.child.fail = operation;
    size_t loads = f.group.loads.size(), stores = f.group.stores;
    if (f.child.fail == "S") {
      ds.clear(); syncFailure(f.trace, [&] { f.group.netStore(ds); });
      EXPECT_EQ(f.group.stores, stores + 1);
    } else if (f.child.fail == "L") {
      syncFailure(f.trace, [&] { f.group.netLoad(ds, {}); });
      EXPECT_EQ(ds.pos(), 1u); EXPECT_EQ(f.group.loads.size(), loads);
    } else {
      ds.clear(); syncFailure(f.trace, [&] { f.group.writeNetDelta(ds, 9); });
      EXPECT_EQ(f.group.stores, stores + 1);
    }
    EXPECT_EQ(ds.data(), DataStreamBuffer::serialize(uint8_t(61)));
    f.child.fail.clear();
  }
  f.trace.emit("stream-failure-prefixes");
}

TEST(NetSync, OptionalCallbacksCanBeReplacedAndClearedWithoutExtraCopies) {
  SyncTrace t;
  NetElementCallbackGroup group;
  struct CopyProbe {
    int* copies;
    explicit CopyProbe(int* c) : copies(c) {}
    CopyProbe(CopyProbe const& other) : copies(other.copies) { ++*copies; }
    void operator()(bool) const {}
  };
  int copies = 0;
  group.setNeedsLoadCallback(CopyProbe(&copies));
  int installedCopies = copies;
  DataStreamBuffer empty;
  group.netLoad(empty, {}); // Empty full-load succeeds and invokes optional callback.
  group.enableNetInterpolation(0.25f); group.disableNetInterpolation();
  EXPECT_EQ(copies, installedCopies);
  group.setNeedsLoadCallback([&](bool full) { t.log(full ? "full" : "delta"); });
  group.setNeedsStoreCallback([&] { t.log("store"); });
  group.netStore(empty); group.netLoad(empty, {});
  EXPECT_FALSE(group.writeNetDelta(empty, 9));
  EXPECT_EQ(t.events, "store,full,store,");
  group.setNeedsLoadCallback({}); group.setNeedsStoreCallback({});
  group.netStore(empty); group.netLoad(empty, {});
  EXPECT_FALSE(group.writeNetDelta(empty, 9));
  EXPECT_EQ(t.events, "store,full,store,");
  t.emit("optional-callbacks");
}

#ifdef STAR_USE_RUST_NET_GROUP
TEST(NetSync, OnCounterNaturalPublicRoots) {
  SyncFixture f;
  // Eight wrapper roots; no direct ABI execution is used to manufacture coverage.
  uint64_t before[8], globalBefore[8];
  for (uint32_t mode = 0; mode < 8; ++mode) {
    before[mode] = sb_net_sync_count(0, mode);
    globalBefore[mode] = sb_net_sync_count(1, mode);
  }
  f.group.enableNetInterpolation(0.25f);
  f.group.disableNetInterpolation();
  f.group.tickNetInterpolation(0.25f);
  f.group.blankNetDelta(0.5f);
  DataStreamBuffer ds;
  NetElementSyncGroup const& constGroup = f.group;
  constGroup.netStore(ds); ds.seek(0); f.group.netLoad(ds, {});
  ds.clear(); EXPECT_TRUE(constGroup.writeNetDelta(ds, 9));
  ds.seek(0); f.group.readNetDelta(ds, 0.5f);
  EXPECT_TRUE(ds.atEnd());
  for (uint32_t mode = 0; mode < 8; ++mode) {
    EXPECT_EQ(sb_net_sync_count(0, mode) - before[mode], uint64_t(1)) << mode;
    EXPECT_GE(sb_net_sync_count(1, mode) - globalBefore[mode], uint64_t(1)) << mode;
  }
  EXPECT_EQ(sb_net_sync_count(0, 8), uint64_t(0));
  EXPECT_EQ(sb_net_sync_count(3, 0), uint64_t(0));
  std::cout << "NET_SYNC_DIAGNOSTIC natural-roots 8\n";
}
#endif
