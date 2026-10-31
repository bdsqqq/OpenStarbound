#include "StarDataStreamDevices.hpp"
#include "StarNetElementDynamicGroup.hpp"

#include "gtest/gtest.h"

#include <algorithm>
#include <exception>
#include <functional>
#include <iostream>
#include <string>
#include <type_traits>
#include <vector>

#ifdef STAR_USE_RUST_NET_DYNAMIC
#include "StarRustNetDynamic.h"
#endif

using namespace Star;

namespace {
struct DynamicMarker : std::exception {};
struct DynamicDerivedMarker : DynamicMarker {};
struct DynamicTrace {
  std::vector<std::string> events;
  std::exception_ptr error = std::make_exception_ptr(DynamicDerivedMarker{});
  std::string fail;
  int failValue = -1;
  void log(std::string s) { events.push_back(std::move(s)); }
  void emit(char const* name) const {
    std::cout << "NET_DYNAMIC_TRACE " << name << ' ';
    for (auto const& e : events) std::cout << e << ',';
    std::cout << '\n';
  }
};
// netLoad creates default-constructed production children. This context only
// supplies their observation sink; it does not replace the group's factory.
thread_local DynamicTrace* dynamicTrace = nullptr;
struct DynamicContext {
  DynamicTrace trace;
  DynamicContext() { dynamicTrace = &trace; }
  ~DynamicContext() { dynamicTrace = nullptr; }
};
struct DynamicElement : NetElement {
  DynamicTrace* trace = dynamicTrace;
  uint8_t value = 0;
  NetElementVersion const* version = nullptr;
  bool enabled = false;
  bool writes = false;
  float hint = 0;
  std::function<void()> initializer, onEnable, onDisable, onDestroy;
  std::vector<float> enables, ticks, blanks;
  DynamicElement() { call("C"); }
  explicit DynamicElement(uint8_t v) : value(v) { call("C"); }
  ~DynamicElement() override {
    trace->log(std::to_string(value) + "X");
    if (onDestroy) onDestroy();
  }
  void call(char const* op, std::string arg = {}) const {
    trace->log(std::to_string(value) + op + arg);
    if (trace->fail == op && (trace->failValue < 0 || trace->failValue == value))
      std::rethrow_exception(trace->error);
  }
  void initNetVersion(NetElementVersion const* v) override {
    version = v;
    call("I", v ? std::to_string(v->current()) : "null");
    if (initializer) initializer();
  }
  void enableNetInterpolation(float h) override {
    enabled = true; hint = h; enables.push_back(h);
    call("E", std::to_string(h));
    if (onEnable) onEnable();
  }
  void disableNetInterpolation() override {
    enabled = false; hint = 0; call("D");
    if (onDisable) onDisable();
  }
  void tickNetInterpolation(float dt) override { ticks.push_back(dt); call("T", std::to_string(dt)); }
  void blankNetDelta(float time) override { blanks.push_back(time); call("B", std::to_string(time)); }
  void netStore(DataStream& ds, NetCompatibilityRules rules) const override {
    ds.write(value); call("S", std::to_string(rules.version()));
  }
  void netLoad(DataStream& ds, NetCompatibilityRules rules) override {
    value = ds.read<uint8_t>(); call("L", std::to_string(rules.version()));
  }
  bool writeNetDelta(DataStream& ds, uint64_t from, NetCompatibilityRules rules) const override {
    call("W", std::to_string(from) + "/" + std::to_string(rules.version()));
    if (writes) ds.write(value);
    return writes;
  }
  void readNetDelta(DataStream& ds, float time, NetCompatibilityRules rules) override {
    value = ds.read<uint8_t>(); call("R", std::to_string(time) + "/" + std::to_string(rules.version()));
  }
};
using DynamicGroup = NetElementDynamicGroup<DynamicElement>;
static_assert(std::is_default_constructible<DynamicElement>::value, "native load factory needs a default constructor");
static_assert(!std::is_copy_constructible<DynamicGroup>::value, "dynamic group is not copyable");
static_assert(!std::is_copy_assignable<DynamicGroup>::value, "dynamic group is not assignable");
using DynamicState = std::vector<std::pair<uint32_t, uint8_t>>;
DynamicState dynamicState(DynamicGroup const& g) {
  DynamicState state;
  for (auto id : g.netElementIds()) state.emplace_back(id, g.getNetElement(id)->value);
  std::sort(state.begin(), state.end());
  return state;
}
void dynamicWire(char const* name, DataStreamBuffer const& ds) {
  static char const hex[] = "0123456789abcdef";
  std::cout << "NET_DYNAMIC_TRACE " << name << ' ';
  for (size_t i = 0; i < ds.size(); ++i) {
    auto b = static_cast<unsigned char>(ds.ptr()[i]);
    std::cout << hex[b >> 4] << hex[b & 15];
  }
  std::cout << '\n';
}
template <typename F> void dynamicFailure(DynamicTrace& t, F f) {
  try { f(); FAIL() << "expected original exception"; }
  catch (...) { EXPECT_EQ(std::current_exception(), t.error); t.log("caught"); }
}
void dynamicAdvance(NetElementVersion& version, uint64_t target) {
  while (version.current() < target) version.increment();
}
// Decode full snapshots independently through public DataStream operations.
DynamicState dynamicFullState(DataStreamBuffer& ds) {
  DynamicState state;
  auto count = ds.readVlqU();
  for (uint64_t i = 0; i < count; ++i) {
    auto id = ds.readVlqU();
    DataStreamBuffer child(ds.read<ByteArray>());
    auto value = child.read<uint8_t>();
    EXPECT_TRUE(child.atEnd());
    state.emplace_back(static_cast<uint32_t>(id), value);
  }
  std::sort(state.begin(), state.end());
  return state;
}
}

