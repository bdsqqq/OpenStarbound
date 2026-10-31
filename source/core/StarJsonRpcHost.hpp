#pragma once
#include "StarRustJsonRpc.h"
#include <exception>
#include <memory>
#include <stdexcept>
#include <type_traits>

namespace Star { namespace JsonRpcDetail {

inline void invalidLeaf() { throw std::logic_error("Invalid JSON-RPC leaf"); }

// The frame borrows the native closure, never std::function-materializes it.
// Native outer try/catch scopes regain the ORIGINAL exception after Rust exits.
template <typename Function>
SbNetGroupReply run(uint32_t mode, Function&& function, uint64_t argument = 0) {
  using F = typename std::remove_reference<Function>::type;
  struct Frame {
    F* function;
    std::exception_ptr error;
    static uint32_t call(void* context, uint32_t leaf, uint64_t value, SbNetGroupReply* out) noexcept {
      auto& frame = *static_cast<Frame*>(context);
      try {
        (*frame.function)(leaf, value, *out);
        return SB_JSON_RPC_OK;
      } catch (...) {
        frame.error = std::current_exception();
        return SB_JSON_RPC_HOST_ERROR;
      }
    }
  };
  Frame frame{std::addressof(function), {}};
  SbNetGroupReply result{};
  auto status = sb_json_rpc_run(mode, &frame, Frame::call, argument, &result);
  if (frame.error)
    std::rethrow_exception(frame.error);
  bool boolean = mode == SB_JSON_RPC_PENDING || mode == SB_JSON_RPC_SEND || mode == SB_JSON_RPC_RECEIVE;
  if (status != SB_JSON_RPC_OK || result.b != 0 ||
      (boolean ? result.a > 1 : mode != SB_JSON_RPC_INVOKE && result.a != 0))
    throw std::logic_error("Invalid JSON-RPC controller result");
  return result;
}

}}
