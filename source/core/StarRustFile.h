#ifndef STAR_RUST_FILE_H
#define STAR_RUST_FILE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef uint32_t (*StarFileHost)(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*);
/*
 * Internal synchronous controller ABI, not general pointer validation.
 * The host owns live native state and supplies bounded scalars in the expected
 * operation order. Output storage must be live, aligned, and disjoint from all
 * reachable native state. Native buffers are never borrowed by Rust.
 * 0 success, 1 captured native exception, 2 protocol error, 3 contained Rust
 * panic. A C++ exception must NEVER unwind through Rust.
 * Counters describe controller entry; typed native setup may precede it.
 */
uint32_t star_file_run(uint32_t,void*,StarFileHost);
uint64_t star_file_call_count(uint32_t,uint32_t);
#ifdef __cplusplus
}
#endif
#endif
