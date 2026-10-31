#ifndef STAR_RUST_JSON_RPC_H
#define STAR_RUST_JSON_RPC_H

#include "StarRustNetGroup.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_JSON_RPC_OK = 0, SB_JSON_RPC_INVALID = 1,
  SB_JSON_RPC_HOST_ERROR = 2, SB_JSON_RPC_PANIC = 3
};
enum {
  SB_JSON_RPC_REGISTER = 0, SB_JSON_RPC_REGISTER_RANGE = 1,
  SB_JSON_RPC_REMOVE = 2, SB_JSON_RPC_CLEAR = 3,
  SB_JSON_RPC_INVOKE = 4, SB_JSON_RPC_TRACK = 5,
  SB_JSON_RPC_PENDING = 6, SB_JSON_RPC_SEND = 7,
  SB_JSON_RPC_SEND_DATA = 8, SB_JSON_RPC_RECEIVE = 9,
  SB_JSON_RPC_BATCH = 10, SB_JSON_RPC_ITEM = 11,
  SB_JSON_RPC_REQUEST = 12, SB_JSON_RPC_ENQUEUE = 13, SB_JSON_RPC_COUNT = 14
};
enum {
  SB_JSON_RPC_HAS_HANDLER = 0, SB_JSON_RPC_THROW_DUPLICATE = 1,
  SB_JSON_RPC_ADD_HANDLER = 2, SB_JSON_RPC_MORE = 3,
  SB_JSON_RPC_REGISTER_CURRENT = 4, SB_JSON_RPC_ADVANCE = 5,
  SB_JSON_RPC_REMOVE_HANDLER = 6, SB_JSON_RPC_THROW_MISSING = 7,
  SB_JSON_RPC_CLEAR_HANDLERS = 8, SB_JSON_RPC_GET_ID = 9,
  SB_JSON_RPC_SET_ID = 10, SB_JSON_RPC_APPEND_REQUEST = 11,
  SB_JSON_RPC_ADD_PROMISE = 12, SB_JSON_RPC_EMPTY_PENDING = 13,
  SB_JSON_RPC_WRITE_PENDING = 14, SB_JSON_RPC_CLEAR_PENDING = 15,
  SB_JSON_RPC_EMPTY_INPUT = 16, SB_JSON_RPC_PROCESS_CURRENT = 17,
  SB_JSON_RPC_IS_REQUEST = 18, SB_JSON_RPC_HANDLE_REQUEST = 19,
  SB_JSON_RPC_IS_RESPONSE = 20, SB_JSON_RPC_HANDLE_RESPONSE = 21,
  SB_JSON_RPC_IS_FAIL = 22, SB_JSON_RPC_HANDLE_FAIL = 23,
  SB_JSON_RPC_THROW_UNKNOWN = 24, SB_JSON_RPC_APPEND_RESPONSE = 25,
  SB_JSON_RPC_OP_COUNT = 26
};

/* JsonRpc control and wrapping u64 request-ID arithmetic only. Intended
 * default-OFF selector STAR_USE_RUST_JSON_RPC (44), existing Rust runtime.
 * C++ owns typed JSON, containers, std::function, streams, typed promises and
 * iterator locals. registerHandler's function parameter remains BY VALUE;
 * invoking a handler uses the stored callable, never a copied handler. Each
 * inbound item retains its native Json by-value copy. Unsafe callable self-
 * destruction and native data races are NOT repaired or newly qualified.
 *
 * REGISTER: HAS_HANDLER ? THROW_DUPLICATE : ADD_HANDLER.
 * REGISTER_RANGE/BATCH: while MORE, REGISTER_CURRENT/PROCESS_CURRENT, ADVANCE.
 * REMOVE: HAS_HANDLER ? REMOVE_HANDLER : THROW_MISSING. CLEAR: CLEAR_HANDLERS.
 * INVOKE: GET_ID; SET_ID(old+1 wrapping); return old. ENQUEUE(argument=old):
 * APPEND_REQUEST(old). TRACK: ADD_PROMISE. C++ must keep this exact sequence:
 * id=INVOKE(); native unused JsonObject request; ENQUEUE(id); native auto
 * pair=RpcPromise<Json>::createPair(); TRACK(); return pair.first. The unused
 * request local lives from AFTER postincrement THROUGH promise creation,
 * tracking and return; do not shorten its scope, add optional ownership, or
 * transport the typed return through Rust. Append precedes promise creation.
 * PENDING/SEND: return !EMPTY_PENDING. SEND_DATA: WRITE_PENDING; CLEAR_PENDING.
 * RECEIVE: return !EMPTY_INPUT. ITEM queries IS_REQUEST, then IS_RESPONSE,
 * then IS_FAIL afresh and short-circuits to the matching HANDLE leaf; unknown
 * commands are ignored. REQUEST: HAS_HANDLER ? APPEND_RESPONSE : THROW_UNKNOWN.
 *
 * Native HANDLE_REQUEST/HANDLE_RESPONSE/HANDLE_FAIL retain their original
 * try scopes and ONLY std::exception catches/logging. A nonstandard exception
 * propagates after the Rust barrier. A fail command FULFILLS JSON null; it does
 * not fail the promise. Request failure retains the unused catch JsonObject
 * and its writes before appending fail. Command queries remain outside catches.
 * All exceptions must be caught by the immediate C++ host trampoline, saved as
 * exception_ptr and reported as nonzero; rethrow only AFTER Rust returns, so
 * native outer catch scopes decide what is handled. No C++ unwind or Rust
 * callback panic may cross this C ABI. Synchronous nested roots are allowed only
 * where native operation/lifetimes permit; Rust retains no context/callback.
 *
 * ENQUEUE accepts any u64 root argument; ALL other root arguments MUST be zero.
 * mode>=COUNT, invalid unused argument, null ctx/host/out, or output
 * not aligned to 8 reject BEFORE counters, callback, dereference or output write.
 * Caller guarantees live captures and a writable 16-byte output (size16/align8).
 * Each callback receives a fresh zero reply. HAS_HANDLER/MORE/EMPTY_PENDING/
 * EMPTY_INPUT/IS_REQUEST/IS_RESPONSE/IS_FAIL require a=0 or1,b=0. GET_ID permits
 * any a,b=0; every other successful leaf requires a=b=0. Only SET_ID and
 * APPEND_REQUEST receive a nonzero-capable argument; all other leaf args are0.
 * Any nonzero host status maps to HOST_ERROR, regardless of reply contents.
 * THROW_DUPLICATE/THROW_MISSING/THROW_UNKNOWN MUST report host failure; even
 * an OK zero reply is INVALID. Errors stop immediately, preserve output and
 * do NOT roll back native effects. Success writes zero except INVOKE's old ID
 * or PENDING/SEND/RECEIVE's boolean in a; b is always zero.
 */
uint32_t sb_json_rpc_run(uint32_t mode, void* ctx, SbNetGroupHost host,
    uint64_t argument, SbNetGroupReply* out_reply);

/* No-reset wrapping diagnostics: kind0 TLS accepted roots[14], kind1 relaxed
 * global accepted roots[14], kind2 TLS attempted leaves[26], kind3 relaxed
 * global attempted leaves[26]. Attempts count BEFORE callback; rejected roots
 * never count. Unknown kind/index returns0. Independent loads are not atomic
 * snapshots, completion barriers or performance evidence. */
uint64_t sb_json_rpc_count(uint32_t kind, uint32_t index);

#ifdef __cplusplus
}
#endif
#endif
