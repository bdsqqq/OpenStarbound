#pragma once

#include "StarJson.hpp"
#include <array>
#ifdef STAR_USE_RUST_JSON_PATCH
#include "StarRustJsonPatch.h"
#endif

namespace Star {
// TLS snapshots exclude JSON construction and Lua conversion from the scope.
using JsonPatchLabCounts = std::array<std::array<uint64_t, 10>, 3>;
inline JsonPatchLabCounts jsonPatchLabSnapshot() {
  JsonPatchLabCounts result{};
#ifdef STAR_USE_RUST_JSON_PATCH
  for (uint32_t event = 0; event != 3; ++event)
    for (uint32_t entry = 0; entry != 10; ++entry)
      result[event][entry] = star_json_patch_call_count(entry, event);
#endif
  return result;
}
inline JsonPatchLabCounts jsonPatchLabDelta(JsonPatchLabCounts const& before) {
  auto result = jsonPatchLabSnapshot();
  for (size_t event = 0; event != 3; ++event)
    for (size_t entry = 0; entry != 10; ++entry)
      result[event][entry] -= before[event][entry];
  return result;
}
inline Json jsonPatchLabJson(JsonPatchLabCounts const& counts) {
  JsonObject result;
  char const* names[] = {"attempt", "success", "exception"};
  for (size_t event = 0; event != 3; ++event) {
    JsonArray values;
    for (auto count : counts[event])
      values.append(count);
    result[names[event]] = std::move(values);
  }
  return result;
}
Json jsonPatchBehaviorAssetProof();
}
