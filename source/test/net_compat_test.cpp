#include "StarNetElement.hpp"
#include "gtest/gtest.h"

#include <array>
#include <cstring>
#include <iostream>
#include <limits>
#include <type_traits>
#include <vector>

#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetCompat.h"
#include "StarRustNetScalar.h"
#endif

using namespace Star;

namespace {
constexpr uint32_t CompatMax = std::numeric_limits<uint32_t>::max();
static_assert(std::is_same<VersionNumber, uint32_t>::value, "native compatibility width");
static_assert(std::has_virtual_destructor<NetElement>::value, "base destruction remains virtual");
static_assert(std::is_copy_assignable<NetElement>::value, "native base assignment remains public");

struct CompatProbe : NetElement {
  uint32_t before = 0x12345678;
  uint32_t payload = 0x87654321;
  uint32_t after = 0xa5a55a5a;
  unsigned calls = 0;
  void initNetVersion(NetElementVersion const*) override { calls += 1; }
  void netStore(DataStream&, NetCompatibilityRules) const override {}
  void netLoad(DataStream&, NetCompatibilityRules) override { calls += 2; }
  bool writeNetDelta(DataStream&, uint64_t, NetCompatibilityRules) const override { return payload != 0; }
  void readNetDelta(DataStream&, float, NetCompatibilityRules) override { calls += 4; }
  void enableNetInterpolation(float) override { calls += 8; }
  void disableNetInterpolation() override { calls += 16; }
  void tickNetInterpolation(float) override { calls += 32; }
  void blankNetDelta(float) override { calls += 64; }
};

struct CompatDigest {
  uint64_t value = UINT64_C(14695981039346656037);
  void add(uint64_t word) {
    for (unsigned i = 0; i != 8; ++i) {
      value ^= (word >> (8 * i)) & 255;
      value *= UINT64_C(1099511628211);
    }
  }
  void probe(CompatProbe const& p) {
    add(p.compatibilityVersion()); add(p.before); add(p.payload); add(p.after); add(p.calls);
  }
  void emit(char const* name) const {
    std::cout << "NET_COMPAT_TRACE " << name << ' ' << value << '\n';
  }
};

void expectPayload(CompatProbe const& p, uint32_t payload = 0x87654321) {
  EXPECT_EQ(p.before, uint32_t(0x12345678));
  EXPECT_EQ(p.payload, payload);
  EXPECT_EQ(p.after, uint32_t(0xa5a55a5a));
}

CompatProbe changeByValue(CompatProbe value) {
  value.setCompatibilityVersion(0x80000000);
  value.payload = 7;
  return value;
}

int compatDestructions = 0;
struct CompatLifetime : CompatProbe {
  ~CompatLifetime() override { ++compatDestructions; }
};
}

TEST(NetCompat, DefaultAnyAndRepeatedSetPreservePayload) {
  CompatProbe plain;
  CompatProbe braces{};
  EXPECT_EQ(plain.compatibilityVersion(), AnyVersion);
  EXPECT_EQ(braces.compatibilityVersion(), AnyVersion);
  CompatDigest digest;
  for (uint32_t version : {uint32_t(0), uint32_t(1), uint32_t(0x7fffffff),
      uint32_t(0x80000000), CompatMax - 1, CompatMax}) {
    plain.setCompatibilityVersion(version);
    EXPECT_EQ(plain.compatibilityVersion(), version);
    EXPECT_EQ(plain.compatibilityVersion(), version);
    expectPayload(plain);
    EXPECT_EQ(plain.calls, 0u);
    digest.probe(plain);
  }
  digest.probe(braces);
  digest.emit("default-set-unsigned-edges");
}

TEST(NetCompat, UnsignedRulesAndAdminDoNotAlterStoredProperty) {
  CompatProbe p;
  CompatDigest digest;
  for (uint32_t version : {uint32_t(0), uint32_t(1), uint32_t(0x7fffffff),
      uint32_t(0x80000000), CompatMax - 1, CompatMax}) {
    p.setCompatibilityVersion(version);
    for (uint32_t rule : {uint32_t(0), uint32_t(1), uint32_t(0x7fffffff),
        uint32_t(0x80000000), CompatMax - 1, CompatMax}) {
      NetCompatibilityRules rules(rule);
      for (bool admin : {false, true}) {
        rules.setIsAdmin(admin);
        bool expected = version == AnyVersion || uint64_t(rule) >= uint64_t(version);
        EXPECT_EQ(p.checkWithRules(rules), expected);
        EXPECT_EQ(p.compatibilityVersion(), version);
        expectPayload(p);
        digest.add(expected); digest.add(p.checkWithRules(rules));
      }
    }
  }
  digest.emit("unsigned-rules-admin-ignored");
}

