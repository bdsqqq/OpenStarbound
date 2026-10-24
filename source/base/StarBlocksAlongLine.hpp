#pragma once

#include "StarVector.hpp"
#ifdef STAR_USE_RUST_BLOCKS_ALONG_LINE
#include "StarRustTraversal.h"
#include <exception>
#include <stdexcept>
#include <type_traits>
#endif

namespace Star {

// Iterate over integral cells based on Bresenham's line drawing algorithm.
// Returns false immediately when the callback returns false for any cell,
// returns true after iterating through every cell otherwise.
template <typename Scalar>
bool forBlocksAlongLine(Vector<Scalar, 2> origin, Vector<Scalar, 2> const& dxdy, function<bool(int, int)> callback) {
#ifdef STAR_USE_RUST_BLOCKS_ALONG_LINE
  if constexpr (std::is_same_v<Scalar, float> || std::is_same_v<Scalar, double>) {
    struct Context {
      function<bool(int, int)>& callback;
      std::exception_ptr exception;
    } context{callback, {}};
    // Never unwind through Rust. Rethrowing the saved pointer after return
    // preserves even non-standard exception object identity.
    auto visitor = +[](void* opaque, int32_t x, int32_t y) noexcept -> int32_t {
      auto& c = *static_cast<Context*>(opaque);
      try { return c.callback(x, y) ? 1 : 0; }
      catch (...) { c.exception = std::current_exception(); return 0; }
    };
    uint32_t policy = 0;
#if defined(STAR_RUST_TRAVERSAL_FP_PRECISE)
    // Pair with -ffp-contract=off for explicitly uncontracted callers.
    policy = 0;
#elif defined(__APPLE__) && defined(__aarch64__) && defined(__clang__) && __clang_major__ == 21
#ifdef __FAST_MATH__
    policy = 1;
#else
    policy = 2;
#endif
#elif defined(__FAST_MATH__)
#error Rust traversal fast-math policy is only calibrated for Apple clang 21 ARM
#endif
    int32_t status;
    if constexpr (std::is_same_v<Scalar, float>)
      status = star_blocks_along_line_f32(origin[0], origin[1], dxdy[0], dxdy[1], policy, visitor, &context);
    else
      status = star_blocks_along_line_f64(origin[0], origin[1], dxdy[0], dxdy[1], policy, visitor, &context);
    if (context.exception)
      std::rethrow_exception(context.exception);
    if (status == 2)
      throw std::invalid_argument("invalid Rust blocks-along-line input");
    if (status != 0 && status != 1)
      throw std::runtime_error("Rust blocks-along-line panic");
    return status == 0;
  }
#endif
  Vector<Scalar, 2> remote = origin + dxdy;

  double dx = dxdy[0];
  if (dx < 0)
    dx *= -1;

  double dy = dxdy[1];
  if (dy < 0)
    dy *= -1;

  double oxfloor = floor(origin[0]);
  double oyfloor = floor(origin[1]);
  double rxfloor = floor(remote[0]);
  double ryfloor = floor(remote[1]);

  if (dx == 0) {
    if (oyfloor < ryfloor) {
      for (int i = oyfloor; i <= ryfloor; ++i) {
        if (!callback(oxfloor, i))
          return false;
      }
    } else {
      for (int i = oyfloor; i >= ryfloor; --i) {
        if (!callback(oxfloor, i))
          return false;
      }
    }
    return true;

  } else if (dy == 0) {
    if (oxfloor < rxfloor) {
      for (int i = oxfloor; i <= rxfloor; ++i) {
        if (!callback(i, oyfloor))
          return false;
      }
    } else {
      for (int i = oxfloor; i >= rxfloor; --i) {
        if (!callback(i, oyfloor))
          return false;
      }
    }
    return true;

  } else {
    int x = oxfloor;
    int y = oyfloor;

    int n = 1;
    int x_inc, y_inc;
    double error;

    if (dxdy[0] > 0) {
      x_inc = 1;
      n += int(rxfloor) - x;
      error = (oxfloor + 1 - origin[0]) * dy;
    } else {
      x_inc = -1;
      n += x - int(rxfloor);
      error = (origin[0] - oxfloor) * dy;
    }

    if (dxdy[1] > 0) {
      y_inc = 1;
      n += int(ryfloor) - y;
      error -= (oyfloor + 1 - origin[1]) * dx;
    } else {
      y_inc = -1;
      n += y - int(ryfloor);
      error -= (origin[1] - oyfloor) * dx;
    }

    for (; n > 0; --n) {
      if (!callback(x, y))
        return false;

      if (error > 0) {
        y += y_inc;
        error -= dx;
      } else if (error < 0) {
        x += x_inc;
        error += dy;
      } else {
        --n;
        y += y_inc;
        x += x_inc;
        error += dy;
        error -= dx;
      }
    }
    return true;
  }
}

}
