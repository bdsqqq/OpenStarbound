#include "StarSet.hpp"
#include "StarWeightedPool.hpp"
#include "StarWeightedPool.original.hpp"
#include <iostream>
#include <iomanip>
#include <functional>
#include <typeinfo>
#include <stdexcept>
#include <cmath>
#include <cstring>

namespace Star {
struct ProxyRandomSource { double value=0; size_t calls=0; double randd(){++calls; return value;} };
namespace ProxyRandom {
static size_t doubles=0, integers=0;
static double value=0;
double randd(){++doubles; return value;}
uint64_t randu64(){++integers; return UINT64_MAX;}
}
static std::vector<uint64_t> seeds;
double proxyStaticRandomDouble(uint64_t seed){seeds.push_back(seed); return double(seed & 7)/8;}
}
#include "StarWeightedPool.proxy.hpp"
using namespace Star;
static void need(bool b, char const* why){if(!b) throw std::runtime_error(why);}
static void pass(char const* name){std::cout<<"PASS\t"<<name<<'\n';}
struct Marker:std::exception { char const* what() const noexcept override{return "weighted-marker";} };
static Marker marker;
static std::vector<std::string> events;
struct Tracked {
 int value=0;
 static bool throwMove,throwCopy;
 static std::function<void(char const*)> hook;
 Tracked(int v=0):value(v){events.push_back("new:"+std::to_string(v));}
 Tracked(Tracked const& v):value(v.value){events.push_back("copy:"+std::to_string(value)); if(throwCopy)throw &marker;}
 Tracked(Tracked&& v):value(v.value){events.push_back("move:"+std::to_string(value)); if(throwMove)throw &marker;v.value=-1;}
 Tracked& operator=(Tracked const&)=default;
 Tracked& operator=(Tracked&&)=default;
 ~Tracked(){events.push_back("dtor:"+std::to_string(value));if(hook)hook("dtor");}
};
bool Tracked::throwMove=false;bool Tracked::throwCopy=false;std::function<void(char const*)> Tracked::hook;
struct Lazy {int v; Lazy()=delete;explicit Lazy(int x):v(x){} Lazy(Lazy&&)=default;Lazy(Lazy const&)=delete;Lazy& operator=(Lazy&&)=default;};
static void trace(char const* name){std::cout<<"TRACE\t"<<name;for(auto const& e:events)std::cout<<'\t'<<e;std::cout<<'\n';events.clear();}
static void properties(){
 WeightedPool<int> p; need(p.empty()&&p.size()==0,"default"); p.add(-1,9);p.add(-0.0,8);p.add(0.0,7);p.add(1,10);p.add(1,20);
 auto const& cp=p;need(cp.items().size()==2&&&cp.at(0)==&cp.items()[0]&&&cp.item(0)==&cp.at(0).second&&cp.weight(1)==1,"accessors");pass("accessors-alias");
 auto copy=p;auto moved=std::move(copy);p.clear();p.add(2,99);need(moved.size()==2&&p.size()==1&&p.item(0)==99,"copies");pass("copy-move-clear-reuse");
 ProxyWeightedPool<int> empty;ProxyRandomSource r;need(empty.select(r)==0&&r.calls==0,"empty source");need(empty.select()==0&&ProxyRandom::doubles==0,"empty global");seeds.clear();need(empty.select(uint64_t(0))==0&&seeds.empty(),"empty static");pass("empty-select-no-random");
 need(empty.selectIndex(r)==NPos&&r.calls==1,"empty index source");need(empty.selectIndex()==NPos&&ProxyRandom::doubles==1,"empty index global");need(empty.selectIndex(uint64_t(3))==NPos&&seeds==std::vector<uint64_t>{3},"empty static index");pass("empty-index-consumes");
 empty.selectUniques(0);need(ProxyRandom::integers==1,"unique zero seed");empty.selectUniques(3);need(ProxyRandom::integers==2,"unique empty seed");pass("unique-zero-consumes-global-seed");
 ProxyWeightedPool<int> q;q.add(1,7);q.add(1,7);auto u=q.selectUniques(8,uint64_t(0));need(u.size()==2&&u[0]==7&&u[1]==7,"duplicates");pass("unique-index-not-value");
 ProxyWeightedPool<int> four;for(int i=0;i<4;++i)four.add(1,i);seeds.clear();auto all=four.selectUniques(10,UINT64_MAX);need(all==List<int>{0,1,2,3}&&seeds.front()==0&&seeds.back()==7,"wrap/order");pass("unique-seed-wrap-order");
 events.clear();{List<pair<double,Tracked>> input;input.append({1,Tracked(42)});events.clear();WeightedPool<Tracked> constructed(input);need(constructed.item(0).value==42,"container");need(std::count(events.begin(),events.end(),"copy:42")>=2,"by-value copies");}trace("container");pass("by-value-container");
 // Observe via public selection, never private-layout access. Appended second
 // item is visible during temporary destruction, but its weight is not yet in
 // the total. target .75 therefore still chooses first item.
 ProxyWeightedPool<Tracked> life;life.add(1,Tracked(10));events.clear();bool saw=false, inside=false;Tracked::hook=[&](char const*){if(!inside&&life.size()==2){inside=true;ProxyRandomSource rr;rr.value=.75;{auto selected=life.select(rr);saw=selected.value==10;}inside=false;}};life.add(1,Tracked(20));Tracked::hook=nullptr;need(saw,"append full expression before total");trace("append");pass("add-full-expression-before-total");
 events.clear();Tracked::throwMove=true;try{life.add(1,Tracked(30));need(false,"missing move throw");}catch(Marker* e){need(e==&marker&&!std::strcmp(e->what(),"weighted-marker"),"exception identity");}Tracked::throwMove=false;need(life.size()==2,"throw append state");trace("throw-move");pass("throw-move-native-identity");
 events.clear();Tracked::throwCopy=true;try{life.select(uint64_t(0));need(false,"missing copy throw");}catch(Marker* e){need(e==&marker,"select exception identity");}Tracked::throwCopy=false;need(life.size()==2,"copy throw state");trace("throw-copy");pass("throw-copy-select-unwind");
 // Reentry only observes size/empty; no mutation during vector destruction.
 size_t observed=0;Tracked::hook=[&](char const*){++observed;(void)life.empty();};life.clear();Tracked::hook=nullptr;need(observed>=2&&life.empty(),"clear reentry");trace("clear");pass("clear-observer-reentry");
 WeightedPool<Lazy> lazy;lazy.add(1,Lazy(4));need(lazy.item(0).v==4&&lazy.size()==1,"lazy");lazy.clear();pass("nondefault-moveonly-lazy");
 for(int i=0;i<3;++i){try{if(i==0)p.at(999);else if(i==1)p.item(999);else p.weight(999);need(false,"range missing");}catch(OutOfRangeException const& e){std::cout<<"RANGE\t"<<typeid(e).name()<<'\t'<<e.what()<<'\n';}}pass("native-range-exception");
 RandomSource a(123),b(123);WeightedPool<int> realEmpty;realEmpty.select(a);need(a.randu64()==b.randu64(),"real empty select");a.init(123);b.init(123);realEmpty.selectIndex(a);b.randd();need(a.randu64()==b.randu64(),"real index consume");pass("real-random-consumption");
 Random::init(321);realEmpty.select();auto after=Random::randu64();Random::init(321);need(after==Random::randu64(),"global empty");Random::init(321);realEmpty.selectUniques(0);after=Random::randu64();Random::init(321);Random::randu64();need(after==Random::randu64(),"global unique");pass("real-global-consumption");
 WeightedPool<int> real;ReferenceWeightedPool<int> ref;for(int i=0;i<4;++i){real.add(1<<i,i);ref.add(1<<i,i);}for(uint64_t s=0;s<128;++s){double t=staticRandomDouble(s);double accumulated=0;size_t want=3;for(size_t i=0;i<4;++i){accumulated+=double(1<<i)/15;if(t<=accumulated){want=i;break;}}need(real.selectIndex(s)==want,"real static");need(real.select(s)==ref.select(s)&&real.selectIndex(s)==ref.selectIndex(s),"clone parity");need(real.selectUniques(4,s)==ref.selectUniques(4,s),"clone unique parity");}pass("real-static-reference");pass("reference-clone-parity");trace("remaining");
}
int main(int argc,char** argv){std::cout<<std::unitbuf;try{
 std::string mode=argc>1?argv[1]:"properties";
 if(mode=="properties"){properties();return 0;}
 if(mode=="hang"){WeightedPool<int> p;p.add(1e308,1);p.add(1e-308,2);p.selectUniques(2,uint64_t(0));return 3;}
 if(mode=="diagnostics"){double ws[]={-1,0.0,-0.0,std::numeric_limits<double>::quiet_NaN(),std::numeric_limits<double>::infinity(),1e308,1e-308};for(double w:ws){ProxyWeightedPool<int> p;p.add(w,1);ProxyRandomSource r;r.value=.5;std::cout<<std::hexfloat<<w<<'\t'<<p.size()<<'\t'<<p.selectIndex(r)<<'\n';}return 0;}
 size_t n;while(std::cin>>n){ProxyWeightedPool<int> p;for(size_t i=0;i<n;++i){double w;std::cin>>w;p.add(w,int(i));}double target;std::cin>>target;ProxyRandomSource r;r.value=target;auto result=p.selectIndex(r);if(result==NPos)std::cout<<-1;else std::cout<<result;std::cout<<'\n';}return 0;
 }catch(std::exception const& e){std::cerr<<e.what()<<'\n';return 1;}}
