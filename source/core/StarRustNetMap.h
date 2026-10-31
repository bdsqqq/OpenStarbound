#ifndef STAR_RUST_NET_MAP_H
#define STAR_RUST_NET_MAP_H

#include "StarRustNetGroup.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_NET_MAP_OK = 0,
  SB_NET_MAP_INVALID = 1,
  SB_NET_MAP_HOST_ERROR = 2,
  SB_NET_MAP_PANIC = 3
};
enum {
  SB_NET_MAP_INIT = 0,
  SB_NET_MAP_FLUSH = 1,
  SB_NET_MAP_TICK = 2,
  SB_NET_MAP_STORE = 3,
  SB_NET_MAP_LOAD = 4,
  SB_NET_MAP_LOAD_ITEM = 5,
  SB_NET_MAP_SHOULD = 6,
  SB_NET_MAP_WRITE = 7,
  SB_NET_MAP_READ = 8,
  SB_NET_MAP_READ_ITEM = 9,
  SB_NET_MAP_HISTORY = 10,
  SB_NET_MAP_PENDING = 11,
  SB_NET_MAP_APPLY = 12,
  SB_NET_MAP_STORE_PENDING = 13,
  SB_NET_MAP_BASE_RECORD = 14,
  SB_NET_MAP_BASE_STORE = 15,
  SB_NET_MAP_DECREMENT_RANGE = 16,
  SB_NET_MAP_SHOULD_SCAN = 17,
  SB_NET_MAP_WRITE_SCAN = 18,
  SB_NET_MAP_INSERT = 19,
  SB_NET_MAP_ADD = 20,
  SB_NET_MAP_SET = 21,
  SB_NET_MAP_REMOVE = 22,
  SB_NET_MAP_CLEAR = 23,
  SB_NET_MAP_RESET = 24,
  SB_NET_MAP_RESET_REMOVALS = 25,
  SB_NET_MAP_RESET_SETS = 26,
  SB_NET_MAP_WRITE_CHANGE = 27,
  SB_NET_MAP_READ_TYPE = 28,
  SB_NET_MAP_RESET_REMOVE_ITEM = 29,
  SB_NET_MAP_RESET_SET_ITEM = 30,
  SB_NET_MAP_COUNT = 31
};
enum {
  SB_NET_MAP_RECORD_RANGE_OP = 0,
  SB_NET_MAP_MORE = 1,
  SB_NET_MAP_ADVANCE = 2,
  SB_NET_MAP_STORE_RANGE_OP = 3,
  SB_NET_MAP_FLUSH_PENDING = 4,
  SB_NET_MAP_RECORD_CLEAR = 5,
  SB_NET_MAP_RECORD_CURRENT_SET = 6,
  SB_NET_MAP_DECREMENT_RANGE_OP = 7,
  SB_NET_MAP_FRONT_READY = 8,
  SB_NET_MAP_APPLY_FRONT = 9,
  SB_NET_MAP_APPLY_PENDING_MOVE = 10,
  SB_NET_MAP_WRITE_SIZE = 11,
  SB_NET_MAP_WRITE_CURRENT_SET = 12,
  SB_NET_MAP_STORE_PENDING_OP = 13,
  SB_NET_MAP_WRITE_PENDING_CHANGE = 14,
  SB_NET_MAP_CLEAR_HISTORY = 15,
  SB_NET_MAP_CAPTURE_VERSION = 16,
  SB_NET_MAP_CLEAR_PENDING = 17,
  SB_NET_MAP_CLEAR_BASE = 18,
  SB_NET_MAP_READ_COUNT = 19,
  SB_NET_MAP_LOAD_ITEM_OP = 20,
  SB_NET_MAP_RECORD_ITEM = 21,
  SB_NET_MAP_APPLY_ITEM_MOVE = 22,
  SB_NET_MAP_MARK_UPDATED = 23,
  SB_NET_MAP_HISTORY_FLOOR = 24,
  SB_NET_MAP_SHOULD_SCAN_OP = 25,
  SB_NET_MAP_ENTRY_VERSION = 26,
  SB_NET_MAP_WRITE_FULL_CODE = 27,
  SB_NET_MAP_STORE_FULL = 28,
  SB_NET_MAP_WRITE_CHANGE_CODE = 29,
  SB_NET_MAP_WRITE_HISTORY_CHANGE = 30,
  SB_NET_MAP_WRITE_TERMINATOR = 31,
  SB_NET_MAP_READ_CODE = 32,
  SB_NET_MAP_LOAD_FULL = 33,
  SB_NET_MAP_READ_ITEM_OP = 34,
  SB_NET_MAP_SHOULD_QUEUE = 35,
  SB_NET_MAP_QUEUE_ITEM_MOVE = 36,
  SB_NET_MAP_THROW_CODE = 37,
  SB_NET_MAP_APPEND_HISTORY = 38,
  SB_NET_MAP_SET_HISTORY_FLOOR = 39,
  SB_NET_MAP_HISTORY_EMPTY = 40,
  SB_NET_MAP_HISTORY_BOUNDS = 41,
  SB_NET_MAP_POP_HISTORY = 42,
  SB_NET_MAP_PENDING_EARLIER = 43,
  SB_NET_MAP_APPEND_PENDING = 44,
  SB_NET_MAP_CHANGE_KIND = 45,
  SB_NET_MAP_APPLY_SET = 46,
  SB_NET_MAP_APPLY_REMOVE = 47,
  SB_NET_MAP_DECREMENT_CURRENT = 48,
  SB_NET_MAP_WRITE_SCAN_OP = 49,
  SB_NET_MAP_INSERTED = 50,
  SB_NET_MAP_RECORD_INSERTED = 51,
  SB_NET_MAP_ADD_FAILED = 52,
  SB_NET_MAP_THROW_DUPLICATE = 53,
  SB_NET_MAP_FOUND = 54,
  SB_NET_MAP_VALUE_DIFFERS = 55,
  SB_NET_MAP_RECORD_EXISTING_SET = 56,
  SB_NET_MAP_ASSIGN_EXISTING = 57,
  SB_NET_MAP_RECORD_NEW_SET = 58,
  SB_NET_MAP_INSERT_NEW = 59,
  SB_NET_MAP_ERASE_FOUND = 60,
  SB_NET_MAP_RECORD_REMOVAL = 61,
  SB_NET_MAP_NONEMPTY = 62,
  SB_NET_MAP_RESET_REMOVALS_OP = 63,
  SB_NET_MAP_RESET_SETS_OP = 64,
  SB_NET_MAP_RESET_ASSIGN = 65,
  SB_NET_MAP_RESET_MISSING = 66,
  SB_NET_MAP_RESET_CHANGED = 67,
  SB_NET_MAP_RECORD_CURRENT_REMOVE = 68,
  SB_NET_MAP_WRITE_TAG = 69,
  SB_NET_MAP_WRITE_KEY = 70,
  SB_NET_MAP_WRITE_VALUE = 71,
  SB_NET_MAP_SELECT_KIND = 72,
  SB_NET_MAP_THROW_TYPE = 73,
  SB_NET_MAP_RESET_REMOVE_ITEM_OP = 74,
  SB_NET_MAP_RESET_SET_ITEM_OP = 75,
  SB_NET_MAP_OP_COUNT = 76
};

