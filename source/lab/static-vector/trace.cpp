// Source-first generic event characterization; no StarJson/StarList includes.
#include <cstddef>
#include <functional>
#include <initializer_list>
#include <iostream>
#include <iterator>
#include <new>
#include <set>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>
#ifndef STATIC_VECTOR_TEST_HEADER
#define STATIC_VECTOR_TEST_HEADER "StarStaticVector.original.hpp"
#endif
#include STATIC_VECTOR_TEST_HEADER

namespace {
struct TraceFailure : std::runtime_error {
  using std::runtime_error::runtime_error;
};
struct Recorder {
  bool enabled = false;
  std::function<size_t()> ownerSize;
  std::vector<std::string> events;
  int copyCalls = 0, compareCalls = 0;
  int throwCopyAt = 0, throwCompareAt = 0;

  void log(std::string const& operation) {
    if (enabled)
      events.push_back(operation + ":size=" + std::to_string(ownerSize()));
  }
  void comparison() {
    if (++compareCalls == throwCompareAt) {
      log("throw:comparison #2");
      throw TraceFailure("comparison #2");
    }
  }
  void stop() {
    enabled = false;
    throwCopyAt = throwCompareAt = 0;
    ownerSize = {};
  }
} recorder;

struct TrackedElement {
  int value;
  TrackedElement() : value(0) { recorder.log("default:0"); }
  explicit TrackedElement(int n) : value(n) { recorder.log("ctor:" + std::to_string(n)); }
  TrackedElement(TrackedElement const& other) : value(other.value) {
    recorder.log("copy.ctor:" + std::to_string(value));
  }
  TrackedElement(TrackedElement&& other) : value(other.value) {
    recorder.log("move.ctor:" + std::to_string(value));
    other.value = -1;
  }
  TrackedElement& operator=(TrackedElement const& other) {
    recorder.log("copy.assign:" + std::to_string(value) + "<-" + std::to_string(other.value));
    if (++recorder.copyCalls == recorder.throwCopyAt) {
      recorder.log("throw:copy assignment #2");
      throw TraceFailure("copy assignment #2");
    }
    value = other.value;
    return *this;
  }
  TrackedElement& operator=(TrackedElement&& other) {
    recorder.log("move.assign:" + std::to_string(value) + "<-" + std::to_string(other.value));
    if (this == &other) value = -777;
    else { value = other.value; other.value = -1; }
    return *this;
  }
  // No injected destructor/constructor throws: every vector slot stays live.
  ~TrackedElement() noexcept { recorder.log("dtor:" + std::to_string(value)); }
  bool operator==(TrackedElement const&) const = delete;
  bool operator!=(TrackedElement const& other) const {
    recorder.log("ne:" + std::to_string(value) + "," + std::to_string(other.value));
    recorder.comparison();
    return value != other.value;
  }
  bool operator<(TrackedElement const& other) const {
    recorder.log("lt:" + std::to_string(value) + "," + std::to_string(other.value));
    recorder.comparison();
    return value < other.value;
  }
};
using V = Star::StaticVector<TrackedElement, 4>;

void seed(V& v, std::initializer_list<int> values) {
  for (int n : values) v.emplace_back(n);
}
void observe(V const& initializedOwner) {
  recorder.events.clear();
  recorder.copyCalls = recorder.compareCalls = 0;
  recorder.throwCopyAt = recorder.throwCompareAt = 0;
  // Published only after default construction/seed. The move constructor case
  // observes its EXISTING source, never the not-yet-constructed destination.
  recorder.ownerSize = [&initializedOwner] { return initializedOwner.size(); };
  recorder.enabled = true;
}
std::vector<int> snapshot(V const& v) {
  std::vector<int> result;
  for (auto const& e : v) result.push_back(e.value);
  return result;
}
void json(std::string const& s) {
  std::cout << '"';
  for (unsigned char c : s) {
    if (c == '"' || c == '\\') std::cout << '\\' << char(c);
    else if (c < 32) {
      static char const* digits = "0123456789abcdef";
      std::cout << "\\u00" << digits[c >> 4] << digits[c & 15];
    } else std::cout << char(c);
  }
  std::cout << '"';
}
void json(int n) { std::cout << n; }
void json(bool b) { std::cout << (b ? "true" : "false"); }
template <class T> void json(std::vector<T> const& values) {
  std::cout << '[';
  bool first = true;
  for (auto const& v : values) { if (!first) std::cout << ','; first = false; json(v); }
  std::cout << ']';
}
std::set<std::string> names;
void emit(std::string const& name, V const& state, std::vector<int> const& source = {},
          bool result = false, std::vector<std::string> const& error = {}) {
  // Stop before serialization and automatic vector/argument destruction.
  recorder.stop();
  if (!names.insert(name).second) throw std::logic_error("duplicate case: " + name);
  if (names.size() != 1) std::cout << ',';
  std::cout << "{\"name\":"; json(name);
  std::cout << ",\"value\":{\"events\":"; json(recorder.events);
  std::cout << ",\"state\":"; json(snapshot(state));
  std::cout << ",\"source\":"; json(source);
  std::cout << ",\"result\":"; json(result);
  std::cout << ",\"error\":"; json(error);
  std::cout << "}}";
}
// Catch only the deliberately injected marker, not arbitrary native errors.
template <class F> std::vector<std::string> failure(F action) {
  try { action(); }
  catch (TraceFailure const& e) { return {"TraceFailure", e.what()}; }
  return {};
}
}

