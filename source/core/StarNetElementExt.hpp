#pragma once

#include "StarNetElement.hpp"
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarNetGroupHost.hpp"
#include "StarRustNetOverride.h"
#endif

namespace Star {

template <typename BaseNetElement>
class NetElementOverride : public BaseNetElement {
public:
  void netStore(DataStream& ds, NetCompatibilityRules rules = {}) const override;
  void netLoad(DataStream& ds, NetCompatibilityRules rules) override;

  bool writeNetDelta(DataStream& ds, uint64_t fromVersion, NetCompatibilityRules rules = {}) const override;
  void readNetDelta(DataStream& ds, float interpolationTime = 0.0f, NetCompatibilityRules rules = {}) override;

  typedef std::function<void(DataStream&, NetCompatibilityRules)> NetStorer;
  typedef std::function<void(DataStream&, NetCompatibilityRules)> NetLoader;
  typedef std::function<bool(DataStream&, uint64_t, NetCompatibilityRules)> NetDeltaWriter;
  typedef std::function<void(DataStream&, float, NetCompatibilityRules)> NetDeltaReader;

  void setNetStorer(NetStorer);
  void setNetLoader(NetLoader);
  void setNetDeltaWriter(NetDeltaWriter);
  void setNetDeltaReader(NetDeltaReader);
  void setOverrides(NetStorer netStorer, NetLoader netLoader,
    NetDeltaWriter netDeltaWriter, NetDeltaReader netDeltaReader);

private:
  NetStorer m_netStorer;
  NetLoader m_netLoader;
  
  NetDeltaWriter m_netDeltaWriter;
  NetDeltaReader m_netDeltaReader;
};

template <typename BaseNetElement>
void NetElementOverride<BaseNetElement>::netStore(DataStream& ds, NetCompatibilityRules rules) const {
#ifdef STAR_USE_RUST_NET_GROUP
  NetGroupDetail::run(SB_NET_OVERRIDE_STORE, 0, [&](uint32_t leaf, uint64_t, SbNetOverrideReply& reply) {
    switch (leaf) {
    case SB_NET_OVERRIDE_HAS:
      if (m_netStorer) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_OVERRIDE_CALL_OVERRIDE: m_netStorer(ds, rules); break;
    case SB_NET_OVERRIDE_CALL_BASE: BaseNetElement::netStore(ds, rules); break;
    default: throw std::logic_error("Invalid network override store leaf");
    }
  }, sb_net_override_run);
#else
  if (m_netStorer)
    m_netStorer(ds, rules);
  else
    BaseNetElement::netStore(ds, rules);
#endif
}

template <typename BaseNetElement>
void NetElementOverride<BaseNetElement>::netLoad(DataStream& ds, NetCompatibilityRules rules) {
#ifdef STAR_USE_RUST_NET_GROUP
  NetGroupDetail::run(SB_NET_OVERRIDE_LOAD, 0, [&](uint32_t leaf, uint64_t, SbNetOverrideReply& reply) {
    switch (leaf) {
    case SB_NET_OVERRIDE_HAS:
      if (m_netLoader) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_OVERRIDE_CALL_OVERRIDE: m_netLoader(ds, rules); break;
    case SB_NET_OVERRIDE_CALL_BASE: BaseNetElement::netLoad(ds, rules); break;
    default: throw std::logic_error("Invalid network override load leaf");
    }
  }, sb_net_override_run);
#else
  if (m_netLoader)
    m_netLoader(ds, rules);
  else
    BaseNetElement::netLoad(ds, rules);
#endif
}

template <typename BaseNetElement>
bool NetElementOverride<BaseNetElement>::writeNetDelta(DataStream& ds, uint64_t fromVersion, NetCompatibilityRules rules) const {
#ifdef STAR_USE_RUST_NET_GROUP
  return NetGroupDetail::run(SB_NET_OVERRIDE_WRITE, 0, [&](uint32_t leaf, uint64_t, SbNetOverrideReply& reply) {
    switch (leaf) {
    case SB_NET_OVERRIDE_HAS:
      if (m_netDeltaWriter) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_OVERRIDE_CALL_OVERRIDE: reply.a = m_netDeltaWriter(ds, fromVersion, rules); break;
    case SB_NET_OVERRIDE_CALL_BASE: reply.a = BaseNetElement::writeNetDelta(ds, fromVersion, rules); break;
    default: throw std::logic_error("Invalid network override write leaf");
    }
  }, sb_net_override_run);
#else
  if (m_netDeltaWriter)
    return m_netDeltaWriter(ds, fromVersion, rules);
  else
    return BaseNetElement::writeNetDelta(ds, fromVersion, rules);
#endif
}

template <typename BaseNetElement>
void NetElementOverride<BaseNetElement>::readNetDelta(DataStream& ds, float interpolationTime, NetCompatibilityRules rules) {
#ifdef STAR_USE_RUST_NET_GROUP
  NetGroupDetail::run(SB_NET_OVERRIDE_READ, 0, [&](uint32_t leaf, uint64_t, SbNetOverrideReply& reply) {
    switch (leaf) {
    case SB_NET_OVERRIDE_HAS:
      if (m_netDeltaReader) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_OVERRIDE_CALL_OVERRIDE: m_netDeltaReader(ds, interpolationTime, rules); break;
    case SB_NET_OVERRIDE_CALL_BASE: BaseNetElement::readNetDelta(ds, interpolationTime, rules); break;
    default: throw std::logic_error("Invalid network override read leaf");
    }
  }, sb_net_override_run);
#else
  if (m_netDeltaReader)
    m_netDeltaReader(ds, interpolationTime, rules);
  else
    BaseNetElement::readNetDelta(ds, interpolationTime, rules);
#endif
}

template <typename BaseNetElement>
inline void NetElementOverride<BaseNetElement>::setNetStorer(NetStorer f) { m_netStorer = std::move(f); }
template <typename BaseNetElement>
inline void NetElementOverride<BaseNetElement>::setNetLoader(NetLoader f) { m_netLoader = std::move(f); }
template <typename BaseNetElement>
inline void NetElementOverride<BaseNetElement>::setNetDeltaWriter(NetDeltaWriter f) { m_netDeltaWriter = std::move(f); }
template <typename BaseNetElement>
inline void NetElementOverride<BaseNetElement>::setNetDeltaReader(NetDeltaReader f) { m_netDeltaReader = std::move(f); }

template <typename BaseNetElement>
inline void NetElementOverride<BaseNetElement>::setOverrides(NetStorer netStorer, NetLoader netLoader, NetDeltaWriter netDeltaWriter, NetDeltaReader netDeltaReader) {
  m_netStorer = std::move(netStorer);
  m_netLoader = std::move(netLoader);
  m_netDeltaWriter = std::move(netDeltaWriter);
  m_netDeltaReader = std::move(netDeltaReader);
}

}