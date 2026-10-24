//! Legacy SHA-256, derived from the engine's Tom St Denis implementation.
//! The 32-bit bit count and destructive repeated finalization are intentional.
//! Tom St Denis attribution retained from StarSha256.cpp.
use std::cell::Cell;
use std::panic::{catch_unwind, AssertUnwindSafe};

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct StarSha256State {
    pub state: [u32; 8],
    pub length: u32,
    pub curlen: u32,
    pub buf: [u8; 64],
}
const _: () = assert!(std::mem::size_of::<StarSha256State>() == 104);
const _: () = assert!(std::mem::align_of::<StarSha256State>() == 4);
const K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];
impl StarSha256State {
    fn new() -> Self {
        Self {
            state: [
                0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
                0x5be0cd19,
            ],
            length: 0,
            curlen: 0,
            buf: [0; 64],
        }
    }
    fn compress(&mut self) {
        let mut w = [0u32; 64];
        for (word, bytes) in w.iter_mut().zip(self.buf.chunks_exact(4)) {
            *word = u32::from_be_bytes(bytes.try_into().unwrap());
        }
        for i in 16..64 {
            let x = w[i - 2];
            let y = w[i - 15];
            let g1 = x.rotate_right(17) ^ x.rotate_right(19) ^ (x >> 10);
            let g0 = y.rotate_right(7) ^ y.rotate_right(18) ^ (y >> 3);
            w[i] = g1
                .wrapping_add(w[i - 7])
                .wrapping_add(g0)
                .wrapping_add(w[i - 16]);
        }
        let mut s = self.state;
        for i in 0..64 {
            let sig1 = s[4].rotate_right(6) ^ s[4].rotate_right(11) ^ s[4].rotate_right(25);
            let sig0 = s[0].rotate_right(2) ^ s[0].rotate_right(13) ^ s[0].rotate_right(22);
            let ch = (s[4] & s[5]) ^ (!s[4] & s[6]);
            let maj = (s[0] & s[1]) ^ (s[0] & s[2]) ^ (s[1] & s[2]);
            let t0 = s[7]
                .wrapping_add(sig1)
                .wrapping_add(ch)
                .wrapping_add(K[i])
                .wrapping_add(w[i]);
            let t1 = sig0.wrapping_add(maj);
            s = [
                t0.wrapping_add(t1),
                s[0],
                s[1],
                s[2],
                s[3].wrapping_add(t0),
                s[4],
                s[5],
                s[6],
            ];
        }
        for (a, b) in self.state.iter_mut().zip(s) {
            *a = a.wrapping_add(b);
        }
    }
    unsafe fn update(&mut self, input: *const u8, len: usize) {
        for i in 0..len {
            self.buf[self.curlen as usize] = input.add(i).read();
            self.curlen += 1;
            if self.curlen == 64 {
                self.compress();
                self.length = self.length.wrapping_add(512);
                self.curlen = 0;
            }
        }
    }
    fn finalize(&mut self) -> [u8; 32] {
        self.length = self.length.wrapping_add(self.curlen.wrapping_mul(8));
        self.buf[self.curlen as usize] = 0x80;
        self.curlen += 1;
        if self.curlen > 56 {
            self.buf[self.curlen as usize..].fill(0);
            self.compress();
            self.curlen = 0;
        }
        self.buf[self.curlen as usize..60].fill(0);
        self.curlen = 56;
        self.buf[60..64].copy_from_slice(&self.length.to_be_bytes());
        self.compress();
        let mut digest = [0; 32];
        for (bytes, word) in digest.chunks_exact_mut(4).zip(self.state) {
            bytes.copy_from_slice(&word.to_be_bytes());
        }
        digest
    }
}
thread_local! { static CALLS: Cell<[u64;4]> = const { Cell::new([0;4]) }; }
#[no_mangle]
pub extern "C" fn star_sha256_call_count(operation: u32) -> u64 {
    CALLS.with(|c| c.get().get(operation as usize).copied().unwrap_or(0))
}
fn contain(f: impl FnOnce() -> i32) -> i32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(3)
}
fn receipt(op: usize) {
    CALLS.with(|c| {
        let mut a = c.get();
        a[op] = a[op].wrapping_add(1);
        c.set(a);
    });
}
fn range(p: usize, n: usize) -> Option<(usize, usize)> {
    if n > isize::MAX as usize || (n != 0 && p == 0) {
        return None;
    }
    Some((p, p.checked_add(n)?))
}
fn state_range(p: *mut StarSha256State) -> Option<(usize, usize)> {
    if (p as usize) % std::mem::align_of::<StarSha256State>() != 0 {
        return None;
    }
    range(p as usize, std::mem::size_of::<StarSha256State>())
}
fn overlaps(a: (usize, usize), b: (usize, usize)) -> bool {
    a.0 != a.1 && b.0 != b.1 && a.0 < b.1 && b.0 < a.1
}
fn output_range(p: *mut u8, cap: usize) -> Option<(usize, usize)> {
    if cap < 32 {
        return None;
    }
    range(p as usize, cap)
}
/// # Safety
/// State must be a live writable aligned allocation. No pointers are retained.
#[no_mangle]
pub unsafe extern "C" fn star_sha256_init(state: *mut StarSha256State) -> i32 {
    contain(|| {
        if state_range(state).is_none() {
            return 2;
        }
        state.write(StarSha256State::new());
        receipt(0);
        0
    })
}
/// # Safety
/// State must be fully initialized and exclusively writable; input must be live
/// readable storage of input_len bytes, disjoint from state. Empty input may be null.
#[no_mangle]
pub unsafe extern "C" fn star_sha256_update(
    state: *mut StarSha256State,
    input: *const u8,
    input_len: usize,
) -> i32 {
    contain(|| {
        let Some(sr) = state_range(state) else {
            return 2;
        };
        let Some(ir) = range(input as usize, input_len) else {
            return 2;
        };
        if overlaps(sr, ir) {
            return 2;
        }
        let mut local = state.read();
        if local.curlen >= 64 {
            return 2;
        }
        local.update(input, input_len);
        state.write(local);
        receipt(1);
        0
    })
}
/// # Safety
/// State must be fully initialized and writable; output must be writable for its
/// declared capacity and disjoint from state. Errors do not modify either range.
#[no_mangle]
pub unsafe extern "C" fn star_sha256_finalize(
    state: *mut StarSha256State,
    out: *mut u8,
    out_capacity: usize,
) -> i32 {
    contain(|| {
        let Some(sr) = state_range(state) else {
            return 2;
        };
        let Some(or) = output_range(out, out_capacity) else {
            return 2;
        };
        if overlaps(sr, or) {
            return 2;
        }
        let mut local = state.read();
        if local.curlen >= 64 {
            return 2;
        }
        let digest = local.finalize();
        state.write(local);
        std::ptr::copy_nonoverlapping(digest.as_ptr(), out, 32);
        receipt(2);
        0
    })
}
/// # Safety
/// Input/output must be live readable/writable allocations of the declared sizes.
/// Input may be null when empty. Input/output overlap is supported: all reads
/// complete before any output write, without aliased foreign slices.
#[no_mangle]
pub unsafe extern "C" fn star_sha256_oneshot(
    input: *const u8,
    input_len: usize,
    out: *mut u8,
    out_capacity: usize,
) -> i32 {
    contain(|| {
        if range(input as usize, input_len).is_none() || output_range(out, out_capacity).is_none() {
            return 2;
        }
        let mut local = StarSha256State::new();
        local.update(input, input_len);
        let digest = local.finalize();
        std::ptr::copy_nonoverlapping(digest.as_ptr(), out, 32);
        receipt(3);
        0
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ptr::{null, null_mut};

    fn hash(bytes: &[u8]) -> [u8; 32] {
        let mut out = [0; 32];
        assert_eq!(
            unsafe { star_sha256_oneshot(bytes.as_ptr(), bytes.len(), out.as_mut_ptr(), 32) },
            0
        );
        out
    }

    #[test]
    fn repository_anchors() {
        // Expected literals from source/test/sha_test.cpp, not a claim about
        // published standard-vector provenance.
        for (input, expected) in [
            (
                "",
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            ),
            (
                "1",
                "6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b",
            ),
            (
                "/animations/muzzleflash/bulletmuzzle1/bulletmuzzle1.png",
                "7e4a2cbe3826945d5f6593b347b49285b00ba8471cb4f6edc9b045c2cb3b6ea6",
            ),
            (
                "This is the one we were having problems with: 55 chars.",
                "6bb7bf41f5f6e625d39e54d58fcc4e458a3af2e30d85eb90199de31fd668a16a",
            ),
            (
                "This is a 56 char string. Just making sure it's good too",
                "446867368ec996d69a822e63454917372c0d0a23d46e6727730b975fcb7a8f25",
            ),
        ] {
            let actual: String = hash(input.as_bytes())
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect();
            assert_eq!(actual, expected);
        }
    }

    #[test]
    fn boundary_partitions_copies_and_destructive_finalize() {
        for len in [0, 1, 55, 56, 57, 63, 64, 65, 119, 120, 128] {
            let input: Vec<u8> = (0..len).map(|n| (n * 73) as u8).collect();
            let expected = hash(&input);
            for split in 0..=len {
                let mut state = StarSha256State::new();
                unsafe {
                    assert_eq!(star_sha256_update(&mut state, input.as_ptr(), split), 0);
                    let mut fork = state;
                    assert_eq!(
                        star_sha256_update(&mut state, input.as_ptr().add(split), len - split),
                        0
                    );
                    assert_eq!(
                        star_sha256_update(&mut fork, input.as_ptr().add(split), len - split),
                        0
                    );
                    let mut out = [0; 32];
                    assert_eq!(star_sha256_finalize(&mut state, out.as_mut_ptr(), 32), 0);
                    assert_eq!(out, expected);
                    assert_eq!(fork.finalize(), expected);
                    assert_eq!(fork, state);
                    assert_eq!(state.curlen, 56);
                    let old_length = state.length;
                    assert_eq!(star_sha256_finalize(&mut state, out.as_mut_ptr(), 32), 0);
                    assert_ne!(out, expected);
                    assert_eq!(state.length, old_length.wrapping_add(448));
                    assert_eq!(state.curlen, 56);
                    assert_eq!(star_sha256_init(&mut state), 0);
                    assert_eq!(state, StarSha256State::new());
                    assert_eq!(star_sha256_update(&mut state, null(), 0), 0);
                    assert_eq!(state.finalize(), hash(&[]));
                }
            }
        }
    }

    #[test]
    fn bitlength_wrap_and_zero_high_word() {
        let mut state = StarSha256State::new();
        state.length = 0xfffffe00;
        state.curlen = 63;
        state.buf.fill(17);
        let byte = 18;
        unsafe {
            assert_eq!(star_sha256_update(&mut state, &byte, 1), 0);
        }
        assert_eq!(state.length, 0);
        assert_eq!(state.curlen, 0);
        state.length = 0xfffffff8;
        state.curlen = 1;
        state.finalize();
        assert_eq!(state.length, 0);
        assert_eq!(&state.buf[56..64], &[0; 8]);
        state.finalize();
        assert_eq!(state.length, 448);
        assert_eq!(&state.buf[56..60], &[0; 4]);
        assert_eq!(&state.buf[60..64], &448u32.to_be_bytes());
    }

    #[test]
    fn invalid_shapes_are_transactional() {
        let mut s = StarSha256State::new();
        let snapshot = s;
        let mut out = [0xa5; 64];
        let before = std::array::from_fn::<_, 4, _>(|i| star_sha256_call_count(i as u32));
        unsafe {
            assert_eq!(star_sha256_init(null_mut()), 2);
            assert_eq!(star_sha256_init(1usize as *mut StarSha256State), 2);
            assert_eq!(
                star_sha256_init((usize::MAX - 3) as *mut StarSha256State),
                2
            );
            assert_eq!(star_sha256_update(&mut s, null(), 1), 2);
            assert_eq!(star_sha256_update(&mut s, out.as_ptr(), usize::MAX), 2);
            assert_eq!(
                star_sha256_update(&mut s, (usize::MAX - 2) as *const u8, 4),
                2
            );
            let p = &mut s as *mut StarSha256State;
            assert_eq!(star_sha256_update(p, p.cast(), 1), 2);
            assert_eq!(star_sha256_finalize(p, p.cast(), 32), 2);
            assert_eq!(star_sha256_finalize(&mut s, out.as_mut_ptr(), 31), 2);
            assert_eq!(star_sha256_finalize(&mut s, null_mut(), 32), 2);
            assert_eq!(
                star_sha256_finalize(&mut s, out.as_mut_ptr(), usize::MAX),
                2
            );
            assert_eq!(star_sha256_oneshot(null(), 1, out.as_mut_ptr(), 64), 2);
            assert_eq!(star_sha256_oneshot(null(), 0, null_mut(), 32), 2);
            assert_eq!(star_sha256_oneshot(null(), 0, out.as_mut_ptr(), 31), 2);
        }
        assert_eq!(s, snapshot);
        s.curlen = 64;
        let invalid = s;
        unsafe {
            assert_eq!(star_sha256_update(&mut s, null(), 0), 2);
            assert_eq!(star_sha256_finalize(&mut s, out.as_mut_ptr(), 32), 2);
        }
        assert_eq!(s, invalid);
        assert_eq!(out, [0xa5; 64]);
        assert_eq!(
            before,
            std::array::from_fn(|i| star_sha256_call_count(i as u32))
        );
        assert_eq!(star_sha256_call_count(99), 0);
    }

    #[test]
    fn oneshot_aliases_and_receipts() {
        for len in [0, 1, 32, 55, 64, 128] {
            for offset in [0, 1, 16, 64] {
                let mut bytes = [0u8; 256];
                for (i, b) in bytes.iter_mut().enumerate() {
                    *b = i as u8;
                }
                let expected = hash(&bytes[..len]);
                let before = star_sha256_call_count(3);
                unsafe {
                    assert_eq!(
                        star_sha256_oneshot(
                            bytes.as_ptr(),
                            len,
                            bytes.as_mut_ptr().add(offset),
                            32
                        ),
                        0
                    );
                }
                assert_eq!(&bytes[offset..offset + 32], &expected);
                assert_eq!(star_sha256_call_count(3), before + 1);
            }
        }
    }

    #[test]
    fn tls_and_panic_containment() {
        let before = std::array::from_fn::<_, 4, _>(|i| star_sha256_call_count(i as u32));
        let threads: Vec<_> = (0..4)
            .map(|_| {
                std::thread::spawn(|| {
                    assert_eq!(
                        std::array::from_fn::<_, 4, _>(|i| star_sha256_call_count(i as u32)),
                        [0; 4]
                    );
                    let mut s = StarSha256State::new();
                    let mut out = [0; 32];
                    unsafe {
                        assert_eq!(star_sha256_init(&mut s), 0);
                        assert_eq!(star_sha256_update(&mut s, null(), 0), 0);
                        assert_eq!(star_sha256_finalize(&mut s, out.as_mut_ptr(), 32), 0);
                        assert_eq!(star_sha256_oneshot(null(), 0, out.as_mut_ptr(), 32), 0);
                    }
                    assert_eq!(
                        std::array::from_fn::<_, 4, _>(|i| star_sha256_call_count(i as u32)),
                        [1; 4]
                    );
                })
            })
            .collect();
        for t in threads {
            t.join().unwrap();
        }
        let mut state = StarSha256State::new();
        let snapshot = state;
        let mut output = [0xa5; 32];
        assert_eq!(
            contain(|| {
                let mut local = state;
                local.finalize();
                if local.curlen == 56 {
                    panic!("test panic before commit");
                }
                state = local;
                output = [0; 32];
                receipt(2);
                0
            }),
            3
        );
        assert_eq!(state, snapshot);
        assert_eq!(output, [0xa5; 32]);
        assert_eq!(
            before,
            std::array::from_fn(|i| star_sha256_call_count(i as u32))
        );
    }
}
