//! Scalar OptionParser controllers. Native strings, containers and exception
//! ownership never cross this boundary; callbacks are primitive full expressions.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

pub type StarOptionParserHost =
    unsafe extern "C" fn(*mut c_void, u32, u64, u64, u64, *mut u64) -> u32;
thread_local! { static COUNTS: Cell<[[u64; 3]; 8]> = const { Cell::new([[0; 3]; 8]) }; }
fn count(mode: u32, event: usize) {
    COUNTS.with(|c| {
        let mut counts = c.get();
        counts[mode as usize][event] = counts[mode as usize][event].wrapping_add(1);
        c.set(counts);
    });
}
#[no_mangle]
pub extern "C" fn star_option_parser_call_count(mode: u32, event: u32) -> u64 {
    if mode > 7 || event > 2 {
        return 0;
    }
    COUNTS.with(|c| c.get()[mode as usize][event as usize])
}
struct Driver {
    context: *mut c_void,
    host: StarOptionParserHost,
}
impl Driver {
    fn call(&self, op: u32, a: u64, b: u64, c: u64) -> Result<u64, u32> {
        // Initialize like the frozen native scalar driver, including void leaves.
        // No reference to native storage exists in Rust, even across reentry.
        let mut out = 0;
        match unsafe { (self.host)(self.context, op, a, b, c, &mut out) } {
            0 => Ok(out),
            1 => Err(1),
            _ => Err(2),
        }
    }
    fn c(&self, op: u32, a: u64) -> Result<u64, u32> {
        self.call(op, a, 0, 0)
    }
    fn run(&self, mode: u32) -> Result<(), u32> {
        match mode {
            0..=2 => {
                self.c(1, mode as u64)?;
            }
            3 | 4 => {
                if self.c(if mode == 3 { 2 } else { 3 }, 0)? == 0 {
                    self.c(5, if mode == 3 { 22 } else { 23 })?;
                    // An exception-construction leaf cannot succeed. Tightening
                    // only malformed hosts prevents publishing a duplicate.
                    return Err(2);
                }
            }
            5 => {
                self.c(4, 0)?;
            }
            6 => self.parse()?,
            7 => self.help()?,
            _ => return Err(2),
        }
        self.c(33, 0)?;
        Ok(())
    }
    fn parse(&self) -> Result<(), u32> {
        let mut ended = false;
        self.c(6, 0)?;
        while self.c(7, 0)? != 0 {
            self.c(8, 0)?;
            if self.c(9, 0)? != 0 {
                ended = true;
            } else if !ended && self.c(10, 0)? != 0 {
                self.c(11, 0)?;
                self.c(12, 0)?;
                if self.c(13, 0)? == 0 {
                    self.c(30, 16)?;
                } else if self.call(14, 0, 0, 0)? != 0 {
                    self.c(18, 0)?;
                } else if self.c(7, 0)? == 0 {
                    self.c(30, 17)?;
                } else {
                    // Consumption precedes duplicate validation, as in native.
                    self.c(16, 0)?;
                    if self.c(15, 0)? != 2 && self.c(17, 0)? != 0 {
                        self.c(30, 18)?;
                    } else {
                        self.c(19, 0)?;
                        self.c(20, 0)?;
                    }
                }
            } else {
                self.c(21, 0)?;
            }
            self.c(22, 0)?;
        }
        self.c(23, 0)?;
        while self.c(24, 0)? != 0 {
            if self.call(14, 1, 1, 0)? != 0 && self.c(15, 1)? == 1 && self.c(17, 1)? == 0 {
                self.c(30, 19)?;
            }
            self.c(25, 0)?;
        }
        self.c(26, 0)?;
        let (mut minimum, mut maximum) = (0u64, 0u64);
        self.c(23, 1)?;
        while self.c(24, 1)? != 0 {
            let r = self.c(15, 2)?;
            if (r == 0 || r == 1) && maximum != u64::MAX {
                maximum = maximum.wrapping_add(1);
            }
            if r == 1 {
                minimum = minimum.wrapping_add(1);
            }
            if r == 2 {
                maximum = u64::MAX;
            }
            self.c(25, 1)?;
        }
        self.c(26, 1)?;
        let count = self.c(32, 0)?;
        if count < minimum {
            self.call(30, 20, minimum, count)?;
        }
        if count > maximum {
            self.call(30, 21, maximum, count)?;
        }
        Ok(())
    }
    fn help(&self) -> Result<(), u32> {
        // Do not cache metadata emptiness: ostream callbacks can mutate it.
        if self.c(27, 0)? == 0 && self.c(27, 1)? == 0 {
            self.c(31, 0)?;
        } else if self.c(27, 0)? == 0 {
            self.c(31, 1)?;
        } else if self.c(27, 1)? == 0 {
            self.c(31, 2)?;
        }
        self.c(28, 0)?;
        self.c(23, 0)?;
        while self.c(24, 0)? != 0 {
            if self.call(14, 1, 0, 0)? != 0 {
                self.c(29, 3)?;
            } else {
                let r = self.c(15, 1)?;
                if r <= 2 {
                    self.c(29, 4 + r)?;
                }
            }
            self.c(25, 0)?;
        }
        self.c(26, 0)?;
        self.c(23, 1)?;
        while self.c(24, 1)? != 0 {
            let r = self.c(15, 2)?;
            self.c(
                29,
                if r == 0 {
                    7
                } else if r == 1 {
                    8
                } else {
                    9
                },
            )?;
            self.c(25, 1)?;
        }
        self.c(26, 1)?;
        let no_name = self.c(27, 0)? != 0;
        self.c(31, if no_name { 10 } else { 11 })?;
        self.c(23, 0)?;
        while self.c(24, 0)? != 0 {
            if self.call(14, 1, 0, 0)? != 0 && self.c(27, 3)? == 0 {
                self.c(31, 12)?;
            }
            if self.call(14, 1, 1, 0)? != 0 && self.c(27, 4)? == 0 {
                self.c(31, 13)?;
            }
            self.c(25, 0)?;
        }
        self.c(26, 0)?;
        self.c(23, 1)?;
        while self.c(24, 1)? != 0 {
            if self.c(27, 5)? == 0 {
                self.c(31, 14)?;
            }
            self.c(25, 1)?;
        }
        self.c(26, 1)?;
        if self.c(27, 2)? == 0 {
            self.c(31, 15)?;
        }
        Ok(())
    }
}
/// Executes one controller with opaque native ownership.
///
/// # Safety
/// The callback must honor the scalar protocol, initialize scalar outputs on
/// success and never unwind across this ABI. Context is opaque and may be null
/// for custom hosts. Native contexts reject null themselves. Scratch lifetime
/// and pending-exception rethrow belong to the host, not this runner.
#[no_mangle]
pub unsafe extern "C" fn star_option_parser_run(
    mode: u32,
    context: *mut c_void,
    host: Option<StarOptionParserHost>,
) -> u32 {
    if mode > 7 || host.is_none() {
        return 2;
    }
    contained(mode, || {
        Driver {
            context,
            host: host.unwrap(),
        }
        .run(mode)
    })
}
fn contained(mode: u32, run: impl FnOnce() -> Result<(), u32>) -> u32 {
    count(mode, 0);
    match catch_unwind(AssertUnwindSafe(run)) {
        Ok(Ok(())) => {
            count(mode, 1);
            0
        }
        Ok(Err(1)) => {
            count(mode, 2);
            1
        }
        Ok(Err(_)) => 2,
        Err(_) => 3,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::VecDeque;
    #[derive(Clone, Debug)]
    struct Step {
        op: u32,
        a: u64,
        b: u64,
        c: u64,
        out: u64,
        status: u32,
    }
    fn s(op: u32, a: u64, out: u64) -> Step {
        Step {
            op,
            a,
            b: 0,
            c: 0,
            out,
            status: 0,
        }
    }
    unsafe extern "C" fn script(
        ctx: *mut c_void,
        op: u32,
        a: u64,
        b: u64,
        c: u64,
        out: *mut u64,
    ) -> u32 {
        let queue = &mut *(ctx as *mut VecDeque<Step>);
        // Never assert/panic inside an extern callback: record failure as invalid.
        match queue.pop_front() {
            Some(step) if (op, a, b, c) == (step.op, step.a, step.b, step.c) => {
                *out = step.out;
                step.status
            }
            _ => {
                queue.push_front(s(u32::MAX, 0, 0));
                2
            }
        }
    }
    fn run(mode: u32, steps: Vec<Step>, status: u32) {
        if status == 0 {
            // Every reached leaf must stop immediately on native pending or an
            // invalid foreign status, without synthetic cleanup callbacks.
            for index in 0..steps.len() {
                for fault in [1, 3, u32::MAX] {
                    let mut prefix = steps[..=index].to_vec();
                    prefix[index].status = fault;
                    run(mode, prefix, if fault == 1 { 1 } else { 2 });
                }
            }
        }
        let mut q: VecDeque<_> = steps.into();
        assert_eq!(
            unsafe { star_option_parser_run(mode, &mut q as *mut _ as *mut c_void, Some(script)) },
            status
        );
        assert!(q.is_empty(), "unconsumed {q:?}");
    }
    fn tail() -> Vec<Step> {
        vec![
            s(23, 0, 0),
            s(24, 0, 0),
            s(26, 0, 0),
            s(23, 1, 0),
            s(24, 1, 0),
            s(26, 1, 0),
            s(32, 0, 0),
            s(33, 0, 0),
        ]
    }
    #[test]
    fn all_registration_modes_and_duplicate_throw() {
        for mode in 0..3 {
            run(mode, vec![s(1, mode as u64, 0), s(33, 0, 0)], 0);
        }
        for mode in 3..5 {
            run(mode, vec![s(mode - 1, 0, 1), s(33, 0, 0)], 0);
            let mut raise = s(5, if mode == 3 { 22 } else { 23 }, 0);
            raise.status = 1;
            run(mode, vec![s(mode - 1, 0, 0), raise.clone()], 1);
            raise.status = 0;
            run(mode, vec![s(mode - 1, 0, 0), raise], 2);
        }
        run(5, vec![s(4, 0, 0), s(33, 0, 0)], 0);
    }
    #[test]
    fn opaque_parse_consumes_duplicate_before_error_and_repeated_end() {
        let mut v = vec![s(6, 0, 0)];
        for duplicate in [false, true] {
            v.extend([
                s(7, 0, 1),
                s(8, 0, 0),
                s(9, 0, 0),
                s(10, 0, 1),
                s(11, 0, 0),
                s(12, 0, 0),
                s(13, 0, 1),
                s(14, 0, 0),
                s(7, 0, 1),
                s(16, 0, 0),
                s(15, 0, 0),
                s(17, 0, duplicate as u64),
            ]);
            if duplicate {
                v.push(s(30, 18, 0));
            } else {
                v.extend([s(19, 0, 0), s(20, 0, 0)]);
            }
            v.push(s(22, 0, 0));
        }
        for _ in 0..2 {
            v.extend([s(7, 0, 1), s(8, 0, 0), s(9, 0, 1), s(22, 0, 0)]);
        }
        v.extend([
            s(7, 0, 1),
            s(8, 0, 0),
            s(9, 0, 0),
            s(21, 0, 0),
            s(22, 0, 0),
            s(7, 0, 0),
        ]);
        let mut t = tail();
        t[6].out = 1;
        let mut too_many = s(30, 21, 0);
        too_many.c = 1;
        t.insert(7, too_many);
        v.extend(t);
        run(6, v, 0);
    }
    #[test]
    fn required_and_cardinality_order() {
        let mut v = vec![s(6, 0, 0), s(7, 0, 0), s(23, 0, 0), s(24, 0, 1)];
        let mut ty = s(14, 1, 1);
        ty.b = 1;
        v.push(ty);
        v.extend([
            s(15, 1, 1),
            s(17, 1, 0),
            s(30, 19, 0),
            s(25, 0, 0),
            s(24, 0, 0),
            s(26, 0, 0),
            s(23, 1, 0),
            s(24, 1, 1),
            s(15, 2, 1),
            s(25, 1, 0),
            s(24, 1, 0),
            s(26, 1, 0),
            s(32, 0, 0),
        ]);
        let mut few = s(30, 20, 0);
        few.b = 1;
        v.extend([few, s(33, 0, 0)]);
        run(6, v, 0);
    }
    #[test]
    fn help_fresh_metadata_and_scoped_loops() {
        run(
            7,
            vec![
                s(27, 0, 0),
                s(27, 1, 0),
                s(31, 0, 0),
                s(28, 0, 0),
                s(23, 0, 0),
                s(24, 0, 0),
                s(26, 0, 0),
                s(23, 1, 0),
                s(24, 1, 0),
                s(26, 1, 0),
                s(27, 0, 1),
                s(31, 10, 0),
                s(23, 0, 0),
                s(24, 0, 0),
                s(26, 0, 0),
                s(23, 1, 0),
                s(24, 1, 0),
                s(26, 1, 0),
                s(27, 2, 0),
                s(31, 15, 0),
                s(33, 0, 0),
            ],
            0,
        );
    }
    #[test]
    fn statuses_stop_without_cleanup_and_void_scalar_is_ignored() {
        for status in [1, 2, 3, u32::MAX] {
            let mut step = s(6, 0, 0);
            step.status = status;
            run(6, vec![step], if status == 1 { 1 } else { 2 });
        }
        run(0, vec![s(1, 0, 97), s(33, 0, 65)], 0);
    }
    unsafe extern "C" fn null_host(
        ctx: *mut c_void,
        _: u32,
        _: u64,
        _: u64,
        _: u64,
        out: *mut u64,
    ) -> u32 {
        if !ctx.is_null() {
            return 2;
        }
        *out = 0;
        0
    }
    #[test]
    fn preflight_null_custom_context_and_wrapping_counters() {
        COUNTS.with(|c| c.set([[u64::MAX; 3]; 8]));
        assert_eq!(
            unsafe { star_option_parser_run(8, std::ptr::null_mut(), Some(null_host)) },
            2
        );
        assert_eq!(
            unsafe { star_option_parser_run(0, std::ptr::null_mut(), None) },
            2
        );
        assert_eq!(star_option_parser_call_count(0, 0), u64::MAX);
        assert_eq!(
            unsafe { star_option_parser_run(0, std::ptr::null_mut(), Some(null_host)) },
            0
        );
        assert_eq!(star_option_parser_call_count(0, 0), 0);
        assert_eq!(star_option_parser_call_count(0, 1), 0);
        assert_eq!(star_option_parser_call_count(0, 2), u64::MAX);
        assert_eq!(star_option_parser_call_count(8, 0), 0);
        assert_eq!(star_option_parser_call_count(0, 3), 0);
    }
    unsafe extern "C" fn reentrant_host(
        ctx: *mut c_void,
        op: u32,
        _: u64,
        _: u64,
        _: u64,
        out: *mut u64,
    ) -> u32 {
        *out = 0;
        if op == 1 {
            let status = star_option_parser_run(0, std::ptr::null_mut(), Some(null_host));
            *(ctx as *mut u32) = status;
            if status != 0 {
                return 2;
            }
        }
        0
    }
    #[test]
    fn callbacks_reenter_and_receipts_are_thread_local() {
        let before = star_option_parser_call_count(0, 0);
        let mut nested = u32::MAX;
        assert_eq!(
            unsafe {
                star_option_parser_run(
                    0,
                    &mut nested as *mut _ as *mut c_void,
                    Some(reentrant_host),
                )
            },
            0
        );
        assert_eq!(nested, 0);
        assert_eq!(star_option_parser_call_count(0, 0), before.wrapping_add(2));
        std::thread::spawn(|| {
            assert_eq!(star_option_parser_call_count(0, 0), 0);
            assert_eq!(
                unsafe { star_option_parser_run(0, std::ptr::null_mut(), Some(null_host)) },
                0
            );
            assert_eq!(star_option_parser_call_count(0, 0), 1);
        })
        .join()
        .unwrap();
        assert_eq!(star_option_parser_call_count(0, 0), before.wrapping_add(2));
    }
    #[test]
    fn internal_rust_panic_containment() {
        // Exercise the containment mechanism without any foreign unwind.
        let before = [
            star_option_parser_call_count(6, 0),
            star_option_parser_call_count(6, 1),
            star_option_parser_call_count(6, 2),
        ];
        assert_eq!(contained(6, || panic!("local Rust panic")), 3);
        assert_eq!(
            star_option_parser_call_count(6, 0),
            before[0].wrapping_add(1)
        );
        assert_eq!(star_option_parser_call_count(6, 1), before[1]);
        assert_eq!(star_option_parser_call_count(6, 2), before[2]);
    }
}
