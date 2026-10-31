#include "StarDataStreamDevices.hpp"
#include "StarNetElementDynamicGroup.hpp"

#include "gtest/gtest.h"

#include <algorithm>
#include <exception>
#include <functional>
#include <iostream>
#include <string>
#include <vector>

using namespace Star;

namespace {
struct WireMarker : std::exception {};
struct WireDerivedMarker : WireMarker {};
struct WireContext;
thread_local WireContext* wireContext = nullptr;
struct WireContext {
  std::vector<std::string> events;
  std::vector<unsigned> storeVersions, loadVersions, memberVersions;
  std::function<void()> factory;
  std::string fail;
  int failValue = -1;
  std::exception_ptr error = std::make_exception_ptr(WireDerivedMarker{});
  WireContext() { wireContext = this; }
  ~WireContext() { wireContext = nullptr; }
  void call(std::string op, unsigned value) {
    events.push_back(op + "/" + std::to_string(value));
    if (op == fail && (failValue < 0 || unsigned(failValue) == value))
      std::rethrow_exception(error);
  }
};
// The public default constructor is the production group's actual load factory.
struct WireElement : NetElement {
  WireContext* context = wireContext;
  uint8_t value = 0;
  bool writeBytes = false, writeResult = false;
  bool enabled = false;
  NetElementVersion const* version = nullptr;
  std::vector<float> blanks;
  WireElement() {
    context->call("factory", 0);
    if (context->factory) context->factory();
  }
  explicit WireElement(uint8_t v) : value(v) {}
  ~WireElement() override { context->events.push_back("destroy/" + std::to_string(value)); }
  void initNetVersion(NetElementVersion const* v) override { version = v; context->call("init", value); }
  void enableNetInterpolation(float) override { enabled = true; context->call("enable", value); }
  void disableNetInterpolation() override { enabled = false; context->call("disable", value); }
  void blankNetDelta(float t) override { blanks.push_back(t); context->call("blank", value); }
  void netStore(DataStream& ds, NetCompatibilityRules) const override {
    context->storeVersions.push_back(ds.streamCompatibilityVersion());
    ds.write(value);
    context->call("store", value);
  }
  void netLoad(DataStream& ds, NetCompatibilityRules) override {
    context->loadVersions.push_back(ds.streamCompatibilityVersion());
    value = ds.read<uint8_t>();
    context->call("load", value);
  }
  bool writeNetDelta(DataStream& ds, uint64_t, NetCompatibilityRules) const override {
    context->memberVersions.push_back(ds.streamCompatibilityVersion());
    if (writeBytes) ds.write(value);
    context->call("write", value);
    return writeResult;
  }
  void readNetDelta(DataStream& ds, float, NetCompatibilityRules) override {
    value = ds.read<uint8_t>();
    context->call("read", value);
  }
};
using WireGroup = NetElementDynamicGroup<WireElement>;

ByteArray wireBytes(std::initializer_list<uint8_t> bytes) {
  DataStreamBuffer ds;
  for (auto b : bytes) ds.write(b);
  return ds.takeData();
}
void wireTrace(char const* name, DataStreamBuffer const& ds) {
  static char const hex[] = "0123456789abcdef";
  std::cout << "NET_DYNAMIC_WIRE_TRACE " << name << ' ';
  for (size_t i = 0; i < ds.size(); ++i) {
    auto b = static_cast<unsigned char>(ds.ptr()[i]);
    std::cout << hex[b >> 4] << hex[b & 15];
  }
  std::cout << '\n';
}
template <typename F> void wireFailure(WireContext& c, F&& f) {
  try { f(); FAIL() << "expected the original exception"; }
  catch (...) { EXPECT_EQ(std::current_exception(), c.error); }
}
void wireItem(DataStream& ds, uint32_t id, uint8_t value) {
  ds.writeVlqU(id); ds.write(wireBytes({value}));
}
void wireAddition(DataStream& ds, uint32_t id, uint8_t value) {
  ds.writeVlqU(1);
  ds.write<uint8_t>(2); // ElementChange's third alternative, not an element ID.
  ds.write(id); ds.write(wireBytes({value}));
}
void wireMember(DataStream& ds, uint64_t code, uint8_t value) {
  ds.writeVlqU(code); ds.write(value);
}
void wireLoadOne(WireGroup& g, uint32_t id, uint8_t value) {
  DataStreamBuffer ds; ds.writeVlqU(1); wireItem(ds, id, value);
  ds.seek(0); g.netLoad(ds, {}); EXPECT_TRUE(ds.atEnd());
}
std::vector<std::pair<uint32_t, uint8_t>> wireState(WireGroup const& g) {
  std::vector<std::pair<uint32_t, uint8_t>> result;
  for (auto id : g.netElementIds()) result.emplace_back(id, g.getNetElement(id)->value);
  std::sort(result.begin(), result.end());
  return result;
}
}

