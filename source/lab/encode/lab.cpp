#include "StarEncode.hpp"
#include "reference.cpp"
#include <array>
#include <cstdio>
#include <cstring>
#include <clocale>
#include <random>
#ifdef STAR_USE_RUST_ENCODE
#include "StarRustEncode.h"
#endif
using Buffer = std::array<char, 2048>;
static unsigned long long cases=0, checks=0, failures=0, receipts[5]={};
static const char* mutation="";
static size_t call(bool frozen, unsigned op, const char* p, size_t n, char* q, size_t cap, bool url) {
#define RUN(NS) switch(op) { case 0:return NS::hexEncode(p,n,q,cap); case 1:return NS::hexDecode(p,n,q,cap); case 2:return NS::nibbleDecode(p,n,q,cap); case 3:return NS::base64Encode(p,n,q,cap,url); default:return NS::base64Decode(p,n,q,cap); }
  if(frozen) { RUN(FrozenReference) } else { RUN(Star) }
#undef RUN
}
static void require(bool good,const char* why) { ++checks; if(!good) { if(failures<8) std::fprintf(stderr,"COMPARISON %s case=%llu\n",why,cases); ++failures; } }
static void test(unsigned op,const std::string& input,size_t cap,bool url=false,int offset=999) {
  ++cases;
  Buffer a,b; a.fill(char(0xa5)); b=a;
  size_t src=512, dst=offset==999?1024:size_t(int(src)+offset);
  std::memcpy(a.data()+src,input.data(),input.size()); b=a;
  auto before=b;
#ifdef STAR_USE_RUST_ENCODE
  auto count=star_encode_call_count(op);
#endif
  size_t na=call(true,op,a.data()+src,input.size(),a.data()+dst,cap,url);
  size_t nb=call(false,op,b.data()+src,input.size(),b.data()+dst,cap,url);
#ifdef STAR_USE_RUST_ENCODE
  auto delta=star_encode_call_count(op)-count;
  if(std::strcmp(mutation,"receipt")==0) delta=0;
  size_t n=input.size();
  size_t bound=op==0?2*n:op==1?n/2:op==2?n:op==3?4*((n+2)/3):3*(n/4)+(n%4>=2?n%4-1:0);
  size_t effective=std::min(cap,bound);
  if(op==0) effective=std::min(n,cap/2)*2;
  bool overlap=n && effective && (dst<src+n) && (src<dst+effective);
  // NPos is a public write limit, not an allocation. Normal disjoint calls
  // still must execute Rust after the adapter bounds the possible output.
  if(overlap) require(delta==0,"fallback receipt");
  else { require(delta==1,"normal per-op receipt"); receipts[op]+=delta; }
#endif
  static bool firstNormalCall=true;
  bool inject=firstNormalCall;firstNormalCall=false;
  if(std::strcmp(mutation,"byte")==0 && inject) b[dst]^=1;
  if(std::strcmp(mutation,"count")==0 && inject) ++nb;
  if(std::strcmp(mutation,"canary")==0 && inject) b[0]^=1;
  require(na==nb,"count"); require(a==b,"whole buffer bytes/canaries");
  size_t allowed=cap==size_t(-1)?512:cap;
  for(size_t i=0;i<b.size();++i) if(i<dst || i>=dst+allowed) { require(b[i]==before[i],"outside output prefix"); }
}
static void rangeFallback(unsigned op,size_t length) {
  ++cases;
  char input='x'; Buffer a,b; a.fill(char(0xa5));b=a;
#ifdef STAR_USE_RUST_ENCODE
  auto count=star_encode_call_count(op);
#endif
  // These declared lengths cannot describe a real object. Zero capacity makes
  // every original kernel return before reading input; no bogus dereference.
  auto na=call(true,op,&input,length,a.data(),0,false);
  auto nb=call(false,op,&input,length,b.data(),0,false);
  require(na==0 && nb==0 && a==b,"range fallback count/bytes");
#ifdef STAR_USE_RUST_ENCODE
  require(star_encode_call_count(op)==count,"range fallback receipt");
#endif
}
static void anchor(unsigned op,const std::string& in,const std::string& expected,bool url=false) {
  Buffer b; b.fill(char(0xa5)); auto n=call(true,op,in.data(),in.size(),b.data(),512,url);
  require(n==expected.size() && std::memcmp(b.data(),expected.data(),n)==0,"independent anchor");
}
int main(int argc,char**argv) {
  if(argc>1) mutation=argv[1];
  std::setlocale(LC_CTYPE,"C");
  for(unsigned op=0;op<5;++op) rangeFallback(op,size_t(-1));
  rangeFallback(3,size_t(INT32_MAX)+1);rangeFallback(4,size_t(INT32_MAX)+1);
  anchor(1,"g1F?",std::string("\x01\xf0",2)); anchor(2,"Gaf",std::string("\0\x0a\x0f",3));
  anchor(4,"Zh==","f"); anchor(4,"Zg$anything","f"); anchor(4,"Z","");
  anchor(3,"f","Zg=="); anchor(3,"f","Zg",true); anchor(0,std::string("\xff",1),"ff");
  for(unsigned v=0;v<256;++v) for(unsigned op=0;op<5;++op) for(size_t cap=0;cap<=6;++cap) test(op,std::string(1,char(v)),cap,v&1);
  for(unsigned v=0;v<65536;++v) for(size_t cap:{size_t(0),size_t(1),size_t(2),size_t(-1)}) test(1,std::string{char(v>>8),char(v)},cap);
  std::mt19937 rng(0x5eed1234);
  for(size_t len=0;len<65;++len) { std::string s(len,' '); for(char& c:s)c=char(rng()); for(unsigned op=0;op<5;++op) {
    for(size_t cap=0;cap<=len*2+5;++cap) { test(op,s,cap,false); test(op,s,cap,true); }
    test(op,s,size_t(-1));
    for(int off: {-7,-1,0,1,7}) test(op,s,len*2+5,false,off);
  }}
  for(auto s:{"Zg==","Zh==","Zm9=","Zg$anything","Z g==","Zg\n==","-_+/", "=AAA","A===","AAAA===="})
    for(unsigned op=0;op<5;++op) for(size_t cap=0;cap<20;++cap)test(op,s,cap);
  for(unsigned j=0;j<1000;++j) { std::string s(rng()%128,' ');for(char&c:s)c=char(rng());for(unsigned op=0;op<5;++op)test(op,s,rng()%260,rng()&1); }
  // Locale availability differs by host; the reference and production decoder
  // see the same unsigned-char isalnum classification at each call.
  unsigned locales=1;
  for(const char* loc:{"en_US.ISO8859-1","en_US.UTF-8"}) if(std::setlocale(LC_CTYPE,loc)) { ++locales;for(unsigned v=0;v<256;++v)test(4,std::string(4,char(v)),8); }
  std::printf("{\"cases\":%llu,\"checks\":%llu,\"failures\":%llu,\"locales\":%u,\"receipts\":[%llu,%llu,%llu,%llu,%llu]}\n",cases,checks,failures,locales,receipts[0],receipts[1],receipts[2],receipts[3],receipts[4]);
  return failures?1:0;
}
