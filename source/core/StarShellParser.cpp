#include "StarShellParser.hpp"

#ifdef STAR_USE_RUST_SHELL
#include "StarRustShell.h"
#include <cctype>
#include <exception>
#include <vector>

namespace {
struct RustShellCollector {
  Star::List<Star::ShellParser::Token>* tokens;
  Star::String word;
  std::exception_ptr failure;
};

int32_t shellClassify(void* context, uint32_t cp, uint32_t* isHex) noexcept {
  auto& collector = *static_cast<RustShellCollector*>(context);
  try {
    // Keep the historical locale and int conversion, only for requested digits.
    *isHex = std::isxdigit(static_cast<int>(cp)) ? 1 : 0;
    return 0;
  } catch (...) {
    collector.failure = std::current_exception();
    return 1;
  }
}

int32_t shellEmit(void* context, uint32_t event, uint32_t cp) noexcept {
  auto& collector = *static_cast<RustShellCollector*>(context);
  try {
    if (event == 0) {
      collector.word.append(static_cast<Star::String::Char>(cp));
    } else {
      collector.tokens->append(Star::ShellParser::Token{
          Star::ShellParser::TokenType::Word, std::move(collector.word)});
      collector.word = Star::String();
    }
    return 0;
  } catch (...) {
    collector.failure = std::current_exception();
    return 1;
  }
}
}
#endif

namespace Star {

ShellParser::ShellParser()
  : m_current(), m_end(), m_quotedType('\0') {}

auto ShellParser::tokenize(String const& command) -> List<Token> {
  List<Token> res;

  init(command);

#ifdef STAR_USE_RUST_SHELL
  // Use the same String iterator as the C++ parser, including embedded NUL and
  // its malformed-UTF8 policy. This staging changes allocation-failure timing.
  std::vector<uint32_t> input;
  for (auto current = command.begin(), end = command.end(); current != end; ++current)
    input.push_back(static_cast<uint32_t>(*current));
  RustShellCollector collector{&res, String(), {}};
  size_t count;
  uint32_t quote;
  auto status = star_shell_tokenize(input.data(), input.size(), shellClassify,
      shellEmit, &collector, &count, &quote);
  if (collector.failure)
    std::rethrow_exception(collector.failure);
  // An executing backend is never retried: it may already have emitted words.
  if (status != 0)
    throw ShellParsingException("Rust shell parser failed");
  m_quotedType = static_cast<Char>(quote);
  m_current = m_end;
#else
  while (notDone()) {
    res.append(Token{TokenType::Word, word()});
  }
#endif

  return res;
}

StringList ShellParser::tokenizeToStringList(String const& command) {
  StringList res;
  for (auto token : tokenize(command)) {
    if (token.type == TokenType::Word) {
      res.append(std::move(token.token));
    }
  }

  return res;
}

void ShellParser::init(String const& string) {
  m_begin = string.begin();
  m_current = m_begin;
  m_end = string.end();
  m_quotedType = '\0';
}

String ShellParser::word() {
  String res;

  while (notDone()) {
    auto letter = *current();
    bool escapedLetter = false;

    if (letter == '\\') {
      escapedLetter = true;
      letter = parseBackslash();
    }

    if (!escapedLetter) {
      if (isSpace(letter) && !inQuotedString()) {
        next();
        if (res.size()) {
          return res;
        }
        continue;
      }

      if (isQuote(letter)) {
        if (inQuotedString() && letter == m_quotedType) {
          m_quotedType = '\0';
          next();
          continue;
        }

        if (!inQuotedString()) {
          m_quotedType = letter;
          next();
          continue;
        }
      }
    }

    res.append(letter);
    next();
  }

  return res;
}

bool ShellParser::isSpace(Char letter) const {
  return String::isSpace(letter);
}

bool ShellParser::isQuote(Char letter) const {
  return letter == '\'' || letter == '"';
}

bool ShellParser::inQuotedString() const {
  return m_quotedType != '\0';
}

auto ShellParser::current() const -> Maybe<Char> {
  if (m_current == m_end) {
    return {};
  }

  return *m_current;
}

auto ShellParser::next() -> Maybe<Char> {
  if (m_current != m_end) {
    ++m_current;
  }

  return current();
}

auto ShellParser::previous() -> Maybe<Char> {
  if (m_current != m_begin) {
    --m_current;
  }

  return current();
}

auto ShellParser::parseBackslash() -> Char {
  auto letter = next();

  if (!letter) {
    return '\\';
  }

  switch (*letter) {
    case ' ':
      return ' ';
    case 'n':
      return '\n';
    case 't':
      return '\t';
    case 'r':
      return '\r';
    case 'b':
      return '\b';
    case 'v':
      return '\v';
    case 'f':
      return '\f';
    case 'a':
      return '\a';
    case '\'':
      return '\'';
    case '"':
      return '"';
    case '\\':
      return '\\';
    case '0':
      return '\0';
    case 'u': {
      auto letter = parseUnicodeEscapeSequence();
      if (isUtf16LeadSurrogate(letter)) {
        auto shouldBeSlash = next();
        if (shouldBeSlash && shouldBeSlash == '\\') {
          auto shouldBeU = next();
          if (shouldBeU && shouldBeU == 'u') {
            return parseUnicodeEscapeSequence(letter);
          } else {
            previous();
          }
        }
        previous();
        return STAR_UTF32_REPLACEMENT_CHAR;
      } else {
        return letter;
      }
    }
    default:
      return *letter;
  }
}

auto ShellParser::parseUnicodeEscapeSequence(Maybe<Char> previousCodepoint) -> Char {
  String codepoint;

  auto letter = current();

  while (!isSpace(*letter) && codepoint.size() < 4) {
    auto letter = next();
    if (!letter) {
      break;
    }

    if (!isxdigit(*letter)) {
      return STAR_UTF32_REPLACEMENT_CHAR;
    }

    codepoint.append(*letter);
  }

  if (!codepoint.size()) {
    return 'u';
  }

  if (codepoint.size() != 4) // exactly 4 digits are required by \u
    return STAR_UTF32_REPLACEMENT_CHAR;

  try {
    return hexStringToUtf32(codepoint.utf8(), previousCodepoint);
  } catch (UnicodeException const&) {
    return STAR_UTF32_REPLACEMENT_CHAR;
  }
}

bool ShellParser::notDone() const {
  return m_current != m_end;
}

}
