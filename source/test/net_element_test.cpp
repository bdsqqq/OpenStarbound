#include "StarNetElement.hpp"

#include "gtest/gtest.h"

#include <cstring>
#include <iostream>
#include <limits>
#include <type_traits>

#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetScalar.h"
#endif

using namespace Star;

namespace {
constexpr uint64_t ElementWordMax = std::numeric_limits<uint64_t>::max();
constexpr VersionNumber ElementVersionMax = std::numeric_limits<VersionNumber>::max();
static_assert(std::is_same<VersionNumber, uint32_t>::value, "compatibility uses native u32");
static_assert(sizeof(NetElementVersion) == 8, "finite native version fixture layout");
static_assert(sizeof(uint64_t) == sizeof(NetElementVersion), "fixture representation width");
static_assert(std::is_standard_layout<NetElementVersion>::value, "native version layout");
static_assert(std::is_trivially_copyable<NetElementVersion>::value, "native version copying");

// A finite native ARM64 ABI fixture, not an all-platform representation proof.
// The native class has one u64 member; copy bytes, never alias a private member.
NetElementVersion elementVersionAt(uint64_t value) {
  NetElementVersion version;
  std::memcpy(&version, &value, sizeof(value));
  return version;
}

struct ElementDigest {
  uint64_t value = UINT64_C(14695981039346656037);
  void add(uint64_t word) {
    for (unsigned i = 0; i != 8; ++i) {
      value ^= (word >> (8 * i)) & 255;
      value *= UINT64_C(1099511628211);
    }
  }
  void emit(char const* name) const {
    std::cout << "NET_ELEMENT_TRACE " << name << ' ' << value << '\n';
  }
};

uint64_t elementRandom(uint64_t& state) {
  state ^= state << 13;
  state ^= state >> 7;
  state ^= state << 17;
  return state;
}

struct MinimalElement : NetElement {
  unsigned calls = 0;
  void initNetVersion(NetElementVersion const*) override { ++calls; }
  void netStore(DataStream&, NetCompatibilityRules) const override {}
  void netLoad(DataStream&, NetCompatibilityRules) override { ++calls; }
  bool writeNetDelta(DataStream&, uint64_t, NetCompatibilityRules) const override { return false; }
  void readNetDelta(DataStream&, float, NetCompatibilityRules) override { ++calls; }
};
}

TEST(NetElement, VersionDefaultAndPreincrement) {
  NetElementVersion version;
  EXPECT_EQ(version.current(), uint64_t(0));
  ElementDigest digest;
  for (uint64_t expected = 1; expected != 17; ++expected) {
    EXPECT_EQ(version.increment(), expected);
    EXPECT_EQ(version.current(), expected);
    EXPECT_EQ(version.current(), expected); // Getter is observational.
    digest.add(version.current());
  }
  digest.emit("version-default-preincrement");
}

TEST(NetElement, VersionCopiesAndAssignmentsAreIndependent) {
  NetElementVersion original;
  original.increment();
  NetElementVersion copy(original);
  NetElementVersion assigned;
  assigned = original;
  EXPECT_EQ(original.increment(), uint64_t(2));
  EXPECT_EQ(copy.current(), uint64_t(1));
  EXPECT_EQ(assigned.current(), uint64_t(1));
  EXPECT_EQ(copy.increment(), uint64_t(2));
  EXPECT_EQ(copy.increment(), uint64_t(3));
  EXPECT_EQ(original.current(), uint64_t(2));
  EXPECT_EQ(assigned.increment(), uint64_t(2));
  ElementDigest digest;
  digest.add(original.current());
  digest.add(copy.current());
  digest.add(assigned.current());
  digest.add(sizeof(NetElementVersion));
  digest.emit("version-independent-copies-layout");
}

TEST(NetElement, VersionNativeRepresentationBoundaryWrap) {
  ElementDigest digest;
  for (uint64_t start : {uint64_t(0), uint64_t(1), ElementWordMax - 2,
      ElementWordMax - 1, ElementWordMax}) {
    auto version = elementVersionAt(start);
    ASSERT_EQ(version.current(), start);
    uint64_t oracle = start;
    for (unsigned i = 0; i != 4; ++i) {
      ++oracle; // Unsigned native arithmetic defines modulo-2^64 wrap.
      ASSERT_EQ(version.increment(), oracle);
      ASSERT_EQ(version.current(), oracle);
      digest.add(oracle);
    }
  }
  digest.emit("version-native-boundary-wrap");
}

