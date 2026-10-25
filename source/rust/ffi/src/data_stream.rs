//! Rust owns all 51 DataStream controllers; native objects and IO remain opaque.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
pub type StarDataStreamHost = unsafe extern "C" fn(*mut c_void, u32, u64, u64, *mut u64) -> u32;
thread_local! { static COUNTS: Cell<[[u64;3];51]> = const { Cell::new([[0;3];51]) }; }
fn count(mode: u32, event: usize) {
    COUNTS.with(|c| {
        let mut v = c.get();
        v[mode as usize][event] = v[mode as usize][event].wrapping_add(1);
        c.set(v);
    });
}
#[no_mangle]
pub extern "C" fn star_data_stream_call_count(mode: u32, event: u32) -> u64 {
    if mode >= 51 || event >= 3 {
        return 0;
    }
    COUNTS.with(|c| c.get()[mode as usize][event as usize])
}
const DS_CTOR: u32 = 0;
const DS_GET_ORDER: u32 = 1;
const DS_SET_ORDER: u32 = 2;
const DS_GET_NULL: u32 = 3;
const DS_SET_NULL: u32 = 4;
const DS_GET_VERSION: u32 = 5;
const DS_SET_VERSION: u32 = 6;
const DS_SET_RULES: u32 = 7;
const DS_READ_BYTES: u32 = 8;
const DS_WRITE_BYTES: u32 = 9;
const DS_WRITE_BOOL: u32 = 10;
const DS_WRITE_CHAR: u32 = 11;
const DS_WRITE_I8: u32 = 12;
const DS_WRITE_U8: u32 = 13;
const DS_WRITE_I16: u32 = 14;
const DS_WRITE_U16: u32 = 15;
const DS_WRITE_I32: u32 = 16;
const DS_WRITE_U32: u32 = 17;
const DS_WRITE_I64: u32 = 18;
const DS_WRITE_U64: u32 = 19;
const DS_WRITE_F32: u32 = 20;
const DS_WRITE_F64: u32 = 21;
const DS_READ_BOOL: u32 = 22;
const DS_READ_CHAR: u32 = 23;
const DS_READ_I8: u32 = 24;
const DS_READ_U8: u32 = 25;
const DS_READ_I16: u32 = 26;
const DS_READ_U16: u32 = 27;
const DS_READ_I32: u32 = 28;
const DS_READ_U32: u32 = 29;
const DS_READ_I64: u32 = 30;
const DS_READ_U64: u32 = 31;
const DS_READ_F32: u32 = 32;
const DS_READ_F64: u32 = 33;
const DS_WRITE_VLQU: u32 = 34;
const DS_WRITE_VLQI: u32 = 35;
const DS_WRITE_VLQS: u32 = 36;
const DS_READ_VLQU: u32 = 37;
const DS_READ_VLQI: u32 = 38;
const DS_READ_VLQS: u32 = 39;
const DS_VALUE_VLQU: u32 = 40;
const DS_VALUE_VLQI: u32 = 41;
const DS_VALUE_VLQS: u32 = 42;
const DS_WRITE_CSTRING: u32 = 43;
const DS_WRITE_STDSTRING: u32 = 44;
const DS_WRITE_ARRAY: u32 = 45;
const DS_WRITE_STRING: u32 = 46;
const DS_READ_STDSTRING: u32 = 47;
const DS_READ_ARRAY: u32 = 48;
const DS_READ_STRING: u32 = 49;
const DS_WRITE_STRING_DATA: u32 = 50;
const DS_CONFIG_GET: u32 = 0;
const DS_CONFIG_SET: u32 = 1;
const DS_ARGUMENT: u32 = 2;
const DS_RESULT: u32 = 3;
const DS_SCALAR_IO: u32 = 4;
const DS_CONVERT: u32 = 5;
const DS_BOOL_ASSIGN: u32 = 6;
const DS_SIZE: u32 = 7;
const DS_CAPTURE: u32 = 8;
const DS_VIEW_IO: u32 = 9;
const DS_RESIZE: u32 = 10;
const DS_CLEAR: u32 = 11;
const DS_APPEND: u32 = 12;
const DS_CHAR_READ: u32 = 13;
const DS_CHILD: u32 = 14;
const DS_VLQ: u32 = 15;
const DS_VLQ_VALUE: u32 = 16;
const DS_ASSIGN_SIZE: u32 = 17;
const DS_ASSIGN_STRING: u32 = 18;
const DS_RAISE_VLQ: u32 = 19;
const DS_FINISH: u32 = 20;
struct Driver {
    ctx: *mut c_void,
    host: StarDataStreamHost,
}
impl Driver {
    fn call(&self, op: u32, a: u64, b: u64) -> Result<u64, u32> {
        let mut out = 0;
        // No borrow of native state survives a callback, including nested controllers.
        match unsafe { (self.host)(self.ctx, op, a, b, &mut out) } {
            0 => Ok(out),
            1 => Err(1),
            _ => Err(2),
        }
    }
    fn c(&self, op: u32, a: u64) -> Result<u64, u32> {
        self.call(op, a, 0)
    }
    fn run(&self, m: u32) -> Result<(), u32> {
        match m {
            DS_CTOR => {
                self.call(DS_CONFIG_SET, 0, 0)?;
                self.call(DS_CONFIG_SET, 1, 0)?;
                let v = self.c(DS_CONFIG_GET, 4)?;
                self.call(DS_CONFIG_SET, 2, v)?;
            }
            DS_GET_ORDER | DS_GET_NULL | DS_GET_VERSION => {
                let v = self.c(DS_CONFIG_GET, ((m - 1) / 2) as u64)?;
                self.call(DS_RESULT, 0, v)?;
            }
            DS_SET_ORDER | DS_SET_NULL | DS_SET_VERSION => {
                let v = self.c(DS_ARGUMENT, 0)?;
                self.call(DS_CONFIG_SET, ((m - 2) / 2) as u64, v)?;
            }
            DS_SET_RULES => {
                let v = self.c(DS_CONFIG_GET, 3)?;
                self.call(DS_CONFIG_SET, 2, v)?;
            }
            DS_READ_BYTES => {
                let n = self.c(DS_ARGUMENT, 0)?;
                self.call(DS_RESIZE, 0, n)?;
                self.c(DS_CAPTURE, 0)?;
                self.c(DS_VIEW_IO, 0)?;
            }
            DS_WRITE_BYTES => {
                self.c(DS_CAPTURE, 0)?;
                self.c(DS_VIEW_IO, 1)?;
            }
            DS_WRITE_BOOL => {
                let v = self.c(DS_ARGUMENT, 0)?;
                self.call(DS_CHILD, 4, v)?;
            }
            DS_WRITE_CHAR | DS_WRITE_I8 | DS_WRITE_U8 | DS_WRITE_I16 | DS_WRITE_U16
            | DS_WRITE_I32 | DS_WRITE_U32 | DS_WRITE_I64 | DS_WRITE_U64 | DS_WRITE_F32
            | DS_WRITE_F64 => {
                if m >= DS_WRITE_I16 {
                    let o = self.c(DS_CONFIG_GET, 0)?;
                    self.c(DS_CONVERT, o)?;
                }
                self.c(DS_SCALAR_IO, 1)?;
            }
            DS_READ_BOOL | DS_READ_CHAR | DS_READ_I8 | DS_READ_U8 | DS_READ_I16 | DS_READ_U16
            | DS_READ_I32 | DS_READ_U32 | DS_READ_I64 | DS_READ_U64 | DS_READ_F32 | DS_READ_F64 => {
                self.c(DS_SCALAR_IO, 0)?;
                if m == DS_READ_BOOL {
                    self.c(DS_BOOL_ASSIGN, 0)?;
                } else if m >= DS_READ_I16 {
                    let o = self.c(DS_CONFIG_GET, 0)?;
                    self.c(DS_CONVERT, o)?;
                }
            }
            DS_WRITE_VLQU | DS_WRITE_VLQI => {
                let v = self.c(DS_ARGUMENT, 0)?;
                let n = self.call(DS_VLQ, (m - DS_WRITE_VLQU) as u64, v)?;
                self.call(DS_RESULT, 0, n)?;
            }
            DS_WRITE_VLQS => {
                let v = self.c(DS_ARGUMENT, 0)?;
                let n = self.call(DS_CHILD, 0, v.wrapping_add(1))?;
                self.call(DS_RESULT, 0, n)?;
            }
            DS_READ_VLQU | DS_READ_VLQI => {
                let n = self.c(DS_VLQ, (2 + m - DS_READ_VLQU) as u64)?;
                if n == u64::MAX {
                    self.c(DS_RAISE_VLQ, 0)?;
                    return Err(2);
                }
                self.call(DS_RESULT, 0, n)?;
            }
            DS_READ_VLQS => {
                let n = self.c(DS_CHILD, 5)?;
                let v = self.c(DS_VLQ_VALUE, 0)?;
                self.call(DS_ASSIGN_SIZE, 0, v.wrapping_sub(1))?;
                self.call(DS_RESULT, 0, n)?;
            }
            DS_VALUE_VLQU | DS_VALUE_VLQI | DS_VALUE_VLQS => {
                self.c(DS_CHILD, (5 + m - DS_VALUE_VLQU) as u64)?;
                let v = self.c(DS_VLQ_VALUE, (m - DS_VALUE_VLQU) as u64)?;
                self.call(DS_RESULT, 0, v)?;
            }
            DS_WRITE_CSTRING | DS_WRITE_STDSTRING | DS_WRITE_STRING => {
                self.c(DS_CAPTURE, 0)?;
                self.c(DS_CHILD, 2)?;
            }
            DS_WRITE_ARRAY => {
                let n = self.c(DS_SIZE, 0)?;
                self.call(DS_CHILD, 0, n)?;
                self.c(DS_CAPTURE, 0)?;
                self.c(DS_VIEW_IO, 1)?;
            }
            DS_READ_STDSTRING => {
                let term = self.c(DS_CONFIG_GET, 1)?;
                if term != 0 {
                    self.c(DS_CLEAR, 0)?;
                    loop {
                        let c = self.c(DS_CHAR_READ, 0)?;
                        if c == 0 {
                            break;
                        }
                        self.call(DS_APPEND, 0, c)?;
                    }
                } else {
                    self.read_container()?;
                }
            }
            DS_READ_ARRAY => self.read_container()?,
            DS_READ_STRING => {
                self.c(DS_CHILD, 3)?;
                self.c(DS_ASSIGN_STRING, 0)?;
            }
            DS_WRITE_STRING_DATA => {
                let term = self.c(DS_CONFIG_GET, 1)?;
                let n = self.c(DS_SIZE, 0)?;
                if term == 0 {
                    self.call(DS_CHILD, 0, n)?;
                }
                self.c(DS_VIEW_IO, 1)?;
                if term != 0 {
                    self.c(DS_CHILD, 4)?;
                }
            }
            _ => return Err(2),
        }
        self.c(DS_FINISH, 0)?;
        Ok(())
    }
    fn read_container(&self) -> Result<(), u32> {
        let n = self.c(DS_CHILD, 1)?;
        self.call(DS_RESIZE, 0, n)?;
        self.c(DS_CAPTURE, 0)?;
        self.c(DS_VIEW_IO, 0)?;
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
/// # Safety
/// A supplied host must support the scalar protocol, keep output storage valid,
/// and contain every native exception. The context is opaque and may be null.
#[no_mangle]
pub unsafe extern "C" fn star_data_stream_run(
    mode: u32,
    ctx: *mut c_void,
    host: Option<StarDataStreamHost>,
) -> u32 {
    if mode >= 51 || host.is_none() {
        return 2;
    }
    let host = host.unwrap();
    count(mode, 0);
    let s = contained(|| Driver { ctx, host }.run(mode));
    if s == 0 {
        count(mode, 1)
    } else if s == 1 {
        count(mode, 2)
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ptr::null_mut;
    #[derive(Default)]
    struct State {
        calls: Vec<(u32, u64, u64)>,
        fail: Option<(u32, u32)>,
        term: u64,
        chars: usize,
        reenter: bool,
        nested: u32,
    }
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, a: u64, b: u64, out: *mut u64) -> u32 {
        let s = &mut *(ctx as *mut State);
        s.calls.push((op, a, b));
        *out = 0;
        if let Some((at, status)) = s.fail {
            if at == op {
                return status;
            }
        }
        match op {
            DS_CONFIG_GET => *out = if a == 1 { s.term } else { 2 },
            DS_ARGUMENT => *out = 7,
            DS_SIZE => *out = 3,
            DS_CAPTURE => *out = 8,
            DS_CHAR_READ => {
                *out = if s.chars == 0 { 65 } else { 0 };
                s.chars += 1;
                s.term = 0;
            }
            DS_SCALAR_IO => {
                if s.reenter {
                    s.reenter = false;
                    let mut child = State::default();
                    s.nested = star_data_stream_run(
                        DS_WRITE_U8,
                        &mut child as *mut _ as *mut c_void,
                        Some(host),
                    );
                }
            }
            DS_CHILD => *out = 3,
            DS_VLQ => *out = 2,
            _ => {}
        };
        0
    }
    fn run(mode: u32, s: &mut State) -> u32 {
        unsafe { star_data_stream_run(mode, s as *mut _ as *mut c_void, Some(host)) }
    }
    fn ops(s: &State) -> Vec<u32> {
        s.calls.iter().map(|x| x.0).collect()
    }
    unsafe extern "C" fn null_host(_: *mut c_void, _: u32, _: u64, _: u64, out: *mut u64) -> u32 {
        *out = 0;
        0
    }
    #[test]
    fn preflight_all_modes_and_receipts() {
        for m in 0..51 {
            let before = star_data_stream_call_count(m, 0);
            assert_eq!(unsafe { star_data_stream_run(m, null_mut(), None) }, 2);
            assert_eq!(star_data_stream_call_count(m, 0), before);
            let mut s = State::default();
            assert_eq!(run(m, &mut s), 0, "mode {m}");
            assert_eq!(star_data_stream_call_count(m, 0), before + 1);
            assert_eq!(s.calls.last().map(|x| x.0), Some(DS_FINISH));
        }
        assert_eq!(
            unsafe { star_data_stream_run(51, null_mut(), Some(null_host)) },
            2
        );
        assert_eq!(star_data_stream_call_count(51, 0), 0);
        assert_eq!(star_data_stream_call_count(0, 3), 0);
        assert_eq!(
            unsafe { star_data_stream_run(DS_WRITE_U8, null_mut(), Some(null_host)) },
            0
        );
    }
    #[test]
    fn directional_conversion_even_no_conversion() {
        let mut s = State::default();
        assert_eq!(run(DS_READ_U32, &mut s), 0);
        assert_eq!(
            s.calls,
            vec![
                (DS_SCALAR_IO, 0, 0),
                (DS_CONFIG_GET, 0, 0),
                (DS_CONVERT, 2, 0),
                (DS_FINISH, 0, 0)
            ]
        );
        s.calls.clear();
        assert_eq!(run(DS_WRITE_U32, &mut s), 0);
        assert_eq!(
            s.calls,
            vec![
                (DS_CONFIG_GET, 0, 0),
                (DS_CONVERT, 2, 0),
                (DS_SCALAR_IO, 1, 0),
                (DS_FINISH, 0, 0)
            ]
        );
    }
    #[test]
    fn pending_stops_before_conversion_bool_assignment_and_publish() {
        for mode in [DS_READ_U32, DS_READ_BOOL] {
            let before = star_data_stream_call_count(mode, 2);
            let mut s = State {
                fail: Some((DS_SCALAR_IO, 1)),
                ..Default::default()
            };
            assert_eq!(run(mode, &mut s), 1);
            assert_eq!(ops(&s), vec![DS_SCALAR_IO]);
            assert_eq!(star_data_stream_call_count(mode, 2), before + 1);
        }
        let mut s = State {
            fail: Some((DS_CHILD, 1)),
            ..Default::default()
        };
        assert_eq!(run(DS_READ_STRING, &mut s), 1);
        assert_eq!(ops(&s), vec![DS_CHILD]);
    }
    #[test]
    fn invalid_status_and_finish_contradictions() {
        for status in [2, 3, u32::MAX] {
            let mut s = State {
                fail: Some((DS_SCALAR_IO, status)),
                ..Default::default()
            };
            assert_eq!(run(DS_READ_U8, &mut s), 2);
            assert_eq!(s.calls.len(), 1);
        }
        let mut s = State {
            fail: Some((DS_FINISH, 1)),
            ..Default::default()
        };
        assert_eq!(run(DS_WRITE_U8, &mut s), 1);
    }
    #[test]
    fn terminated_loop_snapshots_mode() {
        let mut s = State {
            term: 1,
            ..Default::default()
        };
        assert_eq!(run(DS_READ_STDSTRING, &mut s), 0);
        assert_eq!(
            s.calls,
            vec![
                (DS_CONFIG_GET, 1, 0),
                (DS_CLEAR, 0, 0),
                (DS_CHAR_READ, 0, 0),
                (DS_APPEND, 0, 65),
                (DS_CHAR_READ, 0, 0),
                (DS_FINISH, 0, 0)
            ]
        );
    }
    #[test]
    fn fresh_array_capture_and_captured_string_order() {
        let mut s = State::default();
        assert_eq!(run(DS_WRITE_ARRAY, &mut s), 0);
        assert_eq!(
            s.calls,
            vec![
                (DS_SIZE, 0, 0),
                (DS_CHILD, 0, 3),
                (DS_CAPTURE, 0, 0),
                (DS_VIEW_IO, 1, 0),
                (DS_FINISH, 0, 0)
            ]
        );
        s.calls.clear();
        assert_eq!(run(DS_WRITE_CSTRING, &mut s), 0);
        assert_eq!(ops(&s), vec![DS_CAPTURE, DS_CHILD, DS_FINISH]);
        s.calls.clear();
        assert_eq!(run(DS_READ_ARRAY, &mut s), 0);
        assert_eq!(
            s.calls,
            vec![
                (DS_CHILD, 1, 0),
                (DS_RESIZE, 0, 3),
                (DS_CAPTURE, 0, 0),
                (DS_VIEW_IO, 0, 0),
                (DS_FINISH, 0, 0)
            ]
        );
    }
    #[test]
    fn bool_dispatches_child_and_zero_io_stays_observable() {
        let mut s = State::default();
        assert_eq!(run(DS_WRITE_BOOL, &mut s), 0);
        assert_eq!(
            s.calls,
            vec![(DS_ARGUMENT, 0, 0), (DS_CHILD, 4, 7), (DS_FINISH, 0, 0)]
        );
        s.calls.clear();
        assert_eq!(run(DS_WRITE_BYTES, &mut s), 0);
        assert_eq!(ops(&s), vec![DS_CAPTURE, DS_VIEW_IO, DS_FINISH]);
    }
    #[test]
    fn reentry_and_wrapping_receipts() {
        let mut s = State {
            reenter: true,
            nested: 99,
            ..Default::default()
        };
        assert_eq!(run(DS_READ_U8, &mut s), 0);
        assert_eq!(s.nested, 0);
        COUNTS.with(|c| {
            let mut v = c.get();
            v[DS_WRITE_CHAR as usize] = [u64::MAX, u64::MAX, 0];
            c.set(v)
        });
        assert_eq!(run(DS_WRITE_CHAR, &mut s), 0);
        assert_eq!(star_data_stream_call_count(DS_WRITE_CHAR, 0), 0);
        assert_eq!(star_data_stream_call_count(DS_WRITE_CHAR, 1), 0);
    }
    #[test]
    fn rust_panic_contained_without_foreign_unwind() {
        assert_eq!(contained(|| panic!("contained rust closure")), 3);
    }
    unsafe extern "C" fn sentinel_host(
        ctx: *mut c_void,
        op: u32,
        a: u64,
        b: u64,
        out: *mut u64,
    ) -> u32 {
        let status = host(ctx, op, a, b, out);
        if status == 0 && matches!(op, DS_ARGUMENT | DS_VLQ | DS_VLQ_VALUE) {
            *out = u64::MAX;
        }
        status
    }
    #[test]
    fn vlq_sentinels_and_raising_leaf_contradiction() {
        let mut s = State::default();
        let invoke = |m, s: &mut State| unsafe {
            star_data_stream_run(m, s as *mut _ as *mut c_void, Some(sentinel_host))
        };
        assert_eq!(invoke(DS_WRITE_VLQS, &mut s), 0);
        assert!(s.calls.contains(&(DS_CHILD, 0, 0)));
        s.calls.clear();
        assert_eq!(invoke(DS_READ_VLQU, &mut s), 2);
        assert_eq!(ops(&s), vec![DS_VLQ, DS_RAISE_VLQ]);
        s.calls.clear();
        s.fail = Some((DS_RAISE_VLQ, 1));
        assert_eq!(invoke(DS_READ_VLQI, &mut s), 1);
        assert_eq!(ops(&s), vec![DS_VLQ, DS_RAISE_VLQ]);
    }
    #[test]
    fn every_mode_pending_balances_receipt_without_retry() {
        for mode in 0..51 {
            let mut success = State::default();
            assert_eq!(run(mode, &mut success), 0);
            let first = success.calls[0].0;
            let before = star_data_stream_call_count(mode, 2);
            let mut s = State {
                fail: Some((first, 1)),
                ..Default::default()
            };
            assert_eq!(run(mode, &mut s), 1);
            assert_eq!(s.calls.len(), 1);
            assert_eq!(star_data_stream_call_count(mode, 2), before + 1);
        }
    }
}
