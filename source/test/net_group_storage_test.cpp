#include "StarList.hpp"
#include "StarMemory.hpp"
#include "StarNetGroupStorage.hpp"
#include "StarNetElementGroup.hpp"
#include "gtest/gtest.h"

#include <array>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <new>
#include <type_traits>
#include <utility>

// The replacement allocation functions and growth observations below are a
// finite Apple libc++ 220106 fixture, not a policy for other standard libraries.
// OFF runs exercise the actual List/std::vector, under the identical hook.
#if defined(__APPLE__) && defined(_LIBCPP_VERSION) && _LIBCPP_VERSION == 220106 && !defined(STAR_USE_RPMALLOC)
namespace NetGroupStorageHook {
struct Event { void* pointer; size_t bytes; bool allocation; };
struct State {
  Event events[128]{};
  size_t count = 0;
  bool overflow = false;
  size_t failBytes = 0;
  unsigned failures = 0;
  void const* lastRaised = nullptr;
  void* watched = nullptr;
  void* owner = nullptr;
  void (*observe)(State&) noexcept = nullptr;
  unsigned observations = 0;
  void* observedData = nullptr;
  size_t observedSize = 0;
  size_t observedCapacity = 0;
  Star::NetElement* observedChild = nullptr;
  bool observedFlag = false;
};
thread_local State* armed = nullptr;
struct AllocationFailure : std::bad_alloc {
  AllocationFailure() noexcept { if (armed) armed->lastRaised = this; }
  AllocationFailure(AllocationFailure const&) noexcept { if (armed) armed->lastRaised = this; }
};
void record(State& state, void* pointer, size_t bytes, bool allocation) noexcept {
  if (state.count != 128) state.events[state.count++] = {pointer, bytes, allocation};
  else state.overflow = true;
}
struct Arm {
  State* previous;
  explicit Arm(State& state) noexcept : previous(armed) { armed = &state; }
  ~Arm() noexcept { armed = previous; }
};
}

void* operator new(std::size_t bytes) {
  using namespace NetGroupStorageHook;
  if (armed && armed->failBytes && bytes == armed->failBytes) {
    ++armed->failures;
    throw AllocationFailure();
  }
  // Match the application operator exactly while unarmed (including size zero
  // and allocation failure); only the scoped probe injects a different failure.
  auto pointer = Star::malloc(bytes);
  if (!pointer) throw std::bad_alloc();
  if (armed) record(*armed, pointer, bytes, true);
  return pointer;
}
void operator delete(void* pointer) noexcept {
  using namespace NetGroupStorageHook;
  if (pointer && armed) {
    if (pointer == armed->watched && armed->observe) armed->observe(*armed);
    record(*armed, pointer, 0, false);
  }
  Star::free(pointer);
}
void operator delete(void* pointer, std::size_t bytes) noexcept {
  using namespace NetGroupStorageHook;
  if (pointer && armed) {
    if (pointer == armed->watched && armed->observe) armed->observe(*armed);
    record(*armed, pointer, 0, false);
  }
  Star::free(pointer, bytes);
}

