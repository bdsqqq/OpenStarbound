#include "host_api.h"
namespace {
thread_local uint32_t depth=0;
thread_local uint64_t counts[SB_LRU_MODES][4]={};
struct Stop { uint32_t status; };
struct Controller {
 void* ctx; SbLruHost host; uint32_t remaining=1000000;
 uint64_t call(uint32_t op,uint32_t tag=SB_LRU_VOID,uint64_t arg=0) {
  if(!remaining--)throw Stop{2};
  SbLruRequest request{sizeof(SbLruRequest),op,arg};
  SbLruReply reply{sizeof(SbLruReply),UINT32_MAX,UINT64_MAX};
  auto status=host(ctx,&request,&reply);
  if(status)throw Stop{status<=3?status:2};
  if(reply.size!=sizeof(SbLruReply)||reply.tag!=tag)throw Stop{2};
  if((tag==SB_LRU_BOOL&&reply.value>1)||(tag==SB_LRU_VOID&&reply.value))throw Stop{2};
  return reply.value;
 }
 uint64_t limit(){return call(SB_LRU_READ_MAX,SB_LRU_U64);}
 uint64_t size(){return call(SB_LRU_MAP_SIZE,SB_LRU_U64);}
 void trim(bool get){while(size()>(get?limit()-1:limit()))call(SB_LRU_REMOVE_FIRST);}
 SbLruReply run(uint32_t mode,uint32_t stage){
  SbLruReply result{sizeof(SbLruReply),SB_LRU_VOID,0};
  if(stage==SB_LRU_FOUND){
   if(mode==SB_LRU_PTR){if(!call(SB_LRU_IS_END,SB_LRU_BOOL)){call(SB_LRU_PROMOTE_ASSIGN);call(SB_LRU_REFERENCE);}}
   else if(mode==SB_LRU_SET){if(call(SB_LRU_IS_END,SB_LRU_BOOL))call(SB_LRU_ADD);else{call(SB_LRU_ASSIGN);call(SB_LRU_PROMOTE_DISCARD);}}
   else if(mode==SB_LRU_GET){if(call(SB_LRU_IS_END,SB_LRU_BOOL))call(SB_LRU_PAIR_SCOPE);else call(SB_LRU_PROMOTE_ASSIGN);call(SB_LRU_REFERENCE);}
   else throw Stop{2};
   return result;
  }
  if(stage==SB_LRU_PAIR){if(mode!=SB_LRU_GET)throw Stop{2};call(SB_LRU_INSERT_PAIR);return result;}
  if(stage==SB_LRU_TRAVERSE){
   if(mode!=SB_LRU_FILTER)throw Stop{2};
   while(!call(SB_LRU_IS_END,SB_LRU_BOOL)){
    if(call(SB_LRU_PREDICATE,SB_LRU_BOOL))call(SB_LRU_ERASE);else call(SB_LRU_NEXT);
   }
   return result;
  }
  switch(mode){
   case SB_LRU_CTOR:case SB_LRU_LIMIT:{auto n=call(SB_LRU_ARG,SB_LRU_U64);call(SB_LRU_WRITE_MAX,SB_LRU_VOID,n?n:1);trim(false);break;}
   case SB_LRU_MAX:result.tag=SB_LRU_U64;result.value=limit();break;
   case SB_LRU_SIZE:result.tag=SB_LRU_U64;result.value=size();break;
   case SB_LRU_KEYS:result.tag=SB_LRU_KEY_LIST;break;
   case SB_LRU_VALUES:result.tag=SB_LRU_VALUE_LIST;break;
   case SB_LRU_GET:trim(true);call(SB_LRU_FIND_SCOPE);result.tag=SB_LRU_REF;break;
   case SB_LRU_PTR:call(SB_LRU_FIND_SCOPE);result.tag=SB_LRU_REF;break;
   case SB_LRU_SET:call(SB_LRU_FIND_SCOPE);break;
   case SB_LRU_REMOVE:result.tag=SB_LRU_BOOL;result.value=call(SB_LRU_REMOVE_KEY,SB_LRU_BOOL);break;
   case SB_LRU_FILTER:call(SB_LRU_FILTER_SCOPE);break;
   case SB_LRU_CLEAR:call(SB_LRU_MAP_CLEAR);break;
   default:throw Stop{2};
  }
  return result;
 }
};
struct Depth {Depth(){++depth;}~Depth(){--depth;}};
}
extern "C" uint64_t sb_lru_count(uint32_t mode,uint32_t stage){return mode<SB_LRU_MODES&&stage<4?counts[mode][stage]:0;}
extern "C" uint32_t sb_lru_run(uint32_t mode,uint32_t stage,void* ctx,SbLruHost host,SbLruReply* result){
 if(mode>=SB_LRU_MODES||stage>SB_LRU_TRAVERSE||!ctx||!host||!result||result->size!=sizeof(SbLruReply)||depth>=128)return 2;
 Depth guard;++counts[mode][stage];
 try{*result=Controller{ctx,host}.run(mode,stage);return 0;}
 catch(Stop const& stop){return stop.status;}
 catch(...){return 3;}
}
