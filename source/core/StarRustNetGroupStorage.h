#ifndef STAR_RUST_NET_GROUP_STORAGE_H
#define STAR_RUST_NET_GROUP_STORAGE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
struct alignas(uintptr_t) SbNetGroupStorageState {
  unsigned char bytes[3 * sizeof(uintptr_t)];
};
extern "C" {
#else
typedef struct SbNetGroupStorageState {
  _Alignas(uintptr_t) unsigned char bytes[3 * sizeof(uintptr_t)];
} SbNetGroupStorageState;
#endif

enum {
  SB_NET_GROUP_STORAGE_OK = 0,
  SB_NET_GROUP_STORAGE_INVALID = 1,
  SB_NET_GROUP_STORAGE_HOST = 2,
  SB_NET_GROUP_STORAGE_PANIC = 3
};
enum {
  SB_NET_GROUP_STORAGE_DATA = 0,
  SB_NET_GROUP_STORAGE_SIZE = 1,
  SB_NET_GROUP_STORAGE_CAPACITY = 2,
  SB_NET_GROUP_STORAGE_APPEND = 3,
  SB_NET_GROUP_STORAGE_CLEAR = 4,
  SB_NET_GROUP_STORAGE_DROP = 5,
  SB_NET_GROUP_STORAGE_CONTAINS = 6,
  SB_NET_GROUP_STORAGE_COUNT = 7
};

typedef struct SbNetGroupStorageOps {
  void* context;
  uintptr_t (*max_size)(void*);
  uint32_t (*allocate)(void*, uintptr_t count, uintptr_t* out_address);
  void (*construct_new)(void*, uintptr_t buffer, uintptr_t index);
  void (*move_old)(void*, uintptr_t oldbuffer, uintptr_t newbuffer, uintptr_t index);
  void (*destroy)(void*, uintptr_t buffer, uintptr_t index);
  void (*deallocate)(void*, uintptr_t buffer, uintptr_t capacity);
  uintptr_t (*element)(void*, uintptr_t buffer, uintptr_t index);
  uint32_t (*length_error)(void*);
} SbNetGroupStorageOps;

/* Same NET_GROUP aggregate/default-OFF/43 selectors. The parent adapter selects
 * this storage only on its verified Apple libc++ 220106 backend; other platforms
 * retain their C++ List. Rust owns pointer/length/capacity CONTROL, not native
 * pair payload or children. The adapter uses std::allocator and real
 * std::pair<NetElement*, bool> objects, real Pair&/Pair* borrows, and by-VALUE
 * append. Native pair destruction and move construction must not throw.
 *
 * ZERO bytes are an allocation-free empty state, requiring no FFI constructor.
 * Rust's private three-native-word state is Copy for raw reads, but an allocated
 * OWNER MUST NOT be copied/moved by the host. Parent C++ owner deletes copy/move.
 * Never interpret these bytes as native pointers in C++; DATA supplies the
 * borrowed native pair buffer address (zero for empty unallocated state).
 * Callers supply initialized state, live/aligned storage/out, write permissions
 * for mutations/out, stable read-only ops fields (including its context pointer)
 * and valid native pair lifetimes. The pointed-to callback context may be mutable. All hooks must be nonnull even if unused by the selected mode.
 * Context may be null if its callbacks permit it. Ops is copied before callbacks;
 * ops must not overlap writable state/out. State/out never overlap. Address
 * checks establish neither provenance, liveness, initialization nor permissions.
 * No concurrent access or mutation reentry: only read-only reentry into valid
 * state is permitted. Outstanding native references have vector invalidation.
 *
 * DATA/SIZE/CAPACITY require ops=NULL, argument=0, read-only state; output is
 * address/length/capacity. APPEND/CLEAR/DROP require writable state, ops, argument=0
 * and output zero on success. CONTAINS accepts any element uintptr_t argument,
 * read-only state and ops; output 0/1 compares element callback results exactly.
 * State validation requires length<=capacity and capacity==0 iff address==0;
 * zero capacity also implies zero length. Unknown mode/unused argument, bad
 * alignment/nulls/overlaps/missing hooks/basic state reject before count/write.
 * Invalid foreign memory is outside this ABI; no bounds or lifetime repair.
 *
 * APPEND constructs the new pair BEFORE relocating old pairs, destroys old
 * pairs in reverse, commits new state BEFORE freeing old buffer. Capacity uses
 * libc++ recommendation: cap>=max/2 ? max : max(2*cap,len+1). allocate receives
 * this exact count. All fallible allocation happens before pair/state mutation.
 * CLEAR destroys active pairs in reverse and retains buffer/capacity. DROP
 * destroys active pairs in reverse, commits ZERO, then frees old buffer once.
 * During destroy hooks state still describes the old allocation (pair access
 * during destruction is not generally valid); deallocate observes committed
 * new/empty state. DATA/SIZE/CAPACITY read-only reentry is supported there.
 *
 * ONLY allocate/length_error are fallible: native callbacks catch the original
 * C++ exception into context, return HOST, and adapter rethrows it AFTER Rust
 * returns. length_error must fail; successful allocate returns a valid nonzero
 * buffer, failing allocate neither allocates nor writes out_address. No C++
 * exception may unwind through Rust. Other hooks MUST NOT fail/unwind and must
 * not mutate state/ops. Arbitrary host malice or violations are unqualified.
 * HOST leaves state/output unchanged; diagnostic counters may advance. Ordinary
 * Rust panic is contained as PANIC; all potentially panicking Rust work precedes
 * allocation/mutation. No injected post-allocation panic or rollback mechanism.
 */
uint32_t sb_net_group_storage_run(uint32_t mode, void const* state,
    SbNetGroupStorageOps const* ops, uintptr_t argument, uintptr_t* out);

/* kind 0=TLS, 1=relaxed global, seven roots only (no callback/leaf counters).
 * Wrapping accepted-entry diagnostics, not atomic completion/state snapshots.
 * Unknown kind/mode returns zero. */
uint64_t sb_net_group_storage_count(uint32_t kind, uint32_t mode);

#ifdef __cplusplus
}
static_assert(sizeof(SbNetGroupStorageState) == 3 * sizeof(uintptr_t), "storage size");
static_assert(alignof(SbNetGroupStorageState) == alignof(uintptr_t), "storage alignment");
static_assert(offsetof(SbNetGroupStorageState, bytes) == 0, "storage bytes offset");
#else
_Static_assert(sizeof(SbNetGroupStorageState) == 3 * sizeof(uintptr_t), "storage size");
_Static_assert(_Alignof(SbNetGroupStorageState) == _Alignof(uintptr_t), "storage alignment");
_Static_assert(offsetof(SbNetGroupStorageState, bytes) == 0, "storage bytes offset");
#endif
#endif