namespace {
using namespace Star;
using namespace NetGroupStorageHook;
using Pair = std::pair<NetElement*, bool>;
#ifdef STAR_NET_GROUP_RUST_STORAGE
using Slots = NetGroupSlots;
#else
using Slots = List<Pair>;
#endif

static_assert(std::is_trivially_destructible<Pair>::value, "native pair destruction leaf");
static_assert(std::is_nothrow_move_constructible<Pair>::value, "native relocation cannot throw");
static_assert(std::is_same<decltype(std::declval<Slots&>()[0]), Pair&>::value, "real pair reference");
static_assert(std::is_same<decltype(std::declval<Slots const&>()[0]), Pair const&>::value, "real const pair reference");
static_assert(!std::is_copy_constructible<NetElementGroup>::value, "parent copy remains deleted");
static_assert(!std::is_copy_assignable<NetElementGroup>::value, "parent assignment remains deleted");
static_assert(!std::is_move_constructible<NetElementGroup>::value, "parent move remains unavailable");
static_assert(std::is_nothrow_destructible<NetElementGroup>::value, "parent destruction remains noexcept");
static_assert(std::is_nothrow_destructible<Slots>::value, "slot destruction is noexcept");
#ifdef STAR_NET_GROUP_RUST_STORAGE
static_assert(sizeof(Slots) == 3 * sizeof(uintptr_t), "qualified native three-word storage");
static_assert(alignof(Slots) == alignof(uintptr_t), "qualified native word alignment");
static_assert(std::is_same<decltype(&Slots::append), void (Slots::*)(Pair)>::value, "append preserves the by-value boundary");
static_assert(!std::is_copy_constructible<Slots>::value, "opaque owner cannot copy");
static_assert(!std::is_move_constructible<Slots>::value, "opaque owner cannot move");
static_assert(std::is_same<decltype(std::declval<Slots&>().begin()), Pair*>::value, "real pair iterator");
static_assert(std::is_same<decltype(std::declval<Slots const&>().begin()), Pair const*>::value, "real const iterator");
#endif

bool contains(Slots const& slots, NetElement const* element) {
#ifdef STAR_NET_GROUP_RUST_STORAGE
  return slots.contains(element);
#else
  return slots.any([element](Pair const& pair) { return pair.first == element; });
#endif
}
struct Child : NetElement {
  unsigned id = 0;
  unsigned initCalls = 0;
  unsigned enableCalls = 0;
  mutable unsigned storeCalls = 0;
  mutable unsigned writeCalls = 0;
  unsigned* destroyed = nullptr;
  NetElementVersion const* version = nullptr;
  float hint = 0;
  ~Child() override { if (destroyed) ++*destroyed; }
  void initNetVersion(NetElementVersion const* value) override { version = value; ++initCalls; }
  void enableNetInterpolation(float value) override { hint = value; ++enableCalls; }
  void netStore(DataStream& ds, NetCompatibilityRules) const override { ++storeCalls; ds.write(uint8_t(id)); }
  void netLoad(DataStream&, NetCompatibilityRules) override {}
  bool writeNetDelta(DataStream& ds, uint64_t, NetCompatibilityRules) const override {
    ++writeCalls;
    ds.write(uint8_t(id));
    return true;
  }
  void readNetDelta(DataStream&, float, NetCompatibilityRules) override {}
};
struct Digest {
  uint64_t value = UINT64_C(14695981039346656037);
  void add(uint64_t word) {
    for (unsigned i = 0; i != 8; ++i) { value ^= (word >> (i * 8)) & 255; value *= UINT64_C(1099511628211); }
  }
  void emit(char const* name) const { std::cout << "NET_GROUP_STORAGE_TRACE " << name << ' ' << value << '\n'; }
};
size_t allocations(State const& state) {
  size_t count = 0;
  for (size_t i = 0; i != state.count; ++i) count += state.events[i].allocation;
  return count;
}
size_t frees(State const& state) { return state.count - allocations(state); }
// SDK __vector/vector.h:857 swaps the owner's new pointers before destroying
// the old split buffer. The delete observer must see that committed state, not
// merely the final state after append returns. No mutation/reentrant append.
void observe(State& state) noexcept {
  auto& slots = *static_cast<Slots*>(state.owner);
  ++state.observations;
  state.observedData = slots.data();
  state.observedSize = slots.size();
  state.observedCapacity = slots.capacity();
  if (slots.size()) {
    state.observedChild = slots[slots.size() - 1].first;
    state.observedFlag = slots[slots.size() - 1].second;
  }
}
}

TEST(NetGroupStorage, DefaultIsAllocationFreeAndLayoutObserved) {
  State state;
  size_t size = 99, capacity = 99;
  Pair* data = nullptr;
  {
    Arm arm(state);
    Slots slots;
    size = slots.size(); capacity = slots.capacity(); data = slots.data();
  }
  EXPECT_EQ(state.count, 0u);
  EXPECT_EQ(size, 0u); EXPECT_EQ(capacity, 0u); EXPECT_EQ(data, nullptr);
  Digest digest;
  digest.add(size); digest.add(capacity); digest.add(sizeof(Slots)); digest.add(alignof(Slots));
  digest.add(sizeof(NetElementGroup)); digest.add(alignof(NetElementGroup));
  digest.emit("default-layout");
}

TEST(NetGroupStorage, TwelveRealChildrenFlagsContainsIndexAndIteration) {
  std::array<Child, 12> children;
  Child absent;
  Slots slots;
  Digest digest;
  for (size_t i = 0; i != children.size(); ++i) {
    children[i].id = unsigned(i + 1);
    slots.append(Pair(&children[i], (i % 3) == 0));
    digest.add(slots.size()); digest.add(slots.capacity());
  }
  EXPECT_FALSE(contains(slots, &absent)); EXPECT_FALSE(contains(slots, nullptr));
  Slots const& view = slots;
  size_t index = 0;
  for (Pair const& pair : view) {
    ASSERT_LT(index, children.size());
    EXPECT_EQ(&pair, &view[index]);
    EXPECT_EQ(pair.first, &children[index]); EXPECT_EQ(pair.second, index % 3 == 0);
    EXPECT_TRUE(contains(view, &children[index]));
    digest.add(children[index].id); digest.add(pair.second);
    ++index;
  }
  EXPECT_EQ(index, children.size());
  digest.emit("twelve-order-flags-growth");
}

