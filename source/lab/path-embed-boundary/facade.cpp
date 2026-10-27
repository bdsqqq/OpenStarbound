#include "facade.hpp"
#include "boundary.h"
namespace PathEmbedBoundary {
using namespace Star;
namespace {
String noneLeaf(ByteArray const& data) { return base64Encode(data,true); }
String gzipLeaf(ByteArray const&) { throw StarException("Compressing data in gzip is unsupported."); }
String zlibLeaf(ByteArray const& data) { return "zlib;"+base64Encode(compressData(data),true); }
String zstdLeaf(ByteArray const& data) { return "zstd;"+base64Encode(ZstdCompression::compress(data),true); }
using NativeLeaf = String (*)(ByteArray const&);
constexpr NativeLeaf nativeLeafTable[] = {noneLeaf, gzipLeaf, zlibLeaf, zstdLeaf};
}
String compress(ByteArray const& data, EmbeddedCompressionMethod const& method) {
  uint32_t action = UINT32_MAX;
  // The selector has returned before native allocation or throwing begins.
  if (pe_select(static_cast<uint32_t>(method), &action) != PE_OK || action > PE_ZSTD)
    throw StarException("Invalid private PathEmbed selector protocol.");
  // Both returns are same-type prvalues: C++17 requires elision, no named String.
  return nativeLeafTable[action](data);
}
String escape(String const& data) {
  // Preserve native allocation BEFORE acquiring the input reference, and size
  // the string itself, not just its spare capacity.
  auto out = std::string(data.utf8Size()*2,'\0');
  auto const& in = data.utf8();
  size_t len = 0;
  if (pe_span_eligible(in.size(), out.size())) {
    if (pe_escape(reinterpret_cast<uint8_t const*>(in.data()), in.size(),
                  reinterpret_cast<uint8_t*>(out.data()), out.size(), &len) != PE_OK)
      throw StarException("Invalid private PathEmbed escape protocol.");
  } else {
    // Unsupported Rust span: reuse the original allocation and borrowed input.
    // No ABI entry and no second whole-function allocation.
    auto outIt = out.begin();
    auto end = in.end();
    for (std::string::const_iterator it = in.begin(); it < end; ++it) {
      switch (*it) {
        case '%': len += 2; *outIt++ = '%'; *outIt++ = '%'; break;
        case ':': len += 2; *outIt++ = '%'; *outIt++ = 'c'; break;
        case '?': len += 2; *outIt++ = '%'; *outIt++ = 'q'; break;
        case ';': len += 2; *outIt++ = '%'; *outIt++ = 's'; break;
        case '/': len += 2; *outIt++ = '%'; *outIt++ = 'b'; break;
        default: len++; *outIt++ = *it; break;
      }
    }
  }
  out.resize(len);
  return String(std::move(out));
}
}
