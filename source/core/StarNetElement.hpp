#pragma once

#include "StarDataStream.hpp"
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetScalar.h"
#include <stdexcept>
#endif

namespace Star {
#ifdef STAR_USE_RUST_NET_GROUP
namespace NetElementDetail {
inline uint64_t scalar(uint32_t mode, uint32_t bits, uint64_t value, uint64_t previous) {
  SbNetScalarReply reply{};
  if (sb_net_scalar_run(mode, bits, value, previous, &reply) != SB_NET_SCALAR_OK ||
      reply.pulled != 0 || (mode == SB_NET_SCALAR_COMPAT && reply.value > 1))
    throw std::logic_error("Invalid network element scalar result");
  return reply.value;
}
}
#endif

// Monotonically increasing NetElementVersion shared between all NetElements in
// a network.
class NetElementVersion {
public:
  uint64_t current() const;
  uint64_t increment();

private:
  uint64_t m_version = 0;
};

// Primary interface for the composable network synchronizable element system.
class NetElement {
public:
  virtual ~NetElement() = default;

  // A network of NetElements will have a shared monotonically increasing
  // NetElementVersion.  When elements are updated, they will mark the version
  // number at the time they are updated so that a delta can be constructed
  // that contains only changes since any past version.
  virtual void initNetVersion(NetElementVersion const* version = nullptr) = 0;

  // Full store / load of the entire element.
  virtual void netStore(DataStream& ds, NetCompatibilityRules rules) const = 0;
  virtual void netLoad(DataStream& ds, NetCompatibilityRules rules) = 0;

  // Enables interpolation mode.  If interpolation mode is enabled, then
  // NetElements will delay presenting incoming delta data for the
  // 'interpolationTime' parameter given in readNetDelta, and smooth between
  // received values.  When interpolation is enabled, tickNetInterpolation must
  // be periodically called to smooth values forward in time.  If
  // extrapolationHint is given, this may be used as a hint for the amount of
  // time to extrapolate forward if no deltas are received.
  virtual void enableNetInterpolation(float extrapolationHint = 0.0f);
  virtual void disableNetInterpolation();
  virtual void tickNetInterpolation(float dt);

  // Write all the state changes that have happened since (and including)
  // fromVersion.  The normal way to use this would be to call writeDelta with
  // the version at the time of the *last* call to writeDelta, + 1.  If
  // fromVersion is 0, this will always write the full state.  Should return
  // true if a delta was needed and was written to DataStream, false otherwise.
  virtual bool writeNetDelta(DataStream& ds, uint64_t fromVersion, NetCompatibilityRules rules) const = 0;
  // Read a delta written by writeNetDelta.  'interpolationTime' is the time in
  // the future that data from this delta should be delayed and smoothed into,
  // if interpolation is enabled.
  virtual void readNetDelta(DataStream& ds, float interpolationTime = 0.0f, NetCompatibilityRules rules = {}) = 0;
  // When extrapolating, it is important to notify when a delta WOULD have been
  // received even if no deltas are produced, so no extrapolation takes place.
  virtual void blankNetDelta(float interpolationTime);

  VersionNumber compatibilityVersion() const;
  void setCompatibilityVersion(VersionNumber version);
  bool checkWithRules(NetCompatibilityRules const& rules) const;
private:
  VersionNumber m_netCompatibilityVersion = AnyVersion;
};

inline VersionNumber NetElement::compatibilityVersion() const {
  return m_netCompatibilityVersion;
}

inline void NetElement::setCompatibilityVersion(VersionNumber version) {
  m_netCompatibilityVersion = version;
}

inline bool NetElement::checkWithRules(NetCompatibilityRules const& rules) const {
#ifdef STAR_USE_RUST_NET_GROUP
  // Keep the native no-read case: AnyVersion must not inspect rules.version().
  if (m_netCompatibilityVersion != AnyVersion)
    return NetElementDetail::scalar(SB_NET_SCALAR_COMPAT, 32,
        m_netCompatibilityVersion, rules.version()) != 0;
  return true;
#else
  if (m_netCompatibilityVersion != AnyVersion)
    return rules.version() >= m_netCompatibilityVersion;
  return true;
#endif
}

}
