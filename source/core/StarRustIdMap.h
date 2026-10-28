#ifndef STAR_RUST_ID_MAP_H
#define STAR_RUST_ID_MAP_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Native BaseMap, typed IdType locals, mapped values, streams and exceptions
 * never cross this boundary. Callbacks catch ALL C++ throws; the native caller
 * rethrows only AFTER Rust returns. No key bits or result-object storage in Rust.
 */
enum { SB_IDMAP_ABI_VERSION=1 };
enum { SB_IDMAP_OK=0, SB_IDMAP_EXCEPTION=1, SB_IDMAP_INVALID=2, SB_IDMAP_PANIC=3 };
enum {
 SB_IDMAP_CTOR=0, SB_IDMAP_RANGE_CTOR=1, SB_IDMAP_NEXT=2,
 SB_IDMAP_ADD_EXPLICIT=3, SB_IDMAP_ADD_AUTO=4, SB_IDMAP_CLEAR=5,
 SB_IDMAP_EQUAL=6, SB_IDMAP_NOT_EQUAL=7, SB_IDMAP_READ=8,
 SB_IDMAP_WRITE=9, SB_IDMAP_MODE_COUNT=10
};
enum { SB_IDMAP_ROOT=0, SB_IDMAP_CONTINUE=1, SB_IDMAP_STAGE_COUNT=2 };
enum { SB_IDMAP_VOID=0, SB_IDMAP_BOOL=1 };
enum {
 SB_IDMAP_ASSERT_RANGE=1, SB_IDMAP_FULL=2, SB_IDMAP_THROW_FULL=3,
 SB_IDMAP_CURSOR_CONTAINS=4, SB_IDMAP_CURSOR_ADVANCE=5,
 SB_IDMAP_CURSOR_COMMIT=6, SB_IDMAP_EXPLICIT_INSERT=7,
 SB_IDMAP_THROW_DUPLICATE=8, SB_IDMAP_AUTO_INSERT=9,
 SB_IDMAP_CLEAR_MAP=10, SB_IDMAP_CLEAR_CURSOR=11,
 SB_IDMAP_SAME_BOUNDS=12, SB_IDMAP_BASE_EQUAL=13, SB_IDMAP_CALL_EQUAL=14,
 SB_IDMAP_READ_MAP=15, SB_IDMAP_READ_MIN=16, SB_IDMAP_READ_MAX=17,
 SB_IDMAP_READ_CURSOR=18, SB_IDMAP_WRITE_MAP=19, SB_IDMAP_WRITE_MIN=20,
 SB_IDMAP_WRITE_MAX=21, SB_IDMAP_WRITE_CURSOR=22, SB_IDMAP_OP_COUNT=22
};
/* All requests require arg=0. BOOL leaves: FULL, CURSOR_CONTAINS,
 * EXPLICIT_INSERT, SAME_BOUNDS, BASE_EQUAL, CALL_EQUAL. Others return VOID0.
 * THROW_* must return EXCEPTION; an OK acknowledgement is INVALID.
 *
 * Initializers stay native. CTOR ROOT has no callback; RANGE_CTOR ROOT invokes
 * the original native starAssert full expression (possibly compiled out).
 * NEXT ROOT tests the ORIGINAL typed `(IdType)size > max-min` and raises before
 * any key copy. Native then declares `IdType next=m_nextId`; NEXT CONTINUE owns
 * contains/advance iteration and final cursor commit against that bound local.
 * Native returns THAT SAME named local, preserving copy/NRVO/lifetime rules.
 *
 * ADD_AUTO ROOT authorizes native `auto id=nextId()` (nested/reentrant roots).
 * CONTINUE invokes the original named-lvalue insertion full expression; native
 * returns the SAME local id. Do not eagerly construct/copy a key in a frame.
 * EXPLICIT_INSERT retains make_pair(std::move(id),std::move(mapped)) including
 * temporaries; duplicate formatting observes the original possibly moved id.
 * CLEAR_MAP finishes before CLEAR_CURSOR. EQUAL short-circuits bounds/base;
 * NOT_EQUAL calls the native EQUAL wrapper, preserving nested policy entry.
 * READ/WRITE sequence map,min,max,cursor full expressions without validation or
 * rollback. Incomplete native primitive reads may mutate a field before throw.
 * Const and lazy typed operations are captured per method, never instantiated
 * through an eager map-wide host switch. No retry/progress cap on native loops.
 */
typedef struct SbIdMapRequest {uint32_t size,version,op,reserved;uint64_t arg;} SbIdMapRequest;
typedef struct SbIdMapReply {uint32_t size,version,tag,reserved;uint64_t value;} SbIdMapReply;
typedef uint32_t (*SbIdMapHost)(void*,SbIdMapRequest const*,SbIdMapReply*);
uint32_t sb_idmap_run(uint32_t mode,uint32_t stage,void* context,SbIdMapHost host,SbIdMapReply* result);
uint64_t sb_idmap_count(uint32_t mode,uint32_t stage);
#ifdef __cplusplus
}
#endif
#endif
