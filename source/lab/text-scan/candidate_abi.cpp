#include "StarRustTextScan.h"
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <limits>
static void check(bool b,char const*m){if(!b)throw std::runtime_error(m);}
struct Host {unsigned calls=0;uint32_t status=0;};
static uint32_t host(void*ctx,uint32_t kind,uint64_t offset,uint64_t length){if(ctx){auto&h=*static_cast<Host*>(ctx);++h.calls;return h.status;}return 0;}
int main(int argc,char**argv){try{uint8_t data[]={'A','^','x',';','B'},out=91;Host h;
 auto run=[&](uint8_t const*p,uint64_t n,uint8_t commands,uint8_t sides,decltype(&host) callback,uint8_t*result){return star_text_scan_process(p,n,commands,sides,callback,&h,result);};
 auto invalid=[&](uint8_t const*p,uint64_t n,uint8_t commands,uint8_t sides,decltype(&host) callback,uint8_t*result){uint64_t counts[3];for(int i=0;i<3;++i)counts[i]=star_text_scan_call_count(i);out=91;auto calls=h.calls;check(run(p,n,commands,sides,callback,result)==2,"COMPARISON raw preflight status");check(out==91&&h.calls==calls,"COMPARISON preflight side effects");for(int i=0;i<3;++i)check(star_text_scan_call_count(i)==counts[i],"COMPARISON preflight counters");};
 invalid(nullptr,1,1,0,host,&out);invalid(data,5,2,0,host,&out);invalid(data,5,1,2,host,&out);invalid(data,5,1,0,nullptr,&out);invalid(data,5,1,0,host,nullptr);invalid(reinterpret_cast<uint8_t*>(UINTPTR_MAX-1),4,1,0,host,&out);invalid(data,UINT64_MAX,1,0,host,&out);
 check(run(nullptr,0,1,0,host,&out)==0&&out==1,"COMPARISON null empty");check(run(reinterpret_cast<uint8_t*>(UINTPTR_MAX),0,1,0,host,&out)==0&&out==1,"COMPARISON max empty");
 for(uint32_t status:{0u,1u,2u,3u,79u}){h.status=status;h.calls=0;out=91;uint64_t a=star_text_scan_call_count(0),b=star_text_scan_call_count(1),c=star_text_scan_call_count(2);auto code=run(data,5,1,0,host,&out);check(code==(status==0||status==1?0u:status==2?1u:2u),"COMPARISON host status mapping");check(h.calls==(status==0?3u:1u),"COMPARISON host stop");check(out==(status==0?1:status==1?0:91),"COMPARISON publication");check(star_text_scan_call_count(0)-a==1&&star_text_scan_call_count(1)-b==(status==0?2u:1u)&&star_text_scan_call_count(2)-c==(status==0?1u:0u),"COMPARISON raw attempted counts");}
 h.status=0;check(run(data,5,1,0,host,data+1)==0&&data[1]==1,"COMPARISON overlapping publication");
 check(star_text_scan_process(nullptr,0,0,0,host,nullptr,&out)==0,"COMPARISON opaque null context");check(star_text_scan_call_count(999)==0,"COMPARISON unknown receipt");
 if(argc>1)check(false,"COMPARISON deliberate raw receipt failure");std::cout<<"{\"preflight\":true,\"status_mapping\":true,\"overlap\":true}\n";return 0;}catch(std::exception const&e){std::cerr<<e.what()<<'\n';return 1;}}
