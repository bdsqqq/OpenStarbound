#ifndef STAR_RUST_RANDOM_MWC_H
#define STAR_RUST_RANDOM_MWC_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Three independent semantic state spans: data[256], carry[1], index[1].
 * All spans (and next's out[1]) must be live, writable, naturally aligned,
 * pairwise disjoint and exclusively accessible for the call. The caller owns
 * allocation validity; null, misaligned, wrapping and overlapping spans fail.
 * init NEVER reads old state, which may be uninitialized. Entropy and next
 * require initialized state; every uint32_t carry and uint8_t index is valid.
 * No enclosing C++ object/padding access, allocation, callbacks or retention.
 * Status 0 commits state/output and one thread-local receipt; 2 invalid ABI,
 * 3 contained panic leave state/output/receipts unchanged. Never retry on error.
 * Internal warmup/entropy draws do not increment next's receipt.
 */
int32_t star_random_mwc_init(uint32_t* data, uint32_t* carry, uint8_t* index, uint64_t seed);
int32_t star_random_mwc_add_entropy(uint32_t* data, uint32_t* carry, uint8_t* index, uint64_t seed);
int32_t star_random_mwc_next(uint32_t* data, uint32_t* carry, uint8_t* index, uint32_t* out);
/* op 0 init, 1 entropy, 2 next; unknown op returns zero. */
uint64_t star_random_mwc_call_count(uint32_t op);
#ifdef __cplusplus
}
#endif
#endif
