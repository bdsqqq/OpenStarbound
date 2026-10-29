#pragma once

#include "StarRustStaticVector.h"

#include <cstddef>
#include <cstdint>
#include <exception>
#include <limits>
#include <stdexcept>
#include <utility>

namespace Star {
namespace StaticVectorFrames {

inline SbStaticVectorReply voidReply() noexcept {
  return {24, SB_STATIC_VECTOR_ABI_VERSION, SB_STATIC_VECTOR_VOID, 0, 0};
}
inline SbStaticVectorReply boolReply(bool value) noexcept {
  return {24, SB_STATIC_VECTOR_ABI_VERSION, SB_STATIC_VECTOR_BOOL, 0, value ? 1u : 0u};
}
inline SbStaticVectorReply sizeReply(size_t value) noexcept {
  return {24, SB_STATIC_VECTOR_ABI_VERSION, SB_STATIC_VECTOR_SIZE_VALUE, 0, value};
}
inline SbStaticVectorReply invalidReply() noexcept {
  return {24, SB_STATIC_VECTOR_ABI_VERSION, std::numeric_limits<uint32_t>::max(), 0, 0};
}
inline bool validReply(SbStaticVectorReply const& reply) noexcept {
  return reply.size == 24 && reply.version == SB_STATIC_VECTOR_ABI_VERSION && reply.reserved == 0
      && ((reply.tag == SB_STATIC_VECTOR_VOID && reply.value == 0)
          || (reply.tag == SB_STATIC_VECTOR_BOOL && reply.value <= 1)
          || (reply.tag == SB_STATIC_VECTOR_SIZE_VALUE && reply.value <= std::numeric_limits<size_t>::max()));
}
inline bool validRoute(uint32_t mode, uint32_t stage) noexcept {
  return mode < SB_STATIC_VECTOR_MODE_COUNT
      && (stage == SB_STATIC_VECTOR_ROOT || (mode == SB_STATIC_VECTOR_LESS && stage == SB_STATIC_VECTOR_CONTINUE));
}
inline uint32_t leafTag(uint32_t op) noexcept {
  if (op <= SB_STATIC_VECTOR_OTHER_SIZE || op == SB_STATIC_VECTOR_COMPARE_PAIR)
    return SB_STATIC_VECTOR_SIZE_VALUE;
  if (op == SB_STATIC_VECTOR_SELF || op == SB_STATIC_VECTOR_ITERATOR_PRESENT
      || op == SB_STATIC_VECTOR_ELEMENT_NOT_EQUAL || op == SB_STATIC_VECTOR_CALL_EQUAL
      || op == SB_STATIC_VECTOR_PAIR_LESS || op == SB_STATIC_VECTOR_PAIR_GREATER)
    return SB_STATIC_VECTOR_BOOL;
  return SB_STATIC_VECTOR_VOID;
}
inline bool validRequest(SbStaticVectorRequest const& request) noexcept {
  if (request.size != 32 || request.version != SB_STATIC_VECTOR_ABI_VERSION || request.reserved != 0
      || request.op < 1 || request.op > SB_STATIC_VECTOR_OP_COUNT
      || request.arg0 > std::numeric_limits<size_t>::max() || request.arg1 > std::numeric_limits<size_t>::max())
    return false;
  switch (request.op) {
    case SB_STATIC_VECTOR_MOVE_ASSIGN_SLOTS:
      return true;
    case SB_STATIC_VECTOR_CALL_ASSIGN:
    case SB_STATIC_VECTOR_ASSIGN_FROM_ITERATOR:
    case SB_STATIC_VECTOR_ASSIGN_FROM_ARGS:
    case SB_STATIC_VECTOR_ELEMENT_NOT_EQUAL:
    case SB_STATIC_VECTOR_COMPARE_PAIR:
      return request.arg1 == 0;
    default:
      return request.arg0 == 0 && request.arg1 == 0;
  }
}

// The closure owns only native references, never an Element value. Each method
// exposes its own effects so unrelated Element requirements remain lazy.
template <typename F>
struct Frame {
  explicit Frame(F effect) : effect(std::move(effect)) {}
  Frame(Frame const&) = delete;
  Frame(Frame&&) = delete;
  Frame& operator=(Frame const&) = delete;
  Frame& operator=(Frame&&) = delete;

