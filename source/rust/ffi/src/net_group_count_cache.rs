//! Private, nonescaping u32 -> usize count owner. Native C++ supplies allocation,
//! the actual hasher, and WHOLE floating capacity expressions. No Rust allocator
//! or floating point is used by production. See StarRustNetGroupCountCache.h.
use std::cell::Cell;
use std::ffi::c_void;
use std::mem::{align_of, size_of, MaybeUninit};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::ptr::{addr_of, addr_of_mut};
use std::sync::atomic::{AtomicU64, Ordering};

const OK: u32 = 0;
const INVALID: u32 = 1;
const HOST: u32 = 2;
const PANIC: u32 = 3;
const INCREMENT: u32 = 0;
const LOOKUP: u32 = 1;
const CLEAR: u32 = 2;
const DROP: u32 = 3;
const SIZE: u32 = 4;
const COUNT: usize = 5;
const FILLED: usize = 1usize << (usize::BITS - 1);

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct State { buffer: usize, len: usize, cap: usize, filled: usize }
const ZERO: State = State { buffer: 0, len: 0, cap: 0, filled: 0 };

// NEVER read/write a whole Slot: key's trailing padding may be uninitialized,
// and empty/sentinel payloads are intentionally uninitialized or stale.
#[repr(C)]
struct Slot { key: MaybeUninit<u32>, count: MaybeUninit<usize>, hash: usize }
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SbNetGroupCountCacheReply { value: usize, found: u32, reserved: u32 }
const EMPTY_REPLY: SbNetGroupCountCacheReply = SbNetGroupCountCacheReply { value: 0, found: 0, reserved: 0 };
type Hash = unsafe extern "C" fn(*mut c_void, u32) -> usize;
type Plan = unsafe extern "C" fn(*mut c_void, usize, usize, *mut usize) -> u32;
type Allocate = unsafe extern "C" fn(*mut c_void, usize, *mut usize) -> u32;
type Deallocate = unsafe extern "C" fn(*mut c_void, usize, usize);
#[repr(C)]
#[derive(Clone, Copy)]
pub struct SbNetGroupCountCacheOps {
    context: *mut c_void,
    hash: Option<Hash>,
    plan: Option<Plan>,
    allocate: Option<Allocate>,
    deallocate: Option<Deallocate>,
}
#[derive(Clone, Copy)]
struct Hooks { context: *mut c_void, hash: Hash, plan: Plan, allocate: Allocate, deallocate: Deallocate }
impl SbNetGroupCountCacheOps {
    fn full(self) -> Option<Hooks> {
        Some(Hooks { context: self.context, hash: self.hash?, plan: self.plan?,
            allocate: self.allocate?, deallocate: self.deallocate? })
    }
}
static TOTALS: [AtomicU64; COUNT] = [const { AtomicU64::new(0) }; COUNT];
thread_local! { static COUNTS: Cell<[u64; COUNT]> = const { Cell::new([0; COUNT]) }; }
fn count_entry(mode: usize) {
    TOTALS[mode].fetch_add(1, Ordering::Relaxed);
    COUNTS.with(|c| { let mut a = c.get(); a[mode] = a[mode].wrapping_add(1); c.set(a); });
}
fn overlap(a: usize, n: usize, b: usize, m: usize) -> bool {
    n != 0 && m != 0 && if a <= b { b - a < n } else { a - b < m }
}
fn address(a: usize, n: usize, alignment: usize) -> bool {
    a != 0 && a % alignment == 0 && n <= isize::MAX as usize && a.checked_add(n).is_some()
}
fn extent(len: usize) -> Option<usize> {
    if len < 9 || !(len - 1).is_power_of_two() { return None; }
    len.checked_mul(size_of::<Slot>()).filter(|&n| n <= isize::MAX as usize)
}
unsafe fn slot(s: State, i: usize) -> *mut Slot { (s.buffer as *mut Slot).add(i) }
unsafe fn hash_at(s: State, i: usize) -> usize { addr_of!((*slot(s, i)).hash).read() }
unsafe fn key_at(s: State, i: usize) -> u32 {
    // Only called after reading a filled hash, never on empty/sentinel payload.
    addr_of!((*slot(s, i)).key).cast::<u32>().read()
}
unsafe fn count_at(s: State, i: usize) -> usize { addr_of!((*slot(s, i)).count).cast::<usize>().read() }
unsafe fn write_entry(s: State, i: usize, key: u32, count: usize, hash: usize) {
    let p = slot(s, i);
    addr_of_mut!((*p).key).cast::<u32>().write(key);
    addr_of_mut!((*p).count).cast::<usize>().write(count);
    addr_of_mut!((*p).hash).write(hash);
}
unsafe fn commit(p: *const c_void, s: State) { p.cast_mut().cast::<State>().write(s); }

