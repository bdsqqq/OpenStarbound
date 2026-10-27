#include "StarRustTtlCache.h"
#include <stddef.h>
_Static_assert(SB_TTL_ABI_VERSION==1,"version");
_Static_assert(SB_TTL_MODE_COUNT==19 && SB_TTL_STAGE_COUNT==4,"dispatch");
_Static_assert(SB_TTL_PAIR_STAMP_WRITE==31,"leaf count");
_Static_assert(sizeof(SbTtlRequest)==24 && sizeof(SbTtlReply)==24,"POD size");
_Static_assert(_Alignof(SbTtlRequest)==8 && _Alignof(SbTtlReply)==8,"POD alignment");
_Static_assert(offsetof(SbTtlRequest,arg)==16 && offsetof(SbTtlReply,value)==16,"POD offsets");
uint32_t c11_call(void* context,SbTtlHost host,SbTtlReply* reply){return sb_ttl_run(SB_TTL_TTL,SB_TTL_ROOT,context,host,reply);}
