// One TU: real production class plus byte-identical header with dependency/name proxies.
#include "StarTtlCache.hpp"
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <type_traits>
#include <vector>
#include <exception>
#include <thread>
#include <chrono>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
namespace TtlNativeR1 {
struct Fault : std::runtime_error { using std::runtime_error::runtime_error; };
inline int64_t now=100, jitter=0;
inline int timeCalls=0,randomCalls=0, failTime=0,failRandom=0;
inline std::vector<std::string> dependencies;
}
namespace Star {
namespace ScriptTime {
int64_t monotonicMilliseconds(){using namespace TtlNativeR1; ++timeCalls;dependencies.push_back("T:"+std::to_string(now));if(failTime==timeCalls)throw Fault("clock\x01");return now;}
}
namespace ScriptRandom {
long long randInt(long long lo,long long hi){using namespace TtlNativeR1;++randomCalls;dependencies.push_back("R:"+std::to_string(lo)+":"+std::to_string(hi));if(failRandom==randomCalls)throw Fault("random\x02");if(hi<lo)throw StarException("Maximum bound in randInt must be >= minimum bound!");if(jitter<lo||jitter>hi)throw Fault("script-domain");return jitter;}
}
}
#define Time ScriptTime
#define Random ScriptRandom
#define TtlCacheBase ScriptTtlCacheBase
#define TtlCache ScriptTtlCache
#define HashTtlCache ScriptHashTtlCache
#include "StarTtlCache.original.hpp"
#undef HashTtlCache
#undef TtlCache
#undef TtlCacheBase
#undef Random
#undef Time
namespace TtlNativeR1 {
struct Key {
 int n=0; Key(int n=0):n(n){} bool operator<(Key const& x)const{return n<x.n;} bool operator==(Key const& x)const{return n==x.n;}
};
struct Hash {size_t operator()(Key const& k)const{return static_cast<size_t>(k.n);}};
std::ostream& operator<<(std::ostream& o,Key const& k){return o<<k.n;}
using Ordered=Star::ScriptTtlCache<Key,int>;
using Hashed=Star::ScriptHashTtlCache<Key,int,Hash>;
using Real=Star::TtlCache<Key,int>;
using RealHash=Star::HashTtlCache<Key,int,Hash>;
static_assert(sizeof(Ordered)==sizeof(Real));
static_assert(alignof(Ordered)==alignof(Real));
static_assert(std::is_copy_constructible_v<Real> && std::is_move_constructible_v<Real>);
static_assert(std::is_copy_assignable_v<Real> && std::is_move_assignable_v<Real>);
std::string hex(std::string const& s){static char const* h="0123456789abcdef";std::string out;for(unsigned char c:s){out+=h[c>>4];out+=h[c&15];}return out;}
std::string join(std::vector<std::string> const& v){std::string s;for(auto const& x:v){if(!s.empty())s+=",";s+=x;}return s.empty()?"-":s;}
template<class C> std::string state(C const& c){auto keys=c.keys();auto vals=c.values();std::vector<std::string> pairs;for(size_t i=0;i<keys.size();++i)pairs.push_back(std::to_string(keys[i].n)+":"+std::to_string(vals[i]));return join(pairs);}
template<class C> int stream(){
 C c;std::string line;
 while(std::getline(std::cin,line)){
  std::istringstream in(line);int id;std::string op;long long a=0,b=0,d=0,e=0;in>>id>>op>>a>>b>>d>>e;if(!in)return 2;
  std::string result="ok";std::vector<std::string> events;dependencies.clear();timeCalls=randomCalls=0;failTime=failRandom=0;
  try {
   if(op=="new")c=C(a,static_cast<int>(b),static_cast<size_t>(d),e);
   else if(op=="clock"){now=a;jitter=b;}
   else if(op=="fault-set"){failTime=d;failRandom=e;c.set(Key(a),static_cast<int>(b));}
   else if(op=="fault-get"){failTime=d;failRandom=e;result=std::to_string(c.get(Key(a),[&](Key const& k){events.push_back("P:"+std::to_string(k.n));return static_cast<int>(b);}));}
   else if(op=="fault-ptr"){failTime=d;failRandom=e;auto p=c.ptr(Key(a));result=p?std::to_string(*p):"null";}
   else if(op=="set")c.set(Key(a),static_cast<int>(b));
   else if(op=="ptr"){auto p=c.ptr(Key(a));result=p?std::to_string(*p):"null";}
   else if(op=="get"){
    Key key(a);auto& value=c.get(key,[&](Key const& k){events.push_back("P:"+std::to_string(k.n));
     if(d==1)throw Fault("producer\x04");
     if(d==2){c.set(Key(a+10),900);throw Fault("producer\x04");}
     if(d==3){c.set(Key(a),700);c.set(Key(a+1),800);}
     if(d==4)key.n+=20;
     return static_cast<int>(b);});result=std::to_string(value);
   }
   else if(op=="ttl")c.setTimeToLive(a);
   else if(op=="smear")c.setTimeSmear(static_cast<int>(a));
   else if(op=="update")c.setTtlUpdateEnabled(a);
   else if(op=="limit")c.setMaxSize(static_cast<size_t>(a));
   else if(op=="remove")result=c.remove(Key(a))?"1":"0";
   else if(op=="clear")c.clear();
   else if(op=="cleanup"){
    int count=0;
    if(a==0)c.cleanup();
    else c.cleanup([&](Key const& k,int const&){events.push_back("F:"+std::to_string(k.n));++count;
      if(a==3&&count==b)throw Fault("filter\x03");
      if(a==4)c.setTimeToLive(b);
      if(a==5)now+=b;
      if(a==6)c.ptr(Key(b));
      return a==1||(a==2&&k.n%2==0);});
   }
   else if(op=="filter"){
    c.removeWhere([&](Key const& k,int& v){events.push_back("F:"+std::to_string(k.n));++v;
      if(a==2&&k.n==b)throw Fault("filter\x03");
      if(a==3)c.ptr(Key(b));
      return a==1||(a==2&&k.n<b);});
   }
   else if(op=="copy"||op=="move"||op=="assign"||op=="move-assign"){
    C other; if(op=="copy"){C temp(c);other=temp;}else if(op=="move"){C temp(std::move(c));other=temp;}else if(op=="assign")other=c;else other=std::move(c);
    result="other:"+state(other);c.set(Key(a),static_cast<int>(b));
   }
   else if(op=="snapshot")result=state(c);
   else return 3;
  } catch(Fault const& x){result="fault:"+hex(x.what());}
    catch(Star::StarException const& x){result="star:"+hex(x.what());}
  std::cout<<id<<"\t"<<c.timeToLive()<<"\t"<<c.timeSmear()<<"\t"<<c.maxSize()<<"\t"<<c.ttlUpdateEnabled()<<"\t"<<c.currentSize()<<"\t"<<state(c)<<"\t"<<result<<"\t"<<join(events)<<"\t"<<timeCalls<<"\t"<<randomCalls<<"\t"<<join(dependencies)<<"\n";
 }
 return 0;
}
template<class C> void realSmoke(char const* alias){
 Star::Random::init(0x12345678);C c(10000,0,4,false);auto start=Star::Time::monotonicMilliseconds();
 c.set(Key(1),11);c.get(Key(2),[](Key const&){return 22;});c.cleanup();
 if(c.currentSize()!=2||!c.ptr(Key(1))||*c.ptr(Key(1))!=11)throw Fault("real retention");
 c.setTimeSmear(3);c.set(Key(3),33);c.setTtlUpdateEnabled(true);c.ptr(Key(3));
 // A negative TTL well beyond the bounded smear expires without a clock-delay oracle.
 c.setTimeToLive(-100000);c.cleanup();if(c.currentSize()!=0)throw Fault("real expiry");
 auto end=Star::Time::monotonicMilliseconds();if(end<start)throw Fault("real monotonic");
 std::cout<<"real-smoke\t"<<alias<<"\t"<<start<<"\t"<<end<<"\t"<<sizeof(C)<<"\t"<<alignof(C)<<"\n";
}
#include "lifecycle.inc"
void runtimeImages(){
 std::cout<<"compiler\t"<<__clang_version__<<"\tapple="<<__apple_build_version__<<"\tlibcpp="<<_LIBCPP_VERSION<<"\tpointer="<<sizeof(void*)<<"\n";
 for(uint32_t i=0;i<_dyld_image_count();++i){
  auto h=reinterpret_cast<mach_header_64 const*>(_dyld_get_image_header(i));
  auto p=reinterpret_cast<char const*>(h)+sizeof(mach_header_64);
  std::string uuid="absent";
  for(uint32_t j=0;j<h->ncmds;++j){auto cmd=reinterpret_cast<load_command const*>(p);if(cmd->cmd==LC_UUID){auto u=reinterpret_cast<uuid_command const*>(p);uuid=hex(std::string(reinterpret_cast<char const*>(u->uuid),16));}p+=cmd->cmdsize;}
  std::cout<<"loaded-image\t"<<_dyld_get_image_name(i)<<"\t"<<uuid<<"\n";
 }
}
}
int main(int argc,char** argv){using namespace TtlNativeR1;if(argc!=2)return 1;std::string mode=argv[1];if(mode=="ordered")return stream<Ordered>();if(mode=="hash")return stream<Hashed>();if(mode=="lifecycle"){lifecycles();return 0;}if(mode=="real"){realSmoke<Real>("ordered");realSmoke<RealHash>("hash");runtimeImages();return 0;}return 1;}
