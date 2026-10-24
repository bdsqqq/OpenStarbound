#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Byte scanner only: no UTF-8 decoding, copying, or retained pointers.
 * Input stays live through return; callbacks may edit bytes without reallocating
 * and may reenter. Command boundaries are found BEFORE the preceding text host
 * call; later scanning observes edits. No foreign unwinding is permitted.
 * host/context are opaque (a custom host may accept NULL context).
 * Native context must be a live, non-null per-invocation context.
 * Host: 0 continue, 1 stop, 2 native exception pending, 3 invalid.
 * Kind: 0 text, 1 command. Spans are byte offsets in the original input.
 * Run: 0 success, 1 native exception pending, 2 ABI invalid, 3 Rust panic.
 * out_bool is required/live for one byte, exclusively writable, and written
 * ONLY on success (0 stopped, 1 completed). Input/output may overlap: all reads
 * finish before publication. NULL input is allowed iff length is zero; empty
 * non-null input need not be dereferenceable. Flags must be 0 or 1.
 * Metadata rejection precedes counters/callbacks/output writes. Callers own
 * allocation validity. No retry or static parser context. Panic/protocol abort
 * after entry can leave partial attempt counters. */
typedef uint32_t (*StarTextScanHost)(void* context, uint32_t kind,
    uint64_t offset, uint64_t length);
uint32_t star_text_scan_process(uint8_t const* data, uint64_t length,
    uint8_t has_commands, uint8_t include_sides, StarTextScanHost host,
    void* context, uint8_t* out_bool);
/* Thread-local attempts: 0 invocation, 1 text host, 2 command host; unknown=0.
 * Includes stopped/throwing host attempts and nested invocations. */
uint64_t star_text_scan_call_count(uint32_t index);

#ifdef __cplusplus
}
#endif
