#pragma once
#include "StarRustZstd.h"
#include "StarByteArray.hpp"
#include "StarDataStreamDevices.hpp"
#include <zstd.h>
#include <exception>
#include <limits>
#include <utility>

namespace Star::ZstdHost {
static_assert(sizeof(size_t)==8 && sizeof(unsigned long long)==8 && sizeof(uint64_t)==8);
static_assert(std::numeric_limits<size_t>::digits==64 && std::numeric_limits<unsigned long long>::digits==64);
// All allocations, native metadata and borrowed persistent handles stay here.
struct NativeContext {
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
  NativeContext(uint32_t m,char const* p,size_t n,Star::ByteArray* s=nullptr):mode(m),input(p),length(n),stream(s) {}
};
inline uint32_t nativeHost(void* opaque,uint32_t op,uint64_t a,uint64_t b,uint64_t* scalar) noexcept {
  if(!opaque || !scalar) return ZC_HOST_INVALID;
  auto address=reinterpret_cast<uintptr_t>(scalar), base=reinterpret_cast<uintptr_t>(opaque);
  if(address%8 || address>UINTPTR_MAX-8 || base>UINTPTR_MAX-sizeof(NativeContext) ||
     (address<base+sizeof(NativeContext) && base<address+8)) return ZC_HOST_INVALID;
  auto& c=*static_cast<NativeContext*>(opaque);
  if(c.pending || c.busy || op>17 || (b && op!=ZC_PREPARE_OUT)) return ZC_HOST_INVALID;
  bool hasArg=op==ZC_BEGIN || op==ZC_GET || op==ZC_RESIZE_STREAM || op==ZC_PREPARE_OUT || op==ZC_ALLOC_RESULT_ZERO || op==ZC_IS_ERROR || op==ZC_RAISE_CODEC || op==ZC_RESIZE_RESULT;
  if(!hasArg && a) return ZC_HOST_INVALID;
  using C=NativeContext;
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
        c.stream->resize(a); c.phase=C::Sized; break;
      case ZC_PREPARE_OUT: c.out={c.stream->ptr()+a,size_t(b),0}; c.phase=C::Prepared; break;
      case ZC_STEP_COMPRESS: value=ZSTD_compressStream2(c.compression,&c.out,&c.in,ZSTD_e_flush); c.last=value; c.phase=C::Stepped; break;
      case ZC_STEP_DECOMPRESS: value=ZSTD_decompressStream(c.decompression,&c.out,&c.in); c.last=value; c.phase=C::Stepped; break;
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

// Rethrow before context/result destruction; persistent handles remain caller-owned.
inline void run(NativeContext& c) {
  uint32_t status=star_zstd_run(c.mode,nativeHost,&c);
  if(status==ZC_NATIVE_PENDING && c.pending) std::rethrow_exception(c.pending);
  if(status!=ZC_COMPLETE || c.pending)
    throw StarException("Invalid Rust Zstd controller result");
}
} // namespace Star::ZstdHost
