#pragma once

// Fixture support ONLY: not production StarMap, StarString or StarException.
#include <functional>
#include <initializer_list>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#ifdef STAR_DEBUG
#error "this fixture characterizes assertion-off BiMap only"
#endif
// Matches the production non-STAR_DEBUG macro: COND is not evaluated.
#define starAssert(COND)

namespace Star {
using std::pair;
using std::make_pair;
using std::initializer_list;
using String = std::string;
using std::size_t;
template <typename T> using hash = std::hash<T>;
template <typename T> class Maybe; // Deliberately incomplete; wrappers are excluded.
template <typename T> struct List : std::vector<T> {
  using std::vector<T>::vector;
  template <typename U> void append(U const& value) { this->push_back(value); }
};
// Parsing-only defaults. Actual fixture instantiations supply TraceMap explicitly.
template <typename K, typename V> using Map = std::map<K, V>;
template <typename K, typename V, typename H = hash<K>, typename C = std::equal_to<K>>
using StableHashMap = std::map<K, V>;
struct CaseInsensitiveStringHash;
struct CaseInsensitiveStringCompare;

template <typename T> String outputAny(T const& value) {
  std::ostringstream out;
  out << value;
  return out.str();
}
// Only sequential, plain {} substitutions used with fixture integers/strings.
template <typename... Args> String strf(String text, Args const&... args) {
  std::vector<String> values{outputAny(args)...};
  size_t offset = 0;
  for (auto const& value : values) {
    auto pos = text.find("{}", offset);
    if (pos == String::npos) break;
    text.replace(pos, 2, value);
    offset = pos + value.size();
  }
  return text;
}
class MapException : public std::runtime_error {
public:
  using std::runtime_error::runtime_error;
  template <typename... Args> static MapException format(String text, Args const&... args) {
    return MapException(strf(text, args...));
  }
};
}
