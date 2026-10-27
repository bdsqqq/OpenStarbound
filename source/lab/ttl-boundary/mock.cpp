#include "StarRustTtlCache.h"
#include <cstdint>
#include <cstring>
#include <iostream>
namespace {
uint64_t counts[19][4]={},edges[19][4][32]={};
bool omitBorrow=false; // isolated mock controller-mutation control only
struct Stop {uint32_t status;};
struct Controller {
 uint32_t mode,stage;void* context;SbTtlHost host;
 uint64_t leaf(uint32_t op,uint32_t tag=SB_TTL_VOID,uint64_t arg=0) {
  SbTtlRequest q{24,1,op,0,arg};SbTtlReply r{24,1,0,0,0};++edges[mode][stage][op];
  if(omitBorrow && op==SB_TTL_PAIR_VALUE_BORROW)return 0;
  auto status=host(context,&q,&r);
  if(status)throw Stop{status<=SB_TTL_PANIC?status:uint32_t(SB_TTL_INVALID)};
  if(r.size!=24 || r.version!=1 || r.reserved || r.tag!=tag || (tag==SB_TTL_VOID && r.value) || (tag==SB_TTL_BOOL && r.value>1) || ((tag==SB_TTL_REF || tag==SB_TTL_KEY_LIST || tag==SB_TTL_VALUE_LIST) && r.value))throw Stop{SB_TTL_INVALID};
  return r.value;
 }
 uint64_t arg(uint32_t index,uint32_t tag){return leaf(SB_TTL_ARG,tag,index);}
 SbTtlReply run(){
  uint32_t tag=SB_TTL_VOID;uint64_t value=0;
  if(stage==SB_TTL_VALUE_LOOP) {
   while(!leaf(SB_TTL_VALUES_END,SB_TTL_BOOL)){leaf(SB_TTL_VALUES_APPEND);leaf(SB_TTL_VALUES_NEXT);}
  }else if(stage==SB_TTL_FILTER_PREDICATE){tag=SB_TTL_BOOL;value=leaf(SB_TTL_CALL_FILTER,SB_TTL_BOOL);
  }else if(stage==SB_TTL_CLEANUP_PREDICATE){
   tag=SB_TTL_BOOL;
   if(leaf(SB_TTL_FILTER_PRESENT,SB_TTL_BOOL) && leaf(SB_TTL_CALL_REFRESH,SB_TTL_BOOL)) {
    auto time=leaf(SB_TTL_READ_CAPTURED_TIME,SB_TTL_I64);leaf(SB_TTL_PAIR_STAMP_WRITE,SB_TTL_VOID,time);
   }else{
    auto time=leaf(SB_TTL_READ_CAPTURED_TIME,SB_TTL_I64),stamp=leaf(SB_TTL_PAIR_STAMP_READ,SB_TTL_I64);
    auto ttl=leaf(SB_TTL_READ_TTL,SB_TTL_I64);
    // Frozen fixtures exclude C++ signed-overflow UB. Unsigned subtraction
    // preserves those defined signed results without introducing mock UB.
    value=static_cast<int64_t>(time-stamp)>static_cast<int64_t>(ttl);
   }
  }else switch(mode){
   case SB_TTL_CTOR: {
    leaf(SB_TTL_LRU_LIMIT,SB_TTL_VOID,arg(2,SB_TTL_U64));
    leaf(SB_TTL_WRITE_TTL,SB_TTL_VOID,arg(0,SB_TTL_I64));
    leaf(SB_TTL_WRITE_SMEAR,SB_TTL_VOID,arg(1,SB_TTL_I64));
    leaf(SB_TTL_WRITE_UPDATE,SB_TTL_VOID,arg(3,SB_TTL_BOOL));break;
   }
   case SB_TTL_TTL: tag=SB_TTL_I64;value=leaf(SB_TTL_READ_TTL,tag);break;
   case SB_TTL_SET_TTL: leaf(SB_TTL_WRITE_TTL,SB_TTL_VOID,arg(0,SB_TTL_I64));break;
   case SB_TTL_SMEAR: tag=SB_TTL_I64;value=leaf(SB_TTL_READ_SMEAR,tag);break;
   case SB_TTL_SET_SMEAR: leaf(SB_TTL_WRITE_SMEAR,SB_TTL_VOID,arg(0,SB_TTL_I64));break;
   case SB_TTL_MAX: tag=SB_TTL_U64;value=leaf(SB_TTL_LRU_MAX,tag);break;
   case SB_TTL_SET_MAX: leaf(SB_TTL_LRU_LIMIT,SB_TTL_VOID,arg(0,SB_TTL_U64));break;
   case SB_TTL_SIZE: tag=SB_TTL_U64;value=leaf(SB_TTL_LRU_SIZE,tag);break;
   case SB_TTL_KEYS: tag=SB_TTL_KEY_LIST;break;
   case SB_TTL_VALUES: leaf(SB_TTL_VALUES_SCOPE);tag=SB_TTL_VALUE_LIST;break;
   case SB_TTL_UPDATE: tag=SB_TTL_BOOL;value=leaf(SB_TTL_READ_UPDATE,tag);break;
   case SB_TTL_SET_UPDATE: leaf(SB_TTL_WRITE_UPDATE,SB_TTL_VOID,arg(0,SB_TTL_BOOL));break;
   case SB_TTL_PTR:
    tag=SB_TTL_REF;leaf(SB_TTL_LRU_PTR);
    if(leaf(SB_TTL_PAIR_PRESENT,SB_TTL_BOOL)){
     if(leaf(SB_TTL_READ_UPDATE,SB_TTL_BOOL))leaf(SB_TTL_PAIR_STAMP_NATIVE);
     leaf(SB_TTL_PAIR_VALUE_BORROW);
    }break;
   case SB_TTL_SET:leaf(SB_TTL_SET_EXPRESSION);break;
   case SB_TTL_REMOVE:tag=SB_TTL_BOOL;value=leaf(SB_TTL_LRU_REMOVE,tag);break;
   case SB_TTL_FILTER:leaf(SB_TTL_FILTER_SCOPE);break;
   case SB_TTL_GET:
    leaf(SB_TTL_GET_EXPRESSION);
    if(leaf(SB_TTL_PAIR_STAMP_READ,SB_TTL_I64)==0 || leaf(SB_TTL_READ_UPDATE,SB_TTL_BOOL))leaf(SB_TTL_PAIR_STAMP_NATIVE);
    leaf(SB_TTL_PAIR_VALUE_BORROW);tag=SB_TTL_REF;break;
   case SB_TTL_CLEAR:leaf(SB_TTL_LRU_CLEAR);break;
   case SB_TTL_CLEANUP:leaf(SB_TTL_TIME_ONCE);leaf(SB_TTL_CLEANUP_SCOPE);break;
  }
  return {24,1,tag,0,value};
 }
};
}
extern "C" uint32_t sb_ttl_run(uint32_t mode,uint32_t stage,void* context,SbTtlHost host,SbTtlReply* result){
 if(mode>=19 || stage>=4 || !context || !host || !result || result->size!=24 || result->version!=1 || result->reserved)return SB_TTL_INVALID;
 ++counts[mode][stage];
 // Match frozen Rust: in-range but incompatible mode/stage calls are counted.
 if((stage==1 && mode!=9) || (stage==2 && mode!=15) || (stage==3 && mode!=18))return SB_TTL_INVALID;
 try{auto r=Controller{mode,stage,context,host}.run();*result=r;return SB_TTL_OK;}
 catch(Stop const& s){return s.status;}catch(...){return SB_TTL_PANIC;}
}
extern "C" uint64_t sb_ttl_count(uint32_t mode,uint32_t stage){return mode<19 && stage<4?counts[mode][stage]:0;}
extern "C" uint64_t sb_ttl_mock_edge(uint32_t mode,uint32_t stage,uint32_t op){return mode<19 && stage<4 && op<32?edges[mode][stage][op]:0;}
extern "C" void sb_ttl_mock_omit_borrow(bool omit){omitBorrow=omit;}
extern "C" void sb_ttl_mock_dump(){
 for(uint32_t m=0;m<19;++m)for(uint32_t s=0;s<4;++s)if(counts[m][s]){
  std::cerr<<"route\t"<<m<<"\t"<<s<<"\t"<<counts[m][s]<<"\n";
  for(uint32_t op=1;op<32;++op)if(edges[m][s][op])std::cerr<<"edge\t"<<m<<"\t"<<s<<"\t"<<op<<"\t"<<edges[m][s][op]<<"\n";
 }
}