TEST(NetDynamicWire, FullSnapshotsAreLengthPrefixedButMembersAreRaw) {
  WireContext c; WireGroup g;
  auto e = make_shared<WireElement>(0x31); auto id = g.addNetElement(e);
  DataStreamBuffer full, expected;
  g.netStore(full); expected.writeVlqU(1); wireItem(expected, id, 0x31);
  EXPECT_EQ(full.data(), expected.data());
  WireGroup loaded; full.seek(0); loaded.netLoad(full, {});
  EXPECT_EQ(wireState(g), wireState(loaded)); EXPECT_TRUE(full.atEnd());
  e->writeBytes = e->writeResult = true;
  DataStreamBuffer member, memberExpected;
  ASSERT_TRUE(g.writeNetDelta(member, 1));
  memberExpected.write<bool>(false); wireMember(memberExpected, uint64_t(id) + 1, 0x31);
  memberExpected.writeVlqU(0);
  EXPECT_EQ(member.data(), memberExpected.data());
  member.seek(0); loaded.readNetDelta(member); EXPECT_TRUE(member.atEnd());
  wireTrace("full-length", full); wireTrace("member-raw", member);

  NetElementVersion v; for (unsigned i = 0; i < 101; ++i) v.increment();
  g.initNetVersion(&v);
  DataStreamBuffer fallback, fallbackExpected;
  ASSERT_TRUE(g.writeNetDelta(fallback, 0));
  fallbackExpected.write<bool>(true); fallbackExpected.writeBytes(expected.data());
  EXPECT_EQ(fallback.data(), fallbackExpected.data());
  wireTrace("fallback-full", fallback);
}

TEST(NetDynamicWire, HistoryRecomputesLiveAdditionsAndSkipsRemovedOnes) {
  WireContext c; WireGroup g;
  auto a = make_shared<WireElement>(1); auto aid = g.addNetElement(a);
  auto bid = g.addNetElement(make_shared<WireElement>(2));
  g.removeNetElement(bid); a->value = 41;
  DataStreamBuffer ds, expected;
  ASSERT_TRUE(g.writeNetDelta(ds, 0));
  expected.write<bool>(false); wireAddition(expected, aid, 41);
  expected.writeVlqU(1); expected.write<uint8_t>(1); expected.write(bid);
  expected.writeVlqU(0);
  EXPECT_EQ(ds.data(), expected.data());
  WireGroup reader; ds.seek(0); reader.readNetDelta(ds);
  EXPECT_EQ(wireState(g), wireState(reader)); EXPECT_TRUE(ds.atEnd());
  // Repeat serialization must not consume history or retain its earlier bytes.
  a->value = 42; ds.clear(); expected.clear();
  ASSERT_TRUE(g.writeNetDelta(ds, 0));
  expected.write<bool>(false); wireAddition(expected, aid, 42);
  expected.writeVlqU(1); expected.write<uint8_t>(1); expected.write(bid); expected.writeVlqU(0);
  EXPECT_EQ(ds.data(), expected.data()); wireTrace("live-history", ds);
}

