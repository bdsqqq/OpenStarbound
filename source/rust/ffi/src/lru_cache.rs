//! LRU control flow; C++ retains maps, iterators, values and expression owners.
//! Native hosts contain exceptions and return status. A native continuation may
//! rethrow only AFTER this invocation returns, inside an enclosing native catch.
//! There is no call/depth cap: valid native trims and callback reentry are unbounded.
use std::cell::Cell;
use std::ffi::c_void;
use std::mem::size_of;
use std::panic::{catch_unwind, AssertUnwindSafe};

const INVALID: u32 = 2;
const PANIC: u32 = 3;
const MODES: usize = 12;
const STAGES: usize = 4;
const VOID: u32 = 0;
const U64: u32 = 1;
const BOOL: u32 = 2;
const REF: u32 = 3;
const KEYS: u32 = 4;
const VALUES: u32 = 5;
const ARG: u32 = 1;
const READ_MAX: u32 = 2;
const WRITE_MAX: u32 = 3;
const MAP_SIZE: u32 = 4;
const REMOVE_FIRST: u32 = 5;
const FIND_SCOPE: u32 = 6;
const IS_END: u32 = 7;
const PROMOTE_ASSIGN: u32 = 8;
const PROMOTE_DISCARD: u32 = 9;
const REFERENCE: u32 = 10;
const ADD: u32 = 11;
const ASSIGN: u32 = 12;
const REMOVE_KEY: u32 = 13;
const PAIR_SCOPE: u32 = 14;
const INSERT_PAIR: u32 = 15;
const FILTER_SCOPE: u32 = 16;
const PREDICATE: u32 = 17;
const ERASE: u32 = 18;
const NEXT: u32 = 19;
const MAP_CLEAR: u32 = 20;