TEST(NetCompat, DerivedCopiesAssignmentsAndSelfAssignmentAreIndependent) {
  CompatProbe original;
  original.setCompatibilityVersion(0x80000000);
  original.payload = 19;
  CompatProbe copied(original);
  CompatProbe assigned;
  assigned = original;
  auto* self = &original;
  original = *self;
  EXPECT_EQ(original.compatibilityVersion(), uint32_t(0x80000000));
  expectPayload(original, 19);
  copied.setCompatibilityVersion(0);
  copied.payload = 23;
  assigned.setCompatibilityVersion(CompatMax - 1);
  assigned.payload = 29;
  EXPECT_EQ(original.compatibilityVersion(), uint32_t(0x80000000));
  EXPECT_EQ(copied.compatibilityVersion(), uint32_t(0));
  EXPECT_EQ(assigned.compatibilityVersion(), CompatMax - 1);
  expectPayload(original, 19); expectPayload(copied, 23); expectPayload(assigned, 29);
  CompatDigest digest;
  digest.probe(original); digest.probe(copied); digest.probe(assigned);
  digest.emit("derived-copy-self-assignment");
}

TEST(NetCompat, BaseAssignmentCopiesOnlyBaseAndPreservesDerivedPayload) {
  CompatProbe source;
  CompatProbe target;
  source.setCompatibilityVersion(0x80000001);
  source.payload = 41;
  target.payload = 43;
  target.calls = 17;
  NetElement& base = target;
  base = static_cast<NetElement const&>(source);
  EXPECT_EQ(target.compatibilityVersion(), uint32_t(0x80000001));
  expectPayload(target, 43);
  EXPECT_EQ(target.calls, 17u);
  auto* self = &base;
  base = *self;
  target.setCompatibilityVersion(0);
  EXPECT_EQ(source.compatibilityVersion(), uint32_t(0x80000001));
  expectPayload(source, 41);
  CompatDigest digest; digest.probe(source); digest.probe(target);
  digest.emit("base-assignment-independent-payload");
}

TEST(NetCompat, ByValueReturnAndContainersPreserveIndependentState) {
  CompatProbe source;
  source.setCompatibilityVersion(11);
  auto returned = changeByValue(source);
  EXPECT_EQ(source.compatibilityVersion(), uint32_t(11));
  EXPECT_EQ(returned.compatibilityVersion(), uint32_t(0x80000000));
  expectPayload(source); expectPayload(returned, 7);
  std::array<CompatProbe, 3> array{};
  std::vector<CompatProbe> vector(2, source);
  array[1] = returned;
  auto arrayCopy = array;
  arrayCopy[1].setCompatibilityVersion(3);
  arrayCopy[1].payload = 31;
  vector[0].setCompatibilityVersion(5);
  EXPECT_EQ(array[0].compatibilityVersion(), AnyVersion);
  EXPECT_EQ(array[1].compatibilityVersion(), uint32_t(0x80000000));
  EXPECT_EQ(array[2].compatibilityVersion(), AnyVersion);
  EXPECT_EQ(arrayCopy[1].compatibilityVersion(), uint32_t(3));
  EXPECT_EQ(vector[1].compatibilityVersion(), uint32_t(11));
  expectPayload(array[1], 7); expectPayload(arrayCopy[1], 31);
  CompatDigest digest;
  digest.probe(source); digest.probe(returned);
  for (auto const& p : array) digest.probe(p);
  for (auto const& p : arrayCopy) digest.probe(p);
  for (auto const& p : vector) digest.probe(p);
  digest.emit("by-value-array-vector");
}

