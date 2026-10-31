#ifndef STAR_RUST_NET_GROUP_COUNT_CACHE_H
#define STAR_RUST_NET_GROUP_COUNT_CACHE_H
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
struct alignas(uintptr_t) SbNetGroupCountCacheStorage {
  unsigned char bytes[4 * sizeof(uintptr_t)];
};
extern "C" {
#else
typedef struct SbNetGroupCountCacheStorage {
  _Alignas(uintptr_t) unsigned char bytes[4 * sizeof(uintptr_t)];
} SbNetGroupCountCacheStorage;
#endif

enum {
  SB_NET_GROUP_COUNT_CACHE_OK = 0,
  SB_NET_GROUP_COUNT_CACHE_INVALID = 1,
  SB_NET_GROUP_COUNT_CACHE_HOST = 2,
  SB_NET_GROUP_COUNT_CACHE_PANIC = 3
};
enum {
  SB_NET_GROUP_COUNT_CACHE_INCREMENT = 0,
  SB_NET_GROUP_COUNT_CACHE_LOOKUP = 1,
  SB_NET_GROUP_COUNT_CACHE_CLEAR = 2,
  SB_NET_GROUP_COUNT_CACHE_DROP = 3,
  SB_NET_GROUP_COUNT_CACHE_SIZE = 4,
  SB_NET_GROUP_COUNT_CACHE_COUNT = 5
};
typedef struct SbNetGroupCountCacheReply {
  uintptr_t value;
  uint32_t found;
  uint32_t reserved;
} SbNetGroupCountCacheReply;
typedef struct SbNetGroupCountCacheOps {
  void* context;
  uintptr_t (*hash)(void*, uint32_t key);
  uint32_t (*plan)(void*, uintptr_t filled, uintptr_t bucket_len, uintptr_t* out_newlen);
  uint32_t (*allocate)(void*, uintptr_t count, uintptr_t* out_address);
  void (*deallocate)(void*, uintptr_t address, uintptr_t count);
} SbNetGroupCountCacheOps;

/* Private NetElementGroup count owner, selected ONLY by the existing NET_GROUP
 * adapter on Apple/libc++ 220106 with UINTPTR_MAX==UINT64_MAX. Other platforms
 * retain native HashMap. The native adapter verifies its 24-byte, align-8 shadow
 * bucket and baseline allocation bytes; this is not a portable HashMap ABI.
 * No payload references escape. ZERO bytes are allocation-free empty storage;
 * an allocated owner MUST NOT be copied/moved. The parent already forbids both.
 * Rust owns allocation address/length/capacity/filled, probing and u32/usize
 * payloads. Native C++ retains allocator, hash and WHOLE floating capacity/length
 * expressions. Hash is forwarded from the retained native integer hasher object,
 * not assumed to be identity. Slot payloads are private to Rust (including their
 * padding); C++ must not construct/read them as std::pair objects.
 *
 * All objects must be initialized/live/aligned, state writable for mutations,
 * out writable, ops stable during the call. Context may be mutable/null as its
 * hooks permit. Caller guarantees allocated slot liveness and initialized hash
 * fields; payload fields need initialization ONLY where hash has its top bit set.
 * Address/schema checks do not establish provenance/liveness/permissions. No
 * races, mutation reentry, or invalid foreign state qualification. Read-only
 * SIZE/LOOKUP reentry is supported by raw snapshots, without Rust borrows held
 * across callbacks. Output must be disjoint from state, ops, allocated slots;
 * state/ops must also be disjoint from slots and each other.
 *
 * INCREMENT requires all four hooks. LOOKUP requires ONLY hash; all other hooks
 * MUST be NULL. DROP requires ONLY deallocate; other hooks MUST be NULL.
 * CLEAR/SIZE require ops=NULL. Context is unrestricted. Only INCREMENT/LOOKUP
 * accept any u32 key; other keys must be zero. Invalid mode, unused fields,
 * argument, alignment/range/overlap or basic owner schema reject BEFORE counts,
 * callbacks, slot accesses or output writes. Empty owner has address/len/cap=0
 * but allows stale filled (native allocation-failure prefix). Live owner has
 * len=cap=power-of-two+1>=9, filled<=len-1; slot extent fits isize/uintptr_t.
 * Native initialized slot hashes and table invariants remain caller obligations.
 *
 * LOOKUP returns found=0/value=0 or found=1/count; SIZE returns filled/found=0.
 * Mutations return all zero; reserved always zero. Errors NEVER write out.
 * Existing-key increment finds FIRST, wraps usize count, and does not plan/grow.
 * Missing-key plan computes both native capacity-needed and checkCapacity WHOLE
 * expressions; out_newlen=0 means no growth, otherwise exact new power-of-two+1
 * length. Allocate checks the native vector length limit AFTER the swap prefix,
 * then uses std::allocator of the
 * verified shadow bucket, exactly count slots from an EMPTY native vector model.
 * No Rust FP, Vec allocator, or std::HashMap substitution exists in production.
 *
 * Grow snapshots old storage, commits address/len/cap ZERO with filled STALE,
 * then allocates. On failure OLD is STILL deallocated and state stays zero/stale:
 * NO repair/rollback. On success hash fields are zeroed, final sentinel is 1,
 * filled resets, old filled entries are reinserted in SLOT ORDER using native
 * hash/plan callbacks. New state is committed throughout reinsertion BEFORE old
 * free; delete observers see new storage/old counts, NOT the new requested key.
 * Old free completes BEFORE outer insertion/hash. Empty=0, end=1, filled=topbit;
 * probing/swap/bail match FlatHashTable. Clear retains allocation and old payload
 * bytes, clears nonend hashes and filled. Native empty clear is a no-op (including
 * stale filled after failed allocation). Drop commits zero then frees once.
 *
 * ONLY plan/allocate may fail: return nonzero after retaining original native
 * exception_ptr; adapter rethrows AFTER inner Rust AND outer Group Rust return.
 * Failing allocate neither allocates nor writes out_address. Successful allocate
 * supplies valid disjoint aligned space of requested extent. Successful plan
 * must supply a valid sufficient native capacity result. Hash/deallocate MUST
 * be infallible, all callbacks nonunwinding; no exception crosses Rust frames.
 * Native partial state on failure is intentional. Do NOT dereference a failed
 * native map in fixtures: size/deallocation evidence then destruction only.
 * Panic is contained, with a private PRECOMMIT test seam; no postallocation
 * panic rollback guarantee. Counters are wrapping accepted roots, not completion
 * or synchronized state snapshots. kind0=TLS, kind1=relaxed global, unknown=0.
 */
uint32_t sb_net_group_count_cache_run(uint32_t mode, void const* state,
    SbNetGroupCountCacheOps const* ops, uint32_t key, SbNetGroupCountCacheReply* out);
uint64_t sb_net_group_count_cache_count(uint32_t kind, uint32_t index);
#ifdef __cplusplus
}
static_assert(sizeof(SbNetGroupCountCacheStorage) == 4 * sizeof(uintptr_t), "count cache storage size");
static_assert(alignof(SbNetGroupCountCacheStorage) == alignof(uintptr_t), "count cache storage alignment");
static_assert(offsetof(SbNetGroupCountCacheStorage, bytes) == 0, "count cache storage offset");
#if UINTPTR_MAX == UINT64_MAX
static_assert(sizeof(SbNetGroupCountCacheReply) == 16, "count cache reply size");
static_assert(alignof(SbNetGroupCountCacheReply) == 8, "count cache reply alignment");
#endif
#else
_Static_assert(sizeof(SbNetGroupCountCacheStorage) == 4 * sizeof(uintptr_t), "count cache storage size");
_Static_assert(_Alignof(SbNetGroupCountCacheStorage) == _Alignof(uintptr_t), "count cache storage alignment");
_Static_assert(offsetof(SbNetGroupCountCacheStorage, bytes) == 0, "count cache storage offset");
#if UINTPTR_MAX == UINT64_MAX
_Static_assert(sizeof(SbNetGroupCountCacheReply) == 16, "count cache reply size");
_Static_assert(_Alignof(SbNetGroupCountCacheReply) == 8, "count cache reply alignment");
#endif
#endif
#endif
