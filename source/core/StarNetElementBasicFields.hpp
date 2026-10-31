#pragma once

#include <type_traits>

#include "StarNetElement.hpp"
#include "StarString.hpp"
#include "StarByteArray.hpp"
#ifdef STAR_USE_RUST_NET_FIELD
#include "StarNetFieldHost.hpp"
#endif

namespace Star {

template <typename T>
class NetElementBasicField : public NetElement {
public:
  virtual ~NetElementBasicField() = default;

  T const& get() const;

  // Updates the value if the value is different than the existing value,
  // requires T have operator==
  void set(T const& value);

  // Always updates the value and marks it as updated.
  void push(T value);

  // Has this field been updated since the last call to pullUpdated?
  bool pullUpdated();

  // Update the value in place.  The mutator will be called as bool
  // mutator(T&), return true to signal that the value was updated.
  template <typename Mutator>
  void update(Mutator&& mutator);

  void initNetVersion(NetElementVersion const* version = nullptr) override;

  // Values are never interpolated, but they will be delayed for the given
  // interpolationTime.
  void enableNetInterpolation(float extrapolationHint = 0.0f) override;
  void disableNetInterpolation() override;
  void tickNetInterpolation(float dt) override;

  void netStore(DataStream& ds, NetCompatibilityRules rules = {}) const override;
  void netLoad(DataStream& ds, NetCompatibilityRules rules) override;

  bool writeNetDelta(DataStream& ds, uint64_t fromVersion, NetCompatibilityRules rules = {}) const override;
  void readNetDelta(DataStream& ds, float interpolationTime = 0.0f, NetCompatibilityRules rules = {}) override;

protected:
  virtual void readData(DataStream& ds, T& t) const = 0;
  virtual void writeData(DataStream& ds, T const& t) const = 0;

  virtual void updated();

private:
#ifdef STAR_USE_RUST_NET_FIELD
  void netFieldConstLeaf(uint32_t leaf, SbNetFieldReply& reply, DataStream* stream = nullptr) const;
  void netFieldMutableLeaf(uint32_t leaf, SbNetFieldReply& reply, DataStream* stream = nullptr);
#endif
  NetElementVersion const* m_netVersion = nullptr;
  uint64_t m_latestUpdateVersion = 0;
  T m_value = T();
  bool m_updated = false;
  Maybe<Deque<pair<float, T>>> m_pendingInterpolatedValues;
};

template <typename T>
class NetElementIntegral : public NetElementBasicField<T> {
protected:
  void readData(DataStream& ds, T& v) const override;
  void writeData(DataStream& ds, T const& v) const override;
};

typedef NetElementIntegral<int64_t> NetElementInt;
typedef NetElementIntegral<uint64_t> NetElementUInt;

// Properly encodes NPos no matter the platform width of size_t NetElement
// size_t values are NOT clamped when setting.
class NetElementSize : public NetElementBasicField<size_t> {
protected:
  void readData(DataStream& ds, size_t& v) const override;
  void writeData(DataStream& ds, size_t const& v) const override;
};

class NetElementBool : public NetElementBasicField<bool> {
protected:
  void readData(DataStream& ds, bool& v) const override;
  void writeData(DataStream& ds, bool const& v) const override;
};

template <typename Enum>
class NetElementEnum : public NetElementBasicField<Enum> {
protected:
  void readData(DataStream& ds, Enum& v) const override;
  void writeData(DataStream& ds, Enum const& v) const override;
};

// Wraps a uint64_t to give a simple event stream.  Every trigger is an
// increment to a held uint64_t value, and slaves can see how many triggers
// have occurred since the last check.
class NetElementEvent : public NetElementUInt {
public:
  void trigger();

  // Returns the number of times this event has been triggered since the last
  // pullOccurrences call.
  uint64_t pullOccurrences();

  // Pulls whether this event occurred at all, ignoring the number
  bool pullOccurred();

  // Ignore all the existing ocurrences
  void ignoreOccurrences();
  void setIgnoreOccurrencesOnNetLoad(bool ignoreOccurrencesOnNetLoad);

  void netLoad(DataStream& ds, NetCompatibilityRules rules) override;

protected:
  void updated() override;

private:
  using NetElementUInt::get;
  using NetElementUInt::set;
  using NetElementUInt::push;
  using NetElementUInt::update;

