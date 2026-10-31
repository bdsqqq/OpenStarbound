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
  SB_NET_DYNAMIC_STORE = 10,
  SB_NET_DYNAMIC_LOAD = 11,
  SB_NET_DYNAMIC_LOAD_ITEM = 12,
  SB_NET_DYNAMIC_WRITE = 13,
  SB_NET_DYNAMIC_WRITE_CHANGE = 14,
  SB_NET_DYNAMIC_READ = 15,
  SB_NET_DYNAMIC_READ_CHANGE = 16,
  SB_NET_DYNAMIC_READ_MEMBER = 17,
  SB_NET_DYNAMIC_READ_ADDITION = 18,
  SB_NET_DYNAMIC_COUNT = 19
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
  SB_NET_DYNAMIC_SET_BUFFER_RULES = 26,
  SB_NET_DYNAMIC_WRITE_CURRENT_ID = 27,
  SB_NET_DYNAMIC_STORE_CURRENT_BUFFER = 28,
  SB_NET_DYNAMIC_WRITE_BUFFER_TYPED = 29,
  SB_NET_DYNAMIC_CLEAR_BUFFER = 30,
  SB_NET_DYNAMIC_CLEAR_HISTORY = 31,
  SB_NET_DYNAMIC_CAPTURE_LAST_VERSION = 32,
  SB_NET_DYNAMIC_CLEAR_IDMAP = 33,
  SB_NET_DYNAMIC_READ_LOAD_COUNT = 34,
  SB_NET_DYNAMIC_LOAD_ITEM_OP = 35,
  SB_NET_DYNAMIC_CHILD_LOAD = 36,
  SB_NET_DYNAMIC_READY_LOADED = 37,
  SB_NET_DYNAMIC_ADD_LOADED = 38,
  SB_NET_DYNAMIC_RECORD_LOADED = 39,
  SB_NET_DYNAMIC_HISTORY_FLOOR = 40,
  SB_NET_DYNAMIC_WRITE_FULL_MARKER = 41,
  SB_NET_DYNAMIC_STORE_FULL = 42,
  SB_NET_DYNAMIC_ENTER_CHANGE_RANGE = 43,
  SB_NET_DYNAMIC_CHANGE_VERSION = 44,
  SB_NET_DYNAMIC_WRITE_CHANGE_OP = 45,
  SB_NET_DYNAMIC_QUERY_ADDITION = 46,
  SB_NET_DYNAMIC_FIND_ADDITION = 47,
  SB_NET_DYNAMIC_STORE_ADDITION = 48,
  SB_NET_DYNAMIC_WRITE_DELTA_MARKER = 49,
  SB_NET_DYNAMIC_CHANGE_CODE = 50,
  SB_NET_DYNAMIC_WRITE_CURRENT_CHANGE = 51,
  SB_NET_DYNAMIC_WRITE_MEMBER = 52,
  SB_NET_DYNAMIC_WRITE_MEMBER_CODE = 53,
  SB_NET_DYNAMIC_WRITE_BUFFER_RAW = 54,
  SB_NET_DYNAMIC_WRITE_TERMINATOR = 55,
  SB_NET_DYNAMIC_READ_IS_FULL = 56,
  SB_NET_DYNAMIC_LOAD_FULL = 57,
  SB_NET_DYNAMIC_READ_CODE = 58,
  SB_NET_DYNAMIC_READ_CHANGE_OP = 59,
  SB_NET_DYNAMIC_RECORD_INCOMING = 60,
  SB_NET_DYNAMIC_CHANGE_KIND = 61,
  SB_NET_DYNAMIC_READ_ADDITION_OP = 62,
  SB_NET_DYNAMIC_REMOVE_INCOMING = 63,
  SB_NET_DYNAMIC_READ_MEMBER_OP = 64,
  SB_NET_DYNAMIC_CHILD_READ = 65,
  SB_NET_DYNAMIC_MARK_RECEIVED = 66,
  SB_NET_DYNAMIC_HAS_RECEIVED = 67,
  SB_NET_DYNAMIC_CLEAR_RECEIVED = 68,
  SB_NET_DYNAMIC_WRITE_STORE_SIZE = 69,
  SB_NET_DYNAMIC_OP_COUNT = 70
};

typedef SbNetGroupReply SbNetDynamicReply;
typedef SbNetGroupHost SbNetDynamicHost;

