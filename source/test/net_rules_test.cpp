#include "StarNetElement.hpp"
#include "StarDataStreamDevices.hpp"
#include "gtest/gtest.h"

#include <array>
#include <cstring>
#include <iostream>
#include <limits>
#include <type_traits>
#include <utility>
#include <vector>

#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetRules.h"
#endif

using namespace Star;

// Compile this translation unit separately with this macro in both profiles:
// overload resolution must reject the retained deleted uint64_t constructor.
#ifdef STAR_NET_RULES_WIDE_NEGATIVE
NetCompatibilityRules netRulesRejectedWideConstructor(uint64_t(1));
#endif

namespace {
constexpr uint32_t RulesMax = std::numeric_limits<uint32_t>::max();
constexpr std::array<uint32_t, 7> RulesEdges{{0, 1, 2, 0x7fffffff, 0x80000000,
    RulesMax - 1, RulesMax}};

struct RulesDigest {
  uint64_t value = UINT64_C(14695981039346656037);
  void add(uint64_t word) {
    for (unsigned i = 0; i != 8; ++i) {
      value ^= (word >> (8 * i)) & 255;
      value *= UINT64_C(1099511628211);
    }
  }
  void rules(NetCompatibilityRules const& r) {
    add(r.version()); add(r.isAdmin()); add(r.isLegacy());
    add(Star::hash<NetCompatibilityRules>{}(r));
  }
  void emit(char const* name) const {
    std::cout << "NET_RULES_TRACE " << name << ' ' << value << '\n';
  }
};

void expectRules(NetCompatibilityRules const& r, uint32_t version, bool admin) {
  EXPECT_EQ(r.version(), version);
  EXPECT_EQ(r.isAdmin(), admin);
  EXPECT_EQ(r.isLegacy(), version == uint32_t(0));
  EXPECT_EQ(Star::hash<NetCompatibilityRules>{}(r), size_t(version));
}

NetCompatibilityRules changeRulesByValue(NetCompatibilityRules rules) {
  rules.setVersion(0x80000000);
  rules.setIsAdmin(!rules.isAdmin());
  return rules;
}
}

TEST(NetRules, DefaultUsesExternalProtocolVersionAndNonAdmin) {
  NetCompatibilityRules plain;
  NetCompatibilityRules braces{};
  expectRules(plain, OpenProtocolVersion, false);
  expectRules(braces, OpenProtocolVersion, false);
  RulesDigest digest; digest.rules(plain); digest.rules(braces);
  digest.add(OpenProtocolVersion);
  digest.emit("default-external-protocol");
}

TEST(NetRules, ExplicitUnsignedEdgesStartNonAdmin) {
  RulesDigest digest;
  for (uint32_t version : RulesEdges) {
    NetCompatibilityRules rules(version);
    expectRules(rules, version, false);
    digest.rules(rules);
  }
  digest.emit("explicit-u32-edges");
}

TEST(NetRules, SetVersionPreservesAdminAndSetAdminPreservesVersion) {
  RulesDigest digest;
  NetCompatibilityRules rules;
  for (bool admin : {false, true}) {
    rules.setIsAdmin(admin);
    for (uint32_t version : RulesEdges) {
      rules.setVersion(version);
      expectRules(rules, version, admin);
      digest.rules(rules);
      for (bool next : {true, true, false, false, true}) {
        rules.setIsAdmin(next);
        expectRules(rules, version, next);
        digest.rules(rules);
      }
      rules.setIsAdmin(admin);
    }
  }
  digest.emit("independent-setters");
}

TEST(NetRules, LegacyMeansExactlyZeroNotSignedOrWildcard) {
  RulesDigest digest;
  for (uint32_t version : RulesEdges) {
    NetCompatibilityRules rules(version);
    for (bool admin : {false, true}) {
      rules.setIsAdmin(admin);
      EXPECT_EQ(rules.isLegacy(), uint64_t(version) == UINT64_C(0));
      digest.rules(rules);
    }
  }
  digest.emit("legacy-exact-zero");
}

