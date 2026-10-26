#include "StarIODevice.hpp"
#ifdef LAB_REFERENCE
#include "StarIODevice.reference.hpp"
#endif
#include <iostream>
#include <sstream>
#include <cstdint>
using namespace Star;
#ifdef LAB_REFERENCE
namespace D = Star::IODeviceReference;
#else
namespace D = Star;
#endif
using B=D::IODevice;
std::string hex(char const* p,size_t n) {std::string s; for(size_t i=0;i<n;++i){auto c=(unsigned char)p[i];s+="0123456789abcdef"[c>>4];s+="0123456789abcdef"[c&15];}return s;}
struct Spy:B {
 StreamOffset cursor=6;char bytes[8]={'.','.','.','.','.','.','.','.'};char input[8]={'a','b','c','d','e','f','g','h'};std::string sink,events;int ordinal=0;std::string direction,fault;std::exception_ptr marker;void const* identity=nullptr;
 Spy(std::string d,std::string f):direction(d),fault(f){marker=std::make_exception_ptr(IOException("ledger-marker",false));try{std::rethrow_exception(marker);}catch(IOException const&e){identity=&e;}}
 void event(std::string op,std::string phase,int ptr=-1,size_t len=0,size_t n=0,StreamOffset arg=0){if(!events.empty())events+=",";events+="{\"op\":\""+op+"\",\"phase\":\""+phase+"\",\"cursor\":"+std::to_string(cursor)+",\"ptr\":"+std::to_string(ptr)+",\"len\":"+std::to_string(len)+",\"n\":"+std::to_string(n)+",\"arg\":"+std::to_string(arg)+",\"ordinal\":"+std::to_string(ordinal)+",\"output\":\""+hex(bytes,8)+"\",\"sink\":\""+hex(sink.data(),sink.size())+"\"}";}
 size_t io(char* dst,char const* src,size_t len){++ordinal;auto base=direction=="read"?bytes:input;auto p=direction=="read"?dst:src;auto addr=(uintptr_t)p,b=(uintptr_t)base;size_t n=std::min(len,size_t(2));if(addr<b||addr-b>8||n>8-(addr-b))throw std::runtime_error("source bounds");int rel=int(addr-b);event(direction,"before",rel,len);if(ordinal==2&&fault=="before-second-IO"){event(direction,"throw",rel,len);std::rethrow_exception(marker);}if(direction=="read")for(size_t i=0;i<n;++i)dst[i]=char('A'+ordinal-1);else sink.append(src,n);cursor+=n;event(direction,"mutated",rel,len,n);if(ordinal==2&&fault=="after-second-IO"){event(direction,"throw",rel,len,n);std::rethrow_exception(marker);}event(direction,"return",rel,len,n);return n;}
 size_t read(char* p,size_t n)override{return io(p,nullptr,n);}size_t write(char const*p,size_t n)override{return io(nullptr,p,n);}
 StreamOffset pos()override{event("pos","before");event("pos","return");return cursor;}
 void seek(StreamOffset p,D::IOSeek mode=D::IOSeek::Absolute)override{if(mode!=D::IOSeek::Absolute)throw std::runtime_error("unexpected seek mode");event("seek","before",-1,0,0,p);cursor=p;event("seek","mutated",-1,0,0,p);event("seek","return",-1,0,0,p);}
 D::IODevicePtr clone()override{return {};}
};
int main(){for(std::string d:{"read","write"})for(std::string f:{"none","before-second-IO","after-second-IO"}){Spy s(d,f);std::string result="OK";try{if(d=="read")s.B::readFullAbsolute(-4,s.bytes,5);else s.B::writeFullAbsolute(-4,s.input,5);}catch(IOException const&e){result=&e==s.identity?"IO/same":"IO/other";}catch(std::exception const&){result="OTHER";}std::cout<<"{\"case\":\""<<d<<"/"<<f<<"\",\"result\":\""<<result<<"\",\"cursor\":"<<s.cursor<<",\"output\":\""<<hex(s.bytes,8)<<"\",\"sink\":\""<<hex(s.sink.data(),s.sink.size())<<"\",\"events\":["<<s.events<<"]}\n";}return 0;}
