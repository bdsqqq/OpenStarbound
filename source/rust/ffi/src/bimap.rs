//! BiMap scalar policy; native map nodes, iterators and return values stay native.
//! Typed lab callers are separate from production dispatch or application adoption.
use std::cell::Cell;
use std::ffi::c_void;
use std::mem::{align_of, size_of};
use std::panic::{catch_unwind, AssertUnwindSafe};

const VERSION: u32 = 1;
const OK: u32 = 0;
const EXCEPTION: u32 = 1;
const INVALID: u32 = 2;
const PANIC: u32 = 3;
const VOID: u32 = 0;
const BOOL: u32 = 1;
const SIZE_VALUE: u32 = 2;
const MODES: u32 = 23;
const M_SIZE: u32 = 0;
const M_EMPTY: u32 = 1;
const M_HAS_LEFT: u32 = 2;
const M_HAS_RIGHT: u32 = 3;
const M_ADD: u32 = 4;
const M_OVERWRITE: u32 = 5;
const M_REMOVE_LEFT: u32 = 6;
const M_REMOVE_RIGHT: u32 = 7;
const M_CLEAR: u32 = 8;
const M_COPY_ASSIGN: u32 = 9;
const M_RANGE_INSERT: u32 = 10;
const M_LIST_INSERT: u32 = 11;
const M_EQUAL: u32 = 12;
const M_INSERT_ROUTE: u32 = 13;
const M_INSERT_LINK: u32 = 14;
const M_COPY_ENTRIES: u32 = 15;
const M_EQUAL_ENTRIES: u32 = 16;
const M_EQUAL_PAIR: u32 = 17;
const M_EQUAL_SCOPED_ENTRIES: u32 = 18;
const M_PRESENT: u32 = 19;
const M_REMOVE_TAKEN: u32 = 20;
const M_THROW_TAKE: u32 = 21;
const M_PAIRS: u32 = 22;
const SIZE: u32 = 1;
const EMPTY: u32 = 2;
const HAS_LEFT: u32 = 3;
const HAS_RIGHT: u32 = 4;
const THROW_LEFT: u32 = 5;
const THROW_RIGHT: u32 = 6;
const INSERT_IGNORED: u32 = 7;
const REMOVE_LEFT_IGNORED: u32 = 8;
const REMOVE_RIGHT_IGNORED: u32 = 9;
const RIGHT_FOR_LEFT_PRESENT: u32 = 10;
const LEFT_FOR_RIGHT_PRESENT: u32 = 11;
const REMOVE_RIGHT_USING_FOUND: u32 = 12;
const REMOVE_LEFT_USING_FOUND: u32 = 13;
const CLEAR_LEFT: u32 = 14;
const CLEAR_RIGHT: u32 = 15;
const ASSIGN_DISTINCT: u32 = 16;
const COPY_ENTRIES: u32 = 17;
const ITERATOR_PRESENT: u32 = 18;
const INSERT_CURRENT_IGNORED: u32 = 19;
const ADVANCE_ITERATOR: u32 = 20;
const INSERT_CURRENT_CHECKED: u32 = 21;
const THROW_CURRENT_DUPLICATE: u32 = 22;
const SELF_EQUAL: u32 = 23;
const OTHER_SIZE: u32 = 24;
const EQUAL_ENTRIES: u32 = 25;
const FIND_CURRENT_RIGHT: u32 = 26;
const CURRENT_RIGHT_NOT_EQUAL: u32 = 27;
const LEFT_INSERTED: u32 = 28;
const ASSERT_RIGHT_INSERTED: u32 = 29;
const LINK_LEFT: u32 = 30;
const LINK_RIGHT: u32 = 31;
const COMPARE_CURRENT_SCOPED: u32 = 32;
const PRESENT: u32 = 33;
const REMOVE_TAKEN: u32 = 34;
const THROW_TAKE: u32 = 35;
const APPEND_CURRENT: u32 = 36;

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbBiMapRequest {
    pub size: u32,
    pub version: u32,
    pub op: u32,
    pub reserved: u32,
    pub arg0: u64,
    pub arg1: u64,
}
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbBiMapReply {
    pub size: u32,
    pub version: u32,
    pub tag: u32,
    pub reserved: u32,
    pub value: u64,
}
pub type SbBiMapHost =
    unsafe extern "C" fn(*mut c_void, *const SbBiMapRequest, *mut SbBiMapReply) -> u32;
