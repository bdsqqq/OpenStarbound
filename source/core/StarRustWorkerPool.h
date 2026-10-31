#ifndef STAR_RUST_WORKER_POOL_H
#define STAR_RUST_WORKER_POOL_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_WORKER_POOL_OK = 0,
  SB_WORKER_POOL_INVALID = 1,
  SB_WORKER_POOL_HOST_ERROR = 2,
  SB_WORKER_POOL_PANIC = 3
};

enum {
  SB_WORKER_POOL_HANDLE_WAIT = 0,
  SB_WORKER_POOL_HANDLE_FINISH = 1,
  SB_WORKER_POOL_START = 2,
  SB_WORKER_POOL_STOP = 3,
  SB_WORKER_POOL_FINISH = 4,
  SB_WORKER_POOL_MARK = 5,
  SB_WORKER_POOL_SPAWN = 6,
  SB_WORKER_POOL_RUN = 7,
  SB_WORKER_POOL_COUNT = 8
};

enum {
  SB_WORKER_POOL_DONE = 0,
  SB_WORKER_POOL_NONZERO_TIMEOUT = 1,
  SB_WORKER_POOL_TIMED_WAIT = 2,
  SB_WORKER_POOL_RETHROW = 3,
  SB_WORKER_POOL_WAIT = 4,
  SB_WORKER_POOL_MARK_THREADS = 5,
  SB_WORKER_POOL_BROADCAST = 6,
  SB_WORKER_POOL_CLEAR_THREADS = 7,
  SB_WORKER_POOL_ENTER_SPAWN = 8,
  SB_WORKER_POOL_MORE = 9,
  SB_WORKER_POOL_SET_STOP = 10,
  SB_WORKER_POOL_ADVANCE = 11,
  SB_WORKER_POOL_EMPTY = 12,
  SB_WORKER_POOL_FINISH_WORK = 13,
  SB_WORKER_POOL_FINAL_UNLOCK = 14,
  SB_WORKER_POOL_STOP_POOL = 15,
  SB_WORKER_POOL_BROADCAST_LOCKED = 16,
  SB_WORKER_POOL_SHOULD_STOP = 17,
  SB_WORKER_POOL_WAIT_WORK = 18,
  SB_WORKER_POOL_RUN_WORK = 19,
  SB_WORKER_POOL_APPEND_THREAD = 20,
  SB_WORKER_POOL_OP_COUNT = 21
};

