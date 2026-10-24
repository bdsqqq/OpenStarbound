#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Synchronous, ordered, lazy visits. No pointers are retained. The visitor must
 * not unwind; 0 stops, any nonzero value continues. Context may be null.
 * Status: 0 completed, 1 stopped, 2 invalid input/policy, 3 caught Rust panic.
 * Policy: 0 uncontracted precise; 1 Apple clang 21 ARM fast-math;
 * 2 Apple clang 21 ARM default non-fast contraction (no reassociation).
 * Inputs require finite Scalar endpoints and int32-representable floors and
 * diagonal setup arithmetic. Undefined C++ suffix overflow is safely extended.
 */
typedef int32_t (*StarBlocksVisitor)(void* context, int32_t x, int32_t y);
int32_t star_blocks_along_line_f32(float ox, float oy, float dx, float dy,
    uint32_t policy, StarBlocksVisitor visitor, void* context);
int32_t star_blocks_along_line_f64(double ox, double oy, double dx, double dy,
    uint32_t policy, StarBlocksVisitor visitor, void* context);
/* Executing-thread receipt: completed/stopped calls only, including nested calls.
 * Wrapping uint64 counter; never use this diagnostic to choose simulation behavior. */
uint64_t star_blocks_along_line_call_count(void);

#ifdef __cplusplus
}
#endif
