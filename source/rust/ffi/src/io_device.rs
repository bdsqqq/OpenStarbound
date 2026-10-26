//! IODevice source control flow over synchronous native scalar leaves.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

pub type StarIODeviceHost = unsafe extern "C" fn(*mut c_void, u32, u64, u64, u64, *mut u64) -> u32;
thread_local! { static COUNTS: Cell<[[u64; 3]; 22]> = const { Cell::new([[0; 3]; 22]) }; }
fn count(mode: u32, event: usize) {
    COUNTS.with(|c| {
        let mut v = c.get();
        v[mode as usize][event] = v[mode as usize][event].wrapping_add(1);
        c.set(v);
    });
}
#[no_mangle]
pub extern "C" fn star_io_device_call_count(mode: u32, event: u32) -> u64 {
    if mode >= 22 || event >= 3 {
        return 0;
    }
    COUNTS.with(|c| c.get()[mode as usize][event as usize])
}
const ARG: u32 = 1;
const MODE: u32 = 2;
const STORE_MODE: u32 = 3;
const SOURCE_MODE: u32 = 4;
const READ: u32 = 5;
const WRITE: u32 = 6;
const POS: u32 = 7;
const SEEK: u32 = 8;
const END: u32 = 9;
const VIRTUAL_SIZE: u32 = 10;
const NAME: u32 = 11;
const READ_ABS: u32 = 12;
const WRITE_ABS: u32 = 13;
const READFULL: u32 = 14;
const WRITEFULL: u32 = 15;
const READFULLABS: u32 = 16;
const WRITEFULLABS: u32 = 17;
const BASE_CLOSE: u32 = 18;
const NAME_BASE: u32 = 19;
const ARRAY_ALLOC: u32 = 20;
const CAPTURE_INPUT_BYTES: u32 = 21;
const RETURN: u32 = 22;
const FINISH: u32 = 23;
const ERROR: u32 = 24;
const EXCEPTION_KIND: u32 = 25;
const WRAP_SIZE: u32 = 26;

