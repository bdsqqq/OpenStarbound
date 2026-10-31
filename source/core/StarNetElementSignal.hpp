#pragma once

#include "StarNetElement.hpp"
#ifdef STAR_USE_RUST_NET_SIGNAL
#include "StarNetSignalHost.hpp"
#endif

namespace Star {

// NetElement that sends signals during delta writes that can be received by
// slaves.  It has no 'state', and nothing is sent during a store / load, and
// it only keeps past signals for a maximum number of versions.  Thus, it is
// not appropriate to use to send updates to long term states, only for event
// like things that are not harmful if missed.
template <typename Signal>
class NetElementSignal : public NetElement {
public:
  NetElementSignal(size_t maxSignalQueue = 32);

  void initNetVersion(NetElementVersion const* version = nullptr) override;

  void netStore(DataStream& ds, NetCompatibilityRules rules = {}) const override;
  void netLoad(DataStream& ds, NetCompatibilityRules rules) override;

  void enableNetInterpolation(float extrapolationHint = 0.0f) override;
  void disableNetInterpolation() override;
  void tickNetInterpolation(float dt) override;

  bool writeNetDelta(DataStream& ds, uint64_t fromVersion, NetCompatibilityRules rules = {}) const override;
  void readNetDelta(DataStream& ds, float interpolationTime = 0.0f, NetCompatibilityRules rules = {}) override;

  void send(Signal signal);
  List<Signal> receive();

private:
#ifdef STAR_USE_RUST_NET_SIGNAL
  void flushPendingSignals();
#endif
  struct SignalEntry {
    uint64_t version;
    Signal signal;
    bool received;
  };

