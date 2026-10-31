//! Unsigned Periodic state transitions; native callback invocation stays in C++.
use std::cell::Cell;
use std::panic::catch_unwind;
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const PANIC: u32 = 3;
const INIT: u32 = 0;
const SET: u32 = 1;
const READY: u32 = 2;
const TICK: u32 = 3;
const COUNT: usize = 4;

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbPeriodicState {
    pub counter: u32,
    pub every: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbPeriodicReply {
    pub state: SbPeriodicState,
    pub ready: u32,
}

static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
thread_local! {
    static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) };
}

fn increment(counts: &Cell<[u64; COUNT]>, totals: &[AtomicU64; COUNT], op: usize) {
    totals[op].fetch_add(1, Ordering::Relaxed);
    let mut values = counts.get();
    values[op] = values[op].wrapping_add(1);
    counts.set(values);
}

fn transition(operation: u32, mut state: SbPeriodicState, every: u32) -> SbPeriodicReply {
    let mut ready = 0;
    match operation {
        INIT => state = SbPeriodicState { counter: 0, every },
        SET => state = SbPeriodicState {
            counter: if every == 0 { 0 } else { state.counter.min(every - 1) },
            every,
        },
        READY => ready = u32::from(state.every != 0 && state.counter == 0),
        TICK => {
            if state.every != 0 {
                if state.counter == 0 {
                    state.counter = state.every - 1;
                    ready = 1;
                } else {
                    state.counter -= 1;
                }
            }
        }
        _ => unreachable!(),
    }
    SbPeriodicReply { state, ready }
}

/// Computes the whole reply before committing to output; retains no host borrow.
///
/// # Safety
/// For accepted arguments, out must designate live writable aligned reply storage.
/// Numeric validation cannot establish provenance, liveness or writability.
#[no_mangle]
pub unsafe extern "C" fn sb_periodic_run(
    operation: u32, state: SbPeriodicState, every: u32, out: *mut SbPeriodicReply,
) -> u32 {
    if operation >= COUNT as u32 || (operation >= READY && every != 0)
        || out.is_null() || (out as usize) % std::mem::align_of::<SbPeriodicReply>() != 0
    {
        return INVALID;
    }
    catch_unwind(|| {
        COUNTS.with(|counts| increment(counts, &TOTALS, operation as usize));
        let reply = transition(operation, state, every);
        out.write(reply);
        OK
    }).unwrap_or(PANIC)
}

