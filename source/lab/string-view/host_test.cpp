#include "host_header.hpp"
#include <iostream>
#include <thread>
#include <stdexcept>
using namespace Star;
using namespace Star::StringViewHost;
#ifdef SV_CORPUS_AUDIT
namespace {
struct Audit {~Audit(){
 for(unsigned m=0;m<58;++m)std::cerr<<"SV_COUNT "<<m<<' '<<sb_string_view_call_count(m,0)<<' '<<sb_string_view_call_count(m,1)<<' '<<sb_string_view_call_count(m,2)<<'\n';
}} audit;
}
#else
void need(bool ok){if(!ok)throw std::runtime_error("protocol assertion failed");}
uint32_t pending(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*){return 1;}
uint32_t throwing(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*){throw 17;}
uint32_t badStatus(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*){return 42;}
uint32_t badBool(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t* o){*o=2;return 0;}
uint32_t badCompare(void*,uint32_t op,uint64_t,uint64_t,uint64_t,uint64_t* o){*o=op==SV_NATIVE_COMPARE?uint64_t(INT32_MAX)+1:0;return 0;}
uint32_t badCase(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t* o){*o=2;return 0;}
uint32_t badUnit(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t* o){*o=1;return 0;}
int main(){
 Ctx c; c.mode=25;std::string backing="abc";std::string_view v(backing);c.view=&v;
 uint64_t out=99;auto invoke=[&](uint32_t op,uint64_t a=0,uint64_t b=0,uint64_t d=0){return host(&c,op,a,b,d,&out);};
 auto before=sb_string_view_call_count(25,0);
 need(sb_string_view_run(25,nullptr,host)==2);need(sb_string_view_run(25,&c,nullptr)==2);need(sb_string_view_run(58,&c,host)==2);
 need(sb_string_view_call_count(25,0)==before);need(sb_string_view_call_count(58,0)==0);need(sb_string_view_call_count(0,3)==0);
 need(host(nullptr,SV_BYTES,0,0,0,&out)==2);need(host(&c,SV_BYTES,0,0,0,nullptr)==2);
 need(host(&c,SV_BYTES,0,0,0,&c.result)==2);
 need(host(&c,SV_BYTES,0,0,0,reinterpret_cast<uint64_t*>(UINTPTR_MAX-sizeof(uint64_t)+1))==2);
 alignas(uint64_t) char bytes[32]={};std::string_view writable(bytes,sizeof(bytes));Ctx alias;alias.mode=16;alias.mutableView=&writable;
 need(host(&alias,SV_SIMPLE,16,0,0,reinterpret_cast<uint64_t*>(bytes))==2);
 need(host(&c,SV_BYTES,0,0,0,reinterpret_cast<uint64_t*>(bytes+1))==2);
 auto oldMode=c.mode;c.mode=58;need(invoke(SV_BYTES)==2);c.mode=oldMode;
 need(sb_string_view_run(44,&c,badCompare)==2);need(sb_string_view_run(44,&c,badCase)==2);
 need(invoke(999)==2&&out==0);need(invoke(SV_ARG,6)==2);need(invoke(SV_BYTES,2)==2);
 need(invoke(SV_BYTES,0,1)==2);need(invoke(SV_INIT,4)==2);need(invoke(SV_INIT,0,2)==2);
 need(invoke(SV_ADVANCE,0)==2);need(invoke(SV_READ,0)==2);need(invoke(SV_COPY,0,4)==2);
 need(invoke(SV_INIT,0,0)==0);need(invoke(SV_END,0,1)==2);need(invoke(SV_EQUAL,1,1,2)==2);
 need(invoke(SV_LOWER,UINT64_MAX)==2);need(invoke(SV_FIND_BYTES,0,2)==2);need(invoke(SV_CALLBACK)==2);
 need(invoke(SV_SIMPLE,24)==2);need(invoke(SV_RETURN,0,1)==2);need(invoke(SV_FINISH,1)==2);
 need(sb_string_view_run(24,&c,badBool)==2);need(sb_string_view_run(4,&c,badUnit)==2);
 need(sb_string_view_run(4,&c,badStatus)==2);need(sb_string_view_run(4,&c,throwing)==3);
 auto p=sb_string_view_call_count(4,2);need(sb_string_view_run(4,&c,pending)==1);need(sb_string_view_call_count(4,2)==p+1);
 // Native catch records the exact exception object; it is rethrown only after
 // the controller returned. This negative is C++ only, never a Rust test.
 Ctx e;e.view=&v;e.mode=27;e.args[0]=3;need(sb_string_view_run(27,&e,host)==1&&bool(e.pending));
 auto saved=e.pending;try{std::rethrow_exception(e.pending);}catch(OutOfRangeException const&){need(saved==std::current_exception());}
 // FINISH permits no live receiver. An invalid sentinel is never dereferenced.
 Ctx finish;finish.mode=33;finish.view=reinterpret_cast<std::string_view const*>(1);
 need(host(&finish,SV_FINISH,0,0,0,&out)==0);
 auto mainCount=sb_string_view_call_count(25,0);bool tls=false;
 std::thread t([&]{tls=sb_string_view_call_count(25,0)==0;Ctx local;local.view=&v;execute(25,local);tls=tls&&sb_string_view_call_count(25,0)==1;});t.join();
 need(tls&&sb_string_view_call_count(25,0)==mainCount);
 std::cout<<"NATIVE_STRINGVIEW_PROTOCOL_PASS\n";
}
#endif
