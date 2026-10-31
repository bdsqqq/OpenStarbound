//! Basic-field policy only; typed values, lifetimes and all FP stay native.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST_ERROR: u32 = 2;
const PANIC: u32 = 3;
const SET: u32 = 0;
const PUSH: u32 = 1;
const UPDATE: u32 = 2;
const ENABLE: u32 = 3;
const DISABLE: u32 = 4;
const TICK: u32 = 5;
const STORE: u32 = 6;
const LOAD: u32 = 7;
const WRITE: u32 = 8;
const READ: u32 = 9;
const COUNT: usize = 10;
const CHANGED: u32 = 0;
const PUSH_COPY: u32 = 1;
const ASSIGN_PUSH: u32 = 2;
const UPDATED: u32 = 3;
const SET_LATEST: u32 = 4;
const HAS_PENDING: u32 = 5;
const CLEAR_PENDING: u32 = 6;
const MUTATE: u32 = 7;
const EMPLACE_PENDING: u32 = 8;
const PENDING_NONEMPTY: u32 = 9;
const ASSIGN_LAST: u32 = 10;
const RESET_PENDING: u32 = 11;
const ENTER_RANGE: u32 = 12;
const MORE: u32 = 13;
const DECREMENT: u32 = 14;
const ADVANCE: u32 = 15;
const LEAVE_RANGE: u32 = 16;
const NEXT_READY: u32 = 17;
const ASSIGN_FIRST: u32 = 18;
const WRITE_LAST: u32 = 19;
const WRITE_VALUE: u32 = 20;
const READ_VALUE: u32 = 21;
const LATEST_VERSION: u32 = 22;
const READ_INCOMING: u32 = 23;
const ACCEPT_DELAY: u32 = 24;
const APPEND_INCOMING: u32 = 25;
const ASSIGN_INCOMING: u32 = 26;
const LAST_AVAILABLE: u32 = 27;
const OP_COUNT: usize = 28;

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct SbNetFieldReply { pub a: u64, pub b: u64 }
pub type Host = unsafe extern "C" fn(*mut c_void, u32, u64, *mut SbNetFieldReply) -> u32;
static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static LEAVES: [AtomicU64; OP_COUNT] = [const { AtomicU64::new(0) }; OP_COUNT];
thread_local! {
    static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) };
}

fn boolean(op: u32) -> bool {
    matches!(op, CHANGED | HAS_PENDING | MUTATE | PENDING_NONEMPTY | MORE
        | NEXT_READY | ACCEPT_DELAY | LAST_AVAILABLE)
}

fn valid_reply(op: u32, r: SbNetFieldReply) -> bool {
    r.b == 0 && if boolean(op) { r.a <= 1 } else { op == LATEST_VERSION || r.a == 0 }
}

unsafe fn invoke(ctx: *mut c_void, host: Host, op: u32) -> Result<SbNetFieldReply, u32> {
    let mut reply = SbNetFieldReply::default();
    LEAVES[op as usize].fetch_add(1, Ordering::Relaxed);
    match host(ctx, op, 0, &mut reply) {
        OK if valid_reply(op, reply) => Ok(reply),
        OK => Err(INVALID),
        HOST_ERROR => Err(HOST_ERROR),
        _ => Err(INVALID),
    }
}

unsafe fn clear_if_pending(ctx: *mut c_void, host: Host) -> Result<(), u32> {
    if invoke(ctx, host, HAS_PENDING)?.a != 0 {
        invoke(ctx, host, CLEAR_PENDING)?;
    }
    Ok(())
}

unsafe fn store(ctx: *mut c_void, host: Host) -> Result<(), u32> {
    let op = if invoke(ctx, host, LAST_AVAILABLE)?.a != 0 { WRITE_LAST } else { WRITE_VALUE };
    invoke(ctx, host, op)?;
    Ok(())
}

