#ifndef STAR_RUST_BUFFER_H
#define STAR_RUST_BUFFER_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Rust controller ABI; native ownership remains in C++.
 * No class layout, pointer integers, C++ values or
 * borrowed views cross this scalar ABI. host owns ctx and every native slot.
 * host must not unwind. opaque NULL custom ctx is legal.
 * 0 success, 1 native exception pending, 2 invalid protocol, 3 contained Rust panic.
 * Native domain: 64-bit size_t/StreamOffset, two's-complement cast profile.
 * Relative seek must not overflow signed64; bytes ACTUALLY COPIED need live
 * disjoint, nonwrapping spans. Requested READ length may be SIZE_MAX while
 * only available bytes are copied; borrowed logical sizes may be stored and
 * queried without dereference. Neither is a physical-capacity declaration.
 * Growth contents remain uninitialized.
 * IOMode and IOSeek domains are uint8, including unknown values through 255.
 * No allocator/OOM/platform/performance/universal lifetime qualification.
 */
typedef uint32_t (*StarBufferHost)(void*, uint32_t, uint64_t, uint64_t, uint64_t*);
uint32_t star_buffer_run(uint32_t mode, void* ctx, StarBufferHost host);
/* Thread-local wrapping counters: 0 attempt, 1 success, 2 native pending.
 * Invalid preflight is uncounted; invalid mode/event queries return zero. */
uint64_t star_buffer_call_count(uint32_t mode, uint32_t event);
/* mode -> immutable source definition (source/core/StarBuffer.cpp):
 * 0: Buffer::Buffer() line 9
 * 1: Buffer::Buffer(size_t initialSize) line 14
 * 2: Buffer::Buffer(ByteArray b) line 19
 * 3: Buffer::Buffer(Buffer const& buffer) line 24
 * 4: Buffer::Buffer(Buffer&& buffer) line 29
 * 5: StreamOffset Buffer::pos() { line 34
 * 6: void Buffer::seek(StreamOffset pos, IOSeek mode) { line 38
 * 7: void Buffer::resize(StreamOffset size) { line 49
 * 8: bool Buffer::atEnd() { line 53
 * 9: size_t Buffer::read(char* data, size_t len) { line 57
 * 10: size_t Buffer::write(char const* data, size_t len) { line 63
 * 11: size_t Buffer::readAbsolute(StreamOffset readPosition, char* data, size_t len) { line 69
 * 12: size_t Buffer::writeAbsolute(StreamOffset writePosition, char const* data, size_t len) { line 77
 * 13: void Buffer::open(IOMode mode) { line 85
 * 14: String Buffer::deviceName() const { line 93
 * 15: StreamOffset Buffer::size() { line 97
 * 16: ByteArray& Buffer::data() { line 101
 * 17: ByteArray const& Buffer::data() const { line 105
 * 18: ByteArray Buffer::takeData() { line 109
 * 19: char* Buffer::ptr() { line 115
 * 20: char const* Buffer::ptr() const { line 119
 * 21: size_t Buffer::dataSize() const { line 123
 * 22: void Buffer::reserve(size_t size) { line 127
 * 23: void Buffer::clear() { line 131
 * 24: bool Buffer::empty() const { line 136
 * 25: void Buffer::reset(size_t newSize) { line 140
 * 26: void Buffer::reset(ByteArray b) { line 145
 * 27: Buffer& Buffer::operator=(Buffer const& buffer) { line 150
 * 28: Buffer& Buffer::operator=(Buffer&& buffer) { line 157
 * 29: size_t Buffer::doRead(size_t pos, char* data, size_t len) { line 168
 * 30: size_t Buffer::doWrite(size_t pos, char const* data, size_t len) { line 183
 * 31: ExternalBuffer::ExternalBuffer() line 197
 * 32: ExternalBuffer::ExternalBuffer(char const* externalData, size_t len) : ExternalBuffer() { line 202
 * 33: StreamOffset ExternalBuffer::pos() { line 206
 * 34: void ExternalBuffer::seek(StreamOffset pos, IOSeek mode) { line 210
 * 35: bool ExternalBuffer::atEnd() { line 221
 * 36: size_t ExternalBuffer::read(char* data, size_t len) { line 225
 * 37: size_t ExternalBuffer::write(char const*, size_t) { line 231
 * 38: size_t ExternalBuffer::readAbsolute(StreamOffset readPosition, char* data, size_t len) { line 235
 * 39: size_t ExternalBuffer::writeAbsolute(StreamOffset, char const*, size_t) { line 243
 * 40: String ExternalBuffer::deviceName() const { line 247
 * 41: StreamOffset ExternalBuffer::size() { line 251
 * 42: char const* ExternalBuffer::ptr() const { line 255
 * 43: size_t ExternalBuffer::dataSize() const { line 259
 * 44: bool ExternalBuffer::empty() const { line 263
 * 45: ExternalBuffer::operator bool() const { line 267
 * 46: void ExternalBuffer::reset(char const* externalData, size_t len) { line 271
 * 47: IODevicePtr Buffer::clone() { line 277
 * 48: IODevicePtr ExternalBuffer::clone() { line 284
 * 49: size_t ExternalBuffer::doRead(size_t pos, char* data, size_t len) { line 289
 */
