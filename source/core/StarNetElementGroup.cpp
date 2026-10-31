#include "StarNetElementGroup.hpp"
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarNetGroupHost.hpp"
#endif

namespace Star {

void NetElementGroup::addNetElement(NetElement* element, bool propagateInterpolation) {
  starAssert(!m_elements.any([element](auto p) { return p.first == element; }));

#ifdef STAR_USE_RUST_NET_GROUP
  NetGroupDetail::run(SB_NET_GROUP_ADD, CurrentStreamVersion + 1,
      [&](uint32_t leaf, uint64_t argument, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_NET_GROUP_INIT_NEW: element->initNetVersion(m_version); break;
    case SB_NET_GROUP_NEW_INTERPOLATING: reply.a = m_interpolationEnabled && propagateInterpolation; break;
    case SB_NET_GROUP_ENABLE_NEW: element->enableNetInterpolation(m_extrapolationHint); break;
    case SB_NET_GROUP_APPEND_NEW: m_elements.append(pair<NetElement*, bool>(element, propagateInterpolation)); break;
    case SB_NET_GROUP_NEW_COMPAT: reply.a = element->checkWithRules(NetCompatibilityRules(static_cast<VersionNumber>(argument))); break;
    case SB_NET_GROUP_INCREMENT_COUNT: m_elementCounts[static_cast<VersionNumber>(argument)]++; break;
    default: throw std::logic_error("Invalid NetElementGroup add leaf");
    }
  });
#else
  element->initNetVersion(m_version);
  if (m_interpolationEnabled && propagateInterpolation)
    element->enableNetInterpolation(m_extrapolationHint);
  m_elements.append(pair<NetElement*, bool>(element, propagateInterpolation));


  for (VersionNumber i = 0; i < (CurrentStreamVersion + 1); i++) {
    if (element->checkWithRules(NetCompatibilityRules(i)))
      m_elementCounts[i]++;
  }
#endif
}

void NetElementGroup::clearNetElements() {
  m_elementCounts.clear();
  m_elements.clear();
}

void NetElementGroup::initNetVersion(NetElementVersion const* version) {
  m_version = version;
#ifdef STAR_USE_RUST_NET_GROUP
  NetGroupDetail::withRange(SB_NET_GROUP_INIT, 0, m_elements,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetGroupReply&) {
    if (leaf != SB_NET_GROUP_INIT_CURRENT) throw std::logic_error("Invalid NetElementGroup init leaf");
    current().first->initNetVersion(m_version);
  });
#else
  for (auto& p : m_elements)
    p.first->initNetVersion(m_version);
#endif
}

void NetElementGroup::netStore(DataStream& ds, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_GROUP
  NetGroupDetail::withRange(SB_NET_GROUP_STORE, 0, m_elements,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_NET_GROUP_CURRENT_COMPAT: reply.a = current().first->checkWithRules(rules); break;
    case SB_NET_GROUP_STORE_CURRENT: current().first->netStore(ds, rules); break;
    default: throw std::logic_error("Invalid NetElementGroup store leaf");
    }
  });
#else
  for (auto& p : m_elements)
    if (p.first->checkWithRules(rules))
      p.first->netStore(ds, rules);
#endif
}

void NetElementGroup::netLoad(DataStream& ds, NetCompatibilityRules rules) {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_GROUP
  NetGroupDetail::withRange(SB_NET_GROUP_LOAD, 0, m_elements,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_NET_GROUP_CURRENT_COMPAT: reply.a = current().first->checkWithRules(rules); break;
    case SB_NET_GROUP_LOAD_CURRENT: current().first->netLoad(ds, rules); break;
    default: throw std::logic_error("Invalid NetElementGroup load leaf");
    }
  });
#else
  for (auto& p : m_elements)
    if (p.first->checkWithRules(rules))
      p.first->netLoad(ds, rules);
#endif
}

