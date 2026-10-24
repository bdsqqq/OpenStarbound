#include "StarAlgorithm.hpp"
#include "StarVlqEncoding.hpp"
#include "reference.hpp"
#ifdef STAR_USE_RUST_VLQ
#include "StarRustVlq.h"
#endif
#include <array>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <type_traits>
#include <vector>
using namespace Star;
using Bytes=std::vector<uint8_t>;
static uint64_t checks=0,cases=0;
static std::string mutant;
void ck(bool b,const char* why){++checks;if(!b){std::cerr<<"COMPARISON "<<why<<"\n";throw std::runtime_error(why);}}
Bytes independent(uint64_t x){Bytes r;do{r.insert(r.begin(),uint8_t(x%128));x/=128;}while(x);for(size_t i=0;i+1<r.size();++i)r[i]+=128;return r;}
uint64_t zig(int64_t x){return x<0 ? uint64_t(-(x+1))*2+1 : uint64_t(x)*2;}
struct Marker { int code=9; };
struct State {
  std::vector<std::string> events; Bytes bytes,out; size_t pos=0,attempt=0,done=0;
  int fail=-1; uint64_t u=0xabcdef; int64_t s=-999; bool mutate=false,reenter=false,busy=false;
  std::exception_ptr error; State(){try{throw Marker{};}catch(...){error=std::current_exception();}}
  void event(std::string x){events.push_back(x+":"+std::to_string(u)+":"+std::to_string(s));if(int(events.size())==fail)std::rethrow_exception(error);if(mutate&&x=="copy")u=u*5+7;}
  void callback(){if(mutate){u=u*3+11;s=s/2+3;}if(reenter&&!busy){busy=true;uint8_t b[10];Star::writeVlqU(128,b);busy=false;}}
};
struct Proxy {
 State* p;
 operator uint8_t(){++p->attempt;p->event("convert");p->callback();if(p->pos==p->bytes.size())std::rethrow_exception(p->error);auto b=p->bytes[p->pos++];++p->done;return b;}
 template<class T> Proxy& operator=(T x){++p->attempt;p->event(std::is_same<T,int>::value?"assign-int":"assign-u8");p->callback();p->out.push_back(uint8_t(x));++p->done;return *this;}
};
struct Iter {
 State* p; explicit Iter(State& s):p(&s){}
 Iter(const Iter& x):p(x.p){p->event("copy");}
 Iter operator++(int){p->event("postfix");return *this;}
 Proxy operator*(){p->event("deref");return {p};}
};
struct Result {size_t n=NPos;bool thrown=false,same=false;};
template<bool Ref> Result invoke(State& s,int op,size_t max){Result r;Iter it(s);try{
 if(op==0)r.n=Ref?FrozenReference::writeVlqU(16384,it):Star::writeVlqU(16384,it);
 if(op==3)r.n=Ref?FrozenReference::writeVlqI(-8193,it):Star::writeVlqI(-8193,it);
 if(op==2)r.n=Ref?FrozenReference::readVlqU(s.u,it,max):Star::readVlqU(s.u,it,max);
 if(op==5)r.n=Ref?FrozenReference::readVlqI(s.s,it,max):Star::readVlqI(s.s,it,max);
 }catch(...){r.thrown=true;r.same=std::current_exception()==s.error;}
 return r;}
void eventcase(int op,Bytes bytes,size_t max,int fail,bool mutate,bool reenter){State a,b;a.bytes=b.bytes=bytes;a.fail=b.fail=fail;a.mutate=b.mutate=mutate;a.reenter=b.reenter=reenter;auto x=invoke<true>(a,op,max);auto y=invoke<false>(b,op,max);
 if(mutant=="swallowed-exception")y.thrown=false;
 if(mutant=="replaced-exception")y.same=false;
 if(mutant=="copy-events"&&!b.events.empty())b.events.erase(b.events.begin());
 ck(a.events==b.events,"iterator-event-order/copy/proxy-type");ck(a.out==b.out,"event-writer-bytes");ck(a.pos==b.pos&&a.attempt==b.attempt&&a.done==b.done,"attempted/completed IO");ck(a.u==b.u&&a.s==b.s,"partial/callback-mutation");ck(x.n==y.n&&x.thrown==y.thrown&&x.same==y.same,"exception identity/result");++cases;}
