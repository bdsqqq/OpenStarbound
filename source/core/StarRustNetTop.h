#ifndef STAR_RUST_NET_TOP_H
#define STAR_RUST_NET_TOP_H

#include "StarRustNetGroup.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_NET_TOP_OK = 0,
  SB_NET_TOP_INVALID = 1,
  SB_NET_TOP_HOST_ERROR = 2,
  SB_NET_TOP_PANIC = 3
};
enum {
  SB_NET_TOP_WRITE = 0,
  SB_NET_TOP_READ = 1,
  SB_NET_TOP_PAYLOAD = 2,
  SB_NET_TOP_COUNT = 3
};
enum {
  SB_NET_TOP_WRITE_FULL = 0,
  SB_NET_TOP_STORE = 1,
  SB_NET_TOP_WRITE_DELTA_MARKER = 2,
  SB_NET_TOP_WRITE_DELTA = 3,
  SB_NET_TOP_BLANK = 4,
  SB_NET_TOP_SCOPED_PAYLOAD = 5,
  SB_NET_TOP_IS_FULL = 6,
  SB_NET_TOP_LOAD = 7,
  SB_NET_TOP_READ_DELTA = 8,
  SB_NET_TOP_OP_COUNT = 9
};

typedef SbNetGroupReply SbNetTopReply;
typedef SbNetGroupHost SbNetTopHost;

/* NetElementTop framing policy only. Shares the default-OFF NET_GROUP family
 * selector STAR_USE_RUST_NET_GROUP (42) and its runtime selection; no separate
 * family switch. C++ retains all storage, versions, streams and floating-point
 * arguments. The Group reply/host ABI is reused without conversion.
 *
 * WRITE argument accepts ANY uint64_t fromVersion. Zero: WRITE_FULL (native
 * ds.write<bool>(true)), STORE (qualified BaseNetElement::netStore), result=1.
 * Nonzero: WRITE_DELTA_MARKER (native ds.write<bool>(false)), WRITE_DELTA (whole
 * qualified BaseNetElement::writeNetDelta(ds, fromVersion, rules)), result=bool.
 * C++ constructs/configures the whole DataStreamBuffer before entry and keeps
 * each native braced pair return expression AFTER successful Rust return:
 * result=true returns {ds.takeData(), m_netVersion.increment()}; false returns
 * {ByteArray(), m_netVersion.current()}. Never move takeData, increment, current,
 * ByteArray construction or braced-pair evaluation into this policy.
 *
 * READ argument is bool(data.empty()): 1 calls BLANK (whole qualified native
 * blankNetDelta(interpolationTime)); 0 calls SCOPED_PAYLOAD. Result is zero.
 * SCOPED_PAYLOAD owns the WHOLE native nonempty branch scope: construct
 * DataStreamBuffer(std::move(data)), configure compatibility, synchronously
 * reenter PAYLOAD with that live stream capture, and propagate its status.
 * PAYLOAD argument MUST be zero: IS_FULL (native ds.read<bool>()), then LOAD
 * if true, otherwise READ_DELTA; result=0. LOAD/READ_DELTA retain whole qualified
 * BaseNetElement calls with native stream/rules/interpolationTime expressions.
 * C++ owns stream destruction on success AND failure; Rust issues no cleanup.
 *
 * Every leaf argument is zero. Replies start zeroed on every invocation.
 * WRITE_DELTA/IS_FULL return a=0 or 1,b=0; all other leaves return a=b=0.
 * Host statuses are only OK or HOST_ERROR. HOST_ERROR wins over malformed
 * replies; other statuses or malformed successful replies become INVALID.
 * Failure stops immediately, preserves prior native effects and leaves root
 * output untouched. Only successful roots write out_result.
 *
 * Catch ALL C++ exceptions inside host, retain exception_ptr, return HOST_ERROR,
 * and rethrow ONLY after Rust returns. No foreign unwind or callback panic may
 * cross Rust. The Rust barrier catches only ordinary Rust panics (PANIC).
 * Reentrant contexts/captures must remain live through synchronous callbacks;
 * do not hold native mutable guards across reentry unless the native API allows.
 *
 * Invalid mode, null ctx/host/out_result, output not aligned to 4, READ argument
 * >1 or nonzero PAYLOAD argument is INVALID BEFORE any counters/callbacks/output.
 * These checks do not prove provenance/liveness: caller supplies live captures
 * and aligned writable uint32_t output for the entire call. Rust neither
 * interprets nor retains ctx or any native pointer.
 */
uint32_t sb_net_top_run(uint32_t mode, void* ctx, SbNetTopHost host,
    uint64_t argument, uint32_t* out_result);

/* Wrapping, no-reset diagnostics: kind 0=current-thread accepted roots (<3),
 * kind 1=relaxed global accepted roots (<3), kind 2=relaxed global ATTEMPTED
 * leaves (<9), counted BEFORE host. Accepted failures count; rejected roots do
 * not. Invalid queries return zero. Independent loads are not an atomic snapshot,
 * completion observation or performance evidence.
 */
uint64_t sb_net_top_count(uint32_t kind, uint32_t index);

#ifdef __cplusplus
}
static_assert(sizeof(SbNetTopReply) == 16, "SbNetTopReply ABI size");
static_assert(alignof(SbNetTopReply) == 8, "SbNetTopReply ABI alignment");
#endif

#endif
