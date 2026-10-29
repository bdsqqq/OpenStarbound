#ifndef STAR_RUST_STATIC_VECTOR_H
#define STAR_RUST_STATIC_VECTOR_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Only scalar control crosses this boundary. Elements, inline aligned storage,
 * iterators, typed references, arguments, temporaries and exceptions stay C++.
 * Every callback catches ALL C++ exceptions; rethrow only AFTER Rust returns.
 */
enum { SB_STATIC_VECTOR_ABI_VERSION = 1 };
enum { SB_STATIC_VECTOR_OK = 0, SB_STATIC_VECTOR_EXCEPTION = 1,
       SB_STATIC_VECTOR_INVALID = 2, SB_STATIC_VECTOR_PANIC = 3 };
enum {
 SB_STATIC_VECTOR_DEFAULT_CTOR = 0, SB_STATIC_VECTOR_CTOR_INSERT = 1,
 SB_STATIC_VECTOR_CTOR_RESIZE = 2, SB_STATIC_VECTOR_RANGE_COPY = 3,
 SB_STATIC_VECTOR_RANGE_MOVE = 4, SB_STATIC_VECTOR_COPY_ASSIGN = 5,
 SB_STATIC_VECTOR_MOVE_ASSIGN = 6, SB_STATIC_VECTOR_LIST_ASSIGN = 7,
 SB_STATIC_VECTOR_SIZE = 8, SB_STATIC_VECTOR_EMPTY = 9,
 SB_STATIC_VECTOR_RESIZE = 10, SB_STATIC_VECTOR_AT = 11,
 SB_STATIC_VECTOR_INDEX = 12, SB_STATIC_VECTOR_PUSH_BACK = 13,
 SB_STATIC_VECTOR_POP_BACK = 14, SB_STATIC_VECTOR_INSERT_ONE = 15,
 SB_STATIC_VECTOR_INSERT_RANGE = 16, SB_STATIC_VECTOR_INSERT_LIST = 17,
 SB_STATIC_VECTOR_EMPLACE = 18, SB_STATIC_VECTOR_EMPLACE_BACK = 19,
 SB_STATIC_VECTOR_CLEAR = 20, SB_STATIC_VECTOR_ERASE_ONE = 21,
 SB_STATIC_VECTOR_ERASE_RANGE = 22, SB_STATIC_VECTOR_EQUAL = 23,
 SB_STATIC_VECTOR_NOT_EQUAL = 24, SB_STATIC_VECTOR_LESS = 25,
 SB_STATIC_VECTOR_MODE_COUNT = 26
};
enum { SB_STATIC_VECTOR_ROOT = 0, SB_STATIC_VECTOR_CONTINUE = 1,
       SB_STATIC_VECTOR_STAGE_COUNT = 2 };
enum { SB_STATIC_VECTOR_VOID = 0, SB_STATIC_VECTOR_BOOL = 1,
       SB_STATIC_VECTOR_SIZE_VALUE = 2 };
