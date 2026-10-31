#pragma once

#include "StarNetElement.hpp"
#include "StarIdMap.hpp"
#include "StarStrongTypedef.hpp"
#include "StarDataStreamExtra.hpp"
#ifdef STAR_USE_RUST_NET_DYNAMIC
#include "StarNetDynamicHost.hpp"
#endif

namespace Star {

// A dynamic group of NetElements that manages creation and destruction of
// individual elements, that is itself a NetElement.  Element changes are not
// delayed by the interpolation delay, they will always happen immediately, but
// this does not inhibit the Elements themselves from handling their own delta
// update delays normally.
template <typename Element>
class NetElementDynamicGroup : public NetElement {
public:
  typedef shared_ptr<Element> ElementPtr;
  typedef uint32_t ElementId;
  static ElementId const NullElementId = 0;

  NetElementDynamicGroup() = default;

  NetElementDynamicGroup(NetElementDynamicGroup const&) = delete;
  NetElementDynamicGroup& operator=(NetElementDynamicGroup const&) = delete;

  // Must not call addNetElement / removeNetElement when being used as a slave,
  // id errors will result.
  ElementId addNetElement(ElementPtr element);
  void removeNetElement(ElementId id);

  // Remove all elements
  void clearNetElements();

  List<ElementId> netElementIds() const;
  ElementPtr getNetElement(ElementId id) const;

  List<ElementPtr> netElements() const;

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
  // If a delta is written from further back than this many versions, the delta
  // will fall back to a full serialization of the entire state.
  static int64_t const MaxChangeDataVersions = 100;

  typedef ElementId ElementRemovalType;
  typedef pair<ElementId, ByteArray> ElementAdditionType;

  strong_typedef(Empty, ElementReset);
  strong_typedef_builtin(ElementRemovalType, ElementRemoval);
  strong_typedef(ElementAdditionType, ElementAddition);

  typedef Variant<ElementReset, ElementRemoval, ElementAddition> ElementChange;

  typedef IdMap<ElementId, ElementPtr> ElementMap;

  void addChangeData(ElementChange change);

  void readyElement(ElementPtr const& element);

  NetElementVersion const* m_netVersion = nullptr;
  bool m_interpolationEnabled = false;
  float m_extrapolationHint = 0.0f;

  ElementMap m_idMap = ElementMap(1, highest<ElementId>());

  Deque<pair<uint64_t, ElementChange>> m_changeData;
  uint64_t m_changeDataLastVersion = 0;

