use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST_ERROR: u32 = 2;
const PANIC: u32 = 3;

const ADD_RANGE: u32 = 0;
const REMOVE_RANGE: u32 = 1;
const VALUES: u32 = 2;
const INTERSECTION: u32 = 3;
const DIFFERENCE: u32 = 4;
const PRINT: u32 = 5;
const ASSIGN: u32 = 6;
const COUNT: usize = 7; // Legacy ABI boundary.
const ANY: u32 = 7;
const SCOPED_RANGE: u32 = 8;
const RUNTIME_COUNT: usize = 9;

const MORE: u32 = 0;
const ADVANCE: u32 = 1;
const ADD: u32 = 2;
const REMOVE: u32 = 3;
const APPEND_COPY: u32 = 4;
const CONTAINS: u32 = 5;
const ADD_RESULT: u32 = 6;
const SEPARATOR_NEEDED: u32 = 7;
const SEPARATOR: u32 = 8;
const PRINT_VALUE: u32 = 9;
const SELF: u32 = 10;
const CLEAR: u32 = 11;
const ENTER_ADD_RANGE: u32 = 12;
const BODY: u32 = 13;

const SELECT_INSERT: u32 = 0;
const SELECT_REMOVE: u32 = 1;
const SELECT_NONEMPTY: u32 = 2;
const SELECT_INDEX: u32 = 3;
const SELECT_COUNT: usize = 4; // Legacy ABI boundary.
const SELECT_OPTIONAL: u32 = 4;
const SELECT_FILTER_INTERSECTION: u32 = 5;
const SELECT_FILTER_DIFFERENCE: u32 = 6;
const SELECT_RUNTIME_COUNT: usize = 7;

const ACTION_EXISTING: u32 = 0;
const ACTION_NEW: u32 = 1;
const ACTION_ERASE: u32 = 2;
const ACTION_MISS: u32 = 3;
const ACTION_THROW: u32 = 4;
const ACTION_CONTINUE: u32 = 5;
const ACTION_EMPTY: u32 = 6;
const ACTION_DISTANCE: u32 = 7;
const ACTION_VALUE: u32 = 8;

type Leaf = unsafe extern "C" fn(*mut c_void, u32, *mut u32) -> u32;

static GLOBAL_COUNTS: [AtomicU64; RUNTIME_COUNT] = [const { AtomicU64::new(0) }; RUNTIME_COUNT];
static GLOBAL_SELECT_COUNTS: [AtomicU64; SELECT_RUNTIME_COUNT] =
    [const { AtomicU64::new(0) }; SELECT_RUNTIME_COUNT];

thread_local! {
    static COUNTS: Cell<[u64; RUNTIME_COUNT]> = const { Cell::new([0; RUNTIME_COUNT]) };
    static SELECT_COUNTS: Cell<[u64; SELECT_RUNTIME_COUNT]> = const { Cell::new([0; SELECT_RUNTIME_COUNT]) };
}

// Only raw opaque context crosses a callback: no Rust borrow spans host reentry.
unsafe fn invoke(context: *mut c_void, leaf: Leaf, operation: u32, boolean: bool) -> Result<u32, u32> {
    let mut response = 0;
    if leaf(context, operation, &mut response) != 0 {
        return Err(HOST_ERROR);
    }
    if response > u32::from(boolean) {
        return Err(INVALID);
    }
    Ok(response)
}

unsafe fn run(mode: u32, context: *mut c_void, leaf: Leaf) -> Result<u32, u32> {
    if mode == ASSIGN {
        if invoke(context, leaf, SELF, true)? == 0 {
            invoke(context, leaf, CLEAR, false)?;
            // Iterator initialization belongs AFTER clear, inside this native leaf.
            invoke(context, leaf, ENTER_ADD_RANGE, false)?;
        }
        return Ok(0);
    }
    while invoke(context, leaf, MORE, true)? != 0 {
        match mode {
            ADD_RANGE => { invoke(context, leaf, ADD, false)?; }
            REMOVE_RANGE => { invoke(context, leaf, REMOVE, false)?; }
            VALUES => { invoke(context, leaf, APPEND_COPY, false)?; }
            INTERSECTION | DIFFERENCE => {
                let contains = invoke(context, leaf, CONTAINS, true)? != 0;
                if contains == (mode == INTERSECTION) {
                    invoke(context, leaf, ADD_RESULT, false)?;
                }
            }
            ANY => {
                if invoke(context, leaf, CONTAINS, true)? != 0 {
                    return Ok(1); // Short circuit before advancing the native iterator.
                }
            }
            SCOPED_RANGE => { invoke(context, leaf, BODY, false)?; }
            PRINT => {
                if invoke(context, leaf, SEPARATOR_NEEDED, true)? != 0 {
                    invoke(context, leaf, SEPARATOR, false)?;
                }
                invoke(context, leaf, PRINT_VALUE, false)?;
            }
            _ => return Err(INVALID),
        }
        invoke(context, leaf, ADVANCE, false)?;
    }
    Ok(0)
}

