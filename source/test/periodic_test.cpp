#include "StarPeriodic.hpp"

#include "gtest/gtest.h"

#include <cstdint>
#include <cstdio>
#include <limits>
#include <type_traits>

#if defined(STAR_USE_RUST_PERIODIC) && STAR_USE_RUST_PERIODIC
#include "StarRustPeriodic.h"
static_assert(sizeof(SbPeriodicState) == 8 && alignof(SbPeriodicState) == 4, "Periodic state ABI");
static_assert(sizeof(SbPeriodicReply) == 12 && alignof(SbPeriodicReply) == 4, "Periodic reply ABI");
#endif

static_assert(sizeof(unsigned) == sizeof(uint32_t), "Periodic host contract");
static_assert(sizeof(Star::Periodic) == 8, "Periodic value-state size");
static_assert(alignof(Star::Periodic) == alignof(unsigned), "Periodic value-state alignment");
static_assert(std::is_trivially_copyable<Star::Periodic>::value, "Periodic copies its state");
static_assert(std::is_standard_layout<Star::Periodic>::value, "Periodic standard layout");
static_assert(std::is_trivially_copy_constructible<Star::Periodic>::value
    && std::is_trivially_copy_assignable<Star::Periodic>::value
    && std::is_trivially_move_constructible<Star::Periodic>::value
    && std::is_trivially_move_assignable<Star::Periodic>::value, "Periodic value operations");
static_assert(!noexcept(Star::Periodic()), "Preserve constructor exception specification");

using namespace Star;

namespace {
// Independent unsigned arithmetic model, observed only through the public API.
struct PeriodicModel {
  uint32_t counter = 0, every = 1;
  void set(uint32_t n) { every = n; counter = n ? (counter < n ? counter : n - 1) : 0; }
  bool ready() const { return every && !counter; }
  bool tick() {
    if (!every) return false;
    if (!counter) { counter = every - 1; return true; }
    --counter;
    return false;
  }
};
}

TEST(PeriodicTest, All) {
  Periodic periodic(2);

  EXPECT_TRUE(periodic.ready());
  EXPECT_TRUE(periodic.tick());
  EXPECT_FALSE(periodic.ready());
  EXPECT_FALSE(periodic.tick());
  EXPECT_TRUE(periodic.ready());
  EXPECT_TRUE(periodic.tick());

  periodic = Periodic(0);
  EXPECT_FALSE(periodic.tick());
  EXPECT_FALSE(periodic.tick());

  periodic = Periodic(3);
  EXPECT_TRUE(periodic.ready());
  EXPECT_TRUE(periodic.tick());
  EXPECT_FALSE(periodic.ready());
  EXPECT_FALSE(periodic.tick());
  EXPECT_FALSE(periodic.tick());
  EXPECT_TRUE(periodic.ready());
  EXPECT_TRUE(periodic.tick());
  EXPECT_FALSE(periodic.ready());
}

TEST(PeriodicTest, ZeroFreezesAndRearms) {
  Periodic p(0);
  for (unsigned i = 0; i != 8; ++i) {
    EXPECT_FALSE(p.ready());
    EXPECT_FALSE(p.tick());
    EXPECT_EQ(p.stepCount(), 0u);
  }
  p.setStepCount(4);
  EXPECT_TRUE(p.ready());
  EXPECT_TRUE(p.tick());
  p.setStepCount(0);
  EXPECT_FALSE(p.ready());
  EXPECT_FALSE(p.tick());
  p.setStepCount(4);
  EXPECT_TRUE(p.ready());
}

TEST(PeriodicTest, DefaultAlwaysReady) {
  Periodic p;
  for (unsigned i = 0; i != 8; ++i) {
    EXPECT_EQ(p.stepCount(), 1u);
    EXPECT_TRUE(p.ready());
    EXPECT_TRUE(p.tick());
  }
}

TEST(PeriodicTest, SetterClipsCounter) {
  Periodic p(8);
  ASSERT_TRUE(p.tick());
  p.setStepCount(3);
  EXPECT_EQ(p.stepCount(), 3u);
  EXPECT_FALSE(p.tick());
  EXPECT_FALSE(p.tick());
  EXPECT_TRUE(p.ready());
  EXPECT_TRUE(p.tick());
  p.setStepCount(1);
  EXPECT_TRUE(p.ready());
  EXPECT_TRUE(p.tick());
}

TEST(PeriodicTest, LargerSetterDoesNotRestart) {
  Periodic p(3);
  ASSERT_TRUE(p.tick());
  p.setStepCount(9);
  EXPECT_FALSE(p.ready());
  EXPECT_FALSE(p.tick());
  EXPECT_FALSE(p.tick());
  EXPECT_TRUE(p.tick());
  for (unsigned i = 0; i != 8; ++i)
    EXPECT_FALSE(p.tick());
  EXPECT_TRUE(p.ready());
}

TEST(PeriodicTest, MaximumPeriodCountdown) {
  Periodic p(std::numeric_limits<unsigned>::max());
  EXPECT_TRUE(p.tick());
  EXPECT_FALSE(p.ready());
  EXPECT_FALSE(p.tick());
  EXPECT_FALSE(p.tick());
  p.setStepCount(3);
  EXPECT_FALSE(p.tick());
  EXPECT_FALSE(p.tick());
  EXPECT_TRUE(p.tick());
}