  mutable DataStreamBuffer m_buffer;
  mutable HashSet<ElementId> m_receivedDeltaIds;
};

template <typename Element>
auto NetElementDynamicGroup<Element>::addNetElement(ElementPtr element) -> ElementId {
#ifdef STAR_USE_RUST_NET_DYNAMIC
  ElementId id = NullElementId;
  NetDynamicDetail::run(SB_NET_DYNAMIC_ADD, [&](uint32_t leaf, uint64_t, SbNetDynamicReply&) {
    switch (leaf) {
    case SB_NET_DYNAMIC_READY_NEW: readyElement(element); break;
    case SB_NET_DYNAMIC_ADD_NEW: id = m_idMap.add(std::move(element)); break;
    case SB_NET_DYNAMIC_RECORD_ADD: addChangeData(ElementAddition(id, {})); break;
    default: throw std::logic_error("Invalid dynamic-group add leaf");
    }
  });
#else
  readyElement(element);
  auto id = m_idMap.add(std::move(element));

  addChangeData(ElementAddition(id, {})); // we will write the data stream once we know the rules for the one recieving
#endif

  return id;
}

template <typename Element>
void NetElementDynamicGroup<Element>::removeNetElement(ElementId id) {
#ifdef STAR_USE_RUST_NET_DYNAMIC
  NetDynamicDetail::run(SB_NET_DYNAMIC_REMOVE, [&](uint32_t leaf, uint64_t, SbNetDynamicReply&) {
    switch (leaf) {
    case SB_NET_DYNAMIC_REMOVE_ID: m_idMap.remove(id); break;
    case SB_NET_DYNAMIC_RECORD_REMOVE: addChangeData(ElementRemoval{id}); break;
    default: throw std::logic_error("Invalid dynamic-group remove leaf");
    }
  });
#else
  m_idMap.remove(id);
  addChangeData(ElementRemoval{id});
#endif
}

template <typename Element>
void NetElementDynamicGroup<Element>::clearNetElements() {
#ifdef STAR_USE_RUST_NET_DYNAMIC
  // Keep the original range-for-owned id snapshot, not live IdMap iterators.
  auto&& ids = netElementIds();
  auto begin = ids.begin();
  auto end = ids.end();
  NetDynamicDetail::run(SB_NET_DYNAMIC_CLEAR, [&](uint32_t leaf, uint64_t, SbNetDynamicReply& reply) {
    switch (leaf) {
    case SB_NET_DYNAMIC_MORE: reply.a = begin != end; break;
    case SB_NET_DYNAMIC_REMOVE_CURRENT_ID: removeNetElement(*begin); break;
    case SB_NET_DYNAMIC_ADVANCE: ++begin; break;
    default: throw std::logic_error("Invalid dynamic-group clear leaf");
    }
  });
#else
  for (auto const& id : netElementIds())
    removeNetElement(id);
#endif
}

template <typename Element>
auto NetElementDynamicGroup<Element>::netElementIds() const -> List<ElementId> {
  return m_idMap.keys();
}

template <typename Element>
auto NetElementDynamicGroup<Element>::getNetElement(ElementId id) const -> ElementPtr {
  return m_idMap.get(id);
}

template <typename Element>
auto NetElementDynamicGroup<Element>::netElements() const -> List<ElementPtr> {
  return m_idMap.values();
}

template <typename Element>
void NetElementDynamicGroup<Element>::initNetVersion(NetElementVersion const* version) {
  m_netVersion = version;
  m_changeData.clear();
  m_changeDataLastVersion = 0;

#ifdef STAR_USE_RUST_NET_DYNAMIC
  NetDynamicDetail::withRange(SB_NET_DYNAMIC_INIT, m_idMap,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetDynamicReply&) {
    switch (leaf) {
    case SB_NET_DYNAMIC_RECORD_RESET: addChangeData(ElementReset()); break;
    case SB_NET_DYNAMIC_INIT_CURRENT: current().second->initNetVersion(m_netVersion); break;
    case SB_NET_DYNAMIC_RECORD_CURRENT_ADD: addChangeData(ElementAddition(current().first, {})); break;
    default: throw std::logic_error("Invalid dynamic-group init leaf");
    }
  });
#else
  addChangeData(ElementReset());
  for (auto& pair : m_idMap) {
    pair.second->initNetVersion(m_netVersion);
    addChangeData(ElementAddition(pair.first, {})); // we will write the data stream once we know the rules for the one recieving
  }
#endif
}

template <typename Element>
void NetElementDynamicGroup<Element>::enableNetInterpolation(float extrapolationHint) {
  m_interpolationEnabled = true;
  m_extrapolationHint = extrapolationHint;
#ifdef STAR_USE_RUST_NET_DYNAMIC
  NetDynamicDetail::withRange(SB_NET_DYNAMIC_ENABLE, m_idMap,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetDynamicReply&) {
    if (leaf != SB_NET_DYNAMIC_ENABLE_CURRENT) throw std::logic_error("Invalid dynamic-group enable leaf");
    current().second->enableNetInterpolation(extrapolationHint);
  });
#else
  for (auto& p : m_idMap)
    p.second->enableNetInterpolation(extrapolationHint);
#endif
}

template <typename Element>
void NetElementDynamicGroup<Element>::disableNetInterpolation() {
  m_interpolationEnabled = false;
  m_extrapolationHint = 0.0f;
#ifdef STAR_USE_RUST_NET_DYNAMIC
  NetDynamicDetail::withRange(SB_NET_DYNAMIC_DISABLE, m_idMap,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetDynamicReply&) {
    if (leaf != SB_NET_DYNAMIC_DISABLE_CURRENT) throw std::logic_error("Invalid dynamic-group disable leaf");
    current().second->disableNetInterpolation();
  });
