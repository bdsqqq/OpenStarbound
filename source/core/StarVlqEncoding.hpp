#pragma once

#include "StarMemory.hpp"

#ifdef STAR_USE_RUST_VLQ
#include "StarRustVlq.h"
#include <exception>
#include <stdexcept>
#endif

namespace Star {

#ifdef STAR_USE_RUST_VLQ
namespace VlqDetail {
// retain the public by-value parameter's identity: copying here would change
// generic iterator/proxy events, including exceptions before foreign entry.
template <typename Iterator>
struct Writer {
  Iterator& iterator;
  std::exception_ptr exception;
  static int32_t write(void* context, uint8_t octet, uint32_t isFinal) noexcept {
    auto& self = *static_cast<Writer*>(context);
    try {
      // the legacy continuation RHS is int, but the final RHS is uint8_t.
      if (isFinal)
        *self.iterator++ = uint8_t(octet);
      else
        *self.iterator++ = int(octet);
      return 0;
    } catch (...) {
      self.exception = std::current_exception();
      return 1;
    }
  }
};
template <typename Iterator>
struct Reader {
  Iterator& iterator;
  std::exception_ptr exception;
  static int32_t read(void* context, uint8_t* octet) noexcept {
    auto& self = *static_cast<Reader*>(context);
    try {
      uint8_t byte = *self.iterator++;
      *octet = byte;
      return 0;
    } catch (...) {
      self.exception = std::current_exception();
      return 1;
    }
  }
};
inline void check(int32_t status, std::exception_ptr const& exception = {}) {
  if (exception)
    std::rethrow_exception(exception);
  if (status != 0 && status != 4)
    throw std::runtime_error("Rust VLQ failure");
}
}
#endif

// Write an unsigned integer as a VLQ (Variable Length Quantity).  Writes the
// integer in 7 byte chunks, with the 8th bit of each octet indicates whether
// another chunk follows.  Endianness independent, as the chunks are always
// written most significant first. Returns number of octet written (writes a
// maximum of a 64 bit integer, so a maximum of 10)
template <typename OutputIterator>
size_t writeVlqU(uint64_t x, OutputIterator out) {
#ifdef STAR_USE_RUST_VLQ
  VlqDetail::Writer<OutputIterator> context{out, {}};
  uint32_t written;
  auto status = star_vlq_write_u(x, &decltype(context)::write, &context, &written);
  VlqDetail::check(status, context.exception);
  return written;
#else
  size_t i;
  for (i = 9; i > 0; --i) {
    if (x & ((uint64_t)(127) << (i * 7)))
      break;
  }

  for (size_t j = 0; j < i; ++j)
    *out++ = (uint8_t)((x >> ((i - j) * 7)) & 127) | 128;

  *out++ = (uint8_t)(x & 127);
  return i + 1;
#endif
}

inline size_t vlqUSize(uint64_t x) {
#ifdef STAR_USE_RUST_VLQ
  uint32_t size;
  VlqDetail::check(star_vlq_size_u(x, &size));
  return size;
#else
  size_t i;
  for (i = 9; i > 0; --i) {
    if (x & ((uint64_t)(127) << (i * 7)))
      break;
  }
  return i + 1;
#endif
}

// Read a VLQ (Variable Length Quantity) encoded unsigned integer.  Returns
// number of bytes read.  Reads a *maximum of 10 bytes*, cannot read a larger
// than 64 bit integer!  If no end marker is found within 'maxBytes' or 10
// bytes, whichever is smaller, then will return NPos to signal error.
template <typename InputIterator>
size_t readVlqU(uint64_t& x, InputIterator in, size_t maxBytes = 10) {
#ifdef STAR_USE_RUST_VLQ
  VlqDetail::Reader<InputIterator> context{in, {}};
  uint32_t consumed;
  auto status = star_vlq_read_u(&x, &decltype(context)::read, &context, maxBytes, &consumed);
  VlqDetail::check(status, context.exception);
  return status == 4 ? NPos : consumed;
#else
  x = 0;
  for (size_t i = 0; i < min<size_t>(10, maxBytes); ++i) {
    uint8_t oct = *in++;
    x = (x << 7) | (uint64_t)(oct & 127);
    if (!(oct & 128))
      return i + 1;
  }

  return NPos;
#endif
}

// Write a VLQ (Variable Length Quantity) encoded signed integer.  Encoded by
// making the sign bit the least significant bit in the integer.  Returns
// number of bytes written.
template <typename OutputIterator>
size_t writeVlqI(int64_t v, OutputIterator out) {
#ifdef STAR_USE_RUST_VLQ
  // the legacy signed wrapper copies once more when forwarding to unsigned.
  OutputIterator forwarded = out;
  VlqDetail::Writer<OutputIterator> context{forwarded, {}};
  uint32_t written;
  auto status = star_vlq_write_i(v, &decltype(context)::write, &context, &written);
  VlqDetail::check(status, context.exception);
  return written;
#else
  uint64_t target;

  // If negative, then add 1 to properly encode -2^63
  if (v < 0)
    target = ((-(v + 1)) << 1) | 1;
  else
    target = v << 1;

  return writeVlqU(target, out);
#endif
}

inline size_t vlqISize(int64_t v) {
#ifdef STAR_USE_RUST_VLQ
  uint32_t size;
  VlqDetail::check(star_vlq_size_i(v, &size));
  return size;
#else
  uint64_t target;

  // If negative, then add 1 to properly encode -2^63
  if (v < 0)
    target = ((-(v + 1)) << 1) | 1;
  else
    target = v << 1;

  return vlqUSize(target);
#endif
}

// Read a VLQ (Variable Length Quantity) encoded signed integer.  Returns
// number of bytes read.  Reads a *maximum of 10 bytes*, cannot read a larger
// than 64 bit integer!  If no end marker is found within 'maxBytes' or 10
// bytes, whichever is smaller, then will return NPos to signal error.
template <typename InputIterator>
size_t readVlqI(int64_t& v, InputIterator in, size_t maxBytes = 10) {
#ifdef STAR_USE_RUST_VLQ
  int64_t decoded;
  uint32_t consumed;
  int32_t status;
  {
    // The original unsigned callee's parameter is copy-initialized and destroyed
    // BEFORE assigning v. Its destructor may mutate v or throw.
    InputIterator forwarded = in;
    VlqDetail::Reader<InputIterator> context{forwarded, {}};
    status = star_vlq_read_i(&decoded, &decltype(context)::read, &context, maxBytes, &consumed);
    VlqDetail::check(status, context.exception);
  }
  if (status == 0)
    v = decoded;
  return status == 4 ? NPos : consumed;
#else
  uint64_t source;
  size_t bytes = readVlqU(source, in, maxBytes);
  if (bytes == NPos)
    return NPos;

  bool negative = (source & 1);

  // If negative, then need to undo the +1 transformation to encode -2^63
  if (negative)
    v = -(int64_t)(source >> 1) - 1;
  else
    v = (int64_t)(source >> 1);

  return bytes;
#endif
}

}
