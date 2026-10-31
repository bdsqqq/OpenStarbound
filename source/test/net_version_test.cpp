#include "StarNetElement.hpp"

#include "gtest/gtest.h"

#include <array>
#include <cstring>
#include <iostream>
#include <limits>
#include <type_traits>
#include <utility>

#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetVersion.h"
#include "StarRustNetScalar.h"
#endif

using namespace Star;

namespace {
static_assert(sizeof(NetElementVersion) == 8, "version stays an eight-byte value");
static_assert(alignof(NetElementVersion) == alignof(uint64_t), "native word alignment");
static_assert(std::is_standard_layout<NetElementVersion>::value, "opaque value layout");
static_assert(std::is_trivially_copyable<NetElementVersion>::value, "byte copies preserve state");
static_assert(std::is_trivially_destructible<NetElementVersion>::value, "no ownership destructor");
static_assert(std::is_nothrow_default_constructible<NetElementVersion>::value, "default zero cannot call throwing FFI");
static_assert(std::is_nothrow_copy_constructible<NetElementVersion>::value, "copy is native POD copying");
static_assert(std::is_nothrow_copy_assignable<NetElementVersion>::value, "assignment is native POD copying");
static_assert(std::is_nothrow_move_constructible<NetElementVersion>::value, "move is native POD copying");
static_assert(std::is_nothrow_move_assignable<NetElementVersion>::value, "move assignment is native POD copying");

// These declarations are the compile-time contract; current() itself is not constexpr.
constexpr NetElementVersion GlobalConstexprVersion;
constexpr uint64_t VersionMax = std::numeric_limits<uint64_t>::max();
using VersionBytes = std::array<unsigned char, 8>;

VersionBytes versionBytes(NetElementVersion const& value) {
  VersionBytes bytes{};
  std::memcpy(bytes.data(), &value, bytes.size());
  return bytes;
}

// Finite native-word ABI fixtures, not type punning through a private member.
NetElementVersion versionSeed(uint64_t seed) {
  NetElementVersion value;
  std::memcpy(&value, &seed, sizeof(seed));
  return value;
}

struct VersionDigest {
  uint64_t value = UINT64_C(14695981039346656037);
  void add(uint64_t word) {
    for (unsigned i = 0; i != 8; ++i) {
      value ^= (word >> (8 * i)) & 255;
      value *= UINT64_C(1099511628211);
    }
  }
  void emit(char const* name) const {
    std::cout << "NET_VERSION_TRACE " << name << ' ' << value << '\n';
  }
};

struct VersionMembers {
  uint64_t before = UINT64_C(0x0123456789abcdef);
  NetElementVersion versions[3];
  uint64_t after = UINT64_C(0xfedcba9876543210);
};

NetElementVersion advanceByValue(NetElementVersion value) {
  value.increment();
  return value;
}

VersionMembers advanceMemberByValue(VersionMembers value) {
  value.versions[1].increment();
  return value;
}
}

TEST(NetVersion, ConstexprGlobalAndLocalDefaultRemainZero) {
  constexpr NetElementVersion local;
  static constexpr NetElementVersion staticLocal;
  EXPECT_EQ(GlobalConstexprVersion.current(), uint64_t(0));
  EXPECT_EQ(local.current(), uint64_t(0));
  EXPECT_EQ(staticLocal.current(), uint64_t(0));
  EXPECT_EQ(versionBytes(GlobalConstexprVersion), VersionBytes{});
  EXPECT_EQ(versionBytes(local), VersionBytes{});
  VersionDigest digest;
  digest.add(GlobalConstexprVersion.current());
  digest.add(local.current());
  digest.add(staticLocal.current());
  digest.emit("constexpr-default");
}

TEST(NetVersion, DefaultInitializationHasZeroObjectRepresentation) {
  NetElementVersion plain;
  NetElementVersion braces{};
  NetElementVersion equals = {};
  EXPECT_EQ(versionBytes(plain), VersionBytes{});
  EXPECT_EQ(versionBytes(braces), VersionBytes{});
  EXPECT_EQ(versionBytes(equals), VersionBytes{});
  EXPECT_EQ(plain.current(), uint64_t(0));
  EXPECT_EQ(braces.current(), uint64_t(0));
  EXPECT_EQ(equals.current(), uint64_t(0));
  VersionDigest digest;
  digest.add(sizeof(plain));
  digest.add(alignof(NetElementVersion));
  digest.add(plain.current());
  digest.emit("zero-pod-layout");
}

