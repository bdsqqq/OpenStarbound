#pragma once

#include "StarJson.hpp"
#include <array>
#ifdef STAR_USE_RUST_JSON_PATH
#include "StarRustJsonPath.h"
#endif

namespace Star {
// Snapshot on the executing thread, without String/Json work in the scope.
using JsonPathLabCounts = std::array<uint64_t, 2>;
inline JsonPathLabCounts jsonPathLabSnapshot() {
  JsonPathLabCounts result{};
#ifdef STAR_USE_RUST_JSON_PATH
  for (uint32_t kind = 0; kind != 2; ++kind)
    result[kind] = star_json_path_call_count(kind);
#endif
  return result;
}
inline JsonPathLabCounts jsonPathLabDelta(JsonPathLabCounts const& before) {
  auto after = jsonPathLabSnapshot();
  for (size_t kind = 0; kind != 2; ++kind)
    after[kind] -= before[kind];
  return after;
}
inline JsonArray jsonPathLabJson(JsonPathLabCounts const& counts) {
  JsonArray result;
  for (auto count : counts)
    result.append(count);
  return result;
}
Json jsonPathBehaviorAssetProof();
}
