#pragma once
#include "StarRustNetGroup.h"
#include <exception>
#include <optional>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace Star { namespace NetGroupDetail {
// Capture typed failures while their native expressions unwind, then rethrow
// only after the Rust controller has returned. Never unwind C++ through Rust.
template <typename Function>
bool run(uint32_t mode, uint64_t fromVersion, Function&& function,
    uint32_t (*entry)(uint32_t, void*, SbNetGroupHost, uint64_t, uint32_t*) = sb_net_group_run) {
  using F = typename std::remove_reference<Function>::type;
  struct Frame {
    F& function;
    std::exception_ptr error;
    static uint32_t call(void* context, uint32_t leaf, uint64_t argument, SbNetGroupReply* reply) noexcept {
      auto& frame = *static_cast<Frame*>(context);
      try {
        frame.function(leaf, argument, *reply);
        return SB_NET_GROUP_OK;
      } catch (...) {
        frame.error = std::current_exception();
        return SB_NET_GROUP_HOST_ERROR;
      }
    }
  } frame{function, {}};
  uint32_t written = 0;
  auto status = entry(mode, &frame, &Frame::call, fromVersion, &written);
  if (frame.error)
    std::rethrow_exception(frame.error);
  if (status != SB_NET_GROUP_OK || written > 1)
    throw std::logic_error("NetElementGroup Rust controller protocol failure");
  return written != 0;
}
// Iterator scope follows the native range-for, including early successful exits.
// Error cleanup belongs to this C++ owner, not a compensating Rust callback.
template <typename Container, typename Function>
bool withRange(uint32_t mode, uint64_t argument, Container& elements, Function&& function,
    uint32_t (*entry)(uint32_t, void*, SbNetGroupHost, uint64_t, uint32_t*) = sb_net_group_run) {
  using Iterator = decltype(elements.begin());
  std::optional<std::pair<Iterator, Iterator>> range;
  auto current = [&]() -> decltype(auto) { return *range->first; };
  return run(mode, argument, [&](uint32_t leaf, uint64_t value, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_NET_GROUP_ENTER_RANGE: {
      auto begin = elements.begin();
      auto end = elements.end();
      range.emplace(begin, end);
      break;
    }
    case SB_NET_GROUP_MORE: reply.a = range->first != range->second; break;
    case SB_NET_GROUP_ADVANCE: ++range->first; break;
    case SB_NET_GROUP_LEAVE_RANGE: range.reset(); break;
    default: function(leaf, value, current, reply); break;
    }
  }, entry);
}
} }
