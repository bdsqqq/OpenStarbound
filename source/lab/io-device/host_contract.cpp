#include "host_contract.hpp"
#include "StarIODevice.hpp"
#include "StarFormat.hpp"
#include <exception>
#include <stdexcept>
#include <limits>

namespace Star::IODeviceLab {
struct Stop { uint32_t status; };
struct Controller {
 void* ctx; SbIODeviceHost host;
 uint64_t call(uint32_t op,uint64_t a=0,uint64_t b=0,uint64_t c=0) {
  uint64_t out=0; auto s=host(ctx,op,a,b,c,&out);
  if(s) throw Stop{s<=2?s:2}; return out;
 }
 uint64_t arg(uint64_t n){return call(SB_IO_ARG,n);}
 [[noreturn]] void error(uint64_t n){call(SB_IO_ERROR,n);throw Stop{2};}
};
}
extern "C" uint32_t sb_io_device_run(uint32_t mode,void* ctx,SbIODeviceHost host) {
 using namespace Star::IODeviceLab;
 if(!host||mode>SB_IO_ASSIGN)return 2;
 try {
  Controller c{ctx,host};
  auto store=[&](uint64_t m){if(m>255)throw Stop{2};c.call(SB_IO_STORE_MODE,m);};
  switch(mode) {
   case SB_IO_CTOR:case SB_IO_SET_MODE:store(c.arg(0));break;
   case SB_IO_COPY_CTOR:case SB_IO_ASSIGN:store(c.call(SB_IO_SOURCE_MODE));break;
   case SB_IO_DTOR:c.call(SB_IO_BASE_CLOSE);break;
   case SB_IO_RESIZE:c.error(0);
   case SB_IO_READ_FULL:case SB_IO_WRITE_FULL:{
    auto n=c.arg(1);auto r=c.call(mode==SB_IO_READ_FULL?SB_IO_READ:SB_IO_WRITE,0,n);
    if(r<n){auto end=c.call(SB_IO_END);c.error(mode==SB_IO_READ_FULL?(end?1:2):(end?3:4));}break;
   }
   case SB_IO_OPEN:{auto m=c.arg(0);if(m>255)throw Stop{2};if(m!=c.call(SB_IO_MODE)){c.call(SB_IO_NAME);c.error(5);}break;}
   case SB_IO_CLOSE:store(0);break;
   case SB_IO_SYNC:break;
   case SB_IO_DEVICE_NAME:c.call(SB_IO_NAME_BASE);break;
   case SB_IO_AT_END:{auto p=c.call(SB_IO_POS);auto s=c.call(SB_IO_VIRTUAL_SIZE);c.call(SB_IO_RETURN,(int64_t)p>=(int64_t)s);break;}
   case SB_IO_SIZE:{
    try {auto p=c.call(SB_IO_POS);c.call(SB_IO_SEEK,0,2);auto n=c.call(SB_IO_POS);c.call(SB_IO_SEEK,p,0);c.call(SB_IO_RETURN,n);}
    catch(Stop const& s){if(s.status==1&&c.call(SB_IO_EXCEPTION_KIND)==1)c.call(SB_IO_WRAP_SIZE);throw;}break;
   }
   case SB_IO_READ_ABSOLUTE:case SB_IO_WRITE_ABSOLUTE:{
    auto p=c.call(SB_IO_POS);auto offset=c.arg(0),n=c.arg(1);c.call(SB_IO_SEEK,offset,0);
    auto r=c.call(mode==SB_IO_READ_ABSOLUTE?SB_IO_READ:SB_IO_WRITE,0,n);
    c.call(SB_IO_SEEK,p,0);c.call(SB_IO_RETURN,r);break;
   }
   case SB_IO_READ_FULL_ABSOLUTE:case SB_IO_WRITE_FULL_ABSOLUTE:{
    auto offset=c.arg(0),left=c.arg(1);uint64_t index=0;
    while(left){auto r=c.call(mode==SB_IO_READ_FULL_ABSOLUTE?SB_IO_READ_ABS:SB_IO_WRITE_ABS,offset,index,left);
     if(!r)c.error(mode==SB_IO_READ_FULL_ABSOLUTE?6:7);
     if(r>left||index>UINT64_MAX-r)throw Stop{2};
     offset+=r;index+=r;left-=r;
    }break;
   }
   case SB_IO_READ_BYTES:case SB_IO_READ_BYTES_ABSOLUTE:{
    auto n=c.arg(mode==SB_IO_READ_BYTES?0:1);if(n){c.call(SB_IO_ARRAY_ALLOC,n);
     if(mode==SB_IO_READ_BYTES)c.call(SB_IO_READFULL,0,n);
     else c.call(SB_IO_READFULLABS,c.arg(0),0,n);
    }break;
   }
   case SB_IO_WRITE_BYTES:case SB_IO_WRITE_BYTES_ABSOLUTE:{
    auto n=c.call(SB_IO_CAPTURE_INPUT_BYTES);
    if(mode==SB_IO_WRITE_BYTES)c.call(SB_IO_WRITEFULL,0,n);
    else c.call(SB_IO_WRITEFULLABS,c.arg(0),0,n);break;
   }
   default:return 2;
  }
  c.call(SB_IO_FINISH);return 0;
 }catch(Stop const& s){return s.status;}catch(...){return 3;}
}

