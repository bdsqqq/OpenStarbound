#pragma once

#include "StarText.hpp"
#include <array>
#include <cstdint>

namespace Star::TextProcessLab {

// Lab-only observation: callbacks must neither allocate nor throw through the
// scanner boundary. Overflow invalidates the proof instead of truncating it.
struct Recorder {
  struct Event {
    uint32_t kind = 0;
    size_t size = 0;
    std::array<unsigned char, 32> bytes{};
  };
  struct Glyph {
    uint32_t codepoint = 0;
    Vec4B rgba = Vec4B::filled(0);
  };
  std::array<Event, 8> events{};
  std::array<Glyph, 16> glyphs{};
  size_t eventCount = 0;
  size_t glyphCount = 0;
  bool valid = true;
  bool completed = false;
};

inline thread_local Recorder* current = nullptr;
inline thread_local bool foreground = false;

struct Scope {
  Recorder* previous;
  bool previousForeground;
  explicit Scope(Recorder& recorder) noexcept
    : previous(current), previousForeground(foreground) {
    current = &recorder;
    foreground = false;
  }
  ~Scope() noexcept {
    current = previous;
    foreground = previousForeground;
  }
  Scope(Scope const&) = delete;
  Scope& operator=(Scope const&) = delete;
};

struct ForegroundScope {
  bool previous;
  ForegroundScope() noexcept : previous(foreground) { foreground = true; }
  ~ForegroundScope() noexcept { foreground = previous; }
};

inline void event(uint32_t kind, StringView text) noexcept {
  if (!current)
    return;
  if (current->eventCount == current->events.size() || text.utf8Size() > 32) {
    current->valid = false;
    return;
  }
  auto& entry = current->events[current->eventCount++];
  entry.kind = kind;
  entry.size = text.utf8Size();
  for (size_t i = 0; i < entry.size; ++i)
    entry.bytes[i] = static_cast<unsigned char>(text.utf8Ptr()[i]);
}

inline void glyph(uint32_t codepoint, Vec4B const& color) noexcept {
  if (!current || !foreground)
    return;
  if (current->glyphCount == current->glyphs.size()) {
    current->valid = false;
    return;
  }
  auto& entry = current->glyphs[current->glyphCount++];
  entry.codepoint = codepoint;
  entry.rgba = color;
}

}
