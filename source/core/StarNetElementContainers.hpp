#pragma once

#include "StarMap.hpp"
#include "StarDataStreamExtra.hpp"
#include "StarNetElement.hpp"
#include "StarStrongTypedef.hpp"
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarNetMapHost.hpp"
#endif

namespace Star {

// NetElement map container that is more efficient than the naive serialization
// of an entire Map, because it delta encodes changes to save networking
// traffic.
template <typename BaseMap>
class NetElementMapWrapper : public NetElement, private BaseMap {
public:
  typedef typename BaseMap::iterator iterator;
  typedef typename BaseMap::const_iterator const_iterator;

  typedef typename BaseMap::key_type key_type;
  typedef typename BaseMap::mapped_type mapped_type;
  typedef typename BaseMap::value_type value_type;

  void initNetVersion(NetElementVersion const* version = nullptr) override;

  void enableNetInterpolation(float extrapolationHint = 0.0f) override;
  void disableNetInterpolation() override;
  void tickNetInterpolation(float dt) override;

  void netStore(DataStream& ds, NetCompatibilityRules rules = {}) const override;
  void netLoad(DataStream& ds, NetCompatibilityRules rules) override;

  bool shouldWriteNetDelta(uint64_t fromVersion, NetCompatibilityRules rules = {}) const;
  bool writeNetDelta(DataStream& ds, uint64_t fromVersion, NetCompatibilityRules rules = {}) const override;
  void readNetDelta(DataStream& ds, float interpolationTime = 0.0f, NetCompatibilityRules rules = {}) override;

  mapped_type const& get(key_type const& key) const;
  mapped_type const* ptr(key_type const& key) const;

  const_iterator begin() const;
  const_iterator end() const;

  using BaseMap::keys;
  using BaseMap::values;
  using BaseMap::pairs;
  using BaseMap::contains;
  using BaseMap::size;
  using BaseMap::empty;
  using BaseMap::maybe;
  using BaseMap::value;

  pair<const_iterator, bool> insert(value_type v);
  pair<const_iterator, bool> insert(key_type k, mapped_type v);

  void add(key_type k, mapped_type v);
  // Calling set with a matching key and value does not cause a delta to be
  // produced
  void set(key_type k, mapped_type v);
  // set requires that mapped_type implement operator==, push always generates
  // a delta and does not require mapped_type operator==
  void push(key_type k, mapped_type v);

  bool remove(key_type const& k);

  const_iterator erase(const_iterator i);

  mapped_type take(key_type const& k);
  Maybe<mapped_type> maybeTake(key_type const& k);

  void clear();

  BaseMap const& baseMap() const;
  void reset(BaseMap values);
  bool pullUpdated();

  // Sets this map to contain the same keys / values as the given map.  All
  // values in this map not found in the given map are removed.  (Same as
  // reset, but with arbitrary map type).
  template <typename MapType>
  void setContents(MapType const& values);

  uint64_t changeDataLastVersion() const;

private:
  // If a delta is written from further back than this many steps, the delta
  // will fall back to a full serialization of the entire state.
  static int64_t const MaxChangeDataVersions = 100;

  struct SetChange {
    key_type key;
    mapped_type value;
  };
  struct RemoveChange {
    key_type key;
  };
  struct ClearChange {};

  typedef Variant<SetChange, RemoveChange, ClearChange> ElementChange;

  static void writeChange(DataStream& ds, ElementChange const& change);
  static ElementChange readChange(DataStream& ds);

  void addChangeData(ElementChange change);

  void addPendingChangeData(ElementChange change, float interpolationTime);
  void applyChange(ElementChange change);
#ifdef STAR_USE_RUST_NET_GROUP
  void flushPendingChanges();
#endif

