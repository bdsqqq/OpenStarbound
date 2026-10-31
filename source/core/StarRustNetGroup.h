#ifndef STAR_RUST_NET_GROUP_H
#define STAR_RUST_NET_GROUP_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_NET_GROUP_OK = 0,
  SB_NET_GROUP_INVALID = 1,
  SB_NET_GROUP_HOST_ERROR = 2,
  SB_NET_GROUP_PANIC = 3
};
enum {
  SB_NET_GROUP_ADD = 0,
  SB_NET_GROUP_INIT = 1,
  SB_NET_GROUP_STORE = 2,
  SB_NET_GROUP_LOAD = 3,
  SB_NET_GROUP_ENABLE = 4,
  SB_NET_GROUP_DISABLE = 5,
  SB_NET_GROUP_TICK = 6,
  SB_NET_GROUP_WRITE = 7,
  SB_NET_GROUP_READ = 8,
  SB_NET_GROUP_BLANK = 9,
  SB_NET_GROUP_COUNT = 10
};
enum {
  SB_NET_GROUP_ENTER_RANGE = 0,
  SB_NET_GROUP_MORE = 1,
  SB_NET_GROUP_ADVANCE = 2,
  SB_NET_GROUP_LEAVE_RANGE = 3,
  SB_NET_GROUP_INIT_NEW = 4,
  SB_NET_GROUP_NEW_INTERPOLATING = 5,
  SB_NET_GROUP_ENABLE_NEW = 6,
  SB_NET_GROUP_APPEND_NEW = 7,
  SB_NET_GROUP_NEW_COMPAT = 8,
  SB_NET_GROUP_INCREMENT_COUNT = 9,
  SB_NET_GROUP_INIT_CURRENT = 10,
  SB_NET_GROUP_CURRENT_COMPAT = 11,
  SB_NET_GROUP_STORE_CURRENT = 12,
  SB_NET_GROUP_LOAD_CURRENT = 13,
  SB_NET_GROUP_PROPAGATES = 14,
  SB_NET_GROUP_ENABLE_CURRENT = 15,
  SB_NET_GROUP_DISABLE_CURRENT = 16,
  SB_NET_GROUP_GROUP_ENABLED = 17,
  SB_NET_GROUP_TICK_CURRENT = 18,
  SB_NET_GROUP_BLANK_CURRENT = 19,
  SB_NET_GROUP_EXPECTED_SIZE = 20,
  SB_NET_GROUP_WRITE_DIRECT = 21,
  SB_NET_GROUP_SET_BUFFER_RULES = 22,
  SB_NET_GROUP_WRITE_BUFFERED = 23,
  SB_NET_GROUP_WRITE_INDEX = 24,
  SB_NET_GROUP_WRITE_BUFFER = 25,
  SB_NET_GROUP_CLEAR_BUFFER = 26,
  SB_NET_GROUP_WRITE_TERMINATOR = 27,
  SB_NET_GROUP_READ_DIRECT = 28,
  SB_NET_GROUP_READ_INDEX = 29,
  SB_NET_GROUP_BLANK_INDEX = 30,
  SB_NET_GROUP_READ_AT_INDEX = 31,
  SB_NET_GROUP_THROW_EMPTY = 32,
  SB_NET_GROUP_THROW_ORDER = 33,
  SB_NET_GROUP_OP_COUNT = 34
};

typedef struct SbNetGroupReply {
  uint64_t a;
  uint64_t b;
} SbNetGroupReply;

