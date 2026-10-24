#pragma once
#ifdef STAR_LINE_LAB_DIRECT_ABI
#include "StarRustLine.h"
#include <stdexcept>
#endif

// Candidate-only seam: the root C++ header currently implements these calls.
// When its optional Rust backend is linked, preserve the observation layout and
// frozen reference. No caller container/transform behavior is represented here.
struct Production {
  template <typename T>
  static Observation<T> query(Star::Line<T,2> const& a, Star::Line<T,2> const& b,
      Star::Vector<T,2> const& p, bool infinite) {
#ifdef STAR_LINE_LAB_DIRECT_ABI
    // Diagnostic-only boundary: production rejects fast-math, but the failed
    // candidate must remain replayable without changing the frozen reference.
    using I=std::conditional_t<sizeof(T)==4,StarLineInputF32,StarLineInputF64>;
    using R=std::conditional_t<sizeof(T)==4,StarLineResultF32,StarLineResultF64>;
    I input{{a.min()[0],a.min()[1]},{a.max()[0],a.max()[1]},
            {b.min()[0],b.min()[1]},{b.max()[0],b.max()[1]}};
    auto call=[&](uint32_t mode) {
      R r{};
      int32_t status;
      if constexpr(sizeof(T)==4)
        status=star_line_query_f32(&input,mode,infinite,STAR_LINE_LAB_POLICY,&r);
      else
        status=star_line_query_f64(&input,mode,infinite,STAR_LINE_LAB_POLICY,&r);
      if(status) throw std::runtime_error("diagnostic line ABI rejected query");
      return r;
    };
    auto r=call(0),predicate=call(0);
    input.c[0]=p[0]; input.c[1]=p[1];
    auto projection=call(1),distance=call(2);
    return {bool(r.intersects),bool(r.coincides),bool(r.glances),bool(predicate.intersects),
            r.point[0],r.point[1],r.t,projection.t,distance.t};
#else
    return observe<T>(a,b,p,infinite);
#endif
  }
};
