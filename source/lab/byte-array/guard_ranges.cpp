// Standalone regression against the real combined headers and linked core.
// Run guards on the old header FIRST (expected 0), then counts (old 1/new 0).
// No alias is dereferenced as uint64_t; safeOutput only classifies live storage.
#include "StarBufferHost.hpp"
#include "StarRustByteArray.h"
#include <array>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#if !defined(STAR_USE_RUST_BYTE_ARRAY) || !defined(STAR_USE_RUST_BUFFER)
#error guard_ranges requires the full combined ON header configuration
#endif
using namespace Star;
using Ctx = BufferRust::NativeCtx;
static void require(bool ok, char const* label) {
  if (!ok) throw std::runtime_error(label);
}
static uint64_t* alias(void const* p) {
  return reinterpret_cast<uint64_t*>(const_cast<void*>(p));
}
struct ArrayState {
  ByteArray& b;
  char* p;
  size_t n, capacity;
  std::string bytes;
  explicit ArrayState(ByteArray& v) : b(v), p(v.ptr()), n(v.size()),
      capacity(v.capacity()), bytes(p, n) {}
  bool unchanged() const {
    return b.ptr() == p && b.size() == n && b.capacity() == capacity &&
        std::memcmp(p, bytes.data(), n) == 0;
  }
};
static void classify(Ctx& c, uint64_t* out, bool accepted, char const* label) {
  // All four arrays have initialized logical bytes. Compare semantic state,
  // never padding or uninitialized spare capacity.
  ArrayState own(c.value), bound(*c.bytes), source(*c.moveSourceBytes), param(*c.param);
  auto result = c.result;
  auto args = std::array<uint64_t, 3>{{c.args[0], c.args[1], c.args[2]}};
  auto busy = c.busy, finished = c.finished;
  require(BufferRust::safeOutput(c, out) == accepted, label);
  require(own.unchanged() && bound.unchanged() && source.unchanged() && param.unchanged(),
      "guard mutated array");
  require(c.result == result && c.args[0] == args[0] && c.args[1] == args[1] &&
      c.args[2] == args[2] && c.busy == busy && c.finished == finished && !c.pending,
      "guard mutated context");
}
static void bind(Ctx& c, ByteArray& b, ByteArray& s, ByteArray& p) {
  c.bytes = &b; c.constBytes = &b;
  c.moveSourceBytes = &s; c.sourceBytes = &s; c.param = &p;
  c.value = ByteArray(32, 'V');
}
static uint64_t child(Ctx& parent, uint64_t, uint64_t) {
  require(parent.busy, "child must run inside parent callback");
  parent.bytes->resize(96, 'R');
  Ctx nested;
  bind(nested, *parent.bytes, *parent.moveSourceBytes, *parent.param);
  classify(nested, alias(parent.bytes->ptr() + 64), false, "fresh child range");
  uint64_t out = 99;
  require(BufferRust::nativeHost(&nested, SB_OP_ARG, 0, 0, &out) == 0 && out == 0,
      "fresh child host call");
  return 17;
}
static void guards() {
  ByteArray b(32, 'B'), s(32, 'S'), p(32, 'P');
  Ctx c; bind(c, b, s, p);
  alignas(uint64_t) std::array<unsigned char, 24> scratch{};
  uint64_t output = 99;
  classify(c, &output, true, "normal output");
  require(output == 99, "normal output changed");
  classify(c, nullptr, false, "null");
  classify(c, alias(scratch.data() + 1), false, "misaligned");
  classify(c, &c.result, false, "context");
  for (auto object : {&b, &s, &p, &c.value})
    classify(c, alias(object), false, "array object");
  Buffer owner, source;
  ExternalBuffer external;
  c.constOwner = &owner; c.source = &source; c.constExternal = &external;
  for (void const* object : {static_cast<void const*>(&owner),
      static_cast<void const*>(&source), static_cast<void const*>(&external)})
    classify(c, alias(object), false, "buffer object");
  for (auto array : {&b, &s, &p, &c.value}) {
    require(reinterpret_cast<uintptr_t>(array->ptr()) % alignof(uint64_t) == 0,
        "allocation alignment precondition");
    classify(c, alias(array->ptr()), false, "allocation start");
    classify(c, alias(array->ptr() + 24), false, "allocation last word");
    // Initialize before shrinking: the spare bytes remain allocated, and the
    // guard must keep its logical-span contract instead of excluding capacity.
    array->resize(64, 'T'); array->resize(32);
    classify(c, alias(array->ptr() + 32), true, "logical end in capacity");
    // Move a distinct live allocation in while the old allocation is live.
    // This guarantees relocation without inspecting any dangling pointer.
    ByteArray replacement(128, 'N');
    require(replacement.ptr() != array->ptr(), "distinct live allocation");
    *array = std::move(replacement);
    classify(c, alias(array->ptr() + 64), false, "relocated fresh range");
    array->resize(32);
  }
  c.child = child;
  output = 99;
  require(BufferRust::nativeHost(&c, SB_OP_CHILD, 0, 0, &output) == 0 &&
      output == 17 && !c.busy && !c.pending, "child reentry");
  require(b.size() == 96 && b[64] == 'R', "child mutation retained");
  std::puts("BUFFER_GUARD_RANGES_PASS");
}
using Counts = std::array<std::array<uint64_t, 3>, SB_BA_MODE_COUNT>;
static Counts snapshot() {
  Counts counts{};
  for (uint32_t m = 0; m < SB_BA_MODE_COUNT; ++m)
    for (uint32_t e = 0; e < 3; ++e)
      counts[m][e] = star_byte_array_call_count(m, e);
  return counts;
}
static int counts() {
  ByteArray b(32, 'B'), s(32, 'S'), p(32, 'P');
  Ctx c; bind(c, b, s, p);
  uint64_t out = 99;
  auto before = snapshot();
  bool accepted = BufferRust::safeOutput(c, &out);
  auto after = snapshot(); // No getters, cleanup, or assertions in the window.
  bool equal = before == after;
  for (uint32_t m = 0; m < SB_BA_MODE_COUNT; ++m)
    for (uint32_t e = 0; e < 3; ++e)
      if (before[m][e] != after[m][e])
        std::fprintf(stderr, "receipt mode=%u event=%u delta=%llu\n", m, e,
            static_cast<unsigned long long>(after[m][e] - before[m][e]));
  if (!accepted || out != 99 || !equal) return 1;
  std::puts("BUFFER_GUARD_COUNTS_PASS");
  return 0;
}
int main(int argc, char** argv) {
  if (argc != 2) return 2;
  try {
    if (!std::strcmp(argv[1], "guards")) { guards(); return 0; }
    if (!std::strcmp(argv[1], "counts")) return counts();
    return 2;
  } catch (std::exception const& e) {
    std::fprintf(stderr, "BUFFER_GUARD_FAIL %s\n", e.what());
    return 1;
  }
}
