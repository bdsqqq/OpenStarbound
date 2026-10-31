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
  SB_FLAT_HASH_INSERT = 2,
  SB_FLAT_HASH_COUNT = 3
};
enum {
  SB_FLAT_HASH_SIZE = 0,
  SB_FLAT_HASH_HASH = 1,
  SB_FLAT_HASH_LOAD = 2,
  SB_FLAT_HASH_EQUALS = 3,
  SB_FLAT_HASH_ACTIVE_HASH = 4,
  SB_FLAT_HASH_SCAN_EMPTY = 5,
  SB_FLAT_HASH_SCAN_ADVANCE = 6,
  SB_FLAT_HASH_CAPACITY_NEEDED = 7,
  SB_FLAT_HASH_ENSURE_CAPACITY = 8,
  SB_FLAT_HASH_SWAP_VALUE = 9,
  SB_FLAT_HASH_EXCHANGE_HASH = 10,
  SB_FLAT_HASH_SET_FILLED = 11,
  SB_FLAT_HASH_INCREMENT_FILLED = 12
};

typedef uint32_t (*SbFlatHashLeaf)(void*, uint32_t, size_t, size_t*);
typedef struct SbFlatHashReply {
  size_t index;
  uint32_t found;
} SbFlatHashReply;

/* Probe/scan/insert policy: buckets, values, pointers and capacity arithmetic
 * remain native. SIZE includes the end bucket. FIND HASH evaluates the complete
 * native m_hash(key) expression; INSERT HASH evaluates m_hash(m_getKey(value)). LOAD(index) selects the native active
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
 * returns 0. INSERT EQUALS instead evaluates the complete native expression
 * m_equals(m_getKey(*activeValue), m_getKey(value)). Native outer value parameter
 * and native full-expression scopes retain all Value/GetKey temporary lifetimes;
 * Rust never reads, owns or copies Value data.
 *
 * INSERT first calls CAPACITY_NEEDED: exactly the compiled native expression
 * m_buckets.empty() || m_filledCount + 1 > (m_buckets.size() - 1) * MaxFillLevel
 * (MaxFillLevel is 0.7), returning exactly 0/1. If true, ENSURE_CAPACITY calls
 * checkCapacity(1), which may reenter INSERT during rehash, and returns 0.
 * HASH then runs before fresh SIZE/target selection. SWAP_VALUE performs native
 * swap(value, *activeValue), returning 0. EXCHANGE_HASH(currentHash) then exchanges
 * the scalar native activeBucket->hash with currentHash and returns the OLD hash
 * without normalization: Value swap may have changed it. The scalar exchange
 * itself is an unsigned leaf, with no Value crossing the ABI. SET_FILLED(hash)
 * performs activeBucket->setFilled(hash, std::move(value)), returning 0;
 * INCREMENT_FILLED increments m_filledCount and returns 0. On each occupied
 * bucket, fresh ACTIVE_HASH and SIZE after false equality/mismatch determine the
 * entry target before swap; another fresh SIZE determines advancement after swap.
 * All operations except LOAD, EXCHANGE_HASH and SET_FILLED receive argument 0.
 * Predicate replies must be exactly 0/1, void replies exactly 0; word replies
 * (including EXCHANGE_HASH) are unrestricted native size_t values.
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
 * stays native. INSERT always reports its selected bucket: found=1 for a native
 * duplicate (current bucket, even after prior swaps), found=0 for new insertion
 * (first swap bucket, or final empty bucket if no swap). The C++ adapter's insert
 * boolean is !found. Host errors retain native partial mutations but leave reply
 * untouched; a failed SWAP_VALUE must not exchange hash, and failed SET_FILLED
 * must not increment filled count. There is deliberately no capacity validation
 * or probe limit. All size_t arithmetic wraps.
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
