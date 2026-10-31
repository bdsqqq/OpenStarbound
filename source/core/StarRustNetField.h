#ifndef STAR_RUST_NET_FIELD_H
#define STAR_RUST_NET_FIELD_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_NET_FIELD_OK = 0,
  SB_NET_FIELD_INVALID = 1,
  SB_NET_FIELD_HOST_ERROR = 2,
  SB_NET_FIELD_PANIC = 3
};
enum {
  SB_NET_FIELD_SET = 0,
  SB_NET_FIELD_PUSH = 1,
  SB_NET_FIELD_UPDATE = 2,
  SB_NET_FIELD_ENABLE = 3,
  SB_NET_FIELD_DISABLE = 4,
  SB_NET_FIELD_TICK = 5,
  SB_NET_FIELD_STORE = 6,
  SB_NET_FIELD_LOAD = 7,
  SB_NET_FIELD_WRITE = 8,
  SB_NET_FIELD_READ = 9,
  SB_NET_FIELD_COUNT = 10
};
enum {
  SB_NET_FIELD_CHANGED = 0,
  SB_NET_FIELD_PUSH_COPY = 1,
  SB_NET_FIELD_ASSIGN_PUSH = 2,
  SB_NET_FIELD_UPDATED = 3,
  SB_NET_FIELD_SET_LATEST = 4,
  SB_NET_FIELD_HAS_PENDING = 5,
  SB_NET_FIELD_CLEAR_PENDING = 6,
  SB_NET_FIELD_MUTATE = 7,
  SB_NET_FIELD_EMPLACE_PENDING = 8,
  SB_NET_FIELD_PENDING_NONEMPTY = 9,
  SB_NET_FIELD_ASSIGN_LAST = 10,
  SB_NET_FIELD_RESET_PENDING = 11,
  SB_NET_FIELD_ENTER_RANGE = 12,
  SB_NET_FIELD_MORE = 13,
  SB_NET_FIELD_DECREMENT = 14,
  SB_NET_FIELD_ADVANCE = 15,
  SB_NET_FIELD_LEAVE_RANGE = 16,
  SB_NET_FIELD_NEXT_READY = 17,
  SB_NET_FIELD_ASSIGN_FIRST = 18,
  SB_NET_FIELD_WRITE_LAST = 19,
  SB_NET_FIELD_WRITE_VALUE = 20,
  SB_NET_FIELD_READ_VALUE = 21,
  SB_NET_FIELD_LATEST_VERSION = 22,
  SB_NET_FIELD_READ_INCOMING = 23,
  SB_NET_FIELD_ACCEPT_DELAY = 24,
  SB_NET_FIELD_APPEND_INCOMING = 25,
  SB_NET_FIELD_ASSIGN_INCOMING = 26,
  SB_NET_FIELD_LAST_AVAILABLE = 27,
  SB_NET_FIELD_OP_COUNT = 28
};

typedef struct SbNetFieldReply {
  uint64_t a;
  uint64_t b;
} SbNetFieldReply;

