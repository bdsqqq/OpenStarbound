#pragma once

#include "StarMap.hpp"
#include "StarMathCommon.hpp"
#include "StarDataStream.hpp"
#ifdef STAR_USE_RUST_ID_MAP
#include "StarIdMapHost.hpp"
#endif

namespace Star {

STAR_EXCEPTION(IdMapException, StarException);

// Maps key ids to values with auto generated ids in a given id range.  Tries
// to cycle through ids as new values are added and avoid re-using ids until
// the id space wraps around.
template <typename BaseMap>
class IdMapWrapper : private BaseMap {
public:
  typedef typename BaseMap::iterator iterator;
  typedef typename BaseMap::const_iterator const_iterator;
  typedef typename BaseMap::key_type key_type;
  typedef typename BaseMap::value_type value_type;
  typedef typename BaseMap::mapped_type mapped_type;

  typedef key_type IdType;
  typedef value_type ValueType;
  typedef mapped_type MappedType;

  IdMapWrapper();
  IdMapWrapper(IdType min, IdType max);

  // New valid id that does not exist in this map.  Tries not to immediately
  // recycle ids, to avoid temporally close id repeats.
  IdType nextId();

  // Throws exception if key already exists
  void add(IdType id, MappedType mappedType);

  // Add with automatically allocated id
  IdType add(MappedType mappedType);

  void clear();

  bool operator==(IdMapWrapper const& rhs) const;
  bool operator!=(IdMapWrapper const& rhs) const;

  using BaseMap::keys;
  using BaseMap::values;
  using BaseMap::pairs;
  using BaseMap::contains;
  using BaseMap::size;
  using BaseMap::empty;
  using BaseMap::get;
  using BaseMap::ptr;
  using BaseMap::maybe;
  using BaseMap::take;
  using BaseMap::maybeTake;
  using BaseMap::remove;
  using BaseMap::value;
  using BaseMap::begin;
  using BaseMap::end;
  using BaseMap::erase;

