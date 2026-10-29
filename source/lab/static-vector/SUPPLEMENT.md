# static vector: final generic source supplement

## status / boundary

17 independent source-first literal cases in `supplement_model.py`, frozen
before native output. source-only: python tests exercise the validator, source
membership and synthetic bad data, NOT c++ parsing, execution or compiled
mutants. all 39 modules remain OPEN. no rust, abi, production, layout, selector,
cmake, prior 151 values or prior 18 traces changed. parent alone owns subsequent
fresh tool/sdk/source/argv admission, compilation, native execution, archives
and commits. historical native proofs stay HISTORICAL / UNAVAILABLE_ARCHIVED;
never restore tools/sdk or rebind their old origins to this supplement.

stdout schema is exactly `{"schema":1,"cases":[{"name":...,"value":...}]}`.
17 unique names; value has exactly `events` (ordered strings), `state` and
`source` (integer arrays), `result` (boolean), `error` (string array). errors
are empty or typed `[type,message]`. case order is immaterial; event order,
field membership and json types are exact. `state=[]` in failed construction
means no completed target, not a snapshot of an object whose lifetime ended.
alignment uses `source=[alignof(element),address_mod_64]`, not source elements.

## recorder and lifetime contract

`supplement.cpp:32`: operation strings capture operands before assignment;
`size()` is sampled at log entry. a copied optional hook runs BEFORE event
append, so nested events precede the frozen outer event. copying the hook
keeps its closure alive while it disarms itself. qualifying hooks clear the
installed action BEFORE mutating either vector. size observers refer only to
initialized existing owners/sources, never a constructor's destination.

`ProbeElement` stores one meaningful int: default 0; normal moves transfer
then set source -1; self-move assignment sets -777. logs cover default/int/copy/
move construction, assignment, destruction and comparison kind. assignments
log pre-values; injected second copy assignment throws before mutation.
constructors never throw. logger allocations are assumed successful; allocation
failure inside instrumentation is not the tested domain.

reentry touches only distinct, live slots or unused capacity; never an outer
under-construction/destruction slot. appending preserves existing references.
the grow callback first sees size1 after outer slot0's value initialized, then
constructs NEW slot1. shrinking callbacks destroy live slot1 while slot2's
destructor is executing, not slot2 again. hooks stop before automatic teardown.

`supplement.cpp:76`: the sole throwing destructor is `noexcept(false)` and
armed only for an explicit `pop_back` caught by the caller. native pop has
already decremented size; slot2's lifetime ends on destructor entry. the flag
disarms before throwing, leaving exactly slots0/1 alive. no automatic vector
destructor throws; no constructor throws after pre-increment. failed delegating
copy construction throws only during assignment AFTER all target slots are
live, so the completed delegated constructor permits normal reverse cleanup.

## source-derived witnesses

confidence: VERIFIED as source derivation, NOT native execution. locations
below refer to `StarStaticVector.original.hpp`. falsification: independently
admitted native baseline disagrees with a frozen literal; investigate source/
producer rather than fitting values or flags. python controls test rejection
only and cannot falsify c++ lifetime reasoning by execution.

| cases | source / distinguishing observation |
| --- | --- |
| `reentry.copy.assign` | 150–159: resize temp at2; first assign hook appends target9/source8. loop rereads size3, final target/source `[1,2,8]`; assignment event retains entry size2 despite nested ctor events at3 |
| `reentry.resize.grow` | 189–197: default temporary before callee at0; local i snapshots0. first copyctor at1 appends9 at2; outer i still advances to1 and appends0 at3: `[0,9,0]` |
| `reentry.resize.shrink` | 189–197: local shrink counter still pops1 after nested pop2, then local grow loop fills0: `[0]`. nested dtor2 at1 precedes outer dtor3 at2 |
| `reentry.clear` | 339–342: dynamic while observes actual remaining1 after nested pop, destroys1 and ends empty; explicit clear catches ONLY OutOfRangeException for cached-count mutant |
| `ctor.copy.same`, `ctor.range` | 109–112, 131–134, 297–308: insert→resize default temporary, two default-slot copies, temporary destruction, two copy assignments; observer is existing source size2 |
| `ctor.copy.capacity` | 122–126: different capacity chooses converting overload, directly copies1 then2, no default temporary or assignments |
| `ctor.fill.explicit` | 137–140: named argument7 exists before recording; explicit value suppresses default argument; two copies, observer existing empty owner |
| `ctor.list.full.expression` | 143–147: C++17 prvalue array elements1/2 constructed directly, copied into target, backing array destroyed2/1 at semicolon; no optional nrvo assumption |
| `ctor.copy.unwind` | 109–112, 104–106, 297–308: second assignment throws, cleanup destroys remaining0 then copied1; observer source2, source unchanged |
| `erase.single.middle` | 345–351: move2←3; default temp, pop moved-from -1, temp destruction; iterator identity true, `[1,3]` |
| `erase.range.middle` | 354–362: move2←4; pop -1 then3; default temp dies last, `[1,4]` |
| `erase.range.empty` | 354–362: self-move2 then3, THEN default temporary despite no size change, `[1,-777,-777]` |
| `alias.emplace.reference` | 320–326: reference to original slot2 survives; resize/shifts change it to2 BEFORE assigned-element copy; `[1,2,2,3]` |
| `alias.insert.value` | 289–292: by-value copy3 before callee; same shifts; assigned-element move3 then two moved-from temp/parameter destructions; `[1,3,2,3]` |
| `alignment.runtime64` | 96, 330–335: alignas64 element, default-constructed capacity2 vector, emplace/clear; record actual address modulus0 and alignof64 on tested ABI only, no sizeof/layout oracle |
| `pop.destructor.throw.once` | 281–286: decrement before destructor; caught exact SupplementFailure leaves `[1,2]`; later automatic clear has no armed throw |

