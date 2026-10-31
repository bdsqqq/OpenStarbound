//! WorkerPool branch/loop policy; native frames retain locks, jobs and threads.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST_ERROR: u32 = 2;
const PANIC: u32 = 3;
const HANDLE_WAIT: u32 = 0;
const HANDLE_FINISH: u32 = 1;
const START: u32 = 2;
const STOP: u32 = 3;
const FINISH: u32 = 4;
const MARK: u32 = 5;
const SPAWN: u32 = 6;
const RUN: u32 = 7;
const COUNT: usize = 8;
const DONE: u32 = 0;
const NONZERO_TIMEOUT: u32 = 1;
const TIMED_WAIT: u32 = 2;
const RETHROW: u32 = 3;
const WAIT: u32 = 4;
const MARK_THREADS: u32 = 5;
const BROADCAST: u32 = 6;
const CLEAR_THREADS: u32 = 7;
const ENTER_SPAWN: u32 = 8;
const MORE: u32 = 9;
const SET_STOP: u32 = 10;
const ADVANCE: u32 = 11;
const EMPTY: u32 = 12;
const FINISH_WORK: u32 = 13;
const FINAL_UNLOCK: u32 = 14;
const STOP_POOL: u32 = 15;
const BROADCAST_LOCKED: u32 = 16;
const SHOULD_STOP: u32 = 17;
const WAIT_WORK: u32 = 18;
const RUN_WORK: u32 = 19;
const APPEND_THREAD: u32 = 20;
const OP_COUNT: usize = 21;

pub type Leaf = unsafe extern "C" fn(*mut c_void, u32, *mut u32) -> u32;
static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static LEAVES: [AtomicU64; OP_COUNT] = [const { AtomicU64::new(0) }; OP_COUNT];
thread_local! {
    static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) };
}

fn aligned(out: *mut u32) -> bool {
    !out.is_null() && (out as usize) % std::mem::align_of::<u32>() == 0
}

fn boolean(op: u32) -> bool {
    matches!(op, DONE | NONZERO_TIMEOUT | MORE | EMPTY | SHOULD_STOP)
}

// No context borrow or counter-cell borrow survives entry into native code.
unsafe fn invoke(ctx: *mut c_void, leaf: Leaf, op: u32) -> Result<u32, u32> {
    let mut response = 0;
    LEAVES[op as usize].fetch_add(1, Ordering::Relaxed);
    if leaf(ctx, op, &mut response) != 0 { return Err(HOST_ERROR); }
    if response > u32::from(boolean(op)) { return Err(INVALID); }
    Ok(response)
}

unsafe fn run(mode: u32, ctx: *mut c_void, leaf: Leaf) -> Result<u32, u32> {
    match mode {
        HANDLE_WAIT => {
            if invoke(ctx, leaf, DONE)? == 0 && invoke(ctx, leaf, NONZERO_TIMEOUT)? != 0 {
                invoke(ctx, leaf, TIMED_WAIT)?;
            }
            invoke(ctx, leaf, RETHROW)?;
            return invoke(ctx, leaf, DONE);
        }
        HANDLE_FINISH => {
            if invoke(ctx, leaf, DONE)? == 0 { invoke(ctx, leaf, WAIT)?; }
            invoke(ctx, leaf, RETHROW)?;
        }
        START => {
            invoke(ctx, leaf, MARK_THREADS)?;
            invoke(ctx, leaf, BROADCAST)?;
            invoke(ctx, leaf, CLEAR_THREADS)?;
            invoke(ctx, leaf, ENTER_SPAWN)?;
        }
        STOP => {
            invoke(ctx, leaf, MARK_THREADS)?;
            invoke(ctx, leaf, BROADCAST_LOCKED)?;
            invoke(ctx, leaf, CLEAR_THREADS)?;
        }
        FINISH => {
            while invoke(ctx, leaf, EMPTY)? == 0 { invoke(ctx, leaf, FINISH_WORK)?; }
            invoke(ctx, leaf, FINAL_UNLOCK)?;
            invoke(ctx, leaf, STOP_POOL)?;
        }
        MARK | SPAWN => {
            while invoke(ctx, leaf, MORE)? != 0 {
                invoke(ctx, leaf, if mode == MARK { SET_STOP } else { APPEND_THREAD })?;
                invoke(ctx, leaf, ADVANCE)?;
            }
        }
        RUN => loop {
            if invoke(ctx, leaf, SHOULD_STOP)? != 0 { break; }
            if invoke(ctx, leaf, EMPTY)? != 0 { invoke(ctx, leaf, WAIT_WORK)?; }
            // The native worker may execute ONE job after wake even if stop was
            // set during wait. Do not move the next stop check before this job.
            if invoke(ctx, leaf, EMPTY)? == 0 { invoke(ctx, leaf, RUN_WORK)?; }
        },
        _ => unreachable!(),
    }
    Ok(0)
}

