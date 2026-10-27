//! pure byte work only: native ownership, allocation and codecs stay in C++.
use std::cell::Cell;
use std::mem::{align_of, size_of};
use std::panic::{catch_unwind, AssertUnwindSafe};

const OK: u32 = 0;
const INVALID: u32 = 2;
const PANIC: u32 = 3;
#[repr(u32)]
enum Action {
    None = 0,
    Gzip = 1,
    Zlib = 2,
    Zstd = 3,
}
thread_local! { static COMPLETED: Cell<[u64; 2]> = const { Cell::new([0; 2]) }; }
fn complete(op: usize) {
    COMPLETED.with(|c| {
        let mut v = c.get();
        v[op] = v[op].wrapping_add(1);
        c.set(v);
    });
}
#[no_mangle]
pub extern "C" fn star_path_embed_completed(op: u32) -> u64 {
    COMPLETED.with(|c| c.get().get(op as usize).copied().unwrap_or(0))
}
fn contained(f: impl FnOnce() -> u32) -> u32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(PANIC)
}
fn span(p: usize, n: usize, alignment: usize) -> bool {
    (n == 0 || p != 0) && p % alignment == 0 && p.checked_add(n).is_some()
}
fn overlap(a: usize, an: usize, b: usize, bn: usize) -> bool {
    an != 0 && bn != 0 && a < b + bn && b < a + an
}
fn eligible(n: usize, cap: usize) -> bool {
    n <= isize::MAX as usize / 2 && cap <= isize::MAX as usize && cap >= n * 2
}
/// # Safety
/// `action` must be a live aligned writable u32; numeric checks do not establish provenance.
#[no_mangle]
pub unsafe extern "C" fn star_path_embed_select(method: u32, action: *mut u32) -> u32 {
    if !span(action as usize, size_of::<u32>(), align_of::<u32>()) {
        return INVALID;
    }
    contained(|| {
        let selected = match method {
            0 => Action::None,
            1 => Action::Gzip,
            2 => Action::Zlib,
            3 => Action::Zstd,
            _ => return INVALID,
        };
        action.write(selected as u32);
        complete(0);
        OK
    })
}
/// # Safety
/// Nonempty spans must be live with valid provenance; input is initialized,
/// output writable, written aligned/writable. All three spans are disjoint;
/// no concurrent mutation and no retained borrows. See StarRustPathEmbed.h.
#[no_mangle]
pub unsafe extern "C" fn star_path_embed_escape(
    input: *const u8,
    n: usize,
    output: *mut u8,
    cap: usize,
    written: *mut usize,
) -> u32 {
    let (i, o, w) = (input as usize, output as usize, written as usize);
    let ws = size_of::<usize>();
    if !eligible(n, cap)
        || !span(i, n, 1)
        || !span(o, cap, 1)
        || !span(w, ws, align_of::<usize>())
        || overlap(i, n, o, cap)
        || overlap(i, n, w, ws)
        || overlap(o, cap, w, ws)
    {
        return INVALID;
    }
    contained(|| {
        let mut len = 0;
        // raw access avoids creating a zero-length slice from a null pointer.
        for k in 0..n {
            let byte = input.add(k).read();
            let replacement = match byte {
                b'%' => Some(b'%'),
                b':' => Some(b'c'),
                b'?' => Some(b'q'),
                b';' => Some(b's'),
                b'/' => Some(b'b'),
                _ => None,
            };
            if let Some(r) = replacement {
                output.add(len).write(b'%');
                output.add(len + 1).write(r);
                len += 2;
            } else {
                output.add(len).write(byte);
                len += 1;
            }
        }
        written.write(len);
        complete(1);
        OK
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ptr::{null, null_mut};
    fn escaped(input: &[u8]) -> Vec<u8> {
        let mut out = vec![0xa5; input.len() * 2];
        let mut n = usize::MAX;
        assert_eq!(
            unsafe {
                star_path_embed_escape(
                    input.as_ptr(),
                    input.len(),
                    out.as_mut_ptr(),
                    out.len(),
                    &mut n,
                )
            },
            OK
        );
        out.truncate(n);
        out
    }
    #[test]
    fn named_actions_and_rejection() {
        let before = star_path_embed_completed(0);
        let mut action = 99;
        for (m, a) in [
            (0, Action::None),
            (1, Action::Gzip),
            (2, Action::Zlib),
            (3, Action::Zstd),
        ] {
            assert_eq!(unsafe { star_path_embed_select(m, &mut action) }, OK);
            assert_eq!(action, a as u32);
        }
        for m in [4, u32::MAX] {
            action = 99;
            assert_eq!(unsafe { star_path_embed_select(m, &mut action) }, INVALID);
            assert_eq!(action, 99);
        }
        assert_eq!(unsafe { star_path_embed_select(0, null_mut()) }, INVALID);
        let mut owned = [0u32; 4];
        assert_eq!(
            unsafe { star_path_embed_select(0, owned.as_mut_ptr().cast::<u8>().add(1).cast()) },
            INVALID
        );
        assert_eq!(owned, [0; 4]);
        assert_eq!(star_path_embed_completed(0), before + 4);
    }
    #[test]
    fn every_byte_and_literal_binary() {
        for byte in 0..=255u8 {
            let expected: &[u8] = match byte {
                b'%' => b"%%",
                b':' => b"%c",
                b'?' => b"%q",
                b';' => b"%s",
                b'/' => b"%b",
                _ => std::slice::from_ref(&byte),
            };
            assert_eq!(escaped(&[byte]), expected);
        }
        assert_eq!(escaped(b"%:?;/\0\xff\xc3\xa9"), b"%%%c%q%s%b\0\xff\xc3\xa9");
        let mut n = 99usize;
        assert_eq!(
            unsafe { star_path_embed_escape(null(), 0, null_mut(), 0, &mut n) },
            OK
        );
        assert_eq!(n, 0);
    }
    #[test]
    fn rejected_spans_leave_all_state_unchanged() {
        let input = [b':'; 8];
        let mut owned = [0x5555555555555555usize; 16];
        let snapshot = owned;
        let p = owned.as_mut_ptr().cast::<u8>();
        let mut n = 99usize;
        let np = &mut n as *mut usize;
        let before = star_path_embed_completed(1);
        let cases = [
            (input.as_ptr(), 8, p, 15, np),
            (null(), 8, p, 16, np),
            (input.as_ptr(), 8, null_mut(), 16, np),
            (input.as_ptr(), 8, p, 16, null_mut()),
            (input.as_ptr(), usize::MAX, p, 16, np),
            (input.as_ptr(), 8, p, usize::MAX, np),
            (p.cast_const(), 8, unsafe { p.add(2) }, 16, np),
            (input.as_ptr(), 8, p, 16, p.cast()),
            (p.cast_const(), 16, unsafe { p.add(32) }, 32, p.cast()),
            (input.as_ptr(), 8, p, 16, unsafe { p.add(17).cast() }),
        ];
        for (i, len, o, cap, w) in cases {
            assert_eq!(
                unsafe { star_path_embed_escape(i, len, o, cap, w) },
                INVALID
            );
            assert_eq!(owned, snapshot);
            assert_eq!(n, 99);
            assert_eq!(star_path_embed_completed(1), before);
        }
        assert!(!span(usize::MAX - 1, 2, 1));
        assert!(eligible(isize::MAX as usize / 2, isize::MAX as usize - 1));
        assert!(!eligible(isize::MAX as usize / 2 + 1, isize::MAX as usize));
        assert!(!eligible(0, usize::MAX));
    }
    #[test]
    fn tls_wrap_and_contained_panic() {
        COMPLETED.with(|c| c.set([u64::MAX; 2]));
        let mut action = 99;
        assert_eq!(unsafe { star_path_embed_select(0, &mut action) }, OK);
        assert_eq!(escaped(b":"), b"%c");
        assert_eq!(star_path_embed_completed(0), 0);
        assert_eq!(star_path_embed_completed(1), 0);
        complete(0);
        std::thread::spawn(|| {
            assert_eq!(star_path_embed_completed(0), 0);
            complete(0);
            assert_eq!(star_path_embed_completed(0), 1);
        })
        .join()
        .unwrap();
        assert_eq!(star_path_embed_completed(0), 1);
        assert_eq!(star_path_embed_completed(99), 0);
        assert_eq!(contained(|| panic!("contained test panic")), PANIC);
    }
}
