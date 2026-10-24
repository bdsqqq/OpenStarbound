#include "StarBehaviorLab.hpp"
#include "StarBuffer.hpp"
#include "StarFile.hpp"
#include "StarImage.hpp"

#include "GL/glew.h"

#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <set>
#include <stdexcept>
#include <thread>

namespace Star {
namespace {
namespace fs = std::filesystem;

void require(bool condition, char const* message) {
  if (!condition)
    throw std::runtime_error(message);
}

bool regularFile(fs::path const& path) {
  return fs::is_regular_file(fs::symlink_status(path));
}

struct LabState {
  bool active = false;
  Json config;
  fs::path output;
  std::thread::id owner;
  String pendingName;
  Json pendingMetadata;
  std::set<String> captured;

  LabState() {
    auto environment = std::getenv("STAR_BEHAVIOR_LAB");
    if (!environment)
      return; // Ordinary runs do not even inspect the filesystem.
    fs::path configPath = fs::u8path(environment);
    require(configPath.is_absolute() && regularFile(configPath),
        "BehaviorLab: config must be an absolute regular file (not a symlink)");
    require(fs::file_size(configPath) <= 1024 * 1024, "BehaviorLab: config is too large");
    config = Json::parseJson(File::readFileString(String(configPath.u8string())));
    require(config.type() == Json::Type::Object, "BehaviorLab: config must be an object");
    output = fs::u8path(config.getString("outputDirectory").utf8());
    require(output.is_absolute() && fs::is_directory(fs::symlink_status(output)),
        "BehaviorLab: outputDirectory must be an existing absolute directory, not a symlink");
    output = fs::canonical(output);
    validateOutput();
    owner = std::this_thread::get_id();
    active = true;
  }

  void validateOutput() const {
    require(fs::is_directory(fs::symlink_status(output)) && regularFile(output / ".star-behavior-lab"),
        "BehaviorLab: outputDirectory requires runner-owned .star-behavior-lab sentinel file");
  }

  void checkOwner() const {
    require(owner == std::this_thread::get_id(), "BehaviorLab: main-thread-only API");
  }
};

LabState& state() {
  static LabState instance;
  if (instance.active)
    instance.checkOwner();
  return instance;
}

// C11 exclusive creation refuses existing files, including dangling symlinks.
// Failed captures remain unacknowledged; partial artifacts require a fresh run directory.
void writeExclusive(fs::path const& path, char const* data, size_t size) {
#ifdef STAR_SYSTEM_WINDOWS
  auto file = _wfopen(path.c_str(), L"wbx");
#else
  auto file = std::fopen(path.c_str(), "wbx");
#endif
  require(file != nullptr, "BehaviorLab: cannot exclusively create capture output");
  bool written = std::fwrite(data, 1, size, file) == size;
  bool closed = std::fclose(file) == 0;
  require(written && closed, "BehaviorLab: cannot complete capture output");
}

struct ReadbackState {
  GLint framebuffer, readBuffer, defaultReadBuffer, packBuffer;
  GLint alignment, rowLength, skipRows, skipPixels;

  ReadbackState() {
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &framebuffer);
    glGetIntegerv(GL_READ_BUFFER, &readBuffer);
    glGetIntegerv(GL_PIXEL_PACK_BUFFER_BINDING, &packBuffer);
    glGetIntegerv(GL_PACK_ALIGNMENT, &alignment);
    glGetIntegerv(GL_PACK_ROW_LENGTH, &rowLength);
    glGetIntegerv(GL_PACK_SKIP_ROWS, &skipRows);
    glGetIntegerv(GL_PACK_SKIP_PIXELS, &skipPixels);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);
    glGetIntegerv(GL_READ_BUFFER, &defaultReadBuffer);
    glBindBuffer(GL_PIXEL_PACK_BUFFER, 0);
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    glPixelStorei(GL_PACK_ROW_LENGTH, 0);
    glPixelStorei(GL_PACK_SKIP_ROWS, 0);
    glPixelStorei(GL_PACK_SKIP_PIXELS, 0);
  }

  ~ReadbackState() {
    glReadBuffer(defaultReadBuffer);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, framebuffer);
    glReadBuffer(readBuffer);
    glBindBuffer(GL_PIXEL_PACK_BUFFER, packBuffer);
    glPixelStorei(GL_PACK_ALIGNMENT, alignment);
    glPixelStorei(GL_PACK_ROW_LENGTH, rowLength);
    glPixelStorei(GL_PACK_SKIP_ROWS, skipRows);
    glPixelStorei(GL_PACK_SKIP_PIXELS, skipPixels);
  }
};
}

bool BehaviorLab::enabled() {
  return state().active;
}

Json const& BehaviorLab::configuration() {
  auto& lab = state();
  require(lab.active, "BehaviorLab: configuration requested while disabled");
  return lab.config;
}