thread_local! {
    static COUNTS: Cell<[u64; MODES as usize]> = const { Cell::new([0; MODES as usize]) };
}
#[no_mangle]
pub extern "C" fn sb_bimap_count(mode: u32) -> u64 {
    COUNTS.with(|counts| counts.get().get(mode as usize).copied().unwrap_or(0))
}
fn reply(tag: u32, value: u64) -> SbBiMapReply {
    SbBiMapReply { size: size_of::<SbBiMapReply>() as u32, version: VERSION,
        tag, reserved: 0, value }
}
fn valid(value: &SbBiMapReply) -> bool {
    value.size == size_of::<SbBiMapReply>() as u32 && value.version == VERSION
        && value.reserved == 0 && match value.tag {
            VOID => value.value == 0,
            BOOL => value.value <= 1,
            SIZE_VALUE => usize::try_from(value.value).is_ok(),
            _ => false,
        }
}
fn catch_policy(action: impl FnOnce() -> Result<SbBiMapReply, u32>) -> Result<SbBiMapReply, u32> {
    catch_unwind(AssertUnwindSafe(action)).unwrap_or(Err(PANIC))
}
struct Controller { context: *mut c_void, host: SbBiMapHost }
impl Controller {
    fn call(&self, op: u32, tag: u32) -> Result<u64, u32> {
        let request = SbBiMapRequest { size: size_of::<SbBiMapRequest>() as u32,
            version: VERSION, op, reserved: 0, arg0: 0, arg1: 0 };
        let mut output = reply(u32::MAX, u64::MAX);
        let status = unsafe { (self.host)(self.context, &request, &mut output) };
        if status != OK {
            return Err(match status { EXCEPTION | INVALID | PANIC => status, _ => INVALID });
        }
        if !valid(&output) || output.tag != tag { return Err(INVALID); }
        Ok(output.value)
    }
    fn effect(&self, op: u32) -> Result<(), u32> { self.call(op, VOID).map(|_| ()) }
    fn test(&self, op: u32) -> Result<bool, u32> { self.call(op, BOOL).map(|n| n != 0) }
    fn count(&self, op: u32) -> Result<u64, u32> { self.call(op, SIZE_VALUE) }
    fn must_throw(&self, op: u32) -> Result<(), u32> {
        self.effect(op)?;
        Err(INVALID)
    }
    fn clear(&self) -> Result<(), u32> {
        self.effect(CLEAR_LEFT)?;
        self.effect(CLEAR_RIGHT)
    }
    fn equal_current(&self) -> Result<bool, u32> {
        // Missing keys are skipped by the native operator, not unequal.
        Ok(!(self.test(FIND_CURRENT_RIGHT)? && self.test(CURRENT_RIGHT_NOT_EQUAL)?))
    }
    fn run(&self, mode: u32) -> Result<SbBiMapReply, u32> {
        match mode {
            M_SIZE => return Ok(reply(SIZE_VALUE, self.count(SIZE)?)),
            M_EMPTY | M_HAS_LEFT | M_HAS_RIGHT => {
                let op = match mode { M_EMPTY => EMPTY, M_HAS_LEFT => HAS_LEFT, _ => HAS_RIGHT };
                return Ok(reply(BOOL, u64::from(self.test(op)?)));
            }
            M_ADD => {
                if self.test(HAS_LEFT)? { self.must_throw(THROW_LEFT)?; }
                if self.test(HAS_RIGHT)? { self.must_throw(THROW_RIGHT)?; }
                self.effect(INSERT_IGNORED)?;
            }
            M_OVERWRITE => {
                self.effect(REMOVE_LEFT_IGNORED)?;
                self.effect(REMOVE_RIGHT_IGNORED)?;
                self.effect(INSERT_IGNORED)?;
            }
            M_REMOVE_LEFT | M_REMOVE_RIGHT => {
                let (present, opposite, requested) = if mode == M_REMOVE_LEFT {
                    (RIGHT_FOR_LEFT_PRESENT, REMOVE_RIGHT_USING_FOUND, REMOVE_LEFT_IGNORED)
                } else {
                    (LEFT_FOR_RIGHT_PRESENT, REMOVE_LEFT_USING_FOUND, REMOVE_RIGHT_IGNORED)
                };
                if !self.test(present)? { return Ok(reply(BOOL, 0)); }
                self.effect(opposite)?;
                self.effect(requested)?;
                return Ok(reply(BOOL, 1));
            }
            M_CLEAR => self.clear()?,
            M_COPY_ASSIGN => {
                if self.test(ASSIGN_DISTINCT)? {
                    self.clear()?;
                    // Native range preparation belongs AFTER clear, not before
                    // the identity decision or before either destruction.
                    self.effect(COPY_ENTRIES)?;
                }
            }
            M_RANGE_INSERT | M_COPY_ENTRIES | M_LIST_INSERT | M_PAIRS => {
                while self.test(ITERATOR_PRESENT)? {
                    if mode == M_LIST_INSERT {
                        if !self.test(INSERT_CURRENT_CHECKED)? {
                            self.must_throw(THROW_CURRENT_DUPLICATE)?;
                        }
                    } else if mode == M_PAIRS {
                        self.effect(APPEND_CURRENT)?;
                    } else {
                        self.effect(INSERT_CURRENT_IGNORED)?;
                    }
                    self.effect(ADVANCE_ITERATOR)?;
                }
            }
            M_EQUAL => {
                if self.test(SELF_EQUAL)? { return Ok(reply(BOOL, 1)); }
                if self.count(SIZE)? != self.count(OTHER_SIZE)? { return Ok(reply(BOOL, 0)); }
                return Ok(reply(BOOL, u64::from(self.test(EQUAL_ENTRIES)?)));
            }
            M_EQUAL_ENTRIES => {
                while self.test(ITERATOR_PRESENT)? {
                    // Native BiMap equality skips a missing key. Returning
                    // false here would silently "fix" observable behavior.
                    if !self.equal_current()? {
                        return Ok(reply(BOOL, 0));
                    }
                    self.effect(ADVANCE_ITERATOR)?;
                }
                return Ok(reply(BOOL, 1));
            }
            M_EQUAL_PAIR => return Ok(reply(BOOL, u64::from(self.equal_current()?))),
            M_EQUAL_SCOPED_ENTRIES => {
                while self.test(ITERATOR_PRESENT)? {
                    // Native constructs the named reference pair once and keeps
                    // it alive through a nested EQUAL_PAIR Rust invocation.
                    if !self.test(COMPARE_CURRENT_SCOPED)? { return Ok(reply(BOOL, 0)); }
                    self.effect(ADVANCE_ITERATOR)?;
                }
                return Ok(reply(BOOL, 1));
            }
            // Native scopes retain iterators, condition-local Maybe values and
            // copied keys. Rust chooses the typed return route; removal occurs
            // only after the native copy is constructed, in its own scope.
            M_PRESENT => return Ok(reply(BOOL, u64::from(self.test(PRESENT)?))),
            M_REMOVE_TAKEN => self.effect(REMOVE_TAKEN)?,
            M_THROW_TAKE => self.must_throw(THROW_TAKE)?,
            M_INSERT_ROUTE => return Ok(reply(BOOL, u64::from(self.test(LEFT_INSERTED)?))),
            M_INSERT_LINK => {
                // This assertion is native-build dependent. In assertion-off
                // builds a conflicting right insertion still proceeds to link.
                self.effect(ASSERT_RIGHT_INSERTED)?;
                self.effect(LINK_LEFT)?;
                self.effect(LINK_RIGHT)?;
            }
            _ => return Err(INVALID),
        }
        Ok(reply(VOID, 0))
    }
}
/// # Safety
/// Result is live, aligned, initialized and readable/writable. Context and the
/// synchronous host remain live through reentry. The host owns all native
/// values, retains no envelope pointers and catches every C++ exception, which
/// is rethrown only after Rust returns. Checks do not prove pointer provenance.
/// Errors do not write result; host mutations are neither undone nor concealed.
#[no_mangle]
pub unsafe extern "C" fn sb_bimap_run(mode: u32, context: *mut c_void,
    host: Option<SbBiMapHost>, result: *mut SbBiMapReply) -> u32 {
    if mode >= MODES || context.is_null() || result.is_null()
        || (result as usize) % align_of::<SbBiMapReply>() != 0 { return INVALID; }
    let Some(host) = host else { return INVALID; };
    let initial = result.read();
    if !valid(&initial) { return INVALID; }
    let outcome = catch_policy(|| {
        COUNTS.with(|counts| {
            let mut current = counts.get();
            current[mode as usize] = current[mode as usize].wrapping_add(1);
            counts.set(current);
        });
        (Controller { context, host }).run(mode)
    });
    match outcome { Ok(value) => { result.write(value); OK }, Err(status) => status }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::{BTreeSet, VecDeque};
    use std::mem::offset_of;
    #[derive(Clone)]
    struct Step { op: u32, result: SbBiMapReply, status: u32 }
    fn v(op: u32) -> Step { Step { op, result: reply(VOID, 0), status: OK } }
    fn b(op: u32, value: bool) -> Step { Step { op, result: reply(BOOL, u64::from(value)), status: OK } }
    fn n(op: u32, value: u64) -> Step { Step { op, result: reply(SIZE_VALUE, value), status: OK } }
    struct Script { steps: VecDeque<Step>, seen: Vec<u32>, bad: bool }
    unsafe extern "C" fn host(context: *mut c_void, request: *const SbBiMapRequest,
        result: *mut SbBiMapReply) -> u32 {
        let s = &mut *context.cast::<Script>();
        let r = request.read();
        s.seen.push(r.op);
        if (r.size, r.version, r.reserved, r.arg0, r.arg1) != (32, VERSION, 0, 0, 0) {
            s.bad = true; return INVALID;
        }
        let Some(step) = s.steps.pop_front() else { s.bad = true; return INVALID; };
        if step.op != r.op { s.bad = true; return INVALID; }
        if step.status == OK { result.write(step.result); }
        step.status
    }
    fn execute(mode: u32, steps: Vec<Step>) -> (u32, SbBiMapReply, Script) {
        let mut s = Script { steps: steps.into(), seen: vec![], bad: false };
        let mut out = reply(BOOL, 1);
        let status = unsafe { sb_bimap_run(mode, (&mut s as *mut Script).cast(), Some(host), &mut out) };
        (status, out, s)
    }
    fn positive(mode: u32, steps: Vec<Step>, expected: SbBiMapReply) {
        let (status, out, s) = execute(mode, steps);
        assert_eq!(status, OK); assert_eq!(out, expected);
        assert!(s.steps.is_empty()); assert!(!s.bad);
    }
    fn scenarios() -> Vec<(u32, Vec<Step>, SbBiMapReply)> {
        vec![
            (M_SIZE, vec![n(SIZE, 4)], reply(SIZE_VALUE, 4)),
            (M_EMPTY, vec![b(EMPTY, false)], reply(BOOL, 0)),
            (M_HAS_LEFT, vec![b(HAS_LEFT, true)], reply(BOOL, 1)),
            (M_HAS_RIGHT, vec![b(HAS_RIGHT, false)], reply(BOOL, 0)),
            (M_ADD, vec![b(HAS_LEFT, false), b(HAS_RIGHT, false), v(INSERT_IGNORED)], reply(VOID, 0)),
            (M_OVERWRITE, vec![v(REMOVE_LEFT_IGNORED), v(REMOVE_RIGHT_IGNORED), v(INSERT_IGNORED)], reply(VOID, 0)),
            (M_REMOVE_LEFT, vec![b(RIGHT_FOR_LEFT_PRESENT, true), v(REMOVE_RIGHT_USING_FOUND), v(REMOVE_LEFT_IGNORED)], reply(BOOL, 1)),
            (M_REMOVE_RIGHT, vec![b(LEFT_FOR_RIGHT_PRESENT, true), v(REMOVE_LEFT_USING_FOUND), v(REMOVE_RIGHT_IGNORED)], reply(BOOL, 1)),
            (M_CLEAR, vec![v(CLEAR_LEFT), v(CLEAR_RIGHT)], reply(VOID, 0)),
            (M_COPY_ASSIGN, vec![b(ASSIGN_DISTINCT, true), v(CLEAR_LEFT), v(CLEAR_RIGHT), v(COPY_ENTRIES)], reply(VOID, 0)),
            (M_RANGE_INSERT, vec![b(ITERATOR_PRESENT, true), v(INSERT_CURRENT_IGNORED), v(ADVANCE_ITERATOR), b(ITERATOR_PRESENT, false)], reply(VOID, 0)),
            (M_LIST_INSERT, vec![b(ITERATOR_PRESENT, true), b(INSERT_CURRENT_CHECKED, true), v(ADVANCE_ITERATOR), b(ITERATOR_PRESENT, false)], reply(VOID, 0)),
            (M_EQUAL, vec![b(SELF_EQUAL, false), n(SIZE, 2), n(OTHER_SIZE, 2), b(EQUAL_ENTRIES, true)], reply(BOOL, 1)),
            (M_INSERT_ROUTE, vec![b(LEFT_INSERTED, true)], reply(BOOL, 1)),
            (M_INSERT_LINK, vec![v(ASSERT_RIGHT_INSERTED), v(LINK_LEFT), v(LINK_RIGHT)], reply(VOID, 0)),
            (M_COPY_ENTRIES, vec![b(ITERATOR_PRESENT, false)], reply(VOID, 0)),
            (M_EQUAL_ENTRIES, vec![b(ITERATOR_PRESENT, false)], reply(BOOL, 1)),
            (M_EQUAL_PAIR, vec![b(FIND_CURRENT_RIGHT, true), b(CURRENT_RIGHT_NOT_EQUAL, false)], reply(BOOL, 1)),
            (M_EQUAL_SCOPED_ENTRIES, vec![b(ITERATOR_PRESENT, true), b(COMPARE_CURRENT_SCOPED, true), v(ADVANCE_ITERATOR), b(ITERATOR_PRESENT, false)], reply(BOOL, 1)),
            (M_PRESENT, vec![b(PRESENT, true)], reply(BOOL, 1)),
            (M_REMOVE_TAKEN, vec![v(REMOVE_TAKEN)], reply(VOID, 0)),
            (M_PAIRS, vec![b(ITERATOR_PRESENT, true), v(APPEND_CURRENT), v(ADVANCE_ITERATOR), b(ITERATOR_PRESENT, false)], reply(VOID, 0)),
        ]
    }
    #[test]
    fn all_modes_have_scripted_positive_and_count() {
        let cases = scenarios();
        assert_eq!(cases.iter().map(|x| x.0).collect::<BTreeSet<_>>(),
            (0..MODES).filter(|m| *m != M_THROW_TAKE).collect());
        for (mode, steps, expected) in cases {
            let before = sb_bimap_count(mode); positive(mode, steps, expected);
            assert_eq!(sb_bimap_count(mode), before.wrapping_add(1));
        }
        assert_eq!(sb_bimap_count(MODES), 0);
    }
    #[test]
    fn every_effect_failure_stops_without_result_write_or_rollback() {
        for (mode, steps, _) in scenarios() {
            for i in 0..steps.len() {
                for status in [EXCEPTION, INVALID, PANIC, 55] {
                    let mut failed = steps.clone(); failed[i].status = status;
                    let (got, out, s) = execute(mode, failed);
                    assert_eq!(got, if status == 55 { INVALID } else { status });
                    assert_eq!(out, reply(BOOL, 1)); assert_eq!(s.seen.len(), i + 1);
                    assert!(!s.bad);
                }
            }
        }
    }
    #[test]
    fn malformed_or_wrong_tag_reply_fails_before_next_effect() {
        let bad = [SbBiMapReply { size: 23, ..reply(BOOL, 0) },
            SbBiMapReply { version: 2, ..reply(BOOL, 0) },
            SbBiMapReply { reserved: 1, ..reply(BOOL, 0) }, reply(BOOL, 2),
            reply(VOID, 1), reply(88, 0), reply(SIZE_VALUE, 0)];
        for result in bad {
            let (status, out, s) = execute(M_ADD, vec![Step { op: HAS_LEFT, result, status: OK }]);
            assert_eq!(status, INVALID); assert_eq!(out, reply(BOOL, 1)); assert_eq!(s.seen.len(), 1);
        }
    }
    #[test]
    fn left_duplicate_is_lazy_and_throw_cannot_acknowledge_success() {
        for (query, prefix, throw) in [
            (HAS_LEFT, vec![], THROW_LEFT),
            (HAS_RIGHT, vec![b(HAS_LEFT, false)], THROW_RIGHT),
        ] {
            for status in [OK, EXCEPTION] {
                let mut steps = prefix.clone(); steps.push(b(query, true));
                steps.push(Step { status, ..v(throw) });
                let (got, out, s) = execute(M_ADD, steps);
                assert_eq!(got, if status == OK { INVALID } else { EXCEPTION });
                assert_eq!(out, reply(BOOL, 1)); assert!(s.steps.is_empty()); assert!(!s.bad);
            }
        }
    }
    #[test]
    fn list_duplicate_never_advances_but_range_ignores_insert_result() {
        let (status, _, s) = execute(M_LIST_INSERT, vec![b(ITERATOR_PRESENT, true),
            b(INSERT_CURRENT_CHECKED, false), Step { status: EXCEPTION, ..v(THROW_CURRENT_DUPLICATE) }]);
        assert_eq!(status, EXCEPTION); assert_eq!(s.seen, [ITERATOR_PRESENT, INSERT_CURRENT_CHECKED, THROW_CURRENT_DUPLICATE]);
        for mode in [M_RANGE_INSERT, M_COPY_ENTRIES] {
            positive(mode, vec![b(ITERATOR_PRESENT, true), v(INSERT_CURRENT_IGNORED), v(ADVANCE_ITERATOR),
                b(ITERATOR_PRESENT, true), v(INSERT_CURRENT_IGNORED), v(ADVANCE_ITERATOR),
                b(ITERATOR_PRESENT, false)], reply(VOID, 0));
        }
    }
    #[test]
    fn missing_removal_and_self_assignment_do_not_mutate() {
        positive(M_REMOVE_LEFT, vec![b(RIGHT_FOR_LEFT_PRESENT, false)], reply(BOOL, 0));
        positive(M_REMOVE_RIGHT, vec![b(LEFT_FOR_RIGHT_PRESENT, false)], reply(BOOL, 0));
        positive(M_COPY_ASSIGN, vec![b(ASSIGN_DISTINCT, false)], reply(VOID, 0));
        positive(M_INSERT_ROUTE, vec![b(LEFT_INSERTED, false)], reply(BOOL, 0));
    }
    #[test]
    fn equality_keeps_native_missing_key_skip_and_short_circuits() {
        positive(M_EQUAL, vec![b(SELF_EQUAL, true)], reply(BOOL, 1));
        positive(M_EQUAL, vec![b(SELF_EQUAL, false), n(SIZE, 1), n(OTHER_SIZE, 2)], reply(BOOL, 0));
        positive(M_EQUAL, vec![b(SELF_EQUAL, false), n(SIZE, 1), n(OTHER_SIZE, 1), b(EQUAL_ENTRIES, false)], reply(BOOL, 0));
        positive(M_EQUAL_ENTRIES, vec![b(ITERATOR_PRESENT, true), b(FIND_CURRENT_RIGHT, false),
            v(ADVANCE_ITERATOR), b(ITERATOR_PRESENT, false)], reply(BOOL, 1));
        positive(M_EQUAL_ENTRIES, vec![b(ITERATOR_PRESENT, true), b(FIND_CURRENT_RIGHT, true),
            b(CURRENT_RIGHT_NOT_EQUAL, false), v(ADVANCE_ITERATOR), b(ITERATOR_PRESENT, true),
            b(FIND_CURRENT_RIGHT, true), b(CURRENT_RIGHT_NOT_EQUAL, true)], reply(BOOL, 0));
    }
    #[test]
    fn scoped_pair_and_loop_short_circuit_without_lifetime_flattening() {
        positive(M_EQUAL_PAIR, vec![b(FIND_CURRENT_RIGHT, false)], reply(BOOL, 1));
        positive(M_EQUAL_PAIR, vec![b(FIND_CURRENT_RIGHT, true), b(CURRENT_RIGHT_NOT_EQUAL, true)], reply(BOOL, 0));
        positive(M_EQUAL_SCOPED_ENTRIES, vec![b(ITERATOR_PRESENT, true), b(COMPARE_CURRENT_SCOPED, false)], reply(BOOL, 0));
    }
    #[test]
    fn maybe_routes_and_required_take_keep_failure_and_empty_paths_lazy() {
        positive(M_PRESENT, vec![b(PRESENT, false)], reply(BOOL, 0));
        positive(M_PAIRS, vec![b(ITERATOR_PRESENT, false)], reply(VOID, 0));
        for status in [OK, EXCEPTION, INVALID, PANIC, 55] {
            let before = sb_bimap_count(M_THROW_TAKE);
            let (got, out, s) = execute(M_THROW_TAKE, vec![Step { status, ..v(THROW_TAKE) }]);
            assert_eq!(got, match status { EXCEPTION | INVALID | PANIC => status, _ => INVALID });
            assert_eq!(out, reply(BOOL, 1));
            assert_eq!(s.seen, [THROW_TAKE]);
            assert_eq!(sb_bimap_count(M_THROW_TAKE), before.wrapping_add(1));
            assert!(s.steps.is_empty());
            assert!(!s.bad);
        }
    }
    #[test]
    fn assertion_off_right_conflict_still_links_in_native_order() {
        positive(M_INSERT_LINK, vec![v(ASSERT_RIGHT_INSERTED), v(LINK_LEFT), v(LINK_RIGHT)], reply(VOID, 0));
    }
    #[test]
    fn invalid_routes_pointers_and_initial_reply_never_call_host() {
        let mut s = Script { steps: VecDeque::new(), seen: vec![], bad: false };
        let context = (&mut s as *mut Script).cast(); let mut out = reply(VOID, 0);
        unsafe {
            assert_eq!(sb_bimap_run(MODES, context, Some(host), &mut out), INVALID);
            assert_eq!(sb_bimap_run(0, std::ptr::null_mut(), Some(host), &mut out), INVALID);
            assert_eq!(sb_bimap_run(0, context, None, &mut out), INVALID);
            assert_eq!(sb_bimap_run(0, context, Some(host), std::ptr::null_mut()), INVALID);
            let mut bytes = [0u8; 64]; let pointer = bytes.as_mut_ptr();
            let unaligned = if pointer as usize % align_of::<SbBiMapReply>() == 0 { pointer.add(1) } else { pointer };
            assert_eq!(sb_bimap_run(0, context, Some(host), unaligned.cast()), INVALID);
            out.version = 9;
            assert_eq!(sb_bimap_run(0, context, Some(host), &mut out), INVALID);
        }
        assert!(s.seen.is_empty());
    }
    #[test]
    fn abi_layout_and_internal_panic_containment() {
        assert_eq!((size_of::<SbBiMapRequest>(), size_of::<SbBiMapReply>()), (32, 24));
        assert_eq!(offset_of!(SbBiMapRequest, arg0), 16);
        assert_eq!(offset_of!(SbBiMapReply, value), 16);
        assert_eq!(catch_policy(|| panic!("isolated Rust policy panic")), Err(PANIC));
    }
}
