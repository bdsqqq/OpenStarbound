use std::cell::Cell;
use std::mem::align_of;
use std::panic::{catch_unwind, AssertUnwindSafe};

const MULTIPLIER: u64 = 809430660;
thread_local! {
    static CALLS: Cell<[u64; 3]> = const { Cell::new([0; 3]) };
}

#[no_mangle]
pub extern "C" fn star_random_mwc_call_count(op: u32) -> u64 {
    CALLS.with(|c| c.get().get(op as usize).copied().unwrap_or(0))
}

// Check every span before any typed access, including reads of initialized state.
// Address checks cannot establish allocation validity; that remains the caller's contract.
fn valid(spans: &[(usize, usize, usize)]) -> bool {
    for (i, &(start, len, align)) in spans.iter().enumerate() {
        if start == 0 || start % align != 0 {
            return false;
        }
        let Some(end) = start.checked_add(len) else {
            return false;
        };
        for &(other, other_len, _) in &spans[..i] {
            let Some(other_end) = other.checked_add(other_len) else {
                return false;
            };
            if start < other_end && other < end {
                return false;
            }
        }
    }
    true
}

fn state_spans(data: *mut u32, carry: *mut u32, index: *mut u8) -> [(usize, usize, usize); 3] {
    [
        (data as usize, 1024, align_of::<u32>()),
        (carry as usize, 4, align_of::<u32>()),
        (index as usize, 1, align_of::<u8>()),
    ]
}

fn step(word: u32, carry: u32) -> (u32, u32) {
    let t = MULTIPLIER * u64::from(word) + u64::from(carry);
    (t as u32, (t >> 32) as u32)
}

fn draw(data: &mut [u32; 256], carry: &mut u32, index: &mut u8) -> u32 {
    *index = index.wrapping_add(1);
    let (word, next_carry) = step(data[*index as usize], *carry);
    data[*index as usize] = word;
    *carry = next_carry;
    word
}

// Prepare before commit. The commit closure contains only raw stores and Cell::set;
// no allocation, callbacks, checked arithmetic, or other unwinding operations.
fn transaction<P>(op: usize, prepare: impl FnOnce() -> Option<P>, commit: impl FnOnce(P)) -> i32 {
    catch_unwind(AssertUnwindSafe(|| {
        let Some(prepared) = prepare() else {
            return 2;
        };
        CALLS.with(|c| {
            let mut counts = c.get();
            counts[op] = counts[op].wrapping_add(1);
            commit(prepared);
            c.set(counts);
        });
        0
    }))
    .unwrap_or(3)
}

/// # Safety
/// Three live writable aligned disjoint spans of 1024/4/1 bytes are required.
/// Old contents may be uninitialized and are never read.
#[no_mangle]
pub unsafe extern "C" fn star_random_mwc_init(
    data: *mut u32,
    carry: *mut u32,
    index: *mut u8,
    seed: u64,
) -> i32 {
    transaction(
        0,
        || {
            if !valid(&state_spans(data, carry, index)) {
                return None;
            }
            let mut words = [0; 256];
            let mut c = (seed % MULTIPLIER) as u32;
            words[0] = seed as u32;
            words[1] = (seed >> 32) as u32;
            for i in 2..256 {
                words[i] = words[i - 2].wrapping_mul(69069).wrapping_add(362437);
            }
            let mut ix = 255;
            for _ in 0..32 {
                draw(&mut words, &mut c, &mut ix);
            }
            Some((words, c, ix))
        },
        |(words, c, ix)| {
            std::ptr::copy_nonoverlapping(words.as_ptr(), data, 256);
            carry.write(c);
            index.write(ix);
        },
    )
}

/// # Safety
/// Same spans as init, but all state bytes must be initialized.
#[no_mangle]
pub unsafe extern "C" fn star_random_mwc_add_entropy(
    data: *mut u32,
    carry: *mut u32,
    index: *mut u8,
    seed: u64,
) -> i32 {
    transaction(
        1,
        || {
            if !valid(&state_spans(data, carry, index)) {
                return None;
            }
            let mut words = data.cast::<[u32; 256]>().read();
            let mut c = carry.read();
            let mut ix = index.read();
            let high = u64::from(draw(&mut words, &mut c, &mut ix));
            let mixed = seed ^ ((high << 32) | u64::from(draw(&mut words, &mut c, &mut ix)));
            c = ((u64::from(c) ^ mixed) % MULTIPLIER) as u32;
            words[0] ^= mixed as u32;
            words[1] ^= ((mixed >> 32) ^ mixed) as u32;
            for i in 2..256 {
                words[i] ^= words[i - 2].wrapping_mul(69069).wrapping_add(362437);
            }
            Some((words, c, ix))
        },
        |(words, c, ix)| {
            std::ptr::copy_nonoverlapping(words.as_ptr(), data, 256);
            carry.write(c);
            index.write(ix);
        },
    )
}