  size_t m_maxSignalQueue;
  NetElementVersion const* m_netVersion = nullptr;
  bool m_netInterpolationEnabled = false;
  Deque<SignalEntry> m_signals;
  Deque<pair<float, Signal>> m_pendingSignals;
};

template <typename Signal>
NetElementSignal<Signal>::NetElementSignal(size_t maxSignalQueue) {
  m_maxSignalQueue = maxSignalQueue;
}

template <typename Signal>
void NetElementSignal<Signal>::initNetVersion(NetElementVersion const* version) {
  m_netVersion = version;
  m_signals.clear();
}

template <typename Signal>
void NetElementSignal<Signal>::netStore(DataStream&, NetCompatibilityRules) const {}

template <typename Signal>
void NetElementSignal<Signal>::netLoad(DataStream&, NetCompatibilityRules) {
}

template <typename Signal>
void NetElementSignal<Signal>::enableNetInterpolation(float) {
  m_netInterpolationEnabled = true;
}

template <typename Signal>
void NetElementSignal<Signal>::disableNetInterpolation() {
  m_netInterpolationEnabled = false;
#ifdef STAR_USE_RUST_NET_SIGNAL
  flushPendingSignals();
#else
  for (auto& p : take(m_pendingSignals))
    send(std::move(p.second));
#endif
}

template <typename Signal>
void NetElementSignal<Signal>::tickNetInterpolation(float dt) {
#ifdef STAR_USE_RUST_NET_SIGNAL
  using Iterator = typename Deque<pair<float, Signal>>::iterator;
  std::optional<std::pair<Iterator, Iterator>> range;
  NetSignalDetail::run(SB_NET_SIGNAL_TICK, 0,
      [&](uint32_t leaf, uint64_t, SbNetSignalReply& reply) {
    switch (leaf) {
    case SB_NET_SIGNAL_ENTER_RANGE: {
      auto begin = m_pendingSignals.begin();
      auto end = m_pendingSignals.end();
      range.emplace(begin, end);
      break;
    }
    case SB_NET_SIGNAL_MORE: reply.a = range->first != range->second; break;
    case SB_NET_SIGNAL_DECREMENT_TIME: range->first->first -= dt; break;
    case SB_NET_SIGNAL_ADVANCE: ++range->first; break;
    case SB_NET_SIGNAL_LEAVE_RANGE: range.reset(); break;
    case SB_NET_SIGNAL_NEXT_PENDING_READY:
      reply.a = !m_pendingSignals.empty() && m_pendingSignals.first().first <= 0.0f;
      break;
    case SB_NET_SIGNAL_EMIT_PENDING_FRONT: send(m_pendingSignals.takeFirst().second); break;
    default: throw std::logic_error("Invalid NetElementSignal tick leaf");
    }
  });
#else
  for (auto& p : m_pendingSignals)
    p.first -= dt;

  while (!m_pendingSignals.empty() && m_pendingSignals.first().first <= 0.0f)
    send(m_pendingSignals.takeFirst().second);
#endif
}

template <typename Signal>
bool NetElementSignal<Signal>::writeNetDelta(DataStream& ds, uint64_t fromVersion, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return false;
#ifdef STAR_USE_RUST_NET_SIGNAL
  using Iterator = typename Deque<SignalEntry>::const_iterator;
  std::optional<std::pair<Iterator, Iterator>> range;
  return NetSignalDetail::run(SB_NET_SIGNAL_WRITE, fromVersion,
      [&](uint32_t leaf, uint64_t argument, SbNetSignalReply& reply) {
    switch (leaf) {
    case SB_NET_SIGNAL_ENTER_RANGE: {
      auto begin = m_signals.begin();
      auto end = m_signals.end();
      range.emplace(begin, end);
      break;
    }
    case SB_NET_SIGNAL_MORE: reply.a = range->first != range->second; break;
    case SB_NET_SIGNAL_VERSION: reply.a = range->first->version; break;
    case SB_NET_SIGNAL_ADVANCE: ++range->first; break;
    case SB_NET_SIGNAL_LEAVE_RANGE: range.reset(); break;
    case SB_NET_SIGNAL_WRITE_HEADER: ds.writeVlqU(static_cast<size_t>(argument)); break;
    case SB_NET_SIGNAL_WRITE_SIGNAL: ds.write(range->first->signal); break;
    default: throw std::logic_error("Invalid NetElementSignal write leaf");
    }
  });
#else
  size_t numToWrite = 0;
  for (auto const& p : m_signals) {
    if (p.version >= fromVersion)
      ++numToWrite;
  }
  if (numToWrite == 0)
    return false;

  ds.writeVlqU(numToWrite);

  for (auto const& p : m_signals) {
    if (p.version >= fromVersion)
      ds.write(p.signal);
  }

  return true;
#endif
}

template <typename Signal>
void NetElementSignal<Signal>::readNetDelta(DataStream& ds, float interpolationTime, NetCompatibilityRules rules) {
  if (!checkWithRules(rules)) return;
  size_t numToRead = ds.readVlqU();
#ifdef STAR_USE_RUST_NET_SIGNAL
  NetSignalDetail::run(SB_NET_SIGNAL_READ, numToRead,
      [&](uint32_t leaf, uint64_t, SbNetSignalReply&) {
    if (leaf != SB_NET_SIGNAL_READ_ITEM_OP)
      throw std::logic_error("Invalid NetElementSignal read leaf");
    // The typed signal lives across its nested policy, but is destroyed before
    // the outer controller advances, including on read/append/send failures.
    Signal s;
    ds.read(s);
    NetSignalDetail::run(SB_NET_SIGNAL_READ_ITEM, 0,
        [&](uint32_t itemLeaf, uint64_t, SbNetSignalReply& reply) {
      switch (itemLeaf) {
      case SB_NET_SIGNAL_INTERPOLATING:
        reply.a = m_netInterpolationEnabled && interpolationTime > 0.0f;
        break;
      case SB_NET_SIGNAL_NEEDS_FLUSH:
        reply.a = !m_pendingSignals.empty() && m_pendingSignals.last().first > interpolationTime;
        break;
      case SB_NET_SIGNAL_FLUSH_PENDING: flushPendingSignals(); break;
      case SB_NET_SIGNAL_APPEND_PENDING: m_pendingSignals.append({interpolationTime, std::move(s)}); break;
      case SB_NET_SIGNAL_EMIT_READ: send(std::move(s)); break;
      default: throw std::logic_error("Invalid NetElementSignal read-item leaf");
      }
    });
  });
#else
  for (size_t i = 0; i < numToRead; ++i) {
    Signal s;
    ds.read(s);
    if (m_netInterpolationEnabled && interpolationTime > 0.0f) {
      if (!m_pendingSignals.empty() && m_pendingSignals.last().first > interpolationTime) {
        for (auto& p : take(m_pendingSignals))
          send(std::move(p.second));
      }
      m_pendingSignals.append({interpolationTime, std::move(s)});
    } else {
      send(std::move(s));
    }
  }
#endif
}

#ifdef STAR_USE_RUST_NET_SIGNAL
template <typename Signal>
void NetElementSignal<Signal>::flushPendingSignals() {
  // Match the native range-for's owned take() temporary, not a borrowed queue.
  // On a throwing send, all remaining taken signals die before the caller resumes.
  auto&& pending = take(m_pendingSignals);
  auto begin = pending.begin();
  auto end = pending.end();
  NetSignalDetail::run(SB_NET_SIGNAL_FLUSH, 0,
      [&](uint32_t leaf, uint64_t, SbNetSignalReply& reply) {
    switch (leaf) {
    case SB_NET_SIGNAL_MORE: reply.a = begin != end; break;
    case SB_NET_SIGNAL_EMIT_PENDING_MOVE: send(std::move(begin->second)); break;
    case SB_NET_SIGNAL_ADVANCE: ++begin; break;
    default: throw std::logic_error("Invalid NetElementSignal flush leaf");
    }
  });
}

#endif
template <typename Signal>
void NetElementSignal<Signal>::send(Signal signal) {
#ifdef STAR_USE_RUST_NET_SIGNAL
  NetSignalDetail::run(SB_NET_SIGNAL_SEND, 0,
      [&](uint32_t leaf, uint64_t, SbNetSignalReply& reply) {
    switch (leaf) {
    case SB_NET_SIGNAL_APPEND_SIGNAL:
      m_signals.append({m_netVersion ? m_netVersion->current() : 0, signal, false});
      break;
    case SB_NET_SIGNAL_QUEUE_LIMIT:
      reply.a = m_signals.size();
      reply.b = m_maxSignalQueue;
      break;
    case SB_NET_SIGNAL_POP_FRONT: m_signals.removeFirst(); break;
    default: throw std::logic_error("Invalid NetElementSignal send leaf");
    }
  });
#else
  m_signals.append({m_netVersion ? m_netVersion->current() : 0, signal, false});
  while (m_signals.size() > m_maxSignalQueue)
    m_signals.removeFirst();
#endif
}

template <typename Signal>
List<Signal> NetElementSignal<Signal>::receive() {
  List<Signal> received;
#ifdef STAR_USE_RUST_NET_SIGNAL
  using Iterator = typename Deque<SignalEntry>::iterator;
  std::optional<std::pair<Iterator, Iterator>> range;
  NetSignalDetail::run(SB_NET_SIGNAL_RECEIVE, 0,
      [&](uint32_t leaf, uint64_t, SbNetSignalReply& reply) {
    switch (leaf) {
    case SB_NET_SIGNAL_ENTER_RANGE: {
      auto begin = m_signals.begin();
      auto end = m_signals.end();
      range.emplace(begin, end);
      break;
    }
    case SB_NET_SIGNAL_MORE: reply.a = range->first != range->second; break;
    case SB_NET_SIGNAL_RECEIVED: reply.a = range->first->received; break;
    case SB_NET_SIGNAL_APPEND_RECEIVED: received.append(range->first->signal); break;
    case SB_NET_SIGNAL_MARK_RECEIVED: range->first->received = true; break;
    case SB_NET_SIGNAL_ADVANCE: ++range->first; break;
    case SB_NET_SIGNAL_LEAVE_RANGE: range.reset(); break;
    default: throw std::logic_error("Invalid NetElementSignal receive leaf");
    }
  });
#else
  for (auto& p : m_signals) {
    if (!p.received) {
      received.append(p.signal);
      p.received = true;
    }
  }
#endif
  return received;
}

}
