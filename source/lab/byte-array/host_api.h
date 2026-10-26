#ifndef SB_BYTE_ARRAY_HOST_API_H
#define SB_BYTE_ARRAY_HOST_API_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* All values are scalars. No pointer is encoded as an integer. Synchronous
 * borrowed context, callback must not unwind. 0 success, 1 pending native
 * exception, 2 invalid protocol, 3 C++ prototype callback containment. */
typedef uint32_t (*SbByteArrayHost)(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*);
uint32_t sb_byte_array_run(uint32_t mode,void* ctx,SbByteArrayHost host);
/* Thread-local wrapping counters; event 0 attempt, 1 success, 2 pending.
 * Invalid mode/event returns zero. No reset API. */
uint64_t sb_byte_array_call_count(uint32_t mode,uint32_t event);
enum SbByteArrayMode {
 SB_BA_CSTRING=0, SB_BA_CSTRING_NULL, SB_BA_WITH_RESERVE, SB_BA_CTOR,
 SB_BA_FILL_CTOR, SB_BA_PTR_CTOR, SB_BA_COPY_CTOR, SB_BA_MOVE_CTOR,
 SB_BA_DTOR, SB_BA_COPY_ASSIGN, SB_BA_MOVE_ASSIGN, SB_BA_RESET,
 SB_BA_RESERVE, SB_BA_RESIZE_FILL, SB_BA_FILL_SIZE, SB_BA_FILL,
 SB_BA_SUB, SB_BA_LEFT, SB_BA_RIGHT, SB_BA_TRIM_LEFT, SB_BA_TRIM_RIGHT,
 SB_BA_DIFF, SB_BA_COMPARE, SB_BA_AND, SB_BA_OR, SB_BA_XOR,
 SB_BA_INSERT, SB_BA_INSERT_ITER, SB_BA_PUSH, SB_BA_LT, SB_BA_EQ,
 SB_BA_NE, SB_BA_STREAM, SB_BA_CLEAR, SB_BA_RESIZE, SB_BA_APPEND_ARRAY,
 SB_BA_APPEND, SB_BA_APPEND_BYTE, SB_BA_EMPTY, SB_BA_PTR_CONST,
 SB_BA_PTR, SB_BA_SIZE, SB_BA_CAPACITY, SB_BA_COPY_LEN, SB_BA_COPY_ALL,
 SB_BA_COPY_RANGE, SB_BA_WRITE, SB_BA_COMBINE, SB_BA_BEGIN, SB_BA_END,
 SB_BA_CBEGIN, SB_BA_CEND, SB_BA_INDEX, SB_BA_CONST_INDEX, SB_BA_AT,
 SB_BA_HASH, SB_BA_MODE_COUNT
};
enum SbByteArrayOp {
 SB_BA_ARG=1, SB_BA_GET_SIZE, SB_BA_GET_CAPACITY, SB_BA_HAS_DATA,
 SB_BA_INIT, SB_BA_SET_SIZE, SB_BA_ALLOC, SB_BA_FREE, SB_BA_TAKE,
 SB_BA_SAME, SB_BA_CAPTURE, SB_BA_COPY_IN, SB_BA_COPY_OUT, SB_BA_MOVE_BYTES,
 SB_BA_FILL_BYTES, SB_BA_GET_BYTE, SB_BA_SET_BYTE, SB_BA_POINTER,
 SB_BA_STRLEN, SB_BA_INIT_RESULT, SB_BA_ROLES, SB_BA_EXPR,
 SB_BA_TAIL_EXPR, SB_BA_ITER_DISTANCE, SB_BA_ASSERT_INSERT,
 SB_BA_THROW_AT, SB_BA_HASH_PUT, SB_BA_HASH_RESULT,
 SB_BA_STREAM_PREFIX, SB_BA_STREAM_HEX, SB_BA_RETURN, SB_BA_FINISH
};
#ifdef __cplusplus
}
#endif
#endif
