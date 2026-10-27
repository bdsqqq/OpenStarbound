#pragma once
#include "StarOrderedMap.hpp"
#include "StarBlockAllocator.hpp"
#include "host_api.h"
#include <exception>
#include <stdexcept>

namespace LruBoundary {
using namespace Star;
template <typename OrderedMapType>
class LruCacheBase {
public:
 typedef typename OrderedMapType::key_type Key;
 typedef typename OrderedMapType::mapped_type Value;
 typedef function<Value(Key const&)> ProducerFunction;
 LruCacheBase(size_t maxSize=256){Context c(*this,SB_LRU_CTOR);c.arg=maxSize;c.execute();}
 size_t maxSize()const{Context c(*this,SB_LRU_MAX);return c.execute().value;}
 void setMaxSize(size_t n){Context c(*this,SB_LRU_LIMIT);c.arg=n;c.execute();}
 size_t currentSize()const{Context c(*this,SB_LRU_SIZE);return c.execute().value;}
 // native prvalue leaves: never store a List in the ABI frame or move it out.
 List<Key> keys()const{Context c(*this,SB_LRU_KEYS);c.execute();return m_map.keys();}
 List<Value> values()const{Context c(*this,SB_LRU_VALUES);c.execute();return m_map.values();}
 Value* ptr(Key const& key){Context c(*this,SB_LRU_PTR);c.key=&key;c.execute();return c.reference;}
 void set(Key const& key,Value value){Context c(*this,SB_LRU_SET);c.key=&key;c.value=&value;c.execute();}
 bool remove(Key const& key){Context c(*this,SB_LRU_REMOVE);c.key=&key;return c.execute().value;}
 void removeWhere(function<bool(Key const&,Value&)> filter){Context c(*this,SB_LRU_FILTER);c.filter=&filter;c.execute();}
 template <typename Producer> Value& get(Key const& key,Producer producer){
  Context c(*this,SB_LRU_GET);c.key=&key;c.producer=&producer;
  c.produce=[](Context& x)->uint32_t{
   auto& producer=*static_cast<Producer*>(x.producer);
   // retain the original braced pair expression and full-expression scope.
   // the native pair and producer return temporary live through continuation.
   return x.withPair({*x.key,producer(*x.key)});
  };
  c.execute();return *c.reference;
 }
 void clear(){Context c(*this,SB_LRU_CLEAR);c.execute();}
private:
 OrderedMapType m_map;
 size_t m_maxSize;
 // no frame, iterator, callback, exception or counter is a cache data member.
 struct Context {
  using Iterator=typename OrderedMapType::iterator;
  using Pair=typename OrderedMapType::value_type;
  LruCacheBase& owner;uint32_t mode,stage=SB_LRU_ROOT;
  uint64_t arg=0;Key const* key=nullptr;Value* value=nullptr;
  Iterator* iterator=nullptr;Pair const* pair=nullptr;Value* reference=nullptr;
  function<bool(Key const&,Value&)>* filter=nullptr;
  void* producer=nullptr;uint32_t (*produce)(Context&)=nullptr;
  std::exception_ptr pending;
  Context(LruCacheBase const& c,uint32_t m):owner(const_cast<LruCacheBase&>(c)),mode(m){}
  uint32_t resume(uint32_t s){
   auto old=stage;stage=s;SbLruReply result{sizeof(SbLruReply),SB_LRU_VOID,0};
   auto status=sb_lru_run(mode,s,this,host,&result);stage=old;
   // the controller has returned: unwind the native owner, never its frames.
   // status-only return here would destroy pair/producer/iterators normally.
   if(status==1&&pending)std::rethrow_exception(pending);
   if(!status&&(result.size!=sizeof(SbLruReply)||result.tag!=SB_LRU_VOID||result.value))return 2;
   return status;
  }
  template <typename T> struct Borrow {
   T*& slot;
   Borrow(T*& slot,T& value):slot(slot){slot=&value;}
   ~Borrow(){slot=nullptr;}
  };
  uint32_t withPair(Pair const& p){Borrow<Pair const> guard(pair,p);return resume(SB_LRU_PAIR);}
  SbLruReply execute(){
   SbLruReply result{sizeof(SbLruReply),UINT32_MAX,0};
   auto status=sb_lru_run(mode,SB_LRU_ROOT,this,host,&result);
   if(status==1&&pending)std::rethrow_exception(pending);
   uint32_t tag=SB_LRU_VOID;
   switch(mode){case SB_LRU_MAX:case SB_LRU_SIZE:tag=SB_LRU_U64;break;
    case SB_LRU_REMOVE:tag=SB_LRU_BOOL;break;case SB_LRU_PTR:case SB_LRU_GET:tag=SB_LRU_REF;break;
    case SB_LRU_KEYS:tag=SB_LRU_KEY_LIST;break;case SB_LRU_VALUES:tag=SB_LRU_VALUE_LIST;break;}
   if(status||pending||result.size!=sizeof(SbLruReply)||result.tag!=tag||
      (tag==SB_LRU_BOOL&&result.value>1)||(tag!=SB_LRU_U64&&tag!=SB_LRU_BOOL&&result.value)||
      (mode==SB_LRU_GET&&!reference))throw std::logic_error("lru boundary protocol");
   return result;
  }
  static uint32_t host(void* opaque,SbLruRequest const* request,SbLruReply* out)noexcept{
   if(!opaque||!request||!out||request->size!=sizeof(SbLruRequest)||out->size!=sizeof(SbLruReply))return 2;
   auto& c=*static_cast<Context*>(opaque);
   if(c.pending)return 1;
   if(request->op!=SB_LRU_WRITE_MAX&&request->arg)return 2;
   *out={sizeof(SbLruReply),SB_LRU_VOID,0};
   auto& map=c.owner.m_map;
   try{
    switch(request->op){
     case SB_LRU_ARG:if(c.stage||!(c.mode==SB_LRU_CTOR||c.mode==SB_LRU_LIMIT))return 2;out->tag=SB_LRU_U64;out->value=c.arg;break;
     case SB_LRU_READ_MAX:if(c.stage)return 2;out->tag=SB_LRU_U64;out->value=c.owner.m_maxSize;break;
     case SB_LRU_WRITE_MAX:if(c.stage||!(c.mode==SB_LRU_CTOR||c.mode==SB_LRU_LIMIT)||!request->arg)return 2;c.owner.m_maxSize=request->arg;break;
     case SB_LRU_MAP_SIZE:if(c.stage)return 2;out->tag=SB_LRU_U64;out->value=map.size();break;
     case SB_LRU_REMOVE_FIRST:if(c.stage||!(c.mode==SB_LRU_CTOR||c.mode==SB_LRU_LIMIT||c.mode==SB_LRU_GET))return 2;map.removeFirst();break;
     case SB_LRU_FIND_SCOPE:{
      if(c.stage||!c.key||!(c.mode==SB_LRU_PTR||c.mode==SB_LRU_SET||c.mode==SB_LRU_GET))return 2;
      auto i=map.find(*c.key);Borrow<Iterator> guard(c.iterator,i);
      return c.resume(SB_LRU_FOUND);
     }
     case SB_LRU_FILTER_SCOPE:{
      if(c.stage||c.mode!=SB_LRU_FILTER||!c.filter)return 2;
      auto p=std::begin(map);Borrow<Iterator> guard(c.iterator,p);
      return c.resume(SB_LRU_TRAVERSE);
     }
     case SB_LRU_IS_END:if(!c.iterator||!(c.stage==SB_LRU_FOUND||c.stage==SB_LRU_TRAVERSE))return 2;out->tag=SB_LRU_BOOL;out->value=*c.iterator==map.end();break;
     case SB_LRU_PROMOTE_ASSIGN:if(c.stage!=SB_LRU_FOUND||!c.iterator||!(c.mode==SB_LRU_PTR||c.mode==SB_LRU_GET))return 2;*c.iterator=map.toBack(*c.iterator);break;
     case SB_LRU_PROMOTE_DISCARD:if(c.stage!=SB_LRU_FOUND||c.mode!=SB_LRU_SET||!c.iterator)return 2;map.toBack(*c.iterator);break;
     case SB_LRU_REFERENCE:if(c.stage!=SB_LRU_FOUND||!c.iterator||!(c.mode==SB_LRU_PTR||c.mode==SB_LRU_GET))return 2;c.reference=&(*c.iterator)->second;break;
     case SB_LRU_ADD:if(c.stage!=SB_LRU_FOUND||c.mode!=SB_LRU_SET||!c.key||!c.value)return 2;map.add(*c.key,std::move(*c.value));break;
     case SB_LRU_ASSIGN:if(c.stage!=SB_LRU_FOUND||c.mode!=SB_LRU_SET||!c.iterator||!c.value)return 2;(*c.iterator)->second=std::move(*c.value);break;
     case SB_LRU_REMOVE_KEY:if(c.stage||c.mode!=SB_LRU_REMOVE||!c.key)return 2;out->tag=SB_LRU_BOOL;out->value=map.remove(*c.key);break;
     case SB_LRU_PAIR_SCOPE:if(c.stage!=SB_LRU_FOUND||c.mode!=SB_LRU_GET||!c.produce)return 2;return c.produce(c);
     case SB_LRU_INSERT_PAIR:if(c.stage!=SB_LRU_PAIR||c.mode!=SB_LRU_GET||!c.pair||!c.iterator)return 2;*c.iterator=map.insert(*c.pair).first;break;
     case SB_LRU_PREDICATE:if(c.stage!=SB_LRU_TRAVERSE||!c.iterator||!c.filter)return 2;out->tag=SB_LRU_BOOL;out->value=(*c.filter)((*c.iterator)->first,(*c.iterator)->second);break;
     case SB_LRU_ERASE:if(c.stage!=SB_LRU_TRAVERSE||!c.iterator)return 2;*c.iterator=map.erase(*c.iterator);break;
     case SB_LRU_NEXT:if(c.stage!=SB_LRU_TRAVERSE||!c.iterator)return 2;++*c.iterator;break;
     case SB_LRU_MAP_CLEAR:if(c.stage||c.mode!=SB_LRU_CLEAR)return 2;map.clear();break;
     default:return 2;
    }
    return 0;
   }catch(...){c.pending=std::current_exception();return 1;}
  }
 };
};
template <typename Key,typename Value,typename Compare=std::less<Key>,typename Allocator=BlockAllocator<pair<Key const,Value>,1024>>
using LruCache=LruCacheBase<OrderedMap<Key,Value,Compare,Allocator>>;
template <typename Key,typename Value,typename Hash=Star::hash<Key>,typename Equals=std::equal_to<Key>,typename Allocator=BlockAllocator<pair<Key const,Value>,1024>>
using HashLruCache=LruCacheBase<OrderedHashMap<Key,Value,Hash,Equals,Allocator>>;
}
