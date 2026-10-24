#include "StarRandom.hpp"
#include "StarRandom.reference.hpp"
#include "StarException.hpp"
#ifdef STAR_USE_RUST_RANDOM_MWC
#include "StarRustRandomMwc.h"
#endif
#include <array>
#include <cstring>
#include <iostream>
#include <fstream>
#include <thread>
#include <type_traits>
#include <cstdlib>
using namespace Star;
static size_t checks=0,cases=0;
static void require(bool v,char const* message){++checks;if(!v){std::cerr<<"COMPARISON "<<message<<"\n";std::exit(1);}}
// Target-specific observer: never reads tail padding, never observes an uninitialized object.
// The frozen header's three consecutive members plus these ABI guards bind the offsets.
struct State {std::array<uint32_t,256> data;uint32_t carry;uint8_t index;};
template<class R> static State state(R const& r){
 static_assert(std::is_standard_layout<R>::value && sizeof(R)==1032 && alignof(R)==4,"target ABI changed");
 State s; auto p=reinterpret_cast<unsigned char const*>(&r);
 std::memcpy(s.data.data(),p,1024);std::memcpy(&s.carry,p+1024,4);std::memcpy(&s.index,p+1028,1);return s;
}
static bool equal(State const&a,State const&b){return a.data==b.data&&a.carry==b.carry&&a.index==b.index;}
static std::ofstream stream;
static void emit(State const&s){for(auto v:s.data)stream<<v<<',';stream<<s.carry<<','<<unsigned(s.index)<<'\n';}
template<class A,class B> static void compare(A const&a,B const&b){++cases;auto x=state(a),y=state(b);require(equal(x,y),"semantic state");emit(x);}
template<class T> static bool bits(T a,T b){return std::memcmp(&a,&b,sizeof(T))==0;}
template<class T> static void observation(T v){unsigned char b[sizeof(T)];std::memcpy(b,&v,sizeof(T));for(auto x:b)stream<<unsigned(x)<<',';stream<<'\n';}
#ifdef STAR_USE_RUST_RANDOM_MWC
static std::array<uint64_t,3> counts(){return {star_random_mwc_call_count(0),star_random_mwc_call_count(1),star_random_mwc_call_count(2)};}
static void abi(){
 alignas(8) std::array<uint32_t,1024> storage;storage.fill(0xa5a5a5a5u);auto bytes=reinterpret_cast<unsigned char*>(storage.data());auto d=storage.data();auto c=storage.data()+275;auto i=bytes+1200;auto o=storage.data()+325;
 auto before=counts();require(star_random_mwc_init(d,c,i,0)==0,"raw init");auto after=counts();require(after[0]==before[0]+1&&after[1]==before[1]&&after[2]==before[2],"init receipt");
 auto invalid=[&](uint32_t*dd,uint32_t*cc,uint8_t*ii,uint32_t*oo){for(int op=0;op<3;++op){auto saved=storage;auto ct=counts();int s=op==0?star_random_mwc_init(dd,cc,ii,1):op==1?star_random_mwc_add_entropy(dd,cc,ii,1):star_random_mwc_next(dd,cc,ii,oo);require(s==2,"invalid status");require(storage==saved,"invalid transactional memory");require(ct==counts(),"invalid receipt");}};
 invalid(nullptr,c,i,o);invalid(d,nullptr,i,o);invalid(d,c,nullptr,o);invalid(reinterpret_cast<uint32_t*>(bytes+1),c,i,o);invalid(d,reinterpret_cast<uint32_t*>(bytes+1101),i,o);
 invalid(d,d,i,o);invalid(d,d+255,i,o);invalid(d,c,bytes+4,o);invalid(d,c,bytes+1023,o);invalid(d,c,reinterpret_cast<uint8_t*>(c),o);invalid(d,c,reinterpret_cast<uint8_t*>(c)+3,o);
 invalid(reinterpret_cast<uint32_t*>(uintptr_t(-4)),c,i,o);invalid(d,reinterpret_cast<uint32_t*>(uintptr_t(-4)),i,o);invalid(d,c,reinterpret_cast<uint8_t*>(uintptr_t(-1)),o);
 // Output overlap is relevant ONLY to next; init/entropy have no output argument.
 for(auto out:{d,c,reinterpret_cast<uint32_t*>(bytes+1200),static_cast<uint32_t*>(nullptr),reinterpret_cast<uint32_t*>(bytes+1301),reinterpret_cast<uint32_t*>(uintptr_t(-4))}){auto saved=storage;auto ct=counts();require(star_random_mwc_next(d,c,i,out)==2,"invalid next output");require(storage==saved&&counts()==ct,"next transactional");}
 // Raw init must not read the old, uninitialized state; compare every initialized field afterward.
 {std::array<uint32_t,256> raw;uint32_t cr;uint8_t ix;require(star_random_mwc_init(raw.data(),&cr,&ix,31415926)==0,"uninitialized init");MwcReference::RandomSource ref(31415926);auto s=state(ref);require(raw==s.data&&cr==s.carry&&ix==s.index,"raw init full state");auto ct=counts();require(star_random_mwc_add_entropy(raw.data(),&cr,&ix,27182818)==0,"raw entropy");ref.addEntropy(27182818);s=state(ref);require(raw==s.data&&cr==s.carry&&ix==s.index,"raw entropy full state");auto ca=counts();require(ca[1]==ct[1]+1&&ca[0]==ct[0]&&ca[2]==ct[2],"raw entropy receipt");}
 require(star_random_mwc_call_count(99)==0,"unknown count");auto ct=counts();std::thread t([]{require(counts()==std::array<uint64_t,3>{0,0,0},"TLS fresh");std::array<uint32_t,256>d;uint32_t c;uint8_t i;require(star_random_mwc_init(d.data(),&c,&i,9)==0,"thread init");require(counts()==std::array<uint64_t,3>{1,0,0},"TLS isolated");});t.join();require(ct==counts(),"TLS parent unchanged");
 // All carry/index bit patterns are accepted, including carry above multiplier.
 for(unsigned ix:{0u,31u,254u,255u}){for(auto carry:{0u,809430660u,0xffffffffu}){std::array<uint32_t,256>a;for(size_t n=0;n<256;++n)a[n]=uint32_t(n*1234567);uint8_t idx=ix;uint32_t cr=carry,out=0;auto expect=uint64_t(809430660)*a[uint8_t(ix+1)]+carry;auto ct=counts();require(star_random_mwc_next(a.data(),&cr,&idx,&out)==0,"all state valid");require(idx==uint8_t(ix+1)&&out==uint32_t(expect)&&cr==uint32_t(expect>>32)&&a[idx]==out,"raw next math");auto ca=counts();require(ca[2]==ct[2]+1&&ca[0]==ct[0]&&ca[1]==ct[1],"next receipt");
 // Set only valid semantic object representations, never padding or a mirror type.
 MwcReference::RandomSource ref(1);auto p=reinterpret_cast<unsigned char*>(&ref);std::memcpy(p,a.data(),1024);std::memcpy(p+1024,&carry,4);uint8_t oldix=ix;std::memcpy(p+1028,&oldix,1);cr=carry;idx=oldix;ref.addEntropy(UINT64_MAX);ct=counts();require(star_random_mwc_add_entropy(a.data(),&cr,&idx,UINT64_MAX)==0,"arbitrary entropy state");auto expected=state(ref);require(a==expected.data&&cr==expected.carry&&idx==expected.index,"arbitrary entropy math");ca=counts();require(ca[1]==ct[1]+1&&ca[0]==ct[0]&&ca[2]==ct[2],"arbitrary entropy receipt");}}
}
#endif
int main(){try{
 stream.open(std::getenv("LAB_OBSERVATIONS"));require(bool(stream),"observation open");
 std::array<uint64_t,9> seeds={0,1,31415926,0xffffffffULL,0x100000000ULL,0xffffffffffffffffULL,0x8000000000000000ULL,0x123456789abcdef0ULL,809430660};
 for(auto seed:seeds){RandomSource a(seed);MwcReference::RandomSource b(seed);compare(a,b);
 for(unsigned n=0;n<2200;++n){if(n%127==0){uint64_t e=uint64_t(n)*0x100000001ULL^seed;a.addEntropy(e);b.addEntropy(e);}else require(a.randu32()==b.randu32(),"draw");compare(a,b);}
 auto ca=a;auto cb=b;for(int n=0;n<300;++n){require(ca.randu64()==cb.randu64(),"copy fork");compare(ca,cb);}a.init(seed);b.init(seed);compare(a,b);
 }
 RandomSource anchor(31415926);uint32_t first[]={2950892229u,1418047276u,3790079132u,445970691u,2728181679u};for(auto x:first)require(anchor.randu32()==x,"existing first anchor");anchor.addEntropy(27182818);uint32_t second[]={3255590103u,678168874u,3814633989u,4070190392u,265077625u};for(auto x:second)require(anchor.randu32()==x,"existing entropy anchor");for(int n=0;n<100000;++n)anchor.randu32();require(anchor.randu32()==724230938u,"existing long anchor");
 // Exact public façade observations, with valid finite ranges only.
 for(auto seed:seeds){RandomSource a(seed);MwcReference::RandomSource b(seed);
 #define CHECK(expr) {auto x=a.expr;auto y=b.expr;require(bits(x,y),#expr);observation(x);compare(a,b);}
 for(int n=0;n<100;++n){CHECK(randf());CHECK(randd());CHECK(randf(-392.125f,3920.75f));CHECK(randd(-123.456,9876.543));CHECK(nrandf(1.25f,-2.5f));CHECK(nrandd(1.25,-2.5));CHECK(stochasticRound(-12.7));CHECK(randi32());CHECK(randi64());CHECK(randUInt(1234567));CHECK(randInt(-98765,123456));CHECK(randUInt(4,UINT64_MAX));CHECK(randb());char x[37],y[37];a.randBytes(x,sizeof x);b.randBytes(y,sizeof y);require(std::memcmp(x,y,sizeof x)==0,"bytes buffer");for(auto v:x)observation(v);compare(a,b);auto xx=a.randBytes(size_t(19));auto yy=b.randBytes(size_t(19));require(xx==yy,"bytes allocating");compare(a,b);}
 #undef CHECK
 }
 auto error=[](auto&& fn){try{fn();return std::string("NO ERROR");}catch(std::exception const&e){return printException(e,false);}};
 {RandomSource a(9);MwcReference::RandomSource b(9);
 #define BAD(expr) {auto x=error([&]{a.expr;});auto y=error([&]{b.expr;});require(x==y&&x!="NO ERROR", "full exception bytes");for(auto v:x)observation(v);compare(a,b);}
 BAD(randInt(3,2));BAD(randUInt(3,2));BAD(randf(3,2));BAD(randd(3,2));
 #undef BAD
 }
#ifdef STAR_USE_RUST_RANDOM_MWC
 abi();
 auto ct=counts();RandomSource r(7);auto ca=counts();require(ca[0]==ct[0]+1&&ca[1]==ct[1]&&ca[2]==ct[2],"ctor scoped receipts");ct=counts();r.addEntropy(3);ca=counts();require(ca[1]==ct[1]+1&&ca[0]==ct[0]&&ca[2]==ct[2],"entropy internal draws not counted");ct=counts();r.randu64();ca=counts();require(ca[2]==ct[2]+2&&ca[0]==ct[0]&&ca[1]==ct[1],"randu64 receipts");
#endif
 stream.close();std::cout<<"{\"cases\":"<<cases<<",\"checks\":"<<checks<<"}\n";return 0;
 }catch(std::exception const&e){std::cerr<<printException(e,false)<<'\n';return 2;}}
