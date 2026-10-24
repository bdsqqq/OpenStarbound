//! Opaque streaming controllers: native leaves retain allocation, codec and exception ownership.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

pub type StarCompressionHost = unsafe extern "C" fn(*mut c_void, u32, u64, *mut u64) -> u32;
const SLAB: u64 = 32768;
const BUF_ERROR: u64 = (-5i32 as u32) as u64;
thread_local! { static COUNTS: Cell<[[u64; 3]; 3]> = const { Cell::new([[0; 3]; 3]) }; }
fn count(kind: u32, event: usize) {
    COUNTS.with(|c| {
        let mut v = c.get();
        v[kind as usize][event] = v[kind as usize][event].wrapping_add(1);
        c.set(v);
    });
}
#[no_mangle]
pub extern "C" fn star_compression_call_count(kind: u32, event: u32) -> u64 {
    if kind > 2 || event > 2 {
        return 0;
    }
    COUNTS.with(|c| c.get()[kind as usize][event as usize])
}
struct Driver {
    host: StarCompressionHost,
    context: *mut c_void,
}
impl Driver {
    fn call(&self, op: u32, arg: u64) -> Result<u64, u32> {
        let mut scalar = 0;
        // The caller guarantees a non-unwinding host. Context is opaque, even when null.
        match unsafe { (self.host)(self.context, op, arg, &mut scalar) } {
            0 => Ok(scalar),
            1 => Err(1),
            _ => Err(2),
        }
    }
    fn leaf(&self, op: u32, arg: u64) -> Result<(), u32> {
        if self.call(op, arg)? == 0 {
            Ok(())
        } else {
            Err(2)
        }
    }
    fn codec(&self, op: u32) -> Result<u64, u32> {
        let code = self.call(op, 0)?;
        if code <= u32::MAX as u64 {
            Ok(code)
        } else {
            Err(2)
        }
    }
    fn avail(&self) -> Result<u64, u32> {
        let n = self.call(8, 0)?;
        if n <= SLAB {
            Ok(n)
        } else {
            Err(2)
        }
    }
    fn raise(&self, op: u32, arg: u64) -> Result<(), u32> {
        // A successful error-constructor callback contradicts the host contract.
        self.call(op, arg)?;
        Err(2)
    }
    fn run(&self, kind: u32) -> Result<(), u32> {
        self.leaf(0, kind as u64)?;
        match self.call(1, 0)? {
            1 => return Ok(()),
            0 => (),
            _ => return Err(2),
        }
        self.leaf(2, 0)?;
        self.leaf(3, 0)?;
        let mut code = self.codec(4)?;
        if code != 0 {
            return self.raise(13, code);
        }
        self.leaf(5, 0)?;
        self.leaf(6, 0)?;
        while code == 0 || (kind != 0 && code == BUF_ERROR) {
            code = self.codec(7)?;
            let avail = self.avail()?; // Required even when Step returned an error.
            if avail == 0 {
                self.leaf(9, SLAB)?; // No implicit End on append failure.
                self.leaf(6, 0)?;
                if kind != 0 {
                    let limit = self.call(10, 0)?;
                    if limit != 0 && self.call(11, 0)? >= limit {
                        self.codec(12)?;
                        return self.raise(15, 0);
                    }
                }
            } else if kind != 0 && code == BUF_ERROR {
                break;
            }
        }
        self.codec(12)?; // Ignore valid End code, preserving the final Step code.
        if code != 1 {
            return self.raise(14, code);
        }
        let avail = self.avail()?;
        self.leaf(9, SLAB - avail) // Includes a zero-length tail, after End.
    }
}
/// Runs a controller without inspecting native layouts or retaining pointers.
///
/// # Safety
/// The host must accept this opaque context and a live aligned scalar pointer,
/// initialize the scalar on success, and never unwind across the C ABI.
#[no_mangle]
pub unsafe extern "C" fn star_compression_run(
    kind: u32,
    host: Option<StarCompressionHost>,
    context: *mut c_void,
) -> u32 {
    if kind > 2 || host.is_none() {
        return 2;
    }
    contained(kind, || {
        Driver {
            host: host.unwrap(),
            context,
        }
        .run(kind)
    })
}

