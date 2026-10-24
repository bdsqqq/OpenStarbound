#include "host_contract.hpp"
#include "StarByteArray.hpp"
#include "StarDataStreamDevices.hpp"
#include <zstd.h>
#include <algorithm>
#include <exception>
#include <limits>
#include <utility>

namespace ZstdLab {
static_assert(sizeof(size_t)==8 && sizeof(unsigned long long)==8 && sizeof(uint64_t)==8);
static_assert(std::numeric_limits<size_t>::digits==64 && std::numeric_limits<unsigned long long>::digits==64);
struct Stop { uint32_t status; };
// No native object or host identity is visible to this controller.
uint32_t run(uint32_t mode, StarZstdHost host, void* opaque) noexcept {
  if (mode>3 || !host) return ZC_INVALID;
  try {
    auto call=[&](uint32_t op,uint64_t a=0,uint64_t b=0) {
      alignas(8) uint64_t value=0;
      uint32_t s=host(opaque,op,a,b,&value);
      if(s) throw Stop{s==ZC_EXCEPTION ? ZC_NATIVE_PENDING : ZC_INVALID};
      return value;
    };
    auto get=[&](uint64_t f) {return call(ZC_GET,f);};
    call(ZC_BEGIN,mode);
    if(mode<2) {
      uint64_t chunk=call(ZC_STREAM_CHUNK);
      call(ZC_INIT_INPUT);
      uint64_t written=get(ZC_OUTPUT_SIZE);
      call(ZC_RESIZE_STREAM,get(ZC_OUTPUT_SIZE)+chunk);
      for(;;) {
        call(ZC_PREPARE_OUT,written,std::min(chunk,get(ZC_OUTPUT_SIZE)-written));
        uint64_t ret=call(mode==0?ZC_STEP_COMPRESS:ZC_STEP_DECOMPRESS);
        if(call(ZC_IS_ERROR,ret)) call(ZC_RAISE_CODEC,ret);
        uint64_t pos=get(ZC_OUTPUT_POS);
        written+=pos;
        if(pos==get(ZC_OUTPUT_CAPACITY)) {
          if(written>=get(ZC_OUTPUT_SIZE)) call(ZC_RESIZE_STREAM,get(ZC_OUTPUT_SIZE)*2);
          continue;
        }
        if((mode==1 || ret==0) && get(ZC_INPUT_POS)==get(ZC_INPUT_SIZE)) break;
      }
      call(ZC_RESIZE_STREAM,written);
    } else {
      if(mode==2 && get(ZC_INPUT_LENGTH)==0) {call(ZC_EMPTY_RESULT); return ZC_COMPLETE;}
      uint64_t size;
      if(mode==2) size=call(ZC_COMPRESS_BOUND);
      else {
        size=call(ZC_FRAME_SIZE);
        if(size==get(ZC_FRAME_UNKNOWN) || size==get(ZC_FRAME_ERROR)) call(ZC_RAISE_SIZE);
      }
      call(ZC_ALLOC_RESULT_ZERO,size);
      uint64_t ret=call(mode==2?ZC_ONESHOT_COMPRESS_CALL:ZC_ONESHOT_DECOMPRESS_CALL);
      if(call(ZC_IS_ERROR,ret)) call(ZC_RAISE_CODEC,ret);
      call(ZC_RESIZE_RESULT,ret);
    }
    return ZC_COMPLETE;
  } catch(Stop const& s) {return s.status;} catch(...) {return ZC_PANIC;}
}

// All allocations, native metadata and borrowed persistent handles stay here.
struct Context {
  uint32_t mode;
  char const* input;
  size_t length;
  Star::ByteArray* stream;
  Star::ByteArray result;
  ZSTD_CStream* compression=nullptr;
  ZSTD_DStream* decompression=nullptr;
  int level=2;
  ZSTD_inBuffer in{};
  ZSTD_outBuffer out{};
  std::exception_ptr pending;
  enum Phase { Fresh, Begun, Chunk, Input, Sized, Prepared, Stepped, Checked, Bound, Allocated, Called, Done } phase=Fresh;
  bool busy=false, lastError=false;
  size_t last=0;
  // Fixed, nonthrowing observations; overflow makes a test invalid.
  uint32_t trace[4096]{};
  size_t traceSize=0, steps=0;
  bool traceOverflow=false;
  std::exception_ptr resizeFault;
  size_t faultAfter=std::numeric_limits<size_t>::max();
  Context(uint32_t m,char const* p,size_t n,Star::ByteArray* s=nullptr):mode(m),input(p),length(n),stream(s) {}
};
uint32_t host(void* opaque,uint32_t op,uint64_t a,uint64_t b,uint64_t* scalar) noexcept {
  if(!opaque || !scalar) return ZC_HOST_INVALID;
  auto address=reinterpret_cast<uintptr_t>(scalar), base=reinterpret_cast<uintptr_t>(opaque);
  if(address%8 || address>UINTPTR_MAX-8 || base>UINTPTR_MAX-sizeof(Context) ||
     (address<base+sizeof(Context) && base<address+8)) return ZC_HOST_INVALID;
  auto& c=*static_cast<Context*>(opaque);
  if(c.pending || c.busy || op>17 || (b && op!=ZC_PREPARE_OUT)) return ZC_HOST_INVALID;
  bool hasArg=op==ZC_BEGIN || op==ZC_GET || op==ZC_RESIZE_STREAM || op==ZC_PREPARE_OUT || op==ZC_ALLOC_RESULT_ZERO || op==ZC_IS_ERROR || op==ZC_RAISE_CODEC || op==ZC_RESIZE_RESULT;
  if(!hasArg && a) return ZC_HOST_INVALID;
  using C=Context;
  bool valid=false;
  switch(op) {
    case ZC_BEGIN: valid=c.phase==C::Fresh && a==c.mode && a<4 && (a>=2 || (c.stream && (a==0?bool(c.compression):bool(c.decompression)))); break;
    case ZC_GET: valid=c.phase!=C::Fresh && a<=8; break;
    case ZC_STREAM_CHUNK: valid=c.mode<2 && c.phase==C::Begun; break;
    case ZC_INIT_INPUT: valid=c.mode<2 && c.phase==C::Chunk; break;
    case ZC_RESIZE_STREAM: valid=c.mode<2 && (c.phase==C::Input || (c.phase==C::Checked && !c.lastError)); break;
    case ZC_PREPARE_OUT: valid=c.mode<2 && (c.phase==C::Sized || (c.phase==C::Checked && !c.lastError)) && a<=c.stream->size() && b<=c.stream->size()-a; break;
    case ZC_STEP_COMPRESS: valid=c.mode==0 && c.phase==C::Prepared; break;
    case ZC_STEP_DECOMPRESS: valid=c.mode==1 && c.phase==C::Prepared; break;
    case ZC_COMPRESS_BOUND: valid=c.mode==2 && c.phase==C::Begun && c.length; break;
    case ZC_FRAME_SIZE: valid=c.mode==3 && c.phase==C::Begun; break;
    case ZC_ALLOC_RESULT_ZERO: valid=c.mode>=2 && c.phase==C::Bound && a==c.last && (c.mode==2 || (a!=ZSTD_CONTENTSIZE_ERROR && a!=ZSTD_CONTENTSIZE_UNKNOWN)); break;
    case ZC_ONESHOT_COMPRESS_CALL: valid=c.mode==2 && c.phase==C::Allocated; break;
    case ZC_ONESHOT_DECOMPRESS_CALL: valid=c.mode==3 && c.phase==C::Allocated; break;
    case ZC_IS_ERROR: valid=(c.phase==C::Stepped || c.phase==C::Called) && a==c.last; break;
    case ZC_RAISE_CODEC: valid=c.phase==C::Checked && a==c.last && c.lastError; break;
    case ZC_RAISE_SIZE: valid=c.mode==3 && c.phase==C::Bound && (c.last==ZSTD_CONTENTSIZE_ERROR || c.last==ZSTD_CONTENTSIZE_UNKNOWN); break;
    case ZC_RESIZE_RESULT: valid=c.mode>=2 && c.phase==C::Checked && a==c.last && !c.lastError; break;
    case ZC_EMPTY_RESULT: valid=c.mode==2 && c.phase==C::Begun && !c.length; break;
  }
  if(!valid) return ZC_HOST_INVALID;
  c.busy=true;
  struct Guard {bool& busy; ~Guard(){busy=false;}} guard{c.busy};
  if(c.traceSize<4096) c.trace[c.traceSize++]=op; else c.traceOverflow=true;
  try {
    uint64_t value=0;
    switch(op) {
      case ZC_BEGIN: c.phase=C::Begun; break;
      case ZC_GET:
        switch(a) {
          case ZC_INPUT_LENGTH: value=c.length; break;
          case ZC_INPUT_POS: value=c.in.pos; break;
          case ZC_INPUT_SIZE: value=c.in.size; break;
          case ZC_OUTPUT_SIZE: value=c.stream?c.stream->size():c.result.size(); break;
          case ZC_OUTPUT_POS: value=c.out.pos; break;
          case ZC_OUTPUT_CAPACITY: value=c.out.size; break;
          case ZC_FRAME_UNKNOWN: value=ZSTD_CONTENTSIZE_UNKNOWN; break;
          case ZC_FRAME_ERROR: value=ZSTD_CONTENTSIZE_ERROR; break;
          case ZC_NATIVE_SIZE_MAX: value=SIZE_MAX; break;
        } break;
      case ZC_STREAM_CHUNK: value=c.mode==0?ZSTD_CStreamOutSize():ZSTD_DStreamOutSize(); c.phase=C::Chunk; break;
      case ZC_INIT_INPUT: c.in={c.input,c.length,0}; c.phase=C::Input; break;
      case ZC_RESIZE_STREAM:
        if(c.resizeFault && c.steps>=c.faultAfter) std::rethrow_exception(c.resizeFault);
        c.stream->resize(a); c.phase=C::Sized; break;
      case ZC_PREPARE_OUT: c.out={c.stream->ptr()+a,size_t(b),0}; c.phase=C::Prepared; break;
      case ZC_STEP_COMPRESS: value=ZSTD_compressStream2(c.compression,&c.out,&c.in,ZSTD_e_flush); ++c.steps; c.last=value; c.phase=C::Stepped; break;
      case ZC_STEP_DECOMPRESS: value=ZSTD_decompressStream(c.decompression,&c.out,&c.in); ++c.steps; c.last=value; c.phase=C::Stepped; break;
      case ZC_COMPRESS_BOUND: value=ZSTD_compressBound(c.length); c.last=value; c.phase=C::Bound; break;
      case ZC_FRAME_SIZE: value=ZSTD_getFrameContentSize(c.input,c.length); c.last=value; c.phase=C::Bound; break;
      case ZC_ALLOC_RESULT_ZERO: c.result=Star::ByteArray(a,0); c.phase=C::Allocated; break;
      case ZC_ONESHOT_COMPRESS_CALL: value=ZSTD_compress(c.result.ptr(),c.result.size(),c.input,c.length,c.level); c.last=value; c.phase=C::Called; break;
      case ZC_ONESHOT_DECOMPRESS_CALL: value=ZSTD_decompress(c.result.ptr(),c.result.size(),c.input,c.length); c.last=value; c.phase=C::Called; break;
      case ZC_IS_ERROR: value=ZSTD_isError(a); c.lastError=value!=0; c.phase=C::Checked; break;
      case ZC_RAISE_CODEC: throw Star::IOException(Star::strf(c.mode==0 || c.mode==2?"ZSTD compression error {}":"ZSTD decompression error {}",ZSTD_getErrorName(a)));
      case ZC_RAISE_SIZE: throw Star::IOException("Cannot determine ZSTD decompressed size");
      case ZC_RESIZE_RESULT: c.result.resize(a); c.phase=C::Done; break;
      case ZC_EMPTY_RESULT: c.result=Star::ByteArray(); c.phase=C::Done; break;
    }
    *scalar=value; return ZC_OK;
  } catch(...) {c.pending=std::current_exception(); return ZC_EXCEPTION;}
}
void invoke(Context& c,StarZstdHost callback=host) {
  uint32_t status=run(c.mode,callback,&c);
  if(c.pending) std::rethrow_exception(c.pending);
  if(status!=ZC_COMPLETE) throw Star::IOException("Zstd lab protocol failure");
}
Star::ByteArray oneShot(uint32_t mode,char const* input,size_t length,int level=2) {
  Context c(mode,input,length); c.level=level; invoke(c); return std::move(c.result);
}
struct CompressionHandle {
  ZSTD_CStream* value=ZSTD_createCStream();
  CompressionHandle() {ZSTD_CCtx_setParameter(value,ZSTD_c_enableLongDistanceMatching,1); ZSTD_CCtx_setParameter(value,ZSTD_c_windowLog,24); ZSTD_initCStream(value,2);}
  ~CompressionHandle(){ZSTD_freeCStream(value);}
  CompressionHandle(CompressionHandle const&)=delete;
};
struct DecompressionHandle {
  ZSTD_DStream* value=ZSTD_createDStream();
  DecompressionHandle(){ZSTD_DCtx_setParameter(value,ZSTD_d_windowLogMax,25); ZSTD_initDStream(value);}
  ~DecompressionHandle(){ZSTD_freeDStream(value);}
  DecompressionHandle(DecompressionHandle const&)=delete;
};
}