enum {
 SB_STATIC_VECTOR_READ_SIZE = 1, SB_STATIC_VECTOR_READ_CAPACITY = 2,
 SB_STATIC_VECTOR_READ_TARGET = 3, SB_STATIC_VECTOR_READ_INDEX = 4,
 SB_STATIC_VECTOR_READ_TO_ADD = 5, SB_STATIC_VECTOR_READ_START = 6,
 SB_STATIC_VECTOR_READ_END = 7, SB_STATIC_VECTOR_READ_SHIFT = 8,
 SB_STATIC_VECTOR_READ_REMOVE = 9, SB_STATIC_VECTOR_OTHER_SIZE = 10,
 SB_STATIC_VECTOR_SELF = 11, SB_STATIC_VECTOR_THROW_RESIZE = 12,
 SB_STATIC_VECTOR_THROW_AT = 13, SB_STATIC_VECTOR_ASSERT_INDEX = 14,
 SB_STATIC_VECTOR_THROW_POP = 15, SB_STATIC_VECTOR_THROW_EMPLACE_BACK = 16,
 SB_STATIC_VECTOR_INCREMENT_SIZE = 17, SB_STATIC_VECTOR_CONSTRUCT_LAST = 18,
 SB_STATIC_VECTOR_DECREMENT_SIZE = 19, SB_STATIC_VECTOR_DESTROY_LAST = 20,
 SB_STATIC_VECTOR_CALL_POP = 21, SB_STATIC_VECTOR_CALL_EMPLACE_VALUE = 22,
 SB_STATIC_VECTOR_CALL_RESIZE_OTHER = 23, SB_STATIC_VECTOR_CALL_ASSIGN = 24,
 SB_STATIC_VECTOR_ITERATOR_PRESENT = 25, SB_STATIC_VECTOR_CALL_EMPLACE_CURRENT = 26,
 SB_STATIC_VECTOR_ADVANCE_ITERATOR = 27, SB_STATIC_VECTOR_CALL_FORWARD = 28,
 SB_STATIC_VECTOR_CALL_RESIZE_ADD = 29, SB_STATIC_VECTOR_CALL_RESIZE_PLUS_ONE = 30,
 SB_STATIC_VECTOR_CALL_RESIZE_MINUS_ONE = 31, SB_STATIC_VECTOR_CALL_RESIZE_MINUS_REMOVE = 32,
 SB_STATIC_VECTOR_MOVE_ASSIGN_SLOTS = 33, SB_STATIC_VECTOR_ASSIGN_FROM_ITERATOR = 34,
 SB_STATIC_VECTOR_ASSIGN_FROM_ARGS = 35, SB_STATIC_VECTOR_ELEMENT_NOT_EQUAL = 36,
 SB_STATIC_VECTOR_CALL_EQUAL = 37, SB_STATIC_VECTOR_COMPARE_PAIR = 38,
 SB_STATIC_VECTOR_PAIR_LESS = 39, SB_STATIC_VECTOR_PAIR_GREATER = 40,
 SB_STATIC_VECTOR_OP_COUNT = 40
};
/* CONTINUE is valid ONLY for LESS: its native caller already bound the ORIGINAL
 * named `Element const& a` and `b`. It returns SIZE_VALUE 0(equal),1(less),2(greater)
 * after PAIR_LESS then, only if necessary, PAIR_GREATER. ROOT LESS loops over
 * COMPARE_PAIR(index), whose native scope binds a,b and calls that continuation.
 * Do not re-index/re-copy the pair between its two user comparisons.
 *
 * READ_*, OTHER_SIZE return SIZE_VALUE fitting the target's native size_t/usize.
 * SELF, ITERATOR_PRESENT, ELEMENT_NOT_EQUAL, CALL_EQUAL, PAIR_LESS/GREATER return
 * BOOL 0/1. COMPARE_PAIR returns SIZE_VALUE 0/1/2. Other leaves return VOID0.
 * THROW_* MUST return EXCEPTION; an OK acknowledgement is INVALID.
 * Requests require arg0=arg1=0 except: CALL_ASSIGN, ASSIGN_FROM_ITERATOR,
 * ASSIGN_FROM_ARGS, ELEMENT_NOT_EQUAL, COMPARE_PAIR use arg0=index, arg1=0;
 * MOVE_ASSIGN_SLOTS uses arg0=destination, arg1=source. All reserved fields zero.
 * Rust does native-width unsigned wrapping arithmetic, NOT element arithmetic.
 *
 * Native range-insert locals remain declared in original order: toAdd=distance,
 * startIndex, endIndex, toShift. Erase's index/start/end/toRemove likewise stay
 * C++ locals. READ_* retrieves those bound scalar locals, not recomputed values.
 * Native range-copy/move cursors/end are captured once, as the original range-for.
 * CALL_* invokes the PORTED native API wrapper, never a saved C++ policy body.
 * CALL_RESIZE_* retains its complete original call expression and default
 * Element() temporary. CALL_ASSIGN and MOVE_ASSIGN_SLOTS retain complete native
 * assignment expressions. ASSIGN_FROM_ITERATOR retains `*begin++` and its temp;
 * ASSIGN_FROM_ARGS constructs Element(forward<Args>(args)...) ONLY after shifts.
 * No early argument/element copy, moving native locals into Rust, or rollback.
 *
 * RESIZE preserves two local-counter loops, re-reading native size BETWEEN
 * loops. Assign/clear/erase/comparison conditions instead re-read size at each
 * original condition. Construction increments size BEFORE placement; pop
 * decrements BEFORE destructor. Exception replies stop immediately, preserving
 * native partial mutation; C++ unwinds locals/delegating constructors itself.
 * Native typed storage/views/asserts are leaves, not a second loop/branch policy.
 * Per-method lambdas keep unused Element/Iterator requirements uninstantiated.
 */
typedef struct SbStaticVectorRequest {
 uint32_t size, version, op, reserved;
 uint64_t arg0, arg1;
} SbStaticVectorRequest;
typedef struct SbStaticVectorReply {
 uint32_t size, version, tag, reserved;
 uint64_t value;
} SbStaticVectorReply;
typedef uint32_t (*SbStaticVectorHost)(void*, SbStaticVectorRequest const*, SbStaticVectorReply*);
uint32_t sb_static_vector_run(uint32_t mode, uint32_t stage, void* context,
                             SbStaticVectorHost host, SbStaticVectorReply* result);
uint64_t sb_static_vector_count(uint32_t mode, uint32_t stage);
#ifdef __cplusplus
}
#endif
#endif
