// Native template characterization, not a production container/exception oracle.
#include "StarBiMap.original.hpp"
#include <iostream>
#include <type_traits>

namespace Fixture {
using namespace Star;
std::vector<std::string> events;
bool throwRightInsert = false;
void event(std::string const& text) { events.push_back(text); }
void require(bool condition, char const* expression, int line) {
  if (!condition)
    throw std::runtime_error("require line " + std::to_string(line) + ": " + expression);
}
#define REQUIRE(COND) ::Fixture::require(bool(COND), #COND, __LINE__)

// std::map preserves key/node addresses across unrelated insertions/erasures.
// Separate tags distinguish the two int-key maps without fake key lifetimes.
template <typename K, typename V, char Side> class TraceMap {
  std::map<K, V> data;
  static void log(char const* op) { event(std::string(1, Side) + "." + op); }
  static void log(char const* op, K const& key) {
    event(std::string(1, Side) + "." + op + ":" + outputAny(key));
  }
public:
  using iterator = typename std::map<K, V>::iterator;
  using const_iterator = typename std::map<K, V>::const_iterator;
  template <typename P> pair<iterator, bool> insert(P const& value) {
    log("insert", value.first);
    if (Side == 'R' && throwRightInsert) {
      throwRightInsert = false;
      log("throw_insert");
      throw MapException("fixture right insert failure");
    }
    auto result = data.insert(value);
    log(result.second ? "inserted" : "duplicate", value.first);
    return result;
  }
  bool contains(K const& key) const { log("contains", key); return data.count(key) != 0; }
  V value(K const& key, V def = V()) const {
    log("value", key);
    auto it = data.find(key);
    return it == data.end() ? def : it->second;
  }
  V const& get(K const& key) const {
    log("get", key);
    auto it = data.find(key);
    if (it == data.end()) throw MapException("fixture missing key " + outputAny(key));
    return it->second;
  }
  iterator find(K const& key) { log("find", key); return data.find(key); }
  const_iterator find(K const& key) const { log("find", key); return data.find(key); }
  const_iterator begin() const { log("begin"); return data.begin(); }
  const_iterator end() const { log("end"); return data.end(); }
  List<K> keys() const {
    log("keys");
    List<K> result;
    for (auto const& p : data) result.append(p.first);
    return result;
  }
  size_t size() const { log("size"); return data.size(); }
  bool empty() const { log("empty"); return data.empty(); }
  void clear() { log("clear"); data.clear(); }
  bool remove(K const& key) {
    // Log before erasure; a BiMap removal argument may name a stored key.
    log("remove", key);
    return data.erase(key) != 0;
  }
};
using B = BiMap<int, int, TraceMap<int, int const*, 'L'>, TraceMap<int, int const*, 'R'>>;
static_assert(std::is_same<decltype(*std::declval<B::iterator>()),
    pair<int const&, int const&>>::value, "iterator must return references");

std::string quote(std::string const& text) {
  std::string out = "\"";
  char const* digits = "0123456789abcdef";
  for (unsigned char c : text) {
    if (c == '\"' || c == '\\') { out += '\\'; out += char(c); }
    else if (c < 32) {
      out += "\\u00";
      out += digits[c >> 4]; out += digits[c & 15];
    } else out += char(c);
  }
  return out + "\"";
}
void emit(char const* name, std::string const& result) {
  std::cout << "{\"case\":" << quote(name) << ",\"result\":" << result << ",\"events\":[";
  bool first = true;
  for (auto const& e : events) {
    if (!first) std::cout << ',';
    first = false;
    std::cout << quote(e);
  }
  std::cout << "]}\n";
}
std::string state(B const& map) {
  // Only used on fully linked maps. Corrupt/partial maps use counts below.
  std::string out = "{\"left_size\":" + std::to_string(map.size()) + ",\"pairs\":[";
  bool first = true;
  for (auto p : map) {
    if (!first) out += ',';
    first = false;
    out += '[' + std::to_string(p.first) + ',' + std::to_string(p.second) + ']';
  }
  return out + "]}";
}
void exact(std::initializer_list<std::string> wanted) {
  REQUIRE(events == std::vector<std::string>(wanted));
}
template <typename F> std::string caught(F action) {
  try { action(); }
  catch (MapException const& e) { return e.what(); }
  throw std::runtime_error("expected fixture MapException");
}
template <typename F> void run(char const* name, F action) {
  events.clear();
  throwRightInsert = false;
  try { action(); }
  catch (std::exception const& e) {
    throw std::runtime_error(std::string(name) + ": " + e.what());
  }
}

void cases() {
  run("insert_normal", [] {
    B m;
    REQUIRE(m.empty());
    auto inserted = m.insert(B::value_type{1, 10});
    REQUIRE(inserted.second);
    auto refs = *inserted.first;
    REQUIRE(refs.first == 1 && refs.second == 10);
    REQUIRE(m.getRight(1) == 10 && m.getLeft(10) == 1);
    REQUIRE(m.rightPtr(99) == nullptr && m.leftPtr(99) == nullptr);
    REQUIRE(m.hasLeftValue(1) && m.hasRightValue(10));
    REQUIRE(m.size() == 1 && !m.empty());
    REQUIRE(m.leftValues() == List<int>{1});
    REQUIRE(m.rightValues() == List<int>{10});
    REQUIRE(m.pairs().size() == 1);
    emit("insert_normal", state(m));
  });
  run("insert_left_duplicate", [] {
    B m; m.insert(1, 10);
    events.clear();
    auto result = m.insert(B::value_type{1, 20});
    REQUIRE(!result.second);
    exact({"L.insert:1", "L.duplicate:1"});
    REQUIRE((*result.first).second == 10 && m.rightPtr(1) != nullptr);
    REQUIRE(!m.hasRightValue(20) && m.size() == 1);
    emit("insert_left_duplicate", state(m));
  });
  run("insert_right_conflict_assertion_off", [] {
    B m; m.insert(1, 10);
    events.clear();
    REQUIRE(m.insert(2, 10));
    exact({"L.insert:2", "L.inserted:2", "R.insert:10", "R.duplicate:10"});
    REQUIRE(m.size() == 2 && m.rightValues().size() == 1);
    REQUIRE(m.getLeft(10) == 2);
    REQUIRE(m.rightPtr(1) == m.rightPtr(2));
    REQUIRE(m.getRight(1) == 10 && m.getRight(2) == 10);
    emit("insert_right_conflict_assertion_off",
        "{\"inserted\":true,\"left_size\":2,\"right_keys\":1,\"back_left\":2,\"shared_right\":true}");
    // No deletion through this inconsistent relationship. Destruction never
    // dereferences stored pointers, so both map node sets can die safely.
  });
  run("add_left_duplicate_lazy", [] {
    B m; m.add(1, 10);
    events.clear();
    auto message = caught([&] { m.add(1, 10); });
    exact({"L.contains:1"});
    REQUIRE(message == "BiMap already contains left side value '1'");
    REQUIRE(m.size() == 1);
    emit("add_left_duplicate_lazy", "{\"message\":" + quote(message) + ",\"state\":" + state(m) + "}");
  });
  run("add_right_duplicate", [] {
    B m; m.add(1, 10);
    events.clear();
    auto message = caught([&] { m.add(B::value_type{2, 10}); });
    exact({"L.contains:2", "R.contains:10"});
    REQUIRE(message == "BiMap already contains right side value '10'");
    REQUIRE(m.size() == 1 && !m.hasLeftValue(2));
    emit("add_right_duplicate", "{\"message\":" + quote(message) + ",\"state\":" + state(m) + "}");
  });
  run("overwrite_conflicts", [] {
    B m; m.insert(1, 10); m.insert(2, 20);
    events.clear();
    m.overwrite(B::value_type{1, 20});
    exact({"L.value:1", "R.remove:10", "L.remove:1", "R.value:20",
        "L.remove:2", "R.remove:20", "L.insert:1", "L.inserted:1",
        "R.insert:20", "R.inserted:20"});
    REQUIRE(m.size() == 1 && m.getRight(1) == 20 && m.getLeft(20) == 1);
    REQUIRE(!m.hasLeftValue(2) && !m.hasRightValue(10));
    emit("overwrite_conflicts", state(m));
  });
  run("remove_left", [] {
    B m; m.insert(1, 10);
    events.clear();
    REQUIRE(!m.removeLeft(99));
    REQUIRE(m.removeLeft(1));
    exact({"L.value:99", "L.value:1", "R.remove:10", "L.remove:1"});
    REQUIRE(m.empty() && m.rightValues().empty());
    emit("remove_left", state(m));
  });
  run("remove_right", [] {
    B m; m.insert(1, 10);
    events.clear();
    REQUIRE(!m.removeRight(99));
    REQUIRE(m.removeRight(10));
    exact({"R.value:99", "R.value:10", "L.remove:1", "R.remove:10"});
    REQUIRE(m.empty() && m.leftValues().empty());
    emit("remove_right", state(m));
  });
  run("clear_left_then_right", [] {
    B m; m.insert(1, 10); m.insert(2, 20);
    events.clear(); m.clear();
    exact({"L.clear", "R.clear"});
    REQUIRE(m.empty() && m.rightValues().empty());
    emit("clear_left_then_right", state(m));
  });
  run("assignment_self", [] {
    B m; m.insert(1, 10);
    auto ptr = m.rightPtr(1);
    B const& same = m;
    events.clear(); m = same;
    exact({});
    REQUIRE(m.rightPtr(1) == ptr && m.getLeft(10) == 1);
    emit("assignment_self", state(m));
  });
  run("assignment_distinct_clear_copy", [] {
    B source; source.insert(1, 10); source.insert(2, 20);
    B destination; destination.insert(9, 90);
    events.clear(); destination = source;
    REQUIRE(events.size() >= 4);
    REQUIRE(events[0] == "L.clear" && events[1] == "R.clear");
    REQUIRE(events[2] == "L.begin" && events[3] == "L.end");
    REQUIRE(destination.size() == 2 && !destination.hasLeftValue(9));
    REQUIRE(destination.getRight(1) == 10 && destination.getLeft(20) == 2);
    REQUIRE(destination.rightPtr(1) != source.rightPtr(1));
    source.clear();
    REQUIRE(destination.getRight(1) == 10 && destination.getLeft(20) == 2);
    emit("assignment_distinct_clear_copy", state(destination));
  });
  run("copy_constructor", [] {
    B source; source.insert(1, 10);
    B copy(source);
    REQUIRE(copy.rightPtr(1) != source.rightPtr(1));
    source.clear();
    REQUIRE(copy.getRight(1) == 10 && copy.getLeft(10) == 1);
    emit("copy_constructor", state(copy));
  });
  run("range_duplicate_ignored", [] {
    std::vector<B::value_type> input{{1, 10}, {1, 20}, {2, 30}};
    B m = B::from(input);
    REQUIRE(m.size() == 2 && m.getRight(1) == 10 && m.getRight(2) == 30);
    REQUIRE(!m.hasRightValue(20));
    emit("range_duplicate_ignored", state(m));
  });
  run("list_duplicate_throws", [] {
    auto message = caught([] { B m{{1, 10}, {1, 20}, {2, 30}}; });
    exact({"L.insert:1", "L.inserted:1", "R.insert:10", "R.inserted:10",
        "L.insert:1", "L.duplicate:1"});
    REQUIRE(message == "Repeat pair in BiMap initializer_list construction: (1, 20)");
    emit("list_duplicate_throws", "{\"message\":" + quote(message) + "}");
  });
  run("equality_missing_key_skip", [] {
    B a; a.insert(1, 10); a.insert(2, 20);
    B b; b.insert(1, 10); b.insert(3, 30);
    REQUIRE(a == b && b == a);
    emit("equality_missing_key_skip", "{\"equal_both_directions\":true}");
  });
  run("equality_disjoint_same_size", [] {
    B a; a.insert(1, 10);
    B b; b.insert(2, 20);
    REQUIRE(a == b && b == a);
    emit("equality_disjoint_same_size", "{\"equal_both_directions\":true}");
  });
  run("equality_differing_value", [] {
    B a; a.insert(1, 10);
    B b; b.insert(1, 20);
    REQUIRE(!(a == b) && !(b == a));
    emit("equality_differing_value", "{\"equal_both_directions\":false}");
  });
  run("equality_identity_and_size", [] {
    B a; a.insert(1, 10);
    events.clear(); REQUIRE(a == a); exact({});
    B b;
    REQUIRE(!(a == b));
    emit("equality_identity_and_size", "{\"self\":true,\"different_size\":false}");
  });
  run("iterator_refs_and_increment", [] {
    B m; m.insert(1, 10); m.insert(2, 20);
    auto it = m.begin();
    auto refs = *it;
    auto left = &refs.first;
    auto right = &refs.second;
    REQUIRE(right == m.rightPtr(1) && left == m.leftPtr(10));
    auto old = it++;
    REQUIRE((*old).first == 1 && (*it).first == 2 && old != it);
    auto& incremented = ++it;
    REQUIRE(&incremented == &it && it == m.end());
    m.insert(3, 30);
    m.removeLeft(2);
    REQUIRE(&(*old).first == left && &(*old).second == right);
    REQUIRE(refs.first == 1 && refs.second == 10);
    emit("iterator_refs_and_increment", "{\"post_old_left\":1,\"pre_returns_self\":true,\"refs_stable\":true}");
  });
  run("right_insert_throw_partial", [] {
    B m; throwRightInsert = true;
    auto message = caught([&] { m.insert(1, 10); });
    exact({"L.insert:1", "L.inserted:1", "R.insert:10", "R.throw_insert"});
    REQUIRE(message == "fixture right insert failure");
    REQUIRE(m.size() == 1 && m.hasLeftValue(1));
    REQUIRE(!m.hasRightValue(10) && m.rightValues().empty());
    REQUIRE(m.rightPtr(1) == nullptr && m.leftPtr(10) == nullptr);
    // Never iterate/getRight on the null-linked left node.
    emit("right_insert_throw_partial", "{\"left_size\":1,\"left_contains\":true,\"right_keys\":0,\"right_pointer_present\":false,\"message\":" + quote(message) + "}");
  });
}
}
int main() {
  try { Fixture::cases(); return 0; }
  catch (std::exception const& e) {
    std::cerr << "native BiMap fixture failed: " << e.what() << '\n';
    return 1;
  }
}
