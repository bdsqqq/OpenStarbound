#pragma once
#include <stddef.h>

namespace Star { class NetElement; }

// Shared fixed-storage observations for the ONE test allocator interceptor.
// Keep this contract in one header rather than duplicating cross-TU definitions.
namespace NetGroupStorageHook {
struct Event { void* pointer; size_t bytes; bool allocation; };
struct State {
  Event events[128]{};
  size_t count = 0;
  bool overflow = false;
  size_t failBytes = 0;
  bool failAny = false;
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
extern thread_local State* armed;
}

namespace StarTest {

// Test-only, fixed-storage scope; available on the allocator probe's matched
// Apple libc++ configuration. Preparing arguments must happen before arming.
struct AllocationProbeResult {
  bool caught = false;
  bool originalIdentity = false;
  unsigned failures = 0;
};
AllocationProbeResult failNextAllocation(void* context, void (*operation)(void*));

}
