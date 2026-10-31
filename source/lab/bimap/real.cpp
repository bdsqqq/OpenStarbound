// Source-only real-header fixture. The parent supplies an absolute BIMAP_HEADER
// (native or a generated real-support header), native exception bodies and runs.
#include "../../core/StarString.hpp"
#include "../../core/StarMap.hpp"
#include "../../core/StarMaybe.hpp"
#ifndef BIMAP_HEADER
#error "pass an absolute BIMAP_HEADER; do not use the lab StarString shim"
#endif
#ifdef STAR_DEBUG
#error "this fixture must not enable fatal debug assertions"
#endif
#include BIMAP_HEADER
#include <algorithm>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace RealFixture {
struct Event { char op; int id; };
struct Marker : std::runtime_error {
  static int identity;
  int const* token = &identity;
  Marker() : std::runtime_error("real-bimap-marker") {}
};
int Marker::identity = 0;
struct Key {
  int id;
  static std::vector<Event> events;
  static bool overflow;
  static int copyThrow, moveThrow;
  static void log(char op, int id) noexcept {
    // No allocations (including during unwinding). Overflow is reported by the
    // runner after destruction rather than throwing from a destructor.
    if (events.size() == events.capacity()) overflow = true;
    else events.push_back({op, id});
  }
  explicit Key(int n = 0) : id(n) { log('c', id); }
  Key(Key const& k) : id(k.id) {
    log('C', id);
    if (copyThrow == id) { copyThrow = -1; log('X', id); throw Marker(); }
  }
  Key(Key&& k) : id(k.id) {
    log('M', id);
    if (moveThrow == id) { moveThrow = -1; log('X', id); throw Marker(); }
  }
  ~Key() noexcept { log('d', id); }
  bool operator<(Key const& k) const { return id < k.id; }
  bool operator!=(Key const& k) const { return id != k.id; }
  bool operator==(Key const& k) const { return id == k.id; }
  friend std::ostream& operator<<(std::ostream& s, Key const& k) { return s << k.id; }
};
std::vector<Event> Key::events;
bool Key::overflow = false;
int Key::copyThrow = -1;
int Key::moveThrow = -1;
void require(bool ok, char const* text) {
  if (!ok) throw std::runtime_error(std::string("real fixture: ") + text);
}
#define CHECK(x) require(bool(x), #x)

template <typename E, typename F, typename Verify>
void safeThrows(F&& f, Verify&& verify) {
  bool caught = false;
  try { f(); }
  catch (E const& e) { caught = true; verify(e); }
  CHECK(caught);
}
template <typename F> void markerThrows(F&& f) {
  safeThrows<Marker>(std::forward<F>(f), [](Marker const& e) {
    CHECK(e.token == &Marker::identity);
    CHECK(std::string(e.what()) == "real-bimap-marker");
  });
}
using B = Star::BiMap<Key, Key>;

// Only remove is overridden; all storage and pointer maybeTake operations are
// the actual MapMixin implementation. Tags distinguish otherwise equal types.
template <char Tag> struct RemoveMap : Star::Map<Key, Key const*> {
  using Base = Star::Map<Key, Key const*>;
  static bool armed;
  bool remove(Key const& key) {
    Key::log(Tag, key.id);
    if (armed) { armed = false; throw Marker(); }
    return Base::remove(key);
  }
};
template <char Tag> bool RemoveMap<Tag>::armed = false;
using ThrowB = Star::BiMap<Key, Key, RemoveMap<'L'>, RemoveMap<'R'>>;

