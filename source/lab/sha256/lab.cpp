#include "StarString.hpp"
#include "StarByteArray.hpp"
#include "StarFormat.hpp"
#include "StarEncode.hpp"
#include <iostream>
#include <vector>
#include <random>
#include <array>
#include <cstring>
#include <thread>
#define private public
#include "StarSha256.hpp"
#include "reference.hpp"
#undef private
#include "reference.cpp"
#include "candidate.cpp"
#ifdef STAR_USE_RUST_SHA256
#include "StarRustSha256.h"
#endif
static size_t checks=0,cases=0;
static std::string fault;
static void check(bool ok,const char* what){++checks;if(!ok){std::cerr<<"COMPARISON "<<what<<" case="<<cases<<"\n";std::exit(1);}}
static std::string hex(const char* p){const char*h="0123456789abcdef";std::string s;for(int i=0;i<32;++i){auto c=(unsigned char)p[i];s+=h[c>>4];s+=h[c&15];}return s;}
static void state(Star::Sha256Hasher const& a,Frozen::Sha256Hasher const& b){
 check(a.m_finished==b.m_finished,"finished");
 check(a.m_state.length==b.m_state.length && fault!="state","length");check(a.m_state.curlen==b.m_state.curlen,"curlen");
 check(!memcmp(a.m_state.state,b.m_state.state,32),"words");
 // Only initialized active bytes are semantic; never compare an inactive tail.
 check(!memcmp(a.m_state.buf,b.m_state.buf,b.m_state.curlen),"active-buffer");
}
static void push(Star::Sha256Hasher&a,Frozen::Sha256Hasher&b,const char*p,size_t n){
#ifdef STAR_USE_RUST_SHA256
 auto before=star_sha256_call_count(1);auto init=star_sha256_call_count(0);bool reset=a.m_finished;
#endif
 a.push(p,n);b.push(p,n);state(a,b);
#ifdef STAR_USE_RUST_SHA256
 check(star_sha256_call_count(1)-before+(fault=="count") == (n<=INT_MAX?1u:0u),"scoped-update-count");check(star_sha256_call_count(0)-init==(reset?1u:0u),"scoped-reset-count");
#endif
}
static void done(Star::Sha256Hasher&a,Frozen::Sha256Hasher&b){char x[32],y[32];
#ifdef STAR_USE_RUST_SHA256
 auto before=star_sha256_call_count(2);
#endif
 a.compute(x);b.compute(y);
#ifdef STAR_USE_RUST_SHA256
 check(star_sha256_call_count(2)-before==1,"scoped-final-count");
#endif
if(fault=="byte")x[0]^=1;check(!memcmp(x,y,32),"digest");state(a,b);}
static void exercise(std::vector<char> const& v,size_t split){++cases;const char*p=v.empty()?"":v.data();Star::Sha256Hasher a;Frozen::Sha256Hasher b;state(a,b);push(a,b,p,split);auto c=a;auto d=b;push(a,b,p+split,v.size()-split);done(a,b);done(a,b);auto e=a;auto f=b;push(e,f,"",0);done(e,f);done(a,b);c=a;d=b;done(c,d);push(a,b,"xyz",3);done(a,b);push(c,d,"",0);done(c,d);
 // The pre-final fork is independent of subsequent mutation of the original.
 Star::Sha256Hasher g;Frozen::Sha256Hasher h;push(g,h,p,split);auto i=g;auto j=h;Star::Sha256Hasher assigned;Frozen::Sha256Hasher assignedRef;assigned=g;assignedRef=h;push(assigned,assignedRef,"assignment",10);done(assigned,assignedRef);push(i,j,p+split,v.size()-split);done(i,j);push(g,h,"q",1);done(g,h);assigned=i;assignedRef=j;push(assigned,assignedRef,nullptr,0);done(assigned,assignedRef);assigned=g;assignedRef=h;done(assigned,assignedRef);
 char x[32],y[32];Star::sha256(p,v.size(),x);Frozen::sha256(p,v.size(),y);check(!memcmp(x,y,32),"oneshot");
 for(size_t offset:{0u,1u,31u,63u}){std::vector<char> alias(std::max<size_t>(v.size()+64,96),0);std::copy(v.begin(),v.end(),alias.begin());Star::sha256(alias.data(),v.size(),alias.data()+offset);check(!memcmp(alias.data()+offset,y,32),"oneshot-overlap");}
}
int main(int argc,char**argv){if(argc>1)fault=argv[1];std::mt19937 rng(0x256);
 for(size_t n=1;n<=12;++n)for(unsigned mask=0;mask<(1u<<(n-1));++mask){++cases;Star::Sha256Hasher a;Frozen::Sha256Hasher b;std::string s(n,'a');size_t off=0;for(size_t k=1;k<=n;++k)if(k==n||(mask&(1u<<(k-1)))){push(a,b,s.data()+off,k-off);off=k;}done(a,b);}
 for(size_t n=0;n<=193;++n){std::vector<char>v(n);for(auto&c:v)c=rng();for(size_t s=0;s<=n;++s)exercise(v,s);}
 for(int k=0;k<1000;++k){++cases;Star::Sha256Hasher a;Frozen::Sha256Hasher b;std::vector<char>v(rng()%4097);for(auto&c:v)c=rng();for(size_t off=0;off<v.size();){size_t n=std::min<size_t>(1+rng()%97,v.size()-off);push(a,b,v.data()+off,n);off+=n;if(rng()%5==0)push(a,b,"",0);}done(a,b);}
 for(int k=0;k<2000;++k){std::vector<char>v(rng()%8193);for(auto&c:v)c=rng();exercise(v,rng()%(v.size()+1));}
 for(unsigned curl=0;curl<64;++curl)for(uint32_t length:{0u,512u,0xfffffe00u,0xfffffc00u}){++cases;Star::Sha256Hasher a;Frozen::Sha256Hasher b;a.m_state.length=b.m_state.length=length;std::vector<char>v(curl,'a');push(a,b,v.data(),curl);done(a,b);done(a,b);push(a,b,"",0);done(a,b);}
 // Defined narrowing probes: the low 32 bits are nonnegative and tiny. No giant allocation.
 for(size_t n:{size_t(1)<<32,(size_t(1)<<32)+3}){++cases;Star::Sha256Hasher a;Frozen::Sha256Hasher b;push(a,b,"abc",n);done(a,b);char x[32],y[32];Star::sha256("abc",n,x);Frozen::sha256("abc",n,y);check(!memcmp(x,y,32),"narrow-oneshot");}
 // Both aliases start from fully initialized buffer contents; no tail observation.
 {++cases;Star::Sha256Hasher a;Frozen::Sha256Hasher b;push(a,b,std::string(64,'a').data(),64);
#ifdef STAR_USE_RUST_SHA256
 auto uc=star_sha256_call_count(1),fc=star_sha256_call_count(2);
#endif
 a.push(reinterpret_cast<char*>(a.m_state.buf)+3,20);b.push(reinterpret_cast<char*>(b.m_state.buf)+3,20);state(a,b);
 a.compute(reinterpret_cast<char*>(a.m_state.buf)+16);b.compute(reinterpret_cast<char*>(b.m_state.buf)+16);state(a,b);
#ifdef STAR_USE_RUST_SHA256
 check(star_sha256_call_count(1)==uc && star_sha256_call_count(2)==fc,"alias-fallback-receipts");
#endif
 }
#ifdef STAR_USE_RUST_SHA256
 {++cases;StarSha256State s;check(star_sha256_init(&s)==0,"abi-init");auto saved=s;unsigned char out[40];memset(out,0x5a,40);auto uc=star_sha256_call_count(1),fc=star_sha256_call_count(2),oc=star_sha256_call_count(3);
 check(star_sha256_update(&s,nullptr,1)==2,"null-update");check(!memcmp(&s,&saved,sizeof s),"invalid-update-transaction");
 check(star_sha256_update(&s,s.buf,1)==2,"abi-update-alias");check(!memcmp(&s,&saved,sizeof s),"alias-update-transaction");
 check(star_sha256_finalize(&s,out,31)==2,"short-output");check(!memcmp(&s,&saved,sizeof s),"invalid-final-state");for(auto c:out)check(c==0x5a,"invalid-final-output");
 check(star_sha256_finalize(&s,s.buf,32)==2,"abi-final-alias");check(!memcmp(&s,&saved,sizeof s),"alias-final-transaction");
 check(star_sha256_oneshot(nullptr,1,out,40)==2,"invalid-oneshot");for(auto c:out)check(c==0x5a,"invalid-oneshot-output");
 check(star_sha256_call_count(1)==uc && star_sha256_call_count(2)==fc && star_sha256_call_count(3)==oc,"error-no-receipt");
 s.curlen=64;saved=s;check(star_sha256_finalize(&s,out,40)==2,"invalid-curlen");check(!memcmp(&s,&saved,sizeof s),"invalid-shape-transaction");
 bool tls=false;std::thread t([&]{tls=star_sha256_call_count(0)==0;StarSha256State other;tls=tls&&star_sha256_init(&other)==0&&star_sha256_call_count(0)==1;});t.join();check(tls,"thread-local-receipt");
 }
#endif
 // Independent Python hashlib consumes these deterministic normal-domain rows.
 std::vector<std::string> anchors={"","abc","abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",std::string(1000000,'a')};
 for(auto&s:anchors){char x[32];Star::sha256(s.data(),s.size(),x);std::cout<<"VECTOR "<<s.size()<<" "<<hex(x)<<"\n";}
 for(size_t n=0;n<257;++n){std::string s(n,' ');for(size_t k=0;k<n;++k)s[k]=char((k*131+n*17)&255);char d[32];Star::sha256(s.data(),n,d);std::cout<<"HASHLIB "<<n<<" "<<hex(d)<<"\n";}
 // Seeded valid state immediately before the 32-bit bit-count boundary.
 Star::Sha256Hasher a;Frozen::Sha256Hasher b;a.m_state.length=b.m_state.length=0xfffffe00u;push(a,b,std::string(64,'a').data(),64);done(a,b);
 Star::Sha256Hasher z;z.m_state.length=0xfffffe00u;z.push(std::string(64,'a').data(),64);char x[32];z.compute(x);std::cout<<"WRAP "<<hex(x)<<"\n";
#ifdef STAR_USE_RUST_SHA256
 uint64_t counts[4];for(unsigned op=0;op<4;++op)counts[op]=star_sha256_call_count(op);if(fault=="receipt")counts[0]=0;for(auto c:counts)check(c>0,"receipt");
 std::cout<<"RECEIPTS "<<counts[0]<<" "<<counts[1]<<" "<<counts[2]<<" "<<counts[3]<<"\n";
#endif
 std::cout<<"PASS "<<cases<<" "<<checks<<"\n";
}