unsafe fn run(mode: u32, ctx: *mut c_void, host: Host, from_version: u64) -> Result<u32, u32> {
    match mode {
        SET => {
            if invoke(ctx, host, CHANGED)?.a != 0 { invoke(ctx, host, PUSH_COPY)?; }
        }
        PUSH | UPDATE => {
            if mode == PUSH { invoke(ctx, host, ASSIGN_PUSH)?; }
            else if invoke(ctx, host, MUTATE)?.a == 0 { return Ok(0); }
            invoke(ctx, host, UPDATED)?;
            // The virtual hook may change BOTH version source and pending state.
            invoke(ctx, host, SET_LATEST)?;
            clear_if_pending(ctx, host)?;
        }
        ENABLE => {
            if invoke(ctx, host, HAS_PENDING)?.a == 0 { invoke(ctx, host, EMPLACE_PENDING)?; }
        }
        DISABLE => {
            if invoke(ctx, host, HAS_PENDING)?.a != 0 {
                if invoke(ctx, host, PENDING_NONEMPTY)?.a != 0 { invoke(ctx, host, ASSIGN_LAST)?; }
                invoke(ctx, host, RESET_PENDING)?;
            }
        }
        TICK => {
            if invoke(ctx, host, HAS_PENDING)?.a != 0 {
                invoke(ctx, host, ENTER_RANGE)?;
                while invoke(ctx, host, MORE)?.a != 0 {
                    invoke(ctx, host, DECREMENT)?;
                    invoke(ctx, host, ADVANCE)?;
                }
                invoke(ctx, host, LEAVE_RANGE)?;
                // No engaged recheck after UPDATED: preserve original native contract.
                while invoke(ctx, host, NEXT_READY)?.a != 0 {
                    invoke(ctx, host, ASSIGN_FIRST)?;
                    invoke(ctx, host, UPDATED)?;
                }
            }
        }
        STORE => store(ctx, host)?,
        LOAD => {
            invoke(ctx, host, READ_VALUE)?;
            // Unlike PUSH, loading captures version BEFORE the virtual hook.
            invoke(ctx, host, SET_LATEST)?;
            invoke(ctx, host, UPDATED)?;
            clear_if_pending(ctx, host)?;
        }
        WRITE => {
            if invoke(ctx, host, LATEST_VERSION)?.a < from_version { return Ok(0); }
            store(ctx, host)?;
            return Ok(1);
        }
        READ => {
            invoke(ctx, host, READ_INCOMING)?;
            invoke(ctx, host, SET_LATEST)?;
            if invoke(ctx, host, HAS_PENDING)?.a != 0 {
                if invoke(ctx, host, ACCEPT_DELAY)?.a != 0 {
                    invoke(ctx, host, APPEND_INCOMING)?;
                } else {
                    invoke(ctx, host, ASSIGN_INCOMING)?;
                    invoke(ctx, host, CLEAR_PENDING)?;
                    invoke(ctx, host, UPDATED)?;
                }
            } else {
                invoke(ctx, host, ASSIGN_INCOMING)?;
                invoke(ctx, host, UPDATED)?;
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
/// Follow StarRustNetField.h: live native context/output, non-unwinding host,
/// and valid native captures through synchronous reentry. Context stays opaque.
#[no_mangle]
pub unsafe extern "C" fn sb_net_field_run(
    mode: u32, ctx: *mut c_void, host: Option<Host>, from_version: u64, out_written: *mut u32,
) -> u32 {
    if mode >= COUNT as u32 || ctx.is_null() || host.is_none() || out_written.is_null()
        || (out_written as usize) % std::mem::align_of::<u32>() != 0
        || (mode != WRITE && from_version != 0) { return INVALID; }
    barrier(|| {
        TOTALS[mode as usize].fetch_add(1, Ordering::Relaxed);
        COUNTS.with(|cell| {
            let mut counts = cell.get();
            counts[mode as usize] = counts[mode as usize].wrapping_add(1);
            cell.set(counts);
        });
        match run(mode, ctx, host.unwrap(), from_version) {
            Ok(written) => { out_written.write(written); OK }
            Err(status) => status,
        }
    })
}

/// Wrapping diagnostics, not synchronized completion observations.
#[no_mangle]
pub extern "C" fn sb_net_field_count(kind: u32, index: u32) -> u64 {
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
        value: i64, input: i64, incoming: i64, version: u64, latest: u64,
        pending: Option<VecDeque<(i64, i64)>>, delay: i64, dt: i64,
        mutate: bool, updated: usize, hook: u32, pop_fail: bool,
        index: usize, end: usize, active: bool, stream: Vec<i64>,
        seen: Vec<(u32, u64)>, fault: Option<(usize, u32, SbNetFieldReply)>,
    }
    impl Mock {
        fn new() -> Self {
            Self { value: 10, input: 40, incoming: 0, version: 7, latest: 7,
                pending: Some([(1,20),(0,30),(3,35)].into_iter().collect()),
                delay: 4, dt: 1, mutate: true, updated: 0, hook: 0, pop_fail: false,
                index: 0, end: 0, active: false, stream: vec![], seen: vec![], fault: None }
        }
        fn call(&mut self, mode: u32, from: u64, out: &mut u32) -> u32 {
            unsafe { sb_net_field_run(mode, self as *mut _ as _, Some(host), from, out) }
        }
        fn ops(&self) -> Vec<u32> { self.seen.iter().map(|p| p.0).collect() }
        fn pending_values(&self) -> Vec<(i64,i64)> {
            self.pending.as_ref().map(|p| p.iter().copied().collect()).unwrap_or_default()
        }
    }

    // Integer times characterize policy order only, NOT native FP behavior.
    // No assertions or panics may escape this extern C fixture callback.
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, arg: u64, out: *mut SbNetFieldReply) -> u32 {
        // PUSH_COPY reenters only after releasing this temporary mutable borrow.
        {
            let m = &mut *(ctx as *mut Mock);
            let at = m.seen.len(); m.seen.push((op,arg));
            let initial = out.read();
            if arg != 0 || initial.a != 0 || initial.b != 0 { return INVALID; }
            if let Some((i,status,reply)) = m.fault {
                if at == i { out.write(reply); return status; }
            }
        }
        if op == PUSH_COPY {
            let mut ignored = 87;
            return sb_net_field_run(PUSH,ctx,Some(host),0,&mut ignored);
        }
        let m = &mut *(ctx as *mut Mock);
        let mut r = SbNetFieldReply::default();
        match op {
            CHANGED => r.a = u64::from(m.value != m.input),
            ASSIGN_PUSH => m.value = m.input,
            UPDATED => {
                m.updated += 1;
                match m.hook {
                    1 => { m.version = 99; m.pending = Some([(9,90)].into_iter().collect()); }
                    2 => { m.version = 99; m.pending = None; }
                    3 if m.updated == 1 => {
                        // A valid native hook can append a newly due value after range exit.
                        if let Some(p) = &mut m.pending { p.push_back((0,90)); }
                    }
                    _ => {}
                }
            }
            SET_LATEST => m.latest = m.version,
            HAS_PENDING => r.a = u64::from(m.pending.is_some()),
            CLEAR_PENDING => match &mut m.pending { Some(p) => p.clear(), None => return INVALID },
            MUTATE => { m.value += 1; r.a = u64::from(m.mutate); }
            EMPLACE_PENDING if m.pending.is_none() => m.pending = Some(VecDeque::new()),
            PENDING_NONEMPTY => match &m.pending {
                Some(p) => r.a = u64::from(!p.is_empty()), None => return INVALID,
            },
            ASSIGN_LAST | ASSIGN_FIRST => {
                let item = match &mut m.pending {
                    Some(p) if op == ASSIGN_LAST => p.pop_back(),
                    Some(p) => p.pop_front(), None => return INVALID,
                };
                let Some((_,value)) = item else { return INVALID; };
                // Native takeFirst/takeLast happens before a throwing T assignment.
                if m.pop_fail { return HOST_ERROR; }
                m.value = value;
            }
            RESET_PENDING => m.pending = None,
            ENTER_RANGE if !m.active => {
                let Some(p) = &m.pending else { return INVALID; };
                m.index = 0; m.end = p.len(); m.active = true;
            }
            MORE if m.active => r.a = u64::from(m.index < m.end),
            DECREMENT if m.active => {
                let Some(p) = &mut m.pending else { return INVALID; };
                let Some(item) = p.get_mut(m.index) else { return INVALID; };
                item.0 -= m.dt;
            }
            ADVANCE if m.active && m.index < m.end => m.index += 1,
            LEAVE_RANGE if m.active => m.active = false,
            NEXT_READY if !m.active => match &m.pending {
                Some(p) => r.a = u64::from(p.front().is_some_and(|p| p.0 <= 0)),
                // Diagnostic only: a native disengaged dereference is NOT repaired.
                None => return HOST_ERROR,
            },
            WRITE_LAST => match &m.pending {
                Some(p) => match p.back() { Some(p) => m.stream.push(p.1), None => return INVALID },
                None => return INVALID,
            },
            WRITE_VALUE => m.stream.push(m.value),
            READ_VALUE => m.value = m.input,
            LATEST_VERSION => r.a = m.latest,
            READ_INCOMING => m.incoming = m.input,
            ACCEPT_DELAY => match &m.pending {
                Some(p) => r.a = u64::from(m.delay > 0 && p.back().map_or(true, |p| m.delay >= p.0)),
                None => return INVALID,
            },
            APPEND_INCOMING => match &mut m.pending {
                Some(p) => p.push_back((m.delay,m.incoming)), None => return INVALID,
            },
            ASSIGN_INCOMING => m.value = m.incoming,
            LAST_AVAILABLE => r.a = u64::from(m.pending.as_ref().is_some_and(|p| !p.is_empty())),
            _ => return INVALID,
        }
        out.write(r); OK
    }

    // These 26 scenarios cover every root and all branch outcomes. Fault tests
    // replay each trace, including nested PUSH, without duplicating setup logic.
    fn scenarios() -> Vec<(u32,u64,Mock,Vec<u32>,u32)> {
        let mut cases = vec![];
        let mut add = |mode,from,m,ops: &[u32],written| cases.push((mode,from,m,ops.to_vec(),written));
        let n = Mock::new;
        let mut m = n(); m.input = m.value;
        add(SET,0,m,&[CHANGED],0);
        add(SET,0,n(),&[CHANGED,PUSH_COPY,ASSIGN_PUSH,UPDATED,SET_LATEST,HAS_PENDING,CLEAR_PENDING],0);
        add(PUSH,0,n(),&[ASSIGN_PUSH,UPDATED,SET_LATEST,HAS_PENDING,CLEAR_PENDING],0);
        let mut m = n(); m.pending = None;
        add(PUSH,0,m,&[ASSIGN_PUSH,UPDATED,SET_LATEST,HAS_PENDING],0);
        let mut m = n(); m.mutate = false;
        add(UPDATE,0,m,&[MUTATE],0);
        add(UPDATE,0,n(),&[MUTATE,UPDATED,SET_LATEST,HAS_PENDING,CLEAR_PENDING],0);
        let mut m = n(); m.pending = None;
        add(UPDATE,0,m,&[MUTATE,UPDATED,SET_LATEST,HAS_PENDING],0);
        add(ENABLE,0,n(),&[HAS_PENDING],0);
        let mut m = n(); m.pending = None;
        add(ENABLE,0,m,&[HAS_PENDING,EMPLACE_PENDING],0);
        let mut m = n(); m.pending = None;
        add(DISABLE,0,m,&[HAS_PENDING],0);
        let mut m = n(); m.pending = Some(VecDeque::new());
        add(DISABLE,0,m,&[HAS_PENDING,PENDING_NONEMPTY,RESET_PENDING],0);
        add(DISABLE,0,n(),&[HAS_PENDING,PENDING_NONEMPTY,ASSIGN_LAST,RESET_PENDING],0);
        let mut m = n(); m.pending = None;
        add(TICK,0,m,&[HAS_PENDING],0);
        let mut m = n(); m.pending = Some(VecDeque::new());
        add(TICK,0,m,&[HAS_PENDING,ENTER_RANGE,MORE,LEAVE_RANGE,NEXT_READY],0);
        add(TICK,0,n(),&[HAS_PENDING,ENTER_RANGE,MORE,DECREMENT,ADVANCE,MORE,DECREMENT,
            ADVANCE,MORE,DECREMENT,ADVANCE,MORE,LEAVE_RANGE,NEXT_READY,ASSIGN_FIRST,
            UPDATED,NEXT_READY,ASSIGN_FIRST,UPDATED,NEXT_READY],0);
        let mut m = n(); m.pending = None;
        add(STORE,0,m,&[LAST_AVAILABLE,WRITE_VALUE],0);
        let mut m = n(); m.pending = Some(VecDeque::new());
        add(STORE,0,m,&[LAST_AVAILABLE,WRITE_VALUE],0);
        add(STORE,0,n(),&[LAST_AVAILABLE,WRITE_LAST],0);
        add(LOAD,0,n(),&[READ_VALUE,SET_LATEST,UPDATED,HAS_PENDING,CLEAR_PENDING],0);
        let mut m = n(); m.pending = None;
        add(LOAD,0,m,&[READ_VALUE,SET_LATEST,UPDATED,HAS_PENDING],0);
        add(WRITE,8,n(),&[LATEST_VERSION],0);
        add(WRITE,7,n(),&[LATEST_VERSION,LAST_AVAILABLE,WRITE_LAST],1);
        let mut m = n(); m.pending = None; m.latest = u64::MAX;
        add(WRITE,u64::MAX,m,&[LATEST_VERSION,LAST_AVAILABLE,WRITE_VALUE],1);
        add(READ,0,n(),&[READ_INCOMING,SET_LATEST,HAS_PENDING,ACCEPT_DELAY,APPEND_INCOMING],0);
        let mut m = n(); m.delay = 2;
        add(READ,0,m,&[READ_INCOMING,SET_LATEST,HAS_PENDING,ACCEPT_DELAY,ASSIGN_INCOMING,CLEAR_PENDING,UPDATED],0);
        let mut m = n(); m.pending = None;
        add(READ,0,m,&[READ_INCOMING,SET_LATEST,HAS_PENDING,ASSIGN_INCOMING,UPDATED],0);
        cases
    }

    #[test]
    fn prescribed_orders_and_stateful_results() {
        let cases = scenarios();
        assert_eq!(cases.len(),26);
        for (mode,from,mut m,ops,written) in cases {
            let initial = m.clone(); let mut out = 87;
            assert_eq!(m.call(mode,from,&mut out),OK,"mode {mode}");
            assert_eq!(out,written); assert_eq!(m.ops(),ops,"mode {mode}");
            assert!(m.seen.iter().all(|p| p.1 == 0));
            match mode {
                SET | PUSH if initial.input != initial.value || mode == PUSH => {
                    assert_eq!(m.value,40); assert_eq!(m.updated,1);
                    assert_eq!(m.latest,7); assert!(m.pending_values().is_empty());
                }
                UPDATE => {
                    assert_eq!(m.value,11); assert_eq!(m.updated,usize::from(initial.mutate));
                    if initial.mutate { assert!(m.pending_values().is_empty()); }
                    else { assert_eq!(m.pending_values(),initial.pending_values()); }
                }
                ENABLE => { assert!(m.pending.is_some()); assert_eq!(m.updated,0); }
                DISABLE => {
                    assert!(m.pending.is_none()); assert_eq!(m.updated,0); assert_eq!(m.latest,7);
                    assert_eq!(m.value,initial.pending.as_ref().and_then(|p| p.back()).map_or(10,|p|p.1));
                }
                TICK if !initial.pending_values().is_empty() => {
                    assert_eq!(m.value,30); assert_eq!(m.updated,2);
                    assert_eq!(m.pending_values(),[(2,35)]); assert!(!m.active);
                }
                STORE | WRITE if mode == STORE || written == 1 => {
                    assert_eq!(m.stream,[if ops.contains(&WRITE_LAST) {35} else {10}]);
                    assert_eq!(m.pending_values(),initial.pending_values());
                }
                LOAD => { assert_eq!(m.value,40); assert_eq!(m.updated,1); assert_eq!(m.latest,7); }
                READ => {
                    assert_eq!(m.latest,7);
                    if ops.contains(&APPEND_INCOMING) {
                        assert_eq!(m.value,10); assert_eq!(m.updated,0);
                        assert_eq!(m.pending.as_ref().and_then(|p| p.back()),Some(&(4,40)));
                    } else { assert_eq!(m.value,40); assert_eq!(m.updated,1); assert!(m.pending_values().is_empty()); }
                }
                _ => {}
            }
        }
    }

    #[test]
    fn every_reachable_leaf_failure_stops_without_output_or_repair() {
        let mut reached = [false; OP_COUNT];
        for (mode,from,initial,ops,_) in scenarios() {
            let mut baseline = initial.clone(); let mut out = 87;
            assert_eq!(baseline.call(mode,from,&mut out),OK);
            for (at,&op) in ops.iter().enumerate() {
                reached[op as usize] = true;
                let mut faults = vec![(HOST_ERROR,0,0,HOST_ERROR),
                    (HOST_ERROR,u64::MAX,u64::MAX,HOST_ERROR),
                    (INVALID,0,0,INVALID),(PANIC,0,0,INVALID),(99,0,0,INVALID),
                    (OK,0,1,INVALID)];
                if op != LATEST_VERSION { faults.push((OK,if boolean(op) {2} else {1},0,INVALID)); }
                for (status,a,b,expected) in faults {
                    let mut m = initial.clone();
                    m.fault = Some((at,status,SbNetFieldReply {a,b})); out = 87;
                    assert_eq!(m.call(mode,from,&mut out),expected,"mode {mode} leaf {op} at {at}");
                    assert_eq!(out,87); assert_eq!(m.ops(),ops[..=at]);
                    assert!(m.seen.iter().all(|p| p.1 == 0));
                    // Every failure retains exactly the state produced by its successful
                    // prefix, not just its trace. Obtain that prefix with HOST_ERROR.
                    let mut prefix = initial.clone(); let mut ignored = 87;
                    prefix.fault = Some((at,HOST_ERROR,SbNetFieldReply::default()));
                    assert_eq!(prefix.call(mode,from,&mut ignored),HOST_ERROR);
                    assert_eq!((m.value,m.version,m.latest,m.updated,m.active,m.index,m.end),
                        (prefix.value,prefix.version,prefix.latest,prefix.updated,prefix.active,prefix.index,prefix.end));
                    assert_eq!(m.pending,prefix.pending); assert_eq!(m.stream,prefix.stream);
                    assert_eq!(m.incoming,prefix.incoming);
                }
            }
        }
        assert!(reached.iter().all(|b| *b));
    }

    #[test]
    fn virtual_updated_changes_version_and_pending_without_cached_queries() {
        for mode in [PUSH,UPDATE,LOAD] {
            for hook in [1,2] {
                let mut m = Mock::new(); m.pending = None; m.hook = hook; let mut out = 87;
                assert_eq!(m.call(mode,0,&mut out),OK);
                assert_eq!(m.version,99); assert_eq!(m.latest,if mode == LOAD {7} else {99});
                assert_eq!(m.pending,if hook == 1 {Some(VecDeque::new())} else {None});
                assert_eq!(m.ops().last(),Some(&if hook == 1 {CLEAR_PENDING} else {HAS_PENDING}));
            }
        }
        // READ immediate clears BEFORE its hook, so hook's new pending survives.
        let mut m = Mock::new(); m.delay = 0; m.hook = 1; let mut out = 87;
        assert_eq!(m.call(READ,0,&mut out),OK);
        assert_eq!(m.latest,7); assert_eq!(m.version,99); assert_eq!(m.pending_values(),[(9,90)]);
    }

    #[test]
    fn delay_predicate_branches_and_fifo_tick_two_phases() {
        let mut out = 87;
        for (queue,delay,accepted) in [
            (vec![],1,true),(vec![],0,false),(vec![],-1,false),
            (vec![(3,20)],2,false),(vec![(3,20)],3,true),(vec![(3,20)],4,true),
        ] {
            let mut m = Mock::new(); m.pending = Some(queue.into_iter().collect()); m.delay = delay;
            assert_eq!(m.call(READ,0,&mut out),OK);
            assert_eq!(m.ops().contains(&APPEND_INCOMING),accepted);
            assert_eq!(m.updated,if accepted {0} else {1});
        }
        // Unsorted timers retain FIFO; a later ready entry cannot leap the front.
        let mut m = Mock::new(); m.pending = Some([(3,20),(0,30)].into_iter().collect());
        assert_eq!(m.call(TICK,0,&mut out),OK); assert_eq!(m.updated,0);
        assert_eq!(m.pending_values(),[(2,20),(-1,30)]);
        // A hook appends after the decrement range: the fresh ready guard sees it.
        let mut m = Mock::new(); m.pending = Some([(1,20)].into_iter().collect()); m.hook = 3;
        assert_eq!(m.call(TICK,0,&mut out),OK); assert_eq!(m.value,90); assert_eq!(m.updated,2);
        assert!(m.pending_values().is_empty());
        assert_eq!(m.ops(),[HAS_PENDING,ENTER_RANGE,MORE,DECREMENT,ADVANCE,MORE,LEAVE_RANGE,
            NEXT_READY,ASSIGN_FIRST,UPDATED,NEXT_READY,ASSIGN_FIRST,UPDATED,NEXT_READY]);
        // Do not add HAS_PENDING after a hook disengages pending. The mock returns
        // HOST_ERROR to observe the attempted original guard, not native UB proof.
        let mut m = Mock::new(); m.hook = 2; out = 87;
        assert_eq!(m.call(TICK,0,&mut out),HOST_ERROR); assert_eq!(out,87);
        assert_eq!(&m.ops()[m.seen.len()-3..],[ASSIGN_FIRST,UPDATED,NEXT_READY]);
    }

    #[test]
    fn partial_mutations_and_pop_before_failed_assignment_are_retained() {
        let mut out = 87;
        for mode in [DISABLE,TICK] {
            let mut m = Mock::new(); m.pop_fail = true;
            assert_eq!(m.call(mode,0,&mut out),HOST_ERROR); assert_eq!(out,87);
            assert_eq!(m.value,10); assert_eq!(m.updated,0); assert_eq!(m.latest,7);
            assert_eq!(m.pending_values(),if mode == DISABLE {vec![(1,20),(0,30)]} else {vec![(-1,30),(2,35)]});
            assert_eq!(m.ops().last(),Some(&if mode == DISABLE {ASSIGN_LAST} else {ASSIGN_FIRST}));
            assert!(m.pending.is_some());
        }
        let mut m = Mock::new(); m.latest = 2;
        m.fault = Some((2,HOST_ERROR,SbNetFieldReply::default()));
        assert_eq!(m.call(PUSH,0,&mut out),HOST_ERROR);
        assert_eq!(m.value,40); assert_eq!(m.updated,1); assert_eq!(m.latest,2);
        assert_eq!(m.pending_values(),Mock::new().pending_values());
        let mut m = Mock::new(); m.latest = 2;
        m.fault = Some((2,HOST_ERROR,SbNetFieldReply::default()));
        assert_eq!(m.call(LOAD,0,&mut out),HOST_ERROR);
        assert_eq!(m.value,40); assert_eq!(m.latest,7); assert_eq!(m.updated,0);
        // A failed virtual update on the second tick emission keeps both pops,
        // the first notification, and ALL already decremented remaining timers.
        let mut m = Mock::new();
        m.fault = Some((18,HOST_ERROR,SbNetFieldReply::default()));
        assert_eq!(m.call(TICK,0,&mut out),HOST_ERROR);
        assert_eq!(m.value,30); assert_eq!(m.updated,1); assert_eq!(m.pending_values(),[(2,35)]);
    }

    #[test]
    fn abi_reply_domains_entry_denials_and_plain_rust_panic() {
        assert_eq!(std::mem::size_of::<SbNetFieldReply>(),16);
        assert_eq!(std::mem::align_of::<SbNetFieldReply>(),8);
        for op in 0..OP_COUNT as u32 { for a in [0,1,2,u64::MAX] { for b in [0,1,u64::MAX] {
            let expected = b == 0 && match op {
                CHANGED | HAS_PENDING | MUTATE | PENDING_NONEMPTY | MORE | NEXT_READY | ACCEPT_DELAY | LAST_AVAILABLE => a <= 1,
                LATEST_VERSION => true, _ => a == 0,
            };
            assert_eq!(valid_reply(op,SbNetFieldReply {a,b}),expected);
        }}}
        let mut m = Mock::new(); let mut out = 87;
        let ctx = &mut m as *mut _ as *mut c_void;
        let before = COUNTS.with(Cell::get);
        for mode in 0..COUNT as u32 {
            let mut storage = [0x5au32;2];
            unsafe {
                let misaligned = (storage.as_mut_ptr() as *mut u8).add(1) as *mut u32;
                for (c,h,o) in [(std::ptr::null_mut(),Some(host as Host),&mut out as *mut u32),
                    (ctx,None,&mut out),(ctx,Some(host as Host),std::ptr::null_mut()),
                    (ctx,Some(host as Host),misaligned)] {
                    assert_eq!(sb_net_field_run(mode,c,h,0,o),INVALID);
                }
                if mode != WRITE { for from in [1,u64::MAX] {
                    assert_eq!(sb_net_field_run(mode,ctx,Some(host),from,&mut out),INVALID);
                }}
            }
            assert_eq!(storage,[0x5a;2]);
        }
        for mode in [COUNT as u32,u32::MAX] {
            assert_eq!(m.call(mode,0,&mut out),INVALID);
        }
        assert_eq!(out,87); assert!(m.seen.is_empty()); assert_eq!(COUNTS.with(Cell::get),before);
        for from in [0,1,u64::MAX] {
            let mut m = Mock::new(); m.latest = u64::MAX;
            assert_eq!(m.call(WRITE,from,&mut out),OK); assert_eq!(out,1);
        }
        let mut untouched = 87;
        assert_eq!(barrier(|| { assert!(false, "plain Rust panic; never callback unwind"); untouched = 0; OK }),PANIC);
        assert_eq!(untouched,87);
    }

    #[test]
    fn wrapping_counter_banks_observe_attempts_not_completion() {
        std::thread::spawn(|| {
            COUNTS.with(|c| { let mut a = [0; COUNT]; a[PUSH as usize] = u64::MAX; c.set(a); });
            let root = sb_net_field_count(1,PUSH); let leaf = sb_net_field_count(2,ASSIGN_PUSH);
            let mut m = Mock::new(); let mut out = 87;
            m.fault = Some((0,HOST_ERROR,SbNetFieldReply::default()));
            assert_eq!(m.call(PUSH,0,&mut out),HOST_ERROR); assert_eq!(out,87);
            assert_eq!(sb_net_field_count(0,PUSH),0);
            assert!(sb_net_field_count(1,PUSH).wrapping_sub(root) >= 1);
            assert!(sb_net_field_count(2,ASSIGN_PUSH).wrapping_sub(leaf) >= 1);
            std::thread::spawn(move || {
                assert_eq!(sb_net_field_count(0,PUSH),0);
                assert!(sb_net_field_count(1,PUSH).wrapping_sub(root) >= 1);
                assert!(sb_net_field_count(2,ASSIGN_PUSH).wrapping_sub(leaf) >= 1);
            }).join().unwrap();
            let atomic = AtomicU64::new(u64::MAX);
            atomic.fetch_add(1,Ordering::Relaxed); assert_eq!(atomic.load(Ordering::Relaxed),0);
            for (mode,from,mut m,_,_) in scenarios() {
                let before = sb_net_field_count(0,mode);
                assert_eq!(m.call(mode,from,&mut out),OK);
                assert_eq!(sb_net_field_count(0,mode),before.wrapping_add(1));
            }
            for (kind,index) in [(0,COUNT as u32),(1,COUNT as u32),(2,OP_COUNT as u32),
                (3,0),(u32::MAX,u32::MAX)] { assert_eq!(sb_net_field_count(kind,index),0); }
        }).join().unwrap();
    }
}