/// Runs only loop/branch policy; native values and iterators never enter Rust.
///
/// # Safety
/// A nonnull context must remain live and satisfy the callback's contract for
/// every invoked leaf. Callbacks must not unwind across this C ABI. Reentry is
/// allowed; the host must preserve its native scopes and translate nested errors.
#[no_mangle]
pub unsafe extern "C" fn sb_ordered_set_run(mode: u32, context: *mut c_void, leaf: Option<Leaf>) -> u32 {
    run_entry(mode, context, leaf, COUNT, None)
}

fn aligned_output(out: *mut u32) -> bool {
    !out.is_null() && (out as usize) % std::mem::align_of::<u32>() == 0
}

// Both ABI families share validation, policy and diagnostics, but retain their
// own admission boundaries. No output is touched until policy succeeds.
unsafe fn run_entry(mode: u32, context: *mut c_void, leaf: Option<Leaf>, limit: usize,
    output: Option<*mut u32>) -> u32 {
    if mode as usize >= limit || context.is_null() || leaf.is_none()
        || output.is_some_and(|out| !aligned_output(out)) {
        return INVALID;
    }
    catch_unwind(AssertUnwindSafe(|| {
        GLOBAL_COUNTS[mode as usize].fetch_add(1, Ordering::Relaxed);
        COUNTS.with(|cell| {
            let mut counts = cell.get();
            counts[mode as usize] = counts[mode as usize].wrapping_add(1);
            cell.set(counts);
        });
        match run(mode, context, leaf.unwrap()) {
            Ok(result) => {
                if let Some(out) = output { out.write(result); }
                OK
            },
            Err(status) => status,
        }
    })).unwrap_or(PANIC)
}

/// Counts accepted entries per thread, including failed leaves and reentry.
#[no_mangle]
pub extern "C" fn sb_ordered_set_count(mode: u32) -> u64 {
    loop_count(mode, COUNT)
}

fn loop_count(mode: u32, limit: usize) -> u64 {
    if mode as usize >= limit { return 0; }
    catch_unwind(|| COUNTS.with(|cell| cell.get()[mode as usize])).unwrap_or(0)
}

/// Generic set loop policy, including short-circuit membership and scoped bodies.
///
/// # Safety
/// The legacy callback/liveness/no-unwind contract applies. out_result must be
/// live writable aligned u32 storage; it is written only on success.
#[no_mangle]
pub unsafe extern "C" fn sb_set_run(mode: u32, context: *mut c_void, leaf: Option<Leaf>,
    out_result: *mut u32) -> u32 {
    run_entry(mode, context, leaf, RUNTIME_COUNT, Some(out_result))
}

#[no_mangle]
pub extern "C" fn sb_set_count(mode: u32) -> u64 {
    loop_count(mode, RUNTIME_COUNT)
}

/// Selects only an action; C++ retains the original comparisons and typed return
/// scopes. Keeping materialization after this call avoids extra native value slots,
/// copies, or foreign exception unwinding through Rust.
///
/// # Safety
/// For accepted inputs, out_action must designate live writable aligned u32
/// storage. Numerical validation cannot establish pointer provenance or liveness.
#[no_mangle]
pub unsafe extern "C" fn sb_ordered_set_select(mode: u32, predicate: u32, out_action: *mut u32) -> u32 {
    select_entry(mode, predicate, out_action, SELECT_COUNT)
}

