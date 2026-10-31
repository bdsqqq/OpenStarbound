//! In-place vector control only: native callbacks own allocator and pair lifetimes.
//! The all-zero representation is empty. Copying RawSlots is a transient read,
//! NOT permission to duplicate an allocated owner. See StarRustNetGroupStorage.h.
use std::cell::Cell;
use std::ffi::c_void;
use std::mem::{align_of, size_of};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST: u32 = 2;
const PANIC: u32 = 3;
const DATA: u32 = 0;
const SIZE: u32 = 1;
const CAPACITY: u32 = 2;
const APPEND: u32 = 3;
const CLEAR: u32 = 4;
const DROP: u32 = 5;
const CONTAINS: u32 = 6;
const COUNT: usize = 7;

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct RawSlots { allocation: usize, len: usize, cap: usize }
const EMPTY: RawSlots = RawSlots { allocation: 0, len: 0, cap: 0 };

type MaxSize = unsafe extern "C" fn(*mut c_void) -> usize;
type Allocate = unsafe extern "C" fn(*mut c_void, usize, *mut usize) -> u32;
type Construct = unsafe extern "C" fn(*mut c_void, usize, usize);
type MoveOld = unsafe extern "C" fn(*mut c_void, usize, usize, usize);
type Element = unsafe extern "C" fn(*mut c_void, usize, usize) -> usize;
type LengthError = unsafe extern "C" fn(*mut c_void) -> u32;

#[repr(C)]
#[derive(Clone, Copy)]
pub struct SbNetGroupStorageOps {
    context: *mut c_void,
    max_size: Option<MaxSize>,
    allocate: Option<Allocate>,
    construct_new: Option<Construct>,
    move_old: Option<MoveOld>,
    destroy: Option<Construct>,
    deallocate: Option<Construct>,
    element: Option<Element>,
    length_error: Option<LengthError>,
}