/* NetElementBasicField control policy only. Native C++ owns T, Maybe/Deque,
 * DataStream, all iterators, typed temporaries and exception identity. Reply ABI
 * is size 16/alignment 8, a at 0 and b at 8. Rust never dereferences ctx and
 * retains no native reference or borrow across a callback. All leaf arguments
 * are zero. All floating-point expressions remain WHOLE native expressions;
 * no timer or floating-point value crosses this ABI.
 *
 * SET: CHANGED (the whole !(m_value == value)); if true PUSH_COPY owns the
 * whole push(value), including by-value typed parameter copy and nested PUSH.
 * PUSH: ASSIGN_PUSH (m_value = std::move(value)), UPDATED, SET_LATEST,
 * HAS_PENDING, and if true CLEAR_PENDING. UPDATE: MUTATE (whole mutator call);
 * if true UPDATED, SET_LATEST, HAS_PENDING, and if true CLEAR_PENDING.
 * SET_LATEST owns m_latestUpdateVersion = m_netVersion ? current() : 0.
 * UPDATED is virtual: do not cache version or pending state across it.
 * ENABLE: HAS_PENDING; if false EMPLACE_PENDING. DISABLE: HAS_PENDING; if
 * true PENDING_NONEMPTY; if true ASSIGN_LAST; then RESET_PENDING. ASSIGN_LAST
 * owns the exact m_value = m_pendingInterpolatedValues->takeLast().second
 * full-expression, including pop before assignment failure. No UPDATED or
 * version write on disable.
 *
 * TICK: HAS_PENDING; if true ENTER_RANGE; while MORE, DECREMENT then ADVANCE;
 * LEAVE_RANGE; while NEXT_READY, ASSIGN_FIRST then UPDATED. ENTER_RANGE owns
 * original cached native range setup; MORE tests cached end. DECREMENT owns
 * the whole p.first -= dt expression. NEXT_READY owns the whole
 * !m_pendingInterpolatedValues->empty() &&
 * m_pendingInterpolatedValues->first().first <= 0.0f expression and ASSUMES
 * engaged pending, exactly like the original loop: NO extra engagement check
 * after virtual UPDATED. ASSIGN_FIRST owns the exact
 * m_value = m_pendingInterpolatedValues->takeFirst().second full-expression.
 * All timers decrement before any assignment/update. No caching/rechecking
 * can repair native iterator or pending invalidation caused by user callbacks.
 * Native frames clean up active ranges after error return, without extra leaves.
 *
 * STORE: LAST_AVAILABLE ? WRITE_LAST : WRITE_VALUE. LAST_AVAILABLE owns the
 * whole Maybe-engaged && !empty predicate. PENDING_NONEMPTY instead assumes
 * engagement. WRITE_LAST/WRITE_VALUE own whole original writeData expressions.
 * LOAD: READ_VALUE, SET_LATEST, UPDATED, HAS_PENDING/if true CLEAR_PENDING.
 * Note SET_LATEST is BEFORE UPDATED here, unlike PUSH/UPDATE.
 * WRITE: LATEST_VERSION; if a < from_version return result 0 WITHOUT any
 * storage query. Otherwise STORE sequence, result 1 (inclusive cutoff).
 * READ: READ_INCOMING, SET_LATEST, HAS_PENDING. If true ACCEPT_DELAY owns the
 * whole interpolationTime > 0.0f && (pending->empty() ||
 * interpolationTime >= pending->last().first) predicate. If accepted,
 * APPEND_INCOMING owns append({interpolationTime, std::move(t)}), NO UPDATED.
 * Otherwise ASSIGN_INCOMING, CLEAR_PENDING, UPDATED. If HAS_PENDING was false,
 * ASSIGN_INCOMING, UPDATED, with no clear. The native T t lexical scope MUST
 * surround READ run, including deserialization and destruction after errors.
 * Native checkWithRules guards stay BEFORE STORE/LOAD/WRITE/READ entry.
 * All successful modes write result 0 except eligible WRITE writes 1.
 *
 * CHANGED/HAS_PENDING/MUTATE/PENDING_NONEMPTY/MORE/NEXT_READY/ACCEPT_DELAY/
 * LAST_AVAILABLE return strict a=0 or 1,b=0. LATEST_VERSION accepts all u64 a,
 * b=0. All other leaves return a=b=0. Each reply starts zeroed. Only host
 * status OK or HOST_ERROR is accepted: HOST_ERROR wins over malformed reply;
 * every other status or malformed successful reply returns INVALID. Stop
 * immediately on error, preserve out_written and all native partial effects;
 * never issue rollback, cleanup or repair leaves. Catch ALL native exceptions
 * within host, save exception_ptr, return HOST_ERROR and rethrow only after
 * Rust returns. Neither foreign exceptions nor callback panics may unwind
 * through this ABI. The Rust panic barrier returns PANIC only for Rust panics.
 *
 * mode>=COUNT, null ctx/host/output, output not aligned to 4, or nonzero
 * from_version except WRITE returns INVALID BEFORE barrier/counters/callbacks/
 * writes. WRITE accepts every u64. Pointer checks cannot prove liveness or
 * provenance: native context/output/captures must remain valid through the
 * synchronous call and reentry; output must be writable aligned uint32_t.
 * Reentry is permitted only where native operations themselves permit it.
 */
typedef uint32_t (*SbNetFieldHost)(void* ctx, uint32_t leaf,
    uint64_t argument, SbNetFieldReply* out_reply);
uint32_t sb_net_field_run(uint32_t mode, void* ctx, SbNetFieldHost host,
    uint64_t from_version, uint32_t* out_written);

/* Wrapping diagnostics: kind 0=current-thread accepted root entries (index<10),
 * kind 1=relaxed all-thread accepted roots (index<10), kind 2=relaxed all-thread
 * ATTEMPTED leaves (index<28), counted BEFORE host. Accepted failures count;
 * rejected entries do not. Invalid queries return 0; no reset API. Independent
 * loads are not synchronized snapshots, completion or performance evidence.
 */
uint64_t sb_net_field_count(uint32_t kind, uint32_t index);

#ifdef __cplusplus
}
static_assert(sizeof(SbNetFieldReply) == 16, "SbNetFieldReply ABI size");
static_assert(alignof(SbNetFieldReply) == 8, "SbNetFieldReply ABI alignment");
#endif

#endif