  Deque<pair<uint64_t, ElementChange>> m_changeData;
  Deque<pair<float, ElementChange>> m_pendingChangeData;
  NetElementVersion const* m_netVersion = nullptr;
  uint64_t m_changeDataLastVersion = 0;
  bool m_updated = false;
  bool m_interpolationEnabled = false;
};

template <typename Key, typename Value>
using NetElementMap = NetElementMapWrapper<Map<Key, Value>>;

template <typename Key, typename Value>
using NetElementHashMap = NetElementMapWrapper<HashMap<Key, Value>>;

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::initNetVersion(NetElementVersion const* version) {
  m_netVersion = version;

  m_changeData.clear();
  m_changeDataLastVersion = 0;

#ifdef STAR_USE_RUST_NET_GROUP
  NetMapDetail::run(SB_NET_MAP_INIT, [&](uint32_t leaf, uint64_t, SbNetMapReply&) {
    switch (leaf) {
    case SB_NET_MAP_FLUSH_PENDING: flushPendingChanges(); break;
    case SB_NET_MAP_RECORD_CLEAR: addChangeData(ClearChange()); break;
    case SB_NET_MAP_RECORD_RANGE_OP:
      NetMapDetail::withRange(SB_NET_MAP_BASE_RECORD, 0, *this,
          [&](uint32_t item, uint64_t, auto& current, SbNetMapReply&) {
        if (item != SB_NET_MAP_RECORD_CURRENT_SET) throw std::logic_error("Invalid network-map record leaf");
        auto const& p = current();
        addChangeData(SetChange{p.first, p.second});
      });
      break;
    default: throw std::logic_error("Invalid network-map init leaf");
    }
  });
#else
  for (auto& change : Star::take(m_pendingChangeData))
    applyChange(std::move(change.second));

  addChangeData(ClearChange());
  for (auto const& p : *this)
    addChangeData(SetChange{p.first, p.second});
#endif
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::enableNetInterpolation(float) {
  m_interpolationEnabled = true;
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::disableNetInterpolation() {
  m_interpolationEnabled = false;
#ifdef STAR_USE_RUST_NET_GROUP
  flushPendingChanges();
#else
  for (auto& change : Star::take(m_pendingChangeData))
    applyChange(std::move(change.second));
#endif
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::tickNetInterpolation(float dt) {
#ifdef STAR_USE_RUST_NET_GROUP
  NetMapDetail::run(SB_NET_MAP_TICK, [&](uint32_t leaf, uint64_t, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_DECREMENT_RANGE_OP:
      NetMapDetail::withRange(SB_NET_MAP_DECREMENT_RANGE, 0, m_pendingChangeData,
          [&](uint32_t item, uint64_t, auto& current, SbNetMapReply&) {
        if (item != SB_NET_MAP_DECREMENT_CURRENT) throw std::logic_error("Invalid network-map decrement leaf");
        auto& p = current();
        p.first -= dt;
      });
      break;
    case SB_NET_MAP_FRONT_READY:
      reply.a = !m_pendingChangeData.empty() && m_pendingChangeData.first().first <= 0.0f;
      break;
    case SB_NET_MAP_APPLY_FRONT: applyChange(m_pendingChangeData.takeFirst().second); break;
    default: throw std::logic_error("Invalid network-map tick leaf");
    }
  });
#else
  for (auto& p : m_pendingChangeData)
    p.first -= dt;

  while (!m_pendingChangeData.empty() && m_pendingChangeData.first().first <= 0.0f)
    applyChange(m_pendingChangeData.takeFirst().second);
#endif
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::netStore(DataStream& ds, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_GROUP
  NetMapDetail::run(SB_NET_MAP_STORE, [&](uint32_t leaf, uint64_t, SbNetMapReply&) {
    switch (leaf) {
    case SB_NET_MAP_WRITE_SIZE: ds.writeVlqU(BaseMap::size() + m_pendingChangeData.size()); break;
    case SB_NET_MAP_STORE_RANGE_OP:
      NetMapDetail::withRange(SB_NET_MAP_BASE_STORE, 0, *this,
          [&](uint32_t item, uint64_t, auto& current, SbNetMapReply&) {
        if (item != SB_NET_MAP_WRITE_CURRENT_SET) throw std::logic_error("Invalid network-map store value leaf");
        auto const& pair = current();
        writeChange(ds, SetChange{pair.first, pair.second});
      });
      break;
    case SB_NET_MAP_STORE_PENDING_OP:
      NetMapDetail::withRange(SB_NET_MAP_STORE_PENDING, 0, m_pendingChangeData,
          [&](uint32_t item, uint64_t, auto& current, SbNetMapReply&) {
        if (item != SB_NET_MAP_WRITE_PENDING_CHANGE) throw std::logic_error("Invalid network-map store pending leaf");
        auto const& p = current();
        writeChange(ds, p.second);
      });
      break;
    default: throw std::logic_error("Invalid network-map store leaf");
    }
  });
#else
  ds.writeVlqU(BaseMap::size() + m_pendingChangeData.size());
  for (auto const& pair : *this)
    writeChange(ds, SetChange{pair.first, pair.second});

  for (auto const& p : m_pendingChangeData)
    writeChange(ds, p.second);
#endif
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::netLoad(DataStream& ds, NetCompatibilityRules rules) {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_GROUP
  NetMapDetail::run(SB_NET_MAP_LOAD, [&](uint32_t leaf, uint64_t, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_CLEAR_HISTORY: m_changeData.clear(); break;
    case SB_NET_MAP_CAPTURE_VERSION: m_changeDataLastVersion = m_netVersion ? m_netVersion->current() : 0; break;
    case SB_NET_MAP_CLEAR_PENDING: m_pendingChangeData.clear(); break;
    case SB_NET_MAP_CLEAR_BASE: BaseMap::clear(); break;
    case SB_NET_MAP_RECORD_CLEAR: addChangeData(ClearChange()); break;
    case SB_NET_MAP_READ_COUNT: reply.a = ds.readVlqU(); break;
    case SB_NET_MAP_LOAD_ITEM_OP: {
      auto change = readChange(ds);
      NetMapDetail::run(SB_NET_MAP_LOAD_ITEM, [&](uint32_t item, uint64_t, SbNetMapReply&) {
        switch (item) {
        case SB_NET_MAP_RECORD_ITEM: addChangeData(change); break;
        case SB_NET_MAP_APPLY_ITEM_MOVE: applyChange(std::move(change)); break;
        default: throw std::logic_error("Invalid network-map load item leaf");
        }
      });
      break;
    }
    case SB_NET_MAP_MARK_UPDATED: m_updated = true; break;
    default: throw std::logic_error("Invalid network-map load leaf");
    }
  });
#else
  m_changeData.clear();
  m_changeDataLastVersion = m_netVersion ? m_netVersion->current() : 0;
  m_pendingChangeData.clear();
  BaseMap::clear();

  addChangeData(ClearChange());

  uint64_t count = ds.readVlqU();
  for (uint64_t i = 0; i < count; ++i) {
    auto change = readChange(ds);
    addChangeData(change);
    applyChange(std::move(change));
  }

  m_updated = true;
#endif
}

template <typename BaseMap>
bool NetElementMapWrapper<BaseMap>::shouldWriteNetDelta(uint64_t fromVersion, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return false;
#ifdef STAR_USE_RUST_NET_GROUP
  return NetMapDetail::run(SB_NET_MAP_SHOULD, fromVersion,
      [&](uint32_t leaf, uint64_t argument, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_HISTORY_FLOOR: reply.a = m_changeDataLastVersion; break;
    case SB_NET_MAP_SHOULD_SCAN_OP:
      reply.a = NetMapDetail::withRange(SB_NET_MAP_SHOULD_SCAN, argument, m_changeData,
          [&](uint32_t item, uint64_t, auto& current, SbNetMapReply& result) {
        if (item != SB_NET_MAP_ENTRY_VERSION) throw std::logic_error("Invalid network-map should scan leaf");
        auto const& p = current();
        result.a = p.first;
      });
      break;
    default: throw std::logic_error("Invalid network-map should leaf");
    }
  });
#else
  if (fromVersion < m_changeDataLastVersion)
    return true;

  for (auto const& p : m_changeData)
    if (p.first >= fromVersion)
      return true;

  return false;
#endif
}

template <typename BaseMap>
bool NetElementMapWrapper<BaseMap>::writeNetDelta(DataStream& ds, uint64_t fromVersion, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return false;
#ifdef STAR_USE_RUST_NET_GROUP
  return NetMapDetail::run(SB_NET_MAP_WRITE, fromVersion,
      [&](uint32_t leaf, uint64_t argument, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_HISTORY_FLOOR: reply.a = m_changeDataLastVersion; break;
    case SB_NET_MAP_WRITE_FULL_CODE: ds.writeVlqU(1); break;
    case SB_NET_MAP_STORE_FULL: netStore(ds, rules); break;
    case SB_NET_MAP_WRITE_SCAN_OP:
      reply.a = NetMapDetail::withRange(SB_NET_MAP_WRITE_SCAN, argument, m_changeData,
          [&](uint32_t item, uint64_t, auto& current, SbNetMapReply& result) {
        switch (item) {
        case SB_NET_MAP_ENTRY_VERSION: result.a = current().first; break;
        case SB_NET_MAP_WRITE_CHANGE_CODE: ds.writeVlqU(2); break;
        case SB_NET_MAP_WRITE_HISTORY_CHANGE: {
          auto const& p = current();
          writeChange(ds, p.second);
          break;
        }
        default: throw std::logic_error("Invalid network-map write scan leaf");
        }
      });
      break;
    case SB_NET_MAP_WRITE_TERMINATOR: ds.writeVlqU(0); break;
    default: throw std::logic_error("Invalid network-map write leaf");
    }
  });
#else
  bool deltaWritten = false;

  if (fromVersion < m_changeDataLastVersion) {
    deltaWritten = true;
    ds.writeVlqU(1);
    netStore(ds, rules);

  } else {
    for (auto const& p : m_changeData) {
      if (p.first >= fromVersion) {
        deltaWritten = true;
        ds.writeVlqU(2);
        writeChange(ds, p.second);
      }
    }
  }

  if (deltaWritten)
    ds.writeVlqU(0);

  return deltaWritten;
#endif
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::readNetDelta(DataStream& ds, float interpolationTime, NetCompatibilityRules rules) {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_GROUP
  NetMapDetail::run(SB_NET_MAP_READ, [&](uint32_t leaf, uint64_t, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_READ_CODE: reply.a = ds.readVlqU(); break;
    case SB_NET_MAP_LOAD_FULL: netLoad(ds, rules); break;
    case SB_NET_MAP_READ_ITEM_OP: {
      auto change = readChange(ds);
      NetMapDetail::run(SB_NET_MAP_READ_ITEM, [&](uint32_t item, uint64_t, SbNetMapReply& result) {
        switch (item) {
        case SB_NET_MAP_RECORD_ITEM: addChangeData(change); break;
        case SB_NET_MAP_SHOULD_QUEUE: result.a = m_interpolationEnabled && interpolationTime > 0.0f; break;
        case SB_NET_MAP_QUEUE_ITEM_MOVE: addPendingChangeData(std::move(change), interpolationTime); break;
        case SB_NET_MAP_APPLY_ITEM_MOVE: applyChange(std::move(change)); break;
        default: throw std::logic_error("Invalid network-map read item leaf");
        }
      });
      break;
    }
    case SB_NET_MAP_THROW_CODE: throw IOException("Improper delta code received in NetElementMapWrapper::readNetDelta");
    default: throw std::logic_error("Invalid network-map read leaf");
    }
  });
#else
  while (true) {
    uint64_t code = ds.readVlqU();
    if (code == 0) {
      break;
    } else if (code == 1) {
      netLoad(ds, rules);
    } else if (code == 2) {
      auto change = readChange(ds);
      addChangeData(change);

      if (m_interpolationEnabled && interpolationTime > 0.0f)
        addPendingChangeData(std::move(change), interpolationTime);
      else
        applyChange(std::move(change));
    } else {
      throw IOException("Improper delta code received in NetElementMapWrapper::readNetDelta");
    }
  }
#endif
}

template <typename BaseMap>
auto NetElementMapWrapper<BaseMap>::get(key_type const& key) const -> mapped_type const & {
  return BaseMap::get(key);
}

template <typename BaseMap>
auto NetElementMapWrapper<BaseMap>::ptr(key_type const& key) const -> mapped_type const * {
  return BaseMap::ptr(key);
}

template <typename BaseMap>
auto NetElementMapWrapper<BaseMap>::begin() const -> const_iterator {
  return BaseMap::begin();
}

template <typename BaseMap>
auto NetElementMapWrapper<BaseMap>::end() const -> const_iterator {
  return BaseMap::end();
}

template <typename BaseMap>
auto NetElementMapWrapper<BaseMap>::insert(value_type v) -> pair<const_iterator, bool> {
  auto res = BaseMap::insert(v);
#ifdef STAR_USE_RUST_NET_GROUP
  NetMapDetail::run(SB_NET_MAP_INSERT, [&](uint32_t leaf, uint64_t, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_INSERTED:
      if (res.second) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_MAP_RECORD_INSERTED: addChangeData(SetChange{std::move(v.first), std::move(v.second)}); break;
    case SB_NET_MAP_MARK_UPDATED: m_updated = true; break;
    default: throw std::logic_error("Invalid network-map insert leaf");
    }
  });
#else
  if (res.second) {
    addChangeData(SetChange{std::move(v.first), std::move(v.second)});
    m_updated = true;
  }
#endif
  return res;
}

template <typename BaseMap>
auto NetElementMapWrapper<BaseMap>::insert(key_type k, mapped_type v) -> pair<const_iterator, bool> {
  return insert(value_type(std::move(k), std::move(v)));
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::add(key_type k, mapped_type v) {
#ifdef STAR_USE_RUST_NET_GROUP
  NetMapDetail::run(SB_NET_MAP_ADD, [&](uint32_t leaf, uint64_t, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_ADD_FAILED:
      if (!insert(value_type(std::move(k), std::move(v))).second) reply.a = 1;
      else reply.a = 0;
      break;
    case SB_NET_MAP_THROW_DUPLICATE: throw MapException::format("Entry with key '{}' already present.", outputAny(k));
    default: throw std::logic_error("Invalid network-map add leaf");
    }
  });
#else
  if (!insert(value_type(std::move(k), std::move(v))).second)
    throw MapException::format("Entry with key '{}' already present.", outputAny(k));
#endif
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::set(key_type k, mapped_type v) {
  auto i = BaseMap::find(k);
#ifdef STAR_USE_RUST_NET_GROUP
  NetMapDetail::run(SB_NET_MAP_SET, [&](uint32_t leaf, uint64_t, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_FOUND:
      if (i != BaseMap::end()) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_MAP_VALUE_DIFFERS:
      if (!(i->second == v)) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_MAP_RECORD_EXISTING_SET: addChangeData(SetChange{std::move(k), v}); break;
    case SB_NET_MAP_ASSIGN_EXISTING: i->second = std::move(v); break;
    case SB_NET_MAP_RECORD_NEW_SET: addChangeData(SetChange{k, v}); break;
    case SB_NET_MAP_INSERT_NEW: BaseMap::insert(value_type(std::move(k), std::move(v))); break;
    case SB_NET_MAP_MARK_UPDATED: m_updated = true; break;
    default: throw std::logic_error("Invalid network-map set leaf");
    }
  });
#else
  if (i != BaseMap::end()) {
    if (!(i->second == v)) {
      addChangeData(SetChange{std::move(k), v});
      i->second = std::move(v);
      m_updated = true;
    }
  } else {
    addChangeData(SetChange{k, v});
    BaseMap::insert(value_type(std::move(k), std::move(v)));
    m_updated = true;
  }
#endif
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::push(key_type k, mapped_type v) {
  auto i = BaseMap::find(k);
  if (i != BaseMap::end()) {
    addChangeData(SetChange(std::move(k), v));
    i->second = std::move(v);
  } else {
    addChangeData(SetChange(k, v));
    BaseMap::insert(value_type(std::move(k), std::move(v)));
  }
  m_updated = true;
}

template <typename BaseMap>
bool NetElementMapWrapper<BaseMap>::remove(key_type const& k) {
  auto i = BaseMap::find(k);
#ifdef STAR_USE_RUST_NET_GROUP
  return NetMapDetail::run(SB_NET_MAP_REMOVE, 0, [&](uint32_t leaf, uint64_t, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_FOUND:
      if (i != BaseMap::end()) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_MAP_ERASE_FOUND: BaseMap::erase(i); break;
    case SB_NET_MAP_RECORD_REMOVAL: addChangeData(RemoveChange{k}); break;
    case SB_NET_MAP_MARK_UPDATED: m_updated = true; break;
    default: throw std::logic_error("Invalid network-map remove leaf");
    }
  });
#else
  if (i != BaseMap::end()) {
    BaseMap::erase(i);
    addChangeData(RemoveChange{k});
    m_updated = true;
    return true;
  }
  return false;
#endif
}

template <typename BaseMap>
auto NetElementMapWrapper<BaseMap>::erase(const_iterator i) -> const_iterator {
  addChangeData(RemoveChange(i->first));
  m_updated = true;
  return BaseMap::erase(i);
}

template <typename BaseMap>
auto NetElementMapWrapper<BaseMap>::take(key_type const& k) -> mapped_type {
  auto i = BaseMap::find(k);
  if (i == BaseMap::end())
    throw MapException::format("Key '{}' not found in Map::take()", outputAny(k));
  auto m = std::move(i->second);
  erase(i);
  return m;
}

template <typename BaseMap>
auto NetElementMapWrapper<BaseMap>::maybeTake(key_type const& k) -> Maybe<mapped_type> {
  auto i = BaseMap::find(k);
  if (i == BaseMap::end())
    return {};
  auto m = std::move(i->second);
  erase(i);
  return Maybe<mapped_type>(std::move(m));
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::clear() {
#ifdef STAR_USE_RUST_NET_GROUP
  NetMapDetail::run(SB_NET_MAP_CLEAR, [&](uint32_t leaf, uint64_t, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_NONEMPTY:
      if (!empty()) reply.a = 1; else reply.a = 0;
      break;
    case SB_NET_MAP_RECORD_CLEAR: addChangeData(ClearChange()); break;
    case SB_NET_MAP_MARK_UPDATED: m_updated = true; break;
    case SB_NET_MAP_CLEAR_BASE: BaseMap::clear(); break;
    default: throw std::logic_error("Invalid network-map clear leaf");
    }
  });
#else
  if (!empty()) {
    addChangeData(ClearChange());
    m_updated = true;
    BaseMap::clear();
  }
#endif
}

template <typename BaseMap>
BaseMap const& NetElementMapWrapper<BaseMap>::baseMap() const {
  return *this;
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::reset(BaseMap values) {
#ifdef STAR_USE_RUST_NET_GROUP
  NetMapDetail::run(SB_NET_MAP_RESET, [&](uint32_t leaf, uint64_t, SbNetMapReply&) {
    switch (leaf) {
    case SB_NET_MAP_RESET_REMOVALS_OP:
      NetMapDetail::withRange(SB_NET_MAP_RESET_REMOVALS, 0, *this,
          [&](uint32_t item, uint64_t, auto& current, SbNetMapReply&) {
        if (item != SB_NET_MAP_RESET_REMOVE_ITEM_OP) throw std::logic_error("Invalid network-map reset removal item");
        auto const& p = current();
        NetMapDetail::run(SB_NET_MAP_RESET_REMOVE_ITEM, [&](uint32_t part, uint64_t, SbNetMapReply& reply) {
          switch (part) {
          case SB_NET_MAP_RESET_MISSING:
            if (!values.contains(p.first)) reply.a = 1; else reply.a = 0;
            break;
          case SB_NET_MAP_RECORD_CURRENT_REMOVE: addChangeData(RemoveChange{p.first}); break;
          case SB_NET_MAP_MARK_UPDATED: m_updated = true; break;
          default: throw std::logic_error("Invalid network-map reset removal leaf");
          }
        });
      });
      break;
    case SB_NET_MAP_RESET_SETS_OP:
      NetMapDetail::withRange(SB_NET_MAP_RESET_SETS, 0, values,
          [&](uint32_t item, uint64_t, auto& current, SbNetMapReply&) {
        if (item != SB_NET_MAP_RESET_SET_ITEM_OP) throw std::logic_error("Invalid network-map reset set item");
        auto const& p = current();
        auto v = ptr(p.first);
        NetMapDetail::run(SB_NET_MAP_RESET_SET_ITEM, [&](uint32_t part, uint64_t, SbNetMapReply& reply) {
          switch (part) {
          case SB_NET_MAP_RESET_CHANGED:
            if (!v || !(*v == p.second)) reply.a = 1; else reply.a = 0;
            break;
          case SB_NET_MAP_RECORD_CURRENT_SET: addChangeData(SetChange{p.first, p.second}); break;
          case SB_NET_MAP_MARK_UPDATED: m_updated = true; break;
          default: throw std::logic_error("Invalid network-map reset set leaf");
          }
        });
      });
      break;
    case SB_NET_MAP_RESET_ASSIGN: BaseMap::operator=(std::move(values)); break;
    default: throw std::logic_error("Invalid network-map reset leaf");
    }
  });
#else
  for (auto const& p : *this) {
    if (!values.contains(p.first)) {
      addChangeData(RemoveChange{p.first});
      m_updated = true;
    }
  }

  for (auto const& p : values) {
    auto v = ptr(p.first);
    if (!v || !(*v == p.second)) {
      addChangeData(SetChange{p.first, p.second});
      m_updated = true;
    }
  }

  BaseMap::operator=(std::move(values));
#endif
}

template <typename BaseMap>
bool NetElementMapWrapper<BaseMap>::pullUpdated() {
  return Star::take(m_updated);
}

template <typename BaseMap>
template <typename MapType>
void NetElementMapWrapper<BaseMap>::setContents(MapType const& values) {
  reset(BaseMap::from(values));
}

template <typename BaseMap>
uint64_t NetElementMapWrapper<BaseMap>::changeDataLastVersion() const {
  return m_changeDataLastVersion;
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::writeChange(DataStream& ds, ElementChange const& change) {
#ifdef STAR_USE_RUST_NET_GROUP
  SetChange const* sc = nullptr;
  RemoveChange const* rc = nullptr;
  NetMapDetail::run(SB_NET_MAP_WRITE_CHANGE, [&](uint32_t leaf, uint64_t argument, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_CHANGE_KIND:
      if ((sc = change.template ptr<SetChange>())) reply.a = 0;
      else if ((rc = change.template ptr<RemoveChange>())) reply.a = 1;
      else reply.a = 2;
      break;
    case SB_NET_MAP_WRITE_TAG: ds.write<uint8_t>(argument); break;
    case SB_NET_MAP_WRITE_KEY:
      if (sc) ds.write(sc->key); else ds.write(rc->key);
      break;
    case SB_NET_MAP_WRITE_VALUE: ds.write(sc->value); break;
    default: throw std::logic_error("Invalid network-map change writer leaf");
    }
  });
#else
  if (auto sc = change.template ptr<SetChange>()) {
    ds.write<uint8_t>(0);
    ds.write(sc->key);
    ds.write(sc->value);
  } else if (auto rc = change.template ptr<RemoveChange>()) {
    ds.write<uint8_t>(1);
    ds.write(rc->key);
  } else {
    ds.write<uint8_t>(2);
  }
#endif
}

template <typename BaseMap>
auto NetElementMapWrapper<BaseMap>::readChange(DataStream& ds) -> ElementChange {
  uint8_t t = ds.read<uint8_t>();
#ifdef STAR_USE_RUST_NET_GROUP
  // Rust selects the tag; typed local construction/reads/return conversion stay
  // in these native branches, with no optional<Variant> or extra value moves.
  uint32_t kind = 3;
  NetMapDetail::run(SB_NET_MAP_READ_TYPE, t, [&](uint32_t leaf, uint64_t argument, SbNetMapReply&) {
    switch (leaf) {
    case SB_NET_MAP_SELECT_KIND: kind = argument; break;
    case SB_NET_MAP_THROW_TYPE: throw IOException("Improper type code received in NetElementMapWrapper::readChange");
    default: throw std::logic_error("Invalid network-map change reader leaf");
    }
  });
  if (kind == 0) {
    SetChange sc;
    ds.read(sc.key);
    ds.read(sc.value);
    return sc;
  } else if (kind == 1) {
    RemoveChange rc;
    ds.read(rc.key);
    return rc;
  } else {
    return ClearChange();
  }
#else
  if (t == 0) {
    SetChange sc;
    ds.read(sc.key);
    ds.read(sc.value);
    return sc;
  } else if (t == 1) {
    RemoveChange rc;
    ds.read(rc.key);
    return rc;
  } else if (t == 2) {
    return ClearChange();
  } else {
    throw IOException("Improper type code received in NetElementMapWrapper::readChange");
  }
#endif
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::addChangeData(ElementChange change) {
  uint64_t currentVersion = m_netVersion ? m_netVersion->current() : 0;
  starAssert(m_changeData.empty() || m_changeData.last().first <= currentVersion);

#ifdef STAR_USE_RUST_NET_GROUP
  NetMapDetail::run(SB_NET_MAP_HISTORY, [&](uint32_t leaf, uint64_t, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_APPEND_HISTORY: m_changeData.append({currentVersion, std::move(change)}); break;
    // The original signed cast/subtraction and its unsupported domains stay native.
    case SB_NET_MAP_SET_HISTORY_FLOOR: m_changeDataLastVersion = max<int64_t>((int64_t)currentVersion - MaxChangeDataVersions, 0); break;
    case SB_NET_MAP_HISTORY_EMPTY: reply.a = m_changeData.empty(); break;
    case SB_NET_MAP_HISTORY_BOUNDS:
      reply.a = m_changeData.first().first; reply.b = m_changeDataLastVersion; break;
    case SB_NET_MAP_POP_HISTORY: m_changeData.removeFirst(); break;
    default: throw std::logic_error("Invalid network-map history leaf");
    }
  });
#else
  m_changeData.append({currentVersion, std::move(change)});

  m_changeDataLastVersion = max<int64_t>((int64_t)currentVersion - MaxChangeDataVersions, 0);
  while (!m_changeData.empty() && m_changeData.first().first < m_changeDataLastVersion)
    m_changeData.removeFirst();
#endif
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::addPendingChangeData(ElementChange change, float interpolationTime) {
#ifdef STAR_USE_RUST_NET_GROUP
  NetMapDetail::run(SB_NET_MAP_PENDING, [&](uint32_t leaf, uint64_t, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_PENDING_EARLIER:
      reply.a = !m_pendingChangeData.empty() && interpolationTime < m_pendingChangeData.last().first;
      break;
    case SB_NET_MAP_FLUSH_PENDING: flushPendingChanges(); break;
    case SB_NET_MAP_APPEND_PENDING: m_pendingChangeData.append({interpolationTime, std::move(change)}); break;
    default: throw std::logic_error("Invalid network-map pending leaf");
    }
  });
#else
  if (!m_pendingChangeData.empty() && interpolationTime < m_pendingChangeData.last().first) {
    for (auto& change : Star::take(m_pendingChangeData))
      applyChange(std::move(change.second));
  }
  m_pendingChangeData.append({interpolationTime, std::move(change)});
#endif
}

template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::applyChange(ElementChange change) {
#ifdef STAR_USE_RUST_NET_GROUP
  SetChange* set = nullptr;
  RemoveChange* remove = nullptr;
  NetMapDetail::run(SB_NET_MAP_APPLY, [&](uint32_t leaf, uint64_t, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_CHANGE_KIND:
      if ((set = change.template ptr<SetChange>())) reply.a = 0;
      else if ((remove = change.template ptr<RemoveChange>())) reply.a = 1;
      else reply.a = 2;
      break;
    case SB_NET_MAP_APPLY_SET: BaseMap::set(std::move(set->key), std::move(set->value)); break;
    case SB_NET_MAP_APPLY_REMOVE: BaseMap::remove(std::move(remove->key)); break;
    case SB_NET_MAP_CLEAR_BASE: BaseMap::clear(); break;
    case SB_NET_MAP_MARK_UPDATED: m_updated = true; break;
    default: throw std::logic_error("Invalid network-map apply leaf");
    }
  });
#else
  if (auto set = change.template ptr<SetChange>())
    BaseMap::set(std::move(set->key), std::move(set->value));
  else if (auto remove = change.template ptr<RemoveChange>())
    BaseMap::remove(std::move(remove->key));
  else
    BaseMap::clear();
  m_updated = true;
#endif
}

#ifdef STAR_USE_RUST_NET_GROUP
template <typename BaseMap>
void NetElementMapWrapper<BaseMap>::flushPendingChanges() {
  // The taken queue, not the newly reentrant member queue, owns this iteration.
  auto&& pending = Star::take(m_pendingChangeData);
  NetMapDetail::withRange(SB_NET_MAP_FLUSH, 0, pending,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetMapReply&) {
    if (leaf != SB_NET_MAP_APPLY_PENDING_MOVE) throw std::logic_error("Invalid network-map flush leaf");
    auto& change = current();
    applyChange(std::move(change.second));
  });
}
#endif
}
