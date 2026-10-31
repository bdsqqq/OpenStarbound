//! Group control policy; native code retains storage, cached iterators and streams.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST_ERROR: u32 = 2;
const PANIC: u32 = 3;
const ADD: u32 = 0;
const INIT: u32 = 1;
const STORE: u32 = 2;
const LOAD: u32 = 3;
const ENABLE: u32 = 4;
const DISABLE: u32 = 5;
const TICK: u32 = 6;
const WRITE: u32 = 7;
const READ: u32 = 8;
const BLANK: u32 = 9;
const COUNT: usize = 10;
const ENTER_RANGE: u32 = 0;
const MORE: u32 = 1;
const ADVANCE: u32 = 2;
const LEAVE_RANGE: u32 = 3;
const INIT_NEW: u32 = 4;
const NEW_INTERPOLATING: u32 = 5;
const ENABLE_NEW: u32 = 6;
const APPEND_NEW: u32 = 7;
const NEW_COMPAT: u32 = 8;
const INCREMENT_COUNT: u32 = 9;
const INIT_CURRENT: u32 = 10;
const CURRENT_COMPAT: u32 = 11;
const STORE_CURRENT: u32 = 12;
const LOAD_CURRENT: u32 = 13;
const PROPAGATES: u32 = 14;
const ENABLE_CURRENT: u32 = 15;
const DISABLE_CURRENT: u32 = 16;
const GROUP_ENABLED: u32 = 17;
const TICK_CURRENT: u32 = 18;
const BLANK_CURRENT: u32 = 19;
const EXPECTED_SIZE: u32 = 20;
const WRITE_DIRECT: u32 = 21;
const SET_BUFFER_RULES: u32 = 22;
const WRITE_BUFFERED: u32 = 23;
const WRITE_INDEX: u32 = 24;
const WRITE_BUFFER: u32 = 25;
const CLEAR_BUFFER: u32 = 26;
const WRITE_TERMINATOR: u32 = 27;
const READ_DIRECT: u32 = 28;
const READ_INDEX: u32 = 29;
const BLANK_INDEX: u32 = 30;
const READ_AT_INDEX: u32 = 31;
const THROW_EMPTY: u32 = 32;
const THROW_ORDER: u32 = 33;
const OP_COUNT: usize = 34;

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct SbNetGroupReply { pub a: u64, pub b: u64 }
pub type Host = unsafe extern "C" fn(*mut c_void, u32, u64, *mut SbNetGroupReply) -> u32;
static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static LEAVES: [AtomicU64; OP_COUNT] = [const { AtomicU64::new(0) }; OP_COUNT];
thread_local! { static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) }; }

fn boolean(op: u32) -> bool {
    matches!(op, MORE | NEW_INTERPOLATING | NEW_COMPAT | CURRENT_COMPAT |
        PROPAGATES | GROUP_ENABLED | WRITE_DIRECT | WRITE_BUFFERED)
}
fn valid_reply(op: u32, r: SbNetGroupReply) -> bool {
    r.b == 0 && if boolean(op) { r.a <= 1 }
        else { matches!(op, EXPECTED_SIZE | READ_INDEX) || r.a == 0 }
}
unsafe fn invoke(ctx: *mut c_void, host: Host, op: u32, arg: u64) -> Result<u64, u32> {
    let mut reply = SbNetGroupReply::default();
    LEAVES[op as usize].fetch_add(1, Ordering::Relaxed);
    match host(ctx, op, arg, &mut reply) {
        OK if valid_reply(op, reply) => Ok(reply.a),
        HOST_ERROR => Err(HOST_ERROR),
        _ => Err(INVALID),
    }
}

