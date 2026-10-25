#pragma once
#include "StarJson.hpp"
#include "StarByteArray.hpp"
#ifdef STAR_USE_RUST_DATA_STREAM
#include "StarRustDataStream.h"
#endif
namespace Star {
// Main-thread scopes retain nested controller calls; they are not one-hot.
struct DataStreamLabCounts {
  uint64_t values[51][3]{};
  static DataStreamLabCounts snapshot() noexcept {
    DataStreamLabCounts out;
#ifdef STAR_USE_RUST_DATA_STREAM
    for (unsigned m = 0; m != 51; ++m)
      for (unsigned e = 0; e != 3; ++e)
        out.values[m][e] = star_data_stream_call_count(m, e);
#endif
    return out;
  }
  Json delta(DataStreamLabCounts const& before) const {
    JsonObject out;
    char const* names[] = {"attempt", "success", "exception"};
    for (unsigned e = 0; e != 3; ++e) {
      JsonArray row;
      for (unsigned m = 0; m != 51; ++m) row.append(values[m][e] - before.values[m][e]);
      out[names[e]] = std::move(row);
    }
    return out;
  }
};
// The only observer is an explicitly armed fixture on this thread and socket.
// Copy before send, retain only the successfully sent prefix after send; retries
// cannot double-count bytes and no borrowed view survives the native boundary.
struct DataStreamLabWire {
  void const* socket = nullptr;
  ByteArray offered, wire;
  uint64_t attempts = 0, completions = 0;
};
inline thread_local DataStreamLabWire* DataStreamLabActiveWire = nullptr;
inline void dataStreamLabOffer(void const* socket, char const* bytes, size_t size) {
  if (auto p = DataStreamLabActiveWire; p && p->socket == socket) {
    p->offered = ByteArray(bytes, size);
    ++p->attempts;
  }
}
inline void dataStreamLabSent(void const* socket, size_t size) {
  if (auto p = DataStreamLabActiveWire; p && p->socket == socket) {
    if (size > p->offered.size()) throw StarException("BehaviorLab: invalid DataStream send length");
    p->wire.append(p->offered.ptr(), size);
    ++p->completions;
  }
}
}
