#pragma once

#include <cstddef>
#include <exception>
#include <memory>
#include <stdexcept>
#include <type_traits>
#include <utility>

#include "StarRustOrderedSet.h"

namespace Star {
namespace OrderedSetDetail {

// Keep the callable and its iterator references on the native stack. In
// particular, an exception's original object must survive the Rust round trip.
template <typename Function>
struct Frame {
  Function& function;
  std::exception_ptr exception;

  static uint32_t dispatch(void* context, uint32_t operation, uint32_t* response) noexcept {
    auto& frame = *static_cast<Frame*>(context);
    if (frame.exception)
      return SB_ORDERED_SET_HOST_ERROR;
    try {
      if (!response)
        throw std::logic_error("OrderedSet null leaf response");
      *response = frame.function(operation);
      return SB_ORDERED_SET_OK;
    } catch (...) {
      frame.exception = std::current_exception();
      return SB_ORDERED_SET_HOST_ERROR;
    }
  }
};

template <typename Function>
void run(uint32_t mode, Function&& function) {
  Frame<typename std::remove_reference<Function>::type> frame{function, {}};
  auto status = sb_ordered_set_run(mode, &frame, &decltype(frame)::dispatch);
  if (frame.exception)
    std::rethrow_exception(frame.exception);
  if (status != SB_ORDERED_SET_OK)
    throw std::logic_error("OrderedSet Rust protocol failure");
}

[[noreturn]] inline void invalidOperation() {
  throw std::logic_error("OrderedSet unexpected leaf operation");
}

inline uint32_t selectAction(uint32_t mode, bool predicate) {
  uint32_t action = 0;
  auto status = sb_ordered_set_select(mode, predicate ? 1u : 0u, &action);
  if (status != SB_ORDERED_SET_OK)
    throw std::logic_error("OrderedSet Rust selection protocol failure");
  return action;
}

template <typename Thrower>
void requireNonEmpty(bool empty, Thrower&& thrower) {
  switch (selectAction(SB_ORDERED_SET_SELECT_NONEMPTY, empty)) {
    case SB_ORDERED_SET_ACTION_CONTINUE: return;
    case SB_ORDERED_SET_ACTION_THROW: thrower(); break;
    default: invalidOperation();
  }
  invalidOperation();
}

template <typename Range, typename = void>
struct HasMemberRange : std::false_type {};

template <typename Range>
struct HasMemberRange<Range, std::void_t<
    decltype(std::declval<Range&>().begin()),
    decltype(std::declval<Range&>().end())>> : std::true_type {};

namespace AdlRange {
// Stop ordinary lookup here: std::begin would incorrectly prefer a lone member
// begin() over a valid ADL pair. Built-in arrays are handled separately below.
void begin() = delete;
void end() = delete;

template <typename Range>
auto first(Range& range) -> decltype(begin(range)) {
  return begin(range);
}

template <typename Range>
auto last(Range& range) -> decltype(end(range)) {
  return end(range);
}
}

template <typename Range, typename Function>
void withRange(Range& range, Function&& function) {
  if constexpr (std::is_array<Range>::value) {
    auto iterator = range + 0;
    auto end = range + std::extent<Range>::value;
    function(iterator, end);
  } else if constexpr (HasMemberRange<Range>::value) {
    auto iterator = range.begin();
    auto end = range.end();
    function(iterator, end);
  } else {
    auto iterator = AdlRange::first(range);
    auto end = AdlRange::last(range);
    function(iterator, end);
  }
}

}
}
