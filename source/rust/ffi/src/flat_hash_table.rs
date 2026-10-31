//! FlatHashTable control policy; native storage and value lifetimes stay native.
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
const ERASE: u32 = 3;
const ERASE_RANGE: u32 = 4;
const CLEAR: u32 = 5;
const EQUAL: u32 = 6;
const COMPARE: u32 = 7;
const RESERVE: u32 = 8;
const GROW_PLAN: u32 = 9;
const GROW_WORK: u32 = 10;
const REINSERT: u32 = 11;
const BEGIN: u32 = 12;
const COUNT: usize = 13;
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
const REQUEST: u32 = 13;
const SHIFT: u32 = 14;
const CLEAR_BUCKET: u32 = 15;
const DECREMENT_FILLED: u32 = 16;
const ITER_MORE: u32 = 17;
const ERASE_ITER: u32 = 18;
const RESET_FILLED: u32 = 19;
const SIZES_EQUAL: u32 = 20;
const ENTER_COMPARE: u32 = 21;
const NOT_EQUAL: u32 = 22;
const ADVANCE_BOTH: u32 = 23;
const FILLED_COUNT: u32 = 24;
const CALL_GROW: u32 = 25;
const MIN_CAPACITY: u32 = 26;
const TOO_FULL: u32 = 27;
const SWAP_STORAGE: u32 = 28;
const RESIZE_BUCKETS: u32 = 29;
const VECTOR_CAPACITY: u32 = 30;
const SET_END: u32 = 31;
const ENTER_REINSERT: u32 = 32;
const INSERT_VALUE: u32 = 33;
const ADVANCE_OLD: u32 = 34;
const OLD_VALUE: u32 = 35;
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
    if (matches!(op, LOAD | EQUALS | SCAN_EMPTY | CAPACITY_NEEDED
            | ITER_MORE | SIZES_EQUAL | ENTER_COMPARE | NOT_EQUAL | TOO_FULL | OLD_VALUE) && value > 1)
        || (matches!(op, SCAN_ADVANCE | ENSURE_CAPACITY | SWAP_VALUE
            | SET_FILLED | INCREMENT_FILLED | SHIFT | CLEAR_BUCKET
            | DECREMENT_FILLED | ERASE_ITER | RESET_FILLED | ADVANCE_BOTH
            | CALL_GROW | SWAP_STORAGE | RESIZE_BUCKETS | SET_END
            | ENTER_REINSERT | INSERT_VALUE | ADVANCE_OLD) && value != 0)
    {
        return Err(INVALID);
    }
    Ok(value)
}

