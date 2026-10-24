use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

pub type StarJsonPathHost = unsafe extern "C" fn(*mut c_void, u32, u32, *mut u32) -> i32;
thread_local! { static CALLS: Cell<[u64; 2]> = const { Cell::new([0; 2]) }; }

#[no_mangle]
pub extern "C" fn star_json_path_call_count(kind: u32) -> u64 {
    CALLS.with(|c| c.get().get(kind as usize).copied().unwrap_or(0))
}

struct Host {
    call: StarJsonPathHost,
    ctx: *mut c_void,
}
impl Host {
    // Each call is one original C++ expression. In particular, do not cache
    // current/atEnd: callbacks can throw, mutate state, or reenter the parser.
    unsafe fn op(&self, op: u32, arg: u32) -> Result<u32, ()> {
        let mut out = 0;
        if (self.call)(self.ctx, op, arg, &mut out) == 0 {
            Ok(out)
        } else {
            Err(())
        }
    }
    unsafe fn end(&self) -> Result<bool, ()> {
        Ok(self.op(1, 0)? != 0)
    }
    unsafe fn current(&self) -> Result<u32, ()> {
        self.op(2, 0)
    }
    unsafe fn advance(&self) -> Result<(), ()> {
        self.op(3, 0)?;
        Ok(())
    }
    unsafe fn pointer(&self) -> Result<(u32, u32), ()> {
        self.op(0, 0)?;
        if self.current()? != 47 {
            return Ok((0, 1));
        }
        self.advance()?;
        while !self.end()? && self.current()? != 47 {
            if self.current()? == 126 {
                self.advance()?;
                if self.end()? {
                    return Ok((0, 2));
                }
                if self.current()? == 48 {
                    self.op(5, 126)?;
                } else if self.current()? == 49 {
                    self.op(5, 47)?;
                } else {
                    return Ok((0, 3));
                }
                self.advance()?;
            } else {
                self.op(4, 0)?;
            }
        }
        if self.op(6, 0)? != 0 || (self.op(7, 0)? != 0 && self.end()?) {
            Ok((0, 0))
        } else {
            Ok((1, 0))
        }
    }
    unsafe fn query(&self) -> Result<(u32, u32), ()> {
        self.op(0, 0)?;
        if self.current()? == 46 {
            Ok((0, 4))
        } else if self.current()? == 91 {
            self.advance()?;
            while !self.end()? && self.current()? >= 48 && self.current()? <= 57 {
                self.op(4, 0)?;
            }
            if self.end()? || self.current()? != 93 {
                return Ok((0, 5));
            }
            self.advance()?;
            if !self.end()? && self.current()? == 46 {
                self.advance()?;
            }
            Ok((0, 0))
        } else {
            while !self.end()? && self.current()? != 46 && self.current()? != 91 {
                self.op(4, 0)?;
            }
            if !self.end()? && self.current()? == 46 {
                self.advance()?;
            }
            Ok((1, 0))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[derive(Default)]
    struct State {
        input: Vec<u32>,
        pos: usize,
        buffer: Vec<u32>,
        trace: Vec<(u32, u32)>,
        abort: Option<usize>,
        numeric: bool,
        reenter: bool,
    }
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, arg: u32, out: *mut u32) -> i32 {
        let p = ctx as *mut State;
        // No mutable borrow survives the nested callback.
        if (*p).reenter {
            (*p).reenter = false;
            let (mut hint, mut error) = (99, 99);
            assert_eq!(
                star_json_path_parse(
                    1,
                    Some(null_host),
                    std::ptr::null_mut(),
                    &mut hint,
                    &mut error
                ),
                0
            );
        }
        let s = &mut *p;
        s.trace.push((op, arg));
        if s.abort == Some(s.trace.len() - 1) {
            return -7;
        }
        match op {
            0 => s.buffer.clear(),
            1 => out.write(u32::from(s.pos == s.input.len())),
            2 => out.write(s.input.get(s.pos).copied().unwrap_or(0)),
            3 => s.pos += 1,
            4 => {
                let cp = s.input[s.pos];
                s.pos += 1;
                s.buffer.push(cp);
            }
            5 => s.buffer.push(arg),
            6 => out.write(u32::from(s.numeric)),
            7 => out.write(u32::from(s.buffer == [45])),
            _ => unreachable!(),
        }
        0
    }
    unsafe extern "C" fn null_host(_: *mut c_void, op: u32, _: u32, out: *mut u32) -> i32 {
        out.write(u32::from(op == 1));
        0
    }
    fn run(kind: u32, text: &str, numeric: bool) -> (State, u32, u32) {
        let mut s = State {
            input: text.chars().map(u32::from).collect(),
            buffer: vec![999],
            numeric,
            ..State::default()
        };
        let (mut hint, mut error) = (99, 99);
        assert_eq!(
            unsafe {
                star_json_path_parse(
                    kind,
                    Some(host),
                    (&mut s as *mut State).cast(),
                    &mut hint,
                    &mut error,
                )
            },
            0
        );
        (s, hint, error)
    }
    #[test]
    fn literal_segments_and_partial_errors() {
        for (kind, text, buffer, pos, hint, error) in [
            (0, "/a~0~1/b", "a~/", 6, 1, 0),
            (0, "/", "", 1, 1, 0),
            (0, "/-", "-", 2, 0, 0),
            (0, "/-/x", "-", 2, 1, 0),
            (0, "bad", "", 0, 99, 1),
            (0, "/a~", "a", 3, 99, 2),
            (0, "/a~x", "a", 3, 99, 3),
            (0, "/é😀\0", "é😀\0", 4, 1, 0),
            (1, ".x", "", 0, 99, 4),
            (1, "[12x]", "12", 3, 99, 5),
            (1, "[12", "12", 3, 99, 5),
            (1, "[].x", "", 3, 0, 0),
            (1, "[001].x", "001", 6, 0, 0),
            (1, "foo..bar", "foo", 4, 1, 0),
            (1, "foo[1]", "foo", 3, 1, 0),
            (1, "", "", 0, 1, 0),
            (0, "", "", 0, 99, 1),
        ] {
            let (s, h, e) = run(kind, text, false);
            assert_eq!(
                (s.buffer, s.pos, h, e),
                (buffer.chars().map(u32::from).collect(), pos, hint, error),
                "{text:?}"
            );
            assert_eq!(s.trace[0], (0, 0));
        }
    }
    #[test]
    fn exact_short_circuit_traces_and_host_classification() {
        assert_eq!(
            run(0, "/", false).0.trace,
            vec![(0, 0), (2, 0), (3, 0), (1, 0), (6, 0), (7, 0)]
        );
        let (s, hint, _) = run(0, "/anything", true);
        assert_eq!(hint, 0);
        assert_eq!(s.trace.last(), Some(&(6, 0)));
        assert_eq!(
            run(1, "[]", false).0.trace,
            vec![
                (0, 0),
                (2, 0),
                (2, 0),
                (3, 0),
                (1, 0),
                (2, 0),
                (2, 0),
                (1, 0),
                (2, 0),
                (3, 0),
                (1, 0)
            ]
        );
        assert_eq!(
            run(0, "/~x", false).0.trace,
            vec![
                (0, 0),
                (2, 0),
                (3, 0),
                (1, 0),
                (2, 0),
                (2, 0),
                (3, 0),
                (1, 0),
                (2, 0),
                (2, 0)
            ]
        );
    }
    #[test]
    fn every_callback_abort_leaves_metadata_and_counts_once() {
        for (kind, text) in [(0, "/abc~0~1"), (0, "/-"), (1, "[12]."), (1, "foo.bar")] {
            let full = run(kind, text, false).0;
            for stop in 0..full.trace.len() {
                let mut s = State {
                    input: text.chars().map(u32::from).collect(),
                    abort: Some(stop),
                    ..State::default()
                };
                let (mut h, mut e) = (99, 98);
                let before = star_json_path_call_count(kind);
                assert_eq!(
                    unsafe {
                        star_json_path_parse(
                            kind,
                            Some(host),
                            (&mut s as *mut State).cast(),
                            &mut h,
                            &mut e,
                        )
                    },
                    1
                );
                assert_eq!((h, e), (99, 98));
                assert_eq!(s.trace, full.trace[..=stop]);
                assert_eq!(star_json_path_call_count(kind), before + 1);
            }
        }
    }
    #[test]
    fn invalid_abi_has_no_callbacks_or_receipts() {
        let mut s = State::default();
        let (mut h, mut e) = (99, 98);
        let before = star_json_path_call_count(0);
        for (kind, callback, hp, ep) in [
            (
                2,
                Some(host as StarJsonPathHost),
                &mut h as *mut u32,
                &mut e as *mut u32,
            ),
            (0, None, &mut h, &mut e),
            (
                0,
                Some(host as StarJsonPathHost),
                std::ptr::null_mut(),
                &mut e,
            ),
            (
                0,
                Some(host as StarJsonPathHost),
                &mut h,
                std::ptr::null_mut(),
            ),
            (0, Some(host as StarJsonPathHost), &mut h, &mut h),
            (
                0,
                Some(host as StarJsonPathHost),
                1usize as *mut u32,
                &mut e,
            ),
            (
                0,
                Some(host as StarJsonPathHost),
                (usize::MAX - 3) as *mut u32,
                &mut e,
            ),
        ] {
            assert_eq!(
                unsafe {
                    star_json_path_parse(kind, callback, (&mut s as *mut State).cast(), hp, ep)
                },
                2
            );
            assert_eq!((h, e), (99, 98));
        }
        assert!(s.trace.is_empty());
        assert_eq!(star_json_path_call_count(0), before);
        assert_eq!(star_json_path_call_count(2), 0);
    }
    #[test]
    fn null_context_reentry_and_thread_local_receipts() {
        let before = [star_json_path_call_count(0), star_json_path_call_count(1)];
        let mut s = State {
            input: vec![47],
            reenter: true,
            ..State::default()
        };
        let (mut h, mut e) = (99, 98);
        assert_eq!(
            unsafe {
                star_json_path_parse(0, Some(host), (&mut s as *mut State).cast(), &mut h, &mut e)
            },
            0
        );
        assert_eq!(
            [star_json_path_call_count(0), star_json_path_call_count(1)],
            [before[0] + 1, before[1] + 1]
        );
        std::thread::spawn(|| {
            assert_eq!(star_json_path_call_count(0), 0);
            run(0, "/", false);
            assert_eq!(star_json_path_call_count(0), 1);
        })
        .join()
        .unwrap();
        assert_eq!(star_json_path_call_count(0), before[0] + 1);
    }
    #[test]
    fn rust_panic_is_contained_without_metadata_or_receipt_commit() {
        let (h, e) = (99, 98);
        let before = star_json_path_call_count(0);
        assert_eq!(contain(|| panic!("isolated containment probe")), 3);
        assert_eq!((h, e), (99, 98));
        assert_eq!(star_json_path_call_count(0), before);
    }
}

fn span(p: usize) -> Option<(usize, usize)> {
    if p == 0 || p % std::mem::align_of::<u32>() != 0 {
        return None;
    }
    Some((p, p.checked_add(std::mem::size_of::<u32>())?))
}
fn contain(f: impl FnOnce() -> i32) -> i32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(3)
}

