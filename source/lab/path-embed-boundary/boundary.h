#ifndef PATH_EMBED_BOUNDARY_H
#define PATH_EMBED_BOUNDARY_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Private native reference, not a production ABI. Status 3 is reserved for a
 * future contained Rust panic. This native implementation cannot return it.
 * All nonempty buffers must have live initialized storage and proper provenance;
 * output storage must be writable. No concurrent mutation or retained borrows.
 * Numerical checks are NOT general pointer validation. Invalid preflight leaves
 * output, written, and completed-operation counters unchanged. */
enum { PE_OK = 0, PE_INVALID = 2, PE_PANIC_RESERVED = 3 };
enum { PE_NONE = 0, PE_GZIP = 1, PE_ZLIB = 2, PE_ZSTD = 3 };
uint32_t pe_select(uint32_t method, uint32_t* action);
uint32_t pe_escape(const uint8_t* input, size_t length, uint8_t* output,
                   size_t capacity, size_t* written);
/* Eligibility arithmetic only: callers still own storage/provenance checks. */
uint32_t pe_span_eligible(size_t length, size_t capacity);
/* 0: selector completed, BEFORE any codec or native exception; 1: byte loop
 * completed. Unsigned counters wrap modulo 2^64, are per-thread, not timing. */
uint64_t pe_completed(uint32_t operation);
#ifdef __cplusplus
}
#endif
#endif
