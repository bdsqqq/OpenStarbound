#pragma once

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
