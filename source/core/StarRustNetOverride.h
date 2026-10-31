#ifndef STAR_RUST_NET_OVERRIDE_H
#define STAR_RUST_NET_OVERRIDE_H
#include "StarRustNetGroup.h"
#ifdef __cplusplus
extern "C" {
#endif

enum {
  SB_NET_OVERRIDE_STORE = 0,
  SB_NET_OVERRIDE_LOAD = 1,
  SB_NET_OVERRIDE_WRITE = 2,
  SB_NET_OVERRIDE_READ = 3,
  SB_NET_OVERRIDE_COUNT = 4
};
enum {
  SB_NET_OVERRIDE_HAS = 0,
  SB_NET_OVERRIDE_CALL_OVERRIDE = 1,
  SB_NET_OVERRIDE_CALL_BASE = 2,
  SB_NET_OVERRIDE_OP_COUNT = 3
};
typedef SbNetGroupReply SbNetOverrideReply;
typedef SbNetGroupHost SbNetOverrideHost;

/* Control only, same NET_GROUP selector/aggregate/runtime and Group ABI.
 * Native std::function storage, setter order, captures, target lifetime,
 * invocation, qualified Base calls, streams and float/rules/version arguments
 * remain C++. No callback copy or new rules guard is introduced.
 * All root/leaf arguments are zero. HAS replies with strict boolean a/b=0.
 * Invocation replies are strict boolean only for WRITE, otherwise a=b=0.
 * WRITE publishes that boolean; other successful roots publish zero. Native
 * exceptions must be caught by the host and rethrown ONLY after Rust returns.
 * ctx/host/aligned writable out_result must remain valid through synchronous
 * reentry; Rust does not retain or dereference native context pointers.
 * Status: OK0, INVALID1, HOST2, PANIC3; errors leave output/prefix effects alone.
 * count kind0=TLS accepted roots,1=global roots,2=attempted leaves; unknown0.
 */
uint32_t sb_net_override_run(uint32_t mode, void* ctx, SbNetOverrideHost host,
    uint64_t argument, uint32_t* out_result);
uint64_t sb_net_override_count(uint32_t kind, uint32_t index);
#ifdef __cplusplus
}
#endif
#endif