unsafe fn find(s: State, hash: Hash, ctx: *mut c_void, key: u32) -> Option<usize> {
    if s.len == 0 { return None; }
    let hash = hash(ctx, key) | FILLED;
    let mask = s.len - 2;
    let target = hash & mask;
    let mut current = target;
    loop {
        let entry = hash_at(s, current);
        if entry & FILLED == 0 { return None; }
        if entry == hash && key_at(s, current) == key { return Some(current); }
        let entry_error = current.wrapping_sub(entry) & mask;
        let find_error = current.wrapping_sub(target) & mask;
        if find_error > entry_error { return None; }
        current = current.wrapping_add(1) & mask;
    }
}

// Native insert's probing policy, after native capacity planning. The index of
// the original value survives Robin Hood swaps so outer operator[]++ hits it.
unsafe fn insert_ready(p: *const c_void, mut s: State, h: Hooks, mut key: u32, mut count: usize) -> usize {
    let mut hash = (h.hash)(h.context, key) | FILLED;
    let mask = s.len - 2;
    let mut target = hash & mask;
    let mut current = target;
    let mut inserted = None;
    loop {
        let entry = hash_at(s, current);
        if entry & FILLED != 0 {
            let old_key = key_at(s, current);
            if entry == hash && old_key == key { return current; }
            let entry_target = entry & mask;
            if (current.wrapping_sub(target) & mask) > (current.wrapping_sub(entry_target) & mask) {
                if inserted.is_none() { inserted = Some(current); }
                let old_count = count_at(s, current);
                write_entry(s, current, key, count, hash);
                key = old_key; count = old_count; hash = entry; target = entry_target;
            }
            current = current.wrapping_add(1) & mask;
        } else {
            write_entry(s, current, key, count, hash);
            s.filled = s.filled.wrapping_add(1);
            commit(p, s);
            return inserted.unwrap_or(current);
        }
    }
}

// Callback's successful plan is a native capacity result, not arbitrary input.
// Check the representable result before committing the native swap prefix.
unsafe fn insert(p: *const c_void, old: State, h: Hooks, key: u32, count: usize) -> Result<usize, u32> {
    let mut newlen = 0;
    if (h.plan)(h.context, old.filled, old.len, &mut newlen) != OK { return Err(HOST); }
    if newlen != 0 {
        if extent(newlen).is_none() || newlen <= old.len || old.filled >= newlen - 1 { return Err(INVALID); }
        // Native swap into local oldBuckets precedes resize. A resize failure
        // STILL destroys oldBuckets, while native filled remains stale.
        commit(p, State { filled: old.filled, ..ZERO });
        let mut buffer = 0;
        if (h.allocate)(h.context, newlen, &mut buffer) != OK {
            if old.cap != 0 { (h.deallocate)(h.context, old.buffer, old.cap); }
            return Err(HOST);
        }
        let next = State { buffer, len: newlen, cap: newlen, filled: 0 };
        let mut i = 0;
        while i < newlen {
            addr_of_mut!((*slot(next, i)).hash).write(0);
            i += 1;
        }
        addr_of_mut!((*slot(next, newlen - 1)).hash).write(1);
        commit(p, next);
        let mut result = Ok(());
        let mut i = 0;
        while i < old.len {
            if hash_at(old, i) & FILLED != 0 {
                let old_key = key_at(old, i);
                let old_count = count_at(old, i);
                let now = p.cast::<State>().read();
                // Native reinsert calls insert (not operator[]): capacity check
                // and hash again, old slot order, no preceding find callback.
                if let Err(status) = insert(p, now, h, old_key, old_count) { result = Err(status); break; }
            }
            i += 1;
        }
        if old.cap != 0 { (h.deallocate)(h.context, old.buffer, old.cap); }
        result?;
    }
    let current = p.cast::<State>().read();
    // Successful native plan guarantees usable/sufficient space (including
    // newlen==0). No host schema or allocator repair is attempted here.
    Ok(insert_ready(p, current, h, key, count))
}