  static uint32_t host(void* context, SbStaticVectorRequest const* request, SbStaticVectorReply* output) noexcept {
    // Pointer provenance/liveness is the synchronous caller's precondition.
    if (!context || reinterpret_cast<uintptr_t>(context) % alignof(Frame) != 0)
      return SB_STATIC_VECTOR_INVALID;
    return static_cast<Frame*>(context)->dispatch(request, output);
  }

  uint32_t dispatch(SbStaticVectorRequest const* request, SbStaticVectorReply* output) noexcept {
    if (!request || !output
        || reinterpret_cast<uintptr_t>(request) % alignof(SbStaticVectorRequest) != 0
        || reinterpret_cast<uintptr_t>(output) % alignof(SbStaticVectorReply) != 0)
      return SB_STATIC_VECTOR_INVALID;
    auto const req = *request;
    if (!validRequest(req))
      return SB_STATIC_VECTOR_INVALID;
    if (exception)
      return SB_STATIC_VECTOR_EXCEPTION;
    try {
      auto reply = effect(req);
      if (!validReply(reply) || reply.tag != leafTag(req.op)
          || (req.op == SB_STATIC_VECTOR_COMPARE_PAIR && reply.value > 2)
          || req.op == SB_STATIC_VECTOR_THROW_RESIZE || req.op == SB_STATIC_VECTOR_THROW_AT
          || req.op == SB_STATIC_VECTOR_THROW_POP || req.op == SB_STATIC_VECTOR_THROW_EMPLACE_BACK)
        return SB_STATIC_VECTOR_INVALID;
      // Rust deliberately poisons this WRITE-ONLY destination before every call.
      *output = reply;
      return SB_STATIC_VECTOR_OK;
    } catch (...) {
      exception = std::current_exception();
      return SB_STATIC_VECTOR_EXCEPTION;
    }
  }

  SbStaticVectorReply run(uint32_t mode, uint32_t stage = SB_STATIC_VECTOR_ROOT) {
    if (!validRoute(mode, stage))
      throw std::logic_error("Invalid StaticVector boundary protocol");
    auto reply = voidReply();
    auto status = sb_static_vector_run(mode, stage, this, &Frame::host, &reply);
    // Includes throws from nested ported calls: all Rust invocations have now
    // returned before C++ unwinds native locals or a delegating constructor.
    if (exception)
      std::rethrow_exception(exception);
    uint32_t expected = SB_STATIC_VECTOR_VOID;
    if (stage == SB_STATIC_VECTOR_CONTINUE || mode == SB_STATIC_VECTOR_SIZE)
      expected = SB_STATIC_VECTOR_SIZE_VALUE;
    else if (mode == SB_STATIC_VECTOR_EMPTY || mode == SB_STATIC_VECTOR_EQUAL
        || mode == SB_STATIC_VECTOR_NOT_EQUAL || mode == SB_STATIC_VECTOR_LESS)
      expected = SB_STATIC_VECTOR_BOOL;
    if (status != SB_STATIC_VECTOR_OK || !validReply(reply) || reply.tag != expected
        || (stage == SB_STATIC_VECTOR_CONTINUE && reply.value > 2))
      throw std::logic_error("Invalid StaticVector boundary protocol");
    return reply;
  }

  F effect;
  std::exception_ptr exception;
};

template <typename F>
auto makeFrame(F effect) {
  return Frame<F>(std::move(effect));
}

} // namespace StaticVectorFrames
} // namespace Star
