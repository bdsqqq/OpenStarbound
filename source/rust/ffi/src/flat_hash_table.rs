//! FlatHashTable probe/insert policy; native storage and value lifetimes stay native.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST_ERROR: u32 = 2;
const PANIC: u32 = 3;
const FIND: u32 = 0;
const SCAN: u32 = 1;
const INSERT: u32 = 2;
const COUNT: usize = 3;
const SIZE: u32 = 0;
const HASH: u32 = 1;
const LOAD: u32 = 2;
const EQUALS: u32 = 3;
const ACTIVE_HASH: u32 = 4;
const SCAN_EMPTY: u32 = 5;
const SCAN_ADVANCE: u32 = 6;
const CAPACITY_NEEDED: u32 = 7;
const ENSURE_CAPACITY: u32 = 8;
const SWAP_VALUE: u32 = 9;
const EXCHANGE_HASH: u32 = 10;
const SET_FILLED: u32 = 11;
const INCREMENT_FILLED: u32 = 12;
const FILLED: usize = 1usize << (usize::BITS - 1);

type Leaf = unsafe extern "C" fn(*mut c_void, u32, usize, *mut usize) -> u32;

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbFlatHashReply {
    pub index: usize,
    pub found: u32,
}

// Compile-time native ABI checks, selected independently on 32-/64-bit targets.
const _: () = {
    assert!(std::mem::offset_of!(SbFlatHashReply, index) == 0);
    assert!(std::mem::offset_of!(SbFlatHashReply, found) == std::mem::size_of::<usize>());
    assert!(std::mem::align_of::<SbFlatHashReply>() == std::mem::align_of::<usize>());
};
#[cfg(target_pointer_width = "64")]
const _: () = assert!(std::mem::size_of::<SbFlatHashReply>() == 16);
#[cfg(target_pointer_width = "32")]
const _: () = assert!(std::mem::size_of::<SbFlatHashReply>() == 8);

const MISS: SbFlatHashReply = SbFlatHashReply { index: 0, found: 0 };
static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
thread_local! {
    static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) };
}

// Only raw context crosses host calls; never borrow a host frame across reentry.
unsafe fn invoke(ctx: *mut c_void, leaf: Leaf, op: u32, arg: usize) -> Result<usize, u32> {
    let mut value = 0;
    if leaf(ctx, op, arg, &mut value) != 0 {
        return Err(HOST_ERROR);
    }
    if ((op == LOAD || op == EQUALS || op == SCAN_EMPTY || op == CAPACITY_NEEDED) && value > 1)
        || ((op == SCAN_ADVANCE || op == ENSURE_CAPACITY || op == SWAP_VALUE
            || op == SET_FILLED || op == INCREMENT_FILLED) && value != 0)
    {
        return Err(INVALID);
    }
    Ok(value)
}

unsafe fn insert(ctx: *mut c_void, leaf: Leaf) -> Result<SbFlatHashReply, u32> {
    // Keep native fast-math load-factor arithmetic and growth/reentry native.
    if invoke(ctx, leaf, CAPACITY_NEEDED, 0)? != 0 {
        invoke(ctx, leaf, ENSURE_CAPACITY, 0)?;
    }
    let mut hash = invoke(ctx, leaf, HASH, 0)? | FILLED;
    let mut target = hash & invoke(ctx, leaf, SIZE, 0)?.wrapping_sub(2);
    let mut current = target;
    let mut inserted = usize::MAX;
    loop {
        if invoke(ctx, leaf, LOAD, current)? != 0 {
            let loaded_hash = invoke(ctx, leaf, ACTIVE_HASH, 0)?;
            if loaded_hash == hash && invoke(ctx, leaf, EQUALS, 0)? != 0 {
                // Native returns this duplicate bucket even after earlier swaps.
                return Ok(SbFlatHashReply { index: current, found: 1 });
            }
            let active_hash = invoke(ctx, leaf, ACTIVE_HASH, 0)?;
            let mask = invoke(ctx, leaf, SIZE, 0)?.wrapping_sub(2);
            let entry_target = active_hash & mask;
            let entry_error = current.wrapping_sub(entry_target) & mask;
            let add_error = current.wrapping_sub(target) & mask;
            if add_error > entry_error {
                if inserted == usize::MAX {
                    inserted = current;
                }
                invoke(ctx, leaf, SWAP_VALUE, 0)?;
                // Value swap may mutate native hash metadata: exchange only now,
                // and do not normalize the returned raw native hash again.
                hash = invoke(ctx, leaf, EXCHANGE_HASH, hash)?;
                target = entry_target;
            }
            let mask = invoke(ctx, leaf, SIZE, 0)?.wrapping_sub(2);
            current = current.wrapping_add(1) & mask;
        } else {
            invoke(ctx, leaf, SET_FILLED, hash)?;
            invoke(ctx, leaf, INCREMENT_FILLED, 0)?;
            if inserted == usize::MAX {
                inserted = current;
            }
            return Ok(SbFlatHashReply { index: inserted, found: 0 });
        }
    }
}

