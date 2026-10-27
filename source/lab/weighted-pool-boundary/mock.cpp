#include "frame.hpp"
#include <cmath>
#include <algorithm>
#include <cstdint>
using namespace WpBoundary;
namespace {uint64_t counts[19][4]{};struct Stop{uint32_t code;};
struct Policy {void* c;SbWpHost h;SbWpReply call(uint32_t op,uint64_t arg=0){SbWpRequest q{24,1,op,0,arg};auto r=reply();auto s=h(c,&q,&r);if(s)throw Stop{s};if(!canonical(r))throw Stop{SB_WP_INVALID};return r;}uint64_t get(uint32_t op,uint32_t tag,uint64_t arg=0){auto r=call(op,arg);if(r.tag!=tag)throw Stop{SB_WP_INVALID};return r.value;}void action(uint32_t op,uint64_t arg=0){get(op,SB_WP_VOID,arg);}uint64_t arg(uint64_t n,uint32_t tag=SB_WP_U64){return get(SB_WP_ARG,tag,n);}SbWpReply run(uint32_t m,uint32_t s){
 if(s==SB_WP_CONTAINER_LOOP){while(!get(SB_WP_CONTAINER_END,SB_WP_BOOL)){action(SB_WP_CONTAINER_ADD_EXPRESSION);action(SB_WP_CONTAINER_NEXT);}return reply();}
 if(s==SB_WP_UNIQUE_COLLECT){auto target=arg(0),seed=arg(1);while(get(SB_WP_UNIQUE_SET_SIZE,SB_WP_U64)<target){++seed;auto i=get(SB_WP_CALL_INDEX_SEED,SB_WP_U64,seed);action(SB_WP_UNIQUE_SET_ADD,i);}return reply();}
 if(s==SB_WP_UNIQUE_APPEND){while(!get(SB_WP_UNIQUE_END,SB_WP_BOOL)){action(SB_WP_UNIQUE_APPEND_EXPRESSION);action(SB_WP_UNIQUE_NEXT);}return reply();}
 switch(m){
 case 0:return reply();case 1:action(SB_WP_CONTAINER_SCOPE);return reply();
 case 2:{double w=number(arg(0,SB_WP_F64));if(w<=0)return reply();action(SB_WP_APPEND_ITEM_EXPRESSION);double total=number(get(SB_WP_READ_TOTAL,SB_WP_F64));action(SB_WP_WRITE_TOTAL,bits(total+w));return reply();}
 case 3:action(SB_WP_CLEAR_ITEMS);action(SB_WP_WRITE_TOTAL,bits(0));return reply();
 case 4:get(SB_WP_AT_BORROW,SB_WP_BORROW);return reply(SB_WP_BORROW);
 case 5:return reply(SB_WP_U64,get(SB_WP_COUNT,SB_WP_U64));
 case 6:get(SB_WP_AT_BORROW,SB_WP_BORROW,arg(0));return reply(SB_WP_BORROW);
 case 7:return reply(SB_WP_F64,get(SB_WP_AT_WEIGHT,SB_WP_F64,arg(0)));
 case 8:get(SB_WP_AT_ITEM_BORROW,SB_WP_BORROW,arg(0));return reply(SB_WP_BORROW);
 case 9:return reply(SB_WP_BOOL,get(SB_WP_IS_EMPTY,SB_WP_BOOL));
 case 10:case 11:case 12:if(get(SB_WP_IS_EMPTY,SB_WP_BOOL))return reply(SB_WP_DEFAULT_ITEM);return reply(SB_WP_ITEM_RESULT,get(m==10?SB_WP_CALL_INDEX_SOURCE:m==11?SB_WP_CALL_INDEX_GLOBAL:SB_WP_CALL_INDEX_SEED,SB_WP_U64,m==12?arg(0):0));
 case 13:return reply(SB_WP_U64,get(SB_WP_DRAW_SEED,SB_WP_U64));
 case 14:{auto n=arg(0);return reply(SB_WP_U64,std::min(n,get(SB_WP_COUNT,SB_WP_U64)));}
 case 15:case 16:case 17:return reply(SB_WP_F64,get(m==15?SB_WP_DRAW_SOURCE:m==16?SB_WP_DRAW_GLOBAL:SB_WP_DRAW_STATIC,SB_WP_F64,m==17?arg(0):0));
 case 18:{double target=number(arg(0,SB_WP_F64));if(get(SB_WP_IS_EMPTY,SB_WP_BOOL))return reply(SB_WP_U64,UINT64_MAX);double inverse=1.0/number(get(SB_WP_READ_TOTAL,SB_WP_F64)),acc=0;for(uint64_t i=0;i<get(SB_WP_SCAN_SIZE,SB_WP_U64);++i){acc=std::fma(number(get(SB_WP_READ_WEIGHT,SB_WP_F64,i)),inverse,acc);if(target<=acc)return reply(SB_WP_U64,i);}return reply(SB_WP_U64,get(SB_WP_SCAN_SIZE,SB_WP_U64)-1);}
 }throw Stop{SB_WP_INVALID};}};}
extern "C" uint64_t sb_wp_count(uint32_t m,uint32_t s){return m<19&&s<4?counts[m][s]:0;}
extern "C" uint32_t sb_wp_run(uint32_t m,uint32_t s,void* c,SbWpHost h,SbWpReply* out){if(m>=19||s>=4||!c||!h||!out||out->size!=24||out->version!=1||out->tag||out->reserved||out->value|| (s==1&&m!=1)||(s>=2&&m!=14))return SB_WP_INVALID;++counts[m][s];try{Policy p{c,h};auto r=p.run(m,s);*out=r;return 0;}catch(Stop e){return e.code;}catch(...){return SB_WP_PANIC;}}
