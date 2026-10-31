//! Map control policy only. Native lexical scopes own iterators, changes and streams.
use crate::net_group::{SbNetGroupReply as SbNetMapReply, Host};
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST_ERROR: u32 = 2;
const PANIC: u32 = 3;
const INIT: u32 = 0;
const FLUSH: u32 = 1;
const TICK: u32 = 2;
const STORE: u32 = 3;
const LOAD: u32 = 4;
const LOAD_ITEM: u32 = 5;
const SHOULD: u32 = 6;
const WRITE: u32 = 7;
const READ: u32 = 8;
const READ_ITEM: u32 = 9;
const HISTORY: u32 = 10;
const PENDING: u32 = 11;
const APPLY: u32 = 12;
const STORE_PENDING: u32 = 13;
const BASE_RECORD: u32 = 14;
const BASE_STORE: u32 = 15;
const DECREMENT_RANGE: u32 = 16;
const SHOULD_SCAN: u32 = 17;
const WRITE_SCAN: u32 = 18;
const INSERT: u32 = 19;
const ADD: u32 = 20;
const SET: u32 = 21;
const REMOVE: u32 = 22;
const CLEAR: u32 = 23;
const RESET: u32 = 24;
const RESET_REMOVALS: u32 = 25;
const RESET_SETS: u32 = 26;
const WRITE_CHANGE: u32 = 27;
const READ_TYPE: u32 = 28;
const RESET_REMOVE_ITEM: u32 = 29;
const RESET_SET_ITEM: u32 = 30;
const COUNT: usize = 31;
const RECORD_RANGE_OP: u32 = 0;
const MORE: u32 = 1;
const ADVANCE: u32 = 2;
const STORE_RANGE_OP: u32 = 3;
const FLUSH_PENDING: u32 = 4;
const RECORD_CLEAR: u32 = 5;
const RECORD_CURRENT_SET: u32 = 6;
const DECREMENT_RANGE_OP: u32 = 7;
const FRONT_READY: u32 = 8;
const APPLY_FRONT: u32 = 9;
const APPLY_PENDING_MOVE: u32 = 10;
const WRITE_SIZE: u32 = 11;
const WRITE_CURRENT_SET: u32 = 12;
const STORE_PENDING_OP: u32 = 13;
const WRITE_PENDING_CHANGE: u32 = 14;
const CLEAR_HISTORY: u32 = 15;
const CAPTURE_VERSION: u32 = 16;
const CLEAR_PENDING: u32 = 17;
const CLEAR_BASE: u32 = 18;
const READ_COUNT: u32 = 19;
const LOAD_ITEM_OP: u32 = 20;
const RECORD_ITEM: u32 = 21;
const APPLY_ITEM_MOVE: u32 = 22;
const MARK_UPDATED: u32 = 23;
const HISTORY_FLOOR: u32 = 24;
const SHOULD_SCAN_OP: u32 = 25;
const ENTRY_VERSION: u32 = 26;
const WRITE_FULL_CODE: u32 = 27;
const STORE_FULL: u32 = 28;
const WRITE_CHANGE_CODE: u32 = 29;
const WRITE_HISTORY_CHANGE: u32 = 30;
const WRITE_TERMINATOR: u32 = 31;
const READ_CODE: u32 = 32;
const LOAD_FULL: u32 = 33;
const READ_ITEM_OP: u32 = 34;
const SHOULD_QUEUE: u32 = 35;
const QUEUE_ITEM_MOVE: u32 = 36;
const THROW_CODE: u32 = 37;
const APPEND_HISTORY: u32 = 38;
const SET_HISTORY_FLOOR: u32 = 39;
const HISTORY_EMPTY: u32 = 40;
const HISTORY_BOUNDS: u32 = 41;
const POP_HISTORY: u32 = 42;
const PENDING_EARLIER: u32 = 43;
const APPEND_PENDING: u32 = 44;
const CHANGE_KIND: u32 = 45;
const APPLY_SET: u32 = 46;
const APPLY_REMOVE: u32 = 47;
const DECREMENT_CURRENT: u32 = 48;
const WRITE_SCAN_OP: u32 = 49;
const INSERTED: u32 = 50;
const RECORD_INSERTED: u32 = 51;
const ADD_FAILED: u32 = 52;
const THROW_DUPLICATE: u32 = 53;
const FOUND: u32 = 54;
const VALUE_DIFFERS: u32 = 55;
const RECORD_EXISTING_SET: u32 = 56;
const ASSIGN_EXISTING: u32 = 57;
const RECORD_NEW_SET: u32 = 58;
const INSERT_NEW: u32 = 59;
const ERASE_FOUND: u32 = 60;
const RECORD_REMOVAL: u32 = 61;
const NONEMPTY: u32 = 62;
const RESET_REMOVALS_OP: u32 = 63;
const RESET_SETS_OP: u32 = 64;
const RESET_ASSIGN: u32 = 65;
const RESET_MISSING: u32 = 66;
const RESET_CHANGED: u32 = 67;
const RECORD_CURRENT_REMOVE: u32 = 68;
const WRITE_TAG: u32 = 69;
const WRITE_KEY: u32 = 70;
const WRITE_VALUE: u32 = 71;
const SELECT_KIND: u32 = 72;
const THROW_TYPE: u32 = 73;
const RESET_REMOVE_ITEM_OP: u32 = 74;
const RESET_SET_ITEM_OP: u32 = 75;
const OP_COUNT: usize = 76;