## three proposed native header mutants — NOT run

use separate generated header copies selected by `STATIC_VECTOR_TEST_HEADER`;
all baseline/mutants use the SAME `-DStaticVector=StaticVectorCharacterization`
identifier isolation. no production header/optimization changes. these are
precise replacements against the original, not broad loop rewrites:

1. **copy-cache-bound**: ONLY in copy assignment, after `resize(other.size());`
   insert `size_t initialSize = m_size;` and change that method's loop to
   `for (size_t i = 0; i < initialSize; ++i)`. leave move assignment and every
   other loop unchanged. witness `reentry.copy.assign`: target `[1,2,9]`,
   source `[1,2,8]`; final `copy.assign:9<-8:size=3` absent.
2. **resize-current-size**: ONLY resize's two local-counter loops become
   `while (m_size > size) pop_back();` and
   `while (m_size < size) emplace_back(e);`. keep overflow branch and error
   literal unchanged. witnesses: grow `[0,9]` (no final copyctor at3; temporary
   dies at2), shrink `[1]` (no outer pop1/refill0; temporary dies at1).
3. **clear-cache-count**: ONLY clear's loop becomes
   `for (size_t i = m_size; i != 0; --i) pop_back();`.
   witness `reentry.clear`: same destruction events, state empty, but explicit
   clear's extra empty pop throws exact typed error
   `["OutOfRangeException","(OutOfRangeException) StaticVector::pop_back called on empty StaticVector"]`.
   this is a VALID counterexample, not producer failure; catch never surrounds
   automatic vector teardown.

lifetime audit across ALL 17 cases: copy mutant changes only an assignment
bound, never slot construction/destruction. resize mutant stops earlier after
nested mutation but retains correct live-slot count, all loops remain within
capacity, and non-reentrant constructor/erase/alias paths retain live storage.
clear mutant is extra-pop only in explicit hooked clear, whose empty check
throws before touching storage and is caught. in resize-shrink, pop bypasses
clear; in constructor unwind and all automatic teardowns no hook is armed and
initial-count clear exactly matches live slots. one-shot destructor throw is
only explicit pop, untouched by all three mutants and disarmed before cleanup.
no proposed mutant changes publication ordering. NEVER reuse earlier
constructor-publication-after mutants here: grow reentry could then overlap
the outer object under construction and would leave the defined domain.

## source verification

`python3 -B -m unittest discover -s source/lab/static-vector -p test_supplement_model.py -v`
passes 25 tests. evidence is under `build/static-vector-supplement-source-r1/`;
`tests-r2.stderr` is the passing run. first run's `tests.stderr` is retained:
its order-control test swapped two identical fill-copy events and incorrectly
expected rejection. repaired the TEST to swap distinct events and explicitly
recognize the identical-event case; no literal/producer fitting. three synthetic
mutations reject; none is a compiled-native mutant. `completion.json` binds
four source hashes, expected literal hash and named state/error witnesses.

## actually deferred / excluded domains

no exhaustive generic parity claim. excluded as undefined/unsafe: failed
placement construction after pre-increment followed by poisoned cleanup,
invalid iterators/indices, reentry into the same slot under construction or
destruction, dangling/invalidated aliases, overflow via arbitrary reentry,
and throwing automatic vector destructors. capacity-zero pointer/lifetime
language diagnostics, allocation failure, optional nrvo, other element types,
throwing move/compare/copy-constructor paths, exception stack formatting,
unsupported ABI/platforms, performance and native-to-rust generic ownership
remain unqualified. explicit resize-value variants and comparison-prefix
branches are not added as redundant batches; implementation must preserve
native full expressions, typed references and lazy instantiation, and ABI
work must state any concrete unsupported boundary. this supplement supplies
no abi/rust/game qualification and does not close any of the 39 modules.
