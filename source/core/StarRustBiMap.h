#ifndef STAR_RUST_BIMAP_H
#define STAR_RUST_BIMAP_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* scalar source-policy increment, NOT a complete BiMap port or adoption.
 * native maps, keys, iterators, insertion-result prvalues and exceptions stay
 * in C++. typed lifetime/return adapters are pending; no C++ caller exists yet.
 * callbacks catch all native exceptions and rethrow only AFTER Rust returns.
 * stop on non-OK without rollback. result initially contains a valid reply;
 * errors do not write result (callbacks' own mutations are not rolled back).
 */
enum { SB_BIMAP_ABI_VERSION = 1 };
enum { SB_BIMAP_OK = 0, SB_BIMAP_EXCEPTION = 1, SB_BIMAP_INVALID = 2, SB_BIMAP_PANIC = 3 };
enum { SB_BIMAP_VOID = 0, SB_BIMAP_BOOL = 1, SB_BIMAP_SIZE_VALUE = 2 };
enum {
  SB_BIMAP_MODE_SIZE = 0,
  SB_BIMAP_MODE_EMPTY = 1,
  SB_BIMAP_MODE_HAS_LEFT = 2,
  SB_BIMAP_MODE_HAS_RIGHT = 3,
  SB_BIMAP_MODE_ADD = 4,
  SB_BIMAP_MODE_OVERWRITE = 5,
  SB_BIMAP_MODE_REMOVE_LEFT = 6,
  SB_BIMAP_MODE_REMOVE_RIGHT = 7,
  SB_BIMAP_MODE_CLEAR = 8,
  SB_BIMAP_MODE_COPY_ASSIGN = 9,
  SB_BIMAP_MODE_RANGE_INSERT = 10,
  SB_BIMAP_MODE_LIST_INSERT = 11,
  SB_BIMAP_MODE_EQUAL = 12,
  SB_BIMAP_MODE_INSERT_ROUTE = 13,
  SB_BIMAP_MODE_INSERT_LINK = 14,
  SB_BIMAP_MODE_COPY_ENTRIES = 15,
  SB_BIMAP_MODE_EQUAL_ENTRIES = 16,
  SB_BIMAP_MODE_COUNT = 17
};
enum {
  SB_BIMAP_SIZE = 1,
  SB_BIMAP_EMPTY = 2,
  SB_BIMAP_HAS_LEFT = 3,
  SB_BIMAP_HAS_RIGHT = 4,
  SB_BIMAP_THROW_LEFT = 5,
  SB_BIMAP_THROW_RIGHT = 6,
  SB_BIMAP_INSERT_IGNORED = 7,
  SB_BIMAP_REMOVE_LEFT_IGNORED = 8,
  SB_BIMAP_REMOVE_RIGHT_IGNORED = 9,
  SB_BIMAP_RIGHT_FOR_LEFT_PRESENT = 10,
  SB_BIMAP_LEFT_FOR_RIGHT_PRESENT = 11,
  SB_BIMAP_REMOVE_RIGHT_USING_FOUND = 12,
  SB_BIMAP_REMOVE_LEFT_USING_FOUND = 13,
  SB_BIMAP_CLEAR_LEFT = 14,
  SB_BIMAP_CLEAR_RIGHT = 15,
  SB_BIMAP_ASSIGN_DISTINCT = 16,
  SB_BIMAP_COPY_ENTRIES = 17,
  SB_BIMAP_ITERATOR_PRESENT = 18,
  SB_BIMAP_INSERT_CURRENT_IGNORED = 19,
  SB_BIMAP_ADVANCE_ITERATOR = 20,
  SB_BIMAP_INSERT_CURRENT_CHECKED = 21,
  SB_BIMAP_THROW_CURRENT_DUPLICATE = 22,
  SB_BIMAP_SELF_EQUAL = 23,
  SB_BIMAP_OTHER_SIZE = 24,
  SB_BIMAP_EQUAL_ENTRIES = 25,
  SB_BIMAP_FIND_CURRENT_RIGHT = 26,
  SB_BIMAP_CURRENT_RIGHT_NOT_EQUAL = 27,
  SB_BIMAP_LEFT_INSERTED = 28,
  SB_BIMAP_ASSERT_RIGHT_INSERTED = 29,
  SB_BIMAP_LINK_LEFT = 30,
  SB_BIMAP_LINK_RIGHT = 31,
  SB_BIMAP_OP_COUNT = 31
};

/* requests: size32/version1/reserved0/arg0=arg1=0. replies: size24/version1/
 * reserved0; VOID value0, BOOL value0/1, SIZE_VALUE fits native size_t/usize.
 * SIZE/OTHER_SIZE return SIZE_VALUE. boolean leaves are EMPTY, HAS_LEFT,
 * HAS_RIGHT, RIGHT_FOR_LEFT_PRESENT, LEFT_FOR_RIGHT_PRESENT, ASSIGN_DISTINCT,
 * ITERATOR_PRESENT, INSERT_CURRENT_CHECKED, SELF_EQUAL, EQUAL_ENTRIES,
 * FIND_CURRENT_RIGHT, CURRENT_RIGHT_NOT_EQUAL, LEFT_INSERTED. others use VOID.
 * THROW_LEFT/THROW_RIGHT/THROW_CURRENT_DUPLICATE cannot acknowledge success.
 *
 * INSERT_ROUTE runs with the original native left insertion result alive.
 * INSERT_LINK runs with BOTH original results alive: assertion, left link,
 * right link. do not copy these objects into optional result/pair slots.
 * COPY_ENTRIES/EQUAL_ENTRIES prepare native begin/end expressions and invoke
 * modes COPY_ENTRIES/EQUAL_ENTRIES inside their native lifetime scope.
 * ASSIGN_DISTINCT evaluates the original `this != &map`; SELF_EQUAL evaluates
 * the original `&map == this`, without replacing overloadable expressions.
 */
typedef struct SbBiMapRequest {
  uint32_t size, version, op, reserved;
  uint64_t arg0, arg1;
} SbBiMapRequest;
typedef struct SbBiMapReply {
  uint32_t size, version, tag, reserved;
  uint64_t value;
} SbBiMapReply;
typedef uint32_t (*SbBiMapHost)(void*, SbBiMapRequest const*, SbBiMapReply*);
uint32_t sb_bimap_run(uint32_t mode, void* context, SbBiMapHost host, SbBiMapReply* result);
uint64_t sb_bimap_count(uint32_t mode);

#ifdef __cplusplus
}
#endif
#endif