void NetElementGroup::enableNetInterpolation(float extrapolationHint) {
  m_interpolationEnabled = true;
  m_extrapolationHint = extrapolationHint;
#ifdef STAR_USE_RUST_NET_GROUP
  NetGroupDetail::withRange(SB_NET_GROUP_ENABLE, 0, m_elements,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_NET_GROUP_PROPAGATES: reply.a = current().second; break;
    case SB_NET_GROUP_ENABLE_CURRENT: current().first->enableNetInterpolation(extrapolationHint); break;
    default: throw std::logic_error("Invalid NetElementGroup enable leaf");
    }
  });
#else
  for (auto& p : m_elements) {
    if (p.second)
      p.first->enableNetInterpolation(extrapolationHint);
  }
#endif
}

void NetElementGroup::disableNetInterpolation() {
  m_interpolationEnabled = false;
  m_extrapolationHint = 0;
#ifdef STAR_USE_RUST_NET_GROUP
  NetGroupDetail::withRange(SB_NET_GROUP_DISABLE, 0, m_elements,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_NET_GROUP_PROPAGATES: reply.a = current().second; break;
    case SB_NET_GROUP_DISABLE_CURRENT: current().first->disableNetInterpolation(); break;
    default: throw std::logic_error("Invalid NetElementGroup disable leaf");
    }
  });
#else
  for (auto& p : m_elements) {
    if (p.second)
      p.first->disableNetInterpolation();
  }
#endif
}

void NetElementGroup::tickNetInterpolation(float dt) {
#ifdef STAR_USE_RUST_NET_GROUP
  NetGroupDetail::withRange(SB_NET_GROUP_TICK, 0, m_elements,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_NET_GROUP_GROUP_ENABLED: reply.a = m_interpolationEnabled; break;
    case SB_NET_GROUP_TICK_CURRENT: current().first->tickNetInterpolation(dt); break;
    default: throw std::logic_error("Invalid NetElementGroup tick leaf");
    }
  });
#else
  if (m_interpolationEnabled) {
    for (auto& p : m_elements)
      p.first->tickNetInterpolation(dt);
  }
#endif
}

bool NetElementGroup::writeNetDelta(DataStream& ds, uint64_t fromVersion, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return false;

#ifdef STAR_USE_RUST_NET_GROUP
  return NetGroupDetail::withRange(SB_NET_GROUP_WRITE, 0, m_elements,
      [&](uint32_t leaf, uint64_t argument, auto& current, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_NET_GROUP_EXPECTED_SIZE: reply.a = m_elementCounts.maybe(rules.version()).value(m_elements.size()); break;
    case SB_NET_GROUP_CURRENT_COMPAT: reply.a = current().first->checkWithRules(rules); break;
    case SB_NET_GROUP_WRITE_DIRECT: reply.a = current().first->writeNetDelta(ds, fromVersion, rules); break;
    case SB_NET_GROUP_SET_BUFFER_RULES: m_buffer.setStreamCompatibilityVersion(rules); break;
    case SB_NET_GROUP_WRITE_BUFFERED: reply.a = current().first->writeNetDelta(m_buffer, fromVersion, rules); break;
    case SB_NET_GROUP_WRITE_INDEX: ds.writeVlqU(argument); break;
    case SB_NET_GROUP_WRITE_BUFFER: ds.writeBytes(m_buffer.data()); break;
    case SB_NET_GROUP_CLEAR_BUFFER: m_buffer.clear(); break;
    case SB_NET_GROUP_WRITE_TERMINATOR: ds.writeVlqU(0); break;
    default: throw std::logic_error("Invalid NetElementGroup write leaf");
    }
  });
