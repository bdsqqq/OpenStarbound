#pragma once
#include "StarRustTtlCache.h"
#include <exception>
#include <stdexcept>
#include <type_traits>
#include <cstddef>
#include <utility>

static_assert(sizeof(SbTtlRequest)==24 && alignof(SbTtlRequest)==8);
static_assert(sizeof(SbTtlReply)==24 && alignof(SbTtlReply)==8);
static_assert(offsetof(SbTtlRequest,arg)==16 && offsetof(SbTtlReply,value)==16);
static_assert(std::is_standard_layout_v<SbTtlRequest> && std::is_trivially_copyable_v<SbTtlReply>);
namespace Star::TtlCacheRust {
inline SbTtlReply reply(uint32_t tag=SB_TTL_VOID,uint64_t value=0) {return {24,1,tag,0,value};}
inline bool valid(SbTtlReply const& r) {return r.size==24 && r.version==1 && !r.reserved && r.tag<=SB_TTL_VALUE_LIST && (r.tag!=SB_TTL_BOOL || r.value<=1) && (r.tag!=SB_TTL_VOID || !r.value) && (r.tag<SB_TTL_REF || !r.value);}

template<class Lru,uint32_t Mode,class Clock> struct Context {
 using Key=typename Lru::Key;using Pair=typename Lru::Value;using Value=typename Pair::second_type;
 using Range=decltype(std::declval<Lru const&>().values());
 using Iterator=decltype(std::declval<Range&>().begin());
 Lru& cache;int64_t& ttl;int& smear;bool& update;
 uint64_t args[4]={};Key const* key=nullptr;Value* value=nullptr;Pair* pair=nullptr;
 List<Value>* result=nullptr;Iterator* cursor=nullptr;Iterator* end=nullptr;
 function<bool(Key const&,Value&)>* filter=nullptr;
 function<bool(Key const&,Value const&)>* refresh=nullptr;
 Key const* callbackKey=nullptr;int64_t captured=0;
 void* producer=nullptr;void (*getExpression)(Context&)=nullptr;
 std::exception_ptr pending;
 uint32_t stage=SB_TTL_ROOT;
 template<class T> struct Borrow {T*& slot;T* old;Borrow(T*& s,T& object):slot(s),old(s){slot=&object;}~Borrow(){slot=old;}};
 Context(Lru& c,int64_t& t,int& s,bool& u):cache(c),ttl(t),smear(s),update(u){}
 SbTtlReply execute(uint32_t stage=SB_TTL_ROOT) {
  auto previous=this->stage;this->stage=stage;
  SbTtlReply out=reply();auto status=sb_ttl_run(Mode,stage,this,&host,&out);
  this->stage=previous;
  // Nested calls rethrow HERE, while the original native owner is still alive.
  if(status==SB_TTL_EXCEPTION && pending)std::rethrow_exception(pending);
  if(status!=SB_TTL_OK || !valid(out))throw std::logic_error("Rust TtlCache ABI protocol");
  uint32_t tag=SB_TTL_VOID;
  if(stage!=SB_TTL_ROOT)tag=SB_TTL_BOOL;
  else if constexpr(Mode==SB_TTL_TTL || Mode==SB_TTL_SMEAR)tag=SB_TTL_I64;
  else if constexpr(Mode==SB_TTL_MAX || Mode==SB_TTL_SIZE)tag=SB_TTL_U64;
  else if constexpr(Mode==SB_TTL_UPDATE || Mode==SB_TTL_REMOVE)tag=SB_TTL_BOOL;
  else if constexpr(Mode==SB_TTL_PTR || Mode==SB_TTL_GET)tag=SB_TTL_REF;
  else if constexpr(Mode==SB_TTL_KEYS)tag=SB_TTL_KEY_LIST;
  else if constexpr(Mode==SB_TTL_VALUES)tag=SB_TTL_VALUE_LIST;
  // VALUE_LOOP is a void continuation, predicates alone return bool.
  if(stage==SB_TTL_VALUE_LOOP)tag=SB_TTL_VOID;
  if(out.tag!=tag || ((tag==SB_TTL_REF || tag==SB_TTL_KEY_LIST || tag==SB_TTL_VALUE_LIST) && out.value))throw std::logic_error("Rust TtlCache ABI result tag");
  if constexpr(Mode==SB_TTL_GET)if(!value)throw std::logic_error("Rust TtlCache ABI missing borrow");
  return out;
 }
 static uint32_t host(void* opaque,SbTtlRequest const* q,SbTtlReply* out) noexcept {
  if(!opaque || !q || !out || q->size!=24 || q->version!=1 || q->reserved || q->op<1 || q->op>31 || out->size!=24 || out->version!=1 || out->reserved)return SB_TTL_INVALID;
  // Rust initializes leaf destinations with this exact sentinel. Other incoming
  // tags must be canonical before any native field or dependency is mutated.
  if(!valid(*out) && !(out->tag==UINT32_MAX && out->value==UINT64_MAX))return SB_TTL_INVALID;
  if(q->op!=SB_TTL_ARG && q->op!=SB_TTL_WRITE_TTL && q->op!=SB_TTL_WRITE_SMEAR && q->op!=SB_TTL_WRITE_UPDATE && q->op!=SB_TTL_LRU_LIMIT && q->op!=SB_TTL_PAIR_STAMP_WRITE && q->arg)return SB_TTL_INVALID;
  auto& c=*static_cast<Context*>(opaque);SbTtlReply r=reply();
  if(c.pending)return SB_TTL_EXCEPTION;
  // Stages are capabilities: malformed control calls cannot dereference a
  // borrower outside the exact native continuation that owns it.
  if(c.stage==SB_TTL_VALUE_LOOP){if(q->op<SB_TTL_VALUES_END || q->op>SB_TTL_VALUES_NEXT || !c.cursor || !c.end || !c.result)return SB_TTL_INVALID;}
  else if(c.stage==SB_TTL_FILTER_PREDICATE){if(q->op!=SB_TTL_CALL_FILTER || !c.filter || !c.callbackKey || !c.pair)return SB_TTL_INVALID;}
  else if(c.stage==SB_TTL_CLEANUP_PREDICATE){if(q->op!=SB_TTL_READ_TTL && q->op!=SB_TTL_PAIR_STAMP_READ && (q->op<SB_TTL_FILTER_PRESENT || q->op>SB_TTL_PAIR_STAMP_WRITE))return SB_TTL_INVALID;if(!c.refresh || !c.callbackKey || !c.pair)return SB_TTL_INVALID;}
  else if(c.stage!=SB_TTL_ROOT)return SB_TTL_INVALID;
  else if(q->op==SB_TTL_VALUES_END || q->op==SB_TTL_VALUES_APPEND || q->op==SB_TTL_VALUES_NEXT || q->op==SB_TTL_CALL_FILTER || q->op>=SB_TTL_FILTER_PRESENT || (Mode==SB_TTL_CLEANUP && (q->op==SB_TTL_READ_TTL || q->op==SB_TTL_PAIR_STAMP_READ)))return SB_TTL_INVALID;
  if((q->op==SB_TTL_LRU_PTR || q->op==SB_TTL_SET_EXPRESSION || q->op==SB_TTL_GET_EXPRESSION || q->op==SB_TTL_LRU_REMOVE) && !c.key)return SB_TTL_INVALID;
  if(q->op==SB_TTL_SET_EXPRESSION && !c.value)return SB_TTL_INVALID;
  if(q->op==SB_TTL_GET_EXPRESSION && !c.getExpression)return SB_TTL_INVALID;
  if((q->op==SB_TTL_PAIR_STAMP_READ || q->op==SB_TTL_PAIR_STAMP_NATIVE || q->op==SB_TTL_PAIR_VALUE_BORROW || q->op==SB_TTL_PAIR_STAMP_WRITE) && !c.pair)return SB_TTL_INVALID;
  if(q->op==SB_TTL_VALUES_SCOPE && !c.result)return SB_TTL_INVALID;
  if(q->op==SB_TTL_FILTER_SCOPE && !c.filter)return SB_TTL_INVALID;
  if(q->op==SB_TTL_CLEANUP_SCOPE && !c.refresh)return SB_TTL_INVALID;
  try {
   switch(q->op) {
   case SB_TTL_ARG:
    if constexpr(Mode==SB_TTL_CTOR) {if(q->arg>=4)return SB_TTL_INVALID;r=reply(q->arg<2?SB_TTL_I64:q->arg==2?SB_TTL_U64:SB_TTL_BOOL,c.args[q->arg]);break;}
    else if constexpr(Mode==SB_TTL_SET_TTL || Mode==SB_TTL_SET_SMEAR || Mode==SB_TTL_SET_MAX || Mode==SB_TTL_SET_UPDATE) {if(q->arg)return SB_TTL_INVALID;r=reply(Mode==SB_TTL_SET_MAX?SB_TTL_U64:Mode==SB_TTL_SET_UPDATE?SB_TTL_BOOL:SB_TTL_I64,c.args[0]);break;}else return SB_TTL_INVALID;
   case SB_TTL_READ_TTL: if constexpr(Mode==SB_TTL_TTL || Mode==SB_TTL_CLEANUP){r=reply(SB_TTL_I64,c.ttl);break;}else return SB_TTL_INVALID;
   case SB_TTL_WRITE_TTL: if constexpr(Mode==SB_TTL_CTOR || Mode==SB_TTL_SET_TTL){c.ttl=static_cast<int64_t>(q->arg);break;}else return SB_TTL_INVALID;
   case SB_TTL_READ_SMEAR: if constexpr(Mode==SB_TTL_SMEAR){r=reply(SB_TTL_I64,static_cast<int64_t>(c.smear));break;}else return SB_TTL_INVALID;
   case SB_TTL_WRITE_SMEAR: if constexpr(Mode==SB_TTL_CTOR || Mode==SB_TTL_SET_SMEAR){c.smear=static_cast<int>(q->arg);break;}else return SB_TTL_INVALID;
   case SB_TTL_READ_UPDATE: if constexpr(Mode==SB_TTL_UPDATE || Mode==SB_TTL_PTR || Mode==SB_TTL_GET){r=reply(SB_TTL_BOOL,c.update);break;}else return SB_TTL_INVALID;
   case SB_TTL_WRITE_UPDATE: if constexpr(Mode==SB_TTL_CTOR || Mode==SB_TTL_SET_UPDATE){if(q->arg>1)return SB_TTL_INVALID;c.update=q->arg;break;}else return SB_TTL_INVALID;
   case SB_TTL_LRU_MAX: if constexpr(Mode==SB_TTL_MAX){r=reply(SB_TTL_U64,std::as_const(c.cache).maxSize());break;}else return SB_TTL_INVALID;
   case SB_TTL_LRU_LIMIT: if constexpr(Mode==SB_TTL_CTOR || Mode==SB_TTL_SET_MAX){c.cache.setMaxSize(q->arg);break;}else return SB_TTL_INVALID;
   case SB_TTL_LRU_SIZE: if constexpr(Mode==SB_TTL_SIZE){r=reply(SB_TTL_U64,std::as_const(c.cache).currentSize());break;}else return SB_TTL_INVALID;
   case SB_TTL_LRU_PTR: if constexpr(Mode==SB_TTL_PTR){c.pair=c.cache.ptr(*c.key);break;}else return SB_TTL_INVALID;
   case SB_TTL_PAIR_PRESENT: if constexpr(Mode==SB_TTL_PTR){r=reply(SB_TTL_BOOL,c.pair!=nullptr);break;}else return SB_TTL_INVALID;
   case SB_TTL_PAIR_STAMP_READ: if constexpr(Mode==SB_TTL_GET || Mode==SB_TTL_CLEANUP){r=reply(SB_TTL_I64,c.pair->first);break;}else return SB_TTL_INVALID;
   case SB_TTL_PAIR_STAMP_NATIVE: if constexpr(Mode==SB_TTL_PTR || Mode==SB_TTL_GET){c.pair->first=Clock::now()+Clock::random(-c.smear,c.smear);break;}else return SB_TTL_INVALID;
   case SB_TTL_PAIR_VALUE_BORROW: if constexpr(Mode==SB_TTL_PTR || Mode==SB_TTL_GET){c.value=&c.pair->second;break;}else return SB_TTL_INVALID;
   case SB_TTL_SET_EXPRESSION: if constexpr(Mode==SB_TTL_SET){c.cache.set(*c.key,make_pair(Clock::now()+Clock::random(-c.smear,c.smear),*c.value));break;}else return SB_TTL_INVALID;
   case SB_TTL_GET_EXPRESSION: if constexpr(Mode==SB_TTL_GET){c.getExpression(c);break;}else return SB_TTL_INVALID;
   case SB_TTL_LRU_REMOVE: if constexpr(Mode==SB_TTL_REMOVE){r=reply(SB_TTL_BOOL,c.cache.remove(*c.key));break;}else return SB_TTL_INVALID;
   case SB_TTL_LRU_CLEAR: if constexpr(Mode==SB_TTL_CLEAR){c.cache.clear();break;}else return SB_TTL_INVALID;
   case SB_TTL_VALUES_SCOPE: if constexpr(Mode==SB_TTL_VALUES){
    // This block is the original for-range lifetime; result remains in values().
    auto&& range=std::as_const(c.cache).values();auto begin=range.begin();auto end=range.end();
    Borrow<Iterator> cursor(c.cursor,begin),last(c.end,end);c.execute(SB_TTL_VALUE_LOOP);break;
   }else return SB_TTL_INVALID;
   case SB_TTL_VALUES_END: if constexpr(Mode==SB_TTL_VALUES){r=reply(SB_TTL_BOOL,*c.cursor==*c.end);break;}else return SB_TTL_INVALID;
   case SB_TTL_VALUES_APPEND: if constexpr(Mode==SB_TTL_VALUES){auto& p=**c.cursor;c.result->append(std::move(p.second));break;}else return SB_TTL_INVALID;
   case SB_TTL_VALUES_NEXT: if constexpr(Mode==SB_TTL_VALUES){++*c.cursor;break;}else return SB_TTL_INVALID;
   case SB_TTL_FILTER_SCOPE: if constexpr(Mode==SB_TTL_FILTER){
    c.cache.removeWhere([&c](auto const& key,auto& value){Borrow<Key const> k(c.callbackKey,key);Borrow<Pair> p(c.pair,value);return bool(c.execute(SB_TTL_FILTER_PREDICATE).value);});break;
   }else return SB_TTL_INVALID;
   case SB_TTL_CALL_FILTER: if constexpr(Mode==SB_TTL_FILTER){r=reply(SB_TTL_BOOL,(*c.filter)(*c.callbackKey,c.pair->second));break;}else return SB_TTL_INVALID;
   case SB_TTL_TIME_ONCE: if constexpr(Mode==SB_TTL_CLEANUP){c.captured=Clock::now();break;}else return SB_TTL_INVALID;
   case SB_TTL_CLEANUP_SCOPE: if constexpr(Mode==SB_TTL_CLEANUP){
    c.cache.removeWhere([&c](auto const& key,auto& value){Borrow<Key const> k(c.callbackKey,key);Borrow<Pair> p(c.pair,value);return bool(c.execute(SB_TTL_CLEANUP_PREDICATE).value);});break;
   }else return SB_TTL_INVALID;
   case SB_TTL_FILTER_PRESENT: if constexpr(Mode==SB_TTL_CLEANUP){r=reply(SB_TTL_BOOL,bool(*c.refresh));break;}else return SB_TTL_INVALID;
   case SB_TTL_CALL_REFRESH: if constexpr(Mode==SB_TTL_CLEANUP){r=reply(SB_TTL_BOOL,(*c.refresh)(*c.callbackKey,c.pair->second));break;}else return SB_TTL_INVALID;
   case SB_TTL_READ_CAPTURED_TIME: if constexpr(Mode==SB_TTL_CLEANUP){r=reply(SB_TTL_I64,c.captured);break;}else return SB_TTL_INVALID;
   case SB_TTL_PAIR_STAMP_WRITE: if constexpr(Mode==SB_TTL_CLEANUP){c.pair->first=static_cast<int64_t>(q->arg);break;}else return SB_TTL_INVALID;
   default:return SB_TTL_INVALID;
   }
   *out=r;return SB_TTL_OK;
  }catch(...){c.pending=std::current_exception();return SB_TTL_EXCEPTION;}
 }
};
}
