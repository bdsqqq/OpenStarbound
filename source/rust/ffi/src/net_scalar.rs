//! By-value size/event and base-version kernels; storage and native hooks stay native.
use std::cell::Cell;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const PANIC: u32 = 3;
const NEXT: u32 = 0;
const PULL: u32 = 1;
const CLAMP: u32 = 2;
const SIZE_ENCODE: u32 = 3;
const SIZE_DECODE: u32 = 4;
const VERSION_NEXT: u32 = 5;
const COMPAT: u32 = 6;
const COUNT: usize = 7;

#[repr(C)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SbNetScalarReply { pub value: u64, pub pulled: u64 }
static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
thread_local! {
    static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) };
}

fn valid(mode: u32, bits: u32, value: u64, previous: u64) -> bool {
    match mode {
        NEXT | VERSION_NEXT => bits == 0 && previous == 0,
        COMPAT => bits == 32 && value <= u32::MAX as u64 && previous <= u32::MAX as u64,
        PULL | CLAMP => bits == 0,
        SIZE_ENCODE => previous == 0 && (bits == 64 || (bits == 32 && value <= u32::MAX as u64)),
        SIZE_DECODE => previous == 0 && (bits == 32 || bits == 64),
        _ => false,
    }
}

fn scalar(mode: u32, bits: u32, value: u64, previous: u64) -> SbNetScalarReply {
    let mut reply = SbNetScalarReply::default();
    reply.value = match mode {
        NEXT | VERSION_NEXT => value.wrapping_add(1),
        COMPAT => u64::from(value == u32::MAX as u64 || previous >= value),
        PULL => { reply.pulled = value; value.wrapping_sub(previous) }
        CLAMP => value.min(previous),
        SIZE_ENCODE => if bits == 32 && value == u32::MAX as u64 { 0 } else { value.wrapping_add(1) },
        SIZE_DECODE => {
            let max = if bits == 32 { u32::MAX as u64 } else { u64::MAX };
            if value == 0 { max } else { (value - 1) & max }
        }
        _ => unreachable!("validated scalar mode"),
    };
    reply
}

fn barrier(f: impl FnOnce() -> u32) -> u32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(PANIC)
}

fn count_entry(mode: usize) {
    TOTALS[mode].fetch_add(1, Ordering::Relaxed);
    COUNTS.with(|cell| {
        let mut counts = cell.get();
        counts[mode] = counts[mode].wrapping_add(1);
        cell.set(counts);
    });
}

/// # Safety
/// `out` must denote a live writable 16-byte object aligned to 8; see StarRustNetScalar.h.
#[no_mangle]
pub unsafe extern "C" fn sb_net_scalar_run(
    mode: u32, word_bits: u32, value: u64, previous: u64, out: *mut SbNetScalarReply,
) -> u32 {
    if out.is_null() || (out as usize) % 8 != 0 || !valid(mode, word_bits, value, previous) {
        return INVALID;
    }
    barrier(|| {
        count_entry(mode as usize);
        let reply = scalar(mode, word_bits, value, previous);
        out.write(reply);
        OK
    })
}

