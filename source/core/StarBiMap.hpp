#pragma once

#include "StarString.hpp"
#ifdef STAR_USE_RUST_BIMAP
#include "StarBiMapHost.hpp"
#endif

namespace Star {

// Bi-directional map of unique sets of elements with quick map access from
// either the left or right element to the other side.  Every left side value
// must be unique from every other left side value and the same for the right
// side.
template <typename LeftT,
    typename RightT,
    typename LeftMapT = Map<LeftT, RightT const*>,
    typename RightMapT = Map<RightT, LeftT const*>>
class BiMap {
public:
  typedef LeftT Left;
  typedef RightT Right;
  typedef LeftMapT LeftMap;
  typedef RightMapT RightMap;

  typedef pair<Left, Right> value_type;

  struct BiMapIterator {
    BiMapIterator& operator++();
    BiMapIterator operator++(int);

    bool operator==(BiMapIterator const& rhs) const;
    bool operator!=(BiMapIterator const& rhs) const;

    pair<Left const&, Right const&> operator*() const;

    typename LeftMap::const_iterator iterator;
  };

  typedef BiMapIterator iterator;
  typedef iterator const_iterator;

  template <typename Collection>
  static BiMap from(Collection const& c);

  BiMap();
  BiMap(BiMap const& map);

  template <typename InputIterator>
  BiMap(InputIterator beg, InputIterator end);

  BiMap(std::initializer_list<value_type> list);

  List<Left> leftValues() const;
  List<Right> rightValues() const;
  List<value_type> pairs() const;

  bool hasLeftValue(Left const& left) const;
  bool hasRightValue(Right const& right) const;

  Right const& getRight(Left const& left) const;
  Left const& getLeft(Right const& right) const;

  Right valueRight(Left const& left, Right const& def = Right()) const;
  Left valueLeft(Right const& right, Left const& def = Left()) const;

  Maybe<Right> maybeRight(Left const& left) const;

  Maybe<Left> maybeLeft(Right const& right) const;

  Right takeRight(Left const& left);
  Left takeLeft(Right const& right);

  Maybe<Right> maybeTakeRight(Left const& left);
  Maybe<Left> maybeTakeLeft(Right const& right);

  Right const* rightPtr(Left const& left) const;
  Left const* leftPtr(Right const& right) const;

  BiMap& operator=(BiMap const& map);

  pair<iterator, bool> insert(value_type const& val);

  // Returns true if value was inserted, false if either the left or right side
  // already existed.
  bool insert(Left const& left, Right const& right);

  // Throws an exception if the pair cannot be inserted
  void add(Left const& left, Right const& right);
  void add(value_type const& value);

  // Overwrites the left / right mapping regardless of whether each side
  // already exists.
  void overwrite(Left const& left, Right const& right);
  void overwrite(value_type const& value);

  // Removes the pair with the given left side, returns true if this pair was
  // found, false otherwise.
  bool removeLeft(Left const& left);

  // Removes the pair with the given right side, returns true if this pair was
  // found, false otherwise.
  bool removeRight(Right const& right);

  const_iterator begin() const;
  const_iterator end() const;

  size_t size() const;

  void clear();

  bool empty() const;