TEST(NetVersion, CopiesAssignmentsSelfAssignmentsAndMovesAreIndependent) {
  auto source = versionSeed(UINT64_C(0xfedcba9876543210));
  auto originalBytes = versionBytes(source);
  NetElementVersion copied(source);
  NetElementVersion assigned;
  assigned = source;
  // Indirection avoids compiler self-assignment warnings, without changing semantics.
  auto* self = &source;
  source = *self;
  source = std::move(*self);
  EXPECT_EQ(versionBytes(source), originalBytes);
  NetElementVersion moved(std::move(copied));
  NetElementVersion moveAssigned;
  moveAssigned = std::move(assigned);
  EXPECT_EQ(versionBytes(copied), originalBytes);
  EXPECT_EQ(versionBytes(assigned), originalBytes);
  EXPECT_EQ(versionBytes(moved), originalBytes);
  EXPECT_EQ(versionBytes(moveAssigned), originalBytes);
  EXPECT_EQ(source.increment(), UINT64_C(0xfedcba9876543211));
  EXPECT_EQ(moved.current(), UINT64_C(0xfedcba9876543210));
  EXPECT_EQ(moveAssigned.increment(), UINT64_C(0xfedcba9876543211));
  VersionDigest digest;
  for (auto const* v : {&source, &copied, &assigned, &moved, &moveAssigned})
    digest.add(v->current());
  digest.emit("copy-move-self-assignment");
}

TEST(NetVersion, WordSeedBytesAndNativeUnsignedBoundaryWrap) {
  VersionDigest digest;
  for (uint64_t seed : {uint64_t(0), uint64_t(1), UINT64_C(0xffffffff),
      UINT64_C(0x100000000), UINT64_C(0x8000000000000000), VersionMax - 1, VersionMax}) {
    auto value = versionSeed(seed);
    VersionBytes expectedBytes{};
    std::memcpy(expectedBytes.data(), &seed, sizeof(seed));
    EXPECT_EQ(versionBytes(value), expectedBytes);
    ASSERT_EQ(value.current(), seed);
    uint64_t expected = seed;
    for (unsigned step = 0; step != 3; ++step) {
      ++expected;
      EXPECT_EQ(value.increment(), expected);
      EXPECT_EQ(value.current(), expected);
      std::memcpy(expectedBytes.data(), &expected, sizeof(expected));
      EXPECT_EQ(versionBytes(value), expectedBytes);
      digest.add(expected);
    }
  }
  digest.emit("word-bytes-wrap");
}

TEST(NetVersion, RawByteCopiesRoundTripIntoLiveObjects) {
  VersionDigest digest;
  for (uint64_t seed : {uint64_t(0), UINT64_C(0x0123456789abcdef), VersionMax}) {
    auto source = versionSeed(seed);
    auto bytes = versionBytes(source);
    NetElementVersion destination;
    std::memcpy(&destination, bytes.data(), bytes.size());
    EXPECT_EQ(destination.current(), seed);
    EXPECT_EQ(destination.increment(), seed + uint64_t(1));
    EXPECT_EQ(source.current(), seed);
    EXPECT_EQ(versionBytes(source), bytes);
    digest.add(source.current());
    digest.add(destination.current());
  }
  digest.emit("live-object-byte-roundtrip");
}

TEST(NetVersion, NestedArraysDefaultZeroAndCompositionCopiesOwnTheirState) {
  VersionMembers rows[2];
  VersionDigest digest;
  for (auto const& row : rows)
    for (auto const& value : row.versions) {
      EXPECT_EQ(value.current(), uint64_t(0));
      EXPECT_EQ(versionBytes(value), VersionBytes{});
    }
  rows[0].versions[1] = versionSeed(VersionMax);
  auto copy = rows[0];
  EXPECT_EQ(copy.versions[1].increment(), uint64_t(0));
  EXPECT_EQ(rows[0].versions[1].current(), VersionMax);
  EXPECT_EQ(rows[1].versions[1].current(), uint64_t(0));
  EXPECT_EQ(copy.before, rows[0].before);
  EXPECT_EQ(copy.after, rows[0].after);
  for (auto const& row : rows) {
    digest.add(row.before);
    for (auto const& value : row.versions) digest.add(value.current());
    digest.add(row.after);
  }
  digest.add(copy.versions[1].current());
  digest.emit("nested-array-independent-values");
}

TEST(NetVersion, ByValueArgumentsAndReturnsPreservePublicLibraryBehavior) {
  VersionDigest digest;
  for (uint64_t seed : {uint64_t(0), UINT64_C(0x8000000000000000), VersionMax}) {
    auto input = versionSeed(seed);
    auto result = advanceByValue(input);
    EXPECT_EQ(result.current(), seed + uint64_t(1));
    EXPECT_EQ(input.current(), seed);
    VersionMembers members;
    std::memcpy(&members.versions[1], &input, sizeof(input));
    auto returned = advanceMemberByValue(members);
    EXPECT_EQ(returned.versions[0].current(), uint64_t(0));
    EXPECT_EQ(returned.versions[1].current(), seed + uint64_t(1));
    EXPECT_EQ(returned.versions[2].current(), uint64_t(0));
    EXPECT_EQ(members.versions[1].current(), seed);
    EXPECT_EQ(returned.before, members.before);
    EXPECT_EQ(returned.after, members.after);
    digest.add(input.current());
    digest.add(result.current());
    digest.add(returned.versions[1].current());
  }
  digest.emit("by-value-library-calls");
}