// Nonnullable copies resolved BEFORE any allocation/callback. No Rust reference
// to foreign state/ops is retained across calls (including read-only reentry).
#[derive(Clone, Copy)]
struct Hooks {
    context: *mut c_void,
    max_size: MaxSize,
    allocate: Allocate,
    construct_new: Construct,
    move_old: MoveOld,
    destroy: Construct,
    deallocate: Construct,
    element: Element,
    length_error: LengthError,
}
impl SbNetGroupStorageOps {
    fn hooks(self) -> Option<Hooks> {
        Some(Hooks { context: self.context, max_size: self.max_size?,
            allocate: self.allocate?, construct_new: self.construct_new?,
            move_old: self.move_old?, destroy: self.destroy?,
            deallocate: self.deallocate?, element: self.element?,
            length_error: self.length_error? })
    }
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
fn overlap(a: usize, n: usize, b: usize, m: usize) -> bool {
    if a <= b { b - a < n } else { a - b < m }
}
fn address(p: usize, size: usize, alignment: usize) -> bool {
    p != 0 && p % alignment == 0 && p.checked_add(size).is_some()
}

// Validation reads only initialized, live foreign objects supplied by caller.
// The private seam is BEFORE allocation, including before any native callback.
unsafe fn checked(mode: u32, state: *const c_void, ops: *const SbNetGroupStorageOps,
    argument: usize, out: *mut usize, before_allocation: impl FnOnce()) -> u32 {
    let s = state as usize;
    let o = out as usize;
    if mode >= COUNT as u32 || (mode != CONTAINS && argument != 0)
        || !address(s, size_of::<RawSlots>(), align_of::<RawSlots>())
        || !address(o, size_of::<usize>(), align_of::<usize>())
        || overlap(s, size_of::<RawSlots>(), o, size_of::<usize>()) {
        return INVALID;
    }
    let hooks = if mode <= CAPACITY {
        if !ops.is_null() { return INVALID; }
        None
    } else {
        let p = ops as usize;
        if !address(p, size_of::<SbNetGroupStorageOps>(), align_of::<SbNetGroupStorageOps>())
            || overlap(p, size_of::<SbNetGroupStorageOps>(), s, size_of::<RawSlots>())
            || overlap(p, size_of::<SbNetGroupStorageOps>(), o, size_of::<usize>()) {
            return INVALID;
        }
        match ops.read().hooks() {
            Some(h) => Some(h),
            None => return INVALID,
        }
    };
    let old = state.cast::<RawSlots>().read();
    if old.len > old.cap || ((old.cap == 0) != (old.allocation == 0)) {
        return INVALID;
    }
    catch_unwind(AssertUnwindSafe(|| {
        count_entry(mode as usize);
        before_allocation();
        // Resolve the Option before foreign allocation; no unwrap/assertion or
        // indexed data access exists on the post-allocation production path.
        let result = match mode {
            DATA => old.allocation,
            SIZE => old.len,
            CAPACITY => old.cap,
            _ => {
                let h = match hooks { Some(h) => h, None => return INVALID };
                let ctx = h.context;
                match mode {
                    APPEND => {
                        if old.len < old.cap {
                            let len = old.len + 1; // len < cap <= usize::MAX
                            (h.construct_new)(ctx, old.allocation, old.len);
                            state.cast_mut().cast::<RawSlots>().write(RawSlots { len, ..old });
                        } else {
                            let max = (h.max_size)(ctx);
                            if old.len >= max {
                                // Native catches/reports its ORIGINAL length_error.
                                (h.length_error)(ctx);
                                return HOST;
                            }
                            let len = old.len + 1;
                            // libc++ vector::__recommend, including odd/max=1.
                            // In the doubling branch cap<max/2, so 2*cap cannot
                            // overflow. Compute every fallible value before alloc.
                            let cap = if old.cap >= max / 2 { max }
                                else { (2 * old.cap).max(len) };
                            let mut allocation = 0usize;
                            if (h.allocate)(ctx, cap, &mut allocation) != OK {
                                return HOST;
                            }
                            // Successful allocation is a nonnull valid native
                            // buffer by contract. Rust never dereferences payload.
                            (h.construct_new)(ctx, allocation, old.len);
                            let mut i = 0;
                            while i < old.len {
                                (h.move_old)(ctx, old.allocation, allocation, i);
                                i += 1;
                            }
                            let mut i = old.len;
                            while i != 0 {
                                i -= 1;
                                (h.destroy)(ctx, old.allocation, i);
                            }
                            state.cast_mut().cast::<RawSlots>().write(RawSlots { allocation, len, cap });
                            // Native delete hooks may read the owner: commit FIRST.
                            if old.cap != 0 { (h.deallocate)(ctx, old.allocation, old.cap); }
                        }
                        0
                    }
                    CLEAR | DROP => {
                        let mut i = old.len;
                        while i != 0 {
                            i -= 1;
                            (h.destroy)(ctx, old.allocation, i);
                        }
                        let next = if mode == DROP { EMPTY } else { RawSlots { len: 0, ..old } };
                        state.cast_mut().cast::<RawSlots>().write(next);
                        if mode == DROP && old.cap != 0 {
                            (h.deallocate)(ctx, old.allocation, old.cap);
                        }
                        0
                    }
                    CONTAINS => {
                        let mut found = 0;
                        let mut i = 0;
                        while i < old.len {
                            if (h.element)(ctx, old.allocation, i) == argument {
                                found = 1;
                                break;
                            }
                            i += 1;
                        }
                        found
                    }
                    _ => return INVALID,
                }
            }
        };
        out.write(result);
        OK
    })).unwrap_or(PANIC)
}

/// # Safety
/// Caller supplies initialized live state/ops and writable disjoint out. Mutation
/// requires writable state; all native hook/lifetime/exception obligations are
/// specified in StarRustNetGroupStorage.h. Address checks do not prove them.
#[no_mangle]
pub unsafe extern "C" fn sb_net_group_storage_run(mode: u32, state: *const c_void,
    ops: *const SbNetGroupStorageOps, argument: usize, out: *mut usize) -> u32 {
    checked(mode, state, ops, argument, out, || {})
}

/// Accepted root diagnostics only; no synchronized state/completion snapshot.
#[no_mangle]
pub extern "C" fn sb_net_group_storage_count(kind: u32, mode: u32) -> u64 {
    catch_unwind(|| match (kind, mode as usize) {
        (0, i) if i < COUNT => COUNTS.with(|c| c.get()[i]),
        (1, i) if i < COUNT => TOTALS[i].load(Ordering::Relaxed),
        _ => 0,
    }).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;
    use std::ptr;

    #[derive(Debug, PartialEq, Eq)]
    enum Event { Alloc(usize, usize), New(usize, usize), Move(usize, usize, usize),
        Destroy(usize, usize), Free(usize, usize), Length }
    struct Mock {
        state: *const c_void,
        max: usize,
        next: usize,
        value: (usize, bool),
        fail: bool,
        buffers: BTreeMap<usize, BTreeMap<usize, (usize, bool)>>,
        attempts: Vec<usize>,
        log: Vec<Event>,
        observed: Vec<RawSlots>,
    }
    impl Mock {
        fn new() -> Self {
            Self { state: ptr::null(), max: usize::MAX, next: 1, value: (0, false), fail: false,
                buffers: BTreeMap::new(), attempts: Vec::new(), log: Vec::new(), observed: Vec::new() }
        }
        fn ops(&mut self) -> SbNetGroupStorageOps {
            SbNetGroupStorageOps { context: (self as *mut Self).cast(), max_size: Some(max_size),
                allocate: Some(allocate), construct_new: Some(construct_new), move_old: Some(move_old),
                destroy: Some(destroy), deallocate: Some(deallocate), element: Some(element),
                length_error: Some(length_error) }
        }
    }
    unsafe extern "C" fn max_size(p: *mut c_void) -> usize { (*p.cast::<Mock>()).max }
    unsafe extern "C" fn allocate(p: *mut c_void, n: usize, out: *mut usize) -> u32 {
        let m = &mut *p.cast::<Mock>();
        m.attempts.push(n);
        if m.fail { return HOST; }
        let id = m.next;
        m.next += 1;
        m.buffers.insert(id, BTreeMap::new());
        m.log.push(Event::Alloc(id, n));
        out.write(id);
        OK
    }
    unsafe extern "C" fn construct_new(p: *mut c_void, b: usize, i: usize) {
        let m = &mut *p.cast::<Mock>();
        assert!(m.buffers.get_mut(&b).unwrap().insert(i, m.value).is_none());
        m.log.push(Event::New(b, i));
    }
    unsafe extern "C" fn move_old(p: *mut c_void, old: usize, new: usize, i: usize) {
        let m = &mut *p.cast::<Mock>();
        let value = m.buffers[&old][&i];
        assert!(m.buffers.get_mut(&new).unwrap().insert(i, value).is_none());
        m.log.push(Event::Move(old, new, i));
    }
    unsafe extern "C" fn destroy(p: *mut c_void, b: usize, i: usize) {
        let m = &mut *p.cast::<Mock>();
        assert!(m.buffers.get_mut(&b).unwrap().remove(&i).is_some());
        m.log.push(Event::Destroy(b, i));
    }
    unsafe extern "C" fn deallocate(p: *mut c_void, b: usize, cap: usize) {
        let m = &mut *p.cast::<Mock>();
        // Real root reentry, without ops/context references retained by kernel.
        let mut words = [usize::MAX; 3];
        for mode in 0..=CAPACITY {
            assert_eq!(sb_net_group_storage_run(mode, m.state, ptr::null(), 0,
                &mut words[mode as usize]), OK);
        }
        let seen = RawSlots { allocation: words[0], len: words[1], cap: words[2] };
        assert_ne!(seen.allocation, b);
        assert!(m.buffers.remove(&b).unwrap().is_empty());
        m.observed.push(seen);
        m.log.push(Event::Free(b, cap));
    }
    unsafe extern "C" fn element(p: *mut c_void, b: usize, i: usize) -> usize {
        let m = &*p.cast::<Mock>();
        m.buffers[&b][&i].0
    }
    unsafe extern "C" fn length_error(p: *mut c_void) -> u32 {
        (*p.cast::<Mock>()).log.push(Event::Length);
        HOST
    }
    fn call(mode: u32, s: *const c_void, ops: *const SbNetGroupStorageOps, arg: usize) -> usize {
        let mut out = usize::MAX;
        assert_eq!(unsafe { sb_net_group_storage_run(mode, s, ops, arg, &mut out) }, OK);
        out
    }
    fn counts() -> [u64; COUNT] {
        std::array::from_fn(|i| sb_net_group_storage_count(0, i as u32))
    }
    fn p(s: &mut RawSlots) -> *const c_void { (s as *mut RawSlots).cast() }

    #[test]
    fn zero_layout_and_readonly_getters_preserve_all_bytes() {
        assert_eq!(size_of::<RawSlots>(), 3 * size_of::<usize>());
        assert_eq!(align_of::<RawSlots>(), align_of::<usize>());
        assert!(!std::mem::needs_drop::<RawSlots>());
        let s = EMPTY;
        let state = (&s as *const RawSlots).cast();
        for mode in 0..=CAPACITY { assert_eq!(call(mode, state, ptr::null(), 0), 0); }
        assert_eq!(s, EMPTY);
        let raw: [usize; 3] = [17, 2, 3];
        for mode in 0..=CAPACITY {
            assert_eq!(call(mode, raw.as_ptr().cast(), ptr::null(), 0), raw[mode as usize]);
        }
        assert_eq!(raw, [17, 2, 3]);
    }

    #[test]
    fn growth_constructs_new_first_and_commits_before_free() {
        let mut s = EMPTY;
        let state = p(&mut s);
        let mut m = Mock::new(); m.state = state;
        let ops = m.ops();
        for value in [11, 22, 33] {
            m.value = (value, value & 1 != 0);
            assert_eq!(call(APPEND, state, &ops, 0), 0);
        }
        assert_eq!(s, RawSlots { allocation: 3, len: 3, cap: 4 });
        assert_eq!(m.log, vec![Event::Alloc(1, 1), Event::New(1, 0),
            Event::Alloc(2, 2), Event::New(2, 1), Event::Move(1, 2, 0),
            Event::Destroy(1, 0), Event::Free(1, 1),
            Event::Alloc(3, 4), Event::New(3, 2), Event::Move(2, 3, 0),
            Event::Move(2, 3, 1), Event::Destroy(2, 1), Event::Destroy(2, 0), Event::Free(2, 2)]);
        assert_eq!(m.observed, vec![RawSlots { allocation: 2, len: 2, cap: 2 }, s]);
        for value in [11, 22, 33] { assert_eq!(call(CONTAINS, state, &ops, value), 1); }
        assert_eq!(call(CONTAINS, state, &ops, 44), 0);
        call(DROP, state, &ops, 0);
        assert_eq!(s, EMPTY);
        assert!(m.buffers.is_empty());
        assert_eq!(m.observed.last(), Some(&EMPTY));
        let n = m.log.len();
        call(DROP, state, &ops, 0);
        assert_eq!(m.log.len(), n);
    }

    #[test]
    fn clear_retains_buffer_reuses_capacity_and_reverse_destruction() {
        let mut s = EMPTY; let state = p(&mut s);
        let mut m = Mock::new(); m.state = state; let ops = m.ops();
        for _ in 0..3 { call(APPEND, state, &ops, 0); }
        let old = s;
        m.log.clear();
        call(CLEAR, state, &ops, 0);
        assert_eq!(s, RawSlots { len: 0, ..old });
        assert_eq!(m.log, vec![Event::Destroy(old.allocation, 2),
            Event::Destroy(old.allocation, 1), Event::Destroy(old.allocation, 0)]);
        call(CLEAR, state, &ops, 0);
        m.log.clear();
        call(APPEND, state, &ops, 0);
        assert_eq!(m.log, vec![Event::New(old.allocation, 0)]);
        assert_eq!(s.cap, old.cap);
        call(DROP, state, &ops, 0);
    }

    #[test]
    fn failed_allocation_preserves_initialized_owner_and_output() {
        let mut s = EMPTY; let state = p(&mut s);
        let mut m = Mock::new(); m.state = state; let ops = m.ops();
        call(APPEND, state, &ops, 0);
        let old = s; let log = m.log.len(); m.fail = true;
        let mut out = 123;
        let before = counts();
        assert_eq!(unsafe { sb_net_group_storage_run(APPEND, state, &ops, 0, &mut out) }, HOST);
        assert_eq!(s, old); assert_eq!(out, 123); assert_eq!(m.log.len(), log);
        assert_eq!(sb_net_group_storage_count(0, APPEND), before[APPEND as usize] + 1);
        m.fail = false;
        call(DROP, state, &ops, 0);
    }

    #[test]
    fn capacity_boundaries_zero_one_odd_and_usize_edges() {
        // Every fixture is fully initialized; integer IDs are opaque, never dereferenced.
        for max in [0, 1, 7, 9, usize::MAX - 1, usize::MAX] {
            let mut s = EMPTY; let state = p(&mut s);
            let mut m = Mock::new(); m.state = state; m.max = max; let ops = m.ops();
            if max == 0 {
                let mut out = 71;
                assert_eq!(unsafe { sb_net_group_storage_run(APPEND, state, &ops, 0, &mut out) }, HOST);
                assert_eq!(s, EMPTY); assert_eq!(out, 71); assert_eq!(m.log, vec![Event::Length]);
            } else {
                let steps = max.min(9);
                let mut expected_cap = 0;
                for len in 1..=steps {
                    if len > expected_cap {
                        expected_cap = if expected_cap >= max / 2 { max }
                            else { std::cmp::max(expected_cap * 2, len) };
                    }
                    call(APPEND, state, &ops, 0);
                    assert_eq!(s.cap, expected_cap);
                }
                if steps == max {
                    let old = s; let mut out = 71;
                    assert_eq!(unsafe { sb_net_group_storage_run(APPEND, state, &ops, 0, &mut out) }, HOST);
                    assert_eq!(s, old); assert_eq!(out, 71);
                }
                call(DROP, state, &ops, 0);
            }
        }
        // Failed allocations exercise huge growth recommendations without payload
        // loops or real huge allocations; every state word is initialized.
        for max in [7, 9, usize::MAX - 1, usize::MAX] {
            for cap in [max / 2 - 1, max / 2, max - 1] {
                let mut s = RawSlots { allocation: 7, len: cap, cap };
                let state = p(&mut s); let saved = s;
                let mut m = Mock::new(); m.max = max; m.fail = true; let ops = m.ops();
                let mut out = 101;
                assert_eq!(unsafe { sb_net_group_storage_run(APPEND, state, &ops, 0, &mut out) }, HOST);
                let expected = if cap >= max / 2 { max } else { (2 * cap).max(cap + 1) };
                assert_eq!(m.attempts, vec![expected]);
                assert_eq!(s, saved); assert_eq!(out, 101); assert!(m.log.is_empty());
            }
        }
        // Huge full states reject at the bound without touching opaque payloads.
        for max in [usize::MAX - 1, usize::MAX] {
            let mut s = RawSlots { allocation: 7, len: max, cap: max };
            let state = p(&mut s); let mut m = Mock::new(); m.max = max; let ops = m.ops();
            let saved = s; let mut out = 83;
            assert_eq!(unsafe { sb_net_group_storage_run(APPEND, state, &ops, 0, &mut out) }, HOST);
            assert_eq!(s, saved); assert_eq!(out, 83); assert_eq!(m.log, vec![Event::Length]);
        }
    }

    #[test]
    fn hundred_thousand_push_clear_word_model() {
        let mut s = EMPTY; let state = p(&mut s);
        let mut m = Mock::new(); m.state = state; let ops = m.ops();
        let mut model = Vec::new();
        for i in 0..100_000usize {
            if i % 127 == 126 {
                call(CLEAR, state, &ops, 0); model.clear();
            } else {
                m.value = (i.wrapping_mul(0x9e37), i & 1 != 0);
                call(APPEND, state, &ops, 0); model.push(m.value);
            }
            assert_eq!(s.len, model.len());
            let actual: Vec<_> = m.buffers[&s.allocation].values().copied().collect();
            assert_eq!(actual, model);
            assert_eq!(call(CONTAINS, state, &ops, usize::MAX), 0);
            if let Some(&(v, _)) = model.last() { assert_eq!(call(CONTAINS, state, &ops, v), 1); }
            m.log.clear();
        }
        call(DROP, state, &ops, 0);
        assert!(m.buffers.is_empty());
    }

    #[test]
    fn invalid_addresses_unused_ops_hooks_state_and_overlaps_never_count_or_write() {
        let mut words = [0usize; 12]; let state = words.as_mut_ptr().cast::<c_void>();
        let mut m = Mock::new(); let ops = m.ops();
        let mut out = 91; let before = counts();
        for mode in 0..COUNT as u32 {
            let hooks = if mode <= CAPACITY { ptr::null() } else { &ops };
            for bad in [ptr::null(), unsafe { state.cast::<u8>().add(1).cast() }] {
                assert_eq!(unsafe { sb_net_group_storage_run(mode, bad, hooks, 0, &mut out) }, INVALID);
            }
            for output in [ptr::null_mut(), unsafe { words.as_mut_ptr().cast::<u8>().add(1).cast() }] {
                assert_eq!(unsafe { sb_net_group_storage_run(mode, state, hooks, 0, output) }, INVALID);
            }
            for i in 0..3 {
                assert_eq!(unsafe { sb_net_group_storage_run(mode, state, hooks, 0, words.as_mut_ptr().add(i)) }, INVALID);
            }
            // State begins inside the output word (unaligned partial overlap).
            for i in 1..size_of::<usize>() {
                let shifted = unsafe { words.as_ptr().cast::<u8>().add(i).cast() };
                assert_eq!(unsafe { sb_net_group_storage_run(mode, shifted, hooks, 0, words.as_mut_ptr()) }, INVALID);
            }
            if mode != CONTAINS {
                assert_eq!(unsafe { sb_net_group_storage_run(mode, state, hooks, 1, &mut out) }, INVALID);
            }
        }
        for mode in [COUNT as u32, u32::MAX] {
            assert_eq!(unsafe { sb_net_group_storage_run(mode, state, ptr::null(), 0, &mut out) }, INVALID);
        }
        for mode in 0..=CAPACITY {
            assert_eq!(unsafe { sb_net_group_storage_run(mode, state, &ops, 0, &mut out) }, INVALID);
        }
        for mode in APPEND..=CONTAINS {
            // All bytes initialized; rejected before interpreting ops as state or
            // an output word. No invalid foreign object is dereferenced.
            let mut aliased = ops;
            let a = &mut aliased as *mut SbNetGroupStorageOps;
            assert_eq!(unsafe { sb_net_group_storage_run(mode, a.cast(), a, 0, &mut out) }, INVALID);
            assert_eq!(unsafe { sb_net_group_storage_run(mode, state, a, 0, a.cast()) }, INVALID);
            assert_eq!(unsafe { sb_net_group_storage_run(mode, state, ptr::null(), 0, &mut out) }, INVALID);
            let unaligned = unsafe { (&ops as *const SbNetGroupStorageOps).cast::<u8>().add(1).cast() };
            assert_eq!(unsafe { sb_net_group_storage_run(mode, state, unaligned, 0, &mut out) }, INVALID);
            // Check EACH nullable slot, not just one hook used by this mode.
            for slot in 0..8 {
                let mut bad = ops;
                match slot { 0 => bad.max_size = None, 1 => bad.allocate = None,
                    2 => bad.construct_new = None, 3 => bad.move_old = None,
                    4 => bad.destroy = None, 5 => bad.deallocate = None,
                    6 => bad.element = None, _ => bad.length_error = None }
                assert_eq!(unsafe { sb_net_group_storage_run(mode, state, &bad, 0, &mut out) }, INVALID);
            }
        }
        for bad in [RawSlots { allocation: 0, len: 0, cap: 1 },
            RawSlots { allocation: 1, len: 0, cap: 0 }, RawSlots { allocation: 1, len: 2, cap: 1 },
            RawSlots { allocation: 0, len: 1, cap: 0 }] {
            assert_eq!(unsafe { sb_net_group_storage_run(SIZE, (&bad as *const RawSlots).cast(), ptr::null(), 0, &mut out) }, INVALID);
        }
        assert_eq!(counts(), before); assert_eq!(out, 91); assert_eq!(words, [0; 12]);
        assert!(m.log.is_empty());
    }

    #[test]
    fn panic_seam_is_before_allocation_and_preserves_initialized_bytes() {
        let mut s = EMPTY; let state = p(&mut s);
        let mut m = Mock::new(); let ops = m.ops();
        for mode in 0..COUNT as u32 {
            let mut out = 97;
            let before = counts();
            let hooks = if mode <= CAPACITY { ptr::null() } else { &ops };
            assert_eq!(unsafe { checked(mode, state, hooks, 0, &mut out, || panic!("before allocation")) }, PANIC);
            assert_eq!(s, EMPTY); assert_eq!(out, 97); assert!(m.log.is_empty());
            let after = counts();
            for i in 0..COUNT { assert_eq!(after[i], before[i].wrapping_add(u64::from(i == mode as usize))); }
        }
    }

    #[test]
    fn tls_global_and_wrap_only_seven_roots() {
        let before = counts();
        let globals: [u64; COUNT] = std::array::from_fn(|i| sb_net_group_storage_count(1, i as u32));
        std::thread::spawn(|| {
            let mut s = EMPTY; let state = p(&mut s);
            let mut m = Mock::new(); m.state = state; let ops = m.ops();
            for mode in 0..COUNT as u32 {
                assert_eq!(sb_net_group_storage_count(0, mode), 0);
                call(mode, state, if mode <= CAPACITY { ptr::null() } else { &ops }, 0);
                assert_eq!(sb_net_group_storage_count(0, mode), 1);
            }
        }).join().unwrap();
        assert_eq!(counts(), before);
        for i in 0..COUNT {
            assert!(sb_net_group_storage_count(1, i as u32).wrapping_sub(globals[i]) >= 1);
        }
        for kind in [0, 1, 2, u32::MAX] {
            assert_eq!(sb_net_group_storage_count(kind, COUNT as u32), 0);
        }
        for mode in 0..COUNT as u32 { assert_eq!(sb_net_group_storage_count(2, mode), 0); }
        COUNTS.with(|c| {
            let saved = c.get(); c.set([u64::MAX; COUNT]);
            for i in 0..COUNT { count_entry(i); assert_eq!(sb_net_group_storage_count(0, i as u32), 0); }
            c.set(saved);
        });
        let a = AtomicU64::new(u64::MAX);
        a.fetch_add(1, Ordering::Relaxed); assert_eq!(a.load(Ordering::Relaxed), 0);
    }
}