/// # Safety
/// Initialized state spans as above, plus a live writable aligned out[1] u32,
/// disjoint from ALL state spans. Only the selected word is read or changed.
#[no_mangle]
pub unsafe extern "C" fn star_random_mwc_next(
    data: *mut u32,
    carry: *mut u32,
    index: *mut u8,
    out: *mut u32,
) -> i32 {
    transaction(
        2,
        || {
            let [a, b, c] = state_spans(data, carry, index);
            if !valid(&[a, b, c, (out as usize, 4, align_of::<u32>())]) {
                return None;
            }
            let ix = index.read().wrapping_add(1);
            let (word, c) = step(data.add(ix as usize).read(), carry.read());
            Some((ix, word, c))
        },
        |(ix, word, c)| {
            data.add(ix as usize).write(word);
            carry.write(c);
            index.write(ix);
            out.write(word);
        },
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::mem::MaybeUninit;

    fn state(seed: u64) -> ([u32; 256], u32, u8) {
        let mut words = MaybeUninit::<[u32; 256]>::uninit();
        let mut c = MaybeUninit::<u32>::uninit();
        let mut ix = MaybeUninit::<u8>::uninit();
        unsafe {
            assert_eq!(
                star_random_mwc_init(
                    words.as_mut_ptr().cast(),
                    c.as_mut_ptr(),
                    ix.as_mut_ptr(),
                    seed
                ),
                0
            );
            (words.assume_init(), c.assume_init(), ix.assume_init())
        }
    }

    #[test]
    fn literal_sequence_and_receipts() {
        let before = [
            star_random_mwc_call_count(0),
            star_random_mwc_call_count(1),
            star_random_mwc_call_count(2),
        ];
        let (mut words, mut c, mut ix) = state(31415926);
        assert_eq!(ix, 31);
        let mut out = 0;
        for expected in [2950892229, 1418047276, 3790079132, 445970691] {
            assert_eq!(
                unsafe { star_random_mwc_next(words.as_mut_ptr(), &mut c, &mut ix, &mut out) },
                0
            );
            assert_eq!(out, expected);
        }
        assert_eq!(
            unsafe { star_random_mwc_add_entropy(words.as_mut_ptr(), &mut c, &mut ix, 27182818) },
            0
        );
        for expected in [2992900064, 3569137546, 1545455748] {
            assert_eq!(
                unsafe { star_random_mwc_next(words.as_mut_ptr(), &mut c, &mut ix, &mut out) },
                0
            );
            assert_eq!(out, expected);
        }
        assert_eq!(
            [
                star_random_mwc_call_count(0),
                star_random_mwc_call_count(1),
                star_random_mwc_call_count(2)
            ],
            [before[0] + 1, before[1] + 1, before[2] + 7]
        );
        assert_eq!(star_random_mwc_call_count(3), 0);
    }

    // Independent scalar reference: all arithmetic uses explicit wide reduction,
    // and the full state is compared after wraparound and entropy, not just output.
    fn reference_next(words: &mut [u32; 256], c: &mut u32, ix: &mut u8) -> u32 {
        *ix = ((*ix as u16 + 1) % 256) as u8;
        let t = 809430660_u64 * words[*ix as usize] as u64 + *c as u64;
        *c = (t / 4294967296) as u32;
        words[*ix as usize] = (t % 4294967296) as u32;
        words[*ix as usize]
    }

    #[test]
    fn full_state_extreme_seeds_carry_index_entropy() {
        for seed in [0, 1, u32::MAX as u64, 1_u64 << 32, u64::MAX, 809430660] {
            let (mut words, mut c, mut ix) = state(seed);
            let mut expected = [0; 256];
            expected[0] = seed as u32;
            expected[1] = (seed >> 32) as u32;
            for i in 2..256 {
                expected[i] = ((69069_u64 * expected[i - 2] as u64 + 362437) % 4294967296) as u32;
            }
            let mut ec = (seed % 809430660) as u32;
            let mut ei = 255;
            for _ in 0..32 {
                reference_next(&mut expected, &mut ec, &mut ei);
            }
            assert_eq!((words, c, ix), (expected, ec, ei));
            // The ABI admits all carries and indexes, not only reachable ones.
            c = u32::MAX;
            ec = c;
            ix = 255;
            ei = ix;
            for _ in 0..513 {
                let mut out = 0;
                assert_eq!(
                    unsafe { star_random_mwc_next(words.as_mut_ptr(), &mut c, &mut ix, &mut out) },
                    0
                );
                assert_eq!(out, reference_next(&mut expected, &mut ec, &mut ei));
                assert_eq!((words, c, ix), (expected, ec, ei));
            }
            let high = reference_next(&mut expected, &mut ec, &mut ei) as u64;
            let low = reference_next(&mut expected, &mut ec, &mut ei) as u64;
            let mixed = seed ^ (high * 4294967296 + low);
            ec = ((ec as u64 ^ mixed) % 809430660) as u32;
            expected[0] ^= mixed as u32;
            expected[1] ^= ((mixed >> 32) ^ mixed) as u32;
            for i in 2..256 {
                expected[i] ^= ((69069_u64 * expected[i - 2] as u64 + 362437) % 4294967296) as u32;
            }
            assert_eq!(
                unsafe { star_random_mwc_add_entropy(words.as_mut_ptr(), &mut c, &mut ix, seed) },
                0
            );
            assert_eq!((words, c, ix), (expected, ec, ei));
        }
    }

    #[test]
    fn invalid_spans_all_pairwise_aliases_are_transactional() {
        // One aligned live allocation lets every pair alias without constructing
        // invalid references. Snapshot all bytes, including sentinels, before each call.
        let mut storage = [0x91a2b3c4_u32; 260];
        let p = storage.as_mut_ptr();
        let base = [
            p as usize,
            unsafe { p.add(256) } as usize,
            unsafe { p.add(257) } as usize,
            unsafe { p.add(258) } as usize,
        ];
        let counts = CALLS.with(Cell::get);
        for op in 0..3 {
            for a in 0..if op == 2 { 4 } else { 3 } {
                for bad in [0, usize::MAX] {
                    let mut pointers = base;
                    pointers[a] = bad;
                    let snapshot = storage;
                    assert_eq!(unsafe { invoke(op, pointers) }, 2);
                    assert_eq!(storage, snapshot);
                }
                if a != 2 {
                    let mut pointers = base;
                    pointers[a] += 1;
                    let snapshot = storage;
                    assert_eq!(unsafe { invoke(op, pointers) }, 2);
                    assert_eq!(storage, snapshot);
                }
                for b in 0..a {
                    let mut pointers = base;
                    pointers[a] = pointers[b];
                    let snapshot = storage;
                    assert_eq!(unsafe { invoke(op, pointers) }, 2);
                    assert_eq!(storage, snapshot);
                }
            }
        }
        // Aligned range overflow and partial (not merely equal-start) overlap.
        for pointers in [
            [usize::MAX - 1023, base[1], base[2], base[3]],
            [base[0], base[0] + 1020, base[2], base[3]],
            [base[0], base[1], base[1] + 3, base[3]],
        ] {
            let snapshot = storage;
            assert_eq!(unsafe { invoke(2, pointers) }, 2);
            assert_eq!(storage, snapshot);
        }
        assert_eq!(CALLS.with(Cell::get), counts);
    }

    unsafe fn invoke(op: usize, p: [usize; 4]) -> i32 {
        match op {
            0 => star_random_mwc_init(p[0] as *mut u32, p[1] as *mut u32, p[2] as *mut u8, 123),
            1 => star_random_mwc_add_entropy(
                p[0] as *mut u32,
                p[1] as *mut u32,
                p[2] as *mut u8,
                123,
            ),
            _ => star_random_mwc_next(
                p[0] as *mut u32,
                p[1] as *mut u32,
                p[2] as *mut u8,
                p[3] as *mut u32,
            ),
        }
    }

    #[test]
    fn contained_prepare_panic_and_thread_local_receipts() {
        let before = CALLS.with(Cell::get);
        let mut sentinel = 42;
        assert_eq!(
            transaction::<u32>(
                0,
                || panic!("isolated preparation failure"),
                |v| sentinel = v
            ),
            3
        );
        assert_eq!(sentinel, 42);
        assert_eq!(CALLS.with(Cell::get), before);
        std::thread::spawn(|| {
            assert_eq!(CALLS.with(Cell::get), [0; 3]);
            state(0);
            assert_eq!(CALLS.with(Cell::get), [1, 0, 0]);
        })
        .join()
        .unwrap();
        assert_eq!(CALLS.with(Cell::get), before);
    }
}
