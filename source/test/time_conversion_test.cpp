#include "StarTime.hpp"
#include "gtest/gtest.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <initializer_list>

#if defined(STAR_USE_RUST_TIME) && STAR_USE_RUST_TIME
#include "StarRustTime.h"
#endif

using namespace Star;

namespace {
constexpr int64_t Lo = std::numeric_limits<int64_t>::min();
constexpr int64_t Hi = std::numeric_limits<int64_t>::max();
// Operation order: ticks->ms, ticks->us, ms->ticks, us->ticks.
using Convert = int64_t (*)(int64_t, int64_t);
Convert const Native[] = {Time::ticksToMilliseconds, Time::ticksToMicroseconds,
    Time::millisecondsToTicks, Time::microsecondsToTicks};
struct Result { bool defined; int64_t value; };
// MSVC has no __int128. Keep a portable, independently checked oracle and
// cross-check it against the widened one on hosts supporting both.
bool addFits(int64_t a, int64_t b) {
  return !((b > 0 && a > Hi - b) || (b < 0 && a < Lo - b));
}
uint64_t magnitude(int64_t value) {
  return value < 0 ? (uint64_t)(-(value + 1)) + 1 : (uint64_t)value;
}
Result portableOracle(unsigned op, int64_t value, int64_t frequency) {
  int64_t scale = op % 2 ? 1000000 : 1000;
  if (!addFits(frequency, scale / 2)) return {false, 0};
  int64_t factor = (frequency + scale / 2) / scale;
  if (op < 2) {
    int64_t bias = factor / 2;
    if (!addFits(value, bias) || factor == 0) return {false, 0};
    int64_t numerator = value + bias;
    if (numerator == Lo && factor == -1) return {false, 0};
    return {true, numerator / factor};
  }
  bool negative = (value < 0) != (factor < 0);
  uint64_t a = magnitude(value), b = magnitude(factor);
  uint64_t limit = negative ? UINT64_C(1) << 63 : (uint64_t)Hi;
  if (b && a > limit / b) return {false, 0};
  uint64_t product = a * b;
  if (negative && product == (UINT64_C(1) << 63)) return {true, Lo};
  return {true, negative ? -(int64_t)product : (int64_t)product};
}
#if defined(__SIZEOF_INT128__) && !defined(STAR_TIME_PORTABLE_ORACLE)
bool fits(__int128 n) { return n >= Lo && n <= Hi; }
// Widen BEFORE every operation, but reject every intermediate the native signed
// expression cannot represent. A zero FROM factor is valid; a zero TO divisor is not.
Result oracle(unsigned op, int64_t value, int64_t frequency) {
  __int128 scale = op % 2 ? 1000000 : 1000;
  __int128 sum = (__int128)frequency + scale / 2;
  if (!fits(sum)) return {false, 0};
  __int128 factor = sum / scale;
  if (!fits(factor)) return {false, 0};
  if (op >= 2) {
    __int128 product = (__int128)value * factor;
    return {fits(product), fits(product) ? (int64_t)product : 0};
  }
  __int128 bias = factor / 2;
  if (!fits(bias)) return {false, 0};
  __int128 numerator = (__int128)value + bias;
  if (!fits(numerator) || !factor || (numerator == Lo && factor == -1))
    return {false, 0};
  __int128 quotient = numerator / factor;
  return {fits(quotient), fits(quotient) ? (int64_t)quotient : 0};
}
#else
Result oracle(unsigned op, int64_t value, int64_t frequency) {
  return portableOracle(op, value, frequency);
}
#endif
struct Trace {
  uint64_t hash = UINT64_C(14695981039346656037);
  uint64_t safe[4] = {}, unsupported[4] = {};
  void word(uint64_t n) {
    // Explicit low-byte-first serialization, independent of host endianness.
    for (unsigned i = 0; i != 8; ++i) {
      hash ^= (n >> (8 * i)) & 255;
      hash *= UINT64_C(1099511628211);
    }
  }
  void check(unsigned op, int64_t value, int64_t frequency) {
    Result expected = oracle(op, value, frequency);
    Result portable = portableOracle(op, value, frequency);
    EXPECT_EQ(portable.defined, expected.defined);
    if (expected.defined) EXPECT_EQ(portable.value, expected.value);
    word(op); word((uint64_t)value); word((uint64_t)frequency); word(expected.defined);
    if (expected.defined) {
      ++safe[op];
      int64_t actual = Native[op](value, frequency);
      EXPECT_EQ(actual, expected.value) << "op=" << op << " value=" << value << " frequency=" << frequency;
      word((uint64_t)actual);
    } else {
      ++unsupported[op];
      // Never execute the C++ wrapper here: its fallback retains native UB.
#if defined(STAR_USE_RUST_TIME) && STAR_USE_RUST_TIME
      int64_t output = 123456789;
      EXPECT_EQ(sb_time_convert(op, value, frequency, &output), (uint32_t)SB_TIME_DOMAIN);
      EXPECT_EQ(output, 123456789);
#endif
    }
  }
  void all(int64_t value, int64_t frequency) {
    for (unsigned op = 0; op != 4; ++op) check(op, value, frequency);
  }
  void print(char const* label) const {
    std::printf("TIME_CONVERSION_TRACE %s digest=%016llx safe=%llu,%llu,%llu,%llu unsupported=%llu,%llu,%llu,%llu\n",
        label, (unsigned long long)hash,
        (unsigned long long)safe[0], (unsigned long long)safe[1],
        (unsigned long long)safe[2], (unsigned long long)safe[3],
        (unsigned long long)unsupported[0], (unsigned long long)unsupported[1],
        (unsigned long long)unsupported[2], (unsigned long long)unsupported[3]);
  }
};
uint64_t next(uint64_t& state) {
  state ^= state << 13; state ^= state >> 7; state ^= state << 17;
  return state;
}
int64_t signedWord(uint64_t word) {
  // Bit-preserving full-word corpus on the supported two's-complement targets.
  int64_t result;
  static_assert(sizeof(result) == sizeof(word), "64-bit corpus words");
  std::memcpy(&result, &word, sizeof(result));
  return result;
}
}