/// Parses exactly one legacy segment through lazy host expressions.
///
/// # Safety
/// The two outputs must be live, writable, aligned, disjoint u32 objects.
/// The host must not unwind and must keep outputs live through every callback.
/// ctx is opaque and may be null. No host-state references span callbacks;
/// host pointers are borrowed only for this invocation, including reentry.
#[no_mangle]
pub unsafe extern "C" fn star_json_path_parse(
    kind: u32,
    host: Option<StarJsonPathHost>,
    ctx: *mut c_void,
    type_hint: *mut u32,
    grammar_error: *mut u32,
) -> i32 {
    contain(|| {
        let Some(host) = host else { return 2 };
        let (Some(hint), Some(error)) = (span(type_hint as usize), span(grammar_error as usize))
        else {
            return 2;
        };
        if kind > 1 || (hint.0 < error.1 && error.0 < hint.1) {
            return 2;
        }
        let host = Host { call: host, ctx };
        let result = if kind == 0 {
            host.pointer()
        } else {
            host.query()
        };
        if let Ok((hint, error)) = result {
            if error == 0 {
                type_hint.write(hint);
            }
            grammar_error.write(error);
        }
        CALLS.with(|c| {
            let mut counts = c.get();
            counts[kind as usize] = counts[kind as usize].wrapping_add(1);
            c.set(counts);
        });
        if result.is_ok() {
            0
        } else {
            1
        }
    })
}
