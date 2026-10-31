#ifndef STAR_RUST_FLAT_HASH_TABLE_H
#define STAR_RUST_FLAT_HASH_TABLE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_FLAT_HASH_OK = 0,
  SB_FLAT_HASH_INVALID = 1,
  SB_FLAT_HASH_HOST_ERROR = 2,
  SB_FLAT_HASH_PANIC = 3
};
enum {
  SB_FLAT_HASH_FIND = 0,
  SB_FLAT_HASH_SCAN = 1,
  SB_FLAT_HASH_COUNT = 2
};
enum {
  SB_FLAT_HASH_SIZE = 0,
  SB_FLAT_HASH_HASH = 1,
  SB_FLAT_HASH_LOAD = 2,
  SB_FLAT_HASH_EQUALS = 3,
  SB_FLAT_HASH_ACTIVE_HASH = 4,
  SB_FLAT_HASH_SCAN_EMPTY = 5,
  SB_FLAT_HASH_SCAN_ADVANCE = 6
};

typedef uint32_t (*SbFlatHashLeaf)(void*, uint32_t, size_t, size_t*);
typedef struct SbFlatHashReply {
  size_t index;
  uint32_t found;
} SbFlatHashReply;

/* Probe/scan policy only: buckets, values, pointers, mutation and capacity remain
 * native. SIZE includes the end bucket. HASH evaluates the complete native
 * m_hash(key) expression before returning. LOAD(index) selects the native active
 * bucket, calls activeBucket->valuePtr() exactly once, saves that returned Value*
 * as activeValue, and returns exactly 0/1 for activeValue != null. This getter
 * always runs BEFORE any bucket-hash comparison, including on hash mismatch.
 * On presence, ACTIVE_HASH reads activeBucket->hash before the hash comparison.
 * EQUALS evaluates m_equals(m_getKey(*activeValue), key), using the SAVED pointer
 * without calling valuePtr() again, and returns exactly 0/1. After false equality
 * or hash mismatch, ACTIVE_HASH rereads activeBucket->hash, then SIZE is reread
 * for the probe mask. Equality may mutate the bucket; the comparison hash must
 * not be reused. HASH may reallocate before LOAD selects the bucket.
 * SCAN_EMPTY returns exactly 0/1; SCAN_ADVANCE advances the native pointer and
 * returns 0. All operations except LOAD receive scalar argument 0.
 *
 * Leaf returns 0 on success; any other status stops with HOST_ERROR. Native
 * exceptions MUST be caught in the leaf, retained by the host, and rethrown only
 * after this call returns. No foreign unwind may cross Rust. Reentry is allowed;
 * the host owns validity of active buckets and native scopes during callbacks.
 *
 * Context, callback and reply must be nonnull; reply must be naturally aligned.
 * The caller guarantees live, writable reply storage and a live context for the
 * entire call. No Rust reference to context is held across a callback. Reply is
 * written only on OK. FIND reports found=1/index on match, otherwise {0,0}; the
 * host resolves its own end iterator. SCAN always returns {0,0}; its result pointer
 * stays native. There is deliberately no capacity validation or probe limit.
 */
uint32_t sb_flat_hash_run(uint32_t mode, void* context, SbFlatHashLeaf leaf,
    SbFlatHashReply* out);

/* kind 0: calling-thread counts; kind 1: relaxed aggregate atomic counts.
 * Unknown kind/mode returns 0. Accepted entries count once, including host errors;
 * rejected arguments do not count. Counters wrap and do not synchronize state.
 */
uint64_t sb_flat_hash_count(uint32_t kind, uint32_t mode);

#ifdef __cplusplus
}
#endif
#endif
