#include "StarRustPathEmbed.h"
#define pe_select star_path_embed_select
#define pe_escape star_path_embed_escape
#define pe_completed star_path_embed_completed
#define PE_OK STAR_PATH_EMBED_OK
#define PE_INVALID STAR_PATH_EMBED_INVALID
#define PE_PANIC_RESERVED STAR_PATH_EMBED_PANIC
static inline uint32_t pe_span_eligible(size_t n, size_t capacity) {
  return n <= (size_t)PTRDIFF_MAX / 2 && capacity <= (size_t)PTRDIFF_MAX && capacity >= n * 2;
}
