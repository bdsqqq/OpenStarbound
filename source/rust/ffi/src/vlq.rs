//! Legacy most-significant-group-first VLQ, including lazy partial read effects.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

pub type StarVlqWrite = Option<unsafe extern "C" fn(*mut c_void, u8, u32) -> i32>;
pub type StarVlqRead = Option<unsafe extern "C" fn(*mut c_void, *mut u8) -> i32>;
thread_local! { static COUNTS: Cell<[u64; 6]> = const { Cell::new([0; 6]) }; }

#[no_mangle]
pub extern "C" fn star_vlq_call_count(operation: u32) -> u64 {
    COUNTS.with(|c| c.get().get(operation as usize).copied().unwrap_or(0))
}
fn controlled(operation: usize, f: impl FnOnce() -> i32) -> i32 {
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(status) => {
            if matches!(status, 0 | 1 | 4) {
                COUNTS.with(|c| {
                    let mut counts = c.get();
                    counts[operation] = counts[operation].wrapping_add(1);
                    c.set(counts);
                });
            }
            status
        }
        Err(_) => 3,
    }
}
fn valid<T>(p: *mut T) -> bool {
    !p.is_null()
        && (p as usize) % std::mem::align_of::<T>() == 0
        && (p as usize).checked_add(std::mem::size_of::<T>()).is_some()
}
fn read_shape<T>(value: *mut T, count: *mut u32) -> bool {
    valid(value) && valid(count) && {
        let v = value as usize;
        let c = count as usize;
        v + std::mem::size_of::<T>() <= c || c + 4 <= v
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use std::ptr::null_mut;
    struct Io {
        bytes: Vec<u8>,
        index: usize,
        abort: usize,
    }
    unsafe extern "C" fn put(ctx: *mut c_void, b: u8, final_byte: u32) -> i32 {
        let io = &mut *ctx.cast::<Io>();
        assert_eq!(final_byte, u32::from(b & 128 == 0));
        if io.bytes.len() == io.abort {
            return 7;
        }
        io.bytes.push(b);
        0
    }
    unsafe extern "C" fn get(ctx: *mut c_void, b: *mut u8) -> i32 {
        let io = &mut *ctx.cast::<Io>();
        if io.index == io.abort || io.index == io.bytes.len() {
            return -1;
        }
        b.write(io.bytes[io.index]);
        io.index += 1;
        0
    }
    #[test]
    fn anchors_and_signed_extremes() {
        unsafe {
            let anchors: &[(u64, &[u8])] = &[
                (0, &[0]),
                (127, &[127]),
                (128, &[129, 0]),
                (16383, &[255, 127]),
                (16384, &[129, 128, 0]),
            ];
            for &(value, bytes) in anchors {
                let mut io = Io {
                    bytes: vec![],
                    index: 0,
                    abort: usize::MAX,
                };
                let mut n = 99;
                let ctx = (&mut io as *mut Io).cast();
                assert_eq!(star_vlq_write_u(value, Some(put), ctx, &mut n), 0);
                assert_eq!(io.bytes, bytes);
                assert_eq!(n as usize, bytes.len());
                assert_eq!(star_vlq_size_u(value, &mut n), 0);
                assert_eq!(n as usize, bytes.len());
                let mut out = 99;
                assert_eq!(star_vlq_read_u(&mut out, Some(get), ctx, 10, &mut n), 0);
                assert_eq!(out, value);
            }
            for (value, bytes) in [
                (-1, vec![1]),
                (-64, vec![127]),
                (-65, vec![129, 1]),
                (64, vec![129, 0]),
                (
                    i64::MIN,
                    vec![129, 255, 255, 255, 255, 255, 255, 255, 255, 127],
                ),
                (
                    i64::MAX,
                    vec![129, 255, 255, 255, 255, 255, 255, 255, 255, 126],
                ),
            ] {
                let mut io = Io {
                    bytes: vec![],
                    index: 0,
                    abort: usize::MAX,
                };
                let ctx = (&mut io as *mut Io).cast();
                let mut n = 99;
                assert_eq!(star_vlq_write_i(value, Some(put), ctx, &mut n), 0);
                assert_eq!(io.bytes, bytes);
                assert_eq!(star_vlq_size_i(value, &mut n), 0);
                assert_eq!(n as usize, bytes.len());
                let mut out = 42;
                assert_eq!(star_vlq_read_i(&mut out, Some(get), ctx, 10, &mut n), 0);
                assert_eq!(out, value);
            }
        }
    }
    #[test]
    fn limits_abort_invalid_and_receipts() {
        unsafe {
            let before = std::array::from_fn::<_, 6, _>(|op| star_vlq_call_count(op as u32));
            let mut io = Io {
                bytes: vec![128; 11],
                index: 0,
                abort: usize::MAX,
            };
            let ctx = (&mut io as *mut Io).cast();
            let mut n = 99;
            let mut u = 99;
            let mut i = 99;
            assert_eq!(star_vlq_read_u(&mut u, Some(get), ctx, 100, &mut n), 4);
            assert_eq!((u, n, io.index), (0, 10, 10));
            assert_eq!(star_vlq_read_i(&mut i, Some(get), ctx, 0, &mut n), 4);
            assert_eq!((i, n), (99, 0));
            assert_eq!(star_vlq_read_u(&mut u, Some(get), ctx, 0, &mut n), 4);
            assert_eq!((u, n), (0, 0));
            io.bytes = vec![129, 2];
            io.index = 0;
            io.abort = 1;
            assert_eq!(star_vlq_read_u(&mut u, Some(get), ctx, 10, &mut n), 1);
            assert_eq!((u, n), (1, 1));
            io.index = 0;
            assert_eq!(star_vlq_read_i(&mut i, Some(get), ctx, 10, &mut n), 1);
            assert_eq!((i, n), (99, 1));
            io.bytes.clear();
            assert_eq!(star_vlq_write_u(16384, Some(put), ctx, &mut n), 1);
            assert_eq!(n, 1);
            n = 88;
            u = 77;
            assert_eq!(star_vlq_read_u(&mut u, None, ctx, 10, &mut n), 2);
            assert_eq!((u, n), (77, 88));
            assert_eq!(
                star_vlq_read_u(&mut u, Some(get), ctx, 10, (&mut u as *mut u64).cast()),
                2
            );
            assert_eq!(u, 77);
            assert_eq!(star_vlq_size_u(0, null_mut()), 2);
            let mut raw = [0u8; 16];
            assert_eq!(star_vlq_size_u(0, raw.as_mut_ptr().add(1).cast()), 2);
            assert_eq!(raw, [0; 16]);
            assert_eq!(star_vlq_write_i(0, None, ctx, &mut n), 2);
            assert_eq!(n, 88);
            let after = std::array::from_fn::<_, 6, _>(|op| star_vlq_call_count(op as u32));
            assert_eq!(
                std::array::from_fn::<_, 6, _>(|op| after[op].wrapping_sub(before[op])),
                [1, 0, 3, 0, 0, 2]
            );
            std::thread::spawn(|| assert_eq!(star_vlq_call_count(2), 0))
                .join()
                .unwrap();
            assert_eq!(star_vlq_call_count(6), 0);
        }
    }
    #[test]
    fn wrapping_and_panic_receipts() {
        COUNTS.with(|c| c.set([u64::MAX; 6]));
        assert_eq!(controlled(0, || panic!("contained")), 3);
        assert_eq!(star_vlq_call_count(0), u64::MAX);
        assert_eq!(controlled(0, || 2), 2);
        assert_eq!(star_vlq_call_count(0), u64::MAX);
        for (operation, status) in [(0, 0), (1, 1), (2, 4)] {
            assert_eq!(controlled(operation, || status), status);
            assert_eq!(star_vlq_call_count(operation as u32), 0);
        }
    }
    #[test]
    fn permissive_and_mutating_callbacks() {
        unsafe {
            let mut n = 0;
            let mut out = 9;
            for bytes in [
                vec![128, 0],
                vec![130, 128, 128, 128, 128, 128, 128, 128, 128, 0],
            ] {
                let mut io = Io {
                    bytes,
                    index: 0,
                    abort: usize::MAX,
                };
                let ctx = (&mut io as *mut Io).cast();
                assert_eq!(star_vlq_read_u(&mut out, Some(get), ctx, 10, &mut n), 0);
                assert_eq!(out, 0);
            }
            unsafe extern "C" fn mutate(ctx: *mut c_void, b: *mut u8) -> i32 {
                let value = ctx.cast::<u64>();
                assert_eq!(value.read(), 0);
                value.write(7);
                b.write(2);
                0
            }
            let p = &mut out as *mut u64;
            assert_eq!(star_vlq_read_u(p, Some(mutate), p.cast(), 10, &mut n), 0);
            assert_eq!(out, 898);
            unsafe extern "C" fn fail(ctx: *mut c_void, _: *mut u8) -> i32 {
                ctx.cast::<u64>().write(123);
                1
            }
            assert_eq!(star_vlq_read_u(p, Some(fail), p.cast(), 10, &mut n), 1);
            assert_eq!((out, n), (123, 0));
            assert_eq!(controlled(0, || panic!("contained test")), 3);
        }
    }
}

fn zigzag(value: i64) -> u64 {
    ((value as u64) << 1) ^ (0u64.wrapping_sub((value < 0) as u64))
}
fn size(value: u64) -> u32 {
    ((64 - value.leading_zeros()).max(1) + 6) / 7
}
unsafe fn write_impl(value: u64, write: StarVlqWrite, ctx: *mut c_void, written: *mut u32) -> i32 {
    let Some(write) = write else { return 2 };
    if !valid(written) {
        return 2;
    }
    let length = size(value);
    let mut count = 0;
    for group in (0..length).rev() {
        let final_byte = group == 0;
        let octet = ((value >> (group * 7)) & 127) as u8 | if final_byte { 0 } else { 128 };
        if write(ctx, octet, final_byte as u32) != 0 {
            written.write(count);
            return 1;
        }
        count += 1;
    }
    written.write(count);
    0
}
// Raw loads are deliberate: callbacks may mutate/reenter the destination. No
// Rust reference or cached accumulator may live across a foreign callback.
unsafe fn read_impl(
    value: *mut u64,
    read: unsafe extern "C" fn(*mut c_void, *mut u8) -> i32,
    ctx: *mut c_void,
    max_bytes: usize,
    consumed: *mut u32,
) -> i32 {
    value.write(0);
    let mut count = 0;
    for _ in 0..max_bytes.min(10) {
        let mut octet = 0;
        if read(ctx, &mut octet) != 0 {
            consumed.write(count);
            return 1;
        }
        value.write(value.read().wrapping_shl(7) | u64::from(octet & 127));
        count += 1;
        if octet & 128 == 0 {
            consumed.write(count);
            return 0;
        }
    }
    consumed.write(count);
    4
}

/// # Safety
/// Pointers/callbacks obey StarRustVlq.h's borrowed allocation contract.
#[no_mangle]
pub unsafe extern "C" fn star_vlq_write_u(
    value: u64,
    write: StarVlqWrite,
    ctx: *mut c_void,
    written: *mut u32,
) -> i32 {
    controlled(0, || write_impl(value, write, ctx, written))
}
/// # Safety
/// Same contract as star_vlq_write_u.
#[no_mangle]
pub unsafe extern "C" fn star_vlq_write_i(
    value: i64,
    write: StarVlqWrite,
    ctx: *mut c_void,
    written: *mut u32,
) -> i32 {
    controlled(3, || write_impl(zigzag(value), write, ctx, written))
}
/// # Safety
/// size points to a live aligned writable u32.
#[no_mangle]
pub unsafe extern "C" fn star_vlq_size_u(value: u64, out: *mut u32) -> i32 {
    controlled(1, || {
        if !valid(out) {
            return 2;
        }
        out.write(size(value));
        0
    })
}
/// # Safety
/// Same contract as star_vlq_size_u.
#[no_mangle]
pub unsafe extern "C" fn star_vlq_size_i(value: i64, out: *mut u32) -> i32 {
    controlled(4, || {
        if !valid(out) {
            return 2;
        }
        out.write(size(zigzag(value)));
        0
    })
}
/// # Safety
/// Pointers/callbacks obey StarRustVlq.h; callbacks may access value but not
/// invalidate its allocation. count and value must be disjoint.
#[no_mangle]
pub unsafe extern "C" fn star_vlq_read_u(
    value: *mut u64,
    read: StarVlqRead,
    ctx: *mut c_void,
    max_bytes: usize,
    consumed: *mut u32,
) -> i32 {
    controlled(2, || {
        let Some(read) = read else { return 2 };
        if !read_shape(value, consumed) {
            return 2;
        }
        read_impl(value, read, ctx, max_bytes, consumed)
    })
}
/// # Safety
/// Same contract as star_vlq_read_u, with an i64 destination.
#[no_mangle]
pub unsafe extern "C" fn star_vlq_read_i(
    value: *mut i64,
    read: StarVlqRead,
    ctx: *mut c_void,
    max_bytes: usize,
    consumed: *mut u32,
) -> i32 {
    controlled(5, || {
        let Some(read) = read else { return 2 };
        if !read_shape(value, consumed) {
            return 2;
        }
        let mut source = 0u64;
        let status = read_impl(&mut source, read, ctx, max_bytes, consumed);
        if status == 0 {
            value.write(((source >> 1) as i64) ^ -((source & 1) as i64));
        }
        status
    })
}
