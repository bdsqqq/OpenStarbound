#pragma once

#include "StarNetElement.hpp"
#include <memory>
#include <type_traits>
#include <vector>

// Growth is allocator/standard-library behavior, not a portable vector promise.
// Keep other configurations native until their allocation contract is traced.
#if defined(STAR_USE_RUST_NET_GROUP) && defined(__APPLE__) && _LIBCPP_VERSION == 220106
#define STAR_NET_GROUP_RUST_STORAGE 1
#include "StarRustNetGroupStorage.h"
#include <exception>
#include <stdexcept>

namespace Star {

// Rust owns the buffer address/length/capacity and its mutation ordering. Native
// pair objects and allocator calls stay here so borrows and exceptions stay C++.
class NetGroupSlots {
public:
  using value_type = pair<NetElement*, bool>;
  NetGroupSlots() = default;
  NetGroupSlots(NetGroupSlots const&) = delete;
  NetGroupSlots& operator=(NetGroupSlots const&) = delete;
  NetGroupSlots(NetGroupSlots&&) = delete;
  NetGroupSlots& operator=(NetGroupSlots&&) = delete;

  ~NetGroupSlots() noexcept {
    try {
      execute(SB_NET_GROUP_STORAGE_DROP, nullptr);
    } catch (...) {
      std::terminate();
    }
  }

  // ListMixin::append also takes a named value, then moves that exact value into
  // the vector. Keep it alive through all nested callbacks and return unwinding.
  void append(value_type value) { execute(SB_NET_GROUP_STORAGE_APPEND, &value); }
  void clear() { execute(SB_NET_GROUP_STORAGE_CLEAR, nullptr); }
  size_t size() const { return query(SB_NET_GROUP_STORAGE_SIZE); }
  size_t capacity() const { return query(SB_NET_GROUP_STORAGE_CAPACITY); }
  value_type* data() { return reinterpret_cast<value_type*>(query(SB_NET_GROUP_STORAGE_DATA)); }
  value_type const* data() const { return reinterpret_cast<value_type const*>(query(SB_NET_GROUP_STORAGE_DATA)); }
  value_type* begin() { return data(); }
  value_type const* begin() const { return data(); }
  value_type* end() { auto p = data(); return p ? p + size() : p; }
  value_type const* end() const { auto p = data(); return p ? p + size() : p; }
  value_type& operator[](size_t index) { starAssert(index < size()); return data()[index]; }
  value_type const& operator[](size_t index) const { starAssert(index < size()); return data()[index]; }
  bool contains(NetElement const* element) const {
    return execute(SB_NET_GROUP_STORAGE_CONTAINS, nullptr, reinterpret_cast<uintptr_t>(element)) != 0;
  }

private:
  using Allocator = std::allocator<value_type>;
  using Traits = std::allocator_traits<Allocator>;
  static_assert(std::is_nothrow_move_constructible<value_type>::value, "pair relocation must not throw");
  static_assert(std::is_trivially_destructible<value_type>::value, "no observable pair destructor");
  struct Frame {
    value_type* value;
    Allocator allocator;
    std::exception_ptr error;
  };
  static Frame& frame(void* context) noexcept { return *static_cast<Frame*>(context); }
  static value_type* pairs(uintptr_t address) noexcept { return reinterpret_cast<value_type*>(address); }
  static uintptr_t maximum(void*) noexcept { return std::vector<value_type>().max_size(); }
  static uint32_t allocate(void* context, uintptr_t count, uintptr_t* out) noexcept {
    auto& f = frame(context);
    try {
      auto result = Traits::allocate(f.allocator, count);
      *out = reinterpret_cast<uintptr_t>(result);
      return SB_NET_GROUP_STORAGE_OK;
    } catch (...) {
      f.error = std::current_exception();
      return SB_NET_GROUP_STORAGE_HOST;
    }
  }
  static void construct(void* context, uintptr_t address, uintptr_t index) noexcept {
    auto& f = frame(context);
    Traits::construct(f.allocator, pairs(address) + index, std::move(*f.value));
  }
  static void move(void* context, uintptr_t oldAddress, uintptr_t newAddress, uintptr_t index) noexcept {
    auto& f = frame(context);
    Traits::construct(f.allocator, pairs(newAddress) + index, std::move(pairs(oldAddress)[index]));
  }
  static void destroy(void* context, uintptr_t address, uintptr_t index) noexcept {
    Traits::destroy(frame(context).allocator, pairs(address) + index);
  }
  static void deallocate(void* context, uintptr_t address, uintptr_t count) noexcept {
    Traits::deallocate(frame(context).allocator, pairs(address), count);
  }
  static uintptr_t element(void*, uintptr_t address, uintptr_t index) noexcept {
    return reinterpret_cast<uintptr_t>(pairs(address)[index].first);
  }
  static uint32_t lengthError(void* context) noexcept {
    try {
      // Ask this native library to throw its own length_error, not a translated
      // Rust allocation error or a copied implementation-dependent message.
      std::vector<value_type> probe;
      probe.reserve(probe.max_size() + 1);
      std::terminate();
    } catch (...) {
      frame(context).error = std::current_exception();
      return SB_NET_GROUP_STORAGE_HOST;
    }
  }
  uintptr_t query(uint32_t mode) const {
    uintptr_t result = 0;
    if (sb_net_group_storage_run(mode, &m_state, nullptr, 0, &result) != SB_NET_GROUP_STORAGE_OK)
      throw std::logic_error("Invalid network group storage query");
    return result;
  }
  uintptr_t execute(uint32_t mode, value_type* value, uintptr_t argument = 0) const {
    Frame f{value, {}, {}};
    SbNetGroupStorageOps ops{&f, maximum, allocate, construct, move, destroy, deallocate, element, lengthError};
    uintptr_t result = 0;
    auto status = sb_net_group_storage_run(mode, &m_state, &ops, argument, &result);
    // Allocation/length exceptions are rethrown only after the Rust call ends.
    // An outer group callback may catch this same object at its own boundary.
    if (f.error)
      std::rethrow_exception(f.error);
    if (status != SB_NET_GROUP_STORAGE_OK ||
        (mode == SB_NET_GROUP_STORAGE_CONTAINS ? result > 1 : result != 0))
      throw std::logic_error("Invalid network group storage result");
    return result;
  }
  SbNetGroupStorageState m_state{};
};

}
#endif
