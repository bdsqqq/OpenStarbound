// Raw noexcept native leaf tests: no C++ exception crosses Rust. All pointers
// designate live known objects; corrupt scalar fields are restored before use.
#include "StarByteArray.hpp"
#include <array>
#include <cstdio>
#include <cstring>
#include <exception>
#ifndef STAR_USE_RUST_BYTE_ARRAY
#error empty_copy_leaf requires STAR_USE_RUST_BYTE_ARRAY
#endif
using namespace Star;

// Instrumented parent headers may carry testMode; production headers do not.
template <typename C> static auto mode(C& c, int) -> decltype(c.testMode = 36, void()) { c.testMode = 36; }
template <typename C> static void mode(C&, long) {}
static uint32_t copy(ByteArray& owner, char const* input, size_t count,
    uint64_t role, uint64_t offset, uint64_t length, uint64_t* out,
    bool busy = false, bool finished = false) {
  ByteArrayRust::NativeCtx c; c.owner = &owner; c.input = input;
  c.inputCount = count; c.busy = busy; c.finished = finished; mode(c, 0);
  return ByteArrayRust::nativeHost(&c, SB_BA_COPY_IN, role, offset, length, out);
}
int main(int argc, char** argv) {
  // "guards" runs the contrasting pre-existing contract independently.
  if (argc > 2 || (argc == 2 && std::strcmp(argv[1], "guards"))) return 2;
  try {
    ByteArray empty; uint64_t out = 99;
    if (argc == 1) {
      if (copy(empty, nullptr, 0, 0, 0, 0, &out) != 0 || out != 0 ||
          empty.size() != 0 || empty.capacity() != 0 || empty.ptr() != nullptr) return 1;
      ByteArray populated(4, 'K'); auto p = populated.ptr(); auto cap = populated.capacity();
      out = 99;
      if (copy(populated, nullptr, 0, 0, 4, 0, &out) != 0 || out != 0 ||
          populated.size() != 4 || populated.ptr() != p || populated.capacity() != cap ||
          std::memcmp(p, "KKKK", 4)) return 1;
    }
    std::array<char, 4> input{{'a', 'Z', '0', '9'}};
    ByteArray b(4, 'K'); auto p = b.ptr(); auto cap = b.capacity();
    out = 99;
    if (copy(b, input.data(), input.size(), 0, 0, 4, &out) != 0 || out != 0 ||
        b.size() != 4 || b.ptr() != p || b.capacity() != cap || std::memcmp(p, "aZ09", 4)) return 3;
    auto reject = [&](ByteArray& target, char const* src, size_t count,
        uint64_t role, uint64_t offset, uint64_t n) {
      out = 99;
      return copy(target, src, count, role, offset, n, &out) == 2 && out == 99;
    };
    if (!reject(empty, nullptr, 0, 0, 1, 0) ||
        !reject(b, nullptr, 0, 0, 5, 0) ||
        !reject(b, nullptr, 0, 5, 0, 0) ||
        !reject(b, nullptr, 0, 1, 0, 0) ||
        !reject(b, nullptr, 4, 0, 0, 1) ||
        !reject(b, input.data(), 0, 0, 0, 1) ||
        !reject(b, input.data(), 4, 0, UINT64_MAX, 2) ||
        !reject(b, input.data(), 4, 0, 1, UINT64_MAX)) return 4;
    ByteArrayNativeAccess::size(b) = cap + 1;
    bool rejected = reject(b, nullptr, 0, 0, 0, 0);
    ByteArrayNativeAccess::size(b) = 4;
    if (!rejected) return 5;
    // A null destination with positive size is rejected before memcpy.
    ByteArrayNativeAccess::data(b) = nullptr;
    rejected = reject(b, input.data(), 4, 0, 0, 1);
    ByteArrayNativeAccess::data(b) = p;
    if (!rejected) return 6;
    out = 99;
    if (copy(b, input.data(), 4, 0, 0, 1, nullptr) != 2 || out != 99) return 7;
    for (bool finished : {false, true}) {
      out = 99;
      if (copy(b, input.data(), 4, 0, 0, 1, &out, !finished, finished) != 2 || out != 99) return 7;
    }
    if (b.size() != 4 || b.ptr() != p || b.capacity() != cap || std::memcmp(p, "aZ09", 4) ||
        input != std::array<char, 4>{{'a', 'Z', '0', '9'}} ||
        empty.size() != 0 || empty.ptr() != nullptr || empty.capacity() != 0) return 8;
    std::puts("EMPTY_COPY_LEAF_GUARDS_PASS"); return 0;
  } catch (std::exception const& e) {
    std::fprintf(stderr, "EMPTY_COPY_LEAF_EXCEPTION %s\n", e.what()); return 10;
  }
}