TEST(NetElement, VersionHundredThousandMixedSeedSteps) {
  uint64_t random = UINT64_C(0xd7a194be680c235f);
  uint64_t oracle = 0;
  NetElementVersion version;
  ElementDigest digest;
  for (unsigned i = 0; i != 100000; ++i) {
    uint64_t input = elementRandom(random);
    if (i % 11 == 0) {
      oracle = (i % 22 == 0) ? ElementWordMax - (input & 3) : input;
      version = elementVersionAt(oracle);
    }
    ASSERT_EQ(version.current(), oracle);
    unsigned steps = unsigned(input & 3) + 1;
    for (unsigned j = 0; j != steps; ++j) {
      ++oracle;
      ASSERT_EQ(version.increment(), oracle);
      ASSERT_EQ(version.current(), oracle);
    }
    NetElementVersion copy = version;
    ASSERT_EQ(copy.increment(), oracle + uint64_t(1));
    ASSERT_EQ(version.current(), oracle);
    digest.add(input);
    digest.add(oracle);
    digest.add(copy.current());
  }
  digest.emit("version-mixed-seeds-100000");
}

TEST(NetElement, CompatibilityAnySentinelAcceptsEveryRuleEdge) {
  MinimalElement element;
  EXPECT_EQ(element.compatibilityVersion(), AnyVersion);
  ElementDigest digest;
  for (VersionNumber rule : {LegacyVersion, VersionNumber(1), OpenProtocolVersion,
      VersionNumber(0x7fffffff), VersionNumber(0x80000000),
      VersionNumber(ElementVersionMax - 1), ElementVersionMax}) {
    NetCompatibilityRules rules(rule);
    for (bool admin : {false, true}) {
      rules.setIsAdmin(admin);
      EXPECT_TRUE(element.checkWithRules(rules));
      EXPECT_EQ(element.compatibilityVersion(), AnyVersion);
      EXPECT_EQ(rules.version(), rule);
      EXPECT_EQ(rules.isAdmin(), admin);
      digest.add(rule);
      digest.add(element.checkWithRules(rules));
    }
  }
  // The concrete inline rules getter cannot reveal whether it was read.
  // The production AnyVersion-before-rules.version() guard also needs review;
  // a null reference would be UB, not a short-circuit test.
  EXPECT_EQ(element.calls, 0u);
  digest.emit("compatibility-any-rule-edges");
}

TEST(NetElement, CompatibilityUnsignedEdgesSetterGetterAndAdminIndependence) {
  MinimalElement element;
  ElementDigest digest;
  VersionNumber edges[] = {LegacyVersion, VersionNumber(1), OpenProtocolVersion,
      VersionNumber(0x7fffffff), VersionNumber(0x80000000),
      VersionNumber(ElementVersionMax - 1), ElementVersionMax};
  for (VersionNumber stored : edges) {
    element.setCompatibilityVersion(stored);
    ASSERT_EQ(element.compatibilityVersion(), stored);
    for (VersionNumber rule : edges) {
      NetCompatibilityRules rules;
      rules.setVersion(rule);
      bool expected = stored == AnyVersion || rule >= stored;
      for (bool admin : {false, true}) {
        rules.setIsAdmin(admin);
        EXPECT_EQ(element.checkWithRules(rules), expected);
        EXPECT_EQ(element.compatibilityVersion(), stored);
        EXPECT_EQ(rules.version(), rule);
        EXPECT_EQ(rules.isAdmin(), admin);
      }
      digest.add(stored);
      digest.add(rule);
      digest.add(expected);
    }
  }
  EXPECT_EQ(element.calls, 0u);
  digest.emit("compatibility-u32-edges-admin");
}