#else
  for (auto& p : m_idMap)
    p.second->disableNetInterpolation();
#endif
}

template <typename Element>
void NetElementDynamicGroup<Element>::tickNetInterpolation(float dt) {
#ifdef STAR_USE_RUST_NET_DYNAMIC
  NetDynamicDetail::withRange(SB_NET_DYNAMIC_TICK, m_idMap,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetDynamicReply&) {
    if (leaf != SB_NET_DYNAMIC_TICK_CURRENT) throw std::logic_error("Invalid dynamic-group tick leaf");
    current().second->tickNetInterpolation(dt);
  });
#else
  for (auto& p : m_idMap)
    p.second->tickNetInterpolation(dt);
#endif
}

template <typename Element>
void NetElementDynamicGroup<Element>::netStore(DataStream& ds, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_DYNAMIC
  NetDynamicDetail::withRange(SB_NET_DYNAMIC_STORE, m_idMap,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetDynamicReply& reply) {
    (void)reply;
    switch (leaf) {
    case SB_NET_DYNAMIC_WRITE_STORE_SIZE: ds.writeVlqU(m_idMap.size()); break;
    case SB_NET_DYNAMIC_SET_BUFFER_RULES: m_buffer.setStreamCompatibilityVersion(rules); break;
    case SB_NET_DYNAMIC_WRITE_CURRENT_ID: ds.writeVlqU(current().first); break;
    case SB_NET_DYNAMIC_STORE_CURRENT_BUFFER: current().second->netStore(m_buffer, rules); break;
    case SB_NET_DYNAMIC_WRITE_BUFFER_TYPED: ds.write(m_buffer.data()); break;
    case SB_NET_DYNAMIC_CLEAR_BUFFER: m_buffer.clear(); break;
    default: throw std::logic_error("Invalid dynamic-group store leaf");
    }
  });
#else
  ds.writeVlqU(m_idMap.size());

  m_buffer.setStreamCompatibilityVersion(rules);
  for (auto& pair : m_idMap) {
    ds.writeVlqU(pair.first);
    pair.second->netStore(m_buffer, rules);
    ds.write(m_buffer.data());
    m_buffer.clear();
  }
#endif
}

template <typename Element>
void NetElementDynamicGroup<Element>::netLoad(DataStream& ds, NetCompatibilityRules rules) {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_DYNAMIC
  NetDynamicDetail::run(SB_NET_DYNAMIC_LOAD, [&](uint32_t leaf, uint64_t, SbNetDynamicReply& reply) {
    switch (leaf) {
    case SB_NET_DYNAMIC_CLEAR_HISTORY: m_changeData.clear(); break;
    case SB_NET_DYNAMIC_CAPTURE_LAST_VERSION: m_changeDataLastVersion = m_netVersion ? m_netVersion->current() : 0; break;
    case SB_NET_DYNAMIC_CLEAR_IDMAP: m_idMap.clear(); break;
    case SB_NET_DYNAMIC_RECORD_RESET: addChangeData(ElementReset()); break;
    case SB_NET_DYNAMIC_READ_LOAD_COUNT: reply.a = ds.readVlqU(); break;
    case SB_NET_DYNAMIC_LOAD_ITEM_OP: {
      ElementId id = ds.readVlqU();
      DataStreamBuffer storeBuffer(ds.read<ByteArray>());
      ElementPtr element = make_shared<Element>();
      NetDynamicDetail::run(SB_NET_DYNAMIC_LOAD_ITEM, [&](uint32_t item, uint64_t, SbNetDynamicReply&) {
        switch (item) {
        case SB_NET_DYNAMIC_CHILD_LOAD: element->netLoad(storeBuffer, rules); break;
        case SB_NET_DYNAMIC_READY_LOADED: readyElement(element); break;
        case SB_NET_DYNAMIC_ADD_LOADED: m_idMap.add(id, std::move(element)); break;
        case SB_NET_DYNAMIC_RECORD_LOADED: addChangeData(ElementAddition(id, storeBuffer.takeData())); break;
        default: throw std::logic_error("Invalid dynamic-group load item leaf");
        }
      });
      break;
    }
    default: throw std::logic_error("Invalid dynamic-group load leaf");
    }
  });
#else
  m_changeData.clear();
  m_changeDataLastVersion = m_netVersion ? m_netVersion->current() : 0;
  m_idMap.clear();

  addChangeData(ElementReset());

  uint64_t count = ds.readVlqU();

  for (uint64_t i = 0; i < count; ++i) {
    ElementId id = ds.readVlqU();
    DataStreamBuffer storeBuffer(ds.read<ByteArray>());

    ElementPtr element = make_shared<Element>();
    element->netLoad(storeBuffer, rules);
    readyElement(element);

    m_idMap.add(id, std::move(element));
    addChangeData(ElementAddition(id, storeBuffer.takeData()));
  }
#endif
}

