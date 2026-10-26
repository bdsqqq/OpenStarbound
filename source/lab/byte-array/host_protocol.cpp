#include "StarByteArray.hpp"
#include "host_api.h"
#include <cstdlib>
#include <cstdio>
#include <memory>
#include <sstream>
#include <type_traits>
// Deliberately independent of NDEBUG and STAR_DEBUG. Production starAssert is
// untouched; this executable must fail explicitly in the recorded build flags.
#define CHECK(x) do { if(!(x)){std::fprintf(stderr,"CHECK failed %s:%d: %s\n",__FILE__,__LINE__,#x);std::abort();} } while(false)
using namespace Star;
using namespace Star::ByteArrayHost;
static uint32_t badStatus(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*){return 99;}
static uint32_t invalidThree(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*){return 3;}
static uint32_t throws(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*){throw 17;}
static uint32_t falseSuccess(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t* out){*out=7;return 0;}
static uint32_t pending(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*){return 1;}
static char functionCombiner(char a,char b){return a-b;}
struct Proxy {
 int* stage;char value;
 Proxy(int* s,char v):stage(s),value(v){}
 Proxy(Proxy const&)=delete;Proxy(Proxy&&)=delete;
 operator char(){CHECK(*stage==1);*stage=2;return value;}
 ~Proxy(){CHECK(*stage==2);*stage=3;}
};
struct Noncopyable {
 int* stage;
 explicit Noncopyable(int* p):stage(p){}
 Noncopyable(Noncopyable const&)=delete;Noncopyable(Noncopyable&&)=delete;
 Proxy operator()(char a,char b)&{CHECK(*stage==0||*stage==3);*stage=1;return Proxy(stage,char(a-b));}
};
int main(int argc,char**){
 if(argc!=1)return 2;
 static_assert(std::is_same<decltype(std::declval<ByteArray const&>()[0]),char>::value,"const char value");
 static_assert(std::is_same<decltype(std::declval<ByteArray&>()[0]),char&>::value,"mutable reference");
 NativeCtx c;uint64_t out=123;
 auto attempts=sb_byte_array_call_count(SB_BA_CTOR,0);
 CHECK(sb_byte_array_run(56,&c,nativeHost)==2);
 CHECK(sb_byte_array_run(SB_BA_CTOR,nullptr,nativeHost)==2);
 CHECK(sb_byte_array_run(SB_BA_CTOR,&c,nullptr)==2);
 CHECK(sb_byte_array_call_count(SB_BA_CTOR,0)==attempts);
 CHECK(sb_byte_array_call_count(56,0)==0&&sb_byte_array_call_count(0,3)==0);
 CHECK(nativeHost(nullptr,SB_BA_ARG,0,0,0,&out)==2);
 CHECK(nativeHost(&c,999,0,0,0,&out)==2);
 CHECK(nativeHost(&c,SB_BA_ARG,0,1,0,&out)==2);
 CHECK(nativeHost(&c,SB_BA_ARG,2,0,0,&out)==2);
 CHECK(nativeHost(&c,SB_BA_ARG,0,0,0,nullptr)==2);
 CHECK(nativeHost(&c,SB_BA_ARG,0,0,0,&c.result)==2);
 c.busy=true;CHECK(nativeHost(&c,SB_BA_ARG,0,0,0,&out)==2);c.busy=false;
 CHECK(sb_byte_array_run(SB_BA_CTOR,&c,badStatus)==2);
 CHECK(sb_byte_array_run(SB_BA_CTOR,&c,invalidThree)==2);
 CHECK(sb_byte_array_run(SB_BA_CTOR,&c,throws)==3);
 CHECK(sb_byte_array_run(SB_BA_CTOR,&c,falseSuccess)==2);
 auto pc=sb_byte_array_call_count(SB_BA_CTOR,2);
 CHECK(sb_byte_array_run(SB_BA_CTOR,&c,pending)==1);
 CHECK(sb_byte_array_call_count(SB_BA_CTOR,2)==pc+1);
 // An unreadable destination is never inspected by the readiness guard.
 alignas(ByteArray) unsigned char raw[sizeof(ByteArray)];
 NativeCtx uninitialized;uninitialized.owner=reinterpret_cast<ByteArray*>(raw);uninitialized.ready=false;
 CHECK(nativeHost(&uninitialized,SB_BA_GET_SIZE,0,0,0,&out)==2);
 CHECK(nativeHost(&uninitialized,SB_BA_GET_CAPACITY,0,0,0,&out)==2);
 CHECK(nativeHost(&uninitialized,SB_BA_HAS_DATA,0,0,0,&out)==2);
 ByteArray a(3,10),b(5,20);
 NativeCtx guarded;guarded.owner=&a;captureBorrowed(guarded);
 CHECK(nativeHost(&guarded,SB_BA_GET_BYTE,0,a.size(),0,&out)==2);
 CHECK(nativeHost(&guarded,SB_BA_SET_BYTE,0,a.size(),0,&out)==2);
 CHECK(nativeHost(&guarded,SB_BA_POINTER,0,a.size(),2,&out)==2);
 CHECK(nativeHost(&guarded,SB_BA_COPY_IN,0,0,1,&out)==2);
 CHECK(nativeHost(&guarded,SB_BA_COPY_OUT,0,0,1,&out)==2);
 CHECK(nativeHost(&guarded,SB_BA_MOVE_BYTES,0,a.size(),1,&out)==2);
 CHECK(nativeHost(&guarded,SB_BA_CAPTURE,0,a.capacity()+1,0,&out)==2);
 ByteArray backing(64,7);NativeCtx backingCtx;backingCtx.owner=&backing;captureBorrowed(backingCtx);
 CHECK(nativeHost(&backingCtx,SB_BA_ARG,0,0,0,reinterpret_cast<uint64_t*>(backing.ptr()))==2);
 guarded.value.emplace(32,9);
 CHECK(nativeHost(&guarded,SB_BA_ARG,0,0,0,reinterpret_cast<uint64_t*>(guarded.value->ptr()))==2);
 int token=0;
 bool caught=false;
 try{a.combineWith([&](char,char)->char{a[0]=11;throw &token;},b);}
 catch(int* p){caught=p==&token;}
 CHECK(caught&&a[0]==11);
 NativeCtx failed;failed.owner=&a;failed.args[0]=a.size();
 CHECK(nativeHost(&failed,SB_BA_THROW_AT,a.size(),0,0,&out)==1);
 auto first=failed.pending;
 CHECK(nativeHost(&failed,SB_BA_THROW_AT,0,0,0,&out)==1);
 CHECK(first==failed.pending);
 CHECK(nativeHost(&failed,999,0,0,0,&out)==2);
 // Same live owner, independent nested contexts.
 bool nested=false;
 auto reentrant=a.combineWith([&](char x,char y){if(!nested){nested=true;auto r=a.combineWith(functionCombiner,b);CHECK(r.size()==3);}return char(x+y);},b);
 CHECK(nested&&reentrant.size()==3);
 int stage=0;auto proxy=a.combineWith(Noncopyable(&stage),b);CHECK(stage==3&&proxy.size()==3);
 auto functional=a.combineWith(functionCombiner,b);CHECK(functional.size()==3);
 auto large=std::make_unique<ByteArray>(5,20);ByteArray small(2,10);int calls=0;
 auto deleted=small.combineWith([&](char x,char y){if(++calls==2)large.reset();return char(x+y);},*large);
 CHECK(!large&&deleted.size()==2&&deleted[0]==30&&deleted[1]==30);
 auto receiver=std::make_unique<ByteArray>(5,20);calls=0;
 auto deletedThis=receiver->combineWith([&](char x,char y){if(++calls==2)receiver.reset();return char(x+y);},small);
 CHECK(!receiver&&deletedThis.size()==2&&deletedThis[1]==30);
 NativeCtx finish;finish.owner=reinterpret_cast<ByteArray*>(uintptr_t(1));
 CHECK(nativeHost(&finish,SB_BA_FINISH,0,0,0,&out)==0&&finish.finished);
 CHECK(nativeHost(&finish,SB_BA_FINISH,0,0,0,&out)==2);
 std::puts("BYTE_ARRAY_NATIVE_PROTOCOL_PASS");
 return 0;
}
