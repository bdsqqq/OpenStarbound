#include "StarDataStreamDevices.hpp"
#include "StarNetElementBasicFields.hpp"

#include "gtest/gtest.h"

#include <exception>
#include <iostream>
#include <limits>

#ifdef STAR_USE_RUST_NET_FIELD
#include "StarRustNetScalar.h"
#endif

using namespace Star;

namespace {
constexpr uint64_t WordMax = std::numeric_limits<uint64_t>::max();

struct ScalarDigest {
  uint64_t value = UINT64_C(14695981039346656037);
  void add(uint64_t word) {
    for (unsigned i = 0; i != 8; ++i) {
      value ^= (word >> (8 * i)) & 255;
      value *= UINT64_C(1099511628211);
    }
  }
  void emit(char const* name) const {
    std::cout << "NET_SCALAR_TRACE " << name << ' ' << value << '\n';
  }
};

uint64_t scalarRandom(uint64_t& state) {
  state ^= state << 13;
  state ^= state >> 7;
  state ^= state << 17;
  return state;
}

void scalarLoad(NetElement& field, uint64_t value, NetCompatibilityRules rules = {}) {
  DataStreamBuffer wire;
  wire.writeVlqU(value);
  wire.seek(0);
  field.netLoad(wire, rules);
  EXPECT_TRUE(wire.atEnd());
}

uint64_t scalarStored(NetElement const& field) {
  DataStreamBuffer wire;
  field.netStore(wire, {});
  wire.seek(0);
  auto value = wire.readVlqU();
  EXPECT_TRUE(wire.atEnd());
  return value;
}

struct ScalarMarker : std::exception {};
struct DerivedScalarMarker : ScalarMarker {};

struct ObservedEvent : NetElementEvent {
  NetElementVersion const* version = nullptr;
  std::exception_ptr failure;
  unsigned updates = 0;
  uint64_t wordAtUpdate = 0;
  bool deltaAtUpdate = false;
  void readData(DataStream& ds, uint64_t& value) const override {
    if (failure) std::rethrow_exception(failure);
    NetElementUInt::readData(ds, value);
  }
  void updated() override {
    NetElementEvent::updated();
    ++updates;
    wordAtUpdate = scalarStored(*this);
    if (version) {
      DataStreamBuffer wire;
      deltaAtUpdate = writeNetDelta(wire, version->current());
    }
  }
};
}

TEST(NetScalar, SizePublicSentinelAndAdjacentWireValues) {
  NetElementSize field;
  EXPECT_EQ(field.get(), size_t(0));
  EXPECT_FALSE(field.pullUpdated());
  ScalarDigest digest;
  size_t values[] = {NPos, 0, 1, NPos - 1};
  for (size_t value : values) {
    field.set(value);
    EXPECT_EQ(field.get(), value);
    uint64_t encoded = value == NPos ? 0 : uint64_t(value + 1);
    DataStreamBuffer actual;
    field.netStore(actual);
    DataStreamBuffer expected;
    expected.writeVlqU(encoded);
    EXPECT_EQ(actual.data(), expected.data());
    actual.seek(0);
    EXPECT_EQ(actual.readVlqU(), encoded);
    EXPECT_TRUE(actual.atEnd());
    expected.seek(0);
    NetElementSize loaded;
    loaded.netLoad(expected, {});
    EXPECT_EQ(loaded.get(), value);
    EXPECT_TRUE(loaded.pullUpdated());
    EXPECT_FALSE(loaded.pullUpdated());
    digest.add(value);
    digest.add(encoded);
  }
  field.set(NPos);
  EXPECT_EQ(scalarStored(field), uint64_t(0));
  digest.emit("size-native-edges");
}

TEST(NetScalar, SizeDecodeUsesNativeCastAfterSubtractNotClamp) {
  NetElementSize field;
  ScalarDigest digest;
  uint64_t wires[] = {0, 1, 2, UINT64_C(0xffffffff), UINT64_C(0x100000000),
      UINT64_C(0x100000001), UINT64_C(0x100000002), WordMax - 1, WordMax};
  for (auto wire : wires) {
    scalarLoad(field, wire);
    size_t expected = wire == 0 ? NPos : static_cast<size_t>(wire - 1);
    EXPECT_EQ(field.get(), expected);
    EXPECT_EQ(scalarStored(field), expected == NPos ? 0 : uint64_t(expected + 1));
    digest.add(wire);
    digest.add(field.get());
  }
  size_t beforeFailure = field.get();
  field.pullUpdated();
  DataStreamBuffer truncated;
  truncated.write(uint8_t(0x80));
  truncated.seek(0);
  EXPECT_THROW(field.netLoad(truncated, {}), EofException);
  EXPECT_EQ(field.get(), beforeFailure);
  EXPECT_FALSE(field.pullUpdated());
  digest.add(sizeof(size_t));
  digest.emit("size-native-decode-width");
}

