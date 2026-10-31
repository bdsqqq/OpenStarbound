//! Sync-group policy only; storage, rules, virtual hooks and whole FP expressions stay native.
use crate::net_group::{SbNetGroupReply as SbNetSyncReply, Host};
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST_ERROR: u32 = 2;
const PANIC: u32 = 3;
const ENABLE: u32 = 0;
const DISABLE: u32 = 1;
const TICK: u32 = 2;
const STORE: u32 = 3;
const LOAD: u32 = 4;
const WRITE: u32 = 5;
const READ: u32 = 6;
const BLANK: u32 = 7;
const COUNT: usize = 8;
const BASE_ENABLE: u32 = 0;
const BASE_DISABLE: u32 = 1;
const BASE_TICK: u32 = 2;
const HAS_RECENT: u32 = 3;
const NEED_LOAD: u32 = 4;
const DECREMENT_TIME: u32 = 5;
const INTERPOLATING: u32 = 6;
const EXPIRED_BLANK: u32 = 7;
const CLEAR_RECENT: u32 = 8;
const NEED_STORE: u32 = 9;
const BASE_STORE: u32 = 10;
const BASE_LOAD: u32 = 11;
const BASE_WRITE: u32 = 12;
const BASE_READ: u32 = 13;
const MARK_READ: u32 = 14;
const BASE_BLANK: u32 = 15;
const WAS_BLANK: u32 = 16;
const MARK_BLANK: u32 = 17;
const LOAD_BLANK_READY: u32 = 18;
const OP_COUNT: usize = 19;

static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static LEAVES: [AtomicU64; OP_COUNT] = [const { AtomicU64::new(0) }; OP_COUNT];
thread_local! { static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) }; }

