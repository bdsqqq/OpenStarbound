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
  SB_FLAT_HASH_ERASE = 3,
  SB_FLAT_HASH_ERASE_RANGE = 4,
  SB_FLAT_HASH_CLEAR = 5,
  SB_FLAT_HASH_EQUAL = 6,
  SB_FLAT_HASH_COMPARE = 7,
  SB_FLAT_HASH_COUNT = 8
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
  SB_FLAT_HASH_INCREMENT_FILLED = 12,
  SB_FLAT_HASH_REQUEST = 13,
  SB_FLAT_HASH_SHIFT = 14,
  SB_FLAT_HASH_CLEAR_BUCKET = 15,
  SB_FLAT_HASH_DECREMENT_FILLED = 16,
  SB_FLAT_HASH_ITER_MORE = 17,
  SB_FLAT_HASH_ERASE_ITER = 18,
  SB_FLAT_HASH_RESET_FILLED = 19,
  SB_FLAT_HASH_SIZES_EQUAL = 20,
  SB_FLAT_HASH_ENTER_COMPARE = 21,
  SB_FLAT_HASH_NOT_EQUAL = 22,
  SB_FLAT_HASH_ADVANCE_BOTH = 23
};

typedef uint32_t (*SbFlatHashLeaf)(void*, uint32_t, size_t, size_t*);
typedef struct SbFlatHashReply {
  size_t index;
  uint32_t found;
} SbFlatHashReply;

/* Table control policy: buckets, values, pointers and capacity arithmetic
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
 * ERASE REQUEST returns the native pos.current - m_buckets.data() index,
 * computed before entering Rust; native currentBucket initially points there.
 * No empty-table or position-validity check is added: original preconditions hold.
 * Each iteration reads SIZE, masks current+1, and LOAD(next) selects the NEXT
 * native bucket and saves its valuePtr() exactly once. If present, ACTIVE_HASH
 * reads that next bucket's raw hash, followed by fresh SIZE for its distance.
 * A zero distance stops; otherwise SHIFT assigns currentBucket->hash from the
 * next bucket, then *currentBucket->valuePtr() = std::move(*savedNextValue), then
 * currentBucket = nextBucket, returning 0. Keep that exact rollback-free order:
 * hash assignment may survive a throwing move, but current pointer/index advance
 * only after success. Finally CLEAR_BUCKET(currentIndex) calls setEmpty(), then
 * DECREMENT_FILLED decrements m_filledCount. Both return 0. Rust returns the
 * original index with found=0; C++ then calls scan(fresh data + reply.index).
 * ERASE itself must not scan in Rust or cache data for that outer result.
 *
 * ERASE_RANGE ITER_MORE evaluates first != last (exactly 0/1); ERASE_ITER performs
 * first = erase(first) and returns 0. Keep native parameter/end scopes; ignore the
 * Rust MISS reply and construct the result from native first.current.
 * CLEAR returns immediately on initial SIZE==0 WITHOUT resetting filled count.
 * Otherwise its index loop rereads SIZE for every condition, excluding the end
 * bucket, calls CLEAR_BUCKET(index), then RESET_FILLED sets m_filledCount=0.
 * Do not repair odd states or impose bounds. CLEAR returns MISS.
 *
 * EQUAL SIZES_EQUAL evaluates size()==rhs.size() (exactly 0/1). Only after true,
 * ENTER_COMPARE creates named native i=begin(), j=rhs.begin(), e=end(), and calls
 * nested COMPARE while those iterators remain live, returning its boolean.
 * COMPARE ITER_MORE evaluates i != e; NOT_EQUAL evaluates the WHOLE native
 * *i != *j expression, without substituting == or splitting temporary scopes.
 * On false NOT_EQUAL, ADVANCE_BOTH executes ++i then ++j and returns 0. Comparison
 * is deliberately iteration-order-sensitive, NOT unordered membership equality.
 * COMPARE returns {0,1} at end or MISS at first unequal Value; EQUAL returns
 * {0,nestedBool} or MISS on size mismatch. No iterator is created on size mismatch.
 *
 * All operations except LOAD, EXCHANGE_HASH, SET_FILLED and CLEAR_BUCKET
 * receive argument 0.
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
