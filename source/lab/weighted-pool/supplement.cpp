// Callback-free orthogonal acquisition after the lifecycle observer was stopped.
// No failed lifecycle assertion or native algorithm is repaired here.
#include "StarSet.hpp"
#include "StarWeightedPool.hpp"
#include "StarWeightedPool.original.hpp"
#include <iostream>
#include <typeinfo>
#include <cstring>
#include <stdexcept>
using namespace Star;
static void need(bool b,char const* why){if(!b)throw std::runtime_error(why);}
static void pass(char const* p){std::cout<<"PASS\t"<<p<<'\n';}
struct Sentinel:std::exception{char const* what()const noexcept override{return "weighted-native-sentinel";}};
static Sentinel sentinel;
struct Value {
 int value;static bool failMove,failCopy;static int copies,moves,dtors,live;
 explicit Value(int v=0):value(v){++live;}
 Value(Value const& v):value(v.value){++copies;if(failCopy)throw &sentinel;++live;}
 Value(Value&& v):value(v.value){++moves;if(failMove)throw &sentinel;v.value=-1;++live;}
 Value& operator=(Value const&)=default;Value& operator=(Value&&)=default;
 ~Value(){++dtors;--live;}
};
bool Value::failMove=false;bool Value::failCopy=false;int Value::copies=0;int Value::moves=0;int Value::dtors=0;int Value::live=0;
struct Lazy{int v;Lazy()=delete;explicit Lazy(int x):v(x){}Lazy(Lazy&&)=default;Lazy(Lazy const&)=delete;Lazy& operator=(Lazy&&)=default;};
int main(){std::cout<<std::unitbuf;try{
 WeightedPool<int> empty;RandomSource a(123),b(123);need(empty.select(a)==0,"empty real value");need(a.randu64()==b.randu64(),"empty real source no draw");a.init(123);b.init(123);need(empty.selectIndex(a)==NPos,"empty real index");b.randd();need(a.randu64()==b.randu64(),"empty index draws");pass("real-source-empty-consumption");
 Random::init(321);need(empty.select()==0,"global empty select");auto next=Random::randu64();Random::init(321);need(next==Random::randu64(),"global empty no draw");Random::init(321);need(empty.selectIndex()==NPos,"global empty index");next=Random::randu64();Random::init(321);Random::randd();need(next==Random::randu64(),"global index draw");pass("real-global-empty-consumption");
 Random::init(321);need(empty.selectUniques(0).empty(),"zero uniques");next=Random::randu64();Random::init(321);Random::randu64();need(next==Random::randu64(),"zero unique seed draw");Random::init(321);need(empty.selectUniques(8).empty(),"empty uniques");next=Random::randu64();Random::init(321);Random::randu64();need(next==Random::randu64(),"empty unique seed draw");pass("real-global-unique-empty-consumption");
 need(empty.select(uint64_t(0))==0&&empty.selectIndex(uint64_t(0))==NPos,"static empty");pass("real-static-empty");
 List<pair<double,int>> input{{1,0},{1,1},{1,2},{1,3}};WeightedPool<int> pool(input);ReferenceWeightedPool<int> ref(input);need(pool.size()==4&&pool.weight(3)==1&&&pool.item(0)==&pool.at(0).second&&&pool.items()[0]==&pool.at(0),"native access");pass("real-container-accessors");
 for(uint64_t seed=0;seed<128;++seed){double t=staticRandomDouble(seed);size_t want=t<=.25?0:t<=.5?1:t<=.75?2:3;need(pool.selectIndex(seed)==want&&pool.select(seed)==int(want),"static literal quarters");need(pool.select(seed)==ref.select(seed)&&pool.selectIndex(seed)==ref.selectIndex(seed),"reference static parity");need(pool.selectUniques(8,seed)==List<int>{0,1,2,3},"native unique order/clamp");need(pool.selectUniques(8,seed)==ref.selectUniques(8,seed),"reference unique parity");std::cout<<"SEED\t"<<seed<<'\t'<<std::hexfloat<<t<<'\t'<<want<<'\n';}pass("real-static-128-quarter-model");pass("real-reference-128-parity-and-uniques");
 a.init(456);b.init(456);for(int i=0;i<32;++i){double t=b.randd();size_t want=t<=.25?0:t<=.5?1:t<=.75?2:3;need(pool.selectIndex(a)==want,"source index");}a.init(456);b.init(456);for(int i=0;i<32;++i){double t=b.randd();int want=t<=.25?0:t<=.5?1:t<=.75?2:3;need(pool.select(a)==want,"source select");}pass("real-source-32-index-and-select");
 Random::init(789);auto globalIndex=pool.selectIndex();Random::init(789);double t=Random::randd();size_t want=t<=.25?0:t<=.5?1:t<=.75?2:3;need(globalIndex==want,"global index");Random::init(789);int globalValue=pool.select();Random::init(789);t=Random::randd();want=t<=.25?0:t<=.5?1:t<=.75?2:3;need(globalValue==int(want),"global select");Random::init(789);auto unique=pool.selectUniques(4);Random::init(789);uint64_t seed=Random::randu64();need(unique==pool.selectUniques(4,seed),"global unique");pass("real-global-nonempty-routes");
 auto copy=pool;auto moved=std::move(copy);pool.clear();pool.add(-1,7);pool.add(-0.,8);pool.add(0.,9);pool.add(2,99);need(pool.size()==1&&pool.select(uint64_t(0))==99&&moved.size()==4,"copy/move clear reuse");pass("real-copy-move-clear-reuse");
 for(int i=0;i<3;++i){bool caught=false;try{if(i==0)pool.at(999);else if(i==1)pool.item(999);else pool.weight(999);}catch(OutOfRangeException const& e){caught=true;need(typeid(e)==typeid(OutOfRangeException),"dynamic native range type");need(std::string(e.what())=="(OutOfRangeException) out of range list::at(999)","literal native what");std::cout<<"RANGE\t"<<typeid(e).name()<<'\t'<<e.what()<<'\n';}need(caught,"native range missing");}pass("real-native-range-type-message");
 WeightedPool<Lazy> lazy;lazy.add(1,Lazy(4));need(lazy.item(0).v==4,"lazy add");lazy.clear();pass("real-nondefault-moveonly-lazy");
 {WeightedPool<Value> values;Value v(12);Value::failMove=true;bool caught=false;try{values.add(1,v);}catch(Sentinel* e){caught=e==&sentinel&&!std::strcmp(e->what(),"weighted-native-sentinel");}Value::failMove=false;need(caught&&values.empty(),"native add unwind");values.add(1,v);need(values.size()==1&&values.item(0).value==12,"native after throw");pass("real-add-throw-identity-reuse");Value::failCopy=true;caught=false;try{values.select(uint64_t(0));}catch(Sentinel* e){caught=e==&sentinel;}Value::failCopy=false;need(caught&&values.item(0).value==12,"native select unwind");pass("real-select-copy-throw-identity");std::cout<<"COUNTS\t"<<Value::copies<<'\t'<<Value::moves<<'\t'<<Value::dtors<<'\t'<<Value::live<<'\n';}need(Value::live==0,"native leaked value");pass("real-value-balanced-destruction");
 return 0;}catch(std::exception const& e){std::cerr<<e.what()<<'\n';return 1;}}