unsafe fn insert(ctx: *mut c_void, leaf: Leaf) -> Result<SbFlatHashReply, u32> {
    // Keep fast-math arithmetic native; ENSURE_CAPACITY reenters via the host.
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
    match mode {
        INSERT => return insert(ctx, leaf),
        RESERVE => {
            let requested = invoke(ctx, leaf, REQUEST, 0)?;
            let filled = invoke(ctx, leaf, FILLED_COUNT, 0)?;
            if requested > filled {
                invoke(ctx, leaf, CALL_GROW, requested.wrapping_sub(filled))?;
            }
            return Ok(MISS);
        }
        GROW_PLAN => {
            if invoke(ctx, leaf, REQUEST, 0)? == 0 {
                return Ok(MISS);
            }
            let count = invoke(ctx, leaf, SIZE, 0)?;
            let mut new_size = if count != 0 {
                count.wrapping_sub(1)
            } else {
                invoke(ctx, leaf, MIN_CAPACITY, 0)?
            };
            // Native fast-math evaluates the load factor; Rust only branches.
            while invoke(ctx, leaf, TOO_FULL, new_size)? != 0 {
                new_size = new_size.wrapping_mul(2);
            }
            if new_size == invoke(ctx, leaf, SIZE, 0)?.wrapping_sub(1) {
                return Ok(MISS);
            }
            return Ok(SbFlatHashReply { index: new_size, found: 1 });
        }
        GROW_WORK => {
            // Host creates oldBuckets only after GROW_PLAN chose a change,
            // retaining its lexical scope through this entire nested call.
            let mut new_size = invoke(ctx, leaf, REQUEST, 0)?;
            invoke(ctx, leaf, SWAP_STORAGE, 0)?;
            invoke(ctx, leaf, RESIZE_BUCKETS, new_size.wrapping_add(1))?;
            while invoke(ctx, leaf, VECTOR_CAPACITY, 0)? > new_size.wrapping_mul(2).wrapping_add(1) {
                new_size = new_size.wrapping_mul(2);
                invoke(ctx, leaf, RESIZE_BUCKETS, new_size.wrapping_add(1))?;
            }
            invoke(ctx, leaf, SET_END, new_size)?;
            invoke(ctx, leaf, RESET_FILLED, 0)?;
            // Only now may native old-vector iterators be initialized.
            invoke(ctx, leaf, ENTER_REINSERT, 0)?;
            return Ok(MISS);
        }
        REINSERT => {
            while invoke(ctx, leaf, ITER_MORE, 0)? != 0 {
                if invoke(ctx, leaf, OLD_VALUE, 0)? != 0 {
                    invoke(ctx, leaf, INSERT_VALUE, 0)?;
                }
                invoke(ctx, leaf, ADVANCE_OLD, 0)?;
            }
            return Ok(MISS);
        }
        BEGIN => {
            let present = invoke(ctx, leaf, SIZE, 0)? != 0;
            return Ok(SbFlatHashReply { index: 0, found: present as u32 });
        }
        ERASE => {
            // REQUEST is the already-computed native pos.current - data index.
            let start = invoke(ctx, leaf, REQUEST, 0)?;
            let mut current = start;
            loop {
                let mask = invoke(ctx, leaf, SIZE, 0)?.wrapping_sub(2);
                let next = current.wrapping_add(1) & mask;
                if invoke(ctx, leaf, LOAD, next)? == 0 {
                    break;
                }
                let next_hash = invoke(ctx, leaf, ACTIVE_HASH, 0)?;
                let mask = invoke(ctx, leaf, SIZE, 0)?.wrapping_sub(2);
                let next_error = next.wrapping_sub(next_hash) & mask;
                if next_error == 0 {
                    break;
                }
                // Native hash assignment precedes throwing Value move assignment.
                // Only a successful SHIFT advances either current pointer/index.
                invoke(ctx, leaf, SHIFT, 0)?;
                current = next;
            }
            invoke(ctx, leaf, CLEAR_BUCKET, current)?;
            invoke(ctx, leaf, DECREMENT_FILLED, 0)?;
            return Ok(SbFlatHashReply { index: start, found: 0 });
        }
        ERASE_RANGE => {
            while invoke(ctx, leaf, ITER_MORE, 0)? != 0 {
                invoke(ctx, leaf, ERASE_ITER, 0)?;
            }
            return Ok(MISS);
        }
        CLEAR => {
            if invoke(ctx, leaf, SIZE, 0)? == 0 {
                return Ok(MISS);
            }
            let mut index = 0usize;
            while index < invoke(ctx, leaf, SIZE, 0)?.wrapping_sub(1) {
                invoke(ctx, leaf, CLEAR_BUCKET, index)?;
                index = index.wrapping_add(1);
            }
            invoke(ctx, leaf, RESET_FILLED, 0)?;
            return Ok(MISS);
        }
        EQUAL => {
            if invoke(ctx, leaf, SIZES_EQUAL, 0)? == 0 {
                return Ok(MISS);
            }
            // Native ENTER_COMPARE owns named i, j, e through nested COMPARE.
            let equal = invoke(ctx, leaf, ENTER_COMPARE, 0)?;
            return Ok(SbFlatHashReply { index: 0, found: equal as u32 });
        }
        COMPARE => {
            while invoke(ctx, leaf, ITER_MORE, 0)? != 0 {
                if invoke(ctx, leaf, NOT_EQUAL, 0)? != 0 {
                    return Ok(MISS);
                }
                invoke(ctx, leaf, ADVANCE_BOTH, 0)?;
            }
            return Ok(SbFlatHashReply { index: 0, found: 1 });
        }
        _ => {}
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

/// Executes table control, publishing a reply only after success.
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
        let before: [u64; COUNT] = std::array::from_fn(|mode| sb_flat_hash_count(0, mode as u32));
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
        assert_eq!(before, std::array::from_fn(|mode| sb_flat_hash_count(0, mode as u32)));
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
    fn erase_absent() -> Vec<Step> {
        vec![s(REQUEST, 0, 3), s(SIZE, 0, 9), s(LOAD, 4, 0),
            s(CLEAR_BUCKET, 3, 0), s(DECREMENT_FILLED, 0, 0)]
    }
    fn erase_home() -> Vec<Step> {
        vec![s(REQUEST, 0, 3), s(SIZE, 0, 9), s(LOAD, 4, 1),
            s(ACTIVE_HASH, 0, 4), s(SIZE, 0, 9),
            s(CLEAR_BUCKET, 3, 0), s(DECREMENT_FILLED, 0, 0)]
    }
    fn erase_shifts() -> Vec<Step> {
        vec![s(REQUEST, 0, 7), s(SIZE, 0, 9), s(LOAD, 0, 1),
            // Raw 7 (without FILLED) still has distance 1 after wrapping.
            s(ACTIVE_HASH, 0, 7), s(SIZE, 0, 9), s(SHIFT, 0, 0),
            s(SIZE, 0, 9), s(LOAD, 1, 1), s(ACTIVE_HASH, 0, usize::MAX),
            s(SIZE, 0, 9), s(SHIFT, 0, 0),
            s(SIZE, 0, 9), s(LOAD, 2, 0),
            s(CLEAR_BUCKET, 1, 0), s(DECREMENT_FILLED, 0, 0)]
    }
    fn clear_fresh() -> Vec<Step> {
        vec![s(SIZE, 0, 3), s(SIZE, 0, 3), s(CLEAR_BUCKET, 0, 0),
            // Destructor/reentry changes the native size; condition must reread.
            s(SIZE, 0, 4), s(CLEAR_BUCKET, 1, 0),
            s(SIZE, 0, 4), s(CLEAR_BUCKET, 2, 0),
            s(SIZE, 0, 2), s(RESET_FILLED, 0, 0)]
    }
    fn compare_equal() -> Vec<Step> {
        vec![s(ITER_MORE, 0, 1), s(NOT_EQUAL, 0, 0), s(ADVANCE_BOTH, 0, 0),
            s(ITER_MORE, 0, 1), s(NOT_EQUAL, 0, 0), s(ADVANCE_BOTH, 0, 0),
            s(ITER_MORE, 0, 0)]
    }
    fn new_cases() -> Vec<(u32, Vec<Step>, SbFlatHashReply)> {
        vec![
            (ERASE, erase_absent(), SbFlatHashReply { index: 3, found: 0 }),
            (ERASE, erase_home(), SbFlatHashReply { index: 3, found: 0 }),
            (ERASE, erase_shifts(), SbFlatHashReply { index: 7, found: 0 }),
            (ERASE_RANGE, vec![s(ITER_MORE, 0, 0)], MISS),
            (ERASE_RANGE, vec![s(ITER_MORE, 0, 1), s(ERASE_ITER, 0, 0),
                s(ITER_MORE, 0, 1), s(ERASE_ITER, 0, 0), s(ITER_MORE, 0, 0)], MISS),
            (CLEAR, vec![s(SIZE, 0, 0)], MISS),
            (CLEAR, vec![s(SIZE, 0, 1), s(SIZE, 0, 1), s(RESET_FILLED, 0, 0)], MISS),
            (CLEAR, clear_fresh(), MISS),
            (EQUAL, vec![s(SIZES_EQUAL, 0, 0)], MISS),
            (EQUAL, vec![s(SIZES_EQUAL, 0, 1), s(ENTER_COMPARE, 0, 0)], MISS),
            (EQUAL, vec![s(SIZES_EQUAL, 0, 1), s(ENTER_COMPARE, 0, 1)],
                SbFlatHashReply { index: 0, found: 1 }),
            (COMPARE, vec![s(ITER_MORE, 0, 0)], SbFlatHashReply { index: 0, found: 1 }),
            (COMPARE, vec![s(ITER_MORE, 0, 1), s(NOT_EQUAL, 0, 1)], MISS),
            (COMPARE, compare_equal(), SbFlatHashReply { index: 0, found: 1 }),
        ]
    }
    #[test]
    fn erase_clear_range_and_order_sensitive_compare_scripts() {
        for (mode, steps, reply) in new_cases() {
            execute(mode, &steps, OK, reply);
        }
        // A next_error > 0 -> == 0 mutant must fail both required-shift and
        // home-bucket-stop scripts; don't weaken these into final-state checks.
        let mut v = erase_home();
        v[3].value = FILLED | 4;
        execute(ERASE, &v, OK, SbFlatHashReply { index: 3, found: 0 });
        // Read the distance mask AFTER ACTIVE_HASH; using the first mask would
        // wrongly treat raw hash 12 as home at next=4 and omit SHIFT.
        execute(ERASE, &[s(REQUEST, 0, 3), s(SIZE, 0, 9), s(LOAD, 4, 1),
            s(ACTIVE_HASH, 0, 12), s(SIZE, 0, 17), s(SHIFT, 0, 0),
            s(SIZE, 0, 17), s(LOAD, 5, 0), s(CLEAR_BUCKET, 4, 0),
            s(DECREMENT_FILLED, 0, 0)], OK, SbFlatHashReply { index: 3, found: 0 });
        // Start and SIZE are unrestricted words, with no validity repair.
        execute(ERASE, &[s(REQUEST, 0, usize::MAX), s(SIZE, 0, 0),
            s(LOAD, 0, 0), s(CLEAR_BUCKET, usize::MAX, 0),
            s(DECREMENT_FILLED, 0, 0)], OK,
            SbFlatHashReply { index: usize::MAX, found: 0 });
    }
    #[test]
    fn clear_empty_preserves_odd_filled_count_and_zero_fresh_size_wraps() {
        struct Empty { filled: usize, calls: usize }
        unsafe extern "C" fn empty(ctx: *mut c_void, op: u32, arg: usize, out: *mut usize) -> u32 {
            let state = &mut *ctx.cast::<Empty>();
            state.calls = state.calls.wrapping_add(1);
            if op == RESET_FILLED { state.filled = 0; }
            if op != SIZE || arg != 0 { return 1; }
            out.write(0);
            0
        }
        let mut state = Empty { filled: 42, calls: 0 };
        let mut out = UNCHANGED;
        let status = unsafe { sb_flat_hash_run(CLEAR, (&mut state as *mut Empty).cast(), Some(empty), &mut out) };
        assert_eq!(status, OK);
        assert_eq!(out, MISS);
        assert_eq!((state.filled, state.calls), (42, 1));
        // After the initial guard, zero SIZE means usize::MAX as loop bound,
        // not a second empty-table early return or invariant repair.
        execute(CLEAR, &[s(SIZE, 0, 1), s(SIZE, 0, 0),
            s(CLEAR_BUCKET, 0, 0), s(SIZE, 0, 1), s(RESET_FILLED, 0, 0)], OK, MISS);
    }
    #[test]
    fn new_modes_every_callback_failure_and_malformed_reply_stops() {
        for (mode, steps, _) in new_cases() {
            for (i, step) in steps.iter().enumerate() {
                for status in [1, 2, u32::MAX] {
                    let mut v = steps[..=i].to_vec();
                    v[i].status = status;
                    v[i].value = usize::MAX;
                    execute(mode, &v, HOST_ERROR, UNCHANGED);
                }
                let predicate = matches!(step.op, LOAD | ITER_MORE | SIZES_EQUAL | ENTER_COMPARE | NOT_EQUAL);
                let void = matches!(step.op, SHIFT | CLEAR_BUCKET | DECREMENT_FILLED
                    | ERASE_ITER | RESET_FILLED | ADVANCE_BOTH);
                if predicate || void {
                    for value in [2, usize::MAX] {
                        let mut v = steps[..=i].to_vec();
                        v[i].value = value;
                        execute(mode, &v, INVALID, UNCHANGED);
                    }
                }
                if void {
                    let mut v = steps[..=i].to_vec();
                    v[i].value = 1;
                    execute(mode, &v, INVALID, UNCHANGED);
                }
            }
        }
    }
    #[test]
    fn shift_failure_keeps_native_hash_prefix_without_clear_or_decrement() {
        struct Prefix { host: Host, hash: usize, current: usize, moves: usize }
        unsafe extern "C" fn prefix_leaf(ctx: *mut c_void, op: u32, arg: usize, out: *mut usize) -> u32 {
            let state = ctx.cast::<Prefix>();
            let status = scripted(std::ptr::addr_of_mut!((*state).host).cast(), op, arg, out);
            if op == SHIFT {
                // Model the native rollback-free hash write before move throws.
                (*state).hash = 7;
                (*state).moves = (*state).moves.wrapping_add(1);
                if status == 0 {
                    (*state).current = 0;
                }
            }
            status
        }
        let mut steps = erase_shifts();
        let fail = steps.iter().position(|step| step.op == SHIFT).unwrap();
        steps.truncate(fail + 1);
        steps[fail].status = 1;
        let mut state = Prefix { host: Host { steps, next: 0, bad: false }, hash: 12, current: 7, moves: 0 };
        let mut out = UNCHANGED;
        let status = unsafe { sb_flat_hash_run(ERASE, (&mut state as *mut Prefix).cast(), Some(prefix_leaf), &mut out) };
        assert_eq!(status, HOST_ERROR);
        assert_eq!(out, UNCHANGED);
        assert_eq!((state.hash, state.current, state.moves), (7, 7, 1));
        assert!(!state.host.bad);
        assert_eq!(state.host.next, state.host.steps.len());
    }
    #[test]
    fn equal_nested_compare_scope_order_and_early_exit() {
        struct Nested { outer: Host, inner: Host, live: bool, inner_active: bool, nested_status: u32 }
        unsafe extern "C" fn nested_equal(ctx: *mut c_void, op: u32, arg: usize, out: *mut usize) -> u32 {
            let state = ctx.cast::<Nested>();
            if (*state).inner_active {
                if !(*state).live { return 1; }
                return scripted(std::ptr::addr_of_mut!((*state).inner).cast(), op, arg, out);
            }
            let status = scripted(std::ptr::addr_of_mut!((*state).outer).cast(), op, arg, out);
            if status != 0 { return status; }
            if op == ENTER_COMPARE {
                (*state).live = true;
                (*state).inner_active = true;
                let mut reply = UNCHANGED;
                let status = sb_flat_hash_run(COMPARE, ctx, Some(nested_equal), &mut reply);
                (*state).nested_status = status;
                (*state).inner_active = false;
                (*state).live = false;
                if status != OK { return 1; }
                out.write(reply.found as usize);
            }
            0
        }
        let mut cases = vec![(vec![s(ITER_MORE, 0, 0)], 1), (compare_equal(), 1),
            // Same members in another order are unequal at the first Value !=.
            (vec![s(ITER_MORE, 0, 1), s(NOT_EQUAL, 0, 1)], 0)];
        let mut later_mismatch = compare_equal();
        later_mismatch.truncate(5);
        later_mismatch[4].value = 1;
        cases.push((later_mismatch, 0));
        for (inner, found) in cases {
            let mut state = Nested {
                outer: Host { steps: vec![s(SIZES_EQUAL, 0, 1), s(ENTER_COMPARE, 0, 0)], next: 0, bad: false },
                inner: Host { steps: inner, next: 0, bad: false },
                live: false, inner_active: false, nested_status: u32::MAX,
            };
            let before = [sb_flat_hash_count(0, EQUAL), sb_flat_hash_count(0, COMPARE)];
            let mut out = UNCHANGED;
            let status = unsafe { sb_flat_hash_run(EQUAL, (&mut state as *mut Nested).cast(), Some(nested_equal), &mut out) };
            assert_eq!(status, OK);
            assert_eq!(out, SbFlatHashReply { index: 0, found });
            assert_eq!(state.nested_status, OK);
            assert!(!state.live && !state.inner_active);
            for host in [&state.outer, &state.inner] {
                assert!(!host.bad);
                assert_eq!(host.next, host.steps.len());
            }
            assert_eq!(sb_flat_hash_count(0, EQUAL), before[0].wrapping_add(1));
            assert_eq!(sb_flat_hash_count(0, COMPARE), before[1].wrapping_add(1));
        }
    }
    #[test]
    fn all_thirteen_modes_count_and_wrap_independently() {
        COUNTS.with(|cell| {
            let saved = cell.get();
            cell.set([u64::MAX; COUNT]);
            for mode in 0..COUNT as u32 {
                // Every accepted entry counts even if its first callback fails.
                let op = match mode {
                    FIND | CLEAR | BEGIN => SIZE, SCAN => SCAN_EMPTY, INSERT => CAPACITY_NEEDED,
                    ERASE | RESERVE | GROW_PLAN | GROW_WORK => REQUEST,
                    ERASE_RANGE | COMPARE | REINSERT => ITER_MORE,
                    EQUAL => SIZES_EQUAL, _ => unreachable!(),
                };
                execute(mode, &[Step { op, arg: 0, value: usize::MAX, status: 1 }], HOST_ERROR, UNCHANGED);
                assert_eq!(sb_flat_hash_count(0, mode), 0);
            }
            assert_eq!(cell.get(), [0; COUNT]);
            cell.set(saved);
        });
    }
    fn growth_cases() -> Vec<(u32, Vec<Step>, SbFlatHashReply)> {
        vec![
            (RESERVE, vec![s(REQUEST, 0, 0), s(FILLED_COUNT, 0, 7)], MISS),
            (RESERVE, vec![s(REQUEST, 0, 7), s(FILLED_COUNT, 0, 7)], MISS),
            (RESERVE, vec![s(REQUEST, 0, 12), s(FILLED_COUNT, 0, 7), s(CALL_GROW, 5, 0)], MISS),
            (GROW_PLAN, vec![s(REQUEST, 0, 0)], MISS),
            (GROW_PLAN, vec![s(REQUEST, 0, 1), s(SIZE, 0, 9),
                s(TOO_FULL, 8, 0), s(SIZE, 0, 9)], MISS),
            (GROW_PLAN, vec![s(REQUEST, 0, 1), s(SIZE, 0, 0), s(MIN_CAPACITY, 0, 8),
                s(TOO_FULL, 8, 0), s(SIZE, 0, 0)], SbFlatHashReply { index: 8, found: 1 }),
            // TOO_FULL inversion or multiplying by four breaks the exact trace.
            (GROW_PLAN, vec![s(REQUEST, 0, 19), s(SIZE, 0, 9), s(TOO_FULL, 8, 1),
                s(TOO_FULL, 16, 1), s(TOO_FULL, 32, 0), s(SIZE, 0, 9)],
                SbFlatHashReply { index: 32, found: 1 }),
            // Comparison rereads SIZE rather than caching the initial count.
            (GROW_PLAN, vec![s(REQUEST, 0, 1), s(SIZE, 0, 9), s(TOO_FULL, 8, 1),
                s(TOO_FULL, 16, 0), s(SIZE, 0, 17)], MISS),
            (GROW_WORK, vec![s(REQUEST, 0, 8), s(SWAP_STORAGE, 0, 0),
                s(RESIZE_BUCKETS, 9, 0), s(VECTOR_CAPACITY, 0, 17),
                s(SET_END, 8, 0), s(RESET_FILLED, 0, 0), s(ENTER_REINSERT, 0, 0)], MISS),
            // Strict >, repeated fresh capacities and element-count arguments.
            (GROW_WORK, oversized_growth(), MISS),
            (REINSERT, vec![s(ITER_MORE, 0, 0)], MISS),
            (REINSERT, old_entries(), MISS),
            (BEGIN, vec![s(SIZE, 0, 0)], MISS),
            (BEGIN, vec![s(SIZE, 0, 1)], SbFlatHashReply { index: 0, found: 1 }),
            (BEGIN, vec![s(SIZE, 0, usize::MAX)], SbFlatHashReply { index: 0, found: 1 }),
        ]
    }
    fn oversized_growth() -> Vec<Step> {
        vec![s(REQUEST, 0, 8), s(SWAP_STORAGE, 0, 0), s(RESIZE_BUCKETS, 9, 0),
            s(VECTOR_CAPACITY, 0, 66), s(RESIZE_BUCKETS, 17, 0),
            s(VECTOR_CAPACITY, 0, 66), s(RESIZE_BUCKETS, 33, 0),
            s(VECTOR_CAPACITY, 0, 65), s(SET_END, 32, 0),
            s(RESET_FILLED, 0, 0), s(ENTER_REINSERT, 0, 0)]
    }
    fn old_entries() -> Vec<Step> {
        vec![s(ITER_MORE, 0, 1), s(OLD_VALUE, 0, 0), s(ADVANCE_OLD, 0, 0),
            s(ITER_MORE, 0, 1), s(OLD_VALUE, 0, 1), s(INSERT_VALUE, 0, 0), s(ADVANCE_OLD, 0, 0),
            s(ITER_MORE, 0, 1), s(OLD_VALUE, 0, 0), s(ADVANCE_OLD, 0, 0), s(ITER_MORE, 0, 0)]
    }
    #[test]
    fn reserve_plan_work_reinsert_and_begin_exact_scripts() {
        for (mode, steps, reply) in growth_cases() {
            execute(mode, &steps, OK, reply);
        }
    }
    #[test]
    fn growth_words_wrap_without_repairs_or_rust_float() {
        execute(RESERVE, &[s(REQUEST, 0, usize::MAX), s(FILLED_COUNT, 0, 0),
            s(CALL_GROW, usize::MAX, 0)], OK, MISS);
        // Arbitrary native MIN_CAPACITY and wrapping doubling are intentional.
        execute(GROW_PLAN, &[s(REQUEST, 0, usize::MAX), s(SIZE, 0, 0),
            s(MIN_CAPACITY, 0, FILLED), s(TOO_FULL, FILLED, 1),
            s(TOO_FULL, 0, 0), s(SIZE, 0, 0)], OK, SbFlatHashReply { index: 0, found: 1 });
        execute(GROW_PLAN, &[s(REQUEST, 0, 1), s(SIZE, 0, 1),
            s(TOO_FULL, 0, 0), s(SIZE, 0, 1)], OK, MISS);
        // Final SIZE subtraction also wraps rather than validating zero.
        execute(GROW_PLAN, &[s(REQUEST, 0, 1), s(SIZE, 0, 0),
            s(MIN_CAPACITY, 0, usize::MAX), s(TOO_FULL, usize::MAX, 0), s(SIZE, 0, 0)], OK, MISS);
        // newSize+1 and newSize*2+1 wrap; capacity 1 equals the wrapped bound.
        execute(GROW_WORK, &[s(REQUEST, 0, FILLED), s(SWAP_STORAGE, 0, 0),
            s(RESIZE_BUCKETS, FILLED.wrapping_add(1), 0), s(VECTOR_CAPACITY, 0, 2),
            s(RESIZE_BUCKETS, 1, 0), s(VECTOR_CAPACITY, 0, 1),
            s(SET_END, 0, 0), s(RESET_FILLED, 0, 0), s(ENTER_REINSERT, 0, 0)], OK, MISS);
        execute(GROW_WORK, &[s(REQUEST, 0, usize::MAX), s(SWAP_STORAGE, 0, 0),
            s(RESIZE_BUCKETS, 0, 0), s(VECTOR_CAPACITY, 0, usize::MAX),
            s(SET_END, usize::MAX, 0), s(RESET_FILLED, 0, 0), s(ENTER_REINSERT, 0, 0)], OK, MISS);
    }
    #[test]
    fn growth_every_callback_error_and_malformed_reply_stops_without_output() {
        for (mode, steps, _) in growth_cases() {
            for (i, step) in steps.iter().enumerate() {
                for status in [1, 2, u32::MAX] {
                    let mut v = steps[..=i].to_vec();
                    v[i].status = status;
                    v[i].value = usize::MAX;
                    execute(mode, &v, HOST_ERROR, UNCHANGED);
                }
                let predicate = matches!(step.op, TOO_FULL | OLD_VALUE | ITER_MORE);
                let void = matches!(step.op, CALL_GROW | SWAP_STORAGE | RESIZE_BUCKETS
                    | SET_END | RESET_FILLED | ENTER_REINSERT | INSERT_VALUE | ADVANCE_OLD);
                if predicate || void {
                    for value in [2, usize::MAX] {
                        let mut v = steps[..=i].to_vec();
                        v[i].value = value;
                        execute(mode, &v, INVALID, UNCHANGED);
                    }
                }
                if void {
                    let mut v = steps[..=i].to_vec();
                    v[i].value = 1;
                    execute(mode, &v, INVALID, UNCHANGED);
                }
            }
        }
    }
    #[test]
    fn grow_work_nested_reinsert_insert_keeps_scopes_and_error_prefixes() {
        struct Rehash {
            work: Host, old: Host, insert: Host, level: u32,
            swapped: bool, sentinel: bool, reset: bool, iterators: bool,
            inserted: bool, nested_status: u32,
        }
        unsafe extern "C" fn rehash(ctx: *mut c_void, op: u32, arg: usize, out: *mut usize) -> u32 {
            let state = ctx.cast::<Rehash>();
            let host = match (*state).level {
                0 => std::ptr::addr_of_mut!((*state).work),
                1 => std::ptr::addr_of_mut!((*state).old),
                2 => std::ptr::addr_of_mut!((*state).insert),
                _ => return 1,
            };
            let status = scripted(host.cast(), op, arg, out);
            if status != 0 { return status; }
            match op {
                SWAP_STORAGE => (*state).swapped = true,
                RESIZE_BUCKETS => if !(*state).swapped || (*state).iterators { return 1; },
                SET_END => (*state).sentinel = true,
                RESET_FILLED => {
                    if !(*state).sentinel { return 1; }
                    (*state).reset = true;
                }
                ENTER_REINSERT => {
                    if !(*state).reset || !(*state).sentinel { return 1; }
                    (*state).iterators = true;
                    (*state).level = 1;
                    let mut reply = UNCHANGED;
                    let status = sb_flat_hash_run(REINSERT, ctx, Some(rehash), &mut reply);
                    (*state).level = 0;
                    (*state).iterators = false;
                    (*state).nested_status = status;
                    if status != OK {
                        if reply != UNCHANGED { return 2; }
                        return 1;
                    }
                    if reply != MISS { return 1; }
                }
                ITER_MORE | OLD_VALUE | ADVANCE_OLD => if !(*state).iterators { return 1; },
                INSERT_VALUE => {
                    if !(*state).iterators { return 1; }
                    (*state).level = 2;
                    let mut reply = UNCHANGED;
                    let status = sb_flat_hash_run(INSERT, ctx, Some(rehash), &mut reply);
                    (*state).level = 1;
                    if status != OK {
                        if reply != UNCHANGED { return 2; }
                        return 1;
                    }
                    if reply != (SbFlatHashReply { index: 12, found: 0 }) { return 1; }
                    (*state).inserted = true;
                }
                _ => {}
            }
            0
        }
        let make_host = |steps| Host { steps, next: 0, bad: false };
        let insertion = insert_new(false);
        // Exercise every nested INSERT failure, not just the outer callback.
        for fail in 0..=insertion.len() {
            let success = fail == insertion.len();
            let mut inner = insertion.clone();
            if !success {
                inner.truncate(fail + 1);
                inner[fail].status = 1;
            }
            let mut old = old_entries();
            if !success {
                old.truncate(old.iter().position(|step| step.op == INSERT_VALUE).unwrap() + 1);
            }
            let mut state = Rehash {
                work: make_host(oversized_growth()), old: make_host(old), insert: make_host(inner),
                level: 0, swapped: false, sentinel: false, reset: false, iterators: false,
                inserted: false, nested_status: u32::MAX,
            };
            let before = [sb_flat_hash_count(0, GROW_WORK), sb_flat_hash_count(0, REINSERT),
                sb_flat_hash_count(0, INSERT)];
            let mut out = UNCHANGED;
            let status = unsafe { sb_flat_hash_run(GROW_WORK, (&mut state as *mut Rehash).cast(), Some(rehash), &mut out) };
            assert_eq!(status, if success { OK } else { HOST_ERROR });
            assert_eq!(out, if success { MISS } else { UNCHANGED });
            assert_eq!(state.nested_status, status);
            assert!(state.swapped && state.sentinel && state.reset);
            assert!(!state.iterators);
            assert_eq!(state.level, 0);
            assert_eq!(state.inserted, success);
            for host in [&state.work, &state.old, &state.insert] {
                assert!(!host.bad);
                assert_eq!(host.next, host.steps.len());
            }
            for (mode, count) in [GROW_WORK, REINSERT, INSERT].iter().copied().zip(before) {
                assert_eq!(sb_flat_hash_count(0, mode), count.wrapping_add(1));
            }
        }
    }
    #[test]
    fn resize_failure_preserves_swapped_storage_and_skips_later_effects() {
        struct AllocationPrefix { host: Host, swapped: bool, resized: usize, sentinel: bool, reset: bool }
        unsafe extern "C" fn allocation(ctx: *mut c_void, op: u32, arg: usize, out: *mut usize) -> u32 {
            let state = ctx.cast::<AllocationPrefix>();
            let status = scripted(std::ptr::addr_of_mut!((*state).host).cast(), op, arg, out);
            if status != 0 { return status; }
            match op {
                SWAP_STORAGE => (*state).swapped = true,
                RESIZE_BUCKETS => (*state).resized = arg,
                SET_END => (*state).sentinel = true,
                RESET_FILLED => (*state).reset = true,
                _ => {}
            }
            0
        }
        let steps = oversized_growth();
        for (fail, step) in steps.iter().enumerate() {
            if step.op != RESIZE_BUCKETS { continue; }
            let mut prefix = steps[..=fail].to_vec();
            prefix[fail].status = 1;
            let previous_size = steps[..fail].iter().rev()
                .find(|step| step.op == RESIZE_BUCKETS).map_or(0, |step| step.arg);
            let mut state = AllocationPrefix {
                host: Host { steps: prefix, next: 0, bad: false },
                swapped: false, resized: 0, sentinel: false, reset: false,
            };
            let mut out = UNCHANGED;
            let status = unsafe {
                sb_flat_hash_run(GROW_WORK, (&mut state as *mut AllocationPrefix).cast(), Some(allocation), &mut out)
            };
            assert_eq!(status, HOST_ERROR);
            assert_eq!(out, UNCHANGED);
            assert!(state.swapped);
            assert_eq!(state.resized, previous_size);
            assert!(!state.sentinel && !state.reset);
            assert!(!state.host.bad);
            assert_eq!(state.host.next, state.host.steps.len());
        }
    }
    #[test]
    fn growth_modes_success_and_error_count_on_acceptance() {
        for (mode, steps, reply) in growth_cases() {
            let before = sb_flat_hash_count(0, mode);
            let total = sb_flat_hash_count(1, mode);
            execute(mode, &steps, OK, reply);
            let mut failure = steps[..1].to_vec();
            failure[0].status = 1;
            execute(mode, &failure, HOST_ERROR, UNCHANGED);
            assert_eq!(sb_flat_hash_count(0, mode), before.wrapping_add(2));
            assert!(sb_flat_hash_count(1, mode).wrapping_sub(total) >= 2);
        }
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
