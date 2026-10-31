//! Integer Time conversions; clocks, floating arithmetic and native UB stay native.
use std::cell::Cell;
use std::panic::{catch_unwind, UnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const DOMAIN: u32 = 2;
const PANIC: u32 = 3;
const TO_MILLISECONDS: u32 = 0;
const TO_MICROSECONDS: u32 = 1;
const FROM_MILLISECONDS: u32 = 2;
const FROM_MICROSECONDS: u32 = 3;
const COUNT: usize = 4;

static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static DOMAINS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
thread_local! {
    static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) };
}

fn increment(counts: &Cell<[u64; COUNT]>, totals: &[AtomicU64; COUNT], op: usize) {
    totals[op].fetch_add(1, Ordering::Relaxed);
    let mut values = counts.get();
    values[op] = values[op].wrapping_add(1);
    counts.set(values);
}

fn convert(op: u32, value: i64, frequency: i64) -> Option<i64> {
    let scale = match op {
        TO_MILLISECONDS | FROM_MILLISECONDS => 1000,
        TO_MICROSECONDS | FROM_MICROSECONDS => 1_000_000,
        _ => unreachable!(),
    };
    // Preserve each native signed intermediate, including its asymmetric bias.
    let rounded_frequency = frequency.checked_add(scale / 2)?;
    let factor = rounded_frequency.checked_div(scale)?;
    match op {
        TO_MILLISECONDS | TO_MICROSECONDS => {
            let numerator = value.checked_add(factor.checked_div(2)?)?;
            numerator.checked_div(factor)
        }
        _ => value.checked_mul(factor),
    }
}

// Internal seam permits a plain Rust panic test without foreign unwind/callbacks.
unsafe fn accepted<F: FnOnce() -> Option<i64> + UnwindSafe>(
    op: u32, out: *mut i64, compute: F,
) -> u32 {
    catch_unwind(|| {
        COUNTS.with(|counts| increment(counts, &TOTALS, op as usize));
        match compute() {
            Some(result) => { out.write(result); OK }
            None => { DOMAINS[op as usize].fetch_add(1, Ordering::Relaxed); DOMAIN }
        }
    }).unwrap_or(PANIC)
}

/// Only success writes output; all signed input words are accepted by the ABI.
///
/// # Safety
/// Accepted calls require live writable 8-byte-aligned i64 storage. Numeric
/// validation does not prove pointer provenance, liveness or writability.
#[no_mangle]
pub unsafe extern "C" fn sb_time_convert(
    op: u32, value: i64, frequency: i64, out: *mut i64,
) -> u32 {
    if op >= COUNT as u32 || out.is_null() || (out as usize) % 8 != 0 {
        return INVALID;
    }
    accepted(op, out, || convert(op, value, frequency))
}