unsafe fn run(mode: u32, ctx: *mut c_void, host: Host, argument: u64) -> Result<u32, u32> {
    let call = |op| invoke(ctx, host, op, 0);
    let indexed = |op, arg| invoke(ctx, host, op, arg);
    if mode == ADD {
        call(INIT_NEW)?;
        if call(NEW_INTERPOLATING)? != 0 { call(ENABLE_NEW)?; }
        call(APPEND_NEW)?;
        for version in 0..argument {
            if indexed(NEW_COMPAT, version)? != 0 { indexed(INCREMENT_COUNT, version)?; }
        }
        return Ok(0);
    }
    if matches!(mode, TICK | BLANK) && call(GROUP_ENABLED)? == 0 { return Ok(0); }
    let expected = if matches!(mode, WRITE | READ) { call(EXPECTED_SIZE)? } else { 0 };
    if mode == WRITE && expected == 0 { return Ok(0); }
    if mode == READ && expected == 0 {
        call(THROW_EMPTY)?;
        return Err(INVALID); // A throwing leaf must not report successful continuation.
    }
    if mode == WRITE && expected > 1 { call(SET_BUFFER_RULES)?; }
    let mut read_index = if mode == READ && expected > 1 { call(READ_INDEX)? } else { 0 };
    let (mut i, mut offset, mut delta) = (0u64, 0u64, 0u32);
    call(ENTER_RANGE)?;
    while call(MORE)? != 0 {
        // Preserve strict >: stale cached sizes admit one extra compatible entry.
        if matches!(mode, WRITE | READ) && expected > 1 && i > expected { break; }
        match mode {
            INIT => { call(INIT_CURRENT)?; }
            STORE | LOAD => {
                if call(CURRENT_COMPAT)? != 0 {
                    call(if mode == STORE { STORE_CURRENT } else { LOAD_CURRENT })?;
                }
            }
            ENABLE | DISABLE => {
                if call(PROPAGATES)? != 0 {
                    call(if mode == ENABLE { ENABLE_CURRENT } else { DISABLE_CURRENT })?;
                }
            }
            TICK | BLANK => { call(if mode == TICK { TICK_CURRENT } else { BLANK_CURRENT })?; }
            WRITE | READ => {
                if call(CURRENT_COMPAT)? == 0 {
                    offset = offset.wrapping_add(1);
                    call(ADVANCE)?;
                    continue;
                }
                if expected == 1 {
                    if mode == WRITE { delta = call(WRITE_DIRECT)? as u32; }
                    else { call(READ_DIRECT)?; }
                    break;
                }
                if mode == WRITE {
                    i = i.wrapping_add(1);
                    if call(WRITE_BUFFERED)? != 0 {
                        delta = 1;
                        indexed(WRITE_INDEX, i)?;
                        call(WRITE_BUFFER)?;
                        // A false child may have appended bytes. Clear ONLY after successful emission.
                        call(CLEAR_BUFFER)?;
                    }
                } else {
                    let index = i.wrapping_add(offset);
                    if read_index == 0 || read_index - 1 > i {
                        // Child callbacks can change this flag: never cache it across children.
                        if call(GROUP_ENABLED)? != 0 { indexed(BLANK_INDEX, index)?; }
                    } else if read_index - 1 == i {
                        indexed(READ_AT_INDEX, index)?;
                        read_index = call(READ_INDEX)?;
                    } else {
                        call(THROW_ORDER)?;
                        return Err(INVALID);
                    }
                    i = i.wrapping_add(1);
                }
            }
            _ => return Err(INVALID),
        }
        call(ADVANCE)?;
    }
    call(LEAVE_RANGE)?;
    if mode == WRITE && expected > 1 && delta != 0 { call(WRITE_TERMINATOR)?; }
    Ok(delta)
}

