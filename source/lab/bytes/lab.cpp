#include "StarBytes.hpp"
#include "reference.hpp"
#ifdef STAR_USE_RUST_BYTES
#include "StarRustBytes.h"
#endif
#include <array>
#include <algorithm>
#include <iostream>
#include <random>
#include <stdexcept>
#include <climits>
#include <vector>
using A=std::array<uint8_t,512>;
static uint64_t checks=0,cases=0;
static bool corrupt=false;
void ck(bool ok,const char* why){++checks;if(!ok){std::cerr<<"COMPARISON "<<why<<"\n";throw std::runtime_error(why);}}
void call(bool ref,unsigned op,int order,void* d,const void* s,size_t n){
 if(ref){auto o=static_cast<FrozenReference::ByteOrder>(order);switch(op){case 0:FrozenReference::swapByteOrder(d,n);break;case 1:FrozenReference::swapByteOrder(d,s,n);break;case 2:FrozenReference::toByteOrder(o,d,n);break;case 3:FrozenReference::toByteOrder(o,d,s,n);break;case 4:FrozenReference::fromByteOrder(o,d,n);break;case 5:FrozenReference::fromByteOrder(o,d,s,n);break;}}
 else {auto o=static_cast<Star::ByteOrder>(order);switch(op){case 0:Star::swapByteOrder(d,n);break;case 1:Star::swapByteOrder(d,s,n);break;case 2:Star::toByteOrder(o,d,n);break;case 3:Star::toByteOrder(o,d,s,n);break;case 4:Star::fromByteOrder(o,d,n);break;case 5:Star::fromByteOrder(o,d,s,n);break;}}
}
bool reverse(unsigned op,int order){return op<2 || (order!=2 && order!=int(Star::platformByteOrder()));}
void one(unsigned op,int order,size_t n,size_t d,size_t s,std::mt19937& rng){
 A a,b,e;for(auto& x:a)x=uint8_t(rng());b=e=a;
 bool rev=reverse(op,order);bool copy=op%2;
 // The expected observation models sequential writes, NOT snapshot reversal.
 if(copy){if(rev){for(size_t i=0;i<n;++i)e[d+n-1-i]=e[s+i];}else{for(size_t i=0;i<n;++i)e[d+i]=e[s+i];}}
 else if(rev){for(size_t i=0;i<n/2;++i)std::swap(e[d+i],e[d+n-1-i]);}
 call(true,op,order,a.data()+d,a.data()+s,n);
#ifdef STAR_USE_RUST_BYTES
 auto receiptBefore=star_bytes_call_count(op);
#endif
 call(false,op,order,b.data()+d,b.data()+s,n);
#ifdef STAR_USE_RUST_BYTES
 ck(star_bytes_call_count(op)==receiptBefore+1,"public operation executing-thread receipt");
#endif
 ck(a==e,"reference vs independent bytes");ck(b==e,"candidate bytes/guards/overlap");ck(a==b,"frozen reference bytes");++cases;
}
void templates(){
 uint32_t v=0x01020304u;auto host=int(Star::platformByteOrder());ck(host==int(FrozenReference::platformByteOrder()),"platform metadata");
 for(int o:{0,1,2,-1,3,INT_MAX}){auto order=static_cast<Star::ByteOrder>(o);auto ref=static_cast<FrozenReference::ByteOrder>(o);uint32_t expected=(o==2||o==host)?0x01020304u:0x04030201u;
 ck(Star::toByteOrder(order,v)==expected&&FrozenReference::toByteOrder(ref,v)==expected,"template to literal");ck(Star::fromByteOrder(order,v)==expected&&FrozenReference::fromByteOrder(ref,v)==expected,"template from literal");++cases;}
 ck(Star::toBigEndian(v)==(host==0?v:0x04030201u),"toBigEndian");ck(Star::fromBigEndian(v)==(host==0?v:0x04030201u),"fromBigEndian");ck(Star::toLittleEndian(v)==(host==1?v:0x04030201u),"toLittleEndian");ck(Star::fromLittleEndian(v)==(host==1?v:0x04030201u),"fromLittleEndian");
 // Padding remains unobserved. NoConversion transfers the complete POD while
 // assertions read initialized fields only.
 struct P{uint8_t x;uint32_t y;};P p;p.x=7;p.y=0x12345678;auto q=Star::toByteOrder(Star::ByteOrder::NoConversion,p);ck(q.x==7&&q.y==0x12345678,"POD initialized fields");
}
#ifdef STAR_USE_RUST_BYTES
void abi(){
 // Exercise the compiler-supplied platform fact independently of the Rust host.
 for(uint32_t host:{0u,1u})for(uint32_t order:{0u,1u,2u,3u,UINT32_MAX,uint32_t(INT_MAX)})for(unsigned op=0;op<6;++op){
  std::array<uint8_t,4> source{{1,2,3,4}},dest{{9,8,7,6}};auto expected=(op%2)?source:dest;
  if(op<2||(order!=2&&order!=host))std::reverse(expected.begin(),expected.end());
  ck(star_bytes_transform(dest.data(),source.data(),4,op,order,host)==0,"ABI platform metadata status");ck(dest==expected,"ABI platform metadata byte literal");
 }
 // An oversized no-access C++ call stays on its original fallback. No invalid
 // allocation is dereferenced or invented for this bounds observation.
 for(unsigned op:{2u,4u}){auto before=star_bytes_call_count(op);call(false,op,2,nullptr,nullptr,SIZE_MAX);ck(star_bytes_call_count(op)==before,"oversized C++ fallback has no receipt");}
 A a{};for(unsigned op=0;op<6;++op){auto before=star_bytes_call_count(op);ck(star_bytes_transform(a.data()+256,a.data(),16,op,0,1)==0,"ABI status");ck(star_bytes_call_count(op)==before+1,"ABI operation receipt");}
 for(unsigned op=0;op<6;++op){auto before=star_bytes_call_count(op);A b=a;ck(star_bytes_transform(a.data(),a.data()+256,16,op,0,99)==2,"invalid platform");ck(a==b&&star_bytes_call_count(op)==before,"invalid no mutation/receipt");}
 for(unsigned op:{0u,2u,4u}){auto before=star_bytes_call_count(op);ck(star_bytes_transform(nullptr,nullptr,1,op,0,1)==0,"null in-place len1");ck(star_bytes_transform(nullptr,nullptr,1024,op,2,1)==(op==0?2:0),"noop ignores buffers");ck(star_bytes_call_count(op)==before+(op==0?1:2),"noop receipt");ck(star_bytes_transform(nullptr,nullptr,SIZE_MAX,op,2,1)==2,"oversized ABI metadata rejected");}
 for(unsigned op=0;op<6;++op){auto before=star_bytes_call_count(op);ck(star_bytes_transform(nullptr,nullptr,0,op,0,1)==0,"zero null");ck(star_bytes_call_count(op)==before+1,"zero receipt");}
 for(unsigned op:{3u,5u}){A b=a;auto before=star_bytes_call_count(op);ck(star_bytes_transform(a.data(),a.data(),16,op,2,1)==2,"ABI memcpy exact overlap rejected");ck(star_bytes_transform(a.data()+1,a.data(),16,op,1,1)==2,"ABI memcpy partial overlap rejected");ck(a==b&&star_bytes_call_count(op)==before,"ABI overlap rejection transactional");}
 for(unsigned op:{0u,2u,4u}){A b=a;std::reverse(b.begin(),b.begin()+4);ck(star_bytes_transform(a.data(),reinterpret_cast<void const*>(UINTPTR_MAX),4,op,0,1)==0,"in-place source ignored");ck(a==b,"in-place source ignored bytes");}
 for(unsigned op:{1u,3u,5u}){auto before=star_bytes_call_count(op);ck(star_bytes_transform(nullptr,a.data(),1,op,0,1)==2,"copy null rejected");ck(star_bytes_transform(reinterpret_cast<void*>(UINTPTR_MAX-1),a.data(),4,op,0,1)==2,"overflow rejected");ck(star_bytes_call_count(op)==before,"invalid copy receipt");}
 ck(star_bytes_transform(a.data(),a.data(),1,9,0,1)==2,"unknown op rejected");
}
#endif
int main(int argc,char**){try{corrupt=argc>1;std::mt19937 rng(0x42595445);
 templates();
 for(unsigned op=0;op<6;++op)for(int o:{0,1,2,-1,3,INT_MAX}){
 for(size_t n=0;n<=130;++n)for(size_t off:{size_t(0),size_t(1),size_t(7)}){
 one(op,o,n,256+off,off,rng);
 if(op%2&&reverse(op,o))for(int delta:{-7,-1,0,1,7})one(op,o,n,128+delta,128,rng);
 }
 for(unsigned k=0;k<200;++k){size_t n=rng()%200;one(op,o,n,256,rng()%32,rng);}
 }
 // Defined C++ null in-place no-access cases (never null memcpy).
 for(unsigned op:{0u,2u,4u}){call(true,op,0,nullptr,nullptr,0);call(false,op,0,nullptr,nullptr,0);call(true,op,0,nullptr,nullptr,1);call(false,op,0,nullptr,nullptr,1);}
 for(unsigned op:{2u,4u})for(int o:{2,int(Star::platformByteOrder())}){call(true,op,o,nullptr,nullptr,SIZE_MAX);call(false,op,o,nullptr,nullptr,SIZE_MAX);}
 std::array<uint64_t,6> receipts{};
#ifdef STAR_USE_RUST_BYTES
 abi();for(unsigned op=0;op<6;++op){receipts[op]=star_bytes_call_count(op);ck(receipts[op]>0,"executing thread receipt");}
#endif
 if(corrupt){auto expected=receipts;receipts[0]^=1;ck(receipts==expected,"receipt comparison corruption");}
 std::cout<<"{\"cases\":"<<cases<<",\"checks\":"<<checks<<",\"platform_order\":"<<int(Star::platformByteOrder())<<",\"receipts\":[";for(unsigned op=0;op<6;++op)std::cout<<(op?",":"")<<receipts[op];std::cout<<"]}\n";
 return 0;}catch(...){return 1;}}
