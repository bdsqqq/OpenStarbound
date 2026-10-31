#pragma once
#include "StarNetGroupHost.hpp"
#include "StarRustNetMap.h"

namespace Star { namespace NetMapDetail {
template <typename Function>
bool run(uint32_t mode, uint64_t argument, Function&& function) {
  return NetGroupDetail::run(mode, argument, function, sb_net_map_run);
}
template <typename Function>
void run(uint32_t mode, Function&& function) {
  run(mode, 0, function);
}

// Construct/destroy native iterators around the nested controller, not inside
// optional<pair> callbacks: native range-for permits immovable iterators and
// throwing destructors. Keep comparison proxies in their contextual-if scope.
template <typename Container, typename Function>
bool withRange(uint32_t mode, uint64_t argument, Container& elements, Function&& function) {
  auto begin = elements.begin();
  auto end = elements.end();
  auto current = [&]() -> decltype(auto) { return *begin; };
  return run(mode, argument, [&](uint32_t leaf, uint64_t value, SbNetMapReply& reply) {
    switch (leaf) {
    case SB_NET_MAP_MORE:
      if (begin != end) reply.a = 1;
      else reply.a = 0;
      break;
    case SB_NET_MAP_ADVANCE: ++begin; break;
    default: function(leaf, value, current, reply); break;
    }
  });
}
} }