void BehaviorLab::queueFrame(String const& name, Json metadata) {
  auto& lab = state();
  if (!lab.active)
    return;
  auto bytes = name.utf8();
  require(!bytes.empty() && bytes.size() <= 96, "BehaviorLab: invalid frame name length");
  for (unsigned char c : bytes)
    require((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
        (c >= '0' && c <= '9') || c == '-' || c == '_', "BehaviorLab: unsafe frame name");
  // Windows treats these basenames as devices even with a .png suffix.
  auto upper = bytes;
  for (char& c : upper)
    if (c >= 'a' && c <= 'z')
      c -= 'a' - 'A';
  require(upper != "CON" && upper != "PRN" && upper != "AUX" && upper != "NUL" &&
      !(upper.size() == 4 && (upper.substr(0, 3) == "COM" || upper.substr(0, 3) == "LPT") &&
          upper[3] >= '0' && upper[3] <= '9'), "BehaviorLab: reserved device frame name");
  require(metadata.type() == Json::Type::Object, "BehaviorLab: frame metadata must be an object");
  require(lab.pendingName.empty(), "BehaviorLab: overlapping capture requests");
  require(!lab.captured.count(name), "BehaviorLab: duplicate capture request");
  lab.validateOutput();
  for (auto suffix : {".png", ".json"})
    require(!fs::exists(fs::symlink_status(lab.output / (bytes + suffix))),
        "BehaviorLab: capture output already exists");
  lab.pendingMetadata = std::move(metadata);
  lab.pendingName = name;
}

bool BehaviorLab::frameCaptured(String const& name) {
  auto& lab = state();
  return lab.active && lab.captured.count(name) != 0;
}

bool BehaviorLab::hasPendingFrame() {
  auto& lab = state();
  return lab.active && !lab.pendingName.empty();
}

void BehaviorLab::captureFrame(Vec2U drawableSize) {
  auto& lab = state();
  if (!lab.active || lab.pendingName.empty())
    return;
  lab.validateOutput();
  require(drawableSize[0] && drawableSize[1] &&
      drawableSize[0] <= 32768 && drawableSize[1] <= 32768 &&
      uint64_t(drawableSize[0]) * drawableSize[1] * 4 <= 512 * 1024 * 1024,
      "BehaviorLab: invalid or excessive drawable dimensions");
  require(glGetError() == GL_NO_ERROR, "BehaviorLab: GL error before capture");
  Image image(drawableSize, PixelFormat::RGBA32);
  {
    ReadbackState restore;
    GLboolean doubleBuffered = GL_FALSE;
    glGetBooleanv(GL_DOUBLEBUFFER, &doubleBuffered);
    glReadBuffer(doubleBuffered ? GL_BACK : GL_FRONT);
    // Image's origin is lower-left, just like glReadPixels. writePng performs
    // the only row reversal; flipping here would produce an upside-down PNG.
    glReadPixels(0, 0, drawableSize[0], drawableSize[1], GL_RGBA, GL_UNSIGNED_BYTE, image.data());
    require(glGetError() == GL_NO_ERROR, "BehaviorLab: framebuffer readback failed");
  }
  require(glGetError() == GL_NO_ERROR, "BehaviorLab: GL state restoration failed");

  auto png = std::make_shared<Buffer>();
  image.writePng(png);
  auto filename = lab.pendingName.utf8() + ".png";
  auto glText = [](GLenum name) -> String {
    auto value = glGetString(name);
    require(value != nullptr, "BehaviorLab: missing GL device identity");
    return String(reinterpret_cast<char const*>(value));
  };
  // Caller metadata stays nested and unmodified, so capture keys cannot hide
  // scenario/backend assertions supplied by the client.
  Json receipt = JsonObject{
    {"name", lab.pendingName}, {"file", filename},
    {"width", drawableSize[0]}, {"height", drawableSize[1]},
    {"metadata", lab.pendingMetadata},
    {"capture", JsonObject{{"source", "final-default-framebuffer"},
        {"stage", "after-imgui-before-swap"}, {"pixelFormat", "RGBA8"},
        {"pngOrigin", "top-left"},
        {"gpu", JsonObject{{"vendor", glText(GL_VENDOR)},
            {"renderer", glText(GL_RENDERER)}, {"version", glText(GL_VERSION)}}}}}
  };
  auto json = receipt.printJson(2);
  writeExclusive(lab.output / filename, png->ptr(), png->data().size());
  writeExclusive(lab.output / (lab.pendingName.utf8() + ".json"), json.utf8Ptr(), json.utf8().size());
  // Acknowledgement is deliberately last, after both files have closed.
  lab.captured.insert(lab.pendingName);
  lab.pendingName = {};
  lab.pendingMetadata = {};
}

}
