#include "host_api.h"
#include <algorithm>
#include <cstdint>
namespace {
thread_local uint64_t counts[56][3] = {};
struct Stop { uint32_t status; };
struct Controller {
 void* ctx; SbByteArrayHost host;
 uint64_t call(uint32_t op,uint64_t a=0,uint64_t b=0,uint64_t c=0) {
  uint64_t out=0; auto s=host(ctx,op,a,b,c,&out);
  if(s) throw Stop{s<=2?s:2};
  if(op==SB_BA_THROW_AT) throw Stop{2};
  if((op==SB_BA_HAS_DATA||op==SB_BA_SAME)&&out>1)throw Stop{2};
  if(op==SB_BA_GET_BYTE&&out>255)throw Stop{2};
  switch(op){
   case SB_BA_ARG:case SB_BA_GET_SIZE:case SB_BA_GET_CAPACITY:
   case SB_BA_HAS_DATA:case SB_BA_SAME:case SB_BA_CAPTURE:
   case SB_BA_GET_BYTE:case SB_BA_STRLEN:case SB_BA_ITER_DISTANCE:
   case SB_BA_HASH_RESULT:break;
   default:if(out)throw Stop{2};
  }
  return out;
 }
 uint64_t arg(uint64_t n){return call(SB_BA_ARG,n);}
 uint64_t size(uint64_t r=0){return call(SB_BA_GET_SIZE,r);}
 void reserve(uint64_t r,uint64_t n){
  auto cap=call(SB_BA_GET_CAPACITY,r);
  if(n>cap){bool has=call(SB_BA_HAS_DATA,r);if(has)n=std::max({cap*2,n,uint64_t(8)});call(SB_BA_ALLOC,r,n,has);}
 }
 void resize(uint64_t r,uint64_t n){reserve(r,n);call(SB_BA_SET_SIZE,r,n);}
 void reset(uint64_t r){if(call(SB_BA_HAS_DATA,r)){call(SB_BA_FREE,r);call(SB_BA_INIT,r);}}
 void append(uint64_t r,uint64_t n){resize(r,size(r)+n);call(SB_BA_COPY_IN,r,size(r)-n,n);}
 void copyAssign(){if(!call(SB_BA_SAME)){resize(0,0);auto n=call(SB_BA_CAPTURE,1);append(0,n);}}
 void moveAssign(){if(!call(SB_BA_SAME)){reset(0);call(SB_BA_TAKE);}}
 void fill(uint64_t n,uint64_t byte){if(n!=UINT64_MAX)resize(0,n);call(SB_BA_FILL_BYTES,0,byte);}
 void sub(uint64_t b,uint64_t n){
  auto s=size();call(SB_BA_INIT_RESULT);
  if(b==0&&n>=s){auto len=call(SB_BA_CAPTURE,0);append(2,len);}
  else{call(SB_BA_CAPTURE,0,b);append(2,std::min(s,b+n));}
 }
 uint64_t diff(){auto n=std::min(size(),size(1));uint64_t i=0;for(;i<n;++i)if(call(SB_BA_GET_BYTE,0,i)!=call(SB_BA_GET_BYTE,1,i))break;return i;}
 uint64_t compare(){
  auto a=size(),b=size(1);if(!a&&!b)return 0;if(!a)return UINT64_MAX;if(!b)return 1;
  auto d=diff();if(d==a)return d!=b?UINT64_MAX:0;if(d==b)return d!=a?1:0;
  auto x=call(SB_BA_GET_BYTE,0,d),y=call(SB_BA_GET_BYTE,1,d);return x<y?UINT64_MAX:x>y?1:0;
 }
 void combine(uint64_t kind){
  call(SB_BA_ROLES,size()<size(1));call(SB_BA_INIT_RESULT);resize(2,size(3));
  for(uint64_t i=0;i<size(3);++i)call(SB_BA_EXPR,i,kind);
  auto extend=arg(0);if(extend>1)throw Stop{2};
  if(extend){resize(2,size(4));for(uint64_t i=size(3);i<size(4);++i)call(SB_BA_TAIL_EXPR,i);}
 }
 void insert(uint64_t p,uint64_t byte){
  call(SB_BA_ASSERT_INSERT,p);resize(0,size()+1);
  for(uint64_t i=size()-1;i>p;--i)call(SB_BA_SET_BYTE,0,i,call(SB_BA_GET_BYTE,0,i-1));
  call(SB_BA_SET_BYTE,0,p,byte);
 }
 void push(uint64_t byte){resize(0,size()+1);call(SB_BA_SET_BYTE,0,size()-1,byte);}
 void run(uint32_t m){
  uint64_t n,p,d;
  switch(m){
   case SB_BA_CSTRING:case SB_BA_CSTRING_NULL:
    n=call(SB_BA_STRLEN);call(SB_BA_INIT_RESULT);append(2,n+(m==SB_BA_CSTRING_NULL));if(m==SB_BA_CSTRING_NULL)call(SB_BA_SET_BYTE,2,n,0);break;
   case SB_BA_WITH_RESERVE:call(SB_BA_INIT_RESULT);reserve(2,arg(0));break;
   case SB_BA_CTOR:call(SB_BA_INIT,0);break;
   case SB_BA_FILL_CTOR:fill(arg(0),arg(1));break;
   case SB_BA_PTR_CTOR:append(0,arg(0));break;
   case SB_BA_COPY_CTOR:case SB_BA_COPY_ASSIGN:copyAssign();break;
   case SB_BA_MOVE_CTOR:case SB_BA_MOVE_ASSIGN:moveAssign();break;
   case SB_BA_DTOR:case SB_BA_RESET:reset(0);break;
   case SB_BA_RESERVE:reserve(0,arg(0));break;
   case SB_BA_RESIZE_FILL:n=arg(0);p=size();if(n!=p){resize(0,n);for(uint64_t i=p;i<size();++i)call(SB_BA_SET_BYTE,0,i,arg(1));}break;
   case SB_BA_FILL_SIZE:fill(arg(0),arg(1));break;
   case SB_BA_FILL:fill(UINT64_MAX,arg(0));break;
   case SB_BA_SUB:sub(arg(0),arg(1));break;
   case SB_BA_LEFT:sub(0,arg(0));break;
   case SB_BA_RIGHT:n=arg(0);p=size();sub(n>p?0:p-n,p);break;
   case SB_BA_TRIM_LEFT:n=arg(0);p=size();if(n>=p)resize(0,0);else{call(SB_BA_MOVE_BYTES,0,n,p-n);resize(0,size()-n);}break;
   case SB_BA_TRIM_RIGHT:n=arg(0);p=size();resize(0,n>=p?0:p-n);break;
   case SB_BA_DIFF:call(SB_BA_RETURN,diff());break;
   case SB_BA_COMPARE:call(SB_BA_RETURN,compare());break;
   case SB_BA_AND:combine(1);break;case SB_BA_OR:combine(2);break;case SB_BA_XOR:combine(3);break;
   case SB_BA_INSERT:insert(arg(0),arg(1));break;
   case SB_BA_INSERT_ITER:d=call(SB_BA_ITER_DISTANCE);insert(d,arg(0));call(SB_BA_POINTER,0,d+1);break;
   case SB_BA_PUSH:case SB_BA_APPEND_BYTE:push(arg(0));break;
   case SB_BA_LT:call(SB_BA_RETURN,compare()==UINT64_MAX);break;
   case SB_BA_EQ:call(SB_BA_RETURN,compare()==0);break;
   case SB_BA_NE:call(SB_BA_RETURN,compare()!=0);break;
   case SB_BA_STREAM:call(SB_BA_STREAM_PREFIX);call(SB_BA_STREAM_HEX);break;
   case SB_BA_CLEAR:resize(0,0);break;case SB_BA_RESIZE:resize(0,arg(0));break;
   case SB_BA_APPEND_ARRAY:n=call(SB_BA_CAPTURE,1);append(0,n);break;
   case SB_BA_APPEND:append(0,arg(0));break;
   case SB_BA_EMPTY:call(SB_BA_RETURN,size()==0);break;
   case SB_BA_PTR_CONST:case SB_BA_PTR:case SB_BA_BEGIN:case SB_BA_CBEGIN:call(SB_BA_POINTER,0,0,0);break;
   case SB_BA_SIZE:call(SB_BA_RETURN,size());break;
   case SB_BA_CAPACITY:call(SB_BA_RETURN,call(SB_BA_GET_CAPACITY,0));break;
   case SB_BA_COPY_LEN:call(SB_BA_COPY_OUT,0,0,std::min(size(),arg(0)));break;
   case SB_BA_COPY_ALL:call(SB_BA_COPY_OUT,0,0,size());break;
   case SB_BA_COPY_RANGE:p=arg(0);n=arg(1);if(n&&p<size())call(SB_BA_COPY_OUT,0,p,std::min(size()-p,n));break;
   case SB_BA_WRITE:p=arg(0);n=arg(1);if(p+n>size())resize(0,p+n);call(SB_BA_COPY_IN,0,p,n);break;
   case SB_BA_COMBINE:combine(0);break;
   case SB_BA_END:case SB_BA_CEND:call(SB_BA_POINTER,0,size(),1);break;
   case SB_BA_INDEX:call(SB_BA_POINTER,0,arg(0),2);break;
   case SB_BA_CONST_INDEX:call(SB_BA_RETURN,call(SB_BA_GET_BYTE,0,arg(0)));break;
   case SB_BA_AT:n=arg(0);if(n>=size())call(SB_BA_THROW_AT,n);call(SB_BA_RETURN,call(SB_BA_GET_BYTE,0,n));break;
   case SB_BA_HASH:for(uint64_t i=0;i<size();++i)call(SB_BA_HASH_PUT,i);call(SB_BA_RETURN,call(SB_BA_HASH_RESULT));break;
   default:throw Stop{2};
  }
  call(SB_BA_FINISH);
 }
};
}
extern "C" uint64_t sb_byte_array_call_count(uint32_t mode,uint32_t event){return mode<56&&event<3?counts[mode][event]:0;}
extern "C" uint32_t sb_byte_array_run(uint32_t mode,void* ctx,SbByteArrayHost host){
 if(mode>=56||!host||!ctx)return 2;
 ++counts[mode][0];
 try{Controller{ctx,host}.run(mode);++counts[mode][1];return 0;}
 catch(Stop const& s){if(s.status==1)++counts[mode][2];return s.status;}
 catch(...){return 3;}
}