std::string quote(std::string const& s) {
  std::string out = "\"";
  for (unsigned char c : s) {
    if (c == '"' || c == '\\') { out += '\\'; out += char(c); }
    else if (c == '\n') out += "\\n";
    else if (c < 32) throw std::runtime_error("unexpected control character");
    else out += char(c);
  }
  return out + '"';
}
struct Report { std::string outputs = "[]", state = "[]"; };
template <typename Map> std::string fullState(Map const& b) {
  std::ostringstream s;
  s << '[';
  bool first = true;
  for (auto const& p : b) {
    if (!first) s << ',';
    first = false;
    s << '[' << p.first.id << ',' << p.second.id << ']';
  }
  s << ']';
  return s.str();
}
template <typename Map> void partialState(Report& r, Map const& b, Key const& l, Key const& v, bool left, bool right) {
  // Opposite-side mapped pointers can dangle after a throw. Never inspect them.
  CHECK(b.size() == (left ? 1u : 0u));
  CHECK(b.hasLeftValue(l) == left);
  CHECK(b.hasRightValue(v) == right);
  r.state = std::string("{\"size\":") + std::to_string(b.size()) +
    ",\"left\":" + (left ? "true" : "false") + ",\"right\":" + (right ? "true" : "false") + '}';
}
size_t findEvent(size_t start, char op, int id) {
  for (size_t i = start; i < Key::events.size(); ++i)
    if (Key::events[i].op == op && Key::events[i].id == id) return i;
  return Key::events.size();
}
template <typename F> void run(char const* name, F&& body) {
  Key::events.clear(); Key::overflow = false;
  Key::copyThrow = Key::moveThrow = -1;
  Report r;
  body(r); // All case-owned objects have died before the trace is captured.
  CHECK(!Key::overflow);
  CHECK(Key::copyThrow == -1 && Key::moveThrow == -1);
  std::cout << "{\"model\":\"native-real-headers-partial-lab-notgame\",\"case\":" << quote(name)
    << ",\"outputs\":" << r.outputs << ",\"mapstate\":" << r.state << ",\"events\":[";
  bool first = true;
  for (auto const& e : Key::events) {
    if (!first) std::cout << ',';
    first = false;
    std::cout << "[\"" << e.op << "\"," << e.id << ']';
  }
  std::cout << "]}\n";
}

