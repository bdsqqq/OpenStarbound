#pragma once

#include "StarMathCommon.hpp"
#include "StarRandom.hpp"
#ifdef STAR_USE_RUST_PERIODIC
#include "StarRustPeriodic.h"
#include <limits>
#include <stdexcept>
#endif

namespace Star {
#ifdef STAR_USE_RUST_PERIODIC
namespace PeriodicDetail {
static_assert(sizeof(unsigned) == sizeof(uint32_t)
    && std::numeric_limits<unsigned>::max() == UINT32_MAX, "Periodic unsigned ABI");

inline SbPeriodicReply run(uint32_t operation, SbPeriodicState state, uint32_t every = 0) {
  SbPeriodicReply reply;
  if (sb_periodic_run(operation, state, every, &reply) != SB_PERIODIC_OK)
    throw std::logic_error("Periodic Rust protocol failure");
  return reply;
}
}
#endif

// Perform some action every X ticks.  Setting the tick count to 0 means never
// perform the action, 1 performs the action every call, 2 performs the action
// every other call, and so forth.
class Periodic {
public:
  Periodic(unsigned everyXSteps = 1)
#ifdef STAR_USE_RUST_PERIODIC
    : m_state(PeriodicDetail::run(SB_PERIODIC_INIT, {0, 0}, everyXSteps).state) {}
#else
    : m_counter(0), m_everyXSteps(everyXSteps) {}
#endif

  unsigned stepCount() const {
#ifdef STAR_USE_RUST_PERIODIC
    return m_state.every;
#else
    return m_everyXSteps;
#endif
  }

  void setStepCount(unsigned everyXSteps) {
#ifdef STAR_USE_RUST_PERIODIC
    m_state = PeriodicDetail::run(SB_PERIODIC_SET, m_state, everyXSteps).state;
#else
    m_everyXSteps = everyXSteps;
    if (everyXSteps != 0)
      m_counter = clamp<unsigned>(m_counter, 0, m_everyXSteps - 1);
    else
      m_counter = 0;
#endif
  }

  // Will the next tick() return true?
  bool ready() const {
#ifdef STAR_USE_RUST_PERIODIC
    return PeriodicDetail::run(SB_PERIODIC_READY, m_state).ready != 0;
#else
    return m_everyXSteps != 0 && m_counter == 0;
#endif
  }

  bool tick() {
#ifdef STAR_USE_RUST_PERIODIC
    auto reply = PeriodicDetail::run(SB_PERIODIC_TICK, m_state);
    // Commit before the native callback can throw or reenter tick/setStepCount.
    m_state = reply.state;
    return reply.ready != 0;
#else
    if (m_everyXSteps == 0)
      return false;

    if (m_counter == 0) {
      m_counter = m_everyXSteps - 1;
      return true;
    } else {
      --m_counter;
      return false;
    }
#endif
  }

  template <typename Function>
  void tick(Function&& function) {
    if (tick())
      function();
  }

private:
#ifdef STAR_USE_RUST_PERIODIC
  SbPeriodicState m_state;
#else
  unsigned m_counter;
  unsigned m_everyXSteps;
#endif
};

// Perform some action with a given period over an amount of some value (like
// time) with optional randomness.
class RatePeriodic {
public:
  RatePeriodic(double period = 1, double noise = 0)
    : m_period(period), m_noise(noise), m_counter(period + Random::randf(-noise, noise)), m_elapsed(0.0) {}

  double period() const {
    return m_period;
  }

  double noise() const {
    return m_noise;
  }

  template <typename Function>
  void update(double amount, Function&& function) {
    double subAmount = min(amount, m_counter);
    m_counter -= subAmount;
    amount -= subAmount;
    m_elapsed += subAmount;

    if (m_counter <= 0.0) {
      m_counter = m_period + Random::randf(-m_noise, m_noise);
      function(m_elapsed);
      m_elapsed = 0.0;
      if (amount > 0.0)
        update(amount, forward<Function>(function));
    }
  }

private:
  double m_period;
  double m_noise;
  double m_counter;
  double m_elapsed;
};

}
