#ifndef STAR_RUST_NET_COMPAT_H
#define STAR_RUST_NET_COMPAT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
struct alignas(uint32_t) SbNetCompatStorage { unsigned char bytes[4]; };
extern "C" {
#else
typedef struct SbNetCompatStorage {
  _Alignas(uint32_t) unsigned char bytes[4];
} SbNetCompatStorage;
#endif

#define SB_NET_COMPAT_ANY_INITIALIZER {{0xff, 0xff, 0xff, 0xff}}

enum {
  SB_NET_COMPAT_OK = 0,
  SB_NET_COMPAT_INVALID = 1,
  SB_NET_COMPAT_PANIC = 3
};
enum {
  SB_NET_COMPAT_INIT_ANY = 0,
  SB_NET_COMPAT_VALUE = 1,
  SB_NET_COMPAT_SET = 2,
  SB_NET_COMPAT_CHECK = 3,
  SB_NET_COMPAT_COUNT = 4
};

/* Same STAR_USE_RUST_NET_GROUP/default-OFF/runtime; no new selector.
 * Rust-defined Copy/POD, NOT Rust-owned heap: foreign hosts allocate/copy these
 * four opaque bytes with native uint32_t alignment. No destructor, allocation,
 * escaped references or new state synchronization. Every initialized four-byte
 * pattern is valid. ALL-FF is AnyVersion (0xffffffff), independent of byte order.
 * ZERO bytes mean stored version zero, NOT the native default AnyVersion.
 * Native defaults use the aggregate initializer above, NOT an FFI constructor.
 * Byte copying, moving and placement of initialized state between calls is valid.
 *
 * INIT_ANY requires argument zero and writable (possibly uninitialized) storage;
 * commits AnyVersion then writes AnyVersion to out. VALUE requires argument zero
 * and initialized storage, copies its value to out without writing storage.
 * SET accepts any argument, writable (possibly uninitialized) storage; commits
 * argument as state THEN writes argument to out. CHECK accepts any rules version
 * as argument, initialized storage; writes 0 or 1 to out without writing storage.
 * CHECK counts exactly one existing scalar COMPAT entry, even for raw AnyVersion.
 * Native callers MUST first VALUE-check AnyVersion before reading rules.version()
 * and skip CHECK in that case, preserving the lazy native rule-getter contract.
 * INIT_ANY/VALUE/SET do not enter scalar kernels.
 *
 * Invalid mode, unused nonzero argument, null pointers, non-native-uint32_t
 * alignment, partial overlap, or exact CHECK out/storage alias returns INVALID
 * BEFORE counters, dereference or writes. Exact alias is permitted for the other
 * modes ONLY when storage is writable. Inputs are copied before writes. Read-only
 * VALUE/CHECK storage requires distinct writable out. Caller guarantees live
 * four-byte objects, initialized state where required and appropriate permissions;
 * address checks cannot prove liveness, provenance, initialization or permissions.
 * Ordinary Rust panics return PANIC; all fallible work precedes commits, so non-OK
 * leaves state/out unchanged. Accepted-entry diagnostics may advance on panic.
 * No C++ callbacks, Rust references escaping, or unwinding across the ABI.
 */
uint32_t sb_net_compat_run(uint32_t mode, void const* storage, uint32_t argument, uint32_t* out);

/* kind 0=current-thread, 1=relaxed global; wrapping accepted-entry diagnostics.
 * Unknown kind/mode returns zero. No reset, completion or atomic-state guarantee. */
uint64_t sb_net_compat_count(uint32_t kind, uint32_t mode);

#ifdef __cplusplus
}
static_assert(sizeof(SbNetCompatStorage) == 4, "SbNetCompatStorage ABI size");
static_assert(alignof(SbNetCompatStorage) == alignof(uint32_t), "SbNetCompatStorage ABI alignment");
static_assert(offsetof(SbNetCompatStorage, bytes) == 0, "SbNetCompatStorage bytes offset");
#else
_Static_assert(sizeof(SbNetCompatStorage) == 4, "SbNetCompatStorage ABI size");
_Static_assert(_Alignof(SbNetCompatStorage) == _Alignof(uint32_t), "SbNetCompatStorage ABI alignment");
_Static_assert(offsetof(SbNetCompatStorage, bytes) == 0, "SbNetCompatStorage bytes offset");
#endif

#endif