TEST(NetGroupStorage, SpareCapacityPreservesActualReferencesAndByValueAlias) {
  std::array<Child, 5> children;
  Slots slots;
  for (unsigned i = 0; i != 3; ++i) slots.append(Pair(&children[i], false));
  ASSERT_GT(slots.capacity(), slots.size());
  Pair& borrowed = slots[0];
  Pair* data = slots.data();
  borrowed.second = true;
  State state;
  { Arm arm(state); slots.append(Pair(&children[3], true)); }
  EXPECT_EQ(state.count, 0u); EXPECT_EQ(slots.data(), data); EXPECT_EQ(&slots[0], &borrowed);
  EXPECT_TRUE(slots[0].second);
  // append takes its argument BY VALUE, before a growth invalidates this alias.
  while (slots.size() < slots.capacity()) slots.append(Pair(&children[4], false));
  auto oldSize = slots.size();
  slots.append(slots[0]);
  EXPECT_EQ(slots[oldSize].first, &children[0]); EXPECT_TRUE(slots[oldSize].second);
  Digest digest; digest.add(slots.size()); digest.add(slots.capacity()); digest.add(slots[oldSize].second);
  digest.emit("real-reference-and-byvalue-alias");
}

TEST(NetGroupStorage, NativeAllocationSizesAndCommitBeforeOldBufferFree) {
  std::array<Child, 12> children;
  Slots slots;
  State history;
  Digest digest;
  for (size_t i = 0; i != children.size(); ++i) {
    Pair* oldData = slots.data();
    auto oldCapacity = slots.capacity();
    State step;
    step.owner = &slots; step.watched = oldData; step.observe = observe;
    { Arm arm(step); slots.append(Pair(&children[i], i % 2 != 0)); }
    EXPECT_FALSE(step.overflow);
    if (slots.capacity() != oldCapacity) {
      ASSERT_EQ(allocations(step), 1u);
      EXPECT_EQ(step.events[0].bytes, slots.capacity() * sizeof(Pair));
      EXPECT_EQ(step.events[0].pointer, slots.data());
      EXPECT_EQ(frees(step), oldData ? 1u : 0u);
      if (oldData) {
        EXPECT_EQ(step.observations, 1u);
        EXPECT_EQ(step.observedData, slots.data()); EXPECT_NE(step.observedData, oldData);
        EXPECT_EQ(step.observedSize, i + 1); EXPECT_EQ(step.observedCapacity, slots.capacity());
        EXPECT_EQ(step.observedChild, &children[i]); EXPECT_EQ(step.observedFlag, i % 2 != 0);
      }
    } else EXPECT_EQ(step.count, 0u);
    // Record observed native capacities, not a newly fitted doubling golden.
    for (size_t j = 0; j != step.count; ++j) {
      digest.add(step.events[j].allocation); digest.add(step.events[j].bytes);
      record(history, step.events[j].pointer, step.events[j].bytes, step.events[j].allocation);
    }
    digest.add(slots.size()); digest.add(slots.capacity());
  }
  EXPECT_FALSE(history.overflow);
  digest.emit("allocation-and-free-observer");
}

TEST(NetGroupStorage, ClearRetainsAllocationAndNeverOwnsChildren) {
  unsigned destroyed = 0;
  Child first, second;
  first.destroyed = &destroyed; second.destroyed = &destroyed;
  Slots slots;
  slots.append(Pair(&first, true)); slots.append(Pair(&second, false));
  Pair* data = slots.data(); auto capacity = slots.capacity();
  State state;
  size_t emptySize, emptyCapacity;
  Pair* emptyData;
  {
    Arm arm(state);
    slots.clear();
    emptySize = slots.size(); emptyCapacity = slots.capacity(); emptyData = slots.data();
    slots.append(Pair(&second, true));
  }
  EXPECT_EQ(state.count, 0u); EXPECT_EQ(destroyed, 0u);
  EXPECT_EQ(emptySize, 0u); EXPECT_EQ(emptyCapacity, capacity); EXPECT_EQ(emptyData, data);
  EXPECT_EQ(slots.data(), data); EXPECT_EQ(slots.size(), 1u);
  EXPECT_FALSE(contains(slots, &first)); EXPECT_TRUE(contains(slots, &second));
  Digest digest; digest.add(emptySize); digest.add(emptyCapacity); digest.add(slots.size()); digest.add(destroyed);
  digest.emit("clear-retain-reuse-borrowed-children");
}

