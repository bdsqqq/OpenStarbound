#pragma once

#include <exception>
#include <stdexcept>
#include <type_traits>

#include "StarRustMap.h"
#include "StarSetHost.hpp"

namespace Star {
namespace MapDetail {

// Taking this specialization's address forces the compiler to check the exact
// range-for domain without executing it. A callable-only begin/end detector
// alone would wrongly accept noncallable member names through an ADL fallback.
template <typename Range>
void requireNativeRange(Range& range) {
  for (auto const& item : range) { (void)item; }
}

template <typename Range, typename Function>
void withNativeRange(Range& range, Function&& function) {
  (void)&requireNativeRange<Range>;
  SetDetail::withRange(range, std::forward<Function>(function));
}

// Reference-held leaves preserve native iterator scopes and exception identity.
template <typename Function>
struct Frame {
  Function& function;
  std::exception_ptr exception;

  static uint32_t dispatch(void* context, uint32_t operation, uint32_t* response) noexcept {
    auto& frame = *static_cast<Frame*>(context);
    if (frame.exception)
      return SB_MAP_HOST_ERROR;
    try {
      if (!response)
        throw std::logic_error("Map null leaf response");
      *response = frame.function(operation);
      return SB_MAP_OK;
    } catch (...) {
      frame.exception = std::current_exception();
      return SB_MAP_HOST_ERROR;
    }
  }
};

template <typename Function>
uint32_t run(uint32_t mode, Function&& function) {
  Frame<typename std::remove_reference<Function>::type> frame{function, {}};
  uint32_t result = 0;
  auto status = sb_map_run(mode, &frame, &decltype(frame)::dispatch, &result);
  if (frame.exception)
    std::rethrow_exception(frame.exception);
  if (status != SB_MAP_OK)
    throw std::logic_error("Map Rust protocol failure");
  return result;
}

[[noreturn]] inline void invalidOperation() {
  throw std::logic_error("Map unexpected operation");
}

// Callers finish comparison full expressions before entry: native end/proxy
// temporaries must not remain alive across even this callback-free selection.
inline uint32_t selectAction(uint32_t mode, bool predicate) {
  uint32_t action = 0;
  auto status = sb_map_select(mode, predicate ? 1u : 0u, &action);
  if (status != SB_MAP_OK)
    throw std::logic_error("Map Rust selection protocol failure");
  return action;
}

}
}
