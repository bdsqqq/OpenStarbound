use std::cell::Cell;
use std::mem::align_of;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::ptr;

const OK: u32 = 0;
const INVALID: u32 = 1;
const BAD_LENGTH: u32 = 2;
const PANIC: u32 = 3;

thread_local! {
    static COUNTS: Cell<[u64; 3]> = const { Cell::new([0; 3]) };
}

fn counted(operation: usize) {
    COUNTS.with(|cell| {
        let mut counts = cell.get();
        counts[operation] = counts[operation].wrapping_add(1);
        cell.set(counts);
    });
}

fn valid_output<T>(output: *mut T) -> bool {
    !output.is_null() && (output as usize) % align_of::<T>() == 0
}

/// Copies exactly sixteen bytes, including overlapping buffers.
///
/// # Safety
/// For length 16, non-null pointers must designate live readable/writable
/// sixteen-byte regions for this call. No pointer is retained.
#[no_mangle]
pub unsafe extern "C" fn sb_uuid_from_bytes(data: *const u8, len: usize, out16: *mut u8) -> u32 {
    // Length rejection must not inspect either pointer, even for null pointers.
    if len != 16 {
        return BAD_LENGTH;
    }
    catch_unwind(AssertUnwindSafe(|| {
        if data.is_null() || out16.is_null() {
            return INVALID;
        }
        ptr::copy(data, out16, 16);
        counted(0);
        OK
    }))
    .unwrap_or(PANIC)
}

/// Compares the native C++ char values, not necessarily unsigned bytes.
///
/// # Safety
/// Inputs must designate sixteen readable bytes. A non-null, aligned output
/// must designate a writable i32. Regions may overlap; inputs are snapshotted
/// before output is written. All storage must remain live for this call.
#[no_mangle]
pub unsafe extern "C" fn sb_uuid_compare(
    left16: *const u8,
    right16: *const u8,
    signed_chars: u32,
    out_order: *mut i32,
) -> u32 {
    catch_unwind(AssertUnwindSafe(|| {
        if signed_chars > 1 || left16.is_null() || right16.is_null() || !valid_output(out_order) {
            return INVALID;
        }
        let left = left16.cast::<[u8; 16]>().read();
        let right = right16.cast::<[u8; 16]>().read();
        let mut order = 0;
        for i in 0..16 {
            let a = if signed_chars == 1 { left[i] as i8 as i32 } else { left[i] as i32 };
            let b = if signed_chars == 1 { right[i] as i8 as i32 } else { right[i] as i32 };
            if a != b {
                order = if a < b { -1 } else { 1 };
                break;
            }
        }
        out_order.write(order);
        counted(1);
        OK
    }))
    .unwrap_or(PANIC)
}

/// Reproduces Star::hashCombine with native size_t width and char conversion.
///
/// # Safety
/// Input must designate sixteen readable bytes and the aligned output a writable
/// usize, live throughout this call. Input/output may overlap; no pointer escapes.
#[no_mangle]
pub unsafe extern "C" fn sb_uuid_hash(
    data16: *const u8,
    signed_chars: u32,
    out_hash: *mut usize,
) -> u32 {
    catch_unwind(AssertUnwindSafe(|| {
        if signed_chars > 1 || data16.is_null() || !valid_output(out_hash) {
            return INVALID;
        }
        let data = data16.cast::<[u8; 16]>().read();
        let mut seed = 0usize;
        for byte in data {
            // C++ converts char straight to size_t (no std::hash<char> step).
            let comb = if signed_chars == 1 { byte as i8 as isize as usize } else { byte as usize };
            seed ^= comb.wrapping_mul(2654435761)
                .wrapping_add(0x9e3779b9)
                .wrapping_add(seed << 6)
                .wrapping_add(seed >> 2);
        }
        out_hash.write(seed);
        counted(2);
        OK
    }))
    .unwrap_or(PANIC)
}

