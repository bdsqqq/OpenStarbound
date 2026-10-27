// Intentionally re-includable for the explicit scripted Time/Random calibration.
#include "StarLruCache.hpp"
#include "StarTime.hpp"
#include "StarRandom.hpp"
#include "host.hpp"
namespace Star {
template<typename LruCacheType> class BoundaryTtlCacheBase {
public:
 typedef typename LruCacheType::Key Key;
 typedef typename LruCacheType::Value::second_type Value;
 typedef function<Value(Key const&)> ProducerFunction;
 BoundaryTtlCacheBase(int64_t timeToLive=10000,int timeSmear=1000,size_t maxSize=NPos,bool ttlUpdateEnabled=true);
 int64_t timeToLive() const;void setTimeToLive(int64_t timeToLive);
 int timeSmear() const;void setTimeSmear(int timeSmear);
 size_t maxSize() const;void setMaxSize(size_t maxSize=NPos);
 size_t currentSize() const;List<Key> keys() const;List<Value> values() const;
 bool ttlUpdateEnabled() const;void setTtlUpdateEnabled(bool enabled);
 Value* ptr(Key const& key);void set(Key const& key,Value value);bool remove(Key const& key);
 void removeWhere(function<bool(Key const&,Value&)> filter);
 template<typename Producer> Value& get(Key const& key,Producer producer);
 void clear();void cleanup(function<bool(Key const&,Value const&)> refreshFilter={});
private:
 LruCacheType m_cache;
 int64_t m_timeToLive;
 int m_timeSmear;
 bool m_ttlUpdateEnabled;
 // Types and stack frames only: original four fields and implicit lifecycle.
 struct Clock {
  static int64_t now(){return Time::monotonicMilliseconds();}
  static auto random(int lo,int hi){return Random::randInt(lo,hi);}
 };
 template<uint32_t Mode> using Context=TtlBoundaryHost::Context<LruCacheType,Mode,Clock>;
 template<uint32_t Mode> Context<Mode> frame() const {
  auto& self=*const_cast<BoundaryTtlCacheBase*>(this);
  return {self.m_cache,self.m_timeToLive,self.m_timeSmear,self.m_ttlUpdateEnabled};
 }
};
template<typename Key,typename Value,typename Compare=std::less<Key>,typename Allocator=BlockAllocator<pair<Key const,pair<int64_t,Value>>,1024>>
using BoundaryTtlCache=BoundaryTtlCacheBase<LruCache<Key,pair<int64_t,Value>,Compare,Allocator>>;
template<typename Key,typename Value,typename Hash=Star::hash<Key>,typename Equals=std::equal_to<Key>,typename Allocator=BlockAllocator<pair<Key const,pair<int64_t,Value>>,1024>>
using BoundaryHashTtlCache=BoundaryTtlCacheBase<HashLruCache<Key,pair<int64_t,Value>,Hash,Equals,Allocator>>;

template<typename L> BoundaryTtlCacheBase<L>::BoundaryTtlCacheBase(int64_t timeToLive,int timeSmear,size_t maxSize,bool ttlUpdateEnabled){
 auto c=frame<SB_TTL_CTOR>();c.args[0]=timeToLive;c.args[1]=static_cast<int64_t>(timeSmear);c.args[2]=maxSize;c.args[3]=ttlUpdateEnabled;c.execute();
}
template<typename L> int64_t BoundaryTtlCacheBase<L>::timeToLive() const {auto c=frame<SB_TTL_TTL>();return static_cast<int64_t>(c.execute().value);}
template<typename L> void BoundaryTtlCacheBase<L>::setTimeToLive(int64_t timeToLive){auto c=frame<SB_TTL_SET_TTL>();c.args[0]=timeToLive;c.execute();}
template<typename L> int BoundaryTtlCacheBase<L>::timeSmear() const {auto c=frame<SB_TTL_SMEAR>();return static_cast<int>(c.execute().value);}
template<typename L> void BoundaryTtlCacheBase<L>::setTimeSmear(int timeSmear){auto c=frame<SB_TTL_SET_SMEAR>();c.args[0]=static_cast<int64_t>(timeSmear);c.execute();}
template<typename L> size_t BoundaryTtlCacheBase<L>::maxSize() const {auto c=frame<SB_TTL_MAX>();return c.execute().value;}
template<typename L> void BoundaryTtlCacheBase<L>::setMaxSize(size_t maxSize){auto c=frame<SB_TTL_SET_MAX>();c.args[0]=maxSize;c.execute();}
template<typename L> size_t BoundaryTtlCacheBase<L>::currentSize() const {auto c=frame<SB_TTL_SIZE>();return c.execute().value;}
template<typename L> auto BoundaryTtlCacheBase<L>::keys() const -> List<Key>{auto c=frame<SB_TTL_KEYS>();c.execute();return m_cache.keys();}
template<typename L> auto BoundaryTtlCacheBase<L>::values() const -> List<Value>{
 List<Value> values;
 auto c=frame<SB_TTL_VALUES>();c.result=&values;c.execute();
 return values;
}
template<typename L> bool BoundaryTtlCacheBase<L>::ttlUpdateEnabled() const {auto c=frame<SB_TTL_UPDATE>();return c.execute().value;}
template<typename L> void BoundaryTtlCacheBase<L>::setTtlUpdateEnabled(bool enabled){auto c=frame<SB_TTL_SET_UPDATE>();c.args[0]=enabled;c.execute();}
template<typename L> auto BoundaryTtlCacheBase<L>::ptr(Key const& key) -> Value* {
 auto c=frame<SB_TTL_PTR>();c.key=&key;c.execute();return c.value;
}
template<typename L> void BoundaryTtlCacheBase<L>::set(Key const& key,Value value){auto c=frame<SB_TTL_SET>();c.key=&key;c.value=&value;c.execute();}
template<typename L> bool BoundaryTtlCacheBase<L>::remove(Key const& key){auto c=frame<SB_TTL_REMOVE>();c.key=&key;return c.execute().value;}
template<typename L> void BoundaryTtlCacheBase<L>::removeWhere(function<bool(Key const&,Value&)> filter){auto c=frame<SB_TTL_FILTER>();c.filter=&filter;c.execute();}
template<typename L> template<typename Producer> auto BoundaryTtlCacheBase<L>::get(Key const& key,Producer producer) -> Value& {
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
}
template<typename L> void BoundaryTtlCacheBase<L>::clear(){auto c=frame<SB_TTL_CLEAR>();c.execute();}
template<typename L> void BoundaryTtlCacheBase<L>::cleanup(function<bool(Key const&,Value const&)> refreshFilter){auto c=frame<SB_TTL_CLEANUP>();c.refresh=&refreshFilter;c.execute();}
}