  bool operator==(BiMap const& m) const;

private:
  LeftMap m_leftMap;
  RightMap m_rightMap;
};

template <typename Left, typename Right, typename LeftHash = Star::hash<Left>, typename RightHash = Star::hash<Right>>
using BiHashMap = BiMap<Left, Right, StableHashMap<Left, Right const*, LeftHash>, StableHashMap<Right, Left const*, RightHash>>;

// Case insensitive Enum <-> String map
template <typename EnumType>
using EnumMap = BiMap<EnumType,
    String,
    Map<EnumType, String const*>,
    StableHashMap<String, EnumType const*, CaseInsensitiveStringHash, CaseInsensitiveStringCompare>>;

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
auto BiMap<LeftT, RightT, LeftMapT, RightMapT>::BiMapIterator::operator++() -> BiMapIterator & {
  ++iterator;
  return *this;
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
auto BiMap<LeftT, RightT, LeftMapT, RightMapT>::BiMapIterator::operator++(int) -> BiMapIterator {
  BiMapIterator last{iterator};
  ++iterator;
  return last;
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
bool BiMap<LeftT, RightT, LeftMapT, RightMapT>::BiMapIterator::operator==(BiMapIterator const& rhs) const {
  return iterator == rhs.iterator;
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
bool BiMap<LeftT, RightT, LeftMapT, RightMapT>::BiMapIterator::operator!=(BiMapIterator const& rhs) const {
  return iterator != rhs.iterator;
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
pair<LeftT const&, RightT const&> BiMap<LeftT, RightT, LeftMapT, RightMapT>::BiMapIterator::operator*() const {
  return {iterator->first, *iterator->second};
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
template <typename Collection>
BiMap<LeftT, RightT, LeftMapT, RightMapT> BiMap<LeftT, RightT, LeftMapT, RightMapT>::from(Collection const& c) {
  return BiMap(c.begin(), c.end());
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
BiMap<LeftT, RightT, LeftMapT, RightMapT>::BiMap() {}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
BiMap<LeftT, RightT, LeftMapT, RightMapT>::BiMap(BiMap const& map)
  : BiMap(map.begin(), map.end()) {}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
template <typename InputIterator>
BiMap<LeftT, RightT, LeftMapT, RightMapT>::BiMap(InputIterator beg, InputIterator end) {
#ifdef STAR_USE_RUST_BIMAP
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_ITERATOR_PRESENT: return BiMapFrames::boolReply(static_cast<bool>(beg != end));
      case SB_BIMAP_INSERT_CURRENT_IGNORED: { insert(*beg); return BiMapFrames::voidReply(); }
      case SB_BIMAP_ADVANCE_ITERATOR: ++beg; return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  frame.run(SB_BIMAP_MODE_RANGE_INSERT);
#else
  while (beg != end) {
    insert(*beg);
    ++beg;
  }
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
BiMap<LeftT, RightT, LeftMapT, RightMapT>::BiMap(std::initializer_list<value_type> list) {
#ifdef STAR_USE_RUST_BIMAP
  auto cursor = list.begin();
  auto last = list.end();
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_ITERATOR_PRESENT: return BiMapFrames::boolReply(cursor != last);
      case SB_BIMAP_INSERT_CURRENT_CHECKED: {
        value_type const& v = *cursor;
        return BiMapFrames::boolReply(insert(v.first, v.second));
      }
      case SB_BIMAP_THROW_CURRENT_DUPLICATE: {
        value_type const& v = *cursor;
        throw MapException::format("Repeat pair in BiMap initializer_list construction: ({}, {})", outputAny(v.first), outputAny(v.second));
      }
      case SB_BIMAP_ADVANCE_ITERATOR: ++cursor; return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  frame.run(SB_BIMAP_MODE_LIST_INSERT);
#else
  for (value_type const& v : list) {
    if (!insert(v.first, v.second))
      throw MapException::format("Repeat pair in BiMap initializer_list construction: ({}, {})", outputAny(v.first), outputAny(v.second));
  }
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
List<LeftT> BiMap<LeftT, RightT, LeftMapT, RightMapT>::leftValues() const {
  return m_leftMap.keys();
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
List<RightT> BiMap<LeftT, RightT, LeftMapT, RightMapT>::rightValues() const {
  return m_rightMap.keys();
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
auto BiMap<LeftT, RightT, LeftMapT, RightMapT>::pairs() const -> List<value_type> {
#ifdef STAR_USE_RUST_BIMAP
  List<value_type> values;
  {
    auto cursor = begin();
    auto last = end();
    auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
      switch (req.op) {
        case SB_BIMAP_ITERATOR_PRESENT: return BiMapFrames::boolReply((bool)(cursor != last));
        case SB_BIMAP_APPEND_CURRENT: {
          auto const& p = *cursor;
          values.append(p);
          return BiMapFrames::voidReply();
        }
        case SB_BIMAP_ADVANCE_ITERATOR: ++cursor; return BiMapFrames::voidReply();
        default: return BiMapFrames::invalidReply();
      }
    });
    frame.run(SB_BIMAP_MODE_PAIRS);
  }
  return values;
#else
  List<value_type> values;
  for (auto const& p : *this)
    values.append(p);
  return values;
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
bool BiMap<LeftT, RightT, LeftMapT, RightMapT>::hasLeftValue(Left const& left) const {
#ifdef STAR_USE_RUST_BIMAP
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    if (req.op == SB_BIMAP_HAS_LEFT) return BiMapFrames::boolReply(m_leftMap.contains(left));
    return BiMapFrames::invalidReply();
  });
  return frame.run(SB_BIMAP_MODE_HAS_LEFT).value;
#else
  return m_leftMap.contains(left);
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
bool BiMap<LeftT, RightT, LeftMapT, RightMapT>::hasRightValue(Right const& right) const {
#ifdef STAR_USE_RUST_BIMAP
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    if (req.op == SB_BIMAP_HAS_RIGHT) return BiMapFrames::boolReply(m_rightMap.contains(right));
    return BiMapFrames::invalidReply();
  });
  return frame.run(SB_BIMAP_MODE_HAS_RIGHT).value;
#else
  return m_rightMap.contains(right);
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
RightT const& BiMap<LeftT, RightT, LeftMapT, RightMapT>::getRight(Left const& left) const {
  return *m_leftMap.get(left);
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
LeftT const& BiMap<LeftT, RightT, LeftMapT, RightMapT>::getLeft(Right const& right) const {
  return *m_rightMap.get(right);
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
RightT BiMap<LeftT, RightT, LeftMapT, RightMapT>::valueRight(Left const& left, Right const& def) const {
  return maybeRight(left).value(def);
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
LeftT BiMap<LeftT, RightT, LeftMapT, RightMapT>::valueLeft(Right const& right, Left const& def) const {
  return maybeLeft(right).value(def);
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
Maybe<RightT> BiMap<LeftT, RightT, LeftMapT, RightMapT>::maybeRight(Left const& left) const {
#ifdef STAR_USE_RUST_BIMAP
  auto i = m_leftMap.find(left);
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    if (req.op == SB_BIMAP_PRESENT) return BiMapFrames::boolReply((bool)(i != m_leftMap.end()));
    return BiMapFrames::invalidReply();
  });
  if (frame.run(SB_BIMAP_MODE_PRESENT).value)
    return *i->second;
  return {};
#else
  auto i = m_leftMap.find(left);
  if (i != m_leftMap.end())
    return *i->second;
  return {};
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
Maybe<LeftT> BiMap<LeftT, RightT, LeftMapT, RightMapT>::maybeLeft(Right const& right) const {
#ifdef STAR_USE_RUST_BIMAP
  auto i = m_rightMap.find(right);
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    if (req.op == SB_BIMAP_PRESENT) return BiMapFrames::boolReply((bool)(i != m_rightMap.end()));
    return BiMapFrames::invalidReply();
  });
  if (frame.run(SB_BIMAP_MODE_PRESENT).value)
    return *i->second;
  return {};
#else
  auto i = m_rightMap.find(right);
  if (i != m_rightMap.end())
    return *i->second;
  return {};
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
RightT BiMap<LeftT, RightT, LeftMapT, RightMapT>::takeRight(Left const& left) {
#ifdef STAR_USE_RUST_BIMAP
  {
    auto right = maybeTakeRight(left);
    auto present = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
      if (req.op == SB_BIMAP_PRESENT) return BiMapFrames::boolReply((bool)right);
      return BiMapFrames::invalidReply();
    });
    if (present.run(SB_BIMAP_MODE_PRESENT).value)
      return right.take();
  }
  auto missing = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    if (req.op == SB_BIMAP_THROW_TAKE)
      throw MapException::format("No such key in BiMap::takeRight", outputAny(left));
    return BiMapFrames::invalidReply();
  });
  missing.run(SB_BIMAP_MODE_THROW_TAKE);
  throw std::logic_error("Invalid BiMap boundary protocol");
#else
  if (auto right = maybeTakeRight(left))
    return right.take();
  throw MapException::format("No such key in BiMap::takeRight", outputAny(left));
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
LeftT BiMap<LeftT, RightT, LeftMapT, RightMapT>::takeLeft(Right const& right) {
#ifdef STAR_USE_RUST_BIMAP
  {
    auto left = maybeTakeLeft(right);
    auto present = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
      if (req.op == SB_BIMAP_PRESENT) return BiMapFrames::boolReply((bool)left);
      return BiMapFrames::invalidReply();
    });
    if (present.run(SB_BIMAP_MODE_PRESENT).value)
      return left.take();
  }
  auto missing = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    if (req.op == SB_BIMAP_THROW_TAKE)
      throw MapException::format("No such key in BiMap::takeLeft", outputAny(right));
    return BiMapFrames::invalidReply();
  });
  missing.run(SB_BIMAP_MODE_THROW_TAKE);
  throw std::logic_error("Invalid BiMap boundary protocol");
#else
  if (auto left = maybeTakeLeft(right))
    return left.take();
  throw MapException::format("No such key in BiMap::takeLeft", outputAny(right));
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
Maybe<RightT> BiMap<LeftT, RightT, LeftMapT, RightMapT>::maybeTakeRight(Left const& left) {
#ifdef STAR_USE_RUST_BIMAP
  auto rightPtr = m_leftMap.maybeTake(left).value();
  auto present = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    if (req.op == SB_BIMAP_PRESENT) return BiMapFrames::boolReply((bool)rightPtr);
    return BiMapFrames::invalidReply();
  });
  if (present.run(SB_BIMAP_MODE_PRESENT).value) {
    Right right = *rightPtr;
    auto remove = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
      if (req.op == SB_BIMAP_REMOVE_TAKEN) { m_rightMap.remove(*rightPtr); return BiMapFrames::voidReply(); }
      return BiMapFrames::invalidReply();
    });
    remove.run(SB_BIMAP_MODE_REMOVE_TAKEN);
    return right;
  } else {
    return {};
  }
#else
  if (auto rightPtr = m_leftMap.maybeTake(left).value()) {
    Right right = *rightPtr;
    m_rightMap.remove(*rightPtr);
    return right;
  } else {
    return {};
  }
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
Maybe<LeftT> BiMap<LeftT, RightT, LeftMapT, RightMapT>::maybeTakeLeft(Right const& right) {
#ifdef STAR_USE_RUST_BIMAP
  auto leftPtr = m_rightMap.maybeTake(right).value();
  auto present = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    if (req.op == SB_BIMAP_PRESENT) return BiMapFrames::boolReply((bool)leftPtr);
    return BiMapFrames::invalidReply();
  });
  if (present.run(SB_BIMAP_MODE_PRESENT).value) {
    Left left = *leftPtr;
    auto remove = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
      if (req.op == SB_BIMAP_REMOVE_TAKEN) { m_leftMap.remove(*leftPtr); return BiMapFrames::voidReply(); }
      return BiMapFrames::invalidReply();
    });
    remove.run(SB_BIMAP_MODE_REMOVE_TAKEN);
    return left;
  } else {
    return {};
  }