unsafe fn select_entry(mode: u32, predicate: u32, out_action: *mut u32, limit: usize) -> u32 {
    if mode as usize >= limit || predicate > 1 || !aligned_output(out_action) {
        return INVALID;
    }
    catch_unwind(AssertUnwindSafe(|| {
        GLOBAL_SELECT_COUNTS[mode as usize].fetch_add(1, Ordering::Relaxed);
        SELECT_COUNTS.with(|cell| {
            let mut counts = cell.get();
            counts[mode as usize] = counts[mode as usize].wrapping_add(1);
            cell.set(counts);
        });
        let action = match mode {
            SELECT_INSERT => if predicate != 0 { ACTION_EXISTING } else { ACTION_NEW },
            SELECT_REMOVE => if predicate != 0 { ACTION_ERASE } else { ACTION_MISS },
            SELECT_NONEMPTY => if predicate != 0 { ACTION_THROW } else { ACTION_CONTINUE },
            SELECT_INDEX => if predicate != 0 { ACTION_DISTANCE } else { ACTION_EMPTY },
            SELECT_OPTIONAL => if predicate != 0 { ACTION_EMPTY } else { ACTION_VALUE },
            SELECT_FILTER_INTERSECTION => if predicate != 0 { ACTION_VALUE } else { ACTION_EMPTY },
            SELECT_FILTER_DIFFERENCE => if predicate != 0 { ACTION_EMPTY } else { ACTION_VALUE },
            _ => unreachable!(),
        };
        out_action.write(action);
        OK
    })).unwrap_or(PANIC)
}

/// Counts accepted selections independently of loop entries on this thread.
#[no_mangle]
pub extern "C" fn sb_ordered_set_select_count(mode: u32) -> u64 {
    select_count(mode, SELECT_COUNT)
}

fn select_count(mode: u32, limit: usize) -> u64 {
    if mode as usize >= limit { return 0; }
    catch_unwind(|| SELECT_COUNTS.with(|cell| cell.get()[mode as usize])).unwrap_or(0)
}

/// Selects a generic set action without materializing native values.
///
/// # Safety
/// out_action must designate live writable aligned u32 storage.
#[no_mangle]
pub unsafe extern "C" fn sb_set_select(mode: u32, predicate: u32, out_action: *mut u32) -> u32 {
    select_entry(mode, predicate, out_action, SELECT_RUNTIME_COUNT)
}

#[no_mangle]
pub extern "C" fn sb_set_select_count(mode: u32) -> u64 {
    select_count(mode, SELECT_RUNTIME_COUNT)
}

