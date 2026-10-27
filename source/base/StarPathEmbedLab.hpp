#pragma once

#include "StarJson.hpp"
#include "StarImage.hpp"
#include "StarEncode.hpp"
#include <array>
#ifdef STAR_USE_RUST_PATH_EMBED
#include "StarRustPathEmbed.h"
#endif

namespace Star::PathEmbedLab {

using Counts = std::array<uint64_t, 2>;
inline Counts snapshot() noexcept {
#ifdef STAR_USE_RUST_PATH_EMBED
  return {{star_path_embed_completed(0), star_path_embed_completed(1)}};
#else
  return {{0, 0}};
#endif
}
inline char const* backend() {
#ifdef STAR_USE_RUST_PATH_EMBED
  return "rust";
#else
  return "native";
#endif
}
inline Json countsJson(Counts const& counts) {
  return JsonObject{{"selector", counts[0]}, {"escape", counts[1]}};
}

// only the opt-in Lua methods arm this observer; TLS follows the actual Lua
// caller, not the later render thread. exceptions never publish a completion.
struct Record {
  Image const* image = nullptr;
  bool used = false, armed = false, measuring = false, completed = false, valid = true;
  unsigned operations = 0;
  Counts before{}, after{};
  String path, rawFrames, escapedFrames;
};
inline thread_local Record record;
inline thread_local Record* current = nullptr;

// readPng reverses PNG rows (StarImage.cpp); frame rectangles are top-down
// (Assets::loadImage). this full-height right crop retains the native y axis.
inline Json imageJson(Image const& image, bool crop) {
  unsigned width = crop ? 16 : 32;
  if (image.size() != Vec2U(width, 16))
    throw StarException("BehaviorLab: PathEmbed decoded dimensions differ");
  Vec4B const colors[] = {{240, 80, 40, 255}, {40, 200, 120, 255},
      {40, 80, 240, 255}, {240, 200, 40, 255}};
  ByteArray rgba;
  for (unsigned y = 0; y < 16; ++y)
    for (unsigned x = 0; x < width; ++x) {
      unsigned u = x % 16;
      unsigned topY = 15 - y;
      Vec4B expected(224, 32, 176, 255);
      if (crop || x >= 16) {
        expected = colors[(topY / 8) * 2 + u / 8];
        if (u == 1 && topY == 1) expected = Vec4B(255, 255, 255, 255);
        if (u == 14 && topY == 14) expected = Vec4B(0, 0, 0, 255);
      }
      auto pixel = image.getrgb(x, y);
      if (pixel != expected) throw StarException("BehaviorLab: PathEmbed decoded pixels/orientation differ");
      for (unsigned c = 0; c < 4; ++c) rgba.appendByte(char(pixel[c]));
    }
  return JsonObject{{"size", JsonArray{width, 16}}, {"layout", "native-bottom-up-rgba8"},
      {"rgbaHex", hexEncode(rgba)}};
}
inline void begin(Image const& image) {
  if (record.used) throw StarException("BehaviorLab: repeated PathEmbed observer");
  record.used = record.armed = true;
  record.image = &image;
  current = &record;
}
struct Scope {
  bool active = current != nullptr;
  explicit Scope(Image const& image) {
    if (!active) return;
    if (record.image != &image || record.measuring || record.operations++) {
      record.valid = false;
      throw StarException("BehaviorLab: aliased/repeated PathEmbed operation");
    }
    record.measuring = true;
    record.before = snapshot();
  }
  void complete(String const& path, Json const* frames, bool none, bool text) {
    if (!active) return;
    record.after = snapshot();
    record.measuring = false;
    if (!none || !text || !frames) {
      record.valid = false;
      throw StarException("BehaviorLab: PathEmbed must use None/text frames");
    }
    auto parts = path.split(";");
    if (parts.size() != 6 || parts[0] != "/opensb_data" || parts[1] != "image"
        || parts[3] != "frames" || parts[4] != "text") {
      record.valid = false;
      throw StarException("BehaviorLab: malformed PathEmbed path");
    }
    // observations occur after the completed-counter snapshot, not in a
    // replacement façade or codec; the original prvalue expressions stay put.
    record.path = path;
    record.rawFrames = frames->repr();
    record.escapedFrames = parts[5];
    record.completed = true;
  }
  ~Scope() noexcept {
    if (active && record.measuring) {
      record.valid = false;
      record.measuring = false;
    }
  }
};
inline Json finish(Image const& image) {
  if (!record.armed || record.image != &image || record.measuring || !record.valid
      || !record.completed || record.operations != 1)
    throw StarException("BehaviorLab: incomplete PathEmbed operation");
  record.armed = false;
  current = nullptr;
  Counts delta{{record.after[0] - record.before[0], record.after[1] - record.before[1]}};
#ifdef STAR_USE_RUST_PATH_EMBED
  Counts const expected{{1, 1}};
#else
  Counts const expected{{0, 0}};
#endif
  if (delta != expected) throw StarException("BehaviorLab: PathEmbed completed counters differ");
  return JsonObject{{"version", 1}, {"backend", backend()}, {"scopeThread", "lua-calling-thread"},
      {"completed", true}, {"operationCount", record.operations},
      {"before", countsJson(record.before)}, {"after", countsJson(record.after)}, {"delta", countsJson(delta)},
      {"method", "None"}, {"framesMode", "text"}, {"path", record.path},
      {"rawFrames", record.rawFrames}, {"escapedFrames", record.escapedFrames}};
}

}
