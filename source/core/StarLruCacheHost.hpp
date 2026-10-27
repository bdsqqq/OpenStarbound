#pragma once

#include "StarRustLruCache.h"
#include "StarOrderedMap.hpp"
#include <exception>
#include <stdexcept>

namespace Star {
namespace LruCacheRust {

// per-call frame only: no change to cache layout or implicit copy/move behavior.
// the const entry points use only read leaves; mutating leaves are mode-gated.
template <typename OrderedMapType, uint32_t Mode>
struct Context {
  using Key = typename OrderedMapType::key_type;
  using Value = typename OrderedMapType::mapped_type;
  using Iterator = typename OrderedMapType::iterator;
  using Pair = typename OrderedMapType::value_type;

  OrderedMapType& map;
  size_t& maxSize;
  static constexpr uint32_t mode = Mode;
  uint32_t stage = SB_LRU_ROOT;
  uint64_t arg = 0;
  Key const* key = nullptr;
  Value* value = nullptr;
  Iterator* iterator = nullptr;
  Pair const* pair = nullptr;
  Value* reference = nullptr;
  function<bool(Key const&, Value&)>* filter = nullptr;
  void* producer = nullptr;
  uint32_t (*produce)(Context&) = nullptr;
  std::exception_ptr pending;

  Context(OrderedMapType const& map, size_t const& maxSize)
    : map(const_cast<OrderedMapType&>(map)), maxSize(const_cast<size_t&>(maxSize)) {}

  uint32_t resume(uint32_t nextStage) {
    auto old = stage;
    stage = nextStage;
    SbLruReply result{sizeof(SbLruReply), SB_LRU_VOID, 0};
    auto status = sb_lru_run(mode, nextStage, this, host, &result);
    stage = old;
    // Rust has returned. rethrow INSIDE the native owning scope so pair/producer
    // temporaries and iterators unwind (including uncaught_exceptions/reentry).
    // the enclosing noexcept host catches before its outer Rust frame resumes.
    if (status == 1 && pending)
      std::rethrow_exception(pending);
    if (!status && (result.size != sizeof(SbLruReply) || result.tag != SB_LRU_VOID || result.value))
      return 2;
    return status;
  }

  template <typename T>
  struct Borrow {
    T*& slot;
    Borrow(T*& slot, T& value) : slot(slot) { slot = &value; }
    ~Borrow() { slot = nullptr; }
  };

  uint32_t withPair(Pair const& pairValue) {
    Borrow<Pair const> guard(pair, pairValue);
    return resume(SB_LRU_PAIR);
  }

  SbLruReply execute() {
    SbLruReply result{sizeof(SbLruReply), UINT32_MAX, 0};
    auto status = sb_lru_run(mode, SB_LRU_ROOT, this, host, &result);
    if (status == 1 && pending)
      std::rethrow_exception(pending);
    uint32_t tag = SB_LRU_VOID;
    switch (mode) {
      case SB_LRU_MAX: case SB_LRU_SIZE: tag = SB_LRU_U64; break;
      case SB_LRU_REMOVE: tag = SB_LRU_BOOL; break;
      case SB_LRU_PTR: case SB_LRU_GET: tag = SB_LRU_REF; break;
      case SB_LRU_KEYS: tag = SB_LRU_KEY_LIST; break;
      case SB_LRU_VALUES: tag = SB_LRU_VALUE_LIST; break;
      default: break;
    }
    if (status || pending || result.size != sizeof(SbLruReply) || result.tag != tag
        || (tag == SB_LRU_BOOL && result.value > 1)
        || (tag != SB_LRU_U64 && tag != SB_LRU_BOOL && result.value)
        || (mode == SB_LRU_GET && !reference))
      throw std::logic_error("Rust LruCache ABI protocol failure");
    return result;
  }

