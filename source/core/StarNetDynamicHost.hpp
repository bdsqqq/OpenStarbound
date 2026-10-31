#pragma once
#include "StarNetGroupHost.hpp"
#include "StarRustNetDynamic.h"

namespace Star { namespace NetDynamicDetail {
template <typename Function>
bool evaluate(uint32_t mode, uint64_t argument, Function&& function) {
  return NetGroupDetail::run(mode, argument, function, sb_net_dynamic_run);
}
template <typename Function>
void run(uint32_t mode, Function&& function) {
  evaluate(mode, 0, function);
}
template <typename Container, typename Function>
void withRange(uint32_t mode, Container& elements, Function&& function) {
  NetGroupDetail::withRange(mode, 0, elements, function, sb_net_dynamic_run);
}
} }