struct Driver {
    ctx: *mut c_void,
    host: StarIODeviceHost,
}
impl Driver {
    fn call(&self, op: u32, a: u64, b: u64, c: u64) -> Result<u64, u32> {
        let mut out = 0;
        // No native references or object representations survive a callback.
        match unsafe { (self.host)(self.ctx, op, a, b, c, &mut out) } {
            0 => Ok(out),
            1 => Err(1),
            _ => Err(2),
        }
    }
    fn get(&self, op: u32) -> Result<u64, u32> {
        self.call(op, 0, 0, 0)
    }
    fn set(&self, op: u32, a: u64) -> Result<u64, u32> {
        self.call(op, a, 0, 0)
    }
    fn arg(&self, n: u64) -> Result<u64, u32> {
        self.set(ARG, n)
    }
    fn store(&self, value: u64) -> Result<(), u32> {
        if value > 255 {
            return Err(2);
        }
        self.set(STORE_MODE, value)?;
        Ok(())
    }
    fn error(&self, kind: u64) -> Result<(), u32> {
        self.set(ERROR, kind)?;
        Err(2) // ERROR reporting success contradicts its pending-exception contract.
    }
    fn size(&self) -> Result<(), u32> {
        let result = (|| {
            let saved = self.get(POS)?;
            self.call(SEEK, 0, 2, 0)?;
            let size = self.get(POS)?;
            self.call(SEEK, saved, 0, 0)?;
            self.set(RETURN, size)?;
            Ok(())
        })();
        if result == Err(1) {
            match self.get(EXCEPTION_KIND)? {
                1 => {
                    self.get(WRAP_SIZE)?;
                    return Err(2); // A wrapper cannot erase a pending exception.
                }
                2 => return Err(1),
                _ => return Err(2),
            }
        }
        result
    }
    fn run(&self, mode: u32) -> Result<(), u32> {
        match mode {
            0 | 19 => self.store(self.arg(0)?)?,
            20 | 21 => self.store(self.get(SOURCE_MODE)?)?,
            1 => {
                self.get(BASE_CLOSE)?;
            }
            2 => return self.error(0),
            3 | 4 => {
                let len = self.arg(1)?;
                let r = self.call(if mode == 3 { READ } else { WRITE }, 0, len, 0)?;
                if r < len {
                    let end = self.get(END)? != 0;
                    return self.error(if mode == 3 {
                        if end {
                            1
                        } else {
                            2
                        }
                    } else if end {
                        3
                    } else {
                        4
                    });
                }
            }
            5 => {
                let m = self.arg(0)?;
                if m > 255 {
                    return Err(2);
                }
                let old = self.get(MODE)?;
                if old > 255 {
                    return Err(2);
                }
                if m != old {
                    self.get(NAME)?;
                    return self.error(5);
                }
            }
            6 => self.store(0)?,
            7 => {}
            8 => {
                self.get(NAME_BASE)?;
            }
            9 => {
                // Fixed Apple left-first profile; preserve signed StreamOffset comparison.
                let pos = self.get(POS)? as i64;
                let size = self.get(VIRTUAL_SIZE)? as i64;
                self.set(RETURN, u64::from(pos >= size))?;
            }
            10 => self.size()?,
            11 | 12 => {
                let saved = self.get(POS)?;
                let offset = self.arg(0)?;
                let len = self.arg(1)?;
                self.call(SEEK, offset, 0, 0)?;
                let r = self.call(if mode == 11 { READ } else { WRITE }, 0, len, 0)?;
                // A failed virtual I/O intentionally skips restoration, as in the source.
                self.call(SEEK, saved, 0, 0)?;
                self.set(RETURN, r)?;
            }
            13 | 14 => {
                let mut offset = self.arg(0)?;
                let mut left = self.arg(1)?;
                let mut index = 0u64;
                while left != 0 {
                    let r = self.call(
                        if mode == 13 { READ_ABS } else { WRITE_ABS },
                        offset,
                        index,
                        left,
                    )?;
                    if r == 0 {
                        return self.error(if mode == 13 { 6 } else { 7 });
                    }
                    if r > left {
                        return Err(2);
                    }
                    index = index.checked_add(r).ok_or(2u32)?;
                    offset = offset.wrapping_add(r);
                    left -= r;
                }
            }
            15 | 17 => {
                let n = self.arg(if mode == 15 { 0 } else { 1 })?;
                if n != 0 {
                    self.set(ARRAY_ALLOC, n)?;
                    if mode == 15 {
                        self.call(READFULL, 0, n, 0)?;
                    } else {
                        self.call(READFULLABS, self.arg(0)?, 0, n)?;
                    }
                }
            }
            16 | 18 => {
                let n = self.get(CAPTURE_INPUT_BYTES)?;
                if mode == 16 {
                    self.call(WRITEFULL, 0, n, 0)?;
                } else {
                    self.call(WRITEFULLABS, self.arg(0)?, 0, n)?;
                }
            }
            _ => return Err(2),
        }
        self.get(FINISH)?;
        Ok(())
    }
}
fn contained(f: impl FnOnce() -> Result<(), u32>) -> u32 {
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(Ok(())) => 0,
        Ok(Err(s)) => s,
        Err(_) => 3,
    }
}
/// Runs the source controller without retaining native state.
///
/// # Safety
/// Host and context obey StarRustIODevice.h, including no unwinding across the
/// callback ABI. Only Rust panics originating inside the controller are caught.
#[no_mangle]
pub unsafe extern "C" fn star_io_device_run(
    mode: u32,
    ctx: *mut c_void,
    host: Option<StarIODeviceHost>,
) -> u32 {
    let host = match host {
        Some(host) if mode < 22 => host,
        _ => return 2,
    };
    count(mode, 0);
    let status = contained(|| Driver { ctx, host }.run(mode));
    if status == 0 {
        count(mode, 1);
    } else if status == 1 {
        count(mode, 2);
    }
    status
}

