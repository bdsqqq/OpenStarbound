#ifndef STAR_RUST_NET_SIGNAL_H
#define STAR_RUST_NET_SIGNAL_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_NET_SIGNAL_OK = 0,
  SB_NET_SIGNAL_INVALID = 1,
  SB_NET_SIGNAL_HOST_ERROR = 2,
  SB_NET_SIGNAL_PANIC = 3
};
enum {
  SB_NET_SIGNAL_SEND = 0,
  SB_NET_SIGNAL_RECEIVE = 1,
  SB_NET_SIGNAL_WRITE = 2,
  SB_NET_SIGNAL_READ = 3,
  SB_NET_SIGNAL_READ_ITEM = 4,
  SB_NET_SIGNAL_FLUSH = 5,
  SB_NET_SIGNAL_TICK = 6,
  SB_NET_SIGNAL_COUNT = 7
};
enum {
  SB_NET_SIGNAL_APPEND_SIGNAL = 0,
  SB_NET_SIGNAL_QUEUE_LIMIT = 1,
  SB_NET_SIGNAL_POP_FRONT = 2,
  SB_NET_SIGNAL_ENTER_RANGE = 3,
  SB_NET_SIGNAL_MORE = 4,
  SB_NET_SIGNAL_RECEIVED = 5,
  SB_NET_SIGNAL_APPEND_RECEIVED = 6,
  SB_NET_SIGNAL_MARK_RECEIVED = 7,
  SB_NET_SIGNAL_ADVANCE = 8,
  SB_NET_SIGNAL_LEAVE_RANGE = 9,
  SB_NET_SIGNAL_WRITE_HEADER = 10,
  SB_NET_SIGNAL_WRITE_SIGNAL = 11,
  SB_NET_SIGNAL_VERSION = 12,
  SB_NET_SIGNAL_READ_ITEM_OP = 13,
  SB_NET_SIGNAL_INTERPOLATING = 14,
  SB_NET_SIGNAL_NEEDS_FLUSH = 15,
  SB_NET_SIGNAL_FLUSH_PENDING = 16,
  SB_NET_SIGNAL_APPEND_PENDING = 17,
  SB_NET_SIGNAL_EMIT_READ = 18,
  SB_NET_SIGNAL_DECREMENT_TIME = 19,
  SB_NET_SIGNAL_NEXT_PENDING_READY = 20,
  SB_NET_SIGNAL_EMIT_PENDING_FRONT = 21,
  SB_NET_SIGNAL_EMIT_PENDING_MOVE = 22,
  SB_NET_SIGNAL_OP_COUNT = 23
};

typedef struct SbNetSignalReply {
  uint64_t a;
  uint64_t b;
} SbNetSignalReply;

