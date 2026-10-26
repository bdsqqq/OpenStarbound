// Defined zero-copy contract, separate from the frozen legacy corpus. Legacy
// null/zero memcpy is not an equivalence oracle or sanitizer qualification.
#include "StarByteArray.hpp"
#include <cstdio>
#include <cstring>
#include <exception>
#include <utility>
using namespace Star;

static bool freshEmpty(ByteArray const& b) {
  return b.size() == 0 && b.capacity() == 0 && b.ptr() == nullptr;
}
static bool bytes(char const* p, char const* expected, size_t n) {
  for (size_t i = 0; i < n; ++i) if (p[i] != expected[i]) return false;
  return true;
}
int main(int argc, char** argv) {
  if (argc != 2) return 2;
  try {
    if (!std::strcmp(argv[1], "default")) {
      ByteArray source; ByteArray copy(source);
      if (!freshEmpty(source) || !freshEmpty(copy)) return 3;
    } else if (!std::strcmp(argv[1], "moved")) {
      ByteArray source(4, 'K'); auto p = source.ptr(); auto c = source.capacity();
      ByteArray taken(std::move(source)); ByteArray copy(source);
      if (!freshEmpty(source) || !freshEmpty(copy) || taken.ptr() != p ||
          taken.capacity() != c || taken.size() != 4 || !bytes(p, "KKKK", 4)) return 3;
    } else if (!std::strcmp(argv[1], "reserved")) {
      ByteArray source(4, 'Q'); auto p = source.ptr(); auto c = source.capacity();
      source.clear(); ByteArray copy(source);
      if (!freshEmpty(copy) || source.size() != 0 || source.ptr() != p ||
          source.capacity() != c || !bytes(p, "QQQQ", 4)) return 3;
    } else if (!std::strcmp(argv[1], "assignment")) {
      ByteArray source; ByteArray target(4, 'T');
      auto p = target.ptr(); auto c = target.capacity(); auto& result = (target = source);
      // clear retains initialized backing bytes, even though logical size is zero.
      if (&result != &target || !freshEmpty(source) || target.size() != 0 ||
          target.ptr() != p || target.capacity() != c || !bytes(p, "TTTT", 4)) return 3;
    } else if (!std::strcmp(argv[1], "append-empty")) {
      ByteArray b; b.append(nullptr, 0);
      if (!freshEmpty(b)) return 3;
    } else if (!std::strcmp(argv[1], "append-populated")) {
      ByteArray b(4, 'P'); auto p = b.ptr(); auto c = b.capacity();
      b.append(nullptr, 0);
      if (b.size() != 4 || b.ptr() != p || b.capacity() != c || !bytes(p, "PPPP", 4)) return 3;
    } else if (!std::strcmp(argv[1], "cstring")) {
      auto b = ByteArray::fromCString(""); if (!freshEmpty(b)) return 3;
    } else if (!std::strcmp(argv[1], "raw")) {
      ByteArray b(nullptr, size_t{0}); if (!freshEmpty(b)) return 3;
    } else if (!std::strcmp(argv[1], "self")) {
      ByteArray empty; auto& er = (empty = empty);
      ByteArray b(4, 'S'); auto p = b.ptr(); auto c = b.capacity(); auto& br = (b = b);
      if (&er != &empty || !freshEmpty(empty) || &br != &b || b.size() != 4 ||
          b.ptr() != p || b.capacity() != c || !bytes(p, "SSSS", 4)) return 3;
    } else if (!std::strcmp(argv[1], "nonempty")) {
      ByteArray source("aZ09", 4); auto p = source.ptr(); auto c = source.capacity();
      ByteArray copy(source);
      if (copy.size() != 4 || copy.capacity() < 4 || copy.ptr() == p ||
          !bytes(copy.ptr(), "aZ09", 4) || source.ptr() != p || source.capacity() != c ||
          source.size() != 4 || !bytes(p, "aZ09", 4)) return 3;
      copy[1] = '!';
      if (!bytes(copy.ptr(), "a!09", 4) || !bytes(p, "aZ09", 4)) return 3;
    } else return 2;
    std::puts("EMPTY_COPY_CASE_PASS"); return 0;
  } catch (std::exception const& e) {
    std::fprintf(stderr, "EMPTY_COPY_EXCEPTION %s\n", e.what()); return 10;
  }
}
