//! ByteArray control flow over native scalar leaves; all storage stays native.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

pub type StarByteArrayHost = unsafe extern "C" fn(*mut c_void, u32, u64, u64, u64, *mut u64) -> u32;
thread_local! { static COUNTS: Cell<[[u64; 3]; 56]> = const { Cell::new([[0; 3]; 56]) }; }
fn count(mode: u32, event: usize) {
    COUNTS.with(|c| {
        let mut v = c.get();
        v[mode as usize][event] = v[mode as usize][event].wrapping_add(1);
        c.set(v);
    });
}
#[no_mangle]
pub extern "C" fn star_byte_array_call_count(mode: u32, event: u32) -> u64 {
    if mode >= 56 || event >= 3 {
        return 0;
    }
    COUNTS.with(|c| c.get()[mode as usize][event as usize])
}
const ARG: u32 = 1;
const GET_SIZE: u32 = 2;
const GET_CAPACITY: u32 = 3;
const HAS_DATA: u32 = 4;
const INIT: u32 = 5;
const SET_SIZE: u32 = 6;
const ALLOC: u32 = 7;
const FREE: u32 = 8;
const TAKE: u32 = 9;
const SAME: u32 = 10;
const CAPTURE: u32 = 11;
const COPY_IN: u32 = 12;
const COPY_OUT: u32 = 13;
const MOVE_BYTES: u32 = 14;
const FILL_BYTES: u32 = 15;
const GET_BYTE: u32 = 16;
const SET_BYTE: u32 = 17;
const POINTER: u32 = 18;
const STRLEN: u32 = 19;
const INIT_RESULT: u32 = 20;
const ROLES: u32 = 21;
const EXPR: u32 = 22;
const TAIL_EXPR: u32 = 23;
const ITER_DISTANCE: u32 = 24;
const ASSERT_INSERT: u32 = 25;
const THROW_AT: u32 = 26;
const HASH_PUT: u32 = 27;
const HASH_RESULT: u32 = 28;
const STREAM_PREFIX: u32 = 29;
const STREAM_HEX: u32 = 30;
const RETURN: u32 = 31;
const FINISH: u32 = 32;
struct Driver {
    ctx: *mut c_void,
    host: StarByteArrayHost,
}
impl Driver {
    fn call(&self, op: u32, a: u64, b: u64, c: u64) -> Result<u64, u32> {
        let mut out = 0;
        // Only the opaque context crosses calls. No native reference or slice is held.
        match unsafe { (self.host)(self.ctx, op, a, b, c, &mut out) } {
            0 => {}
            1 => return Err(1),
            _ => return Err(2),
        }
        if op == THROW_AT
            || ((op == HAS_DATA || op == SAME) && out > 1)
            || (op == GET_BYTE && out > 255)
        {
            return Err(2);
        }
        match op {
            ARG | GET_SIZE | GET_CAPACITY | HAS_DATA | SAME | CAPTURE | GET_BYTE | STRLEN
            | ITER_DISTANCE | HASH_RESULT => {}
            _ if out != 0 => return Err(2),
            _ => {}
        }
        Ok(out)
    }
    fn get(&self, op: u32) -> Result<u64, u32> {
        self.call(op, 0, 0, 0)
    }
    fn one(&self, op: u32, a: u64) -> Result<u64, u32> {
        self.call(op, a, 0, 0)
    }
    fn arg(&self, n: u64) -> Result<u64, u32> {
        self.one(ARG, n)
    }
    fn size(&self, r: u64) -> Result<u64, u32> {
        self.one(GET_SIZE, r)
    }
    fn reserve(&self, r: u64, mut n: u64) -> Result<(), u32> {
        let cap = self.one(GET_CAPACITY, r)?;
        if n > cap {
            let has = self.one(HAS_DATA, r)?;
            if has != 0 {
                n = cap.wrapping_mul(2).max(n).max(8);
            }
            self.call(ALLOC, r, n, has)?;
        }
        Ok(())
    }
    fn resize(&self, r: u64, n: u64) -> Result<(), u32> {
        self.reserve(r, n)?;
        self.call(SET_SIZE, r, n, 0)?;
        Ok(())
    }
    fn reset(&self, r: u64) -> Result<(), u32> {
        if self.one(HAS_DATA, r)? != 0 {
            self.one(FREE, r)?;
            self.one(INIT, r)?;
        }
        Ok(())
    }
    fn append(&self, r: u64, n: u64) -> Result<(), u32> {
        self.resize(r, self.size(r)?.wrapping_add(n))?;
        self.call(COPY_IN, r, self.size(r)?.wrapping_sub(n), n)?;
        Ok(())
    }
    fn copy_assign(&self) -> Result<(), u32> {
        if self.get(SAME)? == 0 {
            self.resize(0, 0)?;
            // Capture the native source before a resize can relocate its owner.
            let n = self.one(CAPTURE, 1)?;
            self.append(0, n)?;
        }
        Ok(())
    }
    fn move_assign(&self) -> Result<(), u32> {
        if self.get(SAME)? == 0 {
            self.reset(0)?;
            self.get(TAKE)?;
        }
        Ok(())
    }
    fn fill(&self, n: u64, byte: u64) -> Result<(), u32> {
        if n != u64::MAX {
            self.resize(0, n)?;
        }
        self.call(FILL_BYTES, 0, byte, 0)?;
        Ok(())
    }
    fn sub(&self, b: u64, n: u64) -> Result<(), u32> {
        let s = self.size(0)?;
        self.get(INIT_RESULT)?;
        if b == 0 && n >= s {
            let len = self.one(CAPTURE, 0)?;
            self.append(2, len)?;
        } else {
            self.call(CAPTURE, 0, b, 0)?;
            // Preserve the native physical-span quirk, including wrapping b+n.
            self.append(2, s.min(b.wrapping_add(n)))?;
        }
        Ok(())
    }
    fn diff(&self) -> Result<u64, u32> {
        let n = self.size(0)?.min(self.size(1)?);
        let mut i = 0;
        while i < n {
            if self.call(GET_BYTE, 0, i, 0)? != self.call(GET_BYTE, 1, i, 0)? {
                break;
            }
            i = i.wrapping_add(1);
        }
        Ok(i)
    }
    fn compare(&self) -> Result<u64, u32> {
        let a = self.size(0)?;
        let b = self.size(1)?;
        if a == 0 && b == 0 {
            return Ok(0);
        }
        if a == 0 {
            return Ok(u64::MAX);
        }
        if b == 0 {
            return Ok(1);
        }
        let d = self.diff()?;
        if d == a {
            return Ok(if d != b { u64::MAX } else { 0 });
        }
        if d == b {
            return Ok(u64::from(d != a));
        }
        let x = self.call(GET_BYTE, 0, d, 0)?;
        let y = self.call(GET_BYTE, 1, d, 0)?;
        Ok(if x < y { u64::MAX } else { u64::from(x > y) })
    }
    fn combine(&self, kind: u64) -> Result<(), u32> {
        // Roles are selected once, with RHS smaller on ties. Expressions can reenter,
        // resize or delete owners: every source condition reads its size afresh.
        self.one(ROLES, u64::from(self.size(0)? < self.size(1)?))?;
        self.get(INIT_RESULT)?;
        self.resize(2, self.size(3)?)?;
        let mut i = 0;
        while i < self.size(3)? {
            self.call(EXPR, i, kind, 0)?;
            i = i.wrapping_add(1);
        }
        let extend = self.arg(0)?;
        if extend > 1 {
            return Err(2);
        }
        if extend != 0 {
            self.resize(2, self.size(4)?)?;
            i = self.size(3)?;
            while i < self.size(4)? {
                self.one(TAIL_EXPR, i)?;
                i = i.wrapping_add(1);
            }
        }
        Ok(())
    }
    fn insert(&self, p: u64, byte: u64) -> Result<(), u32> {
        self.one(ASSERT_INSERT, p)?;
        self.resize(0, self.size(0)?.wrapping_add(1))?;
        let mut i = self.size(0)?.wrapping_sub(1);
        while i > p {
            self.call(
                SET_BYTE,
                0,
                i,
                self.call(GET_BYTE, 0, i.wrapping_sub(1), 0)?,
            )?;
            i = i.wrapping_sub(1);
        }
        self.call(SET_BYTE, 0, p, byte)?;
        Ok(())
    }
    fn push(&self, byte: u64) -> Result<(), u32> {
        self.resize(0, self.size(0)?.wrapping_add(1))?;
        self.call(SET_BYTE, 0, self.size(0)?.wrapping_sub(1), byte)?;
        Ok(())
    }
    fn run(&self, m: u32) -> Result<(), u32> {
        match m {
            0 | 1 => {
                let n = self.get(STRLEN)?;
                self.get(INIT_RESULT)?;
                self.append(2, n.wrapping_add(u64::from(m == 1)))?;
                if m == 1 {
                    self.call(SET_BYTE, 2, n, 0)?;
                }
            }
            2 => {
                self.get(INIT_RESULT)?;
                self.reserve(2, self.arg(0)?)?;
            }
            3 => {
                self.one(INIT, 0)?;
            }
            4 | 14 => self.fill(self.arg(0)?, self.arg(1)?)?,
            5 => self.append(0, self.arg(0)?)?,
            6 | 9 => self.copy_assign()?,
            7 | 10 => self.move_assign()?,
            8 | 11 => self.reset(0)?,
            12 => self.reserve(0, self.arg(0)?)?,
            13 => {
                let n = self.arg(0)?;
                let mut i = self.size(0)?;
                if n != i {
                    self.resize(0, n)?;
                    while i < self.size(0)? {
                        self.call(SET_BYTE, 0, i, self.arg(1)?)?;
                        i = i.wrapping_add(1);
                    }
                }
            }
            15 => self.fill(u64::MAX, self.arg(0)?)?,
            16 => self.sub(self.arg(0)?, self.arg(1)?)?,
            17 => self.sub(0, self.arg(0)?)?,
            18 => {
                let n = self.arg(0)?;
                let p = self.size(0)?;
                self.sub(if n > p { 0 } else { p.wrapping_sub(n) }, p)?;
            }
            19 => {
                let n = self.arg(0)?;
                let p = self.size(0)?;
                if n >= p {
                    self.resize(0, 0)?;
                } else {
                    self.call(MOVE_BYTES, 0, n, p.wrapping_sub(n))?;
                    self.resize(0, self.size(0)?.wrapping_sub(n))?;
                }
            }
            20 => {
                let n = self.arg(0)?;
                let p = self.size(0)?;
                self.resize(0, if n >= p { 0 } else { p.wrapping_sub(n) })?;
            }
            21 => {
                self.one(RETURN, self.diff()?)?;
            }
            22 => {
                self.one(RETURN, self.compare()?)?;
            }
            23..=25 => self.combine(u64::from(m - 22))?,
            26 => self.insert(self.arg(0)?, self.arg(1)?)?,
            27 => {
                let d = self.get(ITER_DISTANCE)?;
                self.insert(d, self.arg(0)?)?;
                self.call(POINTER, 0, d.wrapping_add(1), 0)?;
            }
            28 | 37 => self.push(self.arg(0)?)?,
            29..=31 => {
                let c = self.compare()?;
                self.one(
                    RETURN,
                    u64::from(match m {
                        29 => c == u64::MAX,
                        30 => c == 0,
                        _ => c != 0,
                    }),
                )?;
            }
            32 => {
                self.get(STREAM_PREFIX)?;
                self.get(STREAM_HEX)?;
            }
            33 => self.resize(0, 0)?,
            34 => self.resize(0, self.arg(0)?)?,
            35 => {
                let n = self.one(CAPTURE, 1)?;
                self.append(0, n)?;
            }
            36 => self.append(0, self.arg(0)?)?,
            38 => {
                self.one(RETURN, u64::from(self.size(0)? == 0))?;
            }
            39 | 40 | 48 | 50 => {
                self.call(POINTER, 0, 0, 0)?;
            }
            41 => {
                self.one(RETURN, self.size(0)?)?;
            }
            42 => {
                self.one(RETURN, self.one(GET_CAPACITY, 0)?)?;
            }
            43 => {
                self.call(COPY_OUT, 0, 0, self.size(0)?.min(self.arg(0)?))?;
            }
            44 => {
                self.call(COPY_OUT, 0, 0, self.size(0)?)?;
            }
            45 => {
                let p = self.arg(0)?;
                let n = self.arg(1)?;
                if n != 0 && p < self.size(0)? {
                    self.call(COPY_OUT, 0, p, self.size(0)?.wrapping_sub(p).min(n))?;
                }
            }
            46 => {
                let p = self.arg(0)?;
                let n = self.arg(1)?;
                if p.wrapping_add(n) > self.size(0)? {
                    self.resize(0, p.wrapping_add(n))?;
                }
                self.call(COPY_IN, 0, p, n)?;
            }
            47 => self.combine(0)?,
            49 | 51 => {
                self.call(POINTER, 0, self.size(0)?, 1)?;
            }
            52 => {
                self.call(POINTER, 0, self.arg(0)?, 2)?;
            }
            53 => {
                self.one(RETURN, self.call(GET_BYTE, 0, self.arg(0)?, 0)?)?;
            }
            54 => {
                let n = self.arg(0)?;
                if n >= self.size(0)? {
                    self.one(THROW_AT, n)?;
                }
                self.one(RETURN, self.call(GET_BYTE, 0, n, 0)?)?;
            }
            55 => {
                let mut i = 0;
                while i < self.size(0)? {
                    self.one(HASH_PUT, i)?;
                    i = i.wrapping_add(1);
                }
                self.one(RETURN, self.get(HASH_RESULT)?)?;
            }
            _ => return Err(2),
        }
        self.get(FINISH)?;
        Ok(())
    }
}
fn contained(mode: u32, f: impl FnOnce() -> Result<(), u32>) -> u32 {
    count(mode, 0);
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(Ok(())) => {
            count(mode, 1);
            0
        }
        Ok(Err(1)) => {
            count(mode, 2);
            1
        }
        Ok(Err(_)) => 2,
        Err(_) => 3,
    }
}
/// Runs one controller operation with synchronous native ownership.
///
/// # Safety
/// Context must remain valid for callbacks. The callback must not unwind and
/// must preserve pending native exceptions until the C++ wrapper rethrows them.
#[no_mangle]
pub unsafe extern "C" fn star_byte_array_run(
    mode: u32,
    ctx: *mut c_void,
    host: Option<StarByteArrayHost>,
) -> u32 {
    if mode >= 56 || ctx.is_null() || host.is_none() {
        return 2;
    }
    contained(mode, || {
        Driver {
            ctx,
            host: host.unwrap(),
        }
        .run(mode)
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::VecDeque;
    type Step = (u32, u64, u64, u64, u64, u32);
    struct Script {
        steps: VecDeque<Step>,
        seen: Vec<(u32, u64, u64, u64)>,
        bad: bool,
    }
    unsafe extern "C" fn host(
        ctx: *mut c_void,
        op: u32,
        a: u64,
        b: u64,
        c: u64,
        out: *mut u64,
    ) -> u32 {
        let s = &mut *ctx.cast::<Script>();
        s.seen.push((op, a, b, c));
        match s.steps.pop_front() {
            Some((eo, ea, eb, ec, value, status)) if (op, a, b, c) == (eo, ea, eb, ec) => {
                *out = value;
                status
            }
            _ => {
                s.bad = true;
                2
            }
        }
    }
    fn step(op: u32, a: u64, b: u64, c: u64, out: u64) -> Step {
        (op, a, b, c, out, 0)
    }
    fn g(op: u32, out: u64) -> Step {
        step(op, 0, 0, 0, out)
    }
    fn a(index: u64, value: u64) -> Step {
        step(ARG, index, 0, 0, value)
    }
    fn sz(role: u64, value: u64) -> Step {
        step(GET_SIZE, role, 0, 0, value)
    }
    fn resize(role: u64, n: u64) -> Vec<Step> {
        vec![
            step(GET_CAPACITY, role, 0, 0, n),
            step(SET_SIZE, role, n, 0, 0),
        ]
    }
    fn append(role: u64) -> Vec<Step> {
        vec![
            sz(role, 0),
            step(GET_CAPACITY, role, 0, 0, 0),
            step(SET_SIZE, role, 0, 0, 0),
            sz(role, 0),
            step(COPY_IN, role, 0, 0, 0),
        ]
    }
    fn sub() -> Vec<Step> {
        let mut v = vec![sz(0, 0), g(INIT_RESULT, 0), g(CAPTURE, 0)];
        v.extend(append(2));
        v
    }
    fn combine(kind: u64) -> Vec<Step> {
        // Equal sizes must bind RHS as smaller; kind is checked on the expression.
        vec![
            sz(0, 1),
            sz(1, 1),
            g(ROLES, 0),
            g(INIT_RESULT, 0),
            sz(3, 1),
            step(GET_CAPACITY, 2, 0, 0, 1),
            step(SET_SIZE, 2, 1, 0, 0),
            sz(3, 1),
            step(EXPR, 0, kind, 0, 0),
            sz(3, 1),
            a(0, 0),
        ]
    }
    fn insertion(iter: bool) -> Vec<Step> {
        let mut v = if iter {
            vec![g(ITER_DISTANCE, 0), a(0, 9)]
        } else {
            vec![a(0, 0), a(1, 9)]
        };
        v.extend([g(ASSERT_INSERT, 0), sz(0, 1)]);
        v.extend(resize(0, 2));
        v.extend([
            sz(0, 2),
            g(GET_BYTE, 7),
            step(SET_BYTE, 0, 1, 7, 0),
            step(SET_BYTE, 0, 0, 9, 0),
        ]);
        if iter {
            v.push(step(POINTER, 0, 1, 0, 0));
        }
        v
    }
    fn run(mode: u32, steps: Vec<Step>, status: u32) -> Script {
        let before = [
            star_byte_array_call_count(mode, 0),
            star_byte_array_call_count(mode, 1),
            star_byte_array_call_count(mode, 2),
        ];
        let mut s = Script {
            steps: steps.into(),
            seen: vec![],
            bad: false,
        };
        let actual =
            unsafe { star_byte_array_run(mode, (&mut s as *mut Script).cast(), Some(host)) };
        assert_eq!(actual, status, "mode {mode}, trace {:?}", s.seen);
        assert!(!s.bad, "mode {mode}, unexpected callback {:?}", s.seen);
        assert!(
            s.steps.is_empty(),
            "mode {mode}, unused steps {:?}",
            s.steps
        );
        for e in 0..3 {
            let delta = u64::from(e == 0 || (e == 1 && status == 0) || (e == 2 && status == 1));
            assert_eq!(
                star_byte_array_call_count(mode, e as u32),
                before[e].wrapping_add(delta)
            );
        }
        s
    }
    #[test]
    fn all_56_routes_exact_callbacks_and_balanced_receipts() {
        for m in 0..56 {
            let mut v = match m {
                0 => {
                    let mut v = vec![g(STRLEN, 0), g(INIT_RESULT, 0)];
                    v.extend(append(2));
                    v
                }
                1 => vec![
                    g(STRLEN, 0),
                    g(INIT_RESULT, 0),
                    sz(2, 0),
                    step(GET_CAPACITY, 2, 0, 0, 1),
                    step(SET_SIZE, 2, 1, 0, 0),
                    sz(2, 1),
                    step(COPY_IN, 2, 0, 1, 0),
                    step(SET_BYTE, 2, 0, 0, 0),
                ],
                2 => vec![g(INIT_RESULT, 0), a(0, 0), step(GET_CAPACITY, 2, 0, 0, 0)],
                3 => vec![g(INIT, 0)],
                4 | 14 => {
                    let mut v = vec![a(0, 0), a(1, 9)];
                    v.extend(resize(0, 0));
                    v.push(step(FILL_BYTES, 0, 9, 0, 0));
                    v
                }
                5 | 36 => {
                    let mut v = vec![a(0, 0)];
                    v.extend(append(0));
                    v
                }
                6 | 9 => {
                    let mut v = vec![g(SAME, 0)];
                    v.extend(resize(0, 0));
                    v.push(step(CAPTURE, 1, 0, 0, 0));
                    v.extend(append(0));
                    v
                }
                7 | 10 => vec![
                    g(SAME, 0),
                    g(HAS_DATA, 1),
                    g(FREE, 0),
                    g(INIT, 0),
                    g(TAKE, 0),
                ],
                8 | 11 => vec![g(HAS_DATA, 1), g(FREE, 0), g(INIT, 0)],
                12 => vec![a(0, 0), g(GET_CAPACITY, 0)],
                13 => {
                    let mut v = vec![a(0, 1), sz(0, 0)];
                    v.extend(resize(0, 1));
                    v.extend([sz(0, 1), a(1, 9), step(SET_BYTE, 0, 0, 9, 0), sz(0, 1)]);
                    v
                }
                15 => vec![a(0, 9), step(FILL_BYTES, 0, 9, 0, 0)],
                16 => {
                    let mut v = vec![a(0, 0), a(1, 0)];
                    v.extend(sub());
                    v
                }
                17 => {
                    let mut v = vec![a(0, 0)];
                    v.extend(sub());
                    v
                }
                18 => {
                    let mut v = vec![a(0, 0), sz(0, 0)];
                    v.extend(sub());
                    v
                }
                19 | 20 => {
                    let mut v = vec![a(0, 0), sz(0, 0)];
                    v.extend(resize(0, 0));
                    v
                }
                21 | 22 | 29 | 30 | 31 => vec![
                    sz(0, 0),
                    sz(1, 0),
                    step(RETURN, u64::from(m == 30), 0, 0, 0),
                ],
                23..=25 => combine(u64::from(m - 22)),
                26 | 27 => insertion(m == 27),
                28 | 37 => {
                    let mut v = vec![a(0, 9), sz(0, 0)];
                    v.extend(resize(0, 1));
                    v.extend([sz(0, 1), step(SET_BYTE, 0, 0, 9, 0)]);
                    v
                }
                32 => vec![g(STREAM_PREFIX, 0), g(STREAM_HEX, 0)],
                33 => resize(0, 0),
                34 => {
                    let mut v = vec![a(0, 0)];
                    v.extend(resize(0, 0));
                    v
                }
                35 => {
                    let mut v = vec![step(CAPTURE, 1, 0, 0, 0)];
                    v.extend(append(0));
                    v
                }
                38 => vec![sz(0, 0), step(RETURN, 1, 0, 0, 0)],
                39 | 40 | 48 | 50 => vec![g(POINTER, 0)],
                41 => vec![sz(0, 0), g(RETURN, 0)],
                42 => vec![g(GET_CAPACITY, 0), g(RETURN, 0)],
                43 => vec![sz(0, 0), a(0, 0), g(COPY_OUT, 0)],
                44 => vec![sz(0, 0), g(COPY_OUT, 0)],
                45 => vec![a(0, 0), a(1, 0)],
                46 => vec![a(0, 0), a(1, 0), sz(0, 0), g(COPY_IN, 0)],
                47 => combine(0),
                49 | 51 => vec![sz(0, 0), step(POINTER, 0, 0, 1, 0)],
                52 => vec![a(0, 0), step(POINTER, 0, 0, 2, 0)],
                53 => vec![a(0, 0), g(GET_BYTE, 255), step(RETURN, 255, 0, 0, 0)],
                54 => vec![
                    a(0, 0),
                    sz(0, 1),
                    g(GET_BYTE, 255),
                    step(RETURN, 255, 0, 0, 0),
                ],
                55 => vec![
                    sz(0, 1),
                    g(HASH_PUT, 0),
                    sz(0, 1),
                    g(HASH_RESULT, 83),
                    step(RETURN, 83, 0, 0, 0),
                ],
                _ => unreachable!(),
            };
            v.push(g(FINISH, 0));
            run(m, v.clone(), 0);
            let mut first_pending = v[0];
            first_pending.5 = 1;
            run(m, vec![first_pending], 1);
            let mut finish_pending = v;
            finish_pending.last_mut().unwrap().5 = 1;
            run(m, finish_pending, 1);
            eprintln!(
                "byte-array mode={m} success=1 first-pending=1 finish-pending=1 receipts=balanced"
            );
        }
    }
    #[test]
    fn preflight_and_protocol_rejection_do_not_retry() {
        let mut s = Script {
            steps: VecDeque::new(),
            seen: vec![],
            bad: false,
        };
        let ctx = (&mut s as *mut Script).cast();
        let before = star_byte_array_call_count(3, 0);
        unsafe {
            assert_eq!(star_byte_array_run(3, std::ptr::null_mut(), Some(host)), 2);
            assert_eq!(star_byte_array_run(3, ctx, None), 2);
            assert_eq!(star_byte_array_run(56, ctx, Some(host)), 2);
        }
        assert_eq!(star_byte_array_call_count(3, 0), before);
        assert_eq!(star_byte_array_call_count(56, 0), 0);
        assert_eq!(star_byte_array_call_count(3, 3), 0);
        assert!(s.seen.is_empty());
        for status in [1, 2, 3, u32::MAX] {
            run(
                3,
                vec![(INIT, 0, 0, 0, 0, status)],
                if status == 1 { 1 } else { 2 },
            );
        }
        run(3, vec![g(INIT, 1)], 2);
        run(11, vec![g(HAS_DATA, 2)], 2);
        run(9, vec![g(SAME, 2)], 2);
        run(53, vec![a(0, 0), g(GET_BYTE, 256)], 2);
        run(54, vec![a(0, 1), sz(0, 1), step(THROW_AT, 1, 0, 0, 0)], 2);
        run(54, vec![a(0, 1), sz(0, 1), (THROW_AT, 1, 0, 0, 0, 1)], 1);
        run(3, vec![g(INIT, 0), (FINISH, 0, 0, 0, 0, 1)], 1);
        // A pending copy occurs after successful resize; do not roll it back or finish.
        run(
            36,
            vec![
                a(0, 1),
                sz(0, 0),
                g(GET_CAPACITY, 1),
                step(SET_SIZE, 0, 1, 0, 0),
                sz(0, 1),
                (COPY_IN, 0, 0, 1, 0, 1),
            ],
            1,
        );
    }
    #[test]
    fn fresh_sizes_dead_larger_owner_and_wrapping_arithmetic() {
        let mut v = combine(0);
        v.pop();
        // Last expression changed smaller size to zero and deleted larger owner.
        v.pop();
        v.extend([sz(3, 0), a(0, 0), g(FINISH, 0)]);
        run(47, v, 0);
        run(
            12,
            vec![
                a(0, u64::MAX),
                g(GET_CAPACITY, 1 << 63),
                g(HAS_DATA, 1),
                step(ALLOC, 0, u64::MAX, 1, 0),
                g(FINISH, 0),
            ],
            0,
        );
        run(
            36,
            vec![
                a(0, 2),
                sz(0, u64::MAX),
                g(GET_CAPACITY, 1),
                step(SET_SIZE, 0, 1, 0, 0),
                sz(0, 1),
                step(COPY_IN, 0, u64::MAX, 2, 0),
                g(FINISH, 0),
            ],
            0,
        );
        run(
            16,
            vec![
                a(0, 2),
                a(1, 2),
                sz(0, 3),
                g(INIT_RESULT, 0),
                step(CAPTURE, 0, 2, 0, 0),
                sz(2, 0),
                step(GET_CAPACITY, 2, 0, 0, 3),
                step(SET_SIZE, 2, 3, 0, 0),
                sz(2, 3),
                step(COPY_IN, 2, 0, 3, 0),
                g(FINISH, 0),
            ],
            0,
        );
        // Tail loop takes a fresh size after each expression.
        let mut v = combine(0);
        v.pop();
        v.push(a(0, 1));
        v.extend([
            sz(4, 3),
            step(GET_CAPACITY, 2, 0, 0, 3),
            step(SET_SIZE, 2, 3, 0, 0),
            sz(3, 1),
            sz(4, 3),
            step(TAIL_EXPR, 1, 0, 0, 0),
            sz(4, 2),
            g(FINISH, 0),
        ]);
        run(47, v, 0);
    }
    #[test]
    fn branch_edges_preserve_unsigned_compare_and_fresh_reads() {
        for (x, y, expected) in [(128, 127, 1), (127, 128, u64::MAX)] {
            run(
                22,
                vec![
                    sz(0, 1),
                    sz(1, 1),
                    sz(0, 1),
                    sz(1, 1),
                    g(GET_BYTE, x),
                    step(GET_BYTE, 1, 0, 0, y),
                    g(GET_BYTE, x),
                    step(GET_BYTE, 1, 0, 0, y),
                    step(RETURN, expected, 0, 0, 0),
                    g(FINISH, 0),
                ],
                0,
            );
        }
        for (left, right, result) in [(0, 1, u64::MAX), (1, 0, 1)] {
            run(
                22,
                vec![
                    sz(0, left),
                    sz(1, right),
                    step(RETURN, result, 0, 0, 0),
                    g(FINISH, 0),
                ],
                0,
            );
        }
        run(
            45,
            vec![
                a(0, 1),
                a(1, 8),
                sz(0, 5),
                sz(0, 3),
                step(COPY_OUT, 0, 1, 2, 0),
                g(FINISH, 0),
            ],
            0,
        );
        run(
            19,
            vec![
                a(0, 1),
                sz(0, 3),
                step(MOVE_BYTES, 0, 1, 2, 0),
                sz(0, 5),
                g(GET_CAPACITY, 5),
                step(SET_SIZE, 0, 4, 0, 0),
                g(FINISH, 0),
            ],
            0,
        );
        run(
            12,
            vec![
                a(0, 2),
                g(GET_CAPACITY, 1),
                g(HAS_DATA, 1),
                step(ALLOC, 0, 8, 1, 0),
                g(FINISH, 0),
            ],
            0,
        );
        run(
            12,
            vec![
                a(0, 2),
                g(GET_CAPACITY, 0),
                g(HAS_DATA, 0),
                step(ALLOC, 0, 2, 0, 0),
                g(FINISH, 0),
            ],
            0,
        );
        for mode in [6, 7, 9, 10] {
            run(mode, vec![g(SAME, 1), g(FINISH, 0)], 0);
        }
        run(11, vec![g(HAS_DATA, 0), g(FINISH, 0)], 0);
        run(13, vec![a(0, 3), sz(0, 3), g(FINISH, 0)], 0);
        run(3, vec![g(INIT, 0), g(FINISH, 1)], 2);
        let mut v = combine(0);
        v.pop();
        v.push(a(0, 2));
        run(47, v, 2);
    }
    #[test]
    fn receipt_storage_is_thread_local() {
        let before = star_byte_array_call_count(3, 0);
        std::thread::spawn(|| {
            assert_eq!(star_byte_array_call_count(3, 0), 0);
            run(3, vec![g(INIT, 0), g(FINISH, 0)], 0);
            assert_eq!(star_byte_array_call_count(3, 0), 1);
        })
        .join()
        .unwrap();
        assert_eq!(star_byte_array_call_count(3, 0), before);
    }
    #[test]
    fn counters_wrap_and_panics_are_contained_inside_rust() {
        let saved = COUNTS.with(Cell::get);
        COUNTS.with(|c| {
            let mut v = c.get();
            v[3] = [u64::MAX; 3];
            c.set(v)
        });
        run(3, vec![g(INIT, 0), g(FINISH, 0)], 0);
        assert_eq!(star_byte_array_call_count(3, 0), 0);
        assert_eq!(star_byte_array_call_count(3, 1), 0);
        run(3, vec![(INIT, 0, 0, 0, 0, 1)], 1);
        assert_eq!(star_byte_array_call_count(3, 2), 0);
        assert_eq!(contained(3, || panic!("internal Rust panic")), 3);
        COUNTS.with(|c| c.set(saved));
    }
    struct Reentry {
        size: u64,
        entered: bool,
        inner_status: u32,
        observed: u64,
    }
    struct ReentryContext {
        owner: *mut Reentry,
        inner: bool,
    }
    unsafe extern "C" fn reenter(
        ctx: *mut c_void,
        op: u32,
        a: u64,
        b: u64,
        _c: u64,
        out: *mut u64,
    ) -> u32 {
        // Raw field accesses end before recursion; no mutable reference spans a callback.
        let context = ctx.cast::<ReentryContext>();
        let p = (*context).owner;
        match op {
            ARG => *out = if (*context).inner { 3 } else { 1 },
            GET_SIZE => *out = (*p).size,
            GET_CAPACITY => *out = 10,
            SET_SIZE => {
                (*p).size = b;
                if !(*p).entered {
                    (*p).entered = true;
                    let mut child = ReentryContext {
                        owner: p,
                        inner: true,
                    };
                    (*p).inner_status = star_byte_array_run(
                        34,
                        (&mut child as *mut ReentryContext).cast(),
                        Some(reenter),
                    );
                    (*p).size = 4;
                }
            }
            COPY_IN => {
                (*p).observed = b;
            }
            FINISH => {}
            _ => {
                let _ = a;
                return 2;
            }
        }
        0
    }
    #[test]
    fn same_owner_fresh_context_reentry_has_no_lock_or_stale_size() {
        let mut r = Reentry {
            size: 2,
            entered: false,
            inner_status: 99,
            observed: 0,
        };
        let mut context = ReentryContext {
            owner: &mut r,
            inner: false,
        };
        assert_eq!(
            unsafe {
                star_byte_array_run(
                    36,
                    (&mut context as *mut ReentryContext).cast(),
                    Some(reenter),
                )
            },
            0
        );
        assert_eq!(r.inner_status, 0);
        assert_eq!(r.observed, 3);
    }
    #[test]
    fn scripted_verifier_detects_wrong_op_and_unused_steps() {
        let mut s = Script {
            steps: vec![g(FREE, 0)].into(),
            seen: vec![],
            bad: false,
        };
        assert_eq!(
            unsafe { star_byte_array_run(3, (&mut s as *mut Script).cast(), Some(host)) },
            2
        );
        assert!(s.bad);
        let mut s = Script {
            steps: vec![g(INIT, 0), g(FINISH, 0), g(FREE, 0)].into(),
            seen: vec![],
            bad: false,
        };
        assert_eq!(
            unsafe { star_byte_array_run(3, (&mut s as *mut Script).cast(), Some(host)) },
            0
        );
        assert_eq!(s.steps.len(), 1);
    }
}
