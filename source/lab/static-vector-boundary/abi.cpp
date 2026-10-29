#include <cstddef>
#include <type_traits>
#include "StarRustStaticVector.h"
static_assert(sizeof(SbStaticVectorRequest) == 32, "request bytes");
static_assert(sizeof(SbStaticVectorReply) == 24, "reply bytes");
static_assert(offsetof(SbStaticVectorRequest, arg0) == 16, "arg0 offset");
static_assert(offsetof(SbStaticVectorRequest, arg1) == 24, "arg1 offset");
static_assert(offsetof(SbStaticVectorReply, value) == 16, "value offset");
static_assert(std::is_standard_layout<SbStaticVectorRequest>::value, "request C layout");
static_assert(std::is_trivially_copyable<SbStaticVectorReply>::value, "reply scalar copy");
static_assert(SB_STATIC_VECTOR_MODE_COUNT == 26, "mode count");
static_assert(SB_STATIC_VECTOR_OP_COUNT == 40, "leaf count");