/* Dynamic-group control policy only; default-OFF selector
 * STAR_USE_RUST_NET_DYNAMIC, same aggregate/runtime as Group.
 * Native storage, streams, payloads, ownership,
 * ids, virtual calls and exception identity remain in C++.
 * Shared Group ABI: reply size=16/alignment=8, a at 0/b at 8; identical host and
 * root signature types. Rust neither interprets nor retains native pointers.
 *
 * Root argument: WRITE accepts any u64 fromVersion; WRITE_CHANGE accepts only
 * 0/1 (deltaAlreadyWritten); all other modes require zero. Leaf arguments are
 * zero except WRITE_CHANGE_OP (0/1 deltaAlreadyWritten) and READ_MEMBER_OP
 * (the complete native read code, >1). Only WRITE/WRITE_CHANGE return a boolean
 * result (0/1); other successful roots write zero. Errors never write output or
 * undo native prefix effects.
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
 * STORE: WRITE_STORE_SIZE, SET_BUFFER_RULES, ENTER_RANGE; while MORE:
 * WRITE_CURRENT_ID, STORE_CURRENT_BUFFER, WRITE_BUFFER_TYPED, CLEAR_BUFFER,
 * ADVANCE; LEAVE_RANGE. All stream expressions remain native, including typed
 * ByteArray write versus raw byte write. Native rules guards precede root entry.
 * LOAD: CLEAR_HISTORY, CAPTURE_LAST_VERSION, CLEAR_IDMAP, RECORD_RESET (CHANGE),
 * READ_LOAD_COUNT; exactly that many LOAD_ITEM_OP callbacks. Native LOAD_ITEM_OP
 * reads id, constructs buffer from typed ByteArray read, THEN constructs element,
 * nesting LOAD_ITEM: CHILD_LOAD, READY_LOADED (READY), ADD_LOADED, RECORD_LOADED
 * (CHANGE). Native owns the whole per-item scope, moves, and takeData expression.
 * READ_ADDITION uses CHILD_LOAD, READY_LOADED, ADD_LOADED, without recording;
 * native constructs its element BEFORE its buffer, unlike LOAD_ITEM.
 *
 * WRITE: HISTORY_FLOOR; if fromVersion<floor: WRITE_FULL_MARKER, STORE_FULL
 * (STORE), return true. Otherwise ENTER_CHANGE_RANGE; while MORE: CHANGE_VERSION;
 * if version>=fromVersion, WRITE_CHANGE_OP(deltaAlreadyWritten), OR reply into
 * deltaAlreadyWritten; ADVANCE; LEAVE_RANGE. Then SET_BUFFER_RULES, ENTER_RANGE;
 * while MORE: WRITE_MEMBER; only if true: first WRITE_DELTA_MARKER if not already
 * written, WRITE_MEMBER_CODE, WRITE_BUFFER_RAW, CLEAR_BUFFER; ADVANCE; LEAVE_RANGE.
 * False WRITE_MEMBER does NOT clear the buffer. WRITE_MEMBER_CODE retains the
 * whole native u32 id+1 expression, with no Rust arithmetic. If anything emitted,
 * WRITE_TERMINATOR; return whether anything emitted.
 * WRITE_CHANGE: QUERY_ADDITION; if addition, FIND_ADDITION and return false if
 * absent. Unless deltaAlreadyWritten, WRITE_DELTA_MARKER; then CHANGE_CODE;
 * STORE_ADDITION if addition, otherwise WRITE_CURRENT_CHANGE; return true.
 * Native captures the variant pointer/id/shared_ptr pointer, not a shared_ptr
 * copy. STORE_ADDITION constructs its typed temporary AFTER marker and code,
 * performs the whole store/takeData/typed change write, and destroys the buffer
 * before the callback returns. Rust never owns any typed value or pointer.
 *
 * READ: READ_IS_FULL; if true LOAD_FULL (LOAD), return WITHOUT received-id clear.
 * Otherwise repeat READ_CODE until zero: code 1 calls READ_CHANGE_OP, code>1
 * calls READ_MEMBER_OP(code). Then GROUP_ENABLED; only if true: ENTER_RANGE;
 * while MORE: HAS_RECEIVED; if false BLANK_CURRENT; ADVANCE; LEAVE_RANGE;
 * CLEAR_RECEIVED. Disabled interpolation preserves the received-id set.
 * READ_CHANGE: RECORD_INCOMING (native COPY to CHANGE before kind dispatch),
 * CHANGE_KIND: 0 CLEAR_IDMAP; 1 READ_ADDITION_OP; 2 REMOVE_INCOMING; 3 no action.
 * READ_MEMBER: CHILD_READ then FRESH GROUP_ENABLED; if true MARK_RECEIVED.
 * Native keeps all factory, stream, virtual-call, full-expression and exception
 * lifetime ordering. Failure stops immediately, with NO cleanup leaves.
 *
 * Replies start zeroed each call. MORE/GROUP_ENABLED/HISTORY_EMPTY and
 * WRITE_CHANGE_OP/QUERY_ADDITION/FIND_ADDITION/WRITE_MEMBER/READ_IS_FULL/HAS_RECEIVED
 * require a=0 or 1,b=0. READ_LOAD_COUNT/HISTORY_FLOOR/CHANGE_VERSION/READ_CODE
 * permit any u64 a,b=0; CHANGE_KIND requires a<=3,b=0. HISTORY_BOUNDS permits any
 * two u64 values. ALL others a=b=0.
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
 * mode>=19, invalid mode-specific argument, null ctx/host/output, or output not aligned to 4
 * is INVALID before counters, callbacks or writes.
 */
uint32_t sb_net_dynamic_run(uint32_t mode, void* ctx, SbNetDynamicHost host,
    uint64_t argument, uint32_t* out_result);

/* No reset. Wrapping diagnostics: kind0 current-thread accepted roots (<19),
 * kind1 relaxed global accepted roots (<19), kind2 relaxed global ATTEMPTED
 * leaves (<70), incremented BEFORE host. Accepted errors count; rejected roots
 * do not. Invalid query returns 0. Not an atomic snapshot/completion/perf metric.
 */
uint64_t sb_net_dynamic_count(uint32_t kind, uint32_t index);

#ifdef __cplusplus
}
#endif

#endif
