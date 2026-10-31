#ifndef STAR_RUST_ORDERED_SET_H
#define STAR_RUST_ORDERED_SET_H

#include "StarRustSet.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_ORDERED_SET_OK = 0,
  SB_ORDERED_SET_INVALID = 1,
  SB_ORDERED_SET_HOST_ERROR = 2,
  SB_ORDERED_SET_PANIC = 3
};

enum {
  SB_ORDERED_SET_ADD_RANGE = 0,
  SB_ORDERED_SET_REMOVE_RANGE = 1,
  SB_ORDERED_SET_VALUES = 2,
  SB_ORDERED_SET_INTERSECTION = 3,
  SB_ORDERED_SET_DIFFERENCE = 4,
  SB_ORDERED_SET_PRINT = 5,
  SB_ORDERED_SET_ASSIGN = 6,
  SB_ORDERED_SET_COUNT = 7
};

enum {
  SB_ORDERED_SET_MORE = 0,
  SB_ORDERED_SET_ADVANCE = 1,
  SB_ORDERED_SET_ADD = 2,
  SB_ORDERED_SET_REMOVE = 3,
  SB_ORDERED_SET_APPEND_COPY = 4,
  SB_ORDERED_SET_CONTAINS = 5,
  SB_ORDERED_SET_ADD_RESULT = 6,
  SB_ORDERED_SET_SEPARATOR_NEEDED = 7,
  SB_ORDERED_SET_SEPARATOR = 8,
  SB_ORDERED_SET_PRINT_VALUE = 9,
  SB_ORDERED_SET_SELF = 10,
  SB_ORDERED_SET_CLEAR = 11,
  SB_ORDERED_SET_ENTER_ADD_RANGE = 12
};

/* The host owns all values, storage, iterator lifetimes and native temporaries.
 * Each callback receives a fresh zero-initialized response. MORE, CONTAINS,
 * SEPARATOR_NEEDED and SELF return only 0/1; every other response must be 0.
 * A nonzero callback status stops immediately with HOST_ERROR, regardless of
 * response. The host must catch C++ exceptions and rethrow only after run returns;
 * no exception may unwind through Rust.
 *
 * ASSIGN calls SELF, then (unless self) CLEAR and ENTER_ADD_RANGE. The latter
 * creates a new native iterator frame AFTER clear and reenters ADD_RANGE; the
 * host maps a nested failure to a nonzero callback status. No context is retained.
 * Native values() keeps its copy/move scope inside APPEND_COPY. PRINT handles
 * only the loop, not opening/closing parentheses. There is no loop bound.
 */
typedef SbSetLeaf SbOrderedSetLeaf;
uint32_t sb_ordered_set_run(uint32_t mode, void* context, SbOrderedSetLeaf leaf);

/* Per-thread wrapping counts: each valid mode with nonnull context/callback
 * counts once on entry, including HOST_ERROR/INVALID response/PANIC outcomes.
 * Nested ADD_RANGE is a separate entry. Rejected calls do not count. Querying
 * an invalid mode (including COUNT, the number of modes) returns zero.
 * Counts aggregate generic and legacy consumers in the same per-thread cells;
 * this legacy query exposes only modes 0..6. Run rejects generic modes 7/8.
 */
uint64_t sb_ordered_set_count(uint32_t mode);

enum {
  SB_ORDERED_SET_SELECT_INSERT = 0,
  SB_ORDERED_SET_SELECT_REMOVE = 1,
  SB_ORDERED_SET_SELECT_NONEMPTY = 2,
  SB_ORDERED_SET_SELECT_INDEX = 3,
  SB_ORDERED_SET_SELECT_COUNT = 4
};

enum {
  SB_ORDERED_SET_ACTION_EXISTING = 0,
  SB_ORDERED_SET_ACTION_NEW = 1,
  SB_ORDERED_SET_ACTION_ERASE = 2,
  SB_ORDERED_SET_ACTION_MISS = 3,
  SB_ORDERED_SET_ACTION_THROW = 4,
  SB_ORDERED_SET_ACTION_CONTINUE = 5,
  SB_ORDERED_SET_ACTION_EMPTY = 6,
  SB_ORDERED_SET_ACTION_DISTANCE = 7
};

/* Native C++ evaluates the original comparisons with contextual bool conversion:
 * INSERT/REMOVE/INDEX take FOUND; NONEMPTY takes EMPTY. Only exact 0/1 is valid.
 * INSERT: found -> EXISTING, else NEW; REMOVE: found -> ERASE, else MISS.
 * NONEMPTY: empty -> THROW, else CONTINUE; INDEX: found -> DISTANCE, else EMPTY.
 * The separate action phase lets a native switch dispatch the Rust-chosen action
 * and materialize the original typed prvalues/references/iterators and exception
 * prefix in their original return scopes, without extra T slots or Value copies.
 * No native value, iterator or storage crosses Rust; selection allocates nothing.
 * out_action must point to live writable aligned uint32_t storage. Invalid mode,
 * predicate, null or misalignment returns INVALID without writing or counting.
 * Success returns OK; caught Rust panics return PANIC.
 */
uint32_t sb_ordered_set_select(uint32_t mode, uint32_t predicate, uint32_t* out_action);

/* Separate per-thread wrapping accepted-call counts; loop counts are unchanged.
 * Unknown modes (including SELECT_COUNT) return zero. Generic and legacy
 * selections share cells; this legacy API accepts/exposes only modes 0..3.
 */
uint64_t sb_ordered_set_select_count(uint32_t mode);

#ifdef __cplusplus
}
#endif

#endif
