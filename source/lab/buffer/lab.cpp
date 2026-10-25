#include "StarBuffer.hpp"
#ifdef LAB_REFERENCE
#include "StarBuffer.reference.hpp"
#endif
#include "StarLogging.hpp"
#include <iostream>
#include <sstream>
using namespace Star;
#ifdef LAB_REFERENCE
using B=BufferReference; using E=ExternalBufferReference;
#else
using B=Buffer; using E=ExternalBuffer;
#endif
std::string hex(char const* p,size_t n){std::string s;for(size_t i=0;i<n;++i){s+="0123456789abcdef"[(unsigned char)p[i]>>4];s+="0123456789abcdef"[(unsigned char)p[i]&15];}return s;}
std::string hx(std::string s){return hex(s.data(),s.size());}
void row(std::string k,std::string v){std::cout<<"{\"key\":\""<<k<<"\",\"value\":\""<<v<<"\"}\n";}
template<class T> std::string state(T& b){return std::to_string(b.pos())+":"+std::to_string(b.size())+":"+std::to_string((int)b.mode())+":"+hex(b.ptr(),b.dataSize());}
template<class F> std::string result(F f){try{return std::to_string(f());}catch(EofException const& e){return "Eof:"+hx(e.what());}catch(IOException const& e){return "IO:"+hx(e.what());}catch(FormatException const& e){return "Format:"+hx(e.what());}}
struct Sink:LogSink{std::string text; void log(char const* p,LogLevel)override{if(text.size()+strlen(p)>512)throw IOException("log bound");text+=p;}};
struct Spy:B {std::string events;std::exception_ptr pending;int fail=0; bool reenter=false;void resize(StreamOffset n)override{events+="resize/"+std::to_string((int)mode())+";";if(reenter){reenter=false;open(IOMode::Read);}B::resize(n);if(fail==1){if(pending)std::rethrow_exception(pending);throw IOException("spy-resize");}}void seek(StreamOffset n,IOSeek m=IOSeek::Absolute)override{events+="seek/"+std::to_string((int)mode())+";";if(fail==2)throw IOException("spy-seek");B::seek(n,m);}};
int main(){
 B def;row("default",state(def));B sized(4);row("size-ctor",state(sized));
 for(int mode=0;mode<16;++mode)for(int n:{0,1,4,8}){
  std::string k="matrix/"+std::to_string(mode)+"/"+std::to_string(n)+"/";
  B b(ByteArray(256,'Q'));b.resize(n);b.seek(1);b.open((IOMode)mode);char out[16];memset(out,'Z',16);
  row(k+"open",state(b));row(k+"predicates",std::to_string(b.atEnd())+":"+std::to_string(b.empty()));row(k+"read-zero",result([&]{return b.read(nullptr,0);}));row(k+"write-zero",result([&]{return b.write(nullptr,0);}));
  row(k+"read",result([&]{return b.read(out,3);})+":"+hex(out,3)+":"+state(b));
  row(k+"write",result([&]{return b.write("abc",3);})+":"+state(b));
  row(k+"absolute",result([&]{return b.readAbsolute(-1,out,2);})+":"+std::to_string(b.pos()));
  row(k+"absolute-zero",result([&]{return b.writeAbsolute(-1,nullptr,0);})+":"+std::to_string(b.pos()));
 }
 B b(ByteArray(256,'Q'));b.resize(4);b.seek(3);b.resize(8);row("growth",state(b));b.seek(2,IOSeek::End);row("end",state(b));b.seek(-1,IOSeek::Relative);row("relative",state(b));b.seek(77,(IOSeek)255);row("unknown-seek",state(b));
 b.open(IOMode::Read);B copy(b);row("copy",state(copy)+":"+std::to_string(copy.ptr()!=b.ptr()));copy.data()[0]='X';row("copy-deep",hex(b.ptr(),4)+":"+hex(copy.ptr(),4));B moved(std::move(copy));row("move",state(moved)+":"+state(copy));
 B assigned;row("copy-assignment-id",std::to_string(&(assigned=b)==&assigned));row("copy-assignment",state(assigned));B moveAssigned;row("move-assignment-id",std::to_string(&(moveAssigned=std::move(assigned))==&moveAssigned));row("move-assignment",state(moveAssigned)+":"+state(assigned));
 b=b;row("self-copy",state(b));b=std::move(b);row("self-move",state(b));
 B cl(ByteArray("abcd",4));cl.seek(3);cl.open(IOMode::Read);auto clone=cl.clone();auto typed=dynamic_cast<B*>(clone.get());row("clone",std::to_string(typed!=nullptr)+":"+std::to_string(clone.get()!=&cl)+":"+std::to_string(clone->pos())+":"+std::to_string((int)clone->mode())+":"+std::to_string(typed&&typed->ptr()!=cl.ptr()));if(typed)typed->data()[0]='X';row("clone-deep",hex(cl.ptr(),4));
 Spy sub;sub.reset(ByteArray("abc",3));sub.seek(2);auto subclone=sub.clone();row("clone-base",std::to_string(dynamic_cast<Spy*>(subclone.get())==nullptr)+":"+std::to_string(subclone->pos()));
 B take(ByteArray("abcd",4));take.seek(3);auto taken=take.takeData();row("take",hex(taken.ptr(),taken.size())+":"+state(take));take.reset(3);row("reset-size",state(take));take.reset(ByteArray("xy",2));row("reset-bytes",state(take));take.clear();row("clear",state(take)+":"+std::to_string(take.empty()));
 B reserve(ByteArray(256,'Q'));reserve.resize(4);reserve.seek(3);auto p=reserve.ptr();reserve.reserve(200);B const& c=reserve;row("reserve",state(reserve)+":"+std::to_string(p==reserve.ptr())+":"+std::to_string(c.ptr()==reserve.ptr())+":"+std::to_string(&c.data()==&reserve.data())+":"+std::to_string(reserve.data().capacity()>=200));
 std::ostringstream owner;owner<<(void*)&reserve;row("device-name",std::to_string(reserve.deviceName().utf8()=="Buffer <"+owner.str()+">"));
 E empty;row("external-default",std::to_string(empty.pos())+":"+std::to_string(empty.size())+":"+std::to_string((int)empty.mode())+":"+std::to_string(empty.ptr()==nullptr)+":"+std::to_string(empty.empty())+":"+std::to_string(bool(empty)));row("external-null-zero",result([&]{return empty.read(nullptr,0);}));
 char bytes[]="abcdefgh";E ext(bytes,8);ext.seek(3);E ec(ext);ec.seek(1);E ea;ea=ext;bytes[0]='Z';row("external-copy",state(ext)+":"+state(ec)+":"+state(ea)+":"+std::to_string(ec.ptr()==bytes)+":"+std::to_string(!bool(ext)));std::ostringstream eo;eo<<(void*)&ext;row("external-name",std::to_string(ext.deviceName().utf8()=="ExternalBuffer <"+eo.str()+">"));
 for(int mode=0;mode<4;++mode){ext=E(bytes,8);ext.reset(bytes,8);if(mode==0)ext.close();else if(mode!=1){/* native base rejects changed mode; read-only/closed cover source path */}char o[4]={'Q','Q','Q','Q'};std::string k="external/"+std::to_string(mode)+"/";row(k+"read",result([&]{return ext.read(o,3);})+":"+hex(o,4)+":"+state(ext));row(k+"absolute",result([&]{return ext.readAbsolute(7,o,3);})+":"+state(ext));row(k+"write-zero",result([&]{return ext.write(nullptr,0);}));row(k+"write-absolute-zero",result([&]{return ext.writeAbsolute(-1,nullptr,0);}));ext.seek(2,IOSeek::End);row(k+"end",std::to_string(ext.pos()));ext.seek(-1,IOSeek::Relative);ext.seek(6,(IOSeek)255);row(k+"unknown",std::to_string(ext.pos()));row(k+"at-end",std::to_string(ext.atEnd()));}
 auto sink=make_shared<Sink>();Logger::addSink(sink);Logger::removeStdoutSink();row("external-clone",result([&]{auto x=ext.clone();return x->pos();}));row("external-clone-log",hx(sink->text));sink->setLevel(LogLevel::Warn);auto extclone=ext.clone();auto et=dynamic_cast<E*>(extclone.get());row("external-clone-quiet",std::to_string(et!=nullptr)+":"+std::to_string(extclone.get()!=&ext)+":"+std::to_string(extclone->pos())+":"+std::to_string(et&&et->ptr()==bytes));bytes[1]='Y';row("external-clone-shared",hex(et->ptr(),8));Logger::removeSink(sink);
 ext.reset(bytes,0);row("external-reset",state(ext)+":"+std::to_string(ext.empty())+":"+std::to_string(bool(ext))+":"+std::to_string(ext.ptr()==bytes));
 for(int f=0;f<3;++f){Spy s;s.reset(ByteArray("abcd",4));s.events.clear();s.fail=f;auto r=result([&]{s.open(IOMode::Write|IOMode::Truncate|IOMode::Append);return 0;});row("spy/"+std::to_string(f),r+":"+s.events+":"+state(s));}
 Spy re;re.reset(ByteArray("abcd",4));re.events.clear();re.reenter=true;re.open(IOMode::Write|IOMode::Truncate|IOMode::Append);row("spy/reentry",re.events+":"+state(re));
 Spy identity;identity.reset(ByteArray("abc",3));identity.fail=1;identity.pending=std::make_exception_ptr(IOException("sentinel"));void const* expected=nullptr;try{std::rethrow_exception(identity.pending);}catch(IOException const& e){expected=&e;}bool same=false;try{identity.open(IOMode::Write|IOMode::Truncate);}catch(IOException const& e){same=&e==expected;}row("spy/identity",std::to_string(same)+":"+state(identity));
 E extEnd(bytes,8);extEnd.seek(8);char unchanged='Q';row("external-eof",result([&]{return extEnd.read(&unchanged,1);})+":"+std::to_string(extEnd.atEnd())+":"+hex(&unchanged,1));row("external-negative",result([&]{return extEnd.readAbsolute(-1,&unchanged,1);})+":"+std::to_string(extEnd.pos()));
 B abs(ByteArray(256,'Q'));abs.resize(4);abs.seek(2);char absOut[4]={'Z','Z','Z','Z'};row("absolute-partial",result([&]{return abs.readAbsolute(3,absOut,4);})+":"+hex(absOut,4)+":"+state(abs));row("absolute-gap",result([&]{return abs.writeAbsolute(7,"xy",2);})+":"+state(abs));
 B eof(ByteArray("abc",3));eof.seek(2);char full[4]={'Q','Q','Q','Q'};row("read-full",result([&]{eof.readFull(full,4);return 0;})+":"+hex(full,4)+":"+state(eof));
 return 0;
}
