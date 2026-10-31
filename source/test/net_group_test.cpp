#include "StarNetElementGroup.hpp"

#include "gtest/gtest.h"

#include <exception>
#include <functional>
#include <iostream>
#include <string>
#include <type_traits>

#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetGroup.h"
#endif

using namespace Star;

namespace {
static_assert(!std::is_copy_constructible<NetElementGroup>::value, "group owns noncopyable state");
static_assert(!std::is_copy_assignable<NetElementGroup>::value, "group owns noncopyable state");
struct GroupMarker : std::exception {};
struct DerivedGroupMarker : GroupMarker {};
struct GroupTrace {
  std::string events;
  std::exception_ptr error = std::make_exception_ptr(DerivedGroupMarker{});
  void log(std::string const& s) { events += s + ","; }
  void emit(char const* name) const { std::cout << "NET_GROUP_TRACE " << name << ' ' << events << '\n'; }
};

struct ProbeElement : NetElement {
  GroupTrace& trace;
  int id;
  uint8_t byte;
  bool writes = true;
  bool interpolation = false;
  NetElementVersion const* version = nullptr;
  std::string fail;
  std::function<void()> initializer;
  ProbeElement(GroupTrace& t, int i) : trace(t), id(i), byte(static_cast<uint8_t>(i)) {}
  void call(char const* op, std::string args = {}) const {
    trace.log(std::to_string(id) + op + args);
    if (fail == op) std::rethrow_exception(trace.error);
  }
  void initNetVersion(NetElementVersion const* v) override {
    version = v;
    call("I", v ? std::to_string(v->current()) : "null");
    if (initializer) initializer();
  }
  void netStore(DataStream& ds, NetCompatibilityRules rules) const override {
    ds.write(byte);
    call("S", std::to_string(rules.version()));
  }
  void netLoad(DataStream& ds, NetCompatibilityRules rules) override {
    byte = ds.read<uint8_t>();
    call("L", std::to_string(rules.version()));
  }
  void enableNetInterpolation(float hint) override {
    EXPECT_TRUE(hint == 0.25f || hint == 0.5f);
    interpolation = true;
    call("E", hint == 0.5f ? "0.5" : "0.25");
  }
  void disableNetInterpolation() override { interpolation = false; call("D"); }
  void tickNetInterpolation(float dt) override { EXPECT_EQ(dt, 0.25f); call("T"); }
  bool writeNetDelta(DataStream& ds, uint64_t from, NetCompatibilityRules rules) const override {
    ds.write(byte);
    call("W", std::to_string(from) + "/" + std::to_string(rules.version()) + "/"
        + std::to_string(ds.streamCompatibilityVersion()));
    return writes;
  }
  void readNetDelta(DataStream& ds, float time, NetCompatibilityRules rules) override {
    EXPECT_EQ(time, 0.5f);
    byte = ds.read<uint8_t>();
    call("R", std::to_string(rules.version()));
  }
  void blankNetDelta(float time) override { EXPECT_EQ(time, 0.5f); call("B"); }
};

ByteArray groupBytes(std::initializer_list<uint8_t> bytes) {
  DataStreamBuffer ds;
  for (auto b : bytes) ds.write(b);
  return ds.takeData();
}
void groupWire(char const* name, DataStreamBuffer const& ds) {
  static char const hex[] = "0123456789abcdef";
  std::string s;
  for (size_t i = 0; i < ds.size(); ++i) {
    auto b = static_cast<unsigned char>(ds.ptr()[i]);
    s += hex[b >> 4]; s += hex[b & 15];
  }
  std::cout << "NET_GROUP_TRACE " << name << ' ' << s << '\n';
}
template <typename F> void groupFailure(GroupTrace& trace, F f) {
  try { f(); FAIL() << "expected original derived exception"; }
  catch (DerivedGroupMarker const&) {
    EXPECT_EQ(std::current_exception(), trace.error);
    trace.log("caught");
  }
}
struct ThrowOutput : DataStreamBuffer {
  GroupTrace& trace;
  size_t calls = 0;
  explicit ThrowOutput(GroupTrace& t) : trace(t) {}
  void writeData(char const* p, size_t n) override {
    DataStreamBuffer::writeData(p, n);
    if (++calls == 2) std::rethrow_exception(trace.error);
  }
};
}

