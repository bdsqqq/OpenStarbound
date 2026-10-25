#include "StarDataStream.hpp"
#include "StarDataStreamDevices.hpp"
#include "StarBuffer.hpp"
#ifdef LAB_REFERENCE
#include "StarDataStream.reference.hpp"
using Base = Star::DataStreamReference;
static_assert(!std::is_base_of<Star::DataStream, Base>::value,"reference must be a distinct class");
#else
using Base = Star::DataStream;
#endif
#include <iostream>
#include <sstream>
#include <cstring>
#include <functional>
#include <stdexcept>
#include <limits>
using namespace Star;
std::string hex(void const* p,size_t n){static char const h[]="0123456789abcdef";std::string s;auto b=(unsigned char const*)p;for(size_t i=0;i<n;++i){s+=h[b[i]>>4];s+=h[b[i]&15];}return s;}
std::string hx(std::string const&s){return hex(s.data(),s.size());}
struct Fault:std::runtime_error{Fault():std::runtime_error("scripted native i/o fault") {}};
struct Stream:Base {
 std::string input,output,trace;size_t pos=0,calls=0;int fail=-1;size_t partial=0;bool flip=false;void const* caller=nullptr;std::exception_ptr injected=std::make_exception_ptr(Fault());std::function<void(bool,char*,size_t)> hook;Fault fault;void const* caught=nullptr;
 void readData(char* p,size_t n) override {
  size_t call=calls++;size_t got=std::min(n,input.size()-pos);if((int)call==fail)got=std::min(got,partial);
  size_t old=pos;if(got)std::memcpy(p,input.data()+pos,got);pos+=got;
  if(flip)setByteOrder(ByteOrder::LittleEndian);
  if(hook)hook(true,p,n);
  trace+="R:"+std::to_string(n)+":"+std::to_string(old)+":"+std::to_string(pos)+":"+hex(p,got)+":"+(!p?"null":caller&&p==caller?"caller":"other")+":"+std::to_string((int)byteOrder())+":"+std::to_string(nullTerminatedStrings())+";";
  if((int)call==fail || got<n)std::rethrow_exception(injected);
 }
 void writeData(char const*p,size_t n) override {
  size_t call=calls++;size_t got=(int)call==fail?std::min(n,partial):n;size_t old=output.size();if(got)output.append(p,got);
  trace+="W:"+std::to_string(n)+":"+std::to_string(old)+":"+std::to_string(output.size())+":"+hex(p,got)+":"+(!p?"null":caller&&p==caller?"caller":"other")+":"+std::to_string((int)byteOrder())+":"+std::to_string(nullTerminatedStrings())+";";
  if(hook)hook(false,const_cast<char*>(p),n);
  if((int)call==fail)std::rethrow_exception(injected);
 }
};
void record(std::string const&key,Stream const&s,std::string const&value="",bool identity=true,std::string const&error=""){
 std::cout<<key<<"|bytes="<<hx(s.output)<<"|value="<<value<<"|pos="<<s.pos<<"|trace="<<hx(s.trace)<<"|identity="<<identity<<"|error="<<hx(error)<<"|order="<<(int)s.byteOrder()<<"|null="<<s.nullTerminatedStrings()<<"|version="<<s.streamCompatibilityVersion()<<"\n";
}
template<class F>std::string attempt(Stream&s,F f){try{f();return "";}catch(Fault const&e){return std::string("Fault:")+e.what()+":same="+std::to_string(std::current_exception()==s.injected);}catch(DataStreamException const&e){return std::string("DataStreamException:")+e.what();}}
template<class T>void primitive(std::string name,uint64_t bits){
 T value{};std::memcpy(&value,&bits,sizeof(T));
 for(int order:{0,1,2,-1,3,2147483647}){
  auto key=name+"/"+std::to_string(bits)+"/"+std::to_string(order);
  Stream w;w.setByteOrder((ByteOrder)order);bool id=&(w<<value)==&w;record("write/"+key,w,"",id);
  Stream r;r.setByteOrder((ByteOrder)order);r.input=w.output;T out{};r.caller=&out;id=&(r>>out)==&r;record("read/"+key,r,hex(&out,sizeof out),id);
  Stream f;f.setByteOrder((ByteOrder)order);f.input.clear();for(size_t j=0;j<sizeof(T);++j)f.input+=char(0x12+j);f.flip=true;out={};f.caller=&out;id=&(f>>out)==&f;record("fresh/"+key,f,hex(&out,sizeof out),id);
  if(sizeof(T)>1){Stream e;e.input=std::string(sizeof(T),'\x12');e.fail=0;e.partial=1;out=value;e.caller=&out;auto err=attempt(e,[&]{e>>out;});record("partial/"+key,e,hex(&out,sizeof out),true,err);}
 }
}
int main(){
 {Stream s;record("default",s);for(unsigned v:{0u,20u,21u,~0u}){s.setStreamCompatibilityVersion(v);record("version/"+std::to_string(v),s);s.setStreamCompatibilityVersion(NetCompatibilityRules(VersionNumber(v)));record("rules/"+std::to_string(v),s);}}
 for(bool v:{false,true}){Stream s;bool id=&(s<<v)==&s;s.input=s.output;bool out=!v;id=id&&&(s>>out)==&s;record("bool/"+std::to_string(v),s,std::to_string(out),id);}
 {Stream s;s.input="\xff";bool b=false;s>>b;record("bool/nonzero",s,std::to_string(b));Stream e;e.input="x";e.fail=0;e.partial=1;b=false;record("bool/fault",e,"pending");auto err=attempt(e,[&]{e>>b;});record("bool/fault-result",e,std::to_string(b),true,err);}
 primitive<char>("char",0xa5);primitive<int8_t>("i8",0xa5);primitive<uint8_t>("u8",0xa5);primitive<int16_t>("i16",0xa153);primitive<uint16_t>("u16",0xa153);primitive<int32_t>("i32",0xa1537294);primitive<uint32_t>("u32",0xa1537294);primitive<int64_t>("i64",0xa1537294b6c8d0efULL);primitive<uint64_t>("u64",0xa1537294b6c8d0efULL);
 for(uint64_t b:{0ULL,0x80000000ULL,0x7f800000ULL,0xff800000ULL,0x7fc12345ULL})primitive<float>("f32",b);
 for(uint64_t b:{0ULL,0x8000000000000000ULL,0x7ff0000000000000ULL,0xfff0000000000000ULL,0x7ff8123456789abcULL})primitive<double>("f64",b);
 for(size_t n:{0,1,4}){Stream s;s.input="abcd";auto b=s.readBytes(n);record("bytes/read/"+std::to_string(n),s,hex(b.ptr(),b.size()));Stream w;w.writeBytes(b);record("bytes/write/"+std::to_string(n),w);}
 for(uint64_t v:{0ULL,1ULL,127ULL,128ULL,16383ULL,16384ULL,0xffffffffffffffffULL}){
  Stream s;auto n=s.writeVlqU(v);record("vlqu/write/"+std::to_string(v),s,std::to_string(n));s.input=s.output;uint64_t out=42;n=s.readVlqU(out);record("vlqu/ref/"+std::to_string(v),s,std::to_string(out)+":"+std::to_string(n));s.pos=0;out=s.readVlqU();record("vlqu/value/"+std::to_string(v),s,std::to_string(out));
 }
 // Full signed range admitted after the parent's scoped C++17 shift probe.
 for(int64_t v:{std::numeric_limits<int64_t>::min(),std::numeric_limits<int64_t>::max(),int64_t(4611686018427387904LL),int64_t(-4611686018427387904LL),int64_t(-65),int64_t(-1),int64_t(0),int64_t(1),int64_t(64),int64_t(4611686018427387903LL)}){Stream s;auto n=s.writeVlqI(v);record("vlqi/write/"+std::to_string(v),s,std::to_string(n));s.input=s.output;int64_t out=42;n=s.readVlqI(out);record("vlqi/ref/"+std::to_string(v),s,std::to_string(out)+":"+std::to_string(n));s.pos=0;out=s.readVlqI();record("vlqi/value/"+std::to_string(v),s,std::to_string(out));}
 for(size_t v:{size_t(0),size_t(127),size_t(128),NPos,NPos-1}){Stream s;auto n=s.writeVlqS(v);record("vlqs/write/"+std::to_string(v),s,std::to_string(n));s.input=s.output;size_t out=42;n=s.readVlqS(out);record("vlqs/ref/"+std::to_string(v),s,std::to_string(out)+":"+std::to_string(n));s.pos=0;out=s.readVlqS();record("vlqs/value/"+std::to_string(v),s,std::to_string(out));}
 for(std::string input:{std::string(),std::string("\x81",1),std::string(10,'\x81')})for(int kind=0;kind<3;++kind){Stream s;s.input=input;uint64_t u=42;int64_t i=42;size_t z=42;auto err=attempt(s,[&]{if(kind==0)s.readVlqU(u);if(kind==1)s.readVlqI(i);if(kind==2)s.readVlqS(z);});record("vlq/error/"+hx(input)+"/"+std::to_string(kind),s,std::to_string(u)+":"+std::to_string(i)+":"+std::to_string(z),true,err);}
 for(bool term:{false,true})for(unsigned ver:{0u,20u,21u,~0u})for(std::string data:{std::string(),std::string("a\0\xffz",4)})for(int kind=0;kind<4;++kind){Stream s;s.setNullTerminatedStrings(term);s.setStreamCompatibilityVersion(ver);bool id=false;ByteArray ba(data.data(),data.size());String str(data);if(kind==0)id=&(s<<data.c_str())==&s;if(kind==1)id=&(s<<data)==&s;if(kind==2)id=&(s<<ba)==&s;if(kind==3)id=&(s<<str)==&s;auto key=std::to_string(term)+"/"+std::to_string(ver)+"/"+hx(data)+"/"+std::to_string(kind);record("strings/write/"+key,s,"",id);
  if(kind>0){Stream r;r.input=s.output;r.setNullTerminatedStrings(term);std::string out="old";ByteArray b("old",3);String t("old");if(kind==1)id=&(r>>out)==&r;if(kind==2)id=&(r>>b)==&r;if(kind==3)id=&(r>>t)==&r;record("strings/read/"+key,r,kind==1?hx(out):kind==2?hex(b.ptr(),b.size()):hex(t.utf8Ptr(),t.utf8Size()),id);}}
 for(bool term:{false,true})for(int kind=0;kind<3;++kind)for(int failure:{0,1,2}){Stream s;s.setNullTerminatedStrings(term);s.input=term&&kind!=1?std::string("abc\0",4):std::string("\x03" "abc",4);s.fail=failure;s.partial=1;std::string out="old";ByteArray b(16,'Q');String t("old");s.hook=[&](bool read,char*,size_t){if(read){if(kind==2)t=String("callback");s.setNullTerminatedStrings(!term);}};auto err=attempt(s,[&]{if(kind==0)s>>out;if(kind==1)s>>b;if(kind==2)s>>t;});record("strings/fault/"+std::to_string(term)+"/"+std::to_string(kind)+"/"+std::to_string(failure),s,kind==0?hx(out):kind==1?hex(b.ptr(),b.size()):hex(t.utf8Ptr(),t.utf8Size()),true,err);}
 {Stream s;ByteArray b("a",1);s.hook=[&](bool r,char*,size_t){if(!r&&s.calls==1)b=ByteArray("expanded",8);};s<<b;record("array/late-payload",s);}
 {Stream s;std::string v="abc";s.hook=[&](bool r,char*,size_t){if(!r&&s.calls==1)v[1]='Z';};s<<v;record("string/captured-inplace",s);}
 {Stream s;s.setNullTerminatedStrings(true);s.input=std::string("abc\0",4);s.hook=[&](bool,char*,size_t){s.setNullTerminatedStrings(false);};std::string out;s>>out;record("strings/branch-snapshot",s,hx(out));}
 for(auto bytes:{std::string("\x81\xff\xff\xff\xff\xff\xff\xff\xff\x7f",10),std::string("\x81\xff\xff\xff\xff\xff\xff\xff\xff\x7e",10)}){Stream s;s.input=bytes;int64_t v=0;auto n=s.readVlqI(v);record("vlqi/extreme/"+hx(bytes),s,std::to_string(v)+":"+std::to_string(n));s.pos=0;v=s.readVlqI();record("vlqi/extreme-value/"+hx(bytes),s,std::to_string(v));}
 {size_t reads=0,writes=0;DataStreamFunctions s([&](char*p,size_t n){++reads;if(n)p[0]='Q';return size_t(0);},[&](char const*,size_t){++writes;return size_t(0);});char c='x';s>>c;s<<c;Stream output;record("devices/functions-ignore-count",output,std::to_string(reads)+":"+std::to_string(writes)+":"+hex(&c,1));}
 {auto b=std::make_shared<Buffer>(ByteArray("x",1));char out[3]={'Q','Q','Q'};std::string error;try{b->readFull(out,3);}catch(IOException const&e){error=e.what();}Stream s;record("devices/readFull-once",s,hex(out,3)+":"+std::to_string(b->pos()),true,error);}
 // Isolated failure probes: callbacks must not mask assignment timing.
 for(bool term:{false,true})for(int kind=0;kind<3;++kind){Stream s;s.setNullTerminatedStrings(term);s.input=term&&kind!=1?std::string("abc\0",4):std::string("\x03" "abc",4);s.fail=0;s.partial=1;std::string out="old";ByteArray b(16,'Q');String t("old");auto err=attempt(s,[&]{if(kind==0)s>>out;if(kind==1)s>>b;if(kind==2)s>>t;});record("isolated/fault/"+std::to_string(term)+"/"+std::to_string(kind),s,kind==0?hx(out):kind==1?hex(b.ptr(),b.size()):hex(t.utf8Ptr(),t.utf8Size()),true,err);}
 {Stream s;s.hook=[&](bool,char*,size_t){s.setByteOrder(ByteOrder::LittleEndian);};uint32_t value=0x12345678;s<<value;record("isolated/write-before-hook",s);}
 for(bool term:{false,true})for(int failure:{0,1}){Stream s;s.setNullTerminatedStrings(term);s.fail=failure;s.partial=1;std::string value="abc";auto err=attempt(s,[&]{s<<value;});record("isolated/write-fault/"+std::to_string(term)+"/"+std::to_string(failure),s,"",true,err);}
 return 0;
}
