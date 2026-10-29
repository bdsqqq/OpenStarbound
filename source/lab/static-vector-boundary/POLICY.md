# static vector: scalar policy / native lifetime boundary

## status

source contract, not an executed ABI or Rust qualification. the production
`StarStaticVector.hpp`, class layout, CMake and selectors are unchanged. the new
`StarRustStaticVector.h` is not included by production. native observations are
151 value cases +18 element traces +17 supplement traces, twice each, with nine
compiled semantic controls. their redundant generated products were conserved;
original native path/inode/provider replay is UNAVAILABLE_ARCHIVED. those facts
do not renew an SDK/source epoch or prove universal generic/platform equivalence.

## ownership

Rust owns conditional decisions, loop bounds, ordering and early exits. C++ owns
`size_t m_size` and the original aligned storage, typed pointer/iterator views,
argument and element lifetimes, native arithmetic expressions with user-facing
formatting, `starAssert`, typed local references and exception objects. no element
bits, pointer arithmetic over elements, iterators or generic references enter Rust.
size replies fit the target's `size_t`/Rust `usize`; control arithmetic wraps at
that native width. the tested architecture is arm64 Darwin, not every platform.

all 41 owned definitions have a route:

| C++ definitions | Rust mode / retained native boundary |
| --- | --- |
| default constructor | DEFAULT_CTOR after native `m_size(0)`; no callback |
| same-type copy / iterator-range constructors | CTOR_INSERT invokes the complete ported `insert(begin(), ...)` call, preserving iterator parameter copies |
| fill constructor | CTOR_RESIZE invokes complete `resize(size,value)` |
| converting-capacity / initializer-list constructors | RANGE_COPY over native captured cursor/end; typed `const& e` and complete `emplace_back(e)` |
| move constructor | RANGE_MOVE, same snapshot cursor/end; `auto& e` and complete `emplace_back(std::move(e))` |
| destructor / clear | CLEAR; destructor calls the ported clear wrapper normally, C++ retains its exception specification |
| three assignment operators | COPY_ASSIGN/MOVE_ASSIGN/LIST_ASSIGN; native resize call then per-index native assignment full expression; only copy has self bypass |
| size / empty | SIZE / EMPTY read native size; Rust computes empty |
| resize | RESIZE, two native-width LOCAL-counter loops with fresh size between them, never current-size replacement loops |
| mutable/const at | AT branches on native index/size; native throw formatting and typed result reference |
| mutable/const operator[] | INDEX invokes original native assert; typed result reference remains C++ |
| begin/end/rbegin/rend and ptr, ten definitions | branchless native typed views over unchanged storage; no duplicated container policy |
| push_back | PUSH_BACK calls complete ported `emplace_back(std::move(e))`; by-value parameter remains native |
| pop_back / emplace_back | POP_BACK / EMPLACE_BACK, Rust sequences size check, publication and native destroy/placement expression |
| single/list insert | INSERT_ONE / INSERT_LIST call complete ported emplace/range-insert expression; return SAME native `pos` |
| range insert | INSERT_RANGE reads native bound locals then owns descending shift and fixed input-count loops |
| emplace | EMPLACE shifts then constructs/assigns from forwarded arguments; NEVER snapshots aliased arguments early |
| single/range erase | ERASE_ONE / ERASE_RANGE, dynamic native size conditions and complete final resize calls; return original native iterator |
| == / != / < | EQUAL / NOT_EQUAL / LESS, preserve element `!=`, nested equality, named comparison references and short-circuiting |

## roots and leaves

26 modes, ROOT plus LESS-only CONTINUE, 40 leaves. requests/replies are C-layout
32/24-byte envelopes on the current ABI. scalar request args are indices only;
the header specifies their exact permitted slots, reply tags and throw protocol.
ROOT results: SIZE returns SIZE_VALUE; EMPTY/EQUAL/NOT_EQUAL/LESS return BOOL;
all others VOID0. LESS CONTINUE returns SIZE_VALUE 0(equal)/1(less)/2(greater).
the caller initializes the output to a valid versioned reply, normally VOID0,
as in the existing IdMap boundary. success replaces it; errors leave it unchanged.
invalid mode/stage, null context/host or null/misaligned result, unknown status,
wrong initial/host reply shape, reserved bytes, tags, bool/range or native-size
overflow fail closed. a throw
leaf returning OK is invalid. no callback on an invalid entry envelope.