  static uint32_t host(void* opaque, SbLruRequest const* request, SbLruReply* out) noexcept {
    if (!opaque || !request || !out || request->size != sizeof(SbLruRequest) || out->size != sizeof(SbLruReply))
      return 2;
    auto& c = *static_cast<Context*>(opaque);
    if (c.pending)
      return 1;
    if (request->op != SB_LRU_WRITE_MAX && request->arg)
      return 2;
    *out = {sizeof(SbLruReply), SB_LRU_VOID, 0};
    auto& map = c.map;
    try {
      switch (request->op) {
        case SB_LRU_ARG:
          if (c.stage || !(c.mode == SB_LRU_CTOR || c.mode == SB_LRU_LIMIT)) return 2;
          out->tag = SB_LRU_U64; out->value = c.arg; break;
        case SB_LRU_READ_MAX:
          if (c.stage) return 2;
          out->tag = SB_LRU_U64; out->value = c.maxSize; break;
        case SB_LRU_WRITE_MAX:
          if (c.stage || !(c.mode == SB_LRU_CTOR || c.mode == SB_LRU_LIMIT) || !request->arg) return 2;
          c.maxSize = request->arg; break;
        case SB_LRU_MAP_SIZE:
          if (c.stage) return 2;
          out->tag = SB_LRU_U64; out->value = map.size(); break;
        case SB_LRU_REMOVE_FIRST:
          if (c.stage || !(c.mode == SB_LRU_CTOR || c.mode == SB_LRU_LIMIT || c.mode == SB_LRU_GET)) return 2;
          map.removeFirst(); break;
        case SB_LRU_FIND_SCOPE: {
          if (c.stage || !c.key || !(c.mode == SB_LRU_PTR || c.mode == SB_LRU_SET || c.mode == SB_LRU_GET)) return 2;
          // lend the original local, not a default/copy-constructed ABI iterator.
          auto i = map.find(*c.key);
          Borrow<Iterator> guard(c.iterator, i);
          return c.resume(SB_LRU_FOUND);
        }
        case SB_LRU_FILTER_SCOPE: {
          if (c.stage || c.mode != SB_LRU_FILTER || !c.filter) return 2;
          auto p = std::begin(map);
          Borrow<Iterator> guard(c.iterator, p);
          return c.resume(SB_LRU_TRAVERSE);
        }
        case SB_LRU_IS_END:
          if (!c.iterator || !(c.stage == SB_LRU_FOUND || c.stage == SB_LRU_TRAVERSE)) return 2;
          out->tag = SB_LRU_BOOL; out->value = *c.iterator == map.end(); break;
        case SB_LRU_PROMOTE_ASSIGN:
          if (c.stage != SB_LRU_FOUND || !c.iterator || !(c.mode == SB_LRU_PTR || c.mode == SB_LRU_GET)) return 2;
          *c.iterator = map.toBack(*c.iterator); break;
        case SB_LRU_PROMOTE_DISCARD:
          if (c.stage != SB_LRU_FOUND || c.mode != SB_LRU_SET || !c.iterator) return 2;
          map.toBack(*c.iterator); break;
        case SB_LRU_REFERENCE:
          if (c.stage != SB_LRU_FOUND || !c.iterator || !(c.mode == SB_LRU_PTR || c.mode == SB_LRU_GET)) return 2;
          c.reference = &(*c.iterator)->second; break;
        case SB_LRU_ADD:
          // unused methods must not add Value requirements to another method:
          // e.g. constructing/reading a cache does not require Value assignment.
          if constexpr (Mode == SB_LRU_SET) {
            if (c.stage != SB_LRU_FOUND || !c.key || !c.value) return 2;
            map.add(*c.key, std::move(*c.value)); break;
          } else return 2;
        case SB_LRU_ASSIGN:
          if constexpr (Mode == SB_LRU_SET) {
            if (c.stage != SB_LRU_FOUND || !c.iterator || !c.value) return 2;
            (*c.iterator)->second = std::move(*c.value); break;
          } else return 2;
        case SB_LRU_REMOVE_KEY:
          if (c.stage || c.mode != SB_LRU_REMOVE || !c.key) return 2;
          out->tag = SB_LRU_BOOL; out->value = map.remove(*c.key); break;
        case SB_LRU_PAIR_SCOPE:
          if (c.stage != SB_LRU_FOUND || c.mode != SB_LRU_GET || !c.produce) return 2;
          return c.produce(c);
        case SB_LRU_INSERT_PAIR:
          if constexpr (Mode == SB_LRU_GET) {
            if (c.stage != SB_LRU_PAIR || !c.pair || !c.iterator) return 2;
            *c.iterator = map.insert(*c.pair).first; break;
          } else return 2;
        case SB_LRU_PREDICATE:
          if (c.stage != SB_LRU_TRAVERSE || !c.iterator || !c.filter) return 2;
          out->tag = SB_LRU_BOOL; out->value = (*c.filter)((*c.iterator)->first, (*c.iterator)->second); break;
        case SB_LRU_ERASE:
          if (c.stage != SB_LRU_TRAVERSE || !c.iterator) return 2;
          *c.iterator = map.erase(*c.iterator); break;
        case SB_LRU_NEXT:
          if (c.stage != SB_LRU_TRAVERSE || !c.iterator) return 2;
          ++*c.iterator; break;
        case SB_LRU_MAP_CLEAR:
          if (c.stage || c.mode != SB_LRU_CLEAR) return 2;
          map.clear(); break;
        default: return 2;
      }
      return 0;
    } catch (...) {
      c.pending = std::current_exception();
      return 1;
    }
  }
};

}
}