void cases() {
  Key::events.reserve(65536);
  for (bool right : {true, false}) {
    run(right ? "maybeRight_hit_miss" : "maybeLeft_hit_miss", [=](Report& r) {
      Key l(1), v(10), absent(99); B b; CHECK(b.insert(l, v));
      auto hit = right ? b.maybeRight(l) : b.maybeLeft(v);
      auto miss = right ? b.maybeRight(absent) : b.maybeLeft(absent);
      CHECK(hit && hit->id == (right ? 10 : 1)); CHECK(!miss);
      r.outputs = right ? "[10,null]" : "[1,null]"; r.state = fullState(b);
    });
    for (bool hit : {true, false}) {
      run(right ? (hit ? "valueRight_hit_eager" : "valueRight_miss") :
        (hit ? "valueLeft_hit_eager" : "valueLeft_miss"), [=](Report& r) {
        Key l(1), v(10), absent(99), def(77); B b; CHECK(b.insert(l, v));
        size_t start = Key::events.size(); Key::log('|', 0);
        Key result = right ? b.valueRight(hit ? l : absent, def) : b.valueLeft(hit ? v : absent, def);
        CHECK(result.id == (hit ? (right ? 10 : 1) : 77));
        CHECK(findEvent(start, 'C', 77) < Key::events.size());
        r.outputs = '[' + std::to_string(result.id) + ']'; r.state = fullState(b);
      });
    }
    run(right ? "maybeTakeRight_hit_miss" : "maybeTakeLeft_hit_miss", [=](Report& r) {
      Key l(1), v(10), absent(99); B b; CHECK(b.insert(l, v));
      auto miss = right ? b.maybeTakeRight(absent) : b.maybeTakeLeft(absent); CHECK(!miss);
      size_t start = Key::events.size(); Key::log('|', 0);
      auto result = right ? b.maybeTakeRight(l) : b.maybeTakeLeft(v);
      int id = right ? 10 : 1;
      CHECK(result && result->id == id);
      size_t copy = findEvent(start, 'C', id), destroy = findEvent(start, 'd', id);
      CHECK(copy < destroy && destroy < Key::events.size());
      CHECK(b.empty() && !b.hasLeftValue(l) && !b.hasRightValue(v));
      r.outputs = '[' + std::to_string(result->id) + ",null]"; r.state = fullState(b);
    });
    run(right ? "takeRight_hit" : "takeLeft_hit", [=](Report& r) {
      Key l(1), v(10); B b; CHECK(b.insert(l, v));
      Key result = right ? b.takeRight(l) : b.takeLeft(v);
      CHECK(result.id == (right ? 10 : 1));
      CHECK(b.empty() && !b.hasLeftValue(l) && !b.hasRightValue(v));
      r.outputs = '[' + std::to_string(result.id) + ']'; r.state = fullState(b);
    });
    run(right ? "takeRight_missing_exception" : "takeLeft_missing_exception", [=](Report& r) {
      Key l(1), v(10), absent(99); B b; CHECK(b.insert(l, v));
      safeThrows<Star::MapException>([&] { if (right) b.takeRight(absent); else b.takeLeft(absent); },
        [&](Star::MapException const& e) {
          std::string expected = right ? "(MapException) No such key in BiMap::takeRight" :
            "(MapException) No such key in BiMap::takeLeft";
          CHECK(std::string(e.what()) == expected);
          r.outputs = '[' + quote(e.what()) + ']';
        });
      r.state = fullState(b);
    });
    run(right ? "copy_throw_takeRight_partial" : "copy_throw_takeLeft_partial", [=](Report& r) {
      Key l(1), v(10); B b; CHECK(b.insert(l, v));
      Key::log('|', 0); Key::copyThrow = right ? 10 : 1;
      markerThrows([&] { if (right) b.maybeTakeRight(l); else b.maybeTakeLeft(v); });
      partialState(r, b, l, v, !right, right); r.outputs = "[\"real-bimap-marker\"]";
    });
    run(right ? "opposite_remove_throw_right" : "opposite_remove_throw_left", [=](Report& r) {
      Key l(1), v(10); ThrowB b; CHECK(b.insert(l, v));
      Key::log('|', 0);
      if (right) RemoveMap<'R'>::armed = true; else RemoveMap<'L'>::armed = true;
      markerThrows([&] { if (right) b.maybeTakeRight(l); else b.maybeTakeLeft(v); });
      CHECK(!RemoveMap<'L'>::armed && !RemoveMap<'R'>::armed);
      partialState(r, b, l, v, !right, right); r.outputs = "[\"real-bimap-marker\"]";
    });
    run(right ? "return_move_throw_right" : "return_move_throw_left", [=](Report& r) {
      Key l(1), v(10); B b; CHECK(b.insert(l, v));
      // Converting the named T to Maybe<T> invokes T's move constructor.
      // Record the semantic observation, never a compiler-specific move count.
      Key::log('|', 0); Key::moveThrow = right ? 10 : 1;
      markerThrows([&] { if (right) b.maybeTakeRight(l); else b.maybeTakeLeft(v); });
      partialState(r, b, l, v, false, false);
      r.outputs = "[{\"returnMoveThrowObserved\":true}]";
    });
  }
  run("get_ptr_reference_identity", [](Report& r) {
    Key l(1), v(10), absent(99); B b; CHECK(b.insert(l, v));
    auto p = *b.begin();
    CHECK(&b.getRight(l) == &p.second && b.rightPtr(l) == &p.second);
    CHECK(&b.getLeft(v) == &p.first && b.leftPtr(v) == &p.first);
    CHECK(!b.rightPtr(absent) && !b.leftPtr(absent));
    Key l2(2), v2(20); CHECK(b.insert(l2, v2));
    CHECK(&b.getRight(l) == &p.second && &b.getLeft(v) == &p.first);
    r.outputs = "[true,true,null,null]"; r.state = fullState(b);
  });
  run("pairs_lists_native_order", [](Report& r) {
    Key a(3), bkey(1), c(2), x(10), y(30), z(20); B b;
    CHECK(b.insert(a, x)); CHECK(b.insert(bkey, y)); CHECK(b.insert(c, z));
    auto pairs = b.pairs(); auto left = b.leftValues(); auto right = b.rightValues();
    CHECK(pairs.size() == 3 && left.size() == 3 && right.size() == 3);
    CHECK(pairs[0].first.id == 1 && pairs[0].second.id == 30);
    CHECK(pairs[1].first.id == 2 && pairs[1].second.id == 20);
    CHECK(pairs[2].first.id == 3 && pairs[2].second.id == 10);
    for (size_t i = 0; i != 3; ++i) { CHECK(left[i].id == int(i + 1)); CHECK(right[i].id == int((i + 1) * 10)); }
    r.outputs = "{\"pairs\":[[1,30],[2,20],[3,10]],\"left\":[1,2,3],\"right\":[10,20,30]}";
    r.state = fullState(b);
  });
}
} // namespace RealFixture

int main() {
  try {
    RealFixture::cases();
#ifdef BIMAP_CANDIDATE
    std::cerr << "BIMAP_RUST_COUNTS [";
    for (uint32_t mode = 0; mode < SB_BIMAP_MODE_COUNT; ++mode) {
      if (mode) std::cerr << ',';
      std::cerr << sb_bimap_count(mode);
    }
    std::cerr << "]\n";
#endif
    return 0;
  } catch (std::exception const& e) {
    std::cerr << "real fixture failed: " << e.what() << '\n';
    return 1;
  }
}