#ifdef STAR_USE_RUST_NET_GROUP
namespace {
// These numeric values intentionally pin the three-mode public ABI.
constexpr uint32_t VersionInit = 0;
constexpr uint32_t VersionCurrent = 1;
constexpr uint32_t VersionAdvance = 2;
constexpr uint32_t VersionModeCount = 3;
constexpr uint32_t VersionOk = 0;
constexpr uint32_t VersionInvalid = 1;
using RawVersionStorage = SbNetVersionStorage;
static_assert(VersionInit == SB_NET_VERSION_INIT && VersionCurrent == SB_NET_VERSION_CURRENT &&
    VersionAdvance == SB_NET_VERSION_ADVANCE && VersionModeCount == SB_NET_VERSION_COUNT,
    "three-mode ABI indices");
static_assert(VersionOk == SB_NET_VERSION_OK && VersionInvalid == SB_NET_VERSION_INVALID,
    "raw ABI status values");
static_assert(sizeof(RawVersionStorage) == 8, "foreign in-place storage width");
static_assert(alignof(RawVersionStorage) == alignof(uint64_t), "foreign storage alignment");

struct GuardedVersionStorage {
  uint64_t before = UINT64_C(0xa5a5a5a5a5a5a5a5);
  RawVersionStorage storage{};
  uint64_t after = UINT64_C(0x5a5a5a5a5a5a5a5a);
};
}

TEST(NetVersion, RustRawZeroGetInitAndAdvanceKeepCanaries) {
  std::array<uint64_t, VersionModeCount> counts{};
  for (uint32_t mode = 0; mode != VersionModeCount; ++mode)
    counts[mode] = sb_net_version_count(0, mode);
  auto scalarBefore = sb_net_scalar_count(0, SB_NET_SCALAR_VERSION_NEXT);
  GuardedVersionStorage guarded;
  uint64_t out = VersionMax;
  // ZERO is valid without INIT, including the actual C++ default-construction path.
  EXPECT_EQ(sb_net_version_run(VersionCurrent, &guarded.storage, &out), VersionOk);
  EXPECT_EQ(out, uint64_t(0));
  std::memset(guarded.storage.bytes, 0xcc, sizeof(guarded.storage.bytes));
  EXPECT_EQ(sb_net_version_run(VersionInit, &guarded.storage, &out), VersionOk);
  EXPECT_EQ(out, uint64_t(0));
  RawVersionStorage zero{};
  EXPECT_EQ(std::memcmp(&guarded.storage, &zero, sizeof(zero)), 0);
  std::memcpy(guarded.storage.bytes, &VersionMax, sizeof(VersionMax));
  EXPECT_EQ(sb_net_version_run(VersionAdvance, &guarded.storage, &out), VersionOk);
  EXPECT_EQ(out, uint64_t(0));
  EXPECT_EQ(std::memcmp(&guarded.storage, &zero, sizeof(zero)), 0);
  EXPECT_EQ(guarded.before, UINT64_C(0xa5a5a5a5a5a5a5a5));
  EXPECT_EQ(guarded.after, UINT64_C(0x5a5a5a5a5a5a5a5a));
  for (uint32_t mode = 0; mode != VersionModeCount; ++mode)
    EXPECT_EQ(sb_net_version_count(0, mode) - counts[mode], uint64_t(1));
  EXPECT_EQ(sb_net_scalar_count(0, SB_NET_SCALAR_VERSION_NEXT) - scalarBefore, uint64_t(1));
}

TEST(NetVersion, RustCurrentAcceptsConstStorageAndExactOutputAliasCopiesFirst) {
  RawVersionStorage seeded;
  uint64_t seed = UINT64_C(0x876543210fedcba9);
  std::memcpy(seeded.bytes, &seed, sizeof(seed));
  RawVersionStorage const storage = seeded;
  uint64_t out = 0;
  EXPECT_EQ(sb_net_version_run(VersionCurrent, &storage, &out), VersionOk);
  EXPECT_EQ(out, seed);
  EXPECT_EQ(std::memcmp(&storage, &seeded, sizeof(storage)), 0);
  // A real writable u64 object supplies both input bytes and output storage.
  // No C++ aliasing access is performed through the opaque pointer.
  uint64_t aliased = VersionMax;
  EXPECT_EQ(sb_net_version_run(VersionCurrent, &aliased, &aliased), VersionOk);
  EXPECT_EQ(aliased, VersionMax);
  EXPECT_EQ(sb_net_version_run(VersionAdvance, &aliased, &aliased), VersionOk);
  EXPECT_EQ(aliased, uint64_t(0));
  aliased = VersionMax;
  EXPECT_EQ(sb_net_version_run(VersionInit, &aliased, &aliased), VersionOk);
  EXPECT_EQ(aliased, uint64_t(0));
}

