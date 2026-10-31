#ifndef STAR_RUST_NET_SYNC_H
#define STAR_RUST_NET_SYNC_H

#include "StarRustNetGroup.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef SbNetGroupReply SbNetSyncReply;
typedef SbNetGroupHost SbNetSyncHost;

enum {
  SB_NET_SYNC_OK = 0,
  SB_NET_SYNC_INVALID = 1,
  SB_NET_SYNC_HOST_ERROR = 2,
  SB_NET_SYNC_PANIC = 3
};
enum {
  SB_NET_SYNC_ENABLE = 0,
  SB_NET_SYNC_DISABLE = 1,
  SB_NET_SYNC_TICK = 2,
  SB_NET_SYNC_STORE = 3,
  SB_NET_SYNC_LOAD = 4,
  SB_NET_SYNC_WRITE = 5,
  SB_NET_SYNC_READ = 6,
  SB_NET_SYNC_BLANK = 7,
  SB_NET_SYNC_COUNT = 8
};
enum {
  SB_NET_SYNC_BASE_ENABLE = 0,
  SB_NET_SYNC_BASE_DISABLE = 1,
  SB_NET_SYNC_BASE_TICK = 2,
  SB_NET_SYNC_HAS_RECENT = 3,
  SB_NET_SYNC_NEED_LOAD = 4,
  SB_NET_SYNC_DECREMENT_TIME = 5,
  SB_NET_SYNC_INTERPOLATING = 6,
  SB_NET_SYNC_EXPIRED_BLANK = 7,
  SB_NET_SYNC_CLEAR_RECENT = 8,
  SB_NET_SYNC_NEED_STORE = 9,
  SB_NET_SYNC_BASE_STORE = 10,
  SB_NET_SYNC_BASE_LOAD = 11,
  SB_NET_SYNC_BASE_WRITE = 12,
  SB_NET_SYNC_BASE_READ = 13,
  SB_NET_SYNC_MARK_READ = 14,
  SB_NET_SYNC_BASE_BLANK = 15,
  SB_NET_SYNC_WAS_BLANK = 16,
  SB_NET_SYNC_MARK_BLANK = 17,
  SB_NET_SYNC_LOAD_BLANK_READY = 18,
  SB_NET_SYNC_OP_COUNT = 19
};

/* Sync-group control policy, using the existing default-OFF
 * STAR_USE_RUST_NET_GROUP selector/runtime. This entry has exactly the group
 * entry's function-pointer type; it does NOT extend the old group's mode/leaf
 * bounds or share its counters. C++ retains fields, rules, streams, native float
 * expressions, optional callbacks and exception identity.
 *
 * C++ applies checkWithRules BEFORE STORE/LOAD/WRITE/READ entry. No BLANK guard.
 * BASE_* must call the qualified NetElementGroup method unchanged: in particular
 * BASE_STORE/BASE_WRITE recheck rules AFTER NEED_STORE may have changed them.
 * NEED_STORE is the const_cast virtual netElementsNeedStore hook. NEED_LOAD is
 * the virtual netElementsNeedLoad(argument != 0), including LOAD after BASE_LOAD
 * even if child callbacks changed rules. Native captured dt/time/hint/version/
 * streams/rules never pass through Rust or this scalar argument.
 *
 * ENABLE/DISABLE: BASE_ENABLE/BASE_DISABLE, HAS_RECENT, if true NEED_LOAD(0).
 * TICK: BASE_TICK, HAS_RECENT; if true DECREMENT_TIME (whole native float -= dt),
 * INTERPOLATING, if true NEED_LOAD(0), then EXPIRED_BLANK (fresh whole native
 * time < 0.0f && wasBlank), if true CLEAR_RECENT. Do NOT recheck HAS_RECENT:
 * the entered native if-scope survives mutations by the virtual load hook.
 * STORE: NEED_STORE then BASE_STORE. LOAD: BASE_LOAD then NEED_LOAD(1).
 * WRITE: NEED_STORE then BASE_WRITE, returning its bool.
 * READ: BASE_READ then MARK_READ (whole native recent=true/time=captured time/
 * wasBlank=false block), then NEED_LOAD(0). Throwing hook retains marked state.
 * BLANK: BASE_BLANK then WAS_BLANK; if false MARK_BLANK (whole native time=
 * captured time/wasBlank=true block); then LOAD_BLANK_READY (fresh whole native
 * hasRecent && netInterpolationEnabled()); if true NEED_LOAD(0).
 * Repeated blanks do not restart expiry. Expiry is STRICT <0, never <=0;
 * recent nonblank reads do not expire. Rust performs NO float/body-value work.
 *
 * Every reply starts a=b=0. HAS_RECENT/INTERPOLATING/EXPIRED_BLANK/BASE_WRITE/
 * WAS_BLANK/LOAD_BLANK_READY require a=0 or 1,b=0; all other replies require
 * a=b=0. All leaf arguments are zero except NEED_LOAD: 1 only in LOAD, else 0.
 * Only OK and HOST_ERROR host statuses are valid. HOST_ERROR wins over bad
 * reply; other statuses or malformed successful replies return INVALID.
 * Errors stop immediately, preserve output and prior native effects, and issue
 * no compensating leaves. C++ catches ALL callback exceptions, retains the
 * exception_ptr and rethrows only AFTER Rust returns. No callback/foreign unwind
 * may cross Rust. The panic barrier handles ordinary Rust panics only.
 *
 * mode>=COUNT, null ctx/host/out_result, out_result not aligned to 4, or any
 * nonzero root argument is INVALID BEFORE counters, callbacks or output writes.
 * Success writes zero except WRITE's bool. Caller supplies live synchronous
 * context/captures and aligned writable output; pointer checks do not establish
 * provenance. Nested group entry is allowed under the original native lifetime
 * and reentry contracts, without retaining any context in Rust.
 */
uint32_t sb_net_sync_run(uint32_t mode, void* ctx, SbNetSyncHost host,
    uint64_t argument, uint32_t* out_result);

/* Independent wrapping, no-reset banks: kind 0=current-thread accepted roots
 * (<8), 1=relaxed global accepted roots (<8), 2=relaxed global ATTEMPTED leaves
 * (<19), counted before callback. Accepted failures count; rejected roots do
 * not. Invalid queries return 0. Not an atomic snapshot/completion observation.
 */
uint64_t sb_net_sync_count(uint32_t kind, uint32_t index);

#ifdef __cplusplus
}
#endif

#endif
