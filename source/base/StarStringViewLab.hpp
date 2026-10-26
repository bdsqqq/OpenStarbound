#pragma once

#include "StarJson.hpp"
#include "StarImage.hpp"
#include <array>
#include <cstdint>
#if defined(STAR_USE_RUST_STRING_VIEW) && STAR_USE_RUST_STRING_VIEW
#include "StarRustStringView.h"
#endif

namespace Star::StringViewLab {

// Internal fixture helpers only. No per-entry allocation or getter hooks.
using Reader = uint64_t (*)(unsigned, unsigned);
inline uint64_t readCount(unsigned mode, unsigned event) {
#if defined(STAR_USE_RUST_STRING_VIEW) && STAR_USE_RUST_STRING_VIEW
  return star_string_view_call_count(mode, event);
#else
  (void)mode;
  (void)event;
  return 0;
#endif
}
struct Counts {
  std::array<std::array<uint64_t, 3>, 58> values{};
  static Counts snapshot(Reader reader) {
    Counts out;
    for (unsigned m = 0; m < 58; ++m)
      for (unsigned e = 0; e < 3; ++e)
        out.values[m][e] = reader(m, e);
    return out;
  }
  void add(Counts const& other) noexcept {
    for (unsigned m = 0; m < 58; ++m)
      for (unsigned e = 0; e < 3; ++e)
        values[m][e] += other.values[m][e];
  }
  Counts delta(Counts const& before) const noexcept {
    Counts out;
    for (unsigned m = 0; m < 58; ++m)
      for (unsigned e = 0; e < 3; ++e)
        out.values[m][e] = values[m][e] - before.values[m][e];
    return out;
  }
  Json toJson() const {
    JsonObject out;
    char const* names[] = {"attempt", "success", "exception"};
    for (unsigned e = 0; e < 3; ++e) {
      JsonArray row;
      for (unsigned m = 0; m < 58; ++m) row.append(values[m][e]);
      out[names[e]] = std::move(row);
    }
    return out;
  }
};
struct Recorder {
  struct Entry { Counts calls; bool started = false; bool completed = false; };
  std::array<Entry, 2> scopes{};
  std::array<Vec4B, 2> transitions{};
  size_t transitionCount = 0;
  bool active = false; // Historical: armed for the normal GUI fixture call.
  bool mainThread = false;
  bool valid = true;
  bool overflow = false;
  bool armed = false;
  bool measuring = false;
  Reader reader = readCount;
  Json toJson() const;
};
inline thread_local Recorder* current = nullptr;

// Caller must establish the application's main-thread identity. TLS alone does
// not establish it. Arm ONLY around the normal fixture GUI call, never capture.
struct Arm {
  Recorder& recorder;
  Recorder* previous;
  Arm(Recorder& r, bool mainThread) : recorder(r), previous(current) {
    if (previous || r.active || !mainThread) r.valid = false;
    r.active = true;
    r.mainThread = mainThread;
    r.armed = true;
    current = &r;
  }
  ~Arm() { recorder.armed = false; current = previous; }
  Arm(Arm const&) = delete;
  Arm& operator=(Arm const&) = delete;
};

// 0: around normal AssetPath construction (not a direct parser invocation).
// Source chain: AssetPath.cpp:40 -> Directives.cpp:145 ->
// ImageProcessing.cpp:133. Pixel assignment is separate at :572.
// 1: exactly applyCommands, AFTER TextProcessLab::event at TextPainter.cpp:452.
// complete() follows successful work; unwinding leaves the entry incomplete.
struct Scope {
  Recorder* recorder = current;
  unsigned index;
  Counts before;
  Counts excluded;
  bool paused = false;
  bool finished = false;
  explicit Scope(unsigned i) : index(i) {
    if (!recorder) return;
    if (i >= 2 || recorder->measuring || recorder->scopes[i].started) {
      recorder->valid = false;
      recorder->overflow = true;
      recorder = nullptr;
      return;
    }
    recorder->scopes[i].started = true;
    recorder->measuring = true;
    before = Counts::snapshot(recorder->reader);
  }
  void complete() {
    if (!recorder || finished) return;
    recorder->scopes[index].calls = Counts::snapshot(recorder->reader).delta(before).delta(excluded);
    recorder->scopes[index].completed = !paused;
    recorder->measuring = false;
    finished = true;
  }
  // Invoke immediately AFTER assigning m_renderSettings.shadow. These extra
  // snapshots exclude observation, not source assignment or command parsing.
  void shadow(Vec4B const& rgba) {
    if (!recorder || finished) return;
    auto start = Counts::snapshot(recorder->reader);
    paused = true;
    if (index != 1 || recorder->transitionCount == recorder->transitions.size()) {
      recorder->valid = false;
      recorder->overflow = true;
    } else {
      recorder->transitions[recorder->transitionCount++] = rgba;
    }
    excluded.add(Counts::snapshot(recorder->reader).delta(start));
    paused = false;
  }
  ~Scope() {
    if (recorder && !finished) {
      recorder->valid = false;
      recorder->measuring = false;
    }
  }
  Scope(Scope const&) = delete;
  Scope& operator=(Scope const&) = delete;
};

inline Json Recorder::toJson() const {
  // Call after scopes complete and Arm ends. Counts are frozen before JSON
  // construction and framebuffer capture, so neither observer earns credit.
  bool done = !armed && !measuring && scopes[0].completed && scopes[1].completed;
  JsonArray entries;
  Counts total;
  char const* methods[] = {"AssetPath::split/Directives::parse/imageOperationFromString",
                          "TextPainter::applyCommands"};
  for (unsigned i = 0; i < 2; ++i) {
    total.add(scopes[i].calls);
    entries.append(JsonObject{{"method", methods[i]}, {"completed", scopes[i].completed},
                              {"calls", scopes[i].calls.toJson()}});
  }
  JsonArray states;
  char const* commands[] = {"shadow", "noshadow"};
  for (size_t i = 0; i < transitionCount; ++i) {
    JsonArray rgba;
    for (unsigned c = 0; c < 4; ++c) rgba.append(transitions[i][c]);
    states.append(JsonObject{{"command", commands[i]}, {"rgba", std::move(rgba)}});
  }
#if defined(STAR_USE_RUST_STRING_VIEW) && STAR_USE_RUST_STRING_VIEW
  char const* backend = "rust";
#else
  char const* backend = "cpp";
#endif
  return JsonObject{{"version", 1}, {"backend", backend}, {"active", active},
    {"scopeThread", mainThread ? "main" : "unknown"}, {"captureExcluded", !armed && !measuring},
    {"valid", valid}, {"overflow", overflow}, {"completed", done},
    {"calls", total.toJson()}, {"scopes", std::move(entries)}, {"transitions", std::move(states)}};
}

// Observe the actual Assets image after measurement/capture. PNG/Pillow rows
// run top-to-bottom; Star::Image coordinates run bottom-to-top.
inline Json imageJson(Image const& image) {
  JsonArray rgba;
  if (image.width() == 2 && image.height() == 2) {
    for (unsigned row = 0; row < 2; ++row)
      for (unsigned x = 0; x < 2; ++x) {
        auto pixel = image.getrgb(x, 1 - row);
        JsonArray channels;
        for (unsigned c = 0; c < 4; ++c) channels.append(pixel[c]);
        rgba.append(std::move(channels));
      }
  }
  return JsonObject{{"width", image.width()}, {"height", image.height()}, {"rgba", std::move(rgba)}};
}

}
