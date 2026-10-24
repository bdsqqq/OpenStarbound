//! Lazy grid traversal; the C++ adapter owns exception capture, never this ABI.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

type Visitor = Option<unsafe extern "C" fn(*mut c_void, i32, i32) -> i32>;
thread_local! { static CALLS: Cell<u64> = const { Cell::new(0) }; }

#[no_mangle]
pub extern "C" fn star_blocks_along_line_call_count() -> u64 {
    CALLS.with(Cell::get)
}

fn boundary(f: impl FnOnce() -> i32) -> i32 {
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(status) => {
            if status <= 1 {
                CALLS.with(|c| c.set(c.get().wrapping_add(1)));
            }
            status
        }
        Err(_) => 3,
    }
}

fn floor_int(x: f64) -> Option<i64> {
    let f = x.floor();
    (f.is_finite() && f >= i32::MIN as f64 && f <= i32::MAX as f64).then_some(f as i64)
}

// i64 loop coordinates safely extend only the original undefined overflow suffix;
// setup validation still rejects arithmetic undefined before the first callback.
fn traverse(
    o: [f64; 2],
    d: [f64; 2],
    r: [f64; 2],
    policy: u32,
    mut visit: impl FnMut(i32, i32) -> bool,
) -> i32 {
    if policy > 2 || o.into_iter().chain(d).chain(r).any(|v| !v.is_finite()) {
        return 2;
    }
    let Some(x) = floor_int(o[0]) else { return 2 };
    let Some(y) = floor_int(o[1]) else { return 2 };
    let Some(rx) = floor_int(r[0]) else { return 2 };
    let Some(ry) = floor_int(r[1]) else { return 2 };
    let (dx, dy) = (d[0].abs(), d[1].abs());
    if dx == 0.0 || dy == 0.0 {
        let (mut a, end, fixed, vertical) = if dx == 0.0 {
            (y, ry, x, true)
        } else {
            (x, rx, y, false)
        };
        let step = if a < end { 1 } else { -1 };
        loop {
            let (vx, vy) = if vertical { (fixed, a) } else { (a, fixed) };
            if !visit(vx as i32, vy as i32) {
                return 1;
            }
            if a == end {
                return 0;
            }
            a += step;
        }
    }
    let xi = if d[0] > 0.0 { 1 } else { -1 };
    let yi = if d[1] > 0.0 { 1 } else { -1 };
    let nx = if xi > 0 { rx - x } else { x - rx };
    let ny = if yi > 0 { ry - y } else { y - ry };
    if nx < 0 || ny < 0 || 1 + nx > i32::MAX as i64 || 1 + nx + ny > i32::MAX as i64 {
        return 2;
    }
    // Recorded Apple clang 21 ARM -O3 -ffast-math emits (1-origin)+floor,
    // fmsub for the initial error, and a hoisted (dy-dx) for corner ties.
    // This is a per-call expression policy, not permission to enable Rust fast math.
    let xd = if xi > 0 {
        if policy == 1 {
            (1.0 - o[0]) + x as f64
        } else {
            x as f64 + 1.0 - o[0]
        }
    } else {
        o[0] - x as f64
    };
    let yd = if yi > 0 {
        if policy == 1 {
            (1.0 - o[1]) + y as f64
        } else {
            y as f64 + 1.0 - o[1]
        }
    } else {
        o[1] - y as f64
    };
    let mut error = if policy != 0 {
        (-yd).mul_add(dx, xd * dy)
    } else {
        xd * dy - yd * dx
    };
    let (mut x, mut y, mut n) = (x, y, 1 + nx + ny);
    while n > 0 {
        // Out-of-range cells can only occur in the C++ undefined suffix.
        if i32::try_from(x).is_err() || i32::try_from(y).is_err() {
            return 2;
        }
        if !visit(x as i32, y as i32) {
            return 1;
        }
        if error > 0.0 {
            y += yi;
            error -= dx;
        } else if error < 0.0 {
            x += xi;
            error += dy;
        } else {
            n -= 1;
            y += yi;
            x += xi;
            if policy == 1 {
                error += dy - dx;
            } else {
                error += dy;
                error -= dx;
            }
        }
        n -= 1;
    }
    0
}

macro_rules! entry {
    ($name:ident, $scalar:ty) => {
        /// # Safety
        /// The visitor/context must remain valid for this synchronous call. The
        /// visitor must not unwind across the C ABI, including on nested calls.
        #[no_mangle]
        pub unsafe extern "C" fn $name(
            ox: $scalar,
            oy: $scalar,
            dx: $scalar,
            dy: $scalar,
            policy: u32,
            visitor: Visitor,
            context: *mut c_void,
        ) -> i32 {
            boundary(|| {
                let Some(visitor) = visitor else { return 2 };
                // Addition MUST occur in Scalar before promotion to double.
                let r = [(ox + dx) as f64, (oy + dy) as f64];
                traverse(
                    [ox as f64, oy as f64],
                    [dx as f64, dy as f64],
                    r,
                    policy,
                    |x, y| visitor(context, x, y) != 0,
                )
            })
        }
    };
}
entry!(star_blocks_along_line_f32, f32);
entry!(star_blocks_along_line_f64, f64);

#[cfg(test)]
mod tests {
    use super::*;
    unsafe extern "C" fn stop(_: *mut c_void, _: i32, _: i32) -> i32 {
        0
    }
    #[test]
    fn statuses_and_thread_receipts() {
        let before = star_blocks_along_line_call_count();
        for args in [
            (f64::NAN, 0.0, 0.0, 0.0, 0),
            (1e100, 0.0, 0.0, 0.0, 0),
            (-2e9, -2e9, 4e9, 4e9, 0),
            (0.0, 0.0, 0.0, 0.0, 3),
        ] {
            assert_eq!(
                unsafe {
                    star_blocks_along_line_f64(
                        args.0,
                        args.1,
                        args.2,
                        args.3,
                        args.4,
                        Some(stop),
                        std::ptr::null_mut(),
                    )
                },
                2
            );
        }
        assert_eq!(
            unsafe {
                star_blocks_along_line_f32(0.0, 0.0, 0.0, 0.0, 0, None, std::ptr::null_mut())
            },
            2
        );
        assert_eq!(boundary(|| panic!("contained internal panic")), 3);
        assert_eq!(star_blocks_along_line_call_count(), before);
        std::thread::spawn(|| {
            assert_eq!(star_blocks_along_line_call_count(), 0);
            assert_eq!(
                unsafe {
                    star_blocks_along_line_f64(
                        -2e9,
                        0.0,
                        4e9,
                        0.0,
                        0,
                        Some(stop),
                        std::ptr::null_mut(),
                    )
                },
                1
            );
            assert_eq!(star_blocks_along_line_call_count(), 1);
        })
        .join()
        .unwrap();
        assert_eq!(star_blocks_along_line_call_count(), before);
    }
}
