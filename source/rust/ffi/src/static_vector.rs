//! Scalar StaticVector policy. Typed storage, full expressions, temporaries,
//! iterator snapshots and pending C++ exceptions belong to native frames.
use std::cell::Cell;
use std::ffi::c_void;
use std::mem::{align_of, size_of};
use std::panic::{catch_unwind, AssertUnwindSafe};

const VERSION: u32 = 1;
const OK: u32 = 0;
const EXCEPTION: u32 = 1;
const INVALID: u32 = 2;
const PANIC: u32 = 3;
const MODES: usize = 26;
const STAGES: usize = 2;
const OPS: u32 = 40;
const DEFAULT_CTOR: u32 = 0;
const CTOR_INSERT: u32 = 1;
const CTOR_RESIZE: u32 = 2;
const RANGE_COPY: u32 = 3;
const RANGE_MOVE: u32 = 4;
const COPY_ASSIGN: u32 = 5;
const MOVE_ASSIGN: u32 = 6;
const LIST_ASSIGN: u32 = 7;
const SIZE: u32 = 8;
const EMPTY: u32 = 9;
const RESIZE: u32 = 10;
const AT: u32 = 11;
const INDEX: u32 = 12;
const PUSH_BACK: u32 = 13;
const POP_BACK: u32 = 14;
const INSERT_ONE: u32 = 15;
const INSERT_RANGE: u32 = 16;
const INSERT_LIST: u32 = 17;
const EMPLACE: u32 = 18;
const EMPLACE_BACK: u32 = 19;
const CLEAR: u32 = 20;
const ERASE_ONE: u32 = 21;
const ERASE_RANGE: u32 = 22;
const EQUAL: u32 = 23;
const NOT_EQUAL: u32 = 24;
const LESS: u32 = 25;
const ROOT: u32 = 0;
const CONTINUE: u32 = 1;
const VOID: u32 = 0;
const BOOL: u32 = 1;
const SIZE_VALUE: u32 = 2;
const READ_SIZE: u32 = 1;
const READ_CAPACITY: u32 = 2;
const READ_TARGET: u32 = 3;
const READ_INDEX: u32 = 4;
const READ_TO_ADD: u32 = 5;
const READ_START: u32 = 6;
const READ_END: u32 = 7;
const READ_SHIFT: u32 = 8;
const READ_REMOVE: u32 = 9;
const OTHER_SIZE: u32 = 10;
const SELF: u32 = 11;
const THROW_RESIZE: u32 = 12;
const THROW_AT: u32 = 13;
const ASSERT_INDEX: u32 = 14;
const THROW_POP: u32 = 15;
const THROW_EMPLACE_BACK: u32 = 16;
const INCREMENT_SIZE: u32 = 17;
const CONSTRUCT_LAST: u32 = 18;
const DECREMENT_SIZE: u32 = 19;
const DESTROY_LAST: u32 = 20;
const CALL_POP: u32 = 21;
const CALL_EMPLACE_VALUE: u32 = 22;
const CALL_RESIZE_OTHER: u32 = 23;
const CALL_ASSIGN: u32 = 24;
const ITERATOR_PRESENT: u32 = 25;
const CALL_EMPLACE_CURRENT: u32 = 26;
const ADVANCE_ITERATOR: u32 = 27;
const CALL_FORWARD: u32 = 28;
const CALL_RESIZE_ADD: u32 = 29;
const CALL_RESIZE_PLUS_ONE: u32 = 30;
const CALL_RESIZE_MINUS_ONE: u32 = 31;
const CALL_RESIZE_MINUS_REMOVE: u32 = 32;
const MOVE_ASSIGN_SLOTS: u32 = 33;
const ASSIGN_FROM_ITERATOR: u32 = 34;
const ASSIGN_FROM_ARGS: u32 = 35;
const ELEMENT_NOT_EQUAL: u32 = 36;
const CALL_EQUAL: u32 = 37;
const COMPARE_PAIR: u32 = 38;
const PAIR_LESS: u32 = 39;
const PAIR_GREATER: u32 = 40;

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbStaticVectorRequest {
    pub size: u32,
    pub version: u32,
    pub op: u32,
    pub reserved: u32,
    pub arg0: u64,
    pub arg1: u64,
}
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbStaticVectorReply {
    pub size: u32,
    pub version: u32,
    pub tag: u32,
    pub reserved: u32,
    pub value: u64,
}
pub type SbStaticVectorHost =
    unsafe extern "C" fn(*mut c_void, *const SbStaticVectorRequest, *mut SbStaticVectorReply) -> u32;

