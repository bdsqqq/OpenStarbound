#include "StarUuid.hpp"
#include "StarHash.hpp"
#include "StarDataStreamDevices.hpp"
#ifdef STAR_USE_RUST_UUID
#include "StarRustUuid.h"
#endif

#include "gtest/gtest.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <type_traits>

using namespace Star;

static_assert(sizeof(Uuid) == 16, "Uuid storage must remain exactly 16 bytes");
static_assert(alignof(Uuid) == alignof(char), "Uuid must remain byte-aligned");
static_assert(std::is_standard_layout<Uuid>::value, "Uuid must remain standard-layout");

namespace {
using Bytes = std::array<char, 16>;

Uuid uuid(Bytes const& bytes) {
  return Uuid(ByteArray(bytes.data(), bytes.size()));
}

size_t nativeHash(Bytes const& bytes) {
  size_t seed = 0;
  // Conversion of native char to size_t is part of the original contract.
  for (char byte : bytes)
    Star::hashCombine(seed, byte);
  return seed;
}

void expectRelations(Bytes const& a, Bytes const& b) {
  auto left = uuid(a), right = uuid(b);
  EXPECT_EQ(left == right, a == b);
  EXPECT_EQ(left != right, a != b);
  EXPECT_EQ(left < right, a < b);
  EXPECT_EQ(left <= right, a <= b);
  EXPECT_EQ(left > right, a > b);
  EXPECT_EQ(left >= right, a >= b);
  EXPECT_EQ(Star::hash<Uuid>()(left), nativeHash(a));
  EXPECT_EQ(Star::hash<Uuid>()(right), nativeHash(b));
}
}

TEST(UuidTest, BytesHexAndIndependentStorage) {
  Bytes original{{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13,
      static_cast<char>(0x80), static_cast<char>(0xff)}};
  ByteArray source(original.data(), original.size());
  Uuid value(source);
  source[0] = 42;
  EXPECT_EQ(value.bytes().size(), 16u);
  for (size_t i = 0; i < original.size(); ++i)
    EXPECT_EQ(value.ptr()[i], original[i]);
  EXPECT_EQ(value.bytes(), ByteArray(original.data(), original.size()));
  auto returned = value.bytes();
  returned[1] = 42;
  EXPECT_EQ(value.ptr()[1], original[1]);
  EXPECT_EQ(value.hex(), String("000102030405060708090a0b0c0d80ff"));
  EXPECT_EQ(Uuid(value.hex()), value);
  EXPECT_EQ(Uuid(String("000102030405060708090A0B0C0D80FF")), value);
  EXPECT_EQ(Uuid().bytes().size(), 16u);
}

TEST(UuidTest, InvalidLengthsAndNativeHexDecoding) {
  for (size_t size : {0u, 15u, 17u}) {
    try {
      Uuid value(ByteArray(size, 0));
      FAIL() << "accepted byte count " << size;
    } catch (UuidException const& e) {
      EXPECT_EQ(std::string(e.what()), "(UuidException) Size mismatch in reading Uuid from ByteArray: "
          + std::to_string(size) + " vs 16");
    }
  }
  // Native hexDecode maps invalid nibbles to zero; it does not throw.
  EXPECT_EQ(Uuid(String("zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz")), uuid(Bytes{}));
}

TEST(UuidTest, NativeCharRelationsAndDeterministicHashCorpus) {
  uint32_t state = 0x71d3a905u;
  for (size_t position = 0; position < 16; ++position) {
    for (unsigned byte = 0; byte < 256; ++byte) {
      Bytes a;
      for (char& item : a) {
        state = state * 1664525u + 1013904223u;
        item = static_cast<char>(state >> 24);
      }
      a[position] = static_cast<char>(byte);
      auto b = a;
      b[position] = static_cast<char>((byte + 1) & 255);
      expectRelations(a, a);
      expectRelations(a, b);
    }
    Bytes low{}, high{};
    low[position] = static_cast<char>(0x7f);
    high[position] = static_cast<char>(0x80);
    expectRelations(low, high);
    EXPECT_EQ(uuid(high) < uuid(low), std::is_signed<char>::value);
  }
}

TEST(UuidTest, DataStreamRoundTrip) {
  Uuid value(String("000102030405060708090a0b0c0d80ff"));
  DataStreamBuffer stream;
  stream << value;
  EXPECT_EQ(stream.data(), value.bytes());
  stream.seek(0);
  auto restored = uuid(Bytes{});
  stream >> restored;
  EXPECT_EQ(restored, value);
}

TEST(UuidTest, DeterministicVectors) {
  std::array<Bytes, 5> vectors{};
  vectors[1].fill(static_cast<char>(0xff));
  vectors[2].fill(static_cast<char>(0x80));
  for (size_t i = 0; i < 16; ++i) {
    vectors[3][i] = static_cast<char>(i * 17);
    vectors[4][i] = static_cast<char>(i % 2 ? 0x7f : 0x80);
  }
  for (auto const& bytes : vectors) {
    auto value = uuid(bytes);
    int order = value < uuid(Bytes{}) ? -1 : (value > uuid(Bytes{}) ? 1 : 0);
    EXPECT_EQ(Star::hash<Uuid>()(value), nativeHash(bytes));
    std::cout << "UUID_VECTOR {\"hex\":\"" << value.hex().utf8()
        << "\",\"hash\":" << Star::hash<Uuid>()(value)
        << ",\"signed_char\":" << std::is_signed<char>::value
        << ",\"order_vs_zero\":" << order << "}\n";
  }
}

#ifdef STAR_USE_RUST_UUID
TEST(UuidTest, RustOperationsAreReached) {
  auto copies = sb_uuid_count(0), comparisons = sb_uuid_count(1), hashes = sb_uuid_count(2);
  auto left = uuid(Bytes{});
  Bytes bytes{};
  bytes[15] = 1;
  auto right = uuid(bytes);
  EXPECT_NE(left, right);
  EXPECT_EQ(Star::hash<Uuid>()(left), nativeHash(Bytes{}));
  EXPECT_GT(sb_uuid_count(0), copies);
  EXPECT_GT(sb_uuid_count(1), comparisons);
  EXPECT_GT(sb_uuid_count(2), hashes);
}
#endif