#else
  auto expectedSize = m_elementCounts.maybe(rules.version()).value(m_elements.size());

  if (expectedSize == 0) {
    return false;
  } else if (expectedSize == 1) {
    for (auto& element : m_elements) {
      if (element.first->checkWithRules(rules)) {
        return element.first->writeNetDelta(ds, fromVersion, rules);
      }
    }
  } else {
    bool deltaWritten = false;
    uint64_t i = 0;
    m_buffer.setStreamCompatibilityVersion(rules);
    for (auto& element : m_elements) {
      if (i > expectedSize)
        break;
      if (!element.first->checkWithRules(rules))
        continue;
      ++i;

      if (element.first->writeNetDelta(m_buffer, fromVersion, rules)) {
        deltaWritten = true;
        ds.writeVlqU(i);
        ds.writeBytes(m_buffer.data());
        m_buffer.clear();
      }
    }
    if (deltaWritten)
      ds.writeVlqU(0);
    return deltaWritten;
  }
  return false;
#endif
}

void NetElementGroup::readNetDelta(DataStream& ds, float interpolationTime, NetCompatibilityRules rules) {
  if (!checkWithRules(rules))
    return;

#ifdef STAR_USE_RUST_NET_GROUP
  NetGroupDetail::withRange(SB_NET_GROUP_READ, 0, m_elements,
      [&](uint32_t leaf, uint64_t argument, auto& current, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_NET_GROUP_EXPECTED_SIZE: reply.a = m_elementCounts.maybe(rules.version()).value(m_elements.size()); break;
    case SB_NET_GROUP_CURRENT_COMPAT: reply.a = current().first->checkWithRules(rules); break;
    case SB_NET_GROUP_READ_DIRECT: current().first->readNetDelta(ds, interpolationTime, rules); break;
    case SB_NET_GROUP_READ_INDEX: reply.a = ds.readVlqU(); break;
    case SB_NET_GROUP_GROUP_ENABLED: reply.a = m_interpolationEnabled; break;
    case SB_NET_GROUP_BLANK_INDEX: m_elements[argument].first->blankNetDelta(interpolationTime); break;
    case SB_NET_GROUP_READ_AT_INDEX: m_elements[argument].first->readNetDelta(ds, interpolationTime, rules); break;
    case SB_NET_GROUP_THROW_EMPTY: throw IOException("readNetDelta called on empty NetElementGroup");
    case SB_NET_GROUP_THROW_ORDER: throw IOException("group indexes out of order in NetElementGroup::readNetDelta");
    default: throw std::logic_error("Invalid NetElementGroup read leaf");
    }
  });
#else
  auto expectedSize = m_elementCounts.maybe(rules.version()).value(m_elements.size());

  if (expectedSize == 0) {
    throw IOException("readNetDelta called on empty NetElementGroup");
  } else if (expectedSize == 1) {
    for (auto& element : m_elements)
      if (element.first->checkWithRules(rules)) {
        element.first->readNetDelta(ds, interpolationTime, rules);
        break;
      }
  } else {
    uint64_t readIndex = ds.readVlqU();
    uint64_t i = 0;
    uint64_t offset = 0;
    for (auto& element : m_elements) {
      if (i > expectedSize)
        break;
      if (!element.first->checkWithRules(rules)) {
        offset++;
        continue;
      }
      if (readIndex == 0 || readIndex - 1 > i) {
        if (m_interpolationEnabled)
          m_elements[i + offset].first->blankNetDelta(interpolationTime);
      } else if (readIndex - 1 == i) {
        m_elements[i + offset].first->readNetDelta(ds, interpolationTime, rules);
        readIndex = ds.readVlqU();
      } else {
        throw IOException("group indexes out of order in NetElementGroup::readNetDelta");
      }
      ++i;
    }
  }
#endif
}

void NetElementGroup::blankNetDelta(float interpolationTime) {
#ifdef STAR_USE_RUST_NET_GROUP
  NetGroupDetail::withRange(SB_NET_GROUP_BLANK, 0, m_elements,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_NET_GROUP_GROUP_ENABLED: reply.a = m_interpolationEnabled; break;
    case SB_NET_GROUP_BLANK_CURRENT: current().first->blankNetDelta(interpolationTime); break;
    default: throw std::logic_error("Invalid NetElementGroup blank leaf");
    }
  });
#else
  if (m_interpolationEnabled) {
    for (auto& p : m_elements)
      p.first->blankNetDelta(interpolationTime);
  }
#endif
}

}
