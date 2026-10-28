#pragma once
#include "StarRustWeightedPool.h"
#include <cstring>
#include <exception>
#include <stdexcept>
#include <type_traits>
namespace Star::RustWeightedPoolDetail {
// Match range-for's ADL-only fallback; std::begin would lose private friend
// access and could introduce a competing member-based overload.
namespace Adl {
void begin()=delete; void end()=delete;
template<class C> auto first(C& c)->decltype(begin(c)){return begin(c);}
template<class C> auto last(C& c)->decltype(end(c)){return end(c);}
}
enum class CursorPhase { condition, value, next, ended };
inline uint64_t bits(double x){uint64_t b;std::memcpy(&b,&x,8);return b;}
inline double number(uint64_t b){double x;std::memcpy(&x,&b,8);return x;}
inline SbWpReply reply(uint32_t tag=SB_WP_VOID,uint64_t value=0){return {24,1,tag,0,value};}
inline bool canonical(SbWpReply const& r){return r.size==24&&r.version==1&&!r.reserved&&r.tag<=SB_WP_ITEM_RESULT&&(!(r.tag==SB_WP_VOID||r.tag==SB_WP_BORROW||r.tag==SB_WP_DEFAULT_ITEM)||!r.value)&&(r.tag!=SB_WP_BOOL||r.value<=1);}
struct Frame {
 using Allowed=bool(*)(void*,uint32_t,uint64_t);
 using Leaf=SbWpReply(*)(void*,uint32_t,uint64_t);
 Allowed allowed=nullptr;
 Leaf leaf=nullptr;
 void* payload=nullptr;
 Frame()=default;
 Frame(Frame const&)=delete;
 Frame(Frame&&)=delete;
 Frame& operator=(Frame const&)=delete;
 Frame& operator=(Frame&&)=delete;
 // The ABI context is a real base pointer, not an assumed derived layout.
 Frame* context() noexcept{return this;}
 std::exception_ptr error;
 bool borrowReturned=false;
 bool hasBorrowCapability(SbWpReply const& r)const{return r.tag!=SB_WP_BORROW||borrowReturned;}
 static uint32_t host(void* c,SbWpRequest const* q,SbWpReply* r) noexcept {
  if(!c||!q||!r)return SB_WP_INVALID;
  auto& f=*static_cast<Frame*>(c);
  // validate both incoming envelopes before a native object can be touched.
  if(q->size!=24||q->version!=1||q->reserved||!q->op||q->op>28||r->size!=24||r->version!=1||r->reserved)return SB_WP_INVALID;
  bool destination=(r->tag==SB_WP_VOID&&!r->value)||(r->tag==UINT32_MAX&&r->value==UINT64_MAX);
  if(!destination||!f.allowed||!f.leaf)return SB_WP_INVALID;
  if(f.error)return SB_WP_EXCEPTION;
  try {if(!f.allowed(f.payload,q->op,q->arg))return SB_WP_INVALID;auto v=f.leaf(f.payload,q->op,q->arg);if(!canonical(v))return SB_WP_INVALID;if(v.tag==SB_WP_BORROW)f.borrowReturned=true;*r=v;return SB_WP_OK;}
  catch(...){f.error=std::current_exception();return SB_WP_EXCEPTION;}
 }
 SbWpReply run(uint32_t mode,uint32_t stage=0){auto r=reply();auto status=sb_wp_run(mode,stage,this,host,&r);if(error)std::rethrow_exception(error);uint32_t expected=stage?SB_WP_VOID:(mode<=3?SB_WP_VOID:mode==4||mode==6||mode==8?SB_WP_BORROW:mode==7||mode==15||mode==16||mode==17?SB_WP_F64:mode==9?SB_WP_BOOL:SB_WP_U64);bool selection=!stage&&mode>=10&&mode<=12;bool tagOk=selection?(r.tag==SB_WP_DEFAULT_ITEM||r.tag==SB_WP_ITEM_RESULT):r.tag==expected;if(status!=SB_WP_OK||!canonical(r)||!tagOk||!hasBorrowCapability(r))throw std::runtime_error("weighted boundary protocol");return r;}
};
// Reference/pointer captures stay inline; immovability keeps payload bound to
// this object. makeFrame's prvalue needs no copy/move under C++17 elision.
template<class A,class L> struct InlineFrame final : Frame {
 static_assert(std::is_trivially_copyable_v<A>&&std::is_trivially_copyable_v<L>,"frame callables must be trivial captures");
 A permission;
 L operation;
 InlineFrame(A a,L l):permission(a),operation(l){
  payload=this;
  allowed=[](void* p,uint32_t op,uint64_t arg){return static_cast<InlineFrame*>(p)->permission(op,arg);};
  leaf=[](void* p,uint32_t op,uint64_t arg){return static_cast<InlineFrame*>(p)->operation(op,arg);};
 }
};
template<class A,class L> InlineFrame<A,L> makeFrame(A allowed,L leaf){return InlineFrame<A,L>(allowed,leaf);}
}
