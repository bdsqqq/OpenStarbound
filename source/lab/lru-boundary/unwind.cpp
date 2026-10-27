#include "cache.hpp"
#include "StarLruCache.hpp"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>

// fixed storage keeps observation itself nonthrowing, including during unwind.
namespace {
struct Event { char kind; int value, unwinding; };
struct Trace {
 Event events[256]{}; unsigned count=0; bool overflow=false;
 bool typed=false, message=false; int keys[8]{}; unsigned keyCount=0;
};
Trace* recording=nullptr;
bool copyFault=false, reentryArmed=false;
void* reentryContext=nullptr;
bool (*removeUnrelated)(void*)=nullptr;
void event(char kind,int value) noexcept {
 if(!recording)return;
 if(recording->count==256){recording->overflow=true;return;}
 recording->events[recording->count++]={kind,value,std::uncaught_exceptions()};
}
struct CopyFault final:std::exception {
 int token=731;
 char const* what()const noexcept override{return "list-node-copy-sentinel";}
};
struct Value {
 int n;
 explicit Value(int value):n(value){event('N',n);}
 Value(Value const& other):n(other.n){
  event('C',n);
  if(copyFault&&n==70){event('F',n);throw CopyFault{};}
 }
 Value(Value&& other)noexcept:n(other.n){event('M',n);}
 Value& operator=(Value const& other){n=other.n;event('A',n);return *this;}
 Value& operator=(Value&& other)noexcept{n=other.n;event('A',n);return *this;}
 ~Value()noexcept {
  event('D',n);
  // only an unrelated key is removed; the failed node and borrowed key survive.
  if(n==70&&reentryArmed&&std::uncaught_exceptions()>0){
   reentryArmed=false;
   event('R',removeUnrelated(reentryContext)?1:0);
  }
 }
};
// a lab-only decorated real ordered map makes iterator destruction observable;
// real aliases above/below remain the mandatory insertion-fault witnesses.
struct IteratorMap {
 using Map=Star::OrderedMap<int,Value>;
 using key_type=int;using mapped_type=Value;using value_type=Map::value_type;
 struct iterator {
  Map::iterator inner;
  explicit iterator(Map::iterator i):inner(i){}
  ~iterator(){event('I',0);}
  value_type* operator->()const{return &*inner;}
  value_type& operator*()const{return *inner;}
  iterator& operator++(){++inner;return *this;}
  bool operator==(iterator const& other)const{return inner==other.inner;}
  bool operator!=(iterator const& other)const{return inner!=other.inner;}
 };
 Map map;
 size_t size()const{return map.size();}
 auto keys()const{return map.keys();}
 auto values()const{return map.values();}
 void removeFirst(){map.removeFirst();}
 void clear(){map.clear();}
 bool remove(int const& key){return map.remove(key);}
 iterator find(int const& key){return iterator(map.find(key));}
 iterator begin(){return iterator(map.begin());}
 iterator end(){return iterator(map.end());}
 iterator toBack(iterator i){return iterator(map.toBack(i.inner));}
 Value& add(int const& key,Value value){return map.add(key,std::move(value));}
 auto insert(value_type const& pair){auto result=map.insert(pair);return std::make_pair(iterator(result.first),result.second);}
 iterator erase(iterator i){return iterator(map.erase(i.inner));}
};
void check(bool value,char const* message){if(!value){std::fprintf(stderr,"unwind control: %s\n",message);std::exit(1);}}
template<class Cache> Trace trace(bool fault,bool reenter){
 Trace result;
 {
  Cache cache(8);cache.set(9,Value(90));cache.set(8,Value(80));
  recording=&result;copyFault=fault;reentryArmed=reenter;
  reentryContext=&cache;removeUnrelated=[](void* raw){return static_cast<Cache*>(raw)->remove(9);};
  try{cache.get(7,[](int const&){event('P',70);return Value(70);});}
  catch(CopyFault const& e){result.typed=e.token==731;result.message=std::strcmp(e.what(),"list-node-copy-sentinel")==0;event('E',e.token);}
  copyFault=false;reentryArmed=false;reentryContext=nullptr;removeUnrelated=nullptr;
  for(auto key:cache.keys()){check(result.keyCount<8,"key storage");result.keys[result.keyCount++]=key;}
 }
 recording=nullptr;return result;
}
bool equal(Trace const& a,Trace const& b){
 if(a.overflow||b.overflow||a.count!=b.count||a.typed!=b.typed||a.message!=b.message||a.keyCount!=b.keyCount)return false;
 for(unsigned i=0;i<a.count;++i)if(a.events[i].kind!=b.events[i].kind||a.events[i].value!=b.events[i].value||a.events[i].unwinding!=b.events[i].unwinding)return false;
 for(unsigned i=0;i<a.keyCount;++i)if(a.keys[i]!=b.keys[i])return false;
 return true;
}
unsigned count(Trace const& t,char kind,int value,int unwinding){
 unsigned n=0;for(unsigned i=0;i<t.count;++i){auto const& e=t.events[i];n+=e.kind==kind&&e.value==value&&e.unwinding==unwinding;}return n;
}
void print(char const* alias,char const* test,char const* side,Trace const& t){
 std::printf("trace\t%s\t%s\t%s\ttyped=%d\tmessage=%d\tkeys=",alias,test,side,t.typed,t.message);
 for(unsigned i=0;i<t.keyCount;++i)std::printf("%s%d",i?",":"",t.keys[i]);
 std::printf("\tevents=");
 for(unsigned i=0;i<t.count;++i){auto const& e=t.events[i];std::printf("%s%c:%d:%d",i?",":"",e.kind,e.value,e.unwinding);}
 std::printf("\n");
}
template<class Native,class Mock> void run(char const* alias,bool expectDifference){
 for(int test=0;test<3;++test){
  bool fault=test!=0,reenter=test==2;
  auto native=trace<Native>(fault,reenter);auto mock=trace<Mock>(fault,reenter);
  auto label=test==0?"success":test==1?"copy-fault":"copy-fault-reentry";
  print(alias,label,"native",native);print(alias,label,"mock",mock);
  check(!native.overflow&&!mock.overflow,"recorder capacity");
  check(count(native,'N',70,0)==1&&count(mock,'N',70,0)==1,"producer constructor");
  check(count(native,'M',70,0)==1&&count(mock,'M',70,0)==1,"pair move succeeds");
  check(count(native,'C',70,0)==1&&count(mock,'C',70,0)==1,"list-node value copy");
  if(fault){
   check(native.typed&&native.message&&mock.typed&&mock.message,"exact typed sentinel");
   check(count(native,'D',70,1)==2,"native pair and producer unwind");
   check(count(mock,'D',70,expectDifference?0:1)==2,"mock owning-scope unwind");
   check(equal(native,mock)!=expectDifference,"fault comparison");
   if(reenter){
    check(native.keyCount==1&&native.keys[0]==8,"native unrelated removal");
    check(mock.keyCount==(expectDifference?2u:1u)&&mock.keys[mock.keyCount-1]==8,"mock unrelated removal");
   }
  }else check(equal(native,mock),"success companion");
  std::printf("comparison\t%s\t%s\t%s\n",alias,label,equal(native,mock)?"equal":"DIFFERENT");
 }
}
template<class Cache> Trace iteratorTrace(bool filter){
 Trace result;
 {
  Cache cache(8);cache.set(9,Value(90));cache.set(8,Value(80));recording=&result;
  try{
   if(filter)cache.removeWhere([](int const& key,Value& value){++value.n;if(key==8)throw CopyFault{};return true;});
   else cache.get(7,[](int const&)->Value{throw CopyFault{};});
  }catch(CopyFault const& e){result.typed=e.token==731;result.message=std::strcmp(e.what(),"list-node-copy-sentinel")==0;}
  for(auto key:cache.keys())result.keys[result.keyCount++]=key;
 }
 recording=nullptr;return result;
}
void iteratorControls(bool difference){
 for(bool filter:{false,true}){
  auto native=iteratorTrace<Star::LruCacheBase<IteratorMap>>(filter);
  auto mock=iteratorTrace<LruBoundary::LruCacheBase<IteratorMap>>(filter);
  check(native.typed&&native.message&&mock.typed&&mock.message,"iterator typed sentinel");
  check(count(native,'I',0,1)==1,"native owning iterator unwinds");
  check(count(mock,'I',0,difference?0:1)>=1,"mock owning iterator cleanup");
  check(count(mock,'I',0,1)==(difference?0u:1u),"mock owning iterator unwind count");
  if(!difference)check(equal(native,mock),"exact iterator lifetime trace");
  check(native.keyCount==mock.keyCount,"iterator partial state size");
  if(filter)check(native.keyCount==1&&native.keys[0]==8&&mock.keys[0]==8&&count(native,'D',81,0)==1&&count(mock,'D',81,0)==1,"filter mutation and prior erase retained");
  print("decorated-ordered",filter?"filter-fault":"find-fault","native",native);
  print("decorated-ordered",filter?"filter-fault":"find-fault","mock",mock);
 }
 std::printf("ITERATOR_UNWIND_CONTROLS_PASS\n");
}
}
int main(){
#ifdef LRU_EXPECT_DIFFERENCE
 constexpr bool difference=true;
#else
 constexpr bool difference=false;
#endif
 run<Star::LruCache<int,Value>,LruBoundary::LruCache<int,Value>>("ordered",difference);
 run<Star::HashLruCache<int,Value>,LruBoundary::HashLruCache<int,Value>>("hash",difference);
 iteratorControls(difference);
 std::printf("%s\n",difference?"EXPECTED_NATIVE_UNWIND_MISMATCH":"NATIVE_UNWIND_CONTROLS_PASS");
}
