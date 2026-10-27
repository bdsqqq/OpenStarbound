#ifndef STAR_RUST_WEIGHTED_POOL_H
#define STAR_RUST_WEIGHTED_POOL_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Native object, cursor, Item, List/Set and exception ownership never crosses.
 * F64 values are exact IEEE payload bits, not C floating arguments. A native
 * callback catches ALL C++ throws; only the native caller rethrows after return.
 */
enum { SB_WP_ABI_VERSION=1 };
enum { SB_WP_OK=0, SB_WP_EXCEPTION=1, SB_WP_INVALID=2, SB_WP_PANIC=3 };
enum {
 SB_WP_CTOR=0, SB_WP_CONTAINER_CTOR=1, SB_WP_ADD=2, SB_WP_CLEAR=3,
 SB_WP_ITEMS=4, SB_WP_SIZE=5, SB_WP_AT=6, SB_WP_WEIGHT=7, SB_WP_ITEM=8,
 SB_WP_EMPTY=9, SB_WP_SELECT_SOURCE=10, SB_WP_SELECT_GLOBAL=11,
 SB_WP_SELECT_SEED=12, SB_WP_UNIQUES_GLOBAL=13, SB_WP_UNIQUES_SEED=14,
 SB_WP_INDEX_SOURCE=15, SB_WP_INDEX_GLOBAL=16, SB_WP_INDEX_SEED=17,
 SB_WP_INDEX_TARGET=18, SB_WP_MODE_COUNT=19
};
enum { SB_WP_ROOT=0, SB_WP_CONTAINER_LOOP=1, SB_WP_UNIQUE_COLLECT=2,
 SB_WP_UNIQUE_APPEND=3, SB_WP_STAGE_COUNT=4 };
enum { SB_WP_VOID=0, SB_WP_U64=1, SB_WP_BOOL=2, SB_WP_F64=3,
 SB_WP_BORROW=4, SB_WP_DEFAULT_ITEM=5, SB_WP_ITEM_RESULT=6 };
enum {
 SB_WP_ARG=1, SB_WP_COUNT=2, SB_WP_IS_EMPTY=3, SB_WP_AT_BORROW=4,
 SB_WP_AT_WEIGHT=5, SB_WP_AT_ITEM_BORROW=6, SB_WP_APPEND_ITEM_EXPRESSION=7,
 SB_WP_CLEAR_ITEMS=8, SB_WP_READ_TOTAL=9, SB_WP_WRITE_TOTAL=10,
 SB_WP_DRAW_SOURCE=11, SB_WP_DRAW_GLOBAL=12, SB_WP_DRAW_STATIC=13,
 SB_WP_DRAW_SEED=14, SB_WP_CALL_INDEX_SOURCE=15, SB_WP_CALL_INDEX_GLOBAL=16,
 SB_WP_CALL_INDEX_SEED=17, SB_WP_READ_WEIGHT=18, SB_WP_CONTAINER_SCOPE=19,
 SB_WP_CONTAINER_END=20, SB_WP_CONTAINER_ADD_EXPRESSION=21,
 SB_WP_CONTAINER_NEXT=22, SB_WP_UNIQUE_SET_SIZE=23, SB_WP_UNIQUE_SET_ADD=24,
 SB_WP_UNIQUE_END=25, SB_WP_UNIQUE_APPEND_EXPRESSION=26,
 SB_WP_UNIQUE_NEXT=27, SB_WP_SCAN_SIZE=28
};
/* ARG index0: ADD/INDEX_TARGET F64; AT/WEIGHT/ITEM/SELECT_SEED/INDEX_SEED U64.
 * UNIQUES_SEED ROOT index0=desiredCount; COLLECT index0=targetCount,index1=seed.
 * AT_* and READ_WEIGHT take index in arg; DRAW_STATIC/CALL_INDEX_SEED take seed;
 * WRITE_TOTAL takes F64 bits; UNIQUE_SET_ADD takes index. Other leaves require0.
 * CONTAINER_SCOPE owns native begin/end and calls stage CONTAINER_LOOP. Its ADD
 * leaf keeps the entire `auto const& pair=*cursor; add(get<0>,get<1>)` lifetime.
 * Seeded unique ROOT returns min(desiredCount,size). Native then creates Set,
 * calls COLLECT, creates the ORIGINAL named List result and native Set cursors,
 * calls APPEND and returns that named result. No early List/Item construction.
 * UNIQUES_GLOBAL ROOT returns randu64 seed for the original native prvalue
 * forwarding return. INDEX_SOURCE/GLOBAL/SEED ROOT returns F64 target for native
 * forwarding to INDEX_TARGET. SELECT_* returns DEFAULT_ITEM0 or ITEM_RESULTindex
 * for native direct-return construction/copy (never an Item in a Rust frame).
 * INDEX_TARGET follows the observed original optimized arm64 scan: reciprocal
 * once after empty check, then fused weight*reciprocal+accumulator per element.
 * Add reads total AFTER the append full expression/reentry, never snapshots it.
 * No retry/iteration cap: unreachable native unique progress stays unreachable.
 */
typedef struct SbWpRequest {uint32_t size,version,op,reserved;uint64_t arg;} SbWpRequest;
typedef struct SbWpReply {uint32_t size,version,tag,reserved;uint64_t value;} SbWpReply;
typedef uint32_t (*SbWpHost)(void*,SbWpRequest const*,SbWpReply*);
uint32_t sb_wp_run(uint32_t mode,uint32_t stage,void* context,SbWpHost host,SbWpReply* result);
uint64_t sb_wp_count(uint32_t mode,uint32_t stage);
#ifdef __cplusplus
}
#endif
#endif
