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
const COUNT: usize = 5;
const MORE: u32 = 0;
const ADVANCE: u32 = 1;
const APPEND: u32 = 2;
const MATCH: u32 = 3;
const ERASE: u32 = 4;
const FIRST_ELEMENT: u32 = 5;
const FIRST_PREFIX: u32 = 6;
const NEXT_PREFIX: u32 = 7;
const PRINT_VALUE: u32 = 8;
const REQUIRED: u32 = 0;
const OPTIONAL: u32 = 1;
const DEFAULT: u32 = 2;
const SET: u32 = 3;
const ADD: u32 = 4;
const VALUE: u32 = 0;
const THROW: u32 = 1;
const EMPTY: u32 = 2;
const DEFAULT_ACTION: u32 = 3;
const INSERT: u32 = 4;
const UPDATE: u32 = 5;

pub type Leaf = unsafe extern "C" fn(*mut c_void, u32, *mut u32) -> u32;
static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
static SELECT_TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
thread_local! {
    static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) };
    static SELECT_COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) };
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
    let boolean = matches!(operation, MORE | MATCH | FIRST_ELEMENT);
    if response > u32::from(boolean) {
        return Err(INVALID);
    }
    Ok(response)
}

unsafe fn run(mode: u32, ctx: *mut c_void, leaf: Leaf) -> Result<u32, u32> {
    let mut removed = 0;
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
                    removed = 1;
                    continue;
                }
            }
            PRINT => {
                let first = invoke(ctx, leaf, FIRST_ELEMENT)? != 0;
                invoke(ctx, leaf, if first { FIRST_PREFIX } else { NEXT_PREFIX })?;
                invoke(ctx, leaf, PRINT_VALUE)?;
            }
            _ => unreachable!(),
        }
        invoke(ctx, leaf, ADVANCE)?;
    }
    Ok(removed)
}

fn count_entry(mode: usize, select: bool) {
    let (totals, counts) = if select { (&SELECT_TOTALS, &SELECT_COUNTS) } else { (&TOTALS, &COUNTS) };
    totals[mode].fetch_add(1, Ordering::Relaxed);
    counts.with(|cell| {
        let mut values = cell.get();
        values[mode] = values[mode].wrapping_add(1);
        cell.set(values);
    });
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
    if mode as usize >= COUNT || predicate > 1 || !aligned(out) { return INVALID; }
    catch_unwind(AssertUnwindSafe(|| {
        count_entry(mode as usize, true);
        let yes = predicate != 0;
        let action = match mode {
            REQUIRED | ADD => if yes { VALUE } else { THROW },
            OPTIONAL => if yes { VALUE } else { EMPTY },
            DEFAULT => if yes { VALUE } else { DEFAULT_ACTION },
            SET => if yes { UPDATE } else { INSERT },
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
    if mode as usize >= COUNT { return 0; }
    catch_unwind(|| SELECT_COUNTS.with(|cell| cell.get()[mode as usize])).unwrap_or(0)
}

/// Relaxed diagnostic totals; not a synchronized snapshot or consumer count.
#[no_mangle]
pub extern "C" fn sb_map_global_count(kind: u32, mode: u32) -> u64 {
    if mode as usize >= COUNT { return 0; }
    match kind {
        0 => TOTALS[mode as usize].load(Ordering::Relaxed),
        1 => SELECT_TOTALS[mode as usize].load(Ordering::Relaxed),
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
        let actual = unsafe { sb_map_run(mode, (&mut script as *mut Script).cast(), Some(scripted), &mut output) };
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
        ]
    }

    #[test]
    fn exact_order_empty_short_circuit_and_consecutive_removal() {
        for mode in 0..COUNT as u32 { execute(mode, &[s(MORE,0)], OK, 0); }
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
                let mut prefix = steps[..=i].to_vec();
                let op = prefix[i].0;
                prefix[i].1 = if matches!(op, MORE | MATCH | FIRST_ELEMENT) { 2 } else { 1 };
                execute(mode, &prefix, INVALID, 0);
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
        let expected = [[THROW,VALUE], [EMPTY,VALUE], [DEFAULT_ACTION,VALUE], [INSERT,UPDATE], [THROW,VALUE]];
        for mode in 0..COUNT as u32 {
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
