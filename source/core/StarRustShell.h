#ifndef STAR_RUST_SHELL_H
#define STAR_RUST_SHELL_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Borrowed, initialized UTF-32 input; callbacks may mutate future input.
 * All spans must be live, aligned and non-overlapping with the two writable
 * outputs. Callbacks are required even for empty input; ctx may be null.
 * Callback nonzero aborts. No foreign exception may cross this boundary.
 * Events: 0 append cp, 1 complete word (cp=0). Completed words count only
 * successful event 1 calls. Status 0 complete, 1 abort, 2 invalid ABI (outputs
 * untouched), 3 contained panic. Never retry after execution/partial output.
 * Counts and quote describe partial execution on status 1. No pointers retained.
 * Allocation-failure timing differs from the historical allocating facade. */
typedef int32_t (*StarShellClassify)(void* ctx, uint32_t cp, uint32_t* is_hex);
typedef int32_t (*StarShellEmit)(void* ctx, uint32_t event, uint32_t cp);
int32_t star_shell_tokenize(uint32_t const* input, size_t len,
    StarShellClassify classify, StarShellEmit emit, void* ctx,
    size_t* token_count, uint32_t* final_quote);
uint64_t star_shell_call_count(void);
#ifdef __cplusplus
}
#endif
#endif
