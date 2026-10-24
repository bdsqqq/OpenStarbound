#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Borrowed pointers, no allocation or retention. Status: 0 complete, 2 invalid
 * ABI, 3 contained panic, 4 invalid lead, 5 invalid trail, 6 invalid codepoint.
 * Only 0/4/5/6 increment executing-thread receipts, ops in declaration order.
 * Outputs must be aligned, writable and disjoint from all other arguments.
 * Nonempty input/output must have valid allocation provenance; integer checks
 * cannot prove it. SIZE_MAX input length means lazy NUL termination, not a
 * SIZE_MAX allocation. All reads preserve the legacy short-circuit order.
 * Status 2/semantic errors leave outputs unchanged. Do not retry after panic:
 * encode may have partially written. Decode with zero consumption leaves its
 * codepoint unchanged. Capacity failure writes no bytes. Unused trail is zero.
 */
int32_t star_unicode_validate(const uint8_t*, size_t, uint32_t*);
int32_t star_unicode_length(const uint8_t*, size_t, size_t*);
int32_t star_unicode_decode(const uint8_t*, size_t, uint32_t*, size_t*);
int32_t star_unicode_encode(uint8_t*, size_t, uint32_t, size_t*);
int32_t star_unicode_hex_to(uint32_t, uint32_t, uint32_t, uint32_t*);
int32_t star_unicode_hex_from(uint32_t, uint32_t*, uint32_t*, uint32_t*);
int32_t star_unicode_is_lead(uint32_t, uint32_t*);
int32_t star_unicode_is_trail(uint32_t, uint32_t*);
int32_t star_unicode_pair_from(uint32_t, uint32_t, uint32_t*);
int32_t star_unicode_pair_to(uint32_t, uint32_t*, uint32_t*, uint32_t*);
uint64_t star_unicode_call_count(uint32_t);
#ifdef __cplusplus
}
static_assert(sizeof(size_t) == sizeof(uintptr_t), "Rust usize must match size_t");
#endif
