//! NetElementSignal policy only; native frames retain signals, ranges and streams.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST_ERROR: u32 = 2;
const PANIC: u32 = 3;
const SEND: u32 = 0;
const RECEIVE: u32 = 1;
const WRITE: u32 = 2;
const COUNT: usize = 3;
const APPEND_SIGNAL: u32 = 0;
const QUEUE_LIMIT: u32 = 1;
const POP_FRONT: u32 = 2;
const ENTER_RANGE: u32 = 3;
const MORE: u32 = 4;
const RECEIVED: u32 = 5;
const APPEND_RECEIVED: u32 = 6;
const MARK_RECEIVED: u32 = 7;
const ADVANCE: u32 = 8;
const LEAVE_RANGE: u32 = 9;
const WRITE_HEADER: u32 = 10;
const WRITE_SIGNAL: u32 = 11;
const VERSION: u32 = 12;
const OP_COUNT: usize = 13;

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct SbNetSignalReply { pub a: u64, pub b: u64 }
pub type Host = unsafe extern "C" fn(*mut c_void, u32, u64, *mut SbNetSignalReply) -> u32;
static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static LEAVES: [AtomicU64; OP_COUNT] = [const { AtomicU64::new(0) }; OP_COUNT];
thread_local! {
    static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) };
}

fn valid_reply(op: u32, r: SbNetSignalReply) -> bool {
    match op {
        QUEUE_LIMIT => true,
        MORE | RECEIVED => r.a <= 1 && r.b == 0,
        VERSION => r.b == 0,
        _ => r.a == 0 && r.b == 0,
    }
}

unsafe fn invoke(ctx: *mut c_void, host: Host, op: u32, argument: u64) -> Result<SbNetSignalReply, u32> {
    let mut reply = SbNetSignalReply::default();
    LEAVES[op as usize].fetch_add(1, Ordering::Relaxed);
    match host(ctx, op, argument, &mut reply) {
        OK if valid_reply(op, reply) => Ok(reply),
        OK => Err(INVALID),
        HOST_ERROR => Err(HOST_ERROR),
        _ => Err(INVALID),
    }
}

unsafe fn run(mode: u32, ctx: *mut c_void, host: Host, from_version: u64) -> Result<u32, u32> {
    if mode == SEND {
        invoke(ctx, host, APPEND_SIGNAL, 0)?;
        loop {
            // Destruction in POP_FRONT may reenter and change the native cap.
            let limit = invoke(ctx, host, QUEUE_LIMIT, 0)?;
            if limit.a <= limit.b { break; }
            invoke(ctx, host, POP_FRONT, 0)?;
        }
    } else if mode == RECEIVE {
        invoke(ctx, host, ENTER_RANGE, 0)?;
        while invoke(ctx, host, MORE, 0)?.a != 0 {
            if invoke(ctx, host, RECEIVED, 0)?.a == 0 {
                invoke(ctx, host, APPEND_RECEIVED, 0)?;
                invoke(ctx, host, MARK_RECEIVED, 0)?;
            }
            invoke(ctx, host, ADVANCE, 0)?;
        }
        invoke(ctx, host, LEAVE_RANGE, 0)?;
    } else {
        let mut count = 0usize;
        invoke(ctx, host, ENTER_RANGE, 0)?;
        while invoke(ctx, host, MORE, 0)?.a != 0 {
            if invoke(ctx, host, VERSION, 0)?.a >= from_version {
                count = count.wrapping_add(1);
            }
            invoke(ctx, host, ADVANCE, 0)?;
        }
        invoke(ctx, host, LEAVE_RANGE, 0)?;
        if count == 0 { return Ok(0); }
        invoke(ctx, host, WRITE_HEADER, count as u64)?;
        // The second cached native end is initialized only AFTER the header.
        invoke(ctx, host, ENTER_RANGE, 0)?;
        while invoke(ctx, host, MORE, 0)?.a != 0 {
            if invoke(ctx, host, VERSION, 0)?.a >= from_version {
                invoke(ctx, host, WRITE_SIGNAL, 0)?;
            }
            invoke(ctx, host, ADVANCE, 0)?;
        }
        invoke(ctx, host, LEAVE_RANGE, 0)?;
        return Ok(1);
    }
    Ok(0)
}