TEST(NetDynamic, AddOwnershipAndNativeIdCursor) {
  DynamicContext c; auto& t = c.trace; DynamicGroup g;
  auto a = make_shared<DynamicElement>(11);
  std::weak_ptr<DynamicElement> weak = a;
  auto id = g.addNetElement(a);
  EXPECT_NE(id, uint32_t(DynamicGroup::NullElementId));
  EXPECT_EQ(a.use_count(), 2);
  EXPECT_EQ(g.getNetElement(id).get(), a.get());
  EXPECT_EQ(t.events, (std::vector<std::string>{"11C", "11Inull", "11D"}));
  a.reset(); g.removeNetElement(id); EXPECT_TRUE(weak.expired());
  auto next = g.addNetElement(make_shared<DynamicElement>(22));
  // Compare with the actual native allocator API, not an assumed recycling policy.
  IdMap<uint32_t, int> ids(1, highest<uint32_t>());
  auto reference = ids.add(11); ids.remove(reference);
  EXPECT_EQ(id, reference); EXPECT_EQ(next, ids.add(22));
  t.emit("ownership-cursor");
}

TEST(NetDynamic, MissingRemovalRecordsNativeNoopRatherThanThrowing) {
  DynamicContext c; DynamicGroup g; NetElementVersion v;
  g.initNetVersion(&v); v.increment();
  EXPECT_NO_THROW(g.removeNetElement(999));
  EXPECT_TRUE(g.netElementIds().empty());
  DataStreamBuffer delta;
  EXPECT_TRUE(g.writeNetDelta(delta, 1));
  EXPECT_FALSE(delta.empty());
  DynamicGroup reader;
  delta.seek(0); EXPECT_FALSE(delta.read<bool>()); delta.seek(0);
  EXPECT_NO_THROW(reader.readNetDelta(delta));
  EXPECT_TRUE(reader.netElementIds().empty()); EXPECT_TRUE(delta.atEnd());
  dynamicWire("missing-removal", delta); c.trace.emit("missing-removal-calls");
}

TEST(NetDynamic, ReadyReadsFreshFlagsAndHintAfterInitHook) {
  DynamicContext c; DynamicGroup g; NetElementVersion v; v.increment();
  g.initNetVersion(&v);
  auto resident = make_shared<DynamicElement>(1); g.addNetElement(resident);
  auto arriving = make_shared<DynamicElement>(2);
  arriving->initializer = [&] {
    EXPECT_EQ(g.netElementIds().size(), 1u);
    EXPECT_EQ(arriving.use_count(), 2); // caller + by-value public argument
    g.enableNetInterpolation(0.5f);
  };
  auto id = g.addNetElement(arriving);
  EXPECT_EQ(arriving->version, &v); EXPECT_TRUE(arriving->enabled);
  EXPECT_EQ(arriving->hint, 0.5f); EXPECT_TRUE(resident->enabled);
  EXPECT_EQ(arriving->enables, (std::vector<float>{0.5f}));
  arriving->initializer = {};
  g.removeNetElement(id);
  auto disabling = make_shared<DynamicElement>(3);
  disabling->initializer = [&] { g.disableNetInterpolation(); };
  g.addNetElement(disabling);
  EXPECT_FALSE(disabling->enabled); EXPECT_TRUE(disabling->enables.empty());
  EXPECT_FALSE(resident->enabled);
  c.trace.emit("fresh-ready-policy");
}

