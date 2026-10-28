#ifdef IDMAP_BOUNDARY
#include "StarIdMap.hpp"
#else
#include "../id-map/StarIdMap.original.hpp"
#endif
#include "StarDataStreamDevices.hpp"
#include <iostream>
#include <stdexcept>
#include <string>
#include <type_traits>
using namespace Star;
namespace {
void check(bool b,char const* why){if(!b)throw std::runtime_error(why);}
struct Marker{void const* identity;};
struct Key {
 static std::string trace;static bool failCopy;static int token;int value;
 Key(int v=0):value(v){trace+="V"+std::to_string(v)+";";}
 Key(Key const& k):value(k.value){trace+="C"+std::to_string(value)+";";if(failCopy)throw Marker{&token};}
 Key(Key&& k):value(k.value){trace+="M"+std::to_string(value)+";";}
 Key& operator=(Key const& k){value=k.value;trace+="A"+std::to_string(value)+";";return *this;}
 ~Key(){trace+="D"+std::to_string(value)+";";}
 friend bool operator>(Key const& a,Key const& b){return a.value>b.value;}
 friend bool operator>(Key const& a,int b){return a.value>b;}
 friend int operator-(Key const& a,Key const& b){return a.value-b.value;}
 friend bool operator<(Key const& a,Key const& b){return a.value<b.value;}
 friend bool operator>=(Key const& a,Key const& b){return a.value>=b.value;}
 friend bool operator==(Key const& a,Key const& b){return a.value==b.value;}
 friend Key operator+(Key const& a,int b){return Key(a.value+b);}
};
std::string Key::trace;bool Key::failCopy=false;int Key::token=0;
struct Opaque {Opaque()=default;Opaque(Opaque const&)=delete;};
// No mapped storage, copying or streaming API is needed by these operations.
struct TinyBase {
 using iterator=int*;using const_iterator=int const*;using key_type=Key;
 using mapped_type=Opaque;using value_type=std::pair<Key,Opaque>;
 static int occupancy;static bool collide;static int equality;
 int size()const{return occupancy;}bool contains(Key const& k)const{return collide&&k.value==10;}
 void clear(){}bool operator==(TinyBase const&)const{++equality;return true;}
 bool operator==(TinyBase const&){throw std::runtime_error("nonconst equality selected");}
 template<class A,class B>void insert(A const&,B const&)=delete;
 void keys();void values();void pairs();void empty();void get();void ptr();void maybe();void take();
 void maybeTake();void remove();void value();void begin();void end();void erase();
};
int TinyBase::occupancy=0;bool TinyBase::collide=false;int TinyBase::equality=0;
void keyTraces(){
 IdMapWrapper<TinyBase> map(Key(10),Key(12));
 for(bool collision:{false,true}){
  map.clear();TinyBase::collide=collision;Key::trace.clear();
  {auto id=map.nextId();check(id.value==(collision?11:10),"typed cursor result");std::cout<<"TRACE\tkey-"<<collision<<"\t"<<Key::trace<<'\n';}
 }
 TinyBase::collide=false;TinyBase::occupancy=9;Key::failCopy=true;Key::trace.clear();
 try{map.nextId();throw std::runtime_error("fullness missing");}catch(IdMapException const&){}
 std::cout<<"TRACE\tfull-before-copy\t"<<Key::trace<<'\n';
 TinyBase::occupancy=0;Key::trace.clear();
 try{map.nextId();throw std::runtime_error("copy failure missing");}catch(Marker const& m){check(m.identity==&Key::token,"copy exception identity");}
 Key::failCopy=false;std::cout<<"TRACE\tlocal-copy-failure\t"<<Key::trace<<'\n';
 IdMapWrapper<TinyBase> other(Key(10),Key(12)),different(Key(20),Key(22));
 TinyBase::equality=0;auto const& a=map;auto const& b=other;check(a==b,"const equal");check(!(a!=b),"nested not equal");check(!(a==different),"bounds short circuit");check(TinyBase::equality==2,"base equality short circuit and constness");
 std::cout<<"TRACE\tconst-equality\t"<<TinyBase::equality<<'\n';
#ifdef IDMAP_LAZY_AUTO_NEGATIVE
 map.add(Opaque{});
#endif
}
#ifdef IDMAP_BOUNDARY
using namespace Star::IdMapBoundary;
using Observer=void(*)(void*,SbIdMapHost,uint32_t,uint32_t,uint32_t,uint32_t);
extern "C" void sb_idmap_mock_observe(Observer);
extern "C" void sb_idmap_mock_fault(uint32_t);
uint64_t rejected=0,barriers=0;bool failed=false;uint32_t roots=0;
void observe(void* context,SbIdMapHost host,uint32_t mode,uint32_t stage,uint32_t expected,uint32_t status){
 if(!stage)roots|=1u<<mode;
 for(uint32_t op=1;op<=SB_IDMAP_OP_COUNT;++op){
  if(op==expected&&status==SB_IDMAP_OK)continue;
  SbIdMapRequest q{24,1,op,0,0};auto r=voidReply();auto before=r;
  auto s=host(context,&q,&r);
  if(s!=(status==SB_IDMAP_EXCEPTION?SB_IDMAP_EXCEPTION:SB_IDMAP_INVALID)||r.size!=before.size||r.version!=before.version||r.tag!=before.tag||r.reserved!=before.reserved||r.value!=before.value)failed=true;
  if(status==SB_IDMAP_EXCEPTION)++barriers;else ++rejected;
 }
}
void actualFrames(){
 sb_idmap_mock_observe(observe);
 IdMap<uint32_t,uint32_t> defaults;
 IdMap<uint32_t,uint32_t> a(1,3),b(1,3),different(8,10);
 a.add(1,10);check(a.nextId()==2,"collision continuation");check(a.add(20)==3,"automatic named insertion");
 try{a.add(1,99);throw std::runtime_error("missing duplicate");}catch(IdMapException const&){}
 a.add(2,30);try{a.nextId();throw std::runtime_error("missing exhaustion");}catch(IdMapException const&){}
 check(!(a==b)&&a!=b&&!(a==different),"equality routes");
 DataStreamBuffer stream;stream<<a;stream.seek(0);stream>>b;check(a==b,"stream routes");
 a.clear();b.clear();sb_idmap_mock_observe(nullptr);
 check(!failed&&rejected>1000&&barriers>=44&&roots==1023,"actual frame denied-op/pending barrier/root coverage");
 std::cout<<"CONTROL\tactual-frame-denials\t"<<rejected<<"\nCONTROL\tpending-barrier\t"<<barriers<<'\n';
 sb_idmap_mock_fault(1);bool denied=false;try{a.nextId();}catch(std::runtime_error const&){denied=true;}sb_idmap_mock_fault(0);check(denied,"forged success cannot skip fullness");
 std::cout<<"CONTROL\tcompletion-before-key-copy\tPASS\n";
}
void envelopes(){
 int touched=0;auto frame=makeFrame(SB_IDMAP_NEXT,SB_IDMAP_ROOT,[](uint32_t op){return op==SB_IDMAP_FULL;},[&](uint32_t){++touched;return boolReply(false);},[]{return true;});
 static_assert(!std::is_move_constructible<decltype(frame)>::value&&!std::is_copy_constructible<decltype(frame)>::value,"stable inline payload");
 unsigned count=0;
 for(unsigned field=0;field!=5;++field){for(uint64_t value:{1ull,2ull,23ull,25ull,99ull,UINT64_MAX}){
  SbIdMapRequest q{24,1,SB_IDMAP_FULL,0,0};auto r=voidReply();bool bad=true;
  switch(field){case 0:q.size=uint32_t(value);bad=q.size!=24;break;case 1:q.version=uint32_t(value);bad=q.version!=1;break;case 2:q.op=uint32_t(value);bad=q.op!=SB_IDMAP_FULL;break;case 3:q.reserved=uint32_t(value);break;case 4:q.arg=value;break;}
  if(bad){auto s=Frame::host(&frame,&q,&r);check(s==SB_IDMAP_INVALID&&r.tag==SB_IDMAP_VOID&&!r.value&&!touched,"invalid request mutation");++count;}
 }}
 for(unsigned field=0;field!=5;++field){SbIdMapRequest q{24,1,SB_IDMAP_FULL,0,0};auto r=voidReply();switch(field){case 0:r.size=23;break;case 1:r.version=2;break;case 2:r.tag=SB_IDMAP_BOOL;break;case 3:r.reserved=1;break;case 4:r.value=1;break;}check(Frame::host(&frame,&q,&r)==SB_IDMAP_INVALID&&!touched,"invalid destination mutation");++count;}
 SbIdMapRequest q{24,1,SB_IDMAP_FULL,0,0};auto r=voidReply();check(Frame::host(nullptr,&q,&r)==SB_IDMAP_INVALID&&Frame::host(&frame,nullptr,&r)==SB_IDMAP_INVALID&&Frame::host(&frame,&q,nullptr)==SB_IDMAP_INVALID&&!touched,"null envelope mutation");count+=3;
 r={24,1,UINT32_MAX,0,UINT64_MAX};check(Frame::host(&frame,&q,&r)==SB_IDMAP_OK&&touched==1&&r.tag==SB_IDMAP_BOOL&&!r.value,"actual Rust sentinel destination");
 Frame nullCallbacks(SB_IDMAP_NEXT,SB_IDMAP_ROOT,nullptr,nullptr,nullptr,nullptr);r=voidReply();check(Frame::host(&nullCallbacks,&q,&r)==SB_IDMAP_INVALID,"null callbacks fail closed");
 std::cout<<"CONTROL\tnull-callbacks\tPASS\n";
 std::cout<<"CONTROL\tenvelopes\t"<<count<<'\n';
 int token=0;auto throwing=makeFrame(SB_IDMAP_NEXT,SB_IDMAP_ROOT,[](uint32_t){return true;},[&](uint32_t)->SbIdMapReply{throw Marker{&token};},[]{return false;});
 bool caught=false;try{throwing.run();}catch(Marker const& m){caught=m.identity==&token;}check(caught,"exception identity outside policy");
 for(uint32_t op=1;op<=22;++op){q.op=op;r=voidReply();check(Frame::host(&throwing,&q,&r)==SB_IDMAP_EXCEPTION,"pending exception barrier");}
 std::cout<<"CONTROL\texception-identity-and-barrier\tPASS\n";
}
#endif
}
int main(){try{keyTraces();
#ifdef IDMAP_BOUNDARY
actualFrames();envelopes();
#endif
return 0;}catch(std::exception const& e){std::cerr<<"FAIL\t"<<e.what()<<'\n';return 1;}catch(...){std::cerr<<"FAIL\tunknown\n";return 1;}}
