#ifndef STAR_RUST_ORDERED_SET_H
#define STAR_RUST_ORDERED_SET_H

#include <stdint.h>

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
typedef uint32_t (*SbOrderedSetLeaf)(void*, uint32_t, uint32_t*);
uint32_t sb_ordered_set_run(uint32_t mode, void* context, SbOrderedSetLeaf leaf);

/* Per-thread wrapping counts: each valid mode with nonnull context/callback
 * counts once on entry, including HOST_ERROR/INVALID response/PANIC outcomes.
 * Nested ADD_RANGE is a separate entry. Rejected calls do not count. Querying
 * an invalid mode (including COUNT, the number of modes) returns zero.
 */
uint64_t sb_ordered_set_count(uint32_t mode);

#ifdef __cplusplus
}
#endif

#endif
