//! Scalar control flow for the 34 portable File definitions, in source-map order.
//! Native prefixes, return expressions, typed storage and exception ownership stay
//! in C++; these receipts count controller entry, not entry to the native facade.

use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

pub type StarFileHost = unsafe extern "C" fn(*mut c_void, u32, u64, u64, u64, *mut u64) -> u32;

thread_local! {
    // Individual cells avoid overwriting receipts produced by recursive callbacks.
    static COUNTS: [[Cell<u64>; 3]; 34] = const {
        [const { [const { Cell::new(0) }; 3] }; 34]
    };
}

fn increment(mode: u32, event: usize) {
    COUNTS.with(|counts| {
        let slot = &counts[mode as usize][event];
        slot.set(slot.get().wrapping_add(1));
    });
}

/// Executing-thread receipts: event 0 = attempt, 1 = success, 2 = error.
#[no_mangle]
pub extern "C" fn star_file_call_count(mode: u32, event: u32) -> u64 {
    if mode >= 34 || event >= 3 {
        return 0;
    }
    COUNTS.with(|counts| counts[mode as usize][event as usize].get())
}

fn counted(mode: u32, body: impl FnOnce() -> Result<(), u32>) -> u32 {
    increment(mode, 0);
    let status = match catch_unwind(AssertUnwindSafe(body)) {
        Ok(Ok(())) => 0,
        Ok(Err(status)) => status,
        Err(payload) => {
            // Dropping an arbitrary panic payload can itself panic at the C boundary.
            std::mem::forget(payload);
            3
        }
    };
    increment(mode, if status == 0 { 1 } else { 2 });
    status
}

/// Run one scalar controller; 0 succeeds, 1 preserves a pending native exception,
/// 2 rejects the protocol, and 3 contains a Rust panic (with unwind enabled).
/// Invalid entry arguments are rejected without incrementing receipts.
///
/// # Safety
/// `ctx` and every reachable native object must remain live for each callback.
/// The host must implement the mode's operations, return valid bounded scalars,
/// and never unwind through Rust. Native exceptions must be captured before the
/// host returns and rethrown by C++ after this function returns. The host may
/// reenter this controller and replace its native values. It must only write the
/// provided live, aligned scalar output, disjoint from all reachable native state,
/// and must not retain that output pointer. Rust only forwards `ctx`; it never
/// creates a reference or slice to native payloads, files, strings or buffers.
#[no_mangle]
pub unsafe extern "C" fn star_file_run(
    mode: u32,
    ctx: *mut c_void,
    host: Option<StarFileHost>,
) -> u32 {
    if mode >= 34 || ctx.is_null() || host.is_none() {
        return 2;
    }
    let host = host.unwrap();
    counted(mode, || {
        control(mode, |op, a, out| unsafe { host(ctx, op, a, 0, 0, out) })
    })
}

