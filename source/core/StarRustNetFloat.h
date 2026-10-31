#ifndef STAR_RUST_NET_FLOAT_H
#define STAR_RUST_NET_FLOAT_H
#include "StarRustNetGroup.h"
#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_NET_FLOAT_SET = 0,
  SB_NET_FLOAT_ENABLE = 1,
  SB_NET_FLOAT_DISABLE = 2,
  SB_NET_FLOAT_TICK = 3,
  SB_NET_FLOAT_STORE = 4,
  SB_NET_FLOAT_LOAD = 5,
  SB_NET_FLOAT_WRITE = 6,
  SB_NET_FLOAT_READ = 7,
  SB_NET_FLOAT_BLANK = 8,
  SB_NET_FLOAT_DECREMENT = 9,
  SB_NET_FLOAT_BLANK_ITEM = 10,
  SB_NET_FLOAT_COUNT = 11
};
enum {
  SB_NET_FLOAT_VALUE_DIFFERS = 0,
  SB_NET_FLOAT_ENCODE_DIFFERS = 1,
  SB_NET_FLOAT_CAPTURE_VERSION = 2,
  SB_NET_FLOAT_ASSIGN_INPUT = 3,
  SB_NET_FLOAT_HAS_POINTS = 4,
  SB_NET_FLOAT_CLEAR_POINTS = 5,
  SB_NET_FLOAT_APPEND_ZERO = 6,
  SB_NET_FLOAT_EMPLACE_POINTS = 7,
  SB_NET_FLOAT_ASSIGN_LAST = 8,
  SB_NET_FLOAT_RESET_POINTS = 9,
  SB_NET_FLOAT_DECREMENT_SCOPE = 10,
  SB_NET_FLOAT_MORE = 11,
  SB_NET_FLOAT_ADVANCE = 12,
  SB_NET_FLOAT_DECREMENT_CURRENT = 13,
  SB_NET_FLOAT_PRUNE_READY = 14,
  SB_NET_FLOAT_REMOVE_FIRST = 15,
  SB_NET_FLOAT_ASSIGN_INTERPOLATED = 16,
  SB_NET_FLOAT_WRITE_LAST = 17,
  SB_NET_FLOAT_WRITE_CURRENT = 18,
  SB_NET_FLOAT_ASSIGN_READ = 19,
  SB_NET_FLOAT_LATEST_VERSION = 20,
  SB_NET_FLOAT_INPUT_EARLIER = 21,
  SB_NET_FLOAT_APPEND_INPUT = 22,
  SB_NET_FLOAT_SCOPED_BLANK = 23,
  SB_NET_FLOAT_SAVED_EARLIER = 24,
  SB_NET_FLOAT_REPLACE_LAST_POINT = 25,
  SB_NET_FLOAT_APPEND_LAST_POINT = 26,
  SB_NET_FLOAT_OP_COUNT = 27
};
typedef SbNetGroupReply SbNetFloatReply;
typedef SbNetGroupHost SbNetFloatHost;

/* Control-only migration, NOT floating-point qualification or a storage port.
 * Same NET_FIELD selector (default OFF), runtime and Group ABI; no new selector.
 * Native code retains ALL floating arithmetic/predicates, interpolation/search/
 * clamp/round, typed reads/writes, default T, Maybe/Deque/function storage,
 * copies and lifetimes. Private readValue/writeValue/interpolate stay unchanged.
 *
 * WRITE's argument is any uint64_t fromVersion; all other root arguments and
 * ALL callback arguments are zero. Replies: a is strict boolean for leaves
 * 0/1/4/11/14/21/24, arbitrary uint64_t for LATEST_VERSION20, otherwise zero;
 * b is always zero. Successful WRITE output is boolean, all others zero.
 *
 * Native setup BEFORE entry: ENABLE assigns extrapolation; STORE/LOAD/WRITE
 * check compatibility; READ performs its unused-rules handling and T t=readValue
 * WITHOUT a compatibility guard. ASSIGN_INPUT/APPEND_INPUT use named copies,
 * not moves. CAPTURE_VERSION precedes SET assignment and READ queue work.
 * DECREMENT_SCOPE owns the cached native range and synchronously calls mode9;
 * destroy its iterators AFTER nested return. SCOPED_BLANK copies lastPoint and
 * lastTime, assigns lastPoint.first=time, then synchronously calls mode10;
 * the named copy remains alive through ASSIGN_INTERPOLATED. No HAS recheck
 * within an entered TICK branch. Failed appends do NOT repair/reset an engaged
 * empty queue; original hazards and completed prefix effects are preserved.
 *
 * ctx/host/aligned writable out_result stay valid through synchronous reentry.
 * Rust neither owns nor dereferences ctx nor retains pointers. Hosts must catch
 * native exceptions, return HOST2, then rethrow ONLY after Rust has returned.
 * Status OK0/INVALID1/HOST2/PANIC3. Validation precedes counting/callbacks;
 * output is written only on success. Errors do not roll back native effects.
 * count kind0=wrapping TLS accepted roots,1=relaxed global accepted roots,
 * 2=relaxed global attempted leaves; unknown kind/index returns zero.
 */
uint32_t sb_net_float_run(uint32_t mode, void* ctx, SbNetFloatHost host,
    uint64_t argument, uint32_t* out_result);
uint64_t sb_net_float_count(uint32_t kind, uint32_t index);
#ifdef __cplusplus
}
#endif
#endif
