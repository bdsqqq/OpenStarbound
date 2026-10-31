#include "StarNetElementSyncGroup.hpp"
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarNetGroupHost.hpp"
#include "StarRustNetSync.h"
#endif

namespace Star {
#ifdef STAR_USE_RUST_NET_GROUP
namespace {
template <typename Function>
bool netSync(uint32_t mode, Function&& function) {
  return NetGroupDetail::run(mode, 0, function, sb_net_sync_run);
}
}
#endif

void NetElementSyncGroup::enableNetInterpolation(float extrapolationHint) {
#ifdef STAR_USE_RUST_NET_GROUP
  netSync(SB_NET_SYNC_ENABLE, [&](uint32_t leaf, uint64_t argument, SbNetSyncReply& reply) {
    switch (leaf) {
    case SB_NET_SYNC_BASE_ENABLE: NetElementGroup::enableNetInterpolation(extrapolationHint); break;
    case SB_NET_SYNC_HAS_RECENT: reply.a = m_hasRecentChanges; break;
    case SB_NET_SYNC_NEED_LOAD: netElementsNeedLoad(argument != 0); break;
    default: throw std::logic_error("Invalid NetElementSyncGroup enable leaf");
    }
  });
#else
  NetElementGroup::enableNetInterpolation(extrapolationHint);
  if (m_hasRecentChanges)
    netElementsNeedLoad(false);
#endif
}

void NetElementSyncGroup::disableNetInterpolation() {
#ifdef STAR_USE_RUST_NET_GROUP
  netSync(SB_NET_SYNC_DISABLE, [&](uint32_t leaf, uint64_t argument, SbNetSyncReply& reply) {
    switch (leaf) {
    case SB_NET_SYNC_BASE_DISABLE: NetElementGroup::disableNetInterpolation(); break;
    case SB_NET_SYNC_HAS_RECENT: reply.a = m_hasRecentChanges; break;
    case SB_NET_SYNC_NEED_LOAD: netElementsNeedLoad(argument != 0); break;
    default: throw std::logic_error("Invalid NetElementSyncGroup disable leaf");
    }
  });
#else
  NetElementGroup::disableNetInterpolation();
  if (m_hasRecentChanges)
    netElementsNeedLoad(false);
#endif
}

void NetElementSyncGroup::tickNetInterpolation(float dt) {
#ifdef STAR_USE_RUST_NET_GROUP
  netSync(SB_NET_SYNC_TICK, [&](uint32_t leaf, uint64_t argument, SbNetSyncReply& reply) {
    switch (leaf) {
    case SB_NET_SYNC_BASE_TICK: NetElementGroup::tickNetInterpolation(dt); break;
    case SB_NET_SYNC_HAS_RECENT: reply.a = m_hasRecentChanges; break;
    case SB_NET_SYNC_DECREMENT_TIME: m_recentDeltaTime -= dt; break;
    case SB_NET_SYNC_INTERPOLATING: reply.a = netInterpolationEnabled(); break;
    case SB_NET_SYNC_NEED_LOAD: netElementsNeedLoad(argument != 0); break;
    case SB_NET_SYNC_EXPIRED_BLANK: reply.a = m_recentDeltaTime < 0.0f && m_recentDeltaWasBlank; break;
    case SB_NET_SYNC_CLEAR_RECENT: m_hasRecentChanges = false; break;
    default: throw std::logic_error("Invalid NetElementSyncGroup tick leaf");
    }
  });
#else
  NetElementGroup::tickNetInterpolation(dt);
  if (m_hasRecentChanges) {
    m_recentDeltaTime -= dt;
    if (netInterpolationEnabled())
      netElementsNeedLoad(false);

    if (m_recentDeltaTime < 0.0f && m_recentDeltaWasBlank)
      m_hasRecentChanges = false;
  }
#endif
}

void NetElementSyncGroup::netStore(DataStream& ds, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_GROUP
  netSync(SB_NET_SYNC_STORE, [&](uint32_t leaf, uint64_t, SbNetSyncReply&) {
    switch (leaf) {
    case SB_NET_SYNC_NEED_STORE: const_cast<NetElementSyncGroup*>(this)->netElementsNeedStore(); break;
    case SB_NET_SYNC_BASE_STORE: NetElementGroup::netStore(ds, rules); break;
    default: throw std::logic_error("Invalid NetElementSyncGroup store leaf");
    }
  });
#else
  const_cast<NetElementSyncGroup*>(this)->netElementsNeedStore();
  return NetElementGroup::netStore(ds, rules);
#endif
}

void NetElementSyncGroup::netLoad(DataStream& ds, NetCompatibilityRules rules) {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_GROUP
  netSync(SB_NET_SYNC_LOAD, [&](uint32_t leaf, uint64_t argument, SbNetSyncReply&) {
    switch (leaf) {
    case SB_NET_SYNC_BASE_LOAD: NetElementGroup::netLoad(ds, rules); break;
    case SB_NET_SYNC_NEED_LOAD: netElementsNeedLoad(argument != 0); break;
    default: throw std::logic_error("Invalid NetElementSyncGroup load leaf");
    }
  });
#else
  NetElementGroup::netLoad(ds, rules);
  netElementsNeedLoad(true);
#endif
}

bool NetElementSyncGroup::writeNetDelta(DataStream& ds, uint64_t fromVersion, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return false;
#ifdef STAR_USE_RUST_NET_GROUP
  return netSync(SB_NET_SYNC_WRITE, [&](uint32_t leaf, uint64_t, SbNetSyncReply& reply) {
    switch (leaf) {
    case SB_NET_SYNC_NEED_STORE: const_cast<NetElementSyncGroup*>(this)->netElementsNeedStore(); break;
    case SB_NET_SYNC_BASE_WRITE: reply.a = NetElementGroup::writeNetDelta(ds, fromVersion, rules); break;
    default: throw std::logic_error("Invalid NetElementSyncGroup write leaf");
    }
  });
#else
  const_cast<NetElementSyncGroup*>(this)->netElementsNeedStore();
  return NetElementGroup::writeNetDelta(ds, fromVersion, rules);
#endif
}

void NetElementSyncGroup::readNetDelta(DataStream& ds, float interpolationTime, NetCompatibilityRules rules) {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_GROUP
  netSync(SB_NET_SYNC_READ, [&](uint32_t leaf, uint64_t argument, SbNetSyncReply&) {
    switch (leaf) {
    case SB_NET_SYNC_BASE_READ: NetElementGroup::readNetDelta(ds, interpolationTime, rules); break;
    case SB_NET_SYNC_MARK_READ:
      m_hasRecentChanges = true;
      m_recentDeltaTime = interpolationTime;
      m_recentDeltaWasBlank = false;
      break;
    case SB_NET_SYNC_NEED_LOAD: netElementsNeedLoad(argument != 0); break;
    default: throw std::logic_error("Invalid NetElementSyncGroup read leaf");
    }
  });
#else
  NetElementGroup::readNetDelta(ds, interpolationTime, rules);

  m_hasRecentChanges = true;
  m_recentDeltaTime = interpolationTime;
  m_recentDeltaWasBlank = false;

  netElementsNeedLoad(false);
#endif
}

void NetElementSyncGroup::blankNetDelta(float interpolationTime) {
#ifdef STAR_USE_RUST_NET_GROUP
  netSync(SB_NET_SYNC_BLANK, [&](uint32_t leaf, uint64_t argument, SbNetSyncReply& reply) {
    switch (leaf) {
    case SB_NET_SYNC_BASE_BLANK: NetElementGroup::blankNetDelta(interpolationTime); break;
    case SB_NET_SYNC_WAS_BLANK: reply.a = m_recentDeltaWasBlank; break;
    case SB_NET_SYNC_MARK_BLANK:
      m_recentDeltaTime = interpolationTime;
      m_recentDeltaWasBlank = true;
      break;
    case SB_NET_SYNC_LOAD_BLANK_READY: reply.a = m_hasRecentChanges && netInterpolationEnabled(); break;
    case SB_NET_SYNC_NEED_LOAD: netElementsNeedLoad(argument != 0); break;
    default: throw std::logic_error("Invalid NetElementSyncGroup blank leaf");
    }
  });
#else
  NetElementGroup::blankNetDelta(interpolationTime);

  if (!m_recentDeltaWasBlank) {
    m_recentDeltaTime = interpolationTime;
    m_recentDeltaWasBlank = true;
  }

  if (m_hasRecentChanges && netInterpolationEnabled())
    netElementsNeedLoad(false);
#endif
}

void NetElementSyncGroup::netElementsNeedLoad(bool) {}

void NetElementSyncGroup::netElementsNeedStore() {}

void NetElementCallbackGroup::setNeedsLoadCallback(function<void(bool)> needsLoadCallback) {
  m_netElementsNeedLoad = std::move(needsLoadCallback);
}

void NetElementCallbackGroup::setNeedsStoreCallback(function<void()> needsStoreCallback) {
  m_netElementsNeedStore = std::move(needsStoreCallback);
}

void NetElementCallbackGroup::netElementsNeedLoad(bool load) {
  if (m_netElementsNeedLoad)
    m_netElementsNeedLoad(load);
}

void NetElementCallbackGroup::netElementsNeedStore() {
  if (m_netElementsNeedStore)
    m_netElementsNeedStore();
}

}