unsafe fn checked(mode: u32, state: *const c_void, ops: *const SbNetGroupCountCacheOps,
    key: u32, out: *mut SbNetGroupCountCacheReply, before_commit: impl FnOnce()) -> u32 {
    let s = state as usize; let o = out as usize;
    let sn = size_of::<State>(); let on = size_of::<SbNetGroupCountCacheReply>();
    if mode >= COUNT as u32 || (mode != INCREMENT && mode != LOOKUP && key != 0)
        || !address(s, sn, align_of::<State>())
        || !address(o, on, align_of::<SbNetGroupCountCacheReply>()) || overlap(s, sn, o, on) { return INVALID; }
    let old = state.cast::<State>().read();
    let bytes = if old.len == 0 {
        if old.buffer != 0 || old.cap != 0 { return INVALID; }
        0 // stale filled intentionally permitted after native allocation failure
    } else {
        let n = match extent(old.len) { Some(n) => n, None => return INVALID };
        if old.cap != old.len || old.filled > old.len - 1
            || !address(old.buffer, n, align_of::<Slot>()) { return INVALID; }
        n
    };
    if overlap(old.buffer, bytes, s, sn) || overlap(old.buffer, bytes, o, on) { return INVALID; }
    let supplied = if mode == CLEAR || mode == SIZE {
        if !ops.is_null() { return INVALID; }
        None
    } else {
        let a = ops as usize; let n = size_of::<SbNetGroupCountCacheOps>();
        if !address(a, n, align_of::<SbNetGroupCountCacheOps>()) || overlap(a, n, s, sn)
            || overlap(a, n, o, on) || overlap(a, n, old.buffer, bytes) { return INVALID; }
        Some(ops.read())
    };
    // Resolve nullable fields BEFORE the panic seam, counts, or callbacks.
    let mut full = None; let mut lookup = None; let mut drop_hook = None;
    match mode {
        INCREMENT => { full = supplied.and_then(|h| h.full()); if full.is_none() { return INVALID; } }
        LOOKUP => {
            let h = match supplied { Some(h) => h, None => return INVALID };
            if h.hash.is_none() || h.plan.is_some() || h.allocate.is_some() || h.deallocate.is_some() { return INVALID; }
            lookup = h.hash.map(|hash| (h.context, hash));
        }
        DROP => {
            let h = match supplied { Some(h) => h, None => return INVALID };
            if h.hash.is_some() || h.plan.is_some() || h.allocate.is_some() || h.deallocate.is_none() { return INVALID; }
            drop_hook = h.deallocate.map(|free| (h.context, free));
        }
        _ => {}
    }
    catch_unwind(AssertUnwindSafe(|| {
        count_entry(mode as usize);
        before_commit();
        let mut reply = EMPTY_REPLY;
        match mode {
            INCREMENT => {
                let h = match full { Some(h) => h, None => return INVALID };
                let index = match find(old, h.hash, h.context, key) {
                    Some(i) => i,
                    None => match insert(state, old, h, key, 0) { Ok(i) => i, Err(status) => return status },
                };
                let now = state.cast::<State>().read();
                let value = count_at(now, index).wrapping_add(1);
                addr_of_mut!((*slot(now, index)).count).cast::<usize>().write(value);
            }
            LOOKUP => {
                let (ctx, hash) = match lookup { Some(h) => h, None => return INVALID };
                if let Some(i) = find(old, hash, ctx, key) { reply.value = count_at(old, i); reply.found = 1; }
            }
            CLEAR => {
                if old.len != 0 {
                    let mut i = 0;
                    while i < old.len - 1 { addr_of_mut!((*slot(old, i)).hash).write(0); i += 1; }
                    commit(state, State { filled: 0, ..old });
                }
            }
            DROP => {
                let (ctx, free) = match drop_hook { Some(h) => h, None => return INVALID };
                commit(state, ZERO);
                if old.cap != 0 { free(ctx, old.buffer, old.cap); }
            }
            SIZE => reply.value = old.filled,
            _ => return INVALID,
        }
        out.write(reply);
        OK
    })).unwrap_or(PANIC)
}