TEST(NetRules, EqualityAndHashIgnoreAdminAcrossAllEdgePairs) {
  RulesDigest digest;
  for (uint32_t a : RulesEdges) for (uint32_t b : RulesEdges) {
    for (bool aa : {false, true}) for (bool ba : {false, true}) {
      NetCompatibilityRules left(a), right(b);
      left.setIsAdmin(aa); right.setIsAdmin(ba);
      bool expected = uint64_t(a) == uint64_t(b);
      EXPECT_EQ(left == right, expected);
      EXPECT_EQ(right == left, expected);
      EXPECT_EQ(left == left, true);
      EXPECT_EQ(Star::hash<NetCompatibilityRules>{}(left), size_t(a));
      EXPECT_EQ(Star::hash<NetCompatibilityRules>{}(right), size_t(b));
      digest.add(left == right); digest.rules(left); digest.rules(right);
    }
  }
  digest.emit("version-only-equality-hash-edges");
}

TEST(NetRules, Seeded100kIndependentLogicalOracle) {
  uint64_t seed = UINT64_C(0xe7037ed1a0b428db);
  RulesDigest digest;
  for (unsigned i = 0; i != 100000; ++i) {
    seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17;
    uint32_t a = uint32_t(seed);
    uint32_t b = i % 3 == 0 ? a : uint32_t(seed >> 32);
    bool aa = (i & 1) != 0, ba = (i & 2) != 0;
    NetCompatibilityRules left(a), right(b);
    left.setIsAdmin(aa); right.setIsAdmin(ba);
    // Widened arithmetic is independent of candidate equality/legacy kernels.
    bool equal = uint64_t(a) - uint64_t(b) == UINT64_C(0);
    EXPECT_EQ(left == right, equal);
    expectRules(left, a, aa); expectRules(right, b, ba);
    digest.add(left == right); digest.rules(left); digest.rules(right);
    left.setVersion(b); right.setIsAdmin(!ba);
    expectRules(left, b, aa); expectRules(right, b, !ba);
    EXPECT_TRUE(left == right);
    digest.rules(left); digest.rules(right);
  }
  digest.emit("seeded-100k-logical-oracle");
}

TEST(NetRules, CopiesMovesAssignmentsAndSelfAssignmentAreIndependent) {
  NetCompatibilityRules source(VersionNumber(17));
  source.setIsAdmin(true);
  NetCompatibilityRules copied(source);
  NetCompatibilityRules moved(std::move(copied));
  NetCompatibilityRules assigned, moveAssigned;
  assigned = source;
  moveAssigned = std::move(assigned);
  auto* self = &source;
  source = *self;
  source = std::move(*self);
  expectRules(source, 17, true);
  expectRules(copied, 17, true); expectRules(assigned, 17, true);
  moved.setVersion(0); moved.setIsAdmin(false);
  moveAssigned.setVersion(RulesMax);
  expectRules(source, 17, true);
  expectRules(moved, 0, false); expectRules(moveAssigned, RulesMax, true);
  RulesDigest digest;
  for (auto const* r : {&source, &copied, &moved, &assigned, &moveAssigned}) digest.rules(*r);
  digest.emit("copy-move-assignment-self");
}

