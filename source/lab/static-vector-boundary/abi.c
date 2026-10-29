#include <stddef.h>
#include "StarRustStaticVector.h"
_Static_assert(sizeof(SbStaticVectorRequest) == 32, "request bytes");
_Static_assert(sizeof(SbStaticVectorReply) == 24, "reply bytes");
_Static_assert(offsetof(SbStaticVectorRequest, arg0) == 16, "arg0 offset");
_Static_assert(offsetof(SbStaticVectorRequest, arg1) == 24, "arg1 offset");
_Static_assert(offsetof(SbStaticVectorReply, value) == 16, "reply value offset");
_Static_assert(SB_STATIC_VECTOR_MODE_COUNT == 26, "mode count");
_Static_assert(SB_STATIC_VECTOR_OP_COUNT == 40, "leaf count");
uint32_t probe(void *ctx, SbStaticVectorRequest const *request, SbStaticVectorReply *reply) {
  (void)ctx; (void)request; (void)reply;
  return SB_STATIC_VECTOR_INVALID;
}
SbStaticVectorHost typed_host = probe;
