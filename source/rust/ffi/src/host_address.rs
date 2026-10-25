//! Scalar host-address controllers. All native objects, pointer results, resolver
//! nodes, formatting and exception ownership remain in the C++ context.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

pub type StarHostAddressHost = unsafe extern "C" fn(*mut c_void, u32, u64, u64, *mut u64) -> u32;
thread_local! { static COUNTS: Cell<[[u64; 3]; 27]> = const { Cell::new([[0; 3]; 27]) }; }
fn count(mode: u32, event: usize) {
    COUNTS.with(|c| {
        let mut v = c.get();
        v[mode as usize][event] = v[mode as usize][event].wrapping_add(1);
        c.set(v);
    });
}
#[no_mangle]
pub extern "C" fn star_host_address_call_count(mode: u32, event: u32) -> u64 {
    if mode >= 27 || event >= 3 {
        return 0;
    }
    COUNTS.with(|c| c.get()[mode as usize][event as usize])
}
// Operation IDs mirror the stable C contract, not native object offsets.
const HA_READ_MODE: u32 = 0;
const HA_READ_BYTE: u32 = 1;
const HA_WRITE_MODE: u32 = 2;
const HA_WRITE_BYTE: u32 = 3;
const HA_RAW_PRESENT: u32 = 4;
const HA_RAW_BYTE: u32 = 5;
const HA_PUBLISH_BYTES: u32 = 6;
const HA_READ_PORT: u32 = 7;
const HA_WRITE_PORT: u32 = 8;
const HA_STRING_EMPTY: u32 = 9;
const HA_STRING_LITERAL: u32 = 10;
const HA_STRING_COPY: u32 = 11;
const HA_STRING_REXTRACT: u32 = 12;
const HA_STRING_BEGINS: u32 = 13;
const HA_STRING_ENDS: u32 = 14;
const HA_STRING_UNBRACKET: u32 = 15;
const HA_PARSE_PORT: u32 = 16;
const HA_RESOLVE: u32 = 17;
const HA_RESOLVER_HAS: u32 = 18;
const HA_RESOLVER_FAMILY: u32 = 19;
const HA_RESOLVER_BYTE: u32 = 20;
const HA_RESOLVER_NEXT: u32 = 21;
const HA_RESOLVER_FREE: u32 = 22;
const HA_CONSTRUCT: u32 = 23;
const HA_CHILD: u32 = 24;
const HA_EITHER_LEFT: u32 = 25;
const HA_TRANSFER: u32 = 26;
const HA_RAISE: u32 = 27;
const HA_STREAM_COPY: u32 = 28;
const HA_FORMAT_ADDRESS: u32 = 29;
const HA_INSERT_COLON: u32 = 30;
const HA_INSERT_PORT: u32 = 31;
const HA_PORT_HASH: u32 = 32;
const HA_SCALAR_RESULT: u32 = 33;
const HA_FINISH: u32 = 34;
const HA_PENDING_NETWORK: u32 = 35;
const HA_CATCH_NETWORK: u32 = 36;
const HA_READ_INDEX: u32 = 37;
struct Driver {
    context: *mut c_void,
    host: StarHostAddressHost,
}
impl Driver {
    fn call(&self, op: u32, a: u64, b: u64) -> Result<u64, u32> {
        let mut out = 0;
        // No Rust reference to native state survives a callback, including reentry.
        match unsafe { (self.host)(self.context, op, a, b, &mut out) } {
            0 => Ok(out),
            1 => Err(1),
            _ => Err(2),
        }
    }
    fn c(&self, op: u32, a: u64) -> Result<u64, u32> {
        self.call(op, a, 0)
    }
    fn raise(&self, error: u64) -> Result<(), u32> {
        self.c(HA_RAISE, error)?;
        Err(2) // A successful exception-raising leaf is a protocol contradiction.
    }
    fn size(&self, slot: u64) -> Result<u64, u32> {
        Ok(match self.c(HA_READ_MODE, slot)? {
            0 => 4,
            1 => 16,
            _ => 0,
        })
    }
    fn hash(&self, slot: u64) -> Result<u64, u32> {
        let mut h = 0u64;
        for i in 0..self.size(slot)? {
            h = h
                .wrapping_mul(101)
                .wrapping_add(self.call(HA_READ_BYTE, slot, i)?);
        }
        Ok(h)
    }
    fn equal(&self, a: u64, b: u64) -> Result<bool, u32> {
        if self.c(HA_READ_MODE, a)? != self.c(HA_READ_MODE, b)? {
            return Ok(false);
        }
        for i in 0..self.size(b)? {
            if self.call(HA_READ_BYTE, a, i)? != self.call(HA_READ_BYTE, b, i)? {
                return Ok(false);
            }
        }
        Ok(true)
    }
    fn lookup(&self) -> Result<(), u32> {
        let result = (|| {
            self.c(HA_CONSTRUCT, 0)?;
            self.call(HA_CHILD, 0, 2)?;
            self.c(HA_TRANSFER, 0)?;
            Ok(())
        })();
        match result {
            Err(1) => {
                if self.c(HA_PENDING_NETWORK, 0)? == 0 {
                    return Err(1);
                }
                self.c(HA_CATCH_NETWORK, 0)?;
                Ok(())
            }
            other => other,
        }
    }
    fn set_string(&self) -> Result<(), u32> {
        if self.c(HA_STRING_EMPTY, 0)? != 0 {
            return Ok(());
        }
        if self.c(HA_STRING_LITERAL, 0)? != 0 || self.c(HA_STRING_LITERAL, 1)? != 0 {
            self.c(HA_CONSTRUCT, 1)?;
            self.call(HA_WRITE_MODE, 7, 0)?;
            self.call(HA_CHILD, 1, 6)?;
        } else if self.c(HA_STRING_LITERAL, 2)? != 0 {
            self.c(HA_CONSTRUCT, 1)?;
            self.call(HA_WRITE_MODE, 7, 1)?;
            self.call(HA_CHILD, 1, 6)?;
        } else {
            if self.c(HA_RESOLVE, 0)? != 0 {
                return self.raise(0);
            }
            while self.c(HA_RESOLVER_HAS, 0)? != 0 {
                let family = self.c(HA_RESOLVER_FAMILY, 0)?;
                if family == 1 || family == 2 {
                    self.call(HA_WRITE_MODE, 7, family - 1)?;
                    for i in 0..if family == 1 { 4 } else { 16 } {
                        self.call(HA_WRITE_BYTE, 6, (i << 8) | self.c(HA_RESOLVER_BYTE, i)?)?;
                    }
                    self.call(HA_CHILD, 1, 6)?;
                    break;
                }
                self.c(HA_RESOLVER_NEXT, 0)?;
            }
            // Source cleanup is normal-path only; pending failures do not free.
            self.c(HA_RESOLVER_FREE, 0)?;
        }
        Ok(())
    }
    fn run(&self, mode: u32) -> Result<(), u32> {
        match mode {
            0 => {
                let m = self.c(HA_READ_MODE, 7)?;
                if m != 0 && m != 1 {
                    self.c(HA_CONSTRUCT, 0)?;
                    self.c(HA_TRANSFER, 0)?;
                } else {
                    self.c(HA_CONSTRUCT, 1)?;
                    if m == 0 {
                        self.call(HA_WRITE_BYTE, 6, 127)?;
                    }
                    self.call(HA_WRITE_BYTE, 6, ((if m == 0 { 3 } else { 15 }) << 8) | 1)?;
                    self.call(HA_CONSTRUCT, 2, m)?;
                }
            }
            1 => self.lookup()?,
            2 => {
                self.c(HA_CHILD, 1)?;
            }
            3 => {
                self.c(HA_CHILD, 2)?;
                if self.c(HA_EITHER_LEFT, 0)? != 0 {
                    return self.raise(2);
                }
                self.c(HA_TRANSFER, 3)?;
            }
            4 => {
                self.c(HA_SCALAR_RESULT, self.c(HA_READ_MODE, 0)?)?;
            }
            5 => {
                self.c(HA_PUBLISH_BYTES, 0)?;
            }
            6 => {
                self.c(
                    HA_SCALAR_RESULT,
                    self.call(HA_READ_BYTE, 0, self.c(HA_READ_INDEX, 0)?)?,
                )?;
            }
            7 => {
                let mut yes = true;
                if self.c(HA_READ_MODE, 0)? == 0 {
                    for (i, expected) in [127, 0, 0, 1].into_iter().enumerate() {
                        if self.call(HA_READ_BYTE, 0, i as u64)? != expected {
                            yes = false;
                            break;
                        }
                    }
                } else {
                    for i in 0..15 {
                        if self.call(HA_READ_BYTE, 0, i)? != 0 {
                            yes = false;
                            break;
                        }
                    }
                    if yes {
                        yes = self.call(HA_READ_BYTE, 0, 15)? == 1;
                    }
                }
                self.c(HA_SCALAR_RESULT, yes as u64)?;
            }
            8 => {
                let n = self.size(0)?;
                let mut yes = n != 0;
                for i in 0..n {
                    if self.call(HA_READ_BYTE, 0, i)? != 0 {
                        yes = false;
                        break;
                    }
                }
                self.c(HA_SCALAR_RESULT, yes as u64)?;
            }
            9 => {
                self.c(HA_SCALAR_RESULT, self.size(0)?)?;
            }
            10 => {
                self.c(HA_SCALAR_RESULT, self.equal(0, 1)? as u64)?;
            }
            11 => self.set_string()?,
            12 => {
                let m = self.c(HA_READ_MODE, 7)?;
                self.call(HA_WRITE_MODE, 0, m)?;
                if self.c(HA_RAW_PRESENT, 0)? != 0 {
                    for i in 0..match m {
                        0 => 4,
                        1 => 16,
                        _ => 0,
                    } {
                        self.call(HA_WRITE_BYTE, 0, (i << 8) | self.call(HA_RAW_BYTE, 0, i)?)?;
                    }
                } else {
                    for i in 0..16 {
                        self.call(HA_WRITE_BYTE, 0, i << 8)?;
                    }
                }
            }
            13 => {
                let m = self.c(HA_READ_MODE, 0)?;
                if m > 1 {
                    return self.raise(1);
                }
                self.call(HA_FORMAT_ADDRESS, m, 0)?;
            }
            14 => {
                self.c(HA_SCALAR_RESULT, self.hash(0)?)?;
            }
            15 => {
                self.c(HA_CHILD, 2)?;
                if self.c(HA_EITHER_LEFT, 0)? != 0 {
                    self.c(HA_TRANSFER, 2)?;
                } else {
                    self.call(HA_CONSTRUCT, 4, 2)?;
                    self.c(HA_TRANSFER, 1)?;
                }
            }
            16 => {
                self.c(HA_STRING_COPY, 0)?;
                self.c(HA_STRING_REXTRACT, 0)?;
                if self.c(HA_STRING_BEGINS, 0)? != 0 && self.c(HA_STRING_ENDS, 0)? != 0 {
                    self.c(HA_STRING_UNBRACKET, 0)?;
                }
                if self.c(HA_PARSE_PORT, 0)? == 0 {
                    self.c(HA_TRANSFER, 6)?;
                } else {
                    self.call(HA_CHILD, 2, 2)?;
                    if self.c(HA_EITHER_LEFT, 0)? != 0 {
                        self.c(HA_TRANSFER, 2)?;
                    } else {
                        self.call(HA_CONSTRUCT, 4, 3)?;
                        self.c(HA_TRANSFER, 1)?;
                    }
                }
            }
            17 => {
                self.c(HA_WRITE_PORT, 0)?;
            }
            18 => {
                self.c(HA_TRANSFER, 7)?;
                self.call(HA_WRITE_PORT, 0, self.c(HA_READ_PORT, 2)?)?;
            }
            19 => {
                self.c(HA_CONSTRUCT, 5)?;
                self.call(HA_WRITE_PORT, 0, self.c(HA_READ_PORT, 2)?)?;
            }
            20 | 21 => {
                self.c(HA_CHILD, if mode == 20 { 3 } else { 4 })?;
                if self.c(HA_EITHER_LEFT, 1)? != 0 {
                    return self.raise(3);
                }
                self.c(HA_TRANSFER, 4)?;
            }
            22 => {
                self.c(HA_TRANSFER, 5)?;
            }
            23 => {
                self.c(HA_SCALAR_RESULT, self.c(HA_READ_PORT, 0)?)?;
            }
            24 => {
                let same =
                    self.equal(4, 5)? && self.c(HA_READ_PORT, 0)? == self.c(HA_READ_PORT, 1)?;
                self.c(HA_SCALAR_RESULT, same as u64)?;
            }
            25 => {
                self.c(HA_STREAM_COPY, 0)?;
                self.call(HA_CHILD, 5, 3)?;
                self.c(HA_INSERT_COLON, 0)?;
                // Native leaf reads fresh port AFTER both previous insertions.
                self.c(HA_INSERT_PORT, 0)?;
            }
            26 => {
                let h = self.hash(4)?;
                let p = self.c(HA_PORT_HASH, 0)?;
                let combined = p
                    .wrapping_mul(2654435761)
                    .wrapping_add(0x9e3779b9)
                    .wrapping_add(h << 6)
                    .wrapping_add(h >> 2);
                self.c(HA_SCALAR_RESULT, h ^ combined)?;
            }
            _ => return Err(2),
        }
        self.c(HA_FINISH, 0)?;
        Ok(())
    }
}
fn contained(f: impl FnOnce() -> Result<(), u32>) -> u32 {
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(Ok(())) => 0,
        Ok(Err(s)) => s,
        Err(_) => 3,
    }
}
/// # Safety
/// Host must obey StarRustHostAddress.h, initialize successful scalar results,
/// retain native ownership, and contain ALL native exceptions before returning.
/// The context is opaque and may be null when the supplied host accepts it.
#[no_mangle]
pub unsafe extern "C" fn star_host_address_run(
    mode: u32,
    context: *mut c_void,
    host: Option<StarHostAddressHost>,
) -> u32 {
    if mode >= 27 || host.is_none() {
        return 2;
    }
    count(mode, 0);
    let status = contained(|| {
        Driver {
            context,
            host: host.unwrap(),
        }
        .run(mode)
    });
    if status == 0 {
        count(mode, 1);
    }
    if status == 1 {
        count(mode, 2);
    }
    status
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::VecDeque;

    #[derive(Clone, Copy, Debug, PartialEq)]
    struct Step(u32, u64, u64, u64, u32);
    #[derive(Default)]
    struct Script {
        steps: VecDeque<Step>,
        observed: Vec<(u32, u64, u64)>,
        mismatch: Option<(Option<Step>, (u32, u64, u64))>,
    }
    // Never assert or panic in an extern C callback: record and check in Rust.
    unsafe extern "C" fn host(p: *mut c_void, op: u32, a: u64, b: u64, out: *mut u64) -> u32 {
        if p.is_null() {
            return 2;
        }
        let s = &mut *p.cast::<Script>();
        s.observed.push((op, a, b));
        let expected = s.steps.pop_front();
        match expected {
            Some(Step(eop, ea, eb, value, status)) if (op, a, b) == (eop, ea, eb) => {
                if status == 0 {
                    *out = value;
                }
                status
            }
            _ => {
                s.mismatch = Some((expected, (op, a, b)));
                2
            }
        }
    }
    fn ok(op: u32, a: u64, b: u64, value: u64) -> Step {
        Step(op, a, b, value, 0)
    }
    fn finish() -> Step {
        ok(HA_FINISH, 0, 0, 0)
    }
    fn run(mode: u32, steps: Vec<Step>, status: u32) -> Script {
        let mut s = Script {
            steps: steps.into(),
            ..Default::default()
        };
        let before = [0, 1, 2].map(|e| star_host_address_call_count(mode, e));
        let actual =
            unsafe { star_host_address_run(mode, (&mut s as *mut Script).cast(), Some(host)) };
        assert_eq!(actual, status, "{:?}", s.mismatch);
        assert_eq!(s.mismatch, None);
        assert!(s.steps.is_empty(), "unconsumed {:?}", s.steps);
        let after = [0, 1, 2].map(|e| star_host_address_call_count(mode, e));
        assert_eq!(after[0], before[0].wrapping_add(1));
        assert_eq!(after[1], before[1].wrapping_add(u64::from(status == 0)));
        assert_eq!(after[2], before[2].wrapping_add(u64::from(status == 1)));
        s
    }
    fn resolve_prefix() -> Vec<Step> {
        vec![
            ok(HA_STRING_EMPTY, 0, 0, 0),
            ok(HA_STRING_LITERAL, 0, 0, 0),
            ok(HA_STRING_LITERAL, 1, 0, 0),
            ok(HA_STRING_LITERAL, 2, 0, 0),
            ok(HA_RESOLVE, 0, 0, 0),
        ]
    }
    #[test]
    fn resolver_skips_unknown_selects_first_family_and_frees_only_normally() {
        for (family, n) in [(1, 4), (2, 16)] {
            let mut v = resolve_prefix();
            v.extend([
                ok(HA_RESOLVER_HAS, 0, 0, 1),
                ok(HA_RESOLVER_FAMILY, 0, 0, 0),
                ok(HA_RESOLVER_NEXT, 0, 0, 0),
                ok(HA_RESOLVER_HAS, 0, 0, 1),
                ok(HA_RESOLVER_FAMILY, 0, 0, family),
                ok(HA_WRITE_MODE, 7, family - 1, 0),
            ]);
            for i in 0..n {
                v.extend([
                    ok(HA_RESOLVER_BYTE, i, 0, 10 + i),
                    ok(HA_WRITE_BYTE, 6, (i << 8) | (10 + i), 0),
                ]);
            }
            v.extend([
                ok(HA_CHILD, 1, 6, 0),
                ok(HA_RESOLVER_FREE, 0, 0, 0),
                finish(),
            ]);
            run(11, v, 0); // No next/has after first recognized result.
        }
        let mut v = resolve_prefix();
        v.extend([
            ok(HA_RESOLVER_HAS, 0, 0, 0),
            ok(HA_RESOLVER_FREE, 0, 0, 0),
            finish(),
        ]);
        run(11, v, 0);
        let mut v = resolve_prefix();
        v.extend([
            ok(HA_RESOLVER_HAS, 0, 0, 1),
            Step(HA_RESOLVER_FAMILY, 0, 0, 0, 1),
        ]);
        run(11, v, 1); // No free, finish or retry on pending exception.
    }
    #[test]
    fn lookup_catches_only_network_and_catch_failure_stays_pending() {
        let prefix = vec![ok(HA_CONSTRUCT, 0, 0, 0), Step(HA_CHILD, 0, 2, 0, 1)];
        let mut v = prefix.clone();
        v.push(ok(HA_PENDING_NETWORK, 0, 0, 0));
        run(1, v, 1);
        let mut v = prefix.clone();
        v.extend([
            ok(HA_PENDING_NETWORK, 0, 0, 1),
            ok(HA_CATCH_NETWORK, 0, 0, 0),
            finish(),
        ]);
        run(1, v, 0);
        let mut v = prefix;
        v.extend([
            ok(HA_PENDING_NETWORK, 0, 0, 1),
            Step(HA_CATCH_NETWORK, 0, 0, 0, 1),
        ]);
        run(1, v, 1);
    }
    #[test]
    fn raw_active_extents_null_initialization_and_unknown_modes() {
        for mode in [0, 1, 2, u32::MAX as u64] {
            for present in [0, 1] {
                let mut v = vec![
                    ok(HA_READ_MODE, 7, 0, mode),
                    ok(HA_WRITE_MODE, 0, mode, 0),
                    ok(HA_RAW_PRESENT, 0, 0, present),
                ];
                let n = if present == 0 {
                    16
                } else {
                    match mode {
                        0 => 4,
                        1 => 16,
                        _ => 0,
                    }
                };
                for i in 0..n {
                    if present != 0 {
                        v.push(ok(HA_RAW_BYTE, 0, i, 250 - i));
                    }
                    v.push(ok(
                        HA_WRITE_BYTE,
                        0,
                        (i << 8) | if present == 0 { 0 } else { 250 - i },
                        0,
                    ));
                }
                v.push(finish());
                run(12, v, 0);
            }
        }
        let mut v = vec![ok(HA_READ_MODE, 0, 0, 99)];
        for i in 0..16 {
            v.push(ok(HA_READ_BYTE, 0, i, u64::from(i == 15)));
        }
        v.extend([ok(HA_SCALAR_RESULT, 1, 0, 0), finish()]);
        run(7, v, 0);
        run(
            8,
            vec![
                ok(HA_READ_MODE, 0, 0, 99),
                ok(HA_SCALAR_RESULT, 0, 0, 0),
                finish(),
            ],
            0,
        );
        run(
            14,
            vec![
                ok(HA_READ_MODE, 0, 0, 99),
                ok(HA_SCALAR_RESULT, 0, 0, 0),
                finish(),
            ],
            0,
        );
        run(
            6,
            vec![
                ok(HA_READ_INDEX, 0, 0, 15),
                ok(HA_READ_BYTE, 0, 15, 91),
                ok(HA_SCALAR_RESULT, 91, 0, 0),
                finish(),
            ],
            0,
        );
    }
    #[test]
    fn empty_wildcard_and_resolver_error_routes() {
        run(11, vec![ok(HA_STRING_EMPTY, 0, 0, 1), finish()], 0);
        for literal in 0..3 {
            let mut v = vec![ok(HA_STRING_EMPTY, 0, 0, 0)];
            for i in 0..=literal {
                v.push(ok(HA_STRING_LITERAL, i, 0, u64::from(i == literal)));
            }
            v.extend([
                ok(HA_CONSTRUCT, 1, 0, 0),
                ok(HA_WRITE_MODE, 7, u64::from(literal == 2), 0),
                ok(HA_CHILD, 1, 6, 0),
                finish(),
            ]);
            run(11, v, 0);
        }
        let mut v = resolve_prefix();
        v.last_mut().unwrap().3 = 7;
        v.push(Step(HA_RAISE, 0, 0, 0, 1));
        run(11, v, 1);
    }
    #[test]
    fn parser_native_port_presence_controls_lookup_and_brackets() {
        for valid in [false, true] {
            let mut v = vec![
                ok(HA_STRING_COPY, 0, 0, 0),
                ok(HA_STRING_REXTRACT, 0, 0, 0),
                ok(HA_STRING_BEGINS, 0, 0, 1),
                ok(HA_STRING_ENDS, 0, 0, 1),
                ok(HA_STRING_UNBRACKET, 0, 0, 0),
                ok(HA_PARSE_PORT, 0, 0, u64::from(valid)),
            ];
            if valid {
                v.extend([
                    ok(HA_CHILD, 2, 2, 0),
                    ok(HA_EITHER_LEFT, 0, 0, 0),
                    ok(HA_CONSTRUCT, 4, 3, 0),
                    ok(HA_TRANSFER, 1, 0, 0),
                ]);
            } else {
                v.push(ok(HA_TRANSFER, 6, 0, 0));
            }
            v.push(finish());
            run(16, v, 0);
        }
    }
    #[test]
    fn stream_copy_survives_until_fresh_port_leaf_after_colon() {
        run(
            25,
            vec![
                ok(HA_STREAM_COPY, 0, 0, 0),
                ok(HA_CHILD, 5, 3, 0),
                ok(HA_INSERT_COLON, 0, 0, 0),
                ok(HA_INSERT_PORT, 0, 0, 0),
                finish(),
            ],
            0,
        );
        run(
            25,
            vec![
                ok(HA_STREAM_COPY, 0, 0, 0),
                ok(HA_CHILD, 5, 3, 0),
                Step(HA_INSERT_COLON, 0, 0, 0, 1),
            ],
            1,
        );
    }
    #[test]
    fn hash_wrap_and_endpoint_native_port_hash_leaf() {
        let mut v = vec![ok(HA_READ_MODE, 4, 0, 1)];
        let mut h = 0u64;
        for i in 0..16 {
            v.push(ok(HA_READ_BYTE, 4, i, 255));
            h = h.wrapping_mul(101).wrapping_add(255);
        }
        let p = u64::MAX;
        let combined = p
            .wrapping_mul(2654435761)
            .wrapping_add(0x9e3779b9)
            .wrapping_add(h << 6)
            .wrapping_add(h >> 2);
        v.extend([
            ok(HA_PORT_HASH, 0, 0, p),
            ok(HA_SCALAR_RESULT, h ^ combined, 0, 0),
            finish(),
        ]);
        run(26, v, 0);
    }
    unsafe extern "C" fn null_host(_: *mut c_void, op: u32, a: u64, b: u64, out: *mut u64) -> u32 {
        if b != 0 {
            return 2;
        }
        match (op, a) {
            (HA_READ_MODE, 0) => *out = 0,
            (HA_SCALAR_RESULT, 4) | (HA_FINISH, 0) => *out = 0,
            _ => return 2,
        }
        0
    }
    unsafe extern "C" fn reentrant_host(
        p: *mut c_void,
        op: u32,
        a: u64,
        b: u64,
        out: *mut u64,
    ) -> u32 {
        // Separate nested context: no mutable Rust reference survives reentry.
        if op == HA_READ_MODE {
            let nested = star_host_address_run(9, std::ptr::null_mut(), Some(null_host));
            if nested != 0 {
                return 2;
            }
        }
        null_host(p, op, a, b, out)
    }
    #[test]
    fn protocol_preflight_opaque_null_reentry_and_status_mapping() {
        unsafe {
            assert_eq!(
                star_host_address_run(9, std::ptr::null_mut(), Some(null_host)),
                0
            );
            assert_eq!(
                star_host_address_run(9, std::ptr::null_mut(), Some(reentrant_host)),
                0
            );
            for fail in [1, 2, 3, 99, u32::MAX] {
                run(
                    9,
                    vec![Step(HA_READ_MODE, 0, 0, 0, fail)],
                    if fail == 1 { 1 } else { 2 },
                );
            }
            let before = star_host_address_call_count(0, 0);
            assert_eq!(
                star_host_address_run(27, std::ptr::null_mut(), Some(null_host)),
                2
            );
            assert_eq!(star_host_address_run(0, std::ptr::null_mut(), None), 2);
            assert_eq!(star_host_address_call_count(0, 0), before);
            assert_eq!(star_host_address_call_count(27, 0), 0);
            assert_eq!(star_host_address_call_count(0, 3), 0);
        }
    }
    #[test]
    fn contained_panic_and_wrapping_receipts() {
        assert_eq!(contained(|| panic!("contained Rust-only panic")), 3);
        COUNTS.with(|c| {
            let mut v = c.get();
            v[9][0] = u64::MAX;
            c.set(v);
        });
        count(9, 0);
        assert_eq!(star_host_address_call_count(9, 0), 0);
    }
}