TEST(NetRules, ByValueArraysAndVectorsPreserveIndependentLogicalState) {
  NetCompatibilityRules source(VersionNumber(11));
  source.setIsAdmin(true);
  auto returned = changeRulesByValue(source);
  expectRules(source, 11, true); expectRules(returned, 0x80000000, false);
  std::array<NetCompatibilityRules, 3> array{};
  array[1] = source;
  auto copied = array;
  copied[1].setVersion(RulesMax); copied[1].setIsAdmin(false);
  std::vector<NetCompatibilityRules> vector(2, source);
  vector.reserve(17);
  vector.push_back(returned);
  vector[0].setVersion(0); vector[0].setIsAdmin(false);
  expectRules(array[0], OpenProtocolVersion, false);
  expectRules(array[1], 11, true); expectRules(array[2], OpenProtocolVersion, false);
  expectRules(copied[1], RulesMax, false);
  expectRules(vector[0], 0, false); expectRules(vector[1], 11, true);
  expectRules(vector[2], 0x80000000, false);
  RulesDigest digest; digest.rules(source); digest.rules(returned);
  for (auto const& r : array) digest.rules(r);
  for (auto const& r : copied) digest.rules(r);
  for (auto const& r : vector) digest.rules(r);
  digest.emit("by-value-array-vector");
}

TEST(NetRules, NativeObservedLayoutAndValueTraits) {
  static_assert(std::is_same<VersionNumber, uint32_t>::value, "version width");
  static_assert(std::is_standard_layout<NetCompatibilityRules>::value, "standard layout");
  static_assert(std::is_trivially_copyable<NetCompatibilityRules>::value, "trivial copies");
  static_assert(std::is_trivially_destructible<NetCompatibilityRules>::value, "no drop");
  static_assert(std::is_nothrow_copy_constructible<NetCompatibilityRules>::value, "nothrow copy");
  static_assert(std::is_nothrow_move_constructible<NetCompatibilityRules>::value, "nothrow move");
  static_assert(std::is_nothrow_copy_assignable<NetCompatibilityRules>::value, "nothrow assignment");
  static_assert(std::is_nothrow_move_assignable<NetCompatibilityRules>::value, "nothrow move assignment");
  static_assert(std::is_constructible<NetCompatibilityRules, uint32_t>::value, "u32 API");
  static_assert(!std::is_constructible<NetCompatibilityRules, uint64_t>::value, "deleted wide API");
  static_assert(!std::is_trivially_default_constructible<NetCompatibilityRules>::value,
      "native default constructor is user-provided, not a zero/constexpr contract");
  RulesDigest digest;
  // Record this platform's observations; do not infer native bool/padding bytes.
  digest.add(sizeof(NetCompatibilityRules)); digest.add(alignof(NetCompatibilityRules));
  digest.add(sizeof(bool)); digest.add(alignof(uint32_t));
  digest.emit("native-observed-layout-traits");
  std::cout << "NET_RULES_TRACE native-observed-layout-values "
      << sizeof(NetCompatibilityRules) << ' ' << alignof(NetCompatibilityRules)
      << ' ' << sizeof(bool) << ' ' << alignof(uint32_t) << '\n';
}

TEST(NetRules, DataStreamConfigurationCopiesVersionNotAdminOrLiveReference) {
  RulesDigest digest;
  DataStreamBuffer stream;
  for (uint32_t version : RulesEdges) {
    NetCompatibilityRules rules(version);
    rules.setIsAdmin(true);
    stream.setStreamCompatibilityVersion(rules);
    EXPECT_EQ(stream.streamCompatibilityVersion(), unsigned(version));
    auto copied = stream;
    rules.setVersion(version ^ RulesMax); rules.setIsAdmin(false);
    EXPECT_EQ(stream.streamCompatibilityVersion(), unsigned(version));
    EXPECT_EQ(copied.streamCompatibilityVersion(), unsigned(version));
    stream.setStreamCompatibilityVersion(rules);
    EXPECT_EQ(stream.streamCompatibilityVersion(), unsigned(version ^ RulesMax));
    EXPECT_EQ(copied.streamCompatibilityVersion(), unsigned(version));
    digest.add(stream.streamCompatibilityVersion()); digest.add(copied.streamCompatibilityVersion());
  }
  digest.emit("data-stream-config-copy");
}