unsafe fn run(mode: u32, ctx: *mut c_void, leaf: Leaf) -> Result<SbFlatHashReply, u32> {
    if mode == INSERT {
        return insert(ctx, leaf);
    }
    if mode == SCAN {
        while invoke(ctx, leaf, SCAN_EMPTY, 0)? != 0 {
            invoke(ctx, leaf, SCAN_ADVANCE, 0)?;
        }
        return Ok(MISS);
    }
    if invoke(ctx, leaf, SIZE, 0)? == 0 {
        return Ok(MISS);
    }
    let hash = invoke(ctx, leaf, HASH, 0)? | FILLED;
    // Hashing may reenter and change/reallocate the native bucket vector.
    let mask = invoke(ctx, leaf, SIZE, 0)?.wrapping_sub(2);
    let target = hash & mask;
    let mut current = target;
    loop {
        // LOAD calls native valuePtr() exactly once and saves that Value* even
        // when the subsequent hash comparison fails. Presence is not a hash test.
        if invoke(ctx, leaf, LOAD, current)? == 0 {
            return Ok(MISS);
        }
        let loaded_hash = invoke(ctx, leaf, ACTIVE_HASH, 0)?;
        if loaded_hash == hash && invoke(ctx, leaf, EQUALS, 0)? != 0 {
            return Ok(SbFlatHashReply { index: current, found: 1 });
        }
        // Do not reuse loaded_hash: equality may have changed the active bucket hash.
        // Native bucketError uses the raw hash; masking after subtraction preserves it.
        let active_hash = invoke(ctx, leaf, ACTIVE_HASH, 0)?;
        let mask = invoke(ctx, leaf, SIZE, 0)?.wrapping_sub(2);
        let entry_error = current.wrapping_sub(active_hash) & mask;
        let find_error = current.wrapping_sub(target) & mask;
        if find_error > entry_error {
            return Ok(MISS);
        }
        current = current.wrapping_add(1) & mask;
    }
}

/// Executes find/scan/insert control, publishing a reply only after success.
///
/// # Safety
/// Context must remain live and satisfy every leaf operation's native contract.
/// `out` must point to live writable reply storage. Leaves must catch all native
/// exceptions and must not unwind through Rust. Reentry is supported, but native
/// active-bucket validity and lifetime remain the host's responsibility.
#[no_mangle]
pub unsafe extern "C" fn sb_flat_hash_run(
    mode: u32,
    ctx: *mut c_void,
    leaf: Option<Leaf>,
    out: *mut SbFlatHashReply,
) -> u32 {
    if mode >= COUNT as u32 || ctx.is_null() || leaf.is_none() || out.is_null()
        || (out as usize) % std::mem::align_of::<SbFlatHashReply>() != 0
    {
        return INVALID;
    }
    match catch_unwind(AssertUnwindSafe(|| {
        COUNTS.with(|cell| {
            let mut counts = cell.get();
            counts[mode as usize] = counts[mode as usize].wrapping_add(1);
            cell.set(counts);
        });
        TOTALS[mode as usize].fetch_add(1, Ordering::Relaxed);
        match run(mode, ctx, leaf.unwrap()) {
            Ok(reply) => { out.write(reply); OK }
            Err(status) => status,
        }
    })) {
        Ok(status) => status,
        Err(_) => PANIC,
    }
}