TEST(NetDynamic, ReadyFailuresKeepExactExceptionAndDoNotInsert) {
  DynamicContext c; auto& t = c.trace; DynamicGroup g;
  for (bool nonstandard : {false, true}) {
    t.error = nonstandard ? std::make_exception_ptr(713) : std::make_exception_ptr(DynamicDerivedMarker{});
    for (auto op : {"I", "D", "E"}) {
      t.fail = op; t.failValue = 7;
      if (std::string(op) == "E") g.enableNetInterpolation(0.5f);
      std::weak_ptr<DynamicElement> weak;
      dynamicFailure(t, [&] {
        auto element = make_shared<DynamicElement>(7); weak = element;
        g.addNetElement(std::move(element));
      });
      EXPECT_TRUE(weak.expired()); EXPECT_TRUE(g.netElementIds().empty());
      t.fail.clear(); g.disableNetInterpolation();
      DataStreamBuffer ds; EXPECT_FALSE(g.writeNetDelta(ds, 0)); EXPECT_TRUE(ds.empty());
    }
  }
  t.emit("ready-exceptions");
}

TEST(NetDynamic, PropagationKeepsOriginalHintAcrossValidReentrantPolicyChange) {
  DynamicContext c; DynamicGroup g;
  auto a = make_shared<DynamicElement>(1), b = make_shared<DynamicElement>(2);
  g.addNetElement(a); g.addNetElement(b);
  bool entered = false;
  auto hook = [&] { if (!entered) { entered = true; g.enableNetInterpolation(0.5f); } };
  a->onEnable = hook; b->onEnable = hook;
  g.enableNetInterpolation(0.25f);
  for (auto e : {a, b}) {
    EXPECT_EQ(std::count(e->enables.begin(), e->enables.end(), 0.25f), 1);
    EXPECT_EQ(std::count(e->enables.begin(), e->enables.end(), 0.5f), 1);
    e->onEnable = {};
  }
  auto fresh = make_shared<DynamicElement>(3); g.addNetElement(fresh);
  EXPECT_TRUE(fresh->enabled); EXPECT_EQ(fresh->hint, 0.5f);
  // A disable callback can observe that parent policy was committed first.
  bool once = false;
  a->onDisable = [&] { if (!once) { once = true; g.enableNetInterpolation(0.25f); } };
  g.disableNetInterpolation(); a->onDisable = {};
  auto after = make_shared<DynamicElement>(4); g.addNetElement(after);
  EXPECT_TRUE(after->enabled); EXPECT_EQ(after->hint, 0.25f);
  c.trace.fail = "E";
  dynamicFailure(c.trace, [&] { g.enableNetInterpolation(0.5f); });
  c.trace.fail.clear();
  auto afterEnableFailure = make_shared<DynamicElement>(5); g.addNetElement(afterEnableFailure);
  EXPECT_TRUE(afterEnableFailure->enabled); EXPECT_EQ(afterEnableFailure->hint, 0.5f);
  c.trace.fail = "D";
  dynamicFailure(c.trace, [&] { g.disableNetInterpolation(); });
  c.trace.fail.clear();
  auto afterDisableFailure = make_shared<DynamicElement>(6); g.addNetElement(afterDisableFailure);
  EXPECT_FALSE(afterDisableFailure->enabled); EXPECT_EQ(afterDisableFailure->hint, 0.0f);
  c.trace.emit("reentrant-policy");
}

