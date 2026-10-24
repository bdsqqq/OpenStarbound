//! Scalar 2D line queries. Arithmetic policies are local to each call, never global.
use std::cell::Cell;
use std::ops::{Add, Div, Mul, Neg, Sub};
use std::panic::{catch_unwind, AssertUnwindSafe};

#[repr(C)]
#[derive(Clone, Copy, Debug)]
pub struct LineInput<T> {
    pub a: [T; 2],
    pub b: [T; 2],
    pub c: [T; 2],
    pub d: [T; 2],
}
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct LineResult<T> {
    pub point: [T; 2],
    pub t: T,
    pub intersects: u32,
    pub coincides: u32,
    pub glances: u32,
}

trait Scalar:
    Copy
    + PartialOrd
    + Add<Output = Self>
    + Sub<Output = Self>
    + Mul<Output = Self>
    + Div<Output = Self>
    + Neg<Output = Self>
{
    const ZERO: Self;
    const ONE: Self;
    const MAX: Self;
    const NEAR_ZERO: Self;
    const EPS: Self;
    const DOUBLE: bool;
    fn abs(self) -> Self;
    fn sqrt(self) -> Self;
    fn fma(self, b: Self, c: Self) -> Self;
    fn min_num(self, b: Self) -> Self;
    fn max_num(self, b: Self) -> Self;
}
impl Scalar for f32 {
    const ZERO: Self = 0.0;
    const ONE: Self = 1.0;
    const MAX: Self = Self::MAX;
    const NEAR_ZERO: Self = 2.0 * Self::MIN_POSITIVE;
    const EPS: Self = Self::EPSILON;
    const DOUBLE: bool = false;
    fn abs(self) -> Self {
        self.abs()
    }
    fn sqrt(self) -> Self {
        self.sqrt()
    }
    fn fma(self, b: Self, c: Self) -> Self {
        self.mul_add(b, c)
    }
    fn min_num(self, b: Self) -> Self {
        self.min(b)
    }
    fn max_num(self, b: Self) -> Self {
        self.max(b)
    }
}
impl Scalar for f64 {
    const ZERO: Self = 0.0;
    const ONE: Self = 1.0;
    const MAX: Self = Self::MAX;
    const NEAR_ZERO: Self = 2.0 * Self::MIN_POSITIVE;
    const EPS: Self = Self::EPSILON;
    const DOUBLE: bool = true;
    fn abs(self) -> Self {
        self.abs()
    }
    fn sqrt(self) -> Self {
        self.sqrt()
    }
    fn fma(self, b: Self, c: Self) -> Self {
        self.mul_add(b, c)
    }
    fn min_num(self, b: Self) -> Self {
        self.min(b)
    }
    fn max_num(self, b: Self) -> Self {
        self.max(b)
    }
}
fn sub<T: Scalar>(a: [T; 2], b: [T; 2]) -> [T; 2] {
    [a[0] - b[0], a[1] - b[1]]
}
// Match Array's ordered comparisons even when an element is unordered (NaN).
fn less<T: Scalar>(a: [T; 2], b: [T; 2]) -> bool {
    for i in 0..2 {
        if a[i] < b[i] {
            return true;
        }
        if b[i] < a[i] {
            return false;
        }
    }
    false
}
fn le<T: Scalar>(a: [T; 2], b: [T; 2]) -> bool {
    for i in 0..2 {
        if a[i] < b[i] {
            return true;
        }
        if b[i] < a[i] {
            return false;
        }
    }
    true
}
fn near_zero<T: Scalar>(a: T) -> bool {
    a.abs() <= T::NEAR_ZERO
}
fn near_one<T: Scalar>(a: T, policy: u32) -> bool {
    let abs = a.abs();
    // std::max returns its first operand when unordered. fast ARM uses fmaxnm.
    let scale = if policy == 1 {
        abs.max_num(T::ONE)
    } else if abs < T::ONE {
        T::ONE
    } else {
        abs
    };
    (a - T::ONE).abs() <= T::EPS * scale
}
fn cross<T: Scalar>(a: [T; 2], b: [T; 2], policy: u32) -> T {
    if policy == 0 {
        a[0] * b[1] - a[1] * b[0]
    } else if policy == 1 && T::DOUBLE {
        (-a[1]).fma(b[0], a[0] * b[1])
    } else {
        a[0].fma(b[1], -(a[1] * b[0]))
    }
}
fn empty<T: Scalar>() -> LineResult<T> {
    LineResult {
        point: [T::ZERO; 2],
        t: T::ZERO,
        intersects: 0,
        coincides: 0,
        glances: 0,
    }
}
fn intersection<T: Scalar>(i: LineInput<T>, infinite: bool, policy: u32) -> LineResult<T> {
    let LineInput { a, b, c, d } = i;
    let ab = sub(b, a);
    let cd = sub(d, c);
    // Fast clang materializes both products before the parallel comparison.
    let denom = cross(ab, cd, if policy == 1 { 0 } else { policy });
    let mut r = empty();
    if near_zero(denom) {
        let axb = cross(a, b, policy);
        let cxd = cross(c, d, policy);
        let xn = if policy == 2 {
            axb.fma(cd[0], -(cxd * ab[0]))
        } else {
            axb * cd[0] - cxd * ab[0]
        };
        let yn = if policy == 2 {
            axb.fma(cd[1], -(cxd * ab[1]))
        } else {
            axb * cd[1] - cxd * ab[1]
        };
        if near_zero(xn) && near_zero(yn) {
            r.intersects = (infinite || (le(c, a) && le(a, d)) || (le(a, c) && le(c, b))) as u32;
            if r.intersects != 0 {
                r.point = if infinite {
                    [-T::MAX; 2]
                } else if less(a, c) {
                    c
                } else {
                    a
                };
            }
            let endpoint = if less(a, c) {
                Some(c)
            } else if less(d, a) {
                Some(d)
            } else {
                None
            };
            if let Some(e) = endpoint {
                r.t = if e[0] != a[0] {
                    (e[0] - a[0]) / ab[0]
                } else {
                    (e[1] - a[1]) / ab[1]
                };
            }
            r.coincides = 1;
            r.glances = r.intersects;
        } else {
            r.t = T::MAX;
        }
    } else {
        let ca = sub(c, a);
        let na = cross(ca, cd, policy);
        let nb = cross(ca, ab, policy);
        // Fast f64 clang shares a reciprocal between the two lane products.
        let (ta, tb) = if policy == 1 && T::DOUBLE {
            let reciprocal = T::ONE / denom;
            (na * reciprocal, nb * reciprocal)
        } else {
            (na / denom, nb / denom)
        };
        r.intersects =
            (infinite || (ta >= T::ZERO && ta <= T::ONE && tb >= T::ZERO && tb <= T::ONE)) as u32;
        r.t = ta;
        r.point = if policy == 0 {
            [ta * ab[0] + a[0], ta * ab[1] + a[1]]
        } else {
            [ta.fma(ab[0], a[0]), ta.fma(ab[1], a[1])]
        };
        r.glances = (!infinite
            && r.intersects != 0
            && (near_zero(ta) || near_one(ta, policy) || near_zero(tb) || near_one(tb, policy)))
            as u32;
    }
    r
}
fn projection<T: Scalar>(i: LineInput<T>, policy: u32) -> T {
    let d = sub(i.b, i.a);
    let c = sub(i.c, i.a);
    let fused = policy != 0;
    let numerator = if fused {
        c[0].fma(d[0], c[1] * d[1])
    } else {
        c[0] * d[0] + c[1] * d[1]
    };
    let denominator = if policy == 1 && fused {
        d[1].fma(d[1], d[0] * d[0])
    } else {
        (T::ZERO + d[0] * d[0]) + d[1] * d[1]
    };
    numerator / denominator
}
fn query<T: Scalar>(i: LineInput<T>, mode: u32, infinite: bool, policy: u32) -> LineResult<T> {
    if mode == 0 {
        return intersection(i, infinite, policy);
    }
    let mut r = empty();
    let mut t = projection(i, policy);
    if mode == 1 {
        r.t = t;
        return r;
    }
    if !infinite {
        // Preserve std::min(std::max(t,0),1)'s operand ordering, including NaN.
        t = if policy == 1 {
            t.max_num(T::ZERO).min_num(T::ONE)
        } else {
            let t = if t < T::ZERO { T::ZERO } else { t };
            if T::ONE < t {
                T::ONE
            } else {
                t
            }
        };
    }
    let d = sub(i.b, i.a);
    // Default contraction leaves the Vector eval multiply/add separate; fast
    // clang contracts it. The subsequent subtraction is never fused here.
    let eval = if policy == 1 {
        [d[0].fma(t, i.a[0]), d[1].fma(t, i.a[1])]
    } else {
        [i.a[0] + d[0] * t, i.a[1] + d[1] * t]
    };
    let delta = sub(i.c, eval);
    r.t = ((T::ZERO + delta[0] * delta[0]) + delta[1] * delta[1]).sqrt();
    r
}