/// # Safety
/// Initialized/live/disjoint state, ops, slots and out; native callback and
/// allocator obligations are detailed in StarRustNetGroupCountCache.h. Mutation
/// needs writable state. Numeric checks do not prove liveness or permissions.
#[no_mangle]
pub unsafe extern "C" fn sb_net_group_count_cache_run(mode: u32, state: *const c_void,
    ops: *const SbNetGroupCountCacheOps, key: u32, out: *mut SbNetGroupCountCacheReply) -> u32 {
    checked(mode, state, ops, key, out, || {})
}
#[no_mangle]
pub extern "C" fn sb_net_group_count_cache_count(kind: u32, index: u32) -> u64 {
    catch_unwind(|| match (kind, index as usize) {
        (0, i) if i < COUNT => COUNTS.with(|c| c.get()[i]),
        (1, i) if i < COUNT => TOTALS[i].load(Ordering::Relaxed),
        _ => 0,
    }).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::alloc::{alloc, dealloc, Layout};
    use std::collections::BTreeMap;
    use std::ptr;

    #[derive(Debug, PartialEq, Eq)]
    enum Event { Plan(usize, usize), Hash(u32), Alloc(usize), Free(usize, usize) }
    struct Mock {
        state: *const c_void,
        fail: bool,
        plan_fail: bool,
        collide: bool,
        reenter: bool,
        hash_reentry: bool,
        request: u32,
        buffers: BTreeMap<usize, usize>,
        events: Vec<Event>,
        allocations_seen: Vec<State>,
        frees_seen: Vec<State>,
        free_counts: Vec<BTreeMap<u32, usize>>,
        lookup_seen: Vec<(u32, SbNetGroupCountCacheReply)>,
    }
    impl Mock {
        fn new(state: *const c_void) -> Self {
            Self { state, fail: false, plan_fail: false, collide: false, reenter: true, hash_reentry: false, request: u32::MAX,
                buffers: BTreeMap::new(), events: Vec::new(), allocations_seen: Vec::new(),
                frees_seen: Vec::new(), free_counts: Vec::new(), lookup_seen: Vec::new() }
        }
        fn ops(&mut self) -> SbNetGroupCountCacheOps {
            SbNetGroupCountCacheOps { context: (self as *mut Self).cast(), hash: Some(hash), plan: Some(plan),
                allocate: Some(allocate), deallocate: Some(free) }
        }
    }
    fn narrow(mut ops: SbNetGroupCountCacheOps, mode: u32) -> SbNetGroupCountCacheOps {
        if mode == LOOKUP { ops.plan = None; ops.allocate = None; ops.deallocate = None; }
        if mode == DROP { ops.hash = None; ops.plan = None; ops.allocate = None; }
        ops
    }
    fn counts() -> [u64; COUNT] { std::array::from_fn(|i| sb_net_group_count_cache_count(0, i as u32)) }
    fn p(s: &mut State) -> *const c_void { (s as *mut State).cast() }
    fn invoke(mode: u32, state: *const c_void, ops: &SbNetGroupCountCacheOps, key: u32) -> SbNetGroupCountCacheReply {
        let narrowed = narrow(*ops, mode);
        let h = if mode == CLEAR || mode == SIZE { ptr::null() } else { &narrowed };
        let mut out = SbNetGroupCountCacheReply { value: 77, found: 88, reserved: 99 };
        assert_eq!(unsafe { sb_net_group_count_cache_run(mode, state, h, key, &mut out) }, OK);
        out
    }
    unsafe fn contents(s: State) -> BTreeMap<u32, usize> {
        let mut map = BTreeMap::new();
        for i in 0..s.len {
            if hash_at(s, i) & FILLED != 0 { assert!(map.insert(key_at(s, i), count_at(s, i)).is_none()); }
        }
        map
    }
    // Raw context field access ONLY: no &mut Mock lives across recursive ABI
    // entry. Collection method borrows end before each read-only reentry.
    unsafe extern "C" fn hash(p: *mut c_void, key: u32) -> usize {
        let m = p.cast::<Mock>();
        (*m).events.push(Event::Hash(key));
        if (*m).hash_reentry {
            let mut out = EMPTY_REPLY;
            assert_eq!(sb_net_group_count_cache_run(SIZE, (*m).state, ptr::null(), 0, &mut out), OK);
        }
        if (*m).collide { 7 } else { (key as usize).wrapping_mul(0x9e3779b1) }
    }
    unsafe extern "C" fn plan(p: *mut c_void, filled: usize, len: usize, out: *mut usize) -> u32 {
        (*p.cast::<Mock>()).events.push(Event::Plan(filled, len));
        if (*p.cast::<Mock>()).plan_fail { return HOST; }
        // Bounded test-only integer oracle for the native whole-expression plan.
        // Powers <= test allocations make these thresholds exact; production
        // intentionally does NOT use this rational arithmetic in place of C++ FP.
        let mut n = if len == 0 { 8 } else { len - 1 };
        if len != 0 && (filled + 1) * 10 <= n * 7 { out.write(0); return OK; }
        while (filled + 1) * 10 > n * 7 { n *= 2; }
        out.write(if len != 0 && n == len - 1 { 0 } else { n + 1 });
        OK
    }
    unsafe extern "C" fn allocate(p: *mut c_void, n: usize, out: *mut usize) -> u32 {
        let m = p.cast::<Mock>();
        (*m).events.push(Event::Alloc(n));
        let seen = (*m).state.cast::<State>().read();
        (*m).allocations_seen.push(seen);
        assert_eq!((seen.buffer, seen.len, seen.cap), (0, 0, 0));
        if (*m).reenter {
            let ops = SbNetGroupCountCacheOps { context: p, hash: Some(hash), plan: None, allocate: None, deallocate: None };
            let mut reply = EMPTY_REPLY;
            assert_eq!(sb_net_group_count_cache_run(LOOKUP, (*m).state, &ops, (*m).request, &mut reply), OK);
            assert_eq!(reply, EMPTY_REPLY);
        }
        if (*m).fail { return HOST; }
        let layout = Layout::array::<Slot>(n).unwrap();
        let buffer = alloc(layout) as usize;
        assert_ne!(buffer, 0);
        // Test buffers deliberately start with initialized payload fields and
        // nonzero padding bytes, then production initializes ONLY hash fields.
        ptr::write_bytes(buffer as *mut u8, 0xa5, layout.size());
        for i in 0..n {
            let q = (buffer as *mut Slot).add(i);
            addr_of_mut!((*q).key).cast::<u32>().write(0xcccccccc);
            addr_of_mut!((*q).count).cast::<usize>().write(0x5555);
            addr_of_mut!((*q).hash).write(0);
        }
        assert!((*m).buffers.insert(buffer, n).is_none());
        out.write(buffer); OK
    }
    unsafe extern "C" fn free(p: *mut c_void, address: usize, n: usize) {
        let m = p.cast::<Mock>();
        let state = (*m).state;
        let seen = state.cast::<State>().read();
        assert_ne!(seen.buffer, address);
        (*m).frees_seen.push(seen);
        (*m).free_counts.push(contents(seen));
        if (*m).reenter {
            let ops = SbNetGroupCountCacheOps { context: p, hash: Some(hash), plan: None, allocate: None, deallocate: None };
            let key = (*m).request;
            let mut reply = EMPTY_REPLY;
            assert_eq!(sb_net_group_count_cache_run(LOOKUP, state, &ops, key, &mut reply), OK);
            (*m).lookup_seen.push((key, reply));
            let mut size = EMPTY_REPLY;
            assert_eq!(sb_net_group_count_cache_run(SIZE, state, ptr::null(), 0, &mut size), OK);
            assert_eq!(size.value, seen.filled);
        }
        assert_eq!((*m).buffers.remove(&address), Some(n));
        (*m).events.push(Event::Free(address, n));
        dealloc(address as *mut u8, Layout::array::<Slot>(n).unwrap());
    }

    #[test]
    fn zero_layout_and_all_u32_edges() {
        assert_eq!(size_of::<State>(), 4 * size_of::<usize>());
        assert_eq!(align_of::<State>(), align_of::<usize>());
        if usize::BITS == 64 {
            assert_eq!(size_of::<Slot>(), 24); assert_eq!(align_of::<Slot>(), 8);
            assert_eq!(size_of::<SbNetGroupCountCacheReply>(), 16);
            assert_eq!(align_of::<SbNetGroupCountCacheReply>(), 8);
        }
        let mut s = ZERO; let state = p(&mut s); let mut m = Mock::new(state); let ops = m.ops();
        assert_eq!(invoke(SIZE, state, &ops, 0), EMPTY_REPLY);
        for key in [0, 1, 21, 22, u32::MAX / 2, u32::MAX - 1, u32::MAX] {
            assert_eq!(invoke(LOOKUP, state, &ops, key), EMPTY_REPLY);
        }
        assert!(m.events.is_empty()); // empty find never even hashes
        for key in [0, 1, 21, 22, u32::MAX / 2, u32::MAX - 1, u32::MAX] {
            assert_eq!(invoke(INCREMENT, state, &ops, key), EMPTY_REPLY);
            let reply = invoke(LOOKUP, state, &ops, key);
            assert_eq!(reply, SbNetGroupCountCacheReply { value: 1, found: 1, reserved: 0 });
        }
        invoke(DROP, state, &ops, 0); assert_eq!(s, ZERO); assert!(m.buffers.is_empty());
        let frees = m.frees_seen.len(); invoke(DROP, state, &ops, 0); assert_eq!(m.frees_seen.len(), frees);
    }

    #[test]
    fn hundred_thousand_increment_lookup_clear_collisions_model() {
        for collide in [false, true] {
            let mut s = ZERO; let state = p(&mut s); let mut m = Mock::new(state); m.collide = collide; m.reenter = false;
            let ops = m.ops(); let mut model = BTreeMap::<u32, usize>::new(); let mut random = 0xabc123u32;
            for i in 0..100_000u32 {
                random = random.wrapping_mul(1664525).wrapping_add(1013904223);
                let key = match i % 29 { 0 => u32::MAX, 1 => 0, 2 => 1, _ => random % 83 };
                if i % 251 == 250 { invoke(CLEAR, state, &ops, 0); model.clear(); }
                else if i % 4 != 0 { invoke(INCREMENT, state, &ops, key); *model.entry(key).or_default() += 1; }
                let reply = invoke(LOOKUP, state, &ops, key);
                assert_eq!(reply.found, u32::from(model.contains_key(&key)));
                assert_eq!(reply.value, model.get(&key).copied().unwrap_or(0));
                assert_eq!(s.filled, model.len());
                assert_eq!(unsafe { contents(s) }, model);
                m.events.clear(); m.free_counts.clear();
            }
            invoke(DROP, state, &ops, 0); assert!(m.buffers.is_empty());
        }
    }

    #[test]
    fn existing_increment_skips_capacity_and_wraps_count() {
        let mut s = ZERO; let state = p(&mut s); let mut m = Mock::new(state); let ops = m.ops();
        for key in 0..5 { invoke(INCREMENT, state, &ops, key); }
        let old = s;
        let index = unsafe { find(s, hash, ops.context, 2).unwrap() };
        unsafe { addr_of_mut!((*slot(s, index)).count).cast::<usize>().write(usize::MAX); }
        m.events.clear(); invoke(INCREMENT, state, &ops, 2);
        assert_eq!(m.events, vec![Event::Hash(2)]); assert_eq!(s, old);
        assert_eq!(invoke(LOOKUP, state, &ops, 2).value, 0);
        assert_eq!(invoke(LOOKUP, state, &ops, 2).found, 1);
        invoke(DROP, state, &ops, 0);
    }

    #[test]
    fn growth_slot_order_commit_before_delete_and_readonly_reentry() {
        let mut s = ZERO; let state = p(&mut s); let mut m = Mock::new(state); m.hash_reentry = true; let ops = m.ops();
        for key in [9, 3, 11, 1, 14] { invoke(INCREMENT, state, &ops, key); }
        assert_eq!(s.len, 9); let old = s;
        let keys: Vec<u32> = (0..old.len).filter(|&i| unsafe { hash_at(old, i) & FILLED != 0 })
            .map(|i| unsafe { key_at(old, i) }).collect();
        let before = unsafe { contents(s) }; m.events.clear(); m.request = 99;
        invoke(INCREMENT, state, &ops, 99);
        assert_eq!(s.len, 17); assert_eq!(s.filled, 6);
        assert_eq!(m.allocations_seen.last(), Some(&State { filled: 5, ..ZERO }));
        let observed = *m.frees_seen.last().unwrap();
        assert_eq!((observed.buffer, observed.len, observed.cap, observed.filled), (s.buffer, 17, 17, 5));
        assert_eq!(m.free_counts.last(), Some(&before));
        assert_eq!(m.lookup_seen.last(), Some(&(99, EMPTY_REPLY)));
        // Ignore reentrant observer hashes, preserve native reinsert slot order.
        let alloc = m.events.iter().position(|e| *e == Event::Alloc(17)).unwrap();
        let free = m.events.iter().position(|e| *e == Event::Free(old.buffer, old.cap)).unwrap();
        let actual: Vec<u32> = m.events[alloc + 1..free].iter().filter_map(|e| match e { Event::Hash(k) if *k != 99 => Some(*k), _ => None }).collect();
        assert_eq!(actual, keys);
        assert_eq!(m.events.last(), Some(&Event::Hash(99)));
        assert_eq!(invoke(LOOKUP, state, &ops, 99).value, 1);
        invoke(DROP, state, &ops, 0);
    }

    #[test]
    fn clear_retains_allocation_payload_bytes_and_sentinel() {
        let mut s = ZERO; let state = p(&mut s); let mut m = Mock::new(state); let ops = m.ops();
        for key in 0..5 { invoke(INCREMENT, state, &ops, key); }
        let old = s;
        let payloads: Vec<_> = (0..s.len - 1).map(|i| unsafe {
            let q = slot(s, i);
            (addr_of!((*q).key).cast::<u32>().read(), addr_of!((*q).count).cast::<usize>().read())
        }).collect(); // test allocator initialized even empty payloads
        m.events.clear(); invoke(CLEAR, state, &ops, 0);
        assert_eq!(s, State { filled: 0, ..old }); assert!(m.events.is_empty());
        for (i, &(key, count)) in payloads.iter().enumerate() { unsafe {
            assert_eq!(hash_at(s, i), 0);
            assert_eq!(addr_of!((*slot(s, i)).key).cast::<u32>().read(), key);
            assert_eq!(addr_of!((*slot(s, i)).count).cast::<usize>().read(), count);
        } }
        assert_eq!(unsafe { hash_at(s, s.len - 1) }, 1);
        invoke(CLEAR, state, &ops, 0); invoke(INCREMENT, state, &ops, 42);
        assert_eq!(s.buffer, old.buffer); assert_eq!(s.len, old.len);
        invoke(DROP, state, &ops, 0);
    }

    #[test]
    fn failed_allocate_frees_old_zeroes_storage_but_keeps_stale_filled_and_output() {
        let mut s = ZERO; let state = p(&mut s); let mut m = Mock::new(state); let ops = m.ops();
        for key in 0..5 { invoke(INCREMENT, state, &ops, key); }
        let old = s; m.reenter = false; m.events.clear();
        let mut out = SbNetGroupCountCacheReply { value: 11, found: 22, reserved: 33 }; let saved = out;
        m.plan_fail = true;
        assert_eq!(unsafe { sb_net_group_count_cache_run(INCREMENT, state, &ops, 10, &mut out) }, HOST);
        assert_eq!(out, saved); assert_eq!(s, old); assert_eq!(m.buffers.len(), 1);
        assert!(m.frees_seen.is_empty());
        m.plan_fail = false; m.fail = true; m.events.clear();
        assert_eq!(unsafe { sb_net_group_count_cache_run(INCREMENT, state, &ops, 10, &mut out) }, HOST);
        assert_eq!(out, saved); assert_eq!(s, State { filled: 5, ..ZERO });
        assert_eq!(m.frees_seen.last(), Some(&s)); assert!(m.buffers.is_empty());
        assert!(m.events.contains(&Event::Free(old.buffer, old.cap)));
        assert_eq!(invoke(SIZE, state, &ops, 0).value, 5);
        // No failed-map lookup in this fixture; native empty clear is no-op.
        invoke(CLEAR, state, &ops, 0); assert_eq!(s.filled, 5);
        invoke(DROP, state, &ops, 0); assert_eq!(s, ZERO);
        let mut t = ZERO; let tp = p(&mut t); m.state = tp;
        assert_eq!(unsafe { sb_net_group_count_cache_run(INCREMENT, tp, &ops, 0, &mut out) }, HOST);
        assert_eq!(t, ZERO); assert_eq!(out, saved); invoke(DROP, tp, &ops, 0);
    }

    #[test]
    fn native_plan_threshold_mock_exact_small_boundaries() {
        let mut s = ZERO; let state = p(&mut s); let mut m = Mock::new(state); let ops = m.ops();
        for (len, last) in [(9usize, 5usize), (17, 11), (33, 22), (65, 44), (129, 89)] {
            for filled in 0..last { let mut n = 99;
                assert_eq!(unsafe { plan(ops.context, filled, len, &mut n) }, OK); assert_eq!(n, 0);
            }
            let mut n = 0; unsafe { plan(ops.context, last, len, &mut n); }
            assert_eq!(n, (len - 1) * 2 + 1);
        }
        let mut n = 0; unsafe { plan(ops.context, 0, 0, &mut n); } assert_eq!(n, 9);
        invoke(DROP, state, &ops, 0);
    }

    #[test]
    fn strict_schema_hooks_alias_ranges_and_no_error_output_or_counts() {
        let mut words = [0usize; 32]; let state = words.as_mut_ptr().cast::<c_void>();
        let mut m = Mock::new(state); let ops = m.ops();
        let mut out = SbNetGroupCountCacheReply { value: 17, found: 18, reserved: 19 }; let saved = out;
        let before = counts();
        for mode in 0..COUNT as u32 {
            let narrow = narrow(ops, mode);
            let h = if mode == CLEAR || mode == SIZE { ptr::null() } else { &narrow };
            for bad in [ptr::null(), unsafe { state.cast::<u8>().add(1).cast() }] {
                assert_eq!(unsafe { sb_net_group_count_cache_run(mode, bad, h, 0, &mut out) }, INVALID);
            }
            for bad in [ptr::null_mut(), unsafe { (&mut out as *mut SbNetGroupCountCacheReply).cast::<u8>().add(1).cast() }] {
                assert_eq!(unsafe { sb_net_group_count_cache_run(mode, state, h, 0, bad) }, INVALID);
            }
            for i in 0..4 {
                assert_eq!(unsafe { sb_net_group_count_cache_run(mode, state, h, 0, words.as_mut_ptr().add(i).cast()) }, INVALID);
            }
            if mode != INCREMENT && mode != LOOKUP { assert_eq!(unsafe { sb_net_group_count_cache_run(mode, state, h, 1, &mut out) }, INVALID); }
            if mode == CLEAR || mode == SIZE {
                assert_eq!(unsafe { sb_net_group_count_cache_run(mode, state, &ops, 0, &mut out) }, INVALID);
            } else {
                assert_eq!(unsafe { sb_net_group_count_cache_run(mode, state, ptr::null(), 0, &mut out) }, INVALID);
                assert_eq!(unsafe { sb_net_group_count_cache_run(mode, state, (&ops as *const SbNetGroupCountCacheOps).cast::<u8>().add(1).cast(), 0, &mut out) }, INVALID);
                let mut alias = narrow; let a = &mut alias as *mut SbNetGroupCountCacheOps;
                assert_eq!(unsafe { sb_net_group_count_cache_run(mode, a.cast(), a, 0, &mut out) }, INVALID);
                assert_eq!(unsafe { sb_net_group_count_cache_run(mode, state, a, 0, a.cast()) }, INVALID);
                for i in 0..4 {
                    let mut bad = narrow;
                    match i { 0 => bad.hash = if bad.hash.is_some() { None } else { Some(hash) },
                        1 => bad.plan = if bad.plan.is_some() { None } else { Some(plan) },
                        2 => bad.allocate = if bad.allocate.is_some() { None } else { Some(allocate) },
                        _ => bad.deallocate = if bad.deallocate.is_some() { None } else { Some(free) } }
                    assert_eq!(unsafe { sb_net_group_count_cache_run(mode, state, &bad, 0, &mut out) }, INVALID);
                }
            }
        }
        for mode in [COUNT as u32, u32::MAX] { assert_eq!(unsafe { sb_net_group_count_cache_run(mode, state, ptr::null(), 0, &mut out) }, INVALID); }
        for bad in [State { buffer: 0, len: 9, cap: 9, filled: 0 }, State { buffer: 8, ..ZERO },
            State { buffer: 8, len: 8, cap: 8, filled: 0 }, State { buffer: 8, len: 9, cap: 17, filled: 0 },
            State { buffer: 9, len: 9, cap: 9, filled: 0 }, State { buffer: 8, len: 9, cap: 9, filled: 9 },
            State { buffer: usize::MAX - 7, len: 9, cap: 9, filled: 0 },
            State { buffer: 8, len: (1usize << (usize::BITS - 1)) + 1, cap: (1usize << (usize::BITS - 1)) + 1, filled: 0 }] {
            assert_eq!(unsafe { sb_net_group_count_cache_run(SIZE, (&bad as *const State).cast(), ptr::null(), 0, &mut out) }, INVALID);
        }
        assert_eq!(out, saved); assert_eq!(counts(), before); assert_eq!(words, [0; 32]); assert!(m.events.is_empty());
        // A live allocated fixture exercises output/state/ops vs payload checks.
        let mut s = ZERO; let live = p(&mut s); m.state = live;
        invoke(INCREMENT, live, &ops, 1); let before = counts();
        let h = narrow(ops, LOOKUP);
        assert_eq!(unsafe { sb_net_group_count_cache_run(LOOKUP, live, &h, 1, s.buffer as *mut SbNetGroupCountCacheReply) }, INVALID);
        assert_eq!(unsafe { sb_net_group_count_cache_run(LOOKUP, live, s.buffer as *const SbNetGroupCountCacheOps, 1, &mut out) }, INVALID);
        let alias = State { buffer: live as usize, len: 9, cap: 9, filled: 0 };
        assert_eq!(unsafe { sb_net_group_count_cache_run(SIZE, (&alias as *const State).cast(), ptr::null(), 0, live.cast_mut().cast()) }, INVALID);
        assert_eq!(counts(), before); assert_eq!(out, saved);
        invoke(DROP, live, &ops, 0);
    }

    #[test]
    fn private_precommit_panic_preserves_all_bytes_and_counts_accepted_root() {
        let mut s = ZERO; let state = p(&mut s); let mut m = Mock::new(state); let ops = m.ops();
        for mode in 0..COUNT as u32 {
            let narrowed = narrow(ops, mode);
            let h = if mode == CLEAR || mode == SIZE { ptr::null() } else { &narrowed };
            let mut out = SbNetGroupCountCacheReply { value: 31, found: 32, reserved: 33 }; let saved = out;
            let before = counts();
            assert_eq!(unsafe { checked(mode, state, h, 0, &mut out, || panic!("private precommit")) }, PANIC);
            assert_eq!(s, ZERO); assert_eq!(out, saved); assert!(m.events.is_empty());
            let after = counts();
            for i in 0..COUNT { assert_eq!(after[i], before[i].wrapping_add(u64::from(i == mode as usize))); }
        }
    }

    #[test]
    fn tls_global_unknown_and_wrap_diagnostics() {
        let before = counts(); let globals: [u64; COUNT] = std::array::from_fn(|i| sb_net_group_count_cache_count(1, i as u32));
        std::thread::spawn(|| {
            assert_eq!(counts(), [0; COUNT]);
            let mut s = ZERO; let state = p(&mut s); let mut m = Mock::new(state); m.reenter = false; let ops = m.ops();
            for mode in 0..COUNT as u32 { invoke(mode, state, &ops, 0); }
            assert_eq!(counts(), [1; COUNT]);
        }).join().unwrap();
        assert_eq!(counts(), before);
        for i in 0..COUNT { assert!(sb_net_group_count_cache_count(1, i as u32).wrapping_sub(globals[i]) >= 1); }
        for kind in [0, 1, 2, u32::MAX] { assert_eq!(sb_net_group_count_cache_count(kind, COUNT as u32), 0); }
        for i in 0..COUNT as u32 { assert_eq!(sb_net_group_count_cache_count(2, i), 0); }
        COUNTS.with(|c| { let saved = c.get(); c.set([u64::MAX; COUNT]);
            for i in 0..COUNT { count_entry(i); assert_eq!(sb_net_group_count_cache_count(0, i as u32), 0); } c.set(saved);
        });
        let total = AtomicU64::new(u64::MAX); total.fetch_add(1, Ordering::Relaxed); assert_eq!(total.load(Ordering::Relaxed), 0);
    }
}
