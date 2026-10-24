#ifndef STAR_RUST_ASSET_PATH_H
#define STAR_RUST_ASSET_PATH_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Byte offsets, not codepoint positions. SIZE_MAX denotes NPos. sub_count is
 * the original std::string::substr count (including wrapping subtraction),
 * not a clamped length; range.end is absolute, NOT a substring count.
 * Input must be initialized, readable and immutable for the whole call.
 * Null input is allowed only for len zero; len must not exceed PTRDIFF_MAX.
 * Output must be live, aligned, writable and disjoint from ALL len input bytes.
 * No allocation, callbacks, UTF-8 validation, normalization or pointer retention.
 * Status 0 success, 2 invalid ABI, 3 contained panic; outputs change only on 0.
 * Never retry/fallback after failure. Receipts count successful calls per thread.
 * Allocation failure in subsequent C++ materialization is outside this ABI. */
typedef struct {
  size_t base_len, sub_start, sub_count, directive_start;
} StarAssetPathSplit;
typedef struct {
  size_t start, end;
} StarAssetPathRange;
int32_t star_asset_path_split(uint8_t const* input, size_t len, StarAssetPathSplit* out);
int32_t star_asset_path_filename_range(uint8_t const* input, size_t len, StarAssetPathRange* out);
/* op 0 split, 1 filename range; unknown op returns zero. */
uint64_t star_asset_path_call_count(uint32_t op);
#ifdef __cplusplus
}
#endif
#endif
