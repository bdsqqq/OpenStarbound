#pragma once
#include "StarRustNetSignal.h"
#include <exception>
#include <optional>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace Star { namespace NetSignalDetail {
// Capture typed failures while their native expressions unwind, then rethrow
// only after the Rust controller has returned. Never unwind C++ through Rust.
template <typename Function>
bool run(uint32_t mode, uint64_t fromVersion, Function&& function) {
  using F = typename std::remove_reference<Function>::type;
  struct Frame {
    F& function;
    std::exception_ptr error;
    static uint32_t call(void* context, uint32_t leaf, uint64_t argument, SbNetSignalReply* reply) noexcept {
      auto& frame = *static_cast<Frame*>(context);
      try {
        frame.function(leaf, argument, *reply);
        return SB_NET_SIGNAL_OK;
      } catch (...) {
        frame.error = std::current_exception();
        return SB_NET_SIGNAL_HOST_ERROR;
      }
    }
  } frame{function, {}};
  uint32_t written = 0;
  auto status = sb_net_signal_run(mode, &frame, &Frame::call, fromVersion, &written);
  if (frame.error)
    std::rethrow_exception(frame.error);
  if (status != SB_NET_SIGNAL_OK || written > 1)
    throw std::logic_error("NetElementSignal Rust controller protocol failure");
  return written != 0;
}
} }