#ifdef STAR_USE_RUST_NET_GROUP
namespace {
constexpr uint32_t RInit = 0, RVersion = 1, RSetVersion = 2, RAdmin = 3,
    RSetAdmin = 4, RLegacy = 5, REqualVersion = 6, RCount = 7;
constexpr uint32_t ROk = 0, RInvalid = 1;
static_assert(RInit == SB_NET_RULES_INIT && RVersion == SB_NET_RULES_VERSION &&
    RSetVersion == SB_NET_RULES_SET_VERSION && RAdmin == SB_NET_RULES_ADMIN &&
    RSetAdmin == SB_NET_RULES_SET_ADMIN && RLegacy == SB_NET_RULES_LEGACY &&
    REqualVersion == SB_NET_RULES_EQUAL_VERSION && RCount == SB_NET_RULES_COUNT,
    "seven rules modes");
static_assert(ROk == SB_NET_RULES_OK && RInvalid == SB_NET_RULES_INVALID, "rules status ABI");
static_assert(sizeof(SbNetRulesStorage) == 8, "opaque rules width");
static_assert(alignof(SbNetRulesStorage) == alignof(uint32_t), "native word alignment");
struct alignas(uint32_t) RawRules { unsigned char bytes[8]; };
struct GuardedRules {
  uint32_t before = 0x12345678;
  RawRules state{};
  uint32_t after = 0x87654321;
};
std::array<uint64_t, RCount> rulesCounts() {
  std::array<uint64_t, RCount> result{};
  for (uint32_t i = 0; i != RCount; ++i) result[i] = sb_net_rules_count(0, i);
  return result;
}
void rawRulesCanaries(GuardedRules const& g) {
  EXPECT_EQ(g.before, uint32_t(0x12345678));
  EXPECT_EQ(g.after, uint32_t(0x87654321));
}
}

TEST(NetRules, RustRawInitAndFieldWritesPreserveOtherBytes) {
  GuardedRules g;
  uint32_t out = 19;
  for (uint32_t version : RulesEdges) {
    std::memset(g.state.bytes, 0xa5, 8);
    EXPECT_EQ(sb_net_rules_run(RInit, &g.state, version, &out), ROk);
    EXPECT_EQ(out, version);
    uint32_t word = 0;
    std::memcpy(&word, g.state.bytes, 4);
    EXPECT_EQ(word, version);
    for (unsigned i = 4; i != 8; ++i) EXPECT_EQ(g.state.bytes[i], 0);
    // Reserved bytes are a raw ABI concern, never native-class padding tests.
    g.state.bytes[5] = 0x91; g.state.bytes[6] = 0x92; g.state.bytes[7] = 0x93;
    EXPECT_EQ(sb_net_rules_run(RSetAdmin, &g.state, 1, &out), ROk);
    EXPECT_EQ(out, uint32_t(1)); EXPECT_EQ(g.state.bytes[4], 1);
    std::memcpy(&word, g.state.bytes, 4);
    EXPECT_EQ(word, version);
    EXPECT_EQ(sb_net_rules_run(RSetVersion, &g.state, version ^ RulesMax, &out), ROk);
    EXPECT_EQ(out, version ^ RulesMax);
    EXPECT_EQ(g.state.bytes[4], 1);
    EXPECT_EQ(sb_net_rules_run(RSetAdmin, &g.state, 0, &out), ROk);
    EXPECT_EQ(out, uint32_t(0)); EXPECT_EQ(g.state.bytes[4], 0);
    std::memcpy(&word, g.state.bytes, 4);
    EXPECT_EQ(word, version ^ RulesMax);
    EXPECT_EQ(g.state.bytes[5], 0x91); EXPECT_EQ(g.state.bytes[6], 0x92);
    EXPECT_EQ(g.state.bytes[7], 0x93);
    // A noncanonical raw admin byte must not affect version-only operations.
    g.state.bytes[4] = 0xe7;
    EXPECT_EQ(sb_net_rules_run(RVersion, &g.state, 0, &out), ROk);
    EXPECT_EQ(out, word);
    EXPECT_EQ(sb_net_rules_run(RLegacy, &g.state, 0, &out), ROk);
    EXPECT_EQ(out, uint32_t(word == 0));
    EXPECT_EQ(sb_net_rules_run(REqualVersion, &g.state, word, &out), ROk);
    EXPECT_EQ(out, uint32_t(1));
    EXPECT_EQ(sb_net_rules_run(RSetVersion, &g.state, version, &out), ROk);
    EXPECT_EQ(g.state.bytes[4], 0xe7);
    rawRulesCanaries(g);
  }
}

