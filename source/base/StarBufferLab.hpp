#pragma once
#include "StarJson.hpp"
#include "StarByteArray.hpp"
#include "StarByteArrayLab.hpp"
#ifdef STAR_USE_RUST_BUFFER
#include "StarRustBuffer.h"
#endif
namespace Star {
struct BufferLabCounts {
  uint64_t values[50][3]{};
  static BufferLabCounts snapshot() noexcept {
    BufferLabCounts out;
#ifdef STAR_USE_RUST_BUFFER
    for (unsigned m = 0; m != 50; ++m)
      for (unsigned e = 0; e != 3; ++e) out.values[m][e] = star_buffer_call_count(m, e);
#endif
    return out;
  }
  Json delta(BufferLabCounts const& before) const {
    JsonObject out;
    char const* names[] = {"attempt", "success", "exception"};
    for (unsigned e = 0; e != 3; ++e) {
      JsonArray row;
      for (unsigned m = 0; m != 50; ++m) row.append(values[m][e] - before.values[m][e]);
      out[names[e]] = std::move(row);
    }
    return out;
  }
};
// Explicit main-thread fixture scope, matched to the receiver object. Production
// traffic outside this scope does not allocate, copy bytes, or collect events.
struct BufferLabReceiver {
  void const* socket = nullptr;
  unsigned stage = 0;
  ByteArray wire;
  JsonArray events;
};
inline thread_local BufferLabReceiver* BufferLabActiveReceiver = nullptr;
inline BufferLabReceiver* bufferLabReceiver(void const* socket) {
  auto p = BufferLabActiveReceiver;
  return p && p->socket == socket ? p : nullptr;
}
inline void bufferLabReceived(void const* socket, char const* bytes, size_t size, size_t buffered) {
  if (auto p = bufferLabReceiver(socket)) {
    ByteArrayLabBookkeepingScope bookkeeping;
    p->wire.append(bytes, size);
    p->events.append(JsonObject{{"stage", p->stage}, {"kind", "receive"},
        {"bytes", size}, {"cumulativeBytes", p->wire.size()}, {"bufferSize", buffered}});
  }
}
inline void bufferLabParser(void const* socket, char const* kind, size_t pos, size_t size, size_t remaining, size_t consumed) {
  if (auto p = bufferLabReceiver(socket)) {
    ByteArrayLabBookkeepingScope bookkeeping;
    p->events.append(JsonObject{{"stage", p->stage}, {"kind", kind}, {"pos", pos},
        {"size", size}, {"remaining", remaining}, {"consumed", consumed}});
  }
}
}