static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static LEAVES: [AtomicU64; OP_COUNT] = [const { AtomicU64::new(0) }; OP_COUNT];
thread_local! { static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) }; }

fn version_argument(mode: u32) -> bool {
    matches!(mode, SHOULD | WRITE | SHOULD_SCAN | WRITE_SCAN)
}
fn valid_argument(mode: u32, argument: u64) -> bool {
    version_argument(mode) || if mode == READ_TYPE { argument <= u8::MAX as u64 }
        else { argument == 0 }
}
fn valid_reply(op: u32, r: SbNetMapReply) -> bool {
    if op == HISTORY_BOUNDS { return true; }
    r.b == 0 && match op {
        MORE | FRONT_READY | SHOULD_SCAN_OP | SHOULD_QUEUE | HISTORY_EMPTY |
        PENDING_EARLIER | WRITE_SCAN_OP | INSERTED | ADD_FAILED | FOUND |
        VALUE_DIFFERS | NONEMPTY | RESET_MISSING | RESET_CHANGED => r.a <= 1,
        READ_COUNT | HISTORY_FLOOR | ENTRY_VERSION | READ_CODE => true,
        CHANGE_KIND => r.a <= 2,
        _ => r.a == 0,
    }
}
unsafe fn invoke(ctx: *mut c_void, host: Host, op: u32, argument: u64) -> Result<SbNetMapReply, u32> {
    let mut reply = SbNetMapReply::default();
    LEAVES[op as usize].fetch_add(1, Ordering::Relaxed);
    match host(ctx, op, argument, &mut reply) {
        OK if valid_reply(op, reply) => Ok(reply),
        HOST_ERROR => Err(HOST_ERROR),
        _ => Err(INVALID),
    }
}
unsafe fn run(mode: u32, ctx: *mut c_void, host: Host, argument: u64) -> Result<u32, u32> {
    let call = |op| invoke(ctx, host, op, 0);
    match mode {
        INIT => {
            call(FLUSH_PENDING)?;
            call(RECORD_CLEAR)?;
            call(RECORD_RANGE_OP)?;
        }
        FLUSH | BASE_RECORD | BASE_STORE | STORE_PENDING | DECREMENT_RANGE => {
            // C++ creates and caches each native range BEFORE entering this root.
            // No synthetic enter/leave callbacks or cleanup on a failed prefix.
            let body = match mode {
                FLUSH => APPLY_PENDING_MOVE,
                BASE_RECORD => RECORD_CURRENT_SET,
                BASE_STORE => WRITE_CURRENT_SET,
                STORE_PENDING => WRITE_PENDING_CHANGE,
                _ => DECREMENT_CURRENT,
            };
            while call(MORE)?.a != 0 {
                call(body)?;
                call(ADVANCE)?;
            }
        }
        TICK => {
            call(DECREMENT_RANGE_OP)?;
            while call(FRONT_READY)?.a != 0 { call(APPLY_FRONT)?; }
        }
        STORE => {
            call(WRITE_SIZE)?;
            call(STORE_RANGE_OP)?;
            call(STORE_PENDING_OP)?;
        }
        LOAD => {
            call(CLEAR_HISTORY)?;
            call(CAPTURE_VERSION)?;
            call(CLEAR_PENDING)?;
            call(CLEAR_BASE)?;
            call(RECORD_CLEAR)?;
            let count = call(READ_COUNT)?.a;
            for _ in 0..count { call(LOAD_ITEM_OP)?; }
            call(MARK_UPDATED)?;
        }
        LOAD_ITEM => { call(RECORD_ITEM)?; call(APPLY_ITEM_MOVE)?; }
        SHOULD => {
            if argument < call(HISTORY_FLOOR)?.a { return Ok(1); }
            return Ok(invoke(ctx, host, SHOULD_SCAN_OP, argument)?.a as u32);
        }
        SHOULD_SCAN | WRITE_SCAN => {
            let mut written = 0;
            while call(MORE)?.a != 0 {
                if call(ENTRY_VERSION)?.a >= argument {
                    if mode == SHOULD_SCAN { return Ok(1); }
                    written = 1;
                    call(WRITE_CHANGE_CODE)?;
                    call(WRITE_HISTORY_CHANGE)?;
                }
                call(ADVANCE)?;
            }
            return Ok(written);
        }
        WRITE => {
            let written = if argument < call(HISTORY_FLOOR)?.a {
                call(WRITE_FULL_CODE)?;
                call(STORE_FULL)?;
                1
            } else { invoke(ctx, host, WRITE_SCAN_OP, argument)?.a as u32 };
            // Native scan scope is already destroyed when WRITE_SCAN_OP returns.
            if written != 0 { call(WRITE_TERMINATOR)?; }
            return Ok(written);
        }
        READ => loop {
            match call(READ_CODE)?.a {
                0 => break,
                1 => { call(LOAD_FULL)?; }
                2 => { call(READ_ITEM_OP)?; }
                _ => {
                    call(THROW_CODE)?;
                    // Native THROW_CODE must throw. Never continue if a malformed
                    // host claims successful completion of the throwing leaf.
                    return Err(INVALID);
                }
            }
        },
        READ_ITEM => {
            call(RECORD_ITEM)?;
            if call(SHOULD_QUEUE)?.a != 0 { call(QUEUE_ITEM_MOVE)?; }
            else { call(APPLY_ITEM_MOVE)?; }
        }
        HISTORY => {
            // Version capture/assert and signed floor arithmetic remain native.
            call(APPEND_HISTORY)?;
            call(SET_HISTORY_FLOOR)?;
            while call(HISTORY_EMPTY)?.a == 0 {
                let bounds = call(HISTORY_BOUNDS)?;
                if bounds.a >= bounds.b { break; }
                call(POP_HISTORY)?;
            }
        }
        PENDING => {
            if call(PENDING_EARLIER)?.a != 0 { call(FLUSH_PENDING)?; }
            // Do not recheck a queue populated reentrantly during the flush.
            call(APPEND_PENDING)?;
        }
        APPLY => {
            let kind = call(CHANGE_KIND)?.a;
            call(match kind { 0 => APPLY_SET, 1 => APPLY_REMOVE, _ => CLEAR_BASE })?;
            call(MARK_UPDATED)?;
        }
        INSERT => {
            // Native named res and original v parameter outlive this root.
            if call(INSERTED)?.a != 0 {
                call(RECORD_INSERTED)?;
                call(MARK_UPDATED)?;
            }
        }
        ADD => {
            if call(ADD_FAILED)?.a != 0 {
                call(THROW_DUPLICATE)?;
                return Err(INVALID);
            }
        }
        SET => {
            if call(FOUND)?.a != 0 {
                if call(VALUE_DIFFERS)?.a != 0 {
                    call(RECORD_EXISTING_SET)?;
                    call(ASSIGN_EXISTING)?;
                    call(MARK_UPDATED)?;
                }
            } else {
                call(RECORD_NEW_SET)?;
                call(INSERT_NEW)?;
                call(MARK_UPDATED)?;
            }
        }
        REMOVE => {
            if call(FOUND)?.a == 0 { return Ok(0); }
            // Erasure precedes history copying, even when history later fails.
            call(ERASE_FOUND)?;
            call(RECORD_REMOVAL)?;
            call(MARK_UPDATED)?;
            return Ok(1);
        }
        CLEAR => {
            if call(NONEMPTY)?.a != 0 {
                call(RECORD_CLEAR)?;
                call(MARK_UPDATED)?;
                call(CLEAR_BASE)?;
            }
        }
        RESET => {
            call(RESET_REMOVALS_OP)?;
            call(RESET_SETS_OP)?;
            call(RESET_ASSIGN)?;
        }
        RESET_REMOVALS | RESET_SETS => {
            while call(MORE)?.a != 0 {
                call(if mode == RESET_REMOVALS { RESET_REMOVE_ITEM_OP } else { RESET_SET_ITEM_OP })?;
                call(ADVANCE)?;
            }
        }
        RESET_REMOVE_ITEM | RESET_SET_ITEM => {
            // The whole native predicate includes its short-circuit/proxy lifetime.
            let (predicate, record) = if mode == RESET_REMOVE_ITEM {
                (RESET_MISSING, RECORD_CURRENT_REMOVE)
            } else { (RESET_CHANGED, RECORD_CURRENT_SET) };
            if call(predicate)?.a != 0 {
                call(record)?;
                call(MARK_UPDATED)?;
            }
        }
        WRITE_CHANGE => {
            let kind = call(CHANGE_KIND)?.a;
            invoke(ctx, host, WRITE_TAG, kind)?;
            if kind < 2 { call(WRITE_KEY)?; }
            if kind == 0 { call(WRITE_VALUE)?; }
        }
        READ_TYPE => {
            // Native t was read as u8 BEFORE entry. Typed locals/read/return
            // scopes stay in C++; no ElementChange or extra move lives here.
            if argument < 3 { invoke(ctx, host, SELECT_KIND, argument)?; }
            else {
                call(THROW_TYPE)?;
                return Err(INVALID);
            }
        }
        _ => return Err(INVALID),
    }
    Ok(0)
}
fn barrier(f: impl FnOnce() -> u32) -> u32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(PANIC)
}
/// # Safety
/// See StarRustNetMap.h. Host callbacks must not unwind; native captures and
/// aligned writable output remain live through synchronous callbacks/reentry.
#[no_mangle]
pub unsafe extern "C" fn sb_net_map_run(
    mode: u32, ctx: *mut c_void, host: Option<Host>, argument: u64, out_result: *mut u32,
) -> u32 {
    if mode >= COUNT as u32 || ctx.is_null() || host.is_none() || out_result.is_null()
        || (out_result as usize) % std::mem::align_of::<u32>() != 0
        || !valid_argument(mode, argument) {
        return INVALID;
    }
    barrier(|| {
        TOTALS[mode as usize].fetch_add(1, Ordering::Relaxed);
        COUNTS.with(|cell| {
            let mut counts = cell.get();
            counts[mode as usize] = counts[mode as usize].wrapping_add(1);
            cell.set(counts);
        });
        match run(mode, ctx, host.unwrap(), argument) {
            Ok(result) => { out_result.write(result); OK }
            Err(status) => status,
        }
    })
}
/// Wrapping relaxed diagnostics: accepted roots and attempted leaves, not commits.
#[no_mangle]
pub extern "C" fn sb_net_map_count(kind: u32, index: u32) -> u64 {
    catch_unwind(|| match (kind, index as usize) {
        (0, i) if i < COUNT => COUNTS.with(|cell| cell.get()[i]),
        (1, i) if i < COUNT => TOTALS[i].load(Ordering::Relaxed),
        (2, i) if i < OP_COUNT => LEAVES[i].load(Ordering::Relaxed),
        _ => 0,
    }).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::VecDeque;

    #[derive(Clone)]
    struct Step { op: u32, arg: u64, a: u64, b: u64 }
    fn s(op: u32) -> Step { r(op, 0) }
    fn r(op: u32, a: u64) -> Step { Step { op, arg: 0, a, b: 0 } }
    fn v(op: u32, arg: u64, a: u64) -> Step { Step { op, arg, a, b: 0 } }
    fn bounds(a: u64, b: u64) -> Step { Step { op: HISTORY_BOUNDS, arg: 0, a, b } }
    struct Mock {
        steps: VecDeque<Step>, events: Vec<(u32, u64)>, mismatch: bool,
        fault: Option<(usize, u32, u64, u64)>, nested: Option<(u32, u32, u64, Vec<Step>)>,
        nested_result: Option<(u32, u32)>,
    }
    impl Mock {
        fn new(steps: Vec<Step>) -> Self {
            Self { steps: steps.into(), events: vec![], mismatch: false, fault: None,
                nested: None, nested_result: None }
        }
        fn call(&mut self, mode: u32, arg: u64, output: &mut u32) -> u32 {
            unsafe { sb_net_map_run(mode, self as *mut _ as _, Some(host), arg, output) }
        }
    }
    // Scripts describe leaf protocol only, not C++ iterator/payload ownership.
    // No assertions or panics cross this extern-C callback.
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, arg: u64, out: *mut SbNetMapReply) -> u32 {
        let m = &mut *(ctx as *mut Mock);
        if (*out).a != 0 || (*out).b != 0 { m.mismatch = true; return HOST_ERROR; }
        let index = m.events.len();
        m.events.push((op, arg));
        let Some(step) = m.steps.pop_front() else { m.mismatch = true; return HOST_ERROR; };
        if (step.op, step.arg) != (op, arg) { m.mismatch = true; return HOST_ERROR; }
        if let Some((at, status, a, b)) = m.fault {
            if at == index { out.write(SbNetMapReply { a, b }); return status; }
        }
        if m.nested.as_ref().is_some_and(|n| n.0 == op) {
            let (_, mode, argument, steps) = m.nested.take().unwrap();
            let mut child = Mock::new(steps);
            let mut result = 99;
            let status = child.call(mode, argument, &mut result);
            m.nested_result = Some((status, result));
            if child.mismatch || !child.steps.is_empty() || status != OK { return HOST_ERROR; }
        }
        out.write(SbNetMapReply { a: step.a, b: step.b });
        OK
    }
    fn schedule(mode: u32, argument: u64, steps: Vec<Step>, expected: u32) {
        let mut m = Mock::new(steps.clone());
        let mut out = 99;
        assert_eq!(m.call(mode, argument, &mut out), OK);
        assert_eq!(out, expected);
        assert!(!m.mismatch);
        assert!(m.steps.is_empty());
        assert_eq!(m.events, steps.iter().map(|s| (s.op, s.arg)).collect::<Vec<_>>());
        // Every failed leaf preserves output and stops at exactly that prefix.
        for at in 0..steps.len() {
            let mut failed = Mock::new(steps.clone());
            failed.fault = Some((at, HOST_ERROR, u64::MAX, u64::MAX));
            let mut output = 77;
            assert_eq!(failed.call(mode, argument, &mut output), HOST_ERROR);
            assert_eq!(output, 77);
            assert!(!failed.mismatch);
            assert_eq!(failed.events, m.events[..=at]);
        }
    }
    #[test]
    fn lifecycle_and_native_scoped_ranges() {
        schedule(INIT, 0, vec![s(FLUSH_PENDING), s(RECORD_CLEAR), s(RECORD_RANGE_OP)], 0);
        for (mode, body) in [(FLUSH, APPLY_PENDING_MOVE), (BASE_RECORD, RECORD_CURRENT_SET),
            (BASE_STORE, WRITE_CURRENT_SET), (STORE_PENDING, WRITE_PENDING_CHANGE),
            (DECREMENT_RANGE, DECREMENT_CURRENT)] {
            schedule(mode, 0, vec![r(MORE,1), s(body), s(ADVANCE), r(MORE,1),
                s(body), s(ADVANCE), r(MORE,0)], 0);
            schedule(mode, 0, vec![r(MORE,0)], 0);
        }
        schedule(TICK, 0, vec![s(DECREMENT_RANGE_OP), r(FRONT_READY,1), s(APPLY_FRONT),
            r(FRONT_READY,1), s(APPLY_FRONT), r(FRONT_READY,0)], 0);
        schedule(STORE, 0, vec![s(WRITE_SIZE), s(STORE_RANGE_OP), s(STORE_PENDING_OP)], 0);
        for count in [0,2] {
            let mut steps = vec![s(CLEAR_HISTORY), s(CAPTURE_VERSION), s(CLEAR_PENDING),
                s(CLEAR_BASE), s(RECORD_CLEAR), r(READ_COUNT,count)];
            for _ in 0..count { steps.push(s(LOAD_ITEM_OP)); }
            steps.push(s(MARK_UPDATED));
            schedule(LOAD, 0, steps, 0);
        }
        schedule(LOAD_ITEM, 0, vec![s(RECORD_ITEM), s(APPLY_ITEM_MOVE)], 0);
    }
    #[test]
    fn scans_and_full_fallback() {
        for version in [0, 7, u64::MAX] {
            schedule(SHOULD, version, vec![r(HISTORY_FLOOR,version),
                v(SHOULD_SCAN_OP,version,0)], 0);
            schedule(SHOULD, version, vec![r(HISTORY_FLOOR,version),
                v(SHOULD_SCAN_OP,version,1)], 1);
            for written in [0,1] {
                let mut steps = vec![r(HISTORY_FLOOR,0),v(WRITE_SCAN_OP,version,written)];
                if written != 0 { steps.push(s(WRITE_TERMINATOR)); }
                schedule(WRITE, version, steps, written as u32);
            }
        }
        schedule(SHOULD, 4, vec![r(HISTORY_FLOOR,5)], 1);
        schedule(WRITE, 4, vec![r(HISTORY_FLOOR,5), s(WRITE_FULL_CODE),
            s(STORE_FULL), s(WRITE_TERMINATOR)], 1);
        schedule(SHOULD_SCAN, 7, vec![r(MORE,1), r(ENTRY_VERSION,6), s(ADVANCE),
            r(MORE,1), r(ENTRY_VERSION,7)], 1); // no advance after early return
        schedule(SHOULD_SCAN, u64::MAX, vec![r(MORE,1), r(ENTRY_VERSION,0),
            s(ADVANCE), r(MORE,0)], 0);
        schedule(WRITE_SCAN, 7, vec![r(MORE,1), r(ENTRY_VERSION,6), s(ADVANCE),
            r(MORE,1), r(ENTRY_VERSION,7), s(WRITE_CHANGE_CODE), s(WRITE_HISTORY_CHANGE),
            s(ADVANCE), r(MORE,1), r(ENTRY_VERSION,8), s(WRITE_CHANGE_CODE),
            s(WRITE_HISTORY_CHANGE), s(ADVANCE), r(MORE,0)], 1);
        schedule(WRITE_SCAN, 0, vec![r(MORE,0)], 0);
    }
    #[test]
    fn incoming_history_pending_and_apply() {
        schedule(READ, 0, vec![r(READ_CODE,1), s(LOAD_FULL), r(READ_CODE,2),
            s(READ_ITEM_OP), r(READ_CODE,1), s(LOAD_FULL), r(READ_CODE,0)], 0);
        for queued in [0,1] {
            schedule(READ_ITEM, 0, vec![s(RECORD_ITEM), r(SHOULD_QUEUE,queued),
                s(if queued != 0 { QUEUE_ITEM_MOVE } else { APPLY_ITEM_MOVE })], 0);
        }
        schedule(HISTORY, 0, vec![s(APPEND_HISTORY), s(SET_HISTORY_FLOOR),
            r(HISTORY_EMPTY,0), bounds(0,5), s(POP_HISTORY), r(HISTORY_EMPTY,0),
            bounds(4,5), s(POP_HISTORY), r(HISTORY_EMPTY,0), bounds(5,5)], 0);
        schedule(HISTORY, 0, vec![s(APPEND_HISTORY), s(SET_HISTORY_FLOOR), r(HISTORY_EMPTY,1)], 0);
        schedule(HISTORY, 0, vec![s(APPEND_HISTORY), s(SET_HISTORY_FLOOR),
            r(HISTORY_EMPTY,0), bounds(u64::MAX,0)], 0);
        for earlier in [0,1] {
            let mut steps = vec![r(PENDING_EARLIER,earlier)];
            if earlier != 0 { steps.push(s(FLUSH_PENDING)); }
            steps.push(s(APPEND_PENDING));
            schedule(PENDING, 0, steps, 0);
        }
        for (kind, body) in [(0,APPLY_SET),(1,APPLY_REMOVE),(2,CLEAR_BASE)] {
            schedule(APPLY, 0, vec![r(CHANGE_KIND,kind),s(body),s(MARK_UPDATED)], 0);
        }
        for status in [OK, HOST_ERROR] {
            let mut m = Mock::new(vec![r(READ_CODE,u64::MAX),s(THROW_CODE)]);
            m.fault = Some((1,status,0,0));
            let mut out = 77;
            assert_eq!(m.call(READ,0,&mut out), if status == OK { INVALID } else { HOST_ERROR });
            assert_eq!(out,77);
            assert_eq!(m.events,vec![(READ_CODE,0),(THROW_CODE,0)]);
        }
    }
    #[test]
    fn synchronous_nested_root_keeps_parent_schedule() {
        let mut m = Mock::new(vec![r(PENDING_EARLIER,1),s(FLUSH_PENDING),s(APPEND_PENDING)]);
        m.nested = Some((FLUSH_PENDING,FLUSH,0,vec![r(MORE,1),s(APPLY_PENDING_MOVE),
            s(ADVANCE),r(MORE,0)]));
        let before = sb_net_map_count(0,FLUSH);
        let mut out = 77;
        assert_eq!(m.call(PENDING,0,&mut out),OK);
        assert_eq!(out,0);
        assert_eq!(m.nested_result,Some((OK,0)));
        assert_eq!(sb_net_map_count(0,FLUSH),before.wrapping_add(1));
        assert!(m.steps.is_empty());
        assert!(!m.mismatch);
        // No second PENDING_EARLIER after nested flush. Native queue isolation
        // and destructor behavior require separate C++ evidence, not this mock.
        assert_eq!(m.events,vec![(PENDING_EARLIER,0),(FLUSH_PENDING,0),(APPEND_PENDING,0)]);
    }
    #[test]
    fn strict_reply_shapes_and_statuses() {
        for op in 0..OP_COUNT as u32 {
            let bool_op = matches!(op,MORE|FRONT_READY|SHOULD_SCAN_OP|SHOULD_QUEUE|
                HISTORY_EMPTY|PENDING_EARLIER|WRITE_SCAN_OP|INSERTED|ADD_FAILED|
                FOUND|VALUE_DIFFERS|NONEMPTY|RESET_MISSING|RESET_CHANGED);
            let scalar = matches!(op,READ_COUNT|HISTORY_FLOOR|ENTRY_VERSION|READ_CODE);
            for a in [0,1,2,3,u64::MAX] {
                for b in [0,1,u64::MAX] {
                    let expected = op == HISTORY_BOUNDS || (b == 0 &&
                        if bool_op { a <= 1 } else if scalar { true }
                        else if op == CHANGE_KIND { a <= 2 } else { a == 0 });
                    assert_eq!(valid_reply(op,SbNetMapReply { a,b }),expected,"op={op} a={a} b={b}");
                }
            }
        }
        for status in [1,2,3,4,u32::MAX] {
            let mut m = Mock::new(vec![s(RECORD_ITEM)]);
            m.fault = Some((0,status,0,0));
            let mut out = 77;
            assert_eq!(m.call(LOAD_ITEM,0,&mut out),if status == HOST_ERROR { HOST_ERROR } else { INVALID });
            assert_eq!(out,77);
        }
        for (mode,op,a,b) in [(FLUSH,MORE,2,0),(APPLY,CHANGE_KIND,3,0),
            (LOAD_ITEM,RECORD_ITEM,1,0),(SHOULD,HISTORY_FLOOR,0,1)] {
            let mut m = Mock::new(vec![s(op)]);
            m.fault = Some((0,OK,a,b));
            let mut out = 77;
            assert_eq!(m.call(mode,0,&mut out),INVALID);
            assert_eq!(out,77);
            assert_eq!(m.events.len(),1);
        }
    }
    #[test]
    fn validation_precedes_counts_and_never_writes_output() {
        let mut m = Mock::new(vec![]);
        let ctx = &mut m as *mut _ as *mut c_void;
        let mut out = 77u32;
        let before = (0..COUNT as u32).map(|i| sb_net_map_count(0,i)).collect::<Vec<_>>();
        unsafe {
            for mode in [COUNT as u32,u32::MAX] {
                assert_eq!(sb_net_map_run(mode,ctx,Some(host),0,&mut out),INVALID);
            }
            for mode in 0..COUNT as u32 {
                if !version_argument(mode) {
                    let argument = if mode == READ_TYPE { 256 } else { 1 };
                    assert_eq!(sb_net_map_run(mode,ctx,Some(host),argument,&mut out),INVALID);
                }
            }
            assert_eq!(sb_net_map_run(INIT,std::ptr::null_mut(),Some(host),0,&mut out),INVALID);
            assert_eq!(sb_net_map_run(INIT,ctx,None,0,&mut out),INVALID);
            assert_eq!(sb_net_map_run(INIT,ctx,Some(host),0,std::ptr::null_mut()),INVALID);
            let mut bytes = [0u32;2];
            let unaligned = (bytes.as_mut_ptr() as *mut u8).add(1) as *mut u32;
            assert_eq!(sb_net_map_run(INIT,ctx,Some(host),0,unaligned),INVALID);
        }
        assert_eq!(out,77);
        assert!(m.events.is_empty());
        assert_eq!((0..COUNT as u32).map(|i| sb_net_map_count(0,i)).collect::<Vec<_>>(),before);
        for (kind,index) in [(0,COUNT as u32),(1,COUNT as u32),(2,OP_COUNT as u32),(3,0)] {
            assert_eq!(sb_net_map_count(kind,index),0);
        }
    }
    #[test]
    fn mutation_schedules_and_every_leaf_failure_prefix() {
        schedule(INSERT,0,vec![r(INSERTED,0)],0);
        schedule(INSERT,0,vec![r(INSERTED,1),s(RECORD_INSERTED),s(MARK_UPDATED)],0);
        schedule(ADD,0,vec![r(ADD_FAILED,0)],0);
        schedule(SET,0,vec![r(FOUND,1),r(VALUE_DIFFERS,0)],0);
        schedule(SET,0,vec![r(FOUND,1),r(VALUE_DIFFERS,1),s(RECORD_EXISTING_SET),
            s(ASSIGN_EXISTING),s(MARK_UPDATED)],0);
        schedule(SET,0,vec![r(FOUND,0),s(RECORD_NEW_SET),s(INSERT_NEW),s(MARK_UPDATED)],0);
        schedule(REMOVE,0,vec![r(FOUND,0)],0);
        schedule(REMOVE,0,vec![r(FOUND,1),s(ERASE_FOUND),s(RECORD_REMOVAL),s(MARK_UPDATED)],1);
        schedule(CLEAR,0,vec![r(NONEMPTY,0)],0);
        schedule(CLEAR,0,vec![r(NONEMPTY,1),s(RECORD_CLEAR),s(MARK_UPDATED),s(CLEAR_BASE)],0);
        schedule(RESET,0,vec![s(RESET_REMOVALS_OP),s(RESET_SETS_OP),s(RESET_ASSIGN)],0);
        for (mode,body) in [(RESET_REMOVALS,RESET_REMOVE_ITEM_OP),(RESET_SETS,RESET_SET_ITEM_OP)] {
            schedule(mode,0,vec![r(MORE,0)],0);
            schedule(mode,0,vec![r(MORE,1),s(body),s(ADVANCE),r(MORE,1),s(body),
                s(ADVANCE),r(MORE,0)],0);
        }
        for (mode,predicate,record) in [(RESET_REMOVE_ITEM,RESET_MISSING,RECORD_CURRENT_REMOVE),
            (RESET_SET_ITEM,RESET_CHANGED,RECORD_CURRENT_SET)] {
            schedule(mode,0,vec![r(predicate,0)],0);
            schedule(mode,0,vec![r(predicate,1),s(record),s(MARK_UPDATED)],0);
        }
    }
    #[test]
    fn tags_classification_and_throwing_leaves() {
        for kind in 0..3 {
            let mut steps = vec![r(CHANGE_KIND,kind),v(WRITE_TAG,kind,0)];
            if kind < 2 { steps.push(s(WRITE_KEY)); }
            if kind == 0 { steps.push(s(WRITE_VALUE)); }
            schedule(WRITE_CHANGE,0,steps,0);
            schedule(READ_TYPE,kind,vec![v(SELECT_KIND,kind,0)],0);
        }
        // All native u8 type codes are admitted, but only 0/1/2 select a kind.
        // The throwing leaf cannot successfully continue into a typed read.
        for code in 3..=255 {
            for (status,expected) in [(OK,INVALID),(HOST_ERROR,HOST_ERROR),(PANIC,INVALID)] {
                let mut m = Mock::new(vec![s(THROW_TYPE)]);
                m.fault = Some((0,status,0,0));
                let mut out = 77;
                assert_eq!(m.call(READ_TYPE,code,&mut out),expected);
                assert_eq!(out,77);
                assert_eq!(m.events,vec![(THROW_TYPE,0)]);
                assert!(!m.mismatch);
            }
        }
        for (status,expected) in [(OK,INVALID),(HOST_ERROR,HOST_ERROR),(PANIC,INVALID)] {
            let mut m = Mock::new(vec![r(ADD_FAILED,1),s(THROW_DUPLICATE)]);
            m.fault = Some((1,status,0,0));
            let mut out = 77;
            assert_eq!(m.call(ADD,0,&mut out),expected);
            assert_eq!(out,77);
            assert_eq!(m.events,vec![(ADD_FAILED,0),(THROW_DUPLICATE,0)]);
            assert!(!m.mismatch);
        }
        let mut failed = Mock::new(vec![r(ADD_FAILED,1),s(THROW_DUPLICATE)]);
        failed.fault = Some((0,HOST_ERROR,0,0));
        let mut out = 77;
        assert_eq!(failed.call(ADD,0,&mut out),HOST_ERROR);
        assert_eq!(out,77);
        assert_eq!(failed.events,vec![(ADD_FAILED,0)]);
    }
    #[test]
    fn appended_leaf_shapes_and_arguments_are_strict() {
        for op in INSERTED..OP_COUNT as u32 {
            let boolean = matches!(op,INSERTED|ADD_FAILED|FOUND|VALUE_DIFFERS|NONEMPTY|
                RESET_MISSING|RESET_CHANGED);
            let arg = if matches!(op,WRITE_TAG|SELECT_KIND) { 2 } else { 0 };
            for (a,b) in [(if boolean { 2 } else { 1 },0),(0,1)] {
                let mut m = Mock::new(vec![v(op,arg,0)]);
                m.fault = Some((0,OK,a,b));
                let ctx = &mut m as *mut _ as *mut c_void;
                assert!(matches!(unsafe { invoke(ctx,host,op,arg) },Err(INVALID)));
                assert_eq!(m.events,vec![(op,arg)]);
                assert!(!m.mismatch);
            }
        }
        for mode in 0..COUNT as u32 {
            for argument in [0,1,2,3,255,256,u64::MAX] {
                assert_eq!(valid_argument(mode,argument),
                    matches!(mode,SHOULD|WRITE|SHOULD_SCAN|WRITE_SCAN) ||
                    if mode == READ_TYPE { argument <= 255 } else { argument == 0 });
            }
        }
        let mut m = Mock::new(vec![]);
        let mut out = 77;
        let before = sb_net_map_count(0,READ_TYPE);
        for invalid in [256,u64::MAX] {
            assert_eq!(m.call(READ_TYPE,invalid,&mut out),INVALID);
        }
        assert_eq!(out,77);
        assert!(m.events.is_empty());
        assert_eq!(sb_net_map_count(0,READ_TYPE),before);
    }
    #[test]
    fn mutation_reentry_preserves_parent_continuation() {
        // Each independent native scope boundary is modeled as a synchronous
        // nested root. This does not certify actual C++ value/iterator lifetimes.
        for (mode,steps,at,child,child_steps) in [
            (INSERT,vec![r(INSERTED,1),s(RECORD_INSERTED),s(MARK_UPDATED)],
                RECORD_INSERTED,HISTORY,vec![s(APPEND_HISTORY),s(SET_HISTORY_FLOOR),r(HISTORY_EMPTY,1)]),
            (ADD,vec![r(ADD_FAILED,0)],ADD_FAILED,INSERT,vec![r(INSERTED,1),s(RECORD_INSERTED),s(MARK_UPDATED)]),
            (RESET,vec![s(RESET_REMOVALS_OP),s(RESET_SETS_OP),s(RESET_ASSIGN)],
                RESET_REMOVALS_OP,RESET_REMOVALS,vec![r(MORE,1),s(RESET_REMOVE_ITEM_OP),s(ADVANCE),r(MORE,0)]),
            (RESET_REMOVALS,vec![r(MORE,1),s(RESET_REMOVE_ITEM_OP),s(ADVANCE),r(MORE,0)],
                RESET_REMOVE_ITEM_OP,RESET_REMOVE_ITEM,vec![r(RESET_MISSING,1),s(RECORD_CURRENT_REMOVE),s(MARK_UPDATED)]),
            (RESET_SETS,vec![r(MORE,1),s(RESET_SET_ITEM_OP),s(ADVANCE),r(MORE,0)],
                RESET_SET_ITEM_OP,RESET_SET_ITEM,vec![r(RESET_CHANGED,1),s(RECORD_CURRENT_SET),s(MARK_UPDATED)]),
        ] {
            let expected = steps.iter().map(|s| (s.op,s.arg)).collect::<Vec<_>>();
            let before = sb_net_map_count(0,child);
            let mut m = Mock::new(steps);
            m.nested = Some((at,child,0,child_steps));
            let mut out = 77;
            assert_eq!(m.call(mode,0,&mut out),OK);
            assert_eq!(out,0);
            assert_eq!(m.nested_result,Some((OK,0)));
            assert_eq!(m.events,expected);
            assert!(m.steps.is_empty());
            assert!(!m.mismatch);
            assert_eq!(sb_net_map_count(0,child),before.wrapping_add(1));
        }
    }
    #[test]
    fn old_numeric_query_prefix_is_unchanged() {
        assert_eq!([INIT,FLUSH,TICK,STORE,LOAD,LOAD_ITEM,SHOULD,WRITE,READ,READ_ITEM,
            HISTORY,PENDING,APPLY,STORE_PENDING,BASE_RECORD,BASE_STORE,DECREMENT_RANGE,
            SHOULD_SCAN,WRITE_SCAN],std::array::from_fn::<_,19,_>(|i| i as u32));
        assert_eq!([RECORD_RANGE_OP,MORE,ADVANCE,STORE_RANGE_OP,FLUSH_PENDING,RECORD_CLEAR,
            RECORD_CURRENT_SET,DECREMENT_RANGE_OP,FRONT_READY,APPLY_FRONT,APPLY_PENDING_MOVE,
            WRITE_SIZE,WRITE_CURRENT_SET,STORE_PENDING_OP,WRITE_PENDING_CHANGE,CLEAR_HISTORY,
            CAPTURE_VERSION,CLEAR_PENDING,CLEAR_BASE,READ_COUNT,LOAD_ITEM_OP,RECORD_ITEM,
            APPLY_ITEM_MOVE,MARK_UPDATED,HISTORY_FLOOR,SHOULD_SCAN_OP,ENTRY_VERSION,
            WRITE_FULL_CODE,STORE_FULL,WRITE_CHANGE_CODE,WRITE_HISTORY_CHANGE,WRITE_TERMINATOR,
            READ_CODE,LOAD_FULL,READ_ITEM_OP,SHOULD_QUEUE,QUEUE_ITEM_MOVE,THROW_CODE,
            APPEND_HISTORY,SET_HISTORY_FLOOR,HISTORY_EMPTY,HISTORY_BOUNDS,POP_HISTORY,
            PENDING_EARLIER,APPEND_PENDING,CHANGE_KIND,APPLY_SET,APPLY_REMOVE,DECREMENT_CURRENT,
            WRITE_SCAN_OP],std::array::from_fn::<_,50,_>(|i| i as u32));
    }
    #[test]
    fn tls_global_attempts_and_panic_barrier() {
        let before_global = sb_net_map_count(1,LOAD_ITEM);
        let before_leaf = sb_net_map_count(2,RECORD_ITEM);
        let local = sb_net_map_count(0,LOAD_ITEM);
        std::thread::spawn(|| {
            assert_eq!(sb_net_map_count(0,LOAD_ITEM),0);
            let mut m = Mock::new(vec![s(RECORD_ITEM)]);
            m.fault = Some((0,HOST_ERROR,0,0));
            let mut output = 77;
            assert_eq!(m.call(LOAD_ITEM,0,&mut output),HOST_ERROR);
            assert_eq!(output,77);
            assert_eq!(sb_net_map_count(0,LOAD_ITEM),1);
        }).join().unwrap();
        assert_eq!(sb_net_map_count(0,LOAD_ITEM),local);
        // Other tests may concurrently increment relaxed global counters.
        assert!(sb_net_map_count(1,LOAD_ITEM).wrapping_sub(before_global) >= 1);
        assert!(sb_net_map_count(2,RECORD_ITEM).wrapping_sub(before_leaf) >= 1);
        let mut output = 77;
        assert_eq!(barrier(|| {
            // Model a panic before the root's only output write, not an
            // unwinding extern-C host (which is outside the supported ABI).
            panic!("internal barrier fixture");
        }),PANIC);
        assert_eq!(output,77);
        assert_eq!(barrier(|| { output = 0; OK }),OK);
        assert_eq!(output,0);
    }
}
