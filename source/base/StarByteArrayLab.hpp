#pragma once

#include "StarJson.hpp"
#include <array>
#include <cstdint>
#ifdef STAR_USE_RUST_BYTE_ARRAY
#include "StarRustByteArray.h"
#endif

namespace Star {

struct ByteArrayLabCounts {
  std::array<std::array<uint64_t, 3>, 56> values{};

  static ByteArrayLabCounts snapshot() noexcept {
    ByteArrayLabCounts out;
#ifdef STAR_USE_RUST_BYTE_ARRAY
    static_assert(SB_BA_MODE_COUNT == 56, "ByteArray receipt schema requires 56 modes");
    for (unsigned mode = 0; mode != 56; ++mode)
      for (unsigned event = 0; event != 3; ++event)
        out.values[mode][event] = star_byte_array_call_count(mode, event);
#endif
    return out;
  }

  ByteArrayLabCounts delta(ByteArrayLabCounts const& before) const noexcept {
    ByteArrayLabCounts out;
    for (unsigned mode = 0; mode != 56; ++mode)
      for (unsigned event = 0; event != 3; ++event)
        // Match the production TLS counters' unsigned wrapping arithmetic.
        out.values[mode][event] = values[mode][event] - before.values[mode][event];
    return out;
  }

  // Serialize only after the final snapshot: Json construction can itself
  // consume ByteArray and must not earn attribution for the proof it encodes.
  Json toJson() const {
    JsonObject out;
    char const* names[] = {"attempt", "success", "exception"};
    for (unsigned event = 0; event != 3; ++event) {
      JsonArray row;
      for (unsigned mode = 0; mode != 56; ++mode)
        row.append(values[mode][event]);
      out[names[event]] = std::move(row);
    }
    return out;
  }
};

// Observer/sender evidence uses ByteArray too. Subtract only outermost measured
// bookkeeping intervals so nested observers cannot earn or double-remove credit.
inline thread_local ByteArrayLabCounts ByteArrayLabBookkeepingCounts;
inline thread_local unsigned ByteArrayLabBookkeepingDepth = 0;
struct ByteArrayLabBookkeepingScope {
  ByteArrayLabCounts before;
  ByteArrayLabBookkeepingScope() noexcept {
    if (ByteArrayLabBookkeepingDepth++ == 0) before = ByteArrayLabCounts::snapshot();
  }
  ~ByteArrayLabBookkeepingScope() {
    if (--ByteArrayLabBookkeepingDepth == 0) {
      auto delta = ByteArrayLabCounts::snapshot().delta(before);
      for (unsigned mode = 0; mode != 56; ++mode)
        for (unsigned event = 0; event != 3; ++event)
          ByteArrayLabBookkeepingCounts.values[mode][event] += delta.values[mode][event];
    }
  }
};
inline ByteArrayLabCounts byteArrayConsumerSnapshot() noexcept {
  return ByteArrayLabCounts::snapshot().delta(ByteArrayLabBookkeepingCounts);
}

}
