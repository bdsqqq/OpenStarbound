#ifndef STAR_RUST_PATH_EMBED_H
#define STAR_RUST_PATH_EMBED_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* numerical preflight is not pointer validation: callers provide live,
 * provenance-valid initialized input and writable output allocations; action
 * and written are nonnull, aligned, writable scalar objects. escape's input,
 * output (the full capacity), and written spans are pairwise disjoint. no
 * concurrent mutation; no pointer is retained. null buffers require zero size.
 * statuses: 0 success, 2 invalid preflight (outputs/counters unchanged),
 * 3 contained Rust panic (partial output is not guaranteed unchanged).
 * lengths must fit ptrdiff_t, capacity >= 2*length, length <= PTRDIFF_MAX/2. */
enum { STAR_PATH_EMBED_OK = 0, STAR_PATH_EMBED_INVALID = 2, STAR_PATH_EMBED_PANIC = 3 };
enum { STAR_PATH_EMBED_NONE = 0, STAR_PATH_EMBED_GZIP = 1,
       STAR_PATH_EMBED_ZLIB = 2, STAR_PATH_EMBED_ZSTD = 3 };
uint32_t star_path_embed_select(uint32_t method, uint32_t* action);
uint32_t star_path_embed_escape(const uint8_t* input, size_t length,
                              uint8_t* output, size_t capacity, size_t* written);
/* per-thread modulo-2^64 completions: 0 is a selector DECISION, before native
 * codec/allocation/throw; 1 is the full escape output and length publication.
 * invalid operation returns zero. these are not codec/facade completion counts. */
uint64_t star_path_embed_completed(uint32_t operation);
#ifdef __cplusplus
}
#endif
#endif
