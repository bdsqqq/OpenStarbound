// SOURCE-ONLY DRAFT: compile/link/execution belong to the parent staged pipeline.
#include "StarIODevice.hpp"
#include "StarFormat.hpp"
#ifdef LAB_REFERENCE
#include "StarIODevice.reference.hpp"
#endif
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <limits>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <vector>
using namespace Star;
#ifdef LAB_REFERENCE
namespace D = Star::IODeviceReference;
#else
namespace D = Star;
#endif
using B = D::IODevice;
using S = StreamOffset;
std::string q(std::string const& s) { std::string r="\""; for(char c:s){if(c=='"'||c=='\\')r+='\\'; if((unsigned char)c<32)throw std::runtime_error("non-ascii protocol");r+=c;}return r+'"'; }
std::string hx(char const* p,size_t n){std::string r;for(size_t i=0;i<n;++i){auto c=(unsigned char)p[i];r+="0123456789abcdef"[c>>4];r+="0123456789abcdef"[c&15];}return r;}
std::string array(std::vector<std::string> const& v,bool quoted){std::string r="[";for(auto const&s:v){if(r.size()>1)r+=',';r+=quoted?q(s):s;}return r+"]";}
struct Opt {
 std::string action,dispatch="base",faultOp,phase,tag="IO";int mode=3,faultIndex=0;size_t length=5,chunk=2;bool eof=false,null=false,reentry=false;
 explicit Opt(std::string a):action(a){}
 std::string json() const {std::ostringstream s;s<<"{\"action\":"<<q(action)<<",\"mode\":"<<mode<<",\"length\":"<<length<<",\"chunk\":"<<chunk<<",\"eof\":"<<(eof?"true":"false")<<",\"null\":"<<(null?"true":"false")<<",\"dispatch\":"<<q(dispatch)<<",\"faultOp\":"<<q(faultOp)<<",\"faultIndex\":"<<faultIndex<<",\"phase\":"<<q(phase)<<",\"tag\":"<<q(tag)<<",\"reentry\":"<<(reentry?"true":"false")<<'}';return s.str();}
};
int derivedCloseCalls=0;
struct TraceSpy:B {
 Opt o; S cursor=6;char output[8]={'Q','Q','Q','Q','Q','Q','Q','Q'};char input[8]={'a','b','c','d','e','f','g','h'};
 std::string sink;std::vector<std::string> writes,events;std::vector<std::pair<std::string,int>> counts;int io=0;uintptr_t tempBase=0,byteInput=0;
 std::exception_ptr marker;
 explicit TraceSpy(Opt const& x):B((D::IOMode)x.mode),o(x){init();}
 TraceSpy(TraceSpy const& x):B(x),o(x.o){init();}
 void init(){if(o.tag=="IO")marker=std::make_exception_ptr(IOException("trace-marker",false));else if(o.tag=="EOF")marker=std::make_exception_ptr(D::EofException("trace-marker",false));else marker=std::make_exception_ptr(std::runtime_error("trace-marker"));}
 void assign(TraceSpy const& x){B::operator=(x);}void set(int m){B::setMode((D::IOMode)m);}
 std::string snapshot() const {return "\"mode\":"+std::to_string((unsigned char)mode())+",\"cursor\":"+std::to_string(cursor)+",\"output\":"+q(hx(output,8))+",\"sink\":"+q(hx(sink.data(),sink.size()))+",\"writes\":"+array(writes,true);}
 int next(std::string const& op){for(auto& c:counts)if(c.first==op)return ++c.second;counts.emplace_back(op,1);return 1;}
 bool fail(std::string const& op,int i,std::string const& phase)const{return o.faultOp==op&&o.faultIndex==i&&o.phase==phase;}
 // Pointer identity is checked while live. Only initialized callback-written chunks
 // are read from native ByteArray temporaries; their untouched tails stay opaque.
 std::pair<std::string,int> pointer(char const* p,bool reading){
  if(!p)return {"null",0};auto a=(uintptr_t)p;
  uintptr_t base=reading?(uintptr_t)output:(byteInput?byteInput:(uintptr_t)input);
  if(a>=base&&a-base<=8)return {reading?"caller":"input",int(a-base)};
  if(!tempBase)tempBase=a;
  if(a<tempBase||a-tempBase>8)throw std::runtime_error("temporary pointer bound");
  return {"temp",int(a-tempBase)};
 }
 S cb(std::string op,char* dst=nullptr,char const* src=nullptr,size_t len=0,S arg=0,int seekmode=0){
  int index=next(op);bool isio=op=="read"||op=="write"||op=="absoluteRead"||op=="absoluteWrite"||op=="fullRead"||op=="fullWrite"||op=="fullReadAbs"||op=="fullWriteAbs";
  bool reading=op=="read"||op=="absoluteRead"||op=="fullRead"||op=="fullReadAbs";
  auto ptr=isio?pointer(reading?dst:src,reading):std::make_pair(std::string("none"),-1);
  auto ev=[&](std::string phase,size_t n=0,S value=0){std::ostringstream s;s<<"{\"op\":"<<q(op)<<",\"index\":"<<index<<",\"phase\":"<<q(phase)<<",\"kind\":"<<q(ptr.first)<<",\"ptr\":"<<ptr.second<<",\"len\":"<<len<<",\"n\":"<<n<<",\"arg\":"<<arg<<",\"seekmode\":"<<seekmode<<",\"value\":"<<value<<','<<snapshot()<<'}';events.push_back(s.str());};
  ev("before");if(fail(op,index,"before")){ev("throw");std::rethrow_exception(marker);}
  size_t n=0;S value=0;
  if(op=="seek")cursor=seekmode==2?8+arg:arg;
  else if(op=="pos")value=cursor;
  else if(op=="end")value=o.eof;
  else if(op=="size")value=8;
  else if(op=="name"){if(o.reentry)set(4);}
  else if(isio){++io;n=std::min(len,o.chunk);if(n){if(ptr.second<0||ptr.second>8||n>size_t(8-ptr.second))throw std::runtime_error("fixture byte bound");if(reading){for(size_t j=0;j<n;++j)dst[j]=char(64+io);writes.push_back(ptr.first+"/"+std::to_string(ptr.second)+"/"+hx(dst,n));}else sink.append(src,n);}cursor+=n;value=n;}
  ev("mutated",n,value);if(fail(op,index,"after")){ev("throw",n,value);std::rethrow_exception(marker);}ev("return",n,value);return value;
 }
 size_t read(char* p,size_t n)override{return cb("read",p,nullptr,n);}size_t write(char const* p,size_t n)override{return cb("write",nullptr,p,n);}
 S pos()override{return cb("pos");}void seek(S p,D::IOSeek m=D::IOSeek::Absolute)override{cb("seek",nullptr,nullptr,0,p,int(m));}
 D::IODevicePtr clone()override{return {};}
 void close()override{++derivedCloseCalls;B::close();}
 bool atEnd()override{return cb("end");}
 S size()override{return o.dispatch=="size"?cb("size"):B::size();}
 String deviceName()const override{const_cast<TraceSpy*>(this)->cb("name");return "TRACE-NAME";}
 size_t readAbsolute(S p,char* b,size_t n)override{return o.dispatch=="absolute"?cb("absoluteRead",b,nullptr,n,p):B::readAbsolute(p,b,n);}
 size_t writeAbsolute(S p,char const* b,size_t n)override{return o.dispatch=="absolute"?cb("absoluteWrite",nullptr,b,n,p):B::writeAbsolute(p,b,n);}
 void readFull(char* b,size_t n)override{if(o.dispatch=="full")cb("fullRead",b,nullptr,n);else B::readFull(b,n);}
 void writeFull(char const* b,size_t n)override{if(o.dispatch=="full")cb("fullWrite",nullptr,b,n);else B::writeFull(b,n);}
 void readFullAbsolute(S p,char* b,size_t n)override{if(o.dispatch=="full")cb("fullReadAbs",b,nullptr,n,p);else B::readFullAbsolute(p,b,n);}
 void writeFullAbsolute(S p,char const* b,size_t n)override{if(o.dispatch=="full")cb("fullWriteAbs",nullptr,b,n,p);else B::writeFullAbsolute(p,b,n);}
};
std::vector<Opt> corpus(){std::vector<Opt> v;auto add=[&](Opt o){v.push_back(o);};
 for(int m=0;m<256;++m)for(auto a:{"construct","copy","assign","self","set","close","open"}){Opt o(a);o.mode=m;add(o);}
 for(auto a:{"construct","destruct","resize","readfull","writefull","open","close","sync","name","atEnd","size","readabs","writeabs","readfullabs","writefullabs","readbytes","writebytes","readbytesabs","writebytesabs","set","copy","assign"})add(Opt(a));
 for(auto a:{"readfull","writefull","readfullabs","writefullabs","readbytes","writebytes","readbytesabs","writebytesabs"})for(size_t n:{0,4})for(size_t k:{0,2,4})for(bool e:{false,true}){Opt o(a);o.length=n;o.chunk=k;o.eof=e;add(o);}
 for(auto a:{"readfull","writefull","readfullabs","writefullabs","readabs","writeabs"}){Opt o(a);o.length=0;o.null=true;add(o);o=Opt(a);o.length=std::numeric_limits<size_t>::max();o.chunk=0;add(o);}
 for(auto a:{"readfullabs","writefullabs","readbytesabs","writebytesabs"}){Opt o(a);o.dispatch="absolute";add(o);}
 for(auto a:{"readbytes","writebytes","readbytesabs","writebytesabs"})for(size_t n:{0,4}){Opt o(a);o.length=n;o.chunk=4;o.dispatch="full";add(o);}
 {Opt o("atEnd");o.dispatch="size";add(o);}
 {Opt o("open");o.dispatch="unequal";add(o);o.reentry=true;add(o);}
 for(auto a:{"size","atEnd","readfull","writefull","readabs","writeabs","readfullabs","writefullabs","readbytes","readbytesabs","writebytes","writebytesabs","open"})
 for(auto op:{"pos","seek","read","write","end","name","absoluteRead","absoluteWrite","fullRead","fullWrite","fullReadAbs","fullWriteAbs","size"})
 for(int i:{1,2,3,4,5,6})for(auto phase:{"before","after"})for(auto tag:{"IO","EOF","OTHER"}){Opt o(a);if(o.action=="open")o.dispatch="unequal";else if(std::string(op).find("absolute")==0&&o.action!="readabs"&&o.action!="writeabs")o.dispatch="absolute";else if(std::string(op).find("full")==0&&o.action.find("bytes")!=std::string::npos){o.dispatch="full";o.chunk=5;}else if(std::string(op)=="size"&&o.action=="atEnd")o.dispatch="size";o.faultOp=op;o.faultIndex=i;o.phase=phase;o.tag=tag;add(o);}
 return v;
}
void run(Opt const&o,size_t index){
 std::unique_ptr<TraceSpy> s(new TraceSpy(o));std::string value="null",outcome="OK",savedSnapshot;std::vector<std::string> savedEvents;
 try{
  auto a=o.action;char* out=o.null?nullptr:s->output;char const* in=o.null?nullptr:s->input;
  if(a=="copy"){TraceSpy c(*s);if(c.mode()!=s->mode())throw std::runtime_error("copy mode");}
  else if(a=="assign"){TraceSpy c(Opt("construct"));c.assign(*s);if(c.mode()!=s->mode())throw std::runtime_error("assign mode");}
  else if(a=="self")s->assign(*s);
  else if(a=="set"){s->set(0);s->set(o.mode);}
  else if(a=="close")s->B::close();else if(a=="sync")s->B::sync();
  else if(a=="destruct"){derivedCloseCalls=0;savedSnapshot=s->snapshot();savedEvents=s->events;s.reset();value=std::to_string(derivedCloseCalls);}
  else if(a=="resize")s->B::resize(-1);
  else if(a=="name"){auto actual=s->B::deviceName();auto own=strf("IODevice <{}>",(void*)static_cast<B*>(s.get()));if(actual!=own)throw std::runtime_error("native self address mismatch");value=q("IODevice <SELF>");}
  else if(a=="open")s->B::open((D::IOMode)(o.dispatch=="unequal"?(o.mode^1):o.mode));
  else if(a=="size")value=std::to_string(s->B::size());
  else if(a=="atEnd")value=std::to_string(int(s->B::atEnd()));
  else if(a=="readabs")value=std::to_string(s->B::readAbsolute(-4,out,o.length));
  else if(a=="writeabs")value=std::to_string(s->B::writeAbsolute(-4,in,o.length));
  else if(a=="readfull")s->B::readFull(out,o.length);else if(a=="writefull")s->B::writeFull(in,o.length);
  else if(a=="readfullabs")s->B::readFullAbsolute(-4,out,o.length);else if(a=="writefullabs")s->B::writeFullAbsolute(-4,in,o.length);
  else if(a=="readbytes"){auto b=s->B::readBytes(o.length);value=q(hx(b.ptr(),b.size()));}
  else if(a=="readbytesabs"){auto b=s->B::readBytesAbsolute(-4,o.length);value=q(hx(b.ptr(),b.size()));}
  else if(a=="writebytes"||a=="writebytesabs"){ByteArray b;if(o.length)b.append(s->input,o.length);s->byteInput=(uintptr_t)b.ptr();if(a=="writebytes")s->B::writeBytes(b);else s->B::writeBytesAbsolute(-4,b);}
 }catch(D::EofException const&){outcome=std::current_exception()==s->marker?"EOF/same":"EOF/new";}
 catch(IOException const&e){bool same=std::current_exception()==s->marker;std::string msg=e.what();bool wrapped=msg.find("Cannot call size() on IODevice")!=std::string::npos&&msg.find("trace-marker")!=std::string::npos;outcome=same?"IO/same":wrapped?"IO/wrapped":"IO/new";
  if(o.action=="open"&&!same){std::string literal="Cannot reopen device 'TRACE-NAME";if(msg.find(literal)==std::string::npos||msg.find(literal+"'")!=std::string::npos)throw std::runtime_error("native open format");}}
 catch(std::exception const&){if(std::current_exception()!=s->marker)throw;outcome="OTHER/same";}
 std::ostringstream id;id<<'t';id.width(5);id.fill('0');id<<index;
 std::cout<<"{\"case\":"<<q(id.str())<<",\"options\":"<<o.json()<<",\"outcome\":"<<q(outcome)<<",\"value\":"<<value<<','<<(s?s->snapshot():savedSnapshot)<<",\"events\":"<<array(s?s->events:savedEvents,false)<<"}\n";
}
int main(int argc,char**){if(argc!=1){std::cerr<<"no arguments accepted; source-only full corpus fixture\n";return 2;}auto v=corpus();for(size_t i=0;i<v.size();++i)run(v[i],i);}