fn barrier(f: impl FnOnce() -> u32) -> u32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(PANIC)
}

/// # Safety
/// Follow StarRustNetSignal.h: live native context, non-unwinding callback and
/// live aligned writable output, all preserved through synchronous reentry.
#[no_mangle]
pub unsafe extern "C" fn sb_net_signal_run(
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
pub extern "C" fn sb_net_signal_count(kind: u32, index: u32) -> u64 {
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

    struct Mock {
        queue: VecDeque<(u64, bool)>, cap: u64, pop_cap: Option<u64>,
        index: usize, end: usize, active: bool, copies: Vec<u64>, stream: Vec<u64>,
        seen: Vec<(u32, u64)>, fault: Option<(usize, u32, SbNetSignalReply)>,
        header_append: bool,
    }
    impl Mock {
        fn new(versions: &[u64]) -> Self {
            Self { queue: versions.iter().map(|v| (*v, false)).collect(), cap: 32,
                pop_cap: None, index: 0, end: 0, active: false, copies: vec![],
                stream: vec![], seen: vec![], fault: None, header_append: false }
        }
        fn call(&mut self, mode: u32, version: u64, out: &mut u32) -> u32 {
            unsafe { sb_net_signal_run(mode, self as *mut _ as _, Some(host), version, out) }
        }
    }
    // No assertions/panics through extern C; protocol violations return INVALID.
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, arg: u64, out: *mut SbNetSignalReply) -> u32 {
        let m = &mut *(ctx as *mut Mock);
        let at = m.seen.len();
        m.seen.push((op, arg));
        if let Some((i, status, reply)) = m.fault {
            if at == i { out.write(reply); return status; }
        }
        let mut r = SbNetSignalReply::default();
        if out.read().a != 0 || out.read().b != 0 || (op != WRITE_HEADER && arg != 0) { return INVALID; }
        match op {
            APPEND_SIGNAL => m.queue.push_back((42, false)),
            QUEUE_LIMIT => { r.a = m.queue.len() as u64; r.b = m.cap; }
            POP_FRONT => {
                if m.queue.pop_front().is_none() { return INVALID; }
                // Models a signal destructor changing the cap during native pop.
                if let Some(cap) = m.pop_cap.take() { m.cap = cap; }
            }
            ENTER_RANGE if !m.active => { m.active = true; m.index = 0; m.end = m.queue.len(); }
            MORE if m.active => r.a = u64::from(m.index < m.end),
            RECEIVED if m.active && m.index < m.end => r.a = u64::from(m.queue[m.index].1),
            APPEND_RECEIVED if m.active && m.index < m.end => m.copies.push(m.queue[m.index].0),
            MARK_RECEIVED if m.active && m.index < m.end => m.queue[m.index].1 = true,
            VERSION if m.active && m.index < m.end => r.a = m.queue[m.index].0,
            WRITE_SIGNAL if m.active && m.index < m.end => m.stream.push(m.queue[m.index].0),
            ADVANCE if m.active && m.index < m.end => m.index += 1,
            LEAVE_RANGE if m.active => m.active = false,
            WRITE_HEADER if !m.active => {
                m.stream.push(arg);
                if m.header_append { m.queue.push_back((u64::MAX, false)); }
            }
            _ => return INVALID,
        }
        out.write(r);
        OK
    }

    #[test]
    fn stateful_queue_receive_and_two_pass_write() {
        let mut out = 87;
        let mut m = Mock::new(&[1, 2, 3]);
        m.cap = 1; m.pop_cap = Some(3);
        assert_eq!(m.call(SEND, 0, &mut out), OK);
        assert_eq!(out, 0);
        assert_eq!(m.seen, [(APPEND_SIGNAL,0),(QUEUE_LIMIT,0),(POP_FRONT,0),(QUEUE_LIMIT,0)]);
        assert_eq!(m.queue.len(), 3);
        let mut m = Mock::new(&[1, 2, 3]);
        m.queue[0].1 = true;
        // Failing the third entry's copy preserves prior flags and copied prefix.
        m.fault = Some((11, HOST_ERROR, SbNetSignalReply::default()));
        out = 87;
        assert_eq!(m.call(RECEIVE, 0, &mut out), HOST_ERROR);
        assert_eq!(out, 87);
        assert_eq!(m.copies, [2]);
        assert_eq!(m.queue.iter().map(|p| p.1).collect::<Vec<_>>(), [true,true,false]);
        assert_eq!(m.seen.last(), Some(&(APPEND_RECEIVED,0)));
        let mut m = Mock::new(&[1,2]);
        m.queue[0].1 = true;
        assert_eq!(m.call(RECEIVE, 0, &mut out), OK);
        assert_eq!(out, 0); assert_eq!(m.copies, [2]);
        assert!(m.queue.iter().all(|p| p.1));
        assert!(!m.active);
        assert_eq!(m.call(RECEIVE, 0, &mut out), OK);
        assert_eq!(m.copies, [2]);
        for from in [0, 2, u64::MAX] {
            let mut m = Mock::new(&[0, 2, u64::MAX]);
            m.header_append = true;
            assert_eq!(m.call(WRITE, from, &mut out), OK);
            let eligible: Vec<_> = [0,2,u64::MAX].into_iter().filter(|v| *v >= from).collect();
            let mut expected = vec![eligible.len() as u64];
            expected.extend(eligible); expected.push(u64::MAX);
            assert_eq!(m.stream, expected);
            assert_eq!(out, 1);
            let h = m.seen.iter().position(|p| p.0 == WRITE_HEADER).unwrap();
            assert_eq!(m.seen[h-1].0, LEAVE_RANGE);
            assert_eq!(m.seen[h+1].0, ENTER_RANGE);
        }
        let mut m = Mock::new(&[0,1]);
        assert_eq!(m.call(WRITE, 2, &mut out), OK);
        assert_eq!(out, 0); assert!(m.stream.is_empty());
        assert_eq!(m.seen.iter().filter(|p| p.0 == ENTER_RANGE).count(), 1);
    }

    #[test]
    fn every_error_stops_at_attempt_without_output_or_rollback() {
        for (mode, from) in [(SEND,0),(RECEIVE,0),(WRITE,2)] {
            let mut baseline = Mock::new(&[1,2,u64::MAX]);
            baseline.cap = 1;
            let mut out = 87;
            assert_eq!(baseline.call(mode, from, &mut out), OK);
            for (at, &(op, _)) in baseline.seen.iter().enumerate() {
                let mut faults = vec![(HOST_ERROR,0,0,HOST_ERROR),(1,0,0,INVALID),
                    (3,0,0,INVALID),(99,0,0,INVALID),(HOST_ERROR,9,9,HOST_ERROR)];
                if op != QUEUE_LIMIT {
                    faults.push((OK,0,1,INVALID));
                    if op != VERSION {
                        faults.push((OK,if matches!(op, MORE | RECEIVED) {2} else {1},0,INVALID));
                    }
                }
                for (status,a,b,expected) in faults {
                    let mut m = Mock::new(&[1,2,u64::MAX]); m.cap = 1;
                    m.fault = Some((at,status,SbNetSignalReply {a,b})); out = 87;
                    assert_eq!(m.call(mode, from, &mut out), expected, "mode {mode} at {at}");
                    assert_eq!(out, 87);
                    assert_eq!(m.seen, baseline.seen[..=at]);
                    if op == WRITE_HEADER { assert!(m.stream.is_empty()); }
                    if op == WRITE_SIGNAL {
                        let prior = baseline.seen[..at].iter().filter(|p| p.0 == WRITE_SIGNAL).count();
                        assert_eq!(m.stream.len(), 1 + prior);
                    }
                }
            }
        }
    }

    #[test]
    fn reply_domains_abi_rejection_and_plain_rust_panic_barrier() {
        assert_eq!(std::mem::size_of::<SbNetSignalReply>(), 16);
        assert_eq!(std::mem::align_of::<SbNetSignalReply>(), 8);
        for op in 0..OP_COUNT as u32 {
            for a in [0,1,2,u64::MAX] { for b in [0,1,u64::MAX] {
                let expected = match op {
                    QUEUE_LIMIT => true, MORE | RECEIVED => a <= 1 && b == 0,
                    VERSION => b == 0, _ => a == 0 && b == 0,
                };
                assert_eq!(valid_reply(op, SbNetSignalReply {a,b}), expected);
            }}
        }
        let mut m = Mock::new(&[]); let ctx = &mut m as *mut _ as *mut c_void;
        let before = COUNTS.with(Cell::get);
        let mut out = 87; let mut storage = [0x5au32; 2];
        unsafe {
            let misaligned = (storage.as_mut_ptr() as *mut u8).add(1) as *mut u32;
            for (mode,c,h,v,o) in [
                (3,ctx,Some(host as Host),0,&mut out as *mut u32),
                (u32::MAX,ctx,Some(host as Host),0,&mut out),
                (SEND,std::ptr::null_mut(),Some(host as Host),0,&mut out),
                (SEND,ctx,None,0,&mut out), (SEND,ctx,Some(host as Host),1,&mut out),
                (RECEIVE,ctx,Some(host as Host),u64::MAX,&mut out),
                (WRITE,ctx,Some(host as Host),0,std::ptr::null_mut()),
                (WRITE,ctx,Some(host as Host),0,misaligned),
            ] { assert_eq!(sb_net_signal_run(mode,c,h,v,o), INVALID); }
        }
        assert_eq!(out,87); assert_eq!(storage,[0x5a;2]); assert!(m.seen.is_empty());
        assert_eq!(COUNTS.with(Cell::get),before);
        for (k,i) in [(0,3),(1,3),(2,13),(3,0),(u32::MAX,u32::MAX)] {
            assert_eq!(sb_net_signal_count(k,i),0);
        }
        let mut untouched = 87;
        assert_eq!(barrier(|| { assert!(false, "plain Rust panic, never a callback unwind"); untouched = 0; OK }), PANIC);
        assert_eq!(untouched,87);
    }

    #[test]
    fn counters_wrap_locally_and_observer_sees_attempts_without_global_reset() {
        std::thread::spawn(|| {
            COUNTS.with(|c| c.set([u64::MAX,0,0]));
            let global = sb_net_signal_count(1,SEND);
            let leaves = sb_net_signal_count(2,APPEND_SIGNAL);
            let mut m = Mock::new(&[]); let mut out = 87;
            m.fault = Some((0,HOST_ERROR,SbNetSignalReply::default()));
            assert_eq!(m.call(SEND,0,&mut out), HOST_ERROR);
            assert_eq!(out,87); assert_eq!(sb_net_signal_count(0,SEND),0);
            assert!(sb_net_signal_count(1,SEND).wrapping_sub(global) >= 1);
            assert!(sb_net_signal_count(2,APPEND_SIGNAL).wrapping_sub(leaves) >= 1);
            std::thread::spawn(move || {
                assert_eq!(sb_net_signal_count(0,SEND),0);
                assert!(sb_net_signal_count(1,SEND).wrapping_sub(global) >= 1);
                assert!(sb_net_signal_count(2,APPEND_SIGNAL).wrapping_sub(leaves) >= 1);
            }).join().unwrap();
            let atomic = AtomicU64::new(u64::MAX);
            atomic.fetch_add(1,Ordering::Relaxed);
            assert_eq!(atomic.load(Ordering::Relaxed),0);
            assert_eq!(usize::MAX.wrapping_add(1),0);
        }).join().unwrap();
    }
}