fn control(mode: u32, mut host: impl FnMut(u32, u64, *mut u64) -> u32) -> Result<(), u32> {
    // The qualified native controller initializes once, then reuses this slot.
    let mut value = 0_u64;
    let mut call = |op, a| {
        let status = host(op, a, &mut value);
        if status == 0 {
            Ok(value)
        } else {
            Err(if status > 3 { 2 } else { status })
        }
    };
    // `?` stops immediately on error, including before native scope-reset leaves.
    // The wrapper's exception unwind owns cleanup in that case.
    match mode {
        0 => {
            if call(0, 0)? == 0 {
                call(1, 0)?;
            }
            if call(2, 0)? == 0 {
                call(3, 0)?;
            }
        }
        1 => {
            call(0, 0)?;
            while call(1, 0)? != 0 {
                call(2, 0)?;
                if call(3, 0)? != 0 {
                    call(4, 0)?;
                } else {
                    call(5, 0)?;
                }
                call(6, 0)?;
            }
            call(7, 0)?; // Destroy traversal before removing its parent directory.
            call(8, 0)?;
        }
        2 => {
            call(0, 0)?;
            while call(1, 0)? == 0 {
                call(2, 0)?;
                call(3, 0)?;
            }
        }
        4 | 5 => {
            while call(0, 0)? == 0 {
                let n = call(1, 0)?;
                if mode == 4 {
                    call(2, n)?;
                } else {
                    let mut i = 0_u64;
                    while i < n {
                        call(2, i)?;
                        i = i.wrapping_add(1);
                    }
                }
            }
        }
        12 => {
            let mut i = call(0, 0)? as u32;
            while i > 0 {
                call(1, u64::from(i))?;
                if call(2, 0)? != 0 {
                    call(3, 0)?;
                }
                call(4, 0)?;
                i = i.wrapping_sub(1);
            }
        }
        17 | 18 | 20 | 29 => {
            if call(0, 0)? == 0 {
                call(1, 0)?;
            }
            call(2, 0)?;
        }
        21 | 22 => {
            if call(0, 0)? == 0 {
                call(1, 0)?;
            }
            if call(2, 0)? == 0 {
                call(3, 0)?;
            }
            call(4, 0)?;
        }
        26 => {
            if call(0, 0)? != 0 {
                call(1, 0)?;
            }
            call(2, 0)?;
        }
        27 => {
            call(0, 0)?;
            if call(1, 0)? != 0 {
                call(2, 0)?;
            }
            call(3, 0)?;
        }
        28 => {
            let temporary = call(0, 0)? == 0;
            if temporary {
                call(1, 0)?;
            }
            call(2, 0)?;
            if temporary {
                call(3, 0)?;
            }
        }
        30 => {
            call(0, 0)?;
            if call(1, 0)? != 0 {
                call(2, 0)?;
            }
            call(3, 0)?;
            call(4, 0)?;
        }
        31 => {
            if call(0, 0)? != 0 {
                call(1, 0)?;
            }
            call(2, 0)?;
            call(3, 0)?;
        }
        32 => {
            if call(0, 0)? != 0 {
                call(1, 0)?;
            } else {
                call(2, 0)?;
            }
        }
        33 => {
            if call(0, 0)? != 0 {
                call(1, 0)?;
                call(2, 0)?;
            }
        }
        // Native single leaves include constructor/getter receipt-only modes.
        3 | 6..=11 | 13..=16 | 19 | 23..=25 => {
            call(0, 0)?;
        }
        _ => return Err(2),
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Clone, Debug)]
    struct Step {
        op: u32,
        a: u64,
        value: Option<u64>,
    }
    fn s(op: u32, value: u64) -> Step {
        Step {
            op,
            a: 0,
            value: Some(value),
        }
    }
    fn a(op: u32, arg: u64) -> Step {
        Step {
            op,
            a: arg,
            value: Some(0),
        }
    }

    struct Mock {
        steps: Vec<Step>,
        seen: Vec<(u32, u64, u64, u64, u64)>,
        fail: Option<(usize, u32)>,
        mismatch: bool,
    }
    // Record mismatches rather than asserting inside extern C (which must not unwind).
    unsafe extern "C" fn host(
        ctx: *mut c_void,
        op: u32,
        a: u64,
        b: u64,
        c: u64,
        out: *mut u64,
    ) -> u32 {
        let mock = unsafe { &mut *ctx.cast::<Mock>() };
        let index = mock.seen.len();
        mock.seen.push((op, a, b, c, unsafe { *out }));
        let Some(step) = mock.steps.get(index) else {
            mock.mismatch = true;
            return 2;
        };
        if (op, a, b, c) != (step.op, step.a, 0, 0) {
            mock.mismatch = true;
            return 2;
        }
        if let Some(value) = step.value {
            unsafe {
                *out = value;
            }
        }
        if let Some((at, status)) = mock.fail {
            if index == at {
                return status;
            }
        }
        0
    }
    fn check(mode: u32, steps: Vec<Step>, fail: Option<(usize, u32)>) {
        let expected_len = fail.map_or(steps.len(), |(at, _)| at + 1);
        let before = [0, 1, 2].map(|e| star_file_call_count(mode, e));
        let mut mock = Mock {
            steps,
            seen: vec![],
            fail,
            mismatch: false,
        };
        let status = unsafe { star_file_run(mode, (&mut mock as *mut Mock).cast(), Some(host)) };
        let expected_status = fail.map_or(0, |(_, status)| if status > 3 { 2 } else { status });
        assert_eq!(status, expected_status, "mode {mode}");
        assert!(!mock.mismatch, "mode {mode}: {:?}", mock.seen);
        assert_eq!(mock.seen.len(), expected_len, "mode {mode}");
        let mut previous = 0;
        for (step, seen) in mock.steps.iter().zip(&mock.seen) {
            assert_eq!(seen.4, previous, "output slot initialization, mode {mode}");
            if let Some(value) = step.value {
                previous = value;
            }
        }
        assert_eq!(star_file_call_count(mode, 0), before[0].wrapping_add(1));
        assert_eq!(
            star_file_call_count(mode, 1),
            before[1].wrapping_add(u64::from(status == 0))
        );
        assert_eq!(
            star_file_call_count(mode, 2),
            before[2].wrapping_add(u64::from(status != 0))
        );
    }

    // Literal traces transcribed from controller.cpp and wrapper leaf contracts,
    // not generated by invoking the Rust controller under test.
    fn traces() -> Vec<(u32, Vec<Step>)> {
        let mut t = vec![
            (0, vec![s(0, 0), s(1, 0), s(2, 0), s(3, 0)]),
            (0, vec![s(0, 7), s(2, 9)]),
            (1, vec![s(0, 0), s(1, 0), s(7, 0), s(8, 0)]),
            (
                1,
                vec![
                    s(0, 0),
                    s(1, 7),
                    s(2, 0),
                    s(3, 9),
                    s(4, 0),
                    s(6, 0),
                    s(1, 1),
                    s(2, 0),
                    s(3, 0),
                    s(5, 0),
                    s(6, 0),
                    s(1, 0),
                    s(7, 0),
                    s(8, 0),
                ],
            ),
            (2, vec![s(0, 0), s(1, 7)]),
            (
                2,
                vec![
                    s(0, 0),
                    s(1, 0),
                    s(2, 0),
                    s(3, 0),
                    s(1, 0),
                    s(2, 0),
                    s(3, 0),
                    s(1, 9),
                ],
            ),
            (
                4,
                vec![
                    s(0, 0),
                    s(1, 3),
                    a(2, 3),
                    s(0, 0),
                    s(1, 0),
                    a(2, 0),
                    s(0, 7),
                ],
            ),
            (
                5,
                vec![
                    s(0, 0),
                    s(1, 3),
                    a(2, 0),
                    a(2, 1),
                    a(2, 2),
                    s(0, 0),
                    s(1, 0),
                    s(0, 7),
                ],
            ),
            (4, vec![s(0, 7)]),
            (5, vec![s(0, 7)]),
            (12, vec![s(0, 0)]),
            (12, vec![s(0, 1_u64 << 32)]),
            (
                12,
                vec![
                    s(0, (1_u64 << 32) + 3),
                    a(1, 3),
                    s(2, 7),
                    s(3, 0),
                    s(4, 0),
                    a(1, 2),
                    s(2, 0),
                    s(4, 0),
                    a(1, 1),
                    s(2, 9),
                    s(3, 0),
                    s(4, 0),
                ],
            ),
            (26, vec![s(0, 0), s(2, 0)]),
            (26, vec![s(0, 7), s(1, 0), s(2, 0)]),
            (27, vec![s(0, 0), s(1, 0), s(3, 0)]),
            (27, vec![s(0, 0), s(1, 7), s(2, 0), s(3, 0)]),
            (28, vec![s(0, 0), s(1, 0), s(2, 0), s(3, 0)]),
            (28, vec![s(0, 7), s(2, 0)]),
            (30, vec![s(0, 0), s(1, 0), s(3, 0), s(4, 0)]),
            (30, vec![s(0, 0), s(1, 7), s(2, 0), s(3, 0), s(4, 0)]),
            (31, vec![s(0, 0), s(2, 0), s(3, 0)]),
            (31, vec![s(0, 7), s(1, 0), s(2, 0), s(3, 0)]),
            (32, vec![s(0, 0), s(2, 0)]),
            (32, vec![s(0, 7), s(1, 0)]),
            (33, vec![s(0, 0)]),
            (33, vec![s(0, 7), s(1, 0), s(2, 0)]),
        ];
        for mode in [3, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 19, 23, 24, 25] {
            t.push((mode, vec![s(0, 0)]));
        }
        for mode in [17, 18, 20, 29] {
            t.push((mode, vec![s(0, 0), s(1, 0), s(2, 0)]));
            t.push((mode, vec![s(0, 7), s(2, 0)]));
        }
        for mode in [21, 22] {
            for open in [0, 7] {
                for capable in [0, 9] {
                    let mut steps = vec![s(0, open)];
                    if open == 0 {
                        steps.push(s(1, 0));
                    }
                    steps.push(s(2, capable));
                    if capable == 0 {
                        steps.push(s(3, 0));
                    }
                    steps.push(s(4, 0));
                    t.push((mode, steps));
                }
            }
        }
        t
    }
    #[test]
    fn all_34_modes_and_every_error_stop_position() {
        let mut covered = [false; 34];
        for (mode, steps) in traces() {
            covered[mode as usize] = true;
            check(mode, steps.clone(), None);
            for index in 0..steps.len() {
                for status in [1, 2, 3, 4, u32::MAX] {
                    check(mode, steps.clone(), Some((index, status)));
                }
            }
        }
        assert!(covered.into_iter().all(|v| v));
    }
    #[test]
    fn output_slot_is_zero_once_then_retained() {
        check(
            0,
            vec![
                s(0, 7),
                Step {
                    op: 2,
                    a: 0,
                    value: None,
                },
            ],
            None,
        );
        check(
            3,
            vec![Step {
                op: 0,
                a: 0,
                value: None,
            }],
            None,
        );
    }
    #[test]
    fn invalid_entries_are_uncounted() {
        let before = [0, 1, 2].map(|e| star_file_call_count(3, e));
        let mut byte = 0_u8;
        unsafe {
            assert_eq!(star_file_run(3, std::ptr::null_mut(), Some(host)), 2);
            assert_eq!(star_file_run(3, (&mut byte as *mut u8).cast(), None), 2);
            assert_eq!(
                star_file_run(34, (&mut byte as *mut u8).cast(), Some(host)),
                2
            );
            assert_eq!(
                star_file_run(u32::MAX, (&mut byte as *mut u8).cast(), Some(host)),
                2
            );
        }
        assert_eq!(before, [0, 1, 2].map(|e| star_file_call_count(3, e)));
        assert_eq!(star_file_call_count(34, 0), 0);
        assert_eq!(star_file_call_count(3, 3), 0);
    }
    #[test]
    fn counters_wrap_per_slot_and_are_thread_local() {
        for event in 0..3 {
            COUNTS.with(|c| c[3][event].set(u64::MAX));
        }
        check(3, vec![s(0, 0)], None);
        assert_eq!(
            [0, 1, 2].map(|e| star_file_call_count(3, e)),
            [0, 0, u64::MAX]
        );
        check(3, vec![s(0, 0)], Some((0, 1)));
        assert_eq!([0, 1, 2].map(|e| star_file_call_count(3, e)), [1, 0, 0]);
        std::thread::spawn(|| {
            assert_eq!([0, 1, 2].map(|e| star_file_call_count(3, e)), [0, 0, 0]);
            check(3, vec![s(0, 0)], None);
        })
        .join()
        .unwrap();
        assert_eq!([0, 1, 2].map(|e| star_file_call_count(3, e)), [1, 0, 0]);
    }
    struct Reentry {
        depth: u32,
        calls: u32,
        value: Box<u64>,
        bad: bool,
    }
    unsafe extern "C" fn reentrant(
        ctx: *mut c_void,
        op: u32,
        a: u64,
        b: u64,
        c: u64,
        out: *mut u64,
    ) -> u32 {
        let p = ctx.cast::<Reentry>();
        unsafe {
            if (op, a, b, c) != (0, 0, 0, 0) {
                (*p).bad = true;
                return 2;
            }
            (*p).calls += 1;
            if (*p).depth == 0 {
                (*p).depth = 1;
                // No payload borrow survives the recursive callback or replacement.
                let status = star_file_run(3, ctx, Some(reentrant));
                if status != 0 {
                    (*p).bad = true;
                    return status;
                }
                (*p).depth = 0;
            } else {
                (*p).value = Box::new(91);
            }
            *out = *(*p).value;
        }
        0
    }
    #[test]
    fn reentry_preserves_nested_receipts_and_allows_value_replacement() {
        let before = [0, 1, 2].map(|e| star_file_call_count(3, e));
        let mut r = Reentry {
            depth: 0,
            calls: 0,
            value: Box::new(8),
            bad: false,
        };
        assert_eq!(
            unsafe { star_file_run(3, (&mut r as *mut Reentry).cast(), Some(reentrant)) },
            0
        );
        assert!(!r.bad);
        assert_eq!(r.calls, 2);
        assert_eq!(*r.value, 91);
        assert_eq!(
            [0, 1, 2].map(|e| star_file_call_count(3, e)),
            [
                before[0].wrapping_add(2),
                before[1].wrapping_add(2),
                before[2]
            ]
        );
    }
    #[test]
    fn rust_panic_is_contained_without_unwinding_an_extern_host() {
        let before = [0, 1, 2].map(|e| star_file_call_count(3, e));
        assert_eq!(
            counted(3, || control(3, |_, _, _| panic!("private Rust closure"))),
            3
        );
        assert_eq!(
            [0, 1, 2].map(|e| star_file_call_count(3, e)),
            [
                before[0].wrapping_add(1),
                before[1],
                before[2].wrapping_add(1)
            ]
        );
    }
}
