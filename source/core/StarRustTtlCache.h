#ifndef STAR_RUST_TTL_CACHE_H
#define STAR_RUST_TTL_CACHE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Canonical C11 boundary. Native objects/references/exception_ptr never cross.
 * Signed scalar values use their exact 64-bit representation in value/arg.
 * Native callbacks catch exceptions; status 1 is rethrown only after Rust returns.
 */
enum { SB_TTL_ABI_VERSION = 1 };
enum { SB_TTL_OK = 0, SB_TTL_EXCEPTION = 1, SB_TTL_INVALID = 2, SB_TTL_PANIC = 3 };
enum {
  SB_TTL_CTOR = 0, SB_TTL_TTL = 1, SB_TTL_SET_TTL = 2,
  SB_TTL_SMEAR = 3, SB_TTL_SET_SMEAR = 4, SB_TTL_MAX = 5,
  SB_TTL_SET_MAX = 6, SB_TTL_SIZE = 7, SB_TTL_KEYS = 8,
  SB_TTL_VALUES = 9, SB_TTL_UPDATE = 10, SB_TTL_SET_UPDATE = 11,
  SB_TTL_PTR = 12, SB_TTL_SET = 13, SB_TTL_REMOVE = 14,
  SB_TTL_FILTER = 15, SB_TTL_GET = 16, SB_TTL_CLEAR = 17,
  SB_TTL_CLEANUP = 18, SB_TTL_MODE_COUNT = 19
};
enum { SB_TTL_ROOT = 0, SB_TTL_VALUE_LOOP = 1,
       SB_TTL_FILTER_PREDICATE = 2, SB_TTL_CLEANUP_PREDICATE = 3,
       SB_TTL_STAGE_COUNT = 4 };
enum { SB_TTL_VOID = 0, SB_TTL_U64 = 1, SB_TTL_I64 = 2,
       SB_TTL_BOOL = 3, SB_TTL_REF = 4, SB_TTL_KEY_LIST = 5,
       SB_TTL_VALUE_LIST = 6 };
enum {
  SB_TTL_ARG = 1, SB_TTL_READ_TTL = 2, SB_TTL_WRITE_TTL = 3,
  SB_TTL_READ_SMEAR = 4, SB_TTL_WRITE_SMEAR = 5,
  SB_TTL_READ_UPDATE = 6, SB_TTL_WRITE_UPDATE = 7,
  SB_TTL_LRU_MAX = 8, SB_TTL_LRU_LIMIT = 9, SB_TTL_LRU_SIZE = 10,
  SB_TTL_LRU_PTR = 11, SB_TTL_PAIR_PRESENT = 12,
  SB_TTL_PAIR_STAMP_READ = 13, SB_TTL_PAIR_STAMP_NATIVE = 14,
  SB_TTL_PAIR_VALUE_BORROW = 15, SB_TTL_SET_EXPRESSION = 16,
  SB_TTL_GET_EXPRESSION = 17, SB_TTL_LRU_REMOVE = 18,
  SB_TTL_LRU_CLEAR = 19, SB_TTL_VALUES_SCOPE = 20,
  SB_TTL_VALUES_END = 21, SB_TTL_VALUES_APPEND = 22,
  SB_TTL_VALUES_NEXT = 23, SB_TTL_FILTER_SCOPE = 24,
  SB_TTL_CALL_FILTER = 25, SB_TTL_TIME_ONCE = 26,
  SB_TTL_CLEANUP_SCOPE = 27, SB_TTL_FILTER_PRESENT = 28,
  SB_TTL_CALL_REFRESH = 29, SB_TTL_READ_CAPTURED_TIME = 30,
  SB_TTL_PAIR_STAMP_WRITE = 31
};
/* ARG: ctor indices 0=ttl/I64,1=smear/I64,2=max/U64,3=update/BOOL.
 * Scalar setters use index0 with their corresponding tag. Other modes reject ARG.
 * WRITE_*, LRU_LIMIT, STAMP_WRITE use arg; remaining non-ARG leaves require arg0.
 * VALUES_SCOPE lends native range/iterators/result list to VALUE_LOOP. Native
 * range ends before the original named result's return/NRVO expression.
 * FILTER/CLEANUP_SCOPE enter original dependency traversal; nested stages return
 * BOOL (erase policy). ROOT VALUES/KEYS return list-action tags, no list payload.
 * SET_EXPRESSION and GET_EXPRESSION retain the ENTIRE original native full
 * expression, producer/lambda copies, pair and argument lifetimes.
 */
typedef struct SbTtlRequest {
  uint32_t size, version, op, reserved;
  uint64_t arg;
} SbTtlRequest;
typedef struct SbTtlReply {
  uint32_t size, version, tag, reserved;
  uint64_t value;
} SbTtlReply;
typedef uint32_t (*SbTtlHost)(void*, SbTtlRequest const*, SbTtlReply*);
uint32_t sb_ttl_run(uint32_t mode, uint32_t stage, void* context,
                    SbTtlHost host, SbTtlReply* result);
uint64_t sb_ttl_count(uint32_t mode, uint32_t stage);
#ifdef __cplusplus
}
#endif
#endif
