// Finite native-contract fixture. Expected values were fixed before native execution.
#ifdef IDMAP_MUTANT_HEADER
#include "StarIdMap.mutant.hpp"
#else
#include "StarIdMap.hpp"
#endif
#include "StarDataStreamDevices.hpp"

#include <algorithm>
#include <cstdint>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <typeinfo>
#include <type_traits>
#include <vector>

using namespace Star;
namespace {
void check(bool ok, char const* why) {
  if (!ok)
    throw std::runtime_error(why);
}
std::string decimal(uint32_t v) { return std::to_string(v); }
void row(std::string const& backend, char const* name, std::string const& actual,
    char const* expected) {
  if (actual != expected)
    throw std::runtime_error(backend + "/" + name + ": expected " + expected + ", got " + actual);
  std::cout << "CASE\t" << backend << "/" << name << "\t" << actual << '\n';
}
void property(std::string const& backend, char const* name) {
  std::cout << "PASS\t" << backend << "/" << name << '\n';
}
std::string hex(ByteArray const& bytes) {
  static char const digits[] = "0123456789abcdef";
  std::string s;
  for (unsigned char c : bytes) {
    s += digits[c >> 4];
    s += digits[c & 15];
  }
  return s;
}
template <typename F>
std::string idFailure(F f) {
  try { f(); } catch (IdMapException const& e) {
    check(typeid(e) == typeid(IdMapException), "exact IdMapException dynamic type");
    return e.what();
  }
  throw std::runtime_error("missing IdMapException");
}

template <template <class, class> class MapType>
void cases(std::string const& backend) {
  using M = MapType<uint32_t, uint32_t>;
  M defaults;
  auto defaultFirst = defaults.nextId();
  auto defaultSecond = defaults.nextId();
  row(backend, "default-unsigned", decimal(defaultFirst) + "," + decimal(defaultSecond), "0,1");
  M high(4294967293u, 4294967295u);
  std::string highIds;
  for (unsigned i = 0; i != 4; ++i) {
    if (i) highIds += ',';
    highIds += decimal(high.nextId());
  }
  row(backend, "uint32-high-wrap", highIds, "4294967293,4294967294,4294967295,4294967293");
  M outside(10, 12);
  outside.add(99, 5);
  check(outside.contains(99) && outside.nextId() == 10, "explicit add does not validate id range");
  row(backend, "explicit-outside-range", decimal(outside.get(99)), "5");
  M m(10, 12);
  std::string ids;
  for (unsigned i = 0; i != 5; ++i) {
    if (i) ids += ',';
    ids += decimal(m.nextId());
  }
  row(backend, "next-unreserved-inclusive", ids, "10,11,12,10,11");
  m.clear();
  m.add(11, 77);
  row(backend, "explicit-no-cursor-advance", decimal(m.nextId()), "10");
  row(backend, "collision-skip", decimal(m.nextId()), "12");
  m.clear();
  row(backend, "auto-first", decimal(m.add(100)), "10");
  row(backend, "auto-second", decimal(m.add(200)), "11");
  // The > to >= fullness mutant must fail on this last available slot.
  row(backend, "fill-last-slot", decimal(m.add(300)), "12");
  row(backend, "exhaustion", idFailure([&] { m.nextId(); }),
      "(IdMapException) No id space left in IdMapWrapper");
  row(backend, "duplicate", idFailure([&] { m.add(11, 999); }),
      "(IdMapException) IdMapWrapper::add(id, value) called with pre-existing id '11'");
  row(backend, "duplicate-preserves-value", decimal(m.get(11)), "200");
  check(m.remove(11), "remove occupied hole");
  row(backend, "hole-reused", decimal(m.add(201)), "11");
  m.clear();
  auto resetId = m.add(7);
  row(backend, "clear-resets", decimal(resetId) + "," + decimal(m.size()), "10,1");

  M equal(10, 12);
  equal.add(10, 7);
  equal.nextId();
  equal.nextId();
  check(m == equal && !(m != equal), "equality excludes cursor");
  M range(10, 13);
  range.add(10, 7);
  check(m != range, "equality checks range");
  equal.get(10) = 8;
  check(m != equal, "equality checks contents");
  row(backend, "equality", "cursor-excluded,range-and-contents-included", "cursor-excluded,range-and-contents-included");

  M api(20, 25);
  check(api.empty() && api.size() == 0, "empty/size");
  api.add(21, 210); api.add(23, 230); api.add(25, 250);
  auto keys = api.keys();
  std::sort(keys.begin(), keys.end());
  check(keys.size() == 3 && keys[0] == 21 && keys[1] == 23 && keys[2] == 25, "keys");
  auto values = api.values();
  std::sort(values.begin(), values.end());
  check(values.size() == 3 && values[0] == 210 && values[1] == 230 && values[2] == 250, "values");
  auto pairs = api.pairs();
  check(pairs.size() == 3, "pairs size");
  for (auto const& p : pairs) check(p.second == p.first * 10, "pairs association");
  check(api.contains(21) && !api.contains(22), "contains");
  check(api.get(21) == 210 && api.ptr(21) && !api.ptr(22), "get/ptr");
  *api.ptr(21) = 211;
  M const& constant = api;
  check(constant.get(21) == 211 && *constant.ptr(21) == 211 && !constant.ptr(22), "const get/ptr");
  check(api.maybe(21) && *api.maybe(21) == 211 && !api.maybe(22), "maybe");
  check(api.value(22, 999) == 999 && api.value(21, 999) == 211, "value default/occupied");
  unsigned n = 0;
  for (auto i = constant.begin(); i != constant.end(); ++i) ++n;
  check(n == 3, "const begin/end");
  for (auto i = api.begin(); i != api.end(); ++i) i->second += 1;
  check(api.take(21) == 212 && !api.contains(21), "take");
  auto taken = api.maybeTake(23);
  check(taken && *taken == 231 && !api.maybeTake(23) && !api.maybeTake(22), "maybeTake");
  check(!api.remove(22), "remove missing");
  api.erase(api.begin());
  check(api.empty() && api.begin() == api.end(), "erase iterator");
  api.add(24, 1);
  check(api.erase(uint32_t(24)) == 1 && api.empty(), "erase key");
  row(backend, "inherited-16", "keys,values,pairs,contains,size,empty,get,ptr,maybe,take,maybeTake,remove,value,begin,end,erase",
      "keys,values,pairs,contains,size,empty,get,ptr,maybe,take,maybeTake,remove,value,begin,end,erase");

  M source(10, 12);
  source.add(11, 77);
  DataStreamBuffer stream;
  stream << source;
  row(backend, "stream-one-entry", hex(stream.data()), "010000000b0000004d0000000a0000000c0000000a");
  stream.seek(0);
  check(stream.readVlqU() == 1, "stream map count first");
  check(stream.read<uint32_t>() == 11 && stream.read<uint32_t>() == 77, "stream key then value");
  check(stream.read<uint32_t>() == 10 && stream.read<uint32_t>() == 12 && stream.read<uint32_t>() == 10 && stream.atEnd(), "stream min,max,cursor");
  stream.seek(0);
  M restored(40, 44);
  restored.add(42, 9);
  stream >> restored;
  check(restored == source && !restored.contains(42), "read replaces map and range");
  auto first = restored.nextId();
  auto second = restored.nextId();
  row(backend, "stream-roundtrip-cursor", decimal(first) + "," + decimal(second), "10,12");

  // Boundary truncations avoid making a golden out of partially overwritten primitive storage.
  for (size_t cut : {size_t(0), size_t(5), size_t(9), size_t(13)}) {
    M target(40, 44);
    target.add(42, 9);
    target.nextId(); // cursor 41, despite no reservation
    DataStreamBuffer broken(ByteArray(stream.ptr(), cut));
    bool failed = false;
    try { broken >> target; } catch (IOException const&) { failed = true; }
    check(failed, "truncated stream must fail");
    DataStreamBuffer after;
    after << target;
    std::string actual = hex(after.data());
    if (cut == 0 || cut == 5)
      row(backend, cut == 0 ? "partial-count" : "partial-entry", actual, "00000000280000002c00000029");
    else if (cut == 9)
      row(backend, "partial-min", actual, "010000000b0000004d000000280000002c00000029");
    else
      row(backend, "partial-max", actual, "010000000b0000004d0000000a0000002c00000029");
  }
  property(backend, "stream-order-and-partial-mutation");
}

struct PayloadFailure { void const* identity; };
struct Counted {
  static int live, made, destroyed, copies, moves;
  static bool failCopy;
  static int token;
  int value;
  explicit Counted(int v) : value(v) { ++live; ++made; }
  Counted(Counted const& other) : value(other.value) {
    if (failCopy) throw PayloadFailure{&token};
    ++live; ++made; ++copies;
  }
  Counted(Counted&& other) noexcept : value(other.value) {
    other.value = -1;
    ++live; ++made; ++moves;
  }
  Counted& operator=(Counted const&) = default;
  Counted& operator=(Counted&&) = default;
  ~Counted() { --live; ++destroyed; }
};
int Counted::live = 0;
int Counted::made = 0;
int Counted::destroyed = 0;
int Counted::copies = 0;
int Counted::moves = 0;
bool Counted::failCopy = false;
int Counted::token = 0;
struct NoDefault {
  int value;
  NoDefault() = delete;
  explicit NoDefault(int v) : value(v) {}
};
struct MoveOnly {
  std::unique_ptr<int> value;
  explicit MoveOnly(int v) : value(new int(v)) {}
  MoveOnly(MoveOnly&&) = default;
  MoveOnly(MoveOnly const&) = delete;
  MoveOnly& operator=(MoveOnly&&) = default;
};

template <template <class, class> class MapType>
void lifetimes(std::string const& backend) {
  check(Counted::live == 0, "no live payload at entry");
  {
    MapType<uint32_t, Counted> map(10, 14);
    int copies = Counted::copies;
    auto id = map.add(Counted(7));
    check(id == 10 && map.get(10).value == 7 && Counted::copies > copies, "auto-add named lvalue is copied");
    property(backend, "auto-add-copy");
    copies = Counted::copies;
    int moves = Counted::moves;
    map.add(13, Counted(8));
    check(map.get(13).value == 8 && Counted::copies == copies && Counted::moves > moves, "explicit-add moves");
    property(backend, "explicit-add-move");
    Counted::failCopy = true;
    bool caught = false;
    try { map.add(Counted(9)); } catch (PayloadFailure const& e) {
      caught = e.identity == &Counted::token;
    }
    Counted::failCopy = false;
    check(caught && map.size() == 2 && !map.contains(11), "payload exception identity/no insertion");
    check(map.nextId() == 12, "cursor advanced before insertion copy threw");
    property(backend, "throw-identity-and-advanced-cursor");
    check(Counted::made - Counted::destroyed == Counted::live, "live conservation before clear");
    map.clear();
    check(Counted::live == 0 && map.nextId() == 10, "clear destroys payloads and resets cursor");
  }
  check(Counted::live == 0 && Counted::made == Counted::destroyed, "lifetime conservation at exit");
  property(backend, "lifetime-conservation");
  {
    MapType<uint32_t, NoDefault> lazy(10, 12);
    lazy.add(11, NoDefault(4));
    check(lazy.get(11).value == 4 && lazy.nextId() == 10, "unused default-requiring APIs stay lazy");
    // FlatHashTable's bucket-vector construction itself requires copies;
    // do not invent move-only support for the native hash-map base.
    if constexpr (std::is_same_v<MapType<uint32_t, uint32_t>, IdMap<uint32_t, uint32_t>>) {
      MapType<uint32_t, MoveOnly> explicitMoveOnly(10, 12);
      explicitMoveOnly.add(11, MoveOnly(5));
      check(*explicitMoveOnly.get(11).value == 5, "ordered explicit move-only add is valid");
    }
  }
  property(backend, "lazy-no-default-and-native-base-constraints");
}
}

int main() {
  try {
#ifdef IDMAP_HASH_MOVE_ONLY_NEGATIVE
    IdHashMap<uint32_t, MoveOnly> negative(10, 12);
    negative.add(11, MoveOnly(1));
#elif defined(IDMAP_LAZY_NEGATIVE)
    // Intentionally ill-formed: auto-add passes its named parameter by copy.
    IdMap<uint32_t, MoveOnly> negative(10, 12);
    negative.add(MoveOnly(1));
#else
    cases<IdMap>("ordered");
    lifetimes<IdMap>("ordered");
    cases<IdHashMap>("hash");
    lifetimes<IdHashMap>("hash");
#endif
    return 0;
  } catch (std::exception const& e) {
    std::cerr << "FAIL\t" << e.what() << '\n';
  } catch (...) {
    std::cerr << "FAIL\tunexpected nonstandard exception\n";
  }
  return 1;
}
