#ifndef STAR_RUST_JSON_PATH_H
#define STAR_RUST_JSON_PATH_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* kind: 0 RFC6901 pointer, 1 query segment. hint: 0 Array, 1 Object.
 * Host ops: 0 clear, 1 atEnd, 2 dereference, 3 ++iterator,
 * 4 buffer.append(*iterator++), 5 append(arg), 6 index classification,
 * 7 buffer == "-". out is ignored for ops 0/3/4/5; otherwise scalar.
 * Required host, even for empty input; ctx may be null. Nonzero host return
 * aborts; foreign exceptions must be caught by the host, never cross this ABI.
 * Outputs must be live, aligned, disjoint writable uint32_t objects.
 * Status 0 complete (including grammar error), 1 host abort, 2 invalid ABI,
 * 3 contained panic. Status 1/2/3 leave outputs untouched. On grammar error,
 * error is written but hint is untouched. Error: 0 none, 1 missing slash,
 * 2 incomplete escape, 3 invalid escape, 4 leading dot, 5 invalid array entry.
 * No pointers retained; never retry partial execution. Receipts are per-thread,
 * per-kind and count status 0/1 only. No staging allocation is introduced. */
typedef int32_t (*StarJsonPathHost)(void* ctx, uint32_t op, uint32_t arg, uint32_t* out);
int32_t star_json_path_parse(uint32_t kind, StarJsonPathHost host, void* ctx,
    uint32_t* type_hint, uint32_t* grammar_error);
uint64_t star_json_path_call_count(uint32_t kind);
#ifdef __cplusplus
}
#endif
#endif
