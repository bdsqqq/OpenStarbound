#pragma once

#include "StarJson.hpp"
#include <array>
#ifdef STAR_USE_RUST_UNICODE
#include "StarRustUnicode.h"
#endif

namespace Star {
// Executing-thread snapshots contain no String/Json work inside the measured scope.
using UnicodeLabCounts = std::array<uint64_t, 10>;
inline UnicodeLabCounts unicodeLabSnapshot() {
  UnicodeLabCounts result{};
#ifdef STAR_USE_RUST_UNICODE
  for (uint32_t op = 0; op != 10; ++op)
    result[op] = star_unicode_call_count(op);
#endif
  return result;
}
inline UnicodeLabCounts unicodeLabDelta(UnicodeLabCounts const& before) {
  auto after = unicodeLabSnapshot();
  for (size_t op = 0; op != 10; ++op)
    after[op] -= before[op];
  return after;
}
inline JsonArray unicodeLabJson(UnicodeLabCounts const& counts) {
  JsonArray result;
  for (auto count : counts)
    result.append(count);
  return result;
}
Json unicodeBehaviorAssetProof();
}