/* Optional policy bridge, selected by STAR_USE_RUST_NET_SIGNAL (default OFF in
 * the parent build). No new runtime is introduced; policy runs in Rust while
 * ALL floating-point expressions remain native (including whole predicates)
 * to preserve native compiler/fast-math behavior. ABI: SbNetSignalReply is
 * size 16, alignment 8, a at 0 and b at 8.
 *
 * Native C++ retains Signal, Deque, List, iterators, DataStream, typed copies,
 * temporaries and exception identity. Each leaf executes the WHOLE original
 * hard-typed full-expression so overload resolution, copy/destructor timing,
 * lifetimes and partial mutations remain native. In particular APPEND_SIGNAL
 * owns append({netVersion ? netVersion->current() : 0, signal, false}); retain
 * the named lvalue signal (not an extra move). POP_FRONT owns removeFirst(),
 * including signal destruction before returning. Native send's by-value signal
 * and receive's result List remain in their original native scopes.
 *
 * SEND: APPEND_SIGNAL; repeatedly QUEUE_LIMIT (a=size, b=maxSignalQueue), and
 * while a>b POP_FRONT. BOTH values are queried afresh at EVERY guard: a signal
 * destructor can reenter and change the cap. Neither value may be cached.
 * SEND writes result 0.
 *
 * RECEIVE: ENTER_RANGE; while MORE, query RECEIVED; if false APPEND_RECEIVED
 * then MARK_RECEIVED; ADVANCE; finally LEAVE_RANGE. APPEND_RECEIVED owns the
 * original received.append(p.signal) full-expression. Mark ONLY after that
 * succeeds: a failing copy leaves that flag false, prior flags and the copied
 * prefix intact. No rollback or repair callbacks. RECEIVE writes result 0.
 *
 * WRITE: native checkWithRules(rules) MUST stay before entry, untouched.
 * ENTER_RANGE; while MORE, VERSION, count if version>=from_version, ADVANCE;
 * LEAVE_RANGE. Count uses wrapping native size_t (Rust usize). If zero, return
 * result 0 without header or second range. Otherwise WRITE_HEADER(argument =
 * count converted to uint64_t), then ENTER_RANGE AGAIN; while MORE, VERSION,
 * if version>=from_version WRITE_SIGNAL, then ADVANCE; LEAVE_RANGE; result 1.
 * These are two separate native range-for scopes: each ENTER_RANGE initializes
 * its iterator and CACHED end exactly once. The second scope starts AFTER the
 * header full-expression completes, not from cached first-pass state. Header
 * or signal writes keep any stream prefix on failure. WRITE_SIGNAL owns the
 * complete ds.write(p.signal); WRITE_HEADER owns ds.writeVlqU(numToWrite).
 * VERSION exposes the full uint64_t, including UINT64_MAX; comparison is >=.
 *
 * READ: from_version is the count, ALREADY cast from ds.readVlqU() to size_t
 * by native C++ before entry. Invoke READ_ITEM_OP once per item, in order.
 * Each callback owns the WHOLE lexical { Signal s; ds.read(s); nested
 * READ_ITEM capturing s; } scope. The Signal destructor runs before the next
 * READ_ITEM_OP, also on failure. READ itself never owns a Signal or timer.
 *
 * READ_ITEM: INTERPOLATING returns the WHOLE native boolean expression
 * m_netInterpolationEnabled && interpolationTime > 0.0. If true, NEEDS_FLUSH
 * returns the WHOLE !m_pendingSignals.empty() &&
 * m_pendingSignals.last().first > interpolationTime expression. If true,
 * FLUSH_PENDING owns the C++ helper with auto&& pending = take(m_pendingSignals),
 * its temporary-owned scope and cached native iterators, then nested FLUSH.
 * Only after that succeeds, APPEND_PENDING owns the whole
 * append({interpolationTime, std::move(s)}) expression. If INTERPOLATING is
 * false, EMIT_READ owns the whole send(std::move(s)) expression instead.
 *
 * FLUSH: native-owned pending range and cached iterators MUST exist BEFORE
 * entry. While MORE, EMIT_PENDING_MOVE owns send(std::move(iter->second)),
 * then ADVANCE. NO ENTER_RANGE or LEAVE_RANGE: the owning C++ scope destroys
 * the taken pending and iterators AFTER Rust returns, on success OR error.
 * A nested send may change the member pending queue, not this captured take.
 *
 * TICK: ENTER_RANGE initializes the native pending cached range; while MORE,
 * DECREMENT_TIME owns the whole p.first -= dt native FP expression, then
 * ADVANCE; LEAVE_RANGE. Only THEN repeatedly NEXT_PENDING_READY (the WHOLE
 * native !m_pendingSignals.empty() && m_pendingSignals.first().first <= 0.0f)
 * and, while true, EMIT_PENDING_FRONT owns the exact prvalue expression
 * send(m_pendingSignals.takeFirst().second). ALL timers decrement BEFORE any
 * due emission. Rust never receives or computes floating-point values.
 * READ/READ_ITEM/FLUSH/TICK write result 0. Existing native version reset and
 * pending queue lifecycle remain unchanged; no extra reset/rollback is added.
 *
 * ENTER_RANGE/LEAVE_RANGE control successful-path scopes, not exception cleanup.
 * Native frames must destroy any active iterator/range scope on error after run
 * returns without invoking additional policy leaves. MORE reads the cached end;
 * ADVANCE follows only a successful body. There is no artificial iteration cap.
 *
 * Every callback gets fresh zeroed reply storage. MORE, RECEIVED,
 * INTERPOLATING, NEEDS_FLUSH and NEXT_PENDING_READY require a exactly 0/1,
 * b=0. VERSION accepts every a, b=0. QUEUE_LIMIT accepts every a and b. ALL other leaves require a=b=0. Only WRITE_HEADER has a nonzero
 * argument; all other arguments are 0. Host status must be OK or HOST_ERROR:
 * HOST_ERROR wins over malformed reply; any other status is INVALID. Bad reply
 * or status stops immediately: no further leaf, no output write. Only success
 * writes uint32_t 0/1; errors preserve native partial side effects.
 *
 * Catch EVERY native exception inside the callback, save it in the native
 * frame, return HOST_ERROR, and rethrow only AFTER Rust returns. No exception
 * or callback panic may unwind through this ABI. A caught Rust controller
 * panic returns PANIC; that barrier does not make foreign unwinds safe.
 *
 * Invalid mode>=COUNT, null context/host/output, output not aligned to 4, or
 * nonzero from_version for SEND/RECEIVE/READ_ITEM/FLUSH/TICK returns INVALID
 * before counters/callbacks/writes. WRITE accepts every uint64_t from_version;
 * READ accepts counts <= SIZE_MAX only (native has already cast the VLQ).
 * The existing ABI parameter name is retained; it is mode-specific. Output
 * must be live writable uint32_t storage: numerical checks cannot establish provenance or liveness. Context,
 * callback, captured native references and output must survive the synchronous
 * call including reentry. Rust never dereferences context, retains pointers or
 * holds context/output/counter-cell borrows across callbacks. Reentry is allowed
 * only where the underlying native operations permit it.
 */
typedef uint32_t (*SbNetSignalHost)(void* ctx, uint32_t leaf,
    uint64_t argument, SbNetSignalReply* out_reply);
uint32_t sb_net_signal_run(uint32_t mode, void* ctx, SbNetSignalHost host,
    uint64_t from_version, uint32_t* out_written);

/* Wrapping diagnostics: kind 0=current-thread root entries (index<COUNT=7),
 * kind 1=relaxed all-thread root entries (index<COUNT=7),
 * kind 2=relaxed all-thread ATTEMPTED leaves (index<OP_COUNT=23), incremented BEFORE
 * callback. Accepted failures/panics count; rejected entries count nothing.
 * Invalid kind/index returns 0. Independent relaxed loads do not establish a
 * synchronized snapshot or completion. No counter reset API.
 */
uint64_t sb_net_signal_count(uint32_t kind, uint32_t index);

#ifdef __cplusplus
}
static_assert(sizeof(SbNetSignalReply) == 16, "SbNetSignalReply ABI size");
static_assert(alignof(SbNetSignalReply) == 8, "SbNetSignalReply ABI alignment");
#endif

#endif