namespace Star::IODeviceLab {
static_assert(sizeof(size_t)==8&&sizeof(StreamOffset)==8,"native 64-bit profile");
struct NativeCtx {
 IODevice* owner=nullptr; IODevice const* constOwner=nullptr; IODevice const* source=nullptr;
 atomic<IOMode>* modeField=nullptr; bool modeReady=true,busy=false,finished=false;
 std::exception_ptr pending; uint32_t exceptionKind=0;
 uint64_t args[2]={0,0},result=0;
 char* output=nullptr;char const* input=nullptr;
 ByteArray const* param=nullptr; uintptr_t paramObject=0,paramData=0;size_t paramSize=0;bool paramCaptured=false;
 ByteArray value;String name;
};
inline void bindParam(NativeCtx& c,ByteArray const& p){
 c.param=&p;c.paramObject=(uintptr_t)&p;c.input=p.ptr();c.paramData=(uintptr_t)c.input;c.paramSize=p.size();
}
inline bool overlapsRange(uint64_t* out,uintptr_t b,size_t n){
 if(!b||!n)return false;auto a=(uintptr_t)out;
 if(n>UINTPTR_MAX-b)return true;return a<b+n&&b<a+sizeof(uint64_t);
}
inline bool overlaps(uint64_t* out,void const* p,size_t n){return overlapsRange(out,(uintptr_t)p,n);}
inline bool safeOutput(NativeCtx& c,uint64_t* out){
 auto a=(uintptr_t)out;if(!out||a%alignof(uint64_t)||a>UINTPTR_MAX-sizeof(uint64_t))return false;
 if(overlaps(out,&c,sizeof c)||overlaps(out,c.constOwner,sizeof(IODevice))||overlaps(out,c.owner,sizeof(IODevice))||overlaps(out,c.source,sizeof(IODevice))||overlaps(out,c.modeField,sizeof(atomic<IOMode>))||overlapsRange(out,c.paramObject,sizeof(ByteArray)))return false;
 // A virtual full-I/O override may destroy the input object. Only numeric
 // exclusions survive capture; no parameter dereference follows that callback.
 if(c.paramObject&&overlapsRange(out,c.paramData,c.paramSize))return false;
 if(overlaps(out,c.value.ptr(),c.value.size())||overlaps(out,c.name.utf8().data(),c.name.utf8().size()))return false;
 return true;
}
inline char const* indexed(char const* p,uint64_t index){
 if(!index)return p;
 if(!p||index>UINTPTR_MAX-(uintptr_t)p)throw Stop{2};return p+index;
}
inline uint32_t nativeHost(void* opaque,uint32_t op,uint64_t a,uint64_t b,uint64_t d,uint64_t* out) noexcept {
 if(!opaque)return 2;auto& c=*static_cast<NativeCtx*>(opaque);
 if(c.busy||c.finished||!safeOutput(c,out))return 2;
 if(c.pending&&op!=SB_IO_EXCEPTION_KIND&&op!=SB_IO_WRAP_SIZE)return 2;
 c.busy=true;struct Unlock{bool& b;~Unlock(){b=false;}} unlock{c.busy};
 try {
  auto need=[](bool yes){if(!yes)throw Stop{2};};uint64_t r=0;
  auto none=[&](){need(!a&&!b&&!d);};
  auto io=[&](bool reading,uint64_t index,uint64_t count,uint64_t offset,uint32_t kind) -> uint64_t {
   need(c.owner);auto p=indexed(reading?c.output:c.input,index);
   if(kind==0)return reading?c.owner->read(const_cast<char*>(p),count):c.owner->write(p,count);
   if(kind==1)return reading?c.owner->readAbsolute((StreamOffset)offset,const_cast<char*>(p),count):c.owner->writeAbsolute((StreamOffset)offset,p,count);
   if(kind==2){if(reading)c.owner->readFull(const_cast<char*>(p),count);else c.owner->writeFull(p,count);}
   else {if(reading)c.owner->readFullAbsolute((StreamOffset)offset,const_cast<char*>(p),count);else c.owner->writeFullAbsolute((StreamOffset)offset,p,count);}
   return uint64_t(0);
  };
  switch(op){
   case SB_IO_ARG:need(a<2&&!b&&!d);r=c.args[a];break;
   case SB_IO_MODE:none();need(c.modeReady&&c.modeField);r=(uint8_t)c.modeField->load();break;
   case SB_IO_STORE_MODE:need(a<=255&&!b&&!d&&c.modeField);c.modeField->store((IOMode)a);c.modeReady=true;break;
   case SB_IO_SOURCE_MODE:none();need(c.source);r=(uint8_t)c.source->mode();break;
   case SB_IO_READ:case SB_IO_WRITE:need(!d);r=io(op==SB_IO_READ,a,b,0,0);break;
   case SB_IO_READ_ABS:case SB_IO_WRITE_ABS:r=io(op==SB_IO_READ_ABS,b,d,a,1);break;
   case SB_IO_READFULL:case SB_IO_WRITEFULL:need(!d);r=io(op==SB_IO_READFULL,a,b,0,2);break;
   case SB_IO_READFULLABS:case SB_IO_WRITEFULLABS:r=io(op==SB_IO_READFULLABS,b,d,a,3);break;
   case SB_IO_POS:none();need(c.owner);r=c.owner->pos();break;
   case SB_IO_SEEK:need(!d&&b<=255&&c.owner);c.owner->seek((StreamOffset)a,(IOSeek)b);break;
   case SB_IO_END:none();need(c.owner);r=c.owner->atEnd();break;
   case SB_IO_VIRTUAL_SIZE:none();need(c.owner);r=c.owner->size();break;
   case SB_IO_NAME:none();need(c.constOwner);c.name=c.constOwner->deviceName();break;
   case SB_IO_BASE_CLOSE:none();need(c.owner);c.owner->IODevice::close();break;
   case SB_IO_NAME_BASE:none();need(c.constOwner);c.name=strf("IODevice <{}>",(void*)c.constOwner);break;
   case SB_IO_ARRAY_ALLOC:need(!b&&!d);c.value.resize(a);c.output=c.value.ptr();break;
   case SB_IO_CAPTURE_INPUT_BYTES:none();need(c.param&&!c.paramCaptured);
    c.paramCaptured=true;c.param=nullptr;r=c.paramSize;break;
   case SB_IO_RETURN:need(!b&&!d);c.result=a;break;
   case SB_IO_FINISH:none();c.finished=true;break;
   case SB_IO_EXCEPTION_KIND:none();need(bool(c.pending));r=c.exceptionKind;break;
   case SB_IO_WRAP_SIZE:{none();need(c.pending&&c.exceptionKind==1);
    try{std::rethrow_exception(c.pending);}catch(IOException const& e){c.pending=std::make_exception_ptr(IOException("Cannot call size() on IODevice",e));}
    return 1;
   }
   case SB_IO_ERROR:need(!b&&!d);
    switch(a){
     case 0:throw IOException("resize not supported");
     case 1:throw EofException("Failed to read full buffer in readFull, eof reached.");
     case 2:throw IOException("Failed to read full buffer in readFull");
     case 3:throw EofException("Failed to write full buffer in writeFull, eof reached.");
     case 4:throw IOException("Failed to write full buffer in writeFull");
     case 5:throw IOException::format("Cannot reopen device '{}",c.name);
     case 6:throw IOException("Failed to read full buffer in readFullAbsolute");
     case 7:throw IOException("Failed to write full buffer in writeFullAbsolute");
     default:throw Stop{2};
    }
   default:throw Stop{2};
  }
  *out=r;return 0;
 }catch(Stop const& s){return s.status;}catch(IOException const&){c.pending=std::current_exception();c.exceptionKind=1;return 1;}catch(...){c.pending=std::current_exception();c.exceptionKind=2;return 1;}
}
inline void execute(uint32_t mode,NativeCtx& c){
 auto s=sb_io_device_run(mode,&c,nativeHost);
 if(c.pending)std::rethrow_exception(c.pending);
 if(s||!c.finished)throw std::runtime_error("IODevice host protocol failure");
}
}