fn barrier(f: impl FnOnce() -> u32) -> u32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(PANIC)
}
/// # Safety
/// See StarRustNetGroup.h. The synchronous host must not unwind; captures and
/// aligned writable output must remain live through callbacks and reentry.
#[no_mangle]
pub unsafe extern "C" fn sb_net_group_run(
    mode: u32, ctx: *mut c_void, host: Option<Host>, argument: u64, out_result: *mut u32,
) -> u32 {
    if mode >= COUNT as u32 || ctx.is_null() || host.is_none() || out_result.is_null()
        || (out_result as usize) % std::mem::align_of::<u32>() != 0
        || (mode == ADD && argument > u32::MAX as u64) || (mode != ADD && argument != 0) {
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
pub extern "C" fn sb_net_group_count(kind: u32, index: u32) -> u64 {
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
    struct Child { compatible: bool, propagates: bool, delta: bool, byte: u64 }
    #[derive(Clone)]
    struct Mock {
        children: Vec<Child>, cursor: usize, end: usize, active: bool,
        expected: u64, enabled: bool, new_enabled: bool, counts: Vec<u64>,
        buffer: Vec<u64>, stream: Vec<u64>, input: VecDeque<u64>,
        events: Vec<(u32,u64)>, fault: Option<(usize,u32,SbNetGroupReply)>,
        toggle_on_blank: bool, nested: bool,
    }
    impl Mock {
        fn new() -> Self {
            Self { children: (0..3).map(|i| Child { compatible: true,
                propagates: i != 1, delta: true, byte: 10+i }).collect(),
                cursor: 0, end: 0, active: false, expected: 3, enabled: true,
                new_enabled: true, counts: vec![0;3], buffer: vec![], stream: vec![],
                input: [1,0].into_iter().collect(), events: vec![], fault: None,
                toggle_on_blank: false, nested: false }
        }
        fn call(&mut self, mode: u32, argument: u64, out: &mut u32) -> u32 {
            unsafe { sb_net_group_run(mode, self as *mut _ as _, Some(host), argument, out) }
        }
        fn ops(&self) -> Vec<u32> { self.events.iter().map(|p| p.0).collect() }
    }
    // No assertions or panics in this callback. Faults stop BEFORE fixture effects.
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, arg: u64, out: *mut SbNetGroupReply) -> u32 {
        let m = &mut *(ctx as *mut Mock);
        // Exercise zero-initialized replies and the frozen scalar argument contract.
        if (*out).a != 0 || (*out).b != 0 ||
            (!matches!(op,NEW_COMPAT|INCREMENT_COUNT|WRITE_INDEX|BLANK_INDEX|READ_AT_INDEX) && arg != 0) {
            return HOST_ERROR;
        }
        let at = m.events.len(); m.events.push((op,arg));
        if let Some((n,status,reply)) = m.fault {
            if n == at { out.write(reply); return status; }
        }
        let mut a = 0;
        match op {
            ENTER_RANGE => { m.cursor = 0; m.end = m.children.len(); m.active = true; }
            MORE => a = u64::from(m.active && m.cursor < m.end),
            ADVANCE => m.cursor += 1,
            LEAVE_RANGE => m.active = false,
            INIT_NEW | ENABLE_NEW | INIT_CURRENT | ENABLE_CURRENT | DISABLE_CURRENT |
            TICK_CURRENT | BLANK_CURRENT | LOAD_CURRENT | SET_BUFFER_RULES => {},
            NEW_INTERPOLATING => a = u64::from(m.new_enabled),
            APPEND_NEW => m.children.push(Child { compatible: true, propagates: true, delta: true, byte: 99 }),
            NEW_COMPAT => a = u64::from(arg != 1),
            INCREMENT_COUNT => {
                if let Some(c) = m.counts.get_mut(arg as usize) { *c = c.wrapping_add(1); }
                else { return HOST_ERROR; }
            }
            CURRENT_COMPAT | PROPAGATES | WRITE_DIRECT | WRITE_BUFFERED | STORE_CURRENT => {
                let Some(child) = m.children.get(m.cursor) else { return HOST_ERROR; };
                match op {
                    CURRENT_COMPAT => a = u64::from(child.compatible),
                    PROPAGATES => a = u64::from(child.propagates),
                    WRITE_DIRECT => { m.stream.push(child.byte); a = u64::from(child.delta); }
                    WRITE_BUFFERED => { m.buffer.push(child.byte); a = u64::from(child.delta); }
                    _ => m.stream.push(child.byte),
                }
            }
            GROUP_ENABLED => a = u64::from(m.enabled),
            EXPECTED_SIZE => a = m.expected,
            WRITE_INDEX => m.stream.push(arg),
            WRITE_BUFFER => m.stream.extend_from_slice(&m.buffer),
            CLEAR_BUFFER => m.buffer.clear(),
            WRITE_TERMINATOR => m.stream.push(0),
            READ_INDEX => match m.input.pop_front() { Some(v) => a = v, None => return HOST_ERROR },
            BLANK_INDEX => {
                if arg as usize >= m.children.len() { return HOST_ERROR; }
                if m.toggle_on_blank { m.enabled = !m.enabled; }
            }
            READ_AT_INDEX | READ_DIRECT => {
                let index = if op == READ_DIRECT { m.cursor } else { arg as usize };
                if index >= m.children.len() { return HOST_ERROR; }
                if m.nested {
                    let mut nested = Mock::new(); nested.expected = 1;
                    let mut result = 77;
                    if nested.call(WRITE, 0, &mut result) != OK { return HOST_ERROR; }
                    m.stream.extend(nested.stream);
                }
            }
            THROW_EMPTY | THROW_ORDER => return HOST_ERROR,
            _ => return HOST_ERROR,
        }
        out.write(SbNetGroupReply { a, b: 0 }); OK
    }
    fn success(m: &mut Mock, mode: u32, arg: u64) -> u32 {
        let mut out = 77; assert_eq!(m.call(mode,arg,&mut out), OK); out
    }
    #[test]
    fn all_modes_and_native_filtering() {
        for mode in 0..COUNT as u32 {
            let mut m = Mock::new(); m.children[1].compatible = false;
            let before = sb_net_group_count(0,mode);
            let result = success(&mut m, mode, if mode == ADD {3} else {0});
            assert_eq!(sb_net_group_count(0,mode),before.wrapping_add(1));
            assert_eq!(result, u32::from(mode == WRITE));
            let ops = m.ops();
            match mode {
                ADD => { assert_eq!(m.counts, [1,0,1]); assert_eq!(m.children.len(),4);
                    assert_eq!(&ops[..4], &[INIT_NEW,NEW_INTERPOLATING,ENABLE_NEW,APPEND_NEW]); }
                INIT => assert_eq!(ops.iter().filter(|&&x| x == INIT_CURRENT).count(),3),
                STORE | LOAD => assert_eq!(ops.iter().filter(|&&x| x == if mode == STORE {STORE_CURRENT} else {LOAD_CURRENT}).count(),2),
                ENABLE | DISABLE => assert_eq!(ops.iter().filter(|&&x| x == if mode == ENABLE {ENABLE_CURRENT} else {DISABLE_CURRENT}).count(),2),
                TICK | BLANK => assert_eq!(ops.iter().filter(|&&x| x == if mode == TICK {TICK_CURRENT} else {BLANK_CURRENT}).count(),3),
                _ => {},
            }
        }
        for mode in [TICK,BLANK] { let mut m = Mock::new(); m.enabled = false;
            success(&mut m,mode,0); assert_eq!(m.ops(),[GROUP_ENABLED]); }
        let mut m = Mock::new(); m.new_enabled = false;
        success(&mut m,ADD,0); assert_eq!(m.ops(),[INIT_NEW,NEW_INTERPOLATING,APPEND_NEW]);
    }
    #[test]
    fn framing_stale_buffer_and_strict_extra_entry() {
        let mut m = Mock::new(); m.expected = 0;
        assert_eq!(success(&mut m,WRITE,0),0); assert_eq!(m.ops(),[EXPECTED_SIZE]);
        let mut out = 77; assert_eq!(m.call(READ,0,&mut out),HOST_ERROR); assert_eq!(out,77);
        for mode in [WRITE,READ] { let mut m = Mock::new(); m.expected = 1;
            m.children[0].compatible = false; success(&mut m,mode,0);
            assert!(!m.ops().contains(&READ_INDEX)); assert!(!m.ops().contains(&WRITE_INDEX));
            assert!(!m.ops().contains(&ADVANCE) || m.cursor == 1); assert!(!m.active); }
        let mut m = Mock::new(); m.expected = 1;
        for c in &mut m.children { c.compatible = false; }
        assert_eq!(success(&mut m,WRITE,0),0); assert!(m.stream.is_empty());
        let mut m = Mock::new(); m.expected = 2; m.buffer = vec![90];
        m.children.push(m.children[2].clone());
        m.children[0].delta = false; success(&mut m,WRITE,0);
        assert_eq!(m.stream,[2,90,10,11,3,12,0]); assert!(m.buffer.is_empty());
        assert_eq!(m.ops().iter().filter(|&&op| op == WRITE_BUFFERED).count(),3);
        assert_eq!(m.cursor,3); // Fourth entry exists, but strict > stops before visiting it.
        assert_eq!(m.ops().iter().filter(|&&op| op == EXPECTED_SIZE).count(),1);
        let mut m = Mock::new(); for c in &mut m.children { c.delta = false; }
        assert_eq!(success(&mut m,WRITE,0),0); assert_eq!(m.buffer,[10,11,12]);
        assert!(!m.ops().contains(&CLEAR_BUFFER));
        m.events.clear(); m.children[0].delta = true;
        success(&mut m,WRITE,0); assert_eq!(&m.stream[..5], &[1,10,11,12,10]);
        assert_eq!(m.buffer,[11,12]);
    }
    #[test]
    fn read_gaps_order_high_index_and_nested_groups() {
        let mut m = Mock::new(); m.children[0].compatible = false;
        m.input = [2,0].into_iter().collect(); success(&mut m,READ,0);
        assert!(m.events.contains(&(BLANK_INDEX,1))); assert!(m.events.contains(&(READ_AT_INDEX,2)));
        let mut m = Mock::new(); m.input = [1,1].into_iter().collect(); let mut out = 77;
        assert_eq!(m.call(READ,0,&mut out),HOST_ERROR); assert_eq!(out,77);
        assert_eq!(m.ops().last(),Some(&THROW_ORDER)); assert!(!m.ops().contains(&LEAVE_RANGE));
        let mut m = Mock::new(); m.input = [u64::MAX,88].into_iter().collect();
        m.toggle_on_blank = true; success(&mut m,READ,0);
        assert_eq!(m.input.iter().copied().collect::<Vec<_>>(),[88]);
        assert_eq!(m.ops().iter().filter(|&&op| op == GROUP_ENABLED).count(),3);
        assert_eq!(m.ops().iter().filter(|&&op| op == BLANK_INDEX).count(),1);
        let mut m = Mock::new(); m.expected = 2; m.input = [0,88].into_iter().collect();
        m.children.push(m.children[2].clone());
        success(&mut m,READ,0); assert!(m.events.contains(&(BLANK_INDEX,2)));
        assert!(!m.events.contains(&(BLANK_INDEX,3))); assert_eq!(m.cursor,3);
        assert_eq!(m.input.iter().copied().collect::<Vec<_>>(),[88]);
        let mut m = Mock::new(); m.nested = true; success(&mut m,READ,0); assert_eq!(m.stream,[10]);
    }
    fn scenarios() -> Vec<(Mock,u32,u64)> {
        let mut cases = vec![];
        for mode in 0..COUNT as u32 { cases.push((Mock::new(),mode,if mode == ADD {3} else {0})); }
        for mode in [WRITE,READ] { let mut m = Mock::new(); m.expected = 1; cases.push((m,mode,0)); }
        let mut empty = Mock::new(); empty.expected = 0; cases.push((empty,READ,0));
        let mut order = Mock::new(); order.input = [1,1].into_iter().collect(); cases.push((order,READ,0));
        cases
    }
    #[test]
    fn every_reachable_leaf_errors_and_strict_replies_stop_without_cleanup_or_output() {
        let mut coverage = [false;OP_COUNT];
        for (initial,mode,arg) in scenarios() {
            let mut baseline = initial.clone(); let mut out = 77; baseline.call(mode,arg,&mut out);
            for (at,&(op,_)) in baseline.events.iter().enumerate() {
                coverage[op as usize] = true;
                for (status,reply,want) in [
                    (HOST_ERROR,SbNetGroupReply {a:99,b:99},HOST_ERROR),
                    (99,SbNetGroupReply::default(),INVALID),
                    (OK,SbNetGroupReply {a:0,b:1},INVALID),
                ] {
                    let mut m = initial.clone(); m.fault = Some((at,status,reply)); let mut out = 77;
                    assert_eq!(m.call(mode,arg,&mut out),want); assert_eq!(out,77);
                    assert_eq!(m.events,&baseline.events[..=at]);
                }
                if !matches!(op, EXPECTED_SIZE | READ_INDEX) {
                    let mut m = initial.clone(); m.fault = Some((at,OK,SbNetGroupReply {
                        a: if boolean(op) {2} else {1}, b:0 })); let mut out = 77;
                    assert_eq!(m.call(mode,arg,&mut out),INVALID); assert_eq!(out,77);
                    assert_eq!(m.events,&baseline.events[..=at]);
                }
            }
        }
        assert!(coverage.into_iter().all(|v|v));
        for op in 0..OP_COUNT as u32 {
            assert_eq!(valid_reply(op,SbNetGroupReply {a:u64::MAX,b:0}),matches!(op,EXPECTED_SIZE|READ_INDEX));
        }
        // Incorrectly successful throw callbacks still cannot continue or publish output.
        for (mut m,mode,arg) in scenarios() {
            let mut b = m.clone(); let mut out = 77; b.call(mode,arg,&mut out);
            if let Some(at) = b.events.iter().position(|p| matches!(p.0,THROW_EMPTY|THROW_ORDER)) {
                m.fault = Some((at,OK,SbNetGroupReply::default())); out = 77;
                assert_eq!(m.call(mode,arg,&mut out),INVALID); assert_eq!(out,77);
                assert_eq!(m.events,&b.events[..=at]);
            }
        }
    }
    #[test]
    fn failed_emission_preserves_native_buffer_and_partial_stream() {
        let mut baseline = Mock::new(); success(&mut baseline,WRITE,0);
        for op in [WRITE_INDEX,WRITE_BUFFER,CLEAR_BUFFER] {
            let at = baseline.events.iter().position(|p| p.0 == op).unwrap();
            let mut m = Mock::new(); m.fault = Some((at,HOST_ERROR,SbNetGroupReply::default()));
            let mut out = 77; assert_eq!(m.call(WRITE,0,&mut out),HOST_ERROR);
            assert_eq!(m.buffer,[10]); assert_eq!(out,77); assert!(m.active);
            let expected: &[u64] = match op { WRITE_INDEX => &[], WRITE_BUFFER => &[1], _ => &[1,10] };
            assert_eq!(m.stream,expected);
        }
    }
    #[test]
    fn scalar_rejection_counters_threads_wrapping_and_ordinary_panic_seam() {
        let mut m = Mock::new(); let ctx = &mut m as *mut _ as *mut c_void;
        let mut out = 77; let before = sb_net_group_count(0,INIT);
        unsafe {
            for mode in 0..COUNT as u32 {
                assert_eq!(sb_net_group_run(mode,ctx,Some(host),if mode==ADD {u32::MAX as u64+1} else {1},&mut out),INVALID);
            }
            assert_eq!(sb_net_group_run(10,ctx,Some(host),0,&mut out),INVALID);
            assert_eq!(sb_net_group_run(INIT,std::ptr::null_mut(),Some(host),0,&mut out),INVALID);
            assert_eq!(sb_net_group_run(INIT,ctx,None,0,&mut out),INVALID);
            assert_eq!(sb_net_group_run(INIT,ctx,Some(host),0,std::ptr::null_mut()),INVALID);
            let mut bytes = [0u32;2]; let misaligned = (bytes.as_mut_ptr() as *mut u8).add(1) as *mut u32;
            assert_eq!(sb_net_group_run(INIT,ctx,Some(host),0,misaligned),INVALID);
        }
        assert_eq!(out,77); assert!(m.events.is_empty()); assert_eq!(sb_net_group_count(0,INIT),before);
        // Maximum ADD limit is accepted, but a first-leaf error bounds this fixture.
        let mut max = Mock::new(); max.fault = Some((0,HOST_ERROR,SbNetGroupReply::default()));
        assert_eq!(max.call(ADD,u32::MAX as u64,&mut out),HOST_ERROR); assert_eq!(out,77);
        let mut wrap = Mock::new(); wrap.counts = vec![u64::MAX;3]; success(&mut wrap,ADD,3);
        assert_eq!(wrap.counts,[0,u64::MAX,0]);
        let mut large = Mock::new(); large.expected = u64::MAX; success(&mut large,WRITE,0);
        let global = sb_net_group_count(1,INIT); let leaves = sb_net_group_count(2,INIT_CURRENT);
        success(&mut m,INIT,0); assert_eq!(sb_net_group_count(0,INIT),before.wrapping_add(1));
        assert!(sb_net_group_count(1,INIT).wrapping_sub(global)>=1);
        assert!(sb_net_group_count(2,INIT_CURRENT).wrapping_sub(leaves)>=3);
        std::thread::spawn(|| { assert_eq!(sb_net_group_count(0,INIT),0);
            success(&mut Mock::new(),INIT,0); assert_eq!(sb_net_group_count(0,INIT),1); }).join().unwrap();
        assert_eq!(sb_net_group_count(0,INIT),before.wrapping_add(1));
        COUNTS.with(|c| { let mut a=c.get(); a[INIT as usize]=u64::MAX; c.set(a); });
        success(&mut Mock::new(),INIT,0); assert_eq!(sb_net_group_count(0,INIT),0);
        // Isolated atomics exercise the exact primitive without racing shared diagnostics.
        let atomic=AtomicU64::new(u64::MAX); atomic.fetch_add(1,Ordering::Relaxed);
        assert_eq!(atomic.load(Ordering::Relaxed),0);
        assert_eq!(barrier(|| panic!("ordinary rust panic, never an extern callback")),PANIC);
        assert_eq!(sb_net_group_count(3,0),0); assert_eq!(sb_net_group_count(0,10),0);
        assert_eq!(sb_net_group_count(1,10),0); assert_eq!(sb_net_group_count(2,34),0);
        assert_eq!(std::mem::size_of::<SbNetGroupReply>(),16);
        assert_eq!(std::mem::align_of::<SbNetGroupReply>(),8);
    }
}