#else
  if (auto leftPtr = m_rightMap.maybeTake(right).value()) {
    Left left = *leftPtr;
    m_leftMap.remove(*leftPtr);
    return left;
  } else {
    return {};
  }
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
RightT const* BiMap<LeftT, RightT, LeftMapT, RightMapT>::rightPtr(Left const& left) const {
  return m_leftMap.value(left);
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
LeftT const* BiMap<LeftT, RightT, LeftMapT, RightMapT>::leftPtr(Right const& right) const {
  return m_rightMap.value(right);
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
BiMap<LeftT, RightT, LeftMapT, RightMapT>& BiMap<LeftT, RightT, LeftMapT, RightMapT>::operator=(BiMap const& map) {
#ifdef STAR_USE_RUST_BIMAP
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_ASSIGN_DISTINCT: return BiMapFrames::boolReply(static_cast<bool>(this != &map));
      case SB_BIMAP_CLEAR_LEFT: m_leftMap.clear(); return BiMapFrames::voidReply();
      case SB_BIMAP_CLEAR_RIGHT: m_rightMap.clear(); return BiMapFrames::voidReply();
      case SB_BIMAP_COPY_ENTRIES: {
        auto cursor = map.begin();
        auto last = map.end();
        auto loop = BiMapFrames::makeFrame([&](SbBiMapRequest const& step) -> SbBiMapReply {
          switch (step.op) {
            case SB_BIMAP_ITERATOR_PRESENT: return BiMapFrames::boolReply(cursor != last);
            case SB_BIMAP_INSERT_CURRENT_IGNORED: {
              auto const& p = *cursor; insert(p);
              return BiMapFrames::voidReply();
            }
            case SB_BIMAP_ADVANCE_ITERATOR: ++cursor; return BiMapFrames::voidReply();
            default: return BiMapFrames::invalidReply();
          }
        });
        loop.run(SB_BIMAP_MODE_COPY_ENTRIES);
        return BiMapFrames::voidReply();
      }
      default: return BiMapFrames::invalidReply();
    }
  });
  frame.run(SB_BIMAP_MODE_COPY_ASSIGN);
  return *this;
