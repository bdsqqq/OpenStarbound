#include "StarTtlCache.hpp"
#include <array>
#include <cstddef>
#include <type_traits>

// This generated baseline differs from original.hpp ONLY by the same friend
// declaration. Names are substituted at inclusion, never the method bodies.
#define TtlCacheBase OriginalTtlCacheBase
#define TtlCache OriginalTtlCache
#define HashTtlCache OriginalHashTtlCache
#include "original-observer.hpp"
#undef HashTtlCache
#undef TtlCache
#undef TtlCacheBase

namespace Star {
struct TtlCacheLabAccess {
  template<class C> static constexpr auto offsets() {
    return std::array<size_t, 4>{offsetof(C, m_cache), offsetof(C, m_timeToLive),
      offsetof(C, m_timeSmear), offsetof(C, m_ttlUpdateEnabled)};
  }
};
}

template<class C, class Original> struct Layout {
  static_assert(sizeof(C) == sizeof(Original));
  static_assert(alignof(C) == alignof(Original));
  static_assert(Star::TtlCacheLabAccess::offsets<C>()[0] == Star::TtlCacheLabAccess::offsets<Original>()[0]);
  static_assert(Star::TtlCacheLabAccess::offsets<C>()[1] == Star::TtlCacheLabAccess::offsets<Original>()[1]);
  static_assert(Star::TtlCacheLabAccess::offsets<C>()[2] == Star::TtlCacheLabAccess::offsets<Original>()[2]);
  static_assert(Star::TtlCacheLabAccess::offsets<C>()[3] == Star::TtlCacheLabAccess::offsets<Original>()[3]);
  static_assert(std::is_copy_constructible_v<C> == std::is_copy_constructible_v<Original>);
  static_assert(std::is_move_constructible_v<C> == std::is_move_constructible_v<Original>);
  static_assert(std::is_copy_assignable_v<C> == std::is_copy_assignable_v<Original>);
  static_assert(std::is_move_assignable_v<C> == std::is_move_assignable_v<Original>);
  static_assert(std::is_nothrow_destructible_v<C> == std::is_nothrow_destructible_v<Original>);
  static_assert(std::is_standard_layout_v<C> == std::is_standard_layout_v<Original>);
};
template struct Layout<Star::TtlCache<int, int>, Star::OriginalTtlCache<int, int>>;
template struct Layout<Star::HashTtlCache<int, int>, Star::OriginalHashTtlCache<int, int>>;

template<class C> void allMethods() {
  C c(10, 0, 8, false);
  C const& read = c;
  (void)read.timeToLive(); c.setTimeToLive(12);
  (void)read.timeSmear(); c.setTimeSmear(0);
  (void)read.maxSize(); c.setMaxSize(9);
  (void)read.currentSize(); (void)read.keys(); (void)read.values();
  (void)read.ttlUpdateEnabled(); c.setTtlUpdateEnabled(true);
  (void)c.ptr(1); c.set(1, 2); (void)c.remove(1);
  c.removeWhere([](int const&, int& value) { return ++value == 4; });
  (void)c.get(1, [](int const&) { return 3; });
  c.clear(); c.cleanup([](int const&, int const& value) { return value == 3; });
  C copied(c); C moved(std::move(c)); copied = moved; moved = std::move(copied);
}
template void allMethods<Star::TtlCache<int, int>>();
template void allMethods<Star::HashTtlCache<int, int>>();

struct Nonassignable {
  Nonassignable() = default;
  Nonassignable(Nonassignable const&) = default;
  Nonassignable(Nonassignable&&) = default;
  Nonassignable& operator=(Nonassignable const&) = delete;
  Nonassignable& operator=(Nonassignable&&) = delete;
};
struct MoveOnly {
  MoveOnly() = default;
  MoveOnly(MoveOnly const&) = delete;
  MoveOnly(MoveOnly&&) = default;
  MoveOnly& operator=(MoveOnly const&) = delete;
  MoveOnly& operator=(MoveOnly&&) = delete;
};
template<class C> void reads() {
  C c(10, 0, 8, false);
  (void)c.timeToLive(); (void)c.timeSmear(); (void)c.maxSize();
  (void)c.currentSize(); (void)c.ttlUpdateEnabled(); (void)c.ptr(1);
  (void)c.keys(); c.cleanup(); c.clear();
}
template void reads<Star::TtlCache<int, Nonassignable>>();
template void reads<Star::HashTtlCache<int, Nonassignable>>();
template void reads<Star::TtlCache<int, MoveOnly>>();
template void reads<Star::HashTtlCache<int, MoveOnly>>();

// Production const methods must select const dependency overloads even though
// native frames borrow nonconst storage for the mutating modes.
struct ConstDependency : Star::LruCache<int, Star::pair<int64_t, int>> {
  using Base = Star::LruCache<int, Star::pair<int64_t, int>>;
  size_t maxSize() = delete;
  size_t maxSize() const { return Base::maxSize(); }
  size_t currentSize() = delete;
  size_t currentSize() const { return Base::currentSize(); }
  Star::List<Value> values() = delete;
  Star::List<Value> values() const { return Base::values(); }
};
template void allMethods<Star::TtlCacheBase<ConstDependency>>();
