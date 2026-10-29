# static vector: generic trace boundary, source revision 1

## status and authority

source-only. `trace_model.py` fixes 18 literal cases before native output exists;
`test_trace_model.py` checks that oracle and isolated bad-data rejection, NOT c++
execution. compiler, linker, native baseline/repeat/mutants and constraint probes
remain UNEXECUTED here. all 39 migration modules remain OPEN; no abi promotion,
rust policy, production/layout/selector/cmake change follows from python tests.

these new source paths intentionally end the old value admission's current
closed-root membership epoch. its 151-case native evidence remains a finite
historical fact; do not waive its reader, rewrite its input hashes, or rebind its
sdk/source/native clock to these files. the parent must admit current tools,
sdk, source, argv and baseline/mutants separately before native execution.

## trace contract

stdout is one standard-library-serialized json object:
`{"schema":1,"cases":[{"name":"unique", "value":{...}}]}`.
each value has exactly `events` (ordered strings), `state` and `source` (int
snapshots), `result` (boolean; false when unused), `error` (empty or exact
`["TraceFailure", message]`). no abi observations or project json/list dependency.
case order is immaterial; event order and json types are not.

`trace.cpp:47` defines one-int elements: default=0, ordinary moves transfer then
set source=-1, self-move assignment sets -777. assignments log pre-mutation
operands. injected second copy assignment throws BEFORE mutation; comparisons
log then throw on their second call. `operator==` is deleted to make an accidental
element-equality requirement a compile failure. marker errors are our exact
`TraceFailure` type/message, not platform exception-name/rtti parity claims.

`trace.cpp:92` publishes the observer only after its owner is initialized. every
callback reads only `size()`, never a slot under construction/destruction. move
construction observes the EXISTING source, not its uninitialized target. no
vector is returned by value and the push argument is a named lvalue, avoiding
optional nrvo/copy-elision dependence. `emit` disables recording and clears throw
flags before automatic fixture teardown. all vector slots remain live after the
injected recoverable throws. no constructor/destructor throws are injected;
ordinary bounded allocations must succeed as with any allocating test logger.

## source-traced expectations, not executed findings

confidence: VERIFIED as source derivation, not native behavior. locations below
are in `StarStaticVector.original.hpp`. falsification is the parent's future
independently admitted native run against the fixed literals; never calibrate
these literals from that output.

| cases | source evidence and constrained boundary |
| --- | --- |
| `emplace.back.publish` | 330–335 increments before placement; `ctor:7:size=1` witnesses constructor reentry publication |
| `pop.publish`, `clear.reverse` | 281–286 decrements before destruction; `dtor:2:size=1` and reverse 3/2/1 destruction at sizes 2/1/0 distinguish delayed publication |
| `push.named` | 276–278 by-value parameter then move; outer copy at size 0, move at 1, moved-from parameter destruction at 1 |
| `resize.same`, `resize.grow` | 47 and 189–197 default argument exists even on no-op; default temporary precedes copy appends and dies after them |
| `emplace.middle` | 320–326 resize's temporary dies before shift; move assignment 0<-2, then int temporary 9, assignment -1<-9, moved-from temporary destruction |
| `insert.empty` | 297–307 resize still runs, descending tail loop self-moves 3 then 2 even with zero input; result is `[1,-777,-777]`, not a no-op |
| `move.construct`, `move.assign`, `move.self` | 115–119 and 162–168 do not clear source size; moved-from snapshots `[-1,-1]` retain two slots, self assignment is observable |
| `copy.assign.throw` | 150–159 resize then left-to-right assignment; first slot updated, second throws, remaining slots original; `[1,8,7]`, source unchanged |
| `compare.equal`, `compare.self`, `compare.throw` | 365–375 identity bypass, then element `!=`; second comparison failure leaves both vectors unchanged |
| `order.less`, `order.greater`, `order.throw` | 384–400 `a<b` then `b<a`, short circuit; no later element calls after deciding or throwing |

## proposed native semantic mutants — NOT run

apply each to a separate frozen-header copy; compile ALL baseline/mutants with
`-DStaticVector=StaticVectorCharacterization` and the same ordinary flags. use
`STATIC_VECTOR_TEST_HEADER` for the selected copy (default is the raw header).
no production header or optimization changes and no reused core instantiation.

1. emplace publication after placement: replace BOTH placement address and size
   sequencing with `new (ptr() + m_size) Element(...); m_size += 1;`.
   merely swapping the original lines would address before slot zero and be UB.
   `emplace.back.publish` must differ only in its observed ctor size, 0 vs 1.
2. pop publication after nonthrowing destruction: use
   `(ptr() + m_size - 1)->~Element(); --m_size;` after the existing empty check.
   preserve the correct slot address; `pop.publish` must report 2 instead of 1.
3. empty range insertion returns immediately AFTER `resize(m_size + toAdd)` if
   `toAdd == 0`. `insert.empty` retains default temporary events but loses both
   self-move events and changes state to `[1,2,3]`.

all three are defined-domain changes across this entire fixture: no poisoned
construction counts, throwing destructors or invalid iterators. python synthetic
controls only demonstrate rejection paths, never compiled-mutant acceptance.

## compile-only constraints — UNEXECUTED

new independent translation units under `constraints/`, same header switch and
identifier isolation, with no main/runtime required:

- `move_only_no_default.cpp`: positive. default vector construction, direct
  emplace_back and clear must not instantiate unused resize/copy requirements.
- `no_default_copy_negative.cpp`: negative. otherwise copyable element deletes
  its default constructor; same-type vector copy invokes insert -> resize with
  `Element()` default argument. require that specific diagnostic chain, not just
  any compilation failure. an unrelated setup failure is not evidence for this constraint.
- `overaligned.cpp`: positive alignas(64) element, vector alignment assertion,
  direct emplacement/clear. not a measured object-size, actual address, abi or
  cross-platform layout certificate. aligned storage rationale: raw header:96.

initializer-list assignment's lazy compile failure already has native evidence
in the prior value unit; no redundant probe is added.

## deliberately deferred

constructor failure after pre-increment can poison live-slot accounting; throwing
destructors can terminate or invalidate cleanup. neither is a parity trace here.
invalid iterators/indices, capacity-zero address arithmetic diagnostics, arbitrary
mutation reentry, aliased insertion arguments, allocator failure, exception
identity/stack formatting, broader throwing move/assignment paths and failed
constructor unwinding remain separate work. copy/range/fill/converting/list
constructor lifetimes, erase lifetime events, explicit-value resize temporary
variants, comparison size/prefix event branches and runtime overaligned address
checks are not covered by these 18 traces. no exhaustive generic-element, abi,
performance, game or rust-equivalence claim.