TEST(NetDynamic, TickAlwaysVisitsChildrenButBlankRequiresEnabledGroup) {
  DynamicContext c; DynamicGroup g;
  auto a = make_shared<DynamicElement>(1), b = make_shared<DynamicElement>(2);
  g.addNetElement(a); g.addNetElement(b);
  g.tickNetInterpolation(0.25f); g.blankNetDelta(0.5f);
  g.enableNetInterpolation(0.5f); g.tickNetInterpolation(-0.25f); g.blankNetDelta(0.75f);
  g.disableNetInterpolation(); g.tickNetInterpolation(0.125f); g.blankNetDelta(0.5f);
  for (auto e : {a, b}) {
    EXPECT_EQ(e->ticks, (std::vector<float>{0.25f, -0.25f, 0.125f}));
    EXPECT_EQ(e->blanks, (std::vector<float>{0.75f}));
  }
  c.trace.error = std::make_exception_ptr(319); c.trace.fail = "T";
  dynamicFailure(c.trace, [&] { g.tickNetInterpolation(0.25f); });
  c.trace.fail.clear(); g.enableNetInterpolation(0.5f); c.trace.fail = "B";
  dynamicFailure(c.trace, [&] { g.blankNetDelta(0.5f); });
  c.trace.fail.clear(); c.trace.emit("tick-blank");
}

TEST(NetDynamic, VersionInitializationReplacesHistoryAndOnlyInitializesChildren) {
  DynamicContext c; DynamicGroup g; NetElementVersion old, fresh;
  g.initNetVersion(&old); dynamicAdvance(old, 102);
  auto a = make_shared<DynamicElement>(1), b = make_shared<DynamicElement>(2);
  g.addNetElement(a); g.addNetElement(b); g.enableNetInterpolation(0.5f);
  fresh.increment(); c.trace.events.clear(); g.initNetVersion(&fresh);
  EXPECT_EQ(a->version, &fresh); EXPECT_EQ(b->version, &fresh);
  EXPECT_EQ(c.trace.events.size(), 2u);
  for (auto const& event : c.trace.events) EXPECT_TRUE(event == "1I1" || event == "2I1");
  EXPECT_EQ(a->enables.size(), 1u); EXPECT_EQ(b->enables.size(), 1u);
  DataStreamBuffer ds; EXPECT_TRUE(g.writeNetDelta(ds, 0));
  ds.seek(0); EXPECT_FALSE(ds.read<bool>()); ds.seek(0);
  DynamicGroup reader; reader.readNetDelta(ds);
  EXPECT_EQ(dynamicState(reader), dynamicState(g)); EXPECT_TRUE(ds.atEnd());
  dynamicWire("reinitialized-history", ds);
  c.trace.fail = "I"; c.trace.failValue = -1;
  dynamicFailure(c.trace, [&] { g.initNetVersion(nullptr); });
  c.trace.fail.clear();
  auto added = make_shared<DynamicElement>(3); g.addNetElement(added);
  EXPECT_EQ(added->version, nullptr); EXPECT_TRUE(added->enabled); EXPECT_EQ(added->hint, 0.5f);
  c.trace.emit("version-init");
}

TEST(NetDynamic, ClearUsesOwnedIdsAndPreservesPolicyVersionAndAllocatorCursor) {
  DynamicContext c; DynamicGroup g; NetElementVersion v; dynamicAdvance(v, 12);
  g.initNetVersion(&v); g.enableNetInterpolation(0.5f);
  std::vector<std::weak_ptr<DynamicElement>> weak;
  IdMap<uint32_t, int> reference(1, highest<uint32_t>());
  std::vector<uint32_t> ids;
  for (uint8_t value : {uint8_t(1), uint8_t(2), uint8_t(3)}) {
    auto e = make_shared<DynamicElement>(value); weak.push_back(e);
    e->onDestroy = [&] {
      // Only inspect public IDs: no container mutation during native erase.
      auto visible = g.netElementIds();
      std::vector<uint32_t> sorted(visible.begin(), visible.end()); std::sort(sorted.begin(), sorted.end());
      std::string event = "destroy-visible";
      for (auto id : sorted) event += "/" + std::to_string(id);
      c.trace.log(event);
    };
    auto id = g.addNetElement(std::move(e)); ids.push_back(id);
    EXPECT_EQ(id, reference.add(value));
  }
  g.clearNetElements();
  EXPECT_TRUE(g.netElementIds().empty()); for (auto const& e : weak) EXPECT_TRUE(e.expired());
  for (auto id : ids) reference.remove(id);
  auto e = make_shared<DynamicElement>(9); auto next = g.addNetElement(e);
  EXPECT_EQ(next, reference.add(9)); EXPECT_EQ(e->version, &v);
  EXPECT_TRUE(e->enabled); EXPECT_EQ(e->hint, 0.5f);
  DataStreamBuffer ds; EXPECT_TRUE(g.writeNetDelta(ds, 12));
  DynamicGroup reader; ds.seek(0); reader.readNetDelta(ds);
  EXPECT_EQ(dynamicState(reader), dynamicState(g)); EXPECT_TRUE(ds.atEnd());
  dynamicWire("clear-history", ds); c.trace.emit("clear-snapshot");
}

