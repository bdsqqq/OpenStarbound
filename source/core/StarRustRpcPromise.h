#ifndef STAR_RUST_RPC_PROMISE_H
#define STAR_RUST_RPC_PROMISE_H

#include "StarRustNetGroup.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_RPC_PROMISE_OK = 0, SB_RPC_PROMISE_INVALID = 1,
  SB_RPC_PROMISE_HOST_ERROR = 2, SB_RPC_PROMISE_PANIC = 3
};
enum {
  SB_RPC_PROMISE_STORE_VALUE = 0, SB_RPC_PROMISE_STORE_ERROR = 1,
  SB_RPC_PROMISE_FINISHED = 2, SB_RPC_PROMISE_SUCCEEDED = 3,
  SB_RPC_PROMISE_FAILED = 4, SB_RPC_PROMISE_RESULT_ROUTE = 5,
  SB_RPC_PROMISE_ERROR_ROUTE = 6, SB_RPC_PROMISE_WRAP = 7,
  SB_RPC_PROMISE_AUTO_CALL = 8, SB_RPC_PROMISE_AUTO_DROP = 9,
  SB_RPC_PROMISE_COUNT = 10
};
enum {
  SB_RPC_PROMISE_DONE = 0, SB_RPC_PROMISE_THROW_FINISHED = 1,
  SB_RPC_PROMISE_ASSIGN = 2, SB_RPC_PROMISE_IS_CHAIN = 3,
  SB_RPC_PROMISE_FOLLOW = 4, SB_RPC_PROMISE_LOCAL = 5,
  SB_RPC_PROMISE_NEEDS_EVALUATION = 6, SB_RPC_PROMISE_OTHER_SUCCEEDED = 7,
  SB_RPC_PROMISE_WRAP_RESULT = 8, SB_RPC_PROMISE_OTHER_FAILED = 9,
  SB_RPC_PROMISE_COPY_ERROR = 10, SB_RPC_PROMISE_SET_DONE = 11,
  SB_RPC_PROMISE_FORWARD = 12, SB_RPC_PROMISE_AUTO_DONE = 13,
  SB_RPC_PROMISE_FAIL_DESTROYED = 14, SB_RPC_PROMISE_OP_COUNT = 15
};

/* RpcPromise POLICY only, under existing default-OFF STAR_USE_RUST_JSON_RPC
 * family44. C++ retains shared Value ownership, nonrecursive Mutex/MutexLocker,
 * typed MVariant/Maybe, factories, callables, captures and payload assignments.
 * Rust owns no native values/locks and retains no pointers or callable copies.
 *
 * STORE_VALUE/STORE_ERROR: DONE ? THROW_FINISHED : ASSIGN. Caller context
 * selects the original fulfill/fail exception message and typed move assignment.
 * FINISHED/SUCCEEDED/FAILED: IS_CHAIN ? FOLLOW : LOCAL, returning bool.
 * RESULT_ROUTE/ERROR_ROUTE: return IS_CHAIN only; C++ keeps BOTH original typed
 * return expressions, with no optional result shuttle or extra owning temporary.
 * WRAP: if NEEDS_EVALUATION, if OTHER_SUCCEEDED then WRAP_RESULT, else if
 * OTHER_FAILED then COPY_ERROR. Do not recheck entered guards. C++ keeps the full
 * valuePtr->result = wrapper(*other.result()) expression and original capture
 * order (wrapper, valuePtr, other). A throwing wrapper is retried on a later
 * getValue call; no cached error or rollback is introduced.
 * AUTO_CALL: SET_DONE then FORWARD, so done stays true even if forwarding throws.
 * AUTO_DROP: if !AUTO_DONE, FAIL_DESTROYED. Native destructor remains implicitly
 * noexcept; a rethrown failure still terminates. Do not execute death/unsafe
 * lifetime cases in ordinary fixtures.
 *
 * C++ calls getValue BEFORE acquiring the query lock, as native. Keep that lock
 * alive ACROSS Rust entry and recursive chain calls/typed return expressions.
 * Wrap's own lock likewise spans Rust and its callbacks. Native nonrecursive
 * cycles, active-callable destruction and data races are not repaired/qualified.
 * DONE preserves the contextual if (result || error) expression. FINISHED LOCAL
 * preserves the original implicit bool return expression return result || error;
 * explicit Maybe/MVariant bool conversion must not silently broaden which native
 * template instantiations compile. SUCCEEDED/FAILED keep their native expressions.
 *
 * Host trampolines catch ALL C++ exceptions, save exception_ptr and return nonOK;
 * rethrow only AFTER this entry returns. No C++ unwind or Rust callback panic may
 * cross the C ABI. Nested synchronous roots require safe native lifetimes/locks.
 * All root arguments are zero. mode>=COUNT, nonzero argument, null ctx/host/out,
 * or output not aligned to8 reject BEFORE counts/callbacks/output writes. Caller
 * guarantees live synchronous captures and writable output size16/align8.
 * Every leaf receives argument0 and a fresh zero reply. DONE/IS_CHAIN/FOLLOW/
 * LOCAL/NEEDS_EVALUATION/OTHER_SUCCEEDED/OTHER_FAILED/AUTO_DONE require strict
 * bool a=0 or1,b=0; all other successful replies require a=b=0. Any nonOK host
 * status maps to HOST_ERROR regardless of reply. THROW_FINISHED MUST return
 * nonOK; even an OK zero reply is INVALID. Errors preserve output and native
 * partial state, with no rollback. Success returns bool in a for modes2..6 only;
 * all other a and every b are zero.
 */
uint32_t sb_rpc_promise_run(uint32_t mode, void* ctx, SbNetGroupHost host,
    uint64_t argument, SbNetGroupReply* out_reply);

/* Wrapping/no-reset diagnostics: kind0 TLS roots[10], kind1 relaxed global
 * roots[10], kind2 TLS attempted leaves[15], kind3 relaxed global attempts[15].
 * Accepted roots count before dispatch; attempts count before callback. Invalid
 * roots never count. Unknown kind/index returns0. Not atomic snapshots, completion
 * barriers, ownership evidence or performance measurements. */
uint64_t sb_rpc_promise_count(uint32_t kind, uint32_t index);

#ifdef __cplusplus
}
#endif
#endif
