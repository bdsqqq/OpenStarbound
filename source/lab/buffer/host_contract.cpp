#include "host_contract.hpp"
#include "StarBuffer.hpp"
#include "StarFormat.hpp"
#include "StarLogging.hpp"
#include <exception>
#include <limits>
#include <stdexcept>
#include <cstring>

namespace {
using namespace Star;
struct Stop { uint32_t status; };
struct Controller {
  void* ctx; SbBufferHost host;
  uint64_t call(uint32_t op,uint64_t a=0,uint64_t b=0) {
    uint64_t out=0; auto s=host(ctx,op,a,b,&out);
    if(s) throw Stop{s<=2?s:2};
    return out;
  }
  uint64_t arg(uint64_t n){return call(SB_OP_ARG,n);}
  void ret(uint64_t n=0){call(SB_OP_RESULT,n);}
  [[noreturn]] void raise(uint64_t error){call(SB_OP_ERROR,error);throw Stop{2};}
};
}
extern "C" uint32_t sb_buffer_run(uint32_t mode,void* ctx,SbBufferHost host) {
  if(!host || mode>SB_E_PRIVATE_READ)return 2;
  try {
    Controller c{ctx,host};
    auto get=[&](uint32_t op){return c.call(op);};
    auto set=[&](uint32_t op,uint64_t a){c.call(op,a);};
    auto child=[&](uint64_t a,uint64_t b=0){return c.call(SB_OP_CHILD,a,b);};
    auto storage=[&](uint64_t a,uint64_t b=0){c.call(SB_OP_STORAGE,a,b);};
    switch(mode) {
      case SB_B_CTOR:set(SB_OP_SET_POS,0);set(SB_OP_SET_MODE,3);break;
      case SB_B_CTOR_SIZE:child(0,c.arg(0));break;
      case SB_B_CTOR_BYTES:child(1);break;
      case SB_B_CTOR_COPY:child(2);break;
      case SB_B_CTOR_MOVE:child(3);break;
      case SB_B_POS:case SB_E_POS:c.ret(get(SB_OP_POS));break;
      case SB_B_SEEK:case SB_E_SEEK: {
        // Snapshot before branch, matching native signed conversion point.
        auto old=get(SB_OP_POS), p=c.arg(0), m=c.arg(1);if(m>255)throw Stop{2};
        uint64_t n=old;
        if(m==0)n=p;
        else if(m==1){auto a=(int64_t)old,b=(int64_t)p;
          if((b>0&&a>INT64_MAX-b)||(b<0&&a<INT64_MIN-b))throw Stop{2};
          n=(uint64_t)(a+b);
        } else if(m==2)n=get(SB_OP_SIZE)-p;
        set(SB_OP_SET_POS,n);break;
      }
      case SB_B_RESIZE:child(4);storage(0,c.arg(0));break;
      case SB_B_END:case SB_E_END:c.ret(get(SB_OP_POS)>=get(SB_OP_SIZE));break;
      case SB_B_READ:case SB_E_READ:case SB_B_WRITE: {
        auto old=get(SB_OP_POS);auto count=child(mode==SB_B_WRITE?6:5,old);
        set(SB_OP_SET_POS,get(SB_OP_POS)+count);c.ret(count);break;
      }
      case SB_B_READ_ABS:case SB_E_READ_ABS:case SB_B_WRITE_ABS: {
        auto p=c.arg(0); // size_t->StreamOffset cast-back is identity on frozen profile.
        static_assert(sizeof(size_t)==8&&sizeof(StreamOffset)==8,"profile");
        if((int64_t)(size_t)p!=(int64_t)p)c.raise(mode==SB_B_WRITE_ABS?4:3);
        c.ret(child(mode==SB_B_WRITE_ABS?6:5,p));break;
      }
      case SB_B_OPEN: {
        auto m=c.arg(0);if(m>255)throw Stop{2};set(SB_OP_SET_MODE,m);
        if((m&2)&&(m&8))child(7,0);
        if(m&4)child(8);break;
      }
      case SB_B_NAME:case SB_E_NAME:c.call(SB_OP_NAME);break;
      case SB_B_SIZE:case SB_B_DATA_SIZE:case SB_E_SIZE:case SB_E_DATA_SIZE:c.ret(get(SB_OP_SIZE));break;
      case SB_B_DATA:case SB_B_CONST_DATA:c.call(SB_OP_REF);break;
      case SB_B_TAKE:storage(5);child(0,0);break;
      case SB_B_PTR:child(4);c.call(SB_OP_PTR);break;
      case SB_B_CONST_PTR:case SB_E_PTR:c.call(SB_OP_PTR);break;
      case SB_B_RESERVE:child(4);storage(1,c.arg(0));break;
      case SB_B_CLEAR:set(SB_OP_SET_POS,0);storage(2);break;
      case SB_B_EMPTY:case SB_E_EMPTY:case SB_E_BOOL:c.ret(get(SB_OP_SIZE)==0);break;
      case SB_B_RESET_SIZE:set(SB_OP_SET_POS,0);storage(3,c.arg(0));break;
      case SB_B_RESET_BYTES:set(SB_OP_SET_POS,0);storage(4);break;
      case SB_B_COPY:case SB_B_MOVE:
        c.call(SB_OP_BASE_COPY);set(SB_OP_SET_POS,get(SB_OP_SOURCE_POS));
        c.call(SB_OP_SOURCE_STORAGE,mode==SB_B_MOVE?1:0);
        if(mode==SB_B_MOVE){set(SB_OP_SET_SOURCE_POS,0);c.call(SB_OP_SOURCE_STORAGE,2);}
        c.call(SB_OP_REF);break;
      case SB_B_PRIVATE_READ:case SB_E_PRIVATE_READ: {
        auto len=c.arg(1);if(!len){c.ret(0);break;}
        if(!(get(SB_OP_MODE)&1))c.raise(0);
        auto p=c.arg(0);if(p>=get(SB_OP_SIZE)){c.ret(0);break;}
        auto count=get(SB_OP_SIZE)-p;if(count>len)count=len;
        c.call(SB_OP_COPY_OUT,p,count);c.ret(count);break;
      }
      case SB_B_PRIVATE_WRITE: {
        auto len=c.arg(1);if(!len){c.ret(0);break;}
        if(!(get(SB_OP_MODE)&2))c.raise(1);
        auto p=c.arg(0);if(p+len>get(SB_OP_SIZE))storage(0,p+len);
        c.call(SB_OP_COPY_IN,p,len);c.ret(len);break;
      }
      case SB_E_CTOR:set(SB_OP_SET_POS,0);c.call(SB_OP_EXTERNAL_INIT);set(SB_OP_SET_MODE,1);break;
      case SB_E_CTOR_BYTES:child(9);break;
      case SB_E_RESET:set(SB_OP_SET_POS,0);c.call(SB_OP_EXTERNAL_BIND);break;
      case SB_E_WRITE:case SB_E_WRITE_ABS:c.raise(2);
      case SB_B_CLONE:c.call(SB_OP_CLONE_ALLOC);c.call(SB_OP_CLONE_SEEK);break;
      case SB_E_CLONE:c.call(SB_OP_LOG);c.call(SB_OP_CLONE_ALLOC);break;
      default:return 2;
    }
    c.call(SB_OP_FINISH);return 0;
  } catch(Stop const& s){return s.status;}catch(...){return 3;}
}