TEST(NetDynamicWire, LocalAdditionAndLoadBuffersKeepDefaultStreamVersion) {
  WireContext c; WireGroup g; auto e = make_shared<WireElement>(9); g.addNetElement(e);
  NetCompatibilityRules rules(LegacyVersion);
  DataStreamBuffer ds; g.netStore(ds, rules);
  EXPECT_EQ(c.storeVersions, (std::vector<unsigned>{unsigned(LegacyVersion)}));
  WireGroup reader; ds.seek(0); reader.netLoad(ds, rules);
  EXPECT_EQ(c.loadVersions, (std::vector<unsigned>{unsigned(CurrentStreamVersion)}));
  c.storeVersions.clear(); ds.clear();
  e->writeBytes = e->writeResult = true;
  ASSERT_TRUE(g.writeNetDelta(ds, 0, rules));
  EXPECT_EQ(c.storeVersions, (std::vector<unsigned>{unsigned(CurrentStreamVersion)}));
  EXPECT_EQ(c.memberVersions.back(), unsigned(LegacyVersion));
  WireGroup deltaReader;
  c.loadVersions.clear(); ds.seek(0); deltaReader.readNetDelta(ds, 0, rules);
  EXPECT_EQ(c.loadVersions, (std::vector<unsigned>{unsigned(CurrentStreamVersion)}));
  EXPECT_TRUE(ds.atEnd()); wireTrace("legacy-local-buffer", ds);
}

TEST(NetDynamicWire, RejectedRulesTouchNeitherInputOutputNorChildren) {
  WireContext c; WireGroup g; auto e = make_shared<WireElement>(7); g.addNetElement(e);
  g.setCompatibilityVersion(OpenProtocolVersion);
  DataStreamBuffer ds; ds.write<uint8_t>(0x7f); ds.seek(0);
  auto before = ds.data(); c.events.clear();
  NetCompatibilityRules rules(LegacyVersion);
  g.netStore(ds, rules); g.netLoad(ds, rules);
  EXPECT_FALSE(g.writeNetDelta(ds, 0, rules)); g.readNetDelta(ds, 0.5f, rules);
  EXPECT_EQ(ds.data(), before); EXPECT_EQ(ds.pos(), 0u); EXPECT_TRUE(c.events.empty());
  EXPECT_EQ(g.getNetElement(g.netElementIds().first()), e);
  wireTrace("rejected-rules", ds);
}

TEST(NetDynamicWire, SharedBufferSurvivesChildFailureFalseWritesAndClear) {
  WireContext c; WireGroup g; auto e = make_shared<WireElement>(0x11); auto id = g.addNetElement(e);
  DataStreamBuffer failed; c.fail = "store";
  wireFailure(c, [&] { g.netStore(failed); }); c.fail.clear();
  DataStreamBuffer prefix; prefix.writeVlqU(1); prefix.writeVlqU(id);
  EXPECT_EQ(failed.data(), prefix.data()); // child byte remains private, not emitted
  e->value = 0x22; e->writeBytes = true; e->writeResult = false;
  DataStreamBuffer empty; EXPECT_FALSE(g.writeNetDelta(empty, 1)); EXPECT_TRUE(empty.empty());
  g.clearNetElements();
  auto next = make_shared<WireElement>(0x33); auto nid = g.addNetElement(next);
  next->writeBytes = next->writeResult = true;
  DataStreamBuffer ds, expected;
  ASSERT_TRUE(g.writeNetDelta(ds, 1));
  expected.write<bool>(false); expected.writeVlqU(uint64_t(nid) + 1);
  expected.writeBytes(wireBytes({0x11, 0x22, 0x33})); expected.writeVlqU(0);
  EXPECT_EQ(ds.data(), expected.data()); wireTrace("retained-raw", ds);
  ds.clear(); expected.clear(); g.netStore(ds);
  expected.writeVlqU(1); wireItem(expected, nid, 0x33);
  EXPECT_EQ(ds.data(), expected.data()); // successful raw emission cleared the buffer
  ds.clear(); g.netStore(ds); EXPECT_EQ(ds.data(), expected.data());
}