fn contained(kind: u32, run: impl FnOnce() -> Result<(), u32>) -> u32 {
    count(kind, 0);
    match catch_unwind(AssertUnwindSafe(run)) {
        Ok(Ok(())) => {
            count(kind, 1);
            0
        }
        Ok(Err(1)) => {
            count(kind, 2);
            1
        }
        Ok(Err(_)) => 2,
        Err(_) => 3,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[derive(Clone, Copy, Debug)]
    struct Event(u32, u64, u64, u32);
    struct Script {
        events: Vec<Event>,
        cursor: usize,
        bad: bool,
    }
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, arg: u64, out: *mut u64) -> u32 {
        let s = &mut *(ctx as *mut Script);
        let Some(e) = s.events.get(s.cursor).copied() else {
            s.bad = true;
            return 2;
        };
        s.cursor += 1;
        if (op, arg) != (e.0, e.1) {
            s.bad = true;
            return 2;
        }
        if e.3 == 0 {
            *out = e.2;
        }
        e.3
    }
    fn run(kind: u32, events: Vec<Event>, expected: u32) {
        let mut s = Script {
            events,
            cursor: 0,
            bad: false,
        };
        let before = [0, 1, 2].map(|e| star_compression_call_count(kind, e));
        assert_eq!(
            unsafe { star_compression_run(kind, Some(host), &mut s as *mut _ as *mut c_void) },
            expected
        );
        assert!(!s.bad, "bad trace at {}: {:?}", s.cursor, s.events);
        assert_eq!(s.cursor, s.events.len());
        assert_eq!(star_compression_call_count(kind, 0), before[0] + 1);
        assert_eq!(
            star_compression_call_count(kind, 1),
            before[1] + u64::from(expected == 0)
        );
        assert_eq!(
            star_compression_call_count(kind, 2),
            before[2] + u64::from(expected == 1)
        );
    }
    fn e(op: u32, value: u64) -> Event {
        Event(op, 0, value, 0)
    }
    fn prefix(k: u32) -> Vec<Event> {
        vec![
            Event(0, k as u64, 0, 0),
            e(1, 0),
            e(2, 0),
            e(3, 0),
            e(4, 0),
            e(5, 0),
            e(6, 0),
        ]
    }
    fn paths(k: u32) -> Vec<Vec<Event>> {
        let mut normal = prefix(k);
        normal.extend([
            e(7, 1),
            e(8, 32763),
            e(12, u32::MAX as u64),
            e(8, 32763),
            Event(9, 5, 0, 0),
        ]);
        let init = vec![
            Event(0, k as u64, 0, 0),
            e(1, 0),
            e(2, 0),
            e(3, 0),
            e(4, (-2i32 as u32) as u64),
            Event(13, (-2i32 as u32) as u64, 0, 1),
        ];
        let mut error = prefix(k);
        error.extend([
            e(7, (-3i32 as u32) as u64),
            e(8, 32763),
            e(12, 0),
            Event(14, (-3i32 as u32) as u64, 0, 1),
        ]);
        let mut full = prefix(k);
        full.extend([e(7, 1), e(8, 0), Event(9, SLAB, 0, 0), e(6, 0)]);
        if k != 0 {
            full.push(e(10, 0));
        }
        full.extend([e(12, 0), e(8, SLAB), Event(9, 0, 0, 0)]);
        let mut result = vec![normal, init, error, full];
        if k != 0 {
            let mut limit = prefix(k);
            limit.extend([
                e(7, (-3i32 as u32) as u64),
                e(8, 0),
                Event(9, SLAB, 0, 0),
                e(6, 0),
                e(10, 1),
                e(11, SLAB),
                e(12, 0),
                Event(15, 0, 0, 1),
            ]);
            result.push(limit);
        }
        result
    }
    #[test]
    fn traces_statuses_and_failures_at_every_leaf() {
        let mut seen = [false; 16];
        for k in 0..3 {
            for path in paths(k) {
                for e in &path {
                    seen[e.0 as usize] = true;
                }
                run(
                    k,
                    path.clone(),
                    if path.last().unwrap().3 == 1 { 1 } else { 0 },
                );
                for i in 0..path.len() {
                    for status in [1, 2, 9] {
                        let mut fault = path[..=i].to_vec();
                        fault[i].3 = status;
                        run(k, fault, if status == 1 { 1 } else { 2 });
                    }
                }
            }
        }
        assert!(seen.into_iter().all(|b| b));
    }
    #[test]
    fn protocol_preflight_and_scalar_domains() {
        let before = star_compression_call_count(0, 0);
        assert_eq!(
            unsafe { star_compression_run(3, Some(host), std::ptr::null_mut()) },
            2
        );
        assert_eq!(
            unsafe { star_compression_run(0, None, std::ptr::null_mut()) },
            2
        );
        assert_eq!(star_compression_call_count(0, 0), before);
        assert_eq!(star_compression_call_count(3, 0), 0);
        assert_eq!(star_compression_call_count(0, 3), 0);
        run(0, vec![e(0, 7)], 2);
        run(0, vec![e(0, 0), e(1, 2)], 2);
        run(0, vec![e(0, 0), e(1, 1)], 0);
        let mut v = prefix(0);
        v.truncate(5);
        v[4].2 = 1 << 32;
        run(0, v, 2);
        let mut v = prefix(0);
        v.extend([e(7, 1), e(8, SLAB + 1)]);
        run(0, v, 2);
        let mut v = prefix(0);
        v.extend([e(7, 1), e(8, 1), e(12, 1 << 32)]);
        run(0, v, 2);
        let mut v = paths(0)[1].clone();
        v.last_mut().unwrap().3 = 0;
        run(0, v, 2);
    }
    #[test]
    fn continued_nonfull_ok_and_inflate_buf_error() {
        for k in 0..3 {
            let mut v = prefix(k);
            v.extend([
                e(7, 0),
                e(8, 5),
                e(7, 1),
                e(8, 5),
                e(12, 0),
                e(8, 5),
                Event(9, SLAB - 5, 0, 0),
            ]);
            run(k, v, 0);
        }
        for k in 1..3 {
            let mut v = prefix(k);
            v.extend([
                e(7, BUF_ERROR),
                e(8, 5),
                e(12, 0),
                Event(14, BUF_ERROR, 0, 1),
            ]);
            run(k, v, 1);
            let mut v = prefix(k);
            v.extend([
                e(7, BUF_ERROR),
                e(8, 0),
                Event(9, SLAB, 0, 0),
                e(6, 0),
                e(10, 0),
                e(7, 1),
                e(8, 5),
                e(12, 0),
                e(8, 5),
                Event(9, SLAB - 5, 0, 0),
            ]);
            run(k, v, 0);
        }
    }
    unsafe extern "C" fn nested(_: *mut c_void, op: u32, _: u64, out: *mut u64) -> u32 {
        if op == 0 {
            assert_eq!(
                star_compression_run(2, Some(empty), std::ptr::null_mut()),
                0
            );
        }
        empty(std::ptr::null_mut(), op, 0, out)
    }
    unsafe extern "C" fn empty(_: *mut c_void, op: u32, _: u64, out: *mut u64) -> u32 {
        *out = u64::from(op == 1);
        0
    }
    #[test]
    fn contained_panic_counts_attempt_not_native_exception() {
        let before = [0, 1, 2].map(|e| star_compression_call_count(1, e));
        assert_eq!(contained(1, || panic!("isolated Rust panic")), 3);
        assert_eq!(star_compression_call_count(1, 0), before[0] + 1);
        assert_eq!(star_compression_call_count(1, 1), before[1]);
        assert_eq!(star_compression_call_count(1, 2), before[2]);
    }
    #[test]
    fn reentry_null_opaque_and_thread_local_counters() {
        let before = star_compression_call_count(2, 0);
        assert_eq!(
            unsafe { star_compression_run(0, Some(nested), std::ptr::null_mut()) },
            0
        );
        assert_eq!(star_compression_call_count(2, 0), before + 1);
        std::thread::spawn(|| assert_eq!(star_compression_call_count(2, 0), 0))
            .join()
            .unwrap();
    }
}
