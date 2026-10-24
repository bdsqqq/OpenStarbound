#pragma once

#include <limits.h>
#include <stddef.h>
#include <stdint.h>

#if CHAR_BIT != 8
#error "Rust bytes requires eight-bit bytes"
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* operations: 0 swap-in-place, 1 swap-copy, 2 to-in-place, 3 to-copy,
 * 4 from-in-place, 5 from-copy. order: big 0, little 1, no-conversion 2;
 * every other order reverses. platform_order is the C++ compile fact, 0 or 1.
 * status: 0 complete, 2 invalid ABI, 3 contained panic. Only status 0 counts
 * toward the executing thread's per-operation receipt. Invalid metadata does
 * not modify output. A contained panic must not be retried (partial output).
 * Borrowed allocations must be valid for every accessed byte; bytes may contain
 * uninitialized padding. No allocation provenance can be checked by this ABI.
 * In-place ignores src; no-conversion and len <= 1 do not access its buffer.
 * len 0 accesses neither buffer. Nonempty copy requires nonnull ranges.
 * Reverse-copy preserves sequential src[i] -> dest[len-1-i], including overlap.
 * Non-reversing copy requires disjoint ranges. No pointers are retained. */
int32_t star_bytes_transform(void* dest, void const* src, size_t len,
    uint32_t operation, uint32_t order, uint32_t platform_order);
uint64_t star_bytes_call_count(uint32_t operation);

#ifdef __cplusplus
}
static_assert(sizeof(size_t) == sizeof(uintptr_t), "Rust usize must match size_t");
#endif
