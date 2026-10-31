#pragma once
#include "StarNetGroupHost.hpp"
#include "StarRustNetDynamic.h"

namespace Star { namespace NetDynamicDetail {
template <typename Function>
void run(uint32_t mode, Function&& function) {
  NetGroupDetail::run(mode, 0, function, sb_net_dynamic_run);
}
template <typename Container, typename Function>
void withRange(uint32_t mode, Container& elements, Function&& function) {
  NetGroupDetail::withRange(mode, 0, elements, function, sb_net_dynamic_run);
}
} }
