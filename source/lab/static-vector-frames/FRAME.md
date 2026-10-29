# static vector native lifetime frames

## scope and evidence

source-only candidate; not production adoption. `StaticVector.hpp` retains the
original declared surface, constructor initializer lists, two storage fields and
ten branchless typed views. no production header fallback or saved policy body.
`frame.hpp` calls the existing `sb_static_vector_run` export; no second crate,
runtime, selector or c++ policy interpreter.

VERIFIED by text comparison: 41 definition signatures and the class declaration
match the frozen raw header; ten views and the destructor body match verbatim.
31 other definitions route to the 26 rust root modes (the destructor routes
indirectly through `clear`). the less callback also enters the less continuation.
source checks and hashes live in `build/static-vector-frames-source-r1/`.
text checks are NOT c++ parsing, layout evaluation, rust linking, native execution
or generic constraint qualification. all module/application gates remain open.

## owned-definition mapping

| definitions | root / effects |
| --- | --- |
| default constructor | DEFAULT_CTOR; no callbacks, native `m_size(0)` |
| destructor | original `clear()`; enters CLEAR |
| same-type copy, iterator constructors | CTOR_INSERT; CALL_FORWARD |
| fill constructor | CTOR_RESIZE; CALL_FORWARD |
| move constructor | RANGE_MOVE; ITERATOR_PRESENT, CALL_EMPLACE_CURRENT, ADVANCE_ITERATOR |
| converting, list constructors | RANGE_COPY; same three cursor effects |
| copy assignment | COPY_ASSIGN; SELF, CALL_RESIZE_OTHER, CALL_ASSIGN, READ_SIZE |
| move/list assignment | MOVE_ASSIGN/LIST_ASSIGN; same except SELF |
| size, empty | SIZE/EMPTY; READ_SIZE |
| resize | RESIZE; READ_TARGET/CAPACITY/SIZE, THROW_RESIZE, CALL_POP/EMPLACE_VALUE |
| mutable/const at | AT; READ_INDEX/SIZE, THROW_AT |
| mutable/const index | INDEX; ASSERT_INDEX |
| ten begin/end/reverse/ptr views | unchanged native expressions |
| push, single insert, list insert | PUSH_BACK/INSERT_ONE/INSERT_LIST; CALL_FORWARD |
| pop | POP_BACK; READ_SIZE, THROW_POP, DECREMENT_SIZE, DESTROY_LAST |
| range insert | INSERT_RANGE; READ_TO_ADD/START/END/SHIFT, CALL_RESIZE_ADD, MOVE_ASSIGN_SLOTS, ASSIGN_FROM_ITERATOR |
| emplace | EMPLACE; READ_INDEX/SIZE, CALL_RESIZE_PLUS_ONE, MOVE_ASSIGN_SLOTS, ASSIGN_FROM_ARGS |
| emplace back | EMPLACE_BACK; READ_SIZE/CAPACITY, THROW_EMPLACE_BACK, INCREMENT_SIZE, CONSTRUCT_LAST |
| clear | CLEAR; READ_SIZE, CALL_POP |
| single erase | ERASE_ONE; READ_INDEX/SIZE, MOVE_ASSIGN_SLOTS, CALL_RESIZE_MINUS_ONE |
| range erase | ERASE_RANGE; READ_START/END/REMOVE/SIZE, MOVE_ASSIGN_SLOTS, CALL_RESIZE_MINUS_REMOVE |
| equality | EQUAL; SELF, READ_SIZE, OTHER_SIZE, ELEMENT_NOT_EQUAL |
| inequality | NOT_EQUAL; CALL_EQUAL |
| less | LESS; READ_SIZE, OTHER_SIZE, COMPARE_PAIR; nested CONTINUE exposes PAIR_LESS/GREATER |

## lifetime constraints

per-method reference-capturing closures prevent unrelated element operations from
being instantiated. the frame stores a closure and an exception pointer, never an
element or vector value. public by-value arguments and default `Element()`
arguments remain native. nested resize/insert/emplace/pop calls retain complete
call expressions, including default-temporary destruction before the next effect.
range insertion binds distance/start/end/shift in original declaration order.
range constructors capture native cursor/end once. forwarded aliased arguments
are not read or materialized until their original assignment/construction effect.
initializer-list assignment deliberately retains dependent `list[i]`; no api fix.

less binds the original named `Element const& a` then `b` in COMPARE_PAIR. a
separate reference-capturing frame enters the rust continuation while those same
references live; it does not reindex between comparisons. element equality still
uses `!=`, not `==`. comparison results use explicit bool conversion because the
original conditions permit a comparison proxy with an explicit bool conversion.

## protocol and exception boundary

`Frame<F>::host` is the synchronous opaque-context trampoline; context must point
to that live frame specialization. pointer provenance/liveness cannot be proved
by envelope checks. its public internal `dispatch` naturally permits independent
parent guard fixtures without modifying production APIs.

before an effect, dispatch checks pointer nonnull/alignment, request size32,
version1, reserved0, op1..40, exact argument slots and native-size fit. each method
rejects unsupported leaves with an invalid sentinel without owner mutation.
reply shape/tag/range checks occur before publishing a successful effect result.
throw effects must throw, never acknowledge success. host output is WRITE-ONLY:
rust initializes it with poison, so dispatch never reads its initial contents.
the rust-entry output instead begins as valid24/version1/VOID0. run validates the
root result tag, or SIZE0/1/2 for the less continuation.

all typed throws, including non-standard exceptions and nested frame failures,
are caught by the active trampoline into `exception_ptr`. subsequent effects are
blocked after a pending throw. run rethrows that same exception only after its
rust call returns; a nested rethrow is caught by its outer trampoline before the
outer rust call can see it. there is no translation, rollback or native loop.

## parent qualification still required

fresh admitted same-aggregate release archive and actual c++ compile/link/run;
malformed-request/write-only-poison/throw-identity guards; all frozen value,
trace and supplement comparisons; lazy move-only/no-default positive probes,
no-default-copy and initializer-list-assignment negatives; actual layout and
runtime overalignment; rust counter/provider/continuation evidence. no such
result is inferred from this source review. undefined iterator/poisoned-storage
and automatic throwing-vector-destructor domains remain excluded, not repaired.