#else
  if (this != &map) {
    clear();
    for (auto const& p : map)
      insert(p);
  }
  return *this;
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
auto BiMap<LeftT, RightT, LeftMapT, RightMapT>::insert(value_type const& val) -> pair<iterator, bool> {
#ifdef STAR_USE_RUST_BIMAP
  auto leftRes = m_leftMap.insert(make_pair(val.first, nullptr));
  auto route = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    if (req.op == SB_BIMAP_LEFT_INSERTED) return BiMapFrames::boolReply(!static_cast<bool>(!leftRes.second));
    return BiMapFrames::invalidReply();
  });
  if (!route.run(SB_BIMAP_MODE_INSERT_ROUTE).value)
    return {BiMapIterator{leftRes.first}, false};

  auto rightRes = m_rightMap.insert(make_pair(val.second, nullptr));
  auto link = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_ASSERT_RIGHT_INSERTED: starAssert(rightRes.second == true); return BiMapFrames::voidReply();
      case SB_BIMAP_LINK_LEFT: leftRes.first->second = &rightRes.first->first; return BiMapFrames::voidReply();
      case SB_BIMAP_LINK_RIGHT: rightRes.first->second = &leftRes.first->first; return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  link.run(SB_BIMAP_MODE_INSERT_LINK);
  return {BiMapIterator{leftRes.first}, true};
