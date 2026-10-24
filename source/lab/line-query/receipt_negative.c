#include "StarRustLine.h"
/* Isolated known failure: success status but no executing-backend receipt. */
int32_t star_line_query_f32(StarLineInputF32 const* input, uint32_t mode,
    uint32_t infinite, uint32_t policy, StarLineResultF32* output) {
  (void)input; (void)mode; (void)infinite; (void)policy;
  *output = (StarLineResultF32){0};
  return 0;
}
int32_t star_line_query_f64(StarLineInputF64 const* input, uint32_t mode,
    uint32_t infinite, uint32_t policy, StarLineResultF64* output) {
  (void)input; (void)mode; (void)infinite; (void)policy;
  *output = (StarLineResultF64){0};
  return 0;
}
uint64_t star_line_query_call_count(void) { return 0; }
