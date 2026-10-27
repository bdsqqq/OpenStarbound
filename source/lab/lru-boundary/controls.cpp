#include "cache.hpp"
#include "StarLruCache.hpp"
#include <cassert>
#include <iostream>
#include <string>
#include <type_traits>
#include <vector>
namespace {
int controls=0;
void require(bool condition){if(!condition)throw std::logic_error("boundary control");++controls;}
struct Protocol {int kind=0,calls=0;};
uint32_t protocol(void* raw,SbLruRequest const* request,SbLruReply* reply)noexcept{
 auto& p=*static_cast<Protocol*>(raw);++p.calls;
 *reply={sizeof(SbLruReply),SB_LRU_U64,7};
 switch(p.kind){
  case 1:reply->size=0;break;case 2:reply->tag=SB_LRU_BOOL;break;
  case 3:return 1;case 4:return 99;
  case 5:reply->tag=SB_LRU_BOOL;reply->value=2;break;
  case 6:reply->tag=SB_LRU_VOID;reply->value=1;break;
  case 7:if(request->op==SB_LRU_MAP_SIZE)reply->value=2;else if(request->op==SB_LRU_READ_MAX)reply->value=1;else *reply={sizeof(SbLruReply),SB_LRU_VOID,0};break;
  case 8:{Protocol child;SbLruReply r{sizeof(SbLruReply),0,0};if(sb_lru_run(SB_LRU_MAX,0,&child,protocol,&r)||r.value!=7)return 2;reply->value=8;break;}
  case 9:{SbLruReply r{sizeof(SbLruReply),0,0};return sb_lru_run(SB_LRU_MAX,0,raw,protocol,&r);}
 }
 return 0;
}
void protocolControls(){
 Protocol p;SbLruReply out{sizeof(SbLruReply),0,0};
 auto run=[&](uint32_t mode=SB_LRU_MAX){out={sizeof(SbLruReply),0,0};return sb_lru_run(mode,0,&p,protocol,&out);};
 require(run()==0&&out.tag==SB_LRU_U64&&out.value==7);
 for(int k:{1,2,4}){p.kind=k;require(run()==2);}
 p.kind=3;require(run()==1);
 p.kind=5;require(run(SB_LRU_REMOVE)==2);
 p.kind=6;require(run(SB_LRU_CLEAR)==2);
 p.kind=7;require(run(SB_LRU_GET)==2&&p.calls>=1000000);
 p.kind=8;require(run()==0&&out.value==8);
 p.kind=9;require(run()==2);
 p.kind=0;require(sb_lru_run(99,0,&p,protocol,&out)==2);
 require(sb_lru_run(SB_LRU_MAX,99,&p,protocol,&out)==2);
 require(sb_lru_run(SB_LRU_MAX,0,nullptr,protocol,&out)==2);
 require(sb_lru_run(SB_LRU_MAX,0,&p,nullptr,&out)==2);
 require(sb_lru_run(SB_LRU_MAX,0,&p,protocol,nullptr)==2);
 out.size=0;require(sb_lru_run(SB_LRU_MAX,0,&p,protocol,&out)==2);
 require(sb_lru_run(SB_LRU_MAX,SB_LRU_PAIR,&p,protocol,&out)==2);
}
std::vector<std::string> events;
struct V {
 int n;
 V(int x):n(x){events.push_back("new:"+std::to_string(n));}
 V(V const& o):n(o.n){events.push_back("copy:"+std::to_string(n));}
 V(V&& o):n(o.n){events.push_back("move:"+std::to_string(n));}
 V& operator=(V&& o){n=o.n;events.push_back("assign:"+std::to_string(n));return *this;}
 V& operator=(V const& o){n=o.n;events.push_back("copyassign:"+std::to_string(n));return *this;}
 ~V(){events.push_back("destroy:"+std::to_string(n));}
};
struct Fault:std::runtime_error{using std::runtime_error::runtime_error;};
template<class C> std::vector<std::string> trace(){
 events.clear();
 {
 C c(8);int key=1;
 c.get(key,[&](int const&){events.push_back("producer");key=2;c.set(9,V(90));return V(10);});
 c.set(2,V(20));auto keys=c.keys();auto vals=c.values();
 c.removeWhere([&](int const& k,V& v){events.push_back("filter:"+std::to_string(k));++v.n;return k==9;});
 try{c.get(3,[&](int const&)->V{c.set(4,V(40));throw Fault("nested");});}catch(Fault const& e){events.push_back(e.what());}
 C copied(c);C moved(std::move(c));copied=c;moved=std::move(c);
 c.setMaxSize(1);c.clear();
 }
 return events;
}
template<class Native,class Candidate> void classControls(){
 require(sizeof(Native)==sizeof(Candidate)&&alignof(Native)==alignof(Candidate));
 require(std::is_copy_constructible<Candidate>::value&&std::is_move_constructible<Candidate>::value&&std::is_copy_assignable<Candidate>::value&&std::is_move_assignable<Candidate>::value);
 auto native=trace<Native>();auto candidate=trace<Candidate>();require(native==candidate);
 Candidate c(4);c.set(1,V(10));c.set(2,V(20));
 bool typed=false;
 try{c.get(3,[&](int const&)->V{c.set(4,V(40));throw Fault("exact-message");});}catch(Fault const& e){typed=std::string(e.what())=="exact-message";}
 require(typed&&c.ptr(4)&&c.ptr(4)->n==40);
 c.get(3,[&](int const&){auto& v=c.get(5,[](int const&){return V(50);});return V(v.n+1);});
 require(c.ptr(3)&&c.ptr(3)->n==51);
}
}
int main(){
 protocolControls();
 classControls<Star::LruCache<int,V>,LruBoundary::LruCache<int,V>>();
 classControls<Star::HashLruCache<int,V>,LruBoundary::HashLruCache<int,V>>();
 for(uint32_t m=0;m<SB_LRU_MODES;++m)require(sb_lru_count(m,SB_LRU_ROOT)>0||m==SB_LRU_MAX||m==SB_LRU_SIZE||m==SB_LRU_PTR||m==SB_LRU_REMOVE);
 std::cout<<"controls\t"<<controls<<"\n";
}
