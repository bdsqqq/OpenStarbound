#undef NDEBUG
#include "StarIODevice.hpp"
#ifdef LAB_REFERENCE
#include "StarIODevice.reference.hpp"
#endif
#include <cassert>
#include <iostream>
#include <sstream>
using namespace Star;
#ifdef LAB_REFERENCE
namespace D = Star::IODeviceReference;
#else
namespace D = Star;
#endif
using B=D::IODevice;
std::string hx(char const* p,size_t n){std::string s;for(size_t i=0;i<n;++i){s+="0123456789abcdef"[(unsigned char)p[i]>>4];s+="0123456789abcdef"[(unsigned char)p[i]&15];}return s;}
void row(std::string k,std::string v){std::cout<<"{\"key\":\""<<k<<"\",\"value\":\""<<v<<"\"}\n";}
struct Spy:B {
 StreamOffset cursor=3;size_t chunk=2;bool eof=false;int fault=0,step=0;bool after=false,other=false;std::string events;char store[256];std::exception_ptr pending;void const* expected=nullptr;std::string* closes=nullptr;
 Spy(D::IOMode mode=D::IOMode::Read):B(mode){memset(store,'Q',256);pending=std::make_exception_ptr(IOException("sentinel",false));try{std::rethrow_exception(pending);}catch(IOException const&e){expected=&e;}}
 Spy(Spy const& s):B(s){memset(store,'Q',256);}
 void assign(Spy const& s){B::operator=(s);}void modeSet(int m){setMode((D::IOMode)m);}
 void enter(std::string e){events+=e+";";++step;if(step==fault&&!after)fail();}void leave(){if(step==fault&&after)fail();}
 void fail(){if(other)throw std::runtime_error("other");std::rethrow_exception(pending);}
 size_t read(char* p,size_t n)override{enter("read/"+std::to_string(n));size_t r=std::min(n,chunk);assert(r<=256);memset(p,'R',r);cursor+=r;leave();return r;}
 size_t write(char const*,size_t n)override{enter("write/"+std::to_string(n));size_t r=std::min(n,chunk);cursor+=r;leave();return r;}
 StreamOffset pos()override{enter("pos");leave();return cursor;}
 void seek(StreamOffset n,D::IOSeek m=D::IOSeek::Absolute)override{enter("seek/"+std::to_string(n)+"/"+std::to_string((int)m));cursor=m==D::IOSeek::End?9:n;leave();}
 bool atEnd()override{enter("end");leave();return eof;}
 String deviceName()const override{const_cast<Spy*>(this)->enter("name");const_cast<Spy*>(this)->leave();return "spy";}
 D::IODevicePtr clone()override{return {};}
 void close()override{if(closes)*closes+="derived;";B::close();}
};
template<class F>std::string result(Spy&s,F f){try{return f();}catch(D::EofException const&){return "EOF";}catch(IOException const&e){return std::string("IO/")+(&e==s.expected?"same":"new")+"/"+(std::string(e.what()).find("sentinel")!=std::string::npos?"cause":"plain");}catch(std::runtime_error const&){return "OTHER";}}
int main(){
 for(int m=0;m<256;++m){Spy s((D::IOMode)m);Spy c(s),a;a.assign(s);a.assign(a);row("mode/"+std::to_string(m),std::to_string((int)s.mode())+":"+std::to_string((int)c.mode())+":"+std::to_string((int)a.mode()));s.modeSet(255-m);s.B::close();row("close/"+std::to_string(m),std::to_string((int)s.mode()));}
 for(std::string op:{"read","write","readabs","writeabs","fullabsread","fullabswrite","size","end","bytes","bytesabs","writebytes","writebytesabs","resize","sync","open-equal","open-different"})for(int len:{0,4})for(int chunk:{0,2,4})for(int eof:{0,1}){
  Spy s;s.chunk=chunk;s.eof=eof;char out[8];memset(out,'Q',8);ByteArray bytes(4,'W');if(!len)bytes.resize(0);assert(bytes.ptr());
  auto v=result(s,[&]()->std::string{
   if(op=="read")s.B::readFull(out,len);else if(op=="write")s.B::writeFull(out,len);
   else if(op=="readabs")return std::to_string(s.B::readAbsolute(-2,out,len));else if(op=="writeabs")return std::to_string(s.B::writeAbsolute(-2,out,len));
   else if(op=="fullabsread")s.B::readFullAbsolute(-2,out,len);else if(op=="fullabswrite")s.B::writeFullAbsolute(-2,out,len);
   else if(op=="size")return std::to_string(s.B::size());else if(op=="end")return std::to_string(s.B::atEnd());
   else if(op=="bytes"){auto b=s.readBytes(len);return hx(b.ptr(),b.size());}else if(op=="bytesabs"){auto b=s.readBytesAbsolute(-2,len);return hx(b.ptr(),b.size());}
   else if(op=="writebytes")s.writeBytes(bytes);else if(op=="writebytesabs")s.writeBytesAbsolute(-2,bytes);
   else if(op=="resize")s.B::resize(len);else if(op=="sync")s.B::sync();else s.B::open(op=="open-equal"?D::IOMode::Read:D::IOMode::Write);return "OK";
  });row(op+"/"+std::to_string(len)+"/"+std::to_string(chunk)+"/"+std::to_string(eof),v+":"+std::to_string(s.cursor)+":"+hx(out,8)+":"+s.events);
 }
 for(std::string op:{"size","readabs","writeabs","read","write","fullabsread","fullabswrite","open-different"})for(int fault=1;fault<=9;++fault)for(int after:{0,1})for(int other:{0,1}){Spy s;s.fault=fault;s.after=after;s.other=other;char out[8];memset(out,'Q',8);auto v=result(s,[&]{if(op=="size")return std::to_string(s.B::size());if(op=="readabs")return std::to_string(s.B::readAbsolute(-2,out,4));if(op=="writeabs")return std::to_string(s.B::writeAbsolute(-2,out,4));if(op=="read")s.B::readFull(out,4);else if(op=="write")s.B::writeFull(out,4);else if(op=="fullabsread")s.B::readFullAbsolute(-2,out,4);else if(op=="fullabswrite")s.B::writeFullAbsolute(-2,out,4);else s.B::open(D::IOMode::Write);return std::string("OK");});row("fault/"+op+"/"+std::to_string(fault)+"/"+std::to_string(after)+"/"+std::to_string(other),v+":"+std::to_string(s.cursor)+":"+hx(out,8)+":"+s.events);}

 struct FullSpy:Spy {std::string calls;void readFull(char*p,size_t n)override{calls+="RF/"+std::to_string(n)+";";Spy::readFull(p,n);}void writeFull(char const*p,size_t n)override{calls+="WF/"+std::to_string(n)+";";Spy::writeFull(p,n);}void readFullAbsolute(StreamOffset o,char*p,size_t n)override{calls+="RA/"+std::to_string(n)+";";Spy::readFullAbsolute(o,p,n);}void writeFullAbsolute(StreamOffset o,char const*p,size_t n)override{calls+="WA/"+std::to_string(n)+";";Spy::writeFullAbsolute(o,p,n);}};
 for(int n:{0,4}){FullSpy s;s.chunk=4;ByteArray empty(4,'W');empty.resize(n);auto a=s.readBytes(n);auto b=s.readBytesAbsolute(-2,n);s.writeBytes(empty);s.writeBytesAbsolute(-2,empty);row("virtual-bytes/"+std::to_string(n),s.calls+":"+hx(a.ptr(),a.size())+":"+hx(b.ptr(),b.size()));}
 struct Reentry:Spy {bool entered=false;StreamOffset pos()override{if(!entered){entered=true;events+="reenter;";modeSet(255);sync();}return Spy::pos();}};Reentry re;auto revalue=re.B::size();row("reentry",std::to_string(revalue)+":"+std::to_string((int)re.mode())+":"+re.events);
 Spy named;std::ostringstream addr;addr<<(void*)static_cast<B*>(&named);row("owner-name",std::to_string(named.B::deviceName().utf8()=="IODevice <"+addr.str()+">"));
 std::string closes;{Spy d;d.closes=&closes;}row("destructor",closes);
 Spy huge;huge.chunk=0;char out[8];row("huge-zero",result(huge,[&]{huge.B::readFull(out,SIZE_MAX);return std::string("OK");})+":"+huge.events);
}
