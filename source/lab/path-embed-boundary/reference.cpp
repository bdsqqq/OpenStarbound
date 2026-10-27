#include "boundary.h"
#include <limits>
namespace {
thread_local uint64_t completed[2] = {};
bool span(void const* p, size_t n, size_t alignment = 1) {
  uintptr_t a = reinterpret_cast<uintptr_t>(p);
  return (!n || p) && a % alignment == 0 && n <= UINTPTR_MAX - a;
}
bool overlap(void const* a, size_t an, void const* b, size_t bn) {
  if (!an || !bn) return false;
  auto x = reinterpret_cast<uintptr_t>(a), y = reinterpret_cast<uintptr_t>(b);
  return x < y + bn && y < x + an;
}
}
extern "C" uint32_t pe_span_eligible(size_t n, size_t capacity) {
  return n <= static_cast<size_t>(PTRDIFF_MAX) / 2 &&
    capacity <= static_cast<size_t>(PTRDIFF_MAX) && capacity >= n * 2;
}
extern "C" uint64_t pe_completed(uint32_t op) { return op < 2 ? completed[op] : 0; }
extern "C" uint32_t pe_select(uint32_t method, uint32_t* action) {
  if (method > 3 || !span(action, sizeof(*action), alignof(uint32_t))) return PE_INVALID;
  uint32_t selected;
  switch (method) {
    case 0: selected = PE_NONE; break;
    case 1: selected = PE_GZIP; break;
    case 2: selected = PE_ZLIB; break;
    case 3: selected = PE_ZSTD; break;
    default: return PE_INVALID;
  }
  *action = selected;
  ++completed[0];
  return PE_OK;
}
extern "C" uint32_t pe_escape(uint8_t const* input, size_t n, uint8_t* output, size_t capacity, size_t* written) {
  if (!pe_span_eligible(n, capacity) || !span(input, n) || !span(output, capacity) ||
      !span(written, sizeof(*written), alignof(size_t)) ||
      overlap(input, n, output, capacity) || overlap(input, n, written, sizeof(*written)) ||
      overlap(output, capacity, written, sizeof(*written))) return PE_INVALID;
  size_t len = 0;
  for (size_t i = 0; i < n; ++i) {
    uint8_t replacement;
    switch (input[i]) {
      case '%': replacement = '%'; break;
      case ':': replacement = 'c'; break;
      case '?': replacement = 'q'; break;
      case ';': replacement = 's'; break;
      case '/': replacement = 'b'; break;
      default: output[len++] = input[i]; continue;
    }
    output[len++] = '%'; output[len++] = replacement;
  }
  *written = len;
  ++completed[1];
  return PE_OK;
}