/// Wrapping accepted entries: kind 0 is this thread, kind 1 relaxed global totals.
#[no_mangle]
pub extern "C" fn sb_periodic_count(kind: u32, operation: u32) -> u64 {
    if kind > 1 || operation >= COUNT as u32 { return 0; }
    catch_unwind(|| match kind {
        0 => COUNTS.with(|counts| counts.get()[operation as usize]),
        _ => TOTALS[operation as usize].load(Ordering::Relaxed),
    }).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    const SENTINEL: SbPeriodicReply = SbPeriodicReply {
        state: SbPeriodicState { counter: 0xabcdef01, every: 0x12345678 }, ready: 99,
    };

    // Exact unsigned native branches, independently expressed without min or bool casts.
    fn oracle(op: u32, input: SbPeriodicState, every: u32) -> SbPeriodicReply {
        let mut counter = input.counter;
        let mut period = input.every;
        let mut ready = 0;
        match op {
            INIT => { counter = 0; period = every; }
            SET => {
                period = every;
                if period == 0 { counter = 0; }
                else if counter > period - 1 { counter = period - 1; }
            }
            READY => { if period != 0 && counter == 0 { ready = 1; } }
            TICK => {
                if period != 0 {
                    if counter == 0 { counter = period - 1; ready = 1; }
                    else { counter -= 1; }
                }
            }
            _ => unreachable!(),
        }
        SbPeriodicReply { state: SbPeriodicState { counter, every: period }, ready }
    }

    fn check(op: u32, counter: u32, period: u32, every: u32) {
        let state = SbPeriodicState { counter, every: period };
        let mut out = SENTINEL;
        assert_eq!(unsafe { sb_periodic_run(op, state, every, &mut out) }, OK);
        assert_eq!(out, oracle(op, state, every));
        assert!(out.ready <= 1);
    }

    #[test]
    fn small_domain_and_word_boundaries() {
        for counter in 0..=255 {
            for period in 0..=255 {
                check(SET, counter, u32::MAX, period);
                check(READY, counter, period, 0);
                check(TICK, counter, period, 0);
                check(INIT, counter, period, period);
            }
        }
        let edges = [0, 1, 2, 255, 256, 0x7fffffff, 0x80000000, u32::MAX - 1, u32::MAX];
        for counter in edges {
            for period in edges {
                check(READY, counter, period, 0);
                check(TICK, counter, period, 0);
                for every in edges {
                    check(SET, counter, period, every);
                    check(INIT, counter, period, every);
                }
            }
        }
    }

    #[test]
    fn deterministic_full_word_corpus() {
        let mut word = 0x19abef07u32;
        let mut next = || {
            word ^= word << 13;
            word ^= word >> 17;
            word ^= word << 5;
            word
        };
        for _ in 0..100_000 {
            let (counter, period, every) = (next(), next(), next());
            check(INIT, counter, period, every);
            check(SET, counter, period, every);
            check(READY, counter, period, 0);
            check(TICK, counter, period, 0);
        }
    }

    #[test]
    fn rejects_without_writing_or_counting() {
        let state = SbPeriodicState { counter: u32::MAX, every: 0 };
        let before = std::array::from_fn::<_, COUNT, _>(|op| sb_periodic_count(0, op as u32));
        let mut out = SENTINEL;
        for op in [COUNT as u32, u32::MAX] {
            assert_eq!(unsafe { sb_periodic_run(op, state, 0, &mut out) }, INVALID);
            // Aligned but inaccessible: invalid operation must reject before any access.
            let inaccessible = std::mem::align_of::<SbPeriodicReply>() as *mut SbPeriodicReply;
            assert_eq!(unsafe { sb_periodic_run(op, state, 0, inaccessible) }, INVALID);
        }
        for op in 0..COUNT as u32 {
            assert_eq!(unsafe { sb_periodic_run(op, state, 0, std::ptr::null_mut()) }, INVALID);
            let misaligned = 1usize as *mut SbPeriodicReply;
            assert_eq!(unsafe { sb_periodic_run(op, state, 0, misaligned) }, INVALID);
        }
        for op in [READY, TICK] {
            for every in [1, u32::MAX] {
                assert_eq!(unsafe { sb_periodic_run(op, state, every, &mut out) }, INVALID);
            }
        }
        assert_eq!(out, SENTINEL);
        for op in 0..COUNT {
            assert_eq!(sb_periodic_count(0, op as u32), before[op]);
        }
        for kind in [0, 1, 2, u32::MAX] {
            assert_eq!(sb_periodic_count(kind, COUNT as u32), 0);
            assert_eq!(sb_periodic_count(kind, u32::MAX), 0);
        }
        assert_eq!(sb_periodic_count(2, INIT), 0);
        assert_eq!(sb_periodic_count(u32::MAX, TICK), 0);
    }

    #[test]
    fn independent_counts_and_thread_visibility() {
        let before = COUNTS.with(Cell::get);
        let global = sb_periodic_count(1, TICK);
        for op in 0..COUNT as u32 {
            check(op, 0, 1, 0);
        }
        for op in 0..COUNT {
            assert_eq!(sb_periodic_count(0, op as u32), before[op].wrapping_add(1));
        }
        let parent = COUNTS.with(Cell::get);
        std::thread::spawn(|| {
            for op in 0..COUNT as u32 { assert_eq!(sb_periodic_count(0, op), 0); }
            check(TICK, 0, 1, 0);
            assert_eq!(sb_periodic_count(0, TICK), 1);
            assert_eq!(sb_periodic_count(0, INIT), 0);
        }).join().unwrap();
        assert_eq!(COUNTS.with(Cell::get), parent);
        // Other tests may run concurrently; totals are not an atomic multi-op snapshot.
        assert!(sb_periodic_count(1, TICK).wrapping_sub(global) >= 2);
    }

    #[test]
    fn both_counter_stores_wrap_independently() {
        let counts = Cell::new([u64::MAX, 7, 8, 9]);
        let totals = [AtomicU64::new(u64::MAX), AtomicU64::new(2),
            AtomicU64::new(3), AtomicU64::new(4)];
        increment(&counts, &totals, INIT as usize);
        assert_eq!(counts.get(), [0, 7, 8, 9]);
        assert_eq!(totals[0].load(Ordering::Relaxed), 0);
        assert_eq!(totals[1].load(Ordering::Relaxed), 2);
    }
}
