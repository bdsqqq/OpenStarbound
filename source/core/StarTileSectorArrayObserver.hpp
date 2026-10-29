#pragma once

#include <array>
#include <cstdint>
#include <type_traits>
#ifdef STAR_USE_RUST_STATIC_VECTOR
#include "StarRustStaticVector.h"
#endif

namespace Star { namespace TileSectorArrayObserver {

// Opt-in caller-thread diagnostics only. Never enter the parallel column callback:
// split construction and iteration happen here, tile samples happen after render.
using Counters = std::array<std::array<uint64_t, 2>, 26>;
struct State {
  void const* array;
  uint64_t frameSequence;
  uint64_t scopeId;
  std::array<int, 2> worldSize;
  std::array<int, 4> clientWindow, tileRange;
  int bufferTiles;
  unsigned callsiteCalls, splitCalls, returnedRects;
  std::array<std::array<int, 5>, 2> splits;
  Counters before, after;
  bool callsiteActive, returned, overflow;
};
static_assert(std::is_trivial<State>::value && std::is_standard_layout<State>::value, "observer state must stay POD");
inline thread_local State state{};
inline thread_local State* armed = nullptr;
inline void disarm() noexcept { armed = nullptr; state.callsiteActive = false; }
inline void snapshot(Counters& out) noexcept {
  for (unsigned mode = 0; mode < 26; ++mode)
    for (unsigned stage = 0; stage < 2; ++stage) {
#ifdef STAR_USE_RUST_STATIC_VECTOR
      out[mode][stage] = sb_static_vector_count(mode, stage);
#else
      out[mode][stage] = 0;
#endif
    }
}
struct Frame {
  bool observing;
  Frame(bool scene, bool ready) noexcept : observing(scene) {
    if (!scene) return;
    auto sequence = state.frameSequence + 1;
    state = State{};
    state.frameSequence = state.scopeId = sequence;
    armed = ready ? &state : nullptr;
  }
  ~Frame() noexcept { if (observing) disarm(); }
  Frame(Frame const&) = delete;
  Frame& operator=(Frame const&) = delete;
};
struct Callsite {
  State* probe;
  template <typename Size, typename Rect>
  Callsite(void const* array, Size const& size, Rect const& window, Rect const& range, int buffer) noexcept
    : probe(armed) {
    if (!probe) return;
    ++probe->callsiteCalls;
    probe->array = array;
    probe->worldSize = {{int(size[0]), int(size[1])}};
    probe->clientWindow = {{window.xMin(), window.yMin(), window.xMax(), window.yMax()}};
    probe->tileRange = {{range.xMin(), range.yMin(), range.xMax(), range.yMax()}};
    probe->bufferTiles = buffer;
    probe->callsiteActive = true;
  }
  ~Callsite() noexcept { if (probe) probe->callsiteActive = false; }
  Callsite(Callsite const&) = delete;
  Callsite& operator=(Callsite const&) = delete;
};
struct Split {
  State* probe;
  explicit Split(void const* array) noexcept
    : probe(armed && armed->callsiteActive && armed->array == array ? armed : nullptr) {
    if (probe) { ++probe->splitCalls; snapshot(probe->before); }
  }
  // Return value construction precedes local destruction, including without NRVO.
  ~Split() noexcept { if (probe) { snapshot(probe->after); probe->returned = true; } }
  Split(Split const&) = delete;
  Split& operator=(Split const&) = delete;
};
template <typename Rect>
inline void observe(void const* array, Rect const& rect, int xOffset) noexcept {
  auto p = armed;
  if (!p || !p->callsiteActive || p->array != array) return;
  auto i = p->returnedRects++;
  if (i >= p->splits.size()) { p->overflow = true; return; }
  p->splits[i] = {{rect.xMin(), rect.yMin(), rect.xMax(), rect.yMax(), xOffset}};
}
}}
