// Source-only supplemental probe: real public API, no private layout or class mirror.
#include "StarByteArray.hpp"
#include <climits>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

using Star::ByteArray;
static_assert(sizeof(size_t) == 8 && CHAR_MIN == -128, "frozen platform profile");

namespace {
struct ThrowToken {};
struct Context {
  std::string name;
  ByteArray* small;
  ByteArray* large;
  ByteArray* owner;
  std::unique_ptr<ByteArray>* destroy;
  ThrowToken token;
  int calls = 0;
  std::vector<std::string> events;
  std::string nested = "null";
};

std::string bytes(ByteArray const& b, size_t count) {
  std::string s = "[";
  for (size_t i = 0; i < count; ++i) {
    if (i) s += ',';
    s += std::to_string(static_cast<unsigned char>(b[i]));
  }
  return s + ']';
}
std::string receipt(ByteArray const& b, size_t known) {
  return "{\"size\":" + std::to_string(b.size()) + ",\"capacity\":" +
      std::to_string(b.capacity()) + ",\"prefix\":" + bytes(b, known) + '}';
}
std::unique_ptr<ByteArray> seeded(size_t n, char base) {
  auto b = std::make_unique<ByteArray>(64, base);
  for (size_t i = 0; i < 64; ++i) (*b)[i] = char(base + i % 8);
  b->resize(n);
  return b;
}
void event(Context& c, std::string const& kind, int i) {
  c.events.push_back(kind + ":" + std::to_string(i));
}
void convertEffects(Context& c, int i) {
  if (i != 1) return;
  if (c.name == "proxy_convert_shrink") c.small->resize(1);
  if (c.name == "throw_convert") {
    (*c.large)[0] = 79;
    throw &c.token;
  }
}
int invoke(Context& c, char a, char b) {
  int i = ++c.calls;
  c.events.push_back("call:" + std::to_string(i) + ":" +
      std::to_string(static_cast<unsigned char>(a)) + ":" +
      std::to_string(static_cast<unsigned char>(b)));
  if (i == 1) {
    if (c.name == "shrink_noextend" || c.name == "shrink_extend") c.small->resize(1);
    if (c.name == "grow_large") c.large->resize(7, 77);
    if (c.name == "shrink_large") c.large->resize(3);
    if (c.name == "flip_roles") { c.small->resize(1); c.large->resize(0); }
    if (c.name == "throw_callback") { (*c.small)[0] = 78; throw &c.token; }
    if (c.name == "reenter") {
      event(c, "nested_begin", i);
      // Same owner, fresh automatic callback/context. No owner-wide guard.
      auto nested = c.owner->combineWith([&c](char x, char y) {
        c.events.push_back("nested:" + std::to_string(int(x)) + ":" + std::to_string(int(y)));
        return char(x + y);
      }, *c.large, false);
      c.nested = receipt(nested, nested.size());
      event(c, "nested_end", i);
    }
  }
  if (i == 2 && c.destroy) {
    event(c, "delete_large", i);
    c.destroy->reset();
    // Both arguments were copied before invocation; never touch large/owner again.
  }
  return 2 * int(a) + int(b);
}
struct Direct {
  Context& c;
  explicit Direct(Context& c) : c(c) {}
  Direct(Direct const&) = delete;
  Direct(Direct&&) = delete;
  char operator()(char a, char b) & { return char(invoke(c, a, b)); }
  char operator()(char, char) && = delete;
};
struct Proxy {
  Context& c;
  int i;
  char value;
  Proxy(Context& c, int i, char value) : c(c), i(i), value(value) {}
  Proxy(Proxy const&) = delete;
  Proxy(Proxy&&) = delete;
  operator char() {
    event(c, "convert", i);
    convertEffects(c, i);
    return value;
  }
  ~Proxy() {
    event(c, "dtor", i);
    if (c.name == "proxy_dtor_grow" && i == 1) c.large->resize(7, 77);
  }
};
struct Proxied {
  Context& c;
  Proxy operator()(char a, char b) & {
    char v = char(invoke(c, a, b));
    return Proxy(c, c.calls, v); // C++17 guaranteed elision; no proxy move/copy.
  }
};

void run(std::string const& name) {
  size_t ln = 3, rn = 5;
  bool extend = true;
  if (name == "tie_rhs") rn = 3;
  if (name == "grow_large" || name == "shrink_large" || name == "delete_rhs_large") ln = 2;
  if (name == "delete_this_large") { ln = 5; rn = 2; }
  if (name == "shrink_noextend" || name == "delete_rhs_large" || name == "delete_this_large") extend = false;
  auto lhs = seeded(ln, 10), rhs = seeded(rn, 40);
  Context c{name, ln < rn ? lhs.get() : rhs.get(), ln < rn ? rhs.get() : lhs.get(), lhs.get(), nullptr};
  if (name == "delete_rhs_large") c.destroy = &rhs;
  if (name == "delete_this_large") c.destroy = &lhs;
  std::string status = "ok", result = "null";
  try {
    auto res = [&]() -> ByteArray {
      if (name == "proxy_convert_shrink" || name == "proxy_dtor_grow" || name == "throw_convert")
        return lhs->combineWith(Proxied{c}, *rhs, extend);
      // CALLBACK_GROW_LARGE_NATIVE_ANCHOR: replace only this complete return for a free-function control.
      return lhs->combineWith(Direct{c}, *rhs, extend);
    }();
    // Shrink + !extend keeps an uninitialized suffix. Never serialize that suffix.
    result = receipt(res, name == "shrink_noextend" ? 1 : res.size());
  } catch (ThrowToken* p) {
    status = p == &c.token ? "throw_same" : "throw_other";
  }
  std::cout << "{\"case\":\"" << name << "\",\"status\":\"" << status
            << "\",\"result\":" << result << ",\"lhs\":"
            << (lhs ? receipt(*lhs, lhs->size()) : "null") << ",\"rhs\":"
            << (rhs ? receipt(*rhs, rhs->size()) : "null") << ",\"nested\":" << c.nested
            << ",\"events\":[";
  for (size_t i = 0; i < c.events.size(); ++i) {
    if (i) std::cout << ',';
    std::cout << '"' << c.events[i] << '"';
  }
  std::cout << "]}\n";
}
}
int main(int argc, char**) {
  if (argc != 1) return 2;
  for (auto name : {"tie_rhs", "lhs_small", "shrink_noextend", "shrink_extend",
      "grow_large", "shrink_large", "flip_roles", "proxy_convert_shrink",
      "proxy_dtor_grow", "throw_callback", "throw_convert", "reenter",
      "delete_rhs_large", "delete_this_large"}) run(name);
  return 0;
}
