#ifndef STAR_RUST_NET_DYNAMIC_H
#define STAR_RUST_NET_DYNAMIC_H

#include "StarRustNetGroup.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_NET_DYNAMIC_OK = 0,
  SB_NET_DYNAMIC_INVALID = 1,
  SB_NET_DYNAMIC_HOST_ERROR = 2,
  SB_NET_DYNAMIC_PANIC = 3
};
enum {
  SB_NET_DYNAMIC_ADD = 0,
  SB_NET_DYNAMIC_REMOVE = 1,
  SB_NET_DYNAMIC_CLEAR = 2,
  SB_NET_DYNAMIC_INIT = 3,
  SB_NET_DYNAMIC_ENABLE = 4,
  SB_NET_DYNAMIC_DISABLE = 5,
  SB_NET_DYNAMIC_TICK = 6,
  SB_NET_DYNAMIC_BLANK = 7,
  SB_NET_DYNAMIC_CHANGE = 8,
  SB_NET_DYNAMIC_READY = 9,
  SB_NET_DYNAMIC_COUNT = 10
};
enum {
  SB_NET_DYNAMIC_ENTER_RANGE = 0,
  SB_NET_DYNAMIC_MORE = 1,
  SB_NET_DYNAMIC_ADVANCE = 2,
  SB_NET_DYNAMIC_LEAVE_RANGE = 3,
  SB_NET_DYNAMIC_READY_NEW = 4,
  SB_NET_DYNAMIC_ADD_NEW = 5,
  SB_NET_DYNAMIC_RECORD_ADD = 6,
  SB_NET_DYNAMIC_REMOVE_ID = 7,
  SB_NET_DYNAMIC_RECORD_REMOVE = 8,
  SB_NET_DYNAMIC_REMOVE_CURRENT_ID = 9,
  SB_NET_DYNAMIC_RECORD_RESET = 10,
  SB_NET_DYNAMIC_INIT_CURRENT = 11,
  SB_NET_DYNAMIC_RECORD_CURRENT_ADD = 12,
  SB_NET_DYNAMIC_ENABLE_CURRENT = 13,
  SB_NET_DYNAMIC_DISABLE_CURRENT = 14,
  SB_NET_DYNAMIC_TICK_CURRENT = 15,
  SB_NET_DYNAMIC_GROUP_ENABLED = 16,
  SB_NET_DYNAMIC_BLANK_CURRENT = 17,
  SB_NET_DYNAMIC_APPEND_CHANGE = 18,
  SB_NET_DYNAMIC_SET_HISTORY_FLOOR = 19,
  SB_NET_DYNAMIC_HISTORY_EMPTY = 20,
  SB_NET_DYNAMIC_HISTORY_BOUNDS = 21,
  SB_NET_DYNAMIC_POP_HISTORY = 22,
  SB_NET_DYNAMIC_INIT_READY = 23,
  SB_NET_DYNAMIC_ENABLE_READY = 24,
  SB_NET_DYNAMIC_DISABLE_READY = 25,
  SB_NET_DYNAMIC_OP_COUNT = 26
};

typedef SbNetGroupReply SbNetDynamicReply;
typedef SbNetGroupHost SbNetDynamicHost;

