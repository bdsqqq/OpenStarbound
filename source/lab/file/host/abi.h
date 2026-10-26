#ifndef FILE_HOST_PROTOTYPE_H
#define FILE_HOST_PROTOTYPE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef uint32_t (*file_host_fn)(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*);
/* Prototype only: 0 success, 1 captured native exception, 2 protocol error,
 * 3 foreign host throw contained by the native controller. Never cross Rust. */
uint32_t file_host_run(uint32_t,void*,file_host_fn);
uint64_t file_host_count(uint32_t,uint32_t);
#ifdef __cplusplus
}
#endif
#endif
