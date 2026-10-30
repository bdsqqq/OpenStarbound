// LAB ONLY: protocol and native exception transport, not production map/game coverage.
// Link the parent's fresh Rust aggregate; do not provide a substitute sb_bimap_run.
#include "frame.hpp"
#include <iostream>
#include <cstring>
#include <vector>
#include <string>

namespace {
using namespace Star::BiMapFrames;

void require(bool condition, char const* expression, int line) {
  if (!condition)
    throw std::logic_error(std::string("frame test line ") + std::to_string(line) + ": " + expression);
}
#define REQUIRE(expression) require(bool(expression), #expression, __LINE__)

struct Totals {
  unsigned tests = 0;
  unsigned calls = 0;
  unsigned rustCalls = 0;
};

SbBiMapRequest request(uint32_t op = SB_BIMAP_HAS_LEFT) {
  return {32, SB_BIMAP_ABI_VERSION, op, 0, 0, 0};
}

struct NativeError : std::runtime_error {
  explicit NativeError(void const*& identity) : std::runtime_error("native left failure") {
    identity = this;
  }
  NativeError(NativeError const&) = delete;
  NativeError(NativeError&&) = delete;
};

struct UnwindEvent {
  std::vector<int>& events;
  ~UnwindEvent() noexcept { events.push_back(2); }
};

void malformed(Totals& totals) {
  auto frame = makeFrame([&](SbBiMapRequest const&) {
    ++totals.calls;
    return boolReply(true);
  });
  auto good = request();
  SbBiMapReply output;
  std::memset(&output, 0xa5, sizeof(output));
  unsigned char original[sizeof(output)];
  std::memcpy(original, &output, sizeof(output));
  auto const before = totals.calls;
  auto reject = [&](void* context, SbBiMapRequest const* input, SbBiMapReply* result) {
    REQUIRE(decltype(frame)::host(context, input, result) == SB_BIMAP_INVALID);
    REQUIRE(totals.calls == before);
    REQUIRE(std::memcmp(original, &output, sizeof(output)) == 0);
    ++totals.tests;
  };
  std::vector<SbBiMapRequest> bad;
  auto add = [&](auto change) { auto value = good; change(value); bad.push_back(value); };
  add([](auto& r) { r.size = 31; });
  add([](auto& r) { r.version = 2; });
  add([](auto& r) { r.op = 0; });
  add([](auto& r) { r.op = SB_BIMAP_OP_COUNT + 1; });
  add([](auto& r) { r.reserved = 1; });
  add([](auto& r) { r.arg0 = 1; });
  add([](auto& r) { r.arg1 = 1; });
  for (auto const& value : bad) reject(&frame, &value, &output);
  reject(nullptr, &good, &output);
  reject(&frame, nullptr, &output);
  reject(&frame, &good, nullptr);

  // Live aligned byte storage + 1 only: no object/payload access before rejection.
  static_assert(alignof(decltype(frame)) > 1, "context alignment control");
  alignas(decltype(frame)) unsigned char contextBytes[sizeof(frame) + 1] = {};
  alignas(SbBiMapRequest) unsigned char inputBytes[sizeof(SbBiMapRequest) + 1] = {};
  alignas(SbBiMapReply) unsigned char outputBytes[sizeof(SbBiMapReply) + 1];
  std::memset(outputBytes, 0x5a, sizeof(outputBytes));
  unsigned char saved[sizeof(outputBytes)];
  std::memcpy(saved, outputBytes, sizeof(saved));
  reject(contextBytes + 1, &good, &output);
  reject(&frame, reinterpret_cast<SbBiMapRequest const*>(inputBytes + 1), &output);
  reject(&frame, &good, reinterpret_cast<SbBiMapReply*>(outputBytes + 1));
  REQUIRE(std::memcmp(saved, outputBytes, sizeof(saved)) == 0);
  REQUIRE(!frame.exception);
}

void wrongTag(Totals& totals) {
  auto frame = makeFrame([&](SbBiMapRequest const&) {
    ++totals.calls;
    return sizeReply(7); // Valid envelope, wrong tag for HAS_LEFT.
  });
  auto output = boolReply(false);
  auto const original = output;
  ++totals.rustCalls;
  REQUIRE(sb_bimap_run(SB_BIMAP_MODE_HAS_LEFT, &frame, &decltype(frame)::host, &output)
      == SB_BIMAP_INVALID);
  REQUIRE(std::memcmp(&original, &output, sizeof(output)) == 0);
  REQUIRE(!frame.exception);
  bool caught = false;
  try {
    ++totals.rustCalls;
    (void)frame.run(SB_BIMAP_MODE_HAS_LEFT);
  } catch (std::logic_error const& e) {
    caught = true;
    REQUIRE(std::string(e.what()) == "Invalid BiMap boundary protocol");
  }
  REQUIRE(caught);
  ++totals.tests;
}

void cannotAcknowledgeThrow(Totals& totals) {
  std::vector<uint32_t> ops;
  auto frame = makeFrame([&](SbBiMapRequest const& r) {
    ++totals.calls;
    ops.push_back(r.op);
    if (r.op == SB_BIMAP_HAS_LEFT) return boolReply(true);
    return voidReply(); // Deliberately attempts to acknowledge THROW_LEFT.
  });
  bool caught = false;
  try {
    ++totals.rustCalls;
    (void)frame.run(SB_BIMAP_MODE_ADD);
  } catch (std::logic_error const& e) {
    caught = true;
    REQUIRE(std::string(e.what()) == "Invalid BiMap boundary protocol");
  }
  REQUIRE(caught);
  REQUIRE((ops == std::vector<uint32_t>{SB_BIMAP_HAS_LEFT, SB_BIMAP_THROW_LEFT}));
  REQUIRE(!frame.exception);
  ++totals.tests;
}

void nativeException(Totals& totals) {
  std::vector<uint32_t> ops;
  std::vector<int> events;
  ops.reserve(8);
  events.reserve(8); // The noexcept guard records without allocating during unwind.
  void const* identity = nullptr;
  auto frame = makeFrame([&](SbBiMapRequest const& r) -> SbBiMapReply {
    ++totals.calls;
    ops.push_back(r.op);
    if (r.op == SB_BIMAP_HAS_LEFT) return boolReply(true);
    REQUIRE(r.op == SB_BIMAP_THROW_LEFT);
    events.push_back(1);
    UnwindEvent guard{events};
    throw NativeError(identity); // C++17 prvalue: identity names the exception object.
  });
  bool caught = false;
  try {
    ++totals.rustCalls;
    (void)frame.run(SB_BIMAP_MODE_ADD);
  } catch (NativeError const& e) {
    caught = true;
    REQUIRE(&e == identity);
    REQUIRE(std::string(e.what()) == "native left failure");
    REQUIRE((events == std::vector<int>{1, 2}));
    events.push_back(3);
  }
  REQUIRE(caught);
  REQUIRE(bool(frame.exception));
  REQUIRE((events == std::vector<int>{1, 2, 3}));
  REQUIRE((ops == std::vector<uint32_t>{SB_BIMAP_HAS_LEFT, SB_BIMAP_THROW_LEFT}));
  auto const before = totals.calls;
  auto input = request();
  auto output = boolReply(false);
  auto const original = output;
  REQUIRE(decltype(frame)::host(&frame, &input, &output) == SB_BIMAP_EXCEPTION);
  REQUIRE(totals.calls == before);
  REQUIRE(std::memcmp(&original, &output, sizeof(output)) == 0);
  // A retained exception cannot be replaced or allow further native effects.
  caught = false;
  try {
    ++totals.rustCalls;
    (void)frame.run(SB_BIMAP_MODE_HAS_LEFT);
  } catch (NativeError const& e) {
    caught = true;
    REQUIRE(&e == identity);
  }
  REQUIRE(caught);
  REQUIRE(totals.calls == before);
  ++totals.tests;
}

void partialMutation(Totals& totals) {
  unsigned cleared = 0;
  std::vector<uint32_t> ops;
  auto frame = makeFrame([&](SbBiMapRequest const& r) -> SbBiMapReply {
    ++totals.calls;
    ops.push_back(r.op);
    if (r.op == SB_BIMAP_CLEAR_LEFT) {
      ++cleared;
      return voidReply();
    }
    REQUIRE(r.op == SB_BIMAP_CLEAR_RIGHT);
    throw 73; // Nonstandard native exception survives exception_ptr transport too.
  });
  bool caught = false;
  try {
    ++totals.rustCalls;
    (void)frame.run(SB_BIMAP_MODE_CLEAR);
  } catch (int value) {
    caught = true;
    REQUIRE(value == 73);
    REQUIRE(cleared == 1);
  }
  REQUIRE(caught);
  REQUIRE(cleared == 1);
  REQUIRE(bool(frame.exception));
  REQUIRE((ops == std::vector<uint32_t>{SB_BIMAP_CLEAR_LEFT, SB_BIMAP_CLEAR_RIGHT}));
  ++totals.tests;
}
} // namespace

int main() {
  try {
    Totals totals;
    malformed(totals);
    wrongTag(totals);
    cannotAcknowledgeThrow(totals);
    nativeException(totals);
    partialMutation(totals);
    std::cout << "{\"tests\":" << totals.tests << ",\"calls\":" << totals.calls
              << ",\"rust_calls\":" << totals.rustCalls << "}\n";
    return 0;
  } catch (std::exception const& e) {
    std::cerr << "frame test: " << e.what() << '\n';
  } catch (...) {
    std::cerr << "frame test: unexpected nonstandard exception\n";
  }
  return 1;
}