#else
  auto leftRes = m_leftMap.insert(make_pair(val.first, nullptr));
  if (!leftRes.second)
    return {BiMapIterator{leftRes.first}, false};

  auto rightRes = m_rightMap.insert(make_pair(val.second, nullptr));
  starAssert(rightRes.second == true);
  leftRes.first->second = &rightRes.first->first;
  rightRes.first->second = &leftRes.first->first;
  return {BiMapIterator{leftRes.first}, true};
#endif
};

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
bool BiMap<LeftT, RightT, LeftMapT, RightMapT>::insert(Left const& left, Right const& right) {
  return insert(make_pair(left, right)).second;
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
void BiMap<LeftT, RightT, LeftMapT, RightMapT>::add(Left const& left, Right const& right) {
#ifdef STAR_USE_RUST_BIMAP
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_HAS_LEFT: return BiMapFrames::boolReply(m_leftMap.contains(left));
      case SB_BIMAP_HAS_RIGHT: return BiMapFrames::boolReply(m_rightMap.contains(right));
      case SB_BIMAP_THROW_LEFT: throw MapException(strf("BiMap already contains left side value '{}'", outputAny(left)));
      case SB_BIMAP_THROW_RIGHT: throw MapException(strf("BiMap already contains right side value '{}'", outputAny(right)));
      case SB_BIMAP_INSERT_IGNORED: insert(left, right); return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  frame.run(SB_BIMAP_MODE_ADD);
#else
  if (m_leftMap.contains(left))
    throw MapException(strf("BiMap already contains left side value '{}'", outputAny(left)));

  if (m_rightMap.contains(right))
    throw MapException(strf("BiMap already contains right side value '{}'", outputAny(right)));

  insert(left, right);
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
void BiMap<LeftT, RightT, LeftMapT, RightMapT>::add(value_type const& value) {
  add(value.first, value.second);
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
void BiMap<LeftT, RightT, LeftMapT, RightMapT>::overwrite(Left const& left, Right const& right) {
#ifdef STAR_USE_RUST_BIMAP
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_REMOVE_LEFT_IGNORED: removeLeft(left); return BiMapFrames::voidReply();
      case SB_BIMAP_REMOVE_RIGHT_IGNORED: removeRight(right); return BiMapFrames::voidReply();
      case SB_BIMAP_INSERT_IGNORED: insert(left, right); return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  frame.run(SB_BIMAP_MODE_OVERWRITE);
#else
  removeLeft(left);
  removeRight(right);
  insert(left, right);
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
void BiMap<LeftT, RightT, LeftMapT, RightMapT>::overwrite(value_type const& value) {
  return overwrite(value.first, value.second);
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
bool BiMap<LeftT, RightT, LeftMapT, RightMapT>::removeLeft(Left const& left) {
#ifdef STAR_USE_RUST_BIMAP
  Right const* right = nullptr;
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_RIGHT_FOR_LEFT_PRESENT: right = m_leftMap.value(left); return BiMapFrames::boolReply(right);
      case SB_BIMAP_REMOVE_RIGHT_USING_FOUND: m_rightMap.remove(*right); return BiMapFrames::voidReply();
      case SB_BIMAP_REMOVE_LEFT_IGNORED: m_leftMap.remove(left); return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  return frame.run(SB_BIMAP_MODE_REMOVE_LEFT).value;
#else
  if (auto right = m_leftMap.value(left)) {
    m_rightMap.remove(*right);
    m_leftMap.remove(left);
    return true;
  }

  return false;
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
bool BiMap<LeftT, RightT, LeftMapT, RightMapT>::removeRight(Right const& right) {
#ifdef STAR_USE_RUST_BIMAP
  Left const* left = nullptr;
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_LEFT_FOR_RIGHT_PRESENT: left = m_rightMap.value(right); return BiMapFrames::boolReply(left);
      case SB_BIMAP_REMOVE_LEFT_USING_FOUND: m_leftMap.remove(*left); return BiMapFrames::voidReply();
      case SB_BIMAP_REMOVE_RIGHT_IGNORED: m_rightMap.remove(right); return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  return frame.run(SB_BIMAP_MODE_REMOVE_RIGHT).value;
#else
  if (auto left = m_rightMap.value(right)) {
    m_leftMap.remove(*left);
    m_rightMap.remove(right);
    return true;
  }

  return false;
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
auto BiMap<LeftT, RightT, LeftMapT, RightMapT>::begin() const -> const_iterator {
  return BiMapIterator{m_leftMap.begin()};
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
auto BiMap<LeftT, RightT, LeftMapT, RightMapT>::end() const -> const_iterator {
  return BiMapIterator{m_leftMap.end()};
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
size_t BiMap<LeftT, RightT, LeftMapT, RightMapT>::size() const {
#ifdef STAR_USE_RUST_BIMAP
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    if (req.op == SB_BIMAP_SIZE) return BiMapFrames::sizeReply(m_leftMap.size());
    return BiMapFrames::invalidReply();
  });
  return frame.run(SB_BIMAP_MODE_SIZE).value;
#else
  return m_leftMap.size();
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
void BiMap<LeftT, RightT, LeftMapT, RightMapT>::clear() {
#ifdef STAR_USE_RUST_BIMAP
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_CLEAR_LEFT: m_leftMap.clear(); return BiMapFrames::voidReply();
      case SB_BIMAP_CLEAR_RIGHT: m_rightMap.clear(); return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  frame.run(SB_BIMAP_MODE_CLEAR);
#else
  m_leftMap.clear();
  m_rightMap.clear();
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
bool BiMap<LeftT, RightT, LeftMapT, RightMapT>::empty() const {
#ifdef STAR_USE_RUST_BIMAP
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    if (req.op == SB_BIMAP_EMPTY) return BiMapFrames::boolReply(m_leftMap.empty());
    return BiMapFrames::invalidReply();
  });
  return frame.run(SB_BIMAP_MODE_EMPTY).value;
#else
  return m_leftMap.empty();
#endif
}

template <typename LeftT, typename RightT, typename LeftMapT, typename RightMapT>
bool BiMap<LeftT, RightT, LeftMapT, RightMapT>::operator==(BiMap const& m) const {
#ifdef STAR_USE_RUST_BIMAP
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_SELF_EQUAL: return BiMapFrames::boolReply(static_cast<bool>(&m == this));
      case SB_BIMAP_SIZE: return BiMapFrames::sizeReply(size());
      case SB_BIMAP_OTHER_SIZE: return BiMapFrames::sizeReply(m.size());
      case SB_BIMAP_EQUAL_ENTRIES: {
        auto cursor = begin();
        auto last = end();
        auto loop = BiMapFrames::makeFrame([&](SbBiMapRequest const& step) -> SbBiMapReply {
          switch (step.op) {
            case SB_BIMAP_ITERATOR_PRESENT: return BiMapFrames::boolReply(cursor != last);
            case SB_BIMAP_ADVANCE_ITERATOR: ++cursor; return BiMapFrames::voidReply();
            case SB_BIMAP_COMPARE_CURRENT_SCOPED: {
              auto const& pair = *cursor;
              Right const* p = nullptr;
              auto current = BiMapFrames::makeFrame([&](SbBiMapRequest const& leaf) -> SbBiMapReply {
                switch (leaf.op) {
                  case SB_BIMAP_FIND_CURRENT_RIGHT: p = m.rightPtr(pair.first); return BiMapFrames::boolReply(p);
                  case SB_BIMAP_CURRENT_RIGHT_NOT_EQUAL: return BiMapFrames::boolReply(static_cast<bool>(!p || *p != pair.second));
                  default: return BiMapFrames::invalidReply();
                }
              });
              return BiMapFrames::boolReply(current.run(SB_BIMAP_MODE_EQUAL_PAIR).value);
            }
            default: return BiMapFrames::invalidReply();
          }
        });
        return BiMapFrames::boolReply(loop.run(SB_BIMAP_MODE_EQUAL_SCOPED_ENTRIES).value);
      }
      default: return BiMapFrames::invalidReply();
    }
  });
  return frame.run(SB_BIMAP_MODE_EQUAL).value;
#else
  if (&m == this)
    return true;

  if (size() != m.size())
    return false;

  for (auto const& pair : *this) {
    if (auto p = m.rightPtr(pair.first))
      if (!p || *p != pair.second)
        return false;
  }

  return true;
#endif
}

}