TEST(NetGroup, EmptyAndRulesRejectBeforeCallsOrStream) {
  GroupTrace t;
  NetElementGroup g;
  DataStreamBuffer ds;
  EXPECT_FALSE(g.writeNetDelta(ds, 9));
  try { g.readNetDelta(ds, 0.5f); FAIL() << "expected empty-group error"; }
  catch (IOException const& e) {
    EXPECT_NE(std::string(e.what()).find("readNetDelta called on empty NetElementGroup"), std::string::npos);
  }
  g.netStore(ds); g.netLoad(ds, {});
  EXPECT_TRUE(ds.empty());
  EXPECT_EQ(NetCompatibilityRules().version(), OpenProtocolVersion);
  ProbeElement a(t, 1);
  g.addNetElement(&a);
  g.setCompatibilityVersion(OpenProtocolVersion);
  t.events.clear();
  NetCompatibilityRules legacy(LegacyVersion);
  g.netStore(ds, legacy); g.netLoad(ds, legacy);
  EXPECT_FALSE(g.writeNetDelta(ds, 9, legacy));
  g.readNetDelta(ds, 0.5f, legacy);
  EXPECT_TRUE(ds.empty()); EXPECT_EQ(ds.pos(), 0u); EXPECT_TRUE(t.events.empty());
  g.tickNetInterpolation(0.25f); g.blankNetDelta(0.5f);
  EXPECT_TRUE(t.events.empty());
  groupWire("rejected", ds); t.emit("rejected-calls");
}

TEST(NetGroup, VersionSharingAddOrderAndFailedAddNotAppended) {
  GroupTrace t;
  NetElementGroup g;
  NetElementVersion version;
  version.increment(); version.increment();
  g.initNetVersion(&version); g.enableNetInterpolation(0.5f);
  ProbeElement a(t, 1), b(t, 2), c(t, 3);
  a.initializer = [&] { EXPECT_EQ(g.netVersion(), &version); EXPECT_TRUE(g.netInterpolationEnabled()); };
  g.addNetElement(&a);
  b.fail = "I"; groupFailure(t, [&] { g.addNetElement(&b); });
  c.fail = "E"; groupFailure(t, [&] { g.addNetElement(&c); });
  EXPECT_EQ(t.events, "1I2,1E0.5,2I2,caught,3I2,3E0.5,caught,");
  EXPECT_EQ(a.version, &version); EXPECT_EQ(b.version, &version); EXPECT_EQ(c.version, &version);
  DataStreamBuffer ds;
  EXPECT_TRUE(g.writeNetDelta(ds, 9));
  EXPECT_EQ(ds.data(), groupBytes({1})); // Failed adds did not alter the cached count.
  t.emit("add-failures"); groupWire("add-failure-wire", ds);
  version.increment(); t.events.clear(); g.initNetVersion(&version);
  EXPECT_EQ(t.events, "1I3,");
}

TEST(NetGroup, InitializerChangesCompatibilityBeforeCountAndNonpropagatingAdd) {
  GroupTrace t;
  NetElementGroup g;
  ProbeElement a(t, 1), b(t, 2), c(t, 3);
  NetElementVersion v;
  v.increment();
  g.initNetVersion(&v); g.enableNetInterpolation(0.5f);
  g.addNetElement(&a);
  b.initializer = [&] { b.setCompatibilityVersion(OpenProtocolVersion); };
  g.addNetElement(&b, false);
  EXPECT_FALSE(b.interpolation); EXPECT_EQ(b.version, &v);
  EXPECT_EQ(t.events, "1I1,1E0.5,2I1,");
  DataStreamBuffer ds;
  NetCompatibilityRules legacy(LegacyVersion);
  EXPECT_TRUE(g.writeNetDelta(ds, 9, legacy));
  EXPECT_EQ(ds.data(), groupBytes({1}));
  c.setCompatibilityVersion(OpenProtocolVersion);
  c.initializer = [&] { c.setCompatibilityVersion(LegacyVersion); };
  g.addNetElement(&c);
  EXPECT_TRUE(c.interpolation);
  ds.clear(); EXPECT_TRUE(g.writeNetDelta(ds, 9, legacy));
  EXPECT_EQ(ds.data(), groupBytes({1, 1, 2, 3, 0}));
  groupWire("initializer-count-wire", ds); t.emit("initializer-count-calls");
}