namespace {
// Native storage only. Addresses are bound in actual member scope, never by layout.
struct NativeCtx {
  uint32_t mode=0; bool busy=false,finished=false,posReady=true,extReady=true;
  std::exception_ptr pending;
  Buffer* owner=nullptr; Buffer const* constOwner=nullptr;
  ExternalBuffer* external=nullptr; ExternalBuffer const* constExternal=nullptr;
  size_t *position=nullptr;size_t const* constPosition=nullptr;
  ByteArray *bytes=nullptr;ByteArray const* constBytes=nullptr;
  char const** borrowed=nullptr;char const* const* constBorrowed=nullptr;
  size_t *externalSize=nullptr;size_t const* constExternalSize=nullptr;
  Buffer const* source=nullptr;Buffer* moveSource=nullptr;
  size_t const* sourcePosition=nullptr;size_t* moveSourcePosition=nullptr;
  ByteArray const* sourceBytes=nullptr;ByteArray* moveSourceBytes=nullptr;
  ByteArray* param=nullptr;char* output=nullptr;char const* input=nullptr;
  uint64_t args[3]={0,0,0},result=0;
  ByteArray value;ByteArray* ref=nullptr;ByteArray const* constRef=nullptr;
  char* pointer=nullptr;char const* constPointer=nullptr;
  String name;IODevicePtr clone;
  void (*setMode)(NativeCtx&,IOMode)=nullptr;
  void (*baseCopy)(NativeCtx&)=nullptr;
  uint64_t (*child)(NativeCtx&,uint64_t,uint64_t)=nullptr;
};
bool overlaps(uint64_t* out,void const* p,size_t n) {
  if(!p||!n)return false;
  auto a=(uintptr_t)out,b=(uintptr_t)p;
  if(n>UINTPTR_MAX-b)return true;
  return a<b+n&&b<a+sizeof(uint64_t);
}
bool safeOutput(NativeCtx& c,uint64_t* out) {
  auto a=(uintptr_t)out;
  if(!out||a%alignof(uint64_t)||a>UINTPTR_MAX-sizeof(uint64_t))return false;
  if(overlaps(out,&c,sizeof c)||overlaps(out,c.constOwner,sizeof(Buffer))||overlaps(out,c.constExternal,sizeof(ExternalBuffer))||overlaps(out,c.source,sizeof(Buffer))||overlaps(out,c.param,sizeof(ByteArray)))return false;
  if(overlaps(out,c.constPosition,sizeof(size_t))||overlaps(out,c.sourcePosition,sizeof(size_t))||overlaps(out,c.constExternalSize,sizeof(size_t))||overlaps(out,c.constBorrowed,sizeof(char const*)))return false;
  if(overlaps(out,c.constBytes,sizeof(ByteArray))||overlaps(out,c.sourceBytes,sizeof(ByteArray)))return false;
  if(c.constBytes&&overlaps(out,c.constBytes->ptr(),c.constBytes->size()))return false;
  if(c.sourceBytes&&overlaps(out,c.sourceBytes->ptr(),c.sourceBytes->size()))return false;
  if(c.param&&overlaps(out,c.param->ptr(),c.param->size()))return false;
  if(overlaps(out,c.value.ptr(),c.value.size()))return false;
  if(overlaps(out,c.name.utf8().data(),c.name.utf8().size()))return false;
  // Requested read length is not caller capacity: SIZE_MAX may copy just 8
  // bytes. Borrowed logical sizes also need not denote accessible storage until
  // actual IO. Check the bounded copied spans at COPY_OUT/IN, not here.
  if(auto p=dynamic_cast<Buffer*>(c.clone.get())){if(overlaps(out,p,sizeof(Buffer)))return false;}
  if(auto p=dynamic_cast<ExternalBuffer*>(c.clone.get())){if(overlaps(out,p,sizeof(ExternalBuffer)))return false;}
  return true;
}
uint32_t nativeHost(void* opaque,uint32_t op,uint64_t a,uint64_t b,uint64_t* out) noexcept {
  if(!opaque)return 2;
  auto& c=*static_cast<NativeCtx*>(opaque);
  if(c.pending)return 1;
  if(c.busy||c.finished||!safeOutput(c,out))return 2;
  c.busy=true;
  struct Unlock{bool& b;~Unlock(){b=false;}} unlock{c.busy};
  try {
    uint64_t r=0;
    // Each selector validates unused arguments before touching native state.
    auto need=[&](bool ok){if(!ok)throw Stop{2};};
    switch(op) {
      case SB_OP_ARG:need(a<3&&!b);r=c.args[a];break;
      case SB_OP_POS:need(!a&&!b&&c.posReady&&c.constPosition);r=*c.constPosition;break;
      case SB_OP_SET_POS:need(!b&&c.position);*c.position=a;c.posReady=true;break;
      case SB_OP_SIZE:need(!a&&!b);if(c.constBytes)r=c.constBytes->size();else{need(c.extReady&&c.constExternalSize);r=*c.constExternalSize;}break;
      case SB_OP_MODE:need(!a&&!b&&(c.constOwner||c.constExternal));r=(uint8_t)(c.constOwner?c.constOwner->mode():c.constExternal->mode());break;
      case SB_OP_SET_MODE:need(a<=255&&!b&&c.setMode);c.setMode(c,(IOMode)a);break;
      case SB_OP_STORAGE:need(c.bytes&&a<=5);need((a==0||a==1||a==3)||!b);switch(a){case 0:c.bytes->resize(b);break;case 1:c.bytes->reserve(b);break;case 2:c.bytes->clear();break;case 3:c.bytes->fill(b,0);break;case 4:need(c.param);*c.bytes=std::move(*c.param);break;case 5:c.value=std::move(*c.bytes);break;}break;
      case SB_OP_CHILD:need(c.child&&a<=9);need((a==0||a==5||a==6||a==7)||!b);r=c.child(c,a,b);break;
      case SB_OP_COPY_OUT: {
        need(c.extReady&&b<=c.args[1]);
        size_t size;char const* input;
        if(c.constBytes){size=c.constBytes->size();input=c.constBytes->ptr();}
        else{need(c.constBorrowed&&c.constExternalSize);size=*c.constExternalSize;input=*c.constBorrowed;}
        need(a<=size&&b<=size-a);
        if(b){
          need(input&&c.output);
          auto start=(uintptr_t)input,destination=(uintptr_t)c.output;
          need(a<=UINTPTR_MAX-start&&b<=UINTPTR_MAX-(start+a)&&b<=UINTPTR_MAX-destination);
          need(!overlaps(out,input+a,b)&&!overlaps(out,c.output,b));
          memcpy(c.output,input+a,b);
        }break;
      }
      case SB_OP_COPY_IN: {
        need(c.bytes&&b<=c.args[1]);auto size=c.bytes->size();
        need(a<=size&&b<=size-a);
        if(b){
          need(c.input&&c.bytes->ptr());
          auto input=(uintptr_t)c.input,destination=(uintptr_t)c.bytes->ptr();
          need(a<=UINTPTR_MAX-destination&&b<=UINTPTR_MAX-(destination+a)&&b<=UINTPTR_MAX-input);
          need(!overlaps(out,c.input,b)&&!overlaps(out,c.bytes->ptr()+a,b));
          memcpy(c.bytes->ptr()+a,c.input,b);
        }break;
      }
      case SB_OP_ERROR:need(a<=4&&!b);switch(a){case 0:throw IOException("Error, read called on non-readable Buffer");case 1:throw EofException("Error, write called on non-writable Buffer");case 2:throw IOException("Error, ExternalBuffer is not writable");case 3:throw IOException("Error, readPosition out of range");default:throw IOException("Error, writePosition out of range");}
      case SB_OP_RESULT:need(!b);c.result=a;break;
      case SB_OP_FINISH:need(!a&&!b);c.finished=true;break;
      case SB_OP_SOURCE_POS:need(!a&&!b&&c.sourcePosition);r=*c.sourcePosition;break;
      case SB_OP_SET_SOURCE_POS:need(!b&&c.moveSourcePosition);*c.moveSourcePosition=a;break;
      case SB_OP_BASE_COPY:need(!a&&!b&&c.baseCopy&&c.source);c.baseCopy(c);break;
      case SB_OP_SOURCE_STORAGE:need(a<=2&&!b&&c.bytes);if(a==0){need(c.sourceBytes);*c.bytes=*c.sourceBytes;}else{need(c.moveSourceBytes);if(a==1)*c.bytes=std::move(*c.moveSourceBytes);else *c.moveSourceBytes=ByteArray();}break;
      case SB_OP_EXTERNAL_INIT:need(!a&&!b&&c.borrowed&&c.externalSize);*c.borrowed=nullptr;*c.externalSize=0;c.extReady=true;break;
      case SB_OP_EXTERNAL_BIND:need(!a&&!b&&c.borrowed&&c.externalSize);*c.borrowed=c.input;*c.externalSize=c.args[0];c.extReady=true;break;
      case SB_OP_NAME:need(!a&&!b);if(c.constOwner)c.name=strf("Buffer <{}>",(void const*)c.constOwner);else{need(c.constExternal);c.name=strf("ExternalBuffer <{}>",(void const*)c.constExternal);}break;
      case SB_OP_CLONE_ALLOC:need(!a&&!b);if(c.owner)c.clone=make_shared<Buffer>(*c.owner);else{need(c.external);c.clone=make_shared<ExternalBuffer>(*c.external);}break;
      case SB_OP_CLONE_SEEK:need(!a&&!b&&c.clone);c.clone->seek(0);break;
      case SB_OP_LOG:need(!a&&!b&&c.external);Logger::info("Cloning ExternalBuffer from position {}");break;
      case SB_OP_REF:need(!a&&!b&&c.constBytes);c.ref=c.bytes;c.constRef=c.constBytes;break;
      case SB_OP_PTR:need(!a&&!b);if(c.mode==SB_B_PTR){need(c.ref);c.pointer=c.ref->ptr();c.constPointer=c.pointer;}else if(c.constBytes)c.constPointer=c.constBytes->ptr();else{need(c.extReady&&c.constBorrowed);c.constPointer=*c.constBorrowed;}break;
      default:return 2;
    }
    *out=r;return 0;
  }catch(Stop const& s){return s.status;}catch(...){c.pending=std::current_exception();return 1;}
}
void execute(NativeCtx& c,uint32_t mode){c.mode=mode;auto s=sb_buffer_run(mode,&c,nativeHost);if(c.pending)std::rethrow_exception(c.pending);if(s||!c.finished)throw std::runtime_error("Buffer native controller protocol");}
}

