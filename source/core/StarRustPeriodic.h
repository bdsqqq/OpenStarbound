#ifndef STAR_RUST_PERIODIC_H
#define STAR_RUST_PERIODIC_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_PERIODIC_OK = 0,
  SB_PERIODIC_INVALID = 1,
  SB_PERIODIC_PANIC = 3
};

enum {
  SB_PERIODIC_INIT = 0,
  SB_PERIODIC_SET = 1,
  SB_PERIODIC_READY = 2,
  SB_PERIODIC_TICK = 3,
  SB_PERIODIC_COUNT = 4
};

typedef struct SbPeriodicState {
  uint32_t counter;
  uint32_t every;
} SbPeriodicState;

typedef struct SbPeriodicReply {
  SbPeriodicState state;
  uint32_t ready;
} SbPeriodicReply;

/* Fixed C ABI: State size 8/alignment 4; Reply size 12/alignment 4.
 * All uint32_t state pairs are accepted, not just reachable Periodic states.
 * Passing state BY VALUE removes input-pointer alignment/provenance and aliasing
 * requirements: no input borrow can overlap output. Rust retains no pointer or
 * native value, allocates nothing and invokes no callback.
 *
 * INIT ignores incoming state, returns {0, every}, ready 0.
 * SET ignores the old period, returns {every ? min(counter, every-1) : 0,
 * every}, ready 0. READY preserves state, returns (state.every != 0 &&
 * state.counter == 0). TICK preserves state/returns 0 when state.every is 0;
 * otherwise counter 0 becomes state.every-1/returns 1; nonzero counter is
 * decremented/returns 0. Success ready is always exactly 0 or 1.
 * READY and TICK require the separate every argument to be 0.
 *
 * Unknown operations (>= COUNT), nonzero READY/TICK every, null output and
 * output misalignment return INVALID before counting, dereferencing or writing.
 * Accepted calls require live writable aligned SbPeriodicReply storage; numeric
 * checks cannot establish provenance, liveness or writability. The whole reply
 * is computed locally and ONLY success writes output. A caught Rust panic
 * returns PANIC without changing output; accepted entries are still counted.
 * No native exception may unwind through Rust.
 *
 * The C++ wrapper commits reply.state only AFTER a successful Rust return.
 * ready() only consumes the reply boolean and need not mutate its const host.
 * tick(Function&&) invokes its named native callable AFTER committing the tick
 * state, preserving native exception identity, lvalue callability and reentry.
 * No native callable or its lifetime crosses this ABI.
 */
uint32_t sb_periodic_run(uint32_t operation, SbPeriodicState state,
    uint32_t every, SbPeriodicReply* out);

/* Accepted entries including caught panics, wrapping modulo 2^64 per operation.
 * kind 0: calling-thread totals; kind 1: independent Relaxed atomic global totals.
 * Invalid kind/operation returns 0. Rejected run calls never increment counters.
 * Global queries are not an atomic multi-operation snapshot or a state barrier.
 */
uint64_t sb_periodic_count(uint32_t kind, uint32_t operation);

#ifdef __cplusplus
}
#endif

#endif
