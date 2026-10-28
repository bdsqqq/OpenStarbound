// Native-only policy double. This is NOT an actual Rust provider.
#include "StarRustIdMap.h"
#include <cstdint>
#include <limits>
#include <initializer_list>
namespace {
thread_local uint64_t counts[SB_IDMAP_MODE_COUNT][SB_IDMAP_STAGE_COUNT]{};
using Observer=void(*)(void*,SbIdMapHost,uint32_t,uint32_t,uint32_t,uint32_t);
thread_local Observer observer=nullptr;
thread_local uint32_t fault=0;
SbIdMapReply reply(uint32_t tag=SB_IDMAP_VOID,uint64_t value=0){return {24,1,tag,0,value};}
bool valid(SbIdMapReply const& r){return r.size==24&&r.version==1&&!r.reserved&&((r.tag==SB_IDMAP_VOID&&!r.value)||(r.tag==SB_IDMAP_BOOL&&r.value<=1));}
struct Stop{uint32_t status;};
struct Controller{
 void* context;SbIdMapHost host;uint32_t mode,stage;
 uint64_t call(uint32_t op,uint32_t tag){
  if(observer)observer(context,host,mode,stage,op,SB_IDMAP_OK);
  SbIdMapRequest q{24,1,op,0,0};auto r=reply(UINT32_MAX,UINT64_MAX);
  uint32_t s=host(context,&q,&r);
  if(s){if(observer&&s==SB_IDMAP_EXCEPTION)observer(context,host,mode,stage,0,s);throw Stop{s<=SB_IDMAP_PANIC?s:static_cast<uint32_t>(SB_IDMAP_INVALID)};}
  if(!valid(r)||r.tag!=tag)throw Stop{SB_IDMAP_INVALID};return r.value;
 }
 void leaf(uint32_t op){call(op,SB_IDMAP_VOID);}
 bool boolean(uint32_t op){return call(op,SB_IDMAP_BOOL)!=0;}
 void mustThrow(uint32_t op){leaf(op);throw Stop{SB_IDMAP_INVALID};}
 SbIdMapReply run(){
  if(stage==SB_IDMAP_CONTINUE){
   if(mode==SB_IDMAP_NEXT){while(boolean(SB_IDMAP_CURSOR_CONTAINS))leaf(SB_IDMAP_CURSOR_ADVANCE);leaf(SB_IDMAP_CURSOR_COMMIT);}
   else leaf(SB_IDMAP_AUTO_INSERT);
   return reply();
  }
  switch(mode){
   case SB_IDMAP_CTOR:case SB_IDMAP_ADD_AUTO:if(observer)observer(context,host,mode,stage,0,SB_IDMAP_OK);break;
   case SB_IDMAP_RANGE_CTOR:leaf(SB_IDMAP_ASSERT_RANGE);break;
   case SB_IDMAP_NEXT:if(boolean(SB_IDMAP_FULL))mustThrow(SB_IDMAP_THROW_FULL);break;
   case SB_IDMAP_ADD_EXPLICIT:if(!boolean(SB_IDMAP_EXPLICIT_INSERT))mustThrow(SB_IDMAP_THROW_DUPLICATE);break;
   case SB_IDMAP_CLEAR:leaf(SB_IDMAP_CLEAR_MAP);leaf(SB_IDMAP_CLEAR_CURSOR);break;
   case SB_IDMAP_EQUAL:return reply(SB_IDMAP_BOOL,boolean(SB_IDMAP_SAME_BOUNDS)&&boolean(SB_IDMAP_BASE_EQUAL));
   case SB_IDMAP_NOT_EQUAL:return reply(SB_IDMAP_BOOL,!boolean(SB_IDMAP_CALL_EQUAL));
   case SB_IDMAP_READ:for(auto op:{SB_IDMAP_READ_MAP,SB_IDMAP_READ_MIN,SB_IDMAP_READ_MAX,SB_IDMAP_READ_CURSOR})leaf(op);break;
   case SB_IDMAP_WRITE:for(auto op:{SB_IDMAP_WRITE_MAP,SB_IDMAP_WRITE_MIN,SB_IDMAP_WRITE_MAX,SB_IDMAP_WRITE_CURSOR})leaf(op);break;
  }
  return reply();
 }
};
}
extern "C" void sb_idmap_mock_observe(Observer value){observer=value;}
extern "C" void sb_idmap_mock_fault(uint32_t value){fault=value;}
extern "C" uint64_t sb_idmap_count(uint32_t mode,uint32_t stage){return mode<10&&stage<2?counts[mode][stage]:0;}
extern "C" uint32_t sb_idmap_run(uint32_t mode,uint32_t stage,void* context,SbIdMapHost host,SbIdMapReply* result){
 if(mode>=10||!(stage==0||(stage==1&&(mode==2||mode==4)))||!context||!host||!result||reinterpret_cast<uintptr_t>(result)%alignof(SbIdMapReply)||!valid(*result))return SB_IDMAP_INVALID;
 ++counts[mode][stage];
 // A test-only hostile controller can acknowledge without any native leaf.
 if(fault==1){*result=reply((mode==6||mode==7)&&!stage?SB_IDMAP_BOOL:SB_IDMAP_VOID);return SB_IDMAP_OK;}
 try{auto r=Controller{context,host,mode,stage}.run();*result=r;return SB_IDMAP_OK;}
 catch(Stop const& s){return s.status;}
 catch(...){return SB_IDMAP_PANIC;}
}