  uint64_t m_pulledOccurrences = 0;
  bool m_ignoreOccurrencesOnNetLoad = false;
};

// Holds an arbitrary serializable value
template <typename T>
class NetElementData : public NetElementBasicField<T> {
public:
  NetElementData();
  NetElementData(function<void(DataStream&, T&)> reader, function<void(DataStream&, T const&)> writer);

protected:
  void readData(DataStream& ds, T& v) const override;
  void writeData(DataStream& ds, T const& v) const override;

private:
  function<void(DataStream&, T&)> m_reader;
  function<void(DataStream&, T const&)> m_writer;
};

typedef NetElementData<String> NetElementString;
typedef NetElementData<ByteArray> NetElementBytes;

#ifdef STAR_USE_RUST_NET_FIELD
template <typename T>
void NetElementBasicField<T>::netFieldConstLeaf(uint32_t leaf, SbNetFieldReply& reply, DataStream* stream) const {
  switch (leaf) {
  case SB_NET_FIELD_HAS_PENDING: reply.a = bool(m_pendingInterpolatedValues); break;
  case SB_NET_FIELD_PENDING_NONEMPTY: reply.a = !m_pendingInterpolatedValues->empty(); break;
  case SB_NET_FIELD_NEXT_READY:
    reply.a = !m_pendingInterpolatedValues->empty() && m_pendingInterpolatedValues->first().first <= 0.0f;
    break;
  case SB_NET_FIELD_LAST_AVAILABLE:
    reply.a = m_pendingInterpolatedValues && !m_pendingInterpolatedValues->empty();
    break;
  case SB_NET_FIELD_LATEST_VERSION: reply.a = m_latestUpdateVersion; break;
  case SB_NET_FIELD_WRITE_LAST: writeData(*stream, m_pendingInterpolatedValues->last().second); break;
  case SB_NET_FIELD_WRITE_VALUE: writeData(*stream, m_value); break;
  default: throw std::logic_error("Invalid NetElementBasicField const leaf");
  }
}

template <typename T>
void NetElementBasicField<T>::netFieldMutableLeaf(uint32_t leaf, SbNetFieldReply& reply, DataStream* stream) {
  // Keep typed assignments and virtual hooks whole: a throwing operation may
  // already have changed a value or popped a pending entry. Do not roll it back.
  switch (leaf) {
  case SB_NET_FIELD_UPDATED: updated(); break;
  case SB_NET_FIELD_SET_LATEST: m_latestUpdateVersion = m_netVersion ? m_netVersion->current() : 0; break;
  case SB_NET_FIELD_CLEAR_PENDING: m_pendingInterpolatedValues->clear(); break;
  case SB_NET_FIELD_EMPLACE_PENDING: m_pendingInterpolatedValues.emplace(); break;
  case SB_NET_FIELD_ASSIGN_LAST: m_value = m_pendingInterpolatedValues->takeLast().second; break;
  case SB_NET_FIELD_RESET_PENDING: m_pendingInterpolatedValues.reset(); break;
  case SB_NET_FIELD_ASSIGN_FIRST: m_value = m_pendingInterpolatedValues->takeFirst().second; break;
  case SB_NET_FIELD_READ_VALUE: readData(*stream, m_value); break;
  default: netFieldConstLeaf(leaf, reply, stream); break;
  }
}

#endif
template <typename T>
T const& NetElementBasicField<T>::get() const {
  return m_value;
}

template <typename T>
void NetElementBasicField<T>::set(T const& value) {
#ifdef STAR_USE_RUST_NET_FIELD
  NetFieldDetail::run(SB_NET_FIELD_SET, 0, [&](uint32_t leaf, uint64_t, SbNetFieldReply& reply) {
    switch (leaf) {
    case SB_NET_FIELD_CHANGED:
      if (!(m_value == value)) reply.a = 1;
      break;
    case SB_NET_FIELD_PUSH_COPY: push(value); break;
    default: throw std::logic_error("Invalid NetElementBasicField set leaf");
    }
  });
#else
  if (!(m_value == value))
    push(value);
#endif
}

template <typename T>
void NetElementBasicField<T>::push(T value) {
#ifdef STAR_USE_RUST_NET_FIELD
  NetFieldDetail::run(SB_NET_FIELD_PUSH, 0, [&](uint32_t leaf, uint64_t, SbNetFieldReply& reply) {
    if (leaf == SB_NET_FIELD_ASSIGN_PUSH)
      m_value = std::move(value);
    else
      netFieldMutableLeaf(leaf, reply);
  });
#else
  m_value = std::move(value);
  updated();
  m_latestUpdateVersion = m_netVersion ? m_netVersion->current() : 0;
  if (m_pendingInterpolatedValues)
    m_pendingInterpolatedValues->clear();
#endif
}

template <typename T>
bool NetElementBasicField<T>::pullUpdated() {
  return take(m_updated);
}

template <typename T>
template <typename Mutator>
void NetElementBasicField<T>::update(Mutator&& mutator) {
#ifdef STAR_USE_RUST_NET_FIELD
  NetFieldDetail::run(SB_NET_FIELD_UPDATE, 0, [&](uint32_t leaf, uint64_t, SbNetFieldReply& reply) {
    if (leaf == SB_NET_FIELD_MUTATE) {
      if (mutator(m_value)) reply.a = 1;
    } else
      netFieldMutableLeaf(leaf, reply);
  });
#else
  if (mutator(m_value)) {
    updated();
    m_latestUpdateVersion = m_netVersion ? m_netVersion->current() : 0;
    if (m_pendingInterpolatedValues)
      m_pendingInterpolatedValues->clear();
  }
#endif
}

template <typename T>
void NetElementBasicField<T>::initNetVersion(NetElementVersion const* version) {
  m_netVersion = version;
  m_latestUpdateVersion = 0;
}

template <typename T>
void NetElementBasicField<T>::enableNetInterpolation(float) {
#ifdef STAR_USE_RUST_NET_FIELD
  NetFieldDetail::run(SB_NET_FIELD_ENABLE, 0, [&](uint32_t leaf, uint64_t, SbNetFieldReply& reply) {
    netFieldMutableLeaf(leaf, reply);
  });
#else
  if (!m_pendingInterpolatedValues)
    m_pendingInterpolatedValues.emplace();
#endif
}

template <typename T>
void NetElementBasicField<T>::disableNetInterpolation() {
#ifdef STAR_USE_RUST_NET_FIELD
  NetFieldDetail::run(SB_NET_FIELD_DISABLE, 0, [&](uint32_t leaf, uint64_t, SbNetFieldReply& reply) {
    netFieldMutableLeaf(leaf, reply);
  });
#else
  if (m_pendingInterpolatedValues) {
    if (!m_pendingInterpolatedValues->empty())
      m_value = m_pendingInterpolatedValues->takeLast().second;
    m_pendingInterpolatedValues.reset();
  }
#endif
}

template <typename T>
void NetElementBasicField<T>::tickNetInterpolation(float dt) {
#ifdef STAR_USE_RUST_NET_FIELD
  using Iterator = typename Deque<pair<float, T>>::iterator;
  std::optional<std::pair<Iterator, Iterator>> range;
  NetFieldDetail::run(SB_NET_FIELD_TICK, 0, [&](uint32_t leaf, uint64_t, SbNetFieldReply& reply) {
    switch (leaf) {
    case SB_NET_FIELD_ENTER_RANGE: {
      auto begin = m_pendingInterpolatedValues->begin();
      auto end = m_pendingInterpolatedValues->end();
      range.emplace(begin, end);
      break;
    }
    case SB_NET_FIELD_MORE: reply.a = range->first != range->second; break;
    case SB_NET_FIELD_DECREMENT: range->first->first -= dt; break;
    case SB_NET_FIELD_ADVANCE: ++range->first; break;
    case SB_NET_FIELD_LEAVE_RANGE: range.reset(); break;
    default: netFieldMutableLeaf(leaf, reply); break;
    }
  });
#else
  if (m_pendingInterpolatedValues) {
    for (auto& p : *m_pendingInterpolatedValues)
      p.first -= dt;
    while (!m_pendingInterpolatedValues->empty() && m_pendingInterpolatedValues->first().first <= 0.0f) {
      m_value = m_pendingInterpolatedValues->takeFirst().second;
      updated();
    }
  }
#endif
}

template <typename T>
void NetElementBasicField<T>::netStore(DataStream& ds, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_FIELD
  NetFieldDetail::run(SB_NET_FIELD_STORE, 0, [&](uint32_t leaf, uint64_t, SbNetFieldReply& reply) {
    netFieldConstLeaf(leaf, reply, &ds);
  });
#else
  if (m_pendingInterpolatedValues && !m_pendingInterpolatedValues->empty())
    writeData(ds, m_pendingInterpolatedValues->last().second);
  else
    writeData(ds, m_value);
#endif
}

template <typename T>
void NetElementBasicField<T>::netLoad(DataStream& ds, NetCompatibilityRules rules) {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_FIELD
  NetFieldDetail::run(SB_NET_FIELD_LOAD, 0, [&](uint32_t leaf, uint64_t, SbNetFieldReply& reply) {
    netFieldMutableLeaf(leaf, reply, &ds);
  });
#else
  readData(ds, m_value);
  m_latestUpdateVersion = m_netVersion ? m_netVersion->current() : 0;
  updated();
  if (m_pendingInterpolatedValues)
    m_pendingInterpolatedValues->clear();
#endif
}

template <typename T>
bool NetElementBasicField<T>::writeNetDelta(DataStream& ds, uint64_t fromVersion, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return false;
#ifdef STAR_USE_RUST_NET_FIELD
  return NetFieldDetail::run(SB_NET_FIELD_WRITE, fromVersion, [&](uint32_t leaf, uint64_t, SbNetFieldReply& reply) {
    netFieldConstLeaf(leaf, reply, &ds);
  });
#else
  if (m_latestUpdateVersion < fromVersion)
    return false;

  if (m_pendingInterpolatedValues && !m_pendingInterpolatedValues->empty())
    writeData(ds, m_pendingInterpolatedValues->last().second);
  else
    writeData(ds, m_value);

  return true;
#endif
}

template <typename T>
void NetElementBasicField<T>::readNetDelta(DataStream& ds, float interpolationTime, NetCompatibilityRules rules) {
  if (!checkWithRules(rules)) return;
  T t;
#ifdef STAR_USE_RUST_NET_FIELD
  NetFieldDetail::run(SB_NET_FIELD_READ, 0, [&](uint32_t leaf, uint64_t, SbNetFieldReply& reply) {
    switch (leaf) {
    case SB_NET_FIELD_READ_INCOMING: readData(ds, t); break;
    case SB_NET_FIELD_ACCEPT_DELAY:
      reply.a = interpolationTime > 0.0f && (m_pendingInterpolatedValues->empty() || interpolationTime >= m_pendingInterpolatedValues->last().first);
      break;
    case SB_NET_FIELD_APPEND_INCOMING: m_pendingInterpolatedValues->append({interpolationTime, std::move(t)}); break;
    case SB_NET_FIELD_ASSIGN_INCOMING: m_value = std::move(t); break;
    default: netFieldMutableLeaf(leaf, reply); break;
    }
  });
#else
  readData(ds, t);
  m_latestUpdateVersion = m_netVersion ? m_netVersion->current() : 0;
  if (m_pendingInterpolatedValues) {
    // Only append an incoming delta to our pending value list if the incoming
    // step is forward in time of every other pending value.  In any other
    // case, this is an error or the step tracking is wildly off, so just clear
    // any other incoming values.
    if (interpolationTime > 0.0f && (m_pendingInterpolatedValues->empty() || interpolationTime >= m_pendingInterpolatedValues->last().first)) {
      m_pendingInterpolatedValues->append({interpolationTime, std::move(t)});
    } else {
      m_value = std::move(t);
      m_pendingInterpolatedValues->clear();
      updated();
    }
  } else {
    m_value = std::move(t);
    updated();
  }
#endif
}

template <typename T>
void NetElementBasicField<T>::updated() {
  m_updated = true;
}

template <typename T>
void NetElementIntegral<T>::readData(DataStream& ds, T& v) const {
  if (sizeof(T) == 1) {
    ds.read(v);
  } else {
    if (std::is_unsigned<T>::value)
      v = ds.readVlqU();
    else
      v = ds.readVlqI();
  }
}

template <typename T>
void NetElementIntegral<T>::writeData(DataStream& ds, T const& v) const {
  if (sizeof(T) == 1) {
    ds.write(v);
  } else {
    if (std::is_unsigned<T>::value)
      ds.writeVlqU(v);
    else
      ds.writeVlqI(v);
  }
}

template <typename Enum>
void NetElementEnum<Enum>::readData(DataStream& ds, Enum& v) const {
  if (sizeof(Enum) == 1)
    ds.read(v);
  else
    v = (Enum)ds.readVlqI();
}

template <typename Enum>
void NetElementEnum<Enum>::writeData(DataStream& ds, Enum const& v) const {
  if (sizeof(Enum) == 1)
    ds.write(v);
  else
    ds.writeVlqI((int64_t)v);
}

template <typename T>
NetElementData<T>::NetElementData()
  : NetElementData([](DataStream& ds, T & t) { ds >> t; }, [](DataStream& ds, T const& t) { ds << t; }) {}

template <typename T>
NetElementData<T>::NetElementData(function<void(DataStream&, T&)> reader, function<void(DataStream&, T const&)> writer)
  : m_reader(std::move(reader)), m_writer(std::move(writer)) {}

template <typename T>
void NetElementData<T>::readData(DataStream& ds, T& v) const {
  m_reader(ds, v);
}

template <typename T>
void NetElementData<T>::writeData(DataStream& ds, T const& v) const {
  m_writer(ds, v);
}

}
