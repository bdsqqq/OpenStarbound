// Actual Rust-backed frame guards and public-route witness; no policy interpreter.
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <iostream>
#include <iterator>
#include <new>
#include <stdexcept>
#include <type_traits>
#include <utility>
#include "StaticVector.hpp"

namespace {
void need(bool value) {
  if (!value) throw std::logic_error("StaticVector frame guard witness failed");
}
struct Marker { int* identity; };
}
int main() {
  using namespace Star::StaticVectorFrames;
  using V = Star::StaticVector<int, 4>;
  uint64_t before[SB_STATIC_VECTOR_MODE_COUNT]{};
  for (uint32_t mode = 0; mode < SB_STATIC_VECTOR_MODE_COUNT; ++mode)
    before[mode] = sb_static_vector_count(mode, SB_STATIC_VECTOR_ROOT);
  {
    V a;
    V same(a);
    V filled(2, 7);
    V moved(std::move(filled));
    Star::StaticVector<int, 3> converted(a);
    V list{1, 2};
    V range(list.begin(), list.end());
    a = list;
    a = std::move(range);
    need(a.size() == 2 && !a.empty() && a.at(0) == 1 && a[1] == 2);
    a.resize(2);
    a.push_back(3);
    a.pop_back();
    a.insert(a.begin(), 4);
    int input[] = {8};
    a.insert(a.begin(), input, input + 1);
    a.erase(a.begin());
    a.insert(a.begin(), {5});
    a.erase(a.begin(), a.begin() + 2);
    a.emplace(a.begin(), 6);
    a.emplace_back(7);
    V twin(a);
    need(a == twin && !(a != twin) && !(a < twin));
    a.clear();
    Star::StaticVector<int, 0> zero;
    need(zero.empty());
    need(sizeof(zero) == 8 && sizeof(V) == 24 && alignof(V) == 8);
  }
  unsigned covered = 0;
  for (uint32_t mode = 0; mode < SB_STATIC_VECTOR_MODE_COUNT; ++mode) {
    auto delta = sb_static_vector_count(mode, SB_STATIC_VECTOR_ROOT) - before[mode];
    // Original dependent initializer_list::operator[] assignment cannot instantiate.
    if (mode == SB_STATIC_VECTOR_LIST_ASSIGN) need(delta == 0);
    else { need(delta > 0); ++covered; }
  }
  need(covered == 25 && sb_static_vector_count(SB_STATIC_VECTOR_LESS, SB_STATIC_VECTOR_CONTINUE) > 0);

  int touched = 0;
  auto frame = makeFrame([&](SbStaticVectorRequest const& r) {
    if (r.op != SB_STATIC_VECTOR_ASSERT_INDEX) return invalidReply();
    ++touched;
    return voidReply();
  });
  SbStaticVectorRequest good{32, 1, SB_STATIC_VECTOR_ASSERT_INDEX, 0, 0, 0};
  unsigned denied = 0;
  auto reject = [&](SbStaticVectorRequest const* request, SbStaticVectorReply* output) {
    need(frame.dispatch(request, output) == SB_STATIC_VECTOR_INVALID && touched == 0);
    ++denied;
  };
  auto out = invalidReply();
  reject(nullptr, &out);
  reject(&good, nullptr);
  need(decltype(frame)::host(nullptr, &good, &out) == SB_STATIC_VECTOR_INVALID); ++denied;
  need(decltype(frame)::host(reinterpret_cast<char*>(&frame) + 1, &good, &out) == SB_STATIC_VECTOR_INVALID); ++denied;
  alignas(SbStaticVectorRequest) unsigned char requestBytes[sizeof(SbStaticVectorRequest) + 8]{};
  alignas(SbStaticVectorReply) unsigned char replyBytes[sizeof(SbStaticVectorReply) + 8]{};
  reject(reinterpret_cast<SbStaticVectorRequest const*>(requestBytes + 1), &out);
  reject(&good, reinterpret_cast<SbStaticVectorReply*>(replyBytes + 1));
  for (unsigned field = 0; field < 7; ++field) {
    auto bad = good;
    switch (field) {
      case 0: bad.size = 31; break;
      case 1: bad.version = 2; break;
      case 2: bad.reserved = 1; break;
      case 3: bad.op = 0; break;
      case 4: bad.op = 41; break;
      case 5: bad.arg0 = 1; break;
      default: bad.arg1 = 1; break;
    }
    reject(&bad, &out);
  }
  auto unsupported = good; unsupported.op = SB_STATIC_VECTOR_READ_SIZE;
  reject(&unsupported, &out);
  need(out.tag == UINT32_MAX && touched == 0);
  need(frame.dispatch(&good, &out) == SB_STATIC_VECTOR_OK && touched == 1
       && out.tag == SB_STATIC_VECTOR_VOID && out.value == 0);
  auto acknowledgesThrow = makeFrame([](SbStaticVectorRequest const&) { return voidReply(); });
  auto throwing = good; throwing.op = SB_STATIC_VECTOR_THROW_POP;
  out = invalidReply();
  need(acknowledgesThrow.dispatch(&throwing, &out) == SB_STATIC_VECTOR_INVALID); ++denied;
  need(denied == 15);

  int token = 73;
  bool identity = false;
  auto marker = makeFrame([&](SbStaticVectorRequest const&) -> SbStaticVectorReply { throw Marker{&token}; });
  auto count = sb_static_vector_count(SB_STATIC_VECTOR_INDEX, SB_STATIC_VECTOR_ROOT);
  try { marker.run(SB_STATIC_VECTOR_INDEX); }
  catch (Marker const& e) {
    identity = e.identity == &token && std::current_exception() == marker.exception;
  }
  need(identity && sb_static_vector_count(SB_STATIC_VECTOR_INDEX, SB_STATIC_VECTOR_ROOT) == count + 1);
  std::cout << "{\"publicRoots\":" << covered
    << ",\"lessContinuation\":true,\"listAssignmentUnavailable\":true,\"denied\":" << denied
    << ",\"effects\":" << touched << ",\"exceptionIdentity\":true}\n";
}
