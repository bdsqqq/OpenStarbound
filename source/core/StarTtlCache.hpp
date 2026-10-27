#pragma once

#include "StarLruCache.hpp"
#include "StarTime.hpp"
#include "StarRandom.hpp"
#ifdef STAR_USE_RUST_TTL_CACHE
#include "StarTtlCacheHost.hpp"
#endif

namespace Star {

template <typename LruCacheType>
class TtlCacheBase {
public:
  typedef typename LruCacheType::Key Key;
  typedef typename LruCacheType::Value::second_type Value;

  typedef function<Value(Key const&)> ProducerFunction;

  TtlCacheBase(int64_t timeToLive = 10000, int timeSmear = 1000, size_t maxSize = NPos, bool ttlUpdateEnabled = true);

  int64_t timeToLive() const;
  void setTimeToLive(int64_t timeToLive);

  int timeSmear() const;
  void setTimeSmear(int timeSmear);

  // If a max size is set, this cache also acts as an LRU cache with the given
  // maximum size.
  size_t maxSize() const;
  void setMaxSize(size_t maxSize = NPos);

  size_t currentSize() const;

  List<Key> keys() const;
  List<Value> values() const;

  // If ttlUpdateEnabled is false, then the time to live for entries will not
  // be updated on access.
  bool ttlUpdateEnabled() const;
  void setTtlUpdateEnabled(bool enabled);

  // If the value is in the cache, returns it and updates the access time,
  // otherwise returns nullptr.
  Value* ptr(Key const& key);

  // Put the given value into the cache.
  void set(Key const& key, Value value);
  // Removes the given value from the cache.  If found and removed, returns
  // true.
  bool remove(Key const& key);

  // Remove all key / value pairs matching a filter.
  void removeWhere(function<bool(Key const&, Value&)> filter);

  // If the value for the key is not found in the cache, produce it with the
  // given producer.  Producer should take the key as an argument and return
  // the Value.
  template <typename Producer>
  Value& get(Key const& key, Producer producer);

  void clear();