void values(uint64_t x){uint8_t a[16]={},b[16]={};auto expected=independent(x);auto n=Star::writeVlqU(x,a);auto ref=FrozenReference::writeVlqU(x,b);if(mutant=="group-order"&&n>1)std::swap(a[0],a[n-1]);ck(n==expected.size()&&n==ref,"unsigned count");ck(Bytes(a,a+n)==expected&&Bytes(a,a+n)==Bytes(b,b+ref),"unsigned bytes");ck(Star::vlqUSize(x)==n&&FrozenReference::vlqUSize(x)==n,"unsigned size");uint64_t u=99;auto ptr=a;auto rn=Star::readVlqU(u,ptr);ck(rn==n&&u==x&&ptr==a,"raw-pointer by-value");
 int64_t v=static_cast<int64_t>(x);expected=independent(zig(v));n=Star::writeVlqI(v,a);ref=FrozenReference::writeVlqI(v,b);if(mutant=="zigzag"&&v<0)a[n-1]^=1;ck(n==expected.size()&&n==ref,"signed count");ck(Bytes(a,a+n)==expected&&Bytes(a,a+n)==Bytes(b,b+ref),"signed bytes");ck(Star::vlqISize(v)==n&&FrozenReference::vlqISize(v)==n,"signed size");int64_t i=99;rn=Star::readVlqI(i,a);ck(rn==n&&i==v,"signed decode");++cases;}