template <typename Element>
bool NetElementDynamicGroup<Element>::writeNetDelta(DataStream& ds, uint64_t fromVersion, NetCompatibilityRules rules) const {
  if (!checkWithRules(rules)) return false;
#ifdef STAR_USE_RUST_NET_DYNAMIC
  using HistoryIterator = decltype(m_changeData.begin());
  using MapIterator = decltype(m_idMap.begin());
  std::optional<std::pair<HistoryIterator, HistoryIterator>> history;
  std::optional<std::pair<MapIterator, MapIterator>> members;
  bool readingHistory = false;
  return NetDynamicDetail::evaluate(SB_NET_DYNAMIC_WRITE, fromVersion,
      [&](uint32_t leaf, uint64_t argument, SbNetDynamicReply& reply) {
    switch (leaf) {
    case SB_NET_DYNAMIC_HISTORY_FLOOR: reply.a = m_changeDataLastVersion; break;
    case SB_NET_DYNAMIC_WRITE_FULL_MARKER: ds.write<bool>(true); break;
    case SB_NET_DYNAMIC_STORE_FULL: netStore(ds, rules); break;
    case SB_NET_DYNAMIC_ENTER_CHANGE_RANGE:
      history.emplace(m_changeData.begin(), m_changeData.end()); readingHistory = true; break;
    case SB_NET_DYNAMIC_ENTER_RANGE:
      members.emplace(m_idMap.begin(), m_idMap.end()); readingHistory = false; break;
    case SB_NET_DYNAMIC_MORE:
      reply.a = readingHistory ? history->first != history->second : members->first != members->second;
      break;
    case SB_NET_DYNAMIC_ADVANCE:
      if (readingHistory) ++history->first; else ++members->first;
      break;
    case SB_NET_DYNAMIC_LEAVE_RANGE:
      if (readingHistory) history.reset(); else members.reset();
      break;
    case SB_NET_DYNAMIC_CHANGE_VERSION: reply.a = history->first->first; break;
    case SB_NET_DYNAMIC_WRITE_CHANGE_OP: {
      auto const& p = *history->first;
      ElementAddition const* addition = nullptr;
      shared_ptr<Element> const* element = nullptr;
      ElementId id = NullElementId;
      reply.a = NetDynamicDetail::evaluate(SB_NET_DYNAMIC_WRITE_CHANGE, argument,
          [&](uint32_t item, uint64_t, SbNetDynamicReply& result) {
        switch (item) {
        case SB_NET_DYNAMIC_QUERY_ADDITION:
          addition = p.second.template ptr<ElementAddition>();
          result.a = addition != nullptr;
          if (addition) id = addition->first;
          break;
        case SB_NET_DYNAMIC_FIND_ADDITION: element = m_idMap.ptr(id); result.a = element != nullptr; break;
        case SB_NET_DYNAMIC_WRITE_DELTA_MARKER: ds.write<bool>(false); break;
        case SB_NET_DYNAMIC_CHANGE_CODE: ds.writeVlqU(1); break;
        case SB_NET_DYNAMIC_STORE_ADDITION: {
          // This local buffer deliberately keeps the native default stream version.
          DataStreamBuffer storeBuffer;
          element->get()->netStore(storeBuffer, rules);
          ds.write((ElementChange)ElementAddition(id, storeBuffer.takeData()));
          break;
        }
        case SB_NET_DYNAMIC_WRITE_CURRENT_CHANGE: ds.write(p.second); break;
        default: throw std::logic_error("Invalid dynamic-group write change leaf");
        }
      });
      break;
    }
    case SB_NET_DYNAMIC_SET_BUFFER_RULES: m_buffer.setStreamCompatibilityVersion(rules); break;
    case SB_NET_DYNAMIC_WRITE_MEMBER:
      reply.a = members->first->second->writeNetDelta(m_buffer, fromVersion, rules); break;
    case SB_NET_DYNAMIC_WRITE_DELTA_MARKER: ds.write<bool>(false); break;
    // Keep the native u32 wrap: MAX id emits the same zero code as a terminator.
    case SB_NET_DYNAMIC_WRITE_MEMBER_CODE: ds.writeVlqU(members->first->first + 1); break;
    case SB_NET_DYNAMIC_WRITE_BUFFER_RAW: ds.writeBytes(m_buffer.data()); break;
    case SB_NET_DYNAMIC_CLEAR_BUFFER: m_buffer.clear(); break;
    case SB_NET_DYNAMIC_WRITE_TERMINATOR: ds.writeVlqU(0); break;
    default: throw std::logic_error("Invalid dynamic-group write leaf");
    }
  });
#else
  if (fromVersion < m_changeDataLastVersion) {
    ds.write<bool>(true);
    netStore(ds, rules);
    return true;

  } else {
    bool deltaWritten = false;
    auto willWrite = [&]() {
      if (!deltaWritten) {
        deltaWritten = true;
        ds.write<bool>(false);
      }
    };

    for (auto const& p : m_changeData) {
      if (p.first >= fromVersion) {
        if (ElementAddition const* elementAddition = p.second.template ptr<ElementAddition>()) {
          ElementId id = elementAddition->first;
          if (shared_ptr<Element> const* element = m_idMap.ptr(id)) {
            willWrite();
            ds.writeVlqU(1);
            DataStreamBuffer storeBuffer;
            element->get()->netStore(storeBuffer, rules);
            ds.write((ElementChange)ElementAddition(id, storeBuffer.takeData()));
          }
        } else {
          willWrite();
          ds.writeVlqU(1);
          ds.write(p.second);
        }
      }
    }

    m_buffer.setStreamCompatibilityVersion(rules);
    for (auto& p : m_idMap) {
      if (p.second->writeNetDelta(m_buffer, fromVersion, rules)) {
        willWrite();
        ds.writeVlqU(p.first + 1);
        ds.writeBytes(m_buffer.data());
        m_buffer.clear();
      }
    }

    if (deltaWritten)
      ds.writeVlqU(0);

    return deltaWritten;
  }
#endif
}