TEST(NetDynamicWire, OutputFailureRetainsBufferUntilSuccessfulTypedEmission) {
  WireContext c; WireGroup g; auto e = make_shared<WireElement>(0x51); auto id = g.addNetElement(e);
  DataStreamBuffer prefix;
  // Allow count and ID, then reject the ByteArray's length field. Use public
  // serialization to determine the byte budget rather than write-call counts.
  DataStreamBuffer header; header.writeVlqU(1); header.writeVlqU(id);
  DataStreamFunctions output({}, [&](char const* bytes, size_t size) -> size_t {
    if (prefix.size() + size > header.size()) std::rethrow_exception(c.error);
    prefix.writeData(bytes, size); return size;
  });
  c.error = std::make_exception_ptr(713);
  wireFailure(c, [&] { g.netStore(output); }); EXPECT_EQ(prefix.data(), header.data());
  e->value = 0x52;
  DataStreamBuffer ds, expected; g.netStore(ds);
  expected.writeVlqU(1); expected.writeVlqU(id); expected.write(wireBytes({0x51, 0x52}));
  EXPECT_EQ(ds.data(), expected.data()); wireTrace("retained-typed", ds);
  ds.clear(); expected.clear(); g.netStore(ds);
  expected.writeVlqU(1); wireItem(expected, id, 0x52); EXPECT_EQ(ds.data(), expected.data());
}

TEST(NetDynamicWire, FullLoadReadsPayloadBeforeFactoryAndKeepsSuccessfulPrefix) {
  WireContext c;
  {
    WireGroup g; g.addNetElement(make_shared<WireElement>(99));
    DataStreamBuffer truncated; truncated.writeVlqU(1); truncated.writeVlqU(7);
    truncated.writeVlqU(1); // declared payload missing: defined stream exception
    truncated.seek(0); c.events.clear();
    EXPECT_ANY_THROW(g.netLoad(truncated, {}));
    EXPECT_TRUE(g.netElementIds().empty());
    EXPECT_EQ(std::count(c.events.begin(), c.events.end(), "factory/0"), 0);
    EXPECT_EQ(c.events, (std::vector<std::string>{"destroy/99"}));
  }
  for (auto op : {"factory", "load", "init", "enable"}) {
    WireGroup g; g.enableNetInterpolation(0.5f);
    DataStreamBuffer ds; ds.writeVlqU(2); wireItem(ds, 7, 17); wireItem(ds, 9, 19);
    ds.seek(0); unsigned factories = 0;
    c.factory = [&] {
      ++factories;
      if (factories == 2) {
        EXPECT_TRUE(ds.atEnd()); // payload consumed BEFORE factory
        if (std::string(op) == "factory") std::rethrow_exception(c.error);
      }
    };
    c.fail = std::string(op) == "factory" ? "" : op; c.failValue = 19;
    c.events.clear(); wireFailure(c, [&] { g.netLoad(ds, {}); });
    c.fail.clear(); c.factory = {};
    EXPECT_EQ(wireState(g), (std::vector<std::pair<uint32_t, uint8_t>>{{7, 17}}));
    EXPECT_TRUE(ds.atEnd()); EXPECT_TRUE(g.getNetElement(7)->enabled);
    if (std::string(op) != "factory") EXPECT_EQ(c.events.back(), "destroy/19");
    DataStreamBuffer replay; ASSERT_TRUE(g.writeNetDelta(replay, 0));
    WireGroup other; replay.seek(0); other.readNetDelta(replay);
    EXPECT_EQ(wireState(g), wireState(other)); EXPECT_TRUE(replay.atEnd());
    wireTrace(op, replay);
  }
}