#[cfg(test)]
mod tests {
    use super::*;
    type Step = (u32, u64, u64, u64, u64, u32);
    struct Script {
        steps: Vec<Step>,
        next: usize,
        mismatch: bool,
    }
    unsafe extern "C" fn host(
        p: *mut c_void,
        op: u32,
        a: u64,
        b: u64,
        c: u64,
        out: *mut u64,
    ) -> u32 {
        let s = &mut *p.cast::<Script>();
        let Some(&(want, x, y, z, value, status)) = s.steps.get(s.next) else {
            s.mismatch = true;
            return 2;
        };
        s.next += 1;
        s.mismatch |= (op, a, b, c) != (want, x, y, z);
        *out = value;
        status
    }
    fn get(op: u32, value: u64) -> Step {
        (op, 0, 0, 0, value, 0)
    }
    fn call(op: u32, a: u64, b: u64, c: u64) -> Step {
        (op, a, b, c, 0, 0)
    }
    fn arg(n: u64, v: u64) -> Step {
        (ARG, n, 0, 0, v, 0)
    }
    fn routes() -> Vec<Vec<Step>> {
        vec![
            vec![arg(0, 3), call(STORE_MODE, 3, 0, 0)],
            vec![get(BASE_CLOSE, 0)],
            vec![(ERROR, 0, 0, 0, 0, 1)],
            vec![arg(1, 4), (READ, 0, 4, 0, 4, 0)],
            vec![arg(1, 4), (WRITE, 0, 4, 0, 4, 0)],
            vec![arg(0, 3), get(MODE, 3)],
            vec![call(STORE_MODE, 0, 0, 0)],
            vec![],
            vec![get(NAME_BASE, 0)],
            vec![get(POS, 3), get(VIRTUAL_SIZE, 8), call(RETURN, 0, 0, 0)],
            vec![
                get(POS, 3),
                call(SEEK, 0, 2, 0),
                get(POS, 8),
                call(SEEK, 3, 0, 0),
                call(RETURN, 8, 0, 0),
            ],
            vec![
                get(POS, 3),
                arg(0, 9),
                arg(1, 4),
                call(SEEK, 9, 0, 0),
                (READ, 0, 4, 0, 4, 0),
                call(SEEK, 3, 0, 0),
                call(RETURN, 4, 0, 0),
            ],
            vec![
                get(POS, 3),
                arg(0, 9),
                arg(1, 4),
                call(SEEK, 9, 0, 0),
                (WRITE, 0, 4, 0, 4, 0),
                call(SEEK, 3, 0, 0),
                call(RETURN, 4, 0, 0),
            ],
            vec![
                arg(0, 9),
                arg(1, 4),
                (READ_ABS, 9, 0, 4, 2, 0),
                (READ_ABS, 11, 2, 2, 2, 0),
            ],
            vec![
                arg(0, 9),
                arg(1, 4),
                (WRITE_ABS, 9, 0, 4, 2, 0),
                (WRITE_ABS, 11, 2, 2, 2, 0),
            ],
            vec![
                arg(0, 4),
                call(ARRAY_ALLOC, 4, 0, 0),
                call(READFULL, 0, 4, 0),
            ],
            vec![get(CAPTURE_INPUT_BYTES, 4), call(WRITEFULL, 0, 4, 0)],
            vec![
                arg(1, 4),
                call(ARRAY_ALLOC, 4, 0, 0),
                arg(0, 9),
                call(READFULLABS, 9, 0, 4),
            ],
            vec![
                get(CAPTURE_INPUT_BYTES, 4),
                arg(0, 9),
                call(WRITEFULLABS, 9, 0, 4),
            ],
            vec![arg(0, 3), call(STORE_MODE, 3, 0, 0)],
            vec![get(SOURCE_MODE, 3), call(STORE_MODE, 3, 0, 0)],
            vec![get(SOURCE_MODE, 3), call(STORE_MODE, 3, 0, 0)],
        ]
    }
    fn check(mode: u32, mut steps: Vec<Step>, status: u32) {
        if status == 0 {
            steps.push(get(FINISH, 0));
        }
        let mut s = Script {
            steps,
            next: 0,
            mismatch: false,
        };
        let before: Vec<_> = (0..3).map(|e| star_io_device_call_count(mode, e)).collect();
        let actual =
            unsafe { star_io_device_run(mode, (&mut s as *mut Script).cast(), Some(host)) };
        assert_eq!(actual, status, "mode {mode}, step {}", s.next);
        assert!(!s.mismatch, "mode {mode}, step {}", s.next);
        assert_eq!(s.next, s.steps.len(), "mode {mode}");
        assert_eq!(
            star_io_device_call_count(mode, 0),
            before[0].wrapping_add(1)
        );
        assert_eq!(
            star_io_device_call_count(mode, 1),
            before[1].wrapping_add(u64::from(status == 0))
        );
        assert_eq!(
            star_io_device_call_count(mode, 2),
            before[2].wrapping_add(u64::from(status == 1))
        );
    }
    #[test]
    fn all_routes_all_op_shapes_and_early_failure_prefixes() {
        let mut seen = [false; 27];
        for (mode, route) in routes().into_iter().enumerate() {
            for s in &route {
                seen[s.0 as usize] = true;
            }
            check(mode as u32, route.clone(), if mode == 2 { 1 } else { 0 });
            if mode == 2 {
                continue;
            }
            let mut full = route;
            full.push(get(FINISH, 0));
            for i in 0..full.len() {
                for status in [1, 2, 7] {
                    let mut prefix = full[..=i].to_vec();
                    prefix[i].5 = status;
                    // Size's inner try classifies only native pending, not protocol errors.
                    if mode == 10 && status == 1 && i + 1 < full.len() {
                        prefix.push(get(EXCEPTION_KIND, 2));
                    }
                    check(mode as u32, prefix, if status == 1 { 1 } else { 2 });
                }
            }
        }
        for (mode, steps, status) in [
            (
                5,
                vec![
                    arg(0, 1),
                    get(MODE, 3),
                    get(NAME, 0),
                    (ERROR, 5, 0, 0, 0, 1),
                ],
                1,
            ),
            (
                3,
                vec![
                    arg(1, 1),
                    call(READ, 0, 1, 0),
                    get(END, 0),
                    (ERROR, 2, 0, 0, 0, 1),
                ],
                1,
            ),
            (
                10,
                vec![
                    (POS, 0, 0, 0, 0, 1),
                    get(EXCEPTION_KIND, 1),
                    (WRAP_SIZE, 0, 0, 0, 0, 1),
                ],
                1,
            ),
        ] {
            for s in &steps {
                seen[s.0 as usize] = true;
            }
            check(mode, steps, status);
        }
        // check() appends and verifies this exact no-argument FINISH shape.
        seen[FINISH as usize] = true;
        assert!(seen[1..].iter().all(|x| *x));
    }
    #[test]
    fn size_classification_wrapper_and_invalid_metadata() {
        for failing in 0..5 {
            let route = routes().remove(10);
            for kind in [0, 1, 2, 3, u64::MAX] {
                let mut prefix = route[..=failing].to_vec();
                prefix[failing].5 = 1;
                prefix.push(get(EXCEPTION_KIND, kind));
                if kind == 1 {
                    prefix.push((WRAP_SIZE, 0, 0, 0, 0, 1));
                }
                check(10, prefix, if kind == 1 || kind == 2 { 1 } else { 2 });
            }
        }
        for status in [0, 2, 99] {
            check(
                10,
                vec![
                    (POS, 0, 0, 0, 0, 1),
                    get(EXCEPTION_KIND, 1),
                    (WRAP_SIZE, 0, 0, 0, 0, status),
                ],
                2,
            );
        }
        check(
            10,
            vec![(POS, 0, 0, 0, 0, 1), (EXCEPTION_KIND, 0, 0, 0, 0, 2)],
            2,
        );
    }
    #[test]
    fn zero_and_full_progress_boundaries() {
        for (mode, op) in [(3, READ), (4, WRITE)] {
            check(mode, vec![arg(1, 0), call(op, 0, 0, 0)], 0);
            for end in [0, 1] {
                let error = if mode == 3 {
                    if end == 1 {
                        1
                    } else {
                        2
                    }
                } else if end == 1 {
                    3
                } else {
                    4
                };
                check(
                    mode,
                    vec![
                        arg(1, u64::MAX),
                        call(op, 0, u64::MAX, 0),
                        get(END, end),
                        (ERROR, error, 0, 0, 0, 1),
                    ],
                    1,
                );
            }
        }
        check(15, vec![arg(0, 0)], 0);
        check(17, vec![arg(1, 0)], 0);
        check(
            16,
            vec![get(CAPTURE_INPUT_BYTES, 0), call(WRITEFULL, 0, 0, 0)],
            0,
        );
        check(
            18,
            vec![
                get(CAPTURE_INPUT_BYTES, 0),
                arg(0, 9),
                call(WRITEFULLABS, 9, 0, 0),
            ],
            0,
        );
        for (mode, op, error) in [(13, READ_ABS, 6), (14, WRITE_ABS, 7)] {
            check(mode, vec![arg(0, 9), arg(1, 0)], 0);
            check(
                mode,
                vec![
                    arg(0, 9),
                    arg(1, u64::MAX),
                    call(op, 9, 0, u64::MAX),
                    (ERROR, error, 0, 0, 0, 1),
                ],
                1,
            );
            check(mode, vec![arg(0, 9), arg(1, 1), (op, 9, 0, 1, 2, 0)], 2);
            check(
                mode,
                vec![
                    arg(0, u64::MAX),
                    arg(1, 3),
                    (op, u64::MAX, 0, 3, 2, 0),
                    (op, 1, 2, 1, 1, 0),
                ],
                0,
            );
            // Huge requested capacity is accepted when actual progress fits the index.
            check(
                mode,
                vec![
                    arg(0, 0),
                    arg(1, u64::MAX),
                    (op, 0, 0, u64::MAX, u64::MAX - 1, 0),
                    (op, u64::MAX - 1, u64::MAX - 1, 1, 1, 0),
                ],
                0,
            );
        }
    }
    #[test]
    fn mode_domain_signed_compare_error_contradiction_and_preflight() {
        for mode in [0, 19, 20, 21] {
            for value in [0, 255, 256, u64::MAX] {
                let first = if mode < 20 {
                    arg(0, value)
                } else {
                    get(SOURCE_MODE, value)
                };
                let mut steps = vec![first];
                if value <= 255 {
                    steps.push(call(STORE_MODE, value, 0, 0));
                }
                check(mode, steps, if value <= 255 { 0 } else { 2 });
            }
        }
        check(5, vec![arg(0, 256)], 2);
        check(5, vec![arg(0, 0), get(MODE, 256)], 2);
        check(
            9,
            vec![
                get(POS, u64::MAX),
                get(VIRTUAL_SIZE, 0),
                call(RETURN, 0, 0, 0),
            ],
            0,
        );
        check(2, vec![get(ERROR, 0)], 2);
        let before = star_io_device_call_count(0, 0);
        assert_eq!(
            unsafe { star_io_device_run(0, std::ptr::null_mut(), None) },
            2
        );
        assert_eq!(
            unsafe { star_io_device_run(22, std::ptr::null_mut(), Some(host)) },
            2
        );
        assert_eq!(star_io_device_call_count(0, 0), before);
        assert_eq!(star_io_device_call_count(22, 0), 0);
        assert_eq!(star_io_device_call_count(0, 3), 0);
        unsafe extern "C" fn null_host(
            _: *mut c_void,
            _: u32,
            _: u64,
            _: u64,
            _: u64,
            out: *mut u64,
        ) -> u32 {
            *out = 0;
            0
        }
        assert_eq!(
            unsafe { star_io_device_run(7, std::ptr::null_mut(), Some(null_host)) },
            0
        );
    }
    #[test]
    fn rust_only_panic_and_wrapping_reentry_counters() {
        assert_eq!(contained(|| panic!("Rust controller test")), 3);
        let old = COUNTS.with(|c| c.get());
        COUNTS.with(|c| {
            let mut x = c.get();
            x[7] = [u64::MAX; 3];
            c.set(x)
        });
        unsafe extern "C" fn reenter(
            _: *mut c_void,
            _: u32,
            _: u64,
            _: u64,
            _: u64,
            out: *mut u64,
        ) -> u32 {
            *out = 0;
            star_io_device_run(7, std::ptr::null_mut(), Some(leaf))
        }
        unsafe extern "C" fn leaf(
            _: *mut c_void,
            _: u32,
            _: u64,
            _: u64,
            _: u64,
            out: *mut u64,
        ) -> u32 {
            *out = 0;
            0
        }
        assert_eq!(
            unsafe { star_io_device_run(7, std::ptr::null_mut(), Some(reenter)) },
            0
        );
        assert_eq!(star_io_device_call_count(7, 0), 1);
        assert_eq!(star_io_device_call_count(7, 1), 1);
        COUNTS.with(|c| c.set(old));
    }
}
