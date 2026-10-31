//! Logical compatibility rules in foreign opaque storage, with field-specific
//! initialization requirements. No native bool/padding representation assumption.
use std::cell::Cell;
use std::ffi::c_void;
use std::mem::align_of;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::ptr::{addr_of, addr_of_mut};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const PANIC: u32 = 3;
const INIT: u32 = 0;
const VERSION: u32 = 1;
const SET_VERSION: u32 = 2;
const ADMIN: u32 = 3;
const SET_ADMIN: u32 = 4;
const LEGACY: u32 = 5;
const EQUAL_VERSION: u32 = 6;
const COUNT: usize = 7;

#[repr(C)]
#[derive(Copy, Clone)]
struct RulesState {
    version: u32,
    admin: u8,
    reserved: [u8; 3],
}

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

// Pointer/argument checks precede any access; only ADMIN inspects its canonical
// byte before counting. No whole-state read: reserved bytes may be uninitialized.
// The private seam cannot call foreign code and runs before either commit.
unsafe fn checked(
    mode: u32, storage: *const c_void, argument: u32, out: *mut u32,
    before_commit: impl FnOnce(),
) -> u32 {
    let s = storage as usize;
    let o = out as usize;
    if mode >= COUNT as u32
        || (matches!(mode, VERSION | ADMIN | LEGACY) && argument != 0)
        || (mode == SET_ADMIN && argument > 1)
        || storage.is_null() || out.is_null()
        || s % align_of::<u32>() != 0 || o % align_of::<u32>() != 0
        || (if s <= o { o - s < 8 } else { s - o < 4 })
    {
        return INVALID;
    }
    let state = storage.cast::<RulesState>();
    // u8 accepts all representations; rejecting >1 is a raw ABI domain check,
    // not execution of a forged native C++ bool.
    let admin = if mode == ADMIN {
        let byte = addr_of!((*state).admin).read();
        if byte > 1 { return INVALID; }
        u32::from(byte)
    } else { 0 };
    catch_unwind(AssertUnwindSafe(|| {
        count_entry(mode as usize);
        let result = match mode {
            INIT | SET_VERSION | SET_ADMIN => argument,
            ADMIN => admin,
            VERSION => addr_of!((*state).version).read(),
            LEGACY => u32::from(addr_of!((*state).version).read() == 0),
            EQUAL_VERSION => u32::from(addr_of!((*state).version).read() == argument),
            _ => unreachable!(),
        };
        before_commit();
        let writable = state.cast_mut();
        match mode {
            INIT => writable.write(RulesState { version: argument, admin: 0, reserved: [0; 3] }),
            SET_VERSION => addr_of_mut!((*writable).version).write(argument),
            SET_ADMIN => addr_of_mut!((*writable).admin).write(argument as u8),
            _ => {},
        }
        out.write(result);
        OK
    })).unwrap_or(PANIC)
}

/// # Safety
/// Eight live storage bytes and four writable output bytes, both aligned like
/// native u32 and disjoint. Only fields read by the selected operation need be
/// initialized; mutations require writable affected bytes. Address validation
/// cannot establish provenance, liveness, permissions or initialization. See
/// StarRustNetRules.h for the canonical admin and field-specific ABI contracts.
#[no_mangle]
pub unsafe extern "C" fn sb_net_rules_run(
    mode: u32, storage: *const c_void, argument: u32, out: *mut u32,
) -> u32 {
    checked(mode, storage, argument, out, || {})
}

