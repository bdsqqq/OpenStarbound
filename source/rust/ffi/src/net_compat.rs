//! In-place compatibility POD hosted by opaque foreign bytes. ALL-FF means
//! AnyVersion; zero bytes mean version zero, not default AnyVersion.
use std::cell::Cell;
use std::ffi::c_void;
use std::mem::align_of;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const PANIC: u32 = 3;
const INIT_ANY: u32 = 0;
const VALUE: u32 = 1;
const SET: u32 = 2;
const CHECK: u32 = 3;
const COUNT: usize = 4;

#[repr(C)]
#[derive(Copy, Clone)]
struct CompatState { value: u32 }

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

// Validated addresses only. The private computation seam allows a panic before
// commit to be exercised without introducing a foreign callback. Raw copies
// deliberately create no references that could conflict with exact-word alias.
unsafe fn accepted(
    mode: u32, storage: *const c_void, argument: u32, out: *mut u32,
    check: impl FnOnce(u32, u32) -> u32,
) -> u32 {
    catch_unwind(AssertUnwindSafe(|| {
        count_entry(mode as usize);
        let value = match mode {
            INIT_ANY => u32::MAX,
            SET => argument,
            _ => storage.cast::<CompatState>().read().value,
        };
        let result = if mode == CHECK { check(value, argument) } else { value };
        if mode == INIT_ANY || mode == SET {
            storage.cast_mut().cast::<CompatState>().write(CompatState { value });
        }
        out.write(result);
        OK
    })).unwrap_or(PANIC)
}

/// # Safety
/// Pointers denote live four-byte objects with native u32 alignment. INIT_ANY
/// and SET require writable storage but not initialized bytes; VALUE and CHECK
/// require initialized state. out is writable and disjoint, except an exact
/// storage alias is allowed for INIT_ANY/VALUE/SET when storage is writable.
/// No permission, initialization, liveness or provenance check is possible here.
/// See StarRustNetCompat.h for the ALL-FF/default and foreign byte-copy contract.
#[no_mangle]
pub unsafe extern "C" fn sb_net_compat_run(
    mode: u32, storage: *const c_void, argument: u32, out: *mut u32,
) -> u32 {
    let s = storage as usize;
    let o = out as usize;
    if mode >= COUNT as u32 || ((mode == INIT_ANY || mode == VALUE) && argument != 0)
        || storage.is_null() || out.is_null()
        || s % align_of::<u32>() != 0 || o % align_of::<u32>() != 0
        || (s != o && s.abs_diff(o) < 4) || (mode == CHECK && s == o)
    {
        return INVALID;
    }
    accepted(mode, storage, argument, out, crate::net_scalar::counted_compat)
}