TEST(NetScalar, SizeNativePublicHundredThousandDeterministicValues) {
  NetElementSize field;
  NetElementSize loaded;
  ScalarDigest digest;
  uint64_t random = UINT64_C(0x95dceb47321a608f);
  for (unsigned i = 0; i != 100000; ++i) {
    size_t value = static_cast<size_t>(scalarRandom(random));
    field.set(value);
    ASSERT_EQ(field.get(), value);
    DataStreamBuffer wire;
    field.netStore(wire);
    wire.seek(0);
    uint64_t encoded = wire.readVlqU();
    ASSERT_EQ(encoded, value == NPos ? 0 : uint64_t(value + 1));
    wire.seek(0);
    loaded.netLoad(wire, {});
    ASSERT_EQ(loaded.get(), value);
    ASSERT_TRUE(wire.atEnd());
    digest.add(value);
    digest.add(encoded);
  }
  digest.emit("size-native-corpus-100000");
}

TEST(NetScalar, EventPublicRepeatedPullOccurredAndIgnorePolicies) {
  NetElementEvent event;
  EXPECT_EQ(event.pullOccurrences(), uint64_t(0));
  EXPECT_FALSE(event.pullOccurred());
  event.trigger();
  event.trigger();
  event.trigger();
  EXPECT_EQ(scalarStored(event), uint64_t(3));
  EXPECT_EQ(event.pullOccurrences(), uint64_t(3));
  EXPECT_EQ(event.pullOccurrences(), uint64_t(0));
  event.trigger();
  EXPECT_TRUE(event.pullOccurred());
  EXPECT_FALSE(event.pullOccurred());
  event.trigger();
  event.ignoreOccurrences();
  EXPECT_FALSE(event.pullOccurred());
  scalarLoad(event, 10);
  EXPECT_EQ(event.pullOccurrences(), uint64_t(5));
  event.setIgnoreOccurrencesOnNetLoad(true);
  scalarLoad(event, 20);
  EXPECT_FALSE(event.pullOccurred());
  event.trigger();
  EXPECT_EQ(event.pullOccurrences(), uint64_t(1));
  event.setIgnoreOccurrencesOnNetLoad(false);
  scalarLoad(event, 25);
  EXPECT_EQ(event.pullOccurrences(), uint64_t(4));
  ScalarDigest digest;
  digest.add(scalarStored(event));
  digest.add(event.pullOccurrences());
  digest.emit("event-pull-ignore-policy");
}

TEST(NetScalar, EventWrapIsZeroOccurrencesAndDecreasingLoadClampsPulled) {
  NetElementEvent event;
  scalarLoad(event, WordMax - 1);
  EXPECT_EQ(event.pullOccurrences(), WordMax - 1);
  event.trigger();
  EXPECT_EQ(scalarStored(event), WordMax);
  EXPECT_EQ(event.pullOccurrences(), uint64_t(1));
  event.trigger();
  EXPECT_EQ(scalarStored(event), uint64_t(0));
  EXPECT_EQ(event.pullOccurrences(), uint64_t(0));
  EXPECT_FALSE(event.pullOccurred());
  event.trigger();
  EXPECT_EQ(event.pullOccurrences(), uint64_t(1));
  scalarLoad(event, WordMax);
  EXPECT_EQ(event.pullOccurrences(), WordMax - 1);
  scalarLoad(event, 7);
  EXPECT_EQ(event.pullOccurrences(), uint64_t(0));
  scalarLoad(event, 11);
  EXPECT_EQ(event.pullOccurrences(), uint64_t(4));
  scalarLoad(event, 9);
  EXPECT_EQ(event.pullOccurrences(), uint64_t(0));
  event.trigger();
  EXPECT_EQ(event.pullOccurrences(), uint64_t(1));
  ScalarDigest digest;
  digest.add(scalarStored(event));
  digest.add(event.pullOccurrences());
  digest.emit("event-wrap-decrease-increase");
}

