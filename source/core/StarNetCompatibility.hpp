#pragma once
#include "StarVersion.hpp"
#include "StarHash.hpp"
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetRules.h"
#include <stdexcept>
#endif

namespace Star {

extern VersionNumber const OpenProtocolVersion;

constexpr VersionNumber AnyVersion = 0xFFFFFFFF;
constexpr VersionNumber LegacyVersion = 0;

#ifdef STAR_USE_RUST_NET_GROUP
namespace NetRulesDetail {
inline uint32_t run(uint32_t mode, void const* storage, uint32_t argument = 0) {
  uint32_t result = 0;
  if (sb_net_rules_run(mode, storage, argument, &result) != SB_NET_RULES_OK ||
      (mode >= SB_NET_RULES_ADMIN && result > 1))
    throw std::logic_error("Invalid opaque network rules result");
  return result;
}
}
#endif
class NetCompatibilityRules {
public:
  NetCompatibilityRules();
  NetCompatibilityRules(uint64_t) = delete;
  NetCompatibilityRules(VersionNumber version);

  VersionNumber version() const;
  void setVersion(VersionNumber version);

  bool isAdmin() const;
  void setIsAdmin(bool admin);

  bool isLegacy() const;

  bool operator==(NetCompatibilityRules const& a) const;

private:
#ifdef STAR_USE_RUST_NET_GROUP
  // Rust owns the logical value; native trivial copies host its opaque POD.
  // Constructors initialize it with the native version constant or argument.
  SbNetRulesStorage m_state;
#else
  VersionNumber m_version = OpenProtocolVersion;
  bool m_isAdmin = false;
#endif
};

#ifdef STAR_USE_RUST_NET_GROUP
inline NetCompatibilityRules::NetCompatibilityRules() {
  NetRulesDetail::run(SB_NET_RULES_INIT, &m_state, OpenProtocolVersion);
}

inline NetCompatibilityRules::NetCompatibilityRules(VersionNumber v) {
  NetRulesDetail::run(SB_NET_RULES_INIT, &m_state, v);
}
#else
inline NetCompatibilityRules::NetCompatibilityRules() : m_version(OpenProtocolVersion) {}

inline NetCompatibilityRules::NetCompatibilityRules(VersionNumber v) : m_version(v) {}
#endif

inline VersionNumber NetCompatibilityRules::version() const {
#ifdef STAR_USE_RUST_NET_GROUP
  return NetRulesDetail::run(SB_NET_RULES_VERSION, &m_state);
#else
  return m_version;
#endif
}

inline void NetCompatibilityRules::setVersion(VersionNumber version) {
#ifdef STAR_USE_RUST_NET_GROUP
  NetRulesDetail::run(SB_NET_RULES_SET_VERSION, &m_state, version);
#else
  m_version = version;
#endif
}

inline bool NetCompatibilityRules::isAdmin() const {
#ifdef STAR_USE_RUST_NET_GROUP
  return NetRulesDetail::run(SB_NET_RULES_ADMIN, &m_state) != 0;
#else
  return m_isAdmin;
#endif
}

inline void NetCompatibilityRules::setIsAdmin(bool admin) {
#ifdef STAR_USE_RUST_NET_GROUP
  NetRulesDetail::run(SB_NET_RULES_SET_ADMIN, &m_state, uint32_t(admin));
#else
  m_isAdmin = admin;
#endif
}

inline bool NetCompatibilityRules::isLegacy() const {
#ifdef STAR_USE_RUST_NET_GROUP
  return NetRulesDetail::run(SB_NET_RULES_LEGACY, &m_state) != 0;
#else
  return m_version == LegacyVersion;
#endif
}

inline bool NetCompatibilityRules::operator==(NetCompatibilityRules const& a) const {
#ifdef STAR_USE_RUST_NET_GROUP
  return NetRulesDetail::run(SB_NET_RULES_EQUAL_VERSION, &m_state, a.version()) != 0;
#else
  return m_version == a.m_version;
#endif
}

template <>
struct hash<NetCompatibilityRules> {
  size_t operator()(NetCompatibilityRules const& s) const {
    return s.version();
  }
};

}