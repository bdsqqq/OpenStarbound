//! JsonRpc control only: typed values, native catch scopes and ownership stay in C++.
use crate::net_group::{Host, SbNetGroupReply};
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST: u32 = 2;
const PANIC: u32 = 3;
const REGISTER: u32 = 0;
const REGISTER_RANGE: u32 = 1;
const REMOVE: u32 = 2;
const CLEAR: u32 = 3;
const INVOKE: u32 = 4;
const TRACK: u32 = 5;
const PENDING: u32 = 6;
const SEND: u32 = 7;
const SEND_DATA: u32 = 8;
const RECEIVE: u32 = 9;
const BATCH: u32 = 10;
const ITEM: u32 = 11;
const REQUEST: u32 = 12;
const ENQUEUE: u32 = 13;
const COUNT: usize = 14;
const HAS_HANDLER: u32 = 0;
const THROW_DUPLICATE: u32 = 1;
const ADD_HANDLER: u32 = 2;
const MORE: u32 = 3;
const REGISTER_CURRENT: u32 = 4;
const ADVANCE: u32 = 5;
const REMOVE_HANDLER: u32 = 6;
const THROW_MISSING: u32 = 7;
const CLEAR_HANDLERS: u32 = 8;
const GET_ID: u32 = 9;
const SET_ID: u32 = 10;
const APPEND_REQUEST: u32 = 11;
const ADD_PROMISE: u32 = 12;
const EMPTY_PENDING: u32 = 13;
const WRITE_PENDING: u32 = 14;
const CLEAR_PENDING: u32 = 15;
const EMPTY_INPUT: u32 = 16;
const PROCESS_CURRENT: u32 = 17;
const IS_REQUEST: u32 = 18;
const HANDLE_REQUEST: u32 = 19;
const IS_RESPONSE: u32 = 20;
const HANDLE_RESPONSE: u32 = 21;
const IS_FAIL: u32 = 22;
const HANDLE_FAIL: u32 = 23;
const THROW_UNKNOWN: u32 = 24;
const APPEND_RESPONSE: u32 = 25;
const OP_COUNT: usize = 26;

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
    matches!(op, HAS_HANDLER | MORE | EMPTY_PENDING | EMPTY_INPUT | IS_REQUEST | IS_RESPONSE | IS_FAIL)
}
fn valid_reply(op: u32, reply: SbNetGroupReply) -> bool {
    reply.b == 0 && if boolean(op) { reply.a <= 1 }
        else { op == GET_ID || reply.a == 0 }
}
unsafe fn invoke(ctx: *mut c_void, host: Host, op: u32, arg: u64) -> Result<u64, u32> {
    let mut reply = SbNetGroupReply::default();
    LEAVES[op as usize].fetch_add(1, Ordering::Relaxed);
    LOCAL_LEAVES.with(|c| increment(c, op as usize));
    if host(ctx, op, arg, &mut reply) != OK { return Err(HOST); }
    if !valid_reply(op, reply) || matches!(op, THROW_DUPLICATE | THROW_MISSING | THROW_UNKNOWN) {
        return Err(INVALID);
    }
    Ok(reply.a)
}
unsafe fn run(mode: u32, ctx: *mut c_void, host: Host, argument: u64) -> Result<u64, u32> {
    let call = |op| invoke(ctx, host, op, 0);
    match mode {
        REGISTER => { call(if call(HAS_HANDLER)? != 0 { THROW_DUPLICATE } else { ADD_HANDLER })?; }
        REGISTER_RANGE | BATCH => {
            while call(MORE)? != 0 {
                call(if mode == REGISTER_RANGE { REGISTER_CURRENT } else { PROCESS_CURRENT })?;
                call(ADVANCE)?;
            }
        }
        REMOVE => { call(if call(HAS_HANDLER)? != 0 { REMOVE_HANDLER } else { THROW_MISSING })?; }
        CLEAR => { call(CLEAR_HANDLERS)?; }
        INVOKE => {
            let old = call(GET_ID)?;
            // Commit before C++ constructs its native unused JsonObject local.
            invoke(ctx, host, SET_ID, old.wrapping_add(1))?;
            return Ok(old);
        }
        TRACK => { call(ADD_PROMISE)?; }
        ENQUEUE => { invoke(ctx, host, APPEND_REQUEST, argument)?; }
        PENDING | SEND => return Ok(u64::from(call(EMPTY_PENDING)? == 0)),
        SEND_DATA => { call(WRITE_PENDING)?; call(CLEAR_PENDING)?; }
        RECEIVE => return Ok(u64::from(call(EMPTY_INPUT)? == 0)),
        ITEM => {
            // Each query evaluates native request.get("command") again; do not cache.
            if call(IS_REQUEST)? != 0 { call(HANDLE_REQUEST)?; }
            else if call(IS_RESPONSE)? != 0 { call(HANDLE_RESPONSE)?; }
            else if call(IS_FAIL)? != 0 { call(HANDLE_FAIL)?; }
        }
        REQUEST => { call(if call(HAS_HANDLER)? != 0 { APPEND_RESPONSE } else { THROW_UNKNOWN })?; }
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
/// See StarRustJsonRpc.h: live synchronous non-unwinding host/context and aligned
/// writable 16-byte output. Scalar checks cannot establish provenance/liveness.
#[no_mangle]
pub unsafe extern "C" fn sb_json_rpc_run(
    mode: u32, ctx: *mut c_void, host: Option<Host>, argument: u64, out: *mut SbNetGroupReply,
) -> u32 {
    if mode >= COUNT as u32 || (mode != ENQUEUE && argument != 0) || ctx.is_null() || host.is_none()
        || out.is_null() || (out as usize) % 8 != 0 { return INVALID; }
    barrier(out, || {
        ROOTS[mode as usize].fetch_add(1, Ordering::Relaxed);
        LOCAL_ROOTS.with(|c| increment(c, mode as usize));
        run(mode, ctx, host.unwrap(), argument)
    })
}
/// Wrapping no-reset diagnostics, not completion synchronization.
#[no_mangle]
pub extern "C" fn sb_json_rpc_count(kind: u32, index: u32) -> u64 {
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
        events: Vec<(u32,u64)>, answers: VecDeque<(u32,u64)>, id: u64,
        remaining: u64, cursor: u64, has: bool, empty: bool,
        fault: Option<(usize,u32,u64,u64)>, nested: bool,
    }
    impl Mock {
        fn new() -> Self {
            Self { events: vec![], answers: VecDeque::new(), id: 0, remaining: 2,
                cursor: 0, has: false, empty: false, fault: None, nested: false }
        }
        fn call(&mut self, mode: u32, out: &mut SbNetGroupReply) -> u32 {
            unsafe { sb_json_rpc_run(mode, self as *mut _ as _, Some(host), 0, out) }
        }
        fn ops(&self) -> Vec<u32> { self.events.iter().map(|p|p.0).collect() }
    }
    // Fully initialized mocks; catch ordinary Rust panic INSIDE the extern C boundary.
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, arg: u64, out: *mut SbNetGroupReply) -> u32 {
        catch_unwind(AssertUnwindSafe(|| {
            let m = &mut *(ctx as *mut Mock);
            if (*out).a != 0 || (*out).b != 0
                || (!matches!(op, SET_ID | APPEND_REQUEST) && arg != 0) { return HOST; }
            let at = m.events.len(); m.events.push((op,arg));
            if let Some((n,status,a,b)) = m.fault {
                if n == at { out.write(SbNetGroupReply {a,b}); return status; }
            }
            let a = if let Some(&(wanted,a)) = m.answers.front() {
                if wanted == op { m.answers.pop_front(); a } else { default_answer(m,op,arg) }
            } else { default_answer(m,op,arg) };
            if matches!(op, THROW_DUPLICATE | THROW_MISSING | THROW_UNKNOWN) { return HOST; }
            if m.nested && op == ADD_HANDLER {
                let mut nested = Mock::new(); let mut result = sentinel();
                if nested.call(CLEAR,&mut result) != OK { return HOST; }
            }
            out.write(SbNetGroupReply {a,b:0}); OK
        })).unwrap_or(HOST)
    }
    fn default_answer(m: &mut Mock, op: u32, arg: u64) -> u64 {
        match op {
            HAS_HANDLER => u64::from(m.has), MORE => u64::from(m.cursor < m.remaining),
            ADVANCE => { m.cursor += 1; 0 }, GET_ID => m.id,
            SET_ID => { m.id = arg; 0 }, EMPTY_PENDING | EMPTY_INPUT => u64::from(m.empty),
            _ => 0,
        }
    }
    fn sentinel() -> SbNetGroupReply { SbNetGroupReply {a:71,b:93} }
    fn unchanged(r: SbNetGroupReply) { assert_eq!((r.a,r.b),(71,93)); }
    fn success(m: &mut Mock, mode: u32) -> u64 {
        let mut out = sentinel(); assert_eq!(m.call(mode,&mut out),OK); assert_eq!(out.b,0); out.a
    }
    #[test]
    fn exact_all_root_routes() {
        let routes: [&[u32]; COUNT] = [
            &[HAS_HANDLER,ADD_HANDLER], &[MORE,REGISTER_CURRENT,ADVANCE,MORE,REGISTER_CURRENT,ADVANCE,MORE],
            &[HAS_HANDLER,REMOVE_HANDLER], &[CLEAR_HANDLERS], &[GET_ID,SET_ID],
            &[ADD_PROMISE], &[EMPTY_PENDING], &[EMPTY_PENDING], &[WRITE_PENDING,CLEAR_PENDING],
            &[EMPTY_INPUT], &[MORE,PROCESS_CURRENT,ADVANCE,MORE,PROCESS_CURRENT,ADVANCE,MORE],
            &[IS_REQUEST,IS_RESPONSE,IS_FAIL], &[HAS_HANDLER,APPEND_RESPONSE], &[APPEND_REQUEST],
        ];
        for mode in 0..COUNT as u32 {
            let mut m = Mock::new(); m.has = matches!(mode,REMOVE|REQUEST);
            assert_eq!(success(&mut m,mode),u64::from(matches!(mode,PENDING|SEND|RECEIVE)));
            assert_eq!(m.ops(),routes[mode as usize]);
            assert!(m.events.iter().all(|&(op,arg)| arg == if op == SET_ID {1} else {0}));
        }
    }
    #[test]
    fn fresh_shortcircuit_command_queries() {
        for (answers,expected) in [
            (vec![(IS_REQUEST,1)],vec![IS_REQUEST,HANDLE_REQUEST]),
            (vec![(IS_REQUEST,0),(IS_RESPONSE,1)],vec![IS_REQUEST,IS_RESPONSE,HANDLE_RESPONSE]),
            (vec![(IS_REQUEST,0),(IS_RESPONSE,0),(IS_FAIL,1)],vec![IS_REQUEST,IS_RESPONSE,IS_FAIL,HANDLE_FAIL]),
            (vec![(IS_REQUEST,0),(IS_RESPONSE,0),(IS_FAIL,0)],vec![IS_REQUEST,IS_RESPONSE,IS_FAIL]),
        ] {
            let mut m = Mock::new(); m.answers = answers.into();
            success(&mut m,ITEM); assert!(m.answers.is_empty()); assert_eq!(m.ops(),expected);
        }
    }
    #[test]
    fn ranges_empty_nonempty_and_exception_prefix() {
        for mode in [REGISTER_RANGE,BATCH] {
            let mut empty = Mock::new(); empty.remaining = 0;
            success(&mut empty,mode); assert_eq!(empty.ops(),[MORE]);
            let mut baseline = Mock::new(); success(&mut baseline,mode);
            for at in 0..baseline.events.len() {
                let mut m = Mock::new(); m.fault = Some((at,HOST,0,0)); let mut out = sentinel();
                assert_eq!(m.call(mode,&mut out),HOST); unchanged(out);
                assert_eq!(m.events,&baseline.events[..=at]);
            }
        }
    }
    #[test]
    fn throw_leaves_require_host_failure() {
        for (mode,has,leaf) in [(REGISTER,true,THROW_DUPLICATE),(REMOVE,false,THROW_MISSING),(REQUEST,false,THROW_UNKNOWN)] {
            for (status,want) in [(OK,INVALID),(HOST,HOST),(99,HOST)] {
                let mut m = Mock::new(); m.has = has; m.fault = Some((1,status,0,0));
                let mut out = sentinel(); assert_eq!(m.call(mode,&mut out),want); unchanged(out);
                assert_eq!(m.ops(),[HAS_HANDLER,leaf]);
            }
        }
    }
    #[test]
    fn full_word_id_u128_oracle_and_eager_commit_prefix() {
        let mut state = 0x9172_6cae_8123_fedcu64;
        for i in 0..100_000 {
            state ^= state << 13; state ^= state >> 7; state ^= state << 17;
            let old = if i < 4 { [0,1,u64::MAX,1u64<<63][i] } else {state};
            let expected = ((old as u128 + 1) % (1u128 << 64)) as u64;
            let mut m = Mock::new(); m.id = old;
            assert_eq!(success(&mut m,INVOKE),old); assert_eq!(m.id,expected);
            assert_eq!(m.events,[(GET_ID,0),(SET_ID,expected)]);
            let mut out = sentinel();
            assert_eq!(unsafe { sb_json_rpc_run(ENQUEUE,&mut m as *mut _ as _,Some(host),old,&mut out) },OK);
            assert_eq!((out.a,out.b),(0,0));
            assert_eq!(m.events,[(GET_ID,0),(SET_ID,expected),(APPEND_REQUEST,old)]);
        }
        let mut m = Mock::new(); m.id = u64::MAX;
        assert_eq!(success(&mut m,INVOKE),u64::MAX);
        m.fault = Some((2,HOST,0,0));
        let mut out = sentinel();
        assert_eq!(unsafe { sb_json_rpc_run(ENQUEUE,&mut m as *mut _ as _,Some(host),u64::MAX,&mut out) },HOST);
        unchanged(out); assert_eq!(m.id,0);
        assert_eq!(m.events,[(GET_ID,0),(SET_ID,0),(APPEND_REQUEST,u64::MAX)]);
        assert!(!m.ops().contains(&ADD_PROMISE));
    }
    #[test]
    fn send_failure_never_clears_and_guards_are_exact() {
        let mut m = Mock::new(); m.fault = Some((0,HOST,0,0)); let mut out = sentinel();
        assert_eq!(m.call(SEND_DATA,&mut out),HOST); unchanged(out); assert_eq!(m.ops(),[WRITE_PENDING]);
        for mode in [PENDING,SEND,RECEIVE] {
            for empty in [false,true] {
                let mut m = Mock::new(); m.empty = empty;
                assert_eq!(success(&mut m,mode),u64::from(!empty)); assert_eq!(m.events.len(),1);
            }
        }
    }
    fn scenarios() -> Vec<(Mock,u32)> {
        let mut cases = vec![];
        for mode in 0..COUNT as u32 {
            let mut m = Mock::new(); m.has = matches!(mode,REMOVE|REQUEST); cases.push((m,mode));
        }
        for (mode,has) in [(REGISTER,true),(REMOVE,false),(REQUEST,false)] {
            let mut m = Mock::new(); m.has = has; cases.push((m,mode));
        }
        for query in [IS_REQUEST,IS_RESPONSE,IS_FAIL] {
            let mut m = Mock::new(); m.answers.push_back((query,1)); cases.push((m,ITEM));
        }
        cases
    }
    #[test]
    fn every_leaf_schema_errors_and_no_output_write() {
        let mut covered = [false;OP_COUNT];
        for (initial,mode) in scenarios() {
            let mut baseline = initial.clone(); let mut out = sentinel(); baseline.call(mode,&mut out);
            for (at,&(op,_)) in baseline.events.iter().enumerate() {
                covered[op as usize] = true;
                let mut faults = vec![(HOST,99,99,HOST),(99,0,0,HOST),(OK,0,1,INVALID)];
                if op != GET_ID { faults.push((OK,if boolean(op) {2} else {1},0,INVALID)); }
                for (status,a,b,want) in faults {
                    let mut m = initial.clone(); m.fault = Some((at,status,a,b)); let mut out = sentinel();
                    assert_eq!(m.call(mode,&mut out),want); unchanged(out);
                    assert_eq!(m.events,&baseline.events[..=at]);
                }
            }
        }
        assert!(covered.into_iter().all(|x|x));
        for op in 0..OP_COUNT as u32 {
            assert!(valid_reply(op,SbNetGroupReply::default()));
            assert_eq!(valid_reply(op,SbNetGroupReply {a:1,b:0}),boolean(op)||op==GET_ID);
            assert_eq!(valid_reply(op,SbNetGroupReply {a:u64::MAX,b:0}),op==GET_ID);
        }
    }
    #[test]
    fn rejected_roots_never_count_or_touch_output() {
        let mut m = Mock::new(); let ctx = &mut m as *mut _ as *mut c_void;
        let before: Vec<_> = (0..COUNT as u32).map(|i|sb_json_rpc_count(0,i)).collect();
        let leaves: Vec<_> = (0..OP_COUNT as u32).map(|i|sb_json_rpc_count(2,i)).collect();
        let mut out = sentinel();
        unsafe {
            for mode in 0..COUNT as u32 { if mode != ENQUEUE { for arg in [1,u64::MAX] {
                assert_eq!(sb_json_rpc_run(mode,ctx,Some(host),arg,&mut out),INVALID);
            }}}
            for mode in [COUNT as u32,u32::MAX] {
                assert_eq!(sb_json_rpc_run(mode,ctx,Some(host),0,&mut out),INVALID);
            }
            assert_eq!(sb_json_rpc_run(CLEAR,std::ptr::null_mut(),Some(host),0,&mut out),INVALID);
            assert_eq!(sb_json_rpc_run(CLEAR,ctx,None,0,&mut out),INVALID);
            assert_eq!(sb_json_rpc_run(CLEAR,ctx,Some(host),0,std::ptr::null_mut()),INVALID);
            let mut storage = [0u64;3];
            assert_eq!(sb_json_rpc_run(CLEAR,ctx,Some(host),0,(storage.as_mut_ptr() as *mut u8).add(1).cast()),INVALID);
            assert_eq!(storage,[0;3]);
        }
        unchanged(out); assert!(m.events.is_empty());
        assert_eq!(before,(0..COUNT as u32).map(|i|sb_json_rpc_count(0,i)).collect::<Vec<_>>());
        assert_eq!(leaves,(0..OP_COUNT as u32).map(|i|sb_json_rpc_count(2,i)).collect::<Vec<_>>());
    }
    #[test]
    fn counters_tls_global_wrap_reentry_and_private_panic_barrier() {
        let root = sb_json_rpc_count(0,REGISTER); let leaf = sb_json_rpc_count(2,ADD_HANDLER);
        let global = sb_json_rpc_count(1,REGISTER); let global_leaf = sb_json_rpc_count(3,ADD_HANDLER);
        let clear = sb_json_rpc_count(0,CLEAR);
        let mut m = Mock::new(); m.nested = true; success(&mut m,REGISTER);
        assert_eq!(sb_json_rpc_count(0,REGISTER),root.wrapping_add(1));
        assert_eq!(sb_json_rpc_count(2,ADD_HANDLER),leaf.wrapping_add(1));
        assert_eq!(sb_json_rpc_count(0,CLEAR),clear.wrapping_add(1));
        assert!(sb_json_rpc_count(1,REGISTER).wrapping_sub(global)>=1);
        assert!(sb_json_rpc_count(3,ADD_HANDLER).wrapping_sub(global_leaf)>=1);
        std::thread::spawn(|| {
            assert_eq!(sb_json_rpc_count(0,CLEAR),0); assert_eq!(sb_json_rpc_count(2,CLEAR_HANDLERS),0);
            success(&mut Mock::new(),CLEAR);
            assert_eq!(sb_json_rpc_count(0,CLEAR),1); assert_eq!(sb_json_rpc_count(2,CLEAR_HANDLERS),1);
        }).join().unwrap();
        assert_eq!(sb_json_rpc_count(0,CLEAR),clear.wrapping_add(1));
        LOCAL_ROOTS.with(|c| { let mut v=c.get(); v[CLEAR as usize]=u64::MAX; c.set(v); });
        LOCAL_LEAVES.with(|c| { let mut v=c.get(); v[CLEAR_HANDLERS as usize]=u64::MAX; c.set(v); });
        success(&mut Mock::new(),CLEAR);
        assert_eq!(sb_json_rpc_count(0,CLEAR),0); assert_eq!(sb_json_rpc_count(2,CLEAR_HANDLERS),0);
        let local = AtomicU64::new(u64::MAX); local.fetch_add(1,Ordering::Relaxed);
        assert_eq!(local.load(Ordering::Relaxed),0);
        let mut out = sentinel();
        assert_eq!(unsafe { barrier(&mut out, || panic!("private ordinary panic seam, not an extern callback")) },PANIC);
        unchanged(out);
        for (kind,index) in [(0,14),(1,14),(2,26),(3,26),(4,0),(u32::MAX,0)] {
            assert_eq!(sb_json_rpc_count(kind,index),0);
        }
        assert_eq!(std::mem::size_of::<SbNetGroupReply>(),16);
        assert_eq!(std::mem::align_of::<SbNetGroupReply>(),8);
    }
}
