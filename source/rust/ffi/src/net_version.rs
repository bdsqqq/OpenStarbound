//! Rust-defined, in-place version POD hosted by foreign opaque bytes.
//! ZERO bytes and every initialized u64 representation are valid; no heap,
//! destructor, escaped references, or synchronization of state is introduced.
use std::cell::Cell;
use std::ffi::c_void;
use std::mem::align_of;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const PANIC: u32 = 3;
const INIT: u32 = 0;
const CURRENT: u32 = 1;
const ADVANCE: u32 = 2;
const COUNT: usize = 3;

#[repr(C)]
#[derive(Copy, Clone)]
struct VersionState { value: u64 }

static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
thread_local! {
    static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) };
}

fn count_entry(mode: usize) {
    TOTALS[mode].fetch_add(1, Ordering::Relaxed);
    COUNTS.with(|cell| {
        let mut counts = cell.get();
        counts[mode] = counts[mode].wrapping_add(1);
        cell.set(counts);
    });
}

fn barrier(f: impl FnOnce() -> u32) -> u32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(PANIC)
}

// Called only after address/mode validation. The injected computation is a
// private panic-test seam, not an FFI callback. All fallible work precedes
// state/output commits; raw copies avoid references aliasing an exact-word out.
unsafe fn accepted(
    mode: u32, storage: *const c_void, out: *mut u64,
    next: impl FnOnce(u64) -> u64,
) -> u32 {
    barrier(|| {
        count_entry(mode as usize);
        let value = if mode == INIT { 0 } else {
            storage.cast::<VersionState>().read().value
        };
        let result = if mode == ADVANCE { next(value) } else { value };
        if mode != CURRENT {
            storage.cast_mut().cast::<VersionState>().write(VersionState { value: result });
        }
        out.write(result);
        OK
    })
}

/// # Safety
/// Both pointers denote live eight-byte objects aligned to native u64.
/// INIT needs writable storage; CURRENT/ADVANCE need initialized POD bytes;
/// ADVANCE also needs writable storage. out is writable and either disjoint
/// or exactly the same word as writable storage. Read-only CURRENT storage
/// requires distinct out. See StarRustNetVersion.h for the ZERO/copy contract.
#[no_mangle]
pub unsafe extern "C" fn sb_net_version_run(
    mode: u32, storage: *const c_void, out: *mut u64,
) -> u32 {
    if mode >= COUNT as u32 || storage.is_null() || out.is_null()
        || (storage as usize) % align_of::<u64>() != 0
        || (out as usize) % align_of::<u64>() != 0
    {
        return INVALID;
    }
    accepted(mode, storage, out, crate::net_scalar::counted_version_next)
}

