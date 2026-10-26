#ifndef STAR_RUST_IO_DEVICE_H
#define STAR_RUST_IO_DEVICE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Synchronous opaque native leaves; the Rust controller owns source branches,
 * progress and ordering. Native code owns pointers, objects, allocation and
 * exceptions. host MUST NOT unwind (C++ or Rust) across this ABI.
 * Status: 0 finished, 1 native exception pending, 2 invalid protocol,
 * 3 contained Rust panic. Invalid mode/null host is uncounted; NULL ctx is
 * legal for custom hosts. Host statuses above 1 are invalid. FINISH must
 * succeed; ERROR must report pending, never success.
 * Native profile: uint8 IOMode/IOSeek, signed64 StreamOffset, size64;
 * atEnd evaluates POS before VIRTUAL_SIZE (fixed Apple profile only).
 * Pending allows only EXCEPTION_KIND (1 IOException, 2 other) and WRAP_SIZE.
 * WRAP_SIZE is allowed only for pending IOException and must return pending.
 * Otherwise the native exception identity is preserved.
 * Context, owner and native temporaries live until run returns; nothing is
 * retained. Bind the input ByteArray pointer/size before entry: the borrowed
 * parameter may die INSIDE a virtual full-I/O override, so callbacks must use
 * the captured snapshot and never dereference that parameter afterward.
 * All unused scalar arguments are zero; uint8 values reject upper bits.
 * Native out must be aligned/nonwrapping and disjoint from known ctx, owner,
 * parameters and temporary storage. This is not arbitrary pointer validation.
 * IO index 0 preserves NULL; positive index requires a nonnull/nonwrapping
 * native base+index. Requested length is not physical capacity. Progress,
 * not requested length, drives index checks. Absolute offsets wrap as u64.
 * Reentry uses a fresh context without owner locks; counters are thread local.
 * No universal platform, OOM, performance or application qualification claim.
 */
typedef uint32_t (*StarIODeviceHost)(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*);
uint32_t star_io_device_run(uint32_t mode,void* ctx,StarIODeviceHost host);
/* event 0 attempt, 1 success, 2 native pending; wrapping thread-local 22x3.
 * Invalid mode/event queries return zero. */
uint64_t star_io_device_call_count(uint32_t mode,uint32_t event);
/* Source order, source/core/StarIODevice.cpp, all 22 real member definitions. */
enum StarIODeviceMode {
 STAR_IO_CTOR=0, STAR_IO_DTOR=1, STAR_IO_RESIZE=2, STAR_IO_READ_FULL=3,
 STAR_IO_WRITE_FULL=4, STAR_IO_OPEN=5, STAR_IO_CLOSE=6, STAR_IO_SYNC=7,
 STAR_IO_DEVICE_NAME=8, STAR_IO_AT_END=9, STAR_IO_SIZE=10,
 STAR_IO_READ_ABSOLUTE=11, STAR_IO_WRITE_ABSOLUTE=12,
 STAR_IO_READ_FULL_ABSOLUTE=13, STAR_IO_WRITE_FULL_ABSOLUTE=14,
 STAR_IO_READ_BYTES=15, STAR_IO_WRITE_BYTES=16, STAR_IO_READ_BYTES_ABSOLUTE=17,
 STAR_IO_WRITE_BYTES_ABSOLUTE=18, STAR_IO_SET_MODE=19, STAR_IO_COPY_CTOR=20,
 STAR_IO_ASSIGN=21
};
/* ARG(a=0/1); STORE_MODE/RETURN(a=value); SEEK(a=signed bits,b=u8).
 * READ/WRITE/FULL(a=index,b=len); ABS/FULL_ABS(a=offset,b=index,c=len).
 * ARRAY_ALLOC(a=len) selects native result buffer; CAPTURE_INPUT_BYTES returns
 * the C++-prepared borrowed input length once, without rereading the parameter.
 * NAME captures virtual native String;
 * NAME_BASE formats actual owner's address. BASE_CLOSE is qualified base call.
 * ERROR(a=0 resize,1 readEOF,2 readIO,3 writeEOF,4 writeIO,5 reopen captured
 * name,6 readFullAbs,7 writeFullAbs). Remaining operations take no arguments.
 */
enum StarIODeviceOp {
 STAR_IO_ARG=1, STAR_IO_MODE=2, STAR_IO_STORE_MODE=3, STAR_IO_SOURCE_MODE=4,
 STAR_IO_READ=5, STAR_IO_WRITE=6, STAR_IO_POS=7, STAR_IO_SEEK=8, STAR_IO_END=9,
 STAR_IO_VIRTUAL_SIZE=10, STAR_IO_NAME=11, STAR_IO_READ_ABS=12, STAR_IO_WRITE_ABS=13,
 STAR_IO_READFULL=14, STAR_IO_WRITEFULL=15, STAR_IO_READFULLABS=16, STAR_IO_WRITEFULLABS=17,
 STAR_IO_BASE_CLOSE=18, STAR_IO_NAME_BASE=19, STAR_IO_ARRAY_ALLOC=20,
 STAR_IO_CAPTURE_INPUT_BYTES=21, STAR_IO_RETURN=22, STAR_IO_FINISH=23,
 STAR_IO_ERROR=24, STAR_IO_EXCEPTION_KIND=25, STAR_IO_WRAP_SIZE=26
};
#ifdef __cplusplus
}
#endif
#endif
