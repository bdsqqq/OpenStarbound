#ifndef STAR_RUST_TIME_H
#define STAR_RUST_TIME_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_TIME_OK = 0,
  SB_TIME_INVALID = 1,
  SB_TIME_DOMAIN = 2,
  SB_TIME_PANIC = 3
};

enum {
  SB_TIME_TO_MILLISECONDS = 0,
  SB_TIME_TO_MICROSECONDS = 1,
  SB_TIME_FROM_MILLISECONDS = 2,
  SB_TIME_FROM_MICROSECONDS = 3,
  SB_TIME_COUNT = 4
};

/* all int64_t input words are accepted at the ABI, including negative/zero
 * frequencies. scale is 1000 or 1000000. preserve native signed order:
 *   roundedFrequency = frequency + scale/2;
 *   factor = roundedFrequency / scale;
 *   TO:   numerator = value + factor/2; result = numerator / factor;
 *   FROM: result = value * factor;
 * division truncates toward zero. the positive bias is intentionally asymmetric
 * for negative values; widening/reassociation would change native definedness.
 * FROM with factor zero succeeds with zero; TO with factor zero is DOMAIN.
 *
 * DOMAIN means an original native signed intermediate would overflow, divide by
 * zero, or divide INT64_MIN by -1. it is NOT an invalid-frequency policy. the
 * C++ caller must execute the ORIGINAL native expression on DOMAIN, preserving
 * its unsupported native undefined behavior rather than repairing it with zero,
 * wrapping or an exception. other non-OK statuses become native logic_error.
 * clocks, platform calls and floating-point conversions stay outside this ABI.
 *
 * unknown op, null out and out not aligned to 8 bytes return INVALID before
 * counts, writes or dereferences. accepted calls require live writable storage
 * for one 8-byte int64_t; numeric checks cannot prove provenance, liveness or
 * writability. inputs are BY VALUE, so there is no borrowed input to alias out.
 * ONLY OK writes out. DOMAIN and caught Rust PANIC leave it unchanged.
 * no pointer is retained, no callback/clock/FP runs, no allocation/new runtime
 * is introduced, and no native exception may unwind through Rust.
 */
uint32_t sb_time_convert(uint32_t op, int64_t value, int64_t frequency,
    int64_t* out);

/* four slots per bank, wrapping modulo 2^64. kind 0: calling-thread accepted
 * entries; kind 1: relaxed atomic global accepted entries; kind 2: relaxed
 * atomic global DOMAIN returns. accepted entries include DOMAIN and PANIC.
 * rejected ABI calls never increment any bank. invalid kind/op returns zero.
 * global reads are neither a multi-slot snapshot nor a synchronization barrier.
 */
uint64_t sb_time_count(uint32_t kind, uint32_t op);

#ifdef __cplusplus
}
#endif

#endif
