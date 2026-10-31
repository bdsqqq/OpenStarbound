//! Dynamic-group control only. Native owners retain ids, payloads and ranges.
use crate::net_group::{SbNetGroupReply as SbNetDynamicReply, Host};
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST_ERROR: u32 = 2;
const PANIC: u32 = 3;
const ADD: u32 = 0;
const REMOVE: u32 = 1;
const CLEAR: u32 = 2;
const INIT: u32 = 3;
const ENABLE: u32 = 4;
const DISABLE: u32 = 5;
const TICK: u32 = 6;
const BLANK: u32 = 7;
const CHANGE: u32 = 8;
const READY: u32 = 9;
const COUNT: usize = 10;
const ENTER_RANGE: u32 = 0;
const MORE: u32 = 1;
const ADVANCE: u32 = 2;
const LEAVE_RANGE: u32 = 3;
const READY_NEW: u32 = 4;
const ADD_NEW: u32 = 5;
const RECORD_ADD: u32 = 6;
const REMOVE_ID: u32 = 7;
const RECORD_REMOVE: u32 = 8;
const REMOVE_CURRENT_ID: u32 = 9;
const RECORD_RESET: u32 = 10;
const INIT_CURRENT: u32 = 11;
const RECORD_CURRENT_ADD: u32 = 12;
const ENABLE_CURRENT: u32 = 13;
const DISABLE_CURRENT: u32 = 14;
const TICK_CURRENT: u32 = 15;
const GROUP_ENABLED: u32 = 16;
const BLANK_CURRENT: u32 = 17;
const APPEND_CHANGE: u32 = 18;
const SET_HISTORY_FLOOR: u32 = 19;
const HISTORY_EMPTY: u32 = 20;
const HISTORY_BOUNDS: u32 = 21;
const POP_HISTORY: u32 = 22;
const INIT_READY: u32 = 23;
const ENABLE_READY: u32 = 24;
const DISABLE_READY: u32 = 25;
const OP_COUNT: usize = 26;

static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static LEAVES: [AtomicU64; OP_COUNT] = [const { AtomicU64::new(0) }; OP_COUNT];
thread_local! { static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) }; }