TEST(TimeConversionTest, BoundaryGrid) {
  int64_t const values[] = {Lo, Lo + 1, -1000001, -1000000, -1000, -501, -500,
      -499, -2, -1, 0, 1, 2, 499, 500, 501, 1000, 1000000, 1000001, Hi - 1, Hi};
  int64_t const frequencies[] = {Lo, Lo + 1, -1000000000, -1500000, -1000000,
      -500001, -500000, -499999, -1500, -1000, -501, -500, -499, -1, 0, 1,
      499, 500, 501, 999, 1000, 1001, 499999, 500000, 500001, 1000000,
      1000000000, Hi - 500001, Hi - 500000, Hi - 500, Hi - 499, Hi};
  Trace trace;
  for (auto value : values) for (auto frequency : frequencies) trace.all(value, frequency);
  trace.print("boundaries");
}

TEST(TimeConversionTest, SignedBiasIsNotSymmetricRounding) {
  Trace trace;
  for (unsigned op : {0u, 1u}) {
    int64_t frequency = op ? 1000000000 : 1000000; // factor 1000
    for (int64_t value : {-1501, -1500, -1499, -501, -500, -499, 499, 500, 501, 1499, 1500})
      trace.check(op, value, frequency);
    EXPECT_EQ(Native[op](-1500, frequency), -1);
    EXPECT_EQ(Native[op](-500, frequency), 0);
    EXPECT_EQ(Native[op](500, frequency), 1);
    trace.check(op, -1500, -frequency);
    EXPECT_EQ(Native[op](-1500, -frequency), 2);
  }
  trace.print("signed-bias");
}

TEST(TimeConversionTest, CommonFrequenciesAndNegativeRoundTrips) {
  Trace trace;
  for (int64_t frequency : {INT64_C(1000000), INT64_C(1000000000)})
    for (int64_t value : {-1000000, -1000, -2, -1, 0, 1, 2, 1000, 1000000}) {
      trace.all(value, frequency);
      for (unsigned op = 0; op != 2; ++op) {
        Result ticks = oracle(op + 2, value, frequency);
        ASSERT_TRUE(ticks.defined);
        trace.check(op, ticks.value, frequency);
      }
    }
  EXPECT_EQ(Time::ticksToMilliseconds(Time::millisecondsToTicks(-1, 1000000000), 1000000000), 0);
  EXPECT_EQ(Time::ticksToMicroseconds(Time::microsecondsToTicks(-1, 1000000000), 1000000000), 0);
  trace.print("common-roundtrip");
}

TEST(TimeConversionTest, ZeroFactorAndUnsupportedIntermediates) {
  Trace trace;
  for (unsigned op = 0; op != 4; ++op) {
    EXPECT_EQ(oracle(op, Hi, 0).defined, op >= 2);
    trace.check(op, Hi, 0);
    trace.check(op, 0, Hi); // Frequency addition overflows even with value zero.
    trace.check(op, Lo, op % 2 ? -1500000 : -1500); // MIN / -1 for TO.
    trace.check(op, Hi, op % 2 ? 2000000 : 2000); // Bias/product overflow.
  }
  trace.print("unsupported");
}

