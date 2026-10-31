//! RpcPromise policy only; C++ owns typed state, locks, captures and exception scopes.
use crate::net_group::{Host, SbNetGroupReply};
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST: u32 = 2;
const PANIC: u32 = 3;
const STORE_VALUE: u32 = 0;
const STORE_ERROR: u32 = 1;
const FINISHED: u32 = 2;
const SUCCEEDED: u32 = 3;
const FAILED: u32 = 4;
const RESULT_ROUTE: u32 = 5;
const ERROR_ROUTE: u32 = 6;
const WRAP: u32 = 7;
const AUTO_CALL: u32 = 8;
const AUTO_DROP: u32 = 9;
const COUNT: usize = 10;
const DONE: u32 = 0;
const THROW_FINISHED: u32 = 1;
const ASSIGN: u32 = 2;
const IS_CHAIN: u32 = 3;
const FOLLOW: u32 = 4;
const LOCAL: u32 = 5;
const NEEDS_EVALUATION: u32 = 6;
const OTHER_SUCCEEDED: u32 = 7;
const WRAP_RESULT: u32 = 8;
const OTHER_FAILED: u32 = 9;
const COPY_ERROR: u32 = 10;
const SET_DONE: u32 = 11;
const FORWARD: u32 = 12;
const AUTO_DONE: u32 = 13;
const FAIL_DESTROYED: u32 = 14;
const OP_COUNT: usize = 15;

