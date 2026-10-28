// Diagnostic-only native allocator observation. Normal Rust interop links the
// untouched StarMemory.cpp.o; ONLY allocation probes replace that one object.
#include "StarMemory.hpp"
#include <cstdlib>
#if defined(STAR_USE_JEMALLOC) || defined(STAR_USE_MIMALLOC) || defined(STAR_USE_RPMALLOC)
#error "allocation probe is admitted only for the measured default allocator"
#endif
namespace AllocationProbe {
thread_local bool tracking=false,deny=false;
thread_local size_t calls=0;
}
void* wpObservedMalloc(size_t size){
 if(AllocationProbe::tracking){++AllocationProbe::calls;if(AllocationProbe::deny)return nullptr;}
 return std::malloc(size);
}
// Keep the native global-new/null-to-bad_alloc/nothrow/delete implementation.
// Rename ONLY its malloc route, after system declarations have been included.
#define malloc wpObservedMalloc
#include "StarMemory.cpp"
#undef malloc
// Other Core callers retain the original default Star::malloc forwarding path.
namespace Star {void* malloc(size_t size){return std::malloc(size);}}
