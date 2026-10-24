#pragma once

#include "StarJson.hpp"
#include <array>
#ifdef STAR_USE_RUST_ASSET_PATH
#include "StarRustAssetPath.h"
#endif

namespace Star {
// Executing-thread receipts; do not materialize Strings/Json inside the scope.
using AssetPathLabCounts = std::array<uint64_t, 2>;
inline AssetPathLabCounts assetPathLabSnapshot() {
  AssetPathLabCounts result{};
#ifdef STAR_USE_RUST_ASSET_PATH
  for (uint32_t op = 0; op != 2; ++op)
    result[op] = star_asset_path_call_count(op);
#endif
  return result;
}
inline AssetPathLabCounts assetPathLabDelta(AssetPathLabCounts const& before) {
  auto after = assetPathLabSnapshot();
  for (size_t op = 0; op != 2; ++op)
    after[op] -= before[op];
  return after;
}
inline JsonArray assetPathLabJson(AssetPathLabCounts const& counts) {
  JsonArray result;
  for (auto count : counts)
    result.append(count);
  return result;
}
Json assetPathBehaviorAssetProof();
}