static ROOTS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static LEAVES: [AtomicU64; OP_COUNT] = [const { AtomicU64::new(0) }; OP_COUNT];
thread_local! {
    static LOCAL_ROOTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) };
    static LOCAL_LEAVES: Cell<[u64; OP_COUNT]> = const { Cell::new([0; OP_COUNT]) };
}
fn increment<const N: usize>(cell: &Cell<[u64; N]>, index: usize) {
    let mut values = cell.get();
    values[index] = values[index].wrapping_add(1);
    cell.set(values);
}
fn boolean(op: u32) -> bool {
    matches!(op, DONE | IS_CHAIN | FOLLOW | LOCAL | NEEDS_EVALUATION
        | OTHER_SUCCEEDED | OTHER_FAILED | AUTO_DONE)
}
fn valid_reply(op: u32, reply: SbNetGroupReply) -> bool {
    reply.b == 0 && if boolean(op) { reply.a <= 1 } else { reply.a == 0 }
}
unsafe fn invoke(ctx: *mut c_void, host: Host, op: u32) -> Result<u64, u32> {
    let mut reply = SbNetGroupReply::default();
    LEAVES[op as usize].fetch_add(1, Ordering::Relaxed);
    LOCAL_LEAVES.with(|c| increment(c, op as usize));
    if host(ctx, op, 0, &mut reply) != OK { return Err(HOST); }
    if !valid_reply(op, reply) || op == THROW_FINISHED { return Err(INVALID); }
    Ok(reply.a)
}
unsafe fn run(mode: u32, ctx: *mut c_void, host: Host) -> Result<u64, u32> {
    let call = |op| invoke(ctx, host, op);
    match mode {
        STORE_VALUE | STORE_ERROR => {
            call(if call(DONE)? != 0 { THROW_FINISHED } else { ASSIGN })?;
        }
        FINISHED | SUCCEEDED | FAILED => {
            return call(if call(IS_CHAIN)? != 0 { FOLLOW } else { LOCAL });
        }
        RESULT_ROUTE | ERROR_ROUTE => return call(IS_CHAIN),
        WRAP => {
            // These are fresh native queries, not a snapshot or a repeated guard.
            if call(NEEDS_EVALUATION)? != 0 {
                if call(OTHER_SUCCEEDED)? != 0 { call(WRAP_RESULT)?; }
                else if call(OTHER_FAILED)? != 0 { call(COPY_ERROR)?; }
            }
        }
        AUTO_CALL => { call(SET_DONE)?; call(FORWARD)?; }
        AUTO_DROP => { if call(AUTO_DONE)? == 0 { call(FAIL_DESTROYED)?; } }
        _ => return Err(INVALID),
    }
    Ok(0)
}
unsafe fn barrier(out: *mut SbNetGroupReply, f: impl FnOnce() -> Result<u64, u32>) -> u32 {
    catch_unwind(AssertUnwindSafe(|| match f() {
        Ok(a) => { out.write(SbNetGroupReply { a, b: 0 }); OK }
        Err(status) => status,
    })).unwrap_or(PANIC)
}
/// # Safety
/// See StarRustRpcPromise.h for live non-unwinding synchronous host/context,
/// native lock/typed-expression obligations, and writable size16/align8 output.
#[no_mangle]
pub unsafe extern "C" fn sb_rpc_promise_run(
    mode: u32, ctx: *mut c_void, host: Option<Host>, argument: u64, out: *mut SbNetGroupReply,
) -> u32 {
    if mode >= COUNT as u32 || argument != 0 || ctx.is_null() || host.is_none()
        || out.is_null() || (out as usize) % 8 != 0 { return INVALID; }
    barrier(out, || {
        ROOTS[mode as usize].fetch_add(1, Ordering::Relaxed);
        LOCAL_ROOTS.with(|c| increment(c, mode as usize));
        run(mode, ctx, host.unwrap())
    })
}
/// Wrapping no-reset diagnostics; independent relaxed loads are not snapshots.
#[no_mangle]
pub extern "C" fn sb_rpc_promise_count(kind: u32, index: u32) -> u64 {
    catch_unwind(|| match (kind, index as usize) {
        (0, i) if i < COUNT => LOCAL_ROOTS.with(|c| c.get()[i]),
        (1, i) if i < COUNT => ROOTS[i].load(Ordering::Relaxed),
        (2, i) if i < OP_COUNT => LOCAL_LEAVES.with(|c| c.get()[i]),
        (3, i) if i < OP_COUNT => LEAVES[i].load(Ordering::Relaxed),
        _ => 0,
    }).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::VecDeque;
    #[derive(Clone)]
    struct Mock {
        events: Vec<u32>, answers: VecDeque<(u32, u64)>,
        fault: Option<(usize, u32, u64, u64)>, done: bool, needs: bool,
        succeeded: bool, failed: bool, chain: bool, nested: bool, panic_host: bool, partial_assign: bool,
        observed_root: u64, observed_leaf: u64,
    }
    impl Mock {
        fn new() -> Self {
            Self { events: vec![], answers: VecDeque::new(), fault: None,
                done: false, needs: true, succeeded: false, failed: false,
                chain: false, nested: false, panic_host: false, partial_assign: false,
                observed_root: 0, observed_leaf: 0 }
        }
        fn call(&mut self, mode: u32, out: &mut SbNetGroupReply) -> u32 {
            unsafe { sb_rpc_promise_run(mode, self as *mut _ as _, Some(host), 0, out) }
        }
    }
    // Ordinary panics are caught INSIDE this extern C boundary, never outside it.
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, arg: u64, out: *mut SbNetGroupReply) -> u32 {
        catch_unwind(AssertUnwindSafe(|| {
            let m = &mut *(ctx as *mut Mock);
            if arg != 0 || (*out).a != 0 || (*out).b != 0 { return HOST; }
            let at = m.events.len(); m.events.push(op);
            m.observed_root = sb_rpc_promise_count(0, AUTO_CALL);
            m.observed_leaf = sb_rpc_promise_count(2, op);
            if m.panic_host { panic!("contained mock host panic"); }
            if let Some((n, status, a, b)) = m.fault {
                if at == n {
                    // Model a native assignment that changes state BEFORE throwing.
                    if m.partial_assign && op == ASSIGN { m.done = true; }
                    out.write(SbNetGroupReply { a, b }); return status;
                }
            }
            let a = if let Some(&(wanted, value)) = m.answers.front() {
                if wanted == op { m.answers.pop_front(); value } else { answer(m, op) }
            } else { answer(m, op) };
            if op == THROW_FINISHED { return HOST; }
            if op == FORWARD && m.nested {
                // Distinct contexts: no native mutex cycles or active callback destruction.
                let mut child = Mock::new(); let mut result = sentinel();
                if child.call(RESULT_ROUTE, &mut result) != OK || result.a != 0 { return HOST; }
            }
            out.write(SbNetGroupReply { a, b: 0 }); OK
        })).unwrap_or(HOST)
    }
    fn answer(m: &mut Mock, op: u32) -> u64 {
        match op {
            DONE | AUTO_DONE => u64::from(m.done), IS_CHAIN => u64::from(m.chain),
            FOLLOW | LOCAL => 1, NEEDS_EVALUATION => u64::from(m.needs),
            OTHER_SUCCEEDED => u64::from(m.succeeded), OTHER_FAILED => u64::from(m.failed),
            SET_DONE | ASSIGN => { m.done = true; 0 }
            WRAP_RESULT | COPY_ERROR => { m.needs = false; 0 }
            _ => 0,
        }
    }
    fn sentinel() -> SbNetGroupReply { SbNetGroupReply { a: 71, b: 93 } }
    fn unchanged(out: SbNetGroupReply) { assert_eq!((out.a, out.b), (71, 93)); }
    fn success(m: &mut Mock, mode: u32) -> u64 {
        let mut out = sentinel(); assert_eq!(m.call(mode, &mut out), OK);
        assert_eq!(out.b, 0); out.a
    }
    fn scenarios() -> Vec<(Mock, u32)> {
        let mut cases = vec![];
        for mode in 0..COUNT as u32 { cases.push((Mock::new(), mode)); }
        for mode in [STORE_VALUE, STORE_ERROR] {
            let mut m = Mock::new(); m.done = true; cases.push((m, mode));
        }
        for mode in [FINISHED, SUCCEEDED, FAILED] {
            let mut m = Mock::new(); m.chain = true; cases.push((m, mode));
        }
        for succeeded in [false, true] {
            let mut m = Mock::new(); m.succeeded = succeeded; m.failed = true;
            cases.push((m, WRAP));
        }
        cases
    }
    #[test]
    fn all_modes_and_chain_bool_routes() {
        let expected: [&[u32]; COUNT] = [
            &[DONE, ASSIGN], &[DONE, ASSIGN], &[IS_CHAIN, LOCAL], &[IS_CHAIN, LOCAL],
            &[IS_CHAIN, LOCAL], &[IS_CHAIN], &[IS_CHAIN],
            &[NEEDS_EVALUATION, OTHER_SUCCEEDED, OTHER_FAILED],
            &[SET_DONE, FORWARD], &[AUTO_DONE, FAIL_DESTROYED],
        ];
        for mode in 0..COUNT as u32 {
            let mut m = Mock::new();
            assert_eq!(success(&mut m, mode), u64::from(matches!(mode, FINISHED | SUCCEEDED | FAILED)));
            assert_eq!(m.events, expected[mode as usize]);
        }
        for mode in [FINISHED, SUCCEEDED, FAILED, RESULT_ROUTE, ERROR_ROUTE] {
            for chain in [false, true] {
                for value in [0, 1] {
                    let mut m = Mock::new(); m.chain = chain;
                    m.answers.push_back((if chain { FOLLOW } else { LOCAL }, value));
                    let route = matches!(mode, RESULT_ROUTE | ERROR_ROUTE);
                    assert_eq!(success(&mut m, mode), if route { u64::from(chain) } else { value });
                    assert_eq!(m.events, if route { vec![IS_CHAIN] }
                        else { vec![IS_CHAIN, if chain { FOLLOW } else { LOCAL }] });
                }
            }
        }
    }
    #[test]
    fn store_already_finished_and_throw_schema() {
        for mode in [STORE_VALUE, STORE_ERROR] {
            for (status, want) in [(OK, INVALID), (HOST, HOST), (99, HOST)] {
                let mut m = Mock::new(); m.done = true; m.fault = Some((1, status, 0, 0));
                let mut out = sentinel(); assert_eq!(m.call(mode, &mut out), want);
                unchanged(out); assert_eq!(m.events, [DONE, THROW_FINISHED]); assert!(m.done);
            }
        }
    }
    #[test]
    fn every_leaf_schema_and_host_failure_prefix() {
        let mut covered = [false; OP_COUNT];
        for (base, mode) in scenarios() {
            let mut baseline = base.clone(); let mut out = sentinel(); baseline.call(mode, &mut out);
            for (at, &op) in baseline.events.iter().enumerate() {
                covered[op as usize] = true;
                for (status, a, b, want) in [(99, 99, 99, HOST), (OK, 2, 0, INVALID), (OK, 0, 1, INVALID)] {
                    let mut m = base.clone(); m.fault = Some((at, status, a, b));
                    let mut out = sentinel(); assert_eq!(m.call(mode, &mut out), want);
                    unchanged(out); assert_eq!(m.events, baseline.events[..=at]);
                }
            }
        }
        assert!(covered.into_iter().all(|v| v));
        for op in 0..OP_COUNT as u32 {
            for a in [0, 1, 2, u64::MAX] {
                for b in [0, 1, u64::MAX] {
                    assert_eq!(valid_reply(op, SbNetGroupReply { a, b }),
                        b == 0 && if boolean(op) { a <= 1 } else { a == 0 });
                }
            }
        }
    }
    #[test]
    fn lazy_wrap_retry_and_fresh_shortcircuit_without_guard_recheck() {
        let mut m = Mock::new(); m.succeeded = true; m.failed = true;
        m.fault = Some((2, HOST, 0, 0)); let mut out = sentinel();
        assert_eq!(m.call(WRAP, &mut out), HOST); unchanged(out); assert!(m.needs);
        assert_eq!(m.events, [NEEDS_EVALUATION, OTHER_SUCCEEDED, WRAP_RESULT]);
        m.events.clear(); m.fault = None;
        success(&mut m, WRAP); assert!(!m.needs);
        assert_eq!(m.events, [NEEDS_EVALUATION, OTHER_SUCCEEDED, WRAP_RESULT]);
        m.events.clear(); success(&mut m, WRAP); assert_eq!(m.events, [NEEDS_EVALUATION]);
        for (answers, expected) in [
            (vec![(NEEDS_EVALUATION, 0)], vec![NEEDS_EVALUATION]),
            (vec![(NEEDS_EVALUATION, 1), (OTHER_SUCCEEDED, 1)], vec![NEEDS_EVALUATION, OTHER_SUCCEEDED, WRAP_RESULT]),
            (vec![(OTHER_SUCCEEDED, 0), (OTHER_FAILED, 1)], vec![NEEDS_EVALUATION, OTHER_SUCCEEDED, OTHER_FAILED, COPY_ERROR]),
            (vec![(OTHER_SUCCEEDED, 0), (OTHER_FAILED, 0)], vec![NEEDS_EVALUATION, OTHER_SUCCEEDED, OTHER_FAILED]),
        ] {
            let mut m = Mock::new(); m.answers = answers.into(); success(&mut m, WRAP);
            assert_eq!(m.events, expected); assert!(m.answers.is_empty());
        }
    }
    #[test]
    fn auto_done_commits_before_forward_error_drop_skips() {
        let mut m = Mock::new(); m.fault = Some((1, HOST, 0, 0)); let mut out = sentinel();
        assert_eq!(m.call(AUTO_CALL, &mut out), HOST); unchanged(out); assert!(m.done);
        assert_eq!(m.events, [SET_DONE, FORWARD]);
        m.events.clear(); m.fault = None; success(&mut m, AUTO_DROP);
        assert_eq!(m.events, [AUTO_DONE]);
        // Mock only: no native destructor throw/death is executed.
        let mut m = Mock::new(); m.fault = Some((1, HOST, 0, 0));
        assert_eq!(m.call(AUTO_DROP, &mut out), HOST); unchanged(out);
        assert_eq!(m.events, [AUTO_DONE, FAIL_DESTROYED]);
        let mut m = Mock::new(); m.fault = Some((1, HOST, 0, 0));
        assert_eq!(m.call(STORE_VALUE, &mut out), HOST); assert!(!m.done);
    }
    #[test]
    fn native_partial_assignment_is_not_rolled_back() {
        for mode in [STORE_VALUE, STORE_ERROR] {
            let mut m = Mock::new(); m.partial_assign = true;
            m.fault = Some((1, HOST, 0, 0)); let mut out = sentinel();
            assert_eq!(m.call(mode, &mut out), HOST); unchanged(out);
            assert!(m.done); assert_eq!(m.events, [DONE, ASSIGN]);
            m.events.clear(); m.fault = None;
            assert_eq!(m.call(mode, &mut out), HOST); unchanged(out);
            assert_eq!(m.events, [DONE, THROW_FINISHED]);
        }
    }
    #[test]
    fn invalid_roots_precede_counts_callbacks_and_writes() {
        let mut m = Mock::new(); let ctx = &mut m as *mut _ as *mut c_void;
        let roots: Vec<_> = (0..COUNT as u32).map(|i| sb_rpc_promise_count(0, i)).collect();
        let leaves: Vec<_> = (0..OP_COUNT as u32).map(|i| sb_rpc_promise_count(2, i)).collect();
        for mode in 0..COUNT as u32 {
            let mut out = sentinel();
            assert_eq!(unsafe { sb_rpc_promise_run(mode, ctx, Some(host), 1, &mut out) }, INVALID);
            unchanged(out);
        }
        let mut out = sentinel();
        for (mode, context, callback, ptr) in [
            (COUNT as u32, ctx, Some(host as Host), &mut out as *mut _),
            (u32::MAX, ctx, Some(host as Host), &mut out as *mut _),
            (STORE_VALUE, std::ptr::null_mut(), Some(host as Host), &mut out as *mut _),
            (STORE_VALUE, ctx, None, &mut out as *mut _),
            (STORE_VALUE, ctx, Some(host as Host), std::ptr::null_mut()),
            (STORE_VALUE, ctx, Some(host as Host), (&mut out as *mut SbNetGroupReply).cast::<u8>().wrapping_add(1).cast()),
        ] {
            assert_eq!(unsafe { sb_rpc_promise_run(mode, context, callback, 0, ptr) }, INVALID);
            unchanged(out);
        }
        assert!(m.events.is_empty());
        assert_eq!(roots, (0..COUNT as u32).map(|i| sb_rpc_promise_count(0, i)).collect::<Vec<_>>());
        assert_eq!(leaves, (0..OP_COUNT as u32).map(|i| sb_rpc_promise_count(2, i)).collect::<Vec<_>>());
        for (kind, index) in [(4, 0), (0, COUNT as u32), (1, u32::MAX), (2, OP_COUNT as u32), (3, u32::MAX)] {
            assert_eq!(sb_rpc_promise_count(kind, index), 0);
        }
    }
    #[test]
    fn pre_callback_counts_reentry_tls_and_global() {
        std::thread::spawn(|| {
            assert!((0..COUNT as u32).all(|i| sb_rpc_promise_count(0, i) == 0));
            assert!((0..OP_COUNT as u32).all(|i| sb_rpc_promise_count(2, i) == 0));
            let global = sb_rpc_promise_count(1, AUTO_CALL);
            let global_leaf = sb_rpc_promise_count(3, FORWARD);
            let mut m = Mock::new(); m.nested = true; success(&mut m, AUTO_CALL);
            assert_eq!(m.observed_root, 1); assert_eq!(m.observed_leaf, 1);
            assert_eq!(sb_rpc_promise_count(0, AUTO_CALL), 1);
            assert_eq!(sb_rpc_promise_count(0, RESULT_ROUTE), 1);
            assert_eq!(sb_rpc_promise_count(2, IS_CHAIN), 1);
            assert!(sb_rpc_promise_count(1, AUTO_CALL).wrapping_sub(global) >= 1);
            assert!(sb_rpc_promise_count(3, FORWARD).wrapping_sub(global_leaf) >= 1);
            let parent = sb_rpc_promise_count(0, AUTO_CALL);
            std::thread::spawn(|| {
                assert_eq!(sb_rpc_promise_count(0, AUTO_CALL), 0);
                let mut m = Mock::new(); success(&mut m, AUTO_CALL);
                assert_eq!(sb_rpc_promise_count(0, AUTO_CALL), 1);
            }).join().unwrap();
            assert_eq!(sb_rpc_promise_count(0, AUTO_CALL), parent);
        }).join().unwrap();
    }
    #[test]
    fn private_panic_barrier_preserves_output_and_host_panic_maps_to_host() {
        let mut out = sentinel();
        assert_eq!(unsafe { barrier(&mut out, || panic!("private policy barrier")) }, PANIC);
        unchanged(out);
        let mut m = Mock::new(); m.panic_host = true;
        assert_eq!(m.call(STORE_VALUE, &mut out), HOST); unchanged(out);
        assert_eq!(m.events, [DONE]);
        let c = Cell::new([u64::MAX]); increment(&c, 0); assert_eq!(c.get(), [0]);
    }
}