/* NetElementGroup control policy only. C++ retains elements, count map,
 * compatibility rules, streams, persistent m_buffer, cached native range
 * iterators, indexed access and exception identity. Reply size=16, alignment=8,
 * offsets a=0,b=8. No native pointer is interpreted or retained by Rust.
 * Intended selector: default-OFF STAR_USE_RUST_NET_GROUP (42).
 *
 * Before ADD entry C++ asserts no duplicate element. Before INIT it assigns
 * m_version. Before ENABLE it assigns enabled=true and extrapolationHint;
 * before DISABLE it assigns enabled=false and hint=0. Before STORE/LOAD/WRITE/
 * READ entry it applies the native group checkWithRules guard. These effects
 * must not move into callbacks or be rolled back after failure.
 *
 * ADD: INIT_NEW; NEW_INTERPOLATING (whole enabled && propagate predicate);
 * if true ENABLE_NEW; APPEND_NEW; for version in [0,argument), NEW_COMPAT(version)
 * then if true INCREMENT_COUNT(version). INCREMENT_COUNT retains the whole
 * native m_elementCounts[version]++ size_t expression, not a Rust-side count.
 * INIT visits ALL children. STORE/LOAD query CURRENT_COMPAT before child call.
 * ENABLE/DISABLE query PROPAGATES for EACH child (never cache). TICK/BLANK query
 * GROUP_ENABLED once before entering a range; if enabled visit ALL children,
 * ignoring propagation flags. Disabled TICK/BLANK issue no range operations.
 * All ranges use ENTER_RANGE, repeated MORE/child/ADVANCE, then LEAVE_RANGE.
 * ENTER_RANGE caches the original native begin/end exactly once. Rust never
 * substitutes indexed lookup for a current-iterator leaf, or vice versa.
 *
 * WRITE/READ: EXPECTED_SIZE is FIRST (native cached count with size fallback).
 * WRITE expected=0 returns false without range; READ expected=0 THROW_EMPTY.
 * expected=1 enters range, skips incompatible entries, handles first compatible
 * with WRITE_DIRECT/READ_DIRECT then LEAVEs, with no index headers. No compatible
 * child is a successful no-op; WRITE returns false. WRITE_DIRECT returns the
 * child's bool. READ_DIRECT retains native stream/time/rules full-expression.
 *
 * WRITE expected>1: SET_BUFFER_RULES BEFORE ENTER_RANGE; i=0. While MORE, break
 * if i>expected (STRICT >, not >=), skip incompatible entries with ADVANCE;
 * otherwise wrapping ++i; WRITE_BUFFERED; if true mark delta then WRITE_INDEX(i),
 * WRITE_BUFFER, CLEAR_BUFFER. ADVANCE; finally LEAVE_RANGE, and if delta then
 * WRITE_TERMINATOR. Buffer is persistent: NEVER clear before first child, on
 * false return, or on error. A false child may still have appended bytes, later
 * emitted as a prefix with the next successful child. CLEAR_BUFFER happens only
 * after successful WRITE_BUFFER. No automatic buffer or framing repair.
 *
 * READ expected>1: READ_INDEX BEFORE ENTER_RANGE; i=offset=0. While MORE, break
 * if i>expected (STRICT >). Incompatible child: wrapping ++offset, ADVANCE,
 * continue. If readIndex==0 or readIndex-1>i, query GROUP_ENABLED AFRESH; if true
 * BLANK_INDEX(i+offset wrapping). Else if readIndex-1==i, READ_AT_INDEX(i+offset
 * wrapping), then READ_INDEX again. Else THROW_ORDER. Wrapping ++i, ADVANCE;
 * finally LEAVE_RANGE. BLANK_INDEX/READ_AT_INDEX perform native m_elements[index]
 * access, separate from cached iterator traversal. Do not consume or repair a
 * leftover index/data, require a terminator, blank tails separately, or reject a
 * high index: original behavior blanks remaining children and leaves data unread.
 * THROW_EMPTY/THROW_ORDER must return HOST_ERROR; an erroneous OK becomes INVALID.
 *
 * Reply starts zeroed on EVERY invocation. MORE/NEW_INTERPOLATING/NEW_COMPAT/
 * CURRENT_COMPAT/PROPAGATES/GROUP_ENABLED/WRITE_DIRECT/WRITE_BUFFERED return
 * a=0 or 1,b=0. EXPECTED_SIZE/READ_INDEX accept any u64 a,b=0. All others return
 * a=b=0. Arguments are zero except NEW_COMPAT/INCREMENT_COUNT (version) and
 * WRITE_INDEX/BLANK_INDEX/READ_AT_INDEX (index). Only OK and HOST_ERROR are valid
 * host statuses. HOST_ERROR wins over malformed reply; other statuses and bad
 * successful replies produce INVALID. Successful root result is zero except
 * WRITE's delta bool. Every error preserves output and all prior native effects,
 * and stops immediately WITHOUT extra LEAVE_RANGE, rollback or cleanup leaves.
 * Native scopes clean up their iterator/capture lifetimes AFTER Rust returns.
 *
 * Catch ALL C++ exceptions inside host, retain exception_ptr, return HOST_ERROR,
 * then rethrow ONLY after Rust returns. NO foreign unwind or callback panic may
 * cross Rust. Rust's panic barrier only handles ordinary Rust panics (PANIC).
 * Reentry is supported only where the original native operation permits it;
 * contexts and captures must remain live through synchronous nested calls.
 *
 * mode>=COUNT, null ctx/host/out_result, out_result not aligned to 4, ADD argument
 * >UINT32_MAX, or ANY nonzero argument for another mode is INVALID BEFORE counts,
 * host calls or output writes. ADD argument is the exclusive version limit.
 * Scalar/pointer checks do not establish provenance/liveness: caller must supply
 * writable aligned uint32_t output and live context/captures for the whole call.
 */
typedef uint32_t (*SbNetGroupHost)(void* ctx, uint32_t leaf,
    uint64_t argument, SbNetGroupReply* out_reply);
uint32_t sb_net_group_run(uint32_t mode, void* ctx, SbNetGroupHost host,
    uint64_t argument, uint32_t* out_result);

/* Wrapping, no-reset diagnostics: kind 0=current-thread accepted roots (<10),
 * kind 1=relaxed global accepted roots (<10), kind 2=relaxed global ATTEMPTED
 * leaves (<34), counted BEFORE host. Accepted failures count, rejected roots
 * do not. Invalid queries return 0. Independent loads are not an atomic snapshot,
 * completion observation, or performance evidence.
 */
uint64_t sb_net_group_count(uint32_t kind, uint32_t index);

#ifdef __cplusplus
}
static_assert(sizeof(SbNetGroupReply) == 16, "SbNetGroupReply ABI size");
static_assert(alignof(SbNetGroupReply) == 8, "SbNetGroupReply ABI alignment");
#endif

#endif
