#include "StarPathEmbed.hpp"
#ifdef STAR_USE_RUST_PATH_EMBED
#include "StarRustPathEmbed.h"
#endif

namespace Star {
    
EnumMap<EmbeddedCompressionMethod> const EmbeddedCompressionMethodNames {
  {EmbeddedCompressionMethod::None, "None"},
  {EmbeddedCompressionMethod::Gzip, "Gzip"},
  {EmbeddedCompressionMethod::Zlib, "Zlib"},
  {EmbeddedCompressionMethod::Zstd, "Zstd"}
};

#ifdef STAR_USE_RUST_PATH_EMBED
namespace {
static_assert(static_cast<uint32_t>(None) == STAR_PATH_EMBED_NONE &&
  static_cast<uint32_t>(Gzip) == STAR_PATH_EMBED_GZIP &&
  static_cast<uint32_t>(Zlib) == STAR_PATH_EMBED_ZLIB &&
  static_cast<uint32_t>(Zstd) == STAR_PATH_EMBED_ZSTD, "PathEmbed action mapping");
String noneLeaf(ByteArray const& data) { return base64Encode(data,true); }
String gzipLeaf(ByteArray const&) { throw StarException("Compressing data in gzip is unsupported."); }
String zlibLeaf(ByteArray const& data) { return "zlib;"+base64Encode(compressData(data),true); }
String zstdLeaf(ByteArray const& data) { return "zstd;"+base64Encode(ZstdCompression::compress(data),true); }
using NativeLeaf = String (*)(ByteArray const&);
constexpr NativeLeaf nativeLeafTable[] = {noneLeaf, gzipLeaf, zlibLeaf, zstdLeaf};
// only arithmetic eligibility; Rust preflight still checks numeric spans.
bool rustEscapeEligible(size_t n, size_t capacity) {
  return n <= static_cast<size_t>(PTRDIFF_MAX) / 2 &&
    capacity <= static_cast<size_t>(PTRDIFF_MAX) && capacity >= n * 2;
}
}
#endif
String embedAndCompressData(ByteArray const& data, EmbeddedCompressionMethod const& compressionMethod) {
#ifdef STAR_USE_RUST_PATH_EMBED
  uint32_t action = UINT32_MAX;
  if (star_path_embed_select(static_cast<uint32_t>(compressionMethod), &action) != STAR_PATH_EMBED_OK || action > STAR_PATH_EMBED_ZSTD)
    throw StarException("Invalid PathEmbed selector protocol.");
  // Rust has returned before native allocation/throw; prvalue returns retain
  // C++17 mandatory elision and the original codec full-expression lifetimes.
  return nativeLeafTable[action](data);
#else
  switch (compressionMethod) {
    case EmbeddedCompressionMethod::None:
      return base64Encode(data,true);
    case EmbeddedCompressionMethod::Gzip:
      throw StarException("Compressing data in gzip is unsupported.");
    case EmbeddedCompressionMethod::Zlib:
      return "zlib;"+base64Encode(compressData(data),true);
    case EmbeddedCompressionMethod::Zstd:
      return "zstd;"+base64Encode(ZstdCompression::compress(data),true);
  }
#endif
}
String embedEscapeText(String const& data) {
  // swaps out a few characters for escaped versions.
  // meant to be fast. string is allocated for worst case scenario (entire string is made of escaped characters)
  typedef std::string::const_iterator const_iterator;
  auto out = std::string(data.utf8Size()*2,'\0');
  auto const& in = data.utf8();
#ifdef STAR_USE_RUST_PATH_EMBED
  size_t len = 0;
  if (rustEscapeEligible(in.size(), out.size())) {
    if (star_path_embed_escape(reinterpret_cast<uint8_t const*>(in.data()), in.size(),
        reinterpret_cast<uint8_t*>(out.data()), out.size(), &len) != STAR_PATH_EMBED_OK || len > out.size())
      throw StarException("Invalid PathEmbed escape protocol.");
  } else {
    // unsupported Rust span: reuse the already allocated native output.
    auto outIt = out.begin();
    auto end = in.end();
    for (const_iterator it = in.begin(); it < end; ++it) {
      switch (*it) {
        case '%':
          len += 2;
          *outIt++ = '%';
          *outIt++ = '%';
          break;
        case ':':
          len += 2;
          *outIt++ = '%';
          *outIt++ = 'c';
          break;
        case '?':
          len += 2;
          *outIt++ = '%';
          *outIt++ = 'q';
          break;
        case ';':
          len += 2;
          *outIt++ = '%';
          *outIt++ = 's';
          break;
        case '/':
          len += 2;
          *outIt++ = '%';
          *outIt++ = 'b';
          break;
        default:
          len++;
          *outIt++ = *it;
          break;
      }
    }
  }
#else
  auto outIt = out.begin();
  auto end = in.end();
  size_t len = 0;
  for (const_iterator it = in.begin(); it < end; ++it) {
    switch (*it) {
      case '%':
        len += 2;
        *outIt++ = '%';
        *outIt++ = '%';
        break;
      case ':':
        len += 2;
        *outIt++ = '%';
        *outIt++ = 'c';
        break;
      case '?':
        len += 2;
        *outIt++ = '%';
        *outIt++ = 'q';
        break;
      case ';':
        len += 2;
        *outIt++ = '%';
        *outIt++ = 's';
        break;
      case '/':
        len += 2;
        *outIt++ = '%';
        *outIt++ = 'b';
        break;
      default:
        len++;
        *outIt++ = *it;
        break;
    }
  }
#endif
  out.resize(len);
  return String(std::move(out));
}
}
