#include "StarRustIdMap.h"
#include <stddef.h>
_Static_assert(sizeof(SbIdMapRequest)==24,"request size");
_Static_assert(sizeof(SbIdMapReply)==24,"reply size");
_Static_assert(_Alignof(SbIdMapRequest)==8,"request alignment");
_Static_assert(_Alignof(SbIdMapReply)==8,"reply alignment");
_Static_assert(offsetof(SbIdMapRequest,arg)==16,"request payload offset");
_Static_assert(offsetof(SbIdMapReply,value)==16,"reply payload offset");
_Static_assert(SB_IDMAP_MODE_COUNT==10 && SB_IDMAP_STAGE_COUNT==2 && SB_IDMAP_OP_COUNT==22,"policy schema");
static uint32_t callback(void* c,SbIdMapRequest const* q,SbIdMapReply* r){(void)c;(void)q;(void)r;return SB_IDMAP_INVALID;}
SbIdMapHost idmap_c_host(void){return callback;}
