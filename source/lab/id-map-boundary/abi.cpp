#include "StarRustIdMap.h"
#include <cstddef>
#include <type_traits>
static_assert(sizeof(SbIdMapRequest)==24 && sizeof(SbIdMapReply)==24,"ABI sizes");
static_assert(alignof(SbIdMapRequest)==8 && alignof(SbIdMapReply)==8,"ABI alignment");
static_assert(offsetof(SbIdMapRequest,arg)==16 && offsetof(SbIdMapReply,value)==16,"ABI offsets");
static_assert(std::is_standard_layout_v<SbIdMapRequest> && std::is_trivially_copyable_v<SbIdMapReply>,"C layout");
static_assert(SB_IDMAP_CTOR==0 && SB_IDMAP_WRITE==9 && SB_IDMAP_MODE_COUNT==10,"root schema");
static_assert(SB_IDMAP_CONTINUE==1 && SB_IDMAP_STAGE_COUNT==2 && SB_IDMAP_OP_COUNT==22,"stage/leaf schema");
extern "C" uint32_t idmap_cpp_host(void*,SbIdMapRequest const*,SbIdMapReply*) noexcept {return SB_IDMAP_INVALID;}
SbIdMapHost idmap_cpp_callback(){return idmap_cpp_host;}
