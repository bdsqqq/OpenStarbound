#ifndef STAR_RUST_UUID_H
#define STAR_RUST_UUID_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_UUID_OK = 0,
  SB_UUID_INVALID = 1,
  SB_UUID_BAD_LENGTH = 2,
  SB_UUID_PANIC = 3
};

/* Status: OK=0, INVALID=1, BAD_LENGTH=2, PANIC=3.
 * No pointers are retained. Callers keep all accessed storage live for the call;
 * non-null inputs must be readable and outputs writable for their full extent.
 * Pointer validity beyond null/alignment is the caller's responsibility.
 * No allocation, callbacks, or C++ exceptions cross this interface.
 * Validation failures write no output and do not increment diagnostic counts.
 */

/* Check len FIRST: len != 16 returns BAD_LENGTH without inspecting pointers or
 * accessing input/output. For len == 16, null pointers return INVALID. Otherwise
 * copy exactly 16 bytes; overlap (including identical pointers) is supported.
 * Byte buffers have no additional alignment requirement.
 */
uint32_t sb_uuid_from_bytes(uint8_t const* data, size_t len, uint8_t* out16);

/* Both inputs contain exactly 16 bytes. signed_chars must be 0 (unsigned char)
 * or 1 (signed char), as selected by the C++ caller's std::is_signed<char>.
 * out_order must be non-null and aligned for int32_t; on OK it receives -1, 0,
 * or 1 for lexicographic less/equal/greater. Null inputs, null/misaligned output,
 * or any other flag return INVALID without writing output. Input/output may
 * overlap: inputs are read in full before writing the result.
 */
uint32_t sb_uuid_compare(uint8_t const* left16, uint8_t const* right16,
    uint32_t signed_chars, int32_t* out_order);

/* Hash exactly 16 native char values using Star::hashCombine, seed zero and
 * native size_t wrapping arithmetic (not std::hash<char>). signed_chars has the
 * same meaning as above, including sign extension before conversion to size_t.
 * out_hash must be non-null, writable, aligned for size_t. Invalid flags/null
 * pointers/misaligned output return INVALID with no writes. Input/output may
 * overlap; input is snapshotted before the result is written.
 */
uint32_t sb_uuid_hash(uint8_t const* data16, uint32_t signed_chars, size_t* out_hash);

/* Per-thread wrapping successful-call counts: 0=copy, 1=compare, 2=hash.
 * Unknown operations return zero. Queries do not change any counts.
 */
uint64_t sb_uuid_count(uint32_t operation);

#ifdef __cplusplus
}
#endif

#endif /* STAR_RUST_UUID_H */
