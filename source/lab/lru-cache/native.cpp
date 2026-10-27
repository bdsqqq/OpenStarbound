#include "selected.hpp"
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <typeinfo>
#include <vector>
#include <string>

// Unique probe types prevent coalescing these cache instantiations with retained Core.
namespace LruNativeR1 {
struct Fault : std::runtime_error { using std::runtime_error::runtime_error; };
inline int live=0,copies=0,throwAt=0,phase=0;
inline bool trackKey=false,earlyKeyCopy=false;
struct Key {
 int n;
 Key(int n=0):n(n){}
 Key(Key const& o):n(o.n){if(trackKey&&phase==0)earlyKeyCopy=true;}
 Key& operator=(Key const&)=default;
 bool operator<(Key const& o)const{return n<o.n;}
 bool operator==(Key const& o)const{return n==o.n;}
};
struct Hash {size_t operator()(Key const& k)const{return static_cast<size_t>(k.n);}};
struct Value {
 int n;
 Value(int n=0):n(n){++live;}
 Value(Value const& o):n(o.n){if(++copies==throwAt)throw Fault("copy");++live;}
 Value(Value&& o):n(o.n){++live;}
 ~Value(){--live;}
 Value& operator=(Value const& o){n=o.n;return *this;}
 Value& operator=(Value&& o){if(o.n==-99){n=-999;throw Fault("assignment");}n=o.n;return *this;}
};
std::ostream& operator<<(std::ostream& o,Key const& k){return o<<k.n;}
std::ostream& operator<<(std::ostream& o,Value const& v){return o<<v.n;}
template<class C> std::string pairs(C const& c){
 auto keys=c.keys();auto vals=c.values();std::string s;
 for(size_t i=0;i<keys.size();++i){if(i)s+=",";s+=std::to_string(keys[i].n)+":"+std::to_string(vals[i].n);}
 return s.empty()?"-":s;
}
struct Producer {int* count;Producer(int* c):count(c){} Producer(Producer const& o):count(o.count){++*count;} Value operator()(Key const&){return Value(*count>0?1:0);}};
struct Filter {int* count;Filter(int* c):count(c){} Filter(Filter const& o):count(o.count){++*count;}bool operator()(Key const&,Value&){return false;}};
void property(char const* n,bool b){std::cout<<"@"<<n<<"\t"<<b<<"\n";}
template<class C> void properties(){
 const int initial=live;
 {
 C c(8);c.set(Key(1),Value(10));c.set(Key(2),Value(20));
 auto p=c.ptr(Key(1));c.ptr(Key(2));property("pointer-promotion-identity",c.ptr(Key(1))==p&&p->n==10);
 auto& r=c.get(Key(1),[](Key const&){return Value(999);});c.ptr(Key(2));property("reference-promotion-identity",c.ptr(Key(1))==&r&&r.n==10);
 C moved(std::move(c));property("move-ctor-copies-map",pairs(c)==pairs(moved)&&c.currentSize()==2&&c.ptr(Key(1))!=moved.ptr(Key(1)));
 C assigned(1);assigned=std::move(c);property("move-assign-copies-map",pairs(c)==pairs(assigned)&&c.currentSize()==2&&assigned.maxSize()==8);
 C copied(c);copied.set(Key(1),Value(77));property("copy-independence",c.ptr(Key(1))->n==10&&copied.ptr(Key(1))->n==77);
 C src(3);src.set(Key(1),Value(11));src.set(Key(2),Value(22));src.set(Key(3),Value(33));C dest(9);dest.set(Key(9),Value(99));
 bool fault=false;copies=0;throwAt=2;try{dest=src;}catch(Fault const& e){fault=std::string(e.what())=="copy";}throwAt=0;
 property("assignment-old-limit-partial-map",fault&&dest.maxSize()==9&&pairs(dest)=="1:11");
 int count=0;Producer prod(&count);C fresh(3);auto& val=fresh.get(Key(1),prod);property("producer-byvalue-copy",count>=1&&val.n==1);
 C pre(3);pre.set(Key(1),Value(5));pre.set(Key(2),Value(6));Value arg(8);copies=0;throwAt=1;fault=false;
 try{pre.set(Key(1),arg);}catch(Fault const& e){fault=std::string(e.what())=="copy";}throwAt=0;
 property("set-byvalue-before-body",fault&&pairs(pre)=="1:5,2:6");
 Key stable(1);C kc(2);phase=0;trackKey=true;earlyKeyCopy=false;
 kc.get(stable,[&](Key const&){phase=1;stable.n=21;return Value(10);});trackKey=false;
 property("key-copy-after-producer",!earlyKeyCopy&&pairs(kc)=="21:10");
 int fc=0;Filter ff(&fc);Star::function<bool(Key const&,Value&)> fn(ff);int before=fc;kc.removeWhere(fn);property("filter-byvalue-copy",fc>before);
 bool typed=false;try{throw Fault("producer");}catch(std::exception const& e){typed=typeid(e)==typeid(Fault)&&std::string(e.what())=="producer";}
 property("exception-dynamic-type-and-bytes",typed);
 }
 property("balanced-native-lifetimes",live==initial);
}
template<class C> int run(){
 C c;std::string line;
 while(std::getline(std::cin,line)){
 std::istringstream in(line);std::string id,op;unsigned long long raw;int v;in>>id>>op>>raw>>v;if(!in)return 2;
 int k=static_cast<int>(raw);Key key(k);std::string result="ok";std::vector<std::string> events;
 try{
 if(op=="new")c=C(static_cast<size_t>(raw));
 else if(op=="limit")c.setMaxSize(static_cast<size_t>(raw));
 else if(op=="set")c.set(key,Value(v));
 else if(op=="ptr"){auto p=c.ptr(key);result=p?std::to_string(p->n):"null";}
 else if(op=="remove")result=c.remove(key)?"1":"0";
 else if(op=="clear")c.clear();
 else if(op=="get"){
 auto& r=c.get(key,[&](Key const& input){int n=input.n;events.push_back("produce:"+std::to_string(n));
 if(v==1){c.set(key,Value(700));c.set(Key(n+1),Value(800));}
 else if(v==2){c.set(Key(n+10),Value(900));c.setMaxSize(1);}
 else if(v==3){c.set(Key(n+10),Value(901));throw Fault("producer");}
 else if(v==4)key.n=n+20;
 return Value(n*10);});result=std::to_string(r.n);
 }
 else if(op=="filter"){
 bool once=false;c.removeWhere([&](Key const& input,Value& value){int n=input.n;events.push_back("filter:"+std::to_string(n));++value.n;
 if(k==2&&n==v)throw Fault("filter");
 if(k==3&&n==2&&!once){c.ptr(Key(1));once=true;}
 return k==1||(k==2&&n<v);});
 }
 else if(op=="assignment-fault")c.set(key,Value(-99));
 else if(op=="copy"){C other(c);c.set(key,Value(v));result="source:"+pairs(other);}
 else if(op=="move"){C other(std::move(c));c.set(key,Value(v));result="source:"+pairs(other);}
 else if(op=="copy-assign"){C other;other=c;c.set(key,Value(v));result="source:"+pairs(other);}
 else if(op=="move-assign"){C other;other=std::move(c);c.set(key,Value(v));result="source:"+pairs(other);}
 else return 3;
 }catch(std::exception const& e){if(typeid(e)!=typeid(Fault))return 4;result="fault:"+std::string(e.what());}
 std::string ev;for(auto const& e:events){if(!ev.empty())ev+=",";ev+=e;}
 std::cout<<id<<"\t"<<c.maxSize()<<"\t"<<c.currentSize()<<"\t"<<pairs(c)<<"\t"<<result<<"\t"<<(ev.empty()?"-":ev)<<"\n";
 }
 properties<C>();return 0;
}
}
extern "C" __attribute__((noinline)) int lru_native_dispatch_ordered(){using namespace LruNativeR1;return run<SELECTED::LruCache<Key,Value>>();}
extern "C" __attribute__((noinline)) int lru_native_dispatch_hash(){using namespace LruNativeR1;return run<SELECTED::HashLruCache<Key,Value,Hash>>();}
int main(int argc,char** argv){
 if(argc!=2)return 1;
 if(std::string(argv[1])=="ordered")return lru_native_dispatch_ordered();
 if(std::string(argv[1])=="hash")return lru_native_dispatch_hash();
 return 1;
}