TEST(NetVersion, RustInvalidCallsPreserveStorageOutputAndDiagnostics) {
  GuardedVersionStorage guarded;
  std::memset(guarded.storage.bytes, 0x93, sizeof(guarded.storage.bytes));
  auto saved = guarded;
  uint64_t out = UINT64_C(0xabcdef0123456789);
  auto savedOut = out;
  std::array<uint64_t, VersionModeCount> counts{};
  for (uint32_t mode = 0; mode != VersionModeCount; ++mode)
    counts[mode] = sb_net_version_count(0, mode);
  auto scalarBefore = sb_net_scalar_count(0, SB_NET_SCALAR_VERSION_NEXT);
  alignas(uint64_t) unsigned char misaligned[24];
  std::memset(misaligned, 0x72, sizeof(misaligned));
  std::array<unsigned char, 24> savedMisaligned{};
  std::memcpy(savedMisaligned.data(), misaligned, sizeof(misaligned));
  for (uint32_t mode = 0; mode != VersionModeCount; ++mode) {
    EXPECT_EQ(sb_net_version_run(mode, nullptr, &out), VersionInvalid);
    EXPECT_EQ(sb_net_version_run(mode, &guarded.storage, nullptr), VersionInvalid);
    EXPECT_EQ(sb_net_version_run(mode, misaligned + 1, &out), VersionInvalid);
    EXPECT_EQ(sb_net_version_run(mode, &guarded.storage,
        reinterpret_cast<uint64_t*>(misaligned + 1)), VersionInvalid);
  }
  for (uint32_t mode : {VersionModeCount, std::numeric_limits<uint32_t>::max()})
    EXPECT_EQ(sb_net_version_run(mode, &guarded.storage, &out), VersionInvalid);
  EXPECT_EQ(out, savedOut);
  EXPECT_EQ(guarded.before, saved.before);
  EXPECT_EQ(guarded.after, saved.after);
  EXPECT_EQ(std::memcmp(&guarded.storage, &saved.storage, sizeof(guarded.storage)), 0);
  EXPECT_EQ(std::memcmp(misaligned, savedMisaligned.data(), sizeof(misaligned)), 0);
  for (uint32_t mode = 0; mode != VersionModeCount; ++mode)
    EXPECT_EQ(sb_net_version_count(0, mode), counts[mode]);
  EXPECT_EQ(sb_net_scalar_count(0, SB_NET_SCALAR_VERSION_NEXT), scalarBefore);
  for (uint32_t kind : {uint32_t(0), uint32_t(1)}) {
    EXPECT_EQ(sb_net_version_count(kind, VersionModeCount), uint64_t(0));
    EXPECT_EQ(sb_net_version_count(kind, std::numeric_limits<uint32_t>::max()), uint64_t(0));
  }
  EXPECT_EQ(sb_net_version_count(2, VersionCurrent), uint64_t(0));
  EXPECT_EQ(sb_net_version_count(std::numeric_limits<uint32_t>::max(), VersionCurrent), uint64_t(0));
}

TEST(NetVersion, RustCppDefaultNeedsNoInitAndIncrementCountsExactlyOnce) {
  auto initBefore = sb_net_version_count(0, VersionInit);
  auto advanceBefore = sb_net_version_count(0, VersionAdvance);
  auto scalarBefore = sb_net_scalar_count(0, SB_NET_SCALAR_VERSION_NEXT);
  NetElementVersion value;
  constexpr NetElementVersion local;
  EXPECT_EQ(value.current(), uint64_t(0));
  EXPECT_EQ(local.current(), uint64_t(0));
  EXPECT_EQ(sb_net_version_count(0, VersionInit), initBefore);
  EXPECT_EQ(value.increment(), uint64_t(1));
  EXPECT_EQ(value.increment(), uint64_t(2));
  EXPECT_EQ(value.current(), uint64_t(2));
  EXPECT_EQ(sb_net_version_count(0, VersionInit), initBefore);
  EXPECT_EQ(sb_net_version_count(0, VersionAdvance) - advanceBefore, uint64_t(2));
  EXPECT_EQ(sb_net_scalar_count(0, SB_NET_SCALAR_VERSION_NEXT) - scalarBefore, uint64_t(2));
  std::cout << "NET_VERSION_DIAGNOSTIC cpp-zero-no-init advance 2 scalar-next 2\n";
}
#endif
