#pragma once

#include <type_traits>

#include "StarNetElement.hpp"
#include "StarInterpolation.hpp"
#ifdef STAR_USE_RUST_NET_FIELD
#include "StarNetGroupHost.hpp"
#include "StarRustNetFloat.h"
#endif

namespace Star {

STAR_EXCEPTION(StepStreamException, StarException);

template <typename T>
class NetElementFloating : public NetElement {
public:
  T get() const;
  void set(T value);

  // If a fixed point base is given, then instead of transmitting the value as
  // a float, it is transmitted as a VLQ of the value divided by the fixed
  // point base.  Any NetElementFloating that is transmitted to must also have
  // the same fixed point base set.
  void setFixedPointBase(Maybe<T> fixedPointBase = {});

  // If interpolation is enabled on the NetStepStates parent, and an
  // interpolator is set, then on steps in between data points this will be
  // used to interpolate this value.  It is not necessary that senders and
  // receivers both have matching interpolation functions, or any interpolation
  // functions at all.
  void setInterpolator(function<T(T, T, T)> interpolator);

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
  void blankNetDelta(float interpolationTime = 0.0f) override;

private:
  void writeValue(DataStream& ds, T t) const;
  T readValue(DataStream& ds) const;

  T interpolate() const;

  Maybe<T> m_fixedPointBase;
  NetElementVersion const* m_netVersion = nullptr;
  uint64_t m_latestUpdateVersion = 0;
  T m_value = T();