TEST(NetScalar, EventRejectedLoadStillIgnoresButThrownReadDoesNot) {
  ObservedEvent event;
  event.trigger();
  event.trigger();
  event.setCompatibilityVersion(static_cast<VersionNumber>(1));
  DataStreamBuffer rejected;
  rejected.writeVlqU(90);
  rejected.seek(0);
  event.netLoad(rejected, NetCompatibilityRules(LegacyVersion));
  EXPECT_EQ(rejected.pos(), size_t(0));
  EXPECT_EQ(event.pullOccurrences(), uint64_t(2));
  event.trigger();
  event.setIgnoreOccurrencesOnNetLoad(true);
  event.netLoad(rejected, NetCompatibilityRules(LegacyVersion));
  EXPECT_EQ(rejected.pos(), size_t(0));
  EXPECT_EQ(event.pullOccurrences(), uint64_t(0));
  event.trigger();
  unsigned updates = event.updates;
  event.failure = std::make_exception_ptr(DerivedScalarMarker{});
  auto accepted = NetCompatibilityRules(static_cast<VersionNumber>(1));
  try {
    event.netLoad(rejected, accepted);
    FAIL() << "expected exact derived read exception";
  } catch (DerivedScalarMarker const&) {
    EXPECT_EQ(std::current_exception(), event.failure);
  }
  EXPECT_EQ(event.updates, updates);
  EXPECT_EQ(event.pullOccurrences(), uint64_t(1));
  EXPECT_EQ(rejected.pos(), size_t(0));
  event.failure = {};
  event.trigger();
  DataStreamBuffer truncated;
  truncated.write(uint8_t(0x80));
  truncated.seek(0);
  EXPECT_THROW(event.netLoad(truncated, accepted), EofException);
  EXPECT_EQ(event.updates, updates + 1);
  EXPECT_EQ(event.pullOccurrences(), uint64_t(1));
  EXPECT_EQ(scalarStored(event), uint64_t(5));
  EXPECT_TRUE(event.pullUpdated());
  EXPECT_FALSE(event.pullUpdated());
  ScalarDigest digest;
  digest.add(scalarStored(event));
  digest.add(truncated.pos());
  digest.add(event.updates);
  digest.emit("event-rejected-and-failed-load");
}

TEST(NetScalar, EventLoadVersionCapturedBeforeVirtualUpdatedAndGuardUnchanged) {
  ObservedEvent event;
  NetElementVersion version;
  event.version = &version;
  event.initNetVersion(&version);
  version.increment();
  scalarLoad(event, WordMax);
  EXPECT_TRUE(event.deltaAtUpdate);
  EXPECT_EQ(event.wordAtUpdate, WordMax);
  EXPECT_TRUE(event.pullUpdated());
  EXPECT_EQ(event.pullOccurrences(), WordMax);
  version.increment();
  DataStreamBuffer stale;
  EXPECT_FALSE(event.writeNetDelta(stale, version.current()));
  EXPECT_TRUE(stale.empty());
  scalarLoad(event, 0);
  EXPECT_TRUE(event.deltaAtUpdate);
  EXPECT_EQ(event.wordAtUpdate, uint64_t(0));
  EXPECT_EQ(event.pullOccurrences(), uint64_t(0));
  EXPECT_TRUE(event.pullUpdated());
  EXPECT_FALSE(event.pullUpdated());
  DataStreamBuffer delta;
  EXPECT_TRUE(event.writeNetDelta(delta, version.current()));
  delta.seek(0);
  EXPECT_EQ(delta.readVlqU(), uint64_t(0));
  EXPECT_TRUE(delta.atEnd());
  event.trigger();
  EXPECT_TRUE(event.deltaAtUpdate);
  EXPECT_EQ(event.wordAtUpdate, uint64_t(1));
  EXPECT_EQ(event.pullOccurrences(), uint64_t(1));
  ScalarDigest digest;
  digest.add(event.updates);
  digest.add(scalarStored(event));
  digest.add(version.current());
  digest.emit("event-version-virtual-update");
}

TEST(NetScalar, EventNativePublicHundredThousandReuseCorpus) {
  NetElementEvent event;
  uint64_t value = 0;
  uint64_t pulled = 0;
  uint64_t random = UINT64_C(0x4f5a1c892b63de07);
  ScalarDigest digest;
  for (unsigned i = 0; i != 100000; ++i) {
    auto input = scalarRandom(random);
    bool ignore = (input & 16) != 0;
    event.setIgnoreOccurrencesOnNetLoad(ignore);
    // Low resets repeatedly exercise decreasing-load clamp without allocation
    // proportional to the occurrence count. Full-width values exercise wrap.
    value = (i % 4 == 0) ? 0 : ((i % 4 == 1) ? (input & 255) : input);
    scalarLoad(event, value);
    if (pulled > value) pulled = value;
    if (ignore) pulled = value;
    unsigned triggers = unsigned(input & 3);
    for (unsigned j = 0; j != triggers; ++j) {
      event.trigger();
      ++value;
      if (pulled > value) pulled = value;
    }
    ASSERT_EQ(scalarStored(event), value);
    uint64_t expected = value - pulled;
    ASSERT_EQ(event.pullOccurrences(), expected);
    pulled = value;
    ASSERT_FALSE(event.pullOccurred());
    digest.add(value);
    digest.add(expected);
    digest.add(ignore);
  }
  digest.emit("event-native-corpus-100000");
}

