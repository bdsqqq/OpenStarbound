#include "host_api.h"
namespace {
thread_local uint64_t counts[58][3]={};
struct Stop {uint32_t status;};
constexpr uint64_t NP=UINT64_MAX;
struct Controller {
 void* ctx; SbStringViewHost host;
 uint64_t call(uint32_t op,uint64_t a=0,uint64_t b=0,uint64_t c=0) {
  uint64_t out=0;auto status=host(ctx,op,a,b,c,&out);
  if(status)throw Stop{status<=2?status:2};
  switch(op){
   case SV_END:case SV_EQUAL:case SV_SPACE:case SV_VALID:if(out>1)throw Stop{2};break;
   case SV_READ:case SV_LOWER:if(out>UINT32_MAX)throw Stop{2};break;
   case SV_NATIVE_COMPARE:if(out>INT32_MAX&&out<UINT64_MAX-uint64_t(INT32_MAX))throw Stop{2};break;
   case SV_ARG:case SV_BYTES:case SV_LENGTH:case SV_FIND_BYTES:break;
   case SV_THROW_AT:case SV_THROW_SUBSTR:throw Stop{2};
   default:if(out)throw Stop{2};
  }
  return out;
 }
 uint64_t arg(unsigned a){auto value=call(SV_ARG,a);if(a==2&&value>1)throw Stop{2};return value;}
 void init(unsigned slot,unsigned role){call(SV_INIT,slot,role);}
 void adv(unsigned slot){call(SV_ADVANCE,slot);}
 bool end(unsigned slot,unsigned role){return call(SV_END,slot,role);}
 uint64_t read(unsigned slot){return call(SV_READ,slot);}
 bool eq(uint64_t a,uint64_t b,uint64_t cs){return call(SV_EQUAL,a,b,cs);}
 uint64_t at(uint64_t index,bool checked){
  init(0,0);for(uint64_t i=0;i<index;++i){adv(0);if(checked&&end(0,0))call(SV_THROW_AT,i);}return read(0);
 }
 uint64_t compareBody(uint64_t so,uint64_t sl,uint64_t oo,uint64_t ol,uint64_t cs){
  init(0,0);init(1,1);
  while(so>0&&!end(0,0)){adv(0);--so;}
  // Preserve the source's otherLen decrement; otherOffset is deliberately fixed.
  while(oo>0&&!end(1,1)){adv(1);--ol;}
  while(true){
   bool a=end(0,0)||sl==0,b=end(1,1)||ol==0;
   if(a&&b)return 0;if(a)return NP;if(b)return 1;
   auto x=read(0),y=read(1);if(cs){x=call(SV_LOWER,x);y=call(SV_LOWER,y);}
   if(x<y)return NP;if(y<x)return 1;
   adv(0);adv(1);--sl;--ol;
  }
 }
 uint64_t compare(uint64_t so,uint64_t sl,uint64_t oo,uint64_t ol,uint64_t cs){
  ++counts[48][0];try{auto r=compareBody(so,sl,oo,ol,cs);++counts[48][1];return r;}
  catch(Stop const& s){if(s.status==1)++counts[48][2];throw;}
 }
 uint64_t findChar(uint64_t ch,uint64_t pos,uint64_t cs,bool last){
  init(0,0);for(uint64_t i=0;i<pos;++i){if(end(0,0))break;adv(0);}
  uint64_t found=NP;
  while(!end(0,0)){if(eq(ch,read(0),cs)){if(!last)return pos;found=pos;}++pos;adv(0);}return found;
 }
 uint64_t findPattern(uint64_t pos,uint64_t cs,bool last){
  if(call(SV_BYTES,1)==0)return 0;
  init(0,0);for(uint64_t i=0;i<pos;++i){if(end(0,0))break;adv(0);}
  init(1,1);call(SV_COPY,2,0);uint64_t found=NP;
  while(!end(0,0)){
   if(eq(read(1),read(2),cs)){
    do{adv(2);adv(1);if(end(1,1)){if(!last)return pos;found=pos;break;}else if(end(2,0))break;}while(eq(read(1),read(2),cs));
    init(1,1);
   }
   ++pos;adv(0);call(SV_COPY,2,0);
  }return found;
 }
 bool has(uint64_t ch,unsigned role,unsigned slot){
  init(slot,role);while(!end(slot,role)){if(read(slot)==ch)return true;adv(slot);}return false;
 }
 uint64_t of(uint64_t pos,bool invert){
  init(0,0);uint64_t i=0;for(;i<pos;++i)adv(0);
  while(!end(0,0)){
   auto ch=read(0);bool match=call(SV_BYTES,1)==0?call(SV_SPACE,ch):has(ch,1,1);
   if(match!=invert)return i;adv(0);++i;
  }return NP;
 }
 uint64_t boundary(uint64_t index,bool back){
  auto n=call(SV_LENGTH,0);call(SV_ASSERT_BOUNDARY,index,n);
  if(!back&&index==n)return index;if(back){if(index==0)return 0;--index;}
  auto ch=at(index,true);
  while(!call(SV_SPACE,ch)){if(back&&index==0)return 0;index+=back?NP:1;if(index==n)return n;ch=at(index,true);}
  while(call(SV_SPACE,ch)){if(back&&index==0)return 0;index+=back?NP:1;if(index==n)return n;ch=at(index,true);}
  return back&&index!=n?index+1:index;
 }
 void split(bool any){
  if(call(SV_BYTES,1)==0)return;
  uint64_t beg=0;
  while(true){auto end=call(SV_FIND_BYTES,beg,any);
   if(end==NP){auto len=call(SV_BYTES,0)-beg;call(SV_CALLBACK,beg,len,1);break;}
   call(SV_CALLBACK,beg,end-beg,0);
   beg=end+(any?1:call(SV_BYTES,1));
  }
 }
 void run(uint32_t mode){
  uint64_t result=0;bool scalar=true;
  switch(mode+1){
   case 1:case 2:case 3:case 4:case 5:case 6:case 7:case 8:case 9:case 10:case 11:case 12:case 13:case 14:case 15:
   case 16:case 17:case 18:case 19:case 21:case 22:case 50:case 51:case 52:case 53:case 54:case 55:case 56:case 57:case 58:
    call(SV_SIMPLE,mode);scalar=false;break;
   case 20:result=call(SV_BYTES,0);break;
   case 23:case 24:result=call(SV_LENGTH,0);break;
   case 25:result=call(SV_VALID);break;
   case 26:result=call(SV_BYTES,0)==0;break;
   case 27:case 28:result=at(arg(0),mode==27);break;
   case 29:{auto n=call(SV_LENGTH,1);if(n==0){result=1;break;}auto m=call(SV_LENGTH,0);result=n<=m&&compare(m-n,NP,0,NP,arg(2))==0;break;}
   case 30:result=call(SV_BYTES,0)!=0&&eq(arg(0),at(call(SV_LENGTH,0)-1,false),arg(2));break;
   case 31:{if(call(SV_BYTES,1)==0){result=1;break;}auto n=call(SV_LENGTH,1);init(0,0);bool enough=true;for(uint64_t i=0;i!=n;++i){if(end(0,0)){enough=false;break;}adv(0);}result=enough&&compare(0,n,0,NP,arg(2))==0;break;}
   case 32:result=call(SV_BYTES,0)!=0&&eq(arg(0),at(0,false),arg(2));break;
   case 33:case 34:split(mode==32);scalar=false;break;
   case 35:result=has(arg(0),0,0);break;
   case 36:result=call(SV_BYTES,0)==0?call(SV_SPACE,arg(0)):has(arg(0),0,0);break;
   case 37:result=findChar(arg(0),arg(1),arg(2),false);break;
   case 38:result=findPattern(arg(1),arg(2),false);break;
   case 39:result=findChar(arg(0),0,arg(2),true);break;
   case 40:result=findPattern(0,arg(2),true);break;
   case 41:case 42:result=of(arg(1),mode==41);break;
   case 43:{auto back=arg(1);if(back>1)throw Stop{2};result=boundary(arg(0),back);break;}
   case 44:result=findPattern(0,arg(2),false)!=NP;break;
   case 45:case 46:case 47:{auto cs=mode==46?1:arg(2);result=cs?compare(0,NP,0,NP,cs):call(SV_NATIVE_COMPARE);if(mode!=44)result=result==0;break;}
   case 48:{auto pos=arg(0),n=arg(1);init(0,0);for(uint64_t i=0;i!=pos;++i){if(end(0,0))call(SV_THROW_SUBSTR,pos,n);adv(0);}call(SV_COPY,3,0);for(uint64_t i=0;i!=n;++i){if(end(0,0))break;adv(0);}call(SV_SUBSTR,3,0);scalar=false;break;}
   case 49:result=compareBody(arg(0),arg(1),arg(3),arg(4),arg(2));break;
   default:throw Stop{2};
  }
  if(scalar)call(SV_RETURN,result);
  // FINISH touches context bookkeeping only: the terminal callback may delete
  // the receiver while its borrowed character backing remains alive.
  call(SV_FINISH);
 }
};
}
extern "C" uint64_t sb_string_view_call_count(uint32_t mode,uint32_t event){return mode<58&&event<3?counts[mode][event]:0;}
extern "C" uint32_t sb_string_view_run(uint32_t mode,void* ctx,SbStringViewHost host){
 if(mode>=58||!ctx||!host)return 2;
 ++counts[mode][0];try{Controller{ctx,host}.run(mode);++counts[mode][1];return 0;}
 catch(Stop const& s){if(s.status==1)++counts[mode][2];return s.status;}
 catch(...){return 3;}
}
