//! IdMap policy only: native frames retain typed keys, mapped values, streams,
//! cursor arithmetic and exceptions. No progress cap or rollback is introduced.
use std::cell::Cell;
use std::ffi::c_void;
use std::mem::{align_of, size_of};
use std::panic::{catch_unwind, AssertUnwindSafe};

const VERSION: u32 = 1;
const OK: u32 = 0;
const EXCEPTION: u32 = 1;
const INVALID: u32 = 2;
const PANIC: u32 = 3;
const MODES: usize = 10;
const STAGES: usize = 2;
const CTOR: u32 = 0;
const RANGE_CTOR: u32 = 1;
const NEXT: u32 = 2;
const ADD_EXPLICIT: u32 = 3;
const ADD_AUTO: u32 = 4;
const CLEAR: u32 = 5;
const EQUAL: u32 = 6;
const NOT_EQUAL: u32 = 7;
const READ: u32 = 8;
const WRITE: u32 = 9;
const ROOT: u32 = 0;
const CONTINUE: u32 = 1;
const VOID: u32 = 0;
const BOOL: u32 = 1;
const ASSERT_RANGE: u32 = 1;
const FULL: u32 = 2;
const THROW_FULL: u32 = 3;
const CURSOR_CONTAINS: u32 = 4;
const CURSOR_ADVANCE: u32 = 5;
const CURSOR_COMMIT: u32 = 6;
const EXPLICIT_INSERT: u32 = 7;
const THROW_DUPLICATE: u32 = 8;
const AUTO_INSERT: u32 = 9;
const CLEAR_MAP: u32 = 10;
const CLEAR_CURSOR: u32 = 11;
const SAME_BOUNDS: u32 = 12;
const BASE_EQUAL: u32 = 13;
const CALL_EQUAL: u32 = 14;
const READ_MAP: u32 = 15;
const READ_MIN: u32 = 16;
const READ_MAX: u32 = 17;
const READ_CURSOR: u32 = 18;
const WRITE_MAP: u32 = 19;
const WRITE_MIN: u32 = 20;
const WRITE_MAX: u32 = 21;
const WRITE_CURSOR: u32 = 22;

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbIdMapRequest {
    pub size: u32,
    pub version: u32,
    pub op: u32,
    pub reserved: u32,
    pub arg: u64,
}
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbIdMapReply {
    pub size: u32,
    pub version: u32,
    pub tag: u32,
    pub reserved: u32,
    pub value: u64,
}
pub type SbIdMapHost =
    unsafe extern "C" fn(*mut c_void, *const SbIdMapRequest, *mut SbIdMapReply) -> u32;