void malformed(Bytes bytes,size_t max){uint64_t a=42,b=42;int64_t c=-777,d=-777;auto na=Star::readVlqU(a,bytes.data(),max),nb=FrozenReference::readVlqU(b,bytes.data(),max);if(mutant=="overflow-rejection"&&bytes[0]==0x82)na=NPos;if(mutant=="success-only"&&na==NPos)a=0;if(mutant=="greedy-read"&&max==0)na=1;ck(a==b&&na==nb,"malformed prefix/limit/overflow");na=Star::readVlqI(c,bytes.data(),max);nb=FrozenReference::readVlqI(d,bytes.data(),max);ck(c==d&&na==nb,"signed success-only commit");++cases;}
struct OutFn {State* s;OutFn(State& x):s(&x){}OutFn(const OutFn& x):s(x.s){s->event("fn-copy");}template<class T>void operator()(T v){s->event(std::is_same<T,int>::value?"fn-int":"fn-u8");s->out.push_back(uint8_t(v));}};
struct InFn {State* s;InFn(State& x):s(&x){}InFn(const InFn& x):s(x.s){s->event("fn-copy");}uint8_t operator()(){s->event("fn-read");if(s->pos==s->bytes.size())std::rethrow_exception(s->error);return s->bytes[s->pos++];}};
void functions(){State a,b;auto ao=makeFunctionOutputIterator(OutFn(a));auto bo=makeFunctionOutputIterator(OutFn(b));FrozenReference::writeVlqU(129,ao);Star::writeVlqU(129,bo);ck(a.events==b.events&&a.out==b.out,"production FunctionOutputIterator");a.events.clear();b.events.clear();a.bytes=b.bytes={0x81,0x01};auto ai=makeFunctionInputIterator(InFn(a));auto bi=makeFunctionInputIterator(InFn(b));FrozenReference::readVlqU(a.u,ai);Star::readVlqU(b.u,bi);ck(a.events==b.events&&a.pos==b.pos&&a.u==b.u,"production FunctionInputIterator");++cases;}
#ifdef STAR_USE_RUST_VLQ
int32_t nullWrite(void* context,uint8_t,uint32_t){return context?9:0;}
int32_t nullRead(void* context,uint8_t* oct){*oct=0;return context?9:0;}
struct AbiState{uint64_t* value;unsigned calls=0;};
int32_t abiRead(void* p,uint8_t* oct){auto& s=*static_cast<AbiState*>(p);++s.calls;*s.value=5;*oct=s.calls==1?0x81:0;return s.calls==3?7:0;}
void abi(){
 for(int op=0;op<6;++op){auto before=star_vlq_call_count(op);uint32_t n=77;uint64_t u=99;int64_t i=-99;int32_t status=-1;
 switch(op){case 0:status=star_vlq_write_u(128,nullWrite,nullptr,&n);break;case 1:status=star_vlq_size_u(128,&n);break;case 2:status=star_vlq_read_u(&u,nullRead,nullptr,10,&n);break;case 3:status=star_vlq_write_i(-65,nullWrite,nullptr,&n);break;case 4:status=star_vlq_size_i(-65,&n);break;case 5:status=star_vlq_read_i(&i,nullRead,nullptr,10,&n);break;}
 ck(status==0&&n==uint32_t(op==2||op==5?1:2),"ABI null context legitimate");ck(star_vlq_call_count(op)-before==1,"ABI one public receipt");}
 uint32_t n=77;uint64_t u=99;int64_t i=-99;int dummy=0;
 auto b=star_vlq_call_count(2);ck(star_vlq_read_u(&u,nullRead,&dummy,10,&n)==1&&u==0&&n==0,"ABI read abort");ck(star_vlq_call_count(2)==b+1,"ABI abort receipt");
 b=star_vlq_call_count(2);u=99;n=77;ck(star_vlq_read_u(&u,nullRead,nullptr,0,&n)==4&&u==0&&n==0,"ABI unsigned zero limit");ck(star_vlq_call_count(2)==b+1,"ABI limit receipt");
 b=star_vlq_call_count(5);n=77;ck(star_vlq_read_i(&i,nullRead,nullptr,0,&n)==4&&i==-99&&n==0,"ABI signed zero limit");ck(star_vlq_call_count(5)==b+1,"ABI signed limit receipt");
 b=star_vlq_call_count(2);n=77;ck(star_vlq_read_u(nullptr,nullRead,nullptr,10,&n)==2&&n==77,"ABI invalid untouched");ck(star_vlq_call_count(2)==b,"ABI invalid uncounted");
 AbiState state{&u};ck(star_vlq_read_u(&u,abiRead,&state,10,&n)==0&&u==640&&n==2,"ABI reload destination after callback");
 b=star_vlq_call_count(0);n=77;ck(star_vlq_write_u(128,nullWrite,&dummy,&n)==1&&n==0,"ABI writer abort");ck(star_vlq_call_count(0)==b+1,"ABI writer abort receipt");++cases;
}
#endif
int main(int argc,char**argv){if(argc>1)mutant=argv[1];try{
#ifdef STAR_USE_RUST_VLQ
 std::array<uint64_t,6> before;for(int i=0;i<6;++i)before[i]=star_vlq_call_count(i);abi();
#endif
 for(auto anchor:std::vector<std::pair<uint64_t,Bytes>>{{0,{0}},{127,{127}},{128,{0x81,0}},{16383,{0xff,0x7f}},{16384,{0x81,0x80,0}},{UINT64_MAX,{0x81,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0x7f}}})ck(independent(anchor.first)==anchor.second,"literal unsigned anchor");
 for(auto anchor:std::vector<std::pair<int64_t,Bytes>>{{-1,{1}},{-64,{127}},{-65,{0x81,1}},{64,{0x81,0}},{INT64_MIN,{0x81,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0x7f}}})ck(independent(zig(anchor.first))==anchor.second,"literal signed anchor");
 for(uint64_t x=0;x<32768;++x){values(x);values(~x);}for(int bit=0;bit<64;++bit){uint64_t x=uint64_t(1)<<bit;values(x);values(x-1);values(x+1);}std::mt19937_64 rng(0x766c71);for(int i=0;i<10000;++i)values(rng());
 std::vector<Bytes> inputs={{0},{0x80,0},{0x81},{0x81,0},{0x81,0x01},{0x82,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0},{0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x01}};
 for(auto bytes:inputs){Bytes padded=bytes;padded.resize(16,0);for(size_t max:std::vector<size_t>{0,1,2,9,10,11,NPos}){malformed(padded,max);for(int op:{0,3,2,5})for(bool mutate:{false,true}){eventcase(op,bytes,max,-1,mutate,false);for(int fail=1;fail<=48;++fail)eventcase(op,bytes,max,fail,mutate,false);}}}
 eventcase(2,{0x81,0},10,-1,true,true);functions();
 State bounded;bounded.bytes=Bytes(11,0x80);auto boundedResult=invoke<false>(bounded,2,NPos);ck(boundedResult.n==NPos&&bounded.pos==10&&bounded.u==0,"ten-byte hard bound leaves byte11");
 State eof;eof.bytes={0x81};auto eofResult=invoke<false>(eof,2,10);ck(eofResult.thrown&&eofResult.same&&eof.u==1&&eof.done==1&&eof.attempt==2,"EOF literal preserves prefix and exception identity");
 // Literal malformed anchors are not derived from either implementation.
 uint8_t over[]={0x80,0};uint64_t u=9;ck(Star::readVlqU(u,over)==2&&u==0,"overlong literal");uint8_t wrap[]={0x82,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0};ck(Star::readVlqU(u,wrap)==10&&u==0,"overflow literal");uint8_t prefix[]={0x81};int64_t s=-55;ck(Star::readVlqU(u,prefix,1)==NPos&&u==1,"unsigned partial literal");ck(Star::readVlqI(s,prefix,1)==NPos&&s==-55,"signed partial literal");u=99;s=-55;ck(Star::readVlqU(u,prefix,0)==NPos&&u==0,"host unsigned zero max");ck(Star::readVlqI(s,prefix,0)==NPos&&s==-55,"host signed zero max");
#ifdef STAR_USE_RUST_VLQ
 for(int op=0;op<6;++op){auto b=star_vlq_call_count(op);uint8_t bytes[16]={0};uint64_t u=0;int64_t s=0;switch(op){case 0:Star::writeVlqU(0,bytes);break;case 1:Star::vlqUSize(0);break;case 2:Star::readVlqU(u,bytes);break;case 3:Star::writeVlqI(0,bytes);break;case 4:Star::vlqISize(0);break;case 5:Star::readVlqI(s,bytes);break;}auto delta=star_vlq_call_count(op)-b;if(mutant=="receipt")delta=0;ck(delta==1,"scoped single public receipt");}std::cout<<"{\"receipts\":[";for(int i=0;i<6;++i){if(i)std::cout<<",";std::cout<<star_vlq_call_count(i)-before[i];}std::cout<<"],";
#else
 std::cout<<"{";
#endif
 std::cout<<"\"cases\":"<<cases<<",\"checks\":"<<checks<<"}\n";return 0;
 }catch(const std::exception&){return 1;}}
