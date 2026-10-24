//! Rust owns JSON-patch control flow; opaque native leaves retain C++ values and exceptions.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

pub type StarJsonPatchHost = unsafe extern "C" fn(*mut c_void, u32, u32, u32, u64, *mut u64) -> u32;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum HostError {
    Traversal,
    Json,
    Map,
    TestFail,
    Other,
    Protocol,
}
type Result<T> = std::result::Result<T, HostError>;
thread_local! { static COUNTS: Cell<[[u64; 3]; 10]> = const { Cell::new([[0; 3]; 10]) }; }
#[cfg(test)]
thread_local! { static PANIC_AFTER_ATTEMPT: Cell<bool> = const { Cell::new(false) }; }
fn count(entry: u32, event: usize) {
    COUNTS.with(|c| {
        let mut values = c.get();
        values[entry as usize][event] = values[entry as usize][event].wrapping_add(1);
        c.set(values);
    });
}
/// Thread-local semantic invocation receipts, including internal calls.
/// Panic/protocol termination need not record an exit after an attempt.
#[no_mangle]
pub extern "C" fn star_json_patch_call_count(entry: u32, event: u32) -> u64 {
    if entry >= 10 || event >= 3 {
        return 0;
    }
    COUNTS.with(|c| c.get()[entry as usize][event as usize])
}
struct Controller {
    host: StarJsonPatchHost,
    context: *mut c_void,
}
impl Controller {
    fn call(&self, opcode: u32, a: u32, b: u32, n: u64) -> Result<u64> {
        let mut scalar = 0;
        // Only the callback's local scalar is exposed; no native value layout is borrowed.
        let status = unsafe { (self.host)(self.context, opcode, a, b, n, &mut scalar) };
        match status {
            0 => Ok(scalar),
            1 => Err(HostError::Traversal),
            2 => Err(HostError::Json),
            3 => Err(HostError::Map),
            4 => Err(HostError::TestFail),
            5 => Err(HostError::Other),
            _ => Err(HostError::Protocol),
        }
    }
    fn op(&self, opcode: u32) -> Result<u64> {
        self.call(opcode, 0, 0, 0)
    }
    fn fail(&self, failure: u32, pointer: u32) -> Result<u64> {
        // MAKE_FAILURE and WRAP_JSON must construct a native pending exception.
        match self.call(35, failure, pointer, 0) {
            Ok(_) => Err(HostError::Protocol),
            err => err,
        }
    }
    fn wrap(&self, kind: u32) -> Result<u64> {
        match self.call(36, kind, 0, 0) {
            Ok(_) => Err(HostError::Protocol),
            err => err,
        }
    }
    fn cleanup<T>(&self, opcode: u32, result: Result<T>) -> Result<T> {
        // Native cleanup is noexcept and preserves the pending exception and result.
        // A broken host cannot replace a semantic failure with a new native error.
        match self.op(opcode) {
            Ok(_) => result,
            Err(_) => Err(HostError::Protocol),
        }
    }
    fn semantic(&self, entry: u32, body: impl FnOnce() -> Result<u64>) -> Result<u64> {
        count(entry, 0);
        #[cfg(test)]
        PANIC_AFTER_ATTEMPT.with(|flag| {
            if flag.replace(false) {
                panic!("injected controller panic");
            }
        });
        let result = body();
        match result {
            Ok(_) => count(entry, 1),
            Err(HostError::Protocol) => (),
            Err(_) => count(entry, 2),
        }
        result
    }
    fn find(&self, pointer: u32) -> Result<u64> {
        self.semantic(2, || {
            let result = (|| {
                if self.op(16)? == 0 {
                    return self.fail(0, pointer);
                }
                self.op(17)?;
                let size = self.op(18)?;
                for i in 0..size {
                    if self.call(19, 0, 0, i)? != 0 {
                        return Ok(i + 1);
                    }
                }
                Ok(0)
            })();
            self.cleanup(39, result)
        })
    }
    fn test_inner(&self, inverse: bool) -> Result<u64> {
        if self.op(10)? != 0 {
            self.op(11)?;
            self.op(12)?;
            let found = self.find(0)? != 0;
            if found && inverse {
                return self.fail(1, 0);
            }
            if !found && !inverse {
                return self.fail(2, 0);
            }
            return self.op(20);
        }
        let present = self.op(13)? != 0;
        self.op(14)?;
        if !present {
            if inverse {
                return self.fail(3, 0);
            }
            return self.op(20);
        }
        if (self.op(15)? != 0) ^ inverse {
            self.op(20)
        } else {
            self.fail(4, 0)
        }
    }
    fn handler_body(&self, entry: u32) -> Result<u64> {
        self.op(4)?;
        if entry == 5 || entry == 6 {
            self.op(5)?;
        }
        self.op(if entry == 6 { 7 } else { 6 })?;
        if entry == 3 {
            // Setup is outside the legacy Traversal catch. Catch-body errors escape it.
            let inverse = self.op(9)? != 0;
            return match self.test_inner(inverse) {
                Err(HostError::Traversal) => {
                    if inverse {
                        self.op(37)?;
                        self.op(20)
                    } else {
                        self.fail(5, 0)
                    }
                }
                result => result,
            };
        }
        if entry == 7 || entry == 8 {
            self.op(8)?;
        }
        if self.op(10)? != 0 {
            let pointer = u32::from(entry == 7 || entry == 8);
            self.call(11, pointer, 0, 0)?;
            self.op(12)?;
            let found = self.find(pointer)?;
            if found == 0 {
                return self.op(20);
            }
            let index = found - 1;
            let leaf = match entry {
                4 => 24,
                5 => 25,
                6 => 26,
                7 => {
                    self.call(27, 0, 0, index)?;
                    28
                }
                8 => 31,
                9 => 32,
                _ => return Err(HostError::Protocol),
            };
            return self.call(leaf, 0, 0, index);
        }
        match entry {
            4 => self.op(21),
            5 => self.op(22),
            6 => self.op(23),
            7 => {
                self.op(29)?;
                self.op(30)
            }
            8 => {
                self.op(29)?;
                self.op(22)
            }
            9 => self.op(33),
            _ => Err(HostError::Protocol),
        }
    }
    fn handler(&self, entry: u32) -> Result<u64> {
        self.semantic(entry, || self.cleanup(40, self.handler_body(entry)))
    }
    fn apply(&self) -> Result<u64> {
        self.semantic(1, || {
            let result = (|| {
                self.op(3)?;
                let entry = self.op(2)?;
                if !(3..=9).contains(&entry) {
                    return Err(HostError::Protocol);
                }
                self.handler(entry as u32)
            })();
            // Operation's lifetime ends before either catch body. These match arms
            // deliberately do not feed newly thrown errors through sibling catches.
            match self.cleanup(41, result) {
                Err(HostError::Json | HostError::Traversal) => self.wrap(0),
                Err(HostError::Map) => self.fail(6, 0),
                result => result,
            }
        })
    }
    fn patch(&self) -> Result<u64> {
        self.semantic(0, || {
            let result = (|| {
                let size = self.op(0)?;
                for i in 0..size {
                    self.call(1, 0, 0, i)?;
                    self.apply()?;
                    self.op(34)?;
                }
                self.op(20)
            })();
            match result {
                Err(HostError::Json | HostError::Traversal) => self.wrap(1),
                result => result,
            }
        })
    }
}
/// Executes one semantic entry without ever retrying a native implementation.
///
/// # Safety
/// `scalar_out` must be a live exclusively writable u64 allocation, even for
/// non-FIND entries. The host must not unwind, retain output pointers, or invalidate
/// its opaque context during the call. A custom host may accept a null context.
#[no_mangle]
pub unsafe extern "C" fn star_json_patch_run(
    entry: u32,
    host: Option<StarJsonPatchHost>,
    context: *mut c_void,
    scalar_out: *mut u64,
) -> u32 {
    let address = scalar_out as usize;
    if entry > 9
        || host.is_none()
        || address == 0
        || address % 8 != 0
        || address.checked_add(8).is_none()
    {
        return 2;
    }
    match catch_unwind(AssertUnwindSafe(|| {
        let controller = Controller {
            host: host.unwrap(),
            context,
        };
        match entry {
            0 => controller.patch(),
            1 => controller.apply(),
            2 => controller.find(2),
            _ => controller.handler(entry),
        }
    })) {
        Ok(Ok(value)) => {
            if entry == 2 {
                scalar_out.write(value);
            }
            0
        }
        Ok(Err(HostError::Protocol)) => 2,
        Ok(Err(_)) => 1,
        Err(_) => 3,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[derive(Default)]
    struct Mock {
        trace: Vec<(u32, u32, u32, u64)>,
        values: Vec<(u32, u64)>,
        faults: Vec<(u32, u32)>,
    }
    unsafe extern "C" fn host(
        raw: *mut c_void,
        op: u32,
        a: u32,
        b: u32,
        n: u64,
        out: *mut u64,
    ) -> u32 {
        let m = &mut *raw.cast::<Mock>();
        m.trace.push((op, a, b, n));
        if let Some(i) = m.faults.iter().position(|&(k, _)| k == op) {
            return m.faults.remove(i).1;
        }
        if op == 35 || op == 36 {
            return if op == 35 && (1..=5).contains(&a) {
                4
            } else {
                2
            };
        }
        *out = m
            .values
            .iter()
            .find(|&&(k, _)| k == op)
            .map_or(0, |&(_, v)| v);
        0
    }
    fn run(e: u32, m: &mut Mock) -> (u32, u64) {
        let mut scalar = 0xface;
        let s = unsafe { star_json_patch_run(e, Some(host), (m as *mut Mock).cast(), &mut scalar) };
        (s, scalar)
    }
    fn ops(m: &Mock) -> Vec<u32> {
        m.trace.iter().map(|v| v.0).collect()
    }
    #[test]
    fn preflight_has_no_effects() {
        let before = COUNTS.with(Cell::get);
        let mut m = Mock::default();
        let mut scalar = 42;
        let p = (&mut m as *mut Mock).cast();
        unsafe {
            assert_eq!(star_json_patch_run(10, Some(host), p, &mut scalar), 2);
            assert_eq!(star_json_patch_run(0, None, p, &mut scalar), 2);
            for out in [
                std::ptr::null_mut(),
                1usize as *mut u64,
                usize::MAX.wrapping_sub(7) as *mut u64,
            ] {
                assert_eq!(star_json_patch_run(0, Some(host), p, out), 2);
            }
        }
        assert!(m.trace.is_empty());
        assert_eq!(scalar, 42);
        assert_eq!(COUNTS.with(Cell::get), before);
        assert_eq!(star_json_patch_call_count(10, 0), 0);
        assert_eq!(star_json_patch_call_count(0, 3), 0);
    }
    #[test]
    fn all_entry_success_traces_and_scalar() {
        let expected: [&[u32]; 10] = [
            &[0, 20],
            &[3, 2, 4, 6, 9, 10, 13, 14, 20, 40, 41],
            &[16, 17, 18, 39],
            &[4, 6, 9, 10, 13, 14, 20, 40],
            &[4, 6, 10, 21, 40],
            &[4, 5, 6, 10, 22, 40],
            &[4, 5, 7, 10, 23, 40],
            &[4, 6, 8, 10, 29, 30, 40],
            &[4, 6, 8, 10, 29, 22, 40],
            &[4, 6, 10, 33, 40],
        ];
        for e in 0..10 {
            let mut m = Mock {
                values: vec![(2, 3), (16, 1)],
                ..Default::default()
            };
            let before = star_json_patch_call_count(e, 0);
            assert_eq!(run(e, &mut m), (0, if e == 2 { 0 } else { 0xface }));
            assert_eq!(ops(&m), expected[e as usize]);
            assert_eq!(star_json_patch_call_count(e, 0), before + 1);
        }
    }
    #[test]
    fn find_search_index_and_short_circuit() {
        for e in 3..10 {
            let mut m = Mock {
                values: vec![(10, 1), (16, 1), (18, 4), (19, 1)],
                ..Default::default()
            };
            assert_eq!(run(e, &mut m).0, 0);
            assert_eq!(m.trace.iter().filter(|v| v.0 == 19).count(), 1);
            for &(_, _, _, n) in m.trace.iter().filter(|v| matches!(v.0, 24..=28 | 31 | 32)) {
                assert_eq!(n, 0);
            }
            assert!(ops(&m).windows(2).any(|v| v == [19, 39]));
        }
        let mut m = Mock {
            values: vec![(16, 1), (18, 4), (19, 1)],
            ..Default::default()
        };
        assert_eq!(run(2, &mut m), (0, 1));
    }
    #[test]
    fn lexical_catches_and_recovery() {
        let mut m = Mock {
            values: vec![(2, 3), (9, 1)],
            faults: vec![(14, 1)],
            ..Default::default()
        };
        assert_eq!(run(1, &mut m).0, 0);
        assert_eq!(ops(&m), vec![3, 2, 4, 6, 9, 10, 13, 14, 37, 20, 40, 41]);
        // Setup traversal is not inside TEST's catch, despite inverse=true.
        let mut m = Mock {
            values: vec![(9, 1)],
            faults: vec![(6, 1)],
            ..Default::default()
        };
        assert_eq!(run(3, &mut m).0, 1);
        assert_eq!(ops(&m), vec![4, 6, 40]);
        // A new JSON error inside the MAP catch must not hit APPLY's JSON catch.
        let mut m = Mock {
            faults: vec![(2, 3), (35, 2)],
            ..Default::default()
        };
        assert_eq!(run(1, &mut m).0, 1);
        assert_eq!(ops(&m), vec![3, 2, 41, 35]);
        // The enclosing PATCH catch can wrap that new JSON error.
        let mut m = Mock {
            values: vec![(0, 1)],
            faults: vec![(2, 3), (35, 2)],
            ..Default::default()
        };
        assert_eq!(run(0, &mut m).0, 1);
        assert_eq!(ops(&m), vec![0, 1, 3, 2, 41, 35, 36]);
        // An error in TEST's recovery body escapes, rather than retrying recovery.
        let mut m = Mock {
            values: vec![(9, 1)],
            faults: vec![(14, 1), (37, 1)],
            ..Default::default()
        };
        assert_eq!(run(3, &mut m).0, 1);
        assert_eq!(ops(&m), vec![4, 6, 9, 10, 13, 14, 37, 40]);
    }
    #[test]
    fn nested_find_exception_is_counted_even_when_recovered() {
        let before = star_json_patch_call_count(2, 2);
        let success = star_json_patch_call_count(3, 1);
        let mut m = Mock {
            values: vec![(9, 1), (10, 1)],
            faults: vec![(16, 1)],
            ..Default::default()
        };
        assert_eq!(run(3, &mut m).0, 0);
        assert_eq!(star_json_patch_call_count(2, 2), before + 1);
        assert_eq!(star_json_patch_call_count(3, 1), success + 1);
    }
    #[test]
    fn protocol_and_cleanup_failures_do_not_fabricate_native_exception() {
        for status in [6, 7, u32::MAX] {
            let before = star_json_patch_call_count(5, 2);
            let mut m = Mock {
                faults: vec![(22, status)],
                ..Default::default()
            };
            assert_eq!(run(5, &mut m), (2, 0xface));
            assert_eq!(ops(&m).last(), Some(&40));
            assert_eq!(star_json_patch_call_count(5, 2), before);
        }
        let mut m = Mock {
            faults: vec![(22, 2), (40, 5)],
            ..Default::default()
        };
        assert_eq!(run(5, &mut m).0, 2);
        let mut m = Mock {
            values: vec![(2, 99)],
            ..Default::default()
        };
        assert_eq!(run(1, &mut m).0, 2);
        assert_eq!(ops(&m), vec![3, 2, 41]);
    }
    #[test]
    fn reentrant_callbacks_and_thread_local_receipts() {
        unsafe extern "C" fn reenter(
            _: *mut c_void,
            op: u32,
            _: u32,
            _: u32,
            _: u64,
            out: *mut u64,
        ) -> u32 {
            if op == 0 {
                let mut m = Mock {
                    values: vec![(16, 1)],
                    ..Default::default()
                };
                assert_eq!(run(2, &mut m), (0, 0));
            }
            *out = 0;
            0
        }
        let before = star_json_patch_call_count(2, 1);
        let mut scalar = 5;
        assert_eq!(
            unsafe { star_json_patch_run(0, Some(reenter), std::ptr::null_mut(), &mut scalar) },
            0
        );
        assert_eq!(scalar, 5);
        assert_eq!(star_json_patch_call_count(2, 1), before + 1);
        std::thread::spawn(|| assert_eq!(star_json_patch_call_count(2, 1), 0))
            .join()
            .unwrap();
    }
    #[test]
    fn panic_is_contained_inside_controller_boundary() {
        let before = COUNTS.with(Cell::get)[0];
        let mut m = Mock::default();
        PANIC_AFTER_ATTEMPT.with(|flag| flag.set(true));
        assert_eq!(run(0, &mut m), (3, 0xface));
        assert!(m.trace.is_empty());
        assert_eq!(
            COUNTS.with(Cell::get)[0],
            [before[0] + 1, before[1], before[2]]
        );
    }
    #[test]
    fn uninitialized_scalar_is_not_read_and_only_find_writes() {
        use std::mem::MaybeUninit;
        let mut out = MaybeUninit::<u64>::uninit();
        let mut m = Mock::default();
        assert_eq!(
            unsafe {
                star_json_patch_run(
                    0,
                    Some(host),
                    (&mut m as *mut Mock).cast(),
                    out.as_mut_ptr(),
                )
            },
            0
        );
        // Do not read the untouched/uninitialized non-FIND slot.
        m.values = vec![(16, 1), (18, 1), (19, 1)];
        assert_eq!(
            unsafe {
                star_json_patch_run(
                    2,
                    Some(host),
                    (&mut m as *mut Mock).cast(),
                    out.as_mut_ptr(),
                )
            },
            0
        );
        assert_eq!(unsafe { out.assume_init() }, 1);
    }
    #[test]
    fn native_error_classes_and_failure_cleanup_preserve_output() {
        for entry in 0..10 {
            let first = match entry {
                0 => 0,
                1 => 3,
                2 => 16,
                _ => 4,
            };
            for class in 1..=5 {
                let mut m = Mock {
                    faults: vec![(first, class)],
                    ..Default::default()
                };
                let before = star_json_patch_call_count(entry, 2);
                assert_eq!(run(entry, &mut m), (1, 0xface));
                assert_eq!(star_json_patch_call_count(entry, 2), before + 1);
                if entry == 2 {
                    assert_eq!(ops(&m).last(), Some(&39));
                }
                if entry >= 3 {
                    assert_eq!(ops(&m).last(), Some(&40));
                }
                if class == 4 {
                    assert!(!ops(&m).contains(&36));
                }
            }
        }
    }
    #[test]
    fn find_later_match_and_no_match_have_exact_indices() {
        unsafe extern "C" fn indexed(
            raw: *mut c_void,
            op: u32,
            a: u32,
            b: u32,
            n: u64,
            out: *mut u64,
        ) -> u32 {
            let status = host(raw, op, a, b, n, out);
            if status == 0 && op == 19 {
                *out = u64::from(n == 2);
            }
            status
        }
        let mut m = Mock {
            values: vec![(16, 1), (18, 4)],
            ..Default::default()
        };
        let mut out = 99;
        assert_eq!(
            unsafe {
                star_json_patch_run(2, Some(indexed), (&mut m as *mut Mock).cast(), &mut out)
            },
            0
        );
        assert_eq!(out, 3);
        assert_eq!(
            m.trace
                .iter()
                .filter(|v| v.0 == 19)
                .map(|v| v.3)
                .collect::<Vec<_>>(),
            vec![0, 1, 2]
        );
        m.trace.clear();
        assert_eq!(run(2, &mut m), (0, 0));
        assert_eq!(m.trace.iter().filter(|v| v.0 == 19).count(), 4);
    }
}