thread_local! { static CALLS: Cell<u64> = const { Cell::new(0) }; }
#[no_mangle]
pub extern "C" fn star_line_query_call_count() -> u64 {
    CALLS.with(Cell::get)
}
fn boundary<T>(f: impl FnOnce() -> T) -> Result<T, i32> {
    catch_unwind(AssertUnwindSafe(f)).map_err(|_| 3)
}
fn range<T>(p: *const T) -> Option<(usize, usize)> {
    let start = p as usize;
    if p.is_null() || !start.is_multiple_of(std::mem::align_of::<T>()) {
        return None;
    }
    Some((start, start.checked_add(std::mem::size_of::<T>())?))
}
/// Pointers must designate live initialized input and exclusively writable output
/// allocations of their declared types. Address checks cannot prove provenance.
unsafe fn dispatch<T: Scalar>(
    input: *const LineInput<T>,
    mode: u32,
    infinite: u32,
    policy: u32,
    output: *mut LineResult<T>,
) -> i32 {
    let Some((is, ie)) = range(input) else {
        return 2;
    };
    let Some((os, oe)) = range(output) else {
        return 2;
    };
    if mode > 2 || infinite > 1 || policy > 2 || (is < oe && os < ie) {
        return 2;
    }
    // Do not create references before structural validation; compute locally so
    // neither invalid arguments nor a contained panic partially writes output.
    match boundary(|| query(unsafe { input.read() }, mode, infinite != 0, policy)) {
        Ok(result) => {
            unsafe {
                output.write(result);
            }
            CALLS.with(|c| c.set(c.get().wrapping_add(1)));
            0
        }
        Err(status) => status,
    }
}
/// # Safety
/// See StarRustLine.h for allocation, borrow and lifetime obligations.
#[no_mangle]
pub unsafe extern "C" fn star_line_query_f32(
    input: *const LineInput<f32>,
    mode: u32,
    infinite: u32,
    policy: u32,
    output: *mut LineResult<f32>,
) -> i32 {
    unsafe { dispatch(input, mode, infinite, policy, output) }
}
/// # Safety
/// See StarRustLine.h for allocation, borrow and lifetime obligations.
#[no_mangle]
pub unsafe extern "C" fn star_line_query_f64(
    input: *const LineInput<f64>,
    mode: u32,
    infinite: u32,
    policy: u32,
    output: *mut LineResult<f64>,
) -> i32 {
    unsafe { dispatch(input, mode, infinite, policy, output) }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn input<T: Copy>(a: [T; 2], b: [T; 2], c: [T; 2], d: [T; 2]) -> LineInput<T> {
        LineInput { a, b, c, d }
    }
    #[test]
    fn intersection_flags_points_and_order() {
        for p in 0..3 {
            let i = input([0.0f64, 0.0], [2.0, 2.0], [0.0, 2.0], [2.0, 0.0]);
            assert_eq!(
                intersection(i, false, p),
                LineResult {
                    point: [1.0, 1.0],
                    t: 0.5,
                    intersects: 1,
                    coincides: 0,
                    glances: 0
                }
            );
            let i = input([0.0f32, 0.0], [2.0, 0.0], [2.0, 0.0], [2.0, 2.0]);
            assert_eq!(intersection(i, false, p).glances, 1);
            let i = input([0.0f64, 0.0], [2.0, 0.0], [1.0, 0.0], [3.0, 0.0]);
            let r = intersection(i, false, p);
            assert_eq!(
                (r.point, r.t, r.intersects, r.coincides, r.glances),
                ([1.0, 0.0], 0.5, 1, 1, 1)
            );
            assert_eq!(intersection(i, true, p).point, [-f64::MAX; 2]);
            let reversed = input([2.0f64, 0.0], [0.0, 0.0], [1.0, 0.0], [3.0, 0.0]);
            assert_eq!(intersection(reversed, false, p).point, [2.0, 0.0]);
            let disjoint = input([0.0f32, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]);
            let r = intersection(disjoint, false, p);
            assert_eq!(
                (r.intersects, r.coincides, r.point, r.t),
                (0, 1, [0.0; 2], 2.0)
            );
            let parallel = input([0.0f64, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]);
            assert_eq!(intersection(parallel, false, p).t, f64::MAX);
        }
    }
    #[test]
    fn projection_distance_zero_and_thresholds() {
        assert!(near_zero(2.0 * f32::MIN_POSITIVE));
        assert!(!near_zero(3.0 * f32::MIN_POSITIVE));
        assert!(!near_zero(f32::EPSILON));
        assert!(near_one(1.0 + f64::EPSILON, 0));
        for p in 0..3 {
            let i = input([0.0f64, 0.0], [2.0, 0.0], [3.0, 4.0], [0.0; 2]);
            assert_eq!(query(i, 1, false, p).t, 1.5);
            assert_eq!(query(i, 2, true, p).t, 4.0);
            assert_eq!(query(i, 2, false, p).t, 17.0f64.sqrt());
            let z = input([0.0f32; 2], [0.0; 2], [1.0, 0.0], [0.0; 2]);
            assert!(query(z, 1, false, p).t.is_nan());
            assert_eq!(query(z, 2, false, p).t.is_nan(), p != 1);
            let z = input([0.0f64; 2], [0.0; 2], [0.0, 1.0], [0.0; 2]);
            assert_eq!(intersection(z, false, p).t, f64::INFINITY);
        }
    }
    #[test]
    fn abi_validation_sentinel_receipts_and_panic() {
        let i = input([0.0f32; 2], [1.0, 0.0], [0.5, 1.0], [0.5, -1.0]);
        let mut o = empty::<f32>();
        o.t = 123.0;
        let before = star_line_query_call_count();
        unsafe {
            assert_eq!(star_line_query_f32(std::ptr::null(), 0, 0, 0, &mut o), 2);
            assert_eq!(star_line_query_f32(&i, 3, 0, 0, &mut o), 2);
            assert_eq!(star_line_query_f32(&i, 0, 2, 0, &mut o), 2);
            assert_eq!(star_line_query_f32(&i, 0, 0, 3, &mut o), 2);
            assert_eq!(star_line_query_f32(&i, 0, 0, 0, std::ptr::null_mut()), 2);
            assert_eq!(
                star_line_query_f32(
                    &i,
                    0,
                    0,
                    0,
                    (&mut o as *mut LineResult<f32>).cast::<u8>().add(1).cast()
                ),
                2
            );
            assert_eq!(
                star_line_query_f32(
                    (&i as *const LineInput<f32>).cast::<u8>().add(1).cast(),
                    0,
                    0,
                    0,
                    &mut o
                ),
                2
            );
            assert_eq!(
                star_line_query_f32(&i, 0, 0, 0, (&i as *const LineInput<f32>).cast_mut().cast()),
                2
            );
        }
        assert_eq!(o.t, 123.0);
        assert_eq!(star_line_query_call_count(), before);
        assert_eq!(boundary::<()>(|| panic!("contained")), Err(3));
        assert_eq!(star_line_query_call_count(), before);
        assert_eq!(unsafe { star_line_query_f32(&i, 0, 0, 0, &mut o) }, 0);
        assert_eq!(star_line_query_call_count(), before + 1);
        std::thread::spawn(|| {
            assert_eq!(star_line_query_call_count(), 0);
            let i = input([0.0f64; 2], [1.0, 0.0], [0.5, 1.0], [0.5, -1.0]);
            let mut o = empty();
            assert_eq!(unsafe { star_line_query_f64(&i, 0, 0, 0, &mut o) }, 0);
            assert_eq!(star_line_query_call_count(), 1);
        })
        .join()
        .unwrap();
        assert_eq!(star_line_query_call_count(), before + 1);
        // Finite inputs can overflow intermediates. This remains a successful
        // observation, never an invalid-input status.
        let huge = input([-f32::MAX, 0.0], [f32::MAX, 0.0], [0.0; 2], [0.0; 2]);
        assert_eq!(unsafe { star_line_query_f32(&huge, 1, 0, 0, &mut o) }, 0);
        assert!(o.t.is_nan());
        assert_eq!(star_line_query_call_count(), before + 2);
        assert_eq!(std::mem::size_of::<LineResult<f32>>(), 24);
        assert_eq!(std::mem::size_of::<LineResult<f64>>(), 40);
    }
}
