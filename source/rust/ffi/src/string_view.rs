//! StringView control flow over synchronous scalar leaves; views and iterators stay native.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

pub type StarStringViewHost =
    unsafe extern "C" fn(*mut c_void, u32, u64, u64, u64, *mut u64) -> u32;
// Each receipt mutation ends before calling the host, including recursive entry.
thread_local! { static COUNTS: [[Cell<u64>; 3]; 58] = const { [const { [const { Cell::new(0) }; 3] }; 58] }; }
fn count(mode: u32, event: usize) {
    COUNTS.with(|c| {
        let slot = &c[mode as usize][event];
        slot.set(slot.get().wrapping_add(1));
    });
}
#[no_mangle]
pub extern "C" fn star_string_view_call_count(mode: u32, event: u32) -> u64 {
    if mode >= 58 || event >= 3 {
        return 0;
    }
    COUNTS.with(|c| c[mode as usize][event as usize].get())
}
const ARG: u32 = 1;
const BYTES: u32 = 2;
const LENGTH: u32 = 3;
const VALID: u32 = 4;
const INIT: u32 = 5;
const ADVANCE: u32 = 6;
const END: u32 = 7;
const READ: u32 = 8;
const COPY: u32 = 9;
const EQUAL: u32 = 10;
const SPACE: u32 = 11;
const LOWER: u32 = 12;
const FIND_BYTES: u32 = 13;
const CALLBACK: u32 = 14;
const THROW_AT: u32 = 15;
const THROW_SUBSTR: u32 = 16;
const SUBSTR: u32 = 17;
const NATIVE_COMPARE: u32 = 18;
const SIMPLE: u32 = 19;
const RETURN: u32 = 20;
const FINISH: u32 = 21;
const ASSERT_BOUNDARY: u32 = 22;
const NP: u64 = u64::MAX;
struct Controller {
    ctx: *mut c_void,
    host: StarStringViewHost,
}
impl Controller {
    fn call(&self, op: u32, a: u64, b: u64, c: u64) -> Result<u64, u32> {
        let mut out = 0;
        // The host catches native exceptions into its context before returning.
        // Rust never borrows the opaque object or its character backing.
        match unsafe { (self.host)(self.ctx, op, a, b, c, &mut out) } {
            0 => {}
            1 => return Err(1),
            _ => return Err(2),
        }
        let valid = match op {
            END | EQUAL | SPACE | VALID => out <= 1,
            READ | LOWER => out <= u32::MAX as u64,
            NATIVE_COMPARE => out <= i32::MAX as u64 || out >= u64::MAX - i32::MAX as u64,
            ARG | BYTES | LENGTH | FIND_BYTES => true,
            THROW_AT | THROW_SUBSTR => false,
            _ => out == 0,
        };
        if valid {
            Ok(out)
        } else {
            Err(2)
        }
    }
    fn get(&self, op: u32) -> Result<u64, u32> {
        self.call(op, 0, 0, 0)
    }
    fn one(&self, op: u32, a: u64) -> Result<u64, u32> {
        self.call(op, a, 0, 0)
    }
    fn arg(&self, a: u64) -> Result<u64, u32> {
        let value = self.one(ARG, a)?;
        if a == 2 && value > 1 {
            Err(2)
        } else {
            Ok(value)
        }
    }
    fn init(&self, slot: u64, role: u64) -> Result<(), u32> {
        self.call(INIT, slot, role, 0)?;
        Ok(())
    }
    fn adv(&self, slot: u64) -> Result<(), u32> {
        self.one(ADVANCE, slot)?;
        Ok(())
    }
    fn end(&self, slot: u64, role: u64) -> Result<bool, u32> {
        Ok(self.call(END, slot, role, 0)? != 0)
    }
    fn read(&self, slot: u64) -> Result<u64, u32> {
        self.one(READ, slot)
    }
    fn eq(&self, a: u64, b: u64, cs: u64) -> Result<bool, u32> {
        Ok(self.call(EQUAL, a, b, cs)? != 0)
    }
    fn at(&self, index: u64, checked: bool) -> Result<u64, u32> {
        self.init(0, 0)?;
        let mut i: u64 = 0;
        while i < index {
            self.adv(0)?;
            if checked && self.end(0, 0)? {
                self.one(THROW_AT, i)?;
            }
            i = i.wrapping_add(1);
        }
        self.read(0)
    }
    fn compare_body(
        &self,
        mut so: u64,
        mut sl: u64,
        oo: u64,
        mut ol: u64,
        cs: u64,
    ) -> Result<u64, u32> {
        self.init(0, 0)?;
        self.init(1, 1)?;
        while so > 0 && !self.end(0, 0)? {
            self.adv(0)?;
            so = so.wrapping_sub(1);
        }
        // Preserve the native source's fixed otherOffset and decrement of otherLen.
        while oo > 0 && !self.end(1, 1)? {
            self.adv(1)?;
            ol = ol.wrapping_sub(1);
        }
        loop {
            let a = self.end(0, 0)? || sl == 0;
            let b = self.end(1, 1)? || ol == 0;
            if a && b {
                return Ok(0);
            }
            if a {
                return Ok(NP);
            }
            if b {
                return Ok(1);
            }
            let mut x = self.read(0)?;
            let mut y = self.read(1)?;
            if cs != 0 {
                x = self.one(LOWER, x)?;
                y = self.one(LOWER, y)?;
            }
            if x < y {
                return Ok(NP);
            }
            if y < x {
                return Ok(1);
            }
            self.adv(0)?;
            self.adv(1)?;
            sl = sl.wrapping_sub(1);
            ol = ol.wrapping_sub(1);
        }
    }
    fn compare(&self, so: u64, sl: u64, oo: u64, ol: u64, cs: u64) -> Result<u64, u32> {
        count(48, 0);
        let result = self.compare_body(so, sl, oo, ol, cs);
        match result {
            Ok(_) => count(48, 1),
            Err(1) => count(48, 2),
            _ => {}
        }
        result
    }
    fn find_char(&self, ch: u64, mut pos: u64, cs: u64, last: bool) -> Result<u64, u32> {
        self.init(0, 0)?;
        let mut i: u64 = 0;
        while i < pos {
            if self.end(0, 0)? {
                break;
            }
            self.adv(0)?;
            i = i.wrapping_add(1);
        }
        let mut found = NP;
        while !self.end(0, 0)? {
            if self.eq(ch, self.read(0)?, cs)? {
                if !last {
                    return Ok(pos);
                }
                found = pos;
            }
            pos = pos.wrapping_add(1);
            self.adv(0)?;
        }
        Ok(found)
    }
    fn find_pattern(&self, mut pos: u64, cs: u64, last: bool) -> Result<u64, u32> {
        if self.one(BYTES, 1)? == 0 {
            return Ok(0);
        }
        self.init(0, 0)?;
        let mut i: u64 = 0;
        while i < pos {
            if self.end(0, 0)? {
                break;
            }
            self.adv(0)?;
            i = i.wrapping_add(1);
        }
        self.init(1, 1)?;
        self.call(COPY, 2, 0, 0)?;
        let mut found = NP;
        while !self.end(0, 0)? {
            if self.eq(self.read(1)?, self.read(2)?, cs)? {
                loop {
                    self.adv(2)?;
                    self.adv(1)?;
                    if self.end(1, 1)? {
                        if !last {
                            return Ok(pos);
                        }
                        found = pos;
                        break;
                    } else if self.end(2, 0)? {
                        break;
                    }
                    if !self.eq(self.read(1)?, self.read(2)?, cs)? {
                        break;
                    }
                }
                self.init(1, 1)?;
            }
            pos = pos.wrapping_add(1);
            self.adv(0)?;
            self.call(COPY, 2, 0, 0)?;
        }
        Ok(found)
    }
    fn has(&self, ch: u64, role: u64, slot: u64) -> Result<bool, u32> {
        self.init(slot, role)?;
        while !self.end(slot, role)? {
            if self.read(slot)? == ch {
                return Ok(true);
            }
            self.adv(slot)?;
        }
        Ok(false)
    }
    fn of(&self, pos: u64, invert: bool) -> Result<u64, u32> {
        self.init(0, 0)?;
        let mut i: u64 = 0;
        while i < pos {
            self.adv(0)?;
            i = i.wrapping_add(1);
        }
        while !self.end(0, 0)? {
            let ch = self.read(0)?;
            let matches = if self.one(BYTES, 1)? == 0 {
                self.one(SPACE, ch)? != 0
            } else {
                self.has(ch, 1, 1)?
            };
            if matches != invert {
                return Ok(i);
            }
            self.adv(0)?;
            i = i.wrapping_add(1);
        }
        Ok(NP)
    }
    fn boundary(&self, mut index: u64, back: bool) -> Result<u64, u32> {
        let n = self.one(LENGTH, 0)?;
        self.call(ASSERT_BOUNDARY, index, n, 0)?;
        if !back && index == n {
            return Ok(index);
        }
        if back {
            if index == 0 {
                return Ok(0);
            }
            index = index.wrapping_sub(1);
        }
        let mut ch = self.at(index, true)?;
        while self.one(SPACE, ch)? == 0 {
            if back && index == 0 {
                return Ok(0);
            }
            index = index.wrapping_add(if back { NP } else { 1 });
            if index == n {
                return Ok(n);
            }
            ch = self.at(index, true)?;
        }
        while self.one(SPACE, ch)? != 0 {
            if back && index == 0 {
                return Ok(0);
            }
            index = index.wrapping_add(if back { NP } else { 1 });
            if index == n {
                return Ok(n);
            }
            ch = self.at(index, true)?;
        }
        Ok(if back && index != n {
            index.wrapping_add(1)
        } else {
            index
        })
    }
    fn split(&self, any: bool) -> Result<(), u32> {
        if self.one(BYTES, 1)? == 0 {
            return Ok(());
        }
        let mut beg = 0;
        loop {
            let end = self.call(FIND_BYTES, beg, u64::from(any), 0)?;
            if end == NP {
                let len = self.one(BYTES, 0)?.wrapping_sub(beg);
                self.call(CALLBACK, beg, len, 1)?;
                // The receiver can be deleted here. Only context-only FINISH follows.
                break;
            }
            self.call(CALLBACK, beg, end.wrapping_sub(beg), 0)?;
            beg = end.wrapping_add(if any { 1 } else { self.one(BYTES, 1)? });
            // FIND_BYTES and the terminal BYTES leaf consult the live receiver anew.
        }
        Ok(())
    }
    fn run(&self, mode: u32) -> Result<(), u32> {
        let mut result = 0;
        let mut scalar = true;
        match mode + 1 {
            1..=19 | 21 | 22 | 50..=58 => {
                self.one(SIMPLE, mode as u64)?;
                scalar = false;
            }
            20 => result = self.one(BYTES, 0)?,
            23 | 24 => result = self.one(LENGTH, 0)?,
            25 => result = self.get(VALID)?,
            26 => result = u64::from(self.one(BYTES, 0)? == 0),
            27 | 28 => result = self.at(self.arg(0)?, mode == 27)?,
            29 => {
                let n = self.one(LENGTH, 1)?;
                if n == 0 {
                    result = 1;
                } else {
                    let m = self.one(LENGTH, 0)?;
                    result = u64::from(
                        n <= m && self.compare(m.wrapping_sub(n), NP, 0, NP, self.arg(2)?)? == 0,
                    );
                }
            }
            30 => {
                result = u64::from(
                    self.one(BYTES, 0)? != 0
                        && self.eq(
                            self.arg(0)?,
                            self.at(self.one(LENGTH, 0)?.wrapping_sub(1), false)?,
                            self.arg(2)?,
                        )?,
                )
            }
            31 => {
                if self.one(BYTES, 1)? == 0 {
                    result = 1;
                } else {
                    let n = self.one(LENGTH, 1)?;
                    self.init(0, 0)?;
                    let mut enough = true;
                    let mut i: u64 = 0;
                    while i != n {
                        if self.end(0, 0)? {
                            enough = false;
                            break;
                        }
                        self.adv(0)?;
                        i = i.wrapping_add(1);
                    }
                    result = u64::from(enough && self.compare(0, n, 0, NP, self.arg(2)?)? == 0);
                }
            }
            32 => {
                result = u64::from(
                    self.one(BYTES, 0)? != 0
                        && self.eq(self.arg(0)?, self.at(0, false)?, self.arg(2)?)?,
                )
            }
            33 | 34 => {
                self.split(mode == 32)?;
                scalar = false;
            }
            35 => result = u64::from(self.has(self.arg(0)?, 0, 0)?),
            36 => {
                result = if self.one(BYTES, 0)? == 0 {
                    self.one(SPACE, self.arg(0)?)?
                } else {
                    u64::from(self.has(self.arg(0)?, 0, 0)?)
                }
            }
            37 => result = self.find_char(self.arg(0)?, self.arg(1)?, self.arg(2)?, false)?,
            38 => result = self.find_pattern(self.arg(1)?, self.arg(2)?, false)?,
            39 => result = self.find_char(self.arg(0)?, 0, self.arg(2)?, true)?,
            40 => result = self.find_pattern(0, self.arg(2)?, true)?,
            41 | 42 => result = self.of(self.arg(1)?, mode == 41)?,
            43 => {
                let back = self.arg(1)?;
                if back > 1 {
                    return Err(2);
                }
                result = self.boundary(self.arg(0)?, back != 0)?;
            }
            44 => result = u64::from(self.find_pattern(0, self.arg(2)?, false)? != NP),
            45..=47 => {
                let cs = if mode == 46 { 1 } else { self.arg(2)? };
                result = if cs != 0 {
                    self.compare(0, NP, 0, NP, cs)?
                } else {
                    self.get(NATIVE_COMPARE)?
                };
                if mode != 44 {
                    result = u64::from(result == 0);
                }
            }
            48 => {
                let pos = self.arg(0)?;
                let n = self.arg(1)?;
                self.init(0, 0)?;
                let mut i: u64 = 0;
                while i != pos {
                    if self.end(0, 0)? {
                        self.call(THROW_SUBSTR, pos, n, 0)?;
                    }
                    self.adv(0)?;
                    i = i.wrapping_add(1);
                }
                self.call(COPY, 3, 0, 0)?;
                i = 0;
                while i != n {
                    if self.end(0, 0)? {
                        break;
                    }
                    self.adv(0)?;
                    i = i.wrapping_add(1);
                }
                self.call(SUBSTR, 3, 0, 0)?;
                scalar = false;
            }
            // The entrypoint already counts a direct private-comparison route.
            49 => {
                result = self.compare_body(
                    self.arg(0)?,
                    self.arg(1)?,
                    self.arg(3)?,
                    self.arg(4)?,
                    self.arg(2)?,
                )?
            }
            _ => return Err(2),
        }
        if scalar {
            self.one(RETURN, result)?;
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
/// # Safety
/// `ctx` and `host` must implement the synchronous native scalar protocol.
/// The host must catch every native exception; none may unwind through Rust.
#[no_mangle]
pub unsafe extern "C" fn star_string_view_run(
    mode: u32,
    ctx: *mut c_void,
    host: Option<StarStringViewHost>,
) -> u32 {
    if mode >= 58 || ctx.is_null() || host.is_none() {
        return 2;
    }
    contained(mode, || {
        Controller {
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
    // Scripted scalar responses are protocol traces, not a replacement UTF/view implementation.
    type Step = (u32, u64, u64, u64, u64, u32);
    struct Script {
        steps: VecDeque<Step>,
        seen: Vec<(u32, u64, u64, u64)>,
        bad: bool,
        deleted: bool,
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
        if s.deleted && op != FINISH {
            s.bad = true;
            return 2;
        }
        if op == CALLBACK && c == 1 {
            s.deleted = true;
        }
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
    fn one(op: u32, a: u64, out: u64) -> Step {
        step(op, a, 0, 0, out)
    }
    fn arg(a: u64, out: u64) -> Step {
        one(ARG, a, out)
    }
    fn init(slot: u64, role: u64) -> Step {
        step(INIT, slot, role, 0, 0)
    }
    fn end(slot: u64, role: u64, value: u64) -> Step {
        step(END, slot, role, 0, value)
    }
    fn empty_compare() -> Vec<Step> {
        vec![init(0, 0), init(1, 1), end(0, 0, 1), end(1, 1, 1)]
    }
    fn script(steps: Vec<Step>) -> Script {
        Script {
            steps: steps.into(),
            seen: vec![],
            bad: false,
            deleted: false,
        }
    }
    fn counts(mode: u32) -> [u64; 3] {
        std::array::from_fn(|e| star_string_view_call_count(mode, e as u32))
    }
    fn run(mode: u32, steps: Vec<Step>, status: u32) -> Script {
        let before = counts(mode);
        let mut s = script(steps);
        let actual =
            unsafe { star_string_view_run(mode, (&mut s as *mut Script).cast(), Some(host)) };
        assert_eq!(actual, status, "mode {mode} trace {:?}", s.seen);
        assert!(!s.bad, "mode {mode} unexpected trace {:?}", s.seen);
        assert!(s.steps.is_empty(), "mode {mode} unused {:?}", s.steps);
        for e in 0..3 {
            assert_eq!(
                counts(mode)[e],
                before[e].wrapping_add(u64::from(
                    e == 0 || (e == 1 && status == 0) || (e == 2 && status == 1)
                ))
            );
        }
        s
    }
    fn returned(mut v: Vec<Step>, value: u64) -> Vec<Step> {
        v.extend([one(RETURN, value, 0), g(FINISH, 0)]);
        v
    }
    // These routes follow host_controller.cpp's mode+1 switch and short circuits.
    // No native execution or expected corpus is generated by these tests.
    fn route(mode: u32) -> Vec<Step> {
        let (mut v, scalar) = match mode {
            0..=18 | 20 | 21 | 49..=57 => (vec![one(SIMPLE, mode as u64, 0)], None),
            19 => (vec![g(BYTES, 3)], Some(3)),
            22 | 23 => (vec![g(LENGTH, 3)], Some(3)),
            24 => (vec![g(VALID, 1)], Some(1)),
            25 => (vec![g(BYTES, 0)], Some(1)),
            26 | 27 => (vec![arg(0, 0), init(0, 0), g(READ, 65)], Some(65)),
            28 => (vec![one(LENGTH, 1, 0)], Some(1)),
            29 | 31 => (vec![g(BYTES, 0)], Some(0)),
            30 => (vec![one(BYTES, 1, 0)], Some(1)),
            32 | 33 => (vec![one(BYTES, 1, 0)], None),
            34 => (vec![arg(0, 65), init(0, 0), end(0, 0, 1)], Some(0)),
            35 => (vec![g(BYTES, 0), arg(0, 32), one(SPACE, 32, 1)], Some(1)),
            36 => (
                vec![arg(0, 65), arg(1, 0), arg(2, 0), init(0, 0), end(0, 0, 1)],
                Some(NP),
            ),
            37 => (vec![arg(1, 9), arg(2, 0), one(BYTES, 1, 0)], Some(0)),
            38 => (
                vec![arg(0, 65), arg(2, 0), init(0, 0), end(0, 0, 1)],
                Some(NP),
            ),
            39 => (vec![arg(2, 0), one(BYTES, 1, 0)], Some(0)),
            40 | 41 => (vec![arg(1, 0), init(0, 0), end(0, 0, 1)], Some(NP)),
            42 => (
                vec![arg(1, 0), arg(0, 0), g(LENGTH, 0), g(ASSERT_BOUNDARY, 0)],
                Some(0),
            ),
            43 => (vec![arg(2, 0), one(BYTES, 1, 0)], Some(1)),
            44 => (vec![arg(2, 0), g(NATIVE_COMPARE, NP)], Some(NP)),
            45 => (vec![arg(2, 0), g(NATIVE_COMPARE, 0)], Some(1)),
            46 => (empty_compare(), Some(1)),
            47 => (
                vec![
                    arg(0, 0),
                    arg(1, 0),
                    init(0, 0),
                    step(COPY, 3, 0, 0, 0),
                    step(SUBSTR, 3, 0, 0, 0),
                ],
                None,
            ),
            48 => {
                let mut v = vec![arg(0, 0), arg(1, NP), arg(3, 0), arg(4, NP), arg(2, 0)];
                v.extend(empty_compare());
                (v, Some(0))
            }
            _ => unreachable!(),
        };
        if let Some(value) = scalar {
            v.push(one(RETURN, value, 0));
        }
        v.push(g(FINISH, 0));
        v
    }
    #[test]
    fn all_58_routes_exact_trace_and_pending_at_every_leaf() {
        std::thread::spawn(|| {
            for mode in 0..58 {
                let v = route(mode);
                run(mode, v.clone(), 0);
                // Pending at every call must stop immediately, including RETURN/FINISH.
                for i in 0..v.len() {
                    let mut pending = v[..=i].to_vec(); pending[i].5 = 1;
                    run(mode, pending, 1);
                }
                eprintln!("string-view mode={mode} exact-route=pass pending-prefixes={} receipts=balanced", v.len());
            }
        }).join().unwrap();
    }
    #[test]
    fn preflight_status_and_strict_leaf_validation() {
        std::thread::spawn(|| {
            let mut s = script(vec![]);
            let ctx = (&mut s as *mut Script).cast();
            unsafe {
                assert_eq!(star_string_view_run(4, std::ptr::null_mut(), Some(host)), 2);
                assert_eq!(star_string_view_run(4, ctx, None), 2);
                assert_eq!(star_string_view_run(58, ctx, Some(host)), 2);
                assert_eq!(star_string_view_run(u32::MAX, ctx, Some(host)), 2);
            }
            assert_eq!(counts(4), [0; 3]);
            assert!(s.seen.is_empty());
            assert_eq!(star_string_view_call_count(58, 0), 0);
            assert_eq!(star_string_view_call_count(0, 3), 0);
            for status in [1, 2, 3, 42, u32::MAX] {
                run(
                    4,
                    vec![(SIMPLE, 4, 0, 0, 0, status)],
                    if status == 1 { 1 } else { 2 },
                );
            }
            run(4, vec![one(SIMPLE, 4, 1)], 2);
            run(24, vec![g(VALID, 2)], 2);
            run(44, vec![arg(2, 2)], 2);
            run(42, vec![arg(1, 2)], 2);
            run(26, vec![arg(0, 0), init(0, 0), g(READ, 1u64 << 32)], 2);
            for value in [0, i32::MAX as u64, NP - i32::MAX as u64, NP] {
                run(
                    44,
                    returned(vec![arg(2, 0), g(NATIVE_COMPARE, value)], value),
                    0,
                );
            }
            for value in [i32::MAX as u64 + 1, NP - i32::MAX as u64 - 1] {
                run(44, vec![arg(2, 0), g(NATIVE_COMPARE, value)], 2);
            }
            // Exercise every validation class directly, including unused malformed outputs.
            for op in [
                END,
                EQUAL,
                SPACE,
                VALID,
                READ,
                LOWER,
                INIT,
                ADVANCE,
                COPY,
                CALLBACK,
                SUBSTR,
                SIMPLE,
                RETURN,
                FINISH,
                ASSERT_BOUNDARY,
                THROW_AT,
                THROW_SUBSTR,
            ] {
                let value = match op {
                    END | EQUAL | SPACE | VALID => 2,
                    READ | LOWER => 1u64 << 32,
                    THROW_AT | THROW_SUBSTR => 0,
                    _ => 1,
                };
                let mut s = script(vec![g(op, value)]);
                let d = Controller {
                    ctx: (&mut s as *mut Script).cast(),
                    host,
                };
                assert_eq!(d.get(op), Err(2), "op {op}");
                assert!(!s.bad);
                assert!(s.steps.is_empty());
            }
            for op in [READ, LOWER] {
                let mut s = script(vec![g(op, u32::MAX as u64)]);
                assert_eq!(
                    Controller {
                        ctx: (&mut s as *mut Script).cast(),
                        host
                    }
                    .get(op),
                    Ok(u32::MAX as u64)
                );
            }
            for status in [0, 1] {
                let mut v = vec![arg(0, 1), init(0, 0), g(ADVANCE, 0), end(0, 0, 1)];
                v.push((THROW_AT, 0, 0, 0, 0, status));
                run(27, v, if status == 0 { 2 } else { 1 });
                run(
                    47,
                    vec![
                        arg(0, 1),
                        arg(1, NP),
                        init(0, 0),
                        end(0, 0, 1),
                        (THROW_SUBSTR, 1, NP, 0, 0, status),
                    ],
                    if status == 0 { 2 } else { 1 },
                );
            }
        })
        .join()
        .unwrap();
    }
    #[test]
    fn split_live_receiver_terminal_deletion_and_wrapping() {
        std::thread::spawn(|| {
            for mode in [32, 33] {
                let any = u64::from(mode == 32);
                let mut v = vec![
                    one(BYTES, 1, 2),
                    step(FIND_BYTES, 0, any, 0, 2),
                    step(CALLBACK, 0, 2, 0, 0),
                ];
                if mode == 33 {
                    v.push(one(BYTES, 1, 2));
                }
                let beg = if mode == 32 { 3 } else { 4 };
                // Receiver grew during the nonterminal callback; terminal size is fresh.
                v.extend([
                    step(FIND_BYTES, beg, any, 0, NP),
                    g(BYTES, 9),
                    step(CALLBACK, beg, 9 - beg, 1, 0),
                    g(FINISH, 0),
                ]);
                assert!(run(mode, v.clone(), 0).deleted);
                v.pop();
                v.last_mut().unwrap().5 = 1;
                assert!(run(mode, v, 1).deleted);
            }
            run(
                33,
                vec![
                    one(BYTES, 1, 2),
                    g(FIND_BYTES, NP - 1),
                    step(CALLBACK, 0, NP - 1, 0, 0),
                    one(BYTES, 1, 3),
                    one(FIND_BYTES, 1, NP),
                    g(BYTES, 0),
                    step(CALLBACK, 1, NP, 1, 0),
                    g(FINISH, 0),
                ],
                0,
            );
            // Trailing empty field is a terminal callback, not silently dropped.
            run(
                32,
                vec![
                    one(BYTES, 1, 1),
                    step(FIND_BYTES, 0, 1, 0, 0),
                    g(CALLBACK, 0),
                    step(FIND_BYTES, 1, 1, 0, NP),
                    g(BYTES, 1),
                    step(CALLBACK, 1, 0, 1, 0),
                    g(FINISH, 0),
                ],
                0,
            );
        })
        .join()
        .unwrap();
    }
    #[test]
    fn comparison_private_receipts_fixed_other_offset_and_wrapping() {
        std::thread::spawn(|| {
            // A direct mode48 call counts once; logical calls from mode46 also count48.
            run(48, route(48), 0);
            assert_eq!(counts(48), [1, 1, 0]);
            run(46, route(46), 0);
            assert_eq!(counts(48), [2, 2, 0]);
            run(46, vec![(INIT, 0, 0, 0, 0, 1)], 1);
            assert_eq!(counts(48), [3, 2, 1]);
            run(46, vec![g(INIT, 1)], 2);
            assert_eq!(counts(48), [4, 2, 1]);
            // otherOffset stays 1 while two advances decrement otherLen 0 through wrap.
            let v = vec![
                arg(0, 0),
                arg(1, NP),
                arg(3, 1),
                arg(4, 0),
                arg(2, 0),
                init(0, 0),
                init(1, 1),
                end(1, 1, 0),
                one(ADVANCE, 1, 0),
                end(1, 1, 0),
                one(ADVANCE, 1, 0),
                end(1, 1, 1),
                end(0, 0, 0),
                end(1, 1, 1),
            ];
            run(48, returned(v, 1), 0);
            for (x, y, want) in [(65, 66, NP), (66, 65, 1)] {
                let mut v = vec![
                    arg(2, 1),
                    init(0, 0),
                    init(1, 1),
                    end(0, 0, 0),
                    end(1, 1, 0),
                    g(READ, x),
                    one(READ, 1, y),
                    one(LOWER, x, x),
                    one(LOWER, y, y),
                ];
                v = returned(v, want);
                run(44, v, 0);
            }
            // Equal characters decrement unbounded lengths and advance both iterators.
            let v = vec![
                arg(2, 1),
                init(0, 0),
                init(1, 1),
                end(0, 0, 0),
                end(1, 1, 0),
                g(READ, 65),
                one(READ, 1, 65),
                one(LOWER, 65, 97),
                one(LOWER, 65, 97),
                g(ADVANCE, 0),
                one(ADVANCE, 1, 0),
                end(0, 0, 1),
                end(1, 1, 1),
            ];
            run(44, returned(v, 0), 0);
        })
        .join()
        .unwrap();
    }
    #[test]
    fn search_loops_exact_scalar_trace() {
        std::thread::spawn(|| {
            // Last-character search continues after a match and reports scalar position.
            let v = vec![
                arg(0, 65),
                arg(2, 0),
                init(0, 0),
                end(0, 0, 0),
                g(READ, 65),
                step(EQUAL, 65, 65, 0, 1),
                g(ADVANCE, 0),
                end(0, 0, 0),
                g(READ, 66),
                step(EQUAL, 65, 66, 0, 0),
                g(ADVANCE, 0),
                end(0, 0, 1),
            ];
            run(38, returned(v, 0), 0);
            // Position advancement stops at native iterator end, even for NPos.
            run(
                36,
                returned(
                    vec![
                        arg(0, 65),
                        arg(1, NP),
                        arg(2, 0),
                        init(0, 0),
                        end(0, 0, 1),
                        end(0, 0, 1),
                    ],
                    NP,
                ),
                0,
            );
            // Pattern match uses independent start/candidate/pattern iterator slots.
            let v = vec![
                arg(1, 0),
                arg(2, 0),
                one(BYTES, 1, 2),
                init(0, 0),
                init(1, 1),
                step(COPY, 2, 0, 0, 0),
                end(0, 0, 0),
                one(READ, 1, 65),
                one(READ, 2, 65),
                step(EQUAL, 65, 65, 0, 1),
                one(ADVANCE, 2, 0),
                one(ADVANCE, 1, 0),
                end(1, 1, 0),
                end(2, 0, 0),
                one(READ, 1, 66),
                one(READ, 2, 66),
                step(EQUAL, 66, 66, 0, 1),
                one(ADVANCE, 2, 0),
                one(ADVANCE, 1, 0),
                end(1, 1, 1),
            ];
            run(37, returned(v, 0), 0);
            // Last-pattern match resets pattern and copies the next start after a hit.
            let v = vec![
                arg(2, 0),
                one(BYTES, 1, 1),
                init(0, 0),
                init(1, 1),
                step(COPY, 2, 0, 0, 0),
                end(0, 0, 0),
                one(READ, 1, 65),
                one(READ, 2, 65),
                step(EQUAL, 65, 65, 0, 1),
                one(ADVANCE, 2, 0),
                one(ADVANCE, 1, 0),
                end(1, 1, 1),
                init(1, 1),
                g(ADVANCE, 0),
                step(COPY, 2, 0, 0, 0),
                end(0, 0, 1),
            ];
            run(39, returned(v, 0), 0);
            // Empty set dispatches whitespace; nonempty set scans the native slot1.
            run(
                40,
                returned(
                    vec![
                        arg(1, 1),
                        init(0, 0),
                        g(ADVANCE, 0),
                        end(0, 0, 0),
                        g(READ, 32),
                        one(BYTES, 1, 0),
                        one(SPACE, 32, 1),
                    ],
                    1,
                ),
                0,
            );
            run(
                41,
                returned(
                    vec![
                        arg(1, 0),
                        init(0, 0),
                        end(0, 0, 0),
                        g(READ, 65),
                        one(BYTES, 1, 1),
                        init(1, 1),
                        end(1, 1, 0),
                        one(READ, 1, 66),
                        one(ADVANCE, 1, 0),
                        end(1, 1, 1),
                    ],
                    0,
                ),
                0,
            );
            run(
                34,
                returned(
                    vec![
                        arg(0, 66),
                        init(0, 0),
                        end(0, 0, 0),
                        g(READ, 65),
                        g(ADVANCE, 0),
                        end(0, 0, 0),
                        g(READ, 66),
                    ],
                    1,
                ),
                0,
            );
        })
        .join()
        .unwrap();
    }
    #[test]
    fn prefixes_suffixes_substring_and_boundary_branches() {
        std::thread::spawn(|| {
            run(28, returned(vec![one(LENGTH, 1, 2), g(LENGTH, 1)], 0), 0);
            run(
                30,
                returned(
                    vec![
                        one(BYTES, 1, 1),
                        one(LENGTH, 1, 1),
                        init(0, 0),
                        end(0, 0, 1),
                    ],
                    0,
                ),
                0,
            );
            for mode in [29, 31] {
                let mut v = vec![g(BYTES, 1), arg(0, 65)];
                if mode == 29 {
                    v.push(g(LENGTH, 1));
                }
                v.extend([
                    init(0, 0),
                    g(READ, 65),
                    arg(2, 0),
                    step(EQUAL, 65, 65, 0, 1),
                ]);
                run(mode, returned(v, 1), 0);
            }
            run(
                47,
                vec![
                    arg(0, 1),
                    arg(1, NP),
                    init(0, 0),
                    end(0, 0, 0),
                    g(ADVANCE, 0),
                    step(COPY, 3, 0, 0, 0),
                    end(0, 0, 0),
                    g(ADVANCE, 0),
                    end(0, 0, 1),
                    step(SUBSTR, 3, 0, 0, 0),
                    g(FINISH, 0),
                ],
                0,
            );
            run(
                42,
                returned(
                    vec![
                        arg(1, 1),
                        arg(0, 0),
                        g(LENGTH, 3),
                        step(ASSERT_BOUNDARY, 0, 3, 0, 0),
                    ],
                    0,
                ),
                0,
            );
            // Forward word then space; at() deliberately restarts iterator traversal.
            let v = vec![
                arg(1, 0),
                arg(0, 0),
                g(LENGTH, 3),
                step(ASSERT_BOUNDARY, 0, 3, 0, 0),
                init(0, 0),
                g(READ, 65),
                one(SPACE, 65, 0),
                init(0, 0),
                g(ADVANCE, 0),
                end(0, 0, 0),
                g(READ, 32),
                one(SPACE, 32, 1),
                one(SPACE, 32, 1),
                init(0, 0),
                g(ADVANCE, 0),
                end(0, 0, 0),
                g(ADVANCE, 0),
                end(0, 0, 0),
                g(READ, 66),
                one(SPACE, 66, 0),
            ];
            run(42, returned(v, 2), 0);
        })
        .join()
        .unwrap();
    }
    #[test]
    fn comparison_prefix_suffix_and_backward_boundary_traces() {
        std::thread::spawn(|| {
            // Suffix advances the receiver offset before comparing native scalar slots.
            let v = vec![
                one(LENGTH, 1, 1),
                g(LENGTH, 2),
                arg(2, 0),
                init(0, 0),
                init(1, 1),
                end(0, 0, 0),
                g(ADVANCE, 0),
                end(0, 0, 0),
                end(1, 1, 0),
                g(READ, 65),
                one(READ, 1, 65),
                g(ADVANCE, 0),
                one(ADVANCE, 1, 0),
                end(0, 0, 1),
                end(1, 1, 1),
            ];
            run(28, returned(v, 1), 0);
            // Prefix first proves enough scalars, then restarts comparison with n=1.
            let v = vec![
                one(BYTES, 1, 1),
                one(LENGTH, 1, 1),
                init(0, 0),
                end(0, 0, 0),
                g(ADVANCE, 0),
                arg(2, 0),
                init(0, 0),
                init(1, 1),
                end(0, 0, 0),
                end(1, 1, 0),
                g(READ, 65),
                one(READ, 1, 65),
                g(ADVANCE, 0),
                one(ADVANCE, 1, 0),
                end(0, 0, 0),
                end(1, 1, 1),
            ];
            run(30, returned(v, 1), 0);
            assert_eq!(counts(48), [2, 2, 0]);
            // Backward traversal consumes the word, then whitespace, returning index+1.
            let v = vec![
                arg(1, 1),
                arg(0, 3),
                g(LENGTH, 3),
                step(ASSERT_BOUNDARY, 3, 3, 0, 0),
                init(0, 0),
                g(ADVANCE, 0),
                end(0, 0, 0),
                g(ADVANCE, 0),
                end(0, 0, 0),
                g(READ, 66),
                one(SPACE, 66, 0),
                init(0, 0),
                g(ADVANCE, 0),
                end(0, 0, 0),
                g(READ, 32),
                one(SPACE, 32, 1),
                one(SPACE, 32, 1),
                init(0, 0),
                g(READ, 65),
                one(SPACE, 65, 0),
            ];
            run(42, returned(v, 1), 0);
            // Partial pattern match stops on receiver end and resets the pattern slot.
            let v = vec![
                arg(1, 0),
                arg(2, 0),
                one(BYTES, 1, 2),
                init(0, 0),
                init(1, 1),
                step(COPY, 2, 0, 0, 0),
                end(0, 0, 0),
                one(READ, 1, 65),
                one(READ, 2, 65),
                step(EQUAL, 65, 65, 0, 1),
                one(ADVANCE, 2, 0),
                one(ADVANCE, 1, 0),
                end(1, 1, 0),
                end(2, 0, 1),
                init(1, 1),
                g(ADVANCE, 0),
                step(COPY, 2, 0, 0, 0),
                end(0, 0, 1),
            ];
            run(37, returned(v, NP), 0);
            // Initial mismatch advances the start without resetting the pattern slot.
            let v = vec![
                arg(1, 0),
                arg(2, 0),
                one(BYTES, 1, 1),
                init(0, 0),
                init(1, 1),
                step(COPY, 2, 0, 0, 0),
                end(0, 0, 0),
                one(READ, 1, 65),
                one(READ, 2, 66),
                step(EQUAL, 65, 66, 0, 0),
                g(ADVANCE, 0),
                step(COPY, 2, 0, 0, 0),
                end(0, 0, 1),
            ];
            run(37, returned(v, NP), 0);
        })
        .join()
        .unwrap();
    }
    #[test]
    fn counters_tls_wrapping_and_rust_only_panic_containment() {
        let before = counts(4);
        std::thread::spawn(|| {
            assert_eq!(counts(4), [0; 3]);
            COUNTS.with(|c| {
                for slot in &c[4] {
                    slot.set(NP);
                }
            });
            run(4, route(4), 0);
            assert_eq!(counts(4), [0, 0, NP]);
            run(4, vec![(SIMPLE, 4, 0, 0, 0, 1)], 1);
            assert_eq!(counts(4), [1, 0, 0]);
            assert_eq!(
                contained(4, || panic!(
                    "contained Rust panic; no extern callback involved"
                )),
                3
            );
            assert_eq!(counts(4), [2, 0, 0]);
            COUNTS.with(|c| {
                for slot in &c[48] {
                    slot.set(NP);
                }
            });
            run(46, route(46), 0);
            assert_eq!(counts(48), [0, 0, NP]);
            run(46, vec![(INIT, 0, 0, 0, 0, 1)], 1);
            assert_eq!(counts(48), [1, 0, 0]);
        })
        .join()
        .unwrap();
        assert_eq!(counts(4), before);
    }
    struct Reentry {
        entered: bool,
        child: u32,
        dead: bool,
        bad: bool,
        size: u64,
        terminal_len: u64,
    }
    unsafe extern "C" fn reenter(
        ctx: *mut c_void,
        op: u32,
        a: u64,
        b: u64,
        c: u64,
        out: *mut u64,
    ) -> u32 {
        let p = ctx.cast::<Reentry>();
        // Raw field accesses end before recursion; no reference is held across it.
        if (*p).dead && op != FINISH {
            (*p).bad = true;
            return 2;
        }
        match op {
            BYTES => *out = if a == 1 { 1 } else { (*p).size },
            FIND_BYTES => *out = if (*p).entered { NP } else { 0 },
            CALLBACK => {
                if c == 0 {
                    (*p).entered = true;
                    (*p).child = star_string_view_run(4, ctx, Some(reenter));
                    (*p).size = 5;
                } else {
                    (*p).terminal_len = b;
                    (*p).dead = true;
                }
            }
            SIMPLE | FINISH => {}
            _ => {
                (*p).bad = true;
                return 2;
            }
        }
        0
    }
    #[test]
    fn callback_reentry_has_no_tls_borrow_and_rereads_receiver() {
        std::thread::spawn(|| {
            let mut r = Reentry {
                entered: false,
                child: 99,
                dead: false,
                bad: false,
                size: 1,
                terminal_len: NP,
            };
            assert_eq!(
                unsafe { star_string_view_run(32, (&mut r as *mut Reentry).cast(), Some(reenter)) },
                0
            );
            assert_eq!(r.child, 0);
            assert_eq!(r.terminal_len, 4);
            assert!(r.dead && !r.bad);
            assert_eq!(counts(4), [1, 1, 0]);
            assert_eq!(counts(32), [1, 1, 0]);
        })
        .join()
        .unwrap();
    }
    #[test]
    fn trace_verifier_known_negative_controls() {
        let mut s = script(vec![g(ADVANCE, 0)]);
        assert_eq!(
            unsafe { star_string_view_run(4, (&mut s as *mut Script).cast(), Some(host)) },
            2
        );
        assert!(s.bad);
        let mut v = route(4);
        v.push(g(ADVANCE, 0));
        let mut s = script(v);
        assert_eq!(
            unsafe { star_string_view_run(4, (&mut s as *mut Script).cast(), Some(host)) },
            0
        );
        assert_eq!(s.steps.len(), 1);
        let mut s = script(vec![g(BYTES, 0)]);
        s.deleted = true;
        assert_eq!(
            Controller {
                ctx: (&mut s as *mut Script).cast(),
                host
            }
            .get(BYTES),
            Err(2)
        );
        assert!(s.bad);
    }
}