thread_local! {
    static COUNTS: Cell<[[u64; STAGES]; MODES]> = const { Cell::new([[0; STAGES]; MODES]) };
}
#[no_mangle]
pub extern "C" fn sb_static_vector_count(mode: u32, stage: u32) -> u64 {
    COUNTS.with(|counts| {
        counts.get().get(mode as usize)
            .and_then(|row| row.get(stage as usize)).copied().unwrap_or(0)
    })
}
fn reply(tag: u32, value: u64) -> SbStaticVectorReply {
    SbStaticVectorReply { size: size_of::<SbStaticVectorReply>() as u32,
        version: VERSION, tag, reserved: 0, value }
}
fn valid_reply(value: &SbStaticVectorReply) -> bool {
    value.size == size_of::<SbStaticVectorReply>() as u32
        && value.version == VERSION && value.reserved == 0
        && match value.tag {
            VOID => value.value == 0,
            BOOL => value.value <= 1,
            SIZE_VALUE => usize::try_from(value.value).is_ok(),
            _ => false,
        }
}
fn valid_route(mode: u32, stage: u32) -> bool {
    mode < MODES as u32 && (stage == ROOT || (mode == LESS && stage == CONTINUE))
}
// Test panic containment here, never by unwinding an extern-C callback.
fn catch_policy(action: impl FnOnce() -> Result<SbStaticVectorReply, u32>)
    -> Result<SbStaticVectorReply, u32>
{
    catch_unwind(AssertUnwindSafe(action)).unwrap_or(Err(PANIC))
}
struct Controller {
    context: *mut c_void,
    host: SbStaticVectorHost,
}
impl Controller {
    fn call(&self, op: u32, arg0: usize, arg1: usize, tag: u32) -> Result<u64, u32> {
        let request = SbStaticVectorRequest { size: size_of::<SbStaticVectorRequest>() as u32,
            version: VERSION, op, reserved: 0, arg0: arg0 as u64, arg1: arg1 as u64 };
        let mut output = reply(u32::MAX, u64::MAX);
        // Only opaque pointers and Rust-owned scalar envelopes span reentry.
        let status = unsafe { (self.host)(self.context, &request, &mut output) };
        if status != OK {
            return Err(match status { EXCEPTION | INVALID | PANIC => status, _ => INVALID });
        }
        if !valid_reply(&output) || output.tag != tag { return Err(INVALID); }
        Ok(output.value)
    }
    fn leaf(&self, op: u32) -> Result<(), u32> {
        self.indexed(op, 0, 0)
    }
    fn indexed(&self, op: u32, arg0: usize, arg1: usize) -> Result<(), u32> {
        self.call(op, arg0, arg1, VOID).map(|_| ())
    }
    fn size(&self, op: u32) -> Result<usize, u32> {
        self.call(op, 0, 0, SIZE_VALUE).map(|n| n as usize)
    }
    fn boolean(&self, op: u32) -> Result<bool, u32> {
        self.test(op, 0)
    }
    fn test(&self, op: u32, index: usize) -> Result<bool, u32> {
        self.call(op, index, 0, BOOL).map(|n| n != 0)
    }
    fn must_throw(&self, op: u32) -> Result<(), u32> {
        self.leaf(op)?;
        Err(INVALID)
    }
    fn run(&self, mode: u32, stage: u32) -> Result<SbStaticVectorReply, u32> {
        if stage == CONTINUE {
            // Native COMPARE_PAIR keeps the SAME original named a/b references
            // live for both comparisons. Rust neither reindexes nor copies T.
            let order = if self.boolean(PAIR_LESS)? { 1 }
                else if self.boolean(PAIR_GREATER)? { 2 } else { 0 };
            return Ok(reply(SIZE_VALUE, order));
        }
        match mode {
            DEFAULT_CTOR => {}
            CTOR_INSERT | CTOR_RESIZE | PUSH_BACK | INSERT_ONE | INSERT_LIST => {
                self.leaf(CALL_FORWARD)?;
            }
            RANGE_COPY | RANGE_MOVE => {
                while self.boolean(ITERATOR_PRESENT)? {
                    self.leaf(CALL_EMPLACE_CURRENT)?;
                    self.leaf(ADVANCE_ITERATOR)?;
                }
            }
            COPY_ASSIGN | MOVE_ASSIGN | LIST_ASSIGN => {
                if mode == COPY_ASSIGN && self.boolean(SELF)? { return Ok(reply(VOID, 0)); }
                self.leaf(CALL_RESIZE_OTHER)?;
                let mut i = 0usize;
                while i < self.size(READ_SIZE)? {
                    self.indexed(CALL_ASSIGN, i, 0)?;
                    i = i.wrapping_add(1);
                }
            }
            SIZE => return Ok(reply(SIZE_VALUE, self.size(READ_SIZE)? as u64)),
            EMPTY => return Ok(reply(BOOL, u64::from(self.size(READ_SIZE)? == 0))),
            RESIZE => {
                let target = self.size(READ_TARGET)?;
                if target > self.size(READ_CAPACITY)? { self.must_throw(THROW_RESIZE)?; }
                // Two local counters, not current-size loops. Reentry may change
                // size inside pop/emplace; only the BETWEEN-loops read is fresh.
                let mut i = self.size(READ_SIZE)?;
                while i > target {
                    self.leaf(CALL_POP)?;
                    i = i.wrapping_sub(1);
                }
                let mut j = self.size(READ_SIZE)?;
                while j < target {
                    self.leaf(CALL_EMPLACE_VALUE)?;
                    j = j.wrapping_add(1);
                }
            }
            AT => {
                let index = self.size(READ_INDEX)?;
                if index >= self.size(READ_SIZE)? { self.must_throw(THROW_AT)?; }
            }
            INDEX => self.leaf(ASSERT_INDEX)?,
            EMPLACE_BACK => {
                if self.size(READ_SIZE)?.wrapping_add(1) > self.size(READ_CAPACITY)? {
                    self.must_throw(THROW_EMPLACE_BACK)?;
                }
                self.leaf(INCREMENT_SIZE)?;
                self.leaf(CONSTRUCT_LAST)?;
            }
            POP_BACK => {
                if self.size(READ_SIZE)? == 0 { self.must_throw(THROW_POP)?; }
                self.leaf(DECREMENT_SIZE)?;
                self.leaf(DESTROY_LAST)?;
            }
            CLEAR => {
                while self.size(READ_SIZE)? != 0 { self.leaf(CALL_POP)?; }
            }
            INSERT_RANGE => {
                let to_add = self.size(READ_TO_ADD)?;
                let start = self.size(READ_START)?;
                let end = self.size(READ_END)?;
                let mut i = self.size(READ_SHIFT)?;
                self.leaf(CALL_RESIZE_ADD)?;
                // Even an empty input retains observable self-move assignments.
                while i != 0 {
                    self.indexed(MOVE_ASSIGN_SLOTS, end.wrapping_add(i).wrapping_sub(1),
                        start.wrapping_add(i).wrapping_sub(1))?;
                    i = i.wrapping_sub(1);
                }
                let mut j = 0usize;
                while j != to_add {
                    self.indexed(ASSIGN_FROM_ITERATOR, start.wrapping_add(j), 0)?;
                    j = j.wrapping_add(1);
                }
            }
            EMPLACE => {
                let index = self.size(READ_INDEX)?;
                self.leaf(CALL_RESIZE_PLUS_ONE)?;
                let mut i = self.size(READ_SIZE)?.wrapping_sub(1);
                while i != index {
                    self.indexed(MOVE_ASSIGN_SLOTS, i, i.wrapping_sub(1))?;
                    i = i.wrapping_sub(1);
                }
                self.indexed(ASSIGN_FROM_ARGS, index, 0)?;
            }
            ERASE_ONE => {
                let mut i = self.size(READ_INDEX)?;
                while i < self.size(READ_SIZE)?.wrapping_sub(1) {
                    self.indexed(MOVE_ASSIGN_SLOTS, i, i.wrapping_add(1))?;
                    i = i.wrapping_add(1);
                }
                self.leaf(CALL_RESIZE_MINUS_ONE)?;
            }
            ERASE_RANGE => {
                let start = self.size(READ_START)?;
                let end = self.size(READ_END)?;
                let _remove = self.size(READ_REMOVE)?; // Native bound local, final full call stays native.
                let mut i = end;
                while i < self.size(READ_SIZE)? {
                    self.indexed(MOVE_ASSIGN_SLOTS, start.wrapping_add(i.wrapping_sub(end)), i)?;
                    i = i.wrapping_add(1);
                }
                self.leaf(CALL_RESIZE_MINUS_REMOVE)?;
            }
            EQUAL => {
                if self.boolean(SELF)? { return Ok(reply(BOOL, 1)); }
                if self.size(READ_SIZE)? != self.size(OTHER_SIZE)? { return Ok(reply(BOOL, 0)); }
                let mut i = 0usize;
                while i < self.size(READ_SIZE)? {
                    if self.test(ELEMENT_NOT_EQUAL, i)? { return Ok(reply(BOOL, 0)); }
                    i = i.wrapping_add(1);
                }
                return Ok(reply(BOOL, 1));
            }
            NOT_EQUAL => return Ok(reply(BOOL, u64::from(!self.boolean(CALL_EQUAL)?))),
            LESS => {
                let mut i = 0usize;
                while i < self.size(READ_SIZE)? {
                    if i >= self.size(OTHER_SIZE)? { return Ok(reply(BOOL, 0)); }
                    match self.call(COMPARE_PAIR, i, 0, SIZE_VALUE)? {
                        0 => {}
                        1 => return Ok(reply(BOOL, 1)),
                        2 => return Ok(reply(BOOL, 0)),
                        _ => return Err(INVALID),
                    }
                    i = i.wrapping_add(1);
                }
                return Ok(reply(BOOL, u64::from(self.size(READ_SIZE)? < self.size(OTHER_SIZE)?)));
            }
            _ => return Err(INVALID),
        }
        Ok(reply(VOID, 0))
    }
}
/// # Safety
/// `result` must be live, aligned, initialized and readable/writable. The opaque
/// context and synchronous host stay live through reentry. The host retains no
/// envelope pointers, owns native objects, and catches ALL C++ exceptions for
/// rethrow only AFTER Rust returns. Checks cannot establish pointer provenance.
/// Errors leave result untouched; native partial mutations are NOT rolled back.
#[no_mangle]
pub unsafe extern "C" fn sb_static_vector_run(
    mode: u32, stage: u32, context: *mut c_void, host: Option<SbStaticVectorHost>,
    result: *mut SbStaticVectorReply,
) -> u32 {
    if !valid_route(mode, stage) || context.is_null() || result.is_null()
        || (result as usize) % align_of::<SbStaticVectorReply>() != 0
    { return INVALID; }
    let Some(host) = host else { return INVALID; };
    // Copy before callbacks: no typed reference to a callback-modifiable output
    // or native object survives reentry, including reentry sharing this result.
    let initial = result.read();
    if !valid_reply(&initial) { return INVALID; }
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

    #[derive(Clone)]
    struct Step { op: u32, arg0: u64, arg1: u64, out: SbStaticVectorReply, status: u32 }
    fn value(op: u32, tag: u32, n: u64) -> Step {
        Step { op, arg0: 0, arg1: 0, out: reply(tag, n), status: OK }
    }
    fn s(op: u32, n: usize) -> Step { value(op, SIZE_VALUE, n as u64) }
    fn b(op: u32, n: bool) -> Step { value(op, BOOL, u64::from(n)) }
    fn v(op: u32) -> Step { value(op, VOID, 0) }
    fn indexed(op: u32, a: usize, z: usize) -> Step {
        Step { arg0: a as u64, arg1: z as u64, ..v(op) }
    }
    fn probe(op: u32, i: usize, tag: u32, n: u64) -> Step {
        Step { arg0: i as u64, ..value(op, tag, n) }
    }
    fn throwing(op: u32) -> Step { Step { status: EXCEPTION, ..v(op) } }
    #[derive(Clone)]
    struct Case { mode: u32, stage: u32, steps: Vec<Step>, out: SbStaticVectorReply, status: u32 }
    fn case(mode: u32, steps: Vec<Step>, tag: u32, n: u64) -> Case {
        Case { mode, stage: ROOT, steps, out: reply(tag, n), status: OK }
    }
    fn unit(mode: u32, steps: Vec<Step>) -> Case { case(mode, steps, VOID, 0) }
    struct Script { steps: VecDeque<Step>, seen: Vec<u32>, failed: bool }
    unsafe extern "C" fn scripted(
        context: *mut c_void, request: *const SbStaticVectorRequest, output: *mut SbStaticVectorReply,
    ) -> u32 {
        // This script is non-reentrant; separate Cell-only frames exercise reentry.
        let script = &mut *context.cast::<Script>();
        let req = *request;
        script.seen.push(req.op);
        let Some(step) = script.steps.pop_front() else { script.failed = true; return INVALID; };
        if req != (SbStaticVectorRequest { size: 32, version: VERSION, op: step.op,
            reserved: 0, arg0: step.arg0, arg1: step.arg1 })
            || *output != reply(u32::MAX, u64::MAX)
        { script.failed = true; return INVALID; }
        output.write(step.out);
        step.status
    }
    fn execute(c: &Case, status: u32, consumed: usize) {
        let mut script = Script { steps: c.steps.clone().into(), seen: vec![], failed: false };
        let original = reply(BOOL, 1);
        let mut out = original;
        let before = sb_static_vector_count(c.mode, c.stage);
        let actual = unsafe { sb_static_vector_run(c.mode, c.stage,
            (&mut script as *mut Script).cast(), Some(scripted), &mut out) };
        assert_eq!(actual, status, "route {}/{}", c.mode, c.stage);
        assert!(!script.failed, "host violation: {:?}", script.seen);
        assert_eq!(script.seen, c.steps[..consumed].iter().map(|s| s.op).collect::<Vec<_>>());
        assert_eq!(script.steps.len(), c.steps.len() - consumed);
        assert_eq!(out, if status == OK { c.out } else { original });
        assert_eq!(sb_static_vector_count(c.mode, c.stage), before.wrapping_add(1));
    }
    fn cases() -> Vec<Case> {
        let mut cases = vec![unit(DEFAULT_CTOR, vec![])];
        for mode in [CTOR_INSERT, CTOR_RESIZE, PUSH_BACK, INSERT_ONE, INSERT_LIST] {
            cases.push(unit(mode, vec![v(CALL_FORWARD)]));
        }
        for mode in [RANGE_COPY, RANGE_MOVE] {
            cases.push(unit(mode, vec![b(ITERATOR_PRESENT, true), v(CALL_EMPLACE_CURRENT),
                v(ADVANCE_ITERATOR), b(ITERATOR_PRESENT, false)]));
            cases.push(unit(mode, vec![b(ITERATOR_PRESENT, false)]));
        }
        cases.push(unit(COPY_ASSIGN, vec![b(SELF, true)]));
        for mode in [COPY_ASSIGN, MOVE_ASSIGN, LIST_ASSIGN] {
            let mut steps = if mode == COPY_ASSIGN { vec![b(SELF, false)] } else { vec![] };
            steps.extend([v(CALL_RESIZE_OTHER), s(READ_SIZE, 2), indexed(CALL_ASSIGN, 0, 0),
                s(READ_SIZE, 2), indexed(CALL_ASSIGN, 1, 0), s(READ_SIZE, 2)]);
            cases.push(unit(mode, steps));
        }
        cases.extend([
            case(SIZE, vec![s(READ_SIZE, 7)], SIZE_VALUE, 7),
            case(EMPTY, vec![s(READ_SIZE, 0)], BOOL, 1),
            case(EMPTY, vec![s(READ_SIZE, 1)], BOOL, 0),
            unit(RESIZE, vec![s(READ_TARGET, 1), s(READ_CAPACITY, 4), s(READ_SIZE, 3),
                v(CALL_POP), v(CALL_POP), s(READ_SIZE, 1)]),
            unit(RESIZE, vec![s(READ_TARGET, 3), s(READ_CAPACITY, 4), s(READ_SIZE, 1),
                s(READ_SIZE, 1), v(CALL_EMPLACE_VALUE), v(CALL_EMPLACE_VALUE)]),
            unit(AT, vec![s(READ_INDEX, 1), s(READ_SIZE, 2)]),
            unit(INDEX, vec![v(ASSERT_INDEX)]),
            unit(EMPLACE_BACK, vec![s(READ_SIZE, 1), s(READ_CAPACITY, 4),
                v(INCREMENT_SIZE), v(CONSTRUCT_LAST)]),
            unit(POP_BACK, vec![s(READ_SIZE, 1), v(DECREMENT_SIZE), v(DESTROY_LAST)]),
            unit(CLEAR, vec![s(READ_SIZE, 2), v(CALL_POP), s(READ_SIZE, 1), v(CALL_POP), s(READ_SIZE, 0)]),
            unit(CLEAR, vec![s(READ_SIZE, 0)]),
            unit(INSERT_RANGE, vec![s(READ_TO_ADD, 2), s(READ_START, 1), s(READ_END, 3),
                s(READ_SHIFT, 2), v(CALL_RESIZE_ADD), indexed(MOVE_ASSIGN_SLOTS, 4, 2),
                indexed(MOVE_ASSIGN_SLOTS, 3, 1), indexed(ASSIGN_FROM_ITERATOR, 1, 0),
                indexed(ASSIGN_FROM_ITERATOR, 2, 0)]),
            unit(INSERT_RANGE, vec![s(READ_TO_ADD, 0), s(READ_START, 1), s(READ_END, 1),
                s(READ_SHIFT, 2), v(CALL_RESIZE_ADD), indexed(MOVE_ASSIGN_SLOTS, 2, 2),
                indexed(MOVE_ASSIGN_SLOTS, 1, 1)]),
            unit(EMPLACE, vec![s(READ_INDEX, 1), v(CALL_RESIZE_PLUS_ONE), s(READ_SIZE, 4),
                indexed(MOVE_ASSIGN_SLOTS, 3, 2), indexed(MOVE_ASSIGN_SLOTS, 2, 1),
                indexed(ASSIGN_FROM_ARGS, 1, 0)]),
            unit(ERASE_ONE, vec![s(READ_INDEX, 1), s(READ_SIZE, 4), indexed(MOVE_ASSIGN_SLOTS, 1, 2),
                s(READ_SIZE, 4), indexed(MOVE_ASSIGN_SLOTS, 2, 3), s(READ_SIZE, 4), v(CALL_RESIZE_MINUS_ONE)]),
            unit(ERASE_RANGE, vec![s(READ_START, 1), s(READ_END, 3), s(READ_REMOVE, 2),
                s(READ_SIZE, 5), indexed(MOVE_ASSIGN_SLOTS, 1, 3), s(READ_SIZE, 5),
                indexed(MOVE_ASSIGN_SLOTS, 2, 4), s(READ_SIZE, 5), v(CALL_RESIZE_MINUS_REMOVE)]),
            unit(ERASE_RANGE, vec![s(READ_START, 1), s(READ_END, 1), s(READ_REMOVE, 0),
                s(READ_SIZE, 2), indexed(MOVE_ASSIGN_SLOTS, 1, 1), s(READ_SIZE, 2), v(CALL_RESIZE_MINUS_REMOVE)]),
            case(EQUAL, vec![b(SELF, true)], BOOL, 1),
            case(EQUAL, vec![b(SELF, false), s(READ_SIZE, 1), s(OTHER_SIZE, 2)], BOOL, 0),
            case(EQUAL, vec![b(SELF, false), s(READ_SIZE, 2), s(OTHER_SIZE, 2), s(READ_SIZE, 2),
                probe(ELEMENT_NOT_EQUAL, 0, BOOL, 1)], BOOL, 0),
            case(EQUAL, vec![b(SELF, false), s(READ_SIZE, 2), s(OTHER_SIZE, 2), s(READ_SIZE, 2),
                probe(ELEMENT_NOT_EQUAL, 0, BOOL, 0), s(READ_SIZE, 2),
                probe(ELEMENT_NOT_EQUAL, 1, BOOL, 0), s(READ_SIZE, 2)], BOOL, 1),
            case(NOT_EQUAL, vec![b(CALL_EQUAL, true)], BOOL, 0),
            case(NOT_EQUAL, vec![b(CALL_EQUAL, false)], BOOL, 1),
            case(LESS, vec![s(READ_SIZE, 1), s(OTHER_SIZE, 0)], BOOL, 0),
            case(LESS, vec![s(READ_SIZE, 0), s(READ_SIZE, 0), s(OTHER_SIZE, 1)], BOOL, 1),
        ]);
        for order in 0..=2 {
            let mut steps = vec![s(READ_SIZE, 1), s(OTHER_SIZE, 1), probe(COMPARE_PAIR, 0, SIZE_VALUE, order)];
            if order == 0 { steps.extend([s(READ_SIZE, 1), s(READ_SIZE, 1), s(OTHER_SIZE, 1)]); }
            cases.push(case(LESS, steps, BOOL, u64::from(order == 1)));
        }
        for (steps, order) in [(vec![b(PAIR_LESS, true)], 1),
            (vec![b(PAIR_LESS, false), b(PAIR_GREATER, true)], 2),
            (vec![b(PAIR_LESS, false), b(PAIR_GREATER, false)], 0)]
        {
            cases.push(Case { stage: CONTINUE, ..case(LESS, steps, SIZE_VALUE, order) });
        }
        for (mode, steps) in [
            (RESIZE, vec![s(READ_TARGET, 5), s(READ_CAPACITY, 4), throwing(THROW_RESIZE)]),
            (AT, vec![s(READ_INDEX, 2), s(READ_SIZE, 2), throwing(THROW_AT)]),
            (POP_BACK, vec![s(READ_SIZE, 0), throwing(THROW_POP)]),
            (EMPLACE_BACK, vec![s(READ_SIZE, 4), s(READ_CAPACITY, 4), throwing(THROW_EMPLACE_BACK)]),
        ] { cases.push(Case { status: EXCEPTION, ..unit(mode, steps) }); }
        cases
    }
    #[test]
    fn all_roots_continuation_branches_and_forty_leaves() {
        let mut routes = BTreeSet::new();
        let mut leaves = BTreeSet::new();
        for c in cases() {
            routes.insert((c.mode, c.stage));
            leaves.extend(c.steps.iter().map(|s| s.op));
            execute(&c, c.status, c.steps.len());
        }
        assert_eq!(routes, (0..MODES as u32).map(|m| (m, ROOT))
            .chain([(LESS, CONTINUE)]).collect::<BTreeSet<_>>());
        assert_eq!(leaves, (1..=OPS).collect::<BTreeSet<_>>());
    }
    #[test]
    fn failure_at_every_reachable_callback_stops_without_later_calls() {
        for c in cases() {
            for i in 0..c.steps.len() {
                for status in [EXCEPTION, INVALID, PANIC, 4, 255, u32::MAX] {
                    let mut bad = c.clone();
                    bad.steps[i].status = status;
                    bad.steps[i].out = reply(u32::MAX, u64::MAX);
                    execute(&bad, if status <= PANIC { status } else { INVALID }, i + 1);
                }
            }
        }
    }
    #[test]
    fn mandatory_throw_cannot_acknowledge_success() {
        for c in cases().into_iter().filter(|c| c.status == EXCEPTION) {
            let mut bad = c.clone();
            let i = bad.steps.len() - 1;
            bad.steps[i].status = OK;
            for out in [reply(VOID, 0), reply(BOOL, 1), reply(SIZE_VALUE, 0)] {
                bad.steps[i].out = out;
                execute(&bad, INVALID, bad.steps.len());
            }
        }
    }
    #[test]
    fn malformed_host_envelopes_rejected_at_every_position() {
        for c in cases() {
            for i in 0..c.steps.len() {
                for field in 0..5 {
                    let mut bad = c.clone();
                    let step = &mut bad.steps[i];
                    step.status = OK;
                    match field {
                        0 => step.out.size = 23,
                        1 => step.out.version = VERSION + 1,
                        2 => step.out.reserved = 1,
                        3 => step.out.tag = u32::MAX,
                        _ => step.out.tag = if step.out.tag == VOID { BOOL } else { VOID },
                    }
                    execute(&bad, INVALID, i + 1);
                }
                let tag = c.steps[i].out.tag;
                let invalid_value = match tag {
                    VOID => Some(1), BOOL => Some(2),
                    SIZE_VALUE if usize::BITS < 64 => Some((usize::MAX as u64).wrapping_add(1)),
                    _ => None,
                };
                if let Some(n) = invalid_value {
                    let mut bad = c.clone();
                    bad.steps[i].out.value = n;
                    bad.steps[i].status = OK;
                    execute(&bad, INVALID, i + 1);
                }
                if c.steps[i].op == COMPARE_PAIR {
                    let mut bad = c.clone();
                    bad.steps[i].out.value = 3;
                    execute(&bad, INVALID, i + 1);
                }
            }
        }
    }
    unsafe extern "C" fn untouched(
        _context: *mut c_void, _request: *const SbStaticVectorRequest, _output: *mut SbStaticVectorReply,
    ) -> u32 { OK }
    #[test]
    fn host_must_replace_sentinel_and_context_is_not_alignment_checked() {
        let context = std::ptr::NonNull::<u8>::dangling().as_ptr().cast();
        let mut out = reply(VOID, 0);
        assert_eq!(unsafe { sb_static_vector_run(DEFAULT_CTOR, ROOT, context, Some(untouched), &mut out) }, OK);
        assert_eq!(unsafe { sb_static_vector_run(SIZE, ROOT, context, Some(untouched), &mut out) }, INVALID);
    }
    #[test]
    fn invalid_routes_and_entry_envelopes_do_not_call_or_count() {
        let mut script = Script { steps: VecDeque::new(), seen: vec![], failed: false };
        let ctx = (&mut script as *mut Script).cast();
        let before = COUNTS.with(Cell::get);
        for mode in (0..=MODES as u32).chain([u32::MAX]) {
            for stage in [ROOT, CONTINUE, 2, u32::MAX] {
                if valid_route(mode, stage) { continue; }
                let mut out = reply(VOID, 0);
                assert_eq!(unsafe { sb_static_vector_run(mode, stage, ctx, Some(scripted), &mut out) }, INVALID);
                assert_eq!(out, reply(VOID, 0));
            }
        }
        let mut out = reply(VOID, 0);
        assert_eq!(unsafe { sb_static_vector_run(DEFAULT_CTOR, ROOT, std::ptr::null_mut(), Some(scripted), &mut out) }, INVALID);
        assert_eq!(unsafe { sb_static_vector_run(DEFAULT_CTOR, ROOT, ctx, None, &mut out) }, INVALID);
        assert_eq!(unsafe { sb_static_vector_run(DEFAULT_CTOR, ROOT, ctx, Some(scripted), std::ptr::null_mut()) }, INVALID);
        #[repr(align(8))]
        struct Bytes([u8; 32]);
        let mut bytes = Bytes([0xa5; 32]);
        let unaligned = unsafe { bytes.0.as_mut_ptr().add(1).cast() };
        assert_eq!(unsafe { sb_static_vector_run(DEFAULT_CTOR, ROOT, ctx, Some(scripted), unaligned) }, INVALID);
        assert_eq!(bytes.0, [0xa5; 32]);
        let mut invalid = vec![reply(VOID, 1), reply(BOOL, 2), reply(3, 0), reply(u32::MAX, u64::MAX)];
        let mut r = reply(VOID, 0); r.size = 0; invalid.push(r);
        let mut r = reply(VOID, 0); r.version = 0; invalid.push(r);
        let mut r = reply(VOID, 0); r.reserved = 1; invalid.push(r);
        if usize::BITS < 64 { invalid.push(reply(SIZE_VALUE, (usize::MAX as u64).wrapping_add(1))); }
        for mut out in invalid {
            let original = out;
            assert_eq!(unsafe { sb_static_vector_run(DEFAULT_CTOR, ROOT, ctx, Some(scripted), &mut out) }, INVALID);
            assert_eq!(out, original);
        }
        assert_eq!(COUNTS.with(Cell::get), before);
        assert!(script.seen.is_empty() && !script.failed);
    }
    #[test]
    fn valid_initial_reply_tags_are_not_restricted_to_final_result_tag() {
        let ctx = std::ptr::NonNull::<u8>::dangling().as_ptr().cast();
        for mut out in [reply(VOID, 0), reply(BOOL, 0), reply(BOOL, 1), reply(SIZE_VALUE, usize::MAX as u64)] {
            assert_eq!(unsafe { sb_static_vector_run(DEFAULT_CTOR, ROOT, ctx, Some(untouched), &mut out) }, OK);
            assert_eq!(out, reply(VOID, 0));
        }
    }
    #[test]
    fn abi_current_layout_and_nullable_host() {
        assert_eq!(size_of::<SbStaticVectorRequest>(), 32);
        assert_eq!(size_of::<SbStaticVectorReply>(), 24);
        assert_eq!(align_of::<SbStaticVectorRequest>(), 8);
        assert_eq!(align_of::<SbStaticVectorReply>(), 8);
        assert_eq!([offset_of!(SbStaticVectorRequest, size), offset_of!(SbStaticVectorRequest, version),
            offset_of!(SbStaticVectorRequest, op), offset_of!(SbStaticVectorRequest, reserved),
            offset_of!(SbStaticVectorRequest, arg0), offset_of!(SbStaticVectorRequest, arg1)], [0, 4, 8, 12, 16, 24]);
        assert_eq!([offset_of!(SbStaticVectorReply, size), offset_of!(SbStaticVectorReply, version),
            offset_of!(SbStaticVectorReply, tag), offset_of!(SbStaticVectorReply, reserved),
            offset_of!(SbStaticVectorReply, value)], [0, 4, 8, 12, 16]);
        assert_eq!(size_of::<Option<SbStaticVectorHost>>(), size_of::<*mut c_void>());
    }
    #[test]
    fn panic_containment_uses_rust_helper_not_extern_host_unwind() {
        assert_eq!(catch_policy(|| -> Result<SbStaticVectorReply, u32> { panic!("policy panic") }), Err(PANIC));
        assert_eq!(catch_policy(|| Ok(reply(VOID, 0))), Ok(reply(VOID, 0)));
        assert_eq!(catch_policy(|| Err(EXCEPTION)), Err(EXCEPTION));
    }
    #[test]
    fn counters_wrap_are_thread_local_and_out_of_shape_queries_are_zero() {
        let saved = COUNTS.with(Cell::get);
        COUNTS.with(|counts| { let mut a = counts.get(); a[0][0] = u64::MAX; counts.set(a); });
        execute(&unit(DEFAULT_CTOR, vec![]), OK, 0);
        assert_eq!(sb_static_vector_count(DEFAULT_CTOR, ROOT), 0);
        std::thread::spawn(|| {
            assert_eq!(COUNTS.with(Cell::get), [[0; STAGES]; MODES]);
            execute(&unit(DEFAULT_CTOR, vec![]), OK, 0);
            assert_eq!(sb_static_vector_count(DEFAULT_CTOR, ROOT), 1);
        }).join().unwrap();
        assert_eq!(sb_static_vector_count(DEFAULT_CTOR, ROOT), 0);
        for (mode, stage) in [(26, 0), (0, 2), (u32::MAX, 0), (0, u32::MAX)] {
            assert_eq!(sb_static_vector_count(mode, stage), 0);
        }
        COUNTS.with(|counts| counts.set(saved));
    }

    // Shared Cell fields only: no exclusive frame/slot/envelope reference lives
    // across nested entry. This models scalar effects, NOT C++ lifetime proof.
    struct Reentrant {
        scenario: u32,
        size: Cell<usize>,
        slots: Cell<[u64; 8]>,
        entered: Cell<bool>,
        failed: Cell<bool>,
        constructing: Cell<u64>,
        log: Cell<[(u32, u64, u64); 128]>,
        len: Cell<usize>,
    }
    impl Reentrant {
        fn new(scenario: u32, size: usize) -> Self {
            Self { scenario, size: Cell::new(size), slots: Cell::new([1, 2, 3, 0, 0, 0, 0, 0]),
                entered: Cell::new(false), failed: Cell::new(false), constructing: Cell::new(0),
                log: Cell::new([(0, 0, 0); 128]), len: Cell::new(0) }
        }
        fn context(&self) -> *mut c_void { (self as *const Self).cast_mut().cast() }
    }
    unsafe fn nested(frame: &Reentrant, mode: u32, stage: u32) -> Result<SbStaticVectorReply, u32> {
        let mut out = reply(VOID, 0);
        let status = sb_static_vector_run(mode, stage, frame.context(), Some(reentrant), &mut out);
        if status == OK { Ok(out) } else { Err(status) }
    }
    unsafe extern "C" fn reentrant(
        context: *mut c_void, request: *const SbStaticVectorRequest, output: *mut SbStaticVectorReply,
    ) -> u32 {
        let frame = &*context.cast::<Reentrant>();
        let req = *request;
        let mut log = frame.log.get();
        let len = frame.len.get();
        if len >= log.len() || req.size != 32 || req.version != VERSION || req.reserved != 0
            || req.arg1 != 0 || (req.op != CALL_ASSIGN && req.arg0 != 0)
            || *output != reply(u32::MAX, u64::MAX)
        { frame.failed.set(true); return INVALID; }
        log[len] = (req.op, req.arg0, frame.size.get() as u64);
        frame.log.set(log);
        frame.len.set(len + 1);
        let result: Result<SbStaticVectorReply, u32> = (|| {
            Ok(match req.op {
                SELF => reply(BOOL, 0),
                READ_SIZE => reply(SIZE_VALUE, frame.size.get() as u64),
                READ_CAPACITY => reply(SIZE_VALUE, 8),
                READ_TARGET => reply(SIZE_VALUE, if frame.scenario == 1 { 2 } else { 1 }),
                CALL_RESIZE_OTHER => reply(VOID, 0),
                CALL_ASSIGN => {
                    if !frame.entered.replace(true) {
                        frame.constructing.set(9);
                        nested(frame, EMPLACE_BACK, ROOT)?;
                    }
                    let i = req.arg0 as usize;
                    if i >= 3 { frame.failed.set(true); return Err(INVALID); }
                    let mut slots = frame.slots.get();
                    slots[i] = [1, 2, 8][i];
                    frame.slots.set(slots);
                    reply(VOID, 0)
                }
                CALL_EMPLACE_VALUE => {
                    frame.constructing.set(0);
                    nested(frame, EMPLACE_BACK, ROOT)?
                }
                INCREMENT_SIZE => {
                    frame.size.set(frame.size.get().wrapping_add(1));
                    reply(VOID, 0)
                }
                CONSTRUCT_LAST => {
                    let i = frame.size.get().wrapping_sub(1);
                    if i >= 8 { frame.failed.set(true); return Err(INVALID); }
                    let mut slots = frame.slots.get();
                    slots[i] = frame.constructing.get();
                    frame.slots.set(slots);
                    if frame.scenario == 1 && !frame.entered.replace(true) {
                        frame.constructing.set(9);
                        nested(frame, EMPLACE_BACK, ROOT)?;
                    }
                    reply(VOID, 0)
                }
                CALL_POP => nested(frame, POP_BACK, ROOT)?,
                DECREMENT_SIZE => {
                    frame.size.set(frame.size.get().wrapping_sub(1));
                    reply(VOID, 0)
                }
                DESTROY_LAST => {
                    if matches!(frame.scenario, 2 | 3) && !frame.entered.replace(true) {
                        nested(frame, POP_BACK, ROOT)?;
                    }
                    reply(VOID, 0)
                }
                OTHER_SIZE => reply(SIZE_VALUE, 1),
                COMPARE_PAIR => nested(frame, LESS, CONTINUE)?,
                PAIR_LESS => reply(BOOL, 0),
                PAIR_GREATER => reply(BOOL, 1),
                _ => { frame.failed.set(true); return Err(INVALID); }
            })
        })();
        match result {
            Ok(value) => { output.write(value); OK }
            Err(status) => status,
        }
    }
    #[test]
    fn mutation_reentry_preserves_dynamic_assignment_clear_and_local_resize_counters() {
        for (scenario, mode, initial, expected, nested_mode, nested_count) in [
            (0, COPY_ASSIGN, 2, vec![1, 2, 8], EMPLACE_BACK, 1),
            (1, RESIZE, 0, vec![0, 9, 0], EMPLACE_BACK, 3),
            (2, RESIZE, 3, vec![0], POP_BACK, 3),
            (3, CLEAR, 3, vec![], POP_BACK, 3),
        ] {
            let frame = Reentrant::new(scenario, initial);
            let before = COUNTS.with(Cell::get);
            assert_eq!(unsafe { nested(&frame, mode, ROOT) }, Ok(reply(VOID, 0)));
            assert!(!frame.failed.get());
            assert_eq!(frame.size.get(), expected.len());
            assert_eq!(&frame.slots.get()[..frame.size.get()], expected.as_slice());
            let after = COUNTS.with(Cell::get);
            for m in 0..MODES {
                for stage in 0..STAGES {
                    let n = if stage != ROOT as usize { 0 }
                        else if m == mode as usize { 1 }
                        else if m == nested_mode as usize { nested_count }
                        else if scenario == 2 && m == EMPLACE_BACK as usize { 1 } else { 0 };
                    assert_eq!(after[m][stage], before[m][stage].wrapping_add(n));
                }
            }
            if scenario == 0 {
                let assigns = frame.log.get()[..frame.len.get()].iter()
                    .filter(|e| e.0 == CALL_ASSIGN).map(|e| e.1).collect::<Vec<_>>();
                assert_eq!(assigns, [0, 1, 2]);
            }
        }
    }
    #[test]
    fn pair_continuation_reentry_keeps_nested_count_and_short_circuit_order() {
        let frame = Reentrant::new(4, 1);
        let before = COUNTS.with(Cell::get);
        assert_eq!(unsafe { nested(&frame, LESS, ROOT) }, Ok(reply(BOOL, 0)));
        assert!(!frame.failed.get());
        let log = frame.log.get();
        assert_eq!(log[..frame.len.get()].iter().map(|e| e.0).collect::<Vec<_>>(),
            [READ_SIZE, OTHER_SIZE, COMPARE_PAIR, PAIR_LESS, PAIR_GREATER]);
        assert_eq!(sb_static_vector_count(LESS, ROOT), before[LESS as usize][ROOT as usize].wrapping_add(1));
        assert_eq!(sb_static_vector_count(LESS, CONTINUE), before[LESS as usize][CONTINUE as usize].wrapping_add(1));
    }
    #[test]
    fn native_width_wrapping_is_scalar_policy_not_a_claim_of_valid_cpp_domains() {
        // Deliberately scalar-only mock inputs: no native invalid iterator or
        // impossible storage operation is executed to exercise these wraps.
        let max = usize::MAX;
        let cases = [
            unit(EMPLACE_BACK, vec![s(READ_SIZE, max), s(READ_CAPACITY, 0),
                v(INCREMENT_SIZE), v(CONSTRUCT_LAST)]),
            unit(INSERT_RANGE, vec![s(READ_TO_ADD, 0), s(READ_START, max), s(READ_END, max),
                s(READ_SHIFT, 2), v(CALL_RESIZE_ADD), indexed(MOVE_ASSIGN_SLOTS, 0, 0),
                indexed(MOVE_ASSIGN_SLOTS, max, max)]),
            unit(INSERT_RANGE, vec![s(READ_TO_ADD, 2), s(READ_START, max), s(READ_END, 1),
                s(READ_SHIFT, 0), v(CALL_RESIZE_ADD), indexed(ASSIGN_FROM_ITERATOR, max, 0),
                indexed(ASSIGN_FROM_ITERATOR, 0, 0)]),
            unit(EMPLACE, vec![s(READ_INDEX, max), v(CALL_RESIZE_PLUS_ONE), s(READ_SIZE, 0),
                indexed(ASSIGN_FROM_ARGS, max, 0)]),
            unit(ERASE_ONE, vec![s(READ_INDEX, max - 1), s(READ_SIZE, 0),
                indexed(MOVE_ASSIGN_SLOTS, max - 1, max), s(READ_SIZE, 0), v(CALL_RESIZE_MINUS_ONE)]),
            unit(ERASE_RANGE, vec![s(READ_START, max), s(READ_END, 1), s(READ_REMOVE, 0),
                s(READ_SIZE, 3), indexed(MOVE_ASSIGN_SLOTS, max, 1), s(READ_SIZE, 3),
                indexed(MOVE_ASSIGN_SLOTS, 0, 2), s(READ_SIZE, 3), v(CALL_RESIZE_MINUS_REMOVE)]),
        ];
        for c in cases { execute(&c, OK, c.steps.len()); }
    }
    #[test]
    fn changing_size_scripts_recheck_erase_and_comparison_conditions() {
        let cases = [
            unit(ERASE_ONE, vec![s(READ_INDEX, 0), s(READ_SIZE, 3), indexed(MOVE_ASSIGN_SLOTS, 0, 1),
                s(READ_SIZE, 4), indexed(MOVE_ASSIGN_SLOTS, 1, 2), s(READ_SIZE, 3), v(CALL_RESIZE_MINUS_ONE)]),
            unit(ERASE_RANGE, vec![s(READ_START, 0), s(READ_END, 1), s(READ_REMOVE, 1),
                s(READ_SIZE, 2), indexed(MOVE_ASSIGN_SLOTS, 0, 1), s(READ_SIZE, 4),
                indexed(MOVE_ASSIGN_SLOTS, 1, 2), s(READ_SIZE, 3), v(CALL_RESIZE_MINUS_REMOVE)]),
            case(EQUAL, vec![b(SELF, false), s(READ_SIZE, 1), s(OTHER_SIZE, 1),
                s(READ_SIZE, 1), probe(ELEMENT_NOT_EQUAL, 0, BOOL, 0), s(READ_SIZE, 2),
                probe(ELEMENT_NOT_EQUAL, 1, BOOL, 0), s(READ_SIZE, 2)], BOOL, 1),
            case(LESS, vec![s(READ_SIZE, 1), s(OTHER_SIZE, 2), probe(COMPARE_PAIR, 0, SIZE_VALUE, 0),
                s(READ_SIZE, 2), s(OTHER_SIZE, 2), probe(COMPARE_PAIR, 1, SIZE_VALUE, 1)], BOOL, 1),
        ];
        for c in cases { execute(&c, OK, c.steps.len()); }
    }
    #[test]
    fn no_fixed_progress_cap_on_captured_iterator_loop() {
        let mut steps = Vec::new();
        for _ in 0..4097 {
            steps.extend([b(ITERATOR_PRESENT, true), v(CALL_EMPLACE_CURRENT), v(ADVANCE_ITERATOR)]);
        }
        steps.push(b(ITERATOR_PRESENT, false));
        let c = unit(RANGE_COPY, steps);
        execute(&c, OK, c.steps.len());
    }
}