/// Wrapping accepted-entry counters, not synchronized completion snapshots.
#[no_mangle]
pub extern "C" fn sb_net_compat_count(kind: u32, mode: u32) -> u64 {
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

    fn run(mode: u32, storage: *const c_void, argument: u32) -> u32 {
        let mut out = 0xdead_beef;
        assert_eq!(unsafe { sb_net_compat_run(mode, storage, argument, &mut out) }, OK);
        out
    }
    fn snapshot() -> [u64; COUNT] {
        std::array::from_fn(|i| sb_net_compat_count(0, i as u32))
    }
    fn scalar_snapshot() -> [u64; 7] {
        std::array::from_fn(|i| crate::net_scalar::sb_net_scalar_count(0, i as u32))
    }
    fn address(state: &CompatState) -> *const c_void {
        (state as *const CompatState).cast()
    }
    fn oracle(value: u32, rules: u32) -> u32 {
        u32::from(value == 0xffff_ffff || rules.cmp(&value) != std::cmp::Ordering::Less)
    }

    #[test]
    fn pod_defaults_and_foreign_uninitialized_init_set() {
        assert_eq!(size_of::<CompatState>(), 4);
        assert_eq!(align_of::<CompatState>(), align_of::<u32>());
        assert!(!needs_drop::<CompatState>());
        #[repr(C, align(4))]
        struct Bytes([u8; 4]);
        let any = Bytes([0xff; 4]);
        let zero = Bytes([0; 4]);
        assert_eq!(run(VALUE, (&any as *const Bytes).cast(), 0), u32::MAX);
        assert_eq!(run(VALUE, (&zero as *const Bytes).cast(), 0), 0);
        let scalar = scalar_snapshot();
        let mut raw = MaybeUninit::<CompatState>::uninit();
        assert_eq!(run(INIT_ANY, raw.as_mut_ptr().cast(), 0), u32::MAX);
        assert_eq!(unsafe { raw.assume_init() }.value, u32::MAX);
        let mut raw = MaybeUninit::<CompatState>::uninit();
        assert_eq!(run(SET, raw.as_mut_ptr().cast(), 0x8123_4567), 0x8123_4567);
        assert_eq!(unsafe { raw.assume_init() }.value, 0x8123_4567);
        assert_eq!(scalar_snapshot(), scalar);
    }

    #[test]
    fn finite_edges_and_full_word_100k_oracle() {
        let before = snapshot();
        let scalar = scalar_snapshot();
        let edges = [0, 1, 2, (1u32 << 31) - 1, 1u32 << 31, u32::MAX - 1, u32::MAX];
        let mut calls = 0u64;
        let mut exercise = |value, rules| {
            let mut state = CompatState { value: 17 };
            let p = (&mut state as *mut CompatState).cast();
            assert_eq!(run(SET, p, value), value);
            assert_eq!(state.value, value);
            assert_eq!(run(VALUE, p, 0), value);
            assert_eq!(run(CHECK, p, rules), oracle(value, rules));
            assert_eq!(state.value, value);
            calls += 1;
        };
        for value in edges { for rules in edges { exercise(value, rules); } }
        let mut seed = 0xe703_7ed1_a0b4_28dbu64;
        for _ in 0..100_000 {
            seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17;
            exercise(seed as u32, (seed >> 32) as u32);
        }
        for mode in 0..COUNT {
            assert_eq!(sb_net_compat_count(0, mode as u32).wrapping_sub(before[mode]),
                if mode == INIT_ANY as usize { 0 } else { calls });
        }
        for mode in 0..7 {
            assert_eq!(crate::net_scalar::sb_net_scalar_count(0, mode as u32).wrapping_sub(scalar[mode]),
                if mode == 6 { calls } else { 0 });
        }
    }

    #[test]
    fn byte_copy_move_and_allowed_exact_aliases() {
        let original = CompatState { value: 0x8123_4567 };
        let mut copied = MaybeUninit::<CompatState>::uninit();
        unsafe { ptr::copy_nonoverlapping(address(&original).cast::<u8>(), copied.as_mut_ptr().cast::<u8>(), 4); }
        let mut copied = unsafe { copied.assume_init() };
        let p = &mut copied as *mut CompatState;
        assert_eq!(unsafe { sb_net_compat_run(VALUE, p.cast(), 0, p.cast()) }, OK);
        assert_eq!(copied.value, original.value);
        assert_eq!(unsafe { sb_net_compat_run(SET, p.cast(), 99, p.cast()) }, OK);
        assert_eq!(copied.value, 99);
        assert_eq!(unsafe { sb_net_compat_run(INIT_ANY, p.cast(), 0, p.cast()) }, OK);
        assert_eq!(copied.value, u32::MAX);
        let moved = copied;
        assert_eq!(run(VALUE, address(&moved), 0), u32::MAX);
        assert_eq!(original.value, 0x8123_4567);
        let mut raw = MaybeUninit::<CompatState>::uninit();
        let p = raw.as_mut_ptr();
        assert_eq!(unsafe { sb_net_compat_run(SET, p.cast(), 0, p.cast()) }, OK);
        assert_eq!(unsafe { raw.assume_init() }.value, 0);
    }

    #[test]
    fn readonly_value_check_canaries_and_raw_any_counts() {
        #[repr(C)]
        struct Guarded { before: u32, state: CompatState, after: u32 }
        for value in [0, 7, u32::MAX] {
            let immutable = Guarded { before: 0x1234_5678, state: CompatState { value }, after: 0x8765_4321 };
            let before = unsafe { ptr::read((&immutable as *const Guarded).cast::<[u8; 12]>()) };
            let counts = snapshot();
            let scalar = scalar_snapshot();
            assert_eq!(run(VALUE, address(&immutable.state), 0), value);
            for rules in [0, 6, 7, 8, u32::MAX] {
                assert_eq!(run(CHECK, address(&immutable.state), rules), oracle(value, rules));
            }
            assert_eq!(unsafe { ptr::read((&immutable as *const Guarded).cast::<[u8; 12]>()) }, before);
            assert_eq!(sb_net_compat_count(0, CHECK).wrapping_sub(counts[CHECK as usize]), 5);
            assert_eq!(crate::net_scalar::sb_net_scalar_count(0, 6).wrapping_sub(scalar[6]), 5);
        }
    }

    #[test]
    fn strict_invalids_preserve_all_bytes_and_counts() {
        let before = snapshot();
        let scalar = scalar_snapshot();
        let mut backing = [0xabcd_0123u32; 4];
        let saved = backing;
        let p = backing.as_mut_ptr();
        let mut out = 0xdead_beef;
        for mode in 0..COUNT as u32 {
            for storage in [ptr::null(), unsafe { p.cast::<u8>().add(1).cast::<c_void>() }] {
                assert_eq!(unsafe { sb_net_compat_run(mode, storage, 0, &mut out) }, INVALID);
            }
            for output in [ptr::null_mut(), unsafe { p.cast::<u8>().add(1).cast::<u32>() }] {
                assert_eq!(unsafe { sb_net_compat_run(mode, p.cast(), 0, output) }, INVALID);
            }
            for offset in 1..4 {
                let partial = unsafe { p.cast::<u8>().add(offset).cast::<u32>() };
                assert_eq!(unsafe { sb_net_compat_run(mode, p.cast(), 0, partial) }, INVALID);
                assert_eq!(unsafe { sb_net_compat_run(mode, partial.cast(), 0, p) }, INVALID);
            }
        }
        for mode in [COUNT as u32, u32::MAX] {
            assert_eq!(unsafe { sb_net_compat_run(mode, p.cast(), 0, &mut out) }, INVALID);
        }
        for mode in [INIT_ANY, VALUE] {
            for argument in [1, u32::MAX] {
                assert_eq!(unsafe { sb_net_compat_run(mode, p.cast(), argument, &mut out) }, INVALID);
            }
        }
        for argument in [0, 7, u32::MAX] {
            assert_eq!(unsafe { sb_net_compat_run(CHECK, p.cast(), argument, p) }, INVALID);
        }
        assert_eq!(out, 0xdead_beef);
        assert_eq!(backing, saved);
        assert_eq!(snapshot(), before);
        assert_eq!(scalar_snapshot(), scalar);
        for kind in [0, 1] {
            for mode in [COUNT as u32, u32::MAX] { assert_eq!(sb_net_compat_count(kind, mode), 0); }
        }
        for kind in [2, u32::MAX] {
            for mode in 0..COUNT as u32 { assert_eq!(sb_net_compat_count(kind, mode), 0); }
        }
    }

    #[test]
    fn panic_before_commit_preserves_state_and_output() {
        let mut state = CompatState { value: 79 };
        let p = (&mut state as *mut CompatState).cast();
        let mut out = 113;
        let before = snapshot();
        let scalar = scalar_snapshot();
        assert_eq!(unsafe { accepted(CHECK, p, 7, &mut out, |_, _| panic!("compat seam")) }, PANIC);
        assert_eq!(state.value, 79);
        assert_eq!(out, 113);
        assert_eq!(sb_net_compat_count(0, CHECK), before[CHECK as usize].wrapping_add(1));
        assert_eq!(scalar_snapshot(), scalar);
    }

    #[test]
    fn tls_isolation_and_global_visibility() {
        let local = snapshot();
        let global: [u64; COUNT] = std::array::from_fn(|i| sb_net_compat_count(1, i as u32));
        std::thread::spawn(|| {
            let mut raw = MaybeUninit::<CompatState>::uninit();
            let p = raw.as_mut_ptr().cast();
            for mode in 0..COUNT as u32 {
                assert_eq!(sb_net_compat_count(0, mode), 0);
                run(mode, p, 0);
                assert_eq!(sb_net_compat_count(0, mode), 1);
            }
        }).join().unwrap();
        assert_eq!(snapshot(), local);
        for i in 0..COUNT {
            assert!(sb_net_compat_count(1, i as u32).wrapping_sub(global[i]) >= 1);
        }
    }

    #[test]
    fn counters_wrap_without_resetting_shared_globals() {
        COUNTS.with(|cell| {
            let saved = cell.get();
            cell.set([u64::MAX; COUNT]);
            for mode in 0..COUNT {
                count_entry(mode);
                assert_eq!(sb_net_compat_count(0, mode as u32), 0);
            }
            cell.set(saved);
        });
        let isolated = AtomicU64::new(u64::MAX);
        assert_eq!(isolated.fetch_add(1, Ordering::Relaxed), u64::MAX);
        assert_eq!(isolated.load(Ordering::Relaxed), 0);
    }
}