TEST(NetGroup, InterpolationPropagationAndClearPreservesParentState) {
  GroupTrace t;
  NetElementGroup g;
  NetElementVersion v;
  g.initNetVersion(&v);
  ProbeElement a(t, 1), b(t, 2), c(t, 3);
  g.addNetElement(&a); g.addNetElement(&b, false);
  t.events.clear();
  g.enableNetInterpolation(0.25f); g.tickNetInterpolation(0.25f); g.blankNetDelta(0.5f);
  g.disableNetInterpolation(); g.tickNetInterpolation(0.25f); g.blankNetDelta(0.5f);
  EXPECT_EQ(t.events, "1E0.25,1T,2T,1B,2B,1D,");
  EXPECT_FALSE(b.interpolation); EXPECT_EQ(g.netExtrapolationHint(), 0.0f);
  g.enableNetInterpolation(0.5f); g.clearNetElements();
  EXPECT_TRUE(g.netInterpolationEnabled()); EXPECT_EQ(g.netExtrapolationHint(), 0.5f);
  EXPECT_EQ(g.netVersion(), &v);
  g.addNetElement(&c);
  EXPECT_EQ(c.version, &v); EXPECT_TRUE(c.interpolation);
  DataStreamBuffer ds;
  EXPECT_TRUE(g.writeNetDelta(ds, 9)); EXPECT_EQ(ds.data(), groupBytes({3}));
  t.emit("interpolation-clear");
}

TEST(NetGroup, FullStoreLoadFilterAndExactExceptionPrefixes) {
  GroupTrace t;
  NetElementGroup g;
  ProbeElement a(t, 1), b(t, 2), c(t, 3);
  b.setCompatibilityVersion(OpenProtocolVersion);
  g.addNetElement(&a); g.addNetElement(&b); g.addNetElement(&c);
  NetCompatibilityRules legacy(LegacyVersion);
  DataStreamBuffer ds;
  g.netStore(ds, legacy); EXPECT_EQ(ds.data(), groupBytes({1, 3}));
  ds.seek(0); a.byte = c.byte = 0; g.netLoad(ds, legacy);
  EXPECT_EQ(a.byte, 1); EXPECT_EQ(c.byte, 3); EXPECT_EQ(ds.pos(), 2u);
  a.fail = "S"; ds.clear(); groupFailure(t, [&] { g.netStore(ds, legacy); });
  EXPECT_EQ(ds.data(), groupBytes({1})); a.fail.clear();
  DataStreamBuffer input(groupBytes({11, 33}));
  c.fail = "L"; groupFailure(t, [&] { g.netLoad(input, legacy); });
  EXPECT_EQ(a.byte, 11); EXPECT_EQ(c.byte, 33); EXPECT_EQ(input.pos(), 2u);
  t.emit("full-prefix"); groupWire("full-store-prefix", ds);
}

TEST(NetGroup, DefaultLegacyAndUncachedFutureRules) {
  GroupTrace t;
  NetElementGroup g;
  ProbeElement a(t, 1), b(t, 2);
  b.setCompatibilityVersion(OpenProtocolVersion);
  g.addNetElement(&a); g.addNetElement(&b);
  DataStreamBuffer ds;
  EXPECT_TRUE(g.writeNetDelta(ds, 9, NetCompatibilityRules(LegacyVersion)));
  EXPECT_EQ(ds.data(), groupBytes({1})); ds.clear();
  EXPECT_TRUE(g.writeNetDelta(ds, 9));
  EXPECT_EQ(ds.data(), groupBytes({1, 1, 2, 2, 0}));
  DataStreamBuffer parse(ds.data());
  EXPECT_EQ(parse.readVlqU(), 1u); EXPECT_EQ(parse.readBytes(1), groupBytes({1}));
  EXPECT_EQ(parse.readVlqU(), 2u); EXPECT_EQ(parse.readBytes(1), groupBytes({2}));
  EXPECT_EQ(parse.readVlqU(), 0u); EXPECT_TRUE(parse.atEnd());
  groupWire("default-multi", ds); ds.clear();
  NetCompatibilityRules future(static_cast<VersionNumber>(CurrentStreamVersion + 1));
  EXPECT_TRUE(g.writeNetDelta(ds, 9, future));
  EXPECT_EQ(ds.data(), groupBytes({1, 1, 2, 2, 0}));
  t.emit("rule-stream-versions");
}