TEST(TimeConversionTest, DeterministicMixedCorpus) {
  Trace trace;
  uint64_t state = UINT64_C(0xd1b54a32d192ed03);
  for (unsigned i = 0; i != 100000; ++i) {
    uint64_t a = next(state), b = next(state);
    int64_t value = signedWord(a), frequency = signedWord(b);
    if (i % 3 == 1) {
      value = (int64_t)(a % 2000001) - 1000000;
      int64_t const common[] = {1000, 1000000, 1000000000, -1000000};
      frequency = common[b % 4];
    } else if (i % 3 == 2) {
      value = (int64_t)(a % 2000001) - 1000000;
      frequency = (int64_t)(b % 2000000001) - 1000000000;
    }
    trace.all(value, frequency);
  }
  for (unsigned op = 0; op != 4; ++op) EXPECT_GT(trace.safe[op], 30000u);
  trace.print("mixed-100000");
}

TEST(TimeConversionTest, StoppedClockUsesBiasedIntegerRoundTrip) {
  Trace trace;
  int64_t frequency = Time::monotonicTickFrequency();
  Clock clock(false);
  for (int64_t millis : {-1000, -2, -1, 0, 1, 2, 1000}) {
    Result ticks = oracle(2, millis, frequency);
    ASSERT_TRUE(ticks.defined);
    Result expected = oracle(0, ticks.value, frequency);
    ASSERT_TRUE(expected.defined);
    trace.check(2, millis, frequency); trace.check(0, ticks.value, frequency);
    clock.setMilliseconds(millis);
    EXPECT_FALSE(clock.running());
    EXPECT_EQ(clock.milliseconds(), expected.value);
    trace.word((uint64_t)clock.milliseconds());
    Clock copy(clock);
    EXPECT_FALSE(copy.running());
    EXPECT_EQ(copy.milliseconds(), expected.value);
  }
  trace.print("stopped-clock");
}

TEST(TimeConversionTest, StoppedTimerClampsAfterBiasedIntegerRoundTrip) {
  Trace trace;
  int64_t frequency = Time::monotonicTickFrequency();
  for (int64_t millis : {-1000, -2, -1, 0, 1, 2, 1000}) {
    Result ticks = oracle(2, -millis, frequency);
    ASSERT_TRUE(ticks.defined);
    Result elapsed = oracle(0, ticks.value, frequency);
    ASSERT_TRUE(elapsed.defined);
    ASSERT_NE(elapsed.value, Lo); // Timer negates the elapsed milliseconds.
    int64_t raw = -elapsed.value;
    trace.check(2, -millis, frequency); trace.check(0, ticks.value, frequency);
    Timer timer = Timer::withMilliseconds(millis, false);
    EXPECT_FALSE(timer.running());
    EXPECT_EQ(timer.millisecondsLeft(true), raw);
    EXPECT_EQ(timer.millisecondsLeft(), raw < 0 ? 0 : raw);
    trace.word((uint64_t)timer.millisecondsLeft(true));
    trace.word((uint64_t)timer.millisecondsLeft());
  }
  trace.print("stopped-timer");
}

#if defined(STAR_USE_RUST_TIME) && STAR_USE_RUST_TIME
TEST(TimeConversionTest, NativeWrappersEnterAllFourRustOperationsWithoutDomain) {
  static_assert(SB_TIME_COUNT == 4 && SB_TIME_TO_MILLISECONDS == 0 && SB_TIME_TO_MICROSECONDS == 1
      && SB_TIME_FROM_MILLISECONDS == 2 && SB_TIME_FROM_MICROSECONDS == 3, "Time operation ABI");
  for (unsigned op = 0; op != 4; ++op) {
    uint64_t before = sb_time_count(0, op), domains = sb_time_count(2, op);
    Result expected = oracle(op, 123, 1000000000);
    ASSERT_TRUE(expected.defined);
    EXPECT_EQ(Native[op](123, 1000000000), expected.value);
    EXPECT_EQ(sb_time_count(0, op) - before, 1u);
    EXPECT_EQ(sb_time_count(2, op), domains);
  }
  EXPECT_EQ(sb_time_count(3, 0), 0u);
  EXPECT_EQ(sb_time_count(0, SB_TIME_COUNT), 0u);
}
#endif
