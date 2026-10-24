#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Lab-only proposal: controllers branch/loop; native leaves retain ByteArray,
 * temp ownership, zng_stream, integer conversions and the same exception_ptr.
 * No complete Star compression handler may be a host operation. */
typedef uint32_t (*StarCompressionHost)(void* context, uint32_t opcode,
    uint64_t argument, uint64_t* scalar_out);
typedef uint32_t (*StarCompressionRun)(uint32_t kind, StarCompressionHost host,
    void* context);

enum StarCompressionKind { SC_DEFLATE=0, SC_INFLATE=1, SC_GZIP=2 };
enum StarCompressionHostStatus { SC_OK=0, SC_EXCEPTION=1, SC_HOST_INVALID=2 };
enum StarCompressionRunStatus { SC_COMPLETE=0, SC_NATIVE_PENDING=1, SC_INVALID=2, SC_PANIC=3 };
enum StarCompressionOpcode {
  SC_CLEAR_OUTPUT=0, SC_INPUT_EMPTY=1, SC_ALLOCATE_TEMP=2, SC_ZERO_STREAM=3,
  SC_INIT_CODEC=4, SC_BIND_INPUT=5, SC_RESET_OUTPUT=6, SC_STEP_FINISH=7,
  SC_AVAIL_OUT=8, SC_APPEND_TEMP=9, SC_READ_LIMIT=10, SC_OUTPUT_SIZE=11,
  SC_END_CODEC=12, SC_RAISE_INIT=13, SC_RAISE_CODEC=14, SC_RAISE_LIMIT=15
};

/* The native context is live/non-null, per-invocation, single-use and owns
 * no automatic codec-End destructor. Separate contexts permit reentry; the
 * same context cannot reenter an active callback/controller. Raw context
 * allocation validity remains a caller precondition; native values/layouts
 * never cross this ABI. The surrounding native wrapper rethrows pending while
 * the context lives, so temp destruction follows the original unwind scope.
 * Releasing a temp MUST NOT implicitly End an abandoned codec on exception.
 * Test-only reclamation is distinct, after legacy trace assertions.
 *
 * CLEAR_OUTPUT argument is kind (0..2), validated against native context kind
 * BEFORE clear; all other unused arguments are zero. APPEND_TEMP takes 0..32768.
 * RAISE_INIT/CODEC take the zero-extended low32 two's-complement codec status,
 * high32 MUST be zero; host codec results use this encoding too. Host errors
 * are separate from codec results (BUF_ERROR=-5 encodes as 4294967291).
 * Native int level and size_t length narrowing remain native leaves: avail_in
 * gets assigned ONCE to uint32_t after successful Init; no input replenishment.
 * Deflate input remains a ByteArray reference read AFTER output clear; inflate
 * input pointer/full size_t length are captured before controller entry.
 * No raw full-length slice/domain assumption replaces that narrowing.
 *
 * Every host scalar_out is required/live/eight-aligned/nonwrapping for 8 bytes,
 * disjoint from native context storage. Reject opcode/arg/state/pending/reentry
 * BEFORE mutation. Scalar is written only on host success (zero for void ops);
 * exceptions/invalid metadata leave it untouched. Capture exception_ptr once;
 * pending forbids all further host ops. No foreign unwind or C++ retry.
 *
 * Order: clear, empty -> early complete; allocate ZERO-INITIALIZED 32768-byte
 * temp, zero stream+allocation fields, Init. Init failure raises with NO End.
 * Bind input then reset output. While code==OK (or BUF_ERROR for inflates):
 * Step(FINISH), read avail_out EVEN ON CODEC ERROR. If full: append32768,
 * reset output, then (inflates only) read limit; limit0 skips OUTPUT_SIZE;
 * size>=limit calls End then raises limit. Else inflate BUF_ERROR breaks.
 * End after loop; ignore its codec return, preserve last Init/Step code.
 * Non-STREAM_END raises exact native error, discarding temp partial bytes.
 * Success appends 32768-AVAIL_OUT read AFTER End, including a zero-length tail.
 * Full append exception: NO End. Tail append exception: End already happened.
 * Init/codec/limit error constructors retain exact legacy text and integer
 * formatting, including deflate's incorrect 'uncompressData' wording.
 *
 * State validation must require temp before zero, zero before Init, successful
 * Init before input bind, bind/full-append before output reset, reset before
 * Step, Step/ended before avail read, full append size32768 before reset, and
 * ended+STREAM_END+exact remaining count for tail append. Limit/size reads are
 * inflate-only; error construction checks prior native status/limit observation
 * without introducing extra observable native getters. End cannot repeat or run
 * after failed Init; ordinary release never adds cleanup missing in legacy.
 *
 * Run preflight unknown kind/missing host is INVALID with no callbacks. A native
 * thunk rejects null context. Completion/pending/invalid never retries. This
 * phase's driver is C++, NOT a Rust production implementation or game proof. */

#ifdef __cplusplus
}
#endif
