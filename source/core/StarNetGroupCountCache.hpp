#pragma once
#include "StarConfig.hpp"
#include "StarHash.hpp"
#include "StarMaybe.hpp"
#include <cstdint>
#include <exception>
#include <memory>
#include <stdexcept>
#include <vector>

// Allocation layout/capacity is a verified backend contract, not a portable
// HashMap promise. Other configurations keep the original private HashMap.
#if defined(STAR_USE_RUST_NET_GROUP) && defined(__APPLE__) && _LIBCPP_VERSION == 220106 && UINTPTR_MAX == UINT64_MAX
#define STAR_NET_GROUP_RUST_COUNT_CACHE 1
#include "StarRustNetGroupCountCache.h"

namespace Star {

class NetGroupCountCache {
public:
  NetGroupCountCache() = default;
  NetGroupCountCache(NetGroupCountCache const&) = delete;
  NetGroupCountCache& operator=(NetGroupCountCache const&) = delete;
  NetGroupCountCache(NetGroupCountCache&&) = delete;
  NetGroupCountCache& operator=(NetGroupCountCache&&) = delete;
  ~NetGroupCountCache() noexcept {
    try { execute(SB_NET_GROUP_COUNT_CACHE_DROP); }
    catch (...) { std::terminate(); }
  }
  void increment(uint32_t key) { execute(SB_NET_GROUP_COUNT_CACHE_INCREMENT, key); }
  Maybe<size_t> maybe(uint32_t key) const {
    auto reply = execute(SB_NET_GROUP_COUNT_CACHE_LOOKUP, key);
    if (reply.found) return Maybe<size_t>(reply.value);
    return {};
  }
  void clear() { execute(SB_NET_GROUP_COUNT_CACHE_CLEAR); }
  size_t size() const { return execute(SB_NET_GROUP_COUNT_CACHE_SIZE).value; }

private:
  // Only size/alignment are used: no C++ pair/Shadow objects are constructed or
  // read in this allocation. Rust owns the private slot payloads and padding.
  struct Shadow { std::pair<uint32_t, size_t> value; size_t hash; };
  using Allocator = std::allocator<Shadow>;
  using Traits = std::allocator_traits<Allocator>;
  static_assert(sizeof(Shadow) == 24 && alignof(Shadow) == 8, "native count bucket allocation layout");
  static_assert(offsetof(Shadow, hash) == 16, "native count bucket hash offset");
  using Hasher = Star::hash<uint32_t>;
  struct Frame { Allocator allocator; std::exception_ptr error; Hasher const* hasher; };
  static uintptr_t nativeHash(void* context, uint32_t key) noexcept {
    static_assert(noexcept(Hasher()(key)), "integer hash must not throw");
    return (*static_cast<Frame*>(context)->hasher)(key);
  }
  static uint32_t plan(void*, uintptr_t filled, uintptr_t length, uintptr_t* out) noexcept {
    // Keep BOTH complete native fast-math expressions and their guard order.
    // Existing-key operator[] never reaches this callback.
    static constexpr size_t MinCapacity = 8;
    static constexpr double MaxFillLevel = 0.7;
    *out = 0;
    if (!(length == 0 || filled + 1 > (length - 1) * MaxFillLevel)) return SB_NET_GROUP_COUNT_CACHE_OK;
    size_t newSize = length != 0 ? length - 1 : MinCapacity;
    while ((double)(filled + 1) / (double)newSize > MaxFillLevel)
      newSize *= 2;
    if (newSize != length - 1) *out = newSize + 1;
    return SB_NET_GROUP_COUNT_CACHE_OK;
  }
  static uint32_t allocate(void* context, uintptr_t count, uintptr_t* out) noexcept {
    auto& frame = *static_cast<Frame*>(context);
    try {
      // Native checkCapacity has already swapped OLD out before vector resize.
      // Preserve the vector's own length_error before std::allocator is called.
      std::vector<Shadow> probe;
      if (count > probe.max_size()) probe.reserve(count);
      *out = reinterpret_cast<uintptr_t>(Traits::allocate(frame.allocator, count));
      return SB_NET_GROUP_COUNT_CACHE_OK;
    } catch (...) {
      frame.error = std::current_exception();
      return SB_NET_GROUP_COUNT_CACHE_HOST;
    }
  }
  static void deallocate(void* context, uintptr_t address, uintptr_t count) noexcept {
    Traits::deallocate(static_cast<Frame*>(context)->allocator, reinterpret_cast<Shadow*>(address), count);
  }
  SbNetGroupCountCacheReply execute(uint32_t mode, uint32_t key = 0) const {
    Frame frame{{}, {}, &m_hash};
    SbNetGroupCountCacheOps ops{&frame, nullptr, nullptr, nullptr, nullptr};
    SbNetGroupCountCacheOps const* selected = &ops;
    switch (mode) {
      case SB_NET_GROUP_COUNT_CACHE_INCREMENT:
        ops.hash = nativeHash; ops.plan = plan; ops.allocate = allocate; ops.deallocate = deallocate;
        break;
      case SB_NET_GROUP_COUNT_CACHE_LOOKUP: ops.hash = nativeHash; break;
      case SB_NET_GROUP_COUNT_CACHE_DROP: ops.deallocate = deallocate; break;
      case SB_NET_GROUP_COUNT_CACHE_CLEAR:
      case SB_NET_GROUP_COUNT_CACHE_SIZE: selected = nullptr; break;
      default: throw std::logic_error("Invalid network group count cache mode");
    }
    SbNetGroupCountCacheReply reply{};
    auto status = sb_net_group_count_cache_run(mode, &m_state, selected, key, &reply);
    // A parent Group callback may catch this SAME original exception once more.
    if (frame.error) std::rethrow_exception(frame.error);
    if (status != SB_NET_GROUP_COUNT_CACHE_OK || reply.reserved != 0 ||
        (mode == SB_NET_GROUP_COUNT_CACHE_LOOKUP ? reply.found > 1 || (!reply.found && reply.value != 0) :
          reply.found != 0 || (mode != SB_NET_GROUP_COUNT_CACHE_SIZE && reply.value != 0)))
      throw std::logic_error("Invalid network group count cache result");
    return reply;
  }
  SbNetGroupCountCacheStorage m_state{};
  // Preserve the native hasher object's lifetime, not a fresh temporary per
  // lookup. Its retained footprint also preserves the enclosing group's layout.
  Hasher m_hash{};
};

}
#endif
