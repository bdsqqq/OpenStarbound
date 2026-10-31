#pragma once
#include "StarRustRpcPromise.h"
#include <exception>
#include <memory>
#include <stdexcept>
#include <type_traits>

namespace Star { namespace RpcPromiseDetail {

inline void invalidLeaf() { throw std::logic_error("Invalid RPC promise leaf"); }

// Borrow native closures; neither typed values nor lock ownership cross the ABI.
// The enclosing native MutexLocker remains alive during callbacks and rethrows.
template <typename Function>
SbNetGroupReply run(uint32_t mode, Function&& function) {
  using F = typename std::remove_reference<Function>::type;
  struct Frame {
    F* function;
    std::exception_ptr error;
    static uint32_t call(void* context, uint32_t leaf, uint64_t argument, SbNetGroupReply* out) noexcept {
      auto& frame = *static_cast<Frame*>(context);
      try {
        if (argument != 0) invalidLeaf();
        (*frame.function)(leaf, *out);
        return SB_RPC_PROMISE_OK;
      } catch (...) {
        frame.error = std::current_exception();
        return SB_RPC_PROMISE_HOST_ERROR;
      }
    }
  };
  Frame frame{std::addressof(function), {}};
  SbNetGroupReply result{};
  auto status = sb_rpc_promise_run(mode, &frame, Frame::call, 0, &result);
  if (frame.error) std::rethrow_exception(frame.error);
  bool boolean = mode >= SB_RPC_PROMISE_FINISHED && mode <= SB_RPC_PROMISE_ERROR_ROUTE;
  if (status != SB_RPC_PROMISE_OK || result.b != 0 || (boolean ? result.a > 1 : result.a != 0))
    throw std::logic_error("Invalid RPC promise controller result");
  return result;
}

template <typename Chain, typename Follow, typename Local>
bool query(uint32_t mode, Chain&& chain, Follow&& follow, Local&& local) {
  return run(mode, [&](uint32_t leaf, SbNetGroupReply& reply) {
    switch (leaf) {
      case SB_RPC_PROMISE_IS_CHAIN: reply.a = chain(); break;
      case SB_RPC_PROMISE_FOLLOW: reply.a = follow(); break;
      case SB_RPC_PROMISE_LOCAL: reply.a = local(); break;
      default: invalidLeaf();
    }
  }).a != 0;
}

template <typename Chain>
bool isChain(uint32_t mode, Chain&& chain) {
  return run(mode, [&](uint32_t leaf, SbNetGroupReply& reply) {
    if (leaf != SB_RPC_PROMISE_IS_CHAIN) invalidLeaf();
    reply.a = chain();
  }).a != 0;
}

template <typename Function>
void forward(bool& done, Function&& function) {
  run(SB_RPC_PROMISE_AUTO_CALL, [&](uint32_t leaf, SbNetGroupReply&) {
    switch (leaf) {
      case SB_RPC_PROMISE_SET_DONE: done = true; break;
      case SB_RPC_PROMISE_FORWARD: function(); break;
      default: invalidLeaf();
    }
  });
}

template <typename Function>
void drop(bool const& done, Function&& function) {
  run(SB_RPC_PROMISE_AUTO_DROP, [&](uint32_t leaf, SbNetGroupReply& reply) {
    switch (leaf) {
      case SB_RPC_PROMISE_AUTO_DONE: reply.a = done; break;
      case SB_RPC_PROMISE_FAIL_DESTROYED: function(); break;
      default: invalidLeaf();
    }
  });
}

}}
