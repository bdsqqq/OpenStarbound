#pragma once

#include "StarJson.hpp"
#ifdef STAR_USE_RUST_HOST_ADDRESS
#include "StarRustHostAddress.h"
#endif

namespace Star {
// Snapshots are main-thread, fixture-local scopes. Nested controllers are not
// one-hot: these deltas deliberately retain their complete 27-mode vectors.
struct HostAddressLabCounts {
  uint64_t values[27][3]{};
  static HostAddressLabCounts snapshot() noexcept {
    HostAddressLabCounts out;
#ifdef STAR_USE_RUST_HOST_ADDRESS
    for (unsigned m = 0; m != 27; ++m)
      for (unsigned e = 0; e != 3; ++e)
        out.values[m][e] = star_host_address_call_count(m, e);
#endif
    return out;
  }
  Json delta(HostAddressLabCounts const& before) const {
    JsonObject out;
    char const* names[] = {"attempt", "success", "exception"};
    for (unsigned e = 0; e != 3; ++e) {
      JsonArray row;
      for (unsigned m = 0; m != 27; ++m)
        row.append(values[m][e] - before.values[m][e]);
      out[names[e]] = std::move(row);
    }
    return out;
  }
};
}
