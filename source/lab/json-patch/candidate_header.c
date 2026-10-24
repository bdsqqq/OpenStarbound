#include "StarRustJsonPatch.h"
#if defined(__cplusplus)
#define ASSERT static_assert
#else
#define ASSERT _Static_assert
#endif
ASSERT(sizeof(uint32_t)==4,"u32");
ASSERT(sizeof(uint64_t)==8,"u64");
ASSERT(JP_APPLY_RELEASE==41,"final opcode");
ASSERT(JP_MERGE==9,"final semantic entry");
int main(void){return 0;}
