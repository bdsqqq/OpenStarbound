// Private implementation inclusion gives the test access to counters without
// adding a production setter or modifying a public/native object layout.
#include "reference.cpp"
#include <cstdio>
#include <type_traits>
int main() {
  static_assert(std::is_same<decltype(completed[0]), uint64_t&>::value, "typed counter");
  uint32_t action; size_t written;
  completed[0]=UINT64_MAX; completed[1]=UINT64_MAX;
  uint8_t live[4]{};
  if (span(live,SIZE_MAX) || pe_select(0,&action) || pe_escape(nullptr,0,nullptr,0,&written) || pe_completed(0) || pe_completed(1)) return 1;
  std::puts("unsigned counters wrap; numerical span overflow rejected");
}