DEFAULT_CTOR performs no host work. CTOR_INSERT/CTOR_RESIZE/PUSH_BACK/INSERT_ONE/
INSERT_LIST use CALL_FORWARD to invoke a PORTED wrapper, not a saved C++ loop.
RANGE_COPY/MOVE repeatedly query ITERATOR_PRESENT, call EMPLACE_CURRENT, advance.
cursor/end are captured before entry, not recomputed from a reentrant source.

COPY_ASSIGN self-checks before constructing the native resize default argument;
move/list do not. CALL_RESIZE_OTHER retains the whole call (`other.size()` or
`list.size()` plus default temporary), then CALL_ASSIGN(index) preserves each
native expression. its loop rereads size on EVERY original condition.

RESIZE reads requested target, checks capacity before either loop, snapshots size
for shrink, calls ported pop per iteration, then snapshots size again for grow
and calls ported emplace_back(e). native error formatting keeps the original
`m_size + size` quirk. EMPLACE_BACK checks wrapping size+1 against capacity, then
increments BEFORE placement. POP_BACK checks empty, decrements BEFORE destructor.
CLEAR instead rereads size after every pop. no rollback, retry or progress cap.

range-insert native locals retain original order: distance(begin,end), start,
end, toShift. Rust reads those snapshots, invokes CALL_RESIZE_ADD preserving the
original full call/default temporary, shifts backward using destination/source
indices, then assigns `*begin++` in native full expressions. empty insertion is
NOT skipped. emplace's index is native; resize-plus-one and subsequent shift
snapshot remain ordered before forwarded argument construction. erase snapshots
its original indices/removal count, but rereads current size at each loop test;
its final size expression/default temporary are native, never eagerly moved.

LESS ROOT loops with dynamic own size, checks other size before dereference, and
requests COMPARE_PAIR(index). that native callback binds original named
`Element const& a` and `b`, enters LESS CONTINUE while those SAME references live,
and returns its order code. CONTINUE asks PAIR_LESS then only if false asks
PAIR_GREATER. do not re-index, copy elements or lose alias/reentry effects between
comparisons. EQUAL uses element !=; NOT_EQUAL invokes the native equality wrapper.

## host safety / lazy constraints

per-method lambda frames expose ONLY leaves used by that instantiated method.
a class-wide generic switch would eagerly require default/copy/equality/move
operations, breaking already observed move-only/no-default lazy constraints.
initializer-list assignment's native dependent `list[i]` compile failure remains;
same-type copy still materializes resize's native `Element()` default argument.

copy the scalar request envelope into Rust-owned values before any callback;
keep no Rust reference/borrow over C++ storage or callback-modifiable envelopes.
callbacks catch all C++ throws in `exception_ptr`, return EXCEPTION immediately,
and rethrow only after the Rust entry returned. native local temporaries unwind
on C++ stacks. nested ported calls may enter Rust again but must each finish
before C++ propagates an exception to their parent callback. delegating constructor
unwind/explicit throwing pop must retain their already observed live-slot state.
Rust panics are caught at the export; never unwind them into native callers.

## acceptance still pending

fresh C11/C++ ABI probes; actual aggregate debug/release mock tests and malformed
reply controls; native per-method frames/lifetime/constraint comparisons; actual
same-aggregate symbol/provider/native-to-Rust edges; default-OFF production;
normal TileSectorArray/StaticList/WorldClient consumer and running-game capture,
old scene/auxiliary regressions; reconstruction-before-prune final module gate.
no additional generic characterization batches without a concrete failure.