  // Cleanup any cached entries that are older than their time to live, if the
  // refreshFilter is given, things that match the refreshFilter instead have
  // their ttl refreshed rather than being removed.
  void cleanup(function<bool(Key const&, Value const&)> refreshFilter = {});

private:
  friend struct TtlCacheLabAccess;
#ifdef STAR_USE_RUST_TTL_CACHE
 // Types and stack frames only: original four fields and implicit lifecycle.
 struct Clock {
  static int64_t now(){return Time::monotonicMilliseconds();}
  static auto random(int lo,int hi){return Random::randInt(lo,hi);}
 };
 template<uint32_t Mode> using Context=TtlCacheRust::Context<LruCacheType,Mode,Clock>;
 template<uint32_t Mode> Context<Mode> frame() const {
  auto& self=*const_cast<TtlCacheBase*>(this);
  return {self.m_cache,self.m_timeToLive,self.m_timeSmear,self.m_ttlUpdateEnabled};
 }
#endif
  LruCacheType m_cache;
  int64_t m_timeToLive;
  int m_timeSmear;
  bool m_ttlUpdateEnabled;
};

template <typename Key, typename Value, typename Compare = std::less<Key>, typename Allocator = BlockAllocator<pair<Key const, pair<int64_t, Value>>, 1024>>
using TtlCache = TtlCacheBase<LruCache<Key, pair<int64_t, Value>, Compare, Allocator>>;

template <typename Key, typename Value, typename Hash = Star::hash<Key>, typename Equals = std::equal_to<Key>, typename Allocator = BlockAllocator<pair<Key const, pair<int64_t, Value>>, 1024>>
using HashTtlCache = TtlCacheBase<HashLruCache<Key, pair<int64_t, Value>, Hash, Equals, Allocator>>;

template <typename LruCacheType>
TtlCacheBase<LruCacheType>::TtlCacheBase(int64_t timeToLive, int timeSmear, size_t maxSize, bool ttlUpdateEnabled) {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_CTOR>();c.args[0]=timeToLive;c.args[1]=static_cast<int64_t>(timeSmear);c.args[2]=maxSize;c.args[3]=ttlUpdateEnabled;c.execute();
#else
  m_cache.setMaxSize(maxSize);
  m_timeToLive = timeToLive;
  m_timeSmear = timeSmear;
  m_ttlUpdateEnabled = ttlUpdateEnabled;
#endif
}

template <typename LruCacheType>
int64_t TtlCacheBase<LruCacheType>::timeToLive() const {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_TTL>();return static_cast<int64_t>(c.execute().value);
#else
  return m_timeToLive;
#endif
}

template <typename LruCacheType>
void TtlCacheBase<LruCacheType>::setTimeToLive(int64_t timeToLive) {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_SET_TTL>();c.args[0]=timeToLive;c.execute();
#else
  m_timeToLive = timeToLive;
#endif
}

template <typename LruCacheType>
int TtlCacheBase<LruCacheType>::timeSmear() const {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_SMEAR>();return static_cast<int>(c.execute().value);
#else
  return m_timeSmear;
#endif
}

template <typename LruCacheType>
void TtlCacheBase<LruCacheType>::setTimeSmear(int timeSmear) {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_SET_SMEAR>();c.args[0]=static_cast<int64_t>(timeSmear);c.execute();
#else
  m_timeSmear = timeSmear;
#endif
}

template <typename LruCacheType>
bool TtlCacheBase<LruCacheType>::ttlUpdateEnabled() const {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_UPDATE>();return c.execute().value;
#else
  return m_ttlUpdateEnabled;
#endif
}

template <typename LruCacheType>
size_t TtlCacheBase<LruCacheType>::maxSize() const {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_MAX>();return c.execute().value;
#else
  return m_cache.maxSize();
#endif
}

template <typename LruCacheType>
void TtlCacheBase<LruCacheType>::setMaxSize(size_t maxSize) {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_SET_MAX>();c.args[0]=maxSize;c.execute();
#else
  m_cache.setMaxSize(maxSize);
#endif
}

template <typename LruCacheType>
size_t TtlCacheBase<LruCacheType>::currentSize() const {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_SIZE>();return c.execute().value;
#else
  return m_cache.currentSize();
#endif
}

template <typename LruCacheType>
auto TtlCacheBase<LruCacheType>::keys() const -> List<Key> {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_KEYS>();c.execute();return m_cache.keys();
#else
  return m_cache.keys();
#endif
}

template <typename LruCacheType>
auto TtlCacheBase<LruCacheType>::values() const -> List<Value> {
#ifdef STAR_USE_RUST_TTL_CACHE
  List<Value> values;
   auto c=frame<SB_TTL_VALUES>();c.result=&values;c.execute();
   return values;
#else
  List<Value> values;
  for (auto& p : m_cache.values())
    values.append(std::move(p.second));
  return values;
#endif
}

template <typename LruCacheType>
void TtlCacheBase<LruCacheType>::setTtlUpdateEnabled(bool enabled) {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_SET_UPDATE>();c.args[0]=enabled;c.execute();
#else
  m_ttlUpdateEnabled = enabled;
#endif
}

template <typename LruCacheType>
auto TtlCacheBase<LruCacheType>::ptr(Key const& key) -> Value * {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_PTR>();c.key=&key;c.execute();return c.value;
#else
  if (auto p = m_cache.ptr(key)) {
    if (m_ttlUpdateEnabled)
      p->first = Time::monotonicMilliseconds() + Random::randInt(-m_timeSmear, m_timeSmear);
    return &p->second;
  }
  return nullptr;
#endif
}

template <typename LruCacheType>
void TtlCacheBase<LruCacheType>::set(Key const& key, Value value) {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_SET>();c.key=&key;c.value=&value;c.execute();
#else
  m_cache.set(key, make_pair(Time::monotonicMilliseconds() + Random::randInt(-m_timeSmear, m_timeSmear), value));
#endif
}

template <typename LruCacheType>
bool TtlCacheBase<LruCacheType>::remove(Key const& key) {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_REMOVE>();c.key=&key;return c.execute().value;
#else
  return m_cache.remove(key);
#endif
}

template <typename LruCacheType>
void TtlCacheBase<LruCacheType>::removeWhere(function<bool(Key const&, Value&)> filter) {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_FILTER>();c.filter=&filter;c.execute();
#else
  m_cache.removeWhere([&filter](auto const& key, auto& value) { return filter(key, value.second); });
#endif
}

template <typename LruCacheType>
template <typename Producer>
auto TtlCacheBase<LruCacheType>::get(Key const& key, Producer producer) -> Value & {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_GET>();c.key=&key;c.producer=&producer;
   c.getExpression=[](Context<SB_TTL_GET>& c){
    auto& producer=*static_cast<Producer*>(c.producer);
    auto& value=c.cache.get(*c.key,[producer](Key const& key){
     return pair<int64_t,Value>(0,producer(key));
    });
    // The original full expression ends above, BEFORE the controller sees stamp.
    c.pair=&value;
   };
   c.execute();return *c.value;
#else
  auto& value = m_cache.get(key, [producer](Key const& key) {
      return pair<int64_t, Value>(0, producer(key));
    });
  if (value.first == 0 || m_ttlUpdateEnabled)
    value.first = Time::monotonicMilliseconds() + Random::randInt(-m_timeSmear, m_timeSmear);
  return value.second;
#endif
}

template <typename LruCacheType>
void TtlCacheBase<LruCacheType>::clear() {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_CLEAR>();c.execute();
#else
  m_cache.clear();
#endif
}

template <typename LruCacheType>
void TtlCacheBase<LruCacheType>::cleanup(function<bool(Key const&, Value const&)> refreshFilter) {
#ifdef STAR_USE_RUST_TTL_CACHE
  auto c=frame<SB_TTL_CLEANUP>();c.refresh=&refreshFilter;c.execute();
#else
  int64_t currentTime = Time::monotonicMilliseconds();
  m_cache.removeWhere([&](auto const& key, auto& value) {
      if (refreshFilter && refreshFilter(key, value.second)) {
        value.first = currentTime;
      } else {
        if (currentTime - value.first > m_timeToLive)
          return true;
      }
      return false;
    });
#endif
}

}