TEST(PeriodicTest, CopiesAreIndependent) {
  Periodic p(4);
  ASSERT_TRUE(p.tick());
  Periodic copy(p), assigned(0);
  assigned = p;
  EXPECT_FALSE(p.tick());
  copy.setStepCount(1);
  EXPECT_TRUE(copy.tick());
  EXPECT_EQ(assigned.stepCount(), 4u);
  for (unsigned i = 0; i != 3; ++i)
    EXPECT_FALSE(assigned.tick());
  EXPECT_TRUE(assigned.tick());
  EXPECT_FALSE(p.tick());
  EXPECT_FALSE(p.tick());
  EXPECT_TRUE(p.tick());
}

TEST(PeriodicTest, CallbackIsNamedLvalueAndConditional) {
  struct Callback {
    unsigned* calls;
    void operator()() & { ++*calls; }
    void operator()() && = delete;
  };
  Periodic p(2);
  unsigned calls = 0;
  Callback callback{&calls};
  p.tick(callback);
  p.tick(Callback{&calls});
  EXPECT_EQ(calls, 1u);
  p.tick(Callback{&calls});
  EXPECT_EQ(calls, 2u);
}

TEST(PeriodicTest, CallbackThrowPreservesIdentityAndUpdatedState) {
  struct Failure {} failure;
  Periodic p(3);
  try {
    p.tick([&] { throw &failure; });
    FAIL() << "callback did not throw";
  } catch (Failure* caught) {
    EXPECT_EQ(caught, &failure);
  } catch (...) {
    FAIL() << "callback exception changed";
  }
  EXPECT_FALSE(p.ready());
  EXPECT_FALSE(p.tick());
  EXPECT_FALSE(p.tick());
  EXPECT_TRUE(p.tick());
}

TEST(PeriodicTest, CallbackReentryObservesUpdatedState) {
  Periodic p(3);
  p.tick([&] {
    EXPECT_FALSE(p.ready());
    EXPECT_FALSE(p.tick());
    p.setStepCount(1);
    EXPECT_TRUE(p.ready());
    EXPECT_TRUE(p.tick());
    p.setStepCount(0);
  });
  EXPECT_EQ(p.stepCount(), 0u);
  EXPECT_FALSE(p.tick());
}

TEST(PeriodicTest, DeterministicPublicSequence) {
  Periodic p;
  PeriodicModel model;
  uint32_t random = 0x7354a219u;
  uint64_t hash = UINT64_C(14695981039346656037);
  auto mix = [&](uint32_t value) {
    for (unsigned byte = 0; byte != 4; ++byte) {
      hash ^= (value >> (byte * 8)) & 255u;
      hash *= UINT64_C(1099511628211);
    }
  };
  for (unsigned i = 0; i != 100000; ++i) {
    random = random * 1664525u + 1013904223u;
    unsigned op = (random >> 24) % 8;
    uint32_t result = 0;
    if (op < 4) {
      uint32_t period = op == 0 ? 0 : op == 1 ? (random >> 8) % 9
          : op == 2 ? UINT32_MAX : random;
      p.setStepCount(period);
      model.set(period);
      result = period;
    } else if (op == 4) {
      result = p.tick();
      EXPECT_EQ(result, model.tick()) << i;
    } else if (op == 5) {
      result = p.ready();
      EXPECT_EQ(result, model.ready()) << i;
    } else if (op == 6) {
      result = p.stepCount();
      EXPECT_EQ(result, model.every) << i;
    } else {
      Periodic copy(p), assigned(0);
      assigned = copy;
      PeriodicModel copied = model;
      result = assigned.tick();
      EXPECT_EQ(result, copied.tick()) << i;
      EXPECT_EQ(copy.ready(), model.ready()) << i;
      mix(copy.ready()); mix(copied.counter); mix(copied.every);
      copy.setStepCount(1);
      bool copiedTick = copy.tick();
      EXPECT_TRUE(copiedTick);
      mix(copiedTick); mix(copy.ready()); mix(copy.stepCount());
    }
    EXPECT_EQ(p.ready(), model.ready()) << i;
    EXPECT_EQ(p.stepCount(), model.every) << i;
    mix(i); mix(random); mix(op); mix(result);
    mix(model.counter); mix(model.every); mix(p.ready()); mix(p.stepCount());
  }
  std::printf("PERIODIC_TRACE %016llx\n", static_cast<unsigned long long>(hash));
}

#if defined(STAR_USE_RUST_PERIODIC) && STAR_USE_RUST_PERIODIC
TEST(PeriodicTest, RustAcceptedOperationCounters) {
  uint64_t local[4], global[4];
  for (unsigned op = 0; op != 4; ++op) {
    local[op] = sb_periodic_count(0, op);
    global[op] = sb_periodic_count(1, op);
  }
  Periodic p(3);
  p.setStepCount(2);
  EXPECT_TRUE(p.ready());
  EXPECT_TRUE(p.tick());
  for (unsigned op = 0; op != 4; ++op) {
    EXPECT_EQ(sb_periodic_count(0, op), local[op] + 1);
    EXPECT_GE(sb_periodic_count(1, op), global[op] + 1);
  }
  EXPECT_EQ(sb_periodic_count(0, 4), 0u);
  EXPECT_EQ(sb_periodic_count(1, 4), 0u);
  EXPECT_EQ(sb_periodic_count(2, 0), 0u);
  EXPECT_EQ(sb_periodic_count(UINT32_MAX, UINT32_MAX), 0u);
}
#endif