int main() {
  std::cout << "{\"schema\":1,\"cases\":[";
  { V v; observe(v); v.emplace_back(7); emit("emplace.back.publish", v); }
  { V v; seed(v, {1, 2}); observe(v); v.pop_back(); emit("pop.publish", v); }
  {
    V v; TrackedElement argument(5); observe(v);
    // Named lvalue forces the outer parameter copy regardless of optional NRVO.
    v.push_back(argument);
    emit("push.named", v, {argument.value});
  }
  { V v; seed(v, {1, 2}); observe(v); v.resize(2); emit("resize.same", v); }
  { V v; seed(v, {8}); observe(v); v.resize(3); emit("resize.grow", v); }
  { V v; seed(v, {1, 2, 3}); observe(v); v.clear(); emit("clear.reverse", v); }
  { V v; seed(v, {1, 2}); observe(v); v.emplace(v.begin() + 1, 9); emit("emplace.middle", v); }
  {
    V v; seed(v, {1, 2, 3});
    TrackedElement input(8); observe(v);
    auto returned = v.insert(v.begin() + 1, &input, &input);
    emit("insert.empty", v, {}, returned == v.begin() + 1);
  }
  {
    V source; seed(source, {1, 2}); observe(source);
    V target(std::move(source));
    emit("move.construct", target, snapshot(source));
  }
  {
    V source, target; seed(source, {1, 2}); seed(target, {8}); observe(target);
    auto& returned = (target = std::move(source));
    emit("move.assign", target, snapshot(source), &returned == &target);
  }
  {
    V v; seed(v, {1, 2}); observe(v); auto& alias = v;
    auto& returned = (v = std::move(alias));
    emit("move.self", v, {}, &returned == &v);
  }
  {
    V source, target; seed(source, {1, 2, 3}); seed(target, {9, 8, 7}); observe(target);
    recorder.throwCopyAt = 2;
    auto error = failure([&] { target = source; });
    recorder.throwCopyAt = 0;
    emit("copy.assign.throw", target, snapshot(source), false, error);
  }
  {
    V a, b; seed(a, {1, 2}); seed(b, {1, 2}); observe(a);
    bool result = a == b; emit("compare.equal", a, snapshot(b), result);
  }
  {
    V a; seed(a, {1, 2}); observe(a);
    bool result = a == a; emit("compare.self", a, {}, result);
  }
  {
    V a, b; seed(a, {1, 2}); seed(b, {1, 3}); observe(a);
    bool result = a < b; emit("order.less", a, snapshot(b), result);
  }
  {
    V a, b; seed(a, {1, 3}); seed(b, {1, 2}); observe(a);
    bool result = a < b; emit("order.greater", a, snapshot(b), result);
  }
  {
    V a, b; seed(a, {1, 2}); seed(b, {1, 3}); observe(a); recorder.throwCompareAt = 2;
    auto error = failure([&] { (void)(a == b); }); recorder.throwCompareAt = 0;
    emit("compare.throw", a, snapshot(b), false, error);
  }
  {
    V a, b; seed(a, {2, 9}); seed(b, {1, 8}); observe(a); recorder.throwCompareAt = 2;
    auto error = failure([&] { (void)(a < b); }); recorder.throwCompareAt = 0;
    emit("order.throw", a, snapshot(b), false, error);
  }
  std::cout << "]}\n";
}
