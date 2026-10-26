#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include "host_contract.cpp"
#include <iostream>
#include <vector>
using namespace Star;
using namespace Star::IODeviceLab;
static int closes=0;
struct Spy:IODevice {
 using IODevice::IODevice;
 StreamOffset cursor=3;size_t calls=0,chunk=0;bool end=false,reenter=false;int fault=0,phase=0;
 std::exception_ptr marker=std::make_exception_ptr(IOException("marker",false));
 std::vector<int> events;
 void check(int p){events.push_back(p);if(fault==p&&(!phase||std::count(events.begin(),events.end(),p)==phase))std::rethrow_exception(marker);}
 size_t read(char* p,size_t n)override{++calls;check(3);auto r=std::min(n,chunk);for(size_t i=0;i<r;++i)p[i]='A';cursor+=r;return r;}
 size_t write(char const*,size_t n)override{++calls;check(4);auto r=std::min(n,chunk);cursor+=r;return r;}
 StreamOffset pos()override{check(1);return cursor;}
 void seek(StreamOffset p,IOSeek m=Absolute)override{check(m==End?2:5);cursor=m==End?8:p;}
 bool atEnd()override{check(6);return end;}
 IODevicePtr clone()override{return {};}
 String deviceName()const override{auto& self=*const_cast<Spy*>(this);if(self.reenter)self.set(4);return "REENTER";}
 void close()override{++closes;IODevice::close();}
 void set(unsigned m){setMode((IOMode)m);}
 Spy(Spy const& rhs):IODevice(rhs){}
 void assign(Spy const& rhs){IODevice::operator=(rhs);}
};
uint32_t custom(void*,uint32_t op,uint64_t,uint64_t,uint64_t,uint64_t* out){*out=0;return op==SB_IO_ERROR?0:0;}
uint32_t foreign(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*){throw 7;}
int main(){
 uint64_t out=99;NativeCtx c;
 assert(sb_io_device_run(22,nullptr,custom)==2);
 assert(sb_io_device_run(SB_IO_SYNC,nullptr,custom)==0);
 assert(sb_io_device_run(SB_IO_RESIZE,nullptr,custom)==2);
 assert(sb_io_device_run(SB_IO_SYNC,nullptr,foreign)==3);
 assert(sb_io_device_run(0,nullptr,nullptr)==2);
 assert(nativeHost(nullptr,SB_IO_FINISH,0,0,0,&out)==2);
 assert(nativeHost(&c,SB_IO_ARG,0,0,1,&out)==2);
 assert(nativeHost(&c,999,0,0,0,&out)==2);
 assert(nativeHost(&c,SB_IO_ARG,0,0,0,nullptr)==2);
 alignas(8) char bad[16];assert(nativeHost(&c,SB_IO_ARG,0,0,0,reinterpret_cast<uint64_t*>(bad+1))==2);
 assert(nativeHost(&c,SB_IO_ARG,0,0,0,&c.result)==2);
 assert(nativeHost(&c,SB_IO_ARG,0,0,0,reinterpret_cast<uint64_t*>(UINTPTR_MAX-3))==2);
 c.busy=true;assert(nativeHost(&c,SB_IO_FINISH,0,0,0,&out)==2);c.busy=false;
 c.args[0]=256;assert(sb_io_device_run(SB_IO_CTOR,&c,nativeHost)==2);
 assert(nativeHost(&c,SB_IO_STORE_MODE,256,0,0,&out)==2);
 assert(nativeHost(&c,SB_IO_SEEK,0,256,0,&out)==2);
 assert(nativeHost(&c,SB_IO_ERROR,0,0,0,&out)==1);auto marker=c.pending;
 assert(nativeHost(&c,SB_IO_FINISH,0,0,0,&out)==2);
 assert(nativeHost(&c,SB_IO_EXCEPTION_KIND,0,0,0,&out)==0&&out==1&&c.pending==marker);
 assert(nativeHost(&c,SB_IO_WRAP_SIZE,0,0,0,&out)==1&&c.pending!=marker);
 c.pending=std::make_exception_ptr(std::runtime_error("other"));c.exceptionKind=2;
 assert(nativeHost(&c,SB_IO_WRAP_SIZE,0,0,0,&out)==2);
 c.pending={};c.exceptionKind=0;assert(nativeHost(&c,SB_IO_FINISH,0,0,0,&out)==0);
 assert(nativeHost(&c,SB_IO_ARG,0,0,0,&out)==2);
 for(unsigned m=0;m<256;++m){Spy s((IOMode)m);assert((uint8_t)s.mode()==m);Spy copy(s);assert((uint8_t)copy.mode()==m);s.set(m^255);copy.assign(s);assert(copy.mode()==s.mode());}
 Spy s;assert(s.mode()==IOMode::Closed);char data[8]={};s.chunk=2;
 s.readFull(nullptr,0);assert(s.calls==1);
 auto before=s.calls;s.readFullAbsolute(0,nullptr,0);assert(s.calls==before);
 s.readFullAbsolute(0,data,4);assert(s.calls==before+2&&data[0]=='A'&&data[3]=='A'&&s.cursor==3);
 s.chunk=0;for(auto p:{data,(char*)nullptr}){try{s.readFull(p,SIZE_MAX);assert(false);}catch(IOException const&){} }
 s.end=true;try{s.readFull(data,1);assert(false);}catch(EofException const&){}
 before=s.calls;auto bytes=s.readBytes(0);assert(bytes.size()==0&&s.calls==before);
 ByteArray empty;s.writeBytes(empty);assert(s.calls==before+1);
 s.fault=3;try{s.readAbsolute(9,data,1);assert(false);}catch(...){assert(std::current_exception()==s.marker);}assert(s.cursor==9);
 s.fault=5;s.phase=2;s.events.clear();s.chunk=1;data[0]='Q';
 try{s.readAbsolute(9,data,1);assert(false);}catch(...){assert(std::current_exception()==s.marker);}
 assert(data[0]=='A'&&s.cursor==10);s.phase=0;
 for(int p:{1,2,5}){s.fault=p;try{s.IODevice::size();assert(false);}catch(IOException const&){assert(std::current_exception()!=s.marker);}}
 s.marker=std::make_exception_ptr(std::runtime_error("other"));s.fault=1;
 try{s.IODevice::size();assert(false);}catch(std::runtime_error const&){assert(std::current_exception()==s.marker);}
 s.fault=0;s.chunk=4;auto filled=s.readBytes(4);assert(filled.size()==4&&filled[0]=='A'&&filled[3]=='A');
 s.reenter=true;try{s.open(IOMode::ReadWrite);assert(false);}catch(IOException const&){}assert((uint8_t)s.mode()==4);
 NativeCtx alias;alias.owner=&s;alias.constOwner=&s;
 assert(nativeHost(&alias,SB_IO_RETURN,0,0,0,reinterpret_cast<uint64_t*>(&s))==2);
 ByteArray param(8,'Q');bindParam(alias,param);
 assert(nativeHost(&alias,SB_IO_ARG,0,0,0,reinterpret_cast<uint64_t*>(param.ptr()))==2);
 assert(param==ByteArray(8,'Q'));
 assert(nativeHost(&alias,SB_IO_RETURN,0,0,0,reinterpret_cast<uint64_t*>(&param))==2);
 alias.value.resize(8);assert(nativeHost(&alias,SB_IO_RETURN,0,0,0,reinterpret_cast<uint64_t*>(alias.value.ptr()))==2);
 s.reenter=false;s.fault=0;auto name=s.IODevice::deviceName();assert(name==strf("IODevice <{}>",(void*)&s));
 // Native writeBytes samples its arguments before dispatch and never rereads
 // them. Destruction inside a full override is therefore a defined input case.
 struct Drop:Spy {std::unique_ptr<ByteArray>* held=nullptr;char const* expected=nullptr;
  void writeFull(char const* p,size_t n)override{assert(p==expected&&n==4);held->reset();}
  void writeFullAbsolute(StreamOffset o,char const* p,size_t n)override{assert(o==-4);writeFull(p,n);}
 } drop;
 for(bool absolute:{false,true}){auto held=std::make_unique<ByteArray>(4,'X');drop.held=&held;drop.expected=held->ptr();
  if(absolute)drop.IODevice::writeBytesAbsolute(-4,*held);else drop.IODevice::writeBytes(*held);assert(!held);
 }
 NativeCtx captured;auto held=std::make_unique<ByteArray>(4,'X');bindParam(captured,*held);
 assert(nativeHost(&captured,SB_IO_CAPTURE_INPUT_BYTES,0,0,0,&out)==0&&out==4&&!captured.param);
 held.reset();assert(nativeHost(&captured,SB_IO_FINISH,0,0,0,&out)==0);
 int old=closes;{Spy local;}assert(closes==old);
 std::cout<<"IODEVICE_HOST_PROTOCOL_SCRATCH_PASS\n";
}
