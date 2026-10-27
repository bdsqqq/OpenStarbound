//! WeightedPool policy; native frames own Items, containers, cursors and exceptions.
//! No retry cap: impossible native unique-selection progress remains impossible.
use std::cell::Cell;
use std::ffi::c_void;
use std::mem::size_of;
use std::panic::{catch_unwind, AssertUnwindSafe};

const VERSION: u32 = 1;
const INVALID: u32 = 2;
const PANIC: u32 = 3;
const MODES: usize = 19;
const STAGES: usize = 4;
const VOID: u32 = 0;
const U64: u32 = 1;
const BOOL: u32 = 2;
const F64: u32 = 3;
const BORROW: u32 = 4;
const DEFAULT_ITEM: u32 = 5;
const ITEM_RESULT: u32 = 6;
const ARG: u32 = 1;
const COUNT: u32 = 2;
const IS_EMPTY: u32 = 3;
const AT_BORROW: u32 = 4;
const AT_WEIGHT: u32 = 5;
const AT_ITEM_BORROW: u32 = 6;
const APPEND_ITEM_EXPRESSION: u32 = 7;
const CLEAR_ITEMS: u32 = 8;
const READ_TOTAL: u32 = 9;
const WRITE_TOTAL: u32 = 10;
const DRAW_SOURCE: u32 = 11;
const DRAW_GLOBAL: u32 = 12;
const DRAW_STATIC: u32 = 13;
const DRAW_SEED: u32 = 14;
const CALL_INDEX_SOURCE: u32 = 15;
const CALL_INDEX_GLOBAL: u32 = 16;
const CALL_INDEX_SEED: u32 = 17;
const READ_WEIGHT: u32 = 18;
const CONTAINER_SCOPE: u32 = 19;
const CONTAINER_END: u32 = 20;
const CONTAINER_ADD_EXPRESSION: u32 = 21;
const CONTAINER_NEXT: u32 = 22;
const UNIQUE_SET_SIZE: u32 = 23;
const UNIQUE_SET_ADD: u32 = 24;
const UNIQUE_END: u32 = 25;
const UNIQUE_APPEND_EXPRESSION: u32 = 26;
const UNIQUE_NEXT: u32 = 27;
const SCAN_SIZE: u32 = 28;

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbWpRequest {
    pub size: u32,
    pub version: u32,
    pub op: u32,
    pub reserved: u32,
    pub arg: u64,
}
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbWpReply {
    pub size: u32,
    pub version: u32,
    pub tag: u32,
    pub reserved: u32,
    pub value: u64,
}
pub type SbWpHost = unsafe extern "C" fn(*mut c_void, *const SbWpRequest, *mut SbWpReply) -> u32;
thread_local! {
    static COUNTS: Cell<[[u64; STAGES]; MODES]> = const { Cell::new([[0; STAGES]; MODES]) };
}
#[no_mangle]
pub extern "C" fn sb_wp_count(mode: u32, stage: u32) -> u64 {
    COUNTS.with(|counts| {
        counts
            .get()
            .get(mode as usize)
            .and_then(|row| row.get(stage as usize))
            .copied()
            .unwrap_or(0)
    })
}
fn reply(tag: u32, value: u64) -> SbWpReply {
    SbWpReply {
        size: size_of::<SbWpReply>() as u32,
        version: VERSION,
        tag,
        reserved: 0,
        value,
    }
}
fn valid_reply(value: &SbWpReply) -> bool {
    value.size == size_of::<SbWpReply>() as u32
        && value.version == VERSION
        && value.reserved == 0
        && match value.tag {
            VOID | BORROW | DEFAULT_ITEM => value.value == 0,
            BOOL => value.value <= 1,
            U64 | F64 | ITEM_RESULT => true,
            _ => false,
        }
}
fn valid_route(mode: u32, stage: u32) -> bool {
    mode < MODES as u32
        && match stage {
            0 => true,
            1 => mode == 1,
            2 | 3 => mode == 14,
            _ => false,
        }
}
struct Controller {
    context: *mut c_void,
    host: SbWpHost,
}
impl Controller {
    fn call(&self, op: u32, tag: u32, arg: u64) -> Result<u64, u32> {
        let request = SbWpRequest {
            size: size_of::<SbWpRequest>() as u32,
            version: VERSION,
            op,
            reserved: 0,
            arg,
        };
        let mut output = reply(u32::MAX, u64::MAX);
        // Only the opaque pointer spans reentry, never an exclusive native/Rust borrow.
        let status = unsafe { (self.host)(self.context, &request, &mut output) };
        if status != 0 {
            return Err(if status <= PANIC { status } else { INVALID });
        }
        if !valid_reply(&output) || output.tag != tag {
            return Err(INVALID);
        }
        Ok(output.value)
    }
    fn leaf(&self, op: u32) -> Result<(), u32> {
        self.call(op, VOID, 0).map(|_| ())
    }
    fn boolean(&self, op: u32) -> Result<bool, u32> {
        self.call(op, BOOL, 0).map(|value| value != 0)
    }
    fn run(&self, mode: u32, stage: u32) -> Result<SbWpReply, u32> {
        match stage {
            1 => {
                while !self.boolean(CONTAINER_END)? {
                    self.leaf(CONTAINER_ADD_EXPRESSION)?;
                    self.leaf(CONTAINER_NEXT)?;
                }
                return Ok(reply(VOID, 0));
            }
            2 => {
                let target = self.call(ARG, U64, 0)?;
                let mut seed = self.call(ARG, U64, 1)?;
                while self.call(UNIQUE_SET_SIZE, U64, 0)? < target {
                    seed = seed.wrapping_add(1);
                    let index = self.call(CALL_INDEX_SEED, U64, seed)?;
                    self.call(UNIQUE_SET_ADD, VOID, index)?;
                }
                return Ok(reply(VOID, 0));
            }
            3 => {
                while !self.boolean(UNIQUE_END)? {
                    self.leaf(UNIQUE_APPEND_EXPRESSION)?;
                    self.leaf(UNIQUE_NEXT)?;
                }
                return Ok(reply(VOID, 0));
            }
            _ => {}
        }
        Ok(match mode {
            0 => reply(VOID, 0), // Native initializer already established total=0.
            1 => {
                self.leaf(CONTAINER_SCOPE)?;
                reply(VOID, 0)
            }
            2 => {
                let weight = f64::from_bits(self.call(ARG, F64, 0)?);
                if weight <= 0.0 {
                    return Ok(reply(VOID, 0));
                }
                self.leaf(APPEND_ITEM_EXPRESSION)?;
                // Append's full expression can reenter and mutate total. Read AFTER it.
                let total = f64::from_bits(self.call(READ_TOTAL, F64, 0)?);
                self.call(WRITE_TOTAL, VOID, (total + weight).to_bits())?;
                reply(VOID, 0)
            }
            3 => {
                self.leaf(CLEAR_ITEMS)?;
                self.call(WRITE_TOTAL, VOID, 0.0f64.to_bits())?;
                reply(VOID, 0)
            }
            4 => reply(BORROW, 0),
            5 => reply(U64, self.call(COUNT, U64, 0)?),
            6 | 7 | 8 => {
                let index = self.call(ARG, U64, 0)?;
                let (op, tag) = match mode {
                    6 => (AT_BORROW, BORROW),
                    7 => (AT_WEIGHT, F64),
                    _ => (AT_ITEM_BORROW, BORROW),
                };
                reply(tag, self.call(op, tag, index)?)
            }
            9 => reply(BOOL, self.call(IS_EMPTY, BOOL, 0)?),
            10 | 11 | 12 => {
                if self.boolean(IS_EMPTY)? {
                    return Ok(reply(DEFAULT_ITEM, 0));
                }
                let index = match mode {
                    10 => self.call(CALL_INDEX_SOURCE, U64, 0)?,
                    11 => self.call(CALL_INDEX_GLOBAL, U64, 0)?,
                    _ => {
                        let seed = self.call(ARG, U64, 0)?;
                        self.call(CALL_INDEX_SEED, U64, seed)?
                    }
                };
                reply(ITEM_RESULT, index)
            }
            // Native preserves the original forwarding prvalue and named List result.
            13 => reply(U64, self.call(DRAW_SEED, U64, 0)?),
            14 => {
                let desired = self.call(ARG, U64, 0)?;
                reply(U64, desired.min(self.call(COUNT, U64, 0)?))
            }
            15 => reply(F64, self.call(DRAW_SOURCE, F64, 0)?),
            16 => reply(F64, self.call(DRAW_GLOBAL, F64, 0)?),
            17 => {
                let seed = self.call(ARG, U64, 0)?;
                reply(F64, self.call(DRAW_STATIC, F64, seed)?)
            }
            18 => {
                let target = f64::from_bits(self.call(ARG, F64, 0)?);
                if self.boolean(IS_EMPTY)? {
                    return Ok(reply(U64, u64::MAX));
                }
                // Original optimized arm64 IR: one reciprocal, fused accumulation.
                // This is not a universal IEEE claim about native fast-math inputs.
                let inverse = 1.0 / f64::from_bits(self.call(READ_TOTAL, F64, 0)?);
                let mut accumulated = 0.0;
                let mut i = 0u64;
                while i < self.call(SCAN_SIZE, U64, 0)? {
                    let weight = f64::from_bits(self.call(READ_WEIGHT, F64, i)?);
                    accumulated = weight.mul_add(inverse, accumulated);
                    if target <= accumulated {
                        return Ok(reply(U64, i));
                    }
                    i = i.wrapping_add(1);
                }
                reply(U64, self.call(SCAN_SIZE, U64, 0)?.wrapping_sub(1))
            }
            _ => return Err(INVALID),
        })
    }
}
/// # Safety
/// `result` is live, aligned, readable/writable and initialized as a valid reply
/// (including its tag/payload). Context and synchronous host remain live through
/// reentry. The host retains neither request nor reply, contains all native
/// exceptions and owns all native storage. Null checks cannot prove provenance.
/// Error returns leave result untouched; prior successful callbacks are not undone.
#[no_mangle]
pub unsafe extern "C" fn sb_wp_run(
    mode: u32,
    stage: u32,
    context: *mut c_void,
    host: Option<SbWpHost>,
    result: *mut SbWpReply,
) -> u32 {
    if !valid_route(mode, stage) || context.is_null() || result.is_null() || !valid_reply(&*result)
    {
        return INVALID;
    }
    let Some(host) = host else {
        return INVALID;
    };
    catch_unwind(AssertUnwindSafe(|| {
        COUNTS.with(|counts| {
            let mut current = counts.get();
            current[mode as usize][stage as usize] =
                current[mode as usize][stage as usize].wrapping_add(1);
            counts.set(current);
        });
        match (Controller { context, host }).run(mode, stage) {
            Ok(value) => {
                result.write(value);
                0
            }
            Err(status) => status,
        }
    }))
    .unwrap_or(PANIC)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;
    use std::collections::{BTreeSet, VecDeque};
    // Exact request and reply, plus callback status. No panic may escape extern C.
    #[derive(Clone, Debug)]
    struct Step {
        op: u32,
        arg: u64,
        out: SbWpReply,
        status: u32,
    }
    fn step(op: u32, arg: u64, tag: u32, value: u64) -> Step {
        Step {
            op,
            arg,
            out: reply(tag, value),
            status: 0,
        }
    }
    fn void(op: u32) -> Step {
        step(op, 0, VOID, 0)
    }
    fn val(op: u32, tag: u32, value: u64) -> Step {
        step(op, 0, tag, value)
    }
    struct Script {
        steps: VecDeque<Step>,
        seen: Vec<(u32, u64)>,
        failed: bool,
    }
    unsafe extern "C" fn scripted(
        context: *mut c_void,
        request: *const SbWpRequest,
        output: *mut SbWpReply,
    ) -> u32 {
        let script = &mut *context.cast::<Script>();
        let request = *request;
        script.seen.push((request.op, request.arg));
        let Some(s) = script.steps.pop_front() else {
            script.failed = true;
            return INVALID;
        };
        if request
            != (SbWpRequest {
                size: 24,
                version: 1,
                op: s.op,
                reserved: 0,
                arg: s.arg,
            })
        {
            script.failed = true;
            return INVALID;
        }
        output.write(s.out);
        s.status
    }
    #[derive(Clone)]
    struct Case {
        mode: u32,
        stage: u32,
        steps: Vec<Step>,
        out: SbWpReply,
    }
    fn case(mode: u32, stage: u32, steps: Vec<Step>, tag: u32, value: u64) -> Case {
        Case {
            mode,
            stage,
            steps,
            out: reply(tag, value),
        }
    }
    fn execute(c: &Case, status: u32, consumed: usize) {
        let mut script = Script {
            steps: c.steps.clone().into(),
            seen: vec![],
            failed: false,
        };
        let original = reply(U64, 0xfeed_face);
        let mut out = original;
        let before = sb_wp_count(c.mode, c.stage);
        let actual = unsafe {
            sb_wp_run(
                c.mode,
                c.stage,
                (&mut script as *mut Script).cast(),
                Some(scripted),
                &mut out,
            )
        };
        assert_eq!(actual, status, "route {}/{}", c.mode, c.stage);
        assert!(!script.failed, "request mismatch: {:?}", script.seen);
        assert_eq!(script.seen.len(), consumed);
        assert_eq!(script.steps.len(), c.steps.len() - consumed);
        assert_eq!(out, if status == 0 { c.out } else { original });
        assert_eq!(sb_wp_count(c.mode, c.stage), before.wrapping_add(1));
    }
    fn cases() -> Vec<Case> {
        let bits = f64::to_bits;
        let mut all = vec![
            case(0, 0, vec![], VOID, 0),
            case(1, 0, vec![void(CONTAINER_SCOPE)], VOID, 0),
            case(
                1,
                1,
                vec![
                    val(CONTAINER_END, BOOL, 0),
                    void(CONTAINER_ADD_EXPRESSION),
                    void(CONTAINER_NEXT),
                    val(CONTAINER_END, BOOL, 1),
                ],
                VOID,
                0,
            ),
            case(
                2,
                0,
                vec![
                    val(ARG, F64, bits(2.0)),
                    void(APPEND_ITEM_EXPRESSION),
                    val(READ_TOTAL, F64, bits(7.0)),
                    step(WRITE_TOTAL, bits(9.0), VOID, 0),
                ],
                VOID,
                0,
            ),
            case(
                3,
                0,
                vec![void(CLEAR_ITEMS), step(WRITE_TOTAL, 0, VOID, 0)],
                VOID,
                0,
            ),
            case(4, 0, vec![], BORROW, 0),
            case(5, 0, vec![val(COUNT, U64, u64::MAX)], U64, u64::MAX),
            case(
                6,
                0,
                vec![val(ARG, U64, 9), step(AT_BORROW, 9, BORROW, 0)],
                BORROW,
                0,
            ),
            case(
                7,
                0,
                vec![val(ARG, U64, 8), step(AT_WEIGHT, 8, F64, bits(2.5))],
                F64,
                bits(2.5),
            ),
            case(
                8,
                0,
                vec![val(ARG, U64, 7), step(AT_ITEM_BORROW, 7, BORROW, 0)],
                BORROW,
                0,
            ),
            case(9, 0, vec![val(IS_EMPTY, BOOL, 1)], BOOL, 1),
            case(
                10,
                0,
                vec![val(IS_EMPTY, BOOL, 0), val(CALL_INDEX_SOURCE, U64, 4)],
                ITEM_RESULT,
                4,
            ),
            case(
                11,
                0,
                vec![val(IS_EMPTY, BOOL, 0), val(CALL_INDEX_GLOBAL, U64, 3)],
                ITEM_RESULT,
                3,
            ),
            case(
                12,
                0,
                vec![
                    val(IS_EMPTY, BOOL, 0),
                    val(ARG, U64, u64::MAX),
                    step(CALL_INDEX_SEED, u64::MAX, U64, 2),
                ],
                ITEM_RESULT,
                2,
            ),
            case(13, 0, vec![val(DRAW_SEED, U64, 23)], U64, 23),
            case(14, 0, vec![val(ARG, U64, 5), val(COUNT, U64, 3)], U64, 3),
            case(
                14,
                2,
                vec![
                    val(ARG, U64, 2),
                    step(ARG, 1, U64, u64::MAX),
                    val(UNIQUE_SET_SIZE, U64, 0),
                    step(CALL_INDEX_SEED, 0, U64, 1),
                    step(UNIQUE_SET_ADD, 1, VOID, 0),
                    val(UNIQUE_SET_SIZE, U64, 1),
                    step(CALL_INDEX_SEED, 1, U64, 1),
                    step(UNIQUE_SET_ADD, 1, VOID, 0),
                    val(UNIQUE_SET_SIZE, U64, 1),
                    step(CALL_INDEX_SEED, 2, U64, 0),
                    step(UNIQUE_SET_ADD, 0, VOID, 0),
                    val(UNIQUE_SET_SIZE, U64, 2),
                ],
                VOID,
                0,
            ),
            case(
                14,
                3,
                vec![
                    val(UNIQUE_END, BOOL, 0),
                    void(UNIQUE_APPEND_EXPRESSION),
                    void(UNIQUE_NEXT),
                    val(UNIQUE_END, BOOL, 1),
                ],
                VOID,
                0,
            ),
            case(
                15,
                0,
                vec![val(DRAW_SOURCE, F64, bits(0.25))],
                F64,
                bits(0.25),
            ),
            case(
                16,
                0,
                vec![val(DRAW_GLOBAL, F64, bits(0.5))],
                F64,
                bits(0.5),
            ),
            case(
                17,
                0,
                vec![val(ARG, U64, 42), step(DRAW_STATIC, 42, F64, bits(0.75))],
                F64,
                bits(0.75),
            ),
            case(
                18,
                0,
                vec![
                    val(ARG, F64, bits(0.5)),
                    val(IS_EMPTY, BOOL, 0),
                    val(READ_TOTAL, F64, bits(4.0)),
                    val(SCAN_SIZE, U64, 2),
                    step(READ_WEIGHT, 0, F64, bits(1.0)),
                    val(SCAN_SIZE, U64, 2),
                    step(READ_WEIGHT, 1, F64, bits(3.0)),
                ],
                U64,
                1,
            ),
        ];
        for mode in 10..=12 {
            all.push(case(mode, 0, vec![val(IS_EMPTY, BOOL, 1)], DEFAULT_ITEM, 0));
        }
        for weight in [-1.0f64, -0.0, 0.0] {
            all.push(case(2, 0, vec![val(ARG, F64, bits(weight))], VOID, 0));
        }
        all.extend([
            case(1, 1, vec![val(CONTAINER_END, BOOL, 1)], VOID, 0),
            case(
                14,
                2,
                vec![
                    val(ARG, U64, 0),
                    step(ARG, 1, U64, 123),
                    val(UNIQUE_SET_SIZE, U64, 0),
                ],
                VOID,
                0,
            ),
            case(14, 3, vec![val(UNIQUE_END, BOOL, 1)], VOID, 0),
            case(14, 0, vec![val(ARG, U64, 0), val(COUNT, U64, 9)], U64, 0),
            case(14, 0, vec![val(ARG, U64, 2), val(COUNT, U64, 9)], U64, 2),
            case(
                18,
                0,
                vec![val(ARG, F64, bits(0.0)), val(IS_EMPTY, BOOL, 1)],
                U64,
                u64::MAX,
            ),
            case(
                18,
                0,
                vec![
                    val(ARG, F64, bits(0.25)),
                    val(IS_EMPTY, BOOL, 0),
                    val(READ_TOTAL, F64, bits(4.0)),
                    val(SCAN_SIZE, U64, 2),
                    step(READ_WEIGHT, 0, F64, bits(1.0)),
                ],
                U64,
                0,
            ),
            case(
                18,
                0,
                vec![
                    val(ARG, F64, bits(2.0)),
                    val(IS_EMPTY, BOOL, 0),
                    val(READ_TOTAL, F64, bits(4.0)),
                    val(SCAN_SIZE, U64, 1),
                    step(READ_WEIGHT, 0, F64, bits(4.0)),
                    val(SCAN_SIZE, U64, 1),
                    val(SCAN_SIZE, U64, 1),
                ],
                U64,
                0,
            ),
        ]);
        all
    }
    #[test]
    fn every_mode_stage_and_all_28_leaves_have_exact_positive_traces() {
        let mut leaves = BTreeSet::new();
        let mut routes = BTreeSet::new();
        for c in cases() {
            leaves.extend(c.steps.iter().map(|s| s.op));
            routes.insert((c.mode, c.stage));
            execute(&c, 0, c.steps.len());
        }
        assert_eq!(leaves, (1..=28).collect());
        let expected: BTreeSet<_> = (0..19)
            .map(|m| (m, 0))
            .chain([(1, 1), (14, 2), (14, 3)])
            .collect();
        assert_eq!(routes, expected);
    }
    #[test]
    fn every_callback_failure_stops_at_that_leaf_and_preserves_output() {
        let mut covered = BTreeSet::new();
        for c in cases() {
            for i in 0..c.steps.len() {
                covered.insert(c.steps[i].op);
                for status in [1, 2, 3, 4, u32::MAX] {
                    let mut bad = c.clone();
                    bad.steps[i].status = status;
                    // Status is authoritative even if the callback left nonsense bytes.
                    bad.steps[i].out = reply(u32::MAX, u64::MAX);
                    execute(&bad, if status <= 3 { status } else { INVALID }, i + 1);
                }
                for field in 0..5 {
                    let mut bad = c.clone();
                    let out = &mut bad.steps[i].out;
                    match field {
                        0 => out.size = 0,
                        1 => out.version = 2,
                        2 => out.reserved = 1,
                        3 => out.tag = u32::MAX,
                        _ => out.tag = if out.tag == U64 { F64 } else { U64 },
                    }
                    execute(&bad, INVALID, i + 1);
                }
                if matches!(c.steps[i].out.tag, VOID | BOOL | BORROW) {
                    let mut bad = c.clone();
                    bad.steps[i].out.value = 2;
                    execute(&bad, INVALID, i + 1);
                }
            }
        }
        assert_eq!(covered, (1..=28).collect());
    }
    #[test]
    fn raw_float_payloads_are_not_reinterpreted_as_handles_or_rejected() {
        for bits in [
            0,
            1,
            u64::MAX,
            f64::INFINITY.to_bits(),
            f64::NEG_INFINITY.to_bits(),
            0x7ff8_0000_0000_1234,
            (-0.0f64).to_bits(),
        ] {
            let c = case(15, 0, vec![val(DRAW_SOURCE, F64, bits)], F64, bits);
            execute(&c, 0, 1);
        }
    }
    #[test]
    fn abi_layout() {
        use std::mem::{align_of, offset_of};
        assert_eq!(size_of::<SbWpRequest>(), 24);
        assert_eq!(size_of::<SbWpReply>(), 24);
        assert_eq!(align_of::<SbWpRequest>(), 8);
        assert_eq!(align_of::<SbWpReply>(), 8);
        assert_eq!(
            [
                offset_of!(SbWpRequest, size),
                offset_of!(SbWpRequest, version),
                offset_of!(SbWpRequest, op),
                offset_of!(SbWpRequest, reserved),
                offset_of!(SbWpRequest, arg)
            ],
            [0, 4, 8, 12, 16]
        );
        assert_eq!(
            [
                offset_of!(SbWpReply, size),
                offset_of!(SbWpReply, version),
                offset_of!(SbWpReply, tag),
                offset_of!(SbWpReply, reserved),
                offset_of!(SbWpReply, value)
            ],
            [0, 4, 8, 12, 16]
        );
        assert_eq!(size_of::<Option<SbWpHost>>(), size_of::<*mut c_void>());
    }
    #[test]
    fn invalid_entries_never_call_host_or_increment_any_counter() {
        let before = COUNTS.with(Cell::get);
        let mut script = Script {
            steps: VecDeque::new(),
            seen: vec![],
            failed: false,
        };
        let ptr = (&mut script as *mut Script).cast();
        for mode in 0..=20 {
            for stage in 0..=5 {
                if valid_route(mode, stage) {
                    continue;
                }
                let mut out = reply(U64, 77);
                let original = out;
                assert_eq!(
                    unsafe { sb_wp_run(mode, stage, ptr, Some(scripted), &mut out) },
                    INVALID
                );
                assert_eq!(out, original);
            }
        }
        let mut malformed = vec![];
        let mut r = reply(VOID, 0);
        r.size = 23;
        malformed.push(r);
        let mut r = reply(VOID, 0);
        r.version = 0;
        malformed.push(r);
        let mut r = reply(VOID, 0);
        r.reserved = 1;
        malformed.push(r);
        malformed.extend([
            reply(77, 0),
            reply(VOID, 1),
            reply(BOOL, 2),
            reply(BORROW, 1),
            reply(DEFAULT_ITEM, 1),
        ]);
        for mut out in malformed {
            let original = out;
            assert_eq!(
                unsafe { sb_wp_run(2, 0, ptr, Some(scripted), &mut out) },
                INVALID
            );
            assert_eq!(out, original);
        }
        let mut out = reply(VOID, 0);
        assert_eq!(
            unsafe { sb_wp_run(0, 0, std::ptr::null_mut(), Some(scripted), &mut out) },
            INVALID
        );
        assert_eq!(unsafe { sb_wp_run(0, 0, ptr, None, &mut out) }, INVALID);
        assert_eq!(
            unsafe { sb_wp_run(0, 0, ptr, Some(scripted), std::ptr::null_mut()) },
            INVALID
        );
        assert_eq!(COUNTS.with(Cell::get), before);
        assert!(script.seen.is_empty() && !script.failed);
        assert_eq!(sb_wp_count(u32::MAX, 0), 0);
        assert_eq!(sb_wp_count(0, u32::MAX), 0);
    }
    #[test]
    fn valid_initial_reply_tags_and_payloads_are_accepted() {
        let mut script = Script {
            steps: VecDeque::new(),
            seen: vec![],
            failed: false,
        };
        let ptr = (&mut script as *mut Script).cast();
        for mut out in [
            reply(VOID, 0),
            reply(U64, u64::MAX),
            reply(BOOL, 1),
            reply(F64, u64::MAX),
            reply(BORROW, 0),
            reply(DEFAULT_ITEM, 0),
            reply(ITEM_RESULT, u64::MAX),
        ] {
            assert_eq!(unsafe { sb_wp_run(0, 0, ptr, Some(scripted), &mut out) }, 0);
            assert_eq!(out, reply(VOID, 0));
        }
    }
    #[test]
    fn counters_are_thread_local_and_wrap_without_panicking() {
        let saved = COUNTS.with(Cell::get);
        COUNTS.with(|c| {
            let mut v = c.get();
            v[0][0] = u64::MAX;
            c.set(v);
        });
        execute(&case(0, 0, vec![], VOID, 0), 0, 0);
        assert_eq!(sb_wp_count(0, 0), 0);
        std::thread::spawn(|| {
            assert_eq!(COUNTS.with(Cell::get), [[0; STAGES]; MODES]);
            execute(&case(0, 0, vec![], VOID, 0), 0, 0);
            assert_eq!(sb_wp_count(0, 0), 1);
        })
        .join()
        .unwrap();
        assert_eq!(sb_wp_count(0, 0), 0);
        COUNTS.with(|c| c.set(saved));
    }

    // Test-only native stand-in. Each RefCell borrow ends BEFORE nested FFI.
    // Using a long-lived &mut State here would invalidate the reentry witness.
    struct State {
        total: f64,
        log: Vec<(u32, u64)>,
        failed: bool,
        nested: bool,
    }
    struct Reentrant {
        state: RefCell<State>,
    }
    unsafe extern "C" fn lifecycle(
        context: *mut c_void,
        req: *const SbWpRequest,
        out: *mut SbWpReply,
    ) -> u32 {
        let host = &*context.cast::<Reentrant>();
        let r = *req;
        host.state.borrow_mut().log.push((r.op, r.arg));
        let response = match r.op {
            ARG => reply(F64, 2.0f64.to_bits()),
            APPEND_ITEM_EXPRESSION => {
                // Simulate destructor reentry after stable append: clear changes total.
                let mut nested = reply(VOID, 0);
                let status = sb_wp_run(3, 0, context, Some(lifecycle), &mut nested);
                if status != 0 || nested != reply(VOID, 0) {
                    host.state.borrow_mut().failed = true;
                    return INVALID;
                }
                reply(VOID, 0)
            }
            CLEAR_ITEMS => {
                // Cross-route reentry before clear's WRITE_TOTAL, no borrowed State.
                let mut nested = reply(VOID, 0);
                let status = sb_wp_run(4, 0, context, Some(lifecycle), &mut nested);
                let mut state = host.state.borrow_mut();
                state.nested = status == 0 && nested == reply(BORROW, 0);
                reply(VOID, 0)
            }
            READ_TOTAL => reply(F64, host.state.borrow().total.to_bits()),
            WRITE_TOTAL => {
                host.state.borrow_mut().total = f64::from_bits(r.arg);
                reply(VOID, 0)
            }
            _ => {
                host.state.borrow_mut().failed = true;
                return INVALID;
            }
        };
        out.write(response);
        0
    }
    #[test]
    fn append_full_expression_reentry_precedes_total_read_and_clear_reset() {
        let host = Reentrant {
            state: RefCell::new(State {
                total: 99.0,
                log: vec![],
                failed: false,
                nested: false,
            }),
        };
        let mut out = reply(VOID, 0);
        let before_clear = sb_wp_count(3, 0);
        let before_items = sb_wp_count(4, 0);
        assert_eq!(
            unsafe {
                sb_wp_run(
                    2,
                    0,
                    (&host as *const Reentrant).cast_mut().cast(),
                    Some(lifecycle),
                    &mut out,
                )
            },
            0
        );
        let state = host.state.borrow();
        assert_eq!(state.total, 2.0);
        assert!(state.nested && !state.failed);
        assert_eq!(
            state.log,
            vec![
                (ARG, 0),
                (APPEND_ITEM_EXPRESSION, 0),
                (CLEAR_ITEMS, 0),
                (WRITE_TOTAL, 0),
                (READ_TOTAL, 0),
                (WRITE_TOTAL, 2.0f64.to_bits())
            ]
        );
        assert_eq!(sb_wp_count(3, 0), before_clear.wrapping_add(1));
        assert_eq!(sb_wp_count(4, 0), before_items.wrapping_add(1));
    }

    struct NestedStep {
        step: Step,
        calls: Vec<(u32, u32, SbWpReply)>,
    }
    struct NestedScript {
        steps: RefCell<VecDeque<NestedStep>>,
        failed: Cell<bool>,
    }
    unsafe extern "C" fn nested_host(
        context: *mut c_void,
        req: *const SbWpRequest,
        out: *mut SbWpReply,
    ) -> u32 {
        let script = &*context.cast::<NestedScript>();
        // Pop under a short borrow, then release it before ANY nested entry.
        let next = { script.steps.borrow_mut().pop_front() };
        let Some(next) = next else {
            script.failed.set(true);
            return INVALID;
        };
        let expected = SbWpRequest {
            size: 24,
            version: 1,
            op: next.step.op,
            reserved: 0,
            arg: next.step.arg,
        };
        if *req != expected {
            script.failed.set(true);
            return INVALID;
        }
        for (mode, stage, expected) in next.calls {
            let mut result = reply(VOID, 0);
            if sb_wp_run(mode, stage, context, Some(nested_host), &mut result) != 0
                || result != expected
            {
                script.failed.set(true);
                return INVALID;
            }
        }
        out.write(next.step.out);
        next.step.status
    }
    #[test]
    fn native_continuations_can_reenter_all_permitted_stages() {
        let plain = |step| NestedStep {
            step,
            calls: vec![],
        };
        let nested = |step, calls| NestedStep { step, calls };
        let steps = vec![
            nested(void(CONTAINER_SCOPE), vec![(1, 1, reply(VOID, 0))]),
            plain(val(CONTAINER_END, BOOL, 0)),
            nested(void(CONTAINER_ADD_EXPRESSION), vec![(2, 0, reply(VOID, 0))]),
            plain(val(ARG, F64, 1.0f64.to_bits())),
            // Native stand-in keeps Set and named result around both later stages.
            nested(
                void(APPEND_ITEM_EXPRESSION),
                vec![
                    (14, 0, reply(U64, 1)),
                    (14, 2, reply(VOID, 0)),
                    (14, 3, reply(VOID, 0)),
                ],
            ),
            plain(val(ARG, U64, 1)),
            plain(val(COUNT, U64, 1)),
            plain(val(ARG, U64, 1)),
            plain(step(ARG, 1, U64, u64::MAX)),
            plain(val(UNIQUE_SET_SIZE, U64, 0)),
            nested(
                step(CALL_INDEX_SEED, 0, U64, 0),
                vec![(17, 0, reply(F64, 0))],
            ),
            plain(val(ARG, U64, 0)),
            plain(step(DRAW_STATIC, 0, F64, 0)),
            plain(step(UNIQUE_SET_ADD, 0, VOID, 0)),
            plain(val(UNIQUE_SET_SIZE, U64, 1)),
            plain(val(UNIQUE_END, BOOL, 0)),
            nested(
                void(UNIQUE_APPEND_EXPRESSION),
                vec![(8, 0, reply(BORROW, 0))],
            ),
            plain(val(ARG, U64, 0)),
            plain(step(AT_ITEM_BORROW, 0, BORROW, 0)),
            plain(void(UNIQUE_NEXT)),
            plain(val(UNIQUE_END, BOOL, 1)),
            plain(val(READ_TOTAL, F64, 0)),
            plain(step(WRITE_TOTAL, 1.0f64.to_bits(), VOID, 0)),
            plain(void(CONTAINER_NEXT)),
            plain(val(CONTAINER_END, BOOL, 1)),
        ];
        let script = NestedScript {
            steps: RefCell::new(steps.into()),
            failed: Cell::new(false),
        };
        let before = COUNTS.with(Cell::get);
        let mut out = reply(VOID, 0);
        assert_eq!(
            unsafe {
                sb_wp_run(
                    1,
                    0,
                    (&script as *const NestedScript).cast_mut().cast(),
                    Some(nested_host),
                    &mut out,
                )
            },
            0
        );
        assert_eq!(out, reply(VOID, 0));
        assert!(!script.failed.get());
        assert!(script.steps.borrow().is_empty());
        let after = COUNTS.with(Cell::get);
        let touched: BTreeSet<_> = [
            (1, 0),
            (1, 1),
            (2, 0),
            (14, 0),
            (14, 2),
            (14, 3),
            (17, 0),
            (8, 0),
        ]
        .into_iter()
        .collect();
        for mode in 0..MODES {
            for stage in 0..STAGES {
                assert_eq!(
                    after[mode][stage],
                    before[mode][stage].wrapping_add(u64::from(touched.contains(&(mode, stage))))
                );
            }
        }
    }

    #[test]
    fn fused_rounding_changes_the_selected_index_not_just_an_intermediate() {
        // Constructed binary rounding boundary, not a fitted native output:
        // the small first weight places the second multiply/add across a tie.
        // A third 2^-100 weight leaves the stored total unchanged, but makes
        // falling through distinguishable from selecting index1.
        let second_weight = 1.0 + 2.0f64.powi(-27);
        let first_weight = (3.0 * 2.0f64.powi(-54)) / (1.0 - 2.0f64.powi(-27));
        let third_weight = 2.0f64.powi(-100);
        let total = (first_weight + second_weight) + third_weight;
        let inverse = 1.0 / total;
        let accumulated = first_weight * inverse;
        assert_eq!(second_weight.mul_add(inverse, accumulated), 1.0);
        assert_eq!(
            second_weight * inverse + accumulated,
            f64::from_bits(1.0f64.to_bits() - 1)
        );
        let c = case(
            18,
            0,
            vec![
                val(ARG, F64, 1.0f64.to_bits()),
                val(IS_EMPTY, BOOL, 0),
                val(READ_TOTAL, F64, total.to_bits()),
                val(SCAN_SIZE, U64, 3),
                step(READ_WEIGHT, 0, F64, first_weight.to_bits()),
                val(SCAN_SIZE, U64, 3),
                step(READ_WEIGHT, 1, F64, second_weight.to_bits()),
            ],
            U64,
            1,
        );
        execute(&c, 0, c.steps.len());
    }

    #[test]
    fn numeric_scan_uses_reciprocal_and_fused_accumulation() {
        // Exact binary witness: (1+2^-27)*(1-2^-27)-1 is -2^-54
        // fused, but zero when the product rounds before addition.
        let a = 1.0 + 2.0f64.powi(-27);
        let b = 1.0 - 2.0f64.powi(-27);
        assert_eq!(a.mul_add(b, -1.0), -2.0f64.powi(-54));
        assert_eq!(a * b - 1.0, 0.0);
        // Positive-weight scan witness, independently using f64's fused operation.
        // A signed accumulator witness above establishes fusion sensitivity; this
        // trace additionally establishes the actual inverse-first policy path.
        let total = 10.0f64;
        let inverse = 1.0 / total;
        let first = 3.0f64.mul_add(inverse, 0.0);
        let second = 7.0f64.mul_add(inverse, first);
        let c = case(
            18,
            0,
            vec![
                val(ARG, F64, second.to_bits()),
                val(IS_EMPTY, BOOL, 0),
                val(READ_TOTAL, F64, total.to_bits()),
                val(SCAN_SIZE, U64, 2),
                step(READ_WEIGHT, 0, F64, 3.0f64.to_bits()),
                val(SCAN_SIZE, U64, 2),
                step(READ_WEIGHT, 1, F64, 7.0f64.to_bits()),
            ],
            U64,
            1,
        );
        execute(&c, 0, c.steps.len());
    }
}
