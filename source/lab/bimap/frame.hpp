#pragma once

// LAB ONLY: scalar core adapter. No production dispatch or Element ownership.
#include "StarRustBiMap.h"
#include <cstddef>
#include <cstdint>
#include <exception>
#include <limits>
#include <stdexcept>
#include <utility>

namespace Star {
namespace BiMapFrames {
static_assert(sizeof(SbBiMapRequest) == 32 && sizeof(SbBiMapReply) == 24, "BiMap ABI layout");
static_assert(offsetof(SbBiMapRequest, arg0) == 16 && offsetof(SbBiMapReply, value) == 16, "BiMap ABI offsets");
static_assert(SB_BIMAP_ABI_VERSION == 1 && SB_BIMAP_MODE_COUNT == 19 && SB_BIMAP_OP_COUNT == 32,
    "requires additive scoped-equality policy extension");

inline SbBiMapReply voidReply() noexcept { return {24, 1, SB_BIMAP_VOID, 0, 0}; }
inline SbBiMapReply boolReply(bool value) noexcept { return {24, 1, SB_BIMAP_BOOL, 0, value ? 1u : 0u}; }
inline SbBiMapReply sizeReply(size_t value) noexcept { return {24, 1, SB_BIMAP_SIZE_VALUE, 0, value}; }
inline SbBiMapReply invalidReply() noexcept { return {24, 1, std::numeric_limits<uint32_t>::max(), 0, 0}; }
inline bool validReply(SbBiMapReply const& reply) noexcept {
  return reply.size == 24 && reply.version == 1 && reply.reserved == 0
      && ((reply.tag == SB_BIMAP_VOID && reply.value == 0)
          || (reply.tag == SB_BIMAP_BOOL && reply.value <= 1)
          || (reply.tag == SB_BIMAP_SIZE_VALUE && reply.value <= std::numeric_limits<size_t>::max()));
}
inline uint32_t leafTag(uint32_t op) noexcept {
  if (op == 1 || op == 24) return SB_BIMAP_SIZE_VALUE;
  switch (op) {
    case 2: case 3: case 4: case 10: case 11: case 16: case 18:
    case 21: case 23: case 25: case 26: case 27: case 28: case 32:
      return SB_BIMAP_BOOL;
    default: return SB_BIMAP_VOID;
  }
}
inline uint32_t modeTag(uint32_t mode) noexcept {
  if (mode == 0) return SB_BIMAP_SIZE_VALUE;
  switch (mode) {
    case 1: case 2: case 3: case 6: case 7: case 12: case 13: case 16: case 17: case 18:
      return SB_BIMAP_BOOL;
    default: return SB_BIMAP_VOID;
  }
}
inline bool validRequest(SbBiMapRequest const& req) noexcept {
  return req.size == 32 && req.version == 1 && req.reserved == 0
      && req.op >= 1 && req.op <= 32 && req.arg0 == 0 && req.arg1 == 0;
}

// Effects capture references/scalars only. Native iterators, insertion results,
// named pair temporaries and exception objects live in their original scopes.
template <typename F>
struct Frame {
  explicit Frame(F effect) : effect(std::move(effect)) {}
  Frame(Frame const&) = delete;
  Frame(Frame&&) = delete;
  Frame& operator=(Frame const&) = delete;
  Frame& operator=(Frame&&) = delete;

  static uint32_t host(void* context, SbBiMapRequest const* request, SbBiMapReply* output) noexcept {
    // Alignment checks cannot establish pointer provenance: synchronous caller
    // supplies live context/envelopes and must not retain their addresses.
    if (!context || reinterpret_cast<uintptr_t>(context) % alignof(Frame) != 0)
      return SB_BIMAP_INVALID;
    return static_cast<Frame*>(context)->dispatch(request, output);
  }
  uint32_t dispatch(SbBiMapRequest const* request, SbBiMapReply* output) noexcept {
    if (!request || !output
        || reinterpret_cast<uintptr_t>(request) % alignof(SbBiMapRequest) != 0
        || reinterpret_cast<uintptr_t>(output) % alignof(SbBiMapReply) != 0)
      return SB_BIMAP_INVALID;
    auto const req = *request;
    if (!validRequest(req)) return SB_BIMAP_INVALID;
    if (exception) return SB_BIMAP_EXCEPTION;
    try {
      auto reply = effect(req);
      if (!validReply(reply) || reply.tag != leafTag(req.op)
          || req.op == 5 || req.op == 6 || req.op == 22)
        return SB_BIMAP_INVALID;
      // WRITE-ONLY destination: Rust poisons it before calling the host.
      *output = reply;
      return SB_BIMAP_OK;
    } catch (...) {
      exception = std::current_exception();
      return SB_BIMAP_EXCEPTION;
    }
  }
  SbBiMapReply run(uint32_t mode) {
    if (mode >= 19) throw std::logic_error("Invalid BiMap boundary protocol");
    auto reply = voidReply();
    auto status = sb_bimap_run(mode, this, &Frame::host, &reply);
    // Nested calls rethrow into the enclosing host catch, never through Rust.
    if (exception) std::rethrow_exception(exception);
    if (status != SB_BIMAP_OK || !validReply(reply) || reply.tag != modeTag(mode))
      throw std::logic_error("Invalid BiMap boundary protocol");
    return reply;
  }
  F effect;
  std::exception_ptr exception;
};
template <typename F>
auto makeFrame(F effect) { return Frame<F>(std::move(effect)); }
} // namespace BiMapFrames
} // namespace Star