TEST(NetRules, RustImmutableGettersEqualityAndCanaries) {
  for (uint32_t version : RulesEdges) for (uint32_t admin : {0u, 1u}) {
    GuardedRules seed;
    uint32_t out = 0;
    ASSERT_EQ(sb_net_rules_run(RInit, &seed.state, version, &out), ROk);
    ASSERT_EQ(sb_net_rules_run(RSetAdmin, &seed.state, admin, &out), ROk);
    GuardedRules const immutable = seed;
    struct { uint32_t before = 23; uint32_t value = 17; uint32_t after = 29; } output;
    EXPECT_EQ(sb_net_rules_run(RVersion, &immutable.state, 0, &output.value), ROk);
    EXPECT_EQ(output.value, version);
    EXPECT_EQ(sb_net_rules_run(RAdmin, &immutable.state, 0, &output.value), ROk);
    EXPECT_EQ(output.value, admin);
    EXPECT_EQ(sb_net_rules_run(RLegacy, &immutable.state, 0, &output.value), ROk);
    EXPECT_EQ(output.value, uint32_t(version == 0));
    for (uint32_t other : RulesEdges) {
      EXPECT_EQ(sb_net_rules_run(REqualVersion, &immutable.state, other, &output.value), ROk);
      EXPECT_EQ(output.value, uint32_t(uint64_t(version) == uint64_t(other)));
    }
    EXPECT_EQ(std::memcmp(immutable.state.bytes, seed.state.bytes, 8), 0);
    rawRulesCanaries(immutable);
    EXPECT_EQ(output.before, uint32_t(23)); EXPECT_EQ(output.after, uint32_t(29));
  }
}

TEST(NetRules, RustInvalidArgumentsRejectBeforeCountsAndWrites) {
  GuardedRules g;
  uint32_t out = 0xabcdef01;
  ASSERT_EQ(sb_net_rules_run(RInit, &g.state, 0x80000000, &out), ROk);
  auto saved = g.state;
  out = 0xabcdef01;
  alignas(uint32_t) unsigned char bad[16];
  std::memset(bad, 0x93, sizeof(bad));
  auto counts = rulesCounts();
  for (uint32_t mode = 0; mode != RCount; ++mode) {
    EXPECT_EQ(sb_net_rules_run(mode, nullptr, 0, &out), RInvalid);
    EXPECT_EQ(sb_net_rules_run(mode, &g.state, 0, nullptr), RInvalid);
    EXPECT_EQ(sb_net_rules_run(mode, bad + 1, 0, &out), RInvalid);
    EXPECT_EQ(sb_net_rules_run(mode, &g.state, 0, reinterpret_cast<uint32_t*>(bad + 1)), RInvalid);
    for (unsigned offset : {0u, 4u}) {
      auto alias = reinterpret_cast<uint32_t*>(g.state.bytes + offset);
      EXPECT_EQ(sb_net_rules_run(mode, &g.state, 0, alias), RInvalid);
    }
  }
  for (uint32_t mode : {RVersion, RAdmin, RLegacy})
    for (uint32_t arg : {1u, RulesMax})
      EXPECT_EQ(sb_net_rules_run(mode, &g.state, arg, &out), RInvalid);
  for (uint32_t arg : {2u, RulesMax})
    EXPECT_EQ(sb_net_rules_run(RSetAdmin, &g.state, arg, &out), RInvalid);
  for (uint32_t mode : {RCount, RulesMax})
    EXPECT_EQ(sb_net_rules_run(mode, &g.state, 0, &out), RInvalid);
  EXPECT_EQ(out, uint32_t(0xabcdef01));
  EXPECT_EQ(std::memcmp(g.state.bytes, saved.bytes, 8), 0);
  for (auto byte : bad) EXPECT_EQ(byte, 0x93);
  rawRulesCanaries(g);
  EXPECT_EQ(rulesCounts(), counts);
  // Raw ABI admin-domain errors are not invalid C++ bool objects.
  g.state.bytes[4] = 2;
  auto invalidAdmin = g.state;
  EXPECT_EQ(sb_net_rules_run(RAdmin, &g.state, 0, &out), RInvalid);
  EXPECT_EQ(std::memcmp(g.state.bytes, invalidAdmin.bytes, 8), 0);
  EXPECT_EQ(out, uint32_t(0xabcdef01));
  EXPECT_EQ(rulesCounts(), counts);
  for (uint32_t kind : {0u, 1u}) {
    EXPECT_EQ(sb_net_rules_count(kind, RCount), uint64_t(0));
    EXPECT_EQ(sb_net_rules_count(kind, RulesMax), uint64_t(0));
  }
  EXPECT_EQ(sb_net_rules_count(2, RVersion), uint64_t(0));
}