TEST(NetDynamic, NativeFullWireRoundTripAndCompatibilityGuard) {
  DynamicContext c; DynamicGroup source;
  source.addNetElement(make_shared<DynamicElement>(17)); source.addNetElement(make_shared<DynamicElement>(29));
  DataStreamBuffer full; source.netStore(full);
  full.seek(0); EXPECT_EQ(dynamicFullState(full), dynamicState(source)); EXPECT_TRUE(full.atEnd());
  DynamicGroup reader; reader.enableNetInterpolation(0.5f);
  full.seek(0); reader.netLoad(full, {});
  EXPECT_EQ(dynamicState(reader), dynamicState(source)); EXPECT_TRUE(full.atEnd());
  for (auto const& child : reader.netElements()) { EXPECT_TRUE(child->enabled); EXPECT_EQ(child->hint, 0.5f); }
  source.setCompatibilityVersion(OpenProtocolVersion);
  NetCompatibilityRules legacy(LegacyVersion); DataStreamBuffer untouched;
  c.trace.events.clear();
  source.netStore(untouched, legacy); source.netLoad(untouched, legacy);
  EXPECT_FALSE(source.writeNetDelta(untouched, 0, legacy)); source.readNetDelta(untouched, 0.5f, legacy);
  EXPECT_TRUE(untouched.empty()); EXPECT_EQ(untouched.pos(), 0u); EXPECT_TRUE(c.trace.events.empty());
  EXPECT_EQ(dynamicState(reader), dynamicState(source));
  dynamicWire("native-full", full); c.trace.emit("rules-rejected");
}

TEST(NetDynamic, AdditionSnapshotIsLazyAndNativeReaderBlanksMissingDeltas) {
  DynamicContext c; DynamicGroup source, reader; NetElementVersion v;
  source.initNetVersion(&v); auto a = make_shared<DynamicElement>(1), b = make_shared<DynamicElement>(2);
  auto aid = source.addNetElement(a); auto bid = source.addNetElement(b);
  a->value = 41; b->value = 42;
  DataStreamBuffer delta; EXPECT_TRUE(source.writeNetDelta(delta, 0));
  delta.seek(0); EXPECT_FALSE(delta.read<bool>()); delta.seek(0);
  reader.enableNetInterpolation(0.5f); reader.readNetDelta(delta, 0.75f);
  EXPECT_EQ(dynamicState(reader), dynamicState(source)); EXPECT_TRUE(delta.atEnd());
  EXPECT_EQ(reader.getNetElement(aid)->value, 41); EXPECT_EQ(reader.getNetElement(bid)->value, 42);
  dynamicWire("lazy-additions", delta);
  v.increment(); a->writes = true; a->value = 51;
  delta.clear(); EXPECT_TRUE(source.writeNetDelta(delta, 1));
  auto ar = reader.getNetElement(aid), br = reader.getNetElement(bid);
  ar->blanks.clear(); br->blanks.clear();
  delta.seek(0); reader.readNetDelta(delta, 0.25f);
  EXPECT_EQ(ar->value, 51); EXPECT_TRUE(ar->blanks.empty());
  EXPECT_EQ(br->blanks, (std::vector<float>{0.25f})); EXPECT_TRUE(delta.atEnd());
  dynamicWire("child-delta", delta); c.trace.emit("lazy-native-reader");
}

