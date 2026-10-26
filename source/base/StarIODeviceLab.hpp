#pragma once

#include "StarJson.hpp"
#include <cstdint>
#ifdef STAR_USE_RUST_IO_DEVICE
#include "StarRustIODevice.h"
#endif

namespace Star {

struct IODeviceLabCounts {
  uint64_t values[22][3]{};

  static IODeviceLabCounts snapshot() noexcept {
    IODeviceLabCounts out;
#ifdef STAR_USE_RUST_IO_DEVICE
    for (unsigned mode = 0; mode != 22; ++mode)
      for (unsigned event = 0; event != 3; ++event)
        out.values[mode][event] = star_io_device_call_count(mode, event);
#endif
    return out;
  }

  Json delta(IODeviceLabCounts const& before) const {
    JsonObject out;
    char const* names[] = {"attempt", "success", "exception"};
    for (unsigned event = 0; event != 3; ++event) {
      JsonArray row;
      for (unsigned mode = 0; mode != 22; ++mode)
        // The production TLS counters wrap; retain unsigned subtraction here.
        row.append(values[mode][event] - before.values[mode][event]);
      out[names[event]] = std::move(row);
    }
    return out;
  }
};

}
