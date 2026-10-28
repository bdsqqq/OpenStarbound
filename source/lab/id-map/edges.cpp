// Separate finite edge contract; baseline native.cpp/model.py remain immutable.
#ifdef IDMAP_EDGE_MUTANT_HEADER
#include "StarIdMap.edge-mutant.hpp"
#else
#include "StarIdMap.hpp"
#endif
#include "StarDataStreamDevices.hpp"

#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <typeinfo>

#if !defined(STAR_LITTLE_ENDIAN) || !STAR_LITTLE_ENDIAN
#error "IdMap partial-scalar edge requires the admitted STAR_LITTLE_ENDIAN native profile"
#endif

using namespace Star;
namespace {
void check(bool condition, char const* why) {
  if (!condition)
    throw std::runtime_error(why);
}
void row(std::string const& backend, char const* name, std::string const& actual,
    char const* expected) {
  if (actual != expected)
    throw std::runtime_error(backend + "/" + name + ": expected " + expected + ", got " + actual);
  std::cout << "CASE\t" << backend << '/' << name << '\t' << actual << '\n';
}
void property(std::string const& backend, char const* name) {
  std::cout << "PASS\t" << backend << '/' << name << '\n';
}
std::string hex(ByteArray const& bytes) {
  static char const digits[] = "0123456789abcdef";
  std::string result;
  for (unsigned char byte : bytes) {
    result += digits[byte >> 4];
    result += digits[byte & 15];
  }
  return result;
}
template <size_t N>
ByteArray packet(uint8_t const (&bytes)[N]) {
  return ByteArray(reinterpret_cast<char const*>(bytes), N);
}
template <typename F>
std::string idFailure(F action) {
  try {
    action();
  } catch (IdMapException const& e) {
    check(typeid(e) == typeid(IdMapException), "exact IdMapException dynamic type");
    return e.what();
  }
  throw std::runtime_error("missing IdMapException");
}

struct CopyFailure { void const* identity; };
struct Payload {
  static int live, made, destroyed, copyAttempts, token;
  static bool throwOnCopy;
  int value;
  explicit Payload(int v) : value(v) { ++live; ++made; }
  Payload(Payload const& other) : value(other.value) {
    ++copyAttempts;
    if (throwOnCopy)
      throw CopyFailure{&token};
    ++live;
    ++made;
  }
  // Copyable even when the flat hash bucket/vector chooses copying on growth.
  Payload(Payload&& other) : value(other.value) { ++live; ++made; }
  Payload& operator=(Payload const&) = default;
  Payload& operator=(Payload&&) = default;
  ~Payload() { --live; ++destroyed; }
};
int Payload::live = 0;
int Payload::made = 0;
int Payload::destroyed = 0;
int Payload::copyAttempts = 0;
int Payload::token = 0;
bool Payload::throwOnCopy = false;

template <template <class, class> class MapType>
void edges(std::string const& backend) {
  using M = MapType<uint32_t, uint32_t>;
  check(Payload::live == 0 && Payload::made == Payload::destroyed, "payload conservation at entry");
  {
    MapType<uint32_t, Payload> map(10, 12);
    map.add(12, Payload(7));
    Payload existing(9);
    auto attempts = Payload::copyAttempts;
    Payload::throwOnCopy = true;
    bool caught = false;
    try {
      // This lvalue copy initializes the OUTER by-value argument, before add's body.
      map.add(existing);
    } catch (CopyFailure const& e) {
      caught = e.identity == &Payload::token;
    }
    Payload::throwOnCopy = false;
    check(caught && Payload::copyAttempts == attempts + 1, "outer argument exception identity");
    check(map.size() == 1 && map.get(12).value == 7 && existing.value == 9, "outer failure preserves existing data");
    auto next = map.nextId();
    row(backend, "outer-argument-copy", "identity-preserved,cursor=" + std::to_string(next) + ",size=" + std::to_string(map.size()),
        "identity-preserved,cursor=10,size=1");
    check(Payload::made - Payload::destroyed == Payload::live, "payload live conservation");
  }
  check(Payload::live == 0 && Payload::made == Payload::destroyed, "payload conservation after outer failure");
  property(backend, "outer-copy-identity-and-conservation");

  // Independent raw packet: two identical keys, different values, then metadata.
  uint8_t const duplicate[] = {
    0x02,
    0x00, 0x00, 0x00, 0x0b, 0x00, 0x00, 0x00, 0x4d,
    0x00, 0x00, 0x00, 0x0b, 0x00, 0x00, 0x00, 0x63,
    0x00, 0x00, 0x00, 0x0a,
    0x00, 0x00, 0x00, 0x0c,
    0x00, 0x00, 0x00, 0x0a
  };
  DataStreamBuffer duplicateStream(packet(duplicate));
  M loaded(40, 44);
  loaded.add(42, 5);
  duplicateStream >> loaded;
  check(duplicateStream.atEnd() && duplicateStream.pos() == sizeof(duplicate), "duplicate packet fully consumed");
  check(!loaded.contains(42), "stream clears old contents");
  auto next = loaded.nextId();
  row(backend, "duplicate-stream-first-wins", "size=" + std::to_string(loaded.size()) + ",value=" + std::to_string(loaded.get(11)) + ",next=" + std::to_string(next),
      "size=1,value=77,next=10");

  uint8_t const outsideCursor[] = {
    0x00,
    0x00, 0x00, 0x00, 0x0a,
    0x00, 0x00, 0x00, 0x0c,
    0x00, 0x00, 0x00, 0x63
  };
  DataStreamBuffer cursorStream(packet(outsideCursor));
  M cursor(40, 44);
  cursorStream >> cursor;
  auto first = cursor.nextId();
  auto second = cursor.nextId();
  row(backend, "loaded-outside-cursor", std::to_string(first) + "," + std::to_string(second), "99,10");
  check(cursor.empty(), "nextId still does not reserve loaded cursor");

  M partial(0x11223344u, 0x55667788u);
  partial.add(0x11223346u, 55);
  check(partial.nextId() == 0x11223344u, "partial setup cursor");
  uint8_t const prefix[] = {0x00, 0x01, 0x02};
  DataStreamBuffer truncated(packet(prefix));
  bool eof = false;
  try {
    truncated >> partial;
  } catch (EofException const& e) {
    check(typeid(e) == typeid(EofException), "exact EofException at partial primitive read");
    eof = true;
  }
  check(eof && partial.empty(), "partial metadata read clears map before failure");
  check(truncated.pos() == 3, "partial primitive read consumes available two bytes");
  DataStreamBuffer after;
  after << partial;
  row(backend, "partial-metadata-little-endian", hex(after.data()) + ",pos=" + std::to_string(truncated.pos()),
      "00112202015566778811223345,pos=3");
  property(backend, "native-partial-scalar-before-conversion");

  MapType<uint8_t, uint32_t> printable(uint8_t(64), uint8_t(67));
  printable.add(uint8_t(65), 1);
  row(backend, "printable-uint8-duplicate", idFailure([&] { printable.add(uint8_t(65), 2); }),
      "(IdMapException) IdMapWrapper::add(id, value) called with pre-existing id 'A'");
  check(printable.get(uint8_t(65)) == 1, "printable duplicate does not replace");

  M outside(10, 12);
  outside.add(99, 1);
  outside.add(100, 2);
  outside.add(101, 3);
  check(!outside.contains(10) && !outside.contains(11) && !outside.contains(12), "range remains free");
  row(backend, "outside-keys-exhaustion", idFailure([&] { outside.nextId(); }),
      "(IdMapException) No id space left in IdMapWrapper");
  check(outside.size() == 3, "outside keys retained after exhaustion");
  property(backend, "unvalidated-load-and-explicit-keys");
}
}

int main() {
  try {
    // Check the actual object representation as well as the required build macro.
    uint32_t const endianProbe = 1;
    check(*reinterpret_cast<unsigned char const*>(&endianProbe) == 1, "native host must be little-endian");
    edges<IdMap>("ordered");
    edges<IdHashMap>("hash");
    return 0;
  } catch (std::exception const& e) {
    std::cerr << "FAIL\t" << e.what() << '\n';
  } catch (...) {
    std::cerr << "FAIL\tunexpected nonstandard exception\n";
  }
  return 1;
}
