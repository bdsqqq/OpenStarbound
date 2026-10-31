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
const COUNT: usize = 19;
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
const OP_COUNT: usize = 50;

static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static LEAVES: [AtomicU64; OP_COUNT] = [const { AtomicU64::new(0) }; OP_COUNT];
thread_local! { static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) }; }

fn version_argument(mode: u32) -> bool {
    matches!(mode, SHOULD | WRITE | SHOULD_SCAN | WRITE_SCAN)
}
fn valid_reply(op: u32, r: SbNetMapReply) -> bool {
    if op == HISTORY_BOUNDS { return true; }
    r.b == 0 && match op {
        MORE | FRONT_READY | SHOULD_SCAN_OP | SHOULD_QUEUE | HISTORY_EMPTY |
        PENDING_EARLIER | WRITE_SCAN_OP => r.a <= 1,
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
        || (!version_argument(mode) && argument != 0) {
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
                HISTORY_EMPTY|PENDING_EARLIER|WRITE_SCAN_OP);
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
                    assert_eq!(sb_net_map_run(mode,ctx,Some(host),1,&mut out),INVALID);
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
