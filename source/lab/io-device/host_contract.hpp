#ifndef SB_IO_DEVICE_HOST_CONTRACT_HPP
#define SB_IO_DEVICE_HOST_CONTRACT_HPP
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Native-owned C++ controller blueprint, NOT Rust/application qualification.
 * Synchronous callback; ctx and all native slots live until run returns. No
 * retained pointer, native layout, allocator or C++ value crosses this ABI.
 * Custom opaque NULL ctx is legal; nativeHost requires a real NativeCtx.
 * host never unwinds. Status: 0 success, 1 native exception pending,
 * 2 invalid protocol, 3 foreign C++ callback throw (PROTOTYPE ONLY).
 * Native profile: uint8 IOMode/IOSeek, signed64 StreamOffset, size64.
 * Successful run MUST issue FINISH. ERROR returning success is invalid.
 * Pending permits only EXCEPTION_KIND and WRAP_SIZE, preserving exception_ptr
 * identity otherwise. WRAP_SIZE is valid only for pending IOException (kind 1).
 * All unused scalar arguments are zero; all uint8 values reject upper bits.
 * Native out must be aligned/nonwrapping and disjoint from known ctx, owner,
 * parameter and temporary objects/storage. This is NOT arbitrary pointer validation.
 * IO index 0 preserves NULL; positive index requires nonnull/nonwrapping native
 * base+index. Requested length is NOT physical capacity: NULL/positive or
 * SIZE_MAX/short backing requests may be accepted by a zero-progress virtual.
 * Busy is per callback context; fresh contexts on the same owner may reenter.
 */
typedef uint32_t (*SbIODeviceHost)(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*);
uint32_t sb_io_device_run(uint32_t,void*,SbIODeviceHost);
/* Source order, source/core/StarIODevice.cpp, all 22 real member definitions. */
enum SbIODeviceMode {
 SB_IO_CTOR=0, SB_IO_DTOR=1, SB_IO_RESIZE=2, SB_IO_READ_FULL=3,
 SB_IO_WRITE_FULL=4, SB_IO_OPEN=5, SB_IO_CLOSE=6, SB_IO_SYNC=7,
 SB_IO_DEVICE_NAME=8, SB_IO_AT_END=9, SB_IO_SIZE=10,
 SB_IO_READ_ABSOLUTE=11, SB_IO_WRITE_ABSOLUTE=12,
 SB_IO_READ_FULL_ABSOLUTE=13, SB_IO_WRITE_FULL_ABSOLUTE=14,
 SB_IO_READ_BYTES=15, SB_IO_WRITE_BYTES=16, SB_IO_READ_BYTES_ABSOLUTE=17,
 SB_IO_WRITE_BYTES_ABSOLUTE=18, SB_IO_SET_MODE=19, SB_IO_COPY_CTOR=20,
 SB_IO_ASSIGN=21
};
/* ARG(a=0/1); SET_MODE/RETURN(a=value); SEEK(a=signed bits,b=u8).
 * READ/WRITE/FULL(a=index,b=len); ABS/FULL_ABS(a=offset,b=index,c=len).
 * ARRAY_ALLOC(a=len) selects native result buffer; CAPTURE_INPUT_BYTES captures
 * param.ptr/size ONCE and returns size. NAME captures virtual native String;
 * NAME_BASE formats actual owner's address. BASE_CLOSE is qualified base call.
 * ERROR(a=0 resize,1 readEOF,2 readIO,3 writeEOF,4 writeIO,5 reopen captured
 * name,6 readFullAbs,7 writeFullAbs). Remaining operations take no arguments.
 */
enum SbIODeviceOp {
 SB_IO_ARG=1, SB_IO_MODE=2, SB_IO_STORE_MODE=3, SB_IO_SOURCE_MODE=4,
 SB_IO_READ=5, SB_IO_WRITE=6, SB_IO_POS=7, SB_IO_SEEK=8, SB_IO_END=9,
 SB_IO_VIRTUAL_SIZE=10, SB_IO_NAME=11, SB_IO_READ_ABS=12, SB_IO_WRITE_ABS=13,
 SB_IO_READFULL=14, SB_IO_WRITEFULL=15, SB_IO_READFULLABS=16, SB_IO_WRITEFULLABS=17,
 SB_IO_BASE_CLOSE=18, SB_IO_NAME_BASE=19, SB_IO_ARRAY_ALLOC=20,
 SB_IO_CAPTURE_INPUT_BYTES=21, SB_IO_RETURN=22, SB_IO_FINISH=23,
 SB_IO_ERROR=24, SB_IO_EXCEPTION_KIND=25, SB_IO_WRAP_SIZE=26
};
#ifdef __cplusplus
}
#endif
#endif
