//! Legacy compiled Unicode operations. Raw conditional reads are intentional:
//! NPos inputs need only provide bytes actually inspected, including their NUL.
use std::cell::Cell;
use std::panic::{catch_unwind, AssertUnwindSafe};
thread_local! { static CALLS: Cell<[u64;10]> = const { Cell::new([0;10]) }; }
#[no_mangle]
pub extern "C" fn star_unicode_call_count(op: u32) -> u64 {
    CALLS.with(|c| c.get().get(op as usize).copied().unwrap_or(0))
}
fn run(op: usize, f: impl FnOnce() -> i32) -> i32 {
    let s = catch_unwind(AssertUnwindSafe(f)).unwrap_or(3);
    if matches!(s, 0 | 4 | 5 | 6) {
        CALLS.with(|c| {
            let mut v = c.get();
            v[op] = v[op].wrapping_add(1);
            c.set(v);
        });
    }
    s
}
fn range(p: usize, n: usize) -> Option<(usize, usize)> {
    if n > isize::MAX as usize || (n > 0 && p == 0) {
        return None;
    }
    Some((p, p.checked_add(n)?))
}
fn overlap(a: (usize, usize), b: (usize, usize)) -> bool {
    a.0 < a.1 && b.0 < b.1 && a.0 < b.1 && b.0 < a.1
}
fn meta(input: usize, len: usize, outputs: &[(usize, usize)]) -> bool {
    let Some(ir) = range(input, if len == usize::MAX { 1 } else { len }) else {
        return false;
    };
    for (i, &(p, n)) in outputs.iter().enumerate() {
        if p % n != 0 {
            return false;
        }
        let Some(r) = range(p, n) else {
            return false;
        };
        if overlap(ir, r) {
            return false;
        }
        for &(q, m) in &outputs[..i] {
            if overlap(r, (q, q + m)) {
                return false;
            }
        }
    }
    true
}
fn lead(c: u32) -> bool {
    (0xd800..=0xdbff).contains(&c)
}
fn trail(c: u32) -> bool {
    (0xdc00..=0xdfff).contains(&c)
}
fn surrogate(c: u32) -> bool {
    (0xd800..=0xdfff).contains(&c)
}
// No standard UTF-8 decoder: preserve the reference's staged checks and reads.
unsafe fn one(p: *const u8, n: usize, stop: bool) -> (u32, usize, bool) {
    if n == 0 || (stop && p.read() == 0) {
        return (0, 0, true);
    }
    let a = p.read() as u32;
    if a & 0x80 == 0 {
        return (a, 1, true);
    }
    if n == 1 {
        return (0xfffd, 1, false);
    }
    if a & 0xe0 == 0xc0 && p.add(1).read() & 0xc0 == 0x80 {
        let c = ((a & 31) << 6) | (p.add(1).read() as u32 & 63);
        return if c >= 0x80 {
            (c, 2, true)
        } else {
            (0xfffd, 1, false)
        };
    }
    if n == 2 {
        return (0xfffd, 1, false);
    }
    if a & 0xf0 == 0xe0 && p.add(1).read() & 0xc0 == 0x80 && p.add(2).read() & 0xc0 == 0x80 {
        let c =
            ((a & 15) << 12) | ((p.add(1).read() as u32 & 63) << 6) | (p.add(2).read() as u32 & 63);
        return if c >= 0x800 && !surrogate(c) {
            (c, 3, true)
        } else {
            (0xfffd, 1, false)
        };
    }
    if n == 3 {
        return (0xfffd, 1, false);
    }
    if a & 0xf8 == 0xf0
        && p.add(1).read() & 0xc0 == 0x80
        && p.add(2).read() & 0xc0 == 0x80
        && p.add(3).read() & 0xc0 == 0x80
    {
        let c = ((a & 7) << 18)
            | ((p.add(1).read() as u32 & 63) << 12)
            | ((p.add(2).read() as u32 & 63) << 6)
            | (p.add(3).read() as u32 & 63);
        return if (0x10000..=0x10ffff).contains(&c) {
            (c, 4, true)
        } else {
            (0xfffd, 1, false)
        };
    }
    (0xfffd, 1, false)
}
// Validation/length omit low payload bits in the original. Those bits cannot
// alter the threshold or surrogate classification, so one() is equivalent.
#[no_mangle]
pub unsafe extern "C" fn star_unicode_validate(p: *const u8, n: usize, out: *mut u32) -> i32 {
    run(0, || {
        if !meta(p as usize, n, &[(out as usize, 4)]) {
            return 2;
        }
        let mut at = p;
        let mut left = n;
        let stop = n == usize::MAX;
        loop {
            let (_, used, valid) = one(at, left, stop);
            if !valid {
                out.write(0);
                return 0;
            }
            if used == 0 {
                out.write(1);
                return 0;
            }
            at = at.add(used);
            left -= used;
        }
    })
}
#[no_mangle]
pub unsafe extern "C" fn star_unicode_length(p: *const u8, n: usize, out: *mut usize) -> i32 {
    run(1, || {
        if !meta(
            p as usize,
            n,
            &[(out as usize, std::mem::size_of::<usize>())],
        ) {
            return 2;
        }
        let mut at = p;
        let mut left = n;
        let mut count = 0;
        let stop = n == usize::MAX;
        loop {
            let (_, used, valid) = one(at, left, stop);
            // The legacy two-byte recovery counts BOTH bytes without reading
            // the second again; it may be uninitialized or inaccessible.
            if left == 2 && used == 1 && !valid {
                out.write(count + 2);
                return 0;
            }
            if used == 0 {
                out.write(count);
                return 0;
            }
            count += 1;
            at = at.add(used);
            left -= used;
        }
    })
}
#[no_mangle]
pub unsafe extern "C" fn star_unicode_decode(
    p: *const u8,
    n: usize,
    out: *mut u32,
    used: *mut usize,
) -> i32 {
    run(2, || {
        if !meta(
            p as usize,
            n,
            &[
                (out as usize, 4),
                (used as usize, std::mem::size_of::<usize>()),
            ],
        ) {
            return 2;
        }
        let (c, k, _) = one(p, n, n == usize::MAX);
        if k > 0 {
            out.write(c);
        }
        used.write(k);
        0
    })
}
#[no_mangle]
pub unsafe extern "C" fn star_unicode_encode(
    p: *mut u8,
    cap: usize,
    c: u32,
    written: *mut usize,
) -> i32 {
    run(3, || {
        let c = if c > 0x10ffff || surrogate(c) {
            0xfffd
        } else {
            c
        };
        let n = if c < 0x80 {
            1
        } else if c < 0x800 {
            2
        } else if c < 0x10000 {
            3
        } else {
            4
        };
        let actual = if cap < n { 0 } else { n };
        if !meta(
            p as usize,
            actual,
            &[(written as usize, std::mem::size_of::<usize>())],
        ) {
            return 2;
        }
        if actual > 0 {
            if n == 1 {
                p.write(c as u8);
            } else {
                let prefix = match n {
                    2 => 0xc0,
                    3 => 0xe0,
                    _ => 0xf0,
                };
                p.write((prefix | (c >> (6 * (n - 1)))) as u8);
                for i in 1..n {
                    p.add(i)
                        .write((0x80 | ((c >> (6 * (n - 1 - i))) & 63)) as u8);
                }
            }
        }
        written.write(actual);
        0
    })
}
fn from_pair(a: u32, b: u32) -> Result<u32, i32> {
    if !lead(a) {
        Err(4)
    } else if !trail(b) {
        Err(5)
    } else {
        Ok(((a - 0xd800) << 10) + (b - 0xdc00) + 0x10000)
    }
}
fn to_pair(c: u32) -> Result<(u32, u32, u32), i32> {
    if c < 0x10000 {
        return Ok((c, 0, 0));
    }
    let d = c - 0x10000;
    let a = (d >> 10) + 0xd800;
    if !lead(a) {
        Err(6)
    } else {
        Ok((a, (d & 1023) + 0xdc00, 1))
    }
}
unsafe fn scalar_out(out: *mut u32, f: impl FnOnce() -> Result<u32, i32>) -> i32 {
    if !meta(0, 0, &[(out as usize, 4)]) {
        return 2;
    }
    match f() {
        Ok(c) => {
            out.write(c);
            0
        }
        Err(s) => s,
    }
}
#[no_mangle]
pub unsafe extern "C" fn star_unicode_hex_to(
    c: u32,
    previous: u32,
    has_previous: u32,
    out: *mut u32,
) -> i32 {
    run(4, || {
        if has_previous > 1 {
            return 2;
        }
        scalar_out(out, || {
            if has_previous == 1 && lead(previous) {
                from_pair(previous, c)
            } else {
                Ok(c)
            }
        })
    })
}
unsafe fn pair_out(c: u32, a: *mut u32, b: *mut u32, has: *mut u32, max: bool) -> i32 {
    if !meta(0, 0, &[(a as usize, 4), (b as usize, 4), (has as usize, 4)]) {
        return 2;
    }
    if max && c > 0x10ffff {
        return 6;
    }
    match to_pair(c) {
        Ok((x, y, z)) => {
            a.write(x);
            b.write(y);
            has.write(z);
            0
        }
        Err(s) => s,
    }
}
#[no_mangle]
pub unsafe extern "C" fn star_unicode_hex_from(
    c: u32,
    a: *mut u32,
    b: *mut u32,
    has: *mut u32,
) -> i32 {
    run(5, || pair_out(c, a, b, has, true))
}
#[no_mangle]
pub unsafe extern "C" fn star_unicode_is_lead(c: u32, out: *mut u32) -> i32 {
    run(6, || scalar_out(out, || Ok(lead(c) as u32)))
}
#[no_mangle]
pub unsafe extern "C" fn star_unicode_is_trail(c: u32, out: *mut u32) -> i32 {
    run(7, || scalar_out(out, || Ok(trail(c) as u32)))
}
#[no_mangle]
pub unsafe extern "C" fn star_unicode_pair_from(a: u32, b: u32, out: *mut u32) -> i32 {
    run(8, || scalar_out(out, || from_pair(a, b)))
}
#[no_mangle]
pub unsafe extern "C" fn star_unicode_pair_to(
    c: u32,
    a: *mut u32,
    b: *mut u32,
    has: *mut u32,
) -> i32 {
    run(9, || pair_out(c, a, b, has, false))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ptr::{null, null_mut};

    #[test]
    fn utf8_independent_anchors_and_capacity() {
        unsafe {
            for (bytes, cp) in [
                (&b"A"[..], 0x41),
                (&b"\xc3\xa9"[..], 0xe9),
                (&b"\xe2\x82\xac"[..], 0x20ac),
                (&b"\xf0\x9f\x98\x80"[..], 0x1f600),
                (&b"\xf4\x8f\xbf\xbf"[..], 0x10ffff),
            ] {
                let mut out = 0;
                let mut used = 99;
                assert_eq!(
                    star_unicode_decode(bytes.as_ptr(), bytes.len(), &mut out, &mut used),
                    0
                );
                assert_eq!((out, used), (cp, bytes.len()));
                for cap in 0..=5 {
                    let mut buf = [0x55; 8];
                    let mut written = 99;
                    assert_eq!(
                        star_unicode_encode(buf.as_mut_ptr(), cap, cp, &mut written),
                        0
                    );
                    if cap < bytes.len() {
                        assert_eq!(written, 0);
                        assert_eq!(buf, [0x55; 8]);
                    } else {
                        assert_eq!(written, bytes.len());
                        assert_eq!(&buf[..written], bytes);
                    }
                }
                for n in 1..bytes.len() {
                    assert_eq!(
                        star_unicode_decode(bytes.as_ptr(), n, &mut out, &mut used),
                        0
                    );
                    assert_eq!((out, used), (0xfffd, 1));
                }
            }
            for bytes in [
                &b"\xc0\x80"[..],
                &b"\xed\xa0\x80"[..],
                &b"\xf4\x90\x80\x80"[..],
                &b"\xff"[..],
            ] {
                let mut valid = 9;
                let mut count = 9;
                let mut cp = 0;
                let mut used = 0;
                assert_eq!(
                    star_unicode_validate(bytes.as_ptr(), bytes.len(), &mut valid),
                    0
                );
                assert_eq!(valid, 0);
                assert_eq!(
                    star_unicode_length(bytes.as_ptr(), bytes.len(), &mut count),
                    0
                );
                assert_eq!(count, bytes.len());
                assert_eq!(
                    star_unicode_decode(bytes.as_ptr(), bytes.len(), &mut cp, &mut used),
                    0
                );
                assert_eq!((cp, used), (0xfffd, 1));
            }
            let mut cp = 123;
            let mut used = 99;
            let mut count = 99;
            let mut valid = 9;
            assert_eq!(star_unicode_decode(null(), 0, &mut cp, &mut used), 0);
            assert_eq!((cp, used), (123, 0));
            assert_eq!(
                star_unicode_decode(b"\0".as_ptr(), usize::MAX, &mut cp, &mut used),
                0
            );
            assert_eq!((cp, used), (123, 0));
            let bytes = b"A\0Z";
            assert_eq!(
                star_unicode_length(bytes.as_ptr(), usize::MAX, &mut count),
                0
            );
            assert_eq!(count, 1);
            assert_eq!(star_unicode_length(bytes.as_ptr(), 3, &mut count), 0);
            assert_eq!(count, 3);
            assert_eq!(star_unicode_validate(null(), 0, &mut valid), 0);
            assert_eq!(valid, 1);
            let mut buf = [0; 4];
            assert_eq!(
                star_unicode_encode(buf.as_mut_ptr(), usize::MAX, 0x110000, &mut used),
                0
            );
            assert_eq!((&buf[..used], used), (&b"\xef\xbf\xbd"[..], 3));
            assert_eq!(star_unicode_encode(null_mut(), 0, 0x41, &mut used), 0);
            assert_eq!(used, 0);
        }
    }
    #[test]
    fn utf16_boundaries_errors_and_receipts() {
        unsafe {
            for cp in [
                0,
                0xd7ff,
                0xd800,
                0xdbff,
                0xdc00,
                0xdfff,
                0xffff,
                0x10000,
                0x1f600,
                0x10ffff,
                0x110000,
                u32::MAX,
            ] {
                let (mut a, mut b, mut has) = (77, 88, 99);
                let before = star_unicode_call_count(9);
                let s = star_unicode_pair_to(cp, &mut a, &mut b, &mut has);
                assert_eq!(star_unicode_call_count(9), before + 1);
                if cp > 0x10ffff {
                    assert_eq!(s, 6);
                    assert_eq!((a, b, has), (77, 88, 99));
                } else if cp < 0x10000 {
                    assert_eq!((s, a, b, has), (0, cp, 0, 0));
                } else {
                    let mut result = 0;
                    assert_eq!(s, 0);
                    assert_eq!(has, 1);
                    assert_eq!(star_unicode_pair_from(a, b, &mut result), 0);
                    assert_eq!(result, cp);
                }
            }
            let mut out = 77;
            assert_eq!(star_unicode_pair_from(0, 0, &mut out), 4);
            assert_eq!(out, 77);
            assert_eq!(star_unicode_pair_from(0xd800, 0, &mut out), 5);
            assert_eq!(out, 77);
            assert_eq!(star_unicode_hex_to(0xde00, 0xd83d, 1, &mut out), 0);
            assert_eq!(out, 0x1f600);
            assert_eq!(star_unicode_hex_to(0xffffffff, 0, 0, &mut out), 0);
            assert_eq!(out, u32::MAX);
            let before = star_unicode_call_count(4);
            assert_eq!(star_unicode_hex_to(0, 0, 2, &mut out), 2);
            assert_eq!(out, u32::MAX);
            assert_eq!(star_unicode_call_count(4), before);
            assert_eq!(
                star_unicode_hex_from(0x110000, &mut out, null_mut(), null_mut()),
                2
            );
            for (a, b, c) in [(0xd800, 0xdc00, 0x10000), (0xdbff, 0xdfff, 0x10ffff)] {
                assert_eq!(star_unicode_pair_from(a, b, &mut out), 0);
                assert_eq!(out, c);
            }
        }
    }
    #[test]
    fn exhaustive_scalars_match_independent_standard_encoder() {
        unsafe {
            for cp in 0..=0x10ffff {
                let expected = char::from_u32(cp).unwrap_or('\u{fffd}');
                let mut reference = [0; 4];
                let bytes = expected.encode_utf8(&mut reference).as_bytes();
                let mut actual = [0; 4];
                let mut used = 99;
                assert_eq!(
                    star_unicode_encode(actual.as_mut_ptr(), 4, cp, &mut used),
                    0
                );
                assert_eq!(&actual[..used], bytes);
                let mut decoded = 0;
                let mut consumed = 0;
                assert_eq!(
                    star_unicode_decode(actual.as_ptr(), used, &mut decoded, &mut consumed),
                    0
                );
                assert_eq!((decoded, consumed), (expected as u32, used));
                let mut valid = 0;
                let mut length = 0;
                assert_eq!(star_unicode_validate(actual.as_ptr(), used, &mut valid), 0);
                assert_eq!(star_unicode_length(actual.as_ptr(), used, &mut length), 0);
                assert_eq!((valid, length), (1, 1));
            }
        }
    }

    #[test]
    fn invalid_metadata_aliases_and_thread_isolation() {
        unsafe {
            let mut out = 9u32;
            let before = star_unicode_call_count(0);
            assert_eq!(star_unicode_validate(null(), 1, &mut out), 2);
            assert_eq!(star_unicode_validate(b"A".as_ptr(), 1, null_mut()), 2);
            assert_eq!(
                star_unicode_validate((&out as *const u32).cast(), 4, &mut out),
                2
            );
            assert_eq!(
                star_unicode_validate(b"A".as_ptr(), isize::MAX as usize + 1, &mut out),
                2
            );
            assert_eq!(star_unicode_call_count(0), before);
            assert_eq!(out, 9);
            assert_eq!(star_unicode_call_count(10), 0);
            let t = std::thread::spawn(|| {
                let mut out = 0;
                assert_eq!(star_unicode_call_count(6), 0);
                assert_eq!(star_unicode_is_lead(0xd800, &mut out), 0);
                assert_eq!(out, 1);
                assert_eq!(star_unicode_call_count(6), 1);
            });
            t.join().unwrap();
            assert_eq!(star_unicode_call_count(6), 0);
            assert_eq!(run(0, || panic!("contained")), 3);
            assert_eq!(star_unicode_call_count(0), before);
        }
    }
}