/// Wrapping diagnostics only, not synchronized completion observations.
#[no_mangle]
pub extern "C" fn sb_net_scalar_count(kind: u32, mode: u32) -> u64 {
    catch_unwind(|| match (kind, mode as usize) {
        (0, i) if i < COUNT => COUNTS.with(|cell| cell.get()[i]),
        (1, i) if i < COUNT => TOTALS[i].load(Ordering::Relaxed),
        _ => 0,
    }).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run(mode: u32, bits: u32, value: u64, previous: u64) -> SbNetScalarReply {
        let mut out = SbNetScalarReply { value: 123, pulled: 456 };
        assert_eq!(unsafe { sb_net_scalar_run(mode, bits, value, previous, &mut out) }, OK);
        out
    }

    // Independent wide arithmetic and native u32 casts, not the kernel's wrapping/mask expressions.
    fn oracle(mode: u32, bits: u32, v: u64, p: u64) -> SbNetScalarReply {
        let modulus = 1u128 << 64;
        let max = if bits == 32 { u32::MAX as u64 } else { u64::MAX };
        let value = match mode {
            NEXT | VERSION_NEXT => ((v as u128 + 1) % modulus) as u64,
            COMPAT => u64::from(v == 0xffff_ffff || p.cmp(&v) != std::cmp::Ordering::Less),
            PULL => ((modulus + v as u128 - p as u128) % modulus) as u64,
            CLAMP => if v < p { v } else { p },
            SIZE_ENCODE => if v == max { 0 } else { (v as u128 + 1) as u64 },
            SIZE_DECODE => if v == 0 { max } else if bits == 32 { (v as u128 - 1) as u32 as u64 } else { (v as u128 - 1) as u64 },
            _ => unreachable!(),
        };
        SbNetScalarReply { value, pulled: if mode == PULL { v } else { 0 } }
    }

    #[test]
    fn cross_operations_100k() {
        let mut state = 0x1234_5678_9abc_def0u64;
        for i in 0..100_000 {
            state ^= state << 13; state ^= state >> 7; state ^= state << 17;
            let v = state;
            let p = state.rotate_left(29);
            for mode in 0..COUNT as u32 {
                for bits in [32, 64] {
                    let (b, x, y) = match mode {
                        NEXT | VERSION_NEXT => (0, v, 0),
                        COMPAT => (32, v as u32 as u64, p as u32 as u64),
                        PULL | CLAMP => (0, v, p),
                        SIZE_ENCODE => (bits, if bits == 32 { v as u32 as u64 } else { v }, 0),
                        SIZE_DECODE => (bits, v, 0),
                        _ => unreachable!("all modes need explicit argument domains"),
                    };
                    assert_eq!(run(mode, b, x, y), oracle(mode, b, x, y), "iteration {i}, mode {mode}, bits {b}");
                }
            }
        }
    }

    #[test]
    fn edge_widths_and_raw_pull_underflow() {
        let edges = [0, 1, 2, (1u64 << 31) - 1, 1u64 << 31, u32::MAX as u64 - 1,
            u32::MAX as u64, 1u64 << 32, (1u64 << 32) + 1, 1u64 << 63, u64::MAX - 1, u64::MAX];
        for v in edges {
            assert_eq!(run(NEXT, 0, v, 0), oracle(NEXT, 0, v, 0));
            for p in edges {
                for mode in [PULL, CLAMP] { assert_eq!(run(mode, 0, v, p), oracle(mode, 0, v, p)); }
            }
            for bits in [32, 64] {
                assert_eq!(run(SIZE_DECODE, bits, v, 0), oracle(SIZE_DECODE, bits, v, 0));
                if bits == 64 || v <= u32::MAX as u64 {
                    let wire = run(SIZE_ENCODE, bits, v, 0).value;
                    assert_eq!(wire, oracle(SIZE_ENCODE, bits, v, 0).value);
                    assert_eq!(run(SIZE_DECODE, bits, wire, 0).value, v);
                }
            }
        }
        assert_eq!(run(SIZE_DECODE, 32, u64::MAX, 0).value, u32::MAX as u64 - 1);
        assert_eq!(run(PULL, 0, 0, 1), SbNetScalarReply { value: u64::MAX, pulled: 0 });
        // Preserve the native trigger -> virtual updated clamp -> pull lost-wrap quirk.
        let current = run(NEXT, 0, u64::MAX, 0).value;
        let pulled = run(CLAMP, 0, current, u64::MAX).value;
        assert_eq!(run(PULL, 0, current, pulled).value, 0);
    }

    #[test]
    fn version_next_edges_wrap_and_full_word_100k() {
        let before = sb_net_scalar_count(0, VERSION_NEXT);
        let event_before = sb_net_scalar_count(0, NEXT);
        let edges = [0, 1, u32::MAX as u64, 1u64 << 32, 1u64 << 63, u64::MAX - 1, u64::MAX];
        for v in edges {
            assert_eq!(run(VERSION_NEXT, 0, v, 0), oracle(VERSION_NEXT, 0, v, 0));
        }
        assert_eq!(run(VERSION_NEXT, 0, u64::MAX, 0), SbNetScalarReply { value: 0, pulled: 0 });
        let mut state = 0xa076_1d64_78bd_642fu64;
        for _ in 0..100_000 {
            state ^= state << 13; state ^= state >> 7; state ^= state << 17;
            assert_eq!(run(VERSION_NEXT, 0, state, 0), oracle(VERSION_NEXT, 0, state, 0));
        }
        assert_eq!(sb_net_scalar_count(0, VERSION_NEXT).wrapping_sub(before), 100_008);
        assert_eq!(sb_net_scalar_count(0, NEXT), event_before);
    }

    #[test]
    fn compatibility_word_edges_and_100k() {
        let before = sb_net_scalar_count(0, COMPAT);
        let max = u32::MAX as u64;
        let edges = [0, 1, 2, (1u64 << 31) - 1, 1u64 << 31, max - 1, max];
        for v in edges {
            for p in edges {
                assert_eq!(run(COMPAT, 32, v, p), oracle(COMPAT, 32, v, p));
            }
        }
        // Equality and Any must remain true; an inverted inequality must fail.
        assert_eq!(run(COMPAT, 32, 7, 7), SbNetScalarReply { value: 1, pulled: 0 });
        assert_eq!(run(COMPAT, 32, 7, 6).value, 0);
        assert_eq!(run(COMPAT, 32, 7, 8).value, 1);
        assert_eq!(run(COMPAT, 32, max, 0).value, 1);
        let mut state = 0xe703_7ed1_a0b4_28dbu64;
        for _ in 0..100_000 {
            state ^= state << 13; state ^= state >> 7; state ^= state << 17;
            let v = state as u32 as u64;
            let p = (state >> 32) as u32 as u64;
            assert_eq!(run(COMPAT, 32, v, p), oracle(COMPAT, 32, v, p));
        }
        assert_eq!(sb_net_scalar_count(0, COMPAT).wrapping_sub(before), 100_053);
    }

    #[test]
    fn version_rejections_preserve_output_and_all_counts() {
        let before = std::array::from_fn::<_, COUNT, _>(|i| sb_net_scalar_count(0, i as u32));
        let marker = SbNetScalarReply { value: 0xdead, pulled: 0xbeef };
        let mut out = marker;
        let max = u32::MAX as u64;
        let bad = [
            (VERSION_NEXT, 0, 0, 1), (VERSION_NEXT, 0, u64::MAX, u64::MAX),
            (VERSION_NEXT, 1, 0, 0), (VERSION_NEXT, 32, 0, 0),
            (VERSION_NEXT, 64, 0, 0), (VERSION_NEXT, u32::MAX, 0, 0),
            (COMPAT, 0, 0, 0), (COMPAT, 1, 0, 0), (COMPAT, 31, 0, 0),
            (COMPAT, 33, 0, 0), (COMPAT, 64, 0, 0), (COMPAT, u32::MAX, 0, 0),
            (COMPAT, 32, max + 1, 0), (COMPAT, 32, 0, max + 1),
            (COMPAT, 32, u64::MAX, 0), (COMPAT, 32, 0, u64::MAX),
            (COMPAT, 32, max, u64::MAX), (COMPAT, 32, u64::MAX, max),
            (COUNT as u32, 32, 0, 0), (u32::MAX, 0, 0, 0),
        ];
        for (m, b, v, p) in bad {
            assert_eq!(unsafe { sb_net_scalar_run(m, b, v, p, &mut out) }, INVALID);
            assert_eq!(out, marker);
        }
        let mut storage = [0xabu64; 4];
        let misaligned = unsafe { storage.as_mut_ptr().cast::<u8>().add(1).cast::<SbNetScalarReply>() };
        for (m, b) in [(VERSION_NEXT, 0), (COMPAT, 32)] {
            assert_eq!(unsafe { sb_net_scalar_run(m, b, 0, 0, std::ptr::null_mut()) }, INVALID);
            assert_eq!(unsafe { sb_net_scalar_run(m, b, 0, 0, misaligned) }, INVALID);
        }
        assert_eq!(storage, [0xabu64; 4]);
        for i in 0..COUNT { assert_eq!(sb_net_scalar_count(0, i as u32), before[i]); }
        for kind in [0, 1] {
            for mode in [COUNT as u32, COUNT as u32 + 1, u32::MAX] {
                assert_eq!(sb_net_scalar_count(kind, mode), 0);
            }
        }
    }

    #[test]
    fn strict_rejections_preserve_output_and_counts() {
        let before = std::array::from_fn::<_, COUNT, _>(|i| sb_net_scalar_count(0, i as u32));
        let marker = SbNetScalarReply { value: 0xdead, pulled: 0xbeef };
        let mut out = marker;
        let bad = [(COUNT as u32, 0, 0, 0), (u32::MAX, 0, 0, 0), (NEXT, 0, 0, 1),
            (NEXT, 32, 0, 0), (PULL, 64, 0, 0), (CLAMP, 1, 0, 0),
            (SIZE_ENCODE, 32, 1u64 << 32, 0), (SIZE_ENCODE, 0, 0, 0),
            (SIZE_ENCODE, 64, 0, 1), (SIZE_DECODE, 64, 0, 1), (SIZE_DECODE, 33, 0, 0)];
        for (m, b, v, p) in bad {
            assert_eq!(unsafe { sb_net_scalar_run(m, b, v, p, &mut out) }, INVALID);
            assert_eq!(out, marker);
        }
        assert_eq!(unsafe { sb_net_scalar_run(NEXT, 0, 0, 0, std::ptr::null_mut()) }, INVALID);
        let mut storage = [0xabu64; 4];
        let misaligned = unsafe { storage.as_mut_ptr().cast::<u8>().add(1).cast::<SbNetScalarReply>() };
        assert_eq!(unsafe { sb_net_scalar_run(NEXT, 0, 0, 0, misaligned) }, INVALID);
        assert_eq!(storage, [0xabu64; 4]);
        for i in 0..COUNT { assert_eq!(sb_net_scalar_count(0, i as u32), before[i]); }
        for (k, m) in [(2, 0), (u32::MAX, 0), (0, COUNT as u32), (1, u32::MAX)] {
            assert_eq!(sb_net_scalar_count(k, m), 0);
        }
    }

    #[test]
    fn tls_isolation_and_global_visibility() {
        let local = std::array::from_fn::<_, COUNT, _>(|i| sb_net_scalar_count(0, i as u32));
        let global = std::array::from_fn::<_, COUNT, _>(|i| sb_net_scalar_count(1, i as u32));
        std::thread::spawn(|| {
            for m in 0..COUNT as u32 {
                assert_eq!(sb_net_scalar_count(0, m), 0);
                let bits = match m {
                    NEXT | PULL | CLAMP | VERSION_NEXT => 0,
                    SIZE_ENCODE | SIZE_DECODE => 64,
                    COMPAT => 32,
                    _ => unreachable!("all modes need explicit argument domains"),
                };
                run(m, bits, 7, 0);
                assert_eq!(sb_net_scalar_count(0, m), 1);
            }
        }).join().unwrap();
        for i in 0..COUNT {
            assert_eq!(sb_net_scalar_count(0, i as u32), local[i]);
            // Other tests may concurrently add accepted entries; do not require an exact global delta.
            assert!(sb_net_scalar_count(1, i as u32).wrapping_sub(global[i]) >= 1);
        }
    }

    #[test]
    fn diagnostic_wrapping_without_resetting_shared_totals() {
        COUNTS.with(|cell| {
            let saved = cell.get();
            cell.set([u64::MAX; COUNT]);
            for mode in 0..COUNT { count_entry(mode); assert_eq!(sb_net_scalar_count(0, mode as u32), 0); }
            cell.set(saved);
        });
        // Exercise the same relaxed atomic operation in isolation, never reset a live global.
        let atomic = AtomicU64::new(u64::MAX);
        assert_eq!(atomic.fetch_add(1, Ordering::Relaxed), u64::MAX);
        assert_eq!(atomic.load(Ordering::Relaxed), 0);
    }

    #[test]
    fn panic_is_contained_by_plain_rust_seam() {
        fn fail() -> SbNetScalarReply { panic!("internal scalar seam") }
        let mut out = SbNetScalarReply { value: 7, pulled: 9 };
        let before = out;
        let count = sb_net_scalar_count(0, NEXT);
        assert_eq!(barrier(|| {
            count_entry(NEXT as usize);
            let reply = fail();
            out = reply;
            OK
        }), PANIC);
        assert_eq!(out, before);
        assert_eq!(sb_net_scalar_count(0, NEXT), count.wrapping_add(1));
        assert_eq!(std::mem::size_of::<SbNetScalarReply>(), 16);
        assert_eq!(std::mem::align_of::<SbNetScalarReply>(), 8);
    }
}
