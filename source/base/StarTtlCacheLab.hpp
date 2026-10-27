#pragma once
#include "StarJson.hpp"
#include "StarEncode.hpp"
#include "StarTime.hpp"
#include <atomic>
#include <mutex>
#include <thread>
#include <cstdlib>
#ifdef STAR_USE_RUST_TTL_CACHE
#include "StarRustTtlCache.h"
#endif

namespace Star {
// Only keys/timestamps/scalars are read, under TenantDatabase's existing lock.
// No cache method is called: inspection cannot refresh recency or Rust counters.
struct TtlCacheLabAccess {
  template <typename Cache> static Json snapshot(Cache const& cache) {
    JsonArray entries;
    for (auto const& entry : cache.m_cache.m_map)
      entries.append(JsonObject{{"keyHex", hexEncode(entry.first.utf8Ptr(), entry.first.utf8Size())},
          {"stamp", entry.second.first}});
    return JsonObject{{"entries", entries}, {"ttl", cache.m_timeToLive},
        {"smear", cache.m_timeSmear}, {"update", cache.m_ttlUpdateEnabled},
        {"maxHex", strf("{:016x}", uint64_t(cache.m_cache.m_maxSize))}};
  }
};
namespace TtlCacheLab {
inline char const* backend() {
#ifdef STAR_USE_RUST_TTL_CACHE
  return "rust";
#else
  return "native";
#endif
}
inline String count(unsigned mode) {
  uint64_t value = 0;
#ifdef STAR_USE_RUST_TTL_CACHE
  value = sb_ttl_count(mode, 0);
#endif
  return strf("{:016x}", value);
}
inline Json counters() { return JsonObject{{"get", count(16)}, {"cleanup", count(18)}}; }
inline std::mutex recordMutex;
inline std::atomic<bool> watching{false};
inline JsonArray events;
inline std::thread::id foreground;
inline unsigned phase = 0;
inline void begin() {
  std::lock_guard<std::mutex> lock(recordMutex);
  if (!std::getenv("STAR_BEHAVIOR_LAB") || watching) throw StarException("BehaviorLab: invalid TTL watch");
  events.clear(); foreground = std::this_thread::get_id(); phase = 0; watching = true;
}
inline void setPhase(unsigned value) { std::lock_guard<std::mutex> lock(recordMutex); phase = value; }
inline Json history() { std::lock_guard<std::mutex> lock(recordMutex); return events; }
inline void stop() { watching = false; }
struct ProducerHook {
  inline static thread_local ProducerHook* current = nullptr;
  ProducerHook* previous = nullptr;
  virtual void producer() = 0;
  virtual ~ProducerHook() noexcept(false) = default;
};
inline void producer() { if (ProducerHook::current) ProducerHook::current->producer(); }
// Stack-scoped observer only, NOT a cache controller. Watch is global so Root's
// maintenance thread cannot expire an entry invisibly. Allocations/time reads
// are lab-only; OOM/observer exceptions are outside this finite proof domain.
template <typename Cache> struct Scope : ProducerHook {
  Cache const& cache;
  bool active;
  Json event;
  Scope(Cache const& c, char const* operation, String const& key = {}) : cache(c), active(watching.load()) {
    if (!active) return;
    std::lock_guard<std::mutex> lock(recordMutex);
    event = JsonObject{{"operation", operation}, {"phase", phase},
        {"foreground", std::this_thread::get_id() == foreground},
        {"keyHex", hexEncode(key.utf8Ptr(), key.utf8Size())},
        {"before", TtlCacheLabAccess::snapshot(cache)}, {"clockBefore", Time::monotonicMilliseconds()},
        {"countersBefore", counters()}, {"producer", Json()}, {"errorHex", Json()}};
    previous = current; current = this;
  }
  void producer() override {
    if (active) event = event.set("producer", JsonObject{{"state", TtlCacheLabAccess::snapshot(cache)},
        {"clock", Time::monotonicMilliseconds()}});
  }
  void error(char const* what) {
    if (active) event = event.set("errorHex", hexEncode(what, std::char_traits<char>::length(what)));
  }
  ~Scope() noexcept(false) {
    if (!active) return;
    current = previous;
    auto after = Time::monotonicMilliseconds();
    std::lock_guard<std::mutex> lock(recordMutex);
    events.append(event.set("after", TtlCacheLabAccess::snapshot(cache)).set("clockAfter", after)
        .set("countersAfter", counters()).set("index", events.size()));
  }
};
}
}