TEST(NetDynamicWire, IncomingAdditionRecordsBeforeFactoryAndRetainsLiveOldChildOnFailure) {
  WireContext c;
  for (auto op : {"factory", "load", "init", "enable"}) {
    WireGroup g; wireLoadOne(g, 7, 21); g.enableNetInterpolation(0.5f);
    auto old = g.getNetElement(7);
    DataStreamBuffer ds; ds.write<bool>(false); wireAddition(ds, 7, 29);
    auto afterAddition = ds.size(); ds.writeVlqU(0); ds.seek(0);
    c.factory = [&] {
      EXPECT_EQ(ds.pos(), afterAddition); // decoded change BEFORE factory
      if (std::string(op) == "factory") std::rethrow_exception(c.error);
    };
    c.fail = std::string(op) == "factory" ? "" : op; c.failValue = 29;
    c.events.clear(); wireFailure(c, [&] { g.readNetDelta(ds, 0.5f); });
    c.fail.clear(); c.factory = {};
    EXPECT_EQ(ds.pos(), afterAddition); EXPECT_EQ(g.getNetElement(7), old);
    if (std::string(op) != "factory") EXPECT_EQ(c.events.back(), "destroy/29");
    // Both the original and failed addition survive in history. Both serialize
    // the CURRENT old child, not either recorded payload (21 and 29).
    old->value = 31;
    DataStreamBuffer replay, expected; ASSERT_TRUE(g.writeNetDelta(replay, 0));
    expected.write<bool>(false); expected.writeVlqU(1); expected.write<uint8_t>(0);
    wireAddition(expected, 7, 31); wireAddition(expected, 7, 31); expected.writeVlqU(0);
    EXPECT_EQ(replay.data(), expected.data()); wireTrace(op, replay);
  }
}

TEST(NetDynamicWire, PartialReadReceiptsSurviveFullLoadAndClearOnlyAfterSuccessfulBlanking) {
  WireContext c; WireGroup g; wireLoadOne(g, 7, 17); g.enableNetInterpolation(0.5f);
  DataStreamBuffer partial; partial.write<bool>(false); wireMember(partial, 8, 18);
  // EOF instead of terminator is a defined read exception AFTER receipt insertion.
  partial.seek(0); EXPECT_ANY_THROW(g.readNetDelta(partial, 0.25f));
  EXPECT_EQ(g.getNetElement(7)->value, 18);
  DataStreamBuffer full; full.write<bool>(true); full.writeVlqU(2);
  wireItem(full, 7, 27); wireItem(full, 9, 29); full.seek(0); g.readNetDelta(full);
  auto a = g.getNetElement(7), b = g.getNetElement(9);
  EXPECT_TRUE(a->blanks.empty()); EXPECT_TRUE(b->blanks.empty());
  DataStreamBuffer empty; empty.write<bool>(false); empty.writeVlqU(0);
  c.fail = "blank"; c.failValue = 29;
  empty.seek(0); wireFailure(c, [&] { g.readNetDelta(empty, 0.5f); }); c.fail.clear();
  EXPECT_TRUE(a->blanks.empty()); EXPECT_EQ(b->blanks, (std::vector<float>{0.5f}));
  empty.seek(0); g.readNetDelta(empty, 0.75f);
  EXPECT_TRUE(a->blanks.empty()); EXPECT_EQ(b->blanks, (std::vector<float>{0.5f, 0.75f}));
  empty.seek(0); g.readNetDelta(empty, 1.0f);
  EXPECT_EQ(a->blanks, (std::vector<float>{1.0f}));
  EXPECT_EQ(b->blanks, (std::vector<float>{0.5f, 0.75f, 1.0f}));
  wireTrace("receipt-full", full);
}

