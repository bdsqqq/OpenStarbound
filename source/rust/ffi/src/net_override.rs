//! Override-vs-qualified-base dispatch; native code owns and invokes callbacks.
use crate::net_group::{SbNetGroupReply as Reply, Host};
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST_ERROR: u32 = 2;
const PANIC: u32 = 3;
const COUNT: usize = 4;
const WRITE: u32 = 2;
const HAS: u32 = 0;
const CALL_OVERRIDE: u32 = 1;
const CALL_BASE: u32 = 2;
const OP_COUNT: usize = 3;
static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static LEAVES: [AtomicU64; OP_COUNT] = [const { AtomicU64::new(0) }; OP_COUNT];
thread_local! { static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) }; }

unsafe fn invoke(mode: u32, ctx: *mut c_void, host: Host, op: u32) -> Result<u32, u32> {
    let mut reply = Reply::default();
    LEAVES[op as usize].fetch_add(1, Ordering::Relaxed);
    match host(ctx, op, 0, &mut reply) {
        OK if reply.b == 0 && if op == HAS || mode == WRITE { reply.a <= 1 } else { reply.a == 0 } => Ok(reply.a as u32),
        HOST_ERROR => Err(HOST_ERROR),
        _ => Err(INVALID),
    }
}
fn barrier(f: impl FnOnce() -> u32) -> u32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(PANIC)
}
/// # Safety
/// See StarRustNetOverride.h. Host must not unwind. Native context, captures and
/// aligned writable output remain live throughout synchronous callbacks/reentry.
#[no_mangle]
pub unsafe extern "C" fn sb_net_override_run(
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
        let result = (|| {
            let present = invoke(mode, ctx, host.unwrap(), HAS)?;
            let op = if present != 0 { CALL_OVERRIDE } else { CALL_BASE };
            let value = invoke(mode, ctx, host.unwrap(), op)?;
            Ok::<u32, u32>(if mode == WRITE { value } else { 0 })
        })();
        match result {
            Ok(value) => { out_result.write(value); OK }
            Err(status) => status,
        }
    })
}
/// Wrapping relaxed diagnostics; accepted roots and attempted, not completed, leaves.
#[no_mangle]
pub extern "C" fn sb_net_override_count(kind: u32, index: u32) -> u64 {
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
    #[derive(Default)]
    struct Mock { events: Vec<u32>, present: bool, written: bool,
        fault: Option<(usize, u32, Reply)>, nested: bool }
    unsafe extern "C" fn host(ctx: *mut c_void, op: u32, arg: u64, out: *mut Reply) -> u32 {
        let m = &mut *(ctx as *mut Mock);
        if arg != 0 || (*out).a != 0 || (*out).b != 0 { return HOST_ERROR; }
        let at = m.events.len(); m.events.push(op);
        if let Some((n, status, reply)) = m.fault {
            if n == at { out.write(reply); return status; }
        }
        let value = if op == HAS { u64::from(m.present) }
            else if op <= CALL_BASE { u64::from(m.written) } else { return HOST_ERROR; };
        let nested = m.nested && op == CALL_OVERRIDE;
        if nested {
            m.nested = false;
            let mut result = 77;
            let status = sb_net_override_run(WRITE, ctx, Some(host), 0, &mut result);
            if status != OK || result > 1 { return HOST_ERROR; }
        }
        out.write(Reply { a: value, b: 0 }); OK
    }
    fn call(m: &mut Mock, mode: u32, out: &mut u32) -> u32 {
        unsafe { sb_net_override_run(mode, m as *mut _ as _, Some(host), 0, out) }
    }
    #[test]
    fn all_dispatch_paths_results_and_failure_prefixes() {
        for mode in 0..COUNT as u32 {
            for present in [false, true] {
                for written in [false, true] {
                    let reply = written && mode == WRITE;
                    let mut m = Mock { present, written: reply, ..Default::default() };
                    let mut out = 77;
                    assert_eq!(call(&mut m, mode, &mut out), OK);
                    let events = vec![HAS, if present { CALL_OVERRIDE } else { CALL_BASE }];
                    assert_eq!(m.events, events); assert_eq!(out, u32::from(reply));
                    for at in 0..2 {
                        let faults = [(HOST_ERROR, Reply {a:99,b:99}, HOST_ERROR),
                            (77, Reply::default(), INVALID),
                            (OK, Reply {a:0,b:1}, INVALID),
                            (OK, Reply {a:2,b:0}, INVALID)];
                        for (status, value, expected) in faults {
                            let mut m = Mock {present, fault:Some((at,status,value)), ..Default::default()};
                            out = 77;
                            assert_eq!(call(&mut m, mode, &mut out), expected);
                            assert_eq!(out,77); assert_eq!(m.events,events[..=at]);
                        }
                    }
                }
            }
        }
        for mode in [0,1,3] {
            let mut m = Mock { written:true, ..Default::default() }; let mut out=77;
            assert_eq!(call(&mut m,mode,&mut out),INVALID); assert_eq!(out,77);
        }
    }
    #[test]
    fn strict_roots_no_output_or_counts_before_validation() {
        let mut m = Mock::default(); let ctx=&mut m as *mut _ as *mut c_void;
        let before=sb_net_override_count(0,0); let mut out=77;
        unsafe {
            assert_eq!(sb_net_override_run(4,ctx,Some(host),0,&mut out),INVALID);
            assert_eq!(sb_net_override_run(0,ctx,Some(host),1,&mut out),INVALID);
            assert_eq!(sb_net_override_run(0,std::ptr::null_mut(),Some(host),0,&mut out),INVALID);
            assert_eq!(sb_net_override_run(0,ctx,None,0,&mut out),INVALID);
            assert_eq!(sb_net_override_run(0,ctx,Some(host),0,std::ptr::null_mut()),INVALID);
            let mut words=[0u32;2];let p=(words.as_mut_ptr()as*mut u8).add(1)as*mut u32;
            assert_eq!(sb_net_override_run(0,ctx,Some(host),0,p),INVALID);
        }
        assert_eq!(out,77);assert!(m.events.is_empty());assert_eq!(sb_net_override_count(0,0),before);
        assert_eq!(sb_net_override_count(0,4),0);assert_eq!(sb_net_override_count(1,4),0);
        assert_eq!(sb_net_override_count(2,3),0);assert_eq!(sb_net_override_count(3,0),0);
    }
    #[test]
    fn same_context_reentry_tls_global_and_panic() {
        let before=sb_net_override_count(0,WRITE);
        let global=sb_net_override_count(1,WRITE);
        let leaves=sb_net_override_count(2,CALL_OVERRIDE);
        let mut m=Mock{present:true,written:true,nested:true,..Default::default()};let mut out=77;
        assert_eq!(call(&mut m,WRITE,&mut out),OK);assert_eq!(out,1);
        assert_eq!(m.events,vec![HAS,CALL_OVERRIDE,HAS,CALL_OVERRIDE]);
        assert_eq!(sb_net_override_count(0,WRITE),before.wrapping_add(2));
        assert!(sb_net_override_count(1,WRITE).wrapping_sub(global)>=2);
        assert!(sb_net_override_count(2,CALL_OVERRIDE).wrapping_sub(leaves)>=2);
        std::thread::spawn(|| {assert_eq!(sb_net_override_count(0,WRITE),0);
            let mut out=77;assert_eq!(call(&mut Mock::default(),WRITE,&mut out),OK);
            assert_eq!(sb_net_override_count(0,WRITE),1);
        }).join().unwrap();
        assert_eq!(sb_net_override_count(0,WRITE),before.wrapping_add(2));
        COUNTS.with(|c| {let mut a=c.get();a[0]=u64::MAX;c.set(a);});
        assert_eq!(call(&mut Mock::default(),0,&mut out),OK);assert_eq!(sb_net_override_count(0,0),0);
        assert_eq!(barrier(||panic!("ordinary Rust panic, not a callback unwind")),PANIC);
    }
}
