//! Buffer control flow over opaque, synchronous native leaves.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
pub type StarBufferHost = unsafe extern "C" fn(*mut c_void, u32, u64, u64, *mut u64) -> u32;
thread_local! { static COUNTS: Cell<[[u64;3];50]> = const { Cell::new([[0;3];50]) }; }
fn count(mode: u32, event: usize) {
    COUNTS.with(|c| {
        let mut v = c.get();
        v[mode as usize][event] = v[mode as usize][event].wrapping_add(1);
        c.set(v);
    });
}
#[no_mangle]
pub extern "C" fn star_buffer_call_count(mode: u32, event: u32) -> u64 {
    if mode >= 50 || event >= 3 {
        return 0;
    }
    COUNTS.with(|c| c.get()[mode as usize][event as usize])
}
const ARG: u32 = 1;
const POS: u32 = 2;
const SET_POS: u32 = 3;
const SIZE: u32 = 4;
const MODE: u32 = 5;
const SET_MODE: u32 = 6;
const STORAGE: u32 = 7;
const CHILD: u32 = 8;
const COPY_OUT: u32 = 9;
const COPY_IN: u32 = 10;
const ERROR: u32 = 11;
const RESULT: u32 = 12;
const FINISH: u32 = 13;
const SOURCE_POS: u32 = 14;
const SET_SOURCE_POS: u32 = 15;
const BASE_COPY: u32 = 16;
const SOURCE_STORAGE: u32 = 17;
const EXTERNAL_INIT: u32 = 18;
const EXTERNAL_BIND: u32 = 19;
const NAME: u32 = 20;
const CLONE_ALLOC: u32 = 21;
const CLONE_SEEK: u32 = 22;
const LOG: u32 = 23;
const REF: u32 = 24;
const PTR: u32 = 25;
struct Driver {
    ctx: *mut c_void,
    host: StarBufferHost,
}
impl Driver {
    fn call(&self, op: u32, a: u64, b: u64) -> Result<u64, u32> {
        let mut out = 0;
        // No native reference, view or object representation survives a callback.
        match unsafe { (self.host)(self.ctx, op, a, b, &mut out) } {
            0 => Ok(out),
            1 => Err(1),
            _ => Err(2),
        }
    }
    fn get(&self, op: u32) -> Result<u64, u32> {
        self.call(op, 0, 0)
    }
    fn set(&self, op: u32, a: u64) -> Result<u64, u32> {
        self.call(op, a, 0)
    }
    fn arg(&self, a: u64) -> Result<u64, u32> {
        self.set(ARG, a)
    }
    fn ret(&self, a: u64) -> Result<u64, u32> {
        self.set(RESULT, a)
    }
    fn raise(&self, a: u64) -> Result<(), u32> {
        self.set(ERROR, a)?;
        Err(2)
    }
    fn run(&self, m: u32) -> Result<(), u32> {
        match m {
            0 => {
                self.set(SET_POS, 0)?;
                self.set(SET_MODE, 3)?;
            }
            1 => {
                self.call(CHILD, 0, self.arg(0)?)?;
            }
            2 => {
                self.set(CHILD, 1)?;
            }
            3 => {
                self.set(CHILD, 2)?;
            }
            4 => {
                self.set(CHILD, 3)?;
            }
            5 | 33 => {
                self.ret(self.get(POS)?)?;
            }
            6 | 34 => {
                let old = self.get(POS)?;
                let p = self.arg(0)?;
                let mode = self.arg(1)?;
                if mode > 255 {
                    return Err(2);
                }
                let n = match mode {
                    0 => p,
                    1 => (old as i64).checked_add(p as i64).ok_or(2u32)? as u64,
                    2 => self.get(SIZE)?.wrapping_sub(p),
                    _ => old,
                };
                self.set(SET_POS, n)?;
            }
            7 => {
                self.set(CHILD, 4)?;
                self.call(STORAGE, 0, self.arg(0)?)?;
            }
            8 | 35 => {
                let p = self.get(POS)?;
                self.ret(u64::from(p >= self.get(SIZE)?))?;
            }
            9 | 10 | 36 => {
                let old = self.get(POS)?;
                let n = self.call(CHILD, if m == 10 { 6 } else { 5 }, old)?;
                // A child may reenter and change the cursor: read it again.
                self.set(SET_POS, self.get(POS)?.wrapping_add(n))?;
                self.ret(n)?;
            }
            11 | 12 | 38 => {
                let p = self.arg(0)?;
                self.ret(self.call(CHILD, if m == 12 { 6 } else { 5 }, p)?)?;
            }
            13 => {
                let mode = self.arg(0)?;
                if mode > 255 {
                    return Err(2);
                }
                self.set(SET_MODE, mode)?;
                // Branch on the original argument even if virtual resize reenters open.
                if mode & 2 != 0 && mode & 8 != 0 {
                    self.call(CHILD, 7, 0)?;
                }
                if mode & 4 != 0 {
                    self.set(CHILD, 8)?;
                }
            }
            14 | 40 => {
                self.get(NAME)?;
            }
            15 | 21 | 41 | 43 => {
                self.ret(self.get(SIZE)?)?;
            }
            16 | 17 => {
                self.get(REF)?;
            }
            18 => {
                self.set(STORAGE, 5)?;
                self.call(CHILD, 0, 0)?;
            }
            19 => {
                self.set(CHILD, 4)?;
                self.get(PTR)?;
            }
            20 | 42 => {
                self.get(PTR)?;
            }
            22 => {
                self.set(CHILD, 4)?;
                self.call(STORAGE, 1, self.arg(0)?)?;
            }
            23 => {
                self.set(SET_POS, 0)?;
                self.set(STORAGE, 2)?;
            }
            24 | 44 | 45 => {
                self.ret(u64::from(self.get(SIZE)? == 0))?;
            }
            25 => {
                self.set(SET_POS, 0)?;
                self.call(STORAGE, 3, self.arg(0)?)?;
            }
            26 => {
                self.set(SET_POS, 0)?;
                self.set(STORAGE, 4)?;
            }
            27 | 28 => {
                self.get(BASE_COPY)?;
                self.set(SET_POS, self.get(SOURCE_POS)?)?;
                self.set(SOURCE_STORAGE, u64::from(m == 28))?;
                if m == 28 {
                    self.set(SET_SOURCE_POS, 0)?;
                    self.set(SOURCE_STORAGE, 2)?;
                }
                self.get(REF)?;
            }
            29 | 49 => {
                let len = self.arg(1)?;
                if len == 0 {
                    self.ret(0)?;
                } else {
                    if self.get(MODE)? & 1 == 0 {
                        return self.raise(0);
                    }
                    let p = self.arg(0)?;
                    if p >= self.get(SIZE)? {
                        self.ret(0)?;
                    } else {
                        let n = (self.get(SIZE)? - p).min(len);
                        self.call(COPY_OUT, p, n)?;
                        self.ret(n)?;
                    }
                }
            }
            30 => {
                let len = self.arg(1)?;
                if len == 0 {
                    self.ret(0)?;
                } else {
                    if self.get(MODE)? & 2 == 0 {
                        return self.raise(1);
                    }
                    let p = self.arg(0)?;
                    let end = p.wrapping_add(len);
                    if end > self.get(SIZE)? {
                        self.call(STORAGE, 0, end)?;
                    }
                    self.call(COPY_IN, p, len)?;
                    self.ret(len)?;
                }
            }
            31 => {
                self.set(SET_POS, 0)?;
                self.get(EXTERNAL_INIT)?;
                self.set(SET_MODE, 1)?;
            }
            32 => {
                self.set(CHILD, 9)?;
            }
            37 | 39 => return self.raise(2),
            46 => {
                self.set(SET_POS, 0)?;
                self.get(EXTERNAL_BIND)?;
            }
            47 => {
                self.get(CLONE_ALLOC)?;
                self.get(CLONE_SEEK)?;
            }
            48 => {
                self.get(LOG)?;
                self.get(CLONE_ALLOC)?;
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
/// The host owns ctx and catches every native exception before returning.
/// No callback may unwind across this C ABI, including in test fixtures.
#[no_mangle]
pub unsafe extern "C" fn star_buffer_run(
    mode: u32,
    ctx: *mut c_void,
    host: Option<StarBufferHost>,
) -> u32 {
    let host = match host {
        Some(h) if mode < 50 => h,
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
    #[derive(Default)]
    struct Spy {
        args: [u64; 3],
        pos: u64,
        size: u64,
        mode: u64,
        source: u64,
        result: u64,
        child: u64,
        status: u32,
        fail_op: u32,
        events: Vec<(u32, u64, u64)>,
        reenter: bool,
    }
    unsafe extern "C" fn host(p: *mut c_void, op: u32, a: u64, b: u64, out: *mut u64) -> u32 {
        let s = &mut *(p as *mut Spy);
        s.events.push((op, a, b));
        if op == s.fail_op {
            return s.status;
        }
        let v = match op {
            ARG => s.args.get(a as usize).copied().unwrap_or(0),
            POS => s.pos,
            SIZE => s.size,
            MODE => s.mode,
            SOURCE_POS => s.source,
            SET_POS => {
                s.pos = a;
                0
            }
            SET_MODE => {
                s.mode = a;
                0
            }
            RESULT => {
                s.result = a;
                0
            }
            CHILD => {
                if s.reenter {
                    s.pos = 40;
                    s.mode = 1;
                }
                s.child
            }
            ERROR => return 1,
            _ => 0,
        };
        *out = v;
        0
    }
    fn run(m: u32, s: &mut Spy) -> u32 {
        unsafe { star_buffer_run(m, (s as *mut Spy).cast(), Some(host)) }
    }
    #[test]
    fn all_fifty_routes_and_preflight() {
        for m in 0..50 {
            let mut s = Spy {
                size: 8,
                mode: 3,
                ..Spy::default()
            };
            let before = star_buffer_call_count(m, 0);
            let code = run(m, &mut s);
            assert_eq!(code, if m == 37 || m == 39 { 1 } else { 0 }, "mode {m}");
            assert_eq!(star_buffer_call_count(m, 0), before.wrapping_add(1));
            if code == 0 {
                assert_eq!(s.events.last().unwrap().0, FINISH);
            }
        }
        let n = star_buffer_call_count(0, 0);
        assert_eq!(unsafe { star_buffer_run(0, std::ptr::null_mut(), None) }, 2);
        assert_eq!(
            unsafe { star_buffer_run(50, std::ptr::null_mut(), Some(host)) },
            2
        );
        assert_eq!(star_buffer_call_count(0, 0), n);
        assert_eq!(star_buffer_call_count(50, 0), 0);
        assert_eq!(star_buffer_call_count(0, 3), 0);
    }
    #[test]
    fn zero_mode_eof_and_huge_min() {
        for m in [29, 30, 49] {
            let mut s = Spy::default();
            assert_eq!(run(m, &mut s), 0);
            assert!(!s.events.iter().any(|e| e.0 == MODE));
        }
        let mut s = Spy {
            args: [8, 1, 0],
            size: 8,
            ..Spy::default()
        };
        assert_eq!(run(29, &mut s), 1);
        assert!(!s.events.iter().any(|e| e.0 == SIZE));
        let mut s = Spy {
            args: [0, u64::MAX, 0],
            size: 8,
            mode: 1,
            ..Spy::default()
        };
        assert_eq!(run(29, &mut s), 0);
        assert_eq!(s.result, 8);
        assert!(s.events.contains(&(COPY_OUT, 0, 8)));
        s = Spy {
            args: [u64::MAX, 1, 0],
            size: 8,
            mode: 1,
            ..Spy::default()
        };
        assert_eq!(run(49, &mut s), 0);
        assert_eq!(s.result, 0);
    }
    #[test]
    fn reentry_argument_branch_fresh_cursor_and_mode_domain() {
        let mut s = Spy {
            args: [14, 0, 0],
            reenter: true,
            ..Spy::default()
        };
        assert_eq!(run(13, &mut s), 0);
        assert!(s.events.contains(&(CHILD, 8, 0)));
        assert_eq!(s.mode, 1);
        s = Spy {
            pos: 2,
            child: 3,
            reenter: true,
            ..Spy::default()
        };
        assert_eq!(run(9, &mut s), 0);
        assert_eq!(s.pos, 43);
        for m in [6, 34] {
            s = Spy {
                pos: 9,
                args: [1, 255, 0],
                ..Spy::default()
            };
            assert_eq!(run(m, &mut s), 0);
            assert_eq!(s.pos, 9);
            s.args[1] = 256;
            assert_eq!(run(m, &mut s), 2);
            s.args = [1, 1, 0];
            s.pos = i64::MAX as u64;
            assert_eq!(run(m, &mut s), 2);
            s.args = [2, 2, 0];
            s.size = 8;
            assert_eq!(run(m, &mut s), 0);
            assert_eq!(s.pos, 6);
        }
        s = Spy {
            args: [256, 0, 0],
            ..Spy::default()
        };
        assert_eq!(run(13, &mut s), 2);
    }
    #[test]
    fn copy_move_self_and_clone_order() {
        let mut s = Spy {
            source: 17,
            ..Spy::default()
        };
        assert_eq!(run(27, &mut s), 0);
        assert_eq!(s.pos, 17);
        assert!(s.events.contains(&(SOURCE_STORAGE, 0, 0)));
        assert_eq!(run(28, &mut s), 0);
        assert!(s.events.contains(&(SET_SOURCE_POS, 0, 0)));
        assert!(s.events.contains(&(SOURCE_STORAGE, 2, 0)));
        s = Spy::default();
        assert_eq!(run(47, &mut s), 0);
        assert_eq!(
            s.events,
            vec![(CLONE_ALLOC, 0, 0), (CLONE_SEEK, 0, 0), (FINISH, 0, 0)]
        );
        s = Spy::default();
        assert_eq!(run(48, &mut s), 0);
        assert_eq!(s.events[0].0, LOG);
        assert_eq!(s.events[1].0, CLONE_ALLOC);
    }
    #[test]
    fn pending_unknown_contradiction_finish_and_contained_panic() {
        for status in [1, 2, 3, u32::MAX] {
            let mut s = Spy {
                fail_op: SIZE,
                status,
                ..Spy::default()
            };
            assert_eq!(run(24, &mut s), if status == 1 { 1 } else { 2 });
            assert_eq!(s.events.len(), 1);
        }
        let mut s = Spy {
            fail_op: ERROR,
            status: 0,
            ..Spy::default()
        };
        assert_eq!(run(37, &mut s), 2);
        assert_eq!(s.events.len(), 1);
        s = Spy {
            fail_op: FINISH,
            status: 2,
            ..Spy::default()
        };
        assert_eq!(run(0, &mut s), 2);
        assert_eq!(contained(|| panic!("internal rust fixture")), 3);
    }
    unsafe extern "C" fn null_host(
        p: *mut c_void,
        op: u32,
        _a: u64,
        _b: u64,
        out: *mut u64,
    ) -> u32 {
        if !p.is_null() {
            return 2;
        }
        *out = 0;
        if [SIZE, RESULT, FINISH].contains(&op) {
            0
        } else {
            2
        }
    }
    #[test]
    fn null_custom_and_tls_wrapping() {
        assert_eq!(
            unsafe { star_buffer_run(24, std::ptr::null_mut(), Some(null_host)) },
            0
        );
        COUNTS.with(|c| {
            let mut v = c.get();
            v[0][0] = u64::MAX;
            c.set(v)
        });
        let mut s = Spy::default();
        assert_eq!(run(0, &mut s), 0);
        assert_eq!(star_buffer_call_count(0, 0), 0);
        std::thread::spawn(|| assert_eq!(star_buffer_call_count(0, 0), 0))
            .join()
            .unwrap();
    }
}
