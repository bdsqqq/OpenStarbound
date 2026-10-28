// Isolated protocol checker: structural per-request conservation, no empirical minimum.
#include "StarIdMap.hpp"
#include "StarDataStreamDevices.hpp"
#include <iostream>
#include <stdexcept>
#include <type_traits>
using namespace Star;
namespace {
void check(bool b,char const* why){if(!b)throw std::runtime_error(why);}
struct Marker{void const* identity;};
using namespace Star::IdMapBoundary;
using Observer=void(*)(void*,SbIdMapHost,uint32_t,uint32_t,uint32_t,uint32_t);
extern "C" void sb_idmap_mock_observe(Observer);
extern "C" void sb_idmap_mock_fault(uint32_t);
uint64_t rejected=0,barriers=0,expectedRejected=0,expectedBarriers=0;bool failed=false;uint32_t roots=0;
void observe(void* context,SbIdMapHost host,uint32_t mode,uint32_t stage,uint32_t expected,uint32_t status){
 if(!stage)roots|=1u<<mode;
 if(status==SB_IDMAP_EXCEPTION)expectedBarriers+=22;else expectedRejected+=expected?21:22;
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
 std::cout<<"OBSERVATION\tdenials="<<rejected<<" expected="<<expectedRejected<<" barriers="<<barriers<<" expectedBarriers="<<expectedBarriers<<" roots="<<roots<<" failed="<<failed<<'\n';
 check(!failed&&rejected==expectedRejected&&barriers==expectedBarriers&&expectedBarriers==44&&roots==1023,"per-request exact denial/barrier/root conservation");
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
}
int main(){try{actualFrames();envelopes();return 0;}catch(std::exception const& e){std::cerr<<"FAIL\t"<<e.what()<<'\n';return 1;}catch(...){std::cerr<<"FAIL\tunknown\n";return 1;}}
