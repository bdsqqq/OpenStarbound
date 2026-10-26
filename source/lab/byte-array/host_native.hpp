#pragma once
#include "host_api.h"
#include "StarMemory.hpp"
#include <optional>
#include <exception>
#include <stdexcept>
#include <cstring>
#include <cstdint>
#include <type_traits>
#include <utility>
namespace Star {
// Legal access to the actual class fields; no duplicate layout or pointer mirror.
struct ByteArrayNativeAccess {
 static char*& data(ByteArray& b){return b.m_data;}
 static size_t& size(ByteArray& b){return b.m_size;}
 static size_t& capacity(ByteArray& b){return b.m_capacity;}
};
namespace ByteArrayHost {
static_assert(sizeof(size_t)==8 && char(-1)<0,"finite native profile");
struct Stop { uint32_t status; };
struct NativeCtx {
 ByteArray const* owner=nullptr;ByteArray const* other=nullptr;
 ByteArray const* smaller=nullptr;ByteArray const* larger=nullptr;
 // Disengaged until INIT_RESULT: constructing a ByteArray here would recurse.
 std::optional<ByteArray> value;
 uint64_t args[2]={0,0},result=0;
 char const* input=nullptr;char* output=nullptr;char* pointer=nullptr;
 size_t inputCount=0,outputCount=0;
 uintptr_t borrowedBase[2]={0,0};size_t borrowedCapacity[2]={0,0};bool captured=false;
 ByteArray::const_iterator position=nullptr;
 std::ostream* stream=nullptr;
 void* generic=nullptr;void (*expression)(NativeCtx&,size_t)=nullptr;
 std::exception_ptr pending;PLHasher hash;
 bool ready=true,busy=false,finished=false;
};
inline void need(bool b){if(!b)throw Stop{2};}
inline ByteArray& role(NativeCtx& c,uint64_t r){
 ByteArray const* p=nullptr;
 switch(r){case 0:need(c.ready);p=c.owner;break;case 1:p=c.other;break;
 case 2:need(bool(c.value));p=&*c.value;break;case 3:p=c.smaller;break;case 4:p=c.larger;break;default:throw Stop{2};}
 need(p);return *const_cast<ByteArray*>(p);
}
inline void captureBorrowed(NativeCtx& c){
 if(c.captured)return;c.captured=true;
 ByteArray const* objects[2]={c.ready?c.owner:nullptr,c.other};
 for(size_t i=0;i<2;++i)if(objects[i]){auto& o=*const_cast<ByteArray*>(objects[i]);c.borrowedBase[i]=reinterpret_cast<uintptr_t>(ByteArrayNativeAccess::data(o));c.borrowedCapacity[i]=ByteArrayNativeAccess::capacity(o);}
}
// A leaf already knows its live target and new storage. Update numeric
// exclusions there, never by refreshing borrowed objects after user code.
inline void trackStorage(NativeCtx& c,ByteArray const* target,char const* data,size_t capacity){
 if(target==c.owner){c.borrowedBase[0]=reinterpret_cast<uintptr_t>(data);c.borrowedCapacity[0]=capacity;}
 if(target==c.other){c.borrowedBase[1]=reinterpret_cast<uintptr_t>(data);c.borrowedCapacity[1]=capacity;}
}
inline void span(char const* p,size_t capacity,size_t offset,size_t count){
 need(p&&offset<=capacity&&count<=capacity-offset);
 auto base=reinterpret_cast<uintptr_t>(p);need(offset<=UINTPTR_MAX-base&&count<=UINTPTR_MAX-(base+offset));
}
void streamHex(NativeCtx&);
inline uint32_t nativeHost(void* opaque,uint32_t op,uint64_t a,uint64_t b,uint64_t d,uint64_t* out) noexcept {
 if(!opaque||!out)return 2;
 auto& c=*static_cast<NativeCtx*>(opaque);
 auto address=reinterpret_cast<uintptr_t>(out),base=reinterpret_cast<uintptr_t>(&c);
 if(address%alignof(uint64_t)||address>UINTPTR_MAX-sizeof(uint64_t)||
    (address<base+sizeof c&&base<address+sizeof(uint64_t)))return 2;
 auto overlaps=[&](void const* p,size_t n){auto start=reinterpret_cast<uintptr_t>(p);return p&&(n>UINTPTR_MAX-start||(address<start+n&&start<address+sizeof(uint64_t)));};
 if(overlaps(c.owner,sizeof(ByteArray))||overlaps(c.other,sizeof(ByteArray)))return 2;
 // No borrowed-owner refresh here: callbacks may legally destroy a larger input.
 if(op<SB_BA_ARG||op>SB_BA_FINISH||c.busy||c.finished)return 2;
 if(c.pending)return 1;
 // Snapshot only while bindings are initially live; never refresh on FINISH.
 if(!c.captured&&op!=SB_BA_FINISH)captureBorrowed(c);
 for(size_t i=0;i<2;++i){auto start=c.borrowedBase[i],n=c.borrowedCapacity[i];if(start&&(n>UINTPTR_MAX-start||(address<start+n&&start<address+sizeof(uint64_t))))return 2;}
 if(c.value){auto& v=*c.value;if(overlaps(&v,sizeof v)||overlaps(ByteArrayNativeAccess::data(v),ByteArrayNativeAccess::capacity(v)))return 2;}
 c.busy=true;struct Unlock{bool& busy;~Unlock(){busy=false;}} unlock{c.busy};
 bool inNativeExpression=false;
 try{
  uint64_t r=0;auto none=[&]{need(!a&&!b&&!d);};
  switch(op){
   case SB_BA_ARG:need(a<2&&!b&&!d);r=c.args[a];break;
   case SB_BA_GET_SIZE:need(!b&&!d);r=ByteArrayNativeAccess::size(role(c,a));break;
   case SB_BA_GET_CAPACITY:need(!b&&!d);r=ByteArrayNativeAccess::capacity(role(c,a));break;
   case SB_BA_HAS_DATA:need(!b&&!d);r=ByteArrayNativeAccess::data(role(c,a))!=nullptr;break;
   case SB_BA_INIT:{need(!b&&!d&&a==0&&c.owner);auto& o=*const_cast<ByteArray*>(c.owner);
    ByteArrayNativeAccess::data(o)=nullptr;ByteArrayNativeAccess::capacity(o)=0;ByteArrayNativeAccess::size(o)=0;c.ready=true;trackStorage(c,&o,nullptr,0);break;}
   case SB_BA_SET_SIZE:need(!d);need(b<=ByteArrayNativeAccess::capacity(role(c,a)));ByteArrayNativeAccess::size(role(c,a))=b;break;
   case SB_BA_ALLOC:{need(d<=1);auto& o=role(c,a);auto& ptr=ByteArrayNativeAccess::data(o);
    need((ptr!=nullptr)==bool(d));auto mem=static_cast<char*>(d?Star::realloc(ptr,b):Star::malloc(b));
    if(!mem)throw MemoryException::format("Could not set new ByteArray capacity {}\n",b);
    ptr=mem;ByteArrayNativeAccess::capacity(o)=b;trackStorage(c,&o,mem,b);break;}
   case SB_BA_FREE:{need(!b&&!d);auto& o=role(c,a);Star::free(ByteArrayNativeAccess::data(o),ByteArrayNativeAccess::capacity(o));break;}
   case SB_BA_TAKE:{none();auto& o=role(c,0);auto& s=role(c,1);
    ByteArrayNativeAccess::data(o)=std::exchange(ByteArrayNativeAccess::data(s),nullptr);
    ByteArrayNativeAccess::capacity(o)=std::exchange(ByteArrayNativeAccess::capacity(s),size_t{});
    ByteArrayNativeAccess::size(o)=std::exchange(ByteArrayNativeAccess::size(s),size_t{});
    trackStorage(c,&o,ByteArrayNativeAccess::data(o),ByteArrayNativeAccess::capacity(o));trackStorage(c,&s,nullptr,0);break;}
   case SB_BA_SAME:none();need(c.owner&&c.other);r=c.owner==c.other;break;
   case SB_BA_CAPTURE:{need(!d);auto& o=role(c,a);need(b<=ByteArrayNativeAccess::capacity(o));c.input=ByteArrayNativeAccess::data(o);c.inputCount=ByteArrayNativeAccess::capacity(o)-b;if(b){span(c.input,ByteArrayNativeAccess::capacity(o),b,0);c.input+=b;}r=ByteArrayNativeAccess::size(o);break;}
   case SB_BA_COPY_IN:{auto& o=role(c,a);span(ByteArrayNativeAccess::data(o),ByteArrayNativeAccess::size(o),b,d);need(ByteArrayNativeAccess::size(o)<=ByteArrayNativeAccess::capacity(o));span(c.input,c.inputCount,0,d);std::memcpy(ByteArrayNativeAccess::data(o)+b,c.input,d);break;}
   case SB_BA_COPY_OUT:{auto& o=role(c,a);span(c.output,c.outputCount,0,d);span(ByteArrayNativeAccess::data(o),ByteArrayNativeAccess::size(o),b,d);need(ByteArrayNativeAccess::size(o)<=ByteArrayNativeAccess::capacity(o));std::memcpy(c.output,ByteArrayNativeAccess::data(o)+b,d);break;}
   case SB_BA_MOVE_BYTES:{need(a==0);auto& o=role(c,0);auto p=ByteArrayNativeAccess::data(o);span(p,ByteArrayNativeAccess::size(o),b,d);span(p,ByteArrayNativeAccess::capacity(o),b,d);span(p,ByteArrayNativeAccess::capacity(o),0,d);std::memmove(p,p+b,d);break;}
   case SB_BA_FILL_BYTES:{need(b<=255&&!d);auto& o=role(c,a);span(ByteArrayNativeAccess::data(o),ByteArrayNativeAccess::capacity(o),0,ByteArrayNativeAccess::size(o));std::memset(ByteArrayNativeAccess::data(o),static_cast<unsigned char>(b),ByteArrayNativeAccess::size(o));break;}
   case SB_BA_GET_BYTE:{need(!d);auto& o=role(c,a);need(b<ByteArrayNativeAccess::size(o));span(ByteArrayNativeAccess::data(o),ByteArrayNativeAccess::capacity(o),b,1);r=static_cast<unsigned char>(ByteArrayNativeAccess::data(o)[b]);break;}
   case SB_BA_SET_BYTE:{need(d<=255);auto& o=role(c,a);need(b<ByteArrayNativeAccess::size(o));span(ByteArrayNativeAccess::data(o),ByteArrayNativeAccess::capacity(o),b,1);ByteArrayNativeAccess::data(o)[b]=static_cast<char>(d);break;}
   case SB_BA_POINTER:{need(d<=2);auto& o=role(c,a);if(d==2){need(b<ByteArrayNativeAccess::size(o));span(ByteArrayNativeAccess::data(o),ByteArrayNativeAccess::capacity(o),b,1);}else{need(b<=ByteArrayNativeAccess::capacity(o));if(b)span(ByteArrayNativeAccess::data(o),ByteArrayNativeAccess::capacity(o),b,0);}
    c.pointer=ByteArrayNativeAccess::data(o);if(b||d)c.pointer+=b;break;}
   case SB_BA_STRLEN:none();need(c.input);r=std::strlen(c.input);c.inputCount=r+1;break;
   case SB_BA_INIT_RESULT:none();need(!c.value);c.value.emplace();break;
   case SB_BA_ROLES:need(a<=1&&!b&&!d&&c.owner&&c.other);c.smaller=a?c.owner:c.other;c.larger=a?c.other:c.owner;break;
   case SB_BA_EXPR:{need(!d&&b<=3&&c.value&&c.smaller&&c.larger);
    if(!b)need(c.expression&&c.generic);inNativeExpression=true;
    if(!b){c.expression(c,a);}
    else if(b==1)(*c.value)[a]=(*c.smaller)[a]&(*c.larger)[a];
    else if(b==2)(*c.value)[a]=(*c.smaller)[a]|(*c.larger)[a];
    else (*c.value)[a]=(*c.smaller)[a]^(*c.larger)[a];inNativeExpression=false;break;}
   case SB_BA_TAIL_EXPR:need(!b&&!d&&c.value&&c.larger);(*c.value)[a]=(*c.larger)[a];break;
   case SB_BA_ITER_DISTANCE:{none();need(c.position);auto& o=role(c,0);auto ptr=ByteArrayNativeAccess::data(o);auto first=reinterpret_cast<uintptr_t>(ptr),pos=reinterpret_cast<uintptr_t>(c.position);need(ptr&&pos>=first&&pos-first<=ByteArrayNativeAccess::size(o));span(ptr,ByteArrayNativeAccess::capacity(o),pos-first,0);r=c.position-ptr;break;}
   case SB_BA_ASSERT_INSERT:need(!b&&!d);need(a<=ByteArrayNativeAccess::size(role(c,0)));break;
   case SB_BA_THROW_AT:need(!b&&!d);throw OutOfRangeException(strf("Out of range in ByteArray::at({})",a));
   case SB_BA_HASH_PUT:need(!b&&!d);c.hash.put(static_cast<ByteArray const&>(role(c,0))[a]);break;
   case SB_BA_HASH_RESULT:none();r=c.hash.hash();break;
   case SB_BA_STREAM_PREFIX:none();need(c.stream);inNativeExpression=true;*c.stream<<"0x";inNativeExpression=false;break;
   case SB_BA_STREAM_HEX:none();need(c.stream&&c.owner);inNativeExpression=true;streamHex(c);inNativeExpression=false;break;
   case SB_BA_RETURN:need(!b&&!d);c.result=a;break;
   case SB_BA_FINISH:none();c.finished=true;break;
   default:throw Stop{2};
  }
  *out=r;return 0;
 }catch(Stop const& s){if(inNativeExpression){if(!c.pending)c.pending=std::current_exception();return 1;}return s.status;}catch(...){if(!c.pending)c.pending=std::current_exception();return 1;}
}
inline void execute(uint32_t mode,NativeCtx& c){
 captureBorrowed(c);
 auto status=sb_byte_array_run(mode,&c,nativeHost);
 if(c.pending){if(status!=1)throw std::runtime_error("ByteArray pending/status contradiction");std::rethrow_exception(c.pending);}
 if(status||!c.finished)throw std::runtime_error("ByteArray host protocol failure");
}
template<class F> struct NativeGenericCtx {
 F& function;
 static void expression(NativeCtx& c,size_t i){
  auto& state=*static_cast<NativeGenericCtx*>(c.generic);
  // One full expression: conversion, destination store, then temporary cleanup.
  (*c.value)[i]=state.function((*c.smaller)[i],(*c.larger)[i]);
 }
};
}
}
