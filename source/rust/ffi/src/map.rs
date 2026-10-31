//! MapMixin control policy; typed values, expressions and iterator scopes stay native.
use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST_ERROR: u32 = 2;
const PANIC: u32 = 3;
const COLLECT: u32 = 0;
const FIRST: u32 = 1;
const FILTER: u32 = 2;
const REMOVE: u32 = 3;
const PRINT: u32 = 4;
const MERGE: u32 = 5;
const MERGE_ITEM: u32 = 6;
const EQUAL: u32 = 7;
const COMPARE: u32 = 8;
const ASSIGN: u32 = 9;
const COUNT: usize = 10;
const SELECT_COUNT: usize = 7;
const MORE: u32 = 0;
const ADVANCE: u32 = 1;
const APPEND: u32 = 2;
const MATCH: u32 = 3;
const ERASE: u32 = 4;
const FIRST_ELEMENT: u32 = 5;
const FIRST_PREFIX: u32 = 6;
const NEXT_PREFIX: u32 = 7;
const PRINT_VALUE: u32 = 8;
const MERGE_ITEM_OP: u32 = 9;
const INSERTED: u32 = 10;
const OVERWRITE: u32 = 11;
const UPDATE: u32 = 12;
const SELF: u32 = 13;
const SIZE_MISMATCH: u32 = 14;
const ENTER_COMPARE: u32 = 15;
const PAIR_MATCH: u32 = 16;
const CLEAR: u32 = 17;
const ENTER_COPY: u32 = 18;
const REQUIRED: u32 = 0;
const OPTIONAL: u32 = 1;
const DEFAULT: u32 = 2;
const SET: u32 = 3;
const ADD: u32 = 4;
const INSERT_SELECT: u32 = 5;
const REMOVE_SELECT: u32 = 6;
const VALUE: u32 = 0;
const THROW: u32 = 1;
const EMPTY: u32 = 2;
const DEFAULT_ACTION: u32 = 3;
const INSERT: u32 = 4;
const UPDATE_ACTION: u32 = 5;
const EXISTING: u32 = 6;
const NEW: u32 = 7;
const ERASE_ACTION: u32 = 8;
const MISS: u32 = 9;

pub type Leaf = unsafe extern "C" fn(*mut c_void, u32, *mut u32) -> u32;
static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static SELECT_TOTALS: [AtomicU64; SELECT_COUNT] = [const { AtomicU64::new(0) }; SELECT_COUNT];
thread_local! {
    static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) };
    static SELECT_COUNTS: Cell<[u64; SELECT_COUNT]> = const { Cell::new([0; SELECT_COUNT]) };
}

fn aligned(out: *mut u32) -> bool {
    !out.is_null() && (out as usize) % std::mem::align_of::<u32>() == 0
}

// Never hold a host borrow across a callback: the host may reenter this policy.
unsafe fn invoke(ctx: *mut c_void, leaf: Leaf, operation: u32) -> Result<u32, u32> {
    let mut response = 0;
    if leaf(ctx, operation, &mut response) != 0 {
        return Err(HOST_ERROR);
    }
    let boolean = matches!(operation, MORE | MATCH | FIRST_ELEMENT | MERGE_ITEM_OP | INSERTED | OVERWRITE
        | SELF | SIZE_MISMATCH | ENTER_COMPARE | PAIR_MATCH);
    if response > u32::from(boolean) {
        return Err(INVALID);
    }
    Ok(response)
}

