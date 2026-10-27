#pragma once

#include "StarOrderedMap.hpp"
#include "StarBlockAllocator.hpp"
#ifdef STAR_USE_RUST_LRU_CACHE
#include "StarLruCacheHost.hpp"
#endif

namespace Star {

template <typename OrderedMapType>
class LruCacheBase {
public:
  typedef typename OrderedMapType::key_type Key;
  typedef typename OrderedMapType::mapped_type Value;

  typedef function<Value(Key const&)> ProducerFunction;

  LruCacheBase(size_t maxSize = 256);

  // Max size cannot be zero, it will be clamped to at least 1 in order to hold
  // the most recent element returned by get.
  size_t maxSize() const;
  void setMaxSize(size_t maxSize);

  size_t currentSize() const;

  List<Key> keys() const;
  List<Value> values() const;

  // If the value is in the cache, returns a pointer to it and marks it as
  // accessed, otherwise returns nullptr.
  Value* ptr(Key const& key);

  // Put the given value into the cache.
  void set(Key const& key, Value value);
  // Removes the given value from the cache.  If found and removed, returns
  // true.
  bool remove(Key const& key);

  // Remove all key / value pairs matching a filter.
  void removeWhere(function<bool(Key const&, Value&)> filter);

  // If the value for the key is not found in the cache, produce it with the
  // given producer.  Producer shold take the key as an argument and return the
  // value.
  template <typename Producer>
  Value& get(Key const& key, Producer producer);

  // Clear all cached entries.
  void clear();

private:
  OrderedMapType m_map;
  size_t m_maxSize;
#ifdef STAR_USE_RUST_LRU_CACHE
  template <uint32_t Mode>
  using Context = LruCacheRust::Context<OrderedMapType, Mode>;
#endif
};

template <typename Key, typename Value, typename Compare = std::less<Key>, typename Allocator = BlockAllocator<pair<Key const, Value>, 1024>>
using LruCache = LruCacheBase<OrderedMap<Key, Value, Compare, Allocator>>;

template <typename Key, typename Value, typename Hash = Star::hash<Key>, typename Equals = std::equal_to<Key>, typename Allocator = BlockAllocator<pair<Key const, Value>, 1024>>
using HashLruCache = LruCacheBase<OrderedHashMap<Key, Value, Hash, Equals, Allocator>>;

template <typename OrderedMapType>
LruCacheBase<OrderedMapType>::LruCacheBase(size_t maxSize) {
#ifdef STAR_USE_RUST_LRU_CACHE
  Context<SB_LRU_CTOR> c(m_map, m_maxSize);
  c.arg = maxSize;
  c.execute();
#else
  setMaxSize(maxSize);
#endif
}

template <typename OrderedMapType>
size_t LruCacheBase<OrderedMapType>::maxSize() const {
#ifdef STAR_USE_RUST_LRU_CACHE
  Context<SB_LRU_MAX> c(m_map, m_maxSize);
  return c.execute().value;
#else
  return m_maxSize;
#endif
}

template <typename OrderedMapType>
void LruCacheBase<OrderedMapType>::setMaxSize(size_t maxSize) {
#ifdef STAR_USE_RUST_LRU_CACHE
  Context<SB_LRU_LIMIT> c(m_map, m_maxSize);
  c.arg = maxSize;
  c.execute();
#else
  m_maxSize = max<size_t>(maxSize, 1);

  while (m_map.size() > m_maxSize)
    m_map.removeFirst();
#endif
}

template <typename OrderedMapType>
size_t LruCacheBase<OrderedMapType>::currentSize() const {
#ifdef STAR_USE_RUST_LRU_CACHE
  Context<SB_LRU_SIZE> c(m_map, m_maxSize);
  return c.execute().value;
#else
  return m_map.size();
#endif
}

template <typename OrderedMapType>
auto LruCacheBase<OrderedMapType>::keys() const -> List<Key> {
#ifdef STAR_USE_RUST_LRU_CACHE
  Context<SB_LRU_KEYS> c(m_map, m_maxSize);
  c.execute();
#endif
  // direct prvalue: no ABI-owned List or extra snapshot move.
  return m_map.keys();
}

template <typename OrderedMapType>
auto LruCacheBase<OrderedMapType>::values() const -> List<Value> {
#ifdef STAR_USE_RUST_LRU_CACHE
  Context<SB_LRU_VALUES> c(m_map, m_maxSize);
  c.execute();
#endif
  return m_map.values();
}

template <typename OrderedMapType>
auto LruCacheBase<OrderedMapType>::ptr(Key const& key) -> Value * {
#ifdef STAR_USE_RUST_LRU_CACHE
  Context<SB_LRU_PTR> c(m_map, m_maxSize);
  c.key = &key;
  c.execute();
  return c.reference;
#else
  auto i = m_map.find(key);
  if (i == m_map.end())
    return nullptr;
  i = m_map.toBack(i);
  return &i->second;
#endif
}

template <typename OrderedMapType>
void LruCacheBase<OrderedMapType>::set(Key const& key, Value value) {
#ifdef STAR_USE_RUST_LRU_CACHE
  Context<SB_LRU_SET> c(m_map, m_maxSize);
  c.key = &key;
  c.value = &value;
  c.execute();
#else
  auto i = m_map.find(key);
  if (i == m_map.end()) {
    m_map.add(key, std::move(value));
  } else {
    i->second = std::move(value);
    m_map.toBack(i);
  }
#endif
}

template <typename OrderedMapType>
bool LruCacheBase<OrderedMapType>::remove(Key const& key) {
#ifdef STAR_USE_RUST_LRU_CACHE
  Context<SB_LRU_REMOVE> c(m_map, m_maxSize);
  c.key = &key;
  return c.execute().value;
#else
  return m_map.remove(key);
#endif
}

template <typename OrderedMapType>
void LruCacheBase<OrderedMapType>::removeWhere(function<bool(Key const&, Value&)> filter) {
#ifdef STAR_USE_RUST_LRU_CACHE
  Context<SB_LRU_FILTER> c(m_map, m_maxSize);
  c.filter = &filter;
  c.execute();
#else
  eraseWhere(m_map, [&filter](auto& p) {
      return filter(p.first, p.second);
    });
#endif
}

template <typename OrderedMapType>
template <typename Producer>
auto LruCacheBase<OrderedMapType>::get(Key const& key, Producer producer) -> Value & {
#ifdef STAR_USE_RUST_LRU_CACHE
  Context<SB_LRU_GET> c(m_map, m_maxSize);
  c.key = &key;
  c.producer = &producer;
  c.produce = [](Context<SB_LRU_GET>& frame) -> uint32_t {
    auto& producer = *static_cast<Producer*>(frame.producer);
    // keep the braced pair and producer prvalue in one native full expression;
    // the continuation inserts before either temporary dies, even on failure.
    return frame.withPair({*frame.key, producer(*frame.key)});
  };
  c.execute();
  return *c.reference;
#else
  while (m_map.size() > m_maxSize - 1)
    m_map.removeFirst();

  auto i = m_map.find(key);
  if (i == m_map.end())
    i = m_map.insert({key, producer(key)}).first;
  else
    i = m_map.toBack(i);

  return i->second;
#endif
}

template <typename OrderedMapType>
void LruCacheBase<OrderedMapType>::clear() {
#ifdef STAR_USE_RUST_LRU_CACHE
  Context<SB_LRU_CLEAR> c(m_map, m_maxSize);
  c.execute();
#else
  m_map.clear();
#endif
}

}
