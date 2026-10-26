#ifndef SB_STRING_VIEW_HOST_API_H
#define SB_STRING_VIEW_HOST_API_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Synchronous scalar ABI. Native objects and pointers remain in the context.
 * Status: 0 success, 1 pending original exception, 2 invalid, 3 prototype-only
 * containment of an incorrectly throwing host. Mode = source-map id - 1. */
typedef uint32_t (*SbStringViewHost)(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*);
uint32_t sb_string_view_run(uint32_t,void*,SbStringViewHost);
uint64_t sb_string_view_call_count(uint32_t,uint32_t);
enum SbStringViewOp {
 SV_ARG=1, SV_BYTES, SV_LENGTH, SV_VALID, SV_INIT, SV_ADVANCE, SV_END,
 SV_READ, SV_COPY, SV_EQUAL, SV_SPACE, SV_LOWER, SV_FIND_BYTES, SV_CALLBACK,
 SV_THROW_AT, SV_THROW_SUBSTR, SV_SUBSTR, SV_NATIVE_COMPARE, SV_SIMPLE,
 SV_RETURN, SV_FINISH, SV_ASSERT_BOUNDARY
};
#ifdef __cplusplus
}
#endif
#endif
