use std::cell::Cell;
use std::mem::{align_of, size_of};
use std::panic::{catch_unwind, AssertUnwindSafe};

const NPOS: usize = usize::MAX;

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct StarAssetPathSplit {
    pub base_len: usize,
    pub sub_start: usize,
    pub sub_count: usize,
    pub directive_start: usize,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct StarAssetPathRange {
    pub start: usize,
    pub end: usize,
}

thread_local! {
    static CALLS: Cell<[u64; 2]> = const { Cell::new([0; 2]) };
}

#[no_mangle]
pub extern "C" fn star_asset_path_call_count(op: u32) -> u64 {
    CALLS.with(|c| c.get().get(op as usize).copied().unwrap_or(0))
}

fn valid<T>(input: *const u8, len: usize, out: *mut T) -> bool {
    if len > isize::MAX as usize
        || (len != 0 && input.is_null())
        || out.is_null()
        || (out as usize) % align_of::<T>() != 0
    {
        return false;
    }
    let Some(input_end) = (input as usize).checked_add(len) else {
        return false;
    };
    let Some(out_end) = (out as usize).checked_add(size_of::<T>()) else {
        return false;
    };
    len == 0 || !((input as usize) < out_end && (out as usize) < input_end)
}

fn split(bytes: &[u8]) -> StarAssetPathSplit {
    let mut end = bytes
        .iter()
        .position(|b| matches!(b, b':' | b'?'))
        .unwrap_or(NPOS);
    let mut result = StarAssetPathSplit {
        base_len: end,
        sub_start: NPOS,
        sub_count: 0,
        directive_start: NPOS,
    };
    if end == NPOS {
        return result;
    }
    if bytes[end] == b':' {
        let beg = end + 1;
        if beg != bytes.len() {
            end = bytes[beg..]
                .iter()
                .position(|b| *b == b'?')
                .map(|i| beg + i)
                .unwrap_or(NPOS);
            // Preserve the C++ count, including the final one-byte wrapping case.
            let count = if end == NPOS && beg + 1 != bytes.len() {
                NPOS
            } else {
                end.wrapping_sub(beg)
            };
            if count != 0 {
                result.sub_start = beg;
                result.sub_count = count;
            }
        }
    }
    if end != NPOS && bytes[end] == b'?' {
        result.directive_start = end;
    }
    result
}

fn filename_range(bytes: &[u8]) -> StarAssetPathRange {
    let end = bytes
        .iter()
        .position(|b| matches!(b, b':' | b'?'))
        .unwrap_or(bytes.len());
    let start = bytes[..end]
        .iter()
        .rposition(|b| *b == b'/')
        .map(|i| i + 1)
        .unwrap_or(0);
    StarAssetPathRange { start, end }
}

unsafe fn run<T>(
    input: *const u8,
    len: usize,
    out: *mut T,
    op: usize,
    kernel: fn(&[u8]) -> T,
) -> i32 {
    catch_unwind(AssertUnwindSafe(|| {
        if !valid(input, len, out) {
            return 2;
        }
        let bytes = if len == 0 {
            &[]
        } else {
            std::slice::from_raw_parts(input, len)
        };
        let result = kernel(bytes);
        out.write(result);
        CALLS.with(|c| {
            let mut counts = c.get();
            counts[op] = counts[op].wrapping_add(1);
            c.set(counts);
        });
        0
    }))
    .unwrap_or(3)
}

/// # Safety
/// Input must be initialized and readable for len bytes, immutable for the call.
/// Output must be a live writable object disjoint from all input bytes.
#[no_mangle]
pub unsafe extern "C" fn star_asset_path_split(
    input: *const u8,
    len: usize,
    out: *mut StarAssetPathSplit,
) -> i32 {
    run(input, len, out, 0, split)
}

/// # Safety
/// Same allocation and disjointness requirements as [star_asset_path_split].
#[no_mangle]
pub unsafe extern "C" fn star_asset_path_filename_range(
    input: *const u8,
    len: usize,
    out: *mut StarAssetPathRange,
) -> i32 {
    run(input, len, out, 1, filename_range)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ptr::{null, null_mut};

    #[test]
    fn native_metadata_anchors() {
        // Literal anchors traced to the original std::string branches, not a
        // corrected grammar. In particular a:x differs from a:xy in count.
        for (input, fields) in [
            (&b""[..], [NPOS, NPOS, 0, NPOS]),
            (&b"abc"[..], [NPOS, NPOS, 0, NPOS]),
            (&b"a:"[..], [1, NPOS, 0, NPOS]),
            (&b"a:x"[..], [1, 2, NPOS - 2, NPOS]),
            (&b"a:xy"[..], [1, 2, NPOS, NPOS]),
            (&b"a:?d"[..], [1, NPOS, 0, 2]),
            (&b"a:x:y?d"[..], [1, 2, 3, 5]),
            (&b"?a:b"[..], [0, NPOS, 0, 0]),
            (&b"\xff\0:x?\xfe"[..], [2, 3, 1, 4]),
        ] {
            let expected = StarAssetPathSplit {
                base_len: fields[0],
                sub_start: fields[1],
                sub_count: fields[2],
                directive_start: fields[3],
            };
            let mut actual = expected;
            assert_eq!(
                unsafe { star_asset_path_split(input.as_ptr(), input.len(), &mut actual) },
                0
            );
            assert_eq!(actual, expected);
        }
        for (input, start, end) in [
            (&b""[..], 0, 0),
            (&b"/a/b:c?d"[..], 3, 4),
            (&b"/a/f.ext:q?d"[..], 3, 8),
            (&b"/a/?x/y"[..], 3, 3),
            (&b"\xff/\0:x"[..], 2, 3),
            (&b"a/b/"[..], 4, 4),
        ] {
            let mut actual = StarAssetPathRange {
                start: NPOS,
                end: NPOS,
            };
            assert_eq!(
                unsafe { star_asset_path_filename_range(input.as_ptr(), input.len(), &mut actual) },
                0
            );
            assert_eq!(actual, StarAssetPathRange { start, end });
        }
    }

    unsafe fn invalid_cases<T: Copy + std::fmt::Debug + PartialEq>(
        sentinel: T,
        call: unsafe extern "C" fn(*const u8, usize, *mut T) -> i32,
        op: u32,
    ) {
        let input = [17u8; 128];
        let mut output = sentinel;
        let before = star_asset_path_call_count(op);
        for (p, n, out) in [
            (null(), 1, &mut output as *mut T),
            (input.as_ptr(), isize::MAX as usize + 1, &mut output),
            (usize::MAX as *const u8, 2, &mut output),
            (input.as_ptr(), 1, null_mut()),
            (input.as_ptr(), 1, 1usize as *mut T),
            (
                input.as_ptr(),
                1,
                (usize::MAX & !(align_of::<T>() - 1)) as *mut T,
            ),
        ] {
            assert_eq!(call(p, n, out), 2);
            assert_eq!(output, sentinel);
        }
        // Overlap with the start and the LAST input byte must both be rejected.
        let p = (&mut output as *mut T).cast::<u8>();
        assert_eq!(call(p, size_of::<T>(), &mut output), 2);
        assert_eq!(call(p.add(size_of::<T>() - 1), 1, &mut output), 2);
        assert_eq!(output, sentinel);
        assert_eq!(star_asset_path_call_count(op), before);
        assert_eq!(call(null(), 0, &mut output), 0);
        assert_eq!(star_asset_path_call_count(op), before + 1);
    }

    #[test]
    fn abi_validation_is_transactional() {
        unsafe {
            invalid_cases(
                StarAssetPathSplit {
                    base_len: 12,
                    sub_start: 34,
                    sub_count: 56,
                    directive_start: 78,
                },
                star_asset_path_split,
                0,
            );
            invalid_cases(
                StarAssetPathRange { start: 12, end: 34 },
                star_asset_path_filename_range,
                1,
            );
        }
    }

    #[test]
    fn contained_panic_does_not_commit_output_or_receipt() {
        let mut out = StarAssetPathRange { start: 17, end: 29 };
        let before = star_asset_path_call_count(1);
        let status = unsafe {
            run(null(), 0, &mut out, 1, |_| {
                panic!("isolated kernel failure")
            })
        };
        assert_eq!(status, 3);
        assert_eq!(out, StarAssetPathRange { start: 17, end: 29 });
        assert_eq!(star_asset_path_call_count(1), before);
    }

    #[test]
    fn receipts_are_thread_local_and_operation_specific() {
        let before = [star_asset_path_call_count(0), star_asset_path_call_count(1)];
        std::thread::spawn(|| {
            assert_eq!(star_asset_path_call_count(0), 0);
            assert_eq!(star_asset_path_call_count(1), 0);
            let mut out = StarAssetPathRange { start: 1, end: 2 };
            assert_eq!(
                unsafe { star_asset_path_filename_range(null(), 0, &mut out) },
                0
            );
            assert_eq!(star_asset_path_call_count(0), 0);
            assert_eq!(star_asset_path_call_count(1), 1);
        })
        .join()
        .unwrap();
        assert_eq!(
            [star_asset_path_call_count(0), star_asset_path_call_count(1)],
            before
        );
        assert_eq!(star_asset_path_call_count(2), 0);
        assert_eq!(star_asset_path_call_count(u32::MAX), 0);
    }
}
