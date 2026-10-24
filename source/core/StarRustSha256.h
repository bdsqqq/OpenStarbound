#ifndef STAR_RUST_SHA256_H
#define STAR_RUST_SHA256_H
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct StarSha256State {
  uint32_t state[8], length, curlen;
  uint8_t buf[64];
} StarSha256State;

/* borrowed state; update/finalize require all bytes initialized (init does so).
 * no allocation or pointer retention. status 0 is
 * success, 2 invalid shape, 3 contained panic. errors leave state/output intact.
 * null input is allowed only when empty; output requires capacity >= 32.
 * update input/state and finalize output/state must not overlap. oneshot input
 * and output may overlap. callers guarantee live allocations, not just ranges.
 * length deliberately wraps at 2^32 bits, matching the legacy implementation. */
int32_t star_sha256_init(StarSha256State* state);
int32_t star_sha256_update(StarSha256State* state, const uint8_t* input, size_t input_len);
int32_t star_sha256_finalize(StarSha256State* state, uint8_t* out, size_t out_capacity);
int32_t star_sha256_oneshot(const uint8_t* input, size_t input_len, uint8_t* out, size_t out_capacity);
/* successful operations on this thread: 0 init, 1 update, 2 finalize, 3 oneshot. */
uint64_t star_sha256_call_count(uint32_t operation);

#ifdef __cplusplus
}
static_assert(sizeof(StarSha256State) == 104 && alignof(StarSha256State) == 4, "SHA256 ABI");
#else
_Static_assert(sizeof(StarSha256State) == 104 && _Alignof(StarSha256State) == 4, "SHA256 ABI");
#endif
#endif