TEST(NetCompat, NativeObservedLayoutAndVirtualDispatchRemainStable) {
  CompatProbe p;
  // Address differences stay inside this live object; no offsetof on a
  // polymorphic type, private-member aliasing, or whole-object byte seeding.
  auto start = reinterpret_cast<unsigned char const*>(&p);
  auto payload = reinterpret_cast<unsigned char const*>(&p.payload);
  auto relative = payload - start;
  EXPECT_GE(relative, 0);
  EXPECT_LT(size_t(relative), sizeof(p));
  NetElement& base = p;
  base.initNetVersion();
  base.enableNetInterpolation();
  base.disableNetInterpolation();
  base.tickNetInterpolation(0.5f);
  base.blankNetDelta(0.5f);
  EXPECT_EQ(p.calls, 121u);
  EXPECT_EQ(base.compatibilityVersion(), AnyVersion);
  base.setCompatibilityVersion(17);
  EXPECT_TRUE(base.checkWithRules(NetCompatibilityRules(VersionNumber(17))));
  expectPayload(p);
  CompatDigest digest;
  digest.add(sizeof(NetElement)); digest.add(alignof(NetElement));
  digest.add(sizeof(CompatProbe)); digest.add(alignof(CompatProbe));
  digest.add(uint64_t(relative)); digest.probe(p);
  digest.emit("native-observed-layout-virtual-api");
}

TEST(NetCompat, ConstructionAndVirtualDestructionHaveNoExtraHooks) {
  int before = compatDestructions;
  {
    CompatLifetime local;
    EXPECT_EQ(local.calls, 0u);
    EXPECT_EQ(local.compatibilityVersion(), AnyVersion);
    EXPECT_EQ(compatDestructions, before);
  }
  EXPECT_EQ(compatDestructions, before + 1);
  CompatDigest digest; digest.add(compatDestructions - before);
  digest.emit("construction-destruction");
}

#ifdef STAR_USE_RUST_NET_GROUP
namespace {
constexpr uint32_t CompatInit = 0, CompatValue = 1, CompatSet = 2, CompatCheck = 3, CompatCount = 4;
constexpr uint32_t CompatOk = 0, CompatInvalid = 1;
static_assert(CompatInit == SB_NET_COMPAT_INIT_ANY && CompatValue == SB_NET_COMPAT_VALUE &&
    CompatSet == SB_NET_COMPAT_SET && CompatCheck == SB_NET_COMPAT_CHECK &&
    CompatCount == SB_NET_COMPAT_COUNT, "four compatibility modes");
static_assert(CompatOk == SB_NET_COMPAT_OK && CompatInvalid == SB_NET_COMPAT_INVALID, "status ABI");
static_assert(SB_NET_SCALAR_COMPAT == 6 && SB_NET_SCALAR_COUNT == 7, "existing scalar diagnostic indices");
static_assert(sizeof(SbNetCompatStorage) == 4, "opaque compatibility width");
static_assert(alignof(SbNetCompatStorage) == alignof(uint32_t), "native word alignment");
struct GuardedCompat {
  uint32_t before = 0x12345678;
  SbNetCompatStorage storage = SB_NET_COMPAT_ANY_INITIALIZER;
  uint32_t after = 0x87654321;
};
std::array<uint64_t, CompatCount> compatCounts() {
  std::array<uint64_t, CompatCount> result{};
  for (uint32_t i = 0; i != CompatCount; ++i) result[i] = sb_net_compat_count(0, i);
  return result;
}
}