TEST(NetDynamic, HistoryStrictFloorAtHundredAndHundredOne) {
  DynamicContext c; DynamicGroup source; NetElementVersion v; source.initNetVersion(&v);
  dynamicAdvance(v, 99); auto a = source.addNetElement(make_shared<DynamicElement>(19));
  dynamicAdvance(v, 100); source.addNetElement(make_shared<DynamicElement>(20));
  DataStreamBuffer at100; EXPECT_TRUE(source.writeNetDelta(at100, 0));
  at100.seek(0); EXPECT_FALSE(at100.read<bool>()); at100.seek(0);
  DynamicGroup reader100;
  reader100.addNetElement(make_shared<DynamicElement>(70));
  reader100.addNetElement(make_shared<DynamicElement>(71));
  reader100.addNetElement(make_shared<DynamicElement>(72));
  // RESET at version zero must survive a floor of zero (strict '<', not '<=').
  EXPECT_NO_THROW(reader100.readNetDelta(at100));
  EXPECT_EQ(dynamicState(reader100), dynamicState(source)); EXPECT_TRUE(at100.atEnd());
  dynamicAdvance(v, 101); source.removeNetElement(a);
  DataStreamBuffer below, equal;
  EXPECT_TRUE(source.writeNetDelta(below, 0)); below.seek(0); EXPECT_TRUE(below.read<bool>());
  EXPECT_EQ(dynamicFullState(below), dynamicState(source)); EXPECT_TRUE(below.atEnd());
  EXPECT_TRUE(source.writeNetDelta(equal, 1)); equal.seek(0); EXPECT_FALSE(equal.read<bool>()); equal.seek(0);
  DynamicGroup reader1; reader1.readNetDelta(equal);
  EXPECT_EQ(dynamicState(reader1), dynamicState(source)); EXPECT_TRUE(equal.atEnd());
  dynamicAdvance(v, 102); source.addNetElement(make_shared<DynamicElement>(22));
  DataStreamBuffer below2, equal2;
  EXPECT_TRUE(source.writeNetDelta(below2, 1)); below2.seek(0); EXPECT_TRUE(below2.read<bool>());
  EXPECT_EQ(dynamicFullState(below2), dynamicState(source)); EXPECT_TRUE(below2.atEnd());
  EXPECT_TRUE(source.writeNetDelta(equal2, 2)); equal2.seek(0); EXPECT_FALSE(equal2.read<bool>()); equal2.seek(0);
  DynamicGroup reader2; reader2.readNetDelta(equal2);
  EXPECT_EQ(dynamicState(reader2), dynamicState(source)); EXPECT_TRUE(equal2.atEnd());
  dynamicWire("floor100", at100); dynamicWire("floor101-below", below);
  dynamicWire("floor101-equal", equal); dynamicWire("floor102-equal", equal2);
  c.trace.emit("history-floor");
}

TEST(NetDynamic, NativeLoadFailureKeepsLoadedPrefixAndDestroysFailedChild) {
  DynamicContext c; DynamicGroup source;
  auto a = source.addNetElement(make_shared<DynamicElement>(31));
  auto b = source.addNetElement(make_shared<DynamicElement>(32));
  DataStreamBuffer full; source.netStore(full);
  // Select the second child from the actual native snapshot order.
  full.seek(0); ASSERT_EQ(full.readVlqU(), 2u);
  auto firstId = static_cast<uint32_t>(full.readVlqU());
  DataStreamBuffer first(full.read<ByteArray>()); auto firstValue = first.read<uint8_t>();
  auto failedId = static_cast<uint32_t>(full.readVlqU());
  DataStreamBuffer second(full.read<ByteArray>()); auto failedValue = second.read<uint8_t>();
  EXPECT_NE(firstId, failedId); EXPECT_TRUE((firstId == a && failedId == b) || (firstId == b && failedId == a));
  for (auto op : {"L", "I", "E"}) {
    DynamicGroup reader; NetElementVersion version; version.increment(); reader.initNetVersion(&version);
    reader.enableNetInterpolation(0.5f);
    std::weak_ptr<DynamicElement> old;
    { auto e = make_shared<DynamicElement>(90); old = e; reader.addNetElement(e); }
    c.trace.fail = op; c.trace.failValue = failedValue;
    full.seek(0); dynamicFailure(c.trace, [&] { reader.netLoad(full, {}); });
    EXPECT_TRUE(old.expired()); EXPECT_EQ(reader.netElementIds().size(), 1u);
    EXPECT_EQ(reader.getNetElement(firstId)->value, firstValue);
    EXPECT_EQ(reader.getNetElement(firstId)->version, &version);
    EXPECT_TRUE(reader.getNetElement(firstId)->enabled);
    ASSERT_GE(c.trace.events.size(), 2u);
    EXPECT_EQ(c.trace.events.back(), "caught");
    EXPECT_EQ(c.trace.events[c.trace.events.size() - 2], std::to_string(failedValue) + "X");
    EXPECT_TRUE(full.atEnd());
    c.trace.fail.clear();
    DataStreamBuffer retained; EXPECT_TRUE(reader.writeNetDelta(retained, 1));
    DynamicGroup replay; retained.seek(0); replay.readNetDelta(retained);
    EXPECT_EQ(dynamicState(replay), dynamicState(reader)); EXPECT_TRUE(retained.atEnd());
    dynamicWire(op, retained);
  }
  c.trace.emit("load-failure-prefix");
}