TEST(NetElement, CompatibilityHundredThousandPublicCorpusAndStateUnchanged) {
  MinimalElement element;
  NetElementVersion version;
  version.increment();
  uint64_t random = UINT64_C(0x65a913dc7f204be8);
  ElementDigest digest;
  for (unsigned i = 0; i != 100000; ++i) {
    uint64_t input = elementRandom(random);
    VersionNumber stored = static_cast<VersionNumber>(input);
    VersionNumber rule = static_cast<VersionNumber>(input >> 32);
    if (i % 7 == 0) rule = stored;
    if (i % 13 == 0) stored = AnyVersion;
    if (i % 17 == 0) rule = LegacyVersion;
    if (i % 19 == 0) rule = ElementVersionMax;
    element.setCompatibilityVersion(stored);
    NetCompatibilityRules rules(rule);
    bool expected = stored == AnyVersion || rule >= stored;
    for (bool admin : {false, true}) {
      rules.setIsAdmin(admin);
      ASSERT_EQ(element.checkWithRules(rules), expected);
      ASSERT_EQ(element.compatibilityVersion(), stored);
      ASSERT_EQ(rules.version(), rule);
      ASSERT_EQ(rules.isAdmin(), admin);
    }
    ASSERT_EQ(version.current(), uint64_t(1));
    digest.add(stored);
    digest.add(rule);
    digest.add(expected);
  }
  EXPECT_EQ(element.calls, 0u);
  digest.emit("compatibility-public-corpus-100000");
}

TEST(NetElement, NativeBaseInterpolationAndBlankRemainNoOps) {
  MinimalElement element;
  element.setCompatibilityVersion(OpenProtocolVersion);
  NetElement& base = element;
  for (float value : {0.0f, -1.0f, 1.0f, std::numeric_limits<float>::max()}) {
    base.enableNetInterpolation(value);
    base.tickNetInterpolation(value);
    base.blankNetDelta(value);
    base.disableNetInterpolation();
    EXPECT_EQ(element.calls, 0u);
    EXPECT_EQ(element.compatibilityVersion(), OpenProtocolVersion);
  }
  ElementDigest digest;
  digest.add(element.calls);
  digest.add(element.compatibilityVersion());
  digest.emit("native-base-noops");
}

#ifdef STAR_USE_RUST_NET_GROUP
TEST(NetElement, RustNaturalVersionAndCompatibilityCounters) {
  static_assert(SB_NET_SCALAR_VERSION_NEXT == 5, "append version diagnostic index");
  static_assert(SB_NET_SCALAR_COMPAT == 6, "append compatibility diagnostic index");
  static_assert(SB_NET_SCALAR_COUNT == 7, "scalar counter width");
  uint64_t before[SB_NET_SCALAR_COUNT];
  uint64_t globalBefore[SB_NET_SCALAR_COUNT];
  for (uint32_t mode = 0; mode != SB_NET_SCALAR_COUNT; ++mode) {
    before[mode] = sb_net_scalar_count(0, mode);
    globalBefore[mode] = sb_net_scalar_count(1, mode);
  }
  MinimalElement element;
  for (VersionNumber rule : {LegacyVersion, OpenProtocolVersion, ElementVersionMax})
    EXPECT_TRUE(element.checkWithRules(NetCompatibilityRules(rule)));
  // Sentinel success must not accidentally enter COMPAT; this observes entry,
  // not the uninstrumentable native rules getter's read behavior.
  EXPECT_EQ(sb_net_scalar_count(0, SB_NET_SCALAR_COMPAT), before[SB_NET_SCALAR_COMPAT]);
  NetElementVersion version;
  EXPECT_EQ(version.increment(), uint64_t(1));
  EXPECT_EQ(version.increment(), uint64_t(2));
  element.setCompatibilityVersion(OpenProtocolVersion);
  EXPECT_FALSE(element.checkWithRules(NetCompatibilityRules(LegacyVersion)));
  EXPECT_TRUE(element.checkWithRules(NetCompatibilityRules(OpenProtocolVersion)));
  uint64_t expectedCounts[SB_NET_SCALAR_COUNT] = {0, 0, 0, 0, 0, 2, 2};
  for (uint32_t mode = 0; mode != SB_NET_SCALAR_COUNT; ++mode) {
    EXPECT_EQ(sb_net_scalar_count(0, mode) - before[mode], expectedCounts[mode]);
    EXPECT_GE(sb_net_scalar_count(1, mode) - globalBefore[mode], expectedCounts[mode]);
  }
  std::cout << "NET_ELEMENT_DIAGNOSTIC natural-version-compat 2 2\n";
}
#endif