TEST(NetDynamicWire, FailedMemberReadMutatesChildButDoesNotMarkReceipt) {
  WireContext c; WireGroup g; wireLoadOne(g, 7, 17); g.enableNetInterpolation(0.5f);
  DataStreamBuffer ds; ds.write<bool>(false); wireMember(ds, 8, 19); ds.writeVlqU(0);
  ds.seek(0); c.fail = "read"; c.failValue = 19;
  wireFailure(c, [&] { g.readNetDelta(ds, 0.25f); }); c.fail.clear();
  EXPECT_EQ(g.getNetElement(7)->value, 19); EXPECT_EQ(ds.pos(), ds.size() - 1);
  DataStreamBuffer empty; empty.write<bool>(false); empty.writeVlqU(0);
  empty.seek(0); g.readNetDelta(empty, 0.5f);
  EXPECT_EQ(g.getNetElement(7)->blanks, (std::vector<float>{0.5f}));
  wireTrace("failed-member-prefix", ds);
}

TEST(NetDynamicWire, DeltaFailuresRetainExactHistoryAndMemberPrefixes) {
  WireContext c; WireGroup g; auto e = make_shared<WireElement>(0x41);
  auto id = g.addNetElement(e);
  DataStreamBuffer ds; c.fail = "store";
  wireFailure(c, [&] { g.writeNetDelta(ds, 0); }); c.fail.clear();
  EXPECT_EQ(ds.data(), wireBytes({0, 1})); // before the change's variant tag
  wireTrace("failed-addition-prefix", ds);
  // Addition serialization uses a fresh local buffer: its failed byte does not
  // contaminate either a retry or the shared member buffer.
  ds.clear(); DataStreamBuffer expected;
  ASSERT_TRUE(g.writeNetDelta(ds, 0));
  expected.write<bool>(false); wireAddition(expected, id, 0x41); expected.writeVlqU(0);
  EXPECT_EQ(ds.data(), expected.data());
  e->writeBytes = e->writeResult = true; c.fail = "write";
  ds.clear(); wireFailure(c, [&] { g.writeNetDelta(ds, 1); }); c.fail.clear();
  EXPECT_TRUE(ds.empty()); // willWrite runs only AFTER the child returns true
  e->value = 0x42; ds.clear(); expected.clear();
  ASSERT_TRUE(g.writeNetDelta(ds, 1));
  expected.write<bool>(false); expected.writeVlqU(uint64_t(id) + 1);
  expected.writeBytes(wireBytes({0x41, 0x42})); expected.writeVlqU(0);
  EXPECT_EQ(ds.data(), expected.data()); wireTrace("failed-member-buffer", ds);
}

TEST(NetDynamicWire, ReadCodesTruncateToU32AndMaxIdWriteWrapsToZero) {
  WireContext c; WireGroup g; wireLoadOne(g, 7, 17);
  DataStreamBuffer wide; wide.write<bool>(false);
  wireMember(wide, (uint64_t(1) << 32) + 8, 33); wide.writeVlqU(0);
  wide.seek(0); g.readNetDelta(wide);
  EXPECT_EQ(g.getNetElement(7)->value, 33); EXPECT_TRUE(wide.atEnd());
  wireTrace("wide-code", wide);
  WireGroup maxId; wireLoadOne(maxId, highest<uint32_t>(), 0x61);
  auto e = maxId.getNetElement(highest<uint32_t>()); e->writeBytes = e->writeResult = true;
  DataStreamBuffer wrapped; ASSERT_TRUE(maxId.writeNetDelta(wrapped, 1));
  EXPECT_EQ(wrapped.data(), wireBytes({0, 0, 0x61, 0}));
  // The first wrapped code is already a terminator; do not feed its orphaned
  // child bytes into another parser or "repair" this native legacy quirk.
  wireTrace("max-id-wrap", wrapped);
}