#ifdef STAR_USE_RUST_NET_FIELD
TEST(NetScalar, RustNaturalCountersAndByValueModelsNotCpp32PlatformExecution) {
  uint64_t before[SB_NET_SCALAR_COUNT];
  uint64_t globalBefore[SB_NET_SCALAR_COUNT];
  for (uint32_t mode = 0; mode != SB_NET_SCALAR_COUNT; ++mode) {
    before[mode] = sb_net_scalar_count(0, mode);
    globalBefore[mode] = sb_net_scalar_count(1, mode);
  }
  NetElementSize size;
  size.set(17);
  EXPECT_EQ(scalarStored(size), uint64_t(18));
  scalarLoad(size, 19);
  EXPECT_EQ(size.get(), size_t(18));
  NetElementEvent event;
  scalarLoad(event, 9);
  event.trigger();
  EXPECT_EQ(event.pullOccurrences(), uint64_t(10));
  uint64_t expectedCounts[] = {1, 1, 2, 1, 1};
  for (uint32_t mode = 0; mode != SB_NET_SCALAR_COUNT; ++mode) {
    EXPECT_EQ(sb_net_scalar_count(0, mode) - before[mode], expectedCounts[mode]);
    EXPECT_GE(sb_net_scalar_count(1, mode) - globalBefore[mode], expectedCounts[mode]);
  }
  EXPECT_EQ(sb_net_scalar_count(0, SB_NET_SCALAR_COUNT), uint64_t(0));
  EXPECT_EQ(sb_net_scalar_count(2, SB_NET_SCALAR_NEXT), uint64_t(0));
  // These are ABI-only word models; the public Size tests above use the real
  // host sizeof(size_t). In particular decoding narrows AFTER subtraction.
  ScalarDigest digest;
  for (uint32_t bits : {uint32_t(32), uint32_t(64)}) {
    uint64_t mask = bits == 32 ? UINT64_C(0xffffffff) : WordMax;
    uint64_t wires[] = {0, 1, 2, UINT64_C(0xffffffff), UINT64_C(0x100000000),
        UINT64_C(0x100000001), UINT64_C(0x100000002), WordMax};
    for (uint64_t wire : wires) {
      SbNetScalarReply reply{};
      ASSERT_EQ(sb_net_scalar_run(SB_NET_SCALAR_SIZE_DECODE, bits, wire, 0, &reply), uint32_t(0));
      uint64_t expected = wire == 0 ? mask : ((wire - 1) & mask);
      EXPECT_EQ(reply.value, expected);
      EXPECT_EQ(reply.pulled, uint64_t(0));
      ASSERT_EQ(sb_net_scalar_run(SB_NET_SCALAR_SIZE_ENCODE, bits, expected, 0, &reply), uint32_t(0));
      EXPECT_EQ(reply.value, expected == mask ? 0 : expected + 1);
      digest.add(wire);
      digest.add(expected);
    }
  }
  SbNetScalarReply reply{};
  ASSERT_EQ(sb_net_scalar_run(SB_NET_SCALAR_NEXT, 0, WordMax, 0, &reply), uint32_t(0));
  EXPECT_EQ(reply.value, uint64_t(0));
  ASSERT_EQ(sb_net_scalar_run(SB_NET_SCALAR_PULL, 0, 0, WordMax, &reply), uint32_t(0));
  EXPECT_EQ(reply.value, uint64_t(1)); // Raw ABI wraps; C++ asserts this domain.
  EXPECT_EQ(reply.pulled, uint64_t(0));
  ASSERT_EQ(sb_net_scalar_run(SB_NET_SCALAR_CLAMP, 0, 0, WordMax, &reply), uint32_t(0));
  EXPECT_EQ(reply.value, uint64_t(0));
  EXPECT_EQ(reply.pulled, uint64_t(0));
  // Candidate-only evidence MUST NOT join native/candidate shared trace keys.
  std::cout << "NET_SCALAR_DIAGNOSTIC abi-model32-64 " << digest.value << '\n';
}
#endif