TEST(NetGroupStorage, DestructorFreesExactlyOnceWithoutDestroyingChildren) {
  unsigned destroyed = 0;
  Child child; child.destroyed = &destroyed;
  State state;
  void* allocation = nullptr;
  {
    Arm arm(state);
    Slots slots;
    slots.append(Pair(&child, false)); allocation = slots.data();
    slots.clear();
  }
  ASSERT_EQ(state.count, 2u);
  EXPECT_TRUE(state.events[0].allocation); EXPECT_FALSE(state.events[1].allocation);
  EXPECT_EQ(state.events[0].pointer, allocation); EXPECT_EQ(state.events[1].pointer, allocation);
  EXPECT_EQ(destroyed, 0u);
  Digest digest; digest.add(allocations(state)); digest.add(frees(state)); digest.add(destroyed);
  digest.emit("destructor-one-free");
}

TEST(NetGroupStorage, GrowthFailurePreservesOriginalExceptionAndOldPairs) {
  Child first, second;
  Slots slots;
  slots.append(Pair(&first, true));
  auto size = slots.size(); auto capacity = slots.capacity(); Pair* data = slots.data();
  ASSERT_EQ(size, capacity);
  State state; state.failBytes = 2 * capacity * sizeof(Pair);
  bool caught = false, identity = false;
  try { Arm arm(state); slots.append(Pair(&second, false)); }
  catch (AllocationFailure const& error) { caught = true; identity = &error == state.lastRaised; }
  EXPECT_TRUE(caught); EXPECT_TRUE(identity); EXPECT_EQ(state.failures, 1u); EXPECT_EQ(state.count, 0u);
  EXPECT_EQ(slots.size(), size); EXPECT_EQ(slots.capacity(), capacity); EXPECT_EQ(slots.data(), data);
  EXPECT_EQ(slots[0].first, &first); EXPECT_TRUE(slots[0].second); EXPECT_FALSE(contains(slots, &second));
  slots.append(Pair(&second, false));
  EXPECT_EQ(slots.size(), size + 1); EXPECT_EQ(slots[size].first, &second);
  Digest digest; digest.add(caught); digest.add(identity); digest.add(state.failures); digest.add(slots.size());
  digest.emit("growth-failure-original-exception");
}

TEST(NetGroupStorage, ParentFailureKeepsInitEnablePrefixWithoutAppendOrCounts) {
  Child rejected, accepted;
  rejected.id = 7; accepted.id = 9;
  NetElementVersion version;
  NetElementGroup group;
  group.initNetVersion(&version);
  group.enableNetInterpolation(0.5f);
  // Rule construction / streams / children / parent are set up before arming.
  // Version zero is in addNetElement's count table on both backends; using a
  // version outside that table could hide a stale count behind size fallback.
  NetCompatibilityRules rules(LegacyVersion);
  DataStreamBuffer empty, full, delta;
  State state; state.failBytes = sizeof(Pair);
  bool caught = false, identity = false;
  try { Arm arm(state); group.addNetElement(&rejected); }
  catch (AllocationFailure const& error) { caught = true; identity = &error == state.lastRaised; }
  EXPECT_TRUE(caught); EXPECT_TRUE(identity); EXPECT_EQ(state.failures, 1u);
  EXPECT_EQ(rejected.initCalls, 1u); EXPECT_EQ(rejected.enableCalls, 1u);
  EXPECT_EQ(rejected.version, &version); EXPECT_EQ(rejected.hint, 0.5f);
  group.netStore(empty, rules);
  EXPECT_EQ(empty.size(), 0u); EXPECT_EQ(rejected.storeCalls, 0u);
  EXPECT_FALSE(group.writeNetDelta(delta, 1, rules)); EXPECT_EQ(delta.size(), 0u);
  group.addNetElement(&accepted);
  group.netStore(full, rules);
  ASSERT_EQ(full.size(), 1u); EXPECT_EQ(uint8_t(full.ptr()[0]), uint8_t(9));
  EXPECT_EQ(rejected.storeCalls, 0u); EXPECT_EQ(accepted.storeCalls, 1u);
  // A stale count from the failed append would select indexed multi-child
  // framing instead of the one-child direct payload (and append a terminator).
  EXPECT_TRUE(group.writeNetDelta(delta, 1, rules));
  ASSERT_EQ(delta.size(), 1u); EXPECT_EQ(uint8_t(delta.ptr()[0]), uint8_t(9));
  EXPECT_EQ(rejected.writeCalls, 0u); EXPECT_EQ(accepted.writeCalls, 1u);
  Digest digest; digest.add(caught); digest.add(identity); digest.add(rejected.initCalls);
  digest.add(rejected.enableCalls); digest.add(rejected.storeCalls); digest.add(accepted.storeCalls);
  digest.add(full.size()); digest.add(delta.size()); digest.add(uint8_t(delta.ptr()[0]));
  digest.emit("parent-failed-add-prefix-and-counts");
}
#endif
