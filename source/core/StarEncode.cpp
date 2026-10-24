#include "StarEncode.hpp"

#ifdef STAR_USE_RUST_ENCODE
#include "StarRustEncode.h"
#include <climits>
#include <limits>
#include <stdexcept>
#endif

namespace Star {

#ifdef STAR_USE_RUST_ENCODE
namespace {
// NPos is a write limit, not an allocation size. Bound it before checking ranges.
bool rustEncode(uint32_t op, char const* input, size_t len, char* output,
    size_t outLen, bool url, size_t& written) {
  if (op >= 3 && len > INT_MAX)
    return false;
  size_t capacity;
  if (op == 0)
    capacity = 2 * std::min(len, outLen / 2);
  else if (op == 1)
    capacity = std::min(outLen, len / 2);
  else if (op == 2)
    capacity = std::min(outLen, len);
  else if (op == 3) {
    size_t groups = len / 3;
    size_t tail = len % 3 ? 4 : 0;
    if (groups > (std::numeric_limits<size_t>::max() - tail) / 4)
      return false;
    capacity = std::min(outLen, 4 * groups + tail);
  } else
    capacity = std::min(outLen, 3 * (len / 4) + (len % 4 >= 2 ? len % 4 - 1 : 0));

  auto range = [](void const* p, size_t n, uintptr_t& end) {
    auto start = reinterpret_cast<uintptr_t>(p);
    if ((n && !p) || n > static_cast<size_t>(PTRDIFF_MAX)
        || n > std::numeric_limits<uintptr_t>::max() - start)
      return false;
    end = start + n;
    return true;
  };
  uintptr_t inputEnd, outputEnd;
  if (!range(input, len, inputEnd) || !range(output, capacity, outputEnd))
    return false;
  auto inputStart = reinterpret_cast<uintptr_t>(input);
  auto outputStart = reinterpret_cast<uintptr_t>(output);
  // Aliasing retains the original C++ read/write order, with no Rust receipt.
  if (len && capacity && inputStart < outputEnd && outputStart < inputEnd)
    return false;
  uint8_t accepted[256];
  if (op == 4) {
    for (unsigned i = 0; i < 256; ++i)
      accepted[i] = !!(isalnum(static_cast<unsigned char>(i)) || i == '+' || i == '/'
          || i == '-' || i == '_');
  }
  auto status = star_encode(op, reinterpret_cast<uint8_t const*>(input), len,
      reinterpret_cast<uint8_t*>(output), capacity, url ? 1 : 0,
      op == 4 ? accepted : nullptr, &written);
  if (status != 0)
    throw std::runtime_error("Rust encoding ABI failure");
  return true;
}
}
#endif

size_t hexEncode(char const* data, size_t len, char* output, size_t outLen) {
#ifdef STAR_USE_RUST_ENCODE
  size_t written;
  if (rustEncode(0, data, len, output, outLen, false, written))
    return written;
#endif
  static char const hex[] = "0123456789abcdef";

  len = std::min(len, outLen / 2);
  for (size_t i = 0; i < len; ++i) {
    output[i * 2] = hex[(data[i] & 0xf0) >> 4];
    output[i * 2 + 1] = hex[(data[i] & 0x0f)];
  }

  return len * 2;
}

size_t hexDecode(char const* src, size_t len, char* output, size_t outLen) {
#ifdef STAR_USE_RUST_ENCODE
  size_t written;
  if (rustEncode(1, src, len, output, outLen, false, written))
    return written;
#endif
  for (size_t i = 0; i < len / 2; ++i) {
    if (i >= outLen)
      return i;

    uint8_t b1 = 0;
    char c1 = src[i * 2];
    if (c1 >= '0' && c1 <= '9')
      b1 = c1 - '0';
    else if (c1 >= 'A' && c1 <= 'F')
      b1 = c1 - 'A' + 10;
    else if (c1 >= 'a' && c1 <= 'f')
      b1 = c1 - 'a' + 10;

    uint8_t b2 = 0;
    char c2 = src[i * 2 + 1];
    if (c2 >= '0' && c2 <= '9')
      b2 = c2 - '0';
    else if (c2 >= 'A' && c2 <= 'F')
      b2 = c2 - 'A' + 10;
    else if (c2 >= 'a' && c2 <= 'f')
      b2 = c2 - 'a' + 10;

    *output++ = (b1 << 4) | b2;
  }

  return len / 2;
}

size_t nibbleDecode(char const* src, size_t len, char* output, size_t outLen) {
#ifdef STAR_USE_RUST_ENCODE
  size_t written;
  if (rustEncode(2, src, len, output, outLen, false, written))
    return written;
#endif
  for (size_t i = 0; i < len; ++i) {
    if (i >= outLen)
      return i;

    uint8_t b = 0;
    char c = src[i];
    if (c >= '0' && c <= '9')
      b = c - '0';
    else if (c >= 'A' && c <= 'F')
      b = c - 'A' + 10;
    else if (c >= 'a' && c <= 'f')
      b = c - 'a' + 10;

    *output++ = b;
  }

  return len;
}

static const std::string base64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
static const std::string base64url_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

size_t base64Encode(char const* data, size_t len, char* output, size_t outLen, bool useUrl) {
#ifdef STAR_USE_RUST_ENCODE
  // Normal-operation byte equivalence; Rust does not copy the C++ alphabet
  // allocation, so allocator-fault-injection exception equivalence is excluded.
  size_t rustWritten;
  if (rustEncode(3, data, len, output, outLen, useUrl, rustWritten))
    return rustWritten;
#endif
  if (outLen == 0)
    return 0;
  size_t written = 0;
  std::string const charsString = useUrl ? base64url_chars : base64_chars;

  unsigned char ca3[3] = {0, 0, 0};
  unsigned char ca4[4] = {0, 0, 0, 0};
  const unsigned char* inPtr = (const unsigned char*)data;
  int i = 0, j = 0, in_len = len;

  while (in_len--) {
    ca3[i++] = *(inPtr++);
    if (i == 3) {
      ca4[0] = (ca3[0] & 0xfc) >> 2;
      ca4[1] = ((ca3[0] & 0x03) << 4) + ((ca3[1] & 0xf0) >> 4);
      ca4[2] = ((ca3[1] & 0x0f) << 2) + ((ca3[2] & 0xc0) >> 6);
      ca4[3] = ca3[2] & 0x3f;
      for (i = 0; (i < 4); i++) {
        --outLen;
        *output = charsString[ca4[i]];
        ++output;
        ++written;

        if (outLen == 0)
          return written;
      }
      i = 0;
    }
  }

  if (i) {
    for (j = i; j < 3; j++)
      ca3[j] = '\0';
    ca4[0] = (ca3[0] & 0xfc) >> 2;
    ca4[1] = ((ca3[0] & 0x03) << 4) + ((ca3[1] & 0xf0) >> 4);
    ca4[2] = ((ca3[1] & 0x0f) << 2) + ((ca3[2] & 0xc0) >> 6);
    ca4[3] = ca3[2] & 0x3f;
    for (j = 0; (j < i + 1); j++) {
      --outLen;
      *output = charsString[ca4[j]];
      ++output;
      ++written;

      if (outLen == 0)
        return written;
    }
    if (useUrl)
      // Base64URL excludes padding, so don't include it.
      return written;
    
    while ((i++ < 3)) {
      --outLen;
      *output = '=';
      ++output;
      ++written;

      if (outLen == 0)
        return written;
    }
  }

  return written;
}

// Follows Base64URL standard as well.
static inline bool is_base64(unsigned char c) {
  return (isalnum(c) || (c == '+') || (c == '/') || (c == '-') || (c == '_'));
}

static inline size_t decodeBase64Char(unsigned char c) {
  if (c == '-')
    return 62;
  if (c == '_')
    return 63;
  return base64_chars.find(c);
}

size_t base64Decode(char const* src, size_t len, char* output, size_t outLen) {
#ifdef STAR_USE_RUST_ENCODE
  size_t rustWritten;
  if (rustEncode(4, src, len, output, outLen, false, rustWritten))
    return rustWritten;
#endif
  if (outLen == 0)
    return 0;

  size_t written = 0;

  int i = 0, j = 0, in_ = 0, in_len = len;
  unsigned char ca4[4], ca3[3];

  while (in_len-- && (src[in_] != '=') && is_base64(src[in_])) {
    ca4[i++] = src[in_++];
    if (i == 4) {
      for (i = 0; i < 4; i++)
        ca4[i] = decodeBase64Char(ca4[i]);
      ca3[0] = (ca4[0] << 2) + ((ca4[1] & 0x30) >> 4);
      ca3[1] = ((ca4[1] & 0xf) << 4) + ((ca4[2] & 0x3c) >> 2);
      ca3[2] = ((ca4[2] & 0x3) << 6) + ca4[3];
      for (i = 0; (i < 3); i++) {
        --outLen;
        *output = ca3[i];
        ++output;
        ++written;

        if (outLen == 0)
          return written;
      }
      i = 0;
    }
  }

  if (i) {
    for (j = i; j < 4; j++)
      ca4[j] = 0;
    for (j = 0; j < 4; j++)
      ca4[j] = decodeBase64Char(ca4[j]);
    ca3[0] = (ca4[0] << 2) + ((ca4[1] & 0x30) >> 4);
    ca3[1] = ((ca4[1] & 0xf) << 4) + ((ca4[2] & 0x3c) >> 2);
    ca3[2] = ((ca4[2] & 0x3) << 6) + ca4[3];
    for (j = 0; (j < i - 1); j++) {
      --outLen;
      *output = ca3[j];
      ++output;
      ++written;

      if (outLen == 0)
        return written;
    }
  }

  return written;
}

String hexEncode(char const* data, size_t len) {
  std::string res(len * 2, '\0');
  size_t encoded = hexEncode(data, len, &res[0], res.size());
  _unused(encoded);
  starAssert(encoded == res.size());
  return res;
}

String base64Encode(char const* data, size_t len, bool useUrl) {
  std::string res(len * 4 / 3 + 3, '\0');
  size_t encoded = base64Encode(data, len, &res[0], res.size(), useUrl);
  _unused(encoded);
  starAssert(encoded <= res.size());
  res.resize(encoded);
  return res;
}

String hexEncode(ByteArray const& data) {
  return hexEncode(data.ptr(), data.size());
}

ByteArray hexDecode(String const& encodedData) {
  ByteArray res(encodedData.size() / 2, 0);
  size_t decoded = hexDecode(encodedData.utf8Ptr(), encodedData.utf8Size(), res.ptr(), res.size());
  _unused(decoded);
  starAssert(decoded == res.size());
  return res;
}

String base64Encode(ByteArray const& data, bool useUrl) {
  return base64Encode(data.ptr(), data.size(), useUrl);
}

ByteArray base64Decode(String const& encodedData) {
  ByteArray res(encodedData.size() * 3 / 4, 0);
  size_t decoded = base64Decode(encodedData.utf8Ptr(), encodedData.utf8Size(), res.ptr(), res.size());
  _unused(decoded);
  starAssert(decoded <= res.size());
  res.resize(decoded);
  return res;
}

}
