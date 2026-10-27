//! TTL control flow; native frames retain storage and entire C++ expressions.
//! No native exception may cross this boundary. There is no depth/iteration cap.
use std::cell::Cell;
use std::ffi::c_void;
use std::mem::size_of;
use std::panic::{catch_unwind, AssertUnwindSafe};

const VERSION: u32 = 1;
const INVALID: u32 = 2;
const PANIC: u32 = 3;
const MODES: usize = 19;
const STAGES: usize = 4;
const VOID: u32 = 0;
const U64: u32 = 1;
const I64: u32 = 2;
const BOOL: u32 = 3;
const REF: u32 = 4;
const KEYS: u32 = 5;
const VALUES: u32 = 6;
const ARG: u32 = 1;
const READ_TTL: u32 = 2;
const WRITE_TTL: u32 = 3;
const READ_SMEAR: u32 = 4;
const WRITE_SMEAR: u32 = 5;
const READ_UPDATE: u32 = 6;
const WRITE_UPDATE: u32 = 7;
const LRU_MAX: u32 = 8;
const LRU_LIMIT: u32 = 9;
const LRU_SIZE: u32 = 10;
const LRU_PTR: u32 = 11;
const PAIR_PRESENT: u32 = 12;
const PAIR_STAMP_READ: u32 = 13;
const PAIR_STAMP_NATIVE: u32 = 14;
const PAIR_VALUE_BORROW: u32 = 15;
const SET_EXPRESSION: u32 = 16;
const GET_EXPRESSION: u32 = 17;
const LRU_REMOVE: u32 = 18;
const LRU_CLEAR: u32 = 19;
const VALUES_SCOPE: u32 = 20;
const VALUES_END: u32 = 21;
const VALUES_APPEND: u32 = 22;
const VALUES_NEXT: u32 = 23;
const FILTER_SCOPE: u32 = 24;
const CALL_FILTER: u32 = 25;
const TIME_ONCE: u32 = 26;
const CLEANUP_SCOPE: u32 = 27;
const FILTER_PRESENT: u32 = 28;
const CALL_REFRESH: u32 = 29;
const READ_CAPTURED_TIME: u32 = 30;
const PAIR_STAMP_WRITE: u32 = 31;

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbTtlRequest {
    pub size: u32,
    pub version: u32,
    pub op: u32,
    pub reserved: u32,
    pub arg: u64,
}
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbTtlReply {
    pub size: u32,
    pub version: u32,
    pub tag: u32,
    pub reserved: u32,
    pub value: u64,
}
pub type SbTtlHost = unsafe extern "C" fn(*mut c_void, *const SbTtlRequest, *mut SbTtlReply) -> u32;
thread_local! {
    static COUNTS: Cell<[[u64; STAGES]; MODES]> = const { Cell::new([[0; STAGES]; MODES]) };
}
#[no_mangle]
pub extern "C" fn sb_ttl_count(mode: u32, stage: u32) -> u64 {
    COUNTS.with(|counts| {
        counts
            .get()
            .get(mode as usize)
            .and_then(|row| row.get(stage as usize))
            .copied()
            .unwrap_or(0)
    })
}
fn reply(tag: u32, value: u64) -> SbTtlReply {
    SbTtlReply {
        size: size_of::<SbTtlReply>() as u32,
        version: VERSION,
        tag,
        reserved: 0,
        value,
    }
}
struct Controller {
    context: *mut c_void,
    host: SbTtlHost,
}
impl Controller {
    fn call(&self, op: u32, tag: u32, arg: u64) -> Result<u64, u32> {
        let request = SbTtlRequest {
            size: size_of::<SbTtlRequest>() as u32,
            version: VERSION,
            op,
            reserved: 0,
            arg,
        };
        let mut output = reply(u32::MAX, u64::MAX);
        // Neither a native object reference nor a Rust exclusive borrow spans reentry.
        let status = unsafe { (self.host)(self.context, &request, &mut output) };
        if status != 0 {
            return Err(if status <= PANIC { status } else { INVALID });
        }
        if output.size != size_of::<SbTtlReply>() as u32
            || output.version != VERSION
            || output.reserved != 0
            || output.tag != tag
            || (tag == BOOL && output.value > 1)
            || (tag == VOID && output.value != 0)
        {
            return Err(INVALID);
        }
        Ok(output.value)
    }
    fn leaf(&self, op: u32) -> Result<(), u32> {
        self.call(op, VOID, 0).map(|_| ())
    }
    fn boolean(&self, op: u32) -> Result<bool, u32> {
        self.call(op, BOOL, 0).map(|value| value != 0)
    }
    fn signed(&self, op: u32) -> Result<i64, u32> {
        self.call(op, I64, 0).map(|bits| bits as i64)
    }
    fn run(&self, mode: u32, stage: u32) -> Result<SbTtlReply, u32> {
        match stage {
            1 if mode == 9 => {
                while !self.boolean(VALUES_END)? {
                    self.leaf(VALUES_APPEND)?;
                    self.leaf(VALUES_NEXT)?;
                }
                return Ok(reply(VOID, 0));
            }
            2 if mode == 15 => return Ok(reply(BOOL, self.call(CALL_FILTER, BOOL, 0)?)),
            3 if mode == 18 => {
                if self.boolean(FILTER_PRESENT)? && self.boolean(CALL_REFRESH)? {
                    let captured = self.call(READ_CAPTURED_TIME, I64, 0)?;
                    self.call(PAIR_STAMP_WRITE, VOID, captured)?;
                    return Ok(reply(BOOL, 0));
                }
                let captured = self.signed(READ_CAPTURED_TIME)?;
                let stamp = self.signed(PAIR_STAMP_READ)?;
                // Read TTL AFTER the false filter callback, never snapshot it in ROOT.
                let ttl = self.signed(READ_TTL)?;
                // Exact on the defined C++ signed-arithmetic domain. Overflow is
                // undefined in the original; wrapping here is not a universal claim.
                return Ok(reply(BOOL, u64::from(captured.wrapping_sub(stamp) > ttl)));
            }
            0 => {}
            _ => return Err(INVALID),
        }
        let result = match mode {
            0 => {
                let limit = self.call(ARG, U64, 2)?;
                self.call(LRU_LIMIT, VOID, limit)?;
                let ttl = self.call(ARG, I64, 0)?;
                self.call(WRITE_TTL, VOID, ttl)?;
                let smear = self.call(ARG, I64, 1)?;
                self.call(WRITE_SMEAR, VOID, smear)?;
                let update = self.call(ARG, BOOL, 3)?;
                self.call(WRITE_UPDATE, VOID, update)?;
                reply(VOID, 0)
            }
            1 => reply(I64, self.call(READ_TTL, I64, 0)?),
            2 => {
                let ttl = self.call(ARG, I64, 0)?;
                self.call(WRITE_TTL, VOID, ttl)?;
                reply(VOID, 0)
            }
            3 => reply(I64, self.call(READ_SMEAR, I64, 0)?),
            4 => {
                let smear = self.call(ARG, I64, 0)?;
                self.call(WRITE_SMEAR, VOID, smear)?;
                reply(VOID, 0)
            }
            5 => reply(U64, self.call(LRU_MAX, U64, 0)?),
            6 => {
                let limit = self.call(ARG, U64, 0)?;
                self.call(LRU_LIMIT, VOID, limit)?;
                reply(VOID, 0)
            }
            7 => reply(U64, self.call(LRU_SIZE, U64, 0)?),
            8 => reply(KEYS, 0), // Native direct-return prvalue, not a Rust list holder.
            9 => {
                self.leaf(VALUES_SCOPE)?;
                reply(VALUES, 0)
            }
            10 => reply(BOOL, self.call(READ_UPDATE, BOOL, 0)?),
            11 => {
                let enabled = self.call(ARG, BOOL, 0)?;
                self.call(WRITE_UPDATE, VOID, enabled)?;
                reply(VOID, 0)
            }
            12 => {
                self.leaf(LRU_PTR)?;
                if self.boolean(PAIR_PRESENT)? {
                    if self.boolean(READ_UPDATE)? {
                        self.leaf(PAIR_STAMP_NATIVE)?;
                    }
                    self.leaf(PAIR_VALUE_BORROW)?;
                }
                reply(REF, 0)
            }
            13 => {
                self.leaf(SET_EXPRESSION)?;
                reply(VOID, 0)
            }
            14 => reply(BOOL, self.call(LRU_REMOVE, BOOL, 0)?),
            15 => {
                self.leaf(FILTER_SCOPE)?;
                reply(VOID, 0)
            }
            16 => {
                // Native lambda/pair/LRU full expression finishes before policy.
                self.leaf(GET_EXPRESSION)?;
                if self.signed(PAIR_STAMP_READ)? == 0 || self.boolean(READ_UPDATE)? {
                    self.leaf(PAIR_STAMP_NATIVE)?;
                }
                self.leaf(PAIR_VALUE_BORROW)?;
                reply(REF, 0)
            }
            17 => {
                self.leaf(LRU_CLEAR)?;
                reply(VOID, 0)
            }
            18 => {
                self.leaf(TIME_ONCE)?; // Even for an empty native cache.
                self.leaf(CLEANUP_SCOPE)?;
                reply(VOID, 0)
            }
            _ => return Err(INVALID),
        };
        Ok(result)
    }
}
/// # Safety
/// `result` is live, aligned, writable, with initialized size/version/reserved.
/// Context and synchronous host remain live through nested reentry. The host
/// retains neither request nor reply, contains every native exception, and owns
/// all borrowed native storage. Null checks do not establish pointer provenance.
/// On error the caller's result is untouched. No native exception may cross Rust.
#[no_mangle]
pub unsafe extern "C" fn sb_ttl_run(
    mode: u32,
    stage: u32,
    context: *mut c_void,
    host: Option<SbTtlHost>,
    result: *mut SbTtlReply,
) -> u32 {
    if mode as usize >= MODES
        || stage as usize >= STAGES
        || context.is_null()
        || result.is_null()
        || (*result).size != size_of::<SbTtlReply>() as u32
        || (*result).version != VERSION
        || (*result).reserved != 0
    {
        return INVALID;
    }
    let Some(host) = host else {
        return INVALID;
    };
    catch_unwind(AssertUnwindSafe(|| {
        COUNTS.with(|counts| {
            let mut current = counts.get();
            current[mode as usize][stage as usize] =
                current[mode as usize][stage as usize].wrapping_add(1);
            counts.set(current);
        });
        match (Controller { context, host }).run(mode, stage) {
            Ok(value) => {
                result.write(value);
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
    // opcode, request arg, expected reply tag, reply value, status
    type Step = (u32, u64, u32, u64, u32);
    struct Script {
        steps: VecDeque<Step>,
        failed: bool,
    }
    unsafe extern "C" fn scripted(
        ctx: *mut c_void,
        req: *const SbTtlRequest,
        out: *mut SbTtlReply,
    ) -> u32 {
        let script = &mut *ctx.cast::<Script>();
        let Some((op, arg, tag, value, status)) = script.steps.pop_front() else {
            script.failed = true;
            return INVALID;
        };
        if *req
            != (SbTtlRequest {
                size: 24,
                version: 1,
                op,
                reserved: 0,
                arg,
            })
        {
            script.failed = true;
            return INVALID;
        }
        out.write(reply(tag, value));
        status
    }
    fn check(mode: u32, stage: u32, steps: &[Step], status: u32, tag: u32, value: u64) {
        let mut script = Script {
            steps: steps.iter().copied().collect(),
            failed: false,
        };
        let original = reply(99, 123);
        let mut output = original;
        let result = unsafe {
            sb_ttl_run(
                mode,
                stage,
                (&mut script as *mut Script).cast(),
                Some(scripted),
                &mut output,
            )
        };
        assert_eq!(result, status);
        assert!(!script.failed && script.steps.is_empty());
        assert_eq!(
            output,
            if status == 0 {
                reply(tag, value)
            } else {
                original
            }
        );
    }
    #[test]
    fn canonical_layout() {
        assert_eq!(size_of::<SbTtlRequest>(), 24);
        assert_eq!(size_of::<SbTtlReply>(), 24);
        assert_eq!(std::mem::align_of::<SbTtlReply>(), 8);
        assert_eq!(std::mem::offset_of!(SbTtlRequest, arg), 16);
        assert_eq!(std::mem::offset_of!(SbTtlReply, value), 16);
        let header = include_str!("../../../core/StarRustTtlCache.h");
        for (name, value) in [
            ("SB_TTL_CTOR", 0),
            ("SB_TTL_CLEANUP", 18),
            ("SB_TTL_MODE_COUNT", 19),
            ("SB_TTL_PAIR_STAMP_WRITE", 31),
            ("SB_TTL_STAGE_COUNT", 4),
        ] {
            assert!(header.contains(&format!("{name} = {value}")));
        }
    }
    #[test]
    fn constructor_orders_dependency_before_scalar_writes() {
        check(
            0,
            0,
            &[
                (ARG, 2, U64, 0, 0),
                (LRU_LIMIT, 0, VOID, 0, 0),
                (ARG, 0, I64, (-3_i64) as u64, 0),
                (WRITE_TTL, (-3_i64) as u64, VOID, 0, 0),
                (ARG, 1, I64, (-2_i64) as u64, 0),
                (WRITE_SMEAR, (-2_i64) as u64, VOID, 0, 0),
                (ARG, 3, BOOL, 1, 0),
                (WRITE_UPDATE, 1, VOID, 0, 0),
            ],
            0,
            VOID,
            0,
        );
    }
    #[test]
    fn all_scalar_and_forward_routes() {
        for (mode, op, tag, value) in [
            (1, READ_TTL, I64, u64::MAX),
            (3, READ_SMEAR, I64, 7),
            (5, LRU_MAX, U64, 3),
            (7, LRU_SIZE, U64, 2),
            (10, READ_UPDATE, BOOL, 1),
            (14, LRU_REMOVE, BOOL, 0),
        ] {
            check(mode, 0, &[(op, 0, tag, value, 0)], 0, tag, value);
        }
        for (mode, op, tag, value) in [
            (2, WRITE_TTL, I64, u64::MAX),
            (4, WRITE_SMEAR, I64, (-4_i64) as u64),
            (6, LRU_LIMIT, U64, 0),
            (11, WRITE_UPDATE, BOOL, 0),
        ] {
            check(
                mode,
                0,
                &[(ARG, 0, tag, value, 0), (op, value, VOID, 0, 0)],
                0,
                VOID,
                0,
            );
        }
        check(8, 0, &[], 0, KEYS, 0);
        for (mode, op, tag) in [
            (9, VALUES_SCOPE, VALUES),
            (13, SET_EXPRESSION, VOID),
            (15, FILTER_SCOPE, VOID),
            (17, LRU_CLEAR, VOID),
        ] {
            check(mode, 0, &[(op, 0, VOID, 0, 0)], 0, tag, 0);
        }
    }
    #[test]
    fn ptr_promotes_before_policy_and_miss_does_not_sample() {
        check(
            12,
            0,
            &[(LRU_PTR, 0, VOID, 0, 0), (PAIR_PRESENT, 0, BOOL, 0, 0)],
            0,
            REF,
            0,
        );
        for enabled in 0..=1 {
            let mut steps = vec![
                (LRU_PTR, 0, VOID, 0, 0),
                (PAIR_PRESENT, 0, BOOL, 1, 0),
                (READ_UPDATE, 0, BOOL, enabled, 0),
            ];
            if enabled == 1 {
                steps.push((PAIR_STAMP_NATIVE, 0, VOID, 0, 0));
            }
            steps.push((PAIR_VALUE_BORROW, 0, VOID, 0, 0));
            check(12, 0, &steps, 0, REF, 0);
        }
    }
    #[test]
    fn get_zero_short_circuits_update_and_negative_stamp_is_not_zero() {
        check(
            16,
            0,
            &[
                (GET_EXPRESSION, 0, VOID, 0, 0),
                (PAIR_STAMP_READ, 0, I64, 0, 0),
                (PAIR_STAMP_NATIVE, 0, VOID, 0, 0),
                (PAIR_VALUE_BORROW, 0, VOID, 0, 0),
            ],
            0,
            REF,
            0,
        );
        for enabled in 0..=1 {
            let mut steps = vec![
                (GET_EXPRESSION, 0, VOID, 0, 0),
                (PAIR_STAMP_READ, 0, I64, u64::MAX, 0),
                (READ_UPDATE, 0, BOOL, enabled, 0),
            ];
            if enabled == 1 {
                steps.push((PAIR_STAMP_NATIVE, 0, VOID, 0, 0));
            }
            steps.push((PAIR_VALUE_BORROW, 0, VOID, 0, 0));
            check(16, 0, &steps, 0, REF, 0);
        }
    }
    #[test]
    fn strict_cleanup_policy_and_refresh_precedence() {
        check(
            18,
            0,
            &[(TIME_ONCE, 0, VOID, 0, 0), (CLEANUP_SCOPE, 0, VOID, 0, 0)],
            0,
            VOID,
            0,
        );
        check(
            18,
            3,
            &[
                (FILTER_PRESENT, 0, BOOL, 1, 0),
                (CALL_REFRESH, 0, BOOL, 1, 0),
                (READ_CAPTURED_TIME, 0, I64, 55, 0),
                (PAIR_STAMP_WRITE, 55, VOID, 0, 0),
            ],
            0,
            BOOL,
            0,
        );
        for (now, stamp, ttl, expired) in [
            (110_i64, 100_i64, 10_i64, 0),
            (111, 100, 10, 1),
            (-5, -10, 4, 1),
            (0, 0, -1, 1),
        ] {
            check(
                18,
                3,
                &[
                    (FILTER_PRESENT, 0, BOOL, 0, 0),
                    (READ_CAPTURED_TIME, 0, I64, now as u64, 0),
                    (PAIR_STAMP_READ, 0, I64, stamp as u64, 0),
                    (READ_TTL, 0, I64, ttl as u64, 0),
                ],
                0,
                BOOL,
                expired,
            );
        }
        check(
            18,
            3,
            &[
                (FILTER_PRESENT, 0, BOOL, 1, 0),
                (CALL_REFRESH, 0, BOOL, 0, 0),
                (READ_CAPTURED_TIME, 0, I64, 105, 0),
                (PAIR_STAMP_READ, 0, I64, 100, 0),
                (READ_TTL, 0, I64, 2, 0),
            ],
            0,
            BOOL,
            1,
        );
        check(15, 2, &[(CALL_FILTER, 0, BOOL, 1, 0)], 0, BOOL, 1);
    }
    #[test]
    fn values_loop_order_and_exception_stops_before_advance() {
        check(
            9,
            1,
            &[
                (VALUES_END, 0, BOOL, 0, 0),
                (VALUES_APPEND, 0, VOID, 0, 0),
                (VALUES_NEXT, 0, VOID, 0, 0),
                (VALUES_END, 0, BOOL, 1, 0),
            ],
            0,
            VOID,
            0,
        );
        check(
            9,
            1,
            &[(VALUES_END, 0, BOOL, 0, 0), (VALUES_APPEND, 0, VOID, 0, 1)],
            1,
            VOID,
            0,
        );
        check(16, 0, &[(GET_EXPRESSION, 0, VOID, 0, 1)], 1, VOID, 0);
        check(
            12,
            0,
            &[
                (LRU_PTR, 0, VOID, 0, 0),
                (PAIR_PRESENT, 0, BOOL, 1, 0),
                (READ_UPDATE, 0, BOOL, 1, 0),
                (PAIR_STAMP_NATIVE, 0, VOID, 0, 1),
            ],
            1,
            VOID,
            0,
        );
    }
    #[test]
    fn rejects_bad_tags_boolean_void_and_status_without_committing_output() {
        for (tag, value, status, expected) in [
            (U64, 1, 0, 2),
            (BOOL, 2, 0, 2),
            (BOOL, 1, 9, 2),
            (BOOL, 0, 1, 1),
            (BOOL, 0, 3, 3),
        ] {
            check(
                10,
                0,
                &[(READ_UPDATE, 0, tag, value, status)],
                expected,
                VOID,
                0,
            );
        }
        check(17, 0, &[(LRU_CLEAR, 0, VOID, 1, 0)], 2, VOID, 0);
        for (mode, stage) in [(0, 1), (9, 2), (15, 3), (18, 1)] {
            check(mode, stage, &[], 2, VOID, 0);
        }
    }
    #[test]
    fn metadata_and_null_contract_fail_closed() {
        unsafe extern "C" fn malformed(
            ctx: *mut c_void,
            _: *const SbTtlRequest,
            out: *mut SbTtlReply,
        ) -> u32 {
            let selector = unsafe { *ctx.cast::<u32>() };
            let mut r = reply(BOOL, 1);
            match selector {
                0 => r.size = 0,
                1 => r.version = 0,
                _ => r.reserved = 1,
            };
            unsafe { out.write(r) };
            0
        }
        for mut selector in 0..3_u32 {
            let mut output = reply(99, 123);
            let original = output;
            assert_eq!(
                unsafe {
                    sb_ttl_run(
                        10,
                        0,
                        (&mut selector as *mut u32).cast(),
                        Some(malformed),
                        &mut output,
                    )
                },
                2
            );
            assert_eq!(output, original);
        }
        let mut ctx = 0_u32;
        for (size, version, reserved) in [(0, 1, 0), (24, 0, 0), (24, 1, 1)] {
            let mut output = SbTtlReply {
                size,
                version,
                tag: 99,
                reserved,
                value: 123,
            };
            let original = output;
            assert_eq!(
                unsafe {
                    sb_ttl_run(
                        10,
                        0,
                        (&mut ctx as *mut u32).cast(),
                        Some(malformed),
                        &mut output,
                    )
                },
                2
            );
            assert_eq!(output, original);
        }
        let mut output = reply(99, 123);
        assert_eq!(
            unsafe { sb_ttl_run(10, 0, std::ptr::null_mut(), Some(malformed), &mut output) },
            2
        );
        assert_eq!(
            unsafe { sb_ttl_run(10, 0, (&mut ctx as *mut u32).cast(), None, &mut output) },
            2
        );
        assert_eq!(
            unsafe {
                sb_ttl_run(
                    19,
                    0,
                    (&mut ctx as *mut u32).cast(),
                    Some(malformed),
                    &mut output,
                )
            },
            2
        );
        assert_eq!(
            unsafe {
                sb_ttl_run(
                    0,
                    4,
                    (&mut ctx as *mut u32).cast(),
                    Some(malformed),
                    &mut output,
                )
            },
            2
        );
        assert_eq!(
            unsafe {
                sb_ttl_run(
                    10,
                    0,
                    (&mut ctx as *mut u32).cast(),
                    Some(malformed),
                    std::ptr::null_mut(),
                )
            },
            2
        );
    }
    #[test]
    fn values_has_no_semantic_iteration_cap_and_nested_calls_have_no_depth_cap() {
        struct Loop {
            remaining: usize,
            next: bool,
        }
        unsafe extern "C" fn looping(
            ctx: *mut c_void,
            req: *const SbTtlRequest,
            out: *mut SbTtlReply,
        ) -> u32 {
            let s = unsafe { &mut *ctx.cast::<Loop>() };
            let op = unsafe { (*req).op };
            let result = match op {
                VALUES_END => reply(BOOL, u64::from(s.remaining == 0)),
                VALUES_APPEND => {
                    if s.next {
                        return 2;
                    }
                    s.next = true;
                    reply(VOID, 0)
                }
                VALUES_NEXT => {
                    if !s.next {
                        return 2;
                    }
                    s.next = false;
                    s.remaining -= 1;
                    reply(VOID, 0)
                }
                _ => return 2,
            };
            unsafe { out.write(result) };
            0
        }
        let mut state = Loop {
            remaining: 350001,
            next: false,
        };
        let mut out = reply(99, 123);
        assert_eq!(
            unsafe {
                sb_ttl_run(
                    9,
                    1,
                    (&mut state as *mut Loop).cast(),
                    Some(looping),
                    &mut out,
                )
            },
            0
        );
        assert_eq!(state.remaining, 0);
        unsafe extern "C" fn nested(
            ctx: *mut c_void,
            req: *const SbTtlRequest,
            out: *mut SbTtlReply,
        ) -> u32 {
            if unsafe { (*req).op } != SET_EXPRESSION {
                return 2;
            }
            let depth = unsafe { *ctx.cast::<usize>() };
            if depth > 0 {
                unsafe { *ctx.cast::<usize>() = depth - 1 };
                let mut result = reply(99, 123);
                let code = unsafe { sb_ttl_run(13, 0, ctx, Some(nested), &mut result) };
                if code != 0 {
                    return code;
                }
            }
            unsafe { out.write(reply(VOID, 0)) };
            0
        }
        let mut depth = 193_usize;
        assert_eq!(
            unsafe {
                sb_ttl_run(
                    13,
                    0,
                    (&mut depth as *mut usize).cast(),
                    Some(nested),
                    &mut out,
                )
            },
            0
        );
        assert_eq!(depth, 0);
        assert_eq!(sb_ttl_count(99, 99), 0);
    }
}