template <typename Element>
void NetElementDynamicGroup<Element>::readNetDelta(DataStream& ds, float interpolationTime, NetCompatibilityRules rules) {
  if (!checkWithRules(rules)) return;
#ifdef STAR_USE_RUST_NET_DYNAMIC
  NetDynamicDetail::withRange(SB_NET_DYNAMIC_READ, m_idMap,
      [&](uint32_t leaf, uint64_t argument, auto& current, SbNetDynamicReply& reply) {
    switch (leaf) {
    case SB_NET_DYNAMIC_READ_IS_FULL: reply.a = ds.read<bool>(); break;
    case SB_NET_DYNAMIC_LOAD_FULL: netLoad(ds, rules); break;
    case SB_NET_DYNAMIC_READ_CODE: reply.a = ds.readVlqU(); break;
    case SB_NET_DYNAMIC_READ_CHANGE_OP: {
      auto changeUpdate = ds.read<ElementChange>();
      ElementAddition* addition = nullptr;
      ElementRemoval* removal = nullptr;
      NetDynamicDetail::run(SB_NET_DYNAMIC_READ_CHANGE, [&](uint32_t item, uint64_t, SbNetDynamicReply& result) {
        switch (item) {
        case SB_NET_DYNAMIC_RECORD_INCOMING: addChangeData(changeUpdate); break;
        case SB_NET_DYNAMIC_CHANGE_KIND:
          if (changeUpdate.template is<ElementReset>()) result.a = 0;
          else if ((addition = changeUpdate.template ptr<ElementAddition>())) result.a = 1;
          else if ((removal = changeUpdate.template ptr<ElementRemoval>())) result.a = 2;
          else result.a = 3;
          break;
        case SB_NET_DYNAMIC_CLEAR_IDMAP: m_idMap.clear(); break;
        case SB_NET_DYNAMIC_REMOVE_INCOMING: m_idMap.remove(*removal); break;
        case SB_NET_DYNAMIC_READ_ADDITION_OP: {
          // Unlike full load, native delta-add constructs the element BEFORE its buffer.
          ElementPtr element = make_shared<Element>();
          DataStreamBuffer storeBuffer(std::move(get<1>(*addition)));
          NetDynamicDetail::run(SB_NET_DYNAMIC_READ_ADDITION, [&](uint32_t part, uint64_t, SbNetDynamicReply&) {
            switch (part) {
            case SB_NET_DYNAMIC_CHILD_LOAD: element->netLoad(storeBuffer, rules); break;
            case SB_NET_DYNAMIC_READY_LOADED: readyElement(element); break;
            case SB_NET_DYNAMIC_ADD_LOADED: m_idMap.add(get<0>(*addition), std::move(element)); break;
            default: throw std::logic_error("Invalid dynamic-group read addition leaf");
            }
          });
          break;
        }
        default: throw std::logic_error("Invalid dynamic-group incoming change leaf");
        }
      });
      break;
    }
    case SB_NET_DYNAMIC_READ_MEMBER_OP: {
      ElementId elementId = argument - 1;
      auto const& element = m_idMap.get(elementId);
      NetDynamicDetail::run(SB_NET_DYNAMIC_READ_MEMBER, [&](uint32_t item, uint64_t, SbNetDynamicReply& result) {
        switch (item) {
        case SB_NET_DYNAMIC_CHILD_READ: element->readNetDelta(ds, interpolationTime, rules); break;
        case SB_NET_DYNAMIC_GROUP_ENABLED: result.a = m_interpolationEnabled; break;
        case SB_NET_DYNAMIC_MARK_RECEIVED: m_receivedDeltaIds.add(elementId); break;
        default: throw std::logic_error("Invalid dynamic-group read member leaf");
        }
      });
      break;
    }
    case SB_NET_DYNAMIC_GROUP_ENABLED: reply.a = m_interpolationEnabled; break;
    case SB_NET_DYNAMIC_HAS_RECEIVED: reply.a = m_receivedDeltaIds.contains(current().first); break;
    case SB_NET_DYNAMIC_BLANK_CURRENT: current().second->blankNetDelta(interpolationTime); break;
    case SB_NET_DYNAMIC_CLEAR_RECEIVED: m_receivedDeltaIds.clear(); break;
    default: throw std::logic_error("Invalid dynamic-group read leaf");
    }
  });
#else
  bool isFull = ds.read<bool>();
  if (isFull) {
    netLoad(ds, rules);
  } else {
    while (true) {
      uint64_t code = ds.readVlqU();
      if (code == 0) {
        break;
      }
      if (code == 1) {
        auto changeUpdate = ds.read<ElementChange>();
        addChangeData(changeUpdate);

        if (changeUpdate.template is<ElementReset>()) {
          m_idMap.clear();
        } else if (auto addition = changeUpdate.template ptr<ElementAddition>()) {
          ElementPtr element = make_shared<Element>();
          DataStreamBuffer storeBuffer(std::move(get<1>(*addition)));
          element->netLoad(storeBuffer, rules);
          readyElement(element);
          m_idMap.add(get<0>(*addition), std::move(element));
        } else if (auto removal = changeUpdate.template ptr<ElementRemoval>()) {
          m_idMap.remove(*removal);
        }
      } else {
        ElementId elementId = code - 1;
        auto const& element = m_idMap.get(elementId);
        element->readNetDelta(ds, interpolationTime, rules);
        if (m_interpolationEnabled)
          m_receivedDeltaIds.add(elementId);
      }
    }

    if (m_interpolationEnabled) {
      for (auto& p : m_idMap) {
        if (!m_receivedDeltaIds.contains(p.first))
          p.second->blankNetDelta(interpolationTime);
      }

      m_receivedDeltaIds.clear();
    }
  }
#endif
}