/// Successful operations on this thread only; unknown operations return zero.
#[no_mangle]
pub extern "C" fn sb_uuid_count(operation: u32) -> u64 {
    catch_unwind(|| COUNTS.with(|c| c.get().get(operation as usize).copied().unwrap_or(0)))
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ptr::{null, null_mut};

    #[test]
    fn fixed_copy_and_all_overlaps() {
        for src in 0..=16 {
            for dst in 0..=16 {
                let mut bytes = std::array::from_fn::<_, 32, _>(|i| i as u8);
                let mut expected = bytes;
                expected[dst..dst + 16].copy_from_slice(&bytes[src..src + 16]);
                let before = sb_uuid_count(0);
                let p = bytes.as_mut_ptr();
                assert_eq!(unsafe { sb_uuid_from_bytes(p.add(src), 16, p.add(dst)) }, OK);
                assert_eq!(bytes, expected);
                assert_eq!(sb_uuid_count(0), before.wrapping_add(1));
            }
        }
    }

    #[test]
    fn char_order_and_six_relations() {
        for signed in 0..=1 {
            for (a, b, expected) in [(0x80, 0x7f, if signed == 1 { -1 } else { 1 }),
                (0x7f, 0x80, if signed == 1 { 1 } else { -1 }), (0xff, 0xff, 0)] {
                let mut left = [0; 16];
                let mut right = left;
                left[15] = a;
                right[15] = b;
                let mut order = 99;
                let before = sb_uuid_count(1);
                assert_eq!(unsafe { sb_uuid_compare(left.as_ptr(), right.as_ptr(), signed, &mut order) }, OK);
                assert_eq!(order, expected);
                assert_eq!([order == 0, order != 0, order < 0, order <= 0, order > 0, order >= 0],
                    [expected == 0, expected != 0, expected < 0, expected <= 0, expected > 0, expected >= 0]);
                assert_eq!(sb_uuid_count(1), before.wrapping_add(1));
            }
        }
        // The first difference, not a later contrary difference, decides order.
        let mut a = [255; 16];
        let mut b = [0; 16];
        a[0] = 0;
        b[0] = 1;
        let mut order = 99;
        assert_eq!(unsafe { sb_uuid_compare(a.as_ptr(), b.as_ptr(), 0, &mut order) }, OK);
        assert_eq!(order, -1);
    }

    // Independently evaluated integer recurrence, reduced modulo the native word
    // after every step; constants below are not obtained from the kernel.
    fn reference(data: [u8; 16], signed: u32) -> usize {
        let modulus = 1i128 << usize::BITS;
        let mut h = 0i128;
        for b in data {
            let c = if signed == 1 && b >= 128 { b as i128 - 256 } else { b as i128 };
            let sum = (c * 2_654_435_761 + 2_654_435_769 + h * 64 + h / 4).rem_euclid(modulus);
            h ^= sum;
        }
        h as usize
    }

    #[test]
    fn hash_goldens_and_scalar_corpus() {
        let corpus = [[0; 16], [255; 16], std::array::from_fn(|i| i as u8), std::array::from_fn(|i| 120 + i as u8)];
        let golden32: [[u64; 2]; 4] = [[0xd48509af; 2], [0x9301a0f0, 0xdd077742], [0x5452917b; 2], [0x3e49e58b, 0xfecbdc0a]];
        let golden64: [[u64; 2]; 4] = [[0xf3b95195c79f012f; 2], [0x097e2d8e2e0421a8, 0xf82b3a8ef6ad9742], [0xc0470273f055a63b; 2], [0x57724b5898615ba3, 0xc4d3c089698e6252]];
        let goldens = if usize::BITS == 64 { golden64 } else { golden32 };
        for (i, data) in corpus.into_iter().enumerate() {
            for signed in 0..=1 {
                let mut actual = 0;
                let before = sb_uuid_count(2);
                assert_eq!(unsafe { sb_uuid_hash(data.as_ptr(), signed, &mut actual) }, OK);
                assert_eq!(actual as u64, goldens[i][signed as usize]);
                assert_eq!(actual, reference(data, signed));
                assert_eq!(sb_uuid_count(2), before.wrapping_add(1));
            }
        }
        for byte in 0..=255u8 {
            for signed in 0..=1 {
                let data = std::array::from_fn(|i| byte.wrapping_add((i * 17) as u8));
                let mut actual = 0;
                assert_eq!(unsafe { sb_uuid_hash(data.as_ptr(), signed, &mut actual) }, OK);
                assert_eq!(actual, reference(data, signed));
            }
        }
    }

    #[test]
    fn invalid_calls_do_not_write_or_count() {
        let counts = [sb_uuid_count(0), sb_uuid_count(1), sb_uuid_count(2)];
        let data = [0; 16];
        let mut output = [0xa5; 32];
        for len in [0, 1, 15, 17, usize::MAX] {
            assert_eq!(unsafe { sb_uuid_from_bytes(null(), len, null_mut()) }, BAD_LENGTH);
            assert_eq!(unsafe { sb_uuid_from_bytes(null(), len, output.as_mut_ptr()) }, BAD_LENGTH);
        }
        assert_eq!(unsafe { sb_uuid_from_bytes(null(), 16, output.as_mut_ptr()) }, INVALID);
        assert_eq!(unsafe { sb_uuid_from_bytes(data.as_ptr(), 16, null_mut()) }, INVALID);
        let mut order = 37;
        let mut hash = 47usize;
        for flag in [2, u32::MAX] {
            assert_eq!(unsafe { sb_uuid_compare(data.as_ptr(), data.as_ptr(), flag, &mut order) }, INVALID);
            assert_eq!(unsafe { sb_uuid_hash(data.as_ptr(), flag, &mut hash) }, INVALID);
        }
        assert_eq!(unsafe { sb_uuid_compare(null(), data.as_ptr(), 0, &mut order) }, INVALID);
        assert_eq!(unsafe { sb_uuid_compare(data.as_ptr(), null(), 0, &mut order) }, INVALID);
        assert_eq!(unsafe { sb_uuid_compare(data.as_ptr(), data.as_ptr(), 0, null_mut()) }, INVALID);
        assert_eq!(unsafe { sb_uuid_hash(null(), 0, &mut hash) }, INVALID);
        assert_eq!(unsafe { sb_uuid_hash(data.as_ptr(), 0, null_mut()) }, INVALID);
        // Choose genuinely misaligned addresses independently of stack alignment.
        let p = output.as_mut_ptr();
        let mis_i32 = unsafe { p.add(if p as usize % align_of::<i32>() == 0 { 1 } else { 0 }) }.cast::<i32>();
        let mis_usize = unsafe { p.add(if p as usize % align_of::<usize>() == 0 { 1 } else { 0 }) }.cast::<usize>();
        assert_eq!(unsafe { sb_uuid_compare(data.as_ptr(), data.as_ptr(), 0, mis_i32) }, INVALID);
        assert_eq!(unsafe { sb_uuid_hash(data.as_ptr(), 0, mis_usize) }, INVALID);
        assert_eq!(order, 37);
        assert_eq!(hash, 47);
        assert_eq!(output, [0xa5; 32]);
        assert_eq!([sb_uuid_count(0), sb_uuid_count(1), sb_uuid_count(2)], counts);
        assert_eq!(sb_uuid_count(3), 0);
        assert_eq!(sb_uuid_count(u32::MAX), 0);
    }
}
