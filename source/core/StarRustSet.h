#ifndef STAR_RUST_SET_H
#define STAR_RUST_SET_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_SET_OK = 0,
  SB_SET_INVALID = 1,
  SB_SET_HOST_ERROR = 2,
  SB_SET_PANIC = 3
};

enum {
  SB_SET_ADD_RANGE = 0,
  SB_SET_REMOVE_RANGE = 1,
  SB_SET_VALUES = 2,
  SB_SET_INTERSECTION = 3,
  SB_SET_DIFFERENCE = 4,
  SB_SET_PRINT = 5,
  SB_SET_ASSIGN = 6,
  SB_SET_ANY = 7,
  SB_SET_SCOPED_RANGE = 8,
  SB_SET_COUNT = 9
};

enum {
  SB_SET_MORE = 0,
  SB_SET_ADVANCE = 1,
  SB_SET_ADD = 2,
  SB_SET_REMOVE = 3,
  SB_SET_APPEND_COPY = 4,
  SB_SET_CONTAINS = 5,
  SB_SET_ADD_RESULT = 6,
  SB_SET_SEPARATOR_NEEDED = 7,
  SB_SET_SEPARATOR = 8,
  SB_SET_PRINT_VALUE = 9,
  SB_SET_SELF = 10,
  SB_SET_CLEAR = 11,
  SB_SET_ENTER_ADD_RANGE = 12,
  SB_SET_BODY = 13
};

/* The host owns all values, storage, native temporaries and iterator lifetimes.
 * Each callback gets a fresh zero-initialized response: MORE, CONTAINS,
 * SEPARATOR_NEEDED and SELF must return exact 0/1; all other responses must be 0.
 * Any nonzero callback status stops immediately with HOST_ERROR, taking
 * precedence over malformed responses (INVALID). No later leaf is called.
 * The host must catch native exceptions and rethrow only after run returns;
 * no exception may unwind through Rust. Raw opaque contexts permit reentry,
 * but the host must preserve native scopes and translate nested errors.
 *
 * ADD_RANGE/REMOVE_RANGE/VALUES dispatch ADD/REMOVE/APPEND_COPY per element.
 * INTERSECTION/DIFFERENCE test CONTAINS and conditionally call ADD_RESULT.
 * PRINT tests SEPARATOR_NEEDED, optionally emits SEPARATOR, then PRINT_VALUE;
 * opening/closing delimiters stay native. Each iteration starts with MORE and
 * ends with ADVANCE. ASSIGN instead calls SELF and, unless self, CLEAR then
 * ENTER_ADD_RANGE, which creates the native iterator frame AFTER clear and
 * reenters ADD_RANGE. ANY tests MORE then CONTAINS; true returns 1 immediately
 * WITHOUT ADVANCE or any further callback, false advances; exhaustion returns 0.
 * SCOPED_RANGE calls MORE, BODY, ADVANCE per element; BODY owns native scopes.
 * There is no loop bound, retained context, allocation or native value in Rust.
 *
 * out_result must designate live writable aligned uint32_t storage. Bad mode,
 * null context/callback/output or misalignment returns INVALID before invoking
 * the host, writing output or counting. Only success writes output: ANY writes
 * its boolean result, all other modes write 0. Errors leave output unchanged;
 * native side effects of already completed callbacks are not rolled back.
 * Caught Rust panics return PANIC. Numeric checks cannot prove pointer liveness.
 */
typedef uint32_t (*SbSetLeaf)(void*, uint32_t, uint32_t*);
uint32_t sb_set_run(uint32_t mode, void* context, SbSetLeaf leaf, uint32_t* out_result);

/* Per-thread wrapping accepted-entry counts, including host failures, malformed
 * responses and panics. Reentry counts separately. Shared with the legacy
 * ordered-set prefix views; not a count of distinct consumers or containers.
 * Rejected calls do not count; mode >= COUNT queries return zero.
 */
uint64_t sb_set_count(uint32_t mode);

enum {
  SB_SET_SELECT_INSERT = 0,
  SB_SET_SELECT_REMOVE = 1,
  SB_SET_SELECT_NONEMPTY = 2,
  SB_SET_SELECT_INDEX = 3,
  SB_SET_SELECT_OPTIONAL = 4,
  SB_SET_SELECT_FILTER_INTERSECTION = 5,
  SB_SET_SELECT_FILTER_DIFFERENCE = 6,
  SB_SET_SELECT_COUNT = 7
};

enum {
  SB_SET_ACTION_EXISTING = 0,
  SB_SET_ACTION_NEW = 1,
  SB_SET_ACTION_ERASE = 2,
  SB_SET_ACTION_MISS = 3,
  SB_SET_ACTION_THROW = 4,
  SB_SET_ACTION_CONTINUE = 5,
  SB_SET_ACTION_EMPTY = 6,
  SB_SET_ACTION_DISTANCE = 7,
  SB_SET_ACTION_VALUE = 8
};

/* Native comparisons use contextual bool conversion before entry. INSERT,
 * REMOVE and INDEX take FOUND; NONEMPTY and OPTIONAL take EMPTY; filters take
 * CONTAINS. Predicates must be exact 0/1.
 * INSERT: true EXISTING / false NEW; REMOVE: true ERASE / false MISS;
 * NONEMPTY: true THROW / false CONTINUE; INDEX: true DISTANCE / false EMPTY;
 * OPTIONAL: true EMPTY / false VALUE;
 * FILTER_INTERSECTION: true VALUE / false EMPTY;
 * FILTER_DIFFERENCE: true EMPTY / false VALUE.
 * Native switches materialize typed prvalues/references/iterators/exceptions
 * after selection, preserving original lifetime/return scopes without extra
 * value slots or foreign exception unwinding. Selection allocates nothing.
 * out_action must be live writable aligned uint32_t storage. Invalid mode,
 * predicate, null or misaligned output returns INVALID without writing/counting.
 * Success writes the action and returns OK; caught Rust panics return PANIC.
 */
uint32_t sb_set_select(uint32_t mode, uint32_t predicate, uint32_t* out_action);

/* Separate shared per-thread wrapping accepted-selection counters. Loop counts
 * are unchanged. Mode >= SELECT_COUNT queries return zero.
 */
uint64_t sb_set_select_count(uint32_t mode);

/* Process-wide wrapping accepted-entry totals shared by generic and legacy
 * entry points: kind 0 counts loops (9 modes), kind 1 selections (7 modes).
 * Invalid kind/mode queries return zero. Relaxed atomics are diagnostics only:
 * not distinct consumers/containers, program state or a synchronized snapshot.
 * Concurrent counters provide only finite-width totals, not synchronization.
 */
uint64_t sb_set_global_count(uint32_t kind, uint32_t mode);

#ifdef __cplusplus
}
#endif

#endif