enum SbBufferMode {
  SB_B_CTOR = 0,
  SB_B_CTOR_SIZE = 1,
  SB_B_CTOR_BYTES = 2,
  SB_B_CTOR_COPY = 3,
  SB_B_CTOR_MOVE = 4,
  SB_B_POS = 5,
  SB_B_SEEK = 6,
  SB_B_RESIZE = 7,
  SB_B_END = 8,
  SB_B_READ = 9,
  SB_B_WRITE = 10,
  SB_B_READ_ABS = 11,
  SB_B_WRITE_ABS = 12,
  SB_B_OPEN = 13,
  SB_B_NAME = 14,
  SB_B_SIZE = 15,
  SB_B_DATA = 16,
  SB_B_CONST_DATA = 17,
  SB_B_TAKE = 18,
  SB_B_PTR = 19,
  SB_B_CONST_PTR = 20,
  SB_B_DATA_SIZE = 21,
  SB_B_RESERVE = 22,
  SB_B_CLEAR = 23,
  SB_B_EMPTY = 24,
  SB_B_RESET_SIZE = 25,
  SB_B_RESET_BYTES = 26,
  SB_B_COPY = 27,
  SB_B_MOVE = 28,
  SB_B_PRIVATE_READ = 29,
  SB_B_PRIVATE_WRITE = 30,
  SB_E_CTOR = 31,
  SB_E_CTOR_BYTES = 32,
  SB_E_POS = 33,
  SB_E_SEEK = 34,
  SB_E_END = 35,
  SB_E_READ = 36,
  SB_E_WRITE = 37,
  SB_E_READ_ABS = 38,
  SB_E_WRITE_ABS = 39,
  SB_E_NAME = 40,
  SB_E_SIZE = 41,
  SB_E_PTR = 42,
  SB_E_DATA_SIZE = 43,
  SB_E_EMPTY = 44,
  SB_E_BOOL = 45,
  SB_E_RESET = 46,
  SB_B_CLONE = 47,
  SB_E_CLONE = 48,
  SB_E_PRIVATE_READ = 49
};
/* All unused a/b arguments MUST be zero. All out spans must be aligned,
 * nonwrapping, disjoint from known native context/owners/params/results/owned
 * storage, plus actual IO spans at COPY_OUT/IN. Borrowed logical view lengths
 * are NOT eagerly treated as accessible spans (even pure getters must work).
 * This is selected known-alias validation, NOT arbitrary pointer validation.
 * ARG a=0..2 returns scalar argument; POS/SIZE/MODE and SOURCE_POS are fresh.
 * SET_POS/SET_SOURCE_POS/SET_MODE/RESULT use a; mode upper bits reject.
 * STORAGE a selector: 0 resize,1 reserve,2 clear,3 fill-zero,4 move param,
 * 5 move owner bytes to result. b=size only for selectors 0/1/3.
 * CHILD a selector: 0 reset-size,1 reset-bytes,2 copy,3 move,4 mutable-data,
 * 5 private-read,6 private-write,7 virtual-resize,8 virtual-seek-end,9 external-reset;
 * b=size/position only for 0/5/6/7, zero otherwise. Native input/output
 * pointers and lengths remain in ctx slots, and nested calls get fresh ctx.
 * COPY_OUT/IN a=position b=count, bounded by current logical storage and
 * requested IO count BEFORE pointer arithmetic/copy; actual nonzero spans are
 * checked for nonwrapping/known output alias, not arbitrary pointer validity.
 * ERROR a=0 unreadable,1 unwritable,
 * 2 external write,3 read-range,4 write-range, b=0; MUST return pending=1
 * from the exact native throw. Contradictory success is invalid=2.
 * BASE_COPY no args; SOURCE_STORAGE a=0 copy,1 move,2 replace-empty.
 * EXTERNAL_INIT no args sets null/zero, EXTERNAL_BIND no args uses native
 * borrowed-param slot and ARG0 length. NAME/CLONE_ALLOC/CLONE_SEEK/LOG/REF/PTR
 * no args; native String/ByteArray/shared_ptr/reference/pointer result slots
 * live until wrapper returns or rethrows. Mutable PTR uses CHILD data slot;
 * const PTR uses native storage directly. FINISH no args seals this ctx.
 * Pending/busy/finished ctx rejects further operations. Pending neither retries
 * nor rolls back. Fresh ctx on same owner is legal, including virtual reentry.
 * Constructors expose field ADDRESSES only until ordered scalar initialization;
 * guards never sample an uninitialized cursor or external pointer/size.
 */
enum SbBufferOp {
  SB_OP_ARG = 1,
  SB_OP_POS = 2,
  SB_OP_SET_POS = 3,
  SB_OP_SIZE = 4,
  SB_OP_MODE = 5,
  SB_OP_SET_MODE = 6,
  SB_OP_STORAGE = 7,
  SB_OP_CHILD = 8,
  SB_OP_COPY_OUT = 9,
  SB_OP_COPY_IN = 10,
  SB_OP_ERROR = 11,
  SB_OP_RESULT = 12,
  SB_OP_FINISH = 13,
  SB_OP_SOURCE_POS = 14,
  SB_OP_SET_SOURCE_POS = 15,
  SB_OP_BASE_COPY = 16,
  SB_OP_SOURCE_STORAGE = 17,
  SB_OP_EXTERNAL_INIT = 18,
  SB_OP_EXTERNAL_BIND = 19,
  SB_OP_NAME = 20,
  SB_OP_CLONE_ALLOC = 21,
  SB_OP_CLONE_SEEK = 22,
  SB_OP_LOG = 23,
  SB_OP_REF = 24,
  SB_OP_PTR = 25
};
#ifdef __cplusplus
}
#endif
#endif