TEST(NetCompat, RustRawDefaultInitSetValueAndCheckKeepCanaries) {
  auto counts = compatCounts();
  auto scalar = sb_net_scalar_count(0, SB_NET_SCALAR_COMPAT);
  GuardedCompat guarded;
  uint32_t out = 7;
  EXPECT_EQ(sb_net_compat_run(CompatValue, &guarded.storage, 0, &out), CompatOk);
  EXPECT_EQ(out, CompatMax);
  SbNetCompatStorage zero{};
  EXPECT_EQ(sb_net_compat_run(CompatValue, &zero, 0, &out), CompatOk);
  EXPECT_EQ(out, uint32_t(0));
  EXPECT_EQ(sb_net_compat_run(CompatInit, &zero, 0, &out), CompatOk);
  EXPECT_EQ(out, CompatMax);
  for (auto byte : zero.bytes) EXPECT_EQ(byte, 0xff);
  for (uint32_t v : {uint32_t(0), uint32_t(0x80000000), CompatMax - 1, CompatMax}) {
    EXPECT_EQ(sb_net_compat_run(CompatSet, &guarded.storage, v, &out), CompatOk);
    EXPECT_EQ(out, v);
    EXPECT_EQ(sb_net_compat_run(CompatValue, &guarded.storage, 0, &out), CompatOk);
    EXPECT_EQ(out, v);
    EXPECT_EQ(sb_net_compat_run(CompatCheck, &guarded.storage, 0x7fffffff, &out), CompatOk);
    EXPECT_EQ(out, uint32_t(v == CompatMax || v <= 0x7fffffff));
  }
  EXPECT_EQ(guarded.before, uint32_t(0x12345678));
  EXPECT_EQ(guarded.after, uint32_t(0x87654321));
  auto after = compatCounts();
  EXPECT_EQ(after[CompatInit] - counts[CompatInit], uint64_t(1));
  EXPECT_EQ(after[CompatValue] - counts[CompatValue], uint64_t(6));
  EXPECT_EQ(after[CompatSet] - counts[CompatSet], uint64_t(4));
  EXPECT_EQ(after[CompatCheck] - counts[CompatCheck], uint64_t(4));
  EXPECT_EQ(sb_net_scalar_count(0, SB_NET_SCALAR_COMPAT) - scalar, uint64_t(4));
}

TEST(NetCompat, RustImmutableValueCheckAndWritableWordAliases) {
  GuardedCompat const immutable;
  auto saved = immutable.storage;
  struct { uint32_t before = 23; uint32_t value = 9; uint32_t after = 29; } out;
  EXPECT_EQ(sb_net_compat_run(CompatValue, &immutable.storage, 0, &out.value), CompatOk);
  EXPECT_EQ(out.value, CompatMax);
  EXPECT_EQ(sb_net_compat_run(CompatCheck, &immutable.storage, 0, &out.value), CompatOk);
  EXPECT_EQ(out.value, uint32_t(1));
  EXPECT_EQ(std::memcmp(&immutable.storage, &saved, sizeof(saved)), 0);
  EXPECT_EQ(immutable.before, uint32_t(0x12345678));
  EXPECT_EQ(immutable.after, uint32_t(0x87654321));
  EXPECT_EQ(out.before, uint32_t(23)); EXPECT_EQ(out.after, uint32_t(29));
  GuardedCompat seeded;
  EXPECT_EQ(sb_net_compat_run(CompatSet, &seeded.storage, 0x80000000, &out.value), CompatOk);
  GuardedCompat const high = seeded;
  for (uint32_t rule : {uint32_t(0x7fffffff), uint32_t(0x80000000), CompatMax}) {
    EXPECT_EQ(sb_net_compat_run(CompatCheck, &high.storage, rule, &out.value), CompatOk);
    EXPECT_EQ(out.value, uint32_t(rule >= 0x80000000));
    EXPECT_EQ(std::memcmp(&high.storage, &seeded.storage, sizeof(high.storage)), 0);
    EXPECT_EQ(high.before, seeded.before); EXPECT_EQ(high.after, seeded.after);
    EXPECT_EQ(out.before, uint32_t(23)); EXPECT_EQ(out.after, uint32_t(29));
  }
  uint32_t word = 0;
  EXPECT_EQ(sb_net_compat_run(CompatInit, &word, 0, &word), CompatOk);
  EXPECT_EQ(word, CompatMax);
  EXPECT_EQ(sb_net_compat_run(CompatSet, &word, 0x80000000, &word), CompatOk);
  EXPECT_EQ(word, uint32_t(0x80000000));
  EXPECT_EQ(sb_net_compat_run(CompatValue, &word, 0, &word), CompatOk);
  EXPECT_EQ(word, uint32_t(0x80000000));
  auto counts = compatCounts();
  auto scalar = sb_net_scalar_count(0, SB_NET_SCALAR_COMPAT);
  EXPECT_EQ(sb_net_compat_run(CompatCheck, &word, CompatMax, &word), CompatInvalid);
  EXPECT_EQ(word, uint32_t(0x80000000));
  EXPECT_EQ(compatCounts(), counts);
  EXPECT_EQ(sb_net_scalar_count(0, SB_NET_SCALAR_COMPAT), scalar);
}

