#ifndef STAR_RUST_NET_RULES_H
#define STAR_RUST_NET_RULES_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
struct alignas(uint32_t) SbNetRulesStorage { unsigned char bytes[8]; };
extern "C" {
#else
typedef struct SbNetRulesStorage {
  _Alignas(uint32_t) unsigned char bytes[8];
} SbNetRulesStorage;
#endif

enum {
  SB_NET_RULES_OK = 0,
  SB_NET_RULES_INVALID = 1,
  SB_NET_RULES_PANIC = 3
};
enum {
  SB_NET_RULES_INIT = 0,
  SB_NET_RULES_VERSION = 1,
  SB_NET_RULES_SET_VERSION = 2,
  SB_NET_RULES_ADMIN = 3,
  SB_NET_RULES_SET_ADMIN = 4,
  SB_NET_RULES_LEGACY = 5,
  SB_NET_RULES_EQUAL_VERSION = 6,
  SB_NET_RULES_COUNT = 7
};

/* Same aggregate STAR_USE_RUST_NET_GROUP/default-OFF/runtime; no new selector.
 * Rust defines a Copy, no-Drop state: native u32 version at offset 0, canonical
 * admin byte (0/1) at offset 4, three reserved bytes at offsets 5..7. Foreign
 * hosts allocate eight opaque bytes aligned like native uint32_t, not universally
 * eight/four-byte alignment. No heap, escaped references or state synchronization.
 * Initialized state may be byte-copied/moved between entries. This is NOT a claim
 * about native C++ bool representations, padding or whole-object byte equality.
 * C++ converts valid native bool values to/from the canonical byte domain.
 *
 * INIT accepts ANY version argument, writes the entire state (admin/reserved zero)
 * then out=argument. C++ MUST supply its extern OpenProtocolVersion for default
 * construction; Rust has no built-in default protocol number. Explicit version
 * construction also uses INIT, so admin starts false. INIT may initialize storage.
 * VERSION/LEGACY require argument=0 and read ONLY the first initialized u32;
 * LEGACY returns version==0. EQUAL_VERSION accepts any other version as argument,
 * reads ONLY the first u32 and returns equality, ignoring admin/reserved. Hashing
 * likewise uses VERSION only. These operations never inspect the admin byte.
 * SET_VERSION writes ONLY the first u32 then out=argument, preserving bytes 4..7;
 * those bytes need not be initialized. ADMIN requires argument=0 and reads ONLY
 * byte 4: 0/1 returns that value, >1 is INVALID before counting or writing.
 * SET_ADMIN requires argument=0/1, writes ONLY byte 4 then out=argument; it never
 * reads old admin/version/reserved. Getters never write storage. Partial-state
 * contracts are byte-specific: no operation other than INIT reads/writes a whole
 * state, and uninitialized reserved bytes must not be read as a whole object.
 *
 * Invalid mode, unused argument, admin argument, null, non-native-u32 alignment,
 * or ANY overlap of storage's eight bytes and out's four bytes is INVALID before
 * counters/dereference/writes (except ADMIN's validated byte read for its domain
 * check). No exact alias is allowed. Callers provide live, appropriately permitted
 * eight-byte storage, writable four-byte out, and initialization of ONLY fields
 * read above. Address checks do not prove provenance, liveness, initialization or
 * permissions. Mutators require writable affected bytes. Native concurrent access
 * remains unsynchronized. All potentially panicking work precedes state/output
 * commit; ordinary Rust panic returns PANIC with state/out unchanged. Accepted
 * counters may advance on panic. No foreign callbacks or unwinding across ABI.
 */
uint32_t sb_net_rules_run(uint32_t mode, void const* storage, uint32_t argument, uint32_t* out);

/* kind 0=thread-local, 1=relaxed global; wrapping accepted-entry diagnostics.
 * Unknown kind/mode returns zero. No reset or atomic state/completion snapshot. */
uint64_t sb_net_rules_count(uint32_t kind, uint32_t mode);

#ifdef __cplusplus
}
static_assert(sizeof(SbNetRulesStorage) == 8, "SbNetRulesStorage ABI size");
static_assert(alignof(SbNetRulesStorage) == alignof(uint32_t), "SbNetRulesStorage ABI alignment");
static_assert(offsetof(SbNetRulesStorage, bytes) == 0, "SbNetRulesStorage bytes offset");
#else
_Static_assert(sizeof(SbNetRulesStorage) == 8, "SbNetRulesStorage ABI size");
_Static_assert(_Alignof(SbNetRulesStorage) == _Alignof(uint32_t), "SbNetRulesStorage ABI alignment");
_Static_assert(offsetof(SbNetRulesStorage, bytes) == 0, "SbNetRulesStorage bytes offset");
#endif

#endif