  function<T(T, T, T)> m_interpolator;
  float m_extrapolation = 0.0f;
  Maybe<Deque<pair<float, T>>> m_interpolationDataPoints;
};

typedef NetElementFloating<float> NetElementFloat;
typedef NetElementFloating<double> NetElementDouble;

template <typename T>
T NetElementFloating<T>::get() const {
  return m_value;
}

template <typename T>
void NetElementFloating<T>::set(T value) {
#ifdef STAR_USE_RUST_NET_FIELD
  NetGroupDetail::run(SB_NET_FLOAT_SET, 0, [&](uint32_t leaf, uint64_t, SbNetFloatReply& reply) {
    switch (leaf) {
    case SB_NET_FLOAT_VALUE_DIFFERS:
      if (m_value != value) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_FLOAT_ENCODE_DIFFERS:
      if (!m_fixedPointBase || round(m_value / *m_fixedPointBase) != round(value / *m_fixedPointBase)) reply.a = 1;
      else reply.a = 0;
      break;
    case SB_NET_FLOAT_CAPTURE_VERSION: m_latestUpdateVersion = m_netVersion ? m_netVersion->current() : 0; break;
    case SB_NET_FLOAT_ASSIGN_INPUT: m_value = value; break;
    case SB_NET_FLOAT_HAS_POINTS:
      if (m_interpolationDataPoints) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_FLOAT_CLEAR_POINTS: m_interpolationDataPoints->clear(); break;
    case SB_NET_FLOAT_APPEND_ZERO: m_interpolationDataPoints->append({0.0f, m_value}); break;
    default: throw std::logic_error("Invalid floating field set leaf");
    }
  }, sb_net_float_run);
#else
  if (m_value != value) {
    // Only mark the step as updated here if it actually would change the
    // transmitted value.
    if (!m_fixedPointBase || round(m_value / *m_fixedPointBase) != round(value / *m_fixedPointBase))
      m_latestUpdateVersion = m_netVersion ? m_netVersion->current() : 0;

    m_value = value;

    if (m_interpolationDataPoints) {
      m_interpolationDataPoints->clear();
      m_interpolationDataPoints->append({0.0f, m_value});
    }
  }
#endif
}

template <typename T>
void NetElementFloating<T>::setFixedPointBase(Maybe<T> fixedPointBase) {
  m_fixedPointBase = fixedPointBase;
}

template <typename T>
void NetElementFloating<T>::setInterpolator(function<T(T, T, T)> interpolator) {
  m_interpolator = std::move(interpolator);
}

template <typename T>
void NetElementFloating<T>::initNetVersion(NetElementVersion const* version) {
  m_netVersion = version;
  m_latestUpdateVersion = 0;
}

template <typename T>
void NetElementFloating<T>::enableNetInterpolation(float extrapolationHint) {
  m_extrapolation = extrapolationHint;
#ifdef STAR_USE_RUST_NET_FIELD
  NetGroupDetail::run(SB_NET_FLOAT_ENABLE, 0, [&](uint32_t leaf, uint64_t, SbNetFloatReply& reply) {
    switch (leaf) {
    case SB_NET_FLOAT_HAS_POINTS:
      if (m_interpolationDataPoints) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_FLOAT_EMPLACE_POINTS: m_interpolationDataPoints.emplace(); break;
    case SB_NET_FLOAT_APPEND_ZERO: m_interpolationDataPoints->append({0.0f, m_value}); break;
    default: throw std::logic_error("Invalid floating field enable leaf");
    }
  }, sb_net_float_run);
#else
  if (!m_interpolationDataPoints) {
    m_interpolationDataPoints.emplace();
    m_interpolationDataPoints->append({0.0f, m_value});
  }
#endif
}

template <typename T>
void NetElementFloating<T>::disableNetInterpolation() {
#ifdef STAR_USE_RUST_NET_FIELD
  NetGroupDetail::run(SB_NET_FLOAT_DISABLE, 0, [&](uint32_t leaf, uint64_t, SbNetFloatReply& reply) {
    switch (leaf) {
    case SB_NET_FLOAT_HAS_POINTS:
      if (m_interpolationDataPoints) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_FLOAT_ASSIGN_LAST: m_value = m_interpolationDataPoints->last().second; break;
    case SB_NET_FLOAT_RESET_POINTS: m_interpolationDataPoints.reset(); break;
    default: throw std::logic_error("Invalid floating field disable leaf");
    }
  }, sb_net_float_run);
#else
  if (m_interpolationDataPoints) {
    m_value = m_interpolationDataPoints->last().second;
    m_interpolationDataPoints.reset();
  }
#endif
}

template <typename T>
void NetElementFloating<T>::tickNetInterpolation(float dt) {
#ifdef STAR_USE_RUST_NET_FIELD
  NetGroupDetail::run(SB_NET_FLOAT_TICK, 0, [&](uint32_t leaf, uint64_t, SbNetFloatReply& reply) {
    switch (leaf) {
    case SB_NET_FLOAT_HAS_POINTS:
      if (m_interpolationDataPoints) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_FLOAT_DECREMENT_SCOPE: {
      auto& points = *m_interpolationDataPoints;
      auto begin = points.begin();
      auto end = points.end();
      NetGroupDetail::run(SB_NET_FLOAT_DECREMENT, 0, [&](uint32_t item, uint64_t, SbNetFloatReply& result) {
        switch (item) {
        case SB_NET_FLOAT_MORE:
          if (begin != end) result.a = 1; else result.a = 0;
          break;
        case SB_NET_FLOAT_ADVANCE: ++begin; break;
        case SB_NET_FLOAT_DECREMENT_CURRENT: {
          auto& p = *begin;
          p.first -= dt;
          break;
        }
        default: throw std::logic_error("Invalid floating field decrement leaf");
        }
      }, sb_net_float_run);
      break;
    }
    case SB_NET_FLOAT_PRUNE_READY:
      reply.a = m_interpolationDataPoints->size() > 2 && (*m_interpolationDataPoints)[1].first <= 0.0f;
      break;
    case SB_NET_FLOAT_REMOVE_FIRST: m_interpolationDataPoints->removeFirst(); break;
    case SB_NET_FLOAT_ASSIGN_INTERPOLATED: m_value = interpolate(); break;
    default: throw std::logic_error("Invalid floating field tick leaf");
    }
  }, sb_net_float_run);
#else
  if (m_interpolationDataPoints) {
    for (auto& p : *m_interpolationDataPoints)
      p.first -= dt;

    while (m_interpolationDataPoints->size() > 2 && (*m_interpolationDataPoints)[1].first <= 0.0f)
      m_interpolationDataPoints->removeFirst();

    m_value = interpolate();
  }
#endif
}

template <typename T>
void NetElementFloating<T>::netStore(DataStream& ds, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_FIELD
  NetGroupDetail::run(SB_NET_FLOAT_STORE, 0, [&](uint32_t leaf, uint64_t, SbNetFloatReply& reply) {
    switch (leaf) {
    case SB_NET_FLOAT_HAS_POINTS:
      if (m_interpolationDataPoints) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_FLOAT_WRITE_LAST: writeValue(ds, m_interpolationDataPoints->last().second); break;
    case SB_NET_FLOAT_WRITE_CURRENT: writeValue(ds, m_value); break;
    default: throw std::logic_error("Invalid floating field store leaf");
    }
  }, sb_net_float_run);
#else
  if (m_interpolationDataPoints)
    writeValue(ds, m_interpolationDataPoints->last().second);
  else
    writeValue(ds, m_value);
#endif
}

template <typename T>
void NetElementFloating<T>::netLoad(DataStream& ds, NetCompatibilityRules rules) {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_FIELD
  NetGroupDetail::run(SB_NET_FLOAT_LOAD, 0, [&](uint32_t leaf, uint64_t, SbNetFloatReply& reply) {
    switch (leaf) {
    case SB_NET_FLOAT_ASSIGN_READ: m_value = readValue(ds); break;
    case SB_NET_FLOAT_CAPTURE_VERSION: m_latestUpdateVersion = m_netVersion ? m_netVersion->current() : 0; break;
    case SB_NET_FLOAT_HAS_POINTS:
      if (m_interpolationDataPoints) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_FLOAT_CLEAR_POINTS: m_interpolationDataPoints->clear(); break;
    case SB_NET_FLOAT_APPEND_ZERO: m_interpolationDataPoints->append({0.0f, m_value}); break;
    default: throw std::logic_error("Invalid floating field load leaf");
    }
  }, sb_net_float_run);
#else
  m_value = readValue(ds);
  m_latestUpdateVersion = m_netVersion ? m_netVersion->current() : 0;
  if (m_interpolationDataPoints) {
    m_interpolationDataPoints->clear();
    m_interpolationDataPoints->append({0.0f, m_value});
  }
#endif
}

template <typename T>
bool NetElementFloating<T>::writeNetDelta(DataStream& ds, uint64_t fromVersion, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return false;
#ifdef STAR_USE_RUST_NET_FIELD
  return NetGroupDetail::run(SB_NET_FLOAT_WRITE, fromVersion,
      [&](uint32_t leaf, uint64_t, SbNetFloatReply& reply) {
    switch (leaf) {
    case SB_NET_FLOAT_LATEST_VERSION: reply.a = m_latestUpdateVersion; break;
    case SB_NET_FLOAT_HAS_POINTS:
      if (m_interpolationDataPoints) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_FLOAT_WRITE_LAST: writeValue(ds, m_interpolationDataPoints->last().second); break;
    case SB_NET_FLOAT_WRITE_CURRENT: writeValue(ds, m_value); break;
    default: throw std::logic_error("Invalid floating field write leaf");
    }
  }, sb_net_float_run);
#else
  if (m_latestUpdateVersion < fromVersion)
    return false;

  if (m_interpolationDataPoints)
    writeValue(ds, m_interpolationDataPoints->last().second);
  else
    writeValue(ds, m_value);

  return true;
#endif
}

template <typename T>
void NetElementFloating<T>::readNetDelta(DataStream& ds, float interpolationTime, NetCompatibilityRules rules) {
  _unused(rules);
  T t = readValue(ds);

#ifdef STAR_USE_RUST_NET_FIELD
  NetGroupDetail::run(SB_NET_FLOAT_READ, 0, [&](uint32_t leaf, uint64_t, SbNetFloatReply& reply) {
    switch (leaf) {
    case SB_NET_FLOAT_CAPTURE_VERSION: m_latestUpdateVersion = m_netVersion ? m_netVersion->current() : 0; break;
    case SB_NET_FLOAT_HAS_POINTS:
      if (m_interpolationDataPoints) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_FLOAT_INPUT_EARLIER: reply.a = interpolationTime < m_interpolationDataPoints->last().first; break;
    case SB_NET_FLOAT_CLEAR_POINTS: m_interpolationDataPoints->clear(); break;
    case SB_NET_FLOAT_APPEND_INPUT: m_interpolationDataPoints->append({interpolationTime, t}); break;
    case SB_NET_FLOAT_ASSIGN_INTERPOLATED: m_value = interpolate(); break;
    case SB_NET_FLOAT_ASSIGN_INPUT: m_value = t; break;
    default: throw std::logic_error("Invalid floating field read leaf");
    }
  }, sb_net_float_run);
#else
  m_latestUpdateVersion = m_netVersion ? m_netVersion->current() : 0;
  if (m_interpolationDataPoints) {
    if (interpolationTime < m_interpolationDataPoints->last().first)
      m_interpolationDataPoints->clear();
    m_interpolationDataPoints->append({interpolationTime, t});
    m_value = interpolate();
  } else {
    m_value = t;
  }
#endif
}

template <typename T>
void NetElementFloating<T>::blankNetDelta(float interpolationTime) {
#ifdef STAR_USE_RUST_NET_FIELD
  NetGroupDetail::run(SB_NET_FLOAT_BLANK, 0, [&](uint32_t leaf, uint64_t, SbNetFloatReply& reply) {
    switch (leaf) {
    case SB_NET_FLOAT_HAS_POINTS:
      if (m_interpolationDataPoints) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_FLOAT_SCOPED_BLANK: {
      auto lastPoint = m_interpolationDataPoints->last();
      float lastTime = lastPoint.first;
      lastPoint.first = interpolationTime;
      NetGroupDetail::run(SB_NET_FLOAT_BLANK_ITEM, 0, [&](uint32_t item, uint64_t, SbNetFloatReply& result) {
        switch (item) {
        case SB_NET_FLOAT_SAVED_EARLIER: result.a = interpolationTime < lastTime; break;
        case SB_NET_FLOAT_REPLACE_LAST_POINT: *m_interpolationDataPoints = {lastPoint}; break;
        case SB_NET_FLOAT_APPEND_LAST_POINT: m_interpolationDataPoints->append(lastPoint); break;
        case SB_NET_FLOAT_ASSIGN_INTERPOLATED: m_value = interpolate(); break;
        default: throw std::logic_error("Invalid floating field blank item leaf");
        }
      }, sb_net_float_run);
      break;
    }
    default: throw std::logic_error("Invalid floating field blank leaf");
    }
  }, sb_net_float_run);
#else
  if (m_interpolationDataPoints) {
    auto lastPoint = m_interpolationDataPoints->last();
    float lastTime = lastPoint.first;
    lastPoint.first = interpolationTime;
    if (interpolationTime < lastTime)
      *m_interpolationDataPoints = {lastPoint};
    else
      m_interpolationDataPoints->append(lastPoint);

    m_value = interpolate();
  }
#endif
}

template <typename T>
void NetElementFloating<T>::writeValue(DataStream& ds, T t) const {
  if (m_fixedPointBase)
    ds.writeVlqI(round(t / *m_fixedPointBase));
  else
    ds.write(t);
}

template <typename T>
T NetElementFloating<T>::readValue(DataStream& ds) const {
  T t;
  if (m_fixedPointBase)
    t = ds.readVlqI() * *m_fixedPointBase;
  else
    ds.read(t);
  return t;
}

template <typename T>
T NetElementFloating<T>::interpolate() const {
  auto& dataPoints = *m_interpolationDataPoints;

  float ipos = inverseLinearInterpolateUpper(dataPoints.begin(), dataPoints.end(), 0.0f,
      [](float lhs, auto const& rhs) {
        return lhs < rhs.first;
      }, [](auto const& dataPoint) {
        return dataPoint.first;
      });
  auto bound = getBound2(ipos, dataPoints.size(), BoundMode::Extrapolate);

  if (m_interpolator) {
    auto const& minPoint = dataPoints[bound.i0];
    auto const& maxPoint = dataPoints[bound.i1];

    // If step separation is less than 1.0, don't normalize extrapolation to
    // the very small step difference, because this can result in large jumps
    // during jitter.
    float stepDist = max(maxPoint.first - minPoint.first, 1.0f);
    float offset = clamp<float>(bound.offset, 0.0f, 1.0f + m_extrapolation / stepDist);
    return m_interpolator(offset, minPoint.second, maxPoint.second);

  } else {
    if (bound.offset < 1.0f)
      return dataPoints[bound.i0].second;
    else
      return dataPoints[bound.i1].second;
  }
}

}
