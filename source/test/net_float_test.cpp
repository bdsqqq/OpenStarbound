#include <functional>

#include "StarDataStreamDevices.hpp"
#include "StarNetElementFloatFields.hpp"
#ifdef STAR_USE_RUST_NET_FIELD
#include "StarRustNetFloat.h"
#endif
#include "gtest/gtest.h"

#include <cstring>
#include <exception>
#include <iostream>
#include <memory>
#include <string>

using namespace Star;

namespace {
template <typename T> ByteArray floatWire(T value) {
  DataStreamBuffer ds;
  ds.write(value);
  return ds.takeData();
}
template <typename T> ByteArray floatStored(NetElementFloating<T> const& field) {
  DataStreamBuffer ds;
  field.netStore(ds);
  return ds.takeData();
}
template <typename T> void floatRead(NetElementFloating<T>& field, T value, float time = 0) {
  DataStreamBuffer ds(floatWire(value));
  field.readNetDelta(ds, time);
  EXPECT_EQ(ds.pos(), sizeof(T));
}
template <typename T> void floatExact(T actual, T expected) {
  EXPECT_EQ(floatWire(actual), floatWire(expected));
}
template <typename T> void floatTrace(char const* name, NetElementFloating<T> const& field) {
  static char const hex[] = "0123456789abcdef";
  std::cout << "NET_FLOAT_TRACE " << sizeof(T) << ' ' << name << ' ';
  for (auto bytes : {floatWire(field.get()), floatStored(field)}) {
    for (size_t i = 0; i < bytes.size(); ++i) {
      auto b = static_cast<unsigned char>(bytes[i]);
      std::cout << hex[b >> 4] << hex[b & 15];
    }
    std::cout << '/';
  }
  std::cout << '\n';
}
struct FloatError : std::exception {};
struct DerivedFloatError : FloatError {};
struct FloatCopies { int copies = 0; int deaths = 0; int calls = 0; };
template <typename T> struct FloatCallable {
  FloatCopies* state;
  explicit FloatCallable(FloatCopies& s) : state(&s) {}
  FloatCallable(FloatCallable const& other) : state(other.state) { ++state->copies; }
  ~FloatCallable() { ++state->deaths; }
  T operator()(T, T a, T) const { ++state->calls; return a; }
};
template <typename T> class NetFloat : public ::testing::Test {};
using FloatTypes = ::testing::Types<float, double>;
TYPED_TEST_SUITE(NetFloat, FloatTypes);

TYPED_TEST(NetFloat, InitialEqualityAndInclusiveVersionCut) {
  using T = TypeParam;
  NetElementFloating<T> f;
  NetElementVersion version;
  f.initNetVersion(&version);
  floatExact(f.get(), T(0));
  DataStreamBuffer zero;
  EXPECT_TRUE(f.writeNetDelta(zero, 0));
  EXPECT_EQ(zero.data(), floatWire(T(0)));
  version.increment();
  f.set(T(0));
  DataStreamBuffer unchanged;
  EXPECT_FALSE(f.writeNetDelta(unchanged, 1));
  f.set(T(-0.5));
  DataStreamBuffer changed;
  EXPECT_TRUE(f.writeNetDelta(changed, 1));
  EXPECT_FALSE(f.writeNetDelta(unchanged, 2));
  EXPECT_EQ(changed.data(), floatWire(T(-0.5)));
  f.enableNetInterpolation();
  floatRead(f, T(8), 2);
  f.set(T(-0.5));
  EXPECT_EQ(floatStored(f), floatWire(T(8)));
  f.set(T(2));
  EXPECT_EQ(floatStored(f), floatWire(T(2)));
  f.tickNetInterpolation(4);
  floatExact(f.get(), T(2));
  floatTrace("initial-version", f);
}

TYPED_TEST(NetFloat, TypedRawWireAndNativeFixedPointVlqi) {
  using T = TypeParam;
  for (T value : {T(-1.375), T(-0.125), T(0.125), T(1.375)}) {
    NetElementFloating<T> f;
    f.set(value);
    EXPECT_EQ(floatStored(f), floatWire(value));
    f.setFixedPointBase(T(0.25));
    DataStreamBuffer oracle;
    oracle.writeVlqI(round(value / T(0.25)));
    EXPECT_EQ(floatStored(f), oracle.data());
    NetElementFloating<T> receiver;
    receiver.setFixedPointBase(T(0.25));
    DataStreamBuffer input(oracle.data());
    receiver.netLoad(input, {});
    DataStreamBuffer expected(oracle.data());
    floatExact(receiver.get(), T(expected.readVlqI() * T(0.25)));
    floatTrace("fixed-wire", f);
  }
}

TYPED_TEST(NetFloat, FixedPointMarkingUsesActualTransmittedChange) {
  using T = TypeParam;
  for (T base : {T(0.25), T(1)}) {
    NetElementFloating<T> f;
    NetElementVersion version;
    f.initNetVersion(&version);
    f.setFixedPointBase(base);
    for (T value : {T(0.125), T(0.25), T(0.375), T(-0.125), T(-0.5), T(-1.5), T(-1.375)}) {
      auto before = floatStored(f);
      auto cut = version.increment();
      f.set(value);
      auto after = floatStored(f);
      DataStreamBuffer delta;
      bool wrote = f.writeNetDelta(delta, cut);
      EXPECT_EQ(wrote, before != after);
      if (wrote) EXPECT_EQ(delta.data(), after);
      floatExact(f.get(), value);
      floatTrace("fixed-mark", f);
    }
  }
}

TYPED_TEST(NetFloat, CallbackStorageCopiesAndLifetimesRemainNative) {
  using T = TypeParam;
  FloatCopies state;
  std::weak_ptr<int> weak;
  {
    NetElementFloating<T> f;
    std::function<T(T, T, T)> fn = FloatCallable<T>(state);
    f.setInterpolator(fn);
    int copies = state.copies;
    int deaths = state.deaths;
    f.enableNetInterpolation();
    floatRead(f, T(2), 1);
    f.tickNetInterpolation(0.25f);
    EXPECT_EQ(state.copies, copies);
    EXPECT_EQ(state.deaths, deaths);
    EXPECT_EQ(state.calls, 2);
    auto owner = std::make_shared<int>(7);
    weak = owner;
    f.setInterpolator([owner](T, T, T) { return T(*owner); });
    owner.reset();
    EXPECT_FALSE(weak.expired());
    f.setInterpolator({});
    EXPECT_TRUE(weak.expired());
    f.setInterpolator(fn);
    int beforeCopy = state.copies;
    auto copy = f;
    EXPECT_EQ(state.copies, beforeCopy + 1);
    copy.tickNetInterpolation(0);
    floatTrace("callback-copy", copy);
  }
  EXPECT_TRUE(weak.expired());
}

TYPED_TEST(NetFloat, EnableSeedsCurrentAndRepeatedEnableKeepsQueueAndUpdatesHint) {
  using T = TypeParam;
  NetElementFloating<T> f;
  f.set(T(2));
  f.setInterpolator([](T offset, T, T) { return offset; });
  f.enableNetInterpolation();
  f.tickNetInterpolation(0);
  floatExact(f.get(), T(0));
  floatRead(f, T(8), 0.5f);
  f.enableNetInterpolation(0.5f);
  f.tickNetInterpolation(1);
  // Separation .5 uses max(separation, 1), so the upper clamp is 1.5, not 2.
  floatExact(f.get(), T(1.5));
  EXPECT_EQ(floatStored(f), floatWire(T(8)));
  floatTrace("enable-repeat", f);
}

TYPED_TEST(NetFloat, DisableSelectsLatestFutureAndIsIdempotent) {
  using T = TypeParam;
  NetElementFloating<T> f;
  f.set(T(1));
  f.enableNetInterpolation();
  floatRead(f, T(4), 2);
  floatRead(f, T(8), 4);
  floatExact(f.get(), T(1));
  f.disableNetInterpolation();
  floatExact(f.get(), T(8));
  f.disableNetInterpolation();
  f.tickNetInterpolation(16);
  floatExact(f.get(), T(8));
  floatTrace("disable", f);
}

TYPED_TEST(NetFloat, TickDecrementsAllPointsPrunesOnlyBeyondTwoAtInclusiveZero) {
  using T = TypeParam;
  NetElementFloating<T> f;
  f.enableNetInterpolation();
  floatRead(f, T(2), 1);
  floatRead(f, T(4), 2);
  floatRead(f, T(8), 3);
  f.tickNetInterpolation(2);
  f.setInterpolator([](T, T a, T) { return a; });
  f.tickNetInterpolation(0);
  floatExact(f.get(), T(4));
  // The remaining pair must survive even once both timestamps are in the past.
  f.tickNetInterpolation(2);
  floatExact(f.get(), T(4));
  EXPECT_EQ(floatStored(f), floatWire(T(8)));
  floatTrace("tick-prune", f);
}

TYPED_TEST(NetFloat, EqualReadTimeAppendsButSmallerTimeClears) {
  using T = TypeParam;
  NetElementFloating<T> equal, smaller;
  equal.enableNetInterpolation();
  smaller.enableNetInterpolation();
  floatRead(equal, T(2), 1);
  floatRead(equal, T(4), 1);
  floatExact(equal.get(), T(0));
  equal.tickNetInterpolation(1);
  floatExact(equal.get(), T(4));
  floatRead(smaller, T(2), 2);
  floatRead(smaller, T(4), 1);
  floatExact(smaller.get(), T(4));
  floatTrace("fifo-equal", equal);
  floatTrace("fifo-smaller", smaller);
}

TYPED_TEST(NetFloat, DelayedReadWithoutInterpolatorHoldsThenSteps) {
  using T = TypeParam;
  NetElementFloating<T> f;
  f.set(T(-2));
  f.enableNetInterpolation();
  floatRead(f, T(6), 1);
  f.tickNetInterpolation(0.5f);
  floatExact(f.get(), T(-2));
  f.tickNetInterpolation(0.5f);
  floatExact(f.get(), T(6));
  floatTrace("hold-step", f);
}

TYPED_TEST(NetFloat, CustomInterpolatorGetsExactFractionAndSeparationClamp) {
  using T = TypeParam;
  NetElementFloating<T> f;
  T seenOffset = -1, seenA = -1, seenB = -1;
  f.set(T(2));
  f.setInterpolator([&](T offset, T a, T b) {
    seenOffset = offset; seenA = a; seenB = b;
    return a + offset * (b - a);
  });
  f.enableNetInterpolation(1);
  floatRead(f, T(10), 2);
  f.tickNetInterpolation(0.5f);
  floatExact(seenOffset, T(0.25));
  floatExact(seenA, T(2)); floatExact(seenB, T(10));
  floatExact(f.get(), T(4));
  f.tickNetInterpolation(4);
  floatExact(seenOffset, T(1.5));
  floatExact(f.get(), T(14));
  floatTrace("custom-fraction", f);
}

TYPED_TEST(NetFloat, BlankEarlierReplacesLaterAppendsAndNeverRefreshesVersion) {
  using T = TypeParam;
  NetElementFloating<T> earlier, later;
  NetElementVersion version;
  earlier.initNetVersion(&version); later.initNetVersion(&version);
  earlier.enableNetInterpolation(); later.enableNetInterpolation();
  floatRead(earlier, T(8), 2); floatRead(later, T(8), 2);
  version.increment();
  earlier.blankNetDelta(1);
  later.blankNetDelta(3);
  floatExact(earlier.get(), T(8));
  floatExact(later.get(), T(0));
  later.tickNetInterpolation(2);
  floatExact(later.get(), T(8));
  DataStreamBuffer ds;
  EXPECT_FALSE(earlier.writeNetDelta(ds, 1));
  EXPECT_FALSE(later.writeNetDelta(ds, 1));
  NetElementFloating<T> disabled;
  disabled.set(T(4)); disabled.blankNetDelta(-1);
  floatExact(disabled.get(), T(4));
  floatTrace("blank-earlier", earlier); floatTrace("blank-later", later);
}

TYPED_TEST(NetFloat, StoreAndDeltaChooseFutureNotCurrent) {
  using T = TypeParam;
  NetElementFloating<T> f;
  f.set(T(1)); f.enableNetInterpolation();
  floatRead(f, T(9), 4);
  floatExact(f.get(), T(1));
  EXPECT_EQ(floatStored(f), floatWire(T(9)));
  DataStreamBuffer delta;
  EXPECT_TRUE(f.writeNetDelta(delta, 0));
  EXPECT_EQ(delta.data(), floatStored(f));
  floatTrace("store-future", f);
}

TYPED_TEST(NetFloat, FullLoadCapturesVersionAndReseedsAtZero) {
  using T = TypeParam;
  NetElementFloating<T> f;
  NetElementVersion version;
  f.initNetVersion(&version); f.enableNetInterpolation();
  floatRead(f, T(8), 4);
  auto cut = version.increment();
  DataStreamBuffer input(floatWire(T(2)));
  f.netLoad(input, {});
  floatExact(f.get(), T(2));
  DataStreamBuffer delta;
  EXPECT_TRUE(f.writeNetDelta(delta, cut));
  EXPECT_FALSE(f.writeNetDelta(delta, cut + 1));
  floatRead(f, T(10), 2);
  f.setInterpolator([](T offset, T a, T b) { return a + offset * (b - a); });
  f.tickNetInterpolation(0.5f);
  floatExact(f.get(), T(4));
  f.initNetVersion();
  DataStreamBuffer reset;
  EXPECT_FALSE(f.writeNetDelta(reset, 1));
  floatTrace("load-zero", f);
}

TYPED_TEST(NetFloat, OrdinaryReadIgnoresCompatibilityUnlikeStoreLoadWrite) {
  using T = TypeParam;
  NetElementFloating<T> f;
  f.set(T(2)); f.setCompatibilityVersion(OpenProtocolVersion);
  NetCompatibilityRules legacy(LegacyVersion);
  DataStreamBuffer stored;
  f.netStore(stored, legacy);
  EXPECT_TRUE(stored.empty());
  EXPECT_FALSE(f.writeNetDelta(stored, 0, legacy));
  DataStreamBuffer input(floatWire(T(8)));
  f.netLoad(input, legacy);
  EXPECT_EQ(input.pos(), 0u);
  floatExact(f.get(), T(2));
  f.readNetDelta(input, 2, legacy);
  EXPECT_EQ(input.pos(), sizeof(T));
  floatExact(f.get(), T(8));
  f.setCompatibilityVersion(AnyVersion);
  floatTrace("rules", f);
}

TYPED_TEST(NetFloat, ExceptionsPreserveIdentityPrefixAndMutatedQueue) {
  using T = TypeParam;
  for (int kind = 0; kind != 2; ++kind) {
    auto error = kind == 0 ? std::make_exception_ptr(DerivedFloatError{}) : std::make_exception_ptr(731);
    NetElementFloating<T> f;
    f.enableNetInterpolation();
    f.setInterpolator([&](T, T, T) -> T { std::rethrow_exception(error); });
    DataStreamBuffer input(floatWire(T(8)));
    try { f.readNetDelta(input, 2); ADD_FAILURE() << "interpolator exception swallowed"; }
    catch (...) { EXPECT_EQ(std::current_exception(), error); }
    EXPECT_EQ(input.pos(), sizeof(T));
    floatExact(f.get(), T(0));
    EXPECT_EQ(floatStored(f), floatWire(T(8)));
    f.setInterpolator({});
    f.disableNetInterpolation();
    floatExact(f.get(), T(8));
    for (bool writing : {false, true}) {
      DataStreamBuffer prefix;
      DataStreamFunctions failing(
        [&](char*, size_t) -> size_t { prefix.write<uint8_t>(0xa1); std::rethrow_exception(error); },
        [&](char const* data, size_t n) -> size_t {
          if (n) prefix.writeData(data, 1);
          std::rethrow_exception(error);
        });
      try {
        if (writing) f.netStore(failing);
        else f.netLoad(failing, {});
        ADD_FAILURE() << "stream exception swallowed";
      } catch (...) { EXPECT_EQ(std::current_exception(), error); }
      ASSERT_EQ(prefix.size(), 1u);
      if (writing) EXPECT_EQ(prefix.data()[0], floatWire(T(8))[0]);
      else EXPECT_EQ(static_cast<unsigned char>(prefix.data()[0]), 0xa1);
      floatExact(f.get(), T(8));
    }
    floatTrace("exceptions", f);
  }
}

TYPED_TEST(NetFloat, CallbackCanDisableQueueButEnteredBranchStillAssignsReturn) {
  using T = TypeParam;
  NetElementFloating<T> f;
  f.enableNetInterpolation();
  f.setInterpolator([&](T, T, T latest) {
    f.disableNetInterpolation();
    floatExact(f.get(), latest);
    return T(3);
  });
  floatRead(f, T(8), 2);
  floatExact(f.get(), T(3));
  f.tickNetInterpolation(1);
  floatExact(f.get(), T(3));
  EXPECT_EQ(floatStored(f), floatWire(T(3)));
  floatTrace("reentry-disable", f);
}
#ifdef STAR_USE_RUST_NET_FIELD
static_assert(SB_NET_FLOAT_COUNT == 11, "float root ABI changed");
static_assert(SB_NET_FLOAT_OP_COUNT == 27, "float leaf ABI changed");
TEST(NetFloatDiagnostic, NaturalSetEnableDisableRoots) {
  auto sets = sb_net_float_count(0, SB_NET_FLOAT_SET);
  auto enables = sb_net_float_count(0, SB_NET_FLOAT_ENABLE);
  auto disables = sb_net_float_count(0, SB_NET_FLOAT_DISABLE);
  NetElementFloat f;
  f.set(2.0f);
  f.enableNetInterpolation();
  f.disableNetInterpolation();
  EXPECT_EQ(sb_net_float_count(0, SB_NET_FLOAT_SET), sets + 1);
  EXPECT_EQ(sb_net_float_count(0, SB_NET_FLOAT_ENABLE), enables + 1);
  EXPECT_EQ(sb_net_float_count(0, SB_NET_FLOAT_DISABLE), disables + 1);
  std::cout << "NET_FLOAT_DIAGNOSTIC natural-set-enable-disable\n";
}
#endif
} // namespace
