#pragma once

#include "StarRustIdMap.h"

#include <exception>
#include <limits>
#include <stdexcept>
#include <type_traits>

namespace Star {
namespace RustIdMapDetail {

inline SbIdMapReply voidReply() noexcept {
  return {24, SB_IDMAP_ABI_VERSION, SB_IDMAP_VOID, 0, 0};
}

inline SbIdMapReply boolReply(bool value) noexcept {
  return {24, SB_IDMAP_ABI_VERSION, SB_IDMAP_BOOL, 0, value ? 1u : 0u};
}

inline bool validReply(SbIdMapReply const& reply) noexcept {
  return reply.size == 24 && reply.version == SB_IDMAP_ABI_VERSION && reply.reserved == 0
      && ((reply.tag == SB_IDMAP_VOID && reply.value == 0)
          || (reply.tag == SB_IDMAP_BOOL && reply.value <= 1));
}

inline bool validRoute(uint32_t mode, uint32_t stage) noexcept {
  return mode < SB_IDMAP_MODE_COUNT && (stage == SB_IDMAP_ROOT
      || (stage == SB_IDMAP_CONTINUE && (mode == SB_IDMAP_NEXT || mode == SB_IDMAP_ADD_AUTO)));
}

inline bool booleanLeaf(uint32_t op) noexcept {
  return op == SB_IDMAP_FULL || op == SB_IDMAP_CURSOR_CONTAINS
      || op == SB_IDMAP_EXPLICIT_INSERT || op == SB_IDMAP_SAME_BOUNDS
      || op == SB_IDMAP_BASE_EQUAL || op == SB_IDMAP_CALL_EQUAL;
}

// Only this non-templated frame crosses the ABI. The payload points explicitly
// to inline closure storage; no derived/base address equivalence is assumed.
struct Frame {
  using Allowed = bool (*)(void*, uint32_t);
  using Leaf = SbIdMapReply (*)(void*, uint32_t);
  using Complete = bool (*)(void*);

  Frame(uint32_t mode, uint32_t stage, void* payload, Allowed allowed, Leaf leaf, Complete complete)
    : mode(mode), stage(stage), payload(payload), allowed(allowed), leaf(leaf), complete(complete) {}

  Frame(Frame const&) = delete;
  Frame(Frame&&) = delete;
  Frame& operator=(Frame const&) = delete;
  Frame& operator=(Frame&&) = delete;

  static uint32_t host(void* context, SbIdMapRequest const* request, SbIdMapReply* output) noexcept {
    if (!context)
      return SB_IDMAP_INVALID;
    auto& frame = *static_cast<Frame*>(context);
    if (!validRoute(frame.mode, frame.stage) || !frame.allowed || !frame.leaf || !frame.complete)
      return SB_IDMAP_INVALID;
    // Once a native expression throws, even a malicious controller cannot
    // perform another native expression before the original exception escapes.
    if (frame.exception)
      return SB_IDMAP_EXCEPTION;
    if (!request || !output)
      return SB_IDMAP_INVALID;
    if (request->size != 24 || request->version != SB_IDMAP_ABI_VERSION
        || request->reserved != 0 || request->op < 1 || request->op > SB_IDMAP_OP_COUNT
        || request->arg != 0)
      return SB_IDMAP_INVALID;
    bool destination = output->size == 24 && output->version == SB_IDMAP_ABI_VERSION
        && output->reserved == 0
        && ((output->tag == SB_IDMAP_VOID && output->value == 0)
            || (output->tag == std::numeric_limits<uint32_t>::max()
                && output->value == std::numeric_limits<uint64_t>::max()));
    if (!destination)
      return SB_IDMAP_INVALID;
    try {
      if (!frame.allowed(frame.payload, request->op))
        return SB_IDMAP_INVALID;
      auto reply = frame.leaf(frame.payload, request->op);
      auto expected = booleanLeaf(request->op) ? SB_IDMAP_BOOL : SB_IDMAP_VOID;
      if (!validReply(reply) || reply.tag != static_cast<uint32_t>(expected)
          || request->op == SB_IDMAP_THROW_FULL || request->op == SB_IDMAP_THROW_DUPLICATE)
        return SB_IDMAP_INVALID;
      *output = reply;
      return SB_IDMAP_OK;
    } catch (...) {
      if (!frame.exception)
        frame.exception = std::current_exception();
      return SB_IDMAP_EXCEPTION;
    }
  }

  SbIdMapReply run() {
    if (!validRoute(mode, stage) || !allowed || !leaf || !complete)
      throw std::runtime_error("Invalid IdMap boundary protocol");
    auto reply = voidReply();
    auto status = sb_idmap_run(mode, stage, static_cast<Frame*>(this), &Frame::host, &reply);
    // This rethrow is outside Rust, and takes precedence over any forged status.
    if (exception)
      std::rethrow_exception(exception);
    bool route = validRoute(mode, stage);
    auto expected = stage == SB_IDMAP_ROOT
        && (mode == SB_IDMAP_EQUAL || mode == SB_IDMAP_NOT_EQUAL) ? SB_IDMAP_BOOL : SB_IDMAP_VOID;
    if (status != SB_IDMAP_OK || !route || !validReply(reply)
        || reply.tag != static_cast<uint32_t>(expected) || !complete(payload))
      throw std::runtime_error("Invalid IdMap boundary protocol");
    return reply;
  }

  uint32_t const mode;
  uint32_t const stage;
  void* const payload;
  Allowed const allowed;
  Leaf const leaf;
  Complete const complete;
  std::exception_ptr exception;
};

// Distinct names matter: the nondependent base's callback aliases otherwise
// hide template parameters inside this class, silently replacing closure types.
template <typename A, typename L, typename C>
struct InlineFrame final : Frame {
  static_assert(std::is_trivially_copyable<A>::value, "allowed closure must be trivial");
  static_assert(std::is_trivially_copyable<L>::value, "leaf closure must be trivial");
  static_assert(std::is_trivially_copyable<C>::value, "completion closure must be trivial");

  InlineFrame(uint32_t mode, uint32_t stage, A allowed, L leaf, C complete)
    : Frame(mode, stage, this,
        [](void* p, uint32_t op) { return static_cast<InlineFrame*>(p)->allowedClosure(op); },
        [](void* p, uint32_t op) { return static_cast<InlineFrame*>(p)->leafClosure(op); },
        [](void* p) { return static_cast<InlineFrame*>(p)->completeClosure(); }),
      allowedClosure(allowed), leafClosure(leaf), completeClosure(complete) {}

  A allowedClosure;
  L leafClosure;
  C completeClosure;
};

template <typename Allowed, typename Leaf, typename Complete>
auto makeFrame(uint32_t mode, uint32_t stage, Allowed allowed, Leaf leaf, Complete complete) {
  // A prvalue is essential: the immovable frame's payload is bound to itself.
  return InlineFrame<Allowed, Leaf, Complete>(mode, stage, allowed, leaf, complete);
}

} // namespace RustIdMapDetail
} // namespace Star