TEST(NetGroup, MissingAndStaleOneCountsAreNotRecomputed) {
  GroupTrace t;
  NetCompatibilityRules legacy(LegacyVersion);
  NetElementGroup zero;
  ProbeElement a(t, 1);
  a.setCompatibilityVersion(OpenProtocolVersion); zero.addNetElement(&a);
  DataStreamBuffer ds;
  t.events.clear();
  EXPECT_FALSE(zero.writeNetDelta(ds, 9, legacy));
  zero.readNetDelta(ds, 0.5f, legacy);
  EXPECT_TRUE(t.events.empty()); EXPECT_TRUE(ds.empty());
  // No compatible add creates no map entry, NOT a cached zero. The missing
  // legacy key falls back to the full native list size on every operation.
  a.setCompatibilityVersion(LegacyVersion);
  EXPECT_TRUE(zero.writeNetDelta(ds, 9, legacy));
  EXPECT_EQ(ds.data(), groupBytes({1})); ds.clear();
  NetElementGroup one;
  ProbeElement b(t, 2), c(t, 3);
  b.setCompatibilityVersion(OpenProtocolVersion);
  one.addNetElement(&b); one.addNetElement(&c);
  b.setCompatibilityVersion(LegacyVersion);
  EXPECT_TRUE(one.writeNetDelta(ds, 9, legacy));
  EXPECT_EQ(ds.data(), groupBytes({2})); // First compatible, not the originally counted child.
  DataStreamBuffer input(groupBytes({42, 77}));
  one.readNetDelta(input, 0.5f, legacy);
  EXPECT_EQ(b.byte, 42); EXPECT_EQ(c.byte, 3); EXPECT_EQ(input.pos(), 1u);
  c.setCompatibilityVersion(OpenProtocolVersion); b.setCompatibilityVersion(OpenProtocolVersion);
  ds.clear(); EXPECT_FALSE(one.writeNetDelta(ds, 9, legacy)); EXPECT_TRUE(ds.empty());
  DataStreamBuffer untouched(groupBytes({88}));
  one.readNetDelta(untouched, 0.5f, legacy); EXPECT_EQ(untouched.pos(), 0u);
  t.emit("missing-and-stale-one");
}

TEST(NetGroup, StaleMultiCountPermitsOneExtraCompatibleChild) {
  GroupTrace t;
  NetElementGroup g;
  ProbeElement a(t, 1), b(t, 2), c(t, 3), d(t, 4);
  NetCompatibilityRules legacy(LegacyVersion);
  c.setCompatibilityVersion(OpenProtocolVersion); d.setCompatibilityVersion(OpenProtocolVersion);
  g.addNetElement(&a); g.addNetElement(&b); g.addNetElement(&c); g.addNetElement(&d);
  c.setCompatibilityVersion(LegacyVersion); d.setCompatibilityVersion(LegacyVersion);
  t.events.clear(); DataStreamBuffer ds;
  EXPECT_TRUE(g.writeNetDelta(ds, 9, legacy));
  EXPECT_EQ(ds.data(), groupBytes({1, 1, 2, 2, 3, 3, 0}));
  EXPECT_EQ(t.events, "1W9/0/0,2W9/0/0,3W9/0/0,");
  t.emit("stale-extra"); groupWire("stale-extra-wire", ds);
}

TEST(NetGroup, FalseWritesPersistAcrossChildrenCallsAndClear) {
  GroupTrace t;
  NetElementGroup g;
  ProbeElement a(t, 1), b(t, 2);
  g.addNetElement(&a); g.addNetElement(&b);
  a.writes = false;
  DataStreamBuffer ds;
  EXPECT_TRUE(g.writeNetDelta(ds, 9)); EXPECT_EQ(ds.data(), groupBytes({2, 1, 2, 0}));
  groupWire("false-before-true", ds); ds.clear(); b.writes = false;
  EXPECT_FALSE(g.writeNetDelta(ds, 9)); EXPECT_TRUE(ds.empty());
  // clear removes children/counts, not the partially accumulated native buffer.
  g.clearNetElements(); g.addNetElement(&a); g.addNetElement(&b); b.writes = true;
  EXPECT_TRUE(g.writeNetDelta(ds, 9));
  EXPECT_EQ(ds.data(), groupBytes({2, 1, 2, 1, 2, 0}));
  groupWire("false-across-clear", ds); t.emit("false-calls");
}