/// Process-wide wrapping accepted-entry totals: kind 0 is loops, kind 1 selections.
/// Shared by generic and legacy entry points; invalid kinds/modes return zero.
/// Diagnostics only: not distinct consumers, program state, or a synchronized
/// snapshot. Concurrent counters provide only finite-width totals.
#[no_mangle]
pub extern "C" fn sb_set_global_count(kind: u32, mode: u32) -> u64 {
    let counters: &[AtomicU64] = match kind {
        0 => &GLOBAL_COUNTS,
        1 => &GLOBAL_SELECT_COUNTS,
        _ => return 0,
    };
    counters.get(mode as usize).map_or(0, |count| count.load(Ordering::Relaxed))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn global_selection_counts_include_other_threads_without_changing_local_counts() {
        let loops = COUNTS.with(|cell| cell.get());
        let selections = SELECT_COUNTS.with(|cell| cell.get());
        let before = sb_set_global_count(1, SELECT_OPTIONAL);
        std::thread::spawn(|| {
            let mut action = u32::MAX;
            assert_eq!(unsafe { sb_set_select(SELECT_OPTIONAL, 0, &mut action) }, OK);
            assert_eq!(action, ACTION_VALUE);
        }).join().unwrap();
        assert!(sb_set_global_count(1, SELECT_OPTIONAL) >= before + 1);
        assert_eq!(COUNTS.with(|cell| cell.get()), loops);
        assert_eq!(SELECT_COUNTS.with(|cell| cell.get()), selections);
        for kind in [2, u32::MAX] {
            assert_eq!(sb_set_global_count(kind, 0), 0);
        }
        for (kind, mode) in [(0, RUNTIME_COUNT as u32), (1, SELECT_RUNTIME_COUNT as u32),
            (0, u32::MAX), (1, u32::MAX)] {
            assert_eq!(sb_set_global_count(kind, mode), 0);
        }
    }

    fn generic_call(host: &mut Script, mode: u32, out: *mut u32) -> u32 {
        unsafe { sb_set_run(mode, (host as *mut Script).cast(), Some(script_leaf), out) }
    }

    fn new_scripts() -> Vec<(u32, u32, Vec<(u32, u32)>)> {
        // Literal IDs/results keep these expectations independent of policy.
        vec![
            (7, 0, vec![(0,0)]),
            (7, 0, vec![(0,1),(5,0),(1,0),(0,0)]),
            (7, 1, vec![(0,1),(5,1)]),
            (7, 1, vec![(0,1),(5,0),(1,0),(0,1),(5,1)]),
            (8, 0, vec![(0,0)]),
            (8, 0, vec![(0,1),(13,0),(1,0),(0,1),(13,0),(1,0),(0,0)]),
        ]
    }

    #[test]
    fn generic_any_short_circuits_and_scoped_range_preserves_order() {
        let mut cases = new_scripts();
        cases.extend(scripts().into_iter().map(|(mode, steps)| (mode, 0, steps)));
        for (mode, expected_result, steps) in cases {
            let trace: Vec<_> = steps.iter().map(|s| s.0).collect();
            let mut host = Script::new(steps);
            let mut result = 0xfeed_beef;
            assert_eq!(generic_call(&mut host, mode, &mut result), OK);
            assert_eq!(result, expected_result, "mode {mode}");
            assert_eq!(host.trace, trace);
            assert!(!host.mismatch);
        }
    }

    #[test]
    fn generic_callbacks_stop_on_errors_without_writing_result() {
        let mut cases = new_scripts();
        cases.extend(scripts().into_iter().map(|(mode, steps)| (mode, 0, steps)));
        for (mode, _, steps) in cases {
            for at in 0..steps.len() {
                let boolean = matches!(steps[at].0, 0 | 5 | 7 | 10);
                for (status, response, expected) in [
                    (1, u32::MAX, HOST_ERROR),
                    (u32::MAX, 0, HOST_ERROR),
                    (0, if boolean { 2 } else { 1 }, INVALID),
                    (0, u32::MAX, INVALID),
                ] {
                    let before = sb_set_count(mode);
                    let mut host = Script::new(steps.clone());
                    host.fault = Some((at, status, response));
                    let mut result = 0xfeed_beef;
                    assert_eq!(generic_call(&mut host, mode, &mut result), expected);
                    assert_eq!(result, 0xfeed_beef);
                    assert_eq!(host.trace, steps[..=at].iter().map(|s| s.0).collect::<Vec<_>>());
                    assert!(!host.mismatch);
                    assert_eq!(sb_set_count(mode), before.wrapping_add(1));
                }
            }
        }
    }

    #[test]
    fn generic_selection_new_truth_tables_and_all_prefix_actions() {
        let loop_before = COUNTS.with(|c| c.get());
        for (mode, predicate, expected) in [
            (0,0,1), (0,1,0), (1,0,3), (1,1,2),
            (2,0,5), (2,1,4), (3,0,6), (3,1,7),
            (4,0,8), (4,1,6), (5,0,6), (5,1,8), (6,0,8), (6,1,6),
        ] {
            let before = SELECT_COUNTS.with(|c| c.get());
            let mut action = 0xfeed_beef;
            assert_eq!(unsafe { sb_set_select(mode, predicate, &mut action) }, OK);
            assert_eq!(action, expected, "mode {mode}, predicate {predicate}");
            let mut counts = before;
            counts[mode as usize] = counts[mode as usize].wrapping_add(1);
            assert_eq!(SELECT_COUNTS.with(|c| c.get()), counts);
            assert_eq!(sb_set_select_count(mode), counts[mode as usize]);
        }
        assert_eq!(COUNTS.with(|c| c.get()), loop_before);
    }

    #[test]
    fn generic_invalid_boundaries_leave_host_outputs_and_shared_counts_untouched() {
        let before = COUNTS.with(|c| c.get());
        let selections = SELECT_COUNTS.with(|c| c.get());
        let mut host = Script::new(vec![]);
        let context = (&mut host as *mut Script).cast();
        let mut storage = [0xfeed_beefu32; 2];
        let aligned = storage.as_mut_ptr();
        let misaligned = unsafe { aligned.cast::<u8>().add(1).cast::<u32>() };
        for mode in [0,1,2,3,4,5,6,7,8,9,u32::MAX] {
            for ctx in [context, std::ptr::null_mut()] {
                for leaf in [Some(script_leaf as Leaf), None] {
                    for out in [aligned, std::ptr::null_mut(), misaligned] {
                        if mode < 9 && ctx == context && leaf.is_some() && out == aligned { continue; }
                        assert_eq!(unsafe { sb_set_run(mode, ctx, leaf, out) }, INVALID);
                        assert_eq!(storage, [0xfeed_beef; 2]);
                        assert_eq!(COUNTS.with(|c| c.get()), before);
                    }
                }
            }
        }
        for mode in [0,1,2,3,4,5,6,7,u32::MAX] {
            for predicate in [0,1,2,u32::MAX] {
                for out in [aligned, std::ptr::null_mut(), misaligned] {
                    if mode < 7 && predicate < 2 && out == aligned { continue; }
                    assert_eq!(unsafe { sb_set_select(mode, predicate, out) }, INVALID);
                    assert_eq!(storage, [0xfeed_beef; 2]);
                    assert_eq!(SELECT_COUNTS.with(|c| c.get()), selections);
                }
            }
        }
        for mode in [9, u32::MAX] { assert_eq!(sb_set_count(mode), 0); }
        for mode in [7, u32::MAX] { assert_eq!(sb_set_select_count(mode), 0); }
        assert!(host.trace.is_empty());
        assert_eq!(COUNTS.with(|c| c.get()), before);
        assert_eq!(SELECT_COUNTS.with(|c| c.get()), selections);
    }

    #[test]
    fn legacy_rejects_new_modes_without_callback_output_or_count_changes() {
        let before = COUNTS.with(|c| c.get());
        let selections = SELECT_COUNTS.with(|c| c.get());
        let mut host = Script::new(vec![]);
        for mode in [7,8,9,u32::MAX] {
            assert_eq!(host.call(mode), INVALID);
            assert_eq!(sb_ordered_set_count(mode), 0);
        }
        let mut buffer = [0xfeed_beefu32; 2];
        for mode in [4,5,6,7,u32::MAX] {
            for predicate in [0,1] {
                assert_eq!(unsafe { sb_ordered_set_select(mode, predicate, buffer.as_mut_ptr()) }, INVALID);
                assert_eq!(buffer, [0xfeed_beef; 2]);
            }
            assert_eq!(sb_ordered_set_select_count(mode), 0);
        }
        assert!(host.trace.is_empty());
        assert_eq!(COUNTS.with(|c| c.get()), before);
        assert_eq!(SELECT_COUNTS.with(|c| c.get()), selections);
    }

    #[test]
    fn generic_and_legacy_queries_are_prefix_views_of_shared_cells() {
        for mode in 0..7 {
            let before = sb_set_count(mode);
            let steps = if mode == 6 { vec![(10,1)] } else { vec![(0,0)] };
            assert_eq!(Script::new(steps.clone()).call(mode), OK);
            assert_eq!(sb_set_count(mode), before.wrapping_add(1));
            let mut result = 99;
            assert_eq!(generic_call(&mut Script::new(steps), mode, &mut result), OK);
            assert_eq!(sb_set_count(mode), before.wrapping_add(2));
            assert_eq!(sb_ordered_set_count(mode), sb_set_count(mode));
            assert_eq!(result, 0);
        }
        for mode in 0..4 {
            let before = sb_set_select_count(mode);
            let mut action = 99;
            assert_eq!(unsafe { sb_ordered_set_select(mode, 0, &mut action) }, OK);
            assert_eq!(sb_set_select_count(mode), before.wrapping_add(1));
            assert_eq!(unsafe { sb_set_select(mode, 1, &mut action) }, OK);
            assert_eq!(sb_set_select_count(mode), before.wrapping_add(2));
            assert_eq!(sb_ordered_set_select_count(mode), sb_set_select_count(mode));
        }
        let mut host = Script::new(vec![(0,0)]);
        let mut result = 99;
        for mode in [7,8] {
            host.trace.clear();
            let before = sb_set_count(mode);
            assert_eq!(generic_call(&mut host, mode, &mut result), OK);
            assert_eq!(sb_set_count(mode), before.wrapping_add(1));
            assert_eq!(sb_ordered_set_count(mode), 0);
        }
        for mode in [4,5,6] {
            let before = sb_set_select_count(mode);
            assert_eq!(unsafe { sb_set_select(mode, 0, &mut result) }, OK);
            assert_eq!(sb_set_select_count(mode), before.wrapping_add(1));
            assert_eq!(sb_ordered_set_select_count(mode), 0);
        }
    }

    #[test]
    fn selection_truth_table_and_independent_counts() {
        let loop_before = COUNTS.with(|cell| cell.get());
        // Explicit ABI literals are independent of the implementation constants.
        // Inverting any predicate guard must fail an expected-action assertion.
        for (mode, predicate, expected) in [
            (0, 0, 1), (0, 1, 0), (1, 0, 3), (1, 1, 2),
            (2, 0, 5), (2, 1, 4), (3, 0, 6), (3, 1, 7),
        ] {
            let before = SELECT_COUNTS.with(|cell| cell.get());
            let mut action = u32::MAX;
            assert_eq!(unsafe { sb_ordered_set_select(mode, predicate, &mut action) }, OK);
            assert_eq!(action, expected, "mode {mode}, predicate {predicate}");
            let mut expected_counts = before;
            expected_counts[mode as usize] = expected_counts[mode as usize].wrapping_add(1);
            assert_eq!(SELECT_COUNTS.with(|cell| cell.get()), expected_counts);
            assert_eq!(sb_ordered_set_select_count(mode), expected_counts[mode as usize]);
        }
        assert_eq!(COUNTS.with(|cell| cell.get()), loop_before);
    }

    #[test]
    fn selection_invalid_inputs_preserve_output_and_all_counts() {
        let before = SELECT_COUNTS.with(|cell| cell.get());
        let loop_before = COUNTS.with(|cell| cell.get());
        let mut storage = [0xfeed_beefu32; 2];
        let aligned = storage.as_mut_ptr();
        // This points within owned storage but is deliberately not u32-aligned.
        let misaligned = unsafe { aligned.cast::<u8>().add(1).cast::<u32>() };
        for mode in [0, 1, 2, 3, 4, u32::MAX] {
            for predicate in [0, 1, 2, u32::MAX] {
                for out in [aligned, std::ptr::null_mut(), misaligned] {
                    if mode < 4 && predicate < 2 && out == aligned { continue; }
                    assert_eq!(unsafe { sb_ordered_set_select(mode, predicate, out) }, INVALID);
                    assert_eq!(storage, [0xfeed_beef; 2]);
                    assert_eq!(SELECT_COUNTS.with(|cell| cell.get()), before);
                    assert_eq!(COUNTS.with(|cell| cell.get()), loop_before);
                }
            }
        }
        for mode in [4, u32::MAX] {
            assert_eq!(sb_ordered_set_select_count(mode), 0);
        }
        assert_eq!(SELECT_COUNTS.with(|cell| cell.get()), before);
    }

    #[test]
    fn selection_counts_wrap_independently() {
        let saved = SELECT_COUNTS.with(|cell| cell.get());
        let loop_before = COUNTS.with(|cell| cell.get());
        SELECT_COUNTS.with(|cell| {
            let mut counts = cell.get();
            counts[SELECT_INSERT as usize] = u64::MAX;
            cell.set(counts);
        });
        let mut action = u32::MAX;
        let status = unsafe { sb_ordered_set_select(SELECT_INSERT, 1, &mut action) };
        let count = sb_ordered_set_select_count(SELECT_INSERT);
        SELECT_COUNTS.with(|cell| cell.set(saved));
        assert_eq!(status, OK);
        assert_eq!(action, ACTION_EXISTING);
        assert_eq!(count, 0);
        assert_eq!(COUNTS.with(|cell| cell.get()), loop_before);
    }

    // Script steps are an independent finite host contract, not a second loop
    // implementation. Errors are recorded rather than panicking through C ABI.
    struct Script {
        steps: Vec<(u32, u32)>,
        trace: Vec<u32>,
        mismatch: bool,
        fault: Option<(usize, u32, u32)>,
    }

    impl Script {
        fn new(steps: Vec<(u32, u32)>) -> Self {
            Self { steps, trace: vec![], mismatch: false, fault: None }
        }
        fn call(&mut self, mode: u32) -> u32 {
            unsafe { sb_ordered_set_run(mode, (self as *mut Self).cast(), Some(script_leaf)) }
        }
    }

    unsafe extern "C" fn script_leaf(context: *mut c_void, op: u32, out: *mut u32) -> u32 {
        let host = &mut *context.cast::<Script>();
        let index = host.trace.len();
        host.trace.push(op);
        if *out != 0 || host.steps.get(index).map(|step| step.0) != Some(op) {
            host.mismatch = true;
            return 19;
        }
        if let Some((at, status, response)) = host.fault {
            if at == index {
                *out = response;
                return status;
            }
        }
        *out = host.steps[index].1;
        OK
    }

    fn scripts() -> Vec<(u32, Vec<(u32, u32)>)> {
        vec![
            (ADD_RANGE, vec![(MORE,1),(ADD,0),(ADVANCE,0),(MORE,1),(ADD,0),(ADVANCE,0),(MORE,0)]),
            (REMOVE_RANGE, vec![(MORE,1),(REMOVE,0),(ADVANCE,0),(MORE,1),(REMOVE,0),(ADVANCE,0),(MORE,0)]),
            (VALUES, vec![(MORE,1),(APPEND_COPY,0),(ADVANCE,0),(MORE,1),(APPEND_COPY,0),(ADVANCE,0),(MORE,0)]),
            (INTERSECTION, vec![(MORE,1),(CONTAINS,0),(ADVANCE,0),(MORE,1),(CONTAINS,1),(ADD_RESULT,0),(ADVANCE,0),(MORE,0)]),
            (DIFFERENCE, vec![(MORE,1),(CONTAINS,1),(ADVANCE,0),(MORE,1),(CONTAINS,0),(ADD_RESULT,0),(ADVANCE,0),(MORE,0)]),
            (PRINT, vec![(MORE,1),(SEPARATOR_NEEDED,0),(PRINT_VALUE,0),(ADVANCE,0),(MORE,1),(SEPARATOR_NEEDED,1),(SEPARATOR,0),(PRINT_VALUE,0),(ADVANCE,0),(MORE,0)]),
            (ASSIGN, vec![(SELF,0),(CLEAR,0),(ENTER_ADD_RANGE,0)]),
        ]
    }

    #[test]
    fn all_modes_full_trace_and_empty_loops() {
        for (mode, steps) in scripts() {
            let expected: Vec<_> = steps.iter().map(|step| step.0).collect();
            let mut host = Script::new(steps);
            assert_eq!(host.call(mode), OK);
            assert!(!host.mismatch);
            assert_eq!(host.trace, expected);
        }
        for mode in 0..ASSIGN {
            let mut host = Script::new(vec![(MORE,0)]);
            assert_eq!(host.call(mode), OK);
            assert_eq!(host.trace, [MORE]);
            assert!(!host.mismatch);
        }
        let mut host = Script::new(vec![(SELF,1)]);
        assert_eq!(host.call(ASSIGN), OK);
        assert_eq!(host.trace, [SELF]);
    }

    #[test]
    fn every_callback_failure_and_invalid_response_stops_without_extra_ops() {
        for (mode, steps) in scripts() {
            for at in 0..steps.len() {
                // Host failure takes precedence even over a malformed response.
                for status in [1, 31, u32::MAX] {
                    let mut host = Script::new(steps.clone());
                    host.fault = Some((at, status, u32::MAX));
                    assert_eq!(host.call(mode), HOST_ERROR, "mode {mode} at {at}");
                    assert!(!host.mismatch);
                    assert_eq!(host.trace, steps[..=at].iter().map(|s| s.0).collect::<Vec<_>>());
                }
                let boolean = matches!(steps[at].0, MORE | CONTAINS | SEPARATOR_NEEDED | SELF);
                for response in [if boolean { 2 } else { 1 }, u32::MAX] {
                    let mut host = Script::new(steps.clone());
                    host.fault = Some((at, OK, response));
                    assert_eq!(host.call(mode), INVALID, "mode {mode} at {at}");
                    assert!(!host.mismatch);
                    assert_eq!(host.trace, steps[..=at].iter().map(|s| s.0).collect::<Vec<_>>());
                }
            }
        }
    }

    struct Host {
        input: Vec<i32>,
        membership: Vec<i32>,
        result: Vec<i32>,
        cursor: usize,
        text: String,
    }

    unsafe extern "C" fn value_leaf(context: *mut c_void, op: u32, out: *mut u32) -> u32 {
        let h = &mut *context.cast::<Host>();
        if *out != 0 { return 1; }
        match op {
            MORE => *out = u32::from(h.cursor < h.input.len()),
            ADVANCE => h.cursor += 1,
            CONTAINS => *out = u32::from(h.membership.contains(&h.input[h.cursor])),
            ADD | ADD_RESULT => {
                let value = h.input[h.cursor];
                if !h.result.contains(&value) { h.result.push(value); }
            }
            REMOVE => {
                let value = h.input[h.cursor];
                h.result.retain(|v| *v != value);
            }
            APPEND_COPY => h.result.push(h.input[h.cursor]),
            SEPARATOR_NEEDED => *out = u32::from(h.cursor != 0),
            SEPARATOR => h.text.push_str(", "),
            PRINT_VALUE => h.text.push_str(&h.input[h.cursor].to_string()),
            _ => return 1,
        }
        OK
    }

    #[test]
    fn filtering_and_insertion_order_and_print_separators() {
        for (mode, expected) in [
            (ADD_RANGE, vec![7,2,9]),
            (REMOVE_RANGE, vec![8]),
            (VALUES, vec![7,2,7,9]),
            (INTERSECTION, vec![7,9]),
            (DIFFERENCE, vec![2]),
            (PRINT, vec![]),
        ] {
            let mut host = Host {
                input: vec![7,2,7,9], membership: vec![9,7],
                result: if mode == REMOVE_RANGE { vec![9,8,7,2] } else { vec![] },
                cursor: 0, text: String::new(),
            };
            assert_eq!(unsafe { sb_ordered_set_run(mode, (&mut host as *mut Host).cast(), Some(value_leaf)) }, OK);
            assert_eq!(host.result, expected);
            if mode == PRINT { assert_eq!(host.text, "7, 2, 7, 9"); }
        }
    }

    struct Assignment {
        trace: Vec<u32>,
        cleared: bool,
        nested_status: u32,
        child: Script,
    }

    unsafe extern "C" fn assignment_leaf(context: *mut c_void, op: u32, out: *mut u32) -> u32 {
        let p = context.cast::<Assignment>();
        // Do not create an exclusive reference to the enclosing frame: the host
        // deliberately reenters Rust, which calls a second native iterator frame.
        (*p).trace.push(op);
        if *out != 0 { return 1; }
        match op {
            SELF => *out = 0,
            CLEAR => (*p).cleared = true,
            ENTER_ADD_RANGE => {
                if !(*p).cleared { return 1; }
                let child = std::ptr::addr_of_mut!((*p).child).cast();
                let status = sb_ordered_set_run(ADD_RANGE, child, Some(script_leaf));
                (*p).nested_status = status;
                if status != OK { return 1; }
            }
            _ => return 1,
        }
        OK
    }

    #[test]
    fn assignment_reenters_after_clear_and_counts_both_entries_even_on_error() {
        for fail in [false, true] {
            let add_before = sb_ordered_set_count(ADD_RANGE);
            let assign_before = sb_ordered_set_count(ASSIGN);
            let mut host = Assignment {
                trace: vec![], cleared: false, nested_status: 99,
                child: Script::new(vec![(MORE,1),(ADD,0),(ADVANCE,0),(MORE,0)]),
            };
            if fail { host.child.fault = Some((1, 71, 0)); }
            let status = unsafe { sb_ordered_set_run(ASSIGN, (&mut host as *mut Assignment).cast(), Some(assignment_leaf)) };
            assert_eq!(status, if fail { HOST_ERROR } else { OK });
            assert_eq!(host.nested_status, status);
            assert_eq!(host.trace, [SELF,CLEAR,ENTER_ADD_RANGE]);
            assert_eq!(host.child.trace, if fail { vec![MORE,ADD] } else { vec![MORE,ADD,ADVANCE,MORE] });
            assert!(!host.child.mismatch);
            assert_eq!(sb_ordered_set_count(ADD_RANGE), add_before.wrapping_add(1));
            assert_eq!(sb_ordered_set_count(ASSIGN), assign_before.wrapping_add(1));
        }
    }

    #[test]
    fn invalid_inputs_do_not_access_host_or_increment_counts() {
        let mut host = Script::new(vec![]);
        let context = (&mut host as *mut Script).cast();
        let before: Vec<_> = (0..COUNT as u32).map(|mode| sb_ordered_set_count(mode)).collect();
        unsafe {
            for mode in [COUNT as u32, u32::MAX] {
                assert_eq!(sb_ordered_set_run(mode, context, Some(script_leaf)), INVALID);
                assert_eq!(sb_ordered_set_count(mode), 0);
            }
            for mode in 0..COUNT as u32 {
                assert_eq!(sb_ordered_set_run(mode, std::ptr::null_mut(), Some(script_leaf)), INVALID);
                assert_eq!(sb_ordered_set_run(mode, context, None), INVALID);
                assert_eq!(sb_ordered_set_run(mode, std::ptr::null_mut(), None), INVALID);
            }
        }
        assert!(host.trace.is_empty());
        assert_eq!(before, (0..COUNT as u32).map(|mode| sb_ordered_set_count(mode)).collect::<Vec<_>>());
    }

    #[test]
    fn counts_include_invalid_host_responses_and_wrap() {
        let saved = COUNTS.with(|c| c.get());
        COUNTS.with(|c| { let mut v = c.get(); v[PRINT as usize] = u64::MAX; c.set(v); });
        let mut host = Script::new(vec![(MORE,1)]);
        host.fault = Some((0, OK, 2));
        let status = host.call(PRINT);
        let count = sb_ordered_set_count(PRINT);
        COUNTS.with(|c| c.set(saved));
        assert_eq!(status, INVALID);
        assert_eq!(count, 0);
    }
}