/// Wrapping accepted-entry diagnostics, not synchronized completion counts.
#[no_mangle]
pub extern "C" fn sb_net_version_count(kind: u32, mode: u32) -> u64 {
    catch_unwind(|| match (kind, mode as usize) {
        (0, i) if i < COUNT => COUNTS.with(|cell| cell.get()[i]),
        (1, i) if i < COUNT => TOTALS[i].load(Ordering::Relaxed),
        _ => 0,
    }).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::mem::{needs_drop, size_of, MaybeUninit};
    use std::ptr;

    fn run(mode: u32, state: *const c_void) -> u64 {
        let mut out = 0xdead_beef;
        assert_eq!(unsafe { sb_net_version_run(mode, state, &mut out) }, OK);
        out
    }
    fn address(state: &VersionState) -> *const c_void {
        (state as *const VersionState).cast()
    }
    fn snapshot() -> [u64; COUNT] {
        std::array::from_fn(|i| sb_net_version_count(0, i as u32))
    }
    fn oracle(value: u64) -> u64 { ((value as u128 + 1) % (1u128 << 64)) as u64 }

    #[test]
    fn pod_zero_and_foreign_raw_init() {
        assert_eq!(size_of::<VersionState>(), 8);
        assert_eq!(align_of::<VersionState>(), align_of::<u64>());
        assert!(!needs_drop::<VersionState>());
        let zero = [0u64; 1];
        assert_eq!(run(CURRENT, zero.as_ptr().cast()), 0);
        let mut raw = MaybeUninit::<VersionState>::uninit();
        assert_eq!(run(INIT, raw.as_mut_ptr().cast()), 0);
        let state = unsafe { raw.assume_init() };
        assert_eq!(state.value, 0);
        assert_eq!(run(CURRENT, address(&state)), 0);
        let before = snapshot();
        let scalar = crate::net_scalar::sb_net_scalar_count(0, 5);
        assert_eq!(run(INIT, raw.as_mut_ptr().cast()), 0);
        assert_eq!(run(CURRENT, raw.as_ptr().cast()), 0);
        assert_eq!(sb_net_version_count(0, INIT), before[INIT as usize].wrapping_add(1));
        assert_eq!(sb_net_version_count(0, CURRENT), before[CURRENT as usize].wrapping_add(1));
        assert_eq!(sb_net_version_count(0, ADVANCE), before[ADVANCE as usize]);
        assert_eq!(crate::net_scalar::sb_net_scalar_count(0, 5), scalar);
    }

    #[test]
    fn edges_and_100k_full_word_in_place() {
        let before = snapshot();
        let scalar_before = crate::net_scalar::sb_net_scalar_count(0, 5);
        let event_before = crate::net_scalar::sb_net_scalar_count(0, 0);
        let edges = [0, 1, 2, (1u64 << 31) - 1, 1u64 << 31,
            u32::MAX as u64 - 1, u32::MAX as u64, 1u64 << 32,
            (1u64 << 32) + 1, (1u64 << 63) - 1, 1u64 << 63,
            u64::MAX - 1, u64::MAX];
        let mut seed = 0xa076_1d64_78bd_642fu64;
        for i in 0..100_000 + edges.len() {
            seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17;
            let value = if i < edges.len() { edges[i] } else { seed };
            let mut state = VersionState { value };
            let p = (&mut state as *mut VersionState).cast();
            assert_eq!(run(CURRENT, p), value);
            assert_eq!(run(ADVANCE, p), oracle(value));
            assert_eq!(state.value, oracle(value));
            assert_eq!(run(CURRENT, p), oracle(value));
        }
        let calls = 100_000 + edges.len() as u64;
        assert_eq!(sb_net_version_count(0, ADVANCE).wrapping_sub(before[ADVANCE as usize]), calls);
        assert_eq!(sb_net_version_count(0, CURRENT).wrapping_sub(before[CURRENT as usize]), 2 * calls);
        assert_eq!(sb_net_version_count(0, INIT), before[INIT as usize]);
        assert_eq!(crate::net_scalar::sb_net_scalar_count(0, 5).wrapping_sub(scalar_before), calls);
        assert_eq!(crate::net_scalar::sb_net_scalar_count(0, 0), event_before);
    }

    #[test]
    fn byte_copies_moves_and_exact_word_alias() {
        let original = VersionState { value: u64::MAX };
        let mut copy = MaybeUninit::<VersionState>::uninit();
        unsafe {
            ptr::copy_nonoverlapping(address(&original).cast::<u8>(), copy.as_mut_ptr().cast::<u8>(), 8);
        }
        let mut copy = unsafe { copy.assume_init() };
        let p = &mut copy as *mut VersionState;
        assert_eq!(unsafe { sb_net_version_run(ADVANCE, p.cast(), p.cast()) }, OK);
        assert_eq!(copy.value, 0);
        assert_eq!(original.value, u64::MAX);
        copy.value = 71;
        let p = &mut copy as *mut VersionState;
        assert_eq!(unsafe { sb_net_version_run(CURRENT, p.cast(), p.cast()) }, OK);
        assert_eq!(copy.value, 71);
        assert_eq!(unsafe { sb_net_version_run(INIT, p.cast(), p.cast()) }, OK);
        assert_eq!(copy.value, 0);
        let moved = copy;
        assert_eq!(run(CURRENT, address(&moved)), 0);
        let mut assigned = original;
        assert_eq!(run(CURRENT, address(&assigned)), u64::MAX);
        assigned = moved;
        assert_eq!(run(CURRENT, address(&assigned)), 0);
    }

    #[test]
    fn current_reads_immutable_state_without_mutating_canaries() {
        #[repr(C)]
        struct Guarded { before: u64, state: VersionState, after: u64 }
        let immutable = Guarded { before: 0x0123_4567_89ab_cdef,
            state: VersionState { value: 0xfedc_ba98_7654_3210 }, after: 0xa5a5_5a5a_a5a5_5a5a };
        // This storage is genuinely shared/read-only to Rust, not a mutable
        // pointer relabeled const; any storage write violates this contract.
        let before = unsafe { ptr::read((&immutable as *const Guarded).cast::<[u8; 24]>()) };
        assert_eq!(run(CURRENT, address(&immutable.state)), immutable.state.value);
        let after = unsafe { ptr::read((&immutable as *const Guarded).cast::<[u8; 24]>()) };
        assert_eq!(after, before);
    }

    #[test]
    fn invalid_addresses_and_modes_do_not_touch_bytes_or_counts() {
        let before = snapshot();
        let scalar = crate::net_scalar::sb_net_scalar_count(0, 5);
        let mut backing = [0xabcd_0123_4567_89efu64; 4];
        let original = backing;
        let p = backing.as_mut_ptr();
        let bad = unsafe { p.cast::<u8>().add(1) };
        let mut out = 0xdead_beef;
        for mode in 0..COUNT as u32 {
            for storage in [ptr::null(), bad.cast::<c_void>()] {
                assert_eq!(unsafe { sb_net_version_run(mode, storage, &mut out) }, INVALID);
            }
            for output in [ptr::null_mut(), bad.cast::<u64>()] {
                assert_eq!(unsafe { sb_net_version_run(mode, p.cast(), output) }, INVALID);
            }
        }
        for mode in [COUNT as u32, u32::MAX] {
            assert_eq!(unsafe { sb_net_version_run(mode, p.cast(), &mut out) }, INVALID);
        }
        assert_eq!(out, 0xdead_beef);
        assert_eq!(backing, original);
        assert_eq!(snapshot(), before);
        assert_eq!(crate::net_scalar::sb_net_scalar_count(0, 5), scalar);
        for kind in [0, 1] {
            for mode in [COUNT as u32, u32::MAX] { assert_eq!(sb_net_version_count(kind, mode), 0); }
        }
        for kind in [2, u32::MAX] {
            for mode in 0..COUNT as u32 { assert_eq!(sb_net_version_count(kind, mode), 0); }
        }
    }

    #[test]
    fn panic_before_commit_preserves_state_and_output() {
        let mut state = VersionState { value: 79 };
        let p = (&mut state as *mut VersionState).cast();
        let mut out = 113;
        let before = sb_net_version_count(0, ADVANCE);
        assert_eq!(unsafe { accepted(ADVANCE, p, &mut out, |_| panic!("version seam")) }, PANIC);
        assert_eq!(state.value, 79);
        assert_eq!(out, 113);
        assert_eq!(sb_net_version_count(0, ADVANCE), before.wrapping_add(1));
        let p = &mut state as *mut VersionState;
        assert_eq!(unsafe { accepted(ADVANCE, p.cast(), p.cast(), |_| panic!("alias seam")) }, PANIC);
        assert_eq!(state.value, 79);
    }

    #[test]
    fn tls_isolation_and_global_visibility() {
        let local = snapshot();
        let global: [u64; COUNT] = std::array::from_fn(|i| sb_net_version_count(1, i as u32));
        std::thread::spawn(|| {
            let mut state = VersionState { value: 19 };
            let p = (&mut state as *mut VersionState).cast();
            for mode in 0..COUNT as u32 {
                assert_eq!(sb_net_version_count(0, mode), 0);
                run(mode, p);
                assert_eq!(sb_net_version_count(0, mode), 1);
            }
        }).join().unwrap();
        assert_eq!(snapshot(), local);
        for i in 0..COUNT {
            assert!(sb_net_version_count(1, i as u32).wrapping_sub(global[i]) >= 1);
        }
    }

    #[test]
    fn counters_wrap_without_resetting_shared_globals() {
        COUNTS.with(|cell| {
            let saved = cell.get();
            cell.set([u64::MAX; COUNT]);
            for mode in 0..COUNT {
                count_entry(mode);
                assert_eq!(sb_net_version_count(0, mode as u32), 0);
            }
            cell.set(saved);
        });
        let isolated = AtomicU64::new(u64::MAX);
        assert_eq!(isolated.fetch_add(1, Ordering::Relaxed), u64::MAX);
        assert_eq!(isolated.load(Ordering::Relaxed), 0);
    }
}
