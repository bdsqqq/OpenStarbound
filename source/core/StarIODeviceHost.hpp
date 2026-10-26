#ifndef STAR_IO_DEVICE_HOST_HPP
#define STAR_IO_DEVICE_HOST_HPP
#include "StarRustIODevice.h"
#include "StarIODevice.hpp"
#include "StarFormat.hpp"
#include <exception>
#include <limits>
#include <stdexcept>
namespace Star::IODeviceRust { struct Stop { uint32_t status; }; }
namespace Star::IODeviceRust {
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
 if(c.pending&&op!=STAR_IO_EXCEPTION_KIND&&op!=STAR_IO_WRAP_SIZE)return 2;
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
   case STAR_IO_ARG:need(a<2&&!b&&!d);r=c.args[a];break;
   case STAR_IO_MODE:none();need(c.modeReady&&c.modeField);r=(uint8_t)c.modeField->load();break;
   case STAR_IO_STORE_MODE:need(a<=255&&!b&&!d&&c.modeField);c.modeField->store((IOMode)a);c.modeReady=true;break;
   case STAR_IO_SOURCE_MODE:none();need(c.source);r=(uint8_t)c.source->mode();break;
   case STAR_IO_READ:case STAR_IO_WRITE:need(!d);r=io(op==STAR_IO_READ,a,b,0,0);break;
   case STAR_IO_READ_ABS:case STAR_IO_WRITE_ABS:r=io(op==STAR_IO_READ_ABS,b,d,a,1);break;
   case STAR_IO_READFULL:case STAR_IO_WRITEFULL:need(!d);r=io(op==STAR_IO_READFULL,a,b,0,2);break;
   case STAR_IO_READFULLABS:case STAR_IO_WRITEFULLABS:r=io(op==STAR_IO_READFULLABS,b,d,a,3);break;
   case STAR_IO_POS:none();need(c.owner);r=c.owner->pos();break;
   case STAR_IO_SEEK:need(!d&&b<=255&&c.owner);c.owner->seek((StreamOffset)a,(IOSeek)b);break;
   case STAR_IO_END:none();need(c.owner);r=c.owner->atEnd();break;
   case STAR_IO_VIRTUAL_SIZE:none();need(c.owner);r=c.owner->size();break;
   case STAR_IO_NAME:none();need(c.constOwner);c.name=c.constOwner->deviceName();break;
   case STAR_IO_BASE_CLOSE:none();need(c.owner);c.owner->IODevice::close();break;
   case STAR_IO_NAME_BASE:none();need(c.constOwner);c.name=strf("IODevice <{}>",(void*)c.constOwner);break;
   case STAR_IO_ARRAY_ALLOC:need(!b&&!d);c.value.resize(a);c.output=c.value.ptr();break;
   case STAR_IO_CAPTURE_INPUT_BYTES:none();need(c.param&&!c.paramCaptured);
    c.paramCaptured=true;c.param=nullptr;r=c.paramSize;break;
   case STAR_IO_RETURN:need(!b&&!d);c.result=a;break;
   case STAR_IO_FINISH:none();c.finished=true;break;
   case STAR_IO_EXCEPTION_KIND:none();need(bool(c.pending));r=c.exceptionKind;break;
   case STAR_IO_WRAP_SIZE:{none();need(c.pending&&c.exceptionKind==1);
    try{std::rethrow_exception(c.pending);}catch(IOException const& e){c.pending=std::make_exception_ptr(IOException("Cannot call size() on IODevice",e));}
    return 1;
   }
   case STAR_IO_ERROR:need(!b&&!d);
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
 auto s=star_io_device_run(mode,&c,nativeHost);
 if(c.pending)std::rethrow_exception(c.pending);
 if(s||!c.finished)throw std::runtime_error("IODevice host protocol failure");
}
}

#endif