typedef SbNetGroupReply SbNetMapReply;
typedef SbNetGroupHost SbNetMapHost;

/* Map control policy, using the existing default-OFF NET_GROUP family selector
 * and runtime. No separate selector. Native map/deque/variant storage, typed
 * values, streams, version pointers, FP operations and exception identity stay
 * in C++. Shared Group ABI: reply size=16/alignment=8, a at 0/b at 8; identical
 * host/root signature types. Rust never interprets or retains native pointers.
 *
 * Root arguments: SHOULD/WRITE/SHOULD_SCAN/WRITE_SCAN accept any u64 fromVersion;
 * READ_TYPE accepts any u8 (0..255); every other mode requires zero. Only those
 * four version roots and REMOVE return booleans (0/1); every other successful
 * root writes zero. INVALID=1, HOST_ERROR=2, PANIC=3
 * never write output. Validation precedes root counters and callbacks. Failure
 * preserves native prefix effects; there is no rollback or invented cleanup.
 *
 * All callbacks receive argument zero except SHOULD_SCAN_OP/WRITE_SCAN_OP,
 * which receive the root fromVersion unchanged, and WRITE_TAG/SELECT_KIND,
 * which receive kind 0..2. Replies are zero-initialized.
 * Strict boolean replies (a<=1,b=0): MORE, FRONT_READY, SHOULD_SCAN_OP,
 * SHOULD_QUEUE, HISTORY_EMPTY, PENDING_EARLIER, WRITE_SCAN_OP, INSERTED,
 * ADD_FAILED, FOUND, VALUE_DIFFERS, NONEMPTY, RESET_MISSING, RESET_CHANGED.
 * Scalar replies (any a,b=0): READ_COUNT, HISTORY_FLOOR, ENTRY_VERSION, READ_CODE.
 * HISTORY_BOUNDS permits any a,b (front version,current floor).
 * CHANGE_KIND requires a<=2,b=0. All other replies require a=b=0.
 * Host status 2 propagates; any status other than 0/2 is INVALID. A successful
 * malformed reply is INVALID. A throwing leaf must report HOST_ERROR, not OK.
 *
 * INIT: BEFORE entry native code assigns version, clears history, sets last=0.
 * FLUSH_PENDING, RECORD_CLEAR, RECORD_RANGE_OP. RECORD_CLEAR performs the whole
 * typed addChangeData(ClearChange()); RECORD_RANGE_OP scopes BASE_RECORD.
 * FLUSH: BEFORE entry native code owns Star::take(pending), caches begin/end.
 * While MORE: APPLY_PENDING_MOVE, ADVANCE. Whole native applyChange of moved
 * change.second is retained. Reentrant additions to the new pending queue are
 * not visited. BASE_RECORD/BASE_STORE/STORE_PENDING/DECREMENT_RANGE have the same
 * loop with RECORD_CURRENT_SET/WRITE_CURRENT_SET/WRITE_PENDING_CHANGE/
 * DECREMENT_CURRENT respectively. Their native lexical ranges are created
 * BEFORE subroot entry and destroyed AFTER subroot return; no ENTER/LEAVE ops,
 * optional iterator, pair iterator, reset, or replacement ownership mechanism.
 * Native per-body const& bindings and exact typed/braced expressions stay in
 * their callback bodies. Failure returns before native scope destruction and
 * captured exception rethrow, without artificial iterator callbacks.
 *
 * TICK: DECREMENT_RANGE_OP (native scopes DECREMENT_RANGE), then while
 * FRONT_READY: APPLY_FRONT. FRONT_READY retains the entire native
 * !empty && first().first<=0.0f expression, APPLY_FRONT retains the whole
 * applyChange(pending.takeFirst().second) expression. FP stays native.
 * STORE: WRITE_SIZE (whole native BaseMap::size()+pending.size()),
 * STORE_RANGE_OP (native scopes BASE_STORE), STORE_PENDING_OP (native scopes
 * STORE_PENDING). No count or typed payload conversion through Rust.
 * LOAD: CLEAR_HISTORY, CAPTURE_VERSION, CLEAR_PENDING, CLEAR_BASE, RECORD_CLEAR,
 * READ_COUNT; exactly count LOAD_ITEM_OP callbacks; MARK_UPDATED. LOAD_ITEM_OP
 * owns auto change=readChange(ds) BEFORE nesting LOAD_ITEM: RECORD_ITEM copies
 * change into addChangeData, then APPLY_ITEM_MOVE applies std::move(change).
 * Native factories, typed parameter owners and destruction order are retained.
 *
 * SHOULD: if fromVersion<HISTORY_FLOOR return true, otherwise return
 * SHOULD_SCAN_OP(fromVersion). Native scan scope wraps SHOULD_SCAN: while MORE,
 * if ENTRY_VERSION>=fromVersion return true WITHOUT ADVANCE; otherwise ADVANCE.
 * Exhaustion returns false. WRITE: if fromVersion<HISTORY_FLOOR,
 * WRITE_FULL_CODE (vlq 1), STORE_FULL, written=true; otherwise written is
 * WRITE_SCAN_OP(fromVersion). If written, WRITE_TERMINATOR (vlq 0). Return
 * written. Native WRITE_SCAN_OP owns its lexical range through WRITE_SCAN and
 * destroys it BEFORE the outer terminator. WRITE_SCAN: while MORE, if
 * ENTRY_VERSION>=fromVersion, written=true, WRITE_CHANGE_CODE (vlq 2),
 * WRITE_HISTORY_CHANGE; ADVANCE. Return written. No forced advance on failure.
 * STORE_FULL retains unqualified native netStore(ds,rules), including its rule
 * recheck; outer native public-method compatibility guards precede entry.
 *
 * READ: loop READ_CODE; 0 stops; 1 LOAD_FULL then CONTINUE; 2 READ_ITEM_OP;
 * otherwise THROW_CODE (original IOException). LOAD_FULL retains native
 * netLoad(ds,rules). READ_ITEM_OP owns its native change variant scope, nesting
 * READ_ITEM: RECORD_ITEM copies history, then SHOULD_QUEUE retains the entire
 * native enabled && interpolationTime>0.0f expression; true QUEUE_ITEM_MOVE
 * calls addPendingChangeData(std::move(change),time), false APPLY_ITEM_MOVE.
 * No extra trailing-data validation or full-load early return is introduced.
 *
 * HISTORY: BEFORE entry native currentVersion capture and monotonic starAssert.
 * APPEND_HISTORY is the whole native append({currentVersion,std::move(change)}).
 * SET_HISTORY_FLOOR retains the original signed max<int64_t>((int64_t)version -
 * 100,0) expression and domain. Then while !HISTORY_EMPTY: HISTORY_BOUNDS;
 * if a>=b stop, else POP_HISTORY. No Rust arithmetic, domain repair or loop cap.
 * PENDING: if PENDING_EARLIER (native !empty && time<last.first), FLUSH_PENDING;
 * APPEND_PENDING. No recheck after a reentrant flush. APPEND_PENDING retains
 * the whole native append({interpolationTime,std::move(change)}) expression.
 * APPLY: CHANGE_KIND (0 set,1 remove,2 clear), APPLY_SET/APPLY_REMOVE/CLEAR_BASE,
 * MARK_UPDATED. Native variant pointer selection, whole typed move calls and
 * parameter lifetimes remain native.
 *
 * INSERT: BEFORE entry native auto res=BaseMap::insert(v) uses the named lvalue
 * v (copy, not move); res/v and return conversion outlive Rust. If INSERTED,
 * RECORD_INSERTED performs addChangeData(SetChange{move(v.first),move(v.second)})
 * then MARK_UPDATED. ADD: ADD_FAILED evaluates the WHOLE original native
 * if(!insert(value_type(move(k),move(v))).second) expression. If true,
 * THROW_DUPLICATE throws original MapException::format with outputAny(k),
 * including the already-moved k state. A claimed successful throw is INVALID.
 * SET: native auto i=BaseMap::find(k) BEFORE entry. If FOUND (whole native
 * i!=BaseMap::end()), then if VALUE_DIFFERS (whole native !(i->second==v),
 * including proxy temporary destruction before callback return),
 * RECORD_EXISTING_SET (SetChange{move(k),v}), ASSIGN_EXISTING (i->second=move(v)),
 * MARK_UPDATED. Missing: RECORD_NEW_SET (SetChange{k,v}), INSERT_NEW (whole
 * BaseMap::insert(value_type(move(k),move(v)))), MARK_UPDATED. No predicate
 * rechecks, extra typed copies, equality conversions or alias repair.
 * REMOVE: native find scope BEFORE entry. If FOUND: ERASE_FOUND,
 * RECORD_REMOVAL (RemoveChange{k}), MARK_UPDATED, return true; else false.
 * Erasure precedes history copy even on failure; no key-alias/domain repair.
 * CLEAR: NONEMPTY retains whole native if(!empty()); if true, RECORD_CLEAR,
 * MARK_UPDATED, CLEAR_BASE, in that order.
 *
 * RESET: native by-value BaseMap values parameter stays live throughout.
 * RESET_REMOVALS_OP owns the original this-range and nests RESET_REMOVALS;
 * RESET_SETS_OP owns the values-range and nests RESET_SETS; then RESET_ASSIGN
 * performs the whole BaseMap::operator=(move(values)). Both range roots loop
 * while MORE: RESET_REMOVE_ITEM_OP/RESET_SET_ITEM_OP respectively, ADVANCE.
 * Each item callback owns const& p=*iterator through the nested item root;
 * RESET_SET_ITEM additionally captures native auto v=ptr(p.first) BEFORE entry.
 * RESET_REMOVE_ITEM: if RESET_MISSING (whole !values.contains(p.first)),
 * RECORD_CURRENT_REMOVE (RemoveChange{p.first}), MARK_UPDATED.
 * RESET_SET_ITEM: if RESET_CHANGED (whole !v||!(*v==p.second)),
 * RECORD_CURRENT_SET (SetChange{p.first,p.second}), MARK_UPDATED. Iterator and
 * per-item/pointer/proxy scopes remain native and close AFTER their subroots,
 * without an optional/pair/extra iterator move. No delayed predicate recheck.
 *
 * WRITE_CHANGE: CHANGE_KIND caches native const SetChange/RemoveChange pointers
 * before any write, returning 0/1/2. WRITE_TAG(kind), if kind<2 WRITE_KEY,
 * if kind==0 WRITE_VALUE. Typed DataStream calls/full-expressions stay native.
 * READ_TYPE: native uint8_t t=ds.read<uint8_t>() BEFORE entry. If argument<3,
 * SELECT_KIND(argument), otherwise THROW_TYPE throws original IOException
 * (successful throwing callback is INVALID). Native code captures selected kind
 * then structurally dispatches ORIGINAL scoped SetChange/RemoveChange locals,
 * reads and return sc/rc/ClearChange(), preserving default construction, NRVO,
 * conversions and copy/move timing. No Rust ElementChange or extra result move.
 * Tag control is NOT typed storage or codec retirement. Public push/erase/take/
 * maybeTake stay untouched, including unsupported C++17 aggregate-paren domains.
 * Old modes 0..18/leaves 0..49, signatures and query prefixes stay unchanged.
 *
 * Safety: nonnull live ctx and host; aligned writable u32 output; all borrowed
 * native captures remain live throughout synchronous callbacks/reentry. Host
 * must never unwind through Rust: capture std::exception_ptr, return 2, rethrow
 * only after Rust returns. No Rust panic may cross this ABI (internal barrier).
 */
uint32_t sb_net_map_run(uint32_t mode, void* ctx, SbNetMapHost host,
    uint64_t argument, uint32_t* out_result);
/* kind 0: thread-local accepted roots; 1: process-wide accepted roots;
 * 2: process-wide attempted leaves. Relaxed/wrapping diagnostics, not atomic
 * snapshots, completion/performance evidence or unique-consumer counts.
 * Unknown kind/index returns zero. No reset API. */
uint64_t sb_net_map_count(uint32_t kind, uint32_t index);

#ifdef __cplusplus
}
#endif
#endif
