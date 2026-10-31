// DataStreamBuffer is supplied by the native include context, not Top itself.
#include "StarDataStreamDevices.hpp"
#include "StarNetElementTop.hpp"

#include "gtest/gtest.h"

#include <exception>
#include <functional>
#include <iostream>
#include <string>
#include <vector>

using namespace Star;

namespace {
struct TopMarker : std::exception {};
struct DerivedTopMarker : TopMarker {};

ByteArray topBytes(std::initializer_list<uint8_t> bytes) {
  DataStreamBuffer ds;
  for (auto byte : bytes) ds.write(byte);
  return ds.takeData();
}

std::string topHex(ByteArray const& data) {
  static char const hex[] = "0123456789abcdef";
  std::string result;
  for (size_t i = 0; i < data.size(); ++i) {
    auto byte = static_cast<unsigned char>(data[i]);
    result += hex[byte >> 4];
    result += hex[byte & 15];
  }
  return result;
}

unsigned topStreamVersion(NetCompatibilityRules rules) {
  DataStreamBuffer ds;
  ds.setStreamCompatibilityVersion(rules);
  return ds.streamCompatibilityVersion();
}

struct TopProbe : NetElement {
  NetElementVersion const* version = nullptr;
  mutable std::string events;
  mutable ByteArray prefix;
  mutable uint64_t observedVersion = 0;
  mutable uint64_t observedFrom = 0;
  mutable unsigned observedStream = 0;
  mutable VersionNumber observedRules = AnyVersion;
  mutable bool observedAdmin = false;
  float observedTime = -1.0f;
  uint8_t value = 0x2a;
  bool writes = true;
  std::string fail;
  std::exception_ptr error = std::make_exception_ptr(DerivedTopMarker{});
  mutable std::function<void()> childWrite;

  void call(char const* op) const {
    events += op;
    observedVersion = version->current();
    if (fail == op) std::rethrow_exception(error);
  }
  void observe(DataStream& ds, NetCompatibilityRules rules) const {
    observedRules = rules.version();
    observedAdmin = rules.isAdmin();
    observedStream = ds.streamCompatibilityVersion();
    prefix = dynamic_cast<DataStreamBuffer&>(ds).data();
  }
  void initNetVersion(NetElementVersion const* v) override {
    version = v;
    call("I");
  }
  void netStore(DataStream& ds, NetCompatibilityRules rules) const override {
    ds.write(value);
    observe(ds, rules);
    call("S");
    if (childWrite) childWrite();
  }
  bool writeNetDelta(DataStream& ds, uint64_t from, NetCompatibilityRules rules) const override {
    observedFrom = from;
    ds.write(value);
    observe(ds, rules);
    call("W");
    if (childWrite) childWrite();
    return writes;
  }
  void netLoad(DataStream& ds, NetCompatibilityRules rules) override {
    value = ds.read<uint8_t>();
    observe(ds, rules);
    call("L");
  }
  void readNetDelta(DataStream& ds, float time, NetCompatibilityRules rules) override {
    observedTime = time;
    value = ds.read<uint8_t>();
    observe(ds, rules);
    call("R");
  }
  void blankNetDelta(float time) override {
    observedTime = time;
    call("B");
  }
  void emit(char const* name) const {
    std::cout << "NET_TOP_TRACE " << name << ' ' << events << '/' << topHex(prefix)
        << '/' << version->current() << '/' << observedVersion << '/' << observedFrom
        << '/' << observedRules << '/' << observedStream << '/' << observedAdmin
        << '/' << observedTime << '/' << unsigned(value) << '\n';
  }
};
using Top = NetElementTop<TopProbe>;

// Top's native mixin also accepts non-NetElement bases. Do not replace the
// original overloaded ! condition with direct conversion to bool.
struct ProxyTopBase {
  TopProbe probe;
  struct Result {
    TopProbe* probe;
    operator bool() const = delete;
    bool operator!() const { return false; }
    ~Result() { const_cast<NetElementVersion*>(probe->version)->increment(); }
  };
  void initNetVersion(NetElementVersion const* v) { probe.initNetVersion(v); }
  void netStore(DataStream& ds, NetCompatibilityRules r) { probe.netStore(ds, r); }
  Result writeNetDelta(DataStream& ds, uint64_t from, NetCompatibilityRules r) {
    probe.writeNetDelta(ds, from, r);
    return {&probe};
  }
  void netLoad(DataStream& ds, NetCompatibilityRules r) { probe.netLoad(ds, r); }
  void readNetDelta(DataStream& ds, float t, NetCompatibilityRules r) { probe.readNetDelta(ds, t, r); }
  void blankNetDelta(float t) { probe.blankNetDelta(t); }
  bool checkWithRules(NetCompatibilityRules const& r) const { return probe.checkWithRules(r); }
};

struct OverrideTop : Top {
  int overrides = 0;
  void initNetVersion(NetElementVersion const*) override { ++overrides; }
  void netStore(DataStream&, NetCompatibilityRules) const override {
    ADD_FAILURE() << "virtual netStore must be bypassed";
  }
  void netLoad(DataStream&, NetCompatibilityRules) override { ++overrides; }
  bool writeNetDelta(DataStream&, uint64_t, NetCompatibilityRules) const override {
    ADD_FAILURE() << "virtual writeNetDelta must be bypassed";
    return false;
  }
  void readNetDelta(DataStream&, float, NetCompatibilityRules) override { ++overrides; }
  void blankNetDelta(float) override { ++overrides; }
};
}

