// Event-only redesign: no selected Item is ever created by the observer.
// Fixed nonallocating log; reserve before arming avoids vector relocation hooks.
#include "StarSet.hpp"
#include "BoundaryWeightedPool.hpp"
#include "StarWeightedPool.original.hpp"

#include <array>
#include <iostream>
#include <cstring>
#include <stdexcept>
using namespace Star;
struct Sentinel:std::exception {char const* what()const noexcept override{return "weighted-lifecycle-sentinel";}};
static Sentinel sentinel;
struct Event {char kind;int id,from,value;};
static std::array<Event,512> logbuf;static size_t used=0;static int nextId=0,live=0,moves=0,copies=0,failMove=0,failCopy=0;static bool overflow=false;
struct Value;static void(*observe)(Value const&)noexcept=nullptr;static void* context=nullptr;
static void event(char kind,int id,int from,int value)noexcept {if(used<logbuf.size())logbuf[used++]={kind,id,from,value};else overflow=true;}
struct Value {
 int id,value;
 explicit Value(int v=0):id(++nextId),value(v){++live;event('C',id,0,value);}
 Value(Value const& v):id(++nextId),value(v.value){event('K',id,v.id,value);if(++copies==failCopy){event('X',id,v.id,value);throw &sentinel;}++live;}
 Value(Value&& v):id(++nextId),value(v.value){event('M',id,v.id,value);if(++moves==failMove){event('X',id,v.id,value);throw &sentinel;}v.value=-1;++live;}
 Value& operator=(Value const&)=default;Value& operator=(Value&&)=default;
 ~Value()noexcept {event('D',id,0,value);if(observe)observe(*this);--live;}
};
static void need(bool b,char const* why){if(!b)throw std::runtime_error(why);}
static void reset(){need(live==0,"live before reset");used=0;nextId=moves=copies=failMove=failCopy=0;overflow=false;observe=nullptr;context=nullptr;}
static void trace(char const* mode){need(!overflow&&live==0,"balanced bounded trace");std::cout<<"TRACE\t"<<mode;for(size_t i=0;i<used;++i){auto e=logbuf[i];std::cout<<'\t'<<e.kind<<':'<<e.id<<':'<<e.from<<':'<<e.value;}std::cout<<'\n';}
static uint64_t seedBetween(double low,double high){for(uint64_t s=0;s<4096;++s){double t=staticRandomDouble(s);if(low<t&&t<high)return s;}throw std::runtime_error("no declared target witness");}
template<template<class>class Pool>static void reserve(Pool<Value>& p){const_cast<typename Pool<Value>::ItemsList&>(p.items()).reserve(8);}
template<template<class>class Pool>struct Watch {
 Pool<Value>* p;Pool<int>* other=nullptr;uint64_t seed;bool mutate=false,busy=false,once=false,bad=false;size_t count=0;std::array<size_t,16> sizes{},indices{};
 static void callback(Value const& v)noexcept {auto& w=*static_cast<Watch*>(context);if(w.busy)return;w.busy=true;try{
  if(w.other){w.other->add(1,v.id);(void)w.other->selectIndex(w.seed);++w.count;}
  else {size_t i=w.count++;if(i>=w.sizes.size())w.bad=true;else{w.sizes[i]=w.p->size();w.indices[i]=w.p->selectIndex(w.seed);}if(w.mutate&&!w.once){w.once=true;w.p->clear();}}
 }catch(...){w.bad=true;}w.busy=false;}
 void arm(){context=this;observe=&callback;}void off(){observe=nullptr;context=nullptr;need(!bad,"observer operation failed");}
};
template<template<class>class Pool>static void run(){
 reset();{Pool<Value> p;reserve(p);p.add(1,Value(10));Watch<Pool>w{&p};w.seed=seedBetween(.5,1);w.arm();p.add(1,Value(20));w.off();need(w.count==2&&w.sizes[0]==2&&w.indices[0]==0&&w.sizes[1]==2&&w.indices[1]==1,"full-expression before total versus parameter after total");std::cout<<"OBS\tappend\t"<<w.count<<'\t'<<w.indices[0]<<'\t'<<w.indices[1]<<'\n';}trace("append-full-expression");
 reset();{Pool<Value>p;reserve(p);p.add(1,Value(10));Watch<Pool>w{&p};w.seed=seedBetween(.5,1);w.mutate=true;w.arm();p.add(1,Value(20));w.off();need(w.once&&p.empty(),"defined same-pool clear at stable append boundary");p.add(1,Value(30));p.add(1,Value(40));uint64_t witness=seedBetween(.25,1.0/3.0);need(p.selectIndex(witness)==0,"post-callback total must be read, not cached");std::cout<<"OBS\tmutation\t"<<w.count<<'\t'<<p.size()<<"\t0\n";}trace("same-pool-mutation");
 reset();{List<pair<double,Value>> input;input.reserve(2);input.append({1,Value(11)});input.append({1,Value(22)});int before=copies;{Pool<Value>p(input);need(p.size()==2&&p.item(0).value==11&&p.item(1).value==22,"container values");need(copies>=before+4,"container parameter and add parameter copies");}need(live==2,"only original input remains");}trace("by-value-container");
 for(int stage=1;stage<=2;++stage){reset();{Pool<Value>p;reserve(p);p.add(1,Value(10));failMove=moves+stage;bool caught=false;try{p.add(1,Value(30));}catch(Sentinel* e){caught=e==&sentinel&&!std::strcmp(e->what(),"weighted-lifecycle-sentinel");}failMove=0;need(caught&&p.size()==1&&p.item(0).value==10,"native add throw identity and strong state");p.add(1,Value(40));need(p.size()==2,"reuse after native throw");}trace(stage==1?"throw-parameter-move":"throw-storage-move");}
 reset();{Pool<Value>p;reserve(p);p.add(1,Value(10));failCopy=copies+1;bool caught=false;try{p.select(uint64_t(0));}catch(Sentinel*e){caught=e==&sentinel;}failCopy=0;need(caught&&p.size()==1&&p.item(0).value==10,"copy throw native identity");}trace("throw-return-copy");
 reset();{Pool<Value>p;reserve(p);p.add(1,Value(10));p.add(1,Value(20));Pool<int>other;Watch<Pool>w{&p};w.other=&other;w.seed=0;w.arm();p.clear();w.off();need(w.count==2&&other.size()==2&&p.empty(),"cross-pool destructor reentry");std::cout<<"OBS\treentry\t"<<w.count<<'\t'<<other.size()<<'\n';}trace("clear-cross-pool-reentry");
 reset();{Pool<Value>p;reserve(p);p.add(1,Value(10));p.add(1,Value(20));int liveBefore=live;{auto result=p.selectUniques(2,uint64_t(0));need(result.size()==2&&result[0].value==10&&result[1].value==20&&live==liveBefore+2,"named result live values");need(&result[0]!=&p.item(0)&&&result[1]!=&p.item(1),"unique result owns independent copies");std::cout<<"OBS\tresult\t"<<result.size()<<'\t'<<live<<'\n';}need(live==liveBefore,"caller result destruction");}trace("named-result-return-lifetime");
 std::cout<<"PASS\tevent-only-complete\n";
}
int main(int argc,char**argv){std::cout<<std::unitbuf;try{std::string mode=argc>1?argv[1]:"current";if(mode=="current")run<BoundaryWeightedPool>();else if(mode=="reference")run<ReferenceWeightedPool>();else throw std::runtime_error("mode");return 0;}catch(std::exception const&e){observe=nullptr;std::cerr<<e.what()<<'\n';return 1;}}
