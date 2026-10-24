#include "StarText.hpp"
#include "StarJsonExtra.hpp"
#include <re2/re2.h>
#ifdef STAR_USE_RUST_TEXT_SCAN
#include "StarRustTextScan.h"
#include <exception>
#include <stdexcept>
#endif

namespace Star {

TextStyle::TextStyle(Json const& config) : TextStyle() {
  if (config.isType(Json::Type::String))
    font = config.toString();
  else
    loadJson(config);
}
TextStyle& TextStyle::loadJson(Json const& config) {
  if (!config)
    return *this;

  lineSpacing = config.getFloat("lineSpacing", lineSpacing);
  if (auto jColor = config.opt("color"))
    color = jsonToColor(*jColor).toRgba();
  if (auto jShadow = config.opt("shadow"))
    shadow = jsonToColor(*jShadow).toRgba();
  fontSize = config.getUInt("fontSize", fontSize);
  if (auto jFont = config.optString("font"))
    font = *jFont;
  if (auto jDirectives = config.optString("directives"))
    directives = *jDirectives;
  if (auto jBackDirectives = config.optString("backDirectives"))
    backDirectives = *jBackDirectives;
  
  return *this;
}

namespace Text {
  std::string const AllEsc = strf("{:c}{:c}", CmdEsc, StartEsc);
  std::string const AllEscEnd = strf("{:c}{:c}{:c}", CmdEsc, StartEsc, EndEsc);

  static RE2 stripEscapeRegex = strf("\\{:c}[^;{:c}]*{:c}", CmdEsc, CmdEsc, EndEsc);
  String stripEscapeCodes(String const& s) {
    if (s.empty())
      return s;
    std::string result = s.utf8();
    RE2::GlobalReplace(&result, stripEscapeRegex, "");
    return String(std::move(result));
  }

#ifdef STAR_USE_RUST_TEXT_SCAN
  namespace {
    struct TextScanContext {
      std::string_view bytes;
      TextCallback& text;
      CommandsCallback& commands;
      std::exception_ptr pending;
    };
    uint32_t textScanHost(void* opaque, uint32_t kind, uint64_t offset, uint64_t length) noexcept {
      if (!opaque)
        return 3;
      auto& context = *static_cast<TextScanContext*>(opaque);
      if (context.pending || kind > 1 || offset > context.bytes.size() || length > context.bytes.size() - offset)
        return 3;
      try {
        // Construct the same native StringView from the current span, without
        // copying callbacks or bytes. Empty text callbacks throw only here.
        auto span = context.bytes.substr(static_cast<size_t>(offset), static_cast<size_t>(length));
        return (kind == 0 ? context.text(span) : context.commands(span)) ? 0 : 1;
      } catch (...) {
        context.pending = std::current_exception();
        return 2;
      }
    }
  }

  bool processText(StringView text, TextCallback textFunc, CommandsCallback commandsFunc, bool includeCommandSides) {
    TextScanContext context{text.utf8(), textFunc, commandsFunc, {}};
    uint8_t result = 0;
    auto status = star_text_scan_process(reinterpret_cast<uint8_t const*>(context.bytes.data()),
        context.bytes.size(), commandsFunc ? 1 : 0, includeCommandSides ? 1 : 0,
        textScanHost, &context, &result);
    if (status == 1 && context.pending)
      std::rethrow_exception(context.pending);
    if (status != 0 || context.pending)
      throw std::runtime_error("Rust text scanner protocol failure");
    return result != 0;
  }
#else
  bool processText(StringView text, TextCallback textFunc, CommandsCallback commandsFunc, bool includeCommandSides) {
    std::string_view str = text.utf8();
    size_t start = 0;
    while (true) {
      size_t escape = str.find_first_of(AllEsc, start);
      start = 0;
      if (escape != NPos) {
        escape = str.find_first_not_of(AllEsc, escape) - 1; // jump to the last ^
        size_t end = str.find_first_of(AllEscEnd, escape + 1);
        if (end != NPos) {
          if (str.at(end) != EndEsc) {
            start = end;
            continue;
          }
          if (escape && !textFunc(str.substr(0, escape)))
            return false;
          if (commandsFunc) {
            StringView commands = includeCommandSides
              ? str.substr(escape, end - escape + 1)
              : str.substr(escape + 1, end - escape - 1);
            if (!commands.empty() && !commandsFunc(commands))
              return false;
          }
          str = str.substr(end + 1);
          continue;
        }
      }

      if (!str.empty())
        return textFunc(str);

      return true;
    }
  }
#endif
}

}