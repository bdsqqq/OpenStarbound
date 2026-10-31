//! Top-level framing policy; native code retains streams, storage and versions.
pub use crate::net_group::{SbNetGroupReply as SbNetTopReply, Host};
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST_ERROR: u32 = 2;
const PANIC: u32 = 3;
const WRITE: u32 = 0;
const READ: u32 = 1;
const PAYLOAD: u32 = 2;
const COUNT: usize = 3;
const WRITE_FULL: u32 = 0;
const STORE: u32 = 1;
const WRITE_DELTA_MARKER: u32 = 2;
const WRITE_DELTA: u32 = 3;
const BLANK: u32 = 4;
const SCOPED_PAYLOAD: u32 = 5;
const IS_FULL: u32 = 6;
const LOAD: u32 = 7;
const READ_DELTA: u32 = 8;
const OP_COUNT: usize = 9;

static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static LEAVES: [AtomicU64; OP_COUNT] = [const { AtomicU64::new(0) }; OP_COUNT];
thread_local! { static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) }; }

fn boolean(op: u32) -> bool { matches!(op, WRITE_DELTA | IS_FULL) }
fn valid_reply(op: u32, reply: SbNetTopReply) -> bool {
    reply.b == 0 && if boolean(op) { reply.a <= 1 } else { reply.a == 0 }
}
unsafe fn invoke(ctx: *mut c_void, host: Host, op: u32) -> Result<u64, u32> {
    let mut reply = SbNetTopReply::default();
    LEAVES[op as usize].fetch_add(1, Ordering::Relaxed);
    match host(ctx, op, 0, &mut reply) {
        OK if valid_reply(op, reply) => Ok(reply.a),
        HOST_ERROR => Err(HOST_ERROR),
        _ => Err(INVALID),
    }
}
unsafe fn run(mode: u32, ctx: *mut c_void, host: Host, argument: u64) -> Result<u32, u32> {
    let call = |op| invoke(ctx, host, op);
    match mode {
        WRITE => {
            if argument == 0 {
                call(WRITE_FULL)?;
                call(STORE)?;
                Ok(1)
            } else {
                call(WRITE_DELTA_MARKER)?;
                Ok(call(WRITE_DELTA)? as u32)
            }
        }
        READ => {
            call(if argument == 1 { BLANK } else { SCOPED_PAYLOAD })?;
            Ok(0)
        }
        PAYLOAD => {
            let full = call(IS_FULL)? != 0;
            call(if full { LOAD } else { READ_DELTA })?;
            Ok(0)
        }
        _ => Err(INVALID),
    }
}
fn barrier(f: impl FnOnce() -> u32) -> u32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(PANIC)
}
/// # Safety
/// See StarRustNetTop.h. Host must not unwind; context, captures and aligned
/// writable output must remain live throughout synchronous callbacks and reentry.
#[no_mangle]
pub unsafe extern "C" fn sb_net_top_run(
    mode: u32, ctx: *mut c_void, host: Option<Host>, argument: u64, out_result: *mut u32,
) -> u32 {
    if mode >= COUNT as u32 || ctx.is_null() || host.is_none() || out_result.is_null()
        || (out_result as usize) % std::mem::align_of::<u32>() != 0
        || (mode == READ && argument > 1) || (mode == PAYLOAD && argument != 0) {
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
/// Wrapping diagnostics, not synchronized completion observations; no reset API.
#[no_mangle]
pub extern "C" fn sb_net_top_count(kind: u32, index: u32) -> u64 {
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

    #[derive(Clone, Default)]
    struct Mock {
        events: Vec<u32>, full: bool, delta: bool, nested: bool,
        fault: Option<(usize, u32, SbNetTopReply)>,
    }
    impl Mock {
        fn call(&mut self, mode: u32, argument: u64, out: &mut u32) -> u32 {
            unsafe { sb_net_top_run(mode, self as *mut _ as _, Some(host), argument, out) }
        }
    }
    // Never panic across the C ABI. Faults stop before fixture effects/reentry.
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, arg: u64, out: *mut SbNetTopReply) -> u32 {
        let m = &mut *(ctx as *mut Mock);
        if arg != 0 || (*out).a != 0 || (*out).b != 0 { return HOST_ERROR; }
        let at = m.events.len();
        m.events.push(op);
        if let Some((n, status, reply)) = m.fault {
            if at == n { out.write(reply); return status; }
        }
        let a = match op {
            WRITE_DELTA => u64::from(m.delta),
            IS_FULL => u64::from(m.full),
            SCOPED_PAYLOAD if m.nested => {
                // End this mutable borrow before reentering the same context.
                let mut result = 77;
                let status = sb_net_top_run(PAYLOAD, ctx, Some(host), 0, &mut result);
                if status != OK { return status; }
                if result != 0 { return HOST_ERROR; }
                0
            }
            WRITE_FULL | STORE | WRITE_DELTA_MARKER | BLANK | SCOPED_PAYLOAD |
            LOAD | READ_DELTA => 0,
            _ => return HOST_ERROR,
        };
        out.write(SbNetTopReply { a, b: 0 });
        OK
    }
    fn scenarios() -> Vec<(u32, u64, bool, bool, Vec<u32>, u32)> {
        vec![
            (WRITE, 0, false, false, vec![WRITE_FULL, STORE], 1),
            (WRITE, 1, false, false, vec![WRITE_DELTA_MARKER, WRITE_DELTA], 0),
            (WRITE, u64::MAX, false, true, vec![WRITE_DELTA_MARKER, WRITE_DELTA], 1),
            (READ, 1, false, false, vec![BLANK], 0),
            (READ, 0, false, false, vec![SCOPED_PAYLOAD], 0),
            (PAYLOAD, 0, true, false, vec![IS_FULL, LOAD], 0),
            (PAYLOAD, 0, false, false, vec![IS_FULL, READ_DELTA], 0),
        ]
    }
    #[test]
    fn finite_schedules_and_success_output() {
        for (mode, arg, full, delta, expected, result) in scenarios() {
            let mut m = Mock { full, delta, ..Mock::default() };
            let before = sb_net_top_count(0, mode);
            let mut out = 77;
            assert_eq!(m.call(mode, arg, &mut out), OK);
            assert_eq!(out, result);
            assert_eq!(m.events, expected);
            assert_eq!(sb_net_top_count(0, mode), before.wrapping_add(1));
        }
    }
    #[test]
    fn every_leaf_failure_preserves_prefix_and_output_without_cleanup() {
        let mut covered = [false; OP_COUNT];
        for (mode, arg, full, delta, expected, _) in scenarios() {
            for (at, &op) in expected.iter().enumerate() {
                covered[op as usize] = true;
                for (status, reply, want) in [
                    (HOST_ERROR, SbNetTopReply { a: 99, b: 99 }, HOST_ERROR),
                    (99, SbNetTopReply::default(), INVALID),
                    (OK, SbNetTopReply { a: 0, b: 1 }, INVALID),
                    (OK, SbNetTopReply { a: if boolean(op) { 2 } else { 1 }, b: 0 }, INVALID),
                ] {
                    let mut m = Mock { full, delta, fault: Some((at, status, reply)), ..Mock::default() };
                    let before = sb_net_top_count(0, mode);
                    let leaves = sb_net_top_count(2, op);
                    let mut out = 77;
                    assert_eq!(m.call(mode, arg, &mut out), want);
                    assert_eq!(out, 77);
                    assert_eq!(m.events, expected[..=at]);
                    assert_eq!(sb_net_top_count(0, mode), before.wrapping_add(1));
                    assert!(sb_net_top_count(2, op).wrapping_sub(leaves) >= 1);
                }
            }
        }
        assert!(covered.into_iter().all(|v| v));
    }
    #[test]
    fn rejects_before_counting_callbacks_or_output() {
        let mut m = Mock::default();
        let ctx = &mut m as *mut _ as *mut c_void;
        let before = COUNTS.with(Cell::get);
        let mut out = 77;
        unsafe {
            for (mode, arg) in [(COUNT as u32, 0), (u32::MAX, 0), (READ, 2),
                (READ, u64::MAX), (PAYLOAD, 1), (PAYLOAD, u64::MAX)] {
                assert_eq!(sb_net_top_run(mode, ctx, Some(host), arg, &mut out), INVALID);
            }
            for mode in 0..COUNT as u32 {
                assert_eq!(sb_net_top_run(mode, std::ptr::null_mut(), Some(host), 0, &mut out), INVALID);
                assert_eq!(sb_net_top_run(mode, ctx, None, 0, &mut out), INVALID);
                assert_eq!(sb_net_top_run(mode, ctx, Some(host), 0, std::ptr::null_mut()), INVALID);
                let mut bytes = [0u32; 2];
                let misaligned = (bytes.as_mut_ptr() as *mut u8).add(1) as *mut u32;
                assert_eq!(sb_net_top_run(mode, ctx, Some(host), 0, misaligned), INVALID);
            }
        }
        assert_eq!(out, 77);
        assert!(m.events.is_empty());
        assert_eq!(COUNTS.with(Cell::get), before);
    }
    #[test]
    fn scoped_reentry_counters_wrapping_and_ordinary_panic_seam() {
        for full in [false, true] {
            let before = COUNTS.with(Cell::get);
            let global = sb_net_top_count(1, PAYLOAD);
            let mut m = Mock { nested: true, full, ..Mock::default() };
            let mut out = 77;
            assert_eq!(m.call(READ, 0, &mut out), OK);
            assert_eq!(out, 0);
            assert_eq!(m.events, [SCOPED_PAYLOAD, IS_FULL, if full { LOAD } else { READ_DELTA }]);
            let after = COUNTS.with(Cell::get);
            assert_eq!(after[READ as usize], before[READ as usize].wrapping_add(1));
            assert_eq!(after[PAYLOAD as usize], before[PAYLOAD as usize].wrapping_add(1));
            assert!(sb_net_top_count(1, PAYLOAD).wrapping_sub(global) >= 1);
        }
        // Inner failure must propagate through the outer scoped leaf unchanged.
        let mut m = Mock { nested: true, fault: Some((2, HOST_ERROR, SbNetTopReply::default())), ..Mock::default() };
        let mut out = 77;
        assert_eq!(m.call(READ, 0, &mut out), HOST_ERROR);
        assert_eq!(out, 77);
        assert_eq!(m.events, [SCOPED_PAYLOAD, IS_FULL, READ_DELTA]);
        COUNTS.with(|cell| { let mut counts = cell.get(); counts[WRITE as usize] = u64::MAX; cell.set(counts); });
        assert_eq!(Mock::default().call(WRITE, 0, &mut out), OK);
        assert_eq!(sb_net_top_count(0, WRITE), 0);
        let atomic = AtomicU64::new(u64::MAX);
        atomic.fetch_add(1, Ordering::Relaxed);
        assert_eq!(atomic.load(Ordering::Relaxed), 0);
        assert_eq!(barrier(|| panic!("ordinary Rust panic, never an extern callback")), PANIC);
        assert_eq!(sb_net_top_count(3, 0), 0);
        assert_eq!(sb_net_top_count(0, COUNT as u32), 0);
        assert_eq!(sb_net_top_count(1, COUNT as u32), 0);
        assert_eq!(sb_net_top_count(2, OP_COUNT as u32), 0);
        assert_eq!(std::mem::size_of::<SbNetTopReply>(), 16);
        assert_eq!(std::mem::align_of::<SbNetTopReply>(), 8);
    }
}
