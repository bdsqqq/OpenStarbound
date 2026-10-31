#pragma once

#include <exception>
#include <stdexcept>
#include <type_traits>

#include "StarRustFlatHashTable.h"

namespace Star {
namespace FlatHashTableDetail {

[[noreturn]] inline void invalidOperation() {
  throw std::logic_error("FlatHashTable unexpected Rust operation or reply");
}

// The callable remains native and borrowed; retain the original exception object
// until Rust returns so no C++ unwind crosses the C ABI.
template <typename Function>
struct Frame {
  Function& function;
  std::exception_ptr exception;

  static uint32_t dispatch(void* context, uint32_t operation, size_t argument, size_t* response) noexcept {
    auto& frame = *static_cast<Frame*>(context);
    if (frame.exception)
      return SB_FLAT_HASH_HOST_ERROR;
    try {
      if (!response)
        invalidOperation();
      *response = frame.function(operation, argument);
      return SB_FLAT_HASH_OK;
    } catch (...) {
      frame.exception = std::current_exception();
      return SB_FLAT_HASH_HOST_ERROR;
    }
  }
};

template <typename Function>
SbFlatHashReply run(uint32_t mode, Function&& function) {
  Frame<typename std::remove_reference<Function>::type> frame{function, {}};
  SbFlatHashReply reply{0, 0};
  auto status = sb_flat_hash_run(mode, &frame, &decltype(frame)::dispatch, &reply);
  if (frame.exception)
    std::rethrow_exception(frame.exception);
  if (status != SB_FLAT_HASH_OK)
    throw std::logic_error("FlatHashTable Rust protocol failure");
  return reply;
}

template <typename Bucket>
Bucket* scan(Bucket* p) {
  run(SB_FLAT_HASH_SCAN, [&](uint32_t operation, size_t) -> size_t {
    switch (operation) {
      case SB_FLAT_HASH_SCAN_EMPTY: return p->isEmpty() ? 1 : 0;
      case SB_FLAT_HASH_SCAN_ADVANCE: ++p; return 0;
      default: invalidOperation();
    }
  });
  return p;
}

}
}