/// Diagnostic counters only: aggregate reads do not synchronize engine state.
#[no_mangle]
pub extern "C" fn sb_flat_hash_count(kind: u32, mode: u32) -> u64 {
    if kind > 1 || mode >= COUNT as u32 {
        return 0;
    }
    catch_unwind(AssertUnwindSafe(|| {
        if kind == 0 {
            COUNTS.with(|cell| cell.get()[mode as usize])
        } else {
            TOTALS[mode as usize].load(Ordering::Relaxed)
        }
    })).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Clone, Copy, Debug)]
    struct Step { op: u32, arg: usize, value: usize, status: u32 }
    fn s(op: u32, arg: usize, value: usize) -> Step {
        Step { op, arg, value, status: 0 }
    }
    struct Host { steps: Vec<Step>, next: usize, bad: bool }
    unsafe extern "C" fn scripted(ctx: *mut c_void, op: u32, arg: usize, out: *mut usize) -> u32 {
        let host = &mut *ctx.cast::<Host>();
        let Some(step) = host.steps.get(host.next).copied() else {
            host.bad = true;
            return 1;
        };
        host.next += 1;
        if step.op != op || step.arg != arg {
            host.bad = true;
            return 1;
        }
        out.write(step.value);
        step.status
    }
    const UNCHANGED: SbFlatHashReply = SbFlatHashReply { index: 713, found: 91 };
    fn execute(mode: u32, steps: &[Step], expected: u32, reply: SbFlatHashReply) {
        let mut host = Host { steps: steps.to_vec(), next: 0, bad: false };
        let mut out = UNCHANGED;
        let status = unsafe { sb_flat_hash_run(mode, (&mut host as *mut Host).cast(), Some(scripted), &mut out) };
        assert_eq!(status, expected, "steps: {steps:?}");
        assert!(!host.bad, "unexpected callback in {steps:?}");
        assert_eq!(host.next, steps.len(), "unconsumed callbacks");
        assert_eq!(out, reply);
    }
    fn prefix(hash: usize) -> Vec<Step> {
        vec![s(SIZE, 0, 9), s(HASH, 0, hash), s(SIZE, 0, 9)]
    }
    fn collision() -> Vec<Step> {
        let mut v = prefix(7);
        // Collision at 7, wrap to 0, then match. Equality false must not stop.
        v.extend([s(LOAD, 7, 1), s(ACTIVE_HASH, 0, FILLED | 7), s(EQUALS, 0, 0),
            s(ACTIVE_HASH, 0, FILLED | 7), s(SIZE, 0, 9),
            s(LOAD, 0, 1), s(ACTIVE_HASH, 0, FILLED | 7), s(EQUALS, 0, 1)]);
        v
    }
    fn insert_prefix(capacity: bool, hash: usize, size: usize) -> Vec<Step> {
        let mut v = vec![s(CAPACITY_NEEDED, 0, capacity as usize)];
        if capacity {
            v.push(s(ENSURE_CAPACITY, 0, 0));
        }
        v.extend([s(HASH, 0, hash), s(SIZE, 0, size)]);
        v
    }
    fn insert_new(capacity: bool) -> Vec<Step> {
        let mut v = insert_prefix(capacity, 12, 17);
        v.extend([s(LOAD, 12, 0), s(SET_FILLED, FILLED | 12, 0),
            s(INCREMENT_FILLED, 0, 0)]);
        v
    }
    fn insert_duplicate() -> Vec<Step> {
        let mut v = insert_prefix(false, 3, 9);
        v.extend([s(LOAD, 3, 1), s(ACTIVE_HASH, 0, FILLED | 3), s(EQUALS, 0, 1)]);
        v
    }
    fn insert_swaps() -> Vec<Step> {
        let mut v = insert_prefix(false, 7, 9);
        v.extend([s(LOAD, 7, 1), s(ACTIVE_HASH, 0, FILLED | 7), s(EQUALS, 0, 0),
            s(ACTIVE_HASH, 0, FILLED | 7), s(SIZE, 0, 9), s(SIZE, 0, 9),
            s(LOAD, 0, 1), s(ACTIVE_HASH, 0, FILLED),
            s(ACTIVE_HASH, 0, FILLED), s(SIZE, 0, 9), s(SWAP_VALUE, 0, 0),
            // Value swap changes the hash to raw 2: don't OR FILLED on exchange.
            s(EXCHANGE_HASH, FILLED | 7, 2), s(SIZE, 0, 9),
            s(LOAD, 1, 1), s(ACTIVE_HASH, 0, FILLED | 1),
            s(ACTIVE_HASH, 0, FILLED | 1), s(SIZE, 0, 9), s(SWAP_VALUE, 0, 0),
            s(EXCHANGE_HASH, 2, 0), s(SIZE, 0, 9),
            s(LOAD, 2, 0), s(SET_FILLED, 0, 0), s(INCREMENT_FILLED, 0, 0)]);
        v
    }
    #[test]
    fn insert_duplicate_new_and_native_capacity_before_hash() {
        execute(INSERT, &insert_duplicate(), OK, SbFlatHashReply { index: 3, found: 1 });
        for capacity in [false, true] {
            // Capacity growth determines the new hash and size before LOAD.
            execute(INSERT, &insert_new(capacity), OK, SbFlatHashReply { index: 12, found: 0 });
        }
        let mut v = insert_prefix(false, 7, 9);
        v.extend([s(LOAD, 7, 1), s(ACTIVE_HASH, 0, FILLED | 7), s(EQUALS, 0, 0),
            s(ACTIVE_HASH, 0, FILLED | 7), s(SIZE, 0, 9), s(SIZE, 0, 9),
            s(LOAD, 0, 0), s(SET_FILLED, FILLED | 7, 0), s(INCREMENT_FILLED, 0, 0)]);
        execute(INSERT, &v, OK, SbFlatHashReply { index: 0, found: 0 });
    }
    #[test]
    fn insert_robin_hood_returns_first_swap_bucket_and_raw_exchanged_hash() {
        // A reversed add_error > entry_error consumes an unexpected SWAP at 7
        // or misses the required swap at 0. Later swaps must not replace index 0.
        execute(INSERT, &insert_swaps(), OK, SbFlatHashReply { index: 0, found: 0 });
        let mut v = insert_swaps();
        v.truncate(v.iter().position(|step| step.op == LOAD && step.arg == 1).unwrap());
        v.extend([s(LOAD, 1, 1), s(ACTIVE_HASH, 0, 2), s(EQUALS, 0, 1)]);
        execute(INSERT, &v, OK, SbFlatHashReply { index: 1, found: 1 });
    }
    #[test]
    fn insert_retains_pre_swap_entry_target_not_exchanged_hash_target() {
        let mut v = insert_swaps();
        let next = v.iter().position(|step| step.op == LOAD && step.arg == 1).unwrap();
        v.truncate(next);
        v.extend([s(LOAD, 1, 1), s(ACTIVE_HASH, 0, FILLED),
            s(ACTIVE_HASH, 0, FILLED), s(SIZE, 0, 9),
            // Correct target remains 0: add_error == entry_error == 1, no swap.
            // Recomputing target from the exchanged hash 2 would swap here.
            s(SIZE, 0, 9), s(LOAD, 2, 0), s(SET_FILLED, 2, 0), s(INCREMENT_FILLED, 0, 0)]);
        execute(INSERT, &v, OK, SbFlatHashReply { index: 0, found: 0 });
    }
    #[test]
    fn insert_equality_metadata_and_advance_size_are_fresh() {
        let mut v = insert_prefix(false, 7, 9);
        v.extend([s(LOAD, 7, 1), s(ACTIVE_HASH, 0, FILLED | 7), s(EQUALS, 0, 0),
            // Reach bucket 0, where equality changes both hash and size;
            // its fresh entry target is 0 rather than the comparison target 7.
            s(ACTIVE_HASH, 0, FILLED | 7), s(SIZE, 0, 9), s(SIZE, 0, 9),
            s(LOAD, 0, 1), s(ACTIVE_HASH, 0, FILLED | 7), s(EQUALS, 0, 0),
            s(ACTIVE_HASH, 0, FILLED), s(SIZE, 0, 17), s(SWAP_VALUE, 0, 0),
            s(EXCHANGE_HASH, FILLED | 7, FILLED | 4), s(SIZE, 0, 33),
            s(LOAD, 1, 0), s(SET_FILLED, FILLED | 4, 0), s(INCREMENT_FILLED, 0, 0)]);
        execute(INSERT, &v, OK, SbFlatHashReply { index: 0, found: 0 });
        // A swap can resize before advancing: stale mask 7 would wrap to 0,
        // whereas the new mask 15 advances to bucket 8.
        let mut v = insert_prefix(false, 6, 9);
        v.extend([s(LOAD, 6, 1), s(ACTIVE_HASH, 0, FILLED | 6), s(EQUALS, 0, 0),
            s(ACTIVE_HASH, 0, FILLED | 6), s(SIZE, 0, 9), s(SIZE, 0, 9),
            s(LOAD, 7, 1), s(ACTIVE_HASH, 0, FILLED | 7),
            s(ACTIVE_HASH, 0, FILLED | 7), s(SIZE, 0, 9), s(SWAP_VALUE, 0, 0),
            s(EXCHANGE_HASH, FILLED | 6, 1), s(SIZE, 0, 17),
            s(LOAD, 8, 0), s(SET_FILLED, 1, 0), s(INCREMENT_FILLED, 0, 0)]);
        execute(INSERT, &v, OK, SbFlatHashReply { index: 7, found: 0 });
    }
    #[test]
    fn insert_growth_reentry_keeps_frames_counts_and_post_capacity_hash_fresh() {
        struct Growth { outer: Host, inner: Host, nested: bool, hash: usize }
        unsafe extern "C" fn growth(ctx: *mut c_void, op: u32, arg: usize, out: *mut usize) -> u32 {
            let state = ctx.cast::<Growth>();
            if (*state).nested {
                return scripted(std::ptr::addr_of_mut!((*state).inner).cast(), op, arg, out);
            }
            let status = scripted(std::ptr::addr_of_mut!((*state).outer).cast(), op, arg, out);
            if status != 0 {
                return status;
            }
            if op == ENSURE_CAPACITY {
                (*state).nested = true;
                let mut reply = UNCHANGED;
                // No reference into either host frame spans nested INSERT.
                let status = sb_flat_hash_run(INSERT, ctx, Some(growth), &mut reply);
                (*state).nested = false;
                if status != OK || reply != (SbFlatHashReply { index: 3, found: 0 }) {
                    return 1;
                }
                (*state).hash = 12;
            } else if op == HASH {
                if (*state).hash != 12 {
                    return 1;
                }
                out.write((*state).hash);
            }
            0
        }
        let mut inner = insert_prefix(false, 3, 9);
        inner.extend([s(LOAD, 3, 0), s(SET_FILLED, FILLED | 3, 0), s(INCREMENT_FILLED, 0, 0)]);
        let mut state = Growth {
            outer: Host { steps: insert_new(true), next: 0, bad: false },
            inner: Host { steps: inner, next: 0, bad: false },
            nested: false,
            hash: 3,
        };
        let before = sb_flat_hash_count(0, INSERT);
        let mut out = UNCHANGED;
        let status = unsafe {
            sb_flat_hash_run(INSERT, (&mut state as *mut Growth).cast(), Some(growth), &mut out)
        };
        assert_eq!(status, OK);
        assert_eq!(out, SbFlatHashReply { index: 12, found: 0 });
        assert_eq!(state.hash, 12);
        assert!(!state.nested);
        for host in [&state.outer, &state.inner] {
            assert!(!host.bad);
            assert_eq!(host.next, host.steps.len());
        }
        assert_eq!(sb_flat_hash_count(0, INSERT), before.wrapping_add(2));
    }
    #[test]
    fn insert_exchange_accepts_all_word_bits_and_sizes_are_not_validated() {
        let mut v = insert_swaps();
        let last_exchange = v.iter().rposition(|step| step.op == EXCHANGE_HASH).unwrap();
        v[last_exchange].value = usize::MAX;
        let set_filled = v.iter().position(|step| step.op == SET_FILLED).unwrap();
        v[set_filled].arg = usize::MAX;
        execute(INSERT, &v, OK, SbFlatHashReply { index: 0, found: 0 });
        let mut v = insert_prefix(false, 3, 0);
        v.extend([s(LOAD, FILLED | 2, 0), s(SET_FILLED, FILLED | 3, 0), s(INCREMENT_FILLED, 0, 0)]);
        execute(INSERT, &v, OK, SbFlatHashReply { index: FILLED | 2, found: 0 });
    }
    #[test]
    fn insert_every_callback_error_stops_with_unchanged_output() {
        for steps in [insert_new(false), insert_new(true), insert_duplicate(), insert_swaps()] {
            for fail in 0..steps.len() {
                for status in [1, 2, u32::MAX] {
                    let mut v = steps[..=fail].to_vec();
                    v[fail].status = status;
                    v[fail].value = usize::MAX;
                    // Includes SWAP_VALUE failure (no EXCHANGE_HASH) and
                    // SET_FILLED failure (no INCREMENT_FILLED).
                    execute(INSERT, &v, HOST_ERROR, UNCHANGED);
                }
            }
        }
    }
    #[test]
    fn insert_rejects_malformed_predicate_and_void_replies() {
        for steps in [insert_new(true), insert_duplicate(), insert_swaps()] {
            for (i, step) in steps.iter().enumerate() {
                let predicate = matches!(step.op, CAPACITY_NEEDED | LOAD | EQUALS);
                let void = matches!(step.op, ENSURE_CAPACITY | SWAP_VALUE | SET_FILLED | INCREMENT_FILLED);
                if predicate || void {
                    for value in [2, usize::MAX] {
                        let mut v = steps[..=i].to_vec();
                        v[i].value = value;
                        execute(INSERT, &v, INVALID, UNCHANGED);
                    }
                    if void {
                        let mut v = steps[..=i].to_vec();
                        v[i].value = 1;
                        execute(INSERT, &v, INVALID, UNCHANGED);
                    }
                }
            }
        }
    }
    #[test]
    fn empty_end_match_mismatch_collision() {
        execute(FIND, &[s(SIZE, 0, 0)], OK, MISS);
        // Native valuePtr() reports false for both empty and end buckets.
        let mut end = prefix(3);
        end.push(s(LOAD, 3, 0));
        execute(FIND, &end, OK, MISS);
        let mut v = prefix(3);
        v.extend([s(LOAD, 3, 1), s(ACTIVE_HASH, 0, FILLED | 3), s(EQUALS, 0, 1)]);
        execute(FIND, &v, OK, SbFlatHashReply { index: 3, found: 1 });
        let mut v = prefix(3);
        v.extend([s(LOAD, 3, 1), s(ACTIVE_HASH, 0, FILLED | 2),
            s(ACTIVE_HASH, 0, FILLED | 2), s(SIZE, 0, 9), s(LOAD, 4, 0)]);
        execute(FIND, &v, OK, MISS);
        execute(FIND, &collision(), OK, SbFlatHashReply { index: 0, found: 1 });
    }
    #[test]
    fn presence_comes_only_from_saved_value_pointer_not_hash_bits() {
        let mut v = prefix(3);
        // A reported native value remains present even when its separately read
        // hash lacks FILLED. LOAD must precede both hash reads, with no EQUALS.
        v.extend([s(LOAD, 3, 1), s(ACTIVE_HASH, 0, 0),
            s(ACTIVE_HASH, 0, 0), s(SIZE, 0, 9), s(LOAD, 4, 0)]);
        execute(FIND, &v, OK, MISS);
    }
    #[test]
    fn early_exit_uses_find_error_and_raw_hash() {
        let mut v = prefix(7);
        v.extend([s(LOAD, 7, 1), s(ACTIVE_HASH, 0, FILLED | 6),
            s(ACTIVE_HASH, 0, FILLED | 6), s(SIZE, 0, 9),
            s(LOAD, 0, 1), s(ACTIVE_HASH, 0, FILLED),
            s(ACTIVE_HASH, 0, FILLED), s(SIZE, 0, 9)]);
        // find error 1 > entry error 0. Reversing the comparison, or using
        // current-hash instead of current-target, consumes an unexpected leaf.
        execute(FIND, &v, OK, MISS);
    }
    #[test]
    fn hash_callback_changes_size_before_target_selection() {
        execute(FIND, &[s(SIZE, 0, 9), s(HASH, 0, 12), s(SIZE, 0, 17),
            s(LOAD, 12, 1), s(ACTIVE_HASH, 0, FILLED | 12), s(EQUALS, 0, 1)], OK,
            SbFlatHashReply { index: 12, found: 1 });
    }
    #[test]
    fn equality_mutation_requires_fresh_active_hash() {
        let mut v = prefix(7);
        v.extend([s(LOAD, 7, 1), s(ACTIVE_HASH, 0, FILLED | 7), s(EQUALS, 0, 0),
            s(ACTIVE_HASH, 0, FILLED | 7), s(SIZE, 0, 9),
            s(LOAD, 0, 1), s(ACTIVE_HASH, 0, FILLED | 7), s(EQUALS, 0, 0),
            s(ACTIVE_HASH, 0, FILLED), s(SIZE, 0, 9)]);
        // Fresh hash yields entry error 0 and exits. Stale loaded hash gives 1.
        execute(FIND, &v, OK, MISS);
    }
    #[test]
    fn post_equality_mask_is_fresh() {
        let mut v = prefix(7);
        v.extend([s(LOAD, 7, 1), s(ACTIVE_HASH, 0, FILLED | 7), s(EQUALS, 0, 0),
            s(ACTIVE_HASH, 0, FILLED | 7), s(SIZE, 0, 17), s(LOAD, 8, 0)]);
        execute(FIND, &v, OK, MISS);
    }
    #[test]
    fn scan_advances_only_while_empty_including_sentinel_stop() {
        execute(SCAN, &[s(SCAN_EMPTY, 0, 0)], OK, MISS);
        execute(SCAN, &[s(SCAN_EMPTY, 0, 1), s(SCAN_ADVANCE, 0, 0),
            s(SCAN_EMPTY, 0, 1), s(SCAN_ADVANCE, 0, 0), s(SCAN_EMPTY, 0, 0)], OK, MISS);
    }
    #[test]
    fn every_callback_failure_stops_and_preserves_output() {
        let scan = vec![s(SCAN_EMPTY, 0, 1), s(SCAN_ADVANCE, 0, 0), s(SCAN_EMPTY, 0, 0)];
        for (mode, steps) in [(FIND, collision()), (SCAN, scan)] {
            for fail in 0..steps.len() {
                for status in [1, 2, u32::MAX] {
                    let mut v = steps[..=fail].to_vec();
                    v[fail].status = status;
                    // A failure takes priority over malformed scalar replies.
                    v[fail].value = usize::MAX;
                    execute(mode, &v, HOST_ERROR, UNCHANGED);
                }
            }
        }
    }
    #[test]
    fn malformed_booleans_and_void_preserve_output() {
        for value in [2, usize::MAX] {
            let mut v = prefix(1);
            v.extend([s(LOAD, 1, 1), s(ACTIVE_HASH, 0, FILLED | 1), s(EQUALS, 0, value)]);
            execute(FIND, &v, INVALID, UNCHANGED);
            let mut malformed_load = prefix(1);
            malformed_load.push(s(LOAD, 1, value));
            execute(FIND, &malformed_load, INVALID, UNCHANGED);
            execute(SCAN, &[s(SCAN_EMPTY, 0, value)], INVALID, UNCHANGED);
        }
        for value in [1, usize::MAX] {
            execute(SCAN, &[s(SCAN_EMPTY, 0, 1), s(SCAN_ADVANCE, 0, value)], INVALID, UNCHANGED);
        }
    }
    #[test]
    fn scalar_sizes_are_not_normalized_or_power_of_two_validated() {
        // After hashing, zero size is intentionally accepted: wrapping mask.
        execute(FIND, &[s(SIZE, 0, 1), s(HASH, 0, 3), s(SIZE, 0, 0),
            s(LOAD, FILLED | 2, 0)], OK, MISS);
        execute(FIND, &[s(SIZE, 0, 6), s(HASH, 0, 7), s(SIZE, 0, 6),
            s(LOAD, 4, 0)], OK, MISS);
    }
    #[test]
    fn invalid_arguments_do_not_call_or_count() {
        let mut host = Host { steps: vec![], next: 0, bad: false };
        let ctx = (&mut host as *mut Host).cast();
        let mut out = UNCHANGED;
        let before = [sb_flat_hash_count(0, FIND), sb_flat_hash_count(0, SCAN), sb_flat_hash_count(0, INSERT)];
        unsafe {
            assert_eq!(sb_flat_hash_run(COUNT as u32, ctx, Some(scripted), &mut out), INVALID);
            assert_eq!(sb_flat_hash_run(FIND, std::ptr::null_mut(), Some(scripted), &mut out), INVALID);
            assert_eq!(sb_flat_hash_run(FIND, ctx, None, &mut out), INVALID);
            assert_eq!(sb_flat_hash_run(FIND, ctx, Some(scripted), std::ptr::null_mut()), INVALID);
            let mut bytes = [0u8; 64];
            let aligned = (bytes.as_mut_ptr() as usize).wrapping_add(7) & !7;
            let misaligned = aligned.wrapping_add(1) as *mut SbFlatHashReply;
            assert_eq!(sb_flat_hash_run(SCAN, ctx, Some(scripted), misaligned), INVALID);
        }
        assert_eq!(out, UNCHANGED);
        assert!(!host.bad);
        assert_eq!(host.next, 0);
        assert_eq!(before, [sb_flat_hash_count(0, FIND), sb_flat_hash_count(0, SCAN), sb_flat_hash_count(0, INSERT)]);
        assert_eq!(sb_flat_hash_count(2, FIND), 0);
        assert_eq!(sb_flat_hash_count(0, COUNT as u32), 0);
        assert_eq!(sb_flat_hash_count(1, u32::MAX), 0);
    }
    #[test]
    fn accepted_entries_count_once_including_host_error_and_thread_total() {
        let before = sb_flat_hash_count(0, FIND);
        execute(FIND, &[s(SIZE, 0, 0)], OK, MISS);
        execute(FIND, &[Step { op: SIZE, arg: 0, value: 0, status: 1 }], HOST_ERROR, UNCHANGED);
        assert_eq!(sb_flat_hash_count(0, FIND), before.wrapping_add(2));
        let total = sb_flat_hash_count(1, SCAN);
        std::thread::spawn(|| {
            assert_eq!(sb_flat_hash_count(0, SCAN), 0);
            execute(SCAN, &[s(SCAN_EMPTY, 0, 0)], OK, MISS);
            assert_eq!(sb_flat_hash_count(0, SCAN), 1);
        }).join().unwrap();
        // Other tests may concurrently add aggregate entries, never remove them.
        assert!(sb_flat_hash_count(1, SCAN).wrapping_sub(total) >= 1);
    }
    #[test]
    fn tls_counter_wraps() {
        COUNTS.with(|cell| {
            let saved = cell.get();
            let mut near_wrap = saved;
            near_wrap[FIND as usize] = u64::MAX;
            cell.set(near_wrap);
            execute(FIND, &[s(SIZE, 0, 0)], OK, MISS);
            let wrapped = sb_flat_hash_count(0, FIND);
            cell.set(saved);
            assert_eq!(wrapped, 0);
        });
    }
    #[test]
    fn same_context_reentry_has_independent_frames_and_counts() {
        struct Reentry { entered: bool, bad: bool }
        unsafe extern "C" fn nested(ctx: *mut c_void, op: u32, arg: usize, out: *mut usize) -> u32 {
            let state = ctx.cast::<Reentry>();
            if op == SIZE && !(*state).entered && arg == 0 {
                (*state).entered = true;
                let mut reply = UNCHANGED;
                // No Rust borrow of state spans this nested call on the same context.
                let status = sb_flat_hash_run(SCAN, ctx, Some(nested), &mut reply);
                if status != OK || reply != MISS {
                    (*state).bad = true;
                    return 1;
                }
            } else if op != SCAN_EMPTY || !(*state).entered || arg != 0 {
                (*state).bad = true;
                return 1;
            }
            out.write(0);
            0
        }
        let before = [sb_flat_hash_count(0, FIND), sb_flat_hash_count(0, SCAN)];
        let mut state = Reentry { entered: false, bad: false };
        let mut out = UNCHANGED;
        let status = unsafe {
            sb_flat_hash_run(FIND, (&mut state as *mut Reentry).cast(), Some(nested), &mut out)
        };
        assert_eq!(status, OK);
        assert_eq!(out, MISS);
        assert!(state.entered && !state.bad);
        assert_eq!(sb_flat_hash_count(0, FIND), before[0].wrapping_add(1));
        assert_eq!(sb_flat_hash_count(0, SCAN), before[1].wrapping_add(1));
    }
    #[test]
    fn reply_matches_native_size_t_u32_layout() {
        use std::mem::{align_of, offset_of, size_of};
        assert_eq!(offset_of!(SbFlatHashReply, index), 0);
        assert_eq!(offset_of!(SbFlatHashReply, found), size_of::<usize>());
        assert_eq!(align_of::<SbFlatHashReply>(), align_of::<usize>());
        match size_of::<usize>() {
            8 => assert_eq!(size_of::<SbFlatHashReply>(), 16),
            4 => assert_eq!(size_of::<SbFlatHashReply>(), 8),
            _ => panic!("unsupported native size_t width"),
        }
    }
}