/// Wrapping accepted-entry diagnostics, not synchronized completion snapshots.
#[no_mangle]
pub extern "C" fn sb_net_rules_count(kind: u32, mode: u32) -> u64 {
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

    fn run(mode: u32, p: *const c_void, argument: u32) -> u32 {
        let mut out = 0xdead_beef;
        assert_eq!(unsafe { sb_net_rules_run(mode, p, argument, &mut out) }, OK);
        out
    }
    fn snapshot() -> [u64; COUNT] {
        std::array::from_fn(|i| sb_net_rules_count(0, i as u32))
    }
    fn address(state: &RulesState) -> *const c_void {
        (state as *const RulesState).cast()
    }
    fn bytes(state: &RulesState) -> [u8; 8] {
        // Only called for fully initialized fixtures, never partial states.
        unsafe { ptr::read((state as *const RulesState).cast::<[u8; 8]>()) }
    }

    #[test]
    fn layout_and_init_uses_supplied_default_or_explicit_version() {
        assert_eq!(size_of::<RulesState>(), 8);
        assert_eq!(align_of::<RulesState>(), align_of::<u32>());
        assert!(!needs_drop::<RulesState>());
        let raw = MaybeUninit::<RulesState>::uninit();
        let p = raw.as_ptr();
        assert_eq!(unsafe { addr_of!((*p).admin) as usize - p as usize }, 4);
        assert_eq!(unsafe { addr_of!((*p).reserved) as usize - p as usize }, 5);
        // 21 is merely one caller-provided test input, never an implementation default.
        for argument in [21, 0, 1, 0x8123_4567, u32::MAX] {
            let mut raw = MaybeUninit::<RulesState>::uninit();
            assert_eq!(run(INIT, raw.as_mut_ptr().cast(), argument), argument);
            let state = unsafe { raw.assume_init() };
            assert_eq!(state.version, argument);
            assert_eq!(state.admin, 0);
            assert_eq!(state.reserved, [0; 3]);
        }
    }

    #[test]
    fn full_word_100k_independent_version_only_oracle() {
        let before = snapshot();
        let mut calls = 0u64;
        let mut exercise = |version: u32, other: u32| {
            let mut state = RulesState { version: 9, admin: 1, reserved: [7, 8, 9] };
            let p = (&mut state as *mut RulesState).cast();
            assert_eq!(run(SET_VERSION, p, version), version);
            assert_eq!(run(VERSION, p, 0), version);
            assert_eq!(run(LEGACY, p, 0), u32::from(u64::from(version) < 1));
            for admin in [0, 1] {
                assert_eq!(run(SET_ADMIN, p, admin), admin);
                assert_eq!(run(ADMIN, p, 0), admin);
                // Ordering over widened words is independent of the kernel's ==.
                let expected = u32::from(u64::from(version).cmp(&u64::from(other)) == std::cmp::Ordering::Equal);
                assert_eq!(run(EQUAL_VERSION, p, other), expected);
                assert_eq!(run(EQUAL_VERSION, p, version), 1);
            }
            assert_eq!(state.reserved, [7, 8, 9]);
            calls += 1;
        };
        let edges = [0, 1, 2, 0x7fff_ffff, 0x8000_0000, u32::MAX - 1, u32::MAX];
        for v in edges { for w in edges { exercise(v, w); } }
        let mut seed = 0xe703_7ed1_a0b4_28dbu64;
        for _ in 0..100_000 {
            seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17;
            exercise(seed as u32, (seed >> 32) as u32);
        }
        for (i, multiplicity) in [0, 1, 1, 2, 2, 1, 4].into_iter().enumerate() {
            assert_eq!(sb_net_rules_count(0, i as u32).wrapping_sub(before[i]), calls * multiplicity);
        }
    }

    #[test]
    fn guarded_mutators_preserve_every_other_byte_and_copies_move() {
        #[repr(C)]
        struct Guarded { before: u32, state: RulesState, after: u32 }
        let mut g = Guarded { before: 0x1234_5678,
            state: RulesState { version: 9, admin: 1, reserved: [0x81, 0xa5, 0xff] }, after: 0x8765_4321 };
        let p = (&mut g.state as *mut RulesState).cast();
        let saved = bytes(&g.state);
        run(SET_VERSION, p, u32::MAX);
        assert_eq!(&bytes(&g.state)[4..], &saved[4..]);
        let saved = bytes(&g.state);
        run(SET_ADMIN, p, 0);
        let mut expected = saved;
        expected[4] = 0;
        assert_eq!(bytes(&g.state), expected);
        let mut copied = MaybeUninit::<RulesState>::uninit();
        unsafe { ptr::copy_nonoverlapping(address(&g.state).cast::<u8>(), copied.as_mut_ptr().cast::<u8>(), 8); }
        let copied = unsafe { copied.assume_init() };
        let moved = copied;
        assert_eq!(bytes(&moved), expected);
        assert_eq!(run(VERSION, address(&moved), 0), u32::MAX);
        assert_eq!(g.before, 0x1234_5678);
        assert_eq!(g.after, 0x8765_4321);
    }

    #[test]
    fn partial_initialization_never_reads_uninitialized_fields() {
        let mut raw = MaybeUninit::<RulesState>::uninit();
        let p = raw.as_mut_ptr();
        let storage = p.cast();
        run(SET_VERSION, storage, 0x8123_4567);
        assert_eq!(run(VERSION, storage, 0), 0x8123_4567);
        assert_eq!(run(LEGACY, storage, 0), 0);
        assert_eq!(run(EQUAL_VERSION, storage, 0x8123_4567), 1);
        run(SET_ADMIN, storage, 1);
        assert_eq!(run(ADMIN, storage, 0), 1);
        // All eight bytes are initialized only after this explicit reserved write.
        unsafe { addr_of_mut!((*p).reserved).write([3, 4, 5]); }
        let state = unsafe { raw.assume_init() };
        assert_eq!(state.reserved, [3, 4, 5]);
        let mut raw = MaybeUninit::<RulesState>::uninit();
        let p = raw.as_mut_ptr();
        run(SET_ADMIN, p.cast(), 0); // old version/admin/reserved all uninitialized
        assert_eq!(run(ADMIN, p.cast(), 0), 0);
        // No assume_init: version and reserved intentionally remain uninitialized.
    }

    #[test]
    fn raw_noncanonical_admin_is_ignored_or_rejected_and_repairable() {
        let mut state = RulesState { version: 0, admin: 2, reserved: [0xff; 3] };
        let p = (&mut state as *mut RulesState).cast();
        assert_eq!(run(VERSION, p, 0), 0);
        assert_eq!(run(LEGACY, p, 0), 1);
        assert_eq!(run(EQUAL_VERSION, p, 0), 1);
        run(SET_VERSION, p, u32::MAX);
        assert_eq!(state.admin, 2);
        let before = snapshot();
        let saved = bytes(&state);
        let mut out = 99;
        assert_eq!(unsafe { sb_net_rules_run(ADMIN, p, 0, &mut out) }, INVALID);
        assert_eq!(snapshot(), before);
        assert_eq!(bytes(&state), saved);
        assert_eq!(out, 99);
        run(SET_ADMIN, p, 1);
        assert_eq!(run(ADMIN, p, 0), 1);
    }

    #[test]
    fn invalid_addresses_arguments_and_all_overlaps_do_not_count_or_write() {
        let mut backing = [0xabcdef01u32; 8];
        let saved = backing;
        let p = backing.as_mut_ptr();
        let mut out = 0xdead_beef;
        let before = snapshot();
        for mode in 0..COUNT as u32 {
            for storage in [ptr::null(), unsafe { p.cast::<u8>().add(1).cast::<c_void>() }] {
                assert_eq!(unsafe { sb_net_rules_run(mode, storage, 0, &mut out) }, INVALID);
            }
            for output in [ptr::null_mut(), unsafe { p.cast::<u8>().add(1).cast::<u32>() }] {
                assert_eq!(unsafe { sb_net_rules_run(mode, p.cast(), 0, output) }, INVALID);
            }
            // Includes exact start, output at offset 4, and storage beginning
            // inside the output interval. Unaligned partial overlaps reject too.
            for delta in 0..8 {
                let q = unsafe { p.cast::<u8>().add(delta).cast::<u32>() };
                assert_eq!(unsafe { sb_net_rules_run(mode, p.cast(), 0, q) }, INVALID);
            }
            for delta in 0..4 {
                let q = unsafe { p.cast::<u8>().add(delta).cast::<c_void>() };
                assert_eq!(unsafe { sb_net_rules_run(mode, q, 0, p) }, INVALID);
            }
        }
        for mode in [COUNT as u32, u32::MAX] {
            assert_eq!(unsafe { sb_net_rules_run(mode, p.cast(), 0, &mut out) }, INVALID);
        }
        for mode in [VERSION, ADMIN, LEGACY] {
            for argument in [1, u32::MAX] {
                assert_eq!(unsafe { sb_net_rules_run(mode, p.cast(), argument, &mut out) }, INVALID);
            }
        }
        for argument in [2, 255, u32::MAX] {
            assert_eq!(unsafe { sb_net_rules_run(SET_ADMIN, p.cast(), argument, &mut out) }, INVALID);
        }
        assert_eq!(snapshot(), before);
        assert_eq!(backing, saved);
        assert_eq!(out, 0xdead_beef);
        for kind in [0, 1, 2, u32::MAX] {
            for mode in [COUNT as u32, u32::MAX] { assert_eq!(sb_net_rules_count(kind, mode), 0); }
        }
        for mode in 0..COUNT as u32 { assert_eq!(sb_net_rules_count(2, mode), 0); }
    }

    #[test]
    fn readonly_getters_and_disjoint_adjacent_output() {
        let state = RulesState { version: 0, admin: 1, reserved: [0x99; 3] };
        let saved = bytes(&state);
        for (mode, argument, expected) in [(VERSION, 0, 0), (ADMIN, 0, 1), (LEGACY, 0, 1), (EQUAL_VERSION, 0, 1)] {
            assert_eq!(run(mode, address(&state), argument), expected);
        }
        assert_eq!(bytes(&state), saved);
        let mut backing = [0u32; 4];
        let p = backing.as_mut_ptr();
        // State [0,8), out [8,12), then out [0,4), state [4,12).
        assert_eq!(unsafe { sb_net_rules_run(INIT, p.cast(), 7, p.add(2)) }, OK);
        assert_eq!(backing[2], 7);
        assert_eq!(unsafe { sb_net_rules_run(INIT, p.add(1).cast(), 13, p) }, OK);
        assert_eq!(backing[0], 13);
        assert_eq!(backing[3], 0);
    }

    #[test]
    fn panic_before_every_commit_preserves_state_and_output() {
        let mut state = RulesState { version: 79, admin: 1, reserved: [7, 8, 9] };
        let p = (&mut state as *mut RulesState).cast();
        let saved = bytes(&state);
        for mode in 0..COUNT as u32 {
            let mut out = 113;
            let before = snapshot();
            assert_eq!(unsafe { checked(mode, p, 0, &mut out, || panic!("rules seam")) }, PANIC);
            assert_eq!(bytes(&state), saved);
            assert_eq!(out, 113);
            for i in 0..COUNT {
                assert_eq!(sb_net_rules_count(0, i as u32), before[i].wrapping_add(u64::from(i == mode as usize)));
            }
        }
    }

    #[test]
    fn tls_global_visibility_and_wrapping_diagnostics() {
        let local = snapshot();
        let global: [u64; COUNT] = std::array::from_fn(|i| sb_net_rules_count(1, i as u32));
        std::thread::spawn(|| {
            let mut raw = MaybeUninit::<RulesState>::uninit();
            let p = raw.as_mut_ptr().cast();
            for mode in 0..COUNT as u32 {
                assert_eq!(sb_net_rules_count(0, mode), 0);
                run(mode, p, 0);
                assert_eq!(sb_net_rules_count(0, mode), 1);
            }
        }).join().unwrap();
        assert_eq!(snapshot(), local);
        for i in 0..COUNT {
            assert!(sb_net_rules_count(1, i as u32).wrapping_sub(global[i]) >= 1);
        }
        COUNTS.with(|cell| {
            let saved = cell.get();
            cell.set([u64::MAX; COUNT]);
            for mode in 0..COUNT {
                count_entry(mode);
                assert_eq!(sb_net_rules_count(0, mode as u32), 0);
            }
            cell.set(saved);
        });
        // Isolated atomic demonstrates wrap without resetting shared globals.
        let isolated = AtomicU64::new(u64::MAX);
        assert_eq!(isolated.fetch_add(1, Ordering::Relaxed), u64::MAX);
        assert_eq!(isolated.load(Ordering::Relaxed), 0);
    }
}