fn boolean(op: u32) -> bool {
    matches!(op, HAS_RECENT | INTERPOLATING | EXPIRED_BLANK | BASE_WRITE |
        WAS_BLANK | LOAD_BLANK_READY)
}
unsafe fn invoke(ctx: *mut c_void, host: Host, op: u32, argument: u64) -> Result<u64, u32> {
    let mut reply = SbNetSyncReply::default();
    LEAVES[op as usize].fetch_add(1, Ordering::Relaxed);
    match host(ctx, op, argument, &mut reply) {
        OK if reply.b == 0 && if boolean(op) { reply.a <= 1 } else { reply.a == 0 } => Ok(reply.a),
        HOST_ERROR => Err(HOST_ERROR),
        _ => Err(INVALID),
    }
}
unsafe fn run(mode: u32, ctx: *mut c_void, host: Host) -> Result<u32, u32> {
    let call = |op| invoke(ctx, host, op, 0);
    match mode {
        ENABLE | DISABLE => {
            call(if mode == ENABLE { BASE_ENABLE } else { BASE_DISABLE })?;
            if call(HAS_RECENT)? != 0 { call(NEED_LOAD)?; }
        }
        TICK => {
            call(BASE_TICK)?;
            if call(HAS_RECENT)? != 0 {
                call(DECREMENT_TIME)?;
                if call(INTERPOLATING)? != 0 { call(NEED_LOAD)?; }
                // Fresh after virtual callback; retain the already-entered recent scope.
                if call(EXPIRED_BLANK)? != 0 { call(CLEAR_RECENT)?; }
            }
        }
        STORE | WRITE => {
            call(NEED_STORE)?;
            if mode == WRITE { return Ok(call(BASE_WRITE)? as u32); }
            call(BASE_STORE)?;
        }
        LOAD => {
            call(BASE_LOAD)?;
            invoke(ctx, host, NEED_LOAD, 1)?;
        }
        READ => {
            call(BASE_READ)?;
            call(MARK_READ)?;
            call(NEED_LOAD)?;
        }
        BLANK => {
            call(BASE_BLANK)?;
            if call(WAS_BLANK)? == 0 { call(MARK_BLANK)?; }
            if call(LOAD_BLANK_READY)? != 0 { call(NEED_LOAD)?; }
        }
        _ => return Err(INVALID),
    }
    Ok(0)
}
fn barrier(f: impl FnOnce() -> u32) -> u32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(PANIC)
}
/// # Safety
/// See StarRustNetSync.h. Host must not unwind; context/captures and aligned
/// writable output must remain live through all synchronous nested callbacks.
#[no_mangle]
pub unsafe extern "C" fn sb_net_sync_run(
    mode: u32, ctx: *mut c_void, host: Option<Host>, argument: u64, out_result: *mut u32,
) -> u32 {
    if mode >= COUNT as u32 || ctx.is_null() || host.is_none() || argument != 0
        || out_result.is_null() || (out_result as usize) % std::mem::align_of::<u32>() != 0 {
        return INVALID;
    }
    barrier(|| {
        TOTALS[mode as usize].fetch_add(1, Ordering::Relaxed);
        COUNTS.with(|cell| {
            let mut counts = cell.get();
            counts[mode as usize] = counts[mode as usize].wrapping_add(1);
            cell.set(counts);
        });
        match run(mode, ctx, host.unwrap()) {
            Ok(result) => { out_result.write(result); OK }
            Err(status) => status,
        }
    })
}
/// Wrapping diagnostics, not atomic snapshots; independent of net_group banks.
#[no_mangle]
pub extern "C" fn sb_net_sync_count(kind: u32, index: u32) -> u64 {
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

    #[derive(Clone)]
    struct Mock {
        recent: bool, blank: bool, interpolating: bool,
        // Integer delay is ONLY a control-policy stand-in, not native FP evidence.
        time: i64, dt: i64, input_time: i64, rules: bool, delta: bool,
        stores: usize, loads: usize, events: Vec<(u32, u64)>,
        hook_state: Option<(bool, i64, bool, bool)>, store_changes_rules: bool,
        load_changes_rules: bool, nested: bool, nested_calls: usize,
        fault: Option<(usize, u32, u64, u64)>,
    }
    impl Mock {
        fn new() -> Self {
            Self { recent: true, blank: true, interpolating: true,
                time: 0, dt: 1, input_time: 4, rules: true, delta: true,
                stores: 0, loads: 0, events: vec![], hook_state: None,
                store_changes_rules: false, load_changes_rules: false,
                nested: false, nested_calls: 0, fault: None }
        }
        fn call(&mut self, mode: u32, out: &mut u32) -> u32 {
            unsafe { sb_net_sync_run(mode, self as *mut _ as _, Some(host), 0, out) }
        }
        fn ops(&self) -> Vec<u32> { self.events.iter().map(|e| e.0).collect() }
    }
    // No assertions or panic in callbacks. Faults stop before fixture effects.
    unsafe extern "C" fn child_host(ctx: *mut c_void, op: u32, arg: u64, reply: *mut SbNetSyncReply) -> u32 {
        let calls = &mut *(ctx as *mut usize);
        if arg != 0 || (*reply).a != 0 || (*reply).b != 0 { return HOST_ERROR; }
        *calls += 1;
        // Disabled group TICK queries only GROUP_ENABLED (17), with no range.
        if op == 17 { OK } else { HOST_ERROR }
    }
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, arg: u64, reply: *mut SbNetSyncReply) -> u32 {
        let m = &mut *(ctx as *mut Mock);
        if (*reply).a != 0 || (*reply).b != 0 ||
            (op != NEED_LOAD && arg != 0) || (op == NEED_LOAD && arg > 1) {
            return HOST_ERROR;
        }
        let at = m.events.len();
        m.events.push((op, arg));
        if let Some((n, status, a, b)) = m.fault {
            if n == at { reply.write(SbNetSyncReply { a, b }); return status; }
        }
        let mut a = 0;
        match op {
            BASE_ENABLE => m.interpolating = true,
            BASE_DISABLE => m.interpolating = false,
            BASE_TICK | BASE_BLANK => {},
            HAS_RECENT => a = u64::from(m.recent),
            NEED_LOAD => {
                if let Some((recent, time, blank, interpolating)) = m.hook_state {
                    m.recent = recent; m.time = time; m.blank = blank; m.interpolating = interpolating;
                }
            }
            DECREMENT_TIME => m.time -= m.dt,
            INTERPOLATING => a = u64::from(m.interpolating),
            EXPIRED_BLANK => a = u64::from(m.time < 0 && m.blank),
            CLEAR_RECENT => m.recent = false,
            NEED_STORE => { if m.store_changes_rules { m.rules = false; } }
            BASE_STORE | BASE_WRITE => {
                if m.rules { m.stores += 1; }
                if op == BASE_WRITE { a = u64::from(m.rules && m.delta); }
            }
            BASE_LOAD | BASE_READ => {
                if m.rules { m.loads += 1; }
                if m.load_changes_rules { m.rules = false; }
            }
            MARK_READ => { m.recent = true; m.time = m.input_time; m.blank = false; }
            WAS_BLANK => a = u64::from(m.blank),
            MARK_BLANK => { m.time = m.input_time; m.blank = true; }
            LOAD_BLANK_READY => a = u64::from(m.recent && m.interpolating),
            _ => return HOST_ERROR,
        }
        if m.nested && matches!(op, BASE_ENABLE | BASE_DISABLE | BASE_TICK | BASE_STORE |
            BASE_LOAD | BASE_WRITE | BASE_READ | BASE_BLANK) {
            let mut result = 99;
            let status = crate::net_group::sb_net_group_run(6,
                &mut m.nested_calls as *mut _ as _, Some(child_host), 0, &mut result);
            if status != OK || result != 0 { return HOST_ERROR; }
        }
        reply.write(SbNetSyncReply { a, b: 0 });
        OK
    }

    #[test]
    fn all_modes_order_arguments_rules_and_nested_base() {
        let expected: [&[u32]; COUNT] = [
            &[BASE_ENABLE, HAS_RECENT, NEED_LOAD], &[BASE_DISABLE, HAS_RECENT, NEED_LOAD],
            &[BASE_TICK, HAS_RECENT, DECREMENT_TIME, INTERPOLATING, NEED_LOAD, EXPIRED_BLANK, CLEAR_RECENT],
            &[NEED_STORE, BASE_STORE], &[BASE_LOAD, NEED_LOAD], &[NEED_STORE, BASE_WRITE],
            &[BASE_READ, MARK_READ, NEED_LOAD], &[BASE_BLANK, WAS_BLANK, LOAD_BLANK_READY, NEED_LOAD],
        ];
        for mode in 0..COUNT as u32 {
            let mut m = Mock::new(); m.nested = true;
            let mut out = 99;
            assert_eq!(m.call(mode, &mut out), OK);
            assert_eq!(out, u32::from(mode == WRITE));
            assert_eq!(m.ops(), expected[mode as usize]);
            assert_eq!(m.nested_calls, 1);
            for &(op, arg) in &m.events { assert_eq!(arg, u64::from(op == NEED_LOAD && mode == LOAD)); }
        }
        for mode in [STORE, WRITE] {
            let mut m = Mock::new(); m.store_changes_rules = true;
            let mut out = 99;
            assert_eq!(m.call(mode, &mut out), OK);
            assert_eq!((out, m.stores), (0, 0)); // Qualified base rechecks mutated rules.
        }
        let mut m = Mock::new(); m.load_changes_rules = true;
        assert_eq!(m.call(LOAD, &mut 99), OK);
        assert_eq!(m.events.last(), Some(&(NEED_LOAD, 1)));
        for mode in [ENABLE, DISABLE, TICK] {
            let mut m = Mock::new(); m.recent = false;
            assert_eq!(m.call(mode, &mut 99), OK);
            assert_eq!(m.events.len(), 2);
        }
        let mut m = Mock::new(); m.delta = false;
        let mut out = 99;
        assert_eq!(m.call(WRITE, &mut out), OK); assert_eq!(out, 0);
    }

    #[test]
    fn fresh_predicates_retained_scope_and_blank_expiry() {
        let mut m = Mock::new(); m.time = 1;
        assert_eq!(m.call(TICK, &mut 99), OK);
        assert!(m.recent); assert_eq!(m.time, 0); // Strictly negative only.
        assert_eq!(m.call(TICK, &mut 99), OK); assert!(!m.recent);
        let mut m = Mock::new(); m.blank = false; m.time = -100;
        assert_eq!(m.call(TICK, &mut 99), OK); assert!(m.recent);
        // Hook executes after decrement, changing every relevant field. Expiry
        // sees new time/blank even when recent and interpolation become false.
        for (state, clears) in [((false, -3, true, false), true),
            ((true, 9, true, false), false), ((true, -3, false, true), false)] {
            let mut m = Mock::new(); m.hook_state = Some(state);
            assert_eq!(m.call(TICK, &mut 99), OK);
            assert_eq!(m.ops().contains(&CLEAR_RECENT), clears);
            assert_eq!(m.ops().iter().filter(|&&op| op == HAS_RECENT).count(), 1);
            assert!(m.ops().contains(&EXPIRED_BLANK));
        }
        let mut m = Mock::new(); m.interpolating = false;
        assert_eq!(m.call(TICK, &mut 99), OK);
        assert!(!m.ops().contains(&NEED_LOAD)); assert!(!m.recent);
        let mut m = Mock::new(); m.blank = false; m.time = 20;
        assert_eq!(m.call(BLANK, &mut 99), OK); assert_eq!(m.time, 4);
        m.time = 2; m.input_time = 50; m.events.clear();
        assert_eq!(m.call(BLANK, &mut 99), OK); assert_eq!(m.time, 2);
        assert!(!m.ops().contains(&MARK_BLANK));
        for (recent, interp) in [(false, true), (true, false), (false, false)] {
            let mut m = Mock::new(); m.recent = recent; m.interpolating = interp;
            assert_eq!(m.call(BLANK, &mut 99), OK);
            assert!(!m.ops().contains(&NEED_LOAD));
        }
    }

    #[test]
    fn every_reachable_leaf_denies_immediately_and_retains_prefix() {
        let mut covered = [false; OP_COUNT];
        for mode in 0..COUNT as u32 {
            for blank in [false, true] {
                let mut clean = Mock::new(); clean.blank = blank;
                assert_eq!(clean.call(mode, &mut 99), OK);
                for (at, &(op, _)) in clean.events.iter().enumerate() {
                    covered[op as usize] = true;
                    let mut denials = vec![(HOST_ERROR, 0, 0), (HOST_ERROR, 9, 9),
                        (INVALID, 0, 0), (PANIC, 0, 0), (u32::MAX, 0, 0),
                        (OK, 0, 1), (OK, 1, 1), (OK, u64::MAX, 0)];
                    denials.push((OK, if boolean(op) { 2 } else { 1 }, 0));
                    for (status, a, b) in denials {
                        let mut m = Mock::new(); m.blank = blank; m.fault = Some((at, status, a, b));
                        let mut out = 0x12345678;
                        assert_eq!(m.call(mode, &mut out), if status == HOST_ERROR { HOST_ERROR } else { INVALID });
                        assert_eq!(out, 0x12345678);
                        assert_eq!(m.events, clean.events[..=at]);
                        if mode == READ && op == NEED_LOAD {
                            assert!(m.recent); assert!(!m.blank); assert_eq!(m.time, m.input_time);
                        }
                    }
                }
            }
        }
        assert!(covered.into_iter().all(|seen| seen));
    }

    #[test]
    fn invalid_roots_leave_outputs_callbacks_and_counts_untouched() {
        let mut m = Mock::new(); let ctx = &mut m as *mut _ as *mut c_void;
        let before: Vec<_> = (0..COUNT as u32).map(|i| sb_net_sync_count(0, i)).collect();
        let mut out = 77;
        unsafe {
            for mode in 0..COUNT as u32 {
                assert_eq!(sb_net_sync_run(mode, ctx, Some(host), 1, &mut out), INVALID);
                assert_eq!(sb_net_sync_run(mode, std::ptr::null_mut(), Some(host), 0, &mut out), INVALID);
                assert_eq!(sb_net_sync_run(mode, ctx, None, 0, &mut out), INVALID);
                assert_eq!(sb_net_sync_run(mode, ctx, Some(host), 0, std::ptr::null_mut()), INVALID);
                let mut aligned = [0u32; 2];
                let misaligned = (aligned.as_mut_ptr() as *mut u8).add(1) as *mut u32;
                assert_eq!(sb_net_sync_run(mode, ctx, Some(host), 0, misaligned), INVALID);
            }
            for mode in [COUNT as u32, u32::MAX] {
                assert_eq!(sb_net_sync_run(mode, ctx, Some(host), 0, &mut out), INVALID);
            }
        }
        assert_eq!(out, 77); assert!(m.events.is_empty());
        assert_eq!(before, (0..COUNT as u32).map(|i| sb_net_sync_count(0, i)).collect::<Vec<_>>());
        for (kind, index) in [(0, 8), (1, 8), (2, 19), (3, 0), (u32::MAX, u32::MAX)] {
            assert_eq!(sb_net_sync_count(kind, index), 0);
        }
    }

    #[test]
    fn diagnostic_wrapping_tls_isolation_visibility_and_plain_rust_panic() {
        // Local bank proves relaxed fetch_add wraps without mutating/resetting
        // shared production banks used concurrently by other test threads.
        let bank = AtomicU64::new(u64::MAX);
        assert_eq!(bank.fetch_add(1, Ordering::Relaxed), u64::MAX);
        assert_eq!(bank.load(Ordering::Relaxed), 0);
        let parent_tls = sb_net_sync_count(0, STORE);
        let global_before = sb_net_sync_count(1, STORE);
        let leaves_before = sb_net_sync_count(2, NEED_STORE);
        std::thread::spawn(|| {
            assert_eq!(sb_net_sync_count(0, STORE), 0);
            COUNTS.with(|cell| { let mut counts = cell.get(); counts[STORE as usize] = u64::MAX; cell.set(counts); });
            let mut m = Mock::new(); m.fault = Some((0, HOST_ERROR, 0, 0));
            let mut out = 77;
            assert_eq!(m.call(STORE, &mut out), HOST_ERROR);
            assert_eq!(out, 77); assert_eq!(sb_net_sync_count(0, STORE), 0);
            assert_eq!(m.events, [(NEED_STORE, 0)]);
        }).join().unwrap();
        assert_eq!(sb_net_sync_count(0, STORE), parent_tls);
        // Other tests may increment these globals; do not require an exact delta.
        assert!(sb_net_sync_count(1, STORE).wrapping_sub(global_before) >= 1);
        assert!(sb_net_sync_count(2, NEED_STORE).wrapping_sub(leaves_before) >= 1);
        let mut out = 77;
        assert_eq!(barrier(|| { panic!("ordinary Rust panic, never callback unwind"); }), PANIC);
        assert_eq!(out, 77);
        assert_eq!(barrier(|| { out = 0; OK }), OK); assert_eq!(out, 0);
    }
}
