// Independent supplement: no inclusion/renaming of the earlier trace main.
#include <cstddef>
#include <cstdint>
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
struct SupplementFailure : std::runtime_error {
  using std::runtime_error::runtime_error;
};
struct Recorder {
  bool enabled = false;
  std::function<size_t()> ownerSize;
  std::function<void(std::string const&, size_t)> hook;
  std::vector<std::string> events;
  int copyCalls = 0, throwCopyAt = 0;
  bool throwDtorOnce = false;

  void log(std::string operation) {
    if (!enabled) return;
    // Freeze pre-operation operands AND entry size before any nested action.
    // The hook runs before append: nested events precede the frozen outer event.
    size_t observed = ownerSize();
    auto action = hook; // self-disarming must not destroy the executing closure
    if (action) action(operation, observed);
    events.push_back(operation + ":size=" + std::to_string(observed));
  }
  void stop() {
    enabled = false;
    hook = {};
    ownerSize = {};
    throwCopyAt = 0;
    throwDtorOnce = false;
  }
} recorder;

struct ProbeElement {
  int value;
  ProbeElement() : value(0) { recorder.log("default:0"); }
  explicit ProbeElement(int n) : value(n) { recorder.log("ctor:" + std::to_string(n)); }
  ProbeElement(ProbeElement const& other) : value(other.value) {
    recorder.log("copy.ctor:" + std::to_string(value));
  }
  ProbeElement(ProbeElement&& other) : value(other.value) {
    recorder.log("move.ctor:" + std::to_string(value));
    other.value = -1;
  }
  ProbeElement& operator=(ProbeElement const& other) {
    recorder.log("copy.assign:" + std::to_string(value) + "<-" + std::to_string(other.value));
    if (++recorder.copyCalls == recorder.throwCopyAt) {
      recorder.log("throw:copy assignment #2");
      throw SupplementFailure("copy assignment #2");
    }
    value = other.value;
    return *this;
  }
  ProbeElement& operator=(ProbeElement&& other) {
    recorder.log("move.assign:" + std::to_string(value) + "<-" + std::to_string(other.value));
    if (this == &other) value = -777;
    else { value = other.value; other.value = -1; }
    return *this;
  }
  ~ProbeElement() noexcept(false) {
    recorder.log("dtor:" + std::to_string(value));
    if (recorder.throwDtorOnce) {
      recorder.throwDtorOnce = false;
      recorder.log("throw:destructor once");
      throw SupplementFailure("destructor once");
    }
  }
  bool operator==(ProbeElement const&) const = delete;
  bool operator!=(ProbeElement const& other) const {
    recorder.log("ne:" + std::to_string(value) + "," + std::to_string(other.value));
    return value != other.value;
  }
  bool operator<(ProbeElement const& other) const {
    recorder.log("lt:" + std::to_string(value) + "," + std::to_string(other.value));
    return value < other.value;
  }
};
using V = Star::StaticVector<ProbeElement, 4>;
struct alignas(64) AlignedElement : ProbeElement {
  using ProbeElement::ProbeElement;
};
using AlignedV = Star::StaticVector<AlignedElement, 2>;

template <class Vector> void seed(Vector& v, std::initializer_list<int> values) {
  for (int n : values) v.emplace_back(n);
}
template <class Vector> void observe(Vector const& existingOwner) {
  recorder.stop();
  recorder.events.clear();
  recorder.copyCalls = 0;
  recorder.ownerSize = [&existingOwner] { return existingOwner.size(); };
  recorder.enabled = true;
}
template <class Vector> std::vector<int> snapshot(Vector const& v) {
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
void emit(std::string const& name, std::vector<int> const& state,
          std::vector<int> const& source = {}, bool result = false,
          std::vector<std::string> const& error = {}) {
  recorder.stop(); // no hook or throw flag survives into automatic teardown
  if (!names.insert(name).second) throw std::logic_error("duplicate case: " + name);
  if (names.size() != 1) std::cout << ',';
  std::cout << "{\"name\":"; json(name);
  std::cout << ",\"value\":{\"events\":"; json(recorder.events);
  std::cout << ",\"state\":"; json(state);
  std::cout << ",\"source\":"; json(source);
  std::cout << ",\"result\":"; json(result);
  std::cout << ",\"error\":"; json(error);
  std::cout << "}}";
}
template <class F> std::vector<std::string> failure(F action) {
  try { action(); }
  catch (SupplementFailure const& e) { return {"SupplementFailure", e.what()}; }
  return {};
}
}

