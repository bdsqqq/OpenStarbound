#ifndef STAR_RUST_NET_SCALAR_H
#define STAR_RUST_NET_SCALAR_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_NET_SCALAR_OK = 0,
  SB_NET_SCALAR_INVALID = 1,
  SB_NET_SCALAR_PANIC = 3
};
enum {
  SB_NET_SCALAR_NEXT = 0,
  SB_NET_SCALAR_PULL = 1,
  SB_NET_SCALAR_CLAMP = 2,
  SB_NET_SCALAR_SIZE_ENCODE = 3,
  SB_NET_SCALAR_SIZE_DECODE = 4,
  SB_NET_SCALAR_VERSION_NEXT = 5,
  SB_NET_SCALAR_COMPAT = 6,
  SB_NET_SCALAR_COUNT = 7
};

typedef struct SbNetScalarReply {
  uint64_t value;
  uint64_t pulled;
} SbNetScalarReply;

/* by-value event/size kernels retain STAR_USE_RUST_NET_FIELD; base-version
 * kernels use the existing STAR_USE_RUST_NET_GROUP selector/runtime instead.
 * both selectors default OFF; no new selector or runtime is introduced.
 * no callbacks, input pointers, heap allocation or floating-point operations.
 * this does not retire the field/event/size classes: native c++ still owns
 * storage, streams, assertions, typed operations and virtual updated ordering.
 * native callers commit returned scalar state ONLY after an OK status.
 *
 * NEXT: word_bits=0, previous=0; value wraps modulo 2^64 on increment.
 * native trigger still calls set(result), including its virtual updated hook.
 * PULL: word_bits=0; value=current, previous=pulled. returns wrapping current
 * minus pulled in reply.value and current in reply.pulled. ALL u64 pairs are
 * accepted here. keep native starAssert(current >= pulled) BEFORE this ABI:
 * that assertion is a native contract, not a reason to reject raw unsigned
 * subtraction inputs in this kernel. commit m_pulledOccurrences after OK.
 * CLAMP: word_bits=0; reply.value=min(current=value, pulled=previous).
 * native updated first calls its base hook, then clamps pulled to current.
 * NEXT/CLAMP do not repair native MAX->0 trigger behavior: the virtual hook
 * clamps pulled to zero and a subsequent pull may lose the wrapped event.
 *
 * SIZE_ENCODE: word_bits=32 or 64, previous=0, value<=MAXwidth; returns zero
 * for MAXwidth (native NPos), otherwise value+1. native stream writing stays
 * outside rust and retains its existing exception/partial-write behavior.
 * SIZE_DECODE: word_bits=32 or 64, previous=0; accepts EVERY u64 wire value.
 * zero returns MAXwidth; otherwise returns (wire-1) modulo 2^word_bits.
 * this preserves native size_t truncation, NOT a clamp: wire UINT64_MAX at
 * width 32 decodes to UINT32_MAX-1. NPos is the zero-wire sentinel, not a
 * license to reject or specially interpret maximal nonzero wire values.
 * VERSION_NEXT: word_bits=0, previous=0; every u64 value is accepted and
 * increment wraps modulo 2^64, sharing NEXT arithmetic but not its counter.
 * native NetElementVersion commits reply.value before returning it; its u64
 * storage, default zero, copies and trivial getter remain native.
 * COMPAT: word_bits=32 ONLY; value=stored compatibility version and
 * previous=rules version, both <=UINT32_MAX. returns u64 boolean
 * (value==UINT32_MAX || previous>=value). raw UINT32_MAX is accepted as Any.
 * native checkWithRules MUST retain its outer AnyVersion guard BEFORE reading
 * rules.version(): passing that read here unconditionally would expand the
 * native read domain despite an equivalent boolean result.
 * reply.pulled is zero except for PULL; each successful reply writes both
 * fields, size 16/alignment 8, value offset 0 and pulled offset 8.
 *
 * null output, output not aligned to 8, invalid mode, unused nonzero bits or
 * previous, invalid width or encode/compat range returns INVALID BEFORE counters,
 * dereference or write. otherwise output must be a live writable 16-byte
 * object; address checks cannot establish provenance or liveness. there are
 * no input-pointer/output alias requirements because inputs are by value.
 * output is unchanged on any non-OK return. rust catch_unwind contains rust
 * panics as PANIC; native state must not be committed on that status.
 */
uint32_t sb_net_scalar_run(uint32_t mode, uint32_t word_bits,
    uint64_t value, uint64_t previous, SbNetScalarReply* out);

/* kind 0=current-thread accepted entries; kind 1=relaxed all-thread accepted
 * entries. seven wrapping u64 counters in each set, retaining the original
 * five-mode numeric prefix; accepted entries count
 * before computation, including a later panic. rejected calls never count.
 * invalid kind/mode queries return zero; no reset API. independent relaxed
 * loads are not synchronized snapshots, completion or performance evidence.
 */
uint64_t sb_net_scalar_count(uint32_t kind, uint32_t mode);

#ifdef __cplusplus
}
static_assert(sizeof(SbNetScalarReply) == 16, "SbNetScalarReply ABI size");
static_assert(alignof(SbNetScalarReply) == 8, "SbNetScalarReply ABI alignment");
static_assert(offsetof(SbNetScalarReply, value) == 0, "SbNetScalarReply value offset");
static_assert(offsetof(SbNetScalarReply, pulled) == 8, "SbNetScalarReply pulled offset");
#else
_Static_assert(sizeof(SbNetScalarReply) == 16, "SbNetScalarReply ABI size");
_Static_assert(_Alignof(SbNetScalarReply) == 8, "SbNetScalarReply ABI alignment");
_Static_assert(offsetof(SbNetScalarReply, value) == 0, "SbNetScalarReply value offset");
_Static_assert(offsetof(SbNetScalarReply, pulled) == 8, "SbNetScalarReply pulled offset");
#endif

#endif
