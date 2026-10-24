#pragma once
#include "StarRustCompression.h"
#include "StarCompression.hpp"
#include "StarFormat.hpp"
#include <zlib-ng.h>
#include <exception>
#include <memory>
#include <type_traits>
#include <limits>

namespace Star::CompressionHost {
constexpr uint32_t Slab = 32768;
static_assert(std::is_same_v<decltype(zng_stream{}.avail_in), uint32_t>);
static_assert(std::is_same_v<decltype(zng_stream{}.avail_out), uint32_t>);
static uint64_t encode(int code) { return uint32_t(code); }
static int decode(uint64_t code) { return int32_t(uint32_t(code)); }
enum class Phase { Fresh, Cleared, EmptyRead, Allocated, Zeroed, Initialized,
  Bound, Reset, Stepped, Observed, FullAppended, Ended, TailAppended };

// Native ownership deliberately does not perform codec End on destruction.
// The outer C++ frame must rethrow pending before releasing this context.
struct NativeContext {
  uint32_t kind;
  ByteArray const* input;
  ByteArray& output;
  char const* raw;
  size_t length;
  int level;
  size_t limit;
  std::unique_ptr<uint8_t[]> temp;
  zng_stream stream{};
  std::exception_ptr pending;
  Phase phase = Phase::Fresh;
  bool callback = false, initialized = false, ended = false;
  bool limitRead = false, sizeRead = false, tailObserved = false;
  size_t steps = 0;
  int initCode = Z_OK, stepCode = Z_OK;
  uint32_t observed = Slab;
  size_t observedSize = 0;
  NativeContext(ByteArray const& i, ByteArray& o, int l)
    : kind(SC_DEFLATE), input(&i), output(o), raw(nullptr), length(0), level(l), limit(0) {}
  NativeContext(uint32_t k, char const* i, size_t n, ByteArray& o, size_t cap)
    : kind(k), input(nullptr), output(o), raw(i), length(n), level(0), limit(cap) {}

};

inline uint32_t nativeHost(void* opaque, uint32_t op, uint64_t arg, uint64_t* scalar) noexcept {
  if (!opaque || !scalar) return SC_HOST_INVALID;
  auto p = reinterpret_cast<uintptr_t>(scalar);
  auto c = reinterpret_cast<uintptr_t>(opaque);
  if (p % 8 || p > UINTPTR_MAX - 8 || c > UINTPTR_MAX - sizeof(NativeContext)
      || (p < c + sizeof(NativeContext) && c < p + 8)) return SC_HOST_INVALID;
  auto& x = *static_cast<NativeContext*>(opaque);
  if (x.callback || x.pending || op > SC_RAISE_LIMIT || x.kind > SC_GZIP)
    return SC_HOST_INVALID;
  if ((op == SC_CLEAR_OUTPUT && arg != x.kind)
      || (op == SC_APPEND_TEMP && arg > Slab)
      || ((op == SC_RAISE_INIT || op == SC_RAISE_CODEC) && arg > UINT32_MAX)
      || (op != SC_CLEAR_OUTPUT && op != SC_APPEND_TEMP && op != SC_RAISE_INIT
          && op != SC_RAISE_CODEC && arg != 0)) return SC_HOST_INVALID;
  bool valid = false;
  switch (op) {
    case SC_CLEAR_OUTPUT: valid = x.phase == Phase::Fresh; break;
    case SC_INPUT_EMPTY: valid = x.phase == Phase::Cleared; break;
    case SC_ALLOCATE_TEMP: valid = x.phase == Phase::EmptyRead &&
      (x.kind == SC_DEFLATE ? !x.input->empty() : x.length != 0); break;
    case SC_ZERO_STREAM: valid = x.phase == Phase::Allocated; break;
    case SC_INIT_CODEC: valid = x.phase == Phase::Zeroed; break;
    case SC_BIND_INPUT: valid = x.phase == Phase::Initialized && x.initCode == Z_OK; break;
    case SC_RESET_OUTPUT: valid = x.phase == Phase::Bound || x.phase == Phase::FullAppended; break;
    case SC_STEP_FINISH: valid = (x.phase == Phase::Reset || (x.phase == Phase::Observed && x.observed != 0 && x.stepCode == Z_OK)) && !x.ended &&
      (x.stepCode == Z_OK || (x.kind != SC_DEFLATE && x.stepCode == Z_BUF_ERROR)); break;
    case SC_AVAIL_OUT: valid = x.phase == Phase::Stepped || x.phase == Phase::Ended; break;
    case SC_APPEND_TEMP: valid = (x.phase == Phase::Observed && x.observed == 0 && arg == Slab && !x.ended)
      || (x.phase == Phase::Ended && x.ended && x.tailObserved && x.stepCode == Z_STREAM_END && x.observed <= Slab && arg == Slab - x.observed); break;
    case SC_READ_LIMIT: valid = x.kind != SC_DEFLATE && x.phase == Phase::Reset && x.steps && !x.limitRead; break;
    case SC_OUTPUT_SIZE: valid = x.kind != SC_DEFLATE && x.phase == Phase::Reset && x.limitRead && x.limit && !x.sizeRead; break;
    case SC_END_CODEC: valid = x.initialized && !x.ended && x.steps &&
      ((x.phase == Phase::Observed && x.observed != 0 && x.stepCode != Z_OK)
       || (x.phase == Phase::Reset &&
         ((x.stepCode != Z_OK && (x.kind == SC_DEFLATE || x.stepCode != Z_BUF_ERROR))
          || (x.limitRead && x.sizeRead && x.limit && x.observedSize >= x.limit)))); break;
    case SC_RAISE_INIT: valid = x.phase == Phase::Initialized && x.initCode != Z_OK && decode(arg) == x.initCode; break;
    case SC_RAISE_CODEC: valid = x.phase == Phase::Ended && x.stepCode != Z_STREAM_END && decode(arg) == x.stepCode; break;
    case SC_RAISE_LIMIT: valid = x.kind != SC_DEFLATE && x.phase == Phase::Ended && x.limitRead && x.sizeRead && x.limit && x.observedSize >= x.limit; break;
  }
  if (!valid) return SC_HOST_INVALID;
  x.callback = true;
  struct Reset { bool& b; ~Reset() { b = false; } } reset{x.callback};
  uint64_t result = 0;
  try {
    switch (op) {
      case SC_CLEAR_OUTPUT: x.output.clear(); x.phase = Phase::Cleared; break;
      case SC_INPUT_EMPTY: result = x.kind == SC_DEFLATE ? x.input->empty() : !x.length; x.phase = Phase::EmptyRead; break;
      case SC_ALLOCATE_TEMP: x.temp = std::make_unique<uint8_t[]>(Slab); x.phase = Phase::Allocated; break;
      case SC_ZERO_STREAM: x.stream = {}; x.stream.zalloc = Z_NULL; x.stream.zfree = Z_NULL; x.stream.opaque = Z_NULL; x.phase = Phase::Zeroed; break;
      case SC_INIT_CODEC:
        x.initCode = x.kind == SC_DEFLATE ? zng_deflateInit(&x.stream, x.level)
          : x.kind == SC_GZIP ? zng_inflateInit2(&x.stream, 31) : zng_inflateInit(&x.stream);
        x.stepCode = x.initCode; x.initialized = x.initCode == Z_OK;
        result = encode(x.initCode); x.phase = Phase::Initialized; break;
      case SC_BIND_INPUT:
        x.stream.next_in = reinterpret_cast<uint8_t const*>(x.kind == SC_DEFLATE ? x.input->ptr() : x.raw);
        x.stream.avail_in = x.kind == SC_DEFLATE ? x.input->size() : x.length;
        x.phase = Phase::Bound; break;
      case SC_RESET_OUTPUT: x.stream.next_out = x.temp.get(); x.stream.avail_out = Slab; x.phase = Phase::Reset; x.limitRead = x.sizeRead = false; break;
      case SC_STEP_FINISH: ++x.steps; x.stepCode = x.kind == SC_DEFLATE ? zng_deflate(&x.stream, Z_FINISH) : zng_inflate(&x.stream, Z_FINISH); result = encode(x.stepCode); x.phase = Phase::Stepped; break;
      case SC_AVAIL_OUT: result = x.observed = x.stream.avail_out; if (!x.ended) x.phase = Phase::Observed; else x.tailObserved = true; break;
      case SC_APPEND_TEMP:
        x.output.append(reinterpret_cast<char const*>(x.temp.get()), size_t(arg));
        x.phase = x.ended ? Phase::TailAppended : Phase::FullAppended; break;
      case SC_READ_LIMIT: result = x.limit; x.limitRead = true; break;
      case SC_OUTPUT_SIZE: result = x.observedSize = x.output.size(); x.sizeRead = true; break;
      case SC_END_CODEC: result = encode(x.kind == SC_DEFLATE ? zng_deflateEnd(&x.stream) : zng_inflateEnd(&x.stream)); x.ended = true; x.phase = Phase::Ended; break;
      case SC_RAISE_INIT: throw IOException(strf("Failed to initialise {} ({})", x.kind == SC_DEFLATE ? "deflate" : "inflate", x.initCode));
      case SC_RAISE_CODEC:
        if (x.kind == SC_DEFLATE) throw IOException(strf("Internal error in uncompressData, deflate_res is {}", x.stepCode));
        throw IOException(strf("Internal error in {}, inflate_res is {}", x.kind == SC_GZIP ? "uncompressDataGzip" : "uncompressData", x.stepCode));
      case SC_RAISE_LIMIT: throw IOException(strf("hit {} limit of {} bytes", x.kind == SC_GZIP ? "uncompressDataGzip" : "uncompressData", x.limit));
    }
    *scalar = result;
    return SC_OK;
  } catch (...) { x.pending = std::current_exception(); return SC_EXCEPTION; }
}

// Rethrow while temp ownership is live, matching the original unwind scope.
inline void run(NativeContext& x) {
  auto status = star_compression_run(x.kind, nativeHost, &x);
  if (status == SC_NATIVE_PENDING && x.pending)
    std::rethrow_exception(x.pending);
  if (status != SC_COMPLETE || x.pending)
    throw StarException("Invalid Rust compression controller result");
}
} // namespace Star::CompressionHost