fn count_entry(mode: usize) {
    TOTALS[mode].fetch_add(1, Ordering::Relaxed);
    COUNTS.with(|cell| {
        let mut counts = cell.get();
        counts[mode] = counts[mode].wrapping_add(1);
        cell.set(counts);
    });
}

/// Executes policy without retaining any native object or allocating threads.
///
/// # Safety
/// Context/callback must remain live and obey StarRustWorkerPool.h, including
/// catching every native exception before returning. No unwind may cross the
/// callback ABI. Output must be live writable aligned u32 storage. Numerical
/// validation cannot prove provenance/liveness. Reentry is allowed; no Rust
/// reference to context or output is held across a callback. Only success writes.
#[no_mangle]
pub unsafe extern "C" fn sb_worker_pool_run(
    mode: u32, ctx: *mut c_void, leaf: Option<Leaf>, out: *mut u32,
) -> u32 {
    if mode as usize >= COUNT || ctx.is_null() || leaf.is_none() || !aligned(out) {
        return INVALID;
    }
    catch_unwind(AssertUnwindSafe(|| {
        count_entry(mode as usize);
        match run(mode, ctx, leaf.unwrap()) {
            Ok(result) => { out.write(result); OK }
            Err(status) => status,
        }
    })).unwrap_or(PANIC)
}