/// Wrapping entries: kind 0 TLS, 1 relaxed global entries, 2 relaxed DOMAINs.
#[no_mangle]
pub extern "C" fn sb_time_count(kind: u32, op: u32) -> u64 {
    if kind > 2 || op >= COUNT as u32 { return 0; }
    catch_unwind(|| match kind {
        0 => COUNTS.with(|counts| counts.get()[op as usize]),
        1 => TOTALS[op as usize].load(Ordering::Relaxed),
        _ => DOMAINS[op as usize].load(Ordering::Relaxed),
    }).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[repr(align(8))]
    struct Output(i64);
    const SENTINEL: i64 = 0x1234_5678_1234_5678;

    // Independent widened native-expression oracle: reject EACH overflowing
    // signed intermediate, not just a final result that happens to fit.
    fn narrow(value: i128) -> Option<i128> {
        if value < i64::MIN as i128 || value > i64::MAX as i128 { None }
        else { Some(value) }
    }

    fn divide(n: i128, d: i128) -> Option<i128> {
        if d == 0 || (n == i64::MIN as i128 && d == -1) { None }
        else { narrow(n / d) }
    }

    fn oracle(op: u32, value: i64, frequency: i64) -> Option<i64> {
        let scale: i128 = if op == 0 || op == 2 { 1000 } else { 1_000_000 };
        let rounded = narrow(frequency as i128 + scale / 2)?;
        let factor = divide(rounded, scale)?;
        let result = if op < 2 {
            let bias = divide(factor, 2)?;
            let numerator = narrow(value as i128 + bias)?;
            divide(numerator, factor)?
        } else {
            narrow(value as i128 * factor)?
        };
        Some(result as i64)
    }

    fn check(op: u32, value: i64, frequency: i64) {
        let mut out = Output(SENTINEL);
        let actual = unsafe { sb_time_convert(op, value, frequency, &mut out.0) };
        match oracle(op, value, frequency) {
            Some(expected) => { assert_eq!(actual, OK); assert_eq!(out.0, expected); }
            None => { assert_eq!(actual, DOMAIN); assert_eq!(out.0, SENTINEL); }
        }
    }

    #[test]
    fn full_word_random_corpus() {
        let mut word = 0x19ab_ef07_59cd_2341u64;
        let mut next = || {
            word ^= word << 13;
            word ^= word >> 7;
            word ^= word << 17;
            word as i64
        };
        for _ in 0..100_000 {
            let (value, frequency) = (next(), next());
            for op in 0..COUNT as u32 { check(op, value, frequency); }
        }
    }

    #[test]
    fn scale_boundaries_and_value_edges() {
        let values = [i64::MIN, i64::MIN + 1, -1_000_001, -1000, -501,
            -500, -1, 0, 1, 500, 501, 1000, 1_000_001, i64::MAX - 1, i64::MAX];
        for scale in [1000i64, 1_000_000] {
            let half = scale / 2;
            let centers = [0, half, -half, scale, -scale, scale * 2, -scale * 2,
                i64::MIN, i64::MIN + half, i64::MAX - half, i64::MAX];
            for center in centers {
                for offset in [-1, 0, 1] {
                    if let Some(frequency) = center.checked_add(offset) {
                        for value in values {
                            for op in 0..COUNT as u32 { check(op, value, frequency); }
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn native_bias_zero_factors_and_intermediate_failures() {
        assert_eq!(convert(TO_MILLISECONDS, -1000, 1_000_000), Some(0));
        assert_eq!(convert(TO_MICROSECONDS, -1000, 1_000_000_000), Some(0));
        assert_eq!(convert(TO_MILLISECONDS, 1000, -1_000_000), Some(0));
        assert_eq!(convert(TO_MILLISECONDS, 2000, -1_000_000), Some(-1));
        for op in [FROM_MILLISECONDS, FROM_MICROSECONDS] {
            for value in [i64::MIN, -1, 0, 1, i64::MAX] {
                assert_eq!(convert(op, value, 0), Some(0));
                check(op, value, 0);
            }
        }
        for op in 0..COUNT as u32 {
            check(op, 0, i64::MAX); // rounded frequency overflows despite zero input
            check(op, i64::MIN, -1500); // milliseconds factor -1: MIN / -1 or MIN * -1
            check(op, i64::MAX, 2_000_000); // positive numerator bias overflow
            check(op, i64::MIN, -2_000_000); // negative numerator bias overflow
            check(op, 0, 0);
        }
        assert_eq!(convert(TO_MILLISECONDS, i64::MIN, -1500), None);
        assert_eq!(convert(FROM_MILLISECONDS, i64::MIN, -1500), None);
    }

    #[test]
    fn invalid_calls_never_write_or_count() {
        let before = COUNTS.with(Cell::get);
        let mut out = Output(SENTINEL);
        for op in [COUNT as u32, u32::MAX] {
            assert_eq!(unsafe { sb_time_convert(op, 0, 0, &mut out.0) }, INVALID);
            // Inaccessible aligned pointer is ONLY passed with rejected op.
            assert_eq!(unsafe { sb_time_convert(op, 0, 0, 8usize as *mut i64) }, INVALID);
        }
        for op in 0..COUNT as u32 {
            assert_eq!(unsafe { sb_time_convert(op, 0, 0, std::ptr::null_mut()) }, INVALID);
            for address in 1usize..8 {
                assert_eq!(unsafe { sb_time_convert(op, 0, 0, address as *mut i64) }, INVALID);
            }
        }
        assert_eq!(out.0, SENTINEL);
        assert_eq!(COUNTS.with(Cell::get), before);
        for kind in [0, 1, 2, 3, u32::MAX] {
            for op in [COUNT as u32, u32::MAX] { assert_eq!(sb_time_count(kind, op), 0); }
        }
        for op in 0..COUNT as u32 {
            assert_eq!(sb_time_count(3, op), 0);
            assert_eq!(sb_time_count(u32::MAX, op), 0);
        }
    }

    #[test]
    fn statuses_counts_domains_and_thread_visibility() {
        let before = COUNTS.with(Cell::get);
        let totals = std::array::from_fn::<_, COUNT, _>(|op| sb_time_count(1, op as u32));
        let domains = std::array::from_fn::<_, COUNT, _>(|op| sb_time_count(2, op as u32));
        for op in 0..COUNT as u32 {
            check(op, 1, 1_000_000);
            check(op, 0, i64::MAX);
            let mut out = Output(SENTINEL);
            let status = unsafe { accepted(op, &mut out.0, || {
                assert!(false, "plain Rust panic, never an extern-C callback");
                Some(7)
            }) };
            assert_eq!(status, PANIC);
            assert_eq!(out.0, SENTINEL);
            assert_eq!(sb_time_count(0, op), before[op as usize].wrapping_add(3));
        }
        let parent = COUNTS.with(Cell::get);
        std::thread::spawn(|| {
            for op in 0..COUNT as u32 {
                assert_eq!(sb_time_count(0, op), 0);
                check(op, 1, 1_000_000);
                check(op, 0, i64::MAX);
                assert_eq!(sb_time_count(0, op), 2);
            }
        }).join().unwrap();
        assert_eq!(COUNTS.with(Cell::get), parent);
        for op in 0..COUNT {
            assert!(sb_time_count(1, op as u32).wrapping_sub(totals[op]) >= 5);
            assert!(sb_time_count(2, op as u32).wrapping_sub(domains[op]) >= 2);
        }
    }

    #[test]
    fn counter_banks_wrap_without_global_reset() {
        let locals = Cell::new([u64::MAX, 7, 8, 9]);
        let totals = [AtomicU64::new(u64::MAX), AtomicU64::new(2),
            AtomicU64::new(3), AtomicU64::new(4)];
        increment(&locals, &totals, 0);
        assert_eq!(locals.get(), [0, 7, 8, 9]);
        assert_eq!(totals[0].load(Ordering::Relaxed), 0);
        assert_eq!(totals[1].load(Ordering::Relaxed), 2);
        // DOMAIN uses the same wrapping atomic operation independently of TLS.
        let domains = [const { AtomicU64::new(u64::MAX) }; COUNT];
        domains[3].fetch_add(1, Ordering::Relaxed);
        assert_eq!(domains[3].load(Ordering::Relaxed), 0);
        assert_eq!(domains[0].load(Ordering::Relaxed), u64::MAX);
    }
}