unsafe fn run(mode: u32, ctx: *mut c_void, leaf: Leaf) -> Result<u32, u32> {
    if mode == MERGE_ITEM {
        if invoke(ctx, leaf, INSERTED)? != 0 { return Ok(1); }
        if invoke(ctx, leaf, OVERWRITE)? != 0 { invoke(ctx, leaf, UPDATE)?; }
        return Ok(0);
    }
    if mode == ASSIGN {
        if invoke(ctx, leaf, SELF)? != 0 { return Ok(0); }
        invoke(ctx, leaf, CLEAR)?;
        // Native range creation belongs AFTER clear, even for an empty source.
        invoke(ctx, leaf, ENTER_COPY)?;
        return Ok(0);
    }
    if mode == EQUAL {
        if invoke(ctx, leaf, SELF)? != 0 { return Ok(1); }
        if invoke(ctx, leaf, SIZE_MISMATCH)? != 0 { return Ok(0); }
        // Native range initialization occurs only after both guards finish.
        return invoke(ctx, leaf, ENTER_COMPARE);
    }
    let mut result = u32::from(matches!(mode, MERGE | COMPARE));
    while invoke(ctx, leaf, MORE)? != 0 {
        match mode {
            COLLECT => { invoke(ctx, leaf, APPEND)?; }
            FIRST => {
                if invoke(ctx, leaf, MATCH)? != 0 { return Ok(1); }
            }
            FILTER => {
                if invoke(ctx, leaf, MATCH)? != 0 { invoke(ctx, leaf, APPEND)?; }
            }
            REMOVE => {
                if invoke(ctx, leaf, MATCH)? != 0 {
                    // ERASE owns the WHOLE native erase(i++), even if erase throws.
                    invoke(ctx, leaf, ERASE)?;
                    result = 1;
                    continue;
                }
            }
            PRINT => {
                let first = invoke(ctx, leaf, FIRST_ELEMENT)? != 0;
                invoke(ctx, leaf, if first { FIRST_PREFIX } else { NEXT_PREFIX })?;
                invoke(ctx, leaf, PRINT_VALUE)?;
            }
            MERGE => {
                // A duplicate changes the result, never visitation of later items.
                if invoke(ctx, leaf, MERGE_ITEM_OP)? == 0 { result = 0; }
            }
            COMPARE => {
                if invoke(ctx, leaf, PAIR_MATCH)? == 0 { return Ok(0); }
            }
            _ => unreachable!(),
        }
        invoke(ctx, leaf, ADVANCE)?;
    }
    Ok(result)
}

fn count_entry(mode: usize, select: bool) {
    fn increment<const N: usize>(mode: usize, totals: &[AtomicU64; N], counts: &'static std::thread::LocalKey<Cell<[u64; N]>>) {
        totals[mode].fetch_add(1, Ordering::Relaxed);
        counts.with(|cell| {
            let mut values = cell.get();
            values[mode] = values[mode].wrapping_add(1);
            cell.set(values);
        });
    }
    if select { increment(mode, &SELECT_TOTALS, &SELECT_COUNTS); }
    else { increment(mode, &TOTALS, &COUNTS); }
}

/// Runs only loop/branch policy, without retaining context or native values.
///
/// # Safety
/// Context and callback must remain live for the call. Callbacks must satisfy
/// the header contract and must not unwind through this C ABI. Reentry is allowed.
/// Output must be live writable aligned u32 storage; numerical validation cannot
/// establish provenance or liveness. Errors leave output unchanged, not host state.
#[no_mangle]
pub unsafe extern "C" fn sb_map_run(mode: u32, ctx: *mut c_void, leaf: Option<Leaf>, out: *mut u32) -> u32 {
    if mode as usize >= COUNT || ctx.is_null() || leaf.is_none() || !aligned(out) {
        return INVALID;
    }
    catch_unwind(AssertUnwindSafe(|| {
        count_entry(mode as usize, false);
        match run(mode, ctx, leaf.unwrap()) {
            Ok(result) => { out.write(result); OK }
            Err(status) => status,
        }
    })).unwrap_or(PANIC)
}

/// Selects an action, leaving typed materialization and exception scopes native.
///
/// # Safety
/// Output must designate live writable aligned u32 storage. Only success writes.
#[no_mangle]
pub unsafe extern "C" fn sb_map_select(mode: u32, predicate: u32, out: *mut u32) -> u32 {
    if mode as usize >= SELECT_COUNT || predicate > 1 || !aligned(out) { return INVALID; }
    catch_unwind(AssertUnwindSafe(|| {
        count_entry(mode as usize, true);
        let yes = predicate != 0;
        let action = match mode {
            REQUIRED | ADD => if yes { VALUE } else { THROW },
            OPTIONAL => if yes { VALUE } else { EMPTY },
            DEFAULT => if yes { VALUE } else { DEFAULT_ACTION },
            SET => if yes { UPDATE_ACTION } else { INSERT },
            INSERT_SELECT => if yes { EXISTING } else { NEW },
            REMOVE_SELECT => if yes { ERASE_ACTION } else { MISS },
            _ => unreachable!(),
        };
        out.write(action);
        OK
    })).unwrap_or(PANIC)
}

/// Wrapping accepted loop entries on this thread, including callback failures.
#[no_mangle]
pub extern "C" fn sb_map_count(mode: u32) -> u64 {
    if mode as usize >= COUNT { return 0; }
    catch_unwind(|| COUNTS.with(|cell| cell.get()[mode as usize])).unwrap_or(0)
}