// Capturingless member-scope thunks have legal private/protected access. No
// std::function allocation, field-layout mirror, or owner-wide busy lock.
#define BCONST NativeCtx c; c.constOwner=this;c.constPosition=&m_pos;c.constBytes=&m_bytes
#define BCTX BCONST; c.owner=this;c.position=&m_pos;c.bytes=&m_bytes; \
 c.setMode=+[](NativeCtx& x,IOMode m){x.owner->setMode(m);}; \
 c.baseCopy=+[](NativeCtx& x){x.owner->IODevice::operator=(*x.source);}; \
 c.child=+[](NativeCtx& x,uint64_t op,uint64_t v)->uint64_t{switch(op){ \
 case 0:x.owner->reset((size_t)v);break;case 1:if(!x.param)throw Stop{2};x.owner->reset(std::move(*x.param));break; \
 case 2:if(!x.source)throw Stop{2};*x.owner=*x.source;break;case 3:if(!x.moveSource)throw Stop{2};*x.owner=std::move(*x.moveSource);break; \
 case 4:x.ref=&x.owner->data();break;case 5:return x.owner->doRead(v,x.output,x.args[1]);case 6:return x.owner->doWrite(v,x.input,x.args[1]); \
 case 7:x.owner->resize((StreamOffset)v);break;case 8:x.owner->seek(0,IOSeek::End);break;default:throw Stop{2};}return 0;}
