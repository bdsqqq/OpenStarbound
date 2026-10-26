#pragma once
#include "StarRustBuffer.h"
#include "StarBuffer.hpp"
#include "StarFormat.hpp"
#include "StarLogging.hpp"
#include <exception>
#include <limits>
#include <stdexcept>
#include <cstring>

namespace Star::BufferRust {
static_assert(sizeof(size_t)==8 && sizeof(StreamOffset)==8, "Buffer Rust native profile requires 64-bit offsets");
struct Stop { uint32_t status; };
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
inline bool overlaps(uint64_t* out,void const* p,size_t n) {
  if(!p||!n)return false;
  auto a=(uintptr_t)out,b=(uintptr_t)p;
  if(n>UINTPTR_MAX-b)return true;
  return a<b+n&&b<a+sizeof(uint64_t);
}
inline bool safeOutput(NativeCtx& c,uint64_t* out) {
  auto a=(uintptr_t)out;
  if(!out||a%alignof(uint64_t)||a>UINTPTR_MAX-sizeof(uint64_t))return false;
  if(overlaps(out,&c,sizeof c)||overlaps(out,c.constOwner,sizeof(Buffer))||overlaps(out,c.constExternal,sizeof(ExternalBuffer))||overlaps(out,c.source,sizeof(Buffer))||overlaps(out,c.param,sizeof(ByteArray)))return false;
  if(overlaps(out,c.constPosition,sizeof(size_t))||overlaps(out,c.sourcePosition,sizeof(size_t))||overlaps(out,c.constExternalSize,sizeof(size_t))||overlaps(out,c.constBorrowed,sizeof(char const*)))return false;
  if(overlaps(out,c.constBytes,sizeof(ByteArray))||overlaps(out,c.sourceBytes,sizeof(ByteArray)))return false;
  // Guard bookkeeping reads current native fields; it must not recursively run
  // public controllers. No snapshot survives mutation or a foreign callback.
  auto arrayOverlaps=[&](ByteArray const& bytes){
#ifdef STAR_USE_RUST_BYTE_ARRAY
    auto& live=const_cast<ByteArray&>(bytes);
    return overlaps(out,ByteArrayNativeAccess::data(live),ByteArrayNativeAccess::size(live));
#else
    return overlaps(out,bytes.ptr(),bytes.size());
#endif
  };
  if(c.constBytes&&arrayOverlaps(*c.constBytes))return false;
  if(c.sourceBytes&&arrayOverlaps(*c.sourceBytes))return false;
  if(c.param&&arrayOverlaps(*c.param))return false;
  if(arrayOverlaps(c.value))return false;
  if(overlaps(out,c.name.utf8().data(),c.name.utf8().size()))return false;
  // Requested read length is not caller capacity: SIZE_MAX may copy just 8
  // bytes. Borrowed logical sizes also need not denote accessible storage until
  // actual IO. Check the bounded copied spans at COPY_OUT/IN, not here.
  if(auto p=dynamic_cast<Buffer*>(c.clone.get())){if(overlaps(out,p,sizeof(Buffer)))return false;}
  if(auto p=dynamic_cast<ExternalBuffer*>(c.clone.get())){if(overlaps(out,p,sizeof(ExternalBuffer)))return false;}
  return true;
}
inline uint32_t nativeHost(void* opaque,uint32_t op,uint64_t a,uint64_t b,uint64_t* out) noexcept {
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
inline void execute(NativeCtx& c,uint32_t mode){c.mode=mode;auto s=star_buffer_run(mode,&c,nativeHost);if(c.pending)std::rethrow_exception(c.pending);if(s||!c.finished)throw std::runtime_error("Buffer native controller protocol");}
}
