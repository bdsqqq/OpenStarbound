#pragma once

#include <limits.h>
#include <stddef.h>
#include <stdint.h>

#if CHAR_BIT != 8
#error "Rust encoding requires eight-bit bytes"
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* operations: 0 hex encode, 1 hex decode, 2 nibble decode, 3 base64 encode,
 * 4 base64 decode. statuses: 0 success, 2 invalid ABI, 3 contained panic.
 * input/output are borrowed ranges; nonempty ranges require valid allocations.
 * empty ranges may be NULL. accepted256 is required only for operation 4 and
 * contains 256 acceptance bytes snapshotted from the caller's locale.
 * use_url must be 0/1 for operation 3; otherwise it is ignored.
 * written must be aligned, writable, and disjoint from every supplied range.
 * output must not overlap input or the acceptance table. no pointers retained.
 * validation cannot establish allocation provenance. failure must not be retried
 * after status 3: output may already have been modified. */
int32_t star_encode(uint32_t operation, const uint8_t* input, size_t input_len,
    uint8_t* output, size_t output_capacity, uint32_t use_url,
    const uint8_t* accepted256, size_t* written);
uint64_t star_encode_call_count(uint32_t operation);

#ifdef __cplusplus
}
static_assert(sizeof(size_t) == sizeof(uintptr_t), "Rust usize must match size_t");
#endif
