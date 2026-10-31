#pragma once

#include "StarDataStream.hpp"
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetCompat.h"
#include "StarRustNetVersion.h"
#include <stdexcept>
#endif

namespace Star {
#ifdef STAR_USE_RUST_NET_GROUP
namespace NetElementDetail {
inline uint32_t compat(uint32_t mode, void const* storage, uint32_t argument = 0) {
  uint32_t result = 0;
  if (sb_net_compat_run(mode, storage, argument, &result) != SB_NET_COMPAT_OK ||
      (mode == SB_NET_COMPAT_CHECK && result > 1))
    throw std::logic_error("Invalid opaque network compatibility result");
  return result;
}
inline uint64_t version(uint32_t mode, void const* storage) {
  uint64_t result = 0;
  if (sb_net_version_run(mode, storage, &result) != SB_NET_VERSION_OK)
    throw std::logic_error("Invalid opaque network version result");
  return result;
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
#ifdef STAR_USE_RUST_NET_GROUP
  // Rust defines the POD representation. Zero bytes preserve native constexpr
  // construction; trivial C++ byte copies are part of the foreign-state ABI.
  SbNetVersionStorage m_state{};
#else
  uint64_t m_version = 0;
#endif
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
#ifdef STAR_USE_RUST_NET_GROUP
  // Constant opaque initialization preserves native construction and copying.
  // Rust defines ALL-FF as AnyVersion; no FFI constructor or destructor is needed.
  SbNetCompatStorage m_compatState = SB_NET_COMPAT_ANY_INITIALIZER;
#else
  VersionNumber m_netCompatibilityVersion = AnyVersion;
#endif
};

inline VersionNumber NetElement::compatibilityVersion() const {
#ifdef STAR_USE_RUST_NET_GROUP
  return NetElementDetail::compat(SB_NET_COMPAT_VALUE, &m_compatState);
#else
  return m_netCompatibilityVersion;
#endif
}

inline void NetElement::setCompatibilityVersion(VersionNumber version) {
#ifdef STAR_USE_RUST_NET_GROUP
  NetElementDetail::compat(SB_NET_COMPAT_SET, &m_compatState, version);
#else
  m_netCompatibilityVersion = version;
#endif
}

inline bool NetElement::checkWithRules(NetCompatibilityRules const& rules) const {
#ifdef STAR_USE_RUST_NET_GROUP
  // Keep the native no-read case: AnyVersion must not inspect rules.version().
  if (compatibilityVersion() != AnyVersion)
    return NetElementDetail::compat(SB_NET_COMPAT_CHECK, &m_compatState, rules.version()) != 0;
  return true;
#else
  if (m_netCompatibilityVersion != AnyVersion)
    return rules.version() >= m_netCompatibilityVersion;
  return true;
#endif
}

}
