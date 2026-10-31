#ifndef STAR_RUST_MAP_H
#define STAR_RUST_MAP_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_MAP_OK = 0,
  SB_MAP_INVALID = 1,
  SB_MAP_HOST_ERROR = 2,
  SB_MAP_PANIC = 3
};

enum {
  SB_MAP_COLLECT = 0,
  SB_MAP_FIRST = 1,
  SB_MAP_FILTER = 2,
  SB_MAP_REMOVE = 3,
  SB_MAP_PRINT = 4,
  SB_MAP_MERGE = 5,
  SB_MAP_MERGE_ITEM = 6,
  SB_MAP_COUNT = 7
};

enum {
  SB_MAP_MORE = 0,
  SB_MAP_ADVANCE = 1,
  SB_MAP_APPEND = 2,
  SB_MAP_MATCH = 3,
  SB_MAP_ERASE = 4,
  SB_MAP_FIRST_ELEMENT = 5,
  SB_MAP_FIRST_PREFIX = 6,
  SB_MAP_NEXT_PREFIX = 7,
  SB_MAP_PRINT_VALUE = 8,
  SB_MAP_MERGE_ITEM_OP = 9,
  SB_MAP_INSERTED = 10,
  SB_MAP_OVERWRITE = 11,
  SB_MAP_UPDATE = 12
};

/* The host owns values, storage, iterator lifetimes and native expression scopes.
 * Rust owns only loop/branch policy; it allocates nothing, retains no context,
 * and imposes no integer iteration bound on native iterator termination.
 * Typed callback leaves keep original native full expressions (including
 * temporaries, contextual bool conversion, ADL and exceptions) together, rather
 * than adding value slots/copies or extending native lifetimes across the ABI.
 *
 * Every invocation gets a fresh zero-initialized response. MORE, MATCH,
 * FIRST_ELEMENT, MERGE_ITEM_OP, INSERTED and OVERWRITE must respond with exact
 * 0/1; all other operations (including UPDATE) require 0.
 * A nonzero host status takes precedence over malformed response, returning
 * HOST_ERROR. A malformed response with host status 0 returns INVALID. Both
 * stop immediately: no later callback is invoked. Host exceptions must be caught
 * inside the leaf and rethrown only after run returns; neither native exceptions
 * nor callback panics may unwind through this C ABI. Raw opaque context permits
 * reentry; the host must preserve native scopes and translate nested errors.
 *
 * COLLECT: MORE -> APPEND -> ADVANCE, repeated until MORE returns false.
 * FIRST: MORE -> MATCH; true returns result 1 WITHOUT ADVANCE or further calls;
 * false calls ADVANCE. Exhaustion returns result 0.
 * FILTER: MORE -> MATCH -> APPEND if true -> ADVANCE.
 * REMOVE: MORE -> MATCH -> ERASE if true, otherwise ADVANCE. ERASE includes the
 * WHOLE native erase(i++) expression, so Rust NEVER calls ADVANCE on that path.
 * A completed ERASE marks the eventual result 1; no removals yields 0. If erase
 * throws after postfix increment, that native prefix is retained, not repaired.
 * PRINT: MORE -> FIRST_ELEMENT -> FIRST_PREFIX if true, otherwise NEXT_PREFIX
 * -> PRINT_VALUE -> ADVANCE. Opening/closing delimiters stay outside Rust.
 * MERGE: MORE -> MERGE_ITEM_OP -> ADVANCE until exhaustion. Result is 1 iff
 * ALL item replies were 1 (including empty input); a 0 NEVER short-circuits.
 * MERGE_ITEM: INSERTED once; true returns 1 without OVERWRITE or UPDATE. False
 * calls OVERWRITE; true calls UPDATE. Either duplicate path returns 0.
 * The native MERGE_ITEM_OP leaf owns the complete auto res = targetMap.insert(*i)
 * expression and keeps res alive through nested MERGE_ITEM and UPDATE. It
 * destroys res BEFORE root ADVANCE; neither res nor Value crosses into Rust.
 * INSERTED preserves native !res.second ? 0u : 1u (including operator!). MORE
 * evaluates sourceMap.end() anew each iteration, not a cached end iterator.
 * COLLECT, FILTER and PRINT return 0; FIRST, REMOVE, MERGE and MERGE_ITEM return
 * exact boolean results on success.
 *
 * out_result must designate live writable aligned uint32_t storage. Invalid
 * mode, null context/function/output or output misalignment returns INVALID
 * BEFORE any entry count, callback or write. Context is opaque and is never
 * dereferenced by Rust; its native alignment is the host's responsibility.
 * Only success writes output. All errors leave output unchanged; completed
 * native side effects are NOT rolled back. Caught Rust panics return PANIC.
 * Numerical checks cannot establish pointer provenance, liveness or writability.
 * These symbols are independent of Set controllers and their legacy ABI views;
 * their callbacks, operation numbers and counters must not be cross-mixed.
 */