fn boolean(op: u32) -> bool { matches!(op, MORE | GROUP_ENABLED | HISTORY_EMPTY) }
fn valid_reply(op: u32, r: SbNetDynamicReply) -> bool {
    if op == HISTORY_BOUNDS { true }
    else { r.b == 0 && if boolean(op) { r.a <= 1 } else { r.a == 0 } }
}
unsafe fn invoke(ctx: *mut c_void, host: Host, op: u32) -> Result<SbNetDynamicReply, u32> {
    let mut reply = SbNetDynamicReply::default();
    LEAVES[op as usize].fetch_add(1, Ordering::Relaxed);
    match host(ctx, op, 0, &mut reply) {
        OK if valid_reply(op, reply) => Ok(reply),
        HOST_ERROR => Err(HOST_ERROR),
        _ => Err(INVALID),
    }
}
unsafe fn run(mode: u32, ctx: *mut c_void, host: Host) -> Result<(), u32> {
    let call = |op| invoke(ctx, host, op);
    match mode {
        ADD => { call(READY_NEW)?; call(ADD_NEW)?; call(RECORD_ADD)?; }
        REMOVE => { call(REMOVE_ID)?; call(RECORD_REMOVE)?; }
        CLEAR => {
            // Native owns the id snapshot before entry, including on failure.
            while call(MORE)?.a != 0 { call(REMOVE_CURRENT_ID)?; call(ADVANCE)?; }
        }
        CHANGE => {
            call(APPEND_CHANGE)?;
            // Preserve the entire native signed expression; Rust only compares u64 replies.
            call(SET_HISTORY_FLOOR)?;
            while call(HISTORY_EMPTY)?.a == 0 {
                let bounds = call(HISTORY_BOUNDS)?;
                if bounds.a >= bounds.b { break; }
                call(POP_HISTORY)?;
            }
        }
        READY => {
            call(INIT_READY)?;
            // Child init may reenter and change both the flag and native hint.
            if call(GROUP_ENABLED)?.a != 0 { call(ENABLE_READY)?; }
            else { call(DISABLE_READY)?; }
        }
        INIT | ENABLE | DISABLE | TICK | BLANK => {
            if mode == INIT { call(RECORD_RESET)?; }
            if mode == BLANK && call(GROUP_ENABLED)?.a == 0 { return Ok(()); }
            call(ENTER_RANGE)?;
            while call(MORE)?.a != 0 {
                match mode {
                    INIT => { call(INIT_CURRENT)?; call(RECORD_CURRENT_ADD)?; }
                    ENABLE => { call(ENABLE_CURRENT)?; }
                    DISABLE => { call(DISABLE_CURRENT)?; }
                    TICK => { call(TICK_CURRENT)?; }
                    BLANK => { call(BLANK_CURRENT)?; }
                    _ => unreachable!(),
                }
                call(ADVANCE)?;
            }
            call(LEAVE_RANGE)?;
        }
        _ => return Err(INVALID),
    }
    Ok(())
}
fn barrier(f: impl FnOnce() -> u32) -> u32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(PANIC)
}
/// # Safety
/// See StarRustNetDynamic.h. Context/captures and aligned writable output must
/// remain live through synchronous reentry. Host must catch all C++ exceptions.
#[no_mangle]
pub unsafe extern "C" fn sb_net_dynamic_run(
    mode: u32, ctx: *mut c_void, host: Option<Host>, argument: u64, out_result: *mut u32,
) -> u32 {
    if mode >= COUNT as u32 || argument != 0 || ctx.is_null() || host.is_none()
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
            Ok(()) => { out_result.write(0); OK }
            Err(status) => status,
        }
    })
}
/// Wrapping, no-reset diagnostics; attempted leaves are not completed leaves.
#[no_mangle]
pub extern "C" fn sb_net_dynamic_count(kind: u32, index: u32) -> u64 {
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
    struct Mock {
        ids: Vec<u64>, snapshot: Vec<u64>, cursor: usize, active: bool,
        enabled: bool, hint: u64, toggle_init: bool, ready_hint: Option<u64>,
        remove_id: u64, added_id: u64, pending: &'static str,
        history: VecDeque<u64>, records: Vec<&'static str>, version: u64,
        floor: u64, supplied_floor: u64, last_version: u64, version_set: bool,
        events: Vec<u32>, fault: Option<(usize, u32, SbNetDynamicReply)>,
        pop_all: bool,
    }
    impl Mock {
        fn new() -> Self {
            Self { ids: vec![7,19,42], snapshot: vec![], cursor: 0, active: false,
                enabled: true, hint: 3, toggle_init: false, ready_hint: None,
                remove_id: 19, added_id: 60, pending: "change",
                history: [99,100,101].into_iter().collect(), records: vec![],
                version: 200, floor: 0, supplied_floor: 100, last_version: 99,
                version_set: false, events: vec![], fault: None, pop_all: false }
        }
        // Models native pre-entry work; deliberately NOT performed by Rust.
        fn prepare(&mut self, mode: u32) {
            match mode {
                CLEAR => { self.snapshot = self.ids.clone(); self.cursor = 0; self.active = true; }
                INIT => { self.version_set = true; self.history.clear();
                    self.records.clear(); self.last_version = 0; }
                ENABLE => { self.enabled = true; self.hint = 8; }
                DISABLE => { self.enabled = false; self.hint = 0; }
                _ => {},
            }
        }
        fn call(&mut self, mode: u32, out: &mut u32) -> u32 {
            unsafe { sb_net_dynamic_run(mode, self as *mut _ as _, Some(host), 0, out) }
        }
    }
    unsafe fn nested(ctx: *mut c_void, mode: u32) -> u32 {
        let mut out = 77;
        let status = sb_net_dynamic_run(mode, ctx, Some(host), 0, &mut out);
        if status == OK && out != 0 { HOST_ERROR } else { status }
    }
    // No assertions/panics in extern C. No fixture reference spans nested calls.
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, arg: u64, out: *mut SbNetDynamicReply) -> u32 {
        {
            let m = &mut *(ctx as *mut Mock);
            if arg != 0 || (*out).a != 0 || (*out).b != 0 { return HOST_ERROR; }
            let at = m.events.len(); m.events.push(op);
            if let Some((n, status, reply)) = m.fault {
                if at == n { out.write(reply); return status; }
            }
        }
        match op {
            READY_NEW => return nested(ctx, READY),
            RECORD_ADD | RECORD_REMOVE | RECORD_RESET | RECORD_CURRENT_ADD => {
                {
                    let m = &mut *(ctx as *mut Mock);
                    m.pending = match op { RECORD_ADD => "add", RECORD_REMOVE => "remove",
                        RECORD_RESET => "reset", _ => "current_add" };
                }
                return nested(ctx, CHANGE);
            }
            REMOVE_CURRENT_ID => {
                {
                    let m = &mut *(ctx as *mut Mock);
                    let Some(&id) = m.snapshot.get(m.cursor) else { return HOST_ERROR; };
                    m.remove_id = id;
                }
                return nested(ctx, REMOVE);
            }
            _ => {},
        }
        let m = &mut *(ctx as *mut Mock);
        let (mut a, mut b) = (0, 0);
        match op {
            ENTER_RANGE => { m.snapshot = m.ids.clone(); m.cursor = 0; m.active = true; }
            MORE => a = u64::from(m.active && m.cursor < m.snapshot.len()),
            ADVANCE => m.cursor += 1,
            LEAVE_RANGE => m.active = false,
            ADD_NEW => m.ids.push(m.added_id),
            REMOVE_ID => {
                let Some(i) = m.ids.iter().position(|&id| id == m.remove_id) else { return HOST_ERROR; };
                m.ids.remove(i);
            }
            INIT_CURRENT | ENABLE_CURRENT | DISABLE_CURRENT | TICK_CURRENT | BLANK_CURRENT => {
                if m.snapshot.get(m.cursor).is_none() { return HOST_ERROR; }
            }
            GROUP_ENABLED => a = u64::from(m.enabled),
            APPEND_CHANGE => { m.history.push_back(m.version); m.records.push(m.pending); }
            SET_HISTORY_FLOOR => { m.floor = m.supplied_floor; m.last_version = m.floor; }
            HISTORY_EMPTY => a = u64::from(m.history.is_empty()),
            HISTORY_BOUNDS => {
                let Some(&front) = m.history.front() else { return HOST_ERROR; };
                a = front; b = m.floor;
            }
            POP_HISTORY => {
                if m.history.pop_front().is_none() { return HOST_ERROR; }
                // Model a native destructor changing history: the next guard must reload.
                if m.pop_all { m.history.clear(); }
            }
            INIT_READY => { if m.toggle_init { m.enabled = !m.enabled; m.hint = 91; } }
            ENABLE_READY => m.ready_hint = Some(m.hint),
            DISABLE_READY => m.ready_hint = None,
            _ => return HOST_ERROR,
        }
        out.write(SbNetDynamicReply { a, b }); OK
    }
    fn success(m: &mut Mock, mode: u32) {
        let mut out = 77;
        assert_eq!(m.call(mode, &mut out), OK);
        assert_eq!(out, 0);
    }

    #[test]
    fn add_remove_and_clear_owned_snapshot_with_failure_prefixes() {
        let mut m = Mock::new(); success(&mut m, ADD);
        assert_eq!(m.ids, [7,19,42,60]); assert_eq!(m.records, ["add"]);
        assert_eq!(&m.events[..5], &[READY_NEW, INIT_READY, GROUP_ENABLED, ENABLE_READY, ADD_NEW]);
        success(&mut m, REMOVE); assert_eq!(m.ids, [7,42,60]);
        assert_eq!(m.records, ["add","remove"]);
        let mut baseline = Mock::new(); baseline.prepare(CLEAR); success(&mut baseline, CLEAR);
        assert!(baseline.ids.is_empty()); assert_eq!(baseline.snapshot, [7,19,42]);
        assert_eq!(baseline.records, ["remove","remove","remove"]);
        assert!(!baseline.events.contains(&ENTER_RANGE)); assert!(!baseline.events.contains(&LEAVE_RANGE));
        assert_eq!(baseline.cursor, 3); // Shrinking live map must not skip snapshot ids.
        let at = baseline.events.iter().enumerate().filter(|(_,op)| **op == RECORD_REMOVE)
            .nth(1).unwrap().0;
        let mut m = Mock::new(); m.prepare(CLEAR);
        m.fault = Some((at, HOST_ERROR, SbNetDynamicReply::default()));
        let mut out = 77; assert_eq!(m.call(CLEAR,&mut out), HOST_ERROR);
        assert_eq!(out,77); assert_eq!(m.ids,[42]); assert_eq!(m.records,["remove"]);
        assert_eq!(m.snapshot,[7,19,42]); assert_eq!(m.cursor,1); assert!(m.active);
        for op in [REMOVE_ID, RECORD_REMOVE] {
            let mut b = Mock::new(); success(&mut b,REMOVE);
            let at = b.events.iter().position(|&x| x == op).unwrap();
            let mut m = Mock::new(); m.fault = Some((at,HOST_ERROR,SbNetDynamicReply::default()));
            let mut out = 77; assert_eq!(m.call(REMOVE,&mut out),HOST_ERROR);
            assert_eq!(m.ids, if op == REMOVE_ID {vec![7,19,42]} else {vec![7,42]});
            assert!(m.records.is_empty()); assert_eq!(out,77);
        }
    }

    #[test]
    fn ready_reads_flag_and_hint_after_init_and_init_does_not_ready() {
        for enabled in [false,true] {
            let mut m = Mock::new(); m.enabled = enabled; m.toggle_init = true;
            success(&mut m,READY);
            assert_eq!(m.events,[INIT_READY,GROUP_ENABLED,if enabled {DISABLE_READY} else {ENABLE_READY}]);
            assert_eq!(m.ready_hint,if enabled {None} else {Some(91)});
        }
        let mut m = Mock::new(); m.records.push("old"); m.prepare(INIT);
        assert!(m.history.is_empty()); assert!(m.records.is_empty());
        assert!(m.version_set); assert_eq!(m.last_version,0);
        success(&mut m,INIT);
        assert_eq!(m.records,["reset","current_add","current_add","current_add"]);
        assert_eq!(m.events.iter().filter(|&&x|x==INIT_CURRENT).count(),3);
        assert!(!m.events.iter().any(|&x| matches!(x,READY_NEW|INIT_READY|GROUP_ENABLED|ENABLE_CURRENT|DISABLE_CURRENT)));
        assert_eq!(m.events[0],RECORD_RESET); assert!(!m.active);
        // INIT root itself must not do the native pre-entry clearing.
        let mut raw = Mock::new(); raw.records.push("old"); success(&mut raw,INIT);
        assert_eq!(raw.records[0],"old"); assert!(!raw.version_set);
        let mut failed = Mock::new(); failed.prepare(INIT);
        failed.fault = Some((0,HOST_ERROR,SbNetDynamicReply::default()));
        let mut out = 77; assert_eq!(failed.call(INIT,&mut out),HOST_ERROR);
        assert!(failed.history.is_empty()); assert_eq!(failed.last_version,0);
        assert!(failed.version_set); assert_eq!(out,77);
    }

    #[test]
    fn traversal_and_disabled_tick_but_not_blank() {
        for (mode,leaf) in [(ENABLE,ENABLE_CURRENT),(DISABLE,DISABLE_CURRENT),
            (TICK,TICK_CURRENT),(BLANK,BLANK_CURRENT)] {
            let mut m = Mock::new(); m.prepare(mode); success(&mut m,mode);
            assert_eq!(m.events.iter().filter(|&&x|x==leaf).count(),3);
            assert_eq!(m.events.iter().filter(|&&x|x==ENTER_RANGE).count(),1);
            assert_eq!(m.events.iter().filter(|&&x|x==LEAVE_RANGE).count(),1);
            assert!(!m.active);
        }
        let mut m = Mock::new(); m.enabled = false; success(&mut m,TICK);
        assert_eq!(m.events.iter().filter(|&&x|x==TICK_CURRENT).count(),3);
        assert!(!m.events.contains(&GROUP_ENABLED));
        m.events.clear(); success(&mut m,BLANK); assert_eq!(m.events,[GROUP_ENABLED]);
        for mode in [ENABLE,DISABLE] {
            let mut m = Mock::new(); m.prepare(mode);
            m.fault = Some((0,HOST_ERROR,SbNetDynamicReply::default()));
            let mut out = 77; assert_eq!(m.call(mode,&mut out),HOST_ERROR);
            assert_eq!(m.enabled,mode==ENABLE); assert_eq!(m.hint,if mode==ENABLE {8} else {0});
        }
    }

    #[test]
    fn history_reload_and_mock_floor_boundary_not_native_signed_arithmetic_proof() {
        let mut m = Mock::new(); success(&mut m,CHANGE);
        assert_eq!(m.history.into_iter().collect::<Vec<_>>(),[100,101,200]);
        assert_eq!(m.events,[APPEND_CHANGE,SET_HISTORY_FLOOR,HISTORY_EMPTY,HISTORY_BOUNDS,
            POP_HISTORY,HISTORY_EMPTY,HISTORY_BOUNDS]); // 100 itself is retained.
        let mut m = Mock::new(); m.pop_all = true; success(&mut m,CHANGE);
        assert!(m.history.is_empty()); assert_eq!(m.events.last(),Some(&HISTORY_EMPTY));
        assert_eq!(m.events.iter().filter(|&&x|x==HISTORY_BOUNDS).count(),1);
        // Bounds are supplied by the mock, never by a Rust emulation of signed C++.
        for (front,floor,pops) in [(0,0,0),(u64::MAX,u64::MAX,0),(0,u64::MAX,2)] {
            let mut m = Mock::new(); m.history = [front].into_iter().collect();
            m.supplied_floor = floor; success(&mut m,CHANGE);
            assert_eq!(m.events.iter().filter(|&&x|x==POP_HISTORY).count(),pops);
        }
    }

    fn scenarios() -> Vec<(Mock,u32)> {
        let mut cases = vec![];
        for mode in 0..COUNT as u32 {
            let mut m = Mock::new(); m.prepare(mode); cases.push((m,mode));
        }
        let mut disabled = Mock::new(); disabled.enabled = false;
        cases.push((disabled,READY));
        cases
    }
    #[test]
    fn every_reachable_leaf_fault_strict_denial_and_error_stop_no_output() {
        let mut coverage = [false;OP_COUNT];
        for (initial,mode) in scenarios() {
            let mut baseline = initial.clone(); success(&mut baseline,mode);
            for (at,&op) in baseline.events.iter().enumerate() {
                coverage[op as usize] = true;
                let mut faults = vec![
                    (HOST_ERROR,SbNetDynamicReply {a:99,b:99},HOST_ERROR),
                    (77,SbNetDynamicReply::default(),INVALID),
                    (INVALID,SbNetDynamicReply::default(),INVALID),
                    (PANIC,SbNetDynamicReply::default(),INVALID),
                ];
                if op != HISTORY_BOUNDS {
                    faults.push((OK,SbNetDynamicReply {a:0,b:1},INVALID));
                    faults.push((OK,SbNetDynamicReply {a:if boolean(op) {2} else {1},b:0},INVALID));
                }
                for (status,reply,want) in faults {
                    let mut m = initial.clone(); m.fault = Some((at,status,reply));
                    let mut out = 77; assert_eq!(m.call(mode,&mut out),want);
                    assert_eq!(out,77); assert_eq!(m.events,&baseline.events[..=at]);
                }
            }
        }
        assert!(coverage.into_iter().all(|v|v));
        for op in 0..OP_COUNT as u32 {
            assert_eq!(valid_reply(op,SbNetDynamicReply {a:u64::MAX,b:u64::MAX}),op==HISTORY_BOUNDS);
        }
    }

    #[test]
    fn rejected_roots_reentry_tls_global_wrapping_and_plain_panic_seam() {
        let mut m = Mock::new(); let ctx = &mut m as *mut _ as *mut c_void;
        let mut out = 77; let before = sb_net_dynamic_count(0,ADD);
        let roots_before: Vec<_> = (0..COUNT as u32).map(|i| sb_net_dynamic_count(0,i)).collect();
        unsafe {
            for mode in 0..COUNT as u32 {
                assert_eq!(sb_net_dynamic_run(mode,ctx,Some(host),1,&mut out),INVALID);
            }
            assert_eq!(sb_net_dynamic_run(COUNT as u32,ctx,Some(host),0,&mut out),INVALID);
            assert_eq!(sb_net_dynamic_run(ADD,std::ptr::null_mut(),Some(host),0,&mut out),INVALID);
            assert_eq!(sb_net_dynamic_run(ADD,ctx,None,0,&mut out),INVALID);
            assert_eq!(sb_net_dynamic_run(ADD,ctx,Some(host),0,std::ptr::null_mut()),INVALID);
            let mut bytes = [0u32;2];
            let unaligned = (bytes.as_mut_ptr() as *mut u8).add(1) as *mut u32;
            assert_eq!(sb_net_dynamic_run(ADD,ctx,Some(host),0,unaligned),INVALID);
        }
        assert!(m.events.is_empty()); assert_eq!(out,77);
        assert_eq!(sb_net_dynamic_count(0,ADD),before);
        assert_eq!((0..COUNT as u32).map(|i| sb_net_dynamic_count(0,i)).collect::<Vec<_>>(),roots_before);
        // Accepted failure counts the root and attempted leaf, but publishes no output.
        let failed_before = sb_net_dynamic_count(0,REMOVE);
        let attempted_before = sb_net_dynamic_count(2,REMOVE_ID);
        let mut failed = Mock::new();
        failed.fault = Some((0,HOST_ERROR,SbNetDynamicReply::default()));
        assert_eq!(failed.call(REMOVE,&mut out),HOST_ERROR); assert_eq!(out,77);
        assert_eq!(sb_net_dynamic_count(0,REMOVE),failed_before.wrapping_add(1));
        assert!(sb_net_dynamic_count(2,REMOVE_ID).wrapping_sub(attempted_before)>=1);
        let ready = sb_net_dynamic_count(0,READY); let change = sb_net_dynamic_count(0,CHANGE);
        let global = sb_net_dynamic_count(1,ADD); let attempts = sb_net_dynamic_count(2,READY_NEW);
        success(&mut m,ADD); // Same-context nested READY and CHANGE, no live fixture borrow.
        assert_eq!(sb_net_dynamic_count(0,ADD),before.wrapping_add(1));
        assert_eq!(sb_net_dynamic_count(0,READY),ready.wrapping_add(1));
        assert_eq!(sb_net_dynamic_count(0,CHANGE),change.wrapping_add(1));
        assert!(sb_net_dynamic_count(1,ADD).wrapping_sub(global)>=1);
        assert!(sb_net_dynamic_count(2,READY_NEW).wrapping_sub(attempts)>=1);
        std::thread::spawn(|| {
            assert_eq!(sb_net_dynamic_count(0,ADD),0);
            success(&mut Mock::new(),ADD);
            assert_eq!(sb_net_dynamic_count(0,ADD),1);
        }).join().unwrap();
        assert_eq!(sb_net_dynamic_count(0,ADD),before.wrapping_add(1));
        COUNTS.with(|c| { let mut a=c.get(); a[ADD as usize]=u64::MAX; c.set(a); });
        success(&mut Mock::new(),ADD); assert_eq!(sb_net_dynamic_count(0,ADD),0);
        let atomic = AtomicU64::new(u64::MAX); atomic.fetch_add(1,Ordering::Relaxed);
        assert_eq!(atomic.load(Ordering::Relaxed),0);
        assert_eq!(barrier(|| panic!("ordinary Rust panic, not an extern callback")),PANIC);
        assert_eq!(sb_net_dynamic_count(3,0),0); assert_eq!(sb_net_dynamic_count(0,10),0);
        assert_eq!(sb_net_dynamic_count(1,10),0); assert_eq!(sb_net_dynamic_count(2,26),0);
        assert_eq!(std::mem::size_of::<SbNetDynamicReply>(),16);
        assert_eq!(std::mem::align_of::<SbNetDynamicReply>(),8);
    }
}
