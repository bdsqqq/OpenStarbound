//! Opaque Zstd controllers. Native leaves retain buffers, codecs and exceptions.
use std::cell::Cell;
use std::ffi::c_void;
use std::mem::MaybeUninit;
use std::panic::{catch_unwind, AssertUnwindSafe};

pub type StarZstdHost = unsafe extern "C" fn(*mut c_void, u32, u64, u64, *mut u64) -> u32;
thread_local! { static COUNTS: Cell<[[u64; 3]; 4]> = const { Cell::new([[0; 3]; 4]) }; }
fn count(mode: u32, event: usize) {
    COUNTS.with(|c| {
        let mut v = c.get();
        v[mode as usize][event] = v[mode as usize][event].wrapping_add(1);
        c.set(v);
    });
}
#[no_mangle]
pub extern "C" fn star_zstd_call_count(mode: u32, event: u32) -> u64 {
    if mode > 3 || event > 2 {
        return 0;
    }
    COUNTS.with(|c| c.get()[mode as usize][event as usize])
}
struct Driver {
    host: StarZstdHost,
    context: *mut c_void,
}
impl Driver {
    fn call(&self, op: u32, a: u64, b: u64) -> Result<u64, u32> {
        let mut value = MaybeUninit::<u64>::uninit();
        // No reference to native storage survives a callback. Success alone initializes scalar.
        match unsafe { (self.host)(self.context, op, a, b, value.as_mut_ptr()) } {
            0 => Ok(unsafe { value.assume_init() }),
            1 => Err(1),
            _ => Err(2),
        }
    }
    fn get(&self, field: u64) -> Result<u64, u32> {
        self.call(1, field, 0)
    }
    fn leaf(&self, op: u32, a: u64, b: u64) -> Result<(), u32> {
        if self.call(op, a, b)? == 0 {
            Ok(())
        } else {
            Err(2)
        }
    }
    fn raise(&self, op: u32, a: u64) -> Result<(), u32> {
        self.call(op, a, 0)?;
        Err(2) // A successful error constructor contradicts the protocol.
    }
    fn checked(&self, ret: u64) -> Result<(), u32> {
        match self.call(13, ret, 0)? {
            0 => Ok(()),
            1 => self.raise(14, ret),
            _ => Err(2),
        }
    }
    fn run(&self, mode: u32) -> Result<(), u32> {
        self.leaf(0, mode as u64, 0)?;
        if mode < 2 {
            let chunk = self.call(2, 0, 0)?;
            self.leaf(3, 0, 0)?;
            let mut written = self.get(3)?;
            self.leaf(4, self.get(3)?.wrapping_add(chunk), 0)?;
            loop {
                let capacity = chunk.min(self.get(3)?.wrapping_sub(written));
                self.leaf(5, written, capacity)?;
                let ret = self.call(if mode == 0 { 6 } else { 7 }, 0, 0)?;
                self.checked(ret)?;
                let pos = self.get(4)?;
                written = written.wrapping_add(pos);
                if pos == self.get(5)? {
                    if written >= self.get(3)? {
                        self.leaf(4, self.get(3)?.wrapping_mul(2), 0)?;
                    }
                    continue; // Full output wins even when input is consumed and ret == 0.
                }
                if (mode == 1 || ret == 0) && self.get(1)? == self.get(2)? {
                    break;
                }
            }
            self.leaf(4, written, 0)
        } else {
            if mode == 2 && self.get(0)? == 0 {
                return self.leaf(17, 0, 0);
            }
            let size = if mode == 2 {
                self.call(8, 0, 0)?
            } else {
                let size = self.call(9, 0, 0)?;
                if size == self.get(6)? || size == self.get(7)? {
                    return self.raise(15, 0);
                }
                size
            };
            self.leaf(10, size, 0)?;
            let ret = self.call(if mode == 2 { 11 } else { 12 }, 0, 0)?;
            self.checked(ret)?;
            self.leaf(16, ret, 0)
        }
    }
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
/// Runs one control graph without inspecting native layouts.
///
/// # Safety
/// Host must initialize every success scalar, accept the opaque context, and never
/// unwind across the C ABI. Native allocations and handles remain exclusively live.
#[no_mangle]
pub unsafe extern "C" fn star_zstd_run(
    mode: u32,
    host: Option<StarZstdHost>,
    context: *mut c_void,
) -> u32 {
    if mode > 3 || host.is_none() {
        return 2;
    }
    contained(mode, || {
        Driver {
            host: host.unwrap(),
            context,
        }
        .run(mode)
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[derive(Clone, Copy, Debug)]
    struct Event(u32, u64, u64, u64, u32);
    struct Script {
        events: Vec<Event>,
        cursor: usize,
        bad: bool,
    }
    unsafe extern "C" fn host(p: *mut c_void, op: u32, a: u64, b: u64, out: *mut u64) -> u32 {
        let s = &mut *(p as *mut Script);
        let Some(e) = s.events.get(s.cursor).copied() else {
            s.bad = true;
            return 2;
        };
        s.cursor += 1;
        if (op, a, b) != (e.0, e.1, e.2) {
            s.bad = true;
            return 2;
        }
        if e.4 == 0 {
            *out = e.3;
        }
        e.4
    }
    fn e(op: u32, a: u64, value: u64) -> Event {
        Event(op, a, 0, value, 0)
    }
    fn run(mode: u32, events: Vec<Event>, status: u32) {
        let mut s = Script {
            events,
            cursor: 0,
            bad: false,
        };
        let before = [0, 1, 2].map(|i| star_zstd_call_count(mode, i));
        assert_eq!(
            unsafe { star_zstd_run(mode, Some(host), &mut s as *mut _ as *mut c_void) },
            status
        );
        assert!(!s.bad, "bad event {}: {:?}", s.cursor, s.events);
        assert_eq!(s.cursor, s.events.len());
        assert_eq!(
            [0, 1, 2].map(|i| star_zstd_call_count(mode, i)),
            [
                before[0] + 1,
                before[1] + u64::from(status == 0),
                before[2] + u64::from(status == 1)
            ]
        );
    }
    fn stream(mode: u32, variant: u32, initial: u64) -> Vec<Event> {
        let mut v = vec![
            e(0, mode as u64, 0),
            e(2, 0, 4),
            e(3, 0, 0),
            e(1, 3, initial),
            e(1, 3, initial),
            e(4, initial.wrapping_add(4), 0),
        ];
        let mut size = initial.wrapping_add(4);
        let mut written = initial;
        let steps = if variant == 0 || variant == 2 || (variant == 1 && mode == 0) {
            2
        } else {
            1
        };
        for i in 0..steps {
            let cap = 4.min(size.wrapping_sub(written));
            let pos = if variant == 0 && i == 0 { cap } else { 1 };
            let ret = if variant == 1 && i == 0 { 7 } else { 0 };
            v.extend([
                e(1, 3, size),
                Event(5, written, cap, 0, 0),
                e(if mode == 0 { 6 } else { 7 }, 0, ret),
                e(13, ret, 0),
                e(1, 4, pos),
                e(1, 5, cap),
            ]);
            written = written.wrapping_add(pos);
            if pos == cap {
                v.push(e(1, 3, size));
                if written >= size {
                    v.extend([e(1, 3, size), e(4, size.wrapping_mul(2), 0)]);
                    size = size.wrapping_mul(2);
                }
                continue;
            }
            if mode == 1 || ret == 0 {
                v.extend([
                    e(1, 1, if variant == 2 && i == 0 { 1 } else { 3 }),
                    e(1, 2, 3),
                ]);
            }
        }
        v.push(e(4, written, 0));
        v
    }
    fn paths(mode: u32) -> Vec<Vec<Event>> {
        if mode < 2 {
            return (0..4).map(|v| stream(mode, v, 2)).collect();
        }
        let mut normal = vec![e(0, mode as u64, 0)];
        if mode == 2 {
            normal.extend([e(1, 0, 3), e(8, 0, 99)]);
        } else {
            normal.extend([e(9, 0, 99), e(1, 6, u64::MAX), e(1, 7, u64::MAX - 1)]);
        }
        normal.extend([
            e(10, 99, 0),
            e(if mode == 2 { 11 } else { 12 }, 0, 3),
            e(13, 3, 0),
            e(16, 3, 0),
        ]);
        let mut result = vec![normal];
        if mode == 2 {
            result.push(vec![e(0, 2, 0), e(1, 0, 0), e(17, 0, 0)]);
        } else {
            for size in [u64::MAX, u64::MAX - 1] {
                let mut v = vec![e(0, 3, 0), e(9, 0, size), e(1, 6, u64::MAX)];
                if size != u64::MAX {
                    v.push(e(1, 7, u64::MAX - 1));
                }
                v.push(Event(15, 0, 0, 0, 1));
                result.push(v);
            }
        }
        result
    }
    #[test]
    fn all_entries_traces_and_fault_each_leaf() {
        let mut seen = [false; 18];
        for mode in 0..4 {
            for path in paths(mode) {
                for e in &path {
                    seen[e.0 as usize] = true;
                }
                run(mode, path.clone(), path.last().unwrap().4);
                for i in 0..path.len() {
                    for status in [1, 2, 99] {
                        let mut v = path[..=i].to_vec();
                        v[i].4 = status;
                        run(mode, v, if status == 1 { 1 } else { 2 });
                    }
                }
            }
        }
        // Full native error is neither truncated nor normalized.
        for mode in 0..4 {
            let mut v = paths(mode).remove(0);
            let i = v.iter().position(|e| e.0 == 13).unwrap();
            v.truncate(i + 1);
            v[i - 1].3 = 0xffffffff00000001;
            v[i].1 = 0xffffffff00000001;
            v[i].3 = 1;
            v.push(Event(14, 0xffffffff00000001, 0, 0, 1));
            seen[14] = true;
            run(mode, v.clone(), 1);
            v.last_mut().unwrap().4 = 0;
            run(mode, v, 2);
        }
        assert!(seen.into_iter().all(|x| x));
    }
    #[test]
    fn empty_stream_and_full_width_success_protocol() {
        for mode in 0..2 {
            let mut v = stream(mode, 3, 2);
            for e in &mut v {
                if e.0 == 1 && (e.1 == 1 || e.1 == 2) {
                    e.3 = 0;
                }
            }
            run(mode, v, 0); // Empty input still executes one real STEP.
        }
        let high = 0x1234567800000003;
        for mode in 2..4 {
            let mut v = paths(mode).remove(0);
            let i = v.iter().position(|e| e.0 == 13).unwrap();
            v[i - 1].3 = high;
            v[i].1 = high;
            v[i + 1].1 = high;
            run(mode, v.clone(), 0);
            v.truncate(i + 1);
            v[i].3 = 2;
            run(mode, v, 2);
        }
        let mut v = paths(3).remove(1);
        v.last_mut().unwrap().4 = 0;
        run(3, v, 2);
        // Force unsigned doubling through the native-width wrap, then terminate.
        let initial = u64::MAX - 6;
        run(0, stream(0, 0, initial), 0);
    }
    #[test]
    fn unsigned_wrap_and_preflight() {
        run(0, stream(0, 3, u64::MAX - 2), 0);
        let before = star_zstd_call_count(0, 0);
        assert_eq!(
            unsafe { star_zstd_run(4, Some(host), std::ptr::null_mut()) },
            2
        );
        assert_eq!(unsafe { star_zstd_run(0, None, std::ptr::null_mut()) }, 2);
        assert_eq!(star_zstd_call_count(0, 0), before);
        assert_eq!(star_zstd_call_count(4, 0), 0);
        assert_eq!(star_zstd_call_count(0, 3), 0);
        run(2, vec![e(0, 2, 1)], 2);
    }
    unsafe extern "C" fn empty(_: *mut c_void, _: u32, _: u64, _: u64, out: *mut u64) -> u32 {
        *out = 0;
        0
    }
    unsafe extern "C" fn nested(_: *mut c_void, op: u32, _: u64, _: u64, out: *mut u64) -> u32 {
        if op == 0 {
            let status = star_zstd_run(2, Some(empty), std::ptr::null_mut());
            if status != 0 {
                return 2;
            }
        }
        *out = 0;
        0
    }
    #[test]
    fn reentry_and_null_context_counters() {
        let before = star_zstd_call_count(2, 0);
        assert_eq!(
            unsafe { star_zstd_run(2, Some(nested), std::ptr::null_mut()) },
            0
        );
        assert_eq!(star_zstd_call_count(2, 0), before + 2);
        std::thread::spawn(|| assert_eq!(star_zstd_call_count(2, 0), 0))
            .join()
            .unwrap();
    }
    #[test]
    fn contained_panic() {
        let before = [0, 1, 2].map(|e| star_zstd_call_count(3, e));
        assert_eq!(
            contained(3, || panic!("isolated Rust panic inside containment")),
            3
        );
        assert_eq!(
            [0, 1, 2].map(|e| star_zstd_call_count(3, e)),
            [before[0] + 1, before[1], before[2]]
        );
    }
}
