#pragma once

#include "StarNetElement.hpp"
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarNetGroupHost.hpp"
#include "StarRustNetTop.h"
#endif

namespace Star {

// Mixin for the NetElement that should be the top element for a network, wraps
// any NetElement class and manages the NetElementVersion.
template <typename BaseNetElement>
class NetElementTop : public BaseNetElement {
public:
  NetElementTop();

  // Writes the state update to the given DataStream then returns the version
  // code that should be passed to the next call to writeState.  If
  // 'fromVersion' is 0, then this is a full write for an initial read of a
  // slave NetElementTop.
  pair<ByteArray, uint64_t> writeNetState(uint64_t fromVersion = 0, NetCompatibilityRules rules = {});
  // Reads a state produced by a call to writeState, optionally with the
  // interpolation delay time for the data contained in this state update.  If
  // the state is a full update rather than a delta, the interoplation delay
  // will be ignored.  Blank updates are not necessary to send to be read by
  // readState, *unless* extrapolation is enabled.  If extrapolation is
  // enabled, reading a blank update calls 'blankNetDelta' which is necessary
  // to not improperly extrapolate past the end of incoming deltas.
  void readNetState(ByteArray data, float interpolationTime = 0.0f, NetCompatibilityRules rules = {});

private:
  using BaseNetElement::initNetVersion;
  using BaseNetElement::netStore;
  using BaseNetElement::netLoad;
  using BaseNetElement::writeNetDelta;
  using BaseNetElement::readNetDelta;
  using BaseNetElement::blankNetDelta;
  using BaseNetElement::checkWithRules;

  NetElementVersion m_netVersion;
};

template <typename BaseNetElement>
NetElementTop<BaseNetElement>::NetElementTop() {
  BaseNetElement::initNetVersion(&m_netVersion);
}

template <typename BaseNetElement>
pair<ByteArray, uint64_t> NetElementTop<BaseNetElement>::writeNetState(uint64_t fromVersion, NetCompatibilityRules rules) {
  DataStreamBuffer ds;
  ds.setStreamCompatibilityVersion(rules);
#ifdef STAR_USE_RUST_NET_GROUP
  bool hasData = NetGroupDetail::run(SB_NET_TOP_WRITE, fromVersion,
      [&](uint32_t leaf, uint64_t, SbNetTopReply& reply) {
    switch (leaf) {
    case SB_NET_TOP_WRITE_FULL: ds.write<bool>(true); break;
    case SB_NET_TOP_STORE: BaseNetElement::netStore(ds, rules); break;
    case SB_NET_TOP_WRITE_DELTA_MARKER: ds.write<bool>(false); break;
    case SB_NET_TOP_WRITE_DELTA:
      // Retain the whole native !/contextual-if expression, including proxy destruction.
      if (!BaseNetElement::writeNetDelta(ds, fromVersion, rules)) reply.a = 0;
      else reply.a = 1;
      break;
    default: throw std::logic_error("Invalid network-top write leaf");
    }
  }, sb_net_top_run);
  // Keep ByteArray construction/takeData BEFORE the native version read/increment.
  if (!hasData) return {ByteArray(), m_netVersion.current()};
  return {ds.takeData(), m_netVersion.increment()};
#else
  if (fromVersion == 0) {
    ds.write<bool>(true);
    BaseNetElement::netStore(ds, rules);
    return {ds.takeData(), m_netVersion.increment()};
  } else {
    ds.write<bool>(false);
    if (!BaseNetElement::writeNetDelta(ds, fromVersion, rules))
      return {ByteArray(), m_netVersion.current()};
    else
      return {ds.takeData(), m_netVersion.increment()};
  }
#endif
}

template <typename BaseNetElement>
void NetElementTop<BaseNetElement>::readNetState(ByteArray data, float interpolationTime, NetCompatibilityRules rules) {
#ifdef STAR_USE_RUST_NET_GROUP
  NetGroupDetail::run(SB_NET_TOP_READ, data.empty(), [&](uint32_t leaf, uint64_t, SbNetTopReply&) {
    switch (leaf) {
    case SB_NET_TOP_BLANK: BaseNetElement::blankNetDelta(interpolationTime); break;
    case SB_NET_TOP_SCOPED_PAYLOAD: {
      DataStreamBuffer ds(std::move(data));
      ds.setStreamCompatibilityVersion(rules);
      NetGroupDetail::run(SB_NET_TOP_PAYLOAD, 0, [&](uint32_t item, uint64_t, SbNetTopReply& reply) {
        switch (item) {
        case SB_NET_TOP_IS_FULL: reply.a = ds.read<bool>(); break;
        case SB_NET_TOP_LOAD: BaseNetElement::netLoad(ds, rules); break;
        case SB_NET_TOP_READ_DELTA: BaseNetElement::readNetDelta(ds, interpolationTime, rules); break;
        default: throw std::logic_error("Invalid network-top payload leaf");
        }
      }, sb_net_top_run);
      break;
    }
    default: throw std::logic_error("Invalid network-top read leaf");
    }
  }, sb_net_top_run);
#else
  if (data.empty()) {
    BaseNetElement::blankNetDelta(interpolationTime);
  } else {
    DataStreamBuffer ds(std::move(data));
    ds.setStreamCompatibilityVersion(rules);
    if (ds.read<bool>())
      BaseNetElement::netLoad(ds, rules);
    else
      BaseNetElement::readNetDelta(ds, interpolationTime, rules);
  }
#endif
}

}