template <typename Element>
void NetElementDynamicGroup<Element>::blankNetDelta(float interpolationTime) {
#ifdef STAR_USE_RUST_NET_DYNAMIC
  NetDynamicDetail::withRange(SB_NET_DYNAMIC_BLANK, m_idMap,
      [&](uint32_t leaf, uint64_t, auto& current, SbNetDynamicReply& reply) {
    switch (leaf) {
    case SB_NET_DYNAMIC_GROUP_ENABLED: reply.a = m_interpolationEnabled; break;
    case SB_NET_DYNAMIC_BLANK_CURRENT: current().second->blankNetDelta(interpolationTime); break;
    default: throw std::logic_error("Invalid dynamic-group blank leaf");
    }
  });
#else
  if (m_interpolationEnabled) {
    for (auto& p : m_idMap)
      p.second->blankNetDelta(interpolationTime);
  }
#endif
}

template <typename Element>
void NetElementDynamicGroup<Element>::addChangeData(ElementChange change) {
  uint64_t currentVersion = m_netVersion ? m_netVersion->current() : 0;
  starAssert(m_changeData.empty() || m_changeData.last().first <= currentVersion);

#ifdef STAR_USE_RUST_NET_DYNAMIC
  NetDynamicDetail::run(SB_NET_DYNAMIC_CHANGE, [&](uint32_t leaf, uint64_t, SbNetDynamicReply& reply) {
    switch (leaf) {
    case SB_NET_DYNAMIC_APPEND_CHANGE: m_changeData.append({currentVersion, std::move(change)}); break;
    // Preserve the native signed cast/subtraction domain, not a repaired Rust floor.
    case SB_NET_DYNAMIC_SET_HISTORY_FLOOR: m_changeDataLastVersion = max<int64_t>((int64_t)currentVersion - MaxChangeDataVersions, 0); break;
    case SB_NET_DYNAMIC_HISTORY_EMPTY: reply.a = m_changeData.empty(); break;
    case SB_NET_DYNAMIC_HISTORY_BOUNDS:
      reply.a = m_changeData.first().first;
      reply.b = m_changeDataLastVersion;
      break;
    case SB_NET_DYNAMIC_POP_HISTORY: m_changeData.removeFirst(); break;
    default: throw std::logic_error("Invalid dynamic-group history leaf");
    }
  });
#else
  m_changeData.append({currentVersion, std::move(change)});

  m_changeDataLastVersion = max<int64_t>((int64_t)currentVersion - MaxChangeDataVersions, 0);
  while (!m_changeData.empty() && m_changeData.first().first < m_changeDataLastVersion)
    m_changeData.removeFirst();
#endif
}

template <typename Element>
void NetElementDynamicGroup<Element>::readyElement(ElementPtr const& element) {
#ifdef STAR_USE_RUST_NET_DYNAMIC
  NetDynamicDetail::run(SB_NET_DYNAMIC_READY, [&](uint32_t leaf, uint64_t, SbNetDynamicReply& reply) {
    switch (leaf) {
    case SB_NET_DYNAMIC_INIT_READY: element->initNetVersion(m_netVersion); break;
    case SB_NET_DYNAMIC_GROUP_ENABLED: reply.a = m_interpolationEnabled; break;
    case SB_NET_DYNAMIC_ENABLE_READY: element->enableNetInterpolation(m_extrapolationHint); break;
    case SB_NET_DYNAMIC_DISABLE_READY: element->disableNetInterpolation(); break;
    default: throw std::logic_error("Invalid dynamic-group ready leaf");
    }
  });
#else
  element->initNetVersion(m_netVersion);
  if (m_interpolationEnabled)
    element->enableNetInterpolation(m_extrapolationHint);
  else
    element->disableNetInterpolation();
#endif
}

}
