#ifndef STAR_RUST_LRU_CACHE_H
#define STAR_RUST_LRU_CACHE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* synchronous borrowed pointers; callbacks contain all native exceptions.
 * status: 0 success, 1 pending native exception, 2 protocol error, 3 contained
 * Rust panic. the native owner rethrows only after the controller returns.
 * storage, values, iterators and snapshot lists remain native. counters record
 * controller entries, not completed operations. no production call/depth cap. */
typedef struct SbLruRequest { uint32_t size, op; uint64_t arg; } SbLruRequest;
typedef struct SbLruReply { uint32_t size, tag; uint64_t value; } SbLruReply;
typedef uint32_t (*SbLruHost)(void*, const SbLruRequest*, SbLruReply*);
enum SbLruMode { SB_LRU_CTOR, SB_LRU_MAX, SB_LRU_LIMIT, SB_LRU_SIZE,
 SB_LRU_KEYS, SB_LRU_VALUES, SB_LRU_PTR, SB_LRU_SET, SB_LRU_REMOVE,
 SB_LRU_FILTER, SB_LRU_GET, SB_LRU_CLEAR, SB_LRU_MODES };
enum SbLruStage { SB_LRU_ROOT, SB_LRU_FOUND, SB_LRU_PAIR, SB_LRU_TRAVERSE };
enum SbLruTag { SB_LRU_VOID, SB_LRU_U64, SB_LRU_BOOL, SB_LRU_REF,
 SB_LRU_KEY_LIST, SB_LRU_VALUE_LIST };
enum SbLruOp { SB_LRU_ARG=1, SB_LRU_READ_MAX, SB_LRU_WRITE_MAX,
 SB_LRU_MAP_SIZE, SB_LRU_REMOVE_FIRST, SB_LRU_FIND_SCOPE, SB_LRU_IS_END,
 SB_LRU_PROMOTE_ASSIGN, SB_LRU_PROMOTE_DISCARD, SB_LRU_REFERENCE,
 SB_LRU_ADD, SB_LRU_ASSIGN, SB_LRU_REMOVE_KEY, SB_LRU_PAIR_SCOPE,
 SB_LRU_INSERT_PAIR, SB_LRU_FILTER_SCOPE, SB_LRU_PREDICATE,
 SB_LRU_ERASE, SB_LRU_NEXT, SB_LRU_MAP_CLEAR };
uint32_t sb_lru_run(uint32_t mode, uint32_t stage, void*, SbLruHost, SbLruReply*);
uint64_t sb_lru_count(uint32_t mode, uint32_t stage);
#ifdef __cplusplus
}
#endif
#endif