typedef uint32_t (*SbMapLeaf)(void*, uint32_t operation, uint32_t* out_response);
uint32_t sb_map_run(uint32_t mode, void* context, SbMapLeaf leaf, uint32_t* out_result);

enum {
  SB_MAP_SELECT_REQUIRED = 0,
  SB_MAP_SELECT_OPTIONAL = 1,
  SB_MAP_SELECT_DEFAULT = 2,
  SB_MAP_SELECT_SET = 3,
  SB_MAP_SELECT_ADD = 4,
  SB_MAP_SELECT_COUNT = 5
};

enum {
  SB_MAP_ACTION_VALUE = 0,
  SB_MAP_ACTION_THROW = 1,
  SB_MAP_ACTION_EMPTY = 2,
  SB_MAP_ACTION_DEFAULT = 3,
  SB_MAP_ACTION_INSERT = 4,
  SB_MAP_ACTION_UPDATE = 5
};

/* predicate is FOUND for REQUIRED/OPTIONAL/DEFAULT/SET, INSERTED for ADD.
 * Native comparisons must perform contextual bool conversion before entry;
 * predicate must be exact 0/1.
 * REQUIRED: true VALUE / false THROW; OPTIONAL: true VALUE / false EMPTY;
 * DEFAULT: true VALUE / false DEFAULT; SET: true UPDATE / false INSERT;
 * ADD: true VALUE / false THROW.
 * The host materializes typed references/prvalues/defaults/insertions/exceptions
 * AFTER selection, preserving original return and temporary lifetime scopes.
 * No Value, allocation or ownership crosses into Rust.
 * out_action must be live writable aligned uint32_t storage. Invalid mode,
 * predicate, null or misaligned output returns INVALID before counting/writing.
 * Success writes the action and returns OK; caught Rust panics return PANIC
 * without writing. Numerical checks cannot prove pointer liveness/writability.
 */
uint32_t sb_map_select(uint32_t mode, uint32_t predicate, uint32_t* out_action);

/* Per-thread wrapping accepted-entry totals, separate for loops and selections.
 * Count host errors, malformed callback replies, panics and each reentrant entry.
 * Rejected calls do not count. Loop modes are 0..6; selection modes remain 0..4.
 * Invalid mode queries return zero. These counters
 * are independent of Set/OrderedSet/FlatHashTable and do not count consumers.
 */
uint64_t sb_map_count(uint32_t mode);
uint64_t sb_map_select_count(uint32_t mode);

/* Process-wide wrapping accepted totals: kind 0 loops, kind 1 selections.
 * Bounds are family-specific: kind 0 accepts 0..6, kind 1 accepts only 0..4.
 * Invalid kind/mode queries return zero. Relaxed atomics are diagnostics only,
 * not synchronized snapshots, program-state barriers or distinct-container counts.
 */
uint64_t sb_map_global_count(uint32_t kind, uint32_t mode);

#ifdef __cplusplus
}
#endif

#endif