/// Wrapping accepted selections on this thread, independent of loop counts.
#[no_mangle]
pub extern "C" fn sb_map_select_count(mode: u32) -> u64 {
    if mode as usize >= SELECT_COUNT { return 0; }
    catch_unwind(|| SELECT_COUNTS.with(|cell| cell.get()[mode as usize])).unwrap_or(0)
}

/// Relaxed diagnostic totals; not a synchronized snapshot or consumer count.
#[no_mangle]
pub extern "C" fn sb_map_global_count(kind: u32, mode: u32) -> u64 {
    match kind {
        0 if (mode as usize) < COUNT => TOTALS[mode as usize].load(Ordering::Relaxed),
        1 if (mode as usize) < SELECT_COUNT => SELECT_TOTALS[mode as usize].load(Ordering::Relaxed),
        _ => 0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::VecDeque;

    #[derive(Clone, Copy, Debug)]
    struct Step(u32, u32, u32); // operation, response, host status
    struct Script { steps: VecDeque<Step>, seen: Vec<u32>, bad: bool }
    unsafe extern "C" fn scripted(ctx: *mut c_void, op: u32, out: *mut u32) -> u32 {
        let script = &mut *ctx.cast::<Script>();
        script.seen.push(op);
        if *out != 0 { script.bad = true; }
        match script.steps.pop_front() {
            Some(Step(expected, response, status)) if expected == op => {
                *out = response;
                status
            }
            _ => { script.bad = true; 99 }
        }
    }
    fn execute(mode: u32, steps: &[Step], status: u32, result: u32) {
        let mut script = Script { steps: steps.iter().copied().collect(), seen: vec![], bad: false };
        let mut output = 91;
        let before = sb_map_count(mode);
        let actual = unsafe { sb_map_run(mode, (&mut script as *mut Script).cast(), Some(scripted), &mut output) };
        assert_eq!(sb_map_count(mode), before.wrapping_add(1));
        assert_eq!((actual, output), (status, if status == OK { result } else { 91 }));
        assert!(!script.bad, "{:?}", script.seen);
        assert!(script.steps.is_empty(), "{:?}", script.steps);
        assert_eq!(script.seen, steps.iter().map(|s| s.0).collect::<Vec<_>>());
    }
    fn s(op: u32, response: u32) -> Step { Step(op, response, 0) }
    fn traces() -> Vec<(u32, Vec<Step>, u32)> {
        vec![
            (COLLECT, vec![s(MORE,1), s(APPEND,0), s(ADVANCE,0), s(MORE,0)], 0),
            (FIRST, vec![s(MORE,1), s(MATCH,0), s(ADVANCE,0), s(MORE,1), s(MATCH,1)], 1),
            (FILTER, vec![s(MORE,1), s(MATCH,0), s(ADVANCE,0), s(MORE,1), s(MATCH,1),
                s(APPEND,0), s(ADVANCE,0), s(MORE,0)], 0),
            (REMOVE, vec![s(MORE,1), s(MATCH,1), s(ERASE,0), s(MORE,1), s(MATCH,1),
                s(ERASE,0), s(MORE,1), s(MATCH,0), s(ADVANCE,0), s(MORE,0)], 1),
            (PRINT, vec![s(MORE,1), s(FIRST_ELEMENT,1), s(FIRST_PREFIX,0), s(PRINT_VALUE,0),
                s(ADVANCE,0), s(MORE,1), s(FIRST_ELEMENT,0), s(NEXT_PREFIX,0),
                s(PRINT_VALUE,0), s(ADVANCE,0), s(MORE,0)], 0),
            (MERGE, vec![s(MORE,1), s(MERGE_ITEM_OP,1), s(ADVANCE,0), s(MORE,1),
                s(MERGE_ITEM_OP,1), s(ADVANCE,0), s(MORE,0)], 1),
            (MERGE, vec![s(MORE,1), s(MERGE_ITEM_OP,0), s(ADVANCE,0), s(MORE,0)], 0),
            (MERGE, vec![s(MORE,1), s(MERGE_ITEM_OP,0), s(ADVANCE,0), s(MORE,1),
                s(MERGE_ITEM_OP,1), s(ADVANCE,0), s(MORE,1), s(MERGE_ITEM_OP,0),
                s(ADVANCE,0), s(MORE,0)], 0),
            (MERGE_ITEM, vec![s(INSERTED,1)], 1),
            (MERGE_ITEM, vec![s(INSERTED,0), s(OVERWRITE,0)], 0),
            (MERGE_ITEM, vec![s(INSERTED,0), s(OVERWRITE,1), s(UPDATE,0)], 0),
            (ASSIGN, vec![s(SELF,1)], 0),
            (ASSIGN, vec![s(SELF,0), s(CLEAR,0), s(ENTER_COPY,0)], 0),
            (EQUAL, vec![s(SELF,1)], 1),
            (EQUAL, vec![s(SELF,0), s(SIZE_MISMATCH,1)], 0),
            (EQUAL, vec![s(SELF,0), s(SIZE_MISMATCH,0), s(ENTER_COMPARE,1)], 1),
            (EQUAL, vec![s(SELF,0), s(SIZE_MISMATCH,0), s(ENTER_COMPARE,0)], 0),
            (COMPARE, vec![s(MORE,0)], 1),
            (COMPARE, vec![s(MORE,1), s(PAIR_MATCH,0)], 0),
            (COMPARE, vec![s(MORE,1), s(PAIR_MATCH,1), s(ADVANCE,0), s(MORE,1),
                s(PAIR_MATCH,1), s(ADVANCE,0), s(MORE,0)], 1),
            (COMPARE, vec![s(MORE,1), s(PAIR_MATCH,1), s(ADVANCE,0), s(MORE,1), s(PAIR_MATCH,0)], 0),
        ]
    }

    #[test]
    fn exact_order_empty_short_circuit_and_consecutive_removal() {
        for mode in 0..MERGE { execute(mode, &[s(MORE,0)], OK, 0); }
        execute(MERGE, &[s(MORE,0)], OK, 1);
        for (mode, steps, result) in traces() { execute(mode, &steps, OK, result); }
        execute(FIRST, &[s(MORE,1), s(MATCH,1)], OK, 1);
        execute(FIRST, &[s(MORE,1), s(MATCH,0), s(ADVANCE,0), s(MORE,0)], OK, 0);
        execute(REMOVE, &[s(MORE,1), s(MATCH,0), s(ADVANCE,0), s(MORE,0)], OK, 0);
    }

    #[test]
    fn every_callback_failure_and_malformed_response_stops_at_exact_prefix() {
        // Every reachable callback position, including both print prefixes and
        // post-removal MORE, fails independently. No subsequent leaf may run.
        for (mode, steps, _) in traces() {
            for i in 0..steps.len() {
                for status in [1, 3, u32::MAX] {
                    let mut prefix = steps[..=i].to_vec();
                    prefix[i].1 = u32::MAX; // Host error outranks malformed reply.
                    prefix[i].2 = status;
                    execute(mode, &prefix, HOST_ERROR, 0);
                }
                let op = steps[i].0;
                let minimum = if matches!(op, MORE | MATCH | FIRST_ELEMENT | MERGE_ITEM_OP | INSERTED | OVERWRITE
                    | SELF | SIZE_MISMATCH | ENTER_COMPARE | PAIR_MATCH) { 2 } else { 1 };
                for reply in [minimum, u32::MAX] {
                    let mut prefix = steps[..=i].to_vec();
                    prefix[i].1 = reply;
                    execute(mode, &prefix, INVALID, 0);
                }
            }
        }
    }

    struct Removal { values: Vec<u32>, index: usize, trace: Vec<u32>, throw: bool }
    unsafe extern "C" fn remove_leaf(ctx: *mut c_void, op: u32, out: *mut u32) -> u32 {
        let r = &mut *ctx.cast::<Removal>();
        r.trace.push(op);
        match op {
            MORE => *out = u32::from(r.index < r.values.len()),
            MATCH => *out = u32::from(r.values[r.index] == 7),
            ADVANCE => r.index += 1,
            ERASE => {
                // Models postfix increment before a throwing native erase.
                let old = r.index;
                r.index += 1;
                if r.throw { return 5; }
                // Stable slots model map iterator identity, not vector shifting.
                r.values[old] = 0;
            }
            _ => return 99,
        }
        0
    }
    #[test]
    fn duplicate_consecutive_matches_erase_each_stable_slot_once() {
        let mut r = Removal { values: vec![7,7,9], index: 0, trace: vec![], throw: false };
        let mut output = 82;
        assert_eq!(unsafe { sb_map_run(REMOVE, (&mut r as *mut Removal).cast(), Some(remove_leaf), &mut output) }, OK);
        assert_eq!(output, 1);
        assert_eq!(r.values, [0,0,9]);
        assert_eq!(r.index, 3);
        assert_eq!(r.trace, [MORE,MATCH,ERASE,MORE,MATCH,ERASE,MORE,MATCH,ADVANCE,MORE]);
    }
    #[test]
    fn erase_postfix_effect_survives_error_without_extra_advance_or_output() {
        let mut r = Removal { values: vec![7,7,9], index: 0, trace: vec![], throw: true };
        let mut output = 82;
        let status = unsafe { sb_map_run(REMOVE, (&mut r as *mut Removal).cast(), Some(remove_leaf), &mut output) };
        assert_eq!(status, HOST_ERROR);
        assert_eq!(output, 82);
        assert_eq!(r.index, 1);
        assert_eq!(r.values, [7,7,9]);
        assert_eq!(r.trace, [MORE,MATCH,ERASE]);
    }

    unsafe extern "C" fn forbidden(_: *mut c_void, _: u32, _: *mut u32) -> u32 {
        // Returning, not panicking across extern C, makes unexpected access visible.
        17
    }
    #[test]
    fn rejected_inputs_do_not_access_context_write_or_count() {
        let ctx = std::ptr::NonNull::<u8>::dangling().as_ptr().cast();
        let mut out = 73;
        let mut bytes = [0u32; 2];
        let misaligned = unsafe { bytes.as_mut_ptr().cast::<u8>().add(1).cast::<u32>() };
        for mode in 0..COUNT as u32 {
            let before = sb_map_count(mode);
            for (context, leaf, output) in [
                (std::ptr::null_mut(), Some(forbidden as Leaf), &mut out as *mut u32),
                (ctx, None, &mut out as *mut u32),
                (ctx, Some(forbidden as Leaf), std::ptr::null_mut()),
                (ctx, Some(forbidden as Leaf), misaligned),
            ] {
                assert_eq!(unsafe { sb_map_run(mode, context, leaf, output) }, INVALID);
            }
            assert_eq!(sb_map_count(mode), before);
            let before_select = sb_map_select_count(mode);
            for predicate in [2, u32::MAX] {
                assert_eq!(unsafe { sb_map_select(mode, predicate, &mut out) }, INVALID);
            }
            for output in [std::ptr::null_mut(), misaligned] {
                assert_eq!(unsafe { sb_map_select(mode, 0, output) }, INVALID);
            }
            assert_eq!(sb_map_select_count(mode), before_select);
        }
        for mode in [COUNT as u32, u32::MAX] {
            assert_eq!(unsafe { sb_map_run(mode, ctx, Some(forbidden), &mut out) }, INVALID);
            assert_eq!(unsafe { sb_map_select(mode, 0, &mut out) }, INVALID);
            assert_eq!(sb_map_count(mode), 0);
            assert_eq!(sb_map_select_count(mode), 0);
            assert_eq!(sb_map_global_count(0, mode), 0);
            assert_eq!(sb_map_global_count(1, mode), 0);
        }
        // Invalid entry rejects even an aligned non-writable output address.
        // It must not try reading/writing the pointer to validate its contents.
        let inaccessible = std::ptr::NonNull::<u32>::dangling().as_ptr();
        assert_eq!(unsafe { sb_map_run(u32::MAX, ctx, Some(forbidden), inaccessible) }, INVALID);
        assert_eq!(unsafe { sb_map_select(u32::MAX, 0, inaccessible) }, INVALID);
        assert_eq!(sb_map_global_count(2, 0), 0);
        assert_eq!(out, 73);
        assert_eq!(bytes, [0,0]);
    }

    #[test]
    fn selection_table_and_independent_accepted_counts() {
        let expected = [[THROW,VALUE], [EMPTY,VALUE], [DEFAULT_ACTION,VALUE], [INSERT,UPDATE_ACTION], [THROW,VALUE],
            [NEW,EXISTING], [MISS,ERASE_ACTION]];
        for mode in 0..SELECT_COUNT as u32 {
            let before = sb_map_select_count(mode);
            let loops = sb_map_count(mode);
            for predicate in 0..=1 {
                let mut out = 99;
                assert_eq!(unsafe { sb_map_select(mode, predicate, &mut out) }, OK);
                assert_eq!(out, expected[mode as usize][predicate as usize]);
            }
            assert_eq!(sb_map_select_count(mode), before.wrapping_add(2));
            assert_eq!(sb_map_count(mode), loops);
        }
    }

    #[test]
    fn extra_loop_modes_do_not_extend_selection_bounds() {
        for mode in [EQUAL, COMPARE, ASSIGN] {
            let loops = sb_map_count(mode);
            let before = sb_map_global_count(0, mode);
            let op = if mode == COMPARE { MORE } else { SELF };
            execute(mode, &[s(op, u32::from(op != MORE))], OK, u32::from(mode != ASSIGN));
            assert_eq!(sb_map_count(mode), loops.wrapping_add(1));
            assert!(sb_map_global_count(0, mode).wrapping_sub(before) >= 1);
            let mut out = 91;
            for predicate in [0,1] {
                assert_eq!(unsafe { sb_map_select(mode, predicate, &mut out) }, INVALID);
            }
            assert_eq!(out, 91);
            assert_eq!(sb_map_select_count(mode), 0);
            assert_eq!(sb_map_global_count(1, mode), 0);
        }
    }

    // Models the host's nested error translation, not C++ typed lifetimes.
    struct MergeHost { index: usize, active: bool, fail: bool, saved_error: u32, updates: usize, trace: Vec<u32> }
    unsafe extern "C" fn merge_host(ctx: *mut c_void, op: u32, out: *mut u32) -> u32 {
        let host = ctx.cast::<MergeHost>();
        (*host).trace.push(op);
        match op {
            MORE => *out = u32::from((*host).index < 3),
            MERGE_ITEM_OP => {
                (*host).active = true;
                let mut nested = 91;
                // No Rust borrow of the host survives this nested call.
                let status = sb_map_run(MERGE_ITEM, ctx, Some(merge_host), &mut nested);
                (*host).active = false;
                if status != OK {
                    assert_eq!(nested, 91);
                    return 7; // Host preserves its saved exception for outer rethrow.
                }
                *out = nested;
            }
            INSERTED => { assert!((*host).active); *out = u32::from((*host).index != 1); }
            OVERWRITE => { assert!((*host).active); *out = 1; }
            UPDATE => {
                assert!((*host).active);
                (*host).updates += 1;
                if (*host).fail { (*host).saved_error = 42; return 7; }
            }
            ADVANCE => { assert!(!(*host).active); (*host).index += 1; }
            _ => return 99,
        }
        0
    }
    #[test]
    fn nested_merge_counts_prefix_and_saved_host_error() {
        for fail in [false,true] {
            let before = [sb_map_count(MERGE), sb_map_count(MERGE_ITEM)];
            let mut host = MergeHost { index: 0, active: false, fail, saved_error: 0, updates: 0, trace: vec![] };
            let mut out = 91;
            let status = unsafe { sb_map_run(MERGE, (&mut host as *mut MergeHost).cast(), Some(merge_host), &mut out) };
            let mut expected = vec![MORE,MERGE_ITEM_OP,INSERTED,ADVANCE,MORE,MERGE_ITEM_OP,INSERTED,OVERWRITE,UPDATE];
            if !fail { expected.extend([ADVANCE,MORE,MERGE_ITEM_OP,INSERTED,ADVANCE,MORE]); }
            assert_eq!(host.trace, expected);
            assert_eq!((status,out), if fail { (HOST_ERROR,91) } else { (OK,0) });
            assert_eq!((host.index,host.updates,host.saved_error,host.active), if fail { (1,1,42,false) } else { (3,1,0,false) });
            assert_eq!(sb_map_count(MERGE), before[0].wrapping_add(1));
            assert_eq!(sb_map_count(MERGE_ITEM), before[1].wrapping_add(if fail { 2 } else { 3 }));
        }
    }

    // Models saved native exceptions and range scope, not typed C++ operators.
    struct EqualHost { remaining: usize, active: bool, fail: bool, saved_error: u32, trace: Vec<u32> }
    unsafe extern "C" fn equal_host(ctx: *mut c_void, op: u32, out: *mut u32) -> u32 {
        let host = ctx.cast::<EqualHost>();
        (*host).trace.push(op);
        match op {
            SELF | SIZE_MISMATCH => { assert!(!(*host).active); }
            ENTER_COMPARE => {
                assert!(!(*host).active);
                (*host).active = true; // Models native withRange after the guards.
                let mut nested = 91;
                let status = sb_map_run(COMPARE, ctx, Some(equal_host), &mut nested);
                (*host).active = false; // Range ends even on nested failure.
                if status != OK { assert_eq!(nested, 91); return 7; }
                *out = nested;
            }
            MORE => { assert!((*host).active); *out = u32::from((*host).remaining != 0); }
            PAIR_MATCH => {
                assert!((*host).active);
                if (*host).fail { (*host).saved_error = 42; return 7; }
                *out = 1;
            }
            ADVANCE => { assert!((*host).active); (*host).remaining -= 1; }
            _ => return 99,
        }
        0
    }
    #[test]
    fn nested_compare_empty_matches_counts_and_saved_host_error() {
        for (remaining, fail) in [(0,false), (2,false), (2,true)] {
            let before = [sb_map_count(EQUAL), sb_map_count(COMPARE)];
            let global = [sb_map_global_count(0,EQUAL), sb_map_global_count(0,COMPARE)];
            let mut host = EqualHost { remaining, active: false, fail, saved_error: 0, trace: vec![] };
            let mut out = 91;
            let status = unsafe { sb_map_run(EQUAL, (&mut host as *mut EqualHost).cast(), Some(equal_host), &mut out) };
            let mut expected = vec![SELF,SIZE_MISMATCH,ENTER_COMPARE];
            if fail { expected.extend([MORE,PAIR_MATCH]); }
            else {
                for _ in 0..remaining { expected.extend([MORE,PAIR_MATCH,ADVANCE]); }
                expected.push(MORE);
            }
            assert_eq!(host.trace, expected);
            assert_eq!((status,out), if fail { (HOST_ERROR,91) } else { (OK,1) });
            assert_eq!((host.remaining,host.saved_error,host.active), if fail { (remaining,42,false) } else { (0,0,false) });
            for (i, mode) in [EQUAL,COMPARE].into_iter().enumerate() {
                assert_eq!(sb_map_count(mode), before[i].wrapping_add(1));
                assert!(sb_map_global_count(0,mode).wrapping_sub(global[i]) >= 1);
            }
        }
    }

    // Models clear-before-range ordering and nested errors, not native values.
    struct AssignHost {
        source: Vec<u32>, target: Vec<u32>, index: usize, self_copy: bool,
        cleared: bool, active: bool, fail: bool, saved_error: u32, trace: Vec<u32>,
    }
    unsafe extern "C" fn assign_host(ctx: *mut c_void, op: u32, out: *mut u32) -> u32 {
        let host = ctx.cast::<AssignHost>();
        (*host).trace.push(op);
        match op {
            SELF => { assert!(!(*host).active); *out = u32::from((*host).self_copy); }
            CLEAR => {
                assert!(!(*host).active);
                (*host).target.clear();
                (*host).cleared = true;
            }
            ENTER_COPY => {
                assert!((*host).cleared && !(*host).active);
                assert!((*host).target.is_empty());
                (*host).active = true; // Cached range initialized here, never before CLEAR.
                let mut nested = 91;
                let status = sb_map_run(COLLECT, ctx, Some(assign_host), &mut nested);
                (*host).active = false;
                if status != OK { assert_eq!(nested, 91); return 7; }
                assert_eq!(nested, 0);
            }
            MORE => { assert!((*host).active); *out = u32::from((*host).index < (*host).source.len()); }
            APPEND => {
                assert!((*host).active && (*host).cleared);
                if (*host).fail { (*host).saved_error = 42; return 7; }
                let value = (&(*host).source)[(*host).index];
                (*host).target.push(value);
            }
            ADVANCE => { assert!((*host).active); (*host).index += 1; }
            _ => return 99,
        }
        0
    }
    #[test]
    fn assignment_clear_then_nested_copy_self_empty_errors_and_counts() {
        for (source, self_copy, fail) in [
            (vec![2,3],false,false), (vec![],false,false),
            (vec![2,3],true,false), (vec![],true,false), (vec![2,3],false,true),
        ] {
            let before = [sb_map_count(ASSIGN), sb_map_count(COLLECT)];
            let global = [sb_map_global_count(0,ASSIGN), sb_map_global_count(0,COLLECT)];
            let original = if self_copy { source.clone() } else { vec![9] };
            let mut host = AssignHost { source: source.clone(), target: original.clone(), index: 0,
                self_copy, cleared: false, active: false, fail, saved_error: 0, trace: vec![] };
            let mut out = 91;
            let status = unsafe { sb_map_run(ASSIGN, (&mut host as *mut AssignHost).cast(), Some(assign_host), &mut out) };
            let mut expected = vec![SELF];
            if !self_copy {
                expected.extend([CLEAR,ENTER_COPY]);
                if fail { expected.extend([MORE,APPEND]); }
                else {
                    for _ in &source { expected.extend([MORE,APPEND,ADVANCE]); }
                    expected.push(MORE);
                }
            }
            assert_eq!(host.trace, expected);
            assert_eq!((status,out), if fail { (HOST_ERROR,91) } else { (OK,0) });
            assert_eq!(host.target, if self_copy { original } else if fail { vec![] } else { source });
            assert_eq!((host.cleared,host.active,host.saved_error), (!self_copy,false,if fail { 42 } else { 0 }));
            for (i, mode) in [ASSIGN,COLLECT].into_iter().enumerate() {
                let entries = u64::from(i == 0 || !self_copy);
                assert_eq!(sb_map_count(mode), before[i].wrapping_add(entries));
                assert!(sb_map_global_count(0,mode).wrapping_sub(global[i]) >= entries);
            }
        }
    }

    struct Reentry { entered: bool, nested_status: u32 }
    unsafe extern "C" fn reenter(ctx: *mut c_void, _: u32, _: *mut u32) -> u32 {
        // End each borrow before reentry, like the production callback boundary.
        if !(*ctx.cast::<Reentry>()).entered {
            (*ctx.cast::<Reentry>()).entered = true;
            let mut out = 99;
            let status = sb_map_run(COLLECT, ctx, Some(reenter), &mut out);
            (*ctx.cast::<Reentry>()).nested_status = status;
            if status != OK || out != 0 { return 19; }
        }
        0 // Leaves fresh zero MORE untouched, proving implicit void/false replies.
    }
    #[test]
    fn fresh_zero_reentry_and_host_errors_count_separately() {
        let before = sb_map_count(COLLECT);
        let mut frame = Reentry { entered: false, nested_status: 99 };
        let mut out = 99;
        assert_eq!(unsafe { sb_map_run(COLLECT, (&mut frame as *mut Reentry).cast(), Some(reenter), &mut out) }, OK);
        assert_eq!((out, frame.nested_status), (0,OK));
        assert_eq!(sb_map_count(COLLECT), before.wrapping_add(2));
        execute(COLLECT, &[Step(MORE,0,7)], HOST_ERROR, 0);
        execute(COLLECT, &[s(MORE,2)], INVALID, 0);
        assert_eq!(sb_map_count(COLLECT), before.wrapping_add(4));
    }

    #[test]
    fn thread_isolation_global_cross_thread_and_wrapping_tls() {
        let local = sb_map_count(PRINT);
        let selections = sb_map_select_count(ADD);
        let global = sb_map_global_count(0, PRINT);
        let global_select = sb_map_global_count(1, ADD);
        std::thread::spawn(|| {
            assert_eq!(sb_map_count(PRINT), 0);
            assert_eq!(sb_map_select_count(ADD), 0);
            execute(PRINT, &[s(MORE,0)], OK, 0);
            let mut out = 99;
            assert_eq!(unsafe { sb_map_select(ADD,1,&mut out) }, OK);
            assert_eq!(sb_map_count(PRINT), 1);
            assert_eq!(sb_map_select_count(ADD), 1);
            COUNTS.with(|c| { let mut a = c.get(); a[PRINT as usize] = u64::MAX; c.set(a); });
            SELECT_COUNTS.with(|c| { let mut a = c.get(); a[ADD as usize] = u64::MAX; c.set(a); });
            execute(PRINT, &[s(MORE,0)], OK, 0);
            assert_eq!(unsafe { sb_map_select(ADD,0,&mut out) }, OK);
            assert_eq!(sb_map_count(PRINT), 0);
            assert_eq!(sb_map_select_count(ADD), 0);
        }).join().unwrap();
        assert_eq!(sb_map_count(PRINT), local);
        assert_eq!(sb_map_select_count(ADD), selections);
        // Other tests may concurrently increment process totals; never reset them.
        assert!(sb_map_global_count(0, PRINT).wrapping_sub(global) >= 2);
        assert!(sb_map_global_count(1, ADD).wrapping_sub(global_select) >= 2);
    }
}
