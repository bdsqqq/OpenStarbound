#pragma once

#include "StarJson.hpp"
#include "StarEncode.hpp"
#include <cstdlib>
#include <cstdint>

// no application dependency in game/core; only the opt-in caller arms this TLS
// observer. snapshots copy keys, never values or their shared_ptr ownership.
#ifdef STAR_USE_RUST_LRU_CACHE
#include "StarRustLruCache.h"
#endif

namespace Star::LruCacheLab {
inline char const* backend() {
#ifdef STAR_USE_RUST_LRU_CACHE
  return "rust";
#else
  return "native";
#endif
}
inline uint64_t rootGets() noexcept {
#ifdef STAR_USE_RUST_LRU_CACHE
  return sb_lru_count(10, 0);
#else
  return 0;
#endif
}
inline String counterHex(uint64_t value) {
  // byte-exact big-endian representation avoids JSON double/Lua integer loss.
  ByteArray bytes;
  for (int shift = 56; shift >= 0; shift -= 8)
    bytes.appendByte(char(value >> shift));
  return hexEncode(bytes);
}
inline thread_local bool armed = false;
inline thread_local JsonArray events;
inline void begin() {
  if (!std::getenv("STAR_BEHAVIOR_LAB") || armed)
    throw StarException("BehaviorLab: invalid LRU observation scope");
  events.clear();
  armed = true;
}
inline Json finish() {
  if (!armed) throw StarException("BehaviorLab: missing LRU observation scope");
  armed = false;
  return Json(events);
}
inline void cancel() noexcept { armed = false; }

template <typename Cache>
inline Json snapshot(Cache const& cache) {
  JsonArray keys;
  for (auto const& key : cache.keys())
    keys.append(hexEncode(key.utf8Ptr(), key.utf8().size()));
  return JsonObject{{"size", cache.currentSize()}, {"max", cache.maxSize()}, {"keysHex", keys}};
}

// declared after the caller's MutexLocker and destroyed before it: both states
// and producer-time pre-eviction state are observed under the existing lock.
// the original get return expression remains a full expression; no Value copy,
// ptr call, nested get, or replacement producer is introduced by observation.
template <typename Cache>
class Scope {
public:
  Scope(Cache const& cache, String const& name) : m_cache(cache), m_active(armed) {
    if (!m_active) return;
    m_event = JsonObject{{"operation", "DungeonDefinitions.get"}, {"index", events.size()},
        {"nameHex", hexEncode(name.utf8Ptr(), name.utf8().size())}, {"before", snapshot(cache)},
        {"producerCalled", false}, {"producerState", Json()},
        {"status", "ok"}, {"error", Json()}, {"rootBeforeHex", counterHex(rootGets())}};
  }
  void producer() {
    if (m_active) m_event = m_event.set("producerCalled", true).set("producerState", snapshot(m_cache));
  }
  void error(char const* kind, String const& message) {
    if (m_active) m_event = m_event.set("status", "error").set("error",
        JsonObject{{"kind", kind}, {"messageHex", hexEncode(message.utf8Ptr(), message.utf8().size())}});
  }
  ~Scope() noexcept(false) {
    if (m_active) events.append(m_event.set("after", snapshot(m_cache))
        .set("rootAfterHex", counterHex(rootGets())));
  }
private:
  Cache const& m_cache;
  bool m_active;
  Json m_event;
};
}
