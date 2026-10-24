#pragma once
#include <stdint.h>

/* Production JSON-patch controller boundary.
 * Named native scratch fields own Json/Maybe/String/Pointer/array values.
 * No C++ object layout or character buffer crosses this interface.
 * Unlisted arguments must be zero. out is live/aligned for every callback;
 * only successful scalar-returning operations write it. A failed semantic
 * callback retains the actual native exception_ptr and returns its category.
 * ABI rejection is not a fabricated legacy exception. */
#ifdef __cplusplus
extern "C" {
#endif

typedef uint32_t (*StarJsonPatchHost)(void* context, uint32_t opcode,
    uint32_t a, uint32_t b, uint64_t n, uint64_t* out);
typedef uint32_t (*StarJsonPatchRun)(uint32_t entry, StarJsonPatchHost host,
    void* context, uint64_t* scalar_out);

enum StarJsonPatchEntry {
  JP_PATCH = 0, JP_APPLY = 1, JP_FIND = 2, JP_TEST = 3, JP_REMOVE = 4,
  JP_ADD = 5, JP_REPLACE = 6, JP_MOVE = 7, JP_COPY = 8, JP_MERGE = 9
};
enum StarJsonPatchHostStatus {
  JP_OK = 0, JP_TRAVERSAL = 1, JP_JSON = 2, JP_MAP = 3,
  JP_TEST_FAIL = 4, JP_OTHER = 5, JP_HOST_ABI_INVALID = 6
};
enum StarJsonPatchRunStatus {
  JP_SUCCESS = 0, JP_NATIVE_EXCEPTION_PENDING = 1,
  JP_ABI_INVALID = 2, JP_RUST_PANIC = 3
};
enum StarJsonPatchOpcode {
  JP_PATCH_SIZE = 0, JP_PATCH_GET = 1, JP_LOOKUP_OPERATION = 2,
  JP_READ_OPERATION = 3, JP_READ_PATH = 4, JP_READ_VALUE = 5,
  JP_MAKE_TO = 6, JP_MAKE_TO_REREAD_PATH = 7, JP_MAKE_FROM = 8,
  JP_READ_INVERSE = 9, JP_HAS_SEARCH = 10, JP_GET_SEARCHABLE = 11,
  JP_READ_SEARCH = 12, JP_READ_OPTIONAL_VALUE = 13,
  JP_GET_TEST_VALUE = 14, JP_OPTIONAL_EQUALS_TEST = 15,
  JP_FIND_IS_ARRAY = 16, JP_FIND_COPY_ARRAY = 17, JP_FIND_ARRAY_SIZE = 18,
  JP_FIND_MATCH_AT = 19, JP_RESULT_BASE = 20, JP_RESULT_REMOVE = 21,
  JP_RESULT_ADD = 22, JP_RESULT_REPLACE = 23,
  JP_RESULT_SEARCH_REMOVE = 24, JP_RESULT_SEARCH_ADD = 25,
  JP_RESULT_SEARCH_REPLACE = 26, JP_RESULT_MOVE_ADD_SEARCH = 27,
  JP_RESULT_MOVE_REPLACE_FROM = 28, JP_READ_FROM_VALUE = 29,
  JP_RESULT_MOVE = 30, JP_RESULT_COPY_SEARCH = 31,
  JP_RESULT_MERGE_SEARCH = 32, JP_RESULT_MERGE = 33,
  JP_ADVANCE_BASE = 34, JP_MAKE_FAILURE = 35, JP_WRAP_JSON = 36,
  JP_CLEAR_TRAVERSAL = 37, JP_RECEIPT = 38,
  JP_FIND_RELEASE = 39, JP_HANDLER_RELEASE = 40, JP_APPLY_RELEASE = 41
};
enum StarJsonPatchPointerSelector { JP_TO = 0, JP_FROM = 1, JP_EXTERNAL_FIND = 2 };
enum StarJsonPatchFailure {
  JP_FIND_NOT_ARRAY = 0, JP_TEST_SEARCH_EXPECT_MISSING = 1,
  JP_TEST_SEARCH_NOT_FOUND = 2, JP_TEST_PATH_EXPECT_MISSING = 3,
  JP_TEST_VALUE_MISMATCH = 4, JP_TEST_TRAVERSAL_FAILURE = 5,
  JP_INVALID_OPERATION = 6
};
enum StarJsonPatchWrap { JP_WRAP_OPERATION = 0, JP_WRAP_PATCH = 1 };
enum StarJsonPatchReceipt { JP_ATTEMPT = 0, JP_SUCCEEDED = 1, JP_EXCEPTION = 2 };

/* Selectors use a on GET_SEARCHABLE and b on FIND_NOT_ARRAY.
 * n is used by PATCH_GET, FIND_MATCH_AT, and indexed result leaves 24..28/31/32.
 * MAKE_FAILURE uses a=failure, b=pointer only for FIND_NOT_ARRAY.
 * WRAP_JSON uses a=wrap; RECEIPT uses a=entry,b=receipt.
 * LOOKUP returns entry 3..9 from native case-sensitive StringMap lookup.
 * FIND returns 0/index+1 and writes scalar_out ONLY on successful direct FIND.
 * Other entries publish native Result only after overall SUCCESS. scalar_out
 * is required/live/aligned for every entry but remains untouched except a
 * successful direct FIND. The host context is opaque to a future controller;
 * the native thunk requires its valid non-null per-invocation context.
 * Missing initial fields, bad indices/selectors, unknown args/opcodes, and
 * impossible pending-error transitions reject BEFORE semantic work.
 * Ordinary ops require no pending error. RECEIPT exception is allowed while
 * Pending exists (success requires no Pending); cleanup always preserves it.
 * Wrapping/construction and recovery
 * must check the expected error category. Classify traversal before Json.
 * CLEAR_TRAVERSAL is the only successful recovery that clears Pending.
 * Cleanup 39..41 is noexcept, permitted while an error is pending, and MUST
 * preserve Pending/result/working base/Op JSON and the scalar result.
 * FIND_RELEASE destroys ONLY MatchArray at FIND exit, before caller mutation.
 * HANDLER_RELEASE destroys handler scratch after its lexical catches exit.
 * APPLY_RELEASE destroys Operation before its catch body or successful exit.
 * These explicit lifetimes avoid retaining COW snapshots across later writes.
 * Callback errors from a catch body leave that catch immediately: never route
 * a new error back through sibling catches. Exact native compound expressions
 * stay unsplit, preserving unspecified sibling evaluation on the tested compiler.
 * Prototype RECEIPT uses fixed storage/no throwing allocations; future Rust
 * instrumentation lives in its controller, not a throwable production callback.
 * No retry, retained pointers, global mutable context, or foreign unwinding. */
/* Callers guarantee live allocations, no foreign unwind, and exclusive scalar
 * output access. Preflight rejects null/misaligned/wrapping scalar spans and
 * unknown entries before callbacks or counters. Null custom context is allowed.
 * Counters are thread-local semantic invocations, including internal calls.
 * Panic/protocol abort after attempt may leave counters without an exit event. */
uint32_t star_json_patch_run(uint32_t entry, StarJsonPatchHost host,
    void* context, uint64_t* scalar_out);
uint64_t star_json_patch_call_count(uint32_t entry, uint32_t event);

#ifdef __cplusplus
}
#endif
