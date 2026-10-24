#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Lab-only opaque proposal. Four control graphs, not vendor codec rewrites. */
typedef uint32_t (*StarZstdHost)(void* context, uint32_t opcode,
    uint64_t arg0, uint64_t arg1, uint64_t* scalar_out);
typedef uint32_t (*StarZstdRun)(uint32_t mode, StarZstdHost host, void* context);
enum StarZstdMode { ZC_STREAM_COMPRESS=0, ZC_STREAM_DECOMPRESS=1,
  ZC_ONESHOT_COMPRESS=2, ZC_ONESHOT_DECOMPRESS=3 };
enum StarZstdHostStatus { ZC_OK=0, ZC_EXCEPTION=1, ZC_HOST_INVALID=2 };
enum StarZstdRunStatus { ZC_COMPLETE=0, ZC_NATIVE_PENDING=1, ZC_INVALID=2, ZC_PANIC=3 };
enum StarZstdOpcode {
  ZC_BEGIN=0, ZC_GET=1, ZC_STREAM_CHUNK=2, ZC_INIT_INPUT=3,
  ZC_RESIZE_STREAM=4, ZC_PREPARE_OUT=5, ZC_STEP_COMPRESS=6,
  ZC_STEP_DECOMPRESS=7, ZC_COMPRESS_BOUND=8, ZC_FRAME_SIZE=9,
  ZC_ALLOC_RESULT_ZERO=10, ZC_ONESHOT_COMPRESS_CALL=11,
  ZC_ONESHOT_DECOMPRESS_CALL=12, ZC_IS_ERROR=13,
  ZC_RAISE_CODEC=14, ZC_RAISE_SIZE=15, ZC_RESIZE_RESULT=16,
  ZC_EMPTY_RESULT=17
};
enum StarZstdField {
  ZC_INPUT_LENGTH=0, ZC_INPUT_POS=1, ZC_INPUT_SIZE=2,
  ZC_OUTPUT_SIZE=3, ZC_OUTPUT_POS=4, ZC_OUTPUT_CAPACITY=5,
  ZC_FRAME_UNKNOWN=6, ZC_FRAME_ERROR=7, ZC_NATIVE_SIZE_MAX=8
};

/* Caller supplies a live, type-valid, single-invocation native context and
 * exclusive live input/native output/stream allocations. Borrowed persistent
 * handles remain C++ owned; no reset/retry/free operation exists here. Distinct
 * contexts AND distinct stream handles support reentry; same-context/handle
 * concurrent use is outside the native API domain. No controller may read a
 * native class, inspect host identity, retain pointers, or hold Rust references
 * into native buffers across callbacks. No whole legacy handler is a leaf.
 *
 * BEGIN arg0=mode must match context before work; GET arg0=field. RESIZE/ALLOC
 * arg0=size, PREPARE_OUT arg0=offset,arg1=capacity; IS_ERROR/RAISE_CODEC arg0=
 * complete native size_t return. All other unused args are zero. EVERY call
 * requires scalar_out live/writable/8-aligned/nonwrapping for eight bytes,
 * disjoint from context storage, including void leaves. Success writes the
 * scalar (zero for void); exception/invalid metadata does not write it.
 * Validate opcode/args/mode/state/span/pending/reentry before mutation. Pending
 * is sticky; later host calls are invalid without replacing the exception_ptr.
 * C++ catches all native exceptions, and the outer invocation rethrows the same
 * pointer WHILE its result/context lives. One-shot result move/assignment occurs
 * only after overall COMPLETE; streaming output is intentionally nontransactional.
 * Context/result destruction follows ordinary C++ return/unwind, not an early
 * cleanup callback. Persistent codec state survives exceptions unchanged by any
 * added reset/retry. Raw pointer allocation validity is a caller precondition.
 *
 * Supported target assertions establish size_t/ULL/scalar are 64 bits. Scalars
 * preserve FULL native codec return values (NOT zlib's low32 encoding). Driver
 * arithmetic has native unsigned wrapping semantics; no debug overflow traps or
 * new smaller length domain. GET never calls a codec. STREAM_CHUNK calls the
 * appropriate recommendation once; INIT_INPUT then creates native inBuffer
 * {captured_ptr,full_length,0}, before any output resize. GET output size reads
 * actual ByteArray::size; other fields read native in/out metadata or constants.
 *
 * Stream graph: chunk, INIT_INPUT, written=GET_OUT_SIZE, RESIZE(GET_OUT_SIZE+
 * chunk). DO at least once (even empty input): PREPARE_OUT(written,min(chunk,
 * GET_OUT_SIZE-written)); one STEP (compress uses ZSTD_e_flush); IS_ERROR, then
 * native error construction if true BEFORE updating written. written+=out.pos;
 * if out.pos==out.size: if written>=GET_OUT_SIZE, RESIZE(GET_OUT_SIZE*2);
 * CONTINUE before finished comparison, even when input is consumed/ret==0.
 * Otherwise compress finishes iff ret==0 AND in.pos==in.size; decompress finishes
 * on in.pos==in.size ALONE, regardless of frame completion. Finally RESIZE(written).
 * Step/resize exceptions preserve advanced codec state and source-equivalent
 * output size/prefix; do not shrink or retry on errors.
 *
 * Plain ByteArray resize does NOT initialize expanded tail. Lab comparisons
 * must preinitialize real backing capacity and assert it stays live, or inspect
 * only proven initialized extents plus metadata. Never hex/memcmp an unknown
 * failure tail. Captured stream input may alias output only where allocation
 * remains live; don't stage input to hide legacy reallocating-alias invalidity.
 *
 * One-shot compression: GET_INPUT_LENGTH==0 -> EMPTY_RESULT (native ByteArray());
 * else COMPRESS_BOUND, ALLOC_RESULT_ZERO(bound), native compress at captured
 * level, IS_ERROR, exact native error or RESIZE_RESULT(ret). Decompression:
 * FRAME_SIZE -> compare FULL native UNKNOWN/ERROR constants -> RAISE_SIZE before
 * allocation if either; ALLOC_RESULT_ZERO(native frame-size conversion), native
 * decompress, IS_ERROR, exact native error or RESIZE_RESULT(ret). Native error
 * leaves call ZSTD_getErrorName and retain exact original IOException text.
 * ALLOC uses actual ByteArray(size,0), not uninitialized resize. All allocating
 * and forwarding public facades/constructors/destructors remain outside this
 * status driver. No foreign unwind and no C++ execution fallback.
 *
 * Run preflight rejects unknown mode/missing host before callbacks. Host requires
 * valid native context; a custom host may accept opaque NULL context. This C++
 * lab driver is a proposed future Rust boundary, not a production/game port. */

#ifdef __cplusplus
}
#endif