TEST(NetGroup, ChildAndOutputFailuresRetainNativeBufferForRetry) {
  GroupTrace t;
  NetElementGroup g;
  ProbeElement a(t, 1), b(t, 2);
  g.addNetElement(&a); g.addNetElement(&b);
  a.fail = "W"; DataStreamBuffer ds;
  groupFailure(t, [&] { g.writeNetDelta(ds, 9); }); EXPECT_TRUE(ds.empty());
  a.fail.clear(); EXPECT_TRUE(g.writeNetDelta(ds, 9));
  EXPECT_EQ(ds.data(), groupBytes({1, 1, 1, 2, 2, 0}));
  groupWire("child-failure-retry", ds);
  ThrowOutput output(t);
  groupFailure(t, [&] { g.writeNetDelta(output, 9); });
  EXPECT_EQ(output.data(), groupBytes({1, 1}));
  ds.clear(); EXPECT_TRUE(g.writeNetDelta(ds, 9));
  EXPECT_EQ(ds.data(), groupBytes({1, 1, 1, 2, 2, 0}));
  groupWire("output-failure-visible", output); groupWire("output-failure-retry", ds);
  t.emit("write-failures");
}

TEST(NetGroup, IndexedReadsBlankFilteredOffsetsAndLeaveTrailingBytes) {
  GroupTrace t;
  NetElementGroup g;
  ProbeElement a(t, 1), filtered(t, 2), c(t, 3);
  filtered.setCompatibilityVersion(OpenProtocolVersion);
  g.addNetElement(&a, false); g.addNetElement(&filtered); g.addNetElement(&c, false);
  g.enableNetInterpolation(0.5f); t.events.clear();
  NetCompatibilityRules legacy(LegacyVersion);
  DataStreamBuffer ds(groupBytes({2, 33, 0, 99}));
  g.readNetDelta(ds, 0.5f, legacy);
  EXPECT_EQ(t.events, "1B,3R0,"); EXPECT_EQ(c.byte, 33); EXPECT_EQ(filtered.byte, 2);
  EXPECT_EQ(ds.pos(), 3u); EXPECT_EQ(ds.read<uint8_t>(), 99);
  t.events.clear(); DataStreamBuffer zero(groupBytes({0, 88}));
  g.readNetDelta(zero, 0.5f, legacy);
  EXPECT_EQ(t.events, "1B,3B,"); EXPECT_EQ(zero.pos(), 1u);
  t.events.clear(); DataStreamBuffer high(groupBytes({9, 77}));
  g.readNetDelta(high, 0.5f, legacy);
  EXPECT_EQ(t.events, "1B,3B,"); EXPECT_EQ(high.pos(), 1u);
  t.emit("high-index-blanks");
  g.disableNetInterpolation(); t.events.clear();
  DataStreamBuffer disabled(groupBytes({0, 66})); g.readNetDelta(disabled, 0.5f, legacy);
  EXPECT_TRUE(t.events.empty()); EXPECT_EQ(disabled.pos(), 1u);
}

TEST(NetGroup, DuplicateOutOfOrderAndEofRetainPriorChildLoads) {
  for (bool duplicate : {true, false}) {
    GroupTrace t; NetElementGroup g;
    ProbeElement a(t, 1), b(t, 2), c(t, 3);
    g.addNetElement(&a); g.addNetElement(&b); g.addNetElement(&c);
    DataStreamBuffer ds(duplicate ? groupBytes({1, 11, 1, 99}) : groupBytes({2, 22, 1, 99}));
    try { g.readNetDelta(ds, 0.5f); FAIL() << "expected ordered-index error"; }
    catch (IOException const& e) {
      EXPECT_NE(std::string(e.what()).find("group indexes out of order in NetElementGroup::readNetDelta"), std::string::npos);
    }
    EXPECT_EQ(ds.pos(), 3u); EXPECT_EQ(duplicate ? a.byte : b.byte, duplicate ? 11 : 22);
    t.emit(duplicate ? "duplicate-prefix" : "unordered-prefix");
  }
  GroupTrace t; NetElementGroup g; ProbeElement a(t, 1), b(t, 2);
  g.addNetElement(&a); g.addNetElement(&b);
  DataStreamBuffer eof(groupBytes({1, 44}));
  EXPECT_THROW(g.readNetDelta(eof, 0.5f), IOException);
  EXPECT_EQ(a.byte, 44); EXPECT_EQ(b.byte, 2); EXPECT_EQ(eof.pos(), 2u);
  t.emit("index-eof-prefix");
}

