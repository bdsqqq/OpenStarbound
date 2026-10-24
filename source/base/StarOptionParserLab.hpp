#pragma once

#include "StarFile.hpp"
#include "StarJson.hpp"
#include "StarOptionParser.hpp"
#ifdef STAR_USE_RUST_OPTION_PARSER
#include "StarRustOptionParser.h"
#endif
#include <cstdlib>
#include <filesystem>

namespace Star {

// Startup-only, main-thread observer. No writes, parser replay, or filesystem
// access without the existing behavior runner's explicit process opt-in.
inline bool optionParserLabEnabled() {
  auto environment = std::getenv("STAR_BEHAVIOR_LAB");
  if (!environment) return false;
  namespace fs = std::filesystem;
  auto path = fs::u8path(environment);
  if (!path.is_absolute() || !fs::is_regular_file(fs::symlink_status(path))
      || fs::file_size(path) > 1024 * 1024) return false;
  auto config = Json::parseJson(File::readFileString(String(path.u8string())));
  if (config.getString("scenario", "") != "option-parser-room") return false;
  auto output = fs::u8path(config.getString("outputDirectory").utf8());
  auto storage = fs::u8path(config.getString("storageDirectory").utf8());
  return output.is_absolute() && output == path.parent_path() / "frames"
      && storage == output / "storage"
      && fs::is_directory(fs::symlink_status(output))
      && fs::is_directory(fs::symlink_status(storage))
      && fs::is_regular_file(fs::symlink_status(output / ".star-behavior-lab"))
      && fs::is_regular_file(fs::symlink_status(storage / ".star-behavior-lab"));
}

inline Json& optionParserLabStartup() {
  static Json value;
  return value;
}

inline Json optionParserLabCounters() {
  JsonArray rows;
  for (unsigned mode = 0; mode != 8; ++mode) {
    JsonArray events;
    for (unsigned event = 0; event != 3; ++event) {
      uint64_t count = 0;
#ifdef STAR_USE_RUST_OPTION_PARSER
      count = star_option_parser_call_count(mode, event);
#endif
      events.append(count);
    }
    rows.append(events);
  }
  return rows;
}

inline void optionParserLabObserveParse(StringList const& arguments,
    OptionParser::Options const& options, StringList const& errors) {
  if (!optionParserLabEnabled()) return;
  // Observe only the runner's real, explicitly selected boot file. This does
  // not change parser acceptance or invent a command-line isolation flag.
  namespace fs = std::filesystem;
  auto configPath = fs::u8path(std::getenv("STAR_BEHAVIOR_LAB"));
  auto selected = options.parameters.value("bootconfig").maybeFirst();
  if (!selected || fs::u8path(selected->utf8()) != configPath.parent_path() / "sbinit.config") return;
  JsonArray args, switches, positional, errorRows;
  JsonObject parameters;
  for (auto const& x : arguments) args.append(x);
  for (auto const& x : options.switches) switches.append(x);
  for (auto const& x : options.arguments) positional.append(x);
  for (auto const& x : errors) errorRows.append(x);
  for (auto const& p : options.parameters) {
    JsonArray values;
    for (auto const& x : p.second) values.append(x);
    parameters[p.first] = values;
  }
  optionParserLabStartup() = JsonObject{{"nativeParseObservations", 1},
      {"arguments", args}, {"switches", switches}, {"parameters", parameters},
      {"positional", positional}, {"errors", errorRows},
      {"afterParseCounters", optionParserLabCounters()}};
}

}
