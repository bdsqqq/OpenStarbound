#pragma once

#include "StarJson.hpp"
#include <array>
#include <cstdint>
#include <stdexcept>
#if defined(STAR_USE_RUST_FILE) && STAR_USE_RUST_FILE
#include "StarRustFile.h"
#endif

namespace Star::FileLab {

// Internal scaffold only; counters measure controller entry, not native prefix
// initialization. The injected reader must not throw, allocate, or call File.
using Reader = uint64_t (*)(unsigned, unsigned);
inline uint64_t readCount(unsigned mode, unsigned event) noexcept {
#if defined(STAR_USE_RUST_FILE) && STAR_USE_RUST_FILE
  return star_file_call_count(mode, event);
#else
  (void)mode; (void)event;
  return 0;
#endif
}
struct Counts {
  std::array<std::array<uint64_t, 3>, 34> values{};
  static Counts snapshot(Reader reader) noexcept {
    Counts out;
    for (unsigned m = 0; m < 34; ++m)
      for (unsigned e = 0; e < 3; ++e) out.values[m][e] = reader(m, e);
    return out;
  }
  Counts delta(Counts const& before) const noexcept {
    Counts out;
    for (unsigned m = 0; m < 34; ++m)
      for (unsigned e = 0; e < 3; ++e) out.values[m][e] = values[m][e] - before.values[m][e];
    return out;
  }
  void add(Counts const& other) noexcept {
    for (unsigned m = 0; m < 34; ++m)
      for (unsigned e = 0; e < 3; ++e) values[m][e] += other.values[m][e];
  }
  Json toJson() const {
    JsonObject out;
    char const* events[] = {"attempt", "success", "exception"};
    for (unsigned e = 0; e < 3; ++e) {
      JsonArray row;
      for (unsigned m = 0; m < 34; ++m) row.append(values[m][e]);
      out[events[e]] = std::move(row);
    }
    return out;
  }
};
struct Recorder {
  struct Entry { Counts calls; bool started = false, completed = false, mainThread = false; };
  std::array<Entry, 5> scopes{};
  unsigned next = 0, liveScopes = 0;
  bool measuring = false, valid = true, overflow = false;
  Reader reader = readCount;
  // Serialize after every scope completes, then retain this same snapshot for
  // the three acknowledged frames. A completed scope may stay in the caller's
  // lexical lifetime so direct native return initialization need not move.
  Json toJson(String const& saveHex, String const& foundHex) const;
};

// No TLS recorder/borrow crosses native callbacks. Application initialization
// establishes the main thread; caller passes that identity for EACH scope.
struct Scope {
  Recorder* recorder;
  unsigned index;
  Counts before;
  bool finished = false;
  Scope(Recorder& r, unsigned i, bool mainThread) noexcept : recorder(&r), index(i) {
    if (i >= 5 || i != r.next || r.measuring || !r.reader) {
      r.valid = false; r.overflow = true; recorder = nullptr; return;
    }
    ++r.liveScopes;
    r.measuring = true;
    r.scopes[i].started = true;
    r.scopes[i].mainThread = mainThread;
    if (!mainThread) r.valid = false;
    before = Counts::snapshot(r.reader);
  }
  // Call immediately after native work, before any observer/metadata/capture.
  // For scope 2: auto bytes = File::readFile(path); scope.complete();
  // Keep the direct local return: do not wrap it in optional/lambda moves.
  void complete() noexcept {
    if (!recorder || finished) return;
    auto& r = *recorder;
    r.scopes[index].calls = Counts::snapshot(r.reader).delta(before);
    r.scopes[index].completed = true;
    r.measuring = false;
    --r.liveScopes;
    ++r.next;
    finished = true;
  }
  ~Scope() noexcept {
    if (!recorder) return;
    if (!finished) {
      recorder->valid = false;
      recorder->measuring = false;
      --recorder->liveScopes;
    }
  }
  Scope(Scope const&) = delete;
  Scope& operator=(Scope const&) = delete;
};

inline Json Recorder::toJson(String const& saveHex, String const& foundHex) const {
  if (liveScopes || measuring)
    throw std::logic_error("FileLab serialization inside native scope");
  char const* methods[] = {"VersionedJson::writeFile", "VersionedJson::readFile", "File::readFile",
    "BTreeSha256Database::open/insert/commit/close(file)", "BTreeSha256Database::open/find/close(file)"};
  Counts total;
  JsonArray entries;
  bool main = true, done = next == 5;
  for (unsigned i = 0; i < 5; ++i) {
    auto const& s = scopes[i];
    main = main && s.mainThread;
    done = done && s.started && s.completed;
    total.add(s.calls);
    entries.append(JsonObject{{"method", methods[i]}, {"started", s.started}, {"completed", s.completed},
      {"mainThread", s.mainThread}, {"calls", s.calls.toJson()}});
  }
#if defined(STAR_USE_RUST_FILE) && STAR_USE_RUST_FILE
  char const* backend = "rust";
#else
  char const* backend = "cpp";
#endif
  return JsonObject{{"version", 1}, {"backend", backend}, {"scopeThread", main ? "main" : "unknown"},
    {"mainThread", main}, {"captureExcluded", !liveScopes && !measuring}, {"valid", valid},
    {"overflow", overflow}, {"completed", done}, {"calls", total.toJson()}, {"scopes", std::move(entries)},
    {"saveFile", "buffer-save.sbvj"}, {"databaseFile", "buffer-payload.btree"},
    {"saveHex", saveHex}, {"foundHex", foundHex}};
}
}