TEST(NetRules, RustCppNaturalEntriesCopiesAndLazyAnyGetterGuard) {
  auto initial = rulesCounts();
  NetCompatibilityRules left;
  NetCompatibilityRules right(VersionNumber(0x80000000));
  auto constructed = rulesCounts();
  EXPECT_EQ(constructed[RInit] - initial[RInit], uint64_t(2));
  for (uint32_t i = 1; i != RCount; ++i) EXPECT_EQ(constructed[i], initial[i]);
  NetCompatibilityRules copied(left);
  auto moved = std::move(copied);
  copied = right;
  moved = std::move(copied);
  EXPECT_EQ(rulesCounts(), constructed);
  auto before = rulesCounts();
  EXPECT_EQ(right.version(), uint32_t(0x80000000));
  right.setVersion(0);
  EXPECT_FALSE(right.isAdmin());
  right.setIsAdmin(true);
  EXPECT_TRUE(right.isLegacy());
  EXPECT_EQ(left == right, OpenProtocolVersion == uint32_t(0)); // RHS VERSION, then left EQUAL_VERSION.
  auto after = rulesCounts();
  for (uint32_t mode = 0; mode != RCount; ++mode) {
    uint64_t expected = mode == RInit ? 0 : mode == RVersion ? 2 : 1;
    EXPECT_EQ(after[mode] - before[mode], expected);
  }
  struct AnyProbe : NetElement {
    void initNetVersion(NetElementVersion const*) override {}
    void netStore(DataStream&, NetCompatibilityRules) const override {}
    void netLoad(DataStream&, NetCompatibilityRules) override {}
    bool writeNetDelta(DataStream&, uint64_t, NetCompatibilityRules) const override { return false; }
    void readNetDelta(DataStream&, float, NetCompatibilityRules) override {}
  } probe;
  // Construct rules before the baseline: this proves no VERSION ABI entry,
  // not a generic physical-memory-read claim. Source establishes guard order.
  before = rulesCounts();
  EXPECT_TRUE(probe.checkWithRules(right));
  EXPECT_EQ(rulesCounts(), before);
  probe.setCompatibilityVersion(1);
  EXPECT_FALSE(probe.checkWithRules(right));
  after = rulesCounts();
  for (uint32_t mode = 0; mode != RCount; ++mode)
    EXPECT_EQ(after[mode] - before[mode], uint64_t(mode == RVersion));
  std::cout << "NET_RULES_DIAGNOSTIC init-2 copies-no-init equality-rhs-version any-no-rules-entry\n";
}
#endif
