#pragma once

#include "StarJson.hpp"
#include "StarImage.hpp"
#include "StarPathEmbed.hpp"
#include "StarEncode.hpp"
#include <cstring>
#ifdef STAR_USE_RUST_ZSTD
#include "StarRustZstd.h"
#endif

namespace Star {
struct ZstdLabCounts {
  uint64_t values[4][3]{};
  static ZstdLabCounts snapshot() noexcept {
    ZstdLabCounts out;
#ifdef STAR_USE_RUST_ZSTD
    for (unsigned k = 0; k != 4; ++k)
      for (unsigned e = 0; e != 3; ++e)
        out.values[k][e] = star_zstd_call_count(k, e);
#endif
    return out;
  }
  ZstdLabCounts delta(ZstdLabCounts const& before) const noexcept {
    ZstdLabCounts out;
    for (unsigned k = 0; k != 4; ++k)
      for (unsigned e = 0; e != 3; ++e)
        out.values[k][e] = values[k][e] - before.values[k][e];
    return out;
  }
  Json json() const {
    JsonObject out;
    char const* names[] = {"attempt", "success", "exception"};
    for (unsigned e = 0; e != 3; ++e) {
      JsonArray a;
      for (unsigned k = 0; k != 4; ++k) a.append(values[k][e]);
      out[names[e]] = std::move(a);
    }
    return out;
  }
};

// Heap-owned before arming; TLS holds only a pointer. No Game dependency here.
struct ZstdLabRecord {
  unsigned kind = 0;
  size_t inputSize = 0, outputSize = 0;
  char input[32768], output[32768];
  ZstdLabCounts calls;
};
struct ZstdLabArena {
  void const* a = nullptr;
  void const* b = nullptr;
  bool valid = true;
  size_t count = 0;
  ZstdLabRecord records[64];
};
inline thread_local ZstdLabArena* ZstdLabActive = nullptr;

// The destructor never reads codec output: an exception can leave an unknown tail.
class ZstdLabCall {
public:
  ZstdLabCall(void const* identity, unsigned kind, char const* input, size_t size,
      size_t oldOutputSize) noexcept : m_arena(ZstdLabActive), m_oldOutputSize(oldOutputSize) {
    if (!m_arena) return;
    if ((identity != m_arena->a && identity != m_arena->b)
        || size > 32768 || m_arena->count == 64) {
      m_arena->valid = false;
      return;
    }
    m_record = &m_arena->records[m_arena->count++];
    m_record->kind = kind;
    m_record->inputSize = size;
    m_record->outputSize = 0;
    if (size) std::memcpy(m_record->input, input, size);
    m_before = ZstdLabCounts::snapshot();
  }
  void success(ByteArray const& output) noexcept {
    if (!m_arena) return;
    auto after = ZstdLabCounts::snapshot();
    m_completed = true;
    if (!m_record) return;
    if (output.size() < m_oldOutputSize || output.size() - m_oldOutputSize > 32768) {
      m_arena->valid = false;
      return;
    }
    m_record->calls = after.delta(m_before);
    m_record->outputSize = output.size() - m_oldOutputSize;
    if (m_record->outputSize)
      std::memcpy(m_record->output, output.ptr() + m_oldOutputSize, m_record->outputSize);
  }
  ~ZstdLabCall() noexcept {
    if (m_arena && !m_completed) m_arena->valid = false;
  }
private:
  ZstdLabArena* m_arena;
  ZstdLabRecord* m_record = nullptr;
  size_t m_oldOutputSize;
  bool m_completed = false;
  ZstdLabCounts m_before;
};

bool zstdLabSource(Image const& image);
String zstdLabEmbed(ByteArray const& png, EmbeddedCompressionMethod method);
void zstdLabEmbedPath(String const& path);
Json zstdLabImageProof();
}