/// Wrapping counters: kind 0 thread entries, 1 global entries, 2 global leaves.
/// Global relaxed loads are diagnostics, not a synchronized snapshot of work.
#[no_mangle]
pub extern "C" fn sb_worker_pool_count(kind: u32, index: u32) -> u64 {
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

    // A mismatched trace returns a host error, never panics through extern C.
    struct Script {
        steps: Vec<(u32, u32)>,
        seen: Vec<u32>,
        fault: Option<(usize, u32, u32)>,
    }
    impl Script {
        fn new(steps: &[(u32, u32)]) -> Self {
            Self { steps: steps.to_vec(), seen: vec![], fault: None }
        }
        fn call(&mut self, mode: u32, out: &mut u32) -> u32 {
            unsafe { sb_worker_pool_run(mode, self as *mut Self as _, Some(script), out) }
        }
    }
    unsafe extern "C" fn script(ctx: *mut c_void, op: u32, out: *mut u32) -> u32 {
        let s = &mut *(ctx as *mut Script);
        let i = s.seen.len();
        s.seen.push(op);
        if s.steps.get(i).map(|p| p.0) != Some(op) { return 99; }
        let (status, response) = match s.fault {
            Some((at, status, response)) if at == i => (status, response),
            _ => (0, s.steps[i].1),
        };
        out.write(response);
        status
    }
    fn cases() -> Vec<(u32, Vec<(u32, u32)>, u32)> {
        vec![
            (HANDLE_WAIT, vec![(DONE,0),(NONZERO_TIMEOUT,1),(TIMED_WAIT,0),(RETHROW,0),(DONE,0)], 0),
            (HANDLE_WAIT, vec![(DONE,0),(NONZERO_TIMEOUT,1),(TIMED_WAIT,0),(RETHROW,0),(DONE,1)], 1),
            (HANDLE_WAIT, vec![(DONE,0),(NONZERO_TIMEOUT,0),(RETHROW,0),(DONE,1)], 1),
            (HANDLE_WAIT, vec![(DONE,1),(RETHROW,0),(DONE,1)], 1),
            (HANDLE_FINISH, vec![(DONE,0),(WAIT,0),(RETHROW,0)], 0),
            (HANDLE_FINISH, vec![(DONE,1),(RETHROW,0)], 0),
            (START, vec![(MARK_THREADS,0),(BROADCAST,0),(CLEAR_THREADS,0),(ENTER_SPAWN,0)], 0),
            (STOP, vec![(MARK_THREADS,0),(BROADCAST_LOCKED,0),(CLEAR_THREADS,0)], 0),
            (FINISH, vec![(EMPTY,0),(FINISH_WORK,0),(EMPTY,0),(FINISH_WORK,0),(EMPTY,1),(FINAL_UNLOCK,0),(STOP_POOL,0)], 0),
            (FINISH, vec![(EMPTY,1),(FINAL_UNLOCK,0),(STOP_POOL,0)], 0),
            (MARK, vec![(MORE,1),(SET_STOP,0),(ADVANCE,0),(MORE,1),(SET_STOP,0),(ADVANCE,0),(MORE,0)], 0),
            (SPAWN, vec![(MORE,1),(APPEND_THREAD,0),(ADVANCE,0),(MORE,1),(APPEND_THREAD,0),(ADVANCE,0),(MORE,0)], 0),
            (MARK, vec![(MORE,0)], 0),
            (SPAWN, vec![(MORE,0)], 0),
            (RUN, vec![(SHOULD_STOP,1)], 0),
            (RUN, vec![(SHOULD_STOP,0),(EMPTY,0),(EMPTY,0),(RUN_WORK,0),(SHOULD_STOP,1)], 0),
            // Spurious wake with no job: do not spin inside WAIT_WORK.
            (RUN, vec![(SHOULD_STOP,0),(EMPTY,1),(WAIT_WORK,0),(EMPTY,1),(SHOULD_STOP,1)], 0),
            (RUN, vec![(SHOULD_STOP,0),(EMPTY,1),(WAIT_WORK,0),(EMPTY,0),(RUN_WORK,0),(SHOULD_STOP,1)], 0),
        ]
    }

    #[test]
    fn exact_root_order_and_every_error_prefix() {
        for (mode, steps, result) in cases() {
            let mut s = Script::new(&steps);
            let mut out = 87;
            assert_eq!(s.call(mode, &mut out), OK, "mode {mode}");
            assert_eq!(out, result);
            assert_eq!(s.seen, steps.iter().map(|p| p.0).collect::<Vec<_>>());
            for at in 0..steps.len() {
                let malformed = if boolean(steps[at].0) { 2 } else { 1 };
                for (host, response, expected) in [(7,0,HOST_ERROR),(0,malformed,INVALID),(7,malformed,HOST_ERROR)] {
                    let mut s = Script::new(&steps);
                    s.fault = Some((at, host, response));
                    let mut out = 87;
                    assert_eq!(s.call(mode, &mut out), expected, "mode {mode}, at {at}");
                    assert_eq!(out, 87);
                    assert_eq!(s.seen, steps[..=at].iter().map(|p| p.0).collect::<Vec<_>>());
                }
            }
        }
    }

    // A host may leave a void reply untouched. Every leaf must receive a fresh
    // zero, not the previous boolean true from DONE.
    unsafe extern "C" fn untouched_void(ctx: *mut c_void, op: u32, out: *mut u32) -> u32 {
        let seen = &mut *(ctx as *mut Vec<u32>);
        seen.push(op);
        if out.read() != 0 { return 99; }
        match op {
            DONE => out.write(1),
            RETHROW => {},
            _ => return 99,
        }
        0
    }
    #[test]
    fn response_is_fresh_zero_and_malformed_entries_still_count() {
        let mut seen: Vec<u32> = vec![];
        let mut out = 87;
        assert_eq!(unsafe { sb_worker_pool_run(HANDLE_WAIT, &mut seen as *mut _ as _, Some(untouched_void), &mut out) }, OK);
        assert_eq!(seen, [DONE, RETHROW, DONE]);
        assert_eq!(out, 1);
        let before = sb_worker_pool_count(0, HANDLE_WAIT);
        let mut s = Script::new(&[(DONE,1)]);
        s.fault = Some((0,0,2));
        out = 87;
        assert_eq!(s.call(HANDLE_WAIT, &mut out), INVALID);
        assert_eq!(out, 87);
        assert_eq!(sb_worker_pool_count(0,HANDLE_WAIT).wrapping_sub(before), 1);
    }

    struct Worker { stopped: bool, pending: bool, ran: bool, seen: Vec<u32> }
    unsafe extern "C" fn worker(ctx: *mut c_void, op: u32, out: *mut u32) -> u32 {
        let w = &mut *(ctx as *mut Worker);
        w.seen.push(op);
        let response = match op {
            SHOULD_STOP => u32::from(w.stopped),
            EMPTY => u32::from(!w.pending),
            WAIT_WORK if !w.stopped => { w.stopped = true; w.pending = true; 0 }
            RUN_WORK if w.pending => { w.pending = false; w.ran = true; 0 }
            _ => return 99,
        };
        out.write(response);
        0
    }
    #[test]
    fn pending_after_wake_runs_before_next_stop_check() {
        let mut w = Worker { stopped: false, pending: false, ran: false, seen: vec![] };
        let mut out = 87;
        assert_eq!(unsafe { sb_worker_pool_run(RUN, &mut w as *mut _ as _, Some(worker), &mut out) }, OK);
        assert!(w.ran);
        assert!(!w.pending);
        assert_eq!(out, 0);
        assert_eq!(w.seen, [SHOULD_STOP, EMPTY, WAIT_WORK, EMPTY, RUN_WORK, SHOULD_STOP]);
    }

    struct Nested { events: Vec<u32>, index: usize, length: usize, mark_entries: u64, spawn_entries: u64 }
    unsafe extern "C" fn nested(ctx: *mut c_void, op: u32, out: *mut u32) -> u32 {
        // End this host borrow BEFORE recursively entering the controller.
        {
            let n = &mut *(ctx as *mut Nested);
            n.events.push(op);
            match op {
                MORE => { out.write(u32::from(n.index < n.length)); return 0; }
                ADVANCE => { n.index += 1; }
                MARK_THREADS | ENTER_SPAWN => { n.index = 0; n.length = 2; }
                SET_STOP | BROADCAST | BROADCAST_LOCKED | CLEAR_THREADS | APPEND_THREAD => {}
                _ => return 99,
            }
        }
        out.write(0);
        if matches!(op, MARK_THREADS | ENTER_SPAWN) {
            let mode = if op == MARK_THREADS { MARK } else { SPAWN };
            let before = sb_worker_pool_count(0, mode);
            let mut result = 87;
            let status = sb_worker_pool_run(mode, ctx, Some(nested), &mut result);
            if status != OK || result != 0 { return 99; }
            let delta = sb_worker_pool_count(0, mode).wrapping_sub(before);
            let n = &mut *(ctx as *mut Nested);
            if mode == MARK { n.mark_entries = delta; } else { n.spawn_entries = delta; }
        }
        0
    }
    #[test]
    fn start_initializes_nested_ranges_in_native_entry_order() {
        let mut n = Nested { events: vec![], index: 99, length: 0, mark_entries: 0, spawn_entries: 0 };
        let before = sb_worker_pool_count(0, START);
        let mut out = 87;
        assert_eq!(unsafe { sb_worker_pool_run(START, &mut n as *mut _ as _, Some(nested), &mut out) }, OK);
        assert_eq!(n.events, [MARK_THREADS, MORE, SET_STOP, ADVANCE, MORE, SET_STOP, ADVANCE, MORE,
            BROADCAST, CLEAR_THREADS, ENTER_SPAWN, MORE, APPEND_THREAD, ADVANCE, MORE, APPEND_THREAD, ADVANCE, MORE]);
        assert_eq!((n.mark_entries, n.spawn_entries), (1, 1));
        assert_eq!(sb_worker_pool_count(0, START).wrapping_sub(before), 1);
        assert_eq!(out, 0);
    }

    #[test]
    fn rejected_entries_do_not_count_callback_or_write() {
        let mut s = Script::new(&[(DONE,1),(RETHROW,0),(DONE,1)]);
        let ctx = &mut s as *mut _ as *mut c_void;
        let mut out = 87;
        let before: Vec<_> = (0..COUNT as u32).map(|i| sb_worker_pool_count(0,i)).collect();
        // Misaligned storage is never dereferenced, even on rejection.
        let mut storage = [0x5au32; 2];
        let misaligned = unsafe { (storage.as_mut_ptr() as *mut u8).add(1) as *mut u32 };
        unsafe {
            for mode in [COUNT as u32, u32::MAX] {
                assert_eq!(sb_worker_pool_run(mode, ctx, Some(script), &mut out), INVALID);
            }
            assert_eq!(sb_worker_pool_run(HANDLE_WAIT, std::ptr::null_mut(), Some(script), &mut out), INVALID);
            assert_eq!(sb_worker_pool_run(HANDLE_WAIT, ctx, None, &mut out), INVALID);
            assert_eq!(sb_worker_pool_run(HANDLE_WAIT, ctx, Some(script), std::ptr::null_mut()), INVALID);
            assert_eq!(sb_worker_pool_run(HANDLE_WAIT, ctx, Some(script), misaligned), INVALID);
        }
        assert_eq!(out, 87);
        assert_eq!(storage, [0x5a; 2]);
        assert!(s.seen.is_empty());
        assert_eq!((0..COUNT as u32).map(|i| sb_worker_pool_count(0,i)).collect::<Vec<_>>(), before);
        for (kind,index) in [(0,8),(1,8),(2,21),(3,0),(u32::MAX,u32::MAX)] {
            assert_eq!(sb_worker_pool_count(kind,index), 0);
        }
    }

    #[test]
    fn counters_include_failed_attempts_wrap_and_isolate_threads() {
        let saved = COUNTS.with(Cell::get);
        COUNTS.with(|c| { let mut v = c.get(); v[HANDLE_FINISH as usize] = u64::MAX; c.set(v); });
        let global = sb_worker_pool_count(1, HANDLE_FINISH);
        let leaves = sb_worker_pool_count(2, DONE);
        let mut s = Script::new(&[(DONE,1)]);
        s.fault = Some((0,9,2));
        let mut out = 87;
        assert_eq!(s.call(HANDLE_FINISH, &mut out), HOST_ERROR);
        assert_eq!(out, 87);
        assert_eq!(sb_worker_pool_count(0,HANDLE_FINISH), 0);
        // Other parallel tests can increase globals; no atomic-snapshot claim.
        assert!(sb_worker_pool_count(1,HANDLE_FINISH).wrapping_sub(global) >= 1);
        assert!(sb_worker_pool_count(2,DONE).wrapping_sub(leaves) >= 1);
        let child = std::thread::spawn(|| {
            assert_eq!(sb_worker_pool_count(0,HANDLE_FINISH), 0);
            let mut s = Script::new(&[(DONE,1),(RETHROW,0)]);
            let mut out = 87;
            assert_eq!(s.call(HANDLE_FINISH, &mut out), OK);
            assert_eq!(sb_worker_pool_count(0,HANDLE_FINISH), 1);
            assert!(sb_worker_pool_count(1,HANDLE_FINISH) >= 1);
            assert!(sb_worker_pool_count(2,RETHROW) >= 1);
        });
        child.join().unwrap();
        assert_eq!(sb_worker_pool_count(0,HANDLE_FINISH), 0);
        COUNTS.with(|c| c.set(saved));
    }
}