TEST(NetDynamic, NativeReadReadyFailureRecordsChangeBeforeChildInsertion) {
  DynamicContext c; DynamicGroup source; source.initNetVersion();
  source.addNetElement(make_shared<DynamicElement>(61));
  DataStreamBuffer ds; EXPECT_TRUE(source.writeNetDelta(ds, 0));
  DynamicGroup reader; reader.enableNetInterpolation(0.5f);
  c.trace.fail = "E"; c.trace.failValue = 61;
  ds.seek(0); dynamicFailure(c.trace, [&] { reader.readNetDelta(ds, 0.25f); });
  EXPECT_TRUE(reader.netElementIds().empty()); c.trace.fail.clear();
  // The failed addition is retained in history, but native write skips additions
  // whose ID is absent. RESET remains replayable through a second actual group.
  DataStreamBuffer replayWire; EXPECT_TRUE(reader.writeNetDelta(replayWire, 0));
  DynamicGroup replay; replayWire.seek(0); replay.readNetDelta(replayWire);
  EXPECT_TRUE(replay.netElementIds().empty()); EXPECT_TRUE(replayWire.atEnd());
  dynamicWire("read-ready-failure-history", replayWire); c.trace.emit("read-ready-failure");
}

#ifdef STAR_USE_RUST_NET_DYNAMIC
TEST(NetDynamic, OnCounterNaturalLifecycleAndHistoryRoots) {
  DynamicContext c;
  uint64_t before[SB_NET_DYNAMIC_COUNT], globalBefore[SB_NET_DYNAMIC_COUNT];
  uint64_t leavesBefore[SB_NET_DYNAMIC_OP_COUNT];
  for (uint32_t mode = 0; mode < SB_NET_DYNAMIC_COUNT; ++mode) {
    before[mode] = sb_net_dynamic_count(0, mode);
    globalBefore[mode] = sb_net_dynamic_count(1, mode);
  }
  for (uint32_t op = 0; op < SB_NET_DYNAMIC_OP_COUNT; ++op)
    leavesBefore[op] = sb_net_dynamic_count(2, op);
  DynamicGroup g; NetElementVersion v; g.initNetVersion(&v);
  auto id = g.addNetElement(make_shared<DynamicElement>(1)); // disabled ready
  g.enableNetInterpolation(0.5f);
  g.addNetElement(make_shared<DynamicElement>(2)); // enabled ready
  g.tickNetInterpolation(0.25f); g.blankNetDelta(0.5f);
  g.disableNetInterpolation(); g.blankNetDelta(0.5f);
  g.initNetVersion(&v); // current-child init/addition leaves, not ready
  DataStreamBuffer full; g.netStore(full);
  DynamicGroup loaded; full.seek(0); loaded.netLoad(full, {});
  EXPECT_EQ(dynamicState(loaded), dynamicState(g));
  dynamicAdvance(v, 101); g.removeNetElement(id); // native floor and real pruning
  g.clearNetElements(); // owned snapshot calls the ordinary remove path
  for (uint32_t mode = 0; mode < SB_NET_DYNAMIC_COUNT; ++mode) {
    EXPECT_GE(sb_net_dynamic_count(0, mode) - before[mode], uint64_t(1)) << mode;
    EXPECT_GE(sb_net_dynamic_count(1, mode) - globalBefore[mode], uint64_t(1)) << mode;
  }
  for (uint32_t op = 0; op < SB_NET_DYNAMIC_OP_COUNT; ++op)
    EXPECT_GE(sb_net_dynamic_count(2, op) - leavesBefore[op], uint64_t(1)) << op;
  EXPECT_EQ(sb_net_dynamic_count(0, SB_NET_DYNAMIC_COUNT), uint64_t(0));
  EXPECT_EQ(sb_net_dynamic_count(2, SB_NET_DYNAMIC_OP_COUNT), uint64_t(0));
  EXPECT_EQ(sb_net_dynamic_count(3, 0), uint64_t(0));
  // ON-only observations deliberately do not enter the shared native trace set.
  std::cout << "NET_DYNAMIC_DIAGNOSTIC natural-roots " << SB_NET_DYNAMIC_COUNT
            << " attempted-leaves " << SB_NET_DYNAMIC_OP_COUNT << '\n';
}
#endif