/* Rust owns branch/loop policy ONLY. Native C++ owns storage, OS threads,
 * mutexes, condition variables, atomics, std::function copies/destruction and
 * exception identity. No engine locations, lock guards or jobs cross this ABI.
 * The opaque context can refer to native frames/Fn references; Rust never
 * dereferences or retains it. Frames and captured references must remain alive
 * through the whole synchronous call, including recursive entries. No Rust
 * context/output borrow is held across a callback. Reentry is allowed but does
 * not make otherwise unsafe native locking/reentrant operations valid.
 *
 * Native lock guards are constructed OUTSIDE run and remain native across it:
 * HANDLE_WAIT/HANDLE_FINISH hold the handle mutex; START/STOP hold threadMutex;
 * FINISH/RUN hold workMutex initially. Keep the original lock acquisition order.
 * Each leaf owns the WHOLE native expression/scope so that callable copies,
 * overloaded operations and destructors are not moved to Rust or extended:
 * - MARK_THREADS creates the native range, enters MARK, then destroys the range.
 *   MORE/SET_STOP/ADVANCE implement its original traversal/atomic assignment.
 * - CLEAR_THREADS owns destruction/join of native worker threads.
 * - ENTER_SPAWN initializes its native index from workerThreads.size() AFTER
 *   CLEAR_THREADS, enters SPAWN, then destroys the index scope. APPEND_THREAD
 *   constructs/appends the native WorkerThread (which starts its OS thread).
 *   MORE is tested afresh each time; ADVANCE follows each successful body only.
 * - BROADCAST is the original START broadcast WITHOUT an added work lock.
 *   BROADCAST_LOCKED owns workMutex lock/broadcast/unlock in STOP, preventing
 *   a waiting worker from missing its stop signal. Do not merge these leaves.
 * - WAIT_WORK owns waiting=true, CV wait(workMutex), waiting=false together.
 * - RUN_WORK owns pop, workLock.unlock(), work(), workLock.lock(), then native
 *   callable destruction AFTER relock. Do not destroy the callable while unlocked.
 * - FINISH_WORK owns pop, unlock, work(), Thread::yield(), lock, then callable
 *   destruction AFTER relock. FINAL_UNLOCK owns the final explicit unlock;
 *   STOP_POOL enters native stop() only AFTER that unlock.
 * These are successful-path lifetime orders, not exception repair: preserve
 * native partial side effects and guard/callable destruction on every throw.
 * Retain original named/lvalue callables and copies; no new job copies in leaves.
 *
 * HANDLE_WAIT: DONE; only if false NONZERO_TIMEOUT; only if that is true
 * TIMED_WAIT ONCE; RETHROW; DONE again, returning that exact boolean.
 * A spurious wake may return false. DONE=true skips the timeout query entirely.
 * HANDLE_FINISH: DONE; only if false WAIT ONCE; RETHROW; result 0 (no final DONE).
 * START: MARK_THREADS, BROADCAST, CLEAR_THREADS, ENTER_SPAWN; result 0.
 * STOP: MARK_THREADS, BROADCAST_LOCKED, CLEAR_THREADS; result 0.
 * FINISH: while !EMPTY, FINISH_WORK; then FINAL_UNLOCK, STOP_POOL; result 0.
 * MARK: while MORE, SET_STOP then ADVANCE; result 0.
 * SPAWN: while MORE, APPEND_THREAD then ADVANCE; result 0.
 * RUN: SHOULD_STOP; if true return 0. Otherwise EMPTY; if true WAIT_WORK.
 * Then EMPTY AGAIN; if false RUN_WORK. Repeat from SHOULD_STOP. A pending job
 * after wake executes BEFORE the next stop check even if stop was set during
 * the wait. Do NOT insert a post-wake stop check or loop within the CV wait.
 * There is no artificial iteration limit; native stop/queue predicates must
 * eventually terminate RUN/FINISH when the caller needs them to return.
 *
 * Each callback receives a fresh zero-initialized response. DONE,
 * NONZERO_TIMEOUT, MORE, EMPTY and SHOULD_STOP require exact 0/1; all other
 * operations require 0. Any nonzero host status returns HOST_ERROR, taking
 * precedence over malformed response. Otherwise malformed response returns
 * INVALID. Both stop immediately, with no later callback and no result write.
 * Native exceptions (including nonstandard ones) MUST be caught inside the
 * callback, saved in the native frame, and rethrown only AFTER run returns.
 * RETHROW tests the native stored exception; if present, catch/save it and
 * return a host error rather than unwinding through Rust. Nested errors must
 * be translated back to the owning frame without losing exception identity.
 * Neither native unwinds nor callback panics may cross this C ABI. A caught
 * Rust controller panic returns PANIC, not a guarantee about foreign unwinds.
 *
 * Invalid mode, null context/callback/output or misaligned output returns
 * INVALID BEFORE entry counts, callbacks or writes. out_result must designate
 * live writable aligned uint32_t storage. Numerical checks cannot establish
 * pointer provenance/liveness/writability; native context alignment is the
 * host's responsibility. Only success writes the full result. Errors do not
 * roll back native side effects. Context/output must not be invalidated by
 * callbacks, including nested entries. Rust retains no pointer after return.
 */
typedef uint32_t (*SbWorkerPoolLeaf)(void*, uint32_t operation, uint32_t* out_response);
uint32_t sb_worker_pool_run(uint32_t mode, void* context, SbWorkerPoolLeaf leaf, uint32_t* out_result);

/* Wrapping diagnostics: kind 0 = current-thread accepted entries, index mode;
 * kind 1 = all-thread accepted entries, index mode; kind 2 = all-thread attempted
 * leaves, index operation. Entries include host errors, malformed replies,
 * caught controller panics and nested entries; rejected calls count nothing.
 * Leaf count increments BEFORE invocation, including a failing host callback.
 * Global counters use relaxed atomics: independent loads are not a synchronized
 * snapshot or proof that work has completed. Unknown kind/index returns 0.
 */
uint64_t sb_worker_pool_count(uint32_t kind, uint32_t index);

#ifdef __cplusplus
}
#endif

#endif
