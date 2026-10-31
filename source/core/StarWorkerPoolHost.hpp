#pragma once

#include <exception>
#include <stdexcept>
#include <type_traits>

#include "StarRustWorkerPool.h"

namespace Star {
namespace WorkerPoolDetail {

// Leaves borrow their native callable: no function copy or allocation crosses
// the ABI, and even non-std exceptions return through Rust as a status first.
template <typename Function>
struct FunctionFrame {
  Function& function;
  std::exception_ptr exception;

  static uint32_t dispatch(void* context, uint32_t operation, uint32_t* response) noexcept {
    auto& frame = *static_cast<FunctionFrame*>(context);
    if (frame.exception)
      return SB_WORKER_POOL_HOST_ERROR;
    try {
      if (!response)
        throw std::logic_error("WorkerPool null leaf response");
      *response = frame.function(operation);
      return SB_WORKER_POOL_OK;
    } catch (...) {
      frame.exception = std::current_exception();
      return SB_WORKER_POOL_HOST_ERROR;
    }
  }
};

template <typename Function>
uint32_t run(uint32_t mode, Function&& function) {
  FunctionFrame<typename std::remove_reference<Function>::type> frame{function, {}};
  uint32_t result = 0;
  auto status = sb_worker_pool_run(mode, &frame, &decltype(frame)::dispatch, &result);
  if (frame.exception)
    std::rethrow_exception(frame.exception);
  if (status != SB_WORKER_POOL_OK)
    throw std::logic_error("WorkerPool Rust protocol failure");
  return result;
}

[[noreturn]] inline void invalidOperation() {
  throw std::logic_error("WorkerPool unexpected operation");
}

}
}
