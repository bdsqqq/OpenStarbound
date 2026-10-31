#ifndef STAR_RUST_NET_VERSION_H
#define STAR_RUST_NET_VERSION_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
/* Byte hosting only: the typed state and its operations are defined in Rust.
 * Aggregate zero initialization preserves native constexpr/noexcept defaults. */
struct alignas(uint64_t) SbNetVersionStorage { unsigned char bytes[8]; };
extern "C" {
#else
typedef struct SbNetVersionStorage {
  _Alignas(uint64_t) unsigned char bytes[8];
} SbNetVersionStorage;
#endif

enum {
  SB_NET_VERSION_OK = 0,
  SB_NET_VERSION_INVALID = 1,
  SB_NET_VERSION_PANIC = 3
};
enum {
  SB_NET_VERSION_INIT = 0,
  SB_NET_VERSION_CURRENT = 1,
  SB_NET_VERSION_ADVANCE = 2,
  SB_NET_VERSION_COUNT = 3
};

/* Existing STAR_USE_RUST_NET_GROUP/default-OFF/runtime; no new selector.
 * In-place Copy/POD state, NOT Rust-owned heap storage. Size 8, alignment of
 * native uint64_t (not a fixed 8 on every target), no destructor or escaped
 * references. All initialized 8-byte bit patterns are valid. ZERO BYTES are
 * initialized state with value zero: native defaults MUST zero-initialize the
 * aggregate directly, without an FFI constructor. INIT is for foreign raw
 * storage and tests, so actual game INIT counts may legitimately remain zero.
 * Initialized state permits byte copy, move and placement between ABI entries.
 * No new atomicity or synchronization of version state is provided.
 *
 * INIT: storage must be writable, but need not already be initialized. Writes
 * zero state, then zero to out. CURRENT: initialized storage may be read-only;
 * copies its value to out and NEVER writes through storage. ADVANCE: storage
 * must be initialized and writable; increments modulo 2^64, commits state,
 * THEN writes the new value to out. ADVANCE also counts exactly one existing
 * scalar VERSION_NEXT entry; INIT/CURRENT do not enter scalar kernels.
 *
 * Invalid mode, null storage/out or either pointer not aligned to uint64_t
 * returns INVALID BEFORE counters, dereference or writes. Otherwise caller
 * guarantees live 8-byte objects, initialized bytes for CURRENT/ADVANCE, and
 * appropriate read/write permissions. Address checks cannot prove liveness,
 * initialization or provenance. out is a writable uint64_t object, disjoint
 * from storage OR the exact same aligned word when storage is writable.
 * CURRENT with read-only storage requires a distinct writable out. Inputs are
 * copied before any writes; no Rust reference is retained across operations.
 * Rust panics are contained as PANIC. Non-OK leaves state/out unchanged;
 * accepted entries may count before a later panic. No callbacks/reentry.
 */
uint32_t sb_net_version_run(uint32_t mode, void const* storage, uint64_t* out);

/* kind 0=current-thread, kind 1=relaxed global accepted entries; three wrapping
 * counters. Unknown kind/mode returns zero. No reset or synchronized snapshot;
 * entry counts are not completion, result, atomic-state or performance proof. */
uint64_t sb_net_version_count(uint32_t kind, uint32_t mode);

#ifdef __cplusplus
}
static_assert(sizeof(SbNetVersionStorage) == 8, "SbNetVersionStorage ABI size");
static_assert(alignof(SbNetVersionStorage) == alignof(uint64_t), "SbNetVersionStorage ABI alignment");
static_assert(offsetof(SbNetVersionStorage, bytes) == 0, "SbNetVersionStorage bytes offset");
#else
_Static_assert(sizeof(SbNetVersionStorage) == 8, "SbNetVersionStorage ABI size");
_Static_assert(_Alignof(SbNetVersionStorage) == _Alignof(uint64_t), "SbNetVersionStorage ABI alignment");
_Static_assert(offsetof(SbNetVersionStorage, bytes) == 0, "SbNetVersionStorage bytes offset");
#endif

#endif