thread_local! {
    static COUNTS: Cell<[[u64; STAGES]; MODES]> = const { Cell::new([[0; STAGES]; MODES]) };
}
#[no_mangle]
pub extern "C" fn sb_idmap_count(mode: u32, stage: u32) -> u64 {
    COUNTS.with(|counts| {
        counts.get().get(mode as usize)
            .and_then(|row| row.get(stage as usize)).copied().unwrap_or(0)
    })
}
fn reply(tag: u32, value: u64) -> SbIdMapReply {
    SbIdMapReply { size: size_of::<SbIdMapReply>() as u32, version: VERSION,
        tag, reserved: 0, value }
}
fn valid_reply(value: &SbIdMapReply) -> bool {
    value.size == size_of::<SbIdMapReply>() as u32
        && value.version == VERSION
        && value.reserved == 0
        && match value.tag {
            VOID => value.value == 0,
            BOOL => value.value <= 1,
            _ => false,
        }
}
fn valid_route(mode: u32, stage: u32) -> bool {
    mode < MODES as u32
        && (stage == ROOT || (stage == CONTINUE && matches!(mode, NEXT | ADD_AUTO)))
}
// Kept separate so a pure Rust panic can exercise the boundary without ever
// unwinding an extern-C host callback (which is forbidden and may abort).
fn catch_policy(action: impl FnOnce() -> Result<SbIdMapReply, u32>) -> Result<SbIdMapReply, u32> {
    catch_unwind(AssertUnwindSafe(action)).unwrap_or(Err(PANIC))
}
struct Controller {
    context: *mut c_void,
    host: SbIdMapHost,
}
impl Controller {
    fn call(&self, op: u32, tag: u32) -> Result<u64, u32> {
        let request = SbIdMapRequest { size: size_of::<SbIdMapRequest>() as u32,
            version: VERSION, op, reserved: 0, arg: 0 };
        let mut output = reply(u32::MAX, u64::MAX);
        // Only an opaque pointer spans host reentry, not an exclusive frame borrow.
        let status = unsafe { (self.host)(self.context, &request, &mut output) };
        if status != OK {
            return Err(match status {
                EXCEPTION | INVALID | PANIC => status,
                _ => INVALID,
            });
        }
        if !valid_reply(&output) || output.tag != tag {
            return Err(INVALID);
        }
        Ok(output.value)
    }
    fn leaf(&self, op: u32) -> Result<(), u32> {
        self.call(op, VOID).map(|_| ())
    }
    fn boolean(&self, op: u32) -> Result<bool, u32> {
        self.call(op, BOOL).map(|value| value != 0)
    }
    fn must_throw(&self, op: u32) -> Result<(), u32> {
        // A native throw leaf cannot successfully acknowledge the request.
        self.leaf(op)?;
        Err(INVALID)
    }
    fn run(&self, mode: u32, stage: u32) -> Result<SbIdMapReply, u32> {
        if stage == CONTINUE {
            match mode {
                NEXT => {
                    while self.boolean(CURSOR_CONTAINS)? {
                        self.leaf(CURSOR_ADVANCE)?;
                    }
                    self.leaf(CURSOR_COMMIT)?;
                }
                ADD_AUTO => self.leaf(AUTO_INSERT)?,
                _ => return Err(INVALID),
            }
            return Ok(reply(VOID, 0));
        }
        Ok(match mode {
            CTOR | ADD_AUTO => reply(VOID, 0), // Native initializers / named local follow outside Rust.
            RANGE_CTOR => {
                self.leaf(ASSERT_RANGE)?;
                reply(VOID, 0)
            }
            NEXT => {
                // Fullness precedes the native key copy; CONTINUE uses that native local.
                if self.boolean(FULL)? {
                    self.must_throw(THROW_FULL)?;
                }
                reply(VOID, 0)
            }
            ADD_EXPLICIT => {
                if !self.boolean(EXPLICIT_INSERT)? {
                    self.must_throw(THROW_DUPLICATE)?;
                }
                reply(VOID, 0)
            }
            CLEAR => {
                self.leaf(CLEAR_MAP)?;
                self.leaf(CLEAR_CURSOR)?;
                reply(VOID, 0)
            }
            EQUAL => {
                let equal = self.boolean(SAME_BOUNDS)? && self.boolean(BASE_EQUAL)?;
                reply(BOOL, u64::from(equal))
            }
            NOT_EQUAL => reply(BOOL, u64::from(!self.boolean(CALL_EQUAL)?)),
            READ => {
                self.leaf(READ_MAP)?;
                self.leaf(READ_MIN)?;
                self.leaf(READ_MAX)?;
                self.leaf(READ_CURSOR)?;
                reply(VOID, 0)
            }
            WRITE => {
                self.leaf(WRITE_MAP)?;
                self.leaf(WRITE_MIN)?;
                self.leaf(WRITE_MAX)?;
                self.leaf(WRITE_CURSOR)?;
                reply(VOID, 0)
            }
            _ => return Err(INVALID),
        })
    }
}
/// # Safety
/// `result` must be live, aligned, initialized and readable/writable. Context and
/// synchronous host stay live through reentry; the host retains neither request
/// nor reply, owns native storage and catches ALL native exceptions. Pointer
/// checks cannot establish provenance. Errors leave result untouched, but do not
/// undo earlier native full expressions or partial reads. No C++ unwind may enter Rust.
#[no_mangle]
pub unsafe extern "C" fn sb_idmap_run(
    mode: u32,
    stage: u32,
    context: *mut c_void,
    host: Option<SbIdMapHost>,
    result: *mut SbIdMapReply,
) -> u32 {
    if !valid_route(mode, stage) || context.is_null() || result.is_null()
        || (result as usize) % align_of::<SbIdMapReply>() != 0
    {
        return INVALID;
    }
    let Some(host) = host else { return INVALID; };
    if !valid_reply(&*result) {
        return INVALID;
    }
    let outcome = catch_policy(|| {
        COUNTS.with(|counts| {
            let mut current = counts.get();
            current[mode as usize][stage as usize] =
                current[mode as usize][stage as usize].wrapping_add(1);
            counts.set(current);
        });
        (Controller { context, host }).run(mode, stage)
    });
    match outcome {
        Ok(value) => { result.write(value); OK }
        Err(status) => status,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::{BTreeSet, VecDeque};
    use std::mem::offset_of;

    #[derive(Clone, Debug)]
    struct Step { op: u32, out: SbIdMapReply, status: u32 }
    fn void(op: u32) -> Step { Step { op, out: reply(VOID, 0), status: OK } }
    fn boolean(op: u32, value: bool) -> Step {
        Step { op, out: reply(BOOL, u64::from(value)), status: OK }
    }
    fn throwing(op: u32) -> Step {
        Step { op, out: reply(u32::MAX, u64::MAX), status: EXCEPTION }
    }
    #[derive(Clone)]
    struct Case { mode: u32, stage: u32, steps: Vec<Step>, out: SbIdMapReply, status: u32 }
    fn case(mode: u32, stage: u32, steps: Vec<Step>, out: SbIdMapReply) -> Case {
        Case { mode, stage, steps, out, status: OK }
    }
    fn unit(mode: u32, stage: u32, steps: Vec<Step>) -> Case {
        case(mode, stage, steps, reply(VOID, 0))
    }
    struct Script {
        steps: VecDeque<Step>,
        seen: Vec<u32>,
        failed: bool,
    }
    unsafe extern "C" fn scripted(
        context: *mut c_void, request: *const SbIdMapRequest, output: *mut SbIdMapReply,
    ) -> u32 {
        // This non-reentrant script does not stand in for the reentry tests below.
        let script = &mut *context.cast::<Script>();
        let request = *request;
        script.seen.push(request.op);
        let Some(step) = script.steps.pop_front() else {
            script.failed = true;
            return INVALID;
        };
        if request != (SbIdMapRequest { size: 24, version: 1, op: step.op, reserved: 0, arg: 0 })
            || *output != reply(u32::MAX, u64::MAX)
        {
            script.failed = true;
            return INVALID;
        }
        output.write(step.out);
        step.status
    }
    fn execute(c: &Case, expected_status: u32, consumed: usize) {
        let mut script = Script { steps: c.steps.clone().into(), seen: vec![], failed: false };
        let original = reply(BOOL, 1);
        let mut out = original;
        let before = sb_idmap_count(c.mode, c.stage);
        let status = unsafe {
            sb_idmap_run(c.mode, c.stage, (&mut script as *mut Script).cast(), Some(scripted), &mut out)
        };
        assert_eq!(status, expected_status, "route {}/{}", c.mode, c.stage);
        assert!(!script.failed, "request mismatch: {:?}", script.seen);
        assert_eq!(script.seen, c.steps[..consumed].iter().map(|s| s.op).collect::<Vec<_>>());
        assert_eq!(script.steps.len(), c.steps.len() - consumed);
        assert_eq!(out, if status == OK { c.out } else { original });
        assert_eq!(sb_idmap_count(c.mode, c.stage), before.wrapping_add(1));
    }
    fn cases() -> Vec<Case> {
        let mut cases = vec![
            unit(CTOR, ROOT, vec![]),
            unit(RANGE_CTOR, ROOT, vec![void(ASSERT_RANGE)]),
            unit(NEXT, ROOT, vec![boolean(FULL, false)]),
            unit(NEXT, CONTINUE, vec![boolean(CURSOR_CONTAINS, false), void(CURSOR_COMMIT)]),
            unit(NEXT, CONTINUE, vec![boolean(CURSOR_CONTAINS, true), void(CURSOR_ADVANCE),
                boolean(CURSOR_CONTAINS, true), void(CURSOR_ADVANCE),
                boolean(CURSOR_CONTAINS, false), void(CURSOR_COMMIT)]),
            unit(ADD_EXPLICIT, ROOT, vec![boolean(EXPLICIT_INSERT, true)]),
            unit(ADD_AUTO, ROOT, vec![]),
            unit(ADD_AUTO, CONTINUE, vec![void(AUTO_INSERT)]),
            unit(CLEAR, ROOT, vec![void(CLEAR_MAP), void(CLEAR_CURSOR)]),
            case(EQUAL, ROOT, vec![boolean(SAME_BOUNDS, false)], reply(BOOL, 0)),
            case(EQUAL, ROOT, vec![boolean(SAME_BOUNDS, true), boolean(BASE_EQUAL, false)], reply(BOOL, 0)),
            case(EQUAL, ROOT, vec![boolean(SAME_BOUNDS, true), boolean(BASE_EQUAL, true)], reply(BOOL, 1)),
            case(NOT_EQUAL, ROOT, vec![boolean(CALL_EQUAL, false)], reply(BOOL, 1)),
            case(NOT_EQUAL, ROOT, vec![boolean(CALL_EQUAL, true)], reply(BOOL, 0)),
            unit(READ, ROOT, vec![void(READ_MAP), void(READ_MIN), void(READ_MAX), void(READ_CURSOR)]),
            unit(WRITE, ROOT, vec![void(WRITE_MAP), void(WRITE_MIN), void(WRITE_MAX), void(WRITE_CURSOR)]),
        ];
        for (mode, probe, throw) in [(NEXT, FULL, THROW_FULL), (ADD_EXPLICIT, EXPLICIT_INSERT, THROW_DUPLICATE)] {
            let mut c = unit(mode, ROOT, vec![boolean(probe, mode == NEXT), throwing(throw)]);
            c.status = EXCEPTION;
            cases.push(c);
        }
        cases
    }
    fn all_for(mode: u32, stage: u32) {
        for c in cases().into_iter().filter(|c| c.mode == mode && c.stage == stage) {
            execute(&c, c.status, c.steps.len());
        }
    }

    #[test]
    fn all_ten_modes_twelve_routes_and_twenty_two_leaves() {
        let mut leaves = BTreeSet::new();
        let mut routes = BTreeSet::new();
        for c in cases() {
            routes.insert((c.mode, c.stage));
            leaves.extend(c.steps.iter().map(|s| s.op));
            execute(&c, c.status, c.steps.len());
        }
        assert_eq!(leaves, (1..=22).collect::<BTreeSet<_>>());
        assert_eq!(routes, (0..10).map(|m| (m, ROOT))
            .chain([(NEXT, CONTINUE), (ADD_AUTO, CONTINUE)]).collect::<BTreeSet<_>>());
    }
    #[test]
    fn constructors_keep_initializers_native_and_range_assert_void() {
        all_for(CTOR, ROOT);
        all_for(RANGE_CTOR, ROOT);
    }
    #[test]
    fn next_root_only_checks_fullness_before_native_key_copy() { all_for(NEXT, ROOT); }
    #[test]
    fn next_continuation_probes_advances_then_commits() { all_for(NEXT, CONTINUE); }
    #[test]
    fn explicit_insert_success_and_duplicate_throw() { all_for(ADD_EXPLICIT, ROOT); }
    #[test]
    fn auto_root_has_no_callbacks_and_continue_only_inserts() {
        all_for(ADD_AUTO, ROOT);
        all_for(ADD_AUTO, CONTINUE);
    }
    #[test]
    fn clear_map_precedes_cursor_reset() { all_for(CLEAR, ROOT); }
    #[test]
    fn equality_bounds_short_circuit_base_comparison() { all_for(EQUAL, ROOT); }
    #[test]
    fn inequality_calls_native_equal_and_negates_both_booleans() { all_for(NOT_EQUAL, ROOT); }
    #[test]
    fn read_preserves_map_min_max_cursor_order() { all_for(READ, ROOT); }
    #[test]
    fn write_preserves_map_min_max_cursor_order() { all_for(WRITE, ROOT); }
    #[test]
    fn every_leaf_failure_stops_immediately_without_output_mutation() {
        let mut covered = BTreeSet::new();
        for c in cases() {
            for i in 0..c.steps.len() {
                covered.insert(c.steps[i].op);
                for status in [EXCEPTION, INVALID, PANIC] {
                    let mut bad = c.clone();
                    bad.steps[i].status = status;
                    bad.steps[i].out = reply(u32::MAX, u64::MAX);
                    execute(&bad, status, i + 1);
                }
            }
        }
        assert_eq!(covered, (1..=22).collect::<BTreeSet<_>>());
    }
    #[test]
    fn unknown_callback_status_normalizes_to_invalid_at_every_leaf() {
        for c in cases() {
            for i in 0..c.steps.len() {
                for status in [4, 255, u32::MAX] {
                    let mut bad = c.clone();
                    bad.steps[i].status = status;
                    execute(&bad, INVALID, i + 1);
                }
            }
        }
    }
    #[test]
    fn mandatory_throw_success_acknowledgements_are_invalid() {
        for c in cases().into_iter().filter(|c| c.status == EXCEPTION) {
            let mut bad = c.clone();
            let last = bad.steps.last_mut().unwrap();
            last.status = OK;
            last.out = reply(VOID, 0);
            execute(&bad, INVALID, bad.steps.len());
            bad.steps.last_mut().unwrap().out = reply(BOOL, 1);
            execute(&bad, INVALID, bad.steps.len());
        }
    }
    #[test]
    fn malformed_callback_envelopes_rejected_at_every_leaf() {
        for c in cases() {
            for i in 0..c.steps.len() {
                for field in 0..6 {
                    let mut bad = c.clone();
                    let step = &mut bad.steps[i];
                    step.status = OK;
                    // Throw leaves expect VOID; their ordinary status bypasses payload checks.
                    if matches!(step.op, THROW_FULL | THROW_DUPLICATE) { step.out = reply(VOID, 0); }
                    match field {
                        0 => step.out.size = 23,
                        1 => step.out.version = 2,
                        2 => step.out.reserved = 1,
                        3 => step.out.tag = u32::MAX,
                        4 => step.out.tag = if step.out.tag == VOID { BOOL } else { VOID },
                        _ => step.out.value = 2,
                    }
                    execute(&bad, INVALID, i + 1);
                }
            }
        }
    }
    #[test]
    fn void_nonzero_and_bool_outside_zero_one_are_invalid() {
        for c in cases().into_iter().filter(|c| c.status == OK) {
            for i in 0..c.steps.len() {
                let tag = c.steps[i].out.tag;
                for value in [if tag == VOID { 1 } else { 2 }, u64::MAX] {
                    let mut bad = c.clone();
                    bad.steps[i].out.value = value;
                    execute(&bad, INVALID, i + 1);
                }
            }
        }
    }
    unsafe extern "C" fn untouched(
        _context: *mut c_void, _request: *const SbIdMapRequest, _output: *mut SbIdMapReply,
    ) -> u32 { OK }
    #[test]
    fn callback_must_replace_max_max_destination_sentinel() {
        let context = std::ptr::NonNull::<u8>::dangling().as_ptr().cast();
        let original = reply(BOOL, 1);
        let mut out = original;
        assert_eq!(unsafe { sb_idmap_run(NEXT, ROOT, context, Some(untouched), &mut out) }, INVALID);
        assert_eq!(out, original);
    }
    fn empty_script() -> Script { Script { steps: VecDeque::new(), seen: vec![], failed: false } }
    #[test]
    fn invalid_routes_never_call_host_or_increment_counts() {
        let before = COUNTS.with(Cell::get);
        let mut script = empty_script();
        let context = (&mut script as *mut Script).cast();
        for mode in (0..=11).chain([u32::MAX]) {
            for stage in [ROOT, CONTINUE, 2, u32::MAX] {
                if valid_route(mode, stage) { continue; }
                let mut out = reply(BOOL, 1);
                let original = out;
                assert_eq!(unsafe { sb_idmap_run(mode, stage, context, Some(scripted), &mut out) }, INVALID);
                assert_eq!(out, original);
            }
        }
        assert_eq!(COUNTS.with(Cell::get), before);
        assert!(script.seen.is_empty() && !script.failed);
    }
    #[test]
    fn null_context_host_and_output_rejected_before_callbacks() {
        let before = COUNTS.with(Cell::get);
        let mut script = empty_script();
        let context = (&mut script as *mut Script).cast();
        let mut out = reply(VOID, 0);
        assert_eq!(unsafe { sb_idmap_run(CTOR, ROOT, std::ptr::null_mut(), Some(scripted), &mut out) }, INVALID);
        assert_eq!(unsafe { sb_idmap_run(CTOR, ROOT, context, None, &mut out) }, INVALID);
        assert_eq!(unsafe { sb_idmap_run(CTOR, ROOT, context, Some(scripted), std::ptr::null_mut()) }, INVALID);
        assert_eq!(out, reply(VOID, 0));
        assert_eq!(COUNTS.with(Cell::get), before);
        assert!(script.seen.is_empty());
    }
    #[test]
    fn misaligned_output_is_rejected_without_read_or_write() {
        #[repr(align(8))]
        struct Bytes([u8; 32]);
        let mut bytes = Bytes([0xa5; 32]);
        let mut script = empty_script();
        let before = COUNTS.with(Cell::get);
        let output = unsafe { bytes.0.as_mut_ptr().add(1).cast::<SbIdMapReply>() };
        assert_eq!(unsafe { sb_idmap_run(CTOR, ROOT, (&mut script as *mut Script).cast(), Some(scripted), output) }, INVALID);
        assert_eq!(bytes.0, [0xa5; 32]);
        assert_eq!(COUNTS.with(Cell::get), before);
        assert!(script.seen.is_empty());
    }
    #[test]
    fn malformed_caller_reply_rejected_unchanged_before_counter() {
        let mut script = empty_script();
        let context = (&mut script as *mut Script).cast();
        let before = COUNTS.with(Cell::get);
        let mut malformed = vec![reply(VOID, 1), reply(BOOL, 2), reply(2, 0), reply(u32::MAX, u64::MAX)];
        let mut r = reply(VOID, 0); r.size = 0; malformed.push(r);
        let mut r = reply(VOID, 0); r.version = 0; malformed.push(r);
        let mut r = reply(VOID, 0); r.reserved = 1; malformed.push(r);
        for mut out in malformed {
            let original = out;
            assert_eq!(unsafe { sb_idmap_run(CTOR, ROOT, context, Some(scripted), &mut out) }, INVALID);
            assert_eq!(out, original);
        }
        assert_eq!(COUNTS.with(Cell::get), before);
        assert!(script.seen.is_empty());
    }
    #[test]
    fn canonical_caller_void_and_both_booleans_are_accepted() {
        let mut script = empty_script();
        for mut out in [reply(VOID, 0), reply(BOOL, 0), reply(BOOL, 1)] {
            assert_eq!(unsafe { sb_idmap_run(CTOR, ROOT, (&mut script as *mut Script).cast(), Some(scripted), &mut out) }, OK);
            assert_eq!(out, reply(VOID, 0));
        }
        assert!(script.seen.is_empty());
    }
    #[test]
    fn counters_are_thread_local_and_wrap_without_panicking() {
        let saved = COUNTS.with(Cell::get);
        COUNTS.with(|counts| { let mut v = counts.get(); v[0][0] = u64::MAX; counts.set(v); });
        execute(&unit(CTOR, ROOT, vec![]), OK, 0);
        assert_eq!(sb_idmap_count(CTOR, ROOT), 0);
        std::thread::spawn(|| {
            assert_eq!(COUNTS.with(Cell::get), [[0; STAGES]; MODES]);
            execute(&unit(CTOR, ROOT, vec![]), OK, 0);
            assert_eq!(sb_idmap_count(CTOR, ROOT), 1);
        }).join().unwrap();
        assert_eq!(sb_idmap_count(CTOR, ROOT), 0);
        COUNTS.with(|counts| counts.set(saved));
    }
    #[test]
    fn counter_queries_outside_shape_return_zero() {
        for (mode, stage) in [(10, 0), (0, 2), (u32::MAX, 0), (0, u32::MAX)] {
            assert_eq!(sb_idmap_count(mode, stage), 0);
        }
    }
    #[test]
    fn factored_boundary_catches_pure_rust_panic_without_extern_c_unwind() {
        let original = reply(BOOL, 1);
        let mut output = original;
        let result = catch_policy(|| -> Result<SbIdMapReply, u32> { panic!("controlled policy panic") });
        let status = match result { Ok(value) => { output = value; OK }, Err(status) => status };
        assert_eq!(status, PANIC);
        assert_eq!(output, original);
        assert_eq!(catch_policy(|| Ok(reply(VOID, 0))), Ok(reply(VOID, 0)));
        assert_eq!(catch_policy(|| Err(EXCEPTION)), Err(EXCEPTION));
    }
    #[test]
    fn abi_size_alignment_offsets_and_nullable_host_match_header() {
        assert_eq!(size_of::<SbIdMapRequest>(), 24);
        assert_eq!(size_of::<SbIdMapReply>(), 24);
        assert_eq!(align_of::<SbIdMapRequest>(), 8);
        assert_eq!(align_of::<SbIdMapReply>(), 8);
        assert_eq!([offset_of!(SbIdMapRequest, size), offset_of!(SbIdMapRequest, version),
            offset_of!(SbIdMapRequest, op), offset_of!(SbIdMapRequest, reserved), offset_of!(SbIdMapRequest, arg)], [0, 4, 8, 12, 16]);
        assert_eq!([offset_of!(SbIdMapReply, size), offset_of!(SbIdMapReply, version),
            offset_of!(SbIdMapReply, tag), offset_of!(SbIdMapReply, reserved), offset_of!(SbIdMapReply, value)], [0, 4, 8, 12, 16]);
        assert_eq!(size_of::<Option<SbIdMapHost>>(), size_of::<*mut c_void>());
    }

    // Reentry stand-in uses shared references and Cell fields ONLY. No &mut frame
    // or interior mutable borrow is held across a nested sb_idmap_run call.
    struct Reentrant {
        log: Cell<[u32; 32]>,
        len: Cell<usize>,
        failed: Cell<bool>,
        entered: Cell<bool>,
        collisions: Cell<u32>,
        advances: Cell<u32>,
    }
    impl Reentrant {
        fn new() -> Self {
            Self { log: Cell::new([0; 32]), len: Cell::new(0), failed: Cell::new(false),
                entered: Cell::new(false), collisions: Cell::new(2), advances: Cell::new(0) }
        }
        fn context(&self) -> *mut c_void { (self as *const Self).cast_mut().cast() }
    }
    unsafe fn nested(frame: &Reentrant, mode: u32, stage: u32) -> Result<SbIdMapReply, u32> {
        let mut out = reply(VOID, 0);
        let status = sb_idmap_run(mode, stage, frame.context(), Some(reentrant), &mut out);
        if status == OK { Ok(out) } else { Err(status) }
    }
    unsafe extern "C" fn reentrant(
        context: *mut c_void, request: *const SbIdMapRequest, output: *mut SbIdMapReply,
    ) -> u32 {
        let frame = &*context.cast::<Reentrant>();
        let req = *request;
        let mut log = frame.log.get();
        let len = frame.len.get();
        if len >= log.len() || req.size != 24 || req.version != VERSION || req.reserved != 0
            || req.arg != 0 || *output != reply(u32::MAX, u64::MAX)
        {
            frame.failed.set(true);
            return INVALID;
        }
        log[len] = req.op;
        frame.log.set(log);
        frame.len.set(len + 1);
        let value = match req.op {
            CALL_EQUAL => match nested(frame, EQUAL, ROOT) {
                Ok(value) => value,
                Err(status) => return status,
            },
            SAME_BOUNDS | BASE_EQUAL => reply(BOOL, 1),
            FULL => reply(BOOL, 0),
            CURSOR_CONTAINS => {
                let n = frame.collisions.get();
                if n != 0 { frame.collisions.set(n - 1); }
                reply(BOOL, u64::from(n != 0))
            }
            CURSOR_ADVANCE => { frame.advances.set(frame.advances.get() + 1); reply(VOID, 0) }
            CURSOR_COMMIT => reply(VOID, 0),
            AUTO_INSERT => {
                if !frame.entered.replace(true) {
                    // Native expression reentry: auto root, nested next root/local
                    // continuation, then insertion using the native named local.
                    for (mode, stage) in [(ADD_AUTO, ROOT), (NEXT, ROOT), (NEXT, CONTINUE), (ADD_AUTO, CONTINUE)] {
                        match nested(frame, mode, stage) {
                            Ok(value) if value == reply(VOID, 0) => {}
                            Ok(_) => { frame.failed.set(true); return INVALID; }
                            Err(status) => return status,
                        }
                    }
                }
                reply(VOID, 0)
            }
            _ => { frame.failed.set(true); return INVALID; }
        };
        output.write(value);
        OK
    }
    #[test]
    fn equality_wrapper_reentry_has_no_exclusive_frame_borrow() {
        let frame = Reentrant::new();
        let before_equal = sb_idmap_count(EQUAL, ROOT);
        let before_not = sb_idmap_count(NOT_EQUAL, ROOT);
        assert_eq!(unsafe { nested(&frame, NOT_EQUAL, ROOT) }, Ok(reply(BOOL, 0)));
        assert!(!frame.failed.get());
        assert_eq!(&frame.log.get()[..frame.len.get()], &[CALL_EQUAL, SAME_BOUNDS, BASE_EQUAL]);
        assert_eq!(sb_idmap_count(EQUAL, ROOT), before_equal.wrapping_add(1));
        assert_eq!(sb_idmap_count(NOT_EQUAL, ROOT), before_not.wrapping_add(1));
    }
    #[test]
    fn nested_auto_and_next_roots_and_continuations_use_cell_state() {
        let frame = Reentrant::new();
        let before = COUNTS.with(Cell::get);
        assert_eq!(unsafe { nested(&frame, ADD_AUTO, CONTINUE) }, Ok(reply(VOID, 0)));
        assert!(!frame.failed.get());
        assert_eq!(frame.advances.get(), 2);
        assert_eq!(&frame.log.get()[..frame.len.get()], &[AUTO_INSERT, FULL,
            CURSOR_CONTAINS, CURSOR_ADVANCE, CURSOR_CONTAINS, CURSOR_ADVANCE,
            CURSOR_CONTAINS, CURSOR_COMMIT, AUTO_INSERT]);
        let after = COUNTS.with(Cell::get);
        for mode in 0..MODES {
            for stage in 0..STAGES {
                let increment = match (mode as u32, stage as u32) {
                    (ADD_AUTO, CONTINUE) => 2,
                    (ADD_AUTO, ROOT) | (NEXT, ROOT) | (NEXT, CONTINUE) => 1,
                    _ => 0,
                };
                assert_eq!(after[mode][stage], before[mode][stage].wrapping_add(increment));
            }
        }
    }
    #[test]
    fn collision_loop_has_no_policy_iteration_cap() {
        let mut steps = Vec::new();
        for _ in 0..4097 { steps.extend([boolean(CURSOR_CONTAINS, true), void(CURSOR_ADVANCE)]); }
        steps.extend([boolean(CURSOR_CONTAINS, false), void(CURSOR_COMMIT)]);
        let c = unit(NEXT, CONTINUE, steps);
        execute(&c, OK, c.steps.len());
    }
}