#[repr(C)]
#[derive(Clone, Copy)]
pub struct SbLruRequest {
    pub size: u32,
    pub op: u32,
    pub arg: u64,
}
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbLruReply {
    pub size: u32,
    pub tag: u32,
    pub value: u64,
}
pub type SbLruHost = unsafe extern "C" fn(*mut c_void, *const SbLruRequest, *mut SbLruReply) -> u32;
thread_local! {
    static COUNTS: Cell<[[u64; STAGES]; MODES]> = const { Cell::new([[0; STAGES]; MODES]) };
}
#[no_mangle]
pub extern "C" fn sb_lru_count(mode: u32, stage: u32) -> u64 {
    COUNTS.with(|c| {
        c.get()
            .get(mode as usize)
            .and_then(|r| r.get(stage as usize))
            .copied()
            .unwrap_or(0)
    })
}
struct Controller {
    ctx: *mut c_void,
    host: SbLruHost,
}
impl Controller {
    fn call(&self, op: u32, tag: u32, arg: u64) -> Result<u64, u32> {
        let request = SbLruRequest {
            size: size_of::<SbLruRequest>() as u32,
            op,
            arg,
        };
        let mut reply = SbLruReply {
            size: size_of::<SbLruReply>() as u32,
            tag: u32::MAX,
            value: u64::MAX,
        };
        // No Rust reference to native state or the caller's result spans reentry.
        let status = unsafe { (self.host)(self.ctx, &request, &mut reply) };
        if status != 0 {
            return Err(if status <= PANIC { status } else { INVALID });
        }
        if reply.size != size_of::<SbLruReply>() as u32
            || reply.tag != tag
            || (tag == BOOL && reply.value > 1)
            || (tag == VOID && reply.value != 0)
        {
            return Err(INVALID);
        }
        Ok(reply.value)
    }
    fn leaf(&self, op: u32) -> Result<(), u32> {
        self.call(op, VOID, 0).map(|_| ())
    }
    fn boolean(&self, op: u32) -> Result<bool, u32> {
        self.call(op, BOOL, 0).map(|v| v != 0)
    }
    fn trim(&self, get: bool) -> Result<(), u32> {
        loop {
            let size = self.call(MAP_SIZE, U64, 0)?;
            let limit = self.call(READ_MAX, U64, 0)?;
            let threshold = if get { limit.wrapping_sub(1) } else { limit };
            if size <= threshold {
                return Ok(());
            }
            self.leaf(REMOVE_FIRST)?;
        }
    }
    fn run(&self, mode: u32, stage: u32) -> Result<SbLruReply, u32> {
        let mut result = SbLruReply {
            size: size_of::<SbLruReply>() as u32,
            tag: VOID,
            value: 0,
        };
        match stage {
            1 => match mode {
                6 => {
                    if !self.boolean(IS_END)? {
                        self.leaf(PROMOTE_ASSIGN)?;
                        self.leaf(REFERENCE)?;
                    }
                }
                7 => {
                    if self.boolean(IS_END)? {
                        self.leaf(ADD)?;
                    } else {
                        self.leaf(ASSIGN)?;
                        self.leaf(PROMOTE_DISCARD)?;
                    }
                }
                10 => {
                    if self.boolean(IS_END)? {
                        self.leaf(PAIR_SCOPE)?;
                    } else {
                        self.leaf(PROMOTE_ASSIGN)?;
                    }
                    self.leaf(REFERENCE)?;
                }
                _ => return Err(INVALID),
            },
            2 => {
                if mode != 10 {
                    return Err(INVALID);
                }
                self.leaf(INSERT_PAIR)?;
            }
            3 => {
                if mode != 9 {
                    return Err(INVALID);
                }
                while !self.boolean(IS_END)? {
                    if self.boolean(PREDICATE)? {
                        self.leaf(ERASE)?;
                    } else {
                        self.leaf(NEXT)?;
                    }
                }
            }
            0 => match mode {
                0 | 2 => {
                    let n = self.call(ARG, U64, 0)?;
                    self.call(WRITE_MAX, VOID, n.max(1))?;
                    self.trim(false)?;
                }
                1 => {
                    result.tag = U64;
                    result.value = self.call(READ_MAX, U64, 0)?;
                }
                3 => {
                    result.tag = U64;
                    result.value = self.call(MAP_SIZE, U64, 0)?;
                }
                4 => result.tag = KEYS,
                5 => result.tag = VALUES,
                6 => {
                    self.leaf(FIND_SCOPE)?;
                    result.tag = REF;
                }
                7 => self.leaf(FIND_SCOPE)?,
                8 => {
                    result.tag = BOOL;
                    result.value = self.call(REMOVE_KEY, BOOL, 0)?;
                }
                9 => self.leaf(FILTER_SCOPE)?,
                10 => {
                    self.trim(true)?;
                    self.leaf(FIND_SCOPE)?;
                    result.tag = REF;
                }
                11 => self.leaf(MAP_CLEAR)?,
                _ => return Err(INVALID),
            },
            _ => return Err(INVALID),
        }
        Ok(result)
    }
}
/// # Safety
/// `result` is live, aligned, writable and has an initialized size field. The
/// synchronous host must accept live request/reply objects, retain neither,
/// contain all native exceptions, and respect the native ownership contract.
/// The opaque context stays live through reentry. Null checks do not establish
/// provenance, liveness or exclusive ownership; arbitrary pointers are not safe.
#[no_mangle]
pub unsafe extern "C" fn sb_lru_run(
    mode: u32,
    stage: u32,
    ctx: *mut c_void,
    host: Option<SbLruHost>,
    result: *mut SbLruReply,
) -> u32 {
    if mode as usize >= MODES
        || stage as usize >= STAGES
        || ctx.is_null()
        || result.is_null()
        || (*result).size != size_of::<SbLruReply>() as u32
    {
        return INVALID;
    }
    let Some(host) = host else {
        return INVALID;
    };
    catch_unwind(AssertUnwindSafe(|| {
        COUNTS.with(|c| {
            let mut counts = c.get();
            counts[mode as usize][stage as usize] =
                counts[mode as usize][stage as usize].wrapping_add(1);
            c.set(counts);
        });
        match (Controller { ctx, host }).run(mode, stage) {
            Ok(reply) => {
                result.write(reply);
                0
            }
            Err(status) => status,
        }
    }))
    .unwrap_or(PANIC)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::VecDeque;
    // (opcode, request argument, reply tag, reply value, status)
    type Step = (u32, u64, u32, u64, u32);
    struct Script {
        steps: VecDeque<Step>,
        failed: bool,
    }
    unsafe extern "C" fn scripted(
        ctx: *mut c_void,
        req: *const SbLruRequest,
        out: *mut SbLruReply,
    ) -> u32 {
        let s = &mut *ctx.cast::<Script>();
        let Some((op, arg, tag, value, status)) = s.steps.pop_front() else {
            s.failed = true;
            return INVALID;
        };
        if (*req).size != size_of::<SbLruRequest>() as u32 || (*req).op != op || (*req).arg != arg {
            s.failed = true;
            return INVALID;
        }
        out.write(SbLruReply {
            size: size_of::<SbLruReply>() as u32,
            tag,
            value,
        });
        status
    }
    fn check(mode: u32, stage: u32, steps: &[Step], status: u32, tag: u32, value: u64) {
        let mut script = Script {
            steps: steps.iter().copied().collect(),
            failed: false,
        };
        let mut reply = SbLruReply {
            size: size_of::<SbLruReply>() as u32,
            tag: u32::MAX,
            value: 0,
        };
        let actual = unsafe {
            sb_lru_run(
                mode,
                stage,
                (&mut script as *mut Script).cast(),
                Some(scripted),
                &mut reply,
            )
        };
        assert_eq!(actual, status);
        assert!(!script.failed);
        assert!(script.steps.is_empty());
        if status == 0 {
            assert_eq!((reply.tag, reply.value), (tag, value));
        }
    }
    fn v(op: u32) -> Step {
        (op, 0, VOID, 0, 0)
    }
    fn b(op: u32, value: u64) -> Step {
        (op, 0, BOOL, value, 0)
    }
    fn n(op: u32, value: u64) -> Step {
        (op, 0, U64, value, 0)
    }
    #[test]
    fn abi_and_rejection() {
        assert_eq!(size_of::<SbLruRequest>(), 16);
        assert_eq!(size_of::<SbLruReply>(), 16);
        let mut reply = SbLruReply {
            size: 16,
            tag: 0,
            value: 0,
        };
        assert_eq!(
            unsafe { sb_lru_run(12, 0, std::ptr::null_mut(), None, &mut reply) },
            INVALID
        );
        check(1, 1, &[], INVALID, 0, 0);
        check(9, 2, &[], INVALID, 0, 0);
    }
    #[test]
    fn clamp_and_trim_reload() {
        check(
            0,
            0,
            &[
                n(ARG, 0),
                (WRITE_MAX, 1, VOID, 0, 0),
                n(MAP_SIZE, 0),
                n(READ_MAX, 1),
            ],
            0,
            VOID,
            0,
        );
        check(
            2,
            0,
            &[
                n(ARG, 3),
                (WRITE_MAX, 3, VOID, 0, 0),
                n(MAP_SIZE, 5),
                n(READ_MAX, 3),
                v(REMOVE_FIRST),
                n(MAP_SIZE, 4),
                n(READ_MAX, 4),
            ],
            0,
            VOID,
            0,
        );
    }
    #[test]
    fn getter_snapshot_remove_clear_routes() {
        check(1, 0, &[n(READ_MAX, u64::MAX)], 0, U64, u64::MAX);
        check(3, 0, &[n(MAP_SIZE, 4)], 0, U64, 4);
        check(4, 0, &[], 0, KEYS, 0);
        check(5, 0, &[], 0, VALUES, 0);
        check(8, 0, &[b(REMOVE_KEY, 1)], 0, BOOL, 1);
        check(11, 0, &[v(MAP_CLEAR)], 0, VOID, 0);
    }
    #[test]
    fn pointer_and_set_branches() {
        check(6, 0, &[v(FIND_SCOPE)], 0, REF, 0);
        check(6, 1, &[b(IS_END, 1)], 0, VOID, 0);
        check(
            6,
            1,
            &[b(IS_END, 0), v(PROMOTE_ASSIGN), v(REFERENCE)],
            0,
            VOID,
            0,
        );
        check(7, 0, &[v(FIND_SCOPE)], 0, VOID, 0);
        check(7, 1, &[b(IS_END, 1), v(ADD)], 0, VOID, 0);
        check(
            7,
            1,
            &[b(IS_END, 0), v(ASSIGN), v(PROMOTE_DISCARD)],
            0,
            VOID,
            0,
        );
    }
    #[test]
    fn get_evicts_before_lookup_and_keeps_pair_scope() {
        check(
            10,
            0,
            &[
                n(MAP_SIZE, 1),
                n(READ_MAX, 1),
                v(REMOVE_FIRST),
                n(MAP_SIZE, 0),
                n(READ_MAX, 1),
                v(FIND_SCOPE),
            ],
            0,
            REF,
            0,
        );
        check(
            10,
            1,
            &[b(IS_END, 1), v(PAIR_SCOPE), v(REFERENCE)],
            0,
            VOID,
            0,
        );
        check(
            10,
            1,
            &[b(IS_END, 0), v(PROMOTE_ASSIGN), v(REFERENCE)],
            0,
            VOID,
            0,
        );
        check(10, 2, &[v(INSERT_PAIR)], 0, VOID, 0);
    }
    #[test]
    fn filter_reloads_current_end_after_callback() {
        check(9, 0, &[v(FILTER_SCOPE)], 0, VOID, 0);
        check(
            9,
            3,
            &[
                b(IS_END, 0),
                b(PREDICATE, 1),
                v(ERASE),
                b(IS_END, 0),
                b(PREDICATE, 0),
                v(NEXT),
                b(IS_END, 1),
            ],
            0,
            VOID,
            0,
        );
    }
    #[test]
    fn status_and_typed_reply_rejection_preserve_partial_effects() {
        check(7, 1, &[b(IS_END, 0), (ASSIGN, 0, VOID, 0, 1)], 1, 0, 0);
        check(8, 0, &[b(REMOVE_KEY, 2)], INVALID, 0, 0);
        check(11, 0, &[(MAP_CLEAR, 0, VOID, 1, 0)], INVALID, 0, 0);
        check(11, 0, &[(MAP_CLEAR, 0, U64, 0, 0)], INVALID, 0, 0);
        check(11, 0, &[(MAP_CLEAR, 0, VOID, 0, 99)], INVALID, 0, 0);
    }
    struct Trim {
        size: Cell<u64>,
        calls: Cell<u64>,
    }
    unsafe extern "C" fn large_trim(
        ctx: *mut c_void,
        req: *const SbLruRequest,
        out: *mut SbLruReply,
    ) -> u32 {
        let s = &*ctx.cast::<Trim>();
        s.calls.set(s.calls.get() + 1);
        let (tag, value) = match (*req).op {
            ARG => (U64, 1),
            WRITE_MAX => (VOID, 0),
            MAP_SIZE => (U64, s.size.get()),
            READ_MAX => (U64, 1),
            REMOVE_FIRST => {
                s.size.set(s.size.get() - 1);
                (VOID, 0)
            }
            _ => return INVALID,
        };
        out.write(SbLruReply {
            size: 16,
            tag,
            value,
        });
        0
    }
    #[test]
    fn no_million_leaf_semantic_cap() {
        let state = Trim {
            size: Cell::new(333_335),
            calls: Cell::new(0),
        };
        let mut reply = SbLruReply {
            size: 16,
            tag: 0,
            value: 0,
        };
        assert_eq!(
            unsafe {
                sb_lru_run(
                    2,
                    0,
                    (&state as *const Trim).cast_mut().cast(),
                    Some(large_trim),
                    &mut reply,
                )
            },
            0
        );
        assert_eq!(state.size.get(), 1);
        assert!(state.calls.get() > 1_000_000);
    }
    struct Depth {
        active: Cell<u32>,
        maximum: Cell<u32>,
    }
    unsafe extern "C" fn reenter(
        ctx: *mut c_void,
        req: *const SbLruRequest,
        out: *mut SbLruReply,
    ) -> u32 {
        let state = &*ctx.cast::<Depth>();
        if (*req).op != FIND_SCOPE {
            return INVALID;
        }
        let depth = state.active.get();
        if depth < 193 {
            state.active.set(depth + 1);
            state.maximum.set(state.maximum.get().max(depth + 1));
            let mut reply = SbLruReply {
                size: 16,
                tag: 0,
                value: 0,
            };
            let status = sb_lru_run(6, 0, ctx, Some(reenter), &mut reply);
            state.active.set(depth);
            if status != 0 {
                return status;
            }
        }
        // The request/reply borrow is local to each invocation, even on reentry.
        out.write(SbLruReply {
            size: 16,
            tag: VOID,
            value: 0,
        });
        0
    }
    #[test]
    fn count_reentry_uses_no_borrow_or_depth_cap() {
        let state = Depth {
            active: Cell::new(0),
            maximum: Cell::new(0),
        };
        let mut reply = SbLruReply {
            size: 16,
            tag: 0,
            value: 0,
        };
        assert_eq!(
            unsafe {
                sb_lru_run(
                    6,
                    0,
                    (&state as *const Depth).cast_mut().cast(),
                    Some(reenter),
                    &mut reply,
                )
            },
            0
        );
        assert_eq!(state.maximum.get(), 193);
        assert_eq!(state.active.get(), 0);
        assert!(sb_lru_count(6, 0) > 193);
        assert_eq!(sb_lru_count(12, 4), 0);
    }
}