/* Dynamic-group control policy only; planned default-OFF selector
 * STAR_USE_RUST_NET_DYNAMIC, same aggregate/runtime as Group. This declaration
 * does not wire production methods. Native storage, streams, payloads, ownership,
 * ids, virtual calls and exception identity remain in C++.
 * Shared Group ABI: reply size=16/alignment=8, a at 0/b at 8; identical host and
 * root signature types. Rust neither interprets nor retains native pointers.
 *
 * ALL root arguments and ALL leaf arguments MUST be zero. Every successful root
 * writes result=0; errors never write output or undo native prefix effects.
 * ADD keeps its ElementPtr parameter alive in the native whole-method scope:
 * READY_NEW calls readyElement(element) by const reference (no extra SharedPtr
 * copy), nesting READY; ADD_NEW performs WHOLE m_idMap.add(std::move(element))
 * and saves id natively; RECORD_ADD performs addChangeData(ElementAddition(id,{}))
 * nesting CHANGE. C++ returns its saved id, not Rust's zero result.
 * REMOVE: REMOVE_ID performs native m_idMap.remove(id); RECORD_REMOVE performs
 * the full typed addChangeData(ElementRemoval{id}), nesting CHANGE.
 *
 * CLEAR: BEFORE entry C++ owns the netElementIds() temporary and caches its
 * begin/end. Rust does NOT ENTER_RANGE or LEAVE_RANGE: while MORE,
 * REMOVE_CURRENT_ID performs WHOLE removeNetElement(*iter), nesting REMOVE,
 * then ADVANCE. Snapshot ownership (not borrowed map iterators) survives Rust
 * success/error; native owner destruction happens after return. Failed removal
 * or recording preserves all earlier effects and the original snapshot prefix.
 *
 * INIT: BEFORE entry C++ sets m_netVersion, clears m_changeData, sets
 * m_changeDataLastVersion=0. RECORD_RESET nests CHANGE; then ENTER_RANGE,
 * while MORE: INIT_CURRENT (child init with current native version),
 * RECORD_CURRENT_ADD (full typed native addition, nesting CHANGE), ADVANCE;
 * LEAVE_RANGE. NO readyElement or interpolation toggle during INIT.
 * ENABLE/DISABLE: BEFORE entry C++ sets flag and hint (true/input or false/0).
 * ENTER_RANGE, while MORE: ENABLE_CURRENT/DISABLE_CURRENT, ADVANCE; LEAVE_RANGE.
 * TICK uses the same range with TICK_CURRENT, ALWAYS visiting all children even
 * when group interpolation is disabled. BLANK queries GROUP_ENABLED once and
 * only if true traverses the range with BLANK_CURRENT.
 * ENTER_RANGE caches original native begin/end once; errors issue NO extra
 * LEAVE_RANGE/cleanup/rollback. Native range owner destructs after Rust returns.
 *
 * CHANGE: BEFORE entry C++ captures currentVersion and performs the original
 * monotonic starAssert. APPEND_CHANGE retains WHOLE native append of
 * {currentVersion,std::move(change)}. SET_HISTORY_FLOOR retains WHOLE ORIGINAL
 * m_changeDataLastVersion = max<int64_t>((int64_t)currentVersion -
 * MaxChangeDataVersions, 0), with
 * MaxChangeDataVersions=100. NO Rust cast/subtraction or repair/extension of the
 * original signed-overflow domain. Then, on EVERY guard: HISTORY_EMPTY; if
 * nonempty HISTORY_BOUNDS returns a=frontVersion,b=current floor (any u64 each).
 * If a>=b stop, otherwise POP_HISTORY (including native payload destructors),
 * repeat. No artificial iteration cap. Native change parameter/full-expression
 * lifetimes extend through Rust return; failure is not transactional.
 * READY: INIT_READY first, then FRESH GROUP_ENABLED; ENABLE_READY if true,
 * otherwise DISABLE_READY. ENABLE_READY uses the current native hint AFTER init.
 *
 * Replies start zeroed each call. MORE/GROUP_ENABLED/HISTORY_EMPTY require
 * a=0 or 1,b=0. HISTORY_BOUNDS permits any two u64 values. ALL others a=b=0.
 * Only OK and HOST_ERROR are valid host statuses; HOST_ERROR wins over malformed
 * replies, other statuses or bad successful replies become INVALID. Stop at
 * first failure without further leaves or output writes.
 *
 * Catch ALL C++ exceptions in host, save exception_ptr, return HOST_ERROR;
 * rethrow only AFTER Rust returns. NO foreign unwind/callback panic may cross
 * Rust. Rust's barrier catches ordinary Rust panics only. Opaque context/captures
 * and aligned writable output must stay live through synchronous callbacks and
 * legal native reentry; scalar checks do not establish pointer provenance.
 * No Rust reference to context/output is held across host calls.
 * mode>=10, nonzero argument, null ctx/host/output, or output not aligned to 4
 * is INVALID before counters, callbacks or writes.
 */
uint32_t sb_net_dynamic_run(uint32_t mode, void* ctx, SbNetDynamicHost host,
    uint64_t argument, uint32_t* out_result);

/* No reset. Wrapping diagnostics: kind0 current-thread accepted roots (<10),
 * kind1 relaxed global accepted roots (<10), kind2 relaxed global ATTEMPTED
 * leaves (<26), incremented BEFORE host. Accepted errors count; rejected roots
 * do not. Invalid query returns 0. Not an atomic snapshot/completion/perf metric.
 */
uint64_t sb_net_dynamic_count(uint32_t kind, uint32_t index);

#ifdef __cplusplus
}
#endif

#endif
