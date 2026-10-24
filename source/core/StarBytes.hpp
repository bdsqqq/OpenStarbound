#pragma once

#include "StarMemory.hpp"

#ifdef STAR_USE_RUST_BYTES
#include "StarRustBytes.h"
#include <limits>
#include <stdexcept>
#endif

namespace Star {

enum class ByteOrder {
  BigEndian,
  LittleEndian,
  NoConversion
};

ByteOrder platformByteOrder();

void swapByteOrder(void* ptr, size_t len);
void swapByteOrder(void* dest, void const* src, size_t len);

void toByteOrder(ByteOrder order, void* ptr, size_t len);
void toByteOrder(ByteOrder order, void* dest, void const* src, size_t len);
void fromByteOrder(ByteOrder order, void* ptr, size_t len);
void fromByteOrder(ByteOrder order, void* dest, void const* src, size_t len);

template <typename T>
T toByteOrder(ByteOrder order, T const& t) {
  T ret;
  toByteOrder(order, &ret, &t, sizeof(t));
  return ret;
}

template <typename T>
T fromByteOrder(ByteOrder order, T const& t) {
  T ret;
  fromByteOrder(order, &ret, &t, sizeof(t));
  return ret;
}

template <typename T>
T toBigEndian(T const& t) {
  return toByteOrder(ByteOrder::BigEndian, t);
}

template <typename T>
T fromBigEndian(T const& t) {
  return fromByteOrder(ByteOrder::BigEndian, t);
}

template <typename T>
T toLittleEndian(T const& t) {
  return toByteOrder(ByteOrder::LittleEndian, t);
}

template <typename T>
T fromLittleEndian(T const& t) {
  return fromByteOrder(ByteOrder::LittleEndian, t);
}

inline ByteOrder platformByteOrder() {
#if STAR_LITTLE_ENDIAN
  return ByteOrder::LittleEndian;
#else
  return ByteOrder::BigEndian;
#endif
}

#ifdef STAR_USE_RUST_BYTES
namespace Detail {
// Unsupported address metadata and memcpy overlap retain the original C++
// domain. Once Rust executes, failure is never retried through the fallback.
inline bool rustBytes(void* dest, void const* src, size_t len, uint32_t op, ByteOrder order) {
  if (len > static_cast<size_t>(PTRDIFF_MAX))
    return false;
  bool reverse = op < 2 || (order != ByteOrder::NoConversion && order != platformByteOrder());
  bool copy = op % 2 != 0;
  if (len && (copy || (reverse && len > 1))) {
    auto range = [len](void const* p, uintptr_t& end) {
      auto start = reinterpret_cast<uintptr_t>(p);
      if (!p || len > std::numeric_limits<uintptr_t>::max() - start)
        return false;
      end = start + len;
      return true;
    };
    uintptr_t destEnd, srcEnd;
    if (!range(dest, destEnd))
      return false;
    if (copy) {
      if (!range(src, srcEnd))
        return false;
      if (!reverse && reinterpret_cast<uintptr_t>(dest) < srcEnd
          && reinterpret_cast<uintptr_t>(src) < destEnd)
        return false;
    }
  }
  auto status = star_bytes_transform(dest, src, len, op,
      static_cast<uint32_t>(order), static_cast<uint32_t>(platformByteOrder()));
  if (status != 0)
    throw std::runtime_error("Rust byte-order ABI failure");
  return true;
}
}
#endif

inline void swapByteOrder(void* ptr, size_t len) {
#ifdef STAR_USE_RUST_BYTES
  if (Detail::rustBytes(ptr, nullptr, len, 0, ByteOrder::NoConversion))
    return;
#endif
  uint8_t* data = static_cast<uint8_t*>(ptr);
  uint8_t spare;
  for (size_t i = 0; i < len / 2; ++i) {
    spare = data[len - 1 - i];
    data[len - 1 - i] = data[i];
    data[i] = spare;
  }
}

inline void swapByteOrder(void* dest, const void* src, size_t len) {
#ifdef STAR_USE_RUST_BYTES
  if (Detail::rustBytes(dest, src, len, 1, ByteOrder::NoConversion))
    return;
#endif
  const uint8_t* srcdata = static_cast<const uint8_t*>(src);
  uint8_t* destdata = static_cast<uint8_t*>(dest);
  for (size_t i = 0; i < len; ++i)
    destdata[len - 1 - i] = srcdata[i];
}

inline void toByteOrder(ByteOrder order, void* ptr, size_t len) {
#ifdef STAR_USE_RUST_BYTES
  if (Detail::rustBytes(ptr, nullptr, len, 2, order))
    return;
#endif
  if (order != ByteOrder::NoConversion && platformByteOrder() != order)
    swapByteOrder(ptr, len);
}

inline void toByteOrder(ByteOrder order, void* dest, void const* src, size_t len) {
#ifdef STAR_USE_RUST_BYTES
  if (Detail::rustBytes(dest, src, len, 3, order))
    return;
#endif
  if (order != ByteOrder::NoConversion && platformByteOrder() != order)
    swapByteOrder(dest, src, len);
  else
    memcpy(dest, src, len);
}

inline void fromByteOrder(ByteOrder order, void* ptr, size_t len) {
#ifdef STAR_USE_RUST_BYTES
  if (Detail::rustBytes(ptr, nullptr, len, 4, order))
    return;
#endif
  if (order != ByteOrder::NoConversion && platformByteOrder() != order)
    swapByteOrder(ptr, len);
}

inline void fromByteOrder(ByteOrder order, void* dest, void const* src, size_t len) {
#ifdef STAR_USE_RUST_BYTES
  if (Detail::rustBytes(dest, src, len, 5, order))
    return;
#endif
  if (order != ByteOrder::NoConversion && platformByteOrder() != order)
    swapByteOrder(dest, src, len);
  else
    memcpy(dest, src, len);
}

}