int main() {
  std::cout << "{\"schema\":1,\"cases\":[";
  {
    V source, target; seed(source, {1, 2}); seed(target, {9, 8}); observe(target);
    recorder.hook = [&](std::string const& op, size_t) {
      if (op.compare(0, 12, "copy.assign:") != 0) return;
      recorder.hook = {};
      target.emplace_back(9);
      source.emplace_back(8);
    };
    auto& returned = (target = source);
    emit("reentry.copy.assign", snapshot(target), snapshot(source), &returned == &target);
  }
  {
    V v; observe(v);
    recorder.hook = [&](std::string const& op, size_t size) {
      if (op != "copy.ctor:0" || size != 1) return;
      recorder.hook = {};
      // The outer element's value has initialized; index 1 is a NEW slot.
      v.emplace_back(9);
    };
    v.resize(2);
    emit("reentry.resize.grow", snapshot(v));
  }
  {
    V v; seed(v, {1, 2, 3}); observe(v);
    recorder.hook = [&](std::string const& op, size_t size) {
      if (op != "dtor:3" || size != 2) return;
      recorder.hook = {};
      v.pop_back(); // destroys live 2, never the outer destructor's element
    };
    v.resize(1);
    emit("reentry.resize.shrink", snapshot(v));
  }
  {
    V v; seed(v, {1, 2, 3}); observe(v);
    recorder.hook = [&](std::string const& op, size_t size) {
      if (op != "dtor:3" || size != 2) return;
      recorder.hook = {};
      v.pop_back();
    };
    std::vector<std::string> error;
    // Only the cached-count mutant adds an empty pop; that error is defined.
    try { v.clear(); }
    catch (Star::OutOfRangeException const& e) {
      error = {"OutOfRangeException", e.what()};
    }
    emit("reentry.clear", snapshot(v), {}, false, error);
  }
  {
    V source; seed(source, {1, 2}); observe(source);
    V target(source);
    emit("ctor.copy.same", snapshot(target), snapshot(source));
  }
  {
    V source; seed(source, {1, 2}); observe(source);
    Star::StaticVector<ProbeElement, 3> target(source);
    emit("ctor.copy.capacity", snapshot(target), snapshot(source));
  }
  {
    V source; seed(source, {1, 2}); observe(source);
    V target(source.begin(), source.end());
    emit("ctor.range", snapshot(target), snapshot(source));
  }
  {
    V observer; ProbeElement argument(7); observe(observer);
    V target(2, argument);
    emit("ctor.fill.explicit", snapshot(target), {argument.value});
  }
  {
    V observer; observe(observer);
    V target{ProbeElement(1), ProbeElement(2)};
    emit("ctor.list.full.expression", snapshot(target));
  }
  {
    V source; seed(source, {1, 2}); observe(source); recorder.throwCopyAt = 2;
    auto error = failure([&] { V target(source); });
    recorder.throwCopyAt = 0;
    emit("ctor.copy.unwind", {}, snapshot(source), false, error);
  }
  {
    V v; seed(v, {1, 2, 3}); observe(v);
    auto returned = v.erase(v.begin() + 1);
    emit("erase.single.middle", snapshot(v), {}, returned == v.begin() + 1);
  }
  {
    V v; seed(v, {1, 2, 3, 4}); observe(v);
    auto returned = v.erase(v.begin() + 1, v.begin() + 3);
    emit("erase.range.middle", snapshot(v), {}, returned == v.begin() + 1);
  }
  {
    V v; seed(v, {1, 2, 3}); observe(v);
    auto returned = v.erase(v.begin() + 1, v.begin() + 1);
    emit("erase.range.empty", snapshot(v), {}, returned == v.begin() + 1);
  }
  {
    V v; seed(v, {1, 2, 3}); observe(v);
    v.emplace(v.begin() + 1, v[2]);
    emit("alias.emplace.reference", snapshot(v));
  }
  {
    V v; seed(v, {1, 2, 3}); observe(v);
    auto returned = v.insert(v.begin() + 1, v[2]);
    emit("alias.insert.value", snapshot(v), {}, returned == v.begin() + 1);
  }
  {
    AlignedV v; observe(v); v.emplace_back(7);
    int mod = static_cast<int>(reinterpret_cast<std::uintptr_t>(&v[0]) % 64);
    int alignment = static_cast<int>(alignof(AlignedElement));
    v.clear();
    emit("alignment.runtime64", snapshot(v), {alignment, mod}, alignment == 64 && mod == 0);
  }
  {
    V v; seed(v, {1, 2, 3}); observe(v); recorder.throwDtorOnce = true;
    auto error = failure([&] { v.pop_back(); });
    recorder.throwDtorOnce = false;
    emit("pop.destructor.throw.once", snapshot(v), {}, false, error);
  }
  std::cout << "]}\n";
}
