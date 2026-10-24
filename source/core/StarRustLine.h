#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct StarLineInputF32 { float a[2], b[2], c[2], d[2]; } StarLineInputF32;
typedef struct StarLineInputF64 { double a[2], b[2], c[2], d[2]; } StarLineInputF64;
typedef struct StarLineResultF32 {
  float point[2], t;
  uint32_t intersects, coincides, glances;
} StarLineResultF32;
typedef struct StarLineResultF64 {
  double point[2], t;
  uint32_t intersects, coincides, glances;
} StarLineResultF64;

/* Borrowed initialized input and exclusively writable output; no retained pointers.
 * Allocations must be valid for their declared types and must not overlap.
 * mode: 0 intersection a->b/c->d, 1 projection of c onto a->b,
 * 2 distance from c to a->b. For modes 1/2 only t carries the scalar result;
 * other result fields are zero. infinite must be 0 or 1 (ignored for mode 1).
 * policy: 0 uncontracted; 1 sampled Apple clang 21 ARM fast expression profile;
 * 2 ARM default contraction. Policy 1 is NOT production-qualified: original
 * fast-math contraction/reassociation varies with inlining context, and the
 * frozen adversarial oracle currently fails. The C++ adapter rejects fast-math
 * builds rather than selecting policy 1. Keep the backend default OFF.
 * Nonstandard flags/platforms are not calibrated. IEEE nonfinite results are
 * observations, not invalid-input statuses.
 * status: 0 success, 2 invalid pointer/alignment/overlap/mode/policy/boolean,
 * 3 contained panic. Nonzero statuses leave output untouched. Pointer checks
 * cannot establish allocation provenance; that remains the caller's obligation.
 */
int32_t star_line_query_f32(StarLineInputF32 const* input, uint32_t mode,
    uint32_t infinite, uint32_t policy, StarLineResultF32* output);
int32_t star_line_query_f64(StarLineInputF64 const* input, uint32_t mode,
    uint32_t infinite, uint32_t policy, StarLineResultF64* output);
/* Executing-thread wrapping receipt; successful calls only. Diagnostic only. */
uint64_t star_line_query_call_count(void);

#ifdef __cplusplus
}
#endif