namespace Star {
// Member scope binds the real private atomic; constructors expose its address
// without loading the uninitialized value. Every reentrant call gets a new ctx.
#define IO_CTX() IODeviceLab::NativeCtx c; c.owner=this;c.constOwner=this;c.modeField=&m_mode
#define IO_RUN(n) IODeviceLab::execute(n,c)
IODevice::IODevice(IOMode m){IO_CTX();c.modeReady=false;c.args[0]=(uint8_t)m;IO_RUN(SB_IO_CTOR);}
IODevice::~IODevice(){IO_CTX();IO_RUN(SB_IO_DTOR);}
void IODevice::resize(StreamOffset n){IO_CTX();c.args[0]=n;IO_RUN(SB_IO_RESIZE);}
void IODevice::readFull(char* p,size_t n){IO_CTX();c.output=p;c.args[1]=n;IO_RUN(SB_IO_READ_FULL);}
void IODevice::writeFull(char const* p,size_t n){IO_CTX();c.input=p;c.args[1]=n;IO_RUN(SB_IO_WRITE_FULL);}
void IODevice::open(IOMode m){IO_CTX();c.args[0]=(uint8_t)m;IO_RUN(SB_IO_OPEN);}
void IODevice::close(){IO_CTX();IO_RUN(SB_IO_CLOSE);}
void IODevice::sync(){IO_CTX();IO_RUN(SB_IO_SYNC);}
String IODevice::deviceName()const{IODeviceLab::NativeCtx c;c.constOwner=this;IO_RUN(SB_IO_DEVICE_NAME);return c.name;}
bool IODevice::atEnd(){IO_CTX();IO_RUN(SB_IO_AT_END);return c.result;}
StreamOffset IODevice::size(){IO_CTX();IO_RUN(SB_IO_SIZE);return (StreamOffset)c.result;}
size_t IODevice::readAbsolute(StreamOffset p,char* b,size_t n){IO_CTX();c.args[0]=p;c.args[1]=n;c.output=b;IO_RUN(SB_IO_READ_ABSOLUTE);return c.result;}
size_t IODevice::writeAbsolute(StreamOffset p,char const* b,size_t n){IO_CTX();c.args[0]=p;c.args[1]=n;c.input=b;IO_RUN(SB_IO_WRITE_ABSOLUTE);return c.result;}
void IODevice::readFullAbsolute(StreamOffset p,char* b,size_t n){IO_CTX();c.args[0]=p;c.args[1]=n;c.output=b;IO_RUN(SB_IO_READ_FULL_ABSOLUTE);}
void IODevice::writeFullAbsolute(StreamOffset p,char const* b,size_t n){IO_CTX();c.args[0]=p;c.args[1]=n;c.input=b;IO_RUN(SB_IO_WRITE_FULL_ABSOLUTE);}
ByteArray IODevice::readBytes(size_t n){IO_CTX();c.args[0]=n;IO_RUN(SB_IO_READ_BYTES);return std::move(c.value);}
void IODevice::writeBytes(ByteArray const& p){IO_CTX();IODeviceLab::bindParam(c,p);IO_RUN(SB_IO_WRITE_BYTES);}
ByteArray IODevice::readBytesAbsolute(StreamOffset p,size_t n){IO_CTX();c.args[0]=p;c.args[1]=n;IO_RUN(SB_IO_READ_BYTES_ABSOLUTE);return std::move(c.value);}
void IODevice::writeBytesAbsolute(StreamOffset p,ByteArray const& b){IO_CTX();c.args[0]=p;IODeviceLab::bindParam(c,b);IO_RUN(SB_IO_WRITE_BYTES_ABSOLUTE);}
void IODevice::setMode(IOMode m){IO_CTX();c.args[0]=(uint8_t)m;IO_RUN(SB_IO_SET_MODE);}
IODevice::IODevice(IODevice const& rhs){IO_CTX();c.modeReady=false;c.source=&rhs;IO_RUN(SB_IO_COPY_CTOR);}
IODevice& IODevice::operator=(IODevice const& rhs){IO_CTX();c.source=&rhs;IO_RUN(SB_IO_ASSIGN);return *this;}
#undef IO_RUN
#undef IO_CTX
}