TEST(NetCompat, RustInvalidArgumentsPreserveAllBytesAndDiagnostics) {
  GuardedCompat guarded;
  auto saved = guarded.storage;
  uint32_t out = 0xabcdef01;
  alignas(uint32_t) unsigned char bad[16];
  std::memset(bad, 0x93, sizeof(bad));
  std::array<unsigned char, 16> savedBad{};
  std::memcpy(savedBad.data(), bad, sizeof(bad));
  auto counts = compatCounts();
  auto scalar = sb_net_scalar_count(0, SB_NET_SCALAR_COMPAT);
  for (uint32_t mode = 0; mode != CompatCount; ++mode) {
    EXPECT_EQ(sb_net_compat_run(mode, nullptr, 0, &out), CompatInvalid);
    EXPECT_EQ(sb_net_compat_run(mode, &guarded.storage, 0, nullptr), CompatInvalid);
    EXPECT_EQ(sb_net_compat_run(mode, bad + 1, 0, &out), CompatInvalid);
    EXPECT_EQ(sb_net_compat_run(mode, &guarded.storage, 0,
        reinterpret_cast<uint32_t*>(bad + 1)), CompatInvalid);
  }
  for (uint32_t mode : {CompatInit, CompatValue})
    EXPECT_EQ(sb_net_compat_run(mode, &guarded.storage, 1, &out), CompatInvalid);
  for (uint32_t mode : {CompatCount, CompatMax})
    EXPECT_EQ(sb_net_compat_run(mode, &guarded.storage, 0, &out), CompatInvalid);
  EXPECT_EQ(out, uint32_t(0xabcdef01));
  EXPECT_EQ(std::memcmp(&guarded.storage, &saved, sizeof(saved)), 0);
  EXPECT_EQ(guarded.before, uint32_t(0x12345678));
  EXPECT_EQ(guarded.after, uint32_t(0x87654321));
  EXPECT_EQ(std::memcmp(bad, savedBad.data(), sizeof(bad)), 0);
  EXPECT_EQ(compatCounts(), counts);
  EXPECT_EQ(sb_net_scalar_count(0, SB_NET_SCALAR_COMPAT), scalar);
  for (uint32_t kind : {uint32_t(0), uint32_t(1)}) {
    EXPECT_EQ(sb_net_compat_count(kind, CompatCount), uint64_t(0));
    EXPECT_EQ(sb_net_compat_count(kind, CompatMax), uint64_t(0));
  }
  EXPECT_EQ(sb_net_compat_count(2, CompatValue), uint64_t(0));
}

TEST(NetCompat, RustCppAnyUsesValueButSkipsCheckAndNeverCallsInit) {
  auto counts = compatCounts();
  auto scalar = sb_net_scalar_count(0, SB_NET_SCALAR_COMPAT);
  {
    CompatProbe p;
    EXPECT_EQ(compatCounts(), counts); // No FFI construction or destruction hook.
    EXPECT_TRUE(p.checkWithRules(NetCompatibilityRules(VersionNumber(0))));
    auto any = compatCounts();
    EXPECT_EQ(any[CompatValue] - counts[CompatValue], uint64_t(1));
    EXPECT_EQ(any[CompatCheck], counts[CompatCheck]);
    EXPECT_EQ(sb_net_scalar_count(0, SB_NET_SCALAR_COMPAT), scalar);
    p.setCompatibilityVersion(0x80000000);
    EXPECT_FALSE(p.checkWithRules(NetCompatibilityRules(VersionNumber(0x7fffffff))));
    EXPECT_TRUE(p.checkWithRules(NetCompatibilityRules(VersionNumber(0x80000000))));
  }
  auto after = compatCounts();
  EXPECT_EQ(after[CompatInit], counts[CompatInit]);
  EXPECT_EQ(after[CompatValue] - counts[CompatValue], uint64_t(3));
  EXPECT_EQ(after[CompatSet] - counts[CompatSet], uint64_t(1));
  EXPECT_EQ(after[CompatCheck] - counts[CompatCheck], uint64_t(2));
  EXPECT_EQ(sb_net_scalar_count(0, SB_NET_SCALAR_COMPAT) - scalar, uint64_t(2));
  std::cout << "NET_COMPAT_DIAGNOSTIC cpp-default-no-init any-value-no-check check-2 scalar-compat-2\n";
}
#endif
