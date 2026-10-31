//! Control only: all floating-point operations, payload/storage and lifetimes
//! remain whole native operations. This is not FP qualification or a storage port.
use crate::net_group::{SbNetGroupReply as SbNetFloatReply, Host};
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST_ERROR: u32 = 2;
const PANIC: u32 = 3;
const SET: u32 = 0;
const ENABLE: u32 = 1;
const DISABLE: u32 = 2;
const TICK: u32 = 3;
const STORE: u32 = 4;
const LOAD: u32 = 5;
const WRITE: u32 = 6;
const READ: u32 = 7;
const BLANK: u32 = 8;
const DECREMENT: u32 = 9;
const BLANK_ITEM: u32 = 10;
const COUNT: usize = 11;
const VALUE_DIFFERS: u32 = 0;
const ENCODE_DIFFERS: u32 = 1;
const CAPTURE_VERSION: u32 = 2;
const ASSIGN_INPUT: u32 = 3;
const HAS_POINTS: u32 = 4;
const CLEAR_POINTS: u32 = 5;
const APPEND_ZERO: u32 = 6;
const EMPLACE_POINTS: u32 = 7;
const ASSIGN_LAST: u32 = 8;
const RESET_POINTS: u32 = 9;
const DECREMENT_SCOPE: u32 = 10;
const MORE: u32 = 11;
const ADVANCE: u32 = 12;
const DECREMENT_CURRENT: u32 = 13;
const PRUNE_READY: u32 = 14;
const REMOVE_FIRST: u32 = 15;
const ASSIGN_INTERPOLATED: u32 = 16;
const WRITE_LAST: u32 = 17;
const WRITE_CURRENT: u32 = 18;
const ASSIGN_READ: u32 = 19;
const LATEST_VERSION: u32 = 20;
const INPUT_EARLIER: u32 = 21;
const APPEND_INPUT: u32 = 22;
const SCOPED_BLANK: u32 = 23;
const SAVED_EARLIER: u32 = 24;
const REPLACE_LAST_POINT: u32 = 25;
const APPEND_LAST_POINT: u32 = 26;
const OP_COUNT: usize = 27;
static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static LEAVES: [AtomicU64; OP_COUNT] = [const { AtomicU64::new(0) }; OP_COUNT];
thread_local! { static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) }; }

fn boolean(op: u32) -> bool {
    matches!(op, VALUE_DIFFERS | ENCODE_DIFFERS | HAS_POINTS | MORE | PRUNE_READY | INPUT_EARLIER | SAVED_EARLIER)
}
unsafe fn invoke(ctx: *mut c_void, host: Host, op: u32) -> Result<u64, u32> {
    let mut reply = SbNetFloatReply::default();
    LEAVES[op as usize].fetch_add(1, Ordering::Relaxed);
    match host(ctx, op, 0, &mut reply) {
        OK if reply.b == 0 && if boolean(op) { reply.a <= 1 }
            else { op == LATEST_VERSION || reply.a == 0 } => Ok(reply.a),
        HOST_ERROR => Err(HOST_ERROR),
        _ => Err(INVALID),
    }
}

