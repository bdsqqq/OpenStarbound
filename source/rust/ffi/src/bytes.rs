use std::cell::Cell;
use std::ffi::c_void;
use std::mem::MaybeUninit;
use std::panic::{catch_unwind, AssertUnwindSafe};

thread_local! {
    static CALLS: Cell<[u64; 6]> = const { Cell::new([0; 6]) };
}

#[no_mangle]
pub extern "C" fn star_bytes_call_count(operation: u32) -> u64 {
    CALLS.with(|c| c.get().get(operation as usize).copied().unwrap_or(0))
}

fn range(p: usize, len: usize) -> Option<(usize, usize)> {
    if p == 0 || len > isize::MAX as usize {
        return None;
    }
    Some((p, p.checked_add(len)?))
}

/// Transforms object representations without interpreting potentially uninitialized padding.
///
/// # Safety
/// All accessed bytes must belong to live readable/writable caller allocations.
/// Reversing copies may alias and follow sequential C++ assignment order; ordinary
/// copies must be disjoint. No references or pointers survive this call. Status 3
/// may follow partial writes and must not trigger fallback/retry.
#[no_mangle]
pub unsafe extern "C" fn star_bytes_transform(
    dest: *mut c_void,
    src: *const c_void,
    len: usize,
    operation: u32,
    order: u32,
    platform_order: u32,
) -> i32 {
    catch_unwind(AssertUnwindSafe(|| {
        if operation > 5 || platform_order > 1 || len > isize::MAX as usize {
            return 2;
        }
        let reverse = operation < 2 || (order != 2 && order != platform_order);
        let copy = operation % 2 == 1;
        // Preserve pointer-free in-place no-ops, including null with len 1.
        if len != 0 && (copy || (reverse && len > 1)) {
            let Some(dr) = range(dest as usize, len) else {
                return 2;
            };
            if copy {
                let Some(sr) = range(src as usize, len) else {
                    return 2;
                };
                if !reverse && dr.0 < sr.1 && sr.0 < dr.1 {
                    return 2;
                }
            }
            let d = dest.cast::<MaybeUninit<u8>>();
            if copy {
                let s = src.cast::<MaybeUninit<u8>>();
                if reverse {
                    // Do not snapshot or reverse the full buffer: overlapping source
                    // bytes can be changed by an earlier destination assignment.
                    for i in 0..len {
                        d.add(len - 1 - i).write(s.add(i).read());
                    }
                } else {
                    std::ptr::copy_nonoverlapping(s, d, len);
                }
            } else {
                for i in 0..len / 2 {
                    let spare = d.add(len - 1 - i).read();
                    d.add(len - 1 - i).write(d.add(i).read());
                    d.add(i).write(spare);
                }
            }
        }
        CALLS.with(|c| {
            let mut counts = c.get();
            counts[operation as usize] = counts[operation as usize].wrapping_add(1);
            c.set(counts);
        });
        0
    }))
    .unwrap_or(3)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ptr::{null, null_mut};

    #[test]
    fn all_orders_modes_and_platform_compile_facts() {
        for platform in 0..=1 {
            for order in [0, 1, 2, 3, u32::MAX] {
                for op in 0..6 {
                    let mut dest = [1u8, 2, 3, 4, 5];
                    let src = [6u8, 7, 8, 9, 10];
                    let before = star_bytes_call_count(op);
                    let reverse = op < 2 || (order != 2 && order != platform);
                    let mut expected = if op % 2 == 1 { src } else { dest };
                    if reverse {
                        expected.reverse();
                    }
                    assert_eq!(
                        unsafe {
                            star_bytes_transform(
                                dest.as_mut_ptr().cast(),
                                src.as_ptr().cast(),
                                5,
                                op,
                                order,
                                platform,
                            )
                        },
                        0
                    );
                    assert_eq!(dest, expected);
                    assert_eq!(star_bytes_call_count(op), before + 1);
                }
            }
        }
    }

    #[test]
    fn sequential_reverse_copy_all_overlaps() {
        for op in [1, 3, 5] {
            for len in 0..=16 {
                for source in 0..=16 {
                    for destination in 0..=16 {
                        let mut actual = std::array::from_fn::<_, 32, _>(|i| i as u8);
                        let mut expected = actual;
                        for i in 0..len {
                            expected[destination + len - 1 - i] = expected[source + i];
                        }
                        let p = actual.as_mut_ptr();
                        assert_eq!(
                            unsafe {
                                star_bytes_transform(
                                    p.add(destination).cast(),
                                    p.add(source).cast(),
                                    len,
                                    op,
                                    9,
                                    0,
                                )
                            },
                            0
                        );
                        assert_eq!(
                            actual, expected,
                            "op={op} len={len} src={source} dst={destination}"
                        );
                    }
                }
            }
        }
    }

    #[test]
    fn no_access_null_and_ignored_source() {
        for op in 0..6 {
            assert_eq!(
                unsafe { star_bytes_transform(null_mut(), null(), 0, op, 0, 1) },
                0
            );
        }
        for op in [0, 2, 4] {
            for len in 0..=1 {
                assert_eq!(
                    unsafe {
                        star_bytes_transform(null_mut(), usize::MAX as *const c_void, len, op, 9, 1)
                    },
                    0
                );
            }
        }
        for op in [2, 4] {
            for order in [1, 2] {
                assert_eq!(
                    unsafe { star_bytes_transform(null_mut(), null(), 1024, op, order, 1) },
                    0
                );
            }
        }
    }

    #[test]
    fn invalid_metadata_is_transactional() {
        let mut output = [42u8; 8];
        let input = [1u8; 8];
        let d = output.as_mut_ptr().cast();
        let s = input.as_ptr().cast();
        let cases = [
            (d, s, 8, 6, 0, 0),
            (d, s, 8, 1, 0, 2),
            (d, null(), 8, 1, 0, 0),
            (null_mut(), s, 8, 1, 0, 0),
            (d, usize::MAX as *const c_void, 8, 1, 0, 0),
            (usize::MAX as *mut c_void, s, 8, 1, 0, 0),
            (d, s, isize::MAX as usize + 1, 1, 0, 0),
            (d, d.cast_const(), 8, 3, 2, 0),
            (d, unsafe { d.cast::<u8>().add(1).cast() }, 7, 5, 0, 0),
        ];
        for (d, s, len, op, order, platform) in cases {
            let before = star_bytes_call_count(op);
            assert_eq!(
                unsafe { star_bytes_transform(d, s, len, op, order, platform) },
                2
            );
            assert_eq!(output, [42; 8]);
            assert_eq!(star_bytes_call_count(op), before);
        }
    }

    #[test]
    fn receipts_are_thread_local() {
        let before = star_bytes_call_count(0);
        std::thread::spawn(|| {
            assert_eq!(star_bytes_call_count(0), 0);
            assert_eq!(
                unsafe { star_bytes_transform(null_mut(), null(), 0, 0, 0, 0) },
                0
            );
            assert_eq!(star_bytes_call_count(0), 1);
        })
        .join()
        .unwrap();
        assert_eq!(star_bytes_call_count(0), before);
        assert_eq!(star_bytes_call_count(6), 0);
    }

    #[test]
    fn padding_remains_uninterpreted() {
        let mut source = [MaybeUninit::<u8>::uninit(); 8];
        source[0].write(123);
        let mut dest = [MaybeUninit::<u8>::uninit(); 8];
        assert_eq!(
            unsafe {
                star_bytes_transform(dest.as_mut_ptr().cast(), source.as_ptr().cast(), 8, 1, 0, 0)
            },
            0
        );
        assert_eq!(unsafe { dest[7].assume_init() }, 123);
        assert_eq!(
            unsafe {
                star_bytes_transform(dest.as_mut_ptr().cast(), source.as_ptr().cast(), 8, 3, 2, 0)
            },
            0
        );
        assert_eq!(unsafe { dest[0].assume_init() }, 123);
    }
}