#define ECONST NativeCtx c;c.constExternal=this;c.constPosition=&m_pos;c.constBorrowed=&m_bytes;c.constExternalSize=&m_size
#define ECTX ECONST;c.external=this;c.position=&m_pos;c.borrowed=&m_bytes;c.externalSize=&m_size; \
 c.setMode=+[](NativeCtx& x,IOMode m){x.external->setMode(m);}; \
 c.child=+[](NativeCtx& x,uint64_t op,uint64_t v)->uint64_t{if(op==9){x.external->reset(x.input,x.args[0]);return 0;}if(op!=5)throw Stop{2};return x.external->doRead(v,x.output,x.args[1]);}
#define SRC c.source=&buffer;c.sourcePosition=&buffer.m_pos;c.sourceBytes=&buffer.m_bytes
#define MOVESRC SRC;c.moveSource=&buffer;c.moveSourcePosition=&buffer.m_pos;c.moveSourceBytes=&buffer.m_bytes
namespace Star {
Buffer::Buffer(){BCTX;c.posReady=false;execute(c,SB_B_CTOR);}
Buffer::Buffer(size_t initialSize):Buffer(){BCTX;c.args[0]=initialSize;execute(c,SB_B_CTOR_SIZE);}
Buffer::Buffer(ByteArray b):Buffer(){BCTX;c.param=&b;execute(c,SB_B_CTOR_BYTES);}
Buffer::Buffer(Buffer const& buffer):Buffer(){BCTX;SRC;execute(c,SB_B_CTOR_COPY);}
Buffer::Buffer(Buffer&& buffer):Buffer(){BCTX;MOVESRC;execute(c,SB_B_CTOR_MOVE);}
StreamOffset Buffer::pos(){BCTX;execute(c,SB_B_POS);return c.result;}
void Buffer::seek(StreamOffset pos,IOSeek mode){BCTX;c.args[0]=pos;c.args[1]=(uint8_t)mode;execute(c,SB_B_SEEK);}
void Buffer::resize(StreamOffset size){BCTX;c.args[0]=size;execute(c,SB_B_RESIZE);}
bool Buffer::atEnd(){BCTX;execute(c,SB_B_END);return c.result;}
size_t Buffer::read(char* data,size_t len){BCTX;c.output=data;c.args[1]=len;execute(c,SB_B_READ);return c.result;}
size_t Buffer::write(char const* data,size_t len){BCTX;c.input=data;c.args[1]=len;execute(c,SB_B_WRITE);return c.result;}
size_t Buffer::readAbsolute(StreamOffset p,char* data,size_t len){BCTX;c.output=data;c.args[0]=p;c.args[1]=len;execute(c,SB_B_READ_ABS);return c.result;}
size_t Buffer::writeAbsolute(StreamOffset p,char const* data,size_t len){BCTX;c.input=data;c.args[0]=p;c.args[1]=len;execute(c,SB_B_WRITE_ABS);return c.result;}
void Buffer::open(IOMode mode){BCTX;c.args[0]=(uint8_t)mode;execute(c,SB_B_OPEN);}
String Buffer::deviceName()const{BCONST;execute(c,SB_B_NAME);return std::move(c.name);}
StreamOffset Buffer::size(){BCTX;execute(c,SB_B_SIZE);return c.result;}
ByteArray& Buffer::data(){BCTX;execute(c,SB_B_DATA);return *c.ref;}
ByteArray const& Buffer::data()const{BCONST;execute(c,SB_B_CONST_DATA);return *c.constRef;}
ByteArray Buffer::takeData(){BCTX;execute(c,SB_B_TAKE);return std::move(c.value);}
char* Buffer::ptr(){BCTX;execute(c,SB_B_PTR);return c.pointer;}
char const* Buffer::ptr()const{BCONST;execute(c,SB_B_CONST_PTR);return c.constPointer;}
size_t Buffer::dataSize()const{BCONST;execute(c,SB_B_DATA_SIZE);return c.result;}
void Buffer::reserve(size_t size){BCTX;c.args[0]=size;execute(c,SB_B_RESERVE);}
void Buffer::clear(){BCTX;execute(c,SB_B_CLEAR);}
bool Buffer::empty()const{BCONST;execute(c,SB_B_EMPTY);return c.result;}
void Buffer::reset(size_t size){BCTX;c.args[0]=size;execute(c,SB_B_RESET_SIZE);}
void Buffer::reset(ByteArray b){BCTX;c.param=&b;execute(c,SB_B_RESET_BYTES);}
Buffer& Buffer::operator=(Buffer const& buffer){BCTX;SRC;execute(c,SB_B_COPY);return *this;}
Buffer& Buffer::operator=(Buffer&& buffer){BCTX;MOVESRC;execute(c,SB_B_MOVE);return *this;}
size_t Buffer::doRead(size_t pos,char* data,size_t len){BCTX;c.args[0]=pos;c.args[1]=len;c.output=data;execute(c,SB_B_PRIVATE_READ);return c.result;}
size_t Buffer::doWrite(size_t pos,char const* data,size_t len){BCTX;c.args[0]=pos;c.args[1]=len;c.input=data;execute(c,SB_B_PRIVATE_WRITE);return c.result;}
ExternalBuffer::ExternalBuffer(){ECTX;c.posReady=false;c.extReady=false;execute(c,SB_E_CTOR);}
ExternalBuffer::ExternalBuffer(char const* data,size_t len):ExternalBuffer(){ECTX;c.input=data;c.args[0]=len;execute(c,SB_E_CTOR_BYTES);}
StreamOffset ExternalBuffer::pos(){ECTX;execute(c,SB_E_POS);return c.result;}
void ExternalBuffer::seek(StreamOffset pos,IOSeek mode){ECTX;c.args[0]=pos;c.args[1]=(uint8_t)mode;execute(c,SB_E_SEEK);}
bool ExternalBuffer::atEnd(){ECTX;execute(c,SB_E_END);return c.result;}
size_t ExternalBuffer::read(char* data,size_t len){ECTX;c.output=data;c.args[1]=len;execute(c,SB_E_READ);return c.result;}
size_t ExternalBuffer::write(char const*,size_t){ECTX;execute(c,SB_E_WRITE);return c.result;}
size_t ExternalBuffer::readAbsolute(StreamOffset pos,char* data,size_t len){ECTX;c.output=data;c.args[0]=pos;c.args[1]=len;execute(c,SB_E_READ_ABS);return c.result;}
size_t ExternalBuffer::writeAbsolute(StreamOffset,char const*,size_t){ECTX;execute(c,SB_E_WRITE_ABS);return c.result;}
String ExternalBuffer::deviceName()const{ECONST;execute(c,SB_E_NAME);return std::move(c.name);}
StreamOffset ExternalBuffer::size(){ECTX;execute(c,SB_E_SIZE);return c.result;}
char const* ExternalBuffer::ptr()const{ECONST;execute(c,SB_E_PTR);return c.constPointer;}
size_t ExternalBuffer::dataSize()const{ECONST;execute(c,SB_E_DATA_SIZE);return c.result;}
bool ExternalBuffer::empty()const{ECONST;execute(c,SB_E_EMPTY);return c.result;}
ExternalBuffer::operator bool()const{ECONST;execute(c,SB_E_BOOL);return c.result;}
void ExternalBuffer::reset(char const* data,size_t len){ECTX;c.input=data;c.args[0]=len;execute(c,SB_E_RESET);}
IODevicePtr Buffer::clone(){BCTX;execute(c,SB_B_CLONE);return std::move(c.clone);}
IODevicePtr ExternalBuffer::clone(){ECTX;execute(c,SB_E_CLONE);return std::move(c.clone);}
size_t ExternalBuffer::doRead(size_t pos,char* data,size_t len){ECTX;c.output=data;c.args[0]=pos;c.args[1]=len;execute(c,SB_E_PRIVATE_READ);return c.result;}
}
#undef BCTX
#undef BCONST
#undef ECTX
#undef ECONST
#undef SRC
#undef MOVESRC