unsafe fn execute(mode: u32, ctx: *mut c_void, host: Host, argument: u64) -> Result<u32, u32> {
    let call = |op| invoke(ctx, host, op);
    match mode {
        SET => {
            if call(VALUE_DIFFERS)? != 0 {
                if call(ENCODE_DIFFERS)? != 0 { call(CAPTURE_VERSION)?; }
                call(ASSIGN_INPUT)?;
                if call(HAS_POINTS)? != 0 {
                    call(CLEAR_POINTS)?;
                    call(APPEND_ZERO)?;
                }
            }
        }
        ENABLE => {
            if call(HAS_POINTS)? == 0 {
                call(EMPLACE_POINTS)?;
                call(APPEND_ZERO)?;
            }
        }
        DISABLE => {
            if call(HAS_POINTS)? != 0 {
                call(ASSIGN_LAST)?;
                call(RESET_POINTS)?;
            }
        }
        TICK => {
            if call(HAS_POINTS)? != 0 {
                // Native cached-range iterators live across the nested mode9.
                call(DECREMENT_SCOPE)?;
                while call(PRUNE_READY)? != 0 { call(REMOVE_FIRST)?; }
                call(ASSIGN_INTERPOLATED)?;
            }
        }
        STORE => {
            if call(HAS_POINTS)? != 0 { call(WRITE_LAST)?; }
            else { call(WRITE_CURRENT)?; }
        }
        LOAD => {
            call(ASSIGN_READ)?;
            call(CAPTURE_VERSION)?;
            if call(HAS_POINTS)? != 0 {
                call(CLEAR_POINTS)?;
                call(APPEND_ZERO)?;
            }
        }
        WRITE => {
            if call(LATEST_VERSION)? < argument { return Ok(0); }
            if call(HAS_POINTS)? != 0 { call(WRITE_LAST)?; }
            else { call(WRITE_CURRENT)?; }
            return Ok(1);
        }
        READ => {
            call(CAPTURE_VERSION)?;
            if call(HAS_POINTS)? != 0 {
                if call(INPUT_EARLIER)? != 0 { call(CLEAR_POINTS)?; }
                call(APPEND_INPUT)?;
                call(ASSIGN_INTERPOLATED)?;
            } else { call(ASSIGN_INPUT)?; }
        }
        BLANK => {
            if call(HAS_POINTS)? != 0 { call(SCOPED_BLANK)?; }
        }
        DECREMENT => {
            while call(MORE)? != 0 {
                call(DECREMENT_CURRENT)?;
                call(ADVANCE)?;
            }
        }
        BLANK_ITEM => {
            if call(SAVED_EARLIER)? != 0 { call(REPLACE_LAST_POINT)?; }
            else { call(APPEND_LAST_POINT)?; }
            call(ASSIGN_INTERPOLATED)?;
        }
        _ => return Err(INVALID),
    }
    Ok(0)
}
fn barrier(f: impl FnOnce() -> u32) -> u32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(PANIC)
}
/// # Safety
/// See StarRustNetFloat.h. Host must not unwind; native context and aligned
/// writable output remain live throughout synchronous callbacks and reentry.
#[no_mangle]
pub unsafe extern "C" fn sb_net_float_run(
    mode: u32, ctx: *mut c_void, host: Option<Host>, argument: u64, out_result: *mut u32,
) -> u32 {
    if mode >= COUNT as u32 || (mode != WRITE && argument != 0) || ctx.is_null()
        || host.is_none() || out_result.is_null()
        || (out_result as usize) % std::mem::align_of::<u32>() != 0 {
        return INVALID;
    }
    barrier(|| {
        TOTALS[mode as usize].fetch_add(1, Ordering::Relaxed);
        COUNTS.with(|cell| {
            let mut counts = cell.get();
            counts[mode as usize] = counts[mode as usize].wrapping_add(1);
            cell.set(counts);
        });
        match execute(mode, ctx, host.unwrap(), argument) {
            Ok(value) => { out_result.write(value); OK }
            Err(status) => status,
        }
    })
}
/// Wrapping diagnostics count accepted roots and attempted (not successful) leaves.
#[no_mangle]
pub extern "C" fn sb_net_float_count(kind: u32, index: u32) -> u64 {
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
    type Step = (u32, u64);
    #[derive(Default)]
    struct Mock {
        script: Vec<Step>, events: Vec<u32>,
        fault: Option<(usize, u32, SbNetFloatReply)>,
        nested: Option<(u32, u32)>,
    }
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, arg: u64, out: *mut SbNetFloatReply) -> u32 {
        // End each native-state borrow before reentry; never unwind this ABI.
        let nested;
        {
            let m = &mut *(ctx as *mut Mock);
            let at = m.events.len();
            m.events.push(op);
            if arg != 0 || (*out).a != 0 || (*out).b != 0 { return HOST_ERROR; }
            if let Some((n, status, reply)) = m.fault {
                if n == at { out.write(reply); return status; }
            }
            let Some(&(expected, value)) = m.script.get(at) else { return HOST_ERROR; };
            if op != expected { return HOST_ERROR; }
            out.write(SbNetFloatReply { a: value, b: 0 });
            nested = match m.nested {
                Some((leaf, mode)) if leaf == op => { m.nested = None; Some(mode) }
                _ => None,
            };
        }
        if let Some(mode) = nested {
            let mut result = 77;
            let status = sb_net_float_run(mode, ctx, Some(host), 0, &mut result);
            if status != OK { return status; }
            if result != 0 { return HOST_ERROR; }
        }
        OK
    }
    fn run(m: &mut Mock, mode: u32, argument: u64, out: &mut u32) -> u32 {
        unsafe { sb_net_float_run(mode, m as *mut _ as _, Some(host), argument, out) }
    }
    fn check(mode: u32, argument: u64, script: &[Step], expected: u32) {
        let mut m = Mock { script: script.to_vec(), ..Default::default() };
        let mut out = 77;
        let before = sb_net_float_count(0, mode);
        assert_eq!(run(&mut m, mode, argument, &mut out), OK);
        assert_eq!(sb_net_float_count(0, mode), before.wrapping_add(1));
        assert_eq!(out, expected);
        let events: Vec<_> = script.iter().map(|s| s.0).collect();
        assert_eq!(m.events, events);
        // Every leaf failure stops at the exact prefix; no output or repair.
        for (at, &(op, _)) in script.iter().enumerate() {
            let mut faults = vec![
                (HOST_ERROR, SbNetFloatReply { a: 99, b: 99 }, HOST_ERROR),
                (INVALID, SbNetFloatReply::default(), INVALID),
                (PANIC, SbNetFloatReply::default(), INVALID),
                (u32::MAX, SbNetFloatReply::default(), INVALID),
                (OK, SbNetFloatReply { a: 0, b: 1 }, INVALID),
            ];
            if op != LATEST_VERSION {
                faults.push((OK, SbNetFloatReply { a: if boolean(op) { 2 } else { 1 }, b: 0 }, INVALID));
            }
            for (status, reply, expected_status) in faults {
                let mut m = Mock { script: script.to_vec(), fault: Some((at, status, reply)), ..Default::default() };
                out = 77;
                let before = sb_net_float_count(0, mode);
                let attempted = sb_net_float_count(2, op);
                assert_eq!(run(&mut m, mode, argument, &mut out), expected_status);
                assert_eq!(sb_net_float_count(0, mode), before.wrapping_add(1));
                assert!(sb_net_float_count(2, op).wrapping_sub(attempted) >= 1);
                assert_eq!(out, 77);
                assert_eq!(m.events, events[..=at]);
            }
        }
    }
    #[test]
    fn all_branches_strict_replies_and_failure_prefixes() {
        check(SET, 0, &[(VALUE_DIFFERS, 0)], 0);
        for has in [0, 1] {
            for encoded in [0, 1] {
                let mut s = vec![(VALUE_DIFFERS, 1), (ENCODE_DIFFERS, encoded)];
                if encoded == 1 { s.push((CAPTURE_VERSION, 0)); }
                s.extend([(ASSIGN_INPUT, 0), (HAS_POINTS, has)]);
                if has == 1 { s.extend([(CLEAR_POINTS, 0), (APPEND_ZERO, 0)]); }
                check(SET, 0, &s, 0);
            }
            let mut s = vec![(HAS_POINTS, has)];
            if has == 0 { s.extend([(EMPLACE_POINTS, 0), (APPEND_ZERO, 0)]); }
            check(ENABLE, 0, &s, 0);
            let mut s = vec![(HAS_POINTS, has)];
            if has == 1 { s.extend([(ASSIGN_LAST, 0), (RESET_POINTS, 0)]); }
            check(DISABLE, 0, &s, 0);
            check(STORE, 0, &[(HAS_POINTS, has), (if has == 1 { WRITE_LAST } else { WRITE_CURRENT }, 0)], 0);
            let mut s = vec![(ASSIGN_READ, 0), (CAPTURE_VERSION, 0), (HAS_POINTS, has)];
            if has == 1 { s.extend([(CLEAR_POINTS, 0), (APPEND_ZERO, 0)]); }
            check(LOAD, 0, &s, 0);
            for earlier in [0, 1] {
                let mut s = vec![(CAPTURE_VERSION, 0), (HAS_POINTS, has)];
                if has == 1 {
                    s.push((INPUT_EARLIER, earlier));
                    if earlier == 1 { s.push((CLEAR_POINTS, 0)); }
                    s.extend([(APPEND_INPUT, 0), (ASSIGN_INTERPOLATED, 0)]);
                } else { s.push((ASSIGN_INPUT, 0)); }
                check(READ, 0, &s, 0);
                check(BLANK_ITEM, 0, &[(SAVED_EARLIER, earlier),
                    (if earlier == 1 { REPLACE_LAST_POINT } else { APPEND_LAST_POINT }, 0),
                    (ASSIGN_INTERPOLATED, 0)], 0);
            }
            let mut s = vec![(HAS_POINTS, has)];
            if has == 1 { s.push((SCOPED_BLANK, 0)); }
            check(BLANK, 0, &s, 0);
            for latest in [0, 1, u64::MAX - 1, u64::MAX] {
                for from in [0, 1, u64::MAX - 1, u64::MAX] {
                    let mut s = vec![(LATEST_VERSION, latest)];
                    if latest >= from {
                        s.extend([(HAS_POINTS, has), (if has == 1 { WRITE_LAST } else { WRITE_CURRENT }, 0)]);
                    }
                    check(WRITE, from, &s, u32::from(latest >= from));
                }
            }
        }
        check(TICK, 0, &[(HAS_POINTS, 0)], 0);
        for n in 0..5 {
            let mut s = vec![(HAS_POINTS, 1), (DECREMENT_SCOPE, 0)];
            for _ in 0..n { s.extend([(PRUNE_READY, 1), (REMOVE_FIRST, 0)]); }
            s.extend([(PRUNE_READY, 0), (ASSIGN_INTERPOLATED, 0)]);
            check(TICK, 0, &s, 0);
            let mut s = Vec::new();
            for _ in 0..n { s.extend([(MORE, 1), (DECREMENT_CURRENT, 0), (ADVANCE, 0)]); }
            s.push((MORE, 0));
            check(DECREMENT, 0, &s, 0);
        }
    }
    #[test]
    fn strict_roots_validate_before_count_callbacks_or_output() {
        let mut m = Mock::default();
        let ctx = &mut m as *mut _ as *mut c_void;
        let before: Vec<_> = (0..COUNT as u32).map(|i| sb_net_float_count(0, i)).collect();
        let mut out = 77;
        unsafe {
            for mode in [COUNT as u32, u32::MAX] {
                assert_eq!(sb_net_float_run(mode, ctx, Some(host), 0, &mut out), INVALID);
            }
            for mode in 0..COUNT as u32 {
                if mode != WRITE {
                    for arg in [1, u64::MAX] {
                        assert_eq!(sb_net_float_run(mode, ctx, Some(host), arg, &mut out), INVALID);
                    }
                }
                assert_eq!(sb_net_float_run(mode, std::ptr::null_mut(), Some(host), 0, &mut out), INVALID);
                assert_eq!(sb_net_float_run(mode, ctx, None, 0, &mut out), INVALID);
                assert_eq!(sb_net_float_run(mode, ctx, Some(host), 0, std::ptr::null_mut()), INVALID);
                let mut words = [0u32; 2];
                let p = (words.as_mut_ptr() as *mut u8).add(1) as *mut u32;
                assert_eq!(sb_net_float_run(mode, ctx, Some(host), 0, p), INVALID);
            }
        }
        assert_eq!(out, 77);
        assert!(m.events.is_empty());
        assert_eq!(before, (0..COUNT as u32).map(|i| sb_net_float_count(0, i)).collect::<Vec<_>>());
        for (kind, index) in [(0, COUNT as u32), (1, COUNT as u32), (2, OP_COUNT as u32), (3, 0), (u32::MAX, u32::MAX)] {
            assert_eq!(sb_net_float_count(kind, index), 0);
        }
    }
    #[test]
    fn synchronous_scopes_reentry_tls_counters_and_panic_barrier() {
        let tick = sb_net_float_count(0, TICK);
        let decrement = sb_net_float_count(0, DECREMENT);
        let global = sb_net_float_count(1, DECREMENT);
        let leaf = sb_net_float_count(2, DECREMENT_CURRENT);
        let mut m = Mock {
            script: vec![(HAS_POINTS, 1), (DECREMENT_SCOPE, 0),
                (MORE, 1), (DECREMENT_CURRENT, 0), (ADVANCE, 0), (MORE, 0),
                (PRUNE_READY, 1), (REMOVE_FIRST, 0), (PRUNE_READY, 0), (ASSIGN_INTERPOLATED, 0)],
            nested: Some((DECREMENT_SCOPE, DECREMENT)), ..Default::default()
        };
        let mut out = 77;
        assert_eq!(run(&mut m, TICK, 0, &mut out), OK);
        assert_eq!(out, 0);
        assert_eq!(m.events, m.script.iter().map(|s| s.0).collect::<Vec<_>>());
        assert_eq!(sb_net_float_count(0, TICK), tick.wrapping_add(1));
        assert_eq!(sb_net_float_count(0, DECREMENT), decrement.wrapping_add(1));
        assert!(sb_net_float_count(1, DECREMENT).wrapping_sub(global) >= 1);
        assert!(sb_net_float_count(2, DECREMENT_CURRENT).wrapping_sub(leaf) >= 1);
        // Scope failure propagates through both roots without the prune/interpolate tail.
        m.events.clear(); m.nested = Some((DECREMENT_SCOPE, DECREMENT));
        m.fault = Some((3, HOST_ERROR, SbNetFloatReply::default())); out = 77;
        assert_eq!(run(&mut m, TICK, 0, &mut out), HOST_ERROR);
        assert_eq!(out, 77);
        assert_eq!(m.events, vec![HAS_POINTS, DECREMENT_SCOPE, MORE, DECREMENT_CURRENT]);
        for earlier in [0, 1] {
            let mut m = Mock {
                script: vec![(HAS_POINTS, 1), (SCOPED_BLANK, 0), (SAVED_EARLIER, earlier),
                    (if earlier == 1 { REPLACE_LAST_POINT } else { APPEND_LAST_POINT }, 0),
                    (ASSIGN_INTERPOLATED, 0)],
                nested: Some((SCOPED_BLANK, BLANK_ITEM)), ..Default::default()
            };
            assert_eq!(run(&mut m, BLANK, 0, &mut out), OK);
            assert_eq!(m.events, m.script.iter().map(|s| s.0).collect::<Vec<_>>());
        }
        let before = sb_net_float_count(0, SET);
        std::thread::spawn(|| {
            assert_eq!(sb_net_float_count(0, SET), 0);
            let mut m = Mock { script: vec![(VALUE_DIFFERS, 0)], ..Default::default() };
            let mut out = 77;
            assert_eq!(run(&mut m, SET, 0, &mut out), OK);
            assert_eq!(sb_net_float_count(0, SET), 1);
        }).join().unwrap();
        assert_eq!(sb_net_float_count(0, SET), before);
        COUNTS.with(|cell| { let mut a = cell.get(); a[SET as usize] = u64::MAX; cell.set(a); });
        let mut m = Mock { script: vec![(VALUE_DIFFERS, 0)], ..Default::default() };
        assert_eq!(run(&mut m, SET, 0, &mut out), OK);
        assert_eq!(sb_net_float_count(0, SET), 0);
        out = 77;
        assert_eq!(barrier(|| {
            // Exercise the same success-only publication shape without ever
            // unwinding a host extern-C callback (forbidden by this ABI).
            let result: Result<u32, u32> = (|| panic!("ordinary Rust panic, not host unwind"))();
            match result { Ok(value) => { out = value; OK }, Err(status) => status }
        }), PANIC);
        assert_eq!(out, 77);
    }
}