  template <typename Base>
  friend DataStream& operator>>(DataStream& ds, IdMapWrapper<Base>& map);
  template <typename Base>
  friend DataStream& operator<<(DataStream& ds, IdMapWrapper<Base> const& map);

private:
  IdType m_min;
  IdType m_max;
  IdType m_nextId;
};

template <class Key, class Value>
using IdMap = IdMapWrapper<Map<Key, Value>>;

template <class Key, class Value>
using IdHashMap = IdMapWrapper<HashMap<Key, Value>>;

#ifdef STAR_USE_RUST_ID_MAP
template <typename BaseMap>
IdMapWrapper<BaseMap>::IdMapWrapper()
  : m_min(lowest<IdType>()), m_max(highest<IdType>()), m_nextId(m_min) {
  auto frame = RustIdMapDetail::makeFrame(SB_IDMAP_CTOR, SB_IDMAP_ROOT,
      [](uint32_t) { return false; },
      [](uint32_t) { return RustIdMapDetail::voidReply(); },
      [] { return true; });
  frame.run();
}

#else
template <typename BaseMap>
IdMapWrapper<BaseMap>::IdMapWrapper()
  : m_min(lowest<IdType>()), m_max(highest<IdType>()), m_nextId(m_min) {}

#endif

#ifdef STAR_USE_RUST_ID_MAP
template <typename BaseMap>
IdMapWrapper<BaseMap>::IdMapWrapper(IdType min, IdType max)
  : m_min(min), m_max(max), m_nextId(m_min) {
  bool done = false;
  auto frame = RustIdMapDetail::makeFrame(SB_IDMAP_RANGE_CTOR, SB_IDMAP_ROOT,
      [&](uint32_t op) { return !done && op == SB_IDMAP_ASSERT_RANGE; },
      [&](uint32_t) {
        starAssert(m_max > m_min);
        done = true;
        return RustIdMapDetail::voidReply();
      },
      [&] { return done; });
  frame.run();
}

#else
template <typename BaseMap>
IdMapWrapper<BaseMap>::IdMapWrapper(IdType min, IdType max)
  : m_min(min), m_max(max), m_nextId(m_min) {
  starAssert(m_max > m_min);
}

#endif

#ifdef STAR_USE_RUST_ID_MAP
template <typename BaseMap>
auto IdMapWrapper<BaseMap>::nextId() -> IdType {
  enum { Check, Throw, Done };
  int phase = Check;
  auto root = RustIdMapDetail::makeFrame(SB_IDMAP_NEXT, SB_IDMAP_ROOT,
      [&](uint32_t op) {
        return (phase == Check && op == SB_IDMAP_FULL)
            || (phase == Throw && op == SB_IDMAP_THROW_FULL);
      },
      [&](uint32_t op) {
        if (op == SB_IDMAP_FULL) {
          bool full = ((IdType)BaseMap::size() > m_max - m_min) ? true : false;
          phase = full ? Throw : Done;
          return RustIdMapDetail::boolReply(full);
        }
        throw IdMapException("No id space left in IdMapWrapper");
      },
      [&] { return phase == Done; });
  root.run();

  // The original named local begins only after the fullness root completes.
  IdType nextId = m_nextId;
  enum { Condition, Advance, Commit, Finished };
  int cursorPhase = Condition;
  auto continuation = RustIdMapDetail::makeFrame(SB_IDMAP_NEXT, SB_IDMAP_CONTINUE,
      [&](uint32_t op) {
        return (cursorPhase == Condition && op == SB_IDMAP_CURSOR_CONTAINS)
            || (cursorPhase == Advance && op == SB_IDMAP_CURSOR_ADVANCE)
            || (cursorPhase == Commit && op == SB_IDMAP_CURSOR_COMMIT);
      },
      [&](uint32_t op) {
        if (op == SB_IDMAP_CURSOR_CONTAINS) {
          bool contains = BaseMap::contains(nextId) ? true : false;
          cursorPhase = contains ? Advance : Commit;
          return RustIdMapDetail::boolReply(contains);
        }
        if (op == SB_IDMAP_CURSOR_ADVANCE) {
          nextId = cycleIncrement(nextId, m_min, m_max);
          cursorPhase = Condition;
        } else {
          m_nextId = cycleIncrement(nextId, m_min, m_max);
          cursorPhase = Finished;
        }
        return RustIdMapDetail::voidReply();
      },
      [&] { return cursorPhase == Finished; });
  continuation.run();
  return nextId;
}

#else
template <typename BaseMap>
auto IdMapWrapper<BaseMap>::nextId() -> IdType {
  if ((IdType)BaseMap::size() > m_max - m_min)
    throw IdMapException("No id space left in IdMapWrapper");

  IdType nextId = m_nextId;
  while (BaseMap::contains(nextId))
    nextId = cycleIncrement(nextId, m_min, m_max);
  m_nextId = cycleIncrement(nextId, m_min, m_max);
  return nextId;
}

#endif

#ifdef STAR_USE_RUST_ID_MAP
template <typename BaseMap>
void IdMapWrapper<BaseMap>::add(IdType id, MappedType mappedType) {
  enum { Insert, Throw, Done };
  int phase = Insert;
  auto frame = RustIdMapDetail::makeFrame(SB_IDMAP_ADD_EXPLICIT, SB_IDMAP_ROOT,
      [&](uint32_t op) {
        return (phase == Insert && op == SB_IDMAP_EXPLICIT_INSERT)
            || (phase == Throw && op == SB_IDMAP_THROW_DUPLICATE);
      },
      [&](uint32_t op) {
        if (op == SB_IDMAP_EXPLICIT_INSERT) {
          bool inserted = (!BaseMap::insert(make_pair(std::move(id), std::move(mappedType))).second) ? false : true;
          phase = inserted ? Done : Throw;
          return RustIdMapDetail::boolReply(inserted);
        }
        throw IdMapException::format("IdMapWrapper::add(id, value) called with pre-existing id '{}'", outputAny(id));
      },
      [&] { return phase == Done; });
  frame.run();
}

#else
template <typename BaseMap>
void IdMapWrapper<BaseMap>::add(IdType id, MappedType mappedType) {
  if (!BaseMap::insert(make_pair(std::move(id), std::move(mappedType))).second)
    throw IdMapException::format("IdMapWrapper::add(id, value) called with pre-existing id '{}'", outputAny(id));
}

#endif

#ifdef STAR_USE_RUST_ID_MAP
template <typename BaseMap>
auto IdMapWrapper<BaseMap>::add(MappedType mappedType) -> IdType {
  auto root = RustIdMapDetail::makeFrame(SB_IDMAP_ADD_AUTO, SB_IDMAP_ROOT,
      [](uint32_t) { return false; },
      [](uint32_t) { return RustIdMapDetail::voidReply(); },
      [] { return true; });
  root.run();
  auto id = nextId();
  bool done = false;
  auto continuation = RustIdMapDetail::makeFrame(SB_IDMAP_ADD_AUTO, SB_IDMAP_CONTINUE,
      [&](uint32_t op) { return !done && op == SB_IDMAP_AUTO_INSERT; },
      [&](uint32_t) {
        BaseMap::insert(id, mappedType);
        done = true;
        return RustIdMapDetail::voidReply();
      },
      [&] { return done; });
  continuation.run();
  return id;
}

#else
template <typename BaseMap>
auto IdMapWrapper<BaseMap>::add(MappedType mappedType) -> IdType {
  auto id = nextId();
  BaseMap::insert(id, mappedType);
  return id;
}

#endif

#ifdef STAR_USE_RUST_ID_MAP
template <typename BaseMap>
void IdMapWrapper<BaseMap>::clear() {
  enum { Map, Cursor, Done };
  int phase = Map;
  auto frame = RustIdMapDetail::makeFrame(SB_IDMAP_CLEAR, SB_IDMAP_ROOT,
      [&](uint32_t op) {
        return (phase == Map && op == SB_IDMAP_CLEAR_MAP)
            || (phase == Cursor && op == SB_IDMAP_CLEAR_CURSOR);
      },
      [&](uint32_t op) {
        if (op == SB_IDMAP_CLEAR_MAP) {
          BaseMap::clear();
          phase = Cursor;
        } else {
          m_nextId = m_min;
          phase = Done;
        }
        return RustIdMapDetail::voidReply();
      },
      [&] { return phase == Done; });
  frame.run();
}

#else
template <typename BaseMap>
void IdMapWrapper<BaseMap>::clear() {
  BaseMap::clear();
  m_nextId = m_min;
}

#endif

#ifdef STAR_USE_RUST_ID_MAP
template <typename BaseMap>
bool IdMapWrapper<BaseMap>::operator==(IdMapWrapper const& rhs) const {
  enum { Bounds, Base, Done };
  int phase = Bounds;
  auto frame = RustIdMapDetail::makeFrame(SB_IDMAP_EQUAL, SB_IDMAP_ROOT,
      [&](uint32_t op) {
        return (phase == Bounds && op == SB_IDMAP_SAME_BOUNDS)
            || (phase == Base && op == SB_IDMAP_BASE_EQUAL);
      },
      [&](uint32_t op) {
        if (op == SB_IDMAP_SAME_BOUNDS) {
          bool same = (tie(m_min, m_max) == tie(rhs.m_min, rhs.m_max)) ? true : false;
          phase = same ? Base : Done;
          return RustIdMapDetail::boolReply(same);
        }
        bool same = BaseMap::operator==(rhs) ? true : false;
        phase = Done;
        return RustIdMapDetail::boolReply(same);
      },
      [&] { return phase == Done; });
  return frame.run().value != 0;
}

#else
template <typename BaseMap>
bool IdMapWrapper<BaseMap>::operator==(IdMapWrapper const& rhs) const {
  return tie(m_min, m_max) == tie(rhs.m_min, rhs.m_max) && BaseMap::operator==(rhs);
}

#endif

#ifdef STAR_USE_RUST_ID_MAP
template <typename BaseMap>
bool IdMapWrapper<BaseMap>::operator!=(IdMapWrapper const& rhs) const {
  bool done = false;
  auto frame = RustIdMapDetail::makeFrame(SB_IDMAP_NOT_EQUAL, SB_IDMAP_ROOT,
      [&](uint32_t op) { return !done && op == SB_IDMAP_CALL_EQUAL; },
      [&](uint32_t) {
        bool same = operator==(rhs) ? true : false;
        done = true;
        return RustIdMapDetail::boolReply(same);
      },
      [&] { return done; });
  return frame.run().value != 0;
}

#else
template <typename BaseMap>
bool IdMapWrapper<BaseMap>::operator!=(IdMapWrapper const& rhs) const {
  return !operator==(rhs);
}

#endif

#ifdef STAR_USE_RUST_ID_MAP
template <typename BaseMap>
DataStream& operator>>(DataStream& ds, IdMapWrapper<BaseMap>& map) {
  uint32_t next = SB_IDMAP_READ_MAP;
  auto frame = RustIdMapDetail::makeFrame(SB_IDMAP_READ, SB_IDMAP_ROOT,
      [&](uint32_t op) { return next <= SB_IDMAP_READ_CURSOR && op == next; },
      [&](uint32_t op) {
        switch (op) {
          case SB_IDMAP_READ_MAP: ds.readMapContainer((BaseMap&)map); break;
          case SB_IDMAP_READ_MIN: ds.read(map.m_min); break;
          case SB_IDMAP_READ_MAX: ds.read(map.m_max); break;
          case SB_IDMAP_READ_CURSOR: ds.read(map.m_nextId); break;
        }
        ++next;
        return RustIdMapDetail::voidReply();
      },
      [&] { return next == SB_IDMAP_READ_CURSOR + 1; });
  frame.run();
  return ds;
}

#else
template <typename BaseMap>
DataStream& operator>>(DataStream& ds, IdMapWrapper<BaseMap>& map) {
  ds.readMapContainer((BaseMap&)map);
  ds.read(map.m_min);
  ds.read(map.m_max);
  ds.read(map.m_nextId);
  return ds;
}

#endif

#ifdef STAR_USE_RUST_ID_MAP
template <typename BaseMap>
DataStream& operator<<(DataStream& ds, IdMapWrapper<BaseMap> const& map) {
  uint32_t next = SB_IDMAP_WRITE_MAP;
  auto frame = RustIdMapDetail::makeFrame(SB_IDMAP_WRITE, SB_IDMAP_ROOT,
      [&](uint32_t op) { return next <= SB_IDMAP_WRITE_CURSOR && op == next; },
      [&](uint32_t op) {
        switch (op) {
          case SB_IDMAP_WRITE_MAP: ds.writeMapContainer((BaseMap const&)map); break;
          case SB_IDMAP_WRITE_MIN: ds.write(map.m_min); break;
          case SB_IDMAP_WRITE_MAX: ds.write(map.m_max); break;
          case SB_IDMAP_WRITE_CURSOR: ds.write(map.m_nextId); break;
        }
        ++next;
        return RustIdMapDetail::voidReply();
      },
      [&] { return next == SB_IDMAP_WRITE_CURSOR + 1; });
  frame.run();
  return ds;
}
#else
template <typename BaseMap>
DataStream& operator<<(DataStream& ds, IdMapWrapper<BaseMap> const& map) {
  ds.writeMapContainer((BaseMap const&)map);
  ds.write(map.m_min);
  ds.write(map.m_max);
  ds.write(map.m_nextId);
  return ds;
}
#endif


}