TEST(NetTop, NativeNegationProxyEndsBeforeBracedReturnVersion) {
  NetElementTop<ProxyTopBase> top;
  top.probe.writes = false; // overloaded !, not the underlying bool, selects data.
  auto result = top.writeNetState(1);
  EXPECT_EQ(result.first, topBytes({0, 0x2a}));
  EXPECT_EQ(result.second, 2u); // proxy destructor increment precedes return increment.
  EXPECT_EQ(top.probe.version->current(), 2u);
  top.probe.emit("negation-proxy");
}

TEST(NetTop, ConstructorBindsNativeVersion) {
  Top a, b;
  ASSERT_NE(a.version, nullptr);
  ASSERT_NE(b.version, nullptr);
  EXPECT_NE(a.version, b.version);
  EXPECT_EQ(a.version->current(), 0u);
  EXPECT_EQ(b.version->current(), 0u);
  EXPECT_EQ(a.events, "I");
  a.writeNetState();
  EXPECT_EQ(a.version->current(), 1u);
  EXPECT_EQ(b.version->current(), 0u);
  a.emit("constructor-a");
  b.emit("constructor-b");
}

TEST(NetTop, FullMarkerStoreThenNativePreincrement) {
  Top top;
  NetCompatibilityRules rules(LegacyVersion);
  rules.setIsAdmin(true);
  auto first = top.writeNetState(0, rules);
  EXPECT_EQ(first.first, topBytes({1, 0x2a}));
  EXPECT_EQ(first.second, 1u); // NetElementVersion::increment returns ++m_version.
  EXPECT_EQ(top.observedVersion, 0u);
  EXPECT_EQ(top.events, "IS");
  EXPECT_EQ(top.observedRules, rules.version());
  EXPECT_TRUE(top.observedAdmin);
  EXPECT_EQ(top.observedStream, topStreamVersion(rules));
  auto second = top.writeNetState(0, rules);
  EXPECT_EQ(second.first, first.first);
  EXPECT_EQ(second.second, 2u);
  EXPECT_EQ(top.observedVersion, 1u);
  EXPECT_EQ(top.version->current(), 2u);
  top.emit("full");
}

TEST(NetTop, FalseDeltaDiscardsWrittenBytesAndReturnsCurrentWithoutIncrement) {
  Top top;
  top.writes = false;
  auto initial = top.writeNetState(71);
  EXPECT_TRUE(initial.first.empty());
  EXPECT_EQ(initial.second, 0u);
  EXPECT_EQ(top.prefix, topBytes({0, 0x2a}));
  top.writeNetState();
  auto result = top.writeNetState(99);
  EXPECT_TRUE(result.first.empty());
  EXPECT_EQ(result.second, 1u);
  EXPECT_EQ(top.version->current(), 1u);
  EXPECT_EQ(top.observedVersion, 1u);
  EXPECT_EQ(top.observedFrom, 99u);
  EXPECT_EQ(top.events, "IWSW");
  top.emit("false-delta");
}

TEST(NetTop, TrueDeltaMarkerRulesAndVersion) {
  Top top;
  NetCompatibilityRules rules(LegacyVersion);
  rules.setIsAdmin(true);
  auto result = top.writeNetState(57, rules);
  EXPECT_EQ(result.first, topBytes({0, 0x2a}));
  EXPECT_EQ(result.second, 1u);
  EXPECT_EQ(top.version->current(), 1u);
  EXPECT_EQ(top.observedVersion, 0u);
  EXPECT_EQ(top.observedFrom, 57u);
  EXPECT_EQ(top.observedRules, rules.version());
  EXPECT_TRUE(top.observedAdmin);
  EXPECT_EQ(top.observedStream, topStreamVersion(rules));
  EXPECT_EQ(top.events, "IW");
  top.emit("true-delta");
}

TEST(NetTop, EmptyReadAlwaysBlanksRegardlessOfCompatibility) {
  Top top;
  top.setCompatibilityVersion(OpenProtocolVersion);
  top.readNetState(ByteArray(), 0.5f, NetCompatibilityRules(LegacyVersion));
  EXPECT_EQ(top.events, "IB");
  EXPECT_EQ(top.observedTime, 0.5f);
  top.readNetState(ByteArray(), 0.25f);
  EXPECT_EQ(top.events, "IBB");
  EXPECT_EQ(top.observedTime, 0.25f);
  EXPECT_EQ(top.version->current(), 0u);
  top.emit("blank");
}

