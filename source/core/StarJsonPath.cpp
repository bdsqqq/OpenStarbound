#include "StarJsonPath.hpp"

#ifdef STAR_USE_RUST_JSON_PATH
#include "StarRustJsonPath.h"
#include <exception>

namespace {
struct RustJsonPathHost {
  Star::String& buffer;
  Star::String::const_iterator& iterator;
  Star::String::const_iterator end;
  std::exception_ptr failure;
};

int32_t jsonPathHost(void* context, uint32_t op, uint32_t arg, uint32_t* out) noexcept {
  auto& host = *static_cast<RustJsonPathHost*>(context);
  try {
    switch (op) {
      case 0: host.buffer.clear(); break;
      case 1: *out = host.iterator == host.end; break;
      case 2: *out = *host.iterator; break;
      case 3: ++host.iterator; break;
      // Keep the exact postfix expression, including its exception ordering.
      case 4: host.buffer.append(*host.iterator++); break;
      case 5: host.buffer.append(static_cast<Star::String::Char>(arg)); break;
      case 6: *out = Star::maybeLexicalCast<size_t>(host.buffer).isValid(); break;
      case 7: *out = host.buffer == "-"; break;
      default: return 1;
    }
    return 0;
  } catch (...) {
    host.failure = std::current_exception();
    return 1;
  }
}

Star::JsonPath::TypeHint parseRustJsonPath(uint32_t kind, Star::String& buffer,
    Star::String const& path, Star::String::const_iterator& iterator,
    Star::String::const_iterator end) {
  RustJsonPathHost host{buffer, iterator, end, {}};
  uint32_t hint = 0;
  uint32_t error = 0;
  auto status = star_json_path_parse(kind, jsonPathHost, &host, &hint, &error);
  if (host.failure)
    std::rethrow_exception(host.failure);
  // Never retry: the buffer and iterator may already have changed.
  if (status != 0)
    throw Star::JsonPath::ParsingException("Rust Json path parser failed");
  using Star::JsonPath::ParsingException;
  switch (error) {
    case 1: throw ParsingException::format("Missing leading '/' in Json pointer \"{}\"", path);
    case 2: throw ParsingException::format("Incomplete escape sequence in Json pointer \"{}\"", path);
    case 3: throw ParsingException::format("Invalid escape sequence in Json pointer \"{}\"", path);
    case 4: throw ParsingException::format("Entry starts with '.' in query path \"{}\"", path);
    case 5: throw ParsingException::format("Array has no trailing ']' or has invalid character in query path \"{}\"", path);
  }
  return static_cast<Star::JsonPath::TypeHint>(hint);
}
}
#endif

namespace Star {

namespace JsonPath {

  TypeHint parsePointer(String& buffer, String const& path, String::const_iterator& iterator, String::const_iterator end) {
#ifdef STAR_USE_RUST_JSON_PATH
    return parseRustJsonPath(0, buffer, path, iterator, end);
#else
    buffer.clear();

    if (*iterator != '/')
      throw ParsingException::format("Missing leading '/' in Json pointer \"{}\"", path);
    iterator++;

    while (iterator != end && *iterator != '/') {
      if (*iterator == '~') {
        ++iterator;
        if (iterator == end)
          throw ParsingException::format("Incomplete escape sequence in Json pointer \"{}\"", path);

        if (*iterator == '0')
          buffer.append('~');
        else if (*iterator == '1')
          buffer.append('/');
        else
          throw ParsingException::format("Invalid escape sequence in Json pointer \"{}\"", path);
        ++iterator;
      } else
        buffer.append(*iterator++);
    }

    Maybe<size_t> index = maybeLexicalCast<size_t>(buffer);
    if (index.isValid() || (buffer == "-" && iterator == end))
      return TypeHint::Array;
    return TypeHint::Object;
#endif
  }

  TypeHint parseQueryPath(String& buffer, String const& path, String::const_iterator& iterator, String::const_iterator end) {
#ifdef STAR_USE_RUST_JSON_PATH
    return parseRustJsonPath(1, buffer, path, iterator, end);
#else
    buffer.clear();

    if (*iterator == '.') {
      throw ParsingException::format("Entry starts with '.' in query path \"{}\"", path);

    } else if (*iterator == '[') {
      // Parse array number and ']'
      // Consume initial '['
      ++iterator;

      while (iterator != end && *iterator >= '0' && *iterator <= '9')
        buffer.append(*iterator++);

      if (iterator == end || *iterator != ']')
        throw ParsingException::format("Array has no trailing ']' or has invalid character in query path \"{}\"", path);

      // Consume trailing ']'
      ++iterator;

      // Consume trailing '.'
      if (iterator != end && *iterator == '.')
        ++iterator;

      return TypeHint::Array;

    } else {
      // Parse path up to next '.' or '['
      while (iterator != end && *iterator != '.' && *iterator != '[')
        buffer.append(*iterator++);

      // Consume single trailing '.' if it exists
      if (iterator != end && *iterator == '.')
        ++iterator;
      return TypeHint::Object;
    }
#endif
  }
}

}
