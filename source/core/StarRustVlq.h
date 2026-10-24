#ifndef STAR_RUST_VLQ_H
#define STAR_RUST_VLQ_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef int32_t (*StarVlqWrite)(void* context, uint8_t octet, uint32_t is_final);
typedef int32_t (*StarVlqRead)(void* context, uint8_t* octet);

/* synchronous callbacks: 0 succeeds, nonzero aborts; never unwind across this
 * boundary. context may be null and no pointers are retained. callers guarantee
 * live writable allocations and callback validity. output pointers must be
 * aligned, nonnull and disjoint. callbacks may observe/mutate read destinations.
 * status: 0 terminated, 1 callback abort, 2 invalid ABI, 3 contained panic,
 * 4 read limit exhausted. invalid calls leave outputs untouched. controlled
 * abort/exhaustion preserves partial effects, not transactional rollback.
 * counts are successful octets (0..10). unsigned reads zero value first and
 * update after each successful callback; signed reads assign only on success.
 * no canonicality/overflow rejection: ten-byte arithmetic wraps at 64 bits. */
int32_t star_vlq_write_u(uint64_t value, StarVlqWrite write, void* context, uint32_t* written);
int32_t star_vlq_write_i(int64_t value, StarVlqWrite write, void* context, uint32_t* written);
int32_t star_vlq_size_u(uint64_t value, uint32_t* size);
int32_t star_vlq_size_i(int64_t value, uint32_t* size);
int32_t star_vlq_read_u(uint64_t* value, StarVlqRead read, void* context, size_t max_bytes, uint32_t* consumed);
int32_t star_vlq_read_i(int64_t* value, StarVlqRead read, void* context, size_t max_bytes, uint32_t* consumed);
/* executing-thread wrapping receipts for statuses 0/1/4, not 2/3:
 * 0 writeU, 1 sizeU, 2 readU, 3 writeI, 4 sizeI, 5 readI. */
uint64_t star_vlq_call_count(uint32_t operation);
#ifdef __cplusplus
}
#endif
#endif