TEST(NetTop, FullReadIgnoresInterpolationAndCallsLoadDespiteRulesRejection) {
  Top top;
  top.setCompatibilityVersion(OpenProtocolVersion);
  NetCompatibilityRules rules(LegacyVersion);
  rules.setIsAdmin(true);
  top.readNetState(topBytes({1, 0x37}), 0.5f, rules);
  EXPECT_EQ(top.events, "IL");
  EXPECT_EQ(top.value, 0x37);
  EXPECT_EQ(top.observedTime, -1.0f);
  EXPECT_EQ(top.observedRules, rules.version());
  EXPECT_TRUE(top.observedAdmin);
  EXPECT_EQ(top.observedStream, topStreamVersion(rules));
  EXPECT_EQ(top.version->current(), 0u);
  top.emit("load");
}

TEST(NetTop, DeltaReadPassesInterpolationRulesAndStreamCompatibility) {
  Top top;
  top.setCompatibilityVersion(OpenProtocolVersion);
  NetCompatibilityRules rules(LegacyVersion);
  rules.setIsAdmin(true);
  top.readNetState(topBytes({0, 0x49}), 0.25f, rules);
  EXPECT_EQ(top.events, "IR");
  EXPECT_EQ(top.value, 0x49);
  EXPECT_EQ(top.observedTime, 0.25f);
  EXPECT_EQ(top.observedRules, rules.version());
  EXPECT_TRUE(top.observedAdmin);
  EXPECT_EQ(top.observedStream, topStreamVersion(rules));
  EXPECT_EQ(top.version->current(), 0u);
  top.emit("read-delta");
}

TEST(NetTop, BothReadFramesAllowTrailingData) {
  Top top;
  top.readNetState(topBytes({1, 0x31, 0xee, 0xff}), 0.5f);
  EXPECT_EQ(top.events, "IL");
  EXPECT_EQ(top.value, 0x31);
  top.emit("load-trailing");
  top.readNetState(topBytes({0, 0x32, 0xee, 0xff}), 0.25f);
  EXPECT_EQ(top.events, "ILR");
  EXPECT_EQ(top.value, 0x32);
  EXPECT_EQ(top.version->current(), 0u);
  top.emit("delta-trailing");
}

TEST(NetTop, OriginalDerivedAndNonstandardExceptionsKeepExactPrefixAndVersion) {
  std::vector<std::exception_ptr> errors{
      std::make_exception_ptr(DerivedTopMarker{}), std::make_exception_ptr(73)};
  for (size_t kind = 0; kind < errors.size(); ++kind) {
    for (auto op : {"S", "W", "L", "R", "B"}) {
      Top top;
      top.writeNetState();
      top.events.clear();
      top.prefix.clear();
      top.error = errors[kind];
      top.fail = op;
      bool caught = false;
      try {
        if (top.fail == "S") top.writeNetState();
        else if (top.fail == "W") top.writeNetState(19);
        else if (top.fail == "L") top.readNetState(topBytes({1, 0x42}), 0.5f);
        else if (top.fail == "R") top.readNetState(topBytes({0, 0x42}), 0.5f);
        else top.readNetState(ByteArray(), 0.5f);
      } catch (...) {
        caught = true;
        EXPECT_EQ(std::current_exception(), errors[kind]);
        try { throw; }
        catch (DerivedTopMarker const&) { EXPECT_EQ(kind, 0u); }
        catch (int value) { EXPECT_EQ(kind, 1u); EXPECT_EQ(value, 73); }
        catch (...) { ADD_FAILURE() << "exception type changed"; }
      }
      EXPECT_TRUE(caught);
      EXPECT_EQ(top.events, op);
      EXPECT_EQ(top.version->current(), 1u);
      EXPECT_EQ(top.observedVersion, 1u);
      if (top.fail == "B") EXPECT_TRUE(top.prefix.empty());
      else EXPECT_EQ(top.prefix, topBytes({
          static_cast<uint8_t>(top.fail == "S" || top.fail == "L"),
          static_cast<uint8_t>(top.fail == "S" || top.fail == "W" ? 0x2a : 0x42)}));
      std::string name = "exception-" + std::to_string(kind) + "-" + op;
      top.emit(name.c_str());
    }
  }
}

TEST(NetTop, QualifiedBaseCallsBypassOverridesAndPermitReentrantChildWrite) {
  OverrideTop top;
  ASSERT_NE(top.version, nullptr);
  bool active = false;
  top.childWrite = [&] {
    if (active) return;
    active = true;
    auto nested = top.writeNetState(23);
    EXPECT_EQ(nested.first, topBytes({0, 0x2a}));
    EXPECT_EQ(nested.second, 1u);
    active = false;
  };
  auto outer = top.writeNetState();
  EXPECT_EQ(outer.first, topBytes({1, 0x2a}));
  EXPECT_EQ(outer.second, 2u);
  EXPECT_EQ(top.events, "ISW");
  top.childWrite = {};
  top.readNetState(topBytes({1, 0x41}), 0.5f);
  top.readNetState(topBytes({0, 0x42}), 0.25f);
  top.readNetState(ByteArray(), 0.5f);
  EXPECT_EQ(top.events, "ISWLRB");
  EXPECT_EQ(top.overrides, 0);
  EXPECT_EQ(top.version->current(), 2u);
  top.emit("qualified-reentrant");
}