TEST(NetGroup, CallbackFailuresPreservePrefixAndParentFlags) {
  GroupTrace t; NetElementGroup g; ProbeElement a(t, 1), b(t, 2);
  g.addNetElement(&a); g.addNetElement(&b);
  NetElementVersion v; v.increment(); b.fail = "I";
  groupFailure(t, [&] { g.initNetVersion(&v); });
  EXPECT_EQ(g.netVersion(), &v); EXPECT_EQ(a.version, &v); EXPECT_EQ(b.version, &v);
  b.fail = "E"; groupFailure(t, [&] { g.enableNetInterpolation(0.5f); });
  EXPECT_TRUE(g.netInterpolationEnabled()); EXPECT_EQ(g.netExtrapolationHint(), 0.5f);
  b.fail = "D"; groupFailure(t, [&] { g.disableNetInterpolation(); });
  EXPECT_FALSE(g.netInterpolationEnabled()); EXPECT_EQ(g.netExtrapolationHint(), 0.0f);
  b.fail.clear(); g.enableNetInterpolation(0.5f);
  a.fail = "T"; groupFailure(t, [&] { g.tickNetInterpolation(0.25f); });
  a.fail = "B"; groupFailure(t, [&] { g.blankNetDelta(0.5f); });
  a.fail = "R"; DataStreamBuffer ds(groupBytes({1, 55, 0}));
  groupFailure(t, [&] { g.readNetDelta(ds, 0.5f); });
  EXPECT_EQ(a.byte, 55); EXPECT_EQ(ds.pos(), 2u);
  t.emit("callback-failures");
}

TEST(NetGroup, NestedNativeGroupsComposeAllOperationsAndWire) {
  GroupTrace t; NetElementGroup outer, inner;
  ProbeElement a(t, 1), b(t, 2), c(t, 3);
  inner.addNetElement(&a); inner.addNetElement(&b);
  outer.addNetElement(&inner); outer.addNetElement(&c);
  NetElementVersion v; v.increment(); outer.initNetVersion(&v);
  EXPECT_EQ(a.version, &v); EXPECT_EQ(b.version, &v); EXPECT_EQ(c.version, &v);
  outer.enableNetInterpolation(0.5f); outer.tickNetInterpolation(0.25f); outer.blankNetDelta(0.5f);
  DataStreamBuffer full; outer.netStore(full); EXPECT_EQ(full.data(), groupBytes({1, 2, 3}));
  full.seek(0); outer.netLoad(full, {});
  DataStreamBuffer ds; EXPECT_TRUE(outer.writeNetDelta(ds, 9));
  EXPECT_EQ(ds.data(), groupBytes({1, 1, 1, 2, 2, 0, 2, 3, 0}));
  ds.seek(0); outer.readNetDelta(ds, 0.5f); EXPECT_TRUE(ds.atEnd());
  outer.disableNetInterpolation();
  groupWire("nested-wire", ds); t.emit("nested-calls");
}

#ifdef STAR_USE_RUST_NET_GROUP
TEST(NetGroup, OnCounterNaturalNativeRoots) {
  GroupTrace t;
  NetElementGroup g;
  ProbeElement a(t, 1);
  uint64_t before[SB_NET_GROUP_COUNT], globalBefore[SB_NET_GROUP_COUNT];
  for (uint32_t mode = 0; mode < SB_NET_GROUP_COUNT; ++mode) {
    before[mode] = sb_net_group_count(0, mode);
    globalBefore[mode] = sb_net_group_count(1, mode);
  }
  g.addNetElement(&a);
  NetElementVersion v;
  g.initNetVersion(&v);
  g.enableNetInterpolation(0.5f);
  g.tickNetInterpolation(0.25f);
  g.blankNetDelta(0.5f);
  g.disableNetInterpolation();
  DataStreamBuffer ds;
  g.netStore(ds); ds.seek(0); g.netLoad(ds, {});
  ds.clear(); EXPECT_TRUE(g.writeNetDelta(ds, 9));
  ds.seek(0); g.readNetDelta(ds, 0.5f);
  EXPECT_TRUE(ds.atEnd());
  for (uint32_t mode = 0; mode < SB_NET_GROUP_COUNT; ++mode) {
    EXPECT_EQ(sb_net_group_count(0, mode) - before[mode], uint64_t(1)) << mode;
    EXPECT_GE(sb_net_group_count(1, mode) - globalBefore[mode], uint64_t(1)) << mode;
  }
  EXPECT_EQ(sb_net_group_count(0, SB_NET_GROUP_COUNT), uint64_t(0));
  EXPECT_EQ(sb_net_group_count(3, 0), uint64_t(0));
  // Candidate diagnostics deliberately never share the native trace namespace.
  std::cout << "NET_GROUP_DIAGNOSTIC natural-roots " << SB_NET_GROUP_COUNT << '\n';
}
#endif
