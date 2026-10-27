# weighted pool: native calibration, not a rust port

this lab owns no production files. it uses the current all27OFF, 472-entry
reference recipe and directly links its 113 frozen core/extern objects. no
archive, cargo, cmake configuration, full build, game or capture is produced.

## contracts frozen before acquisition

`model.py` declares the independent rational/dyadic expectations before native
outputs. its 27 rows cover empty, one/two/four retained weights, rejected negative
and signed zeros, exact cumulative boundaries, targets below zero/above one,
and final-index fallback. nonfinite, overflow-scale and subnormal values are
**diagnostics only** under unchanged production `-O3 -ffast-math`; this is not an
IEEE/nonfinite equivalence claim. broad arithmetic/model fitting is forbidden.

`native.cpp` includes the actual original production header unchanged. a
reference view changes ONLY the type name `WeightedPool` to
`ReferenceWeightedPool`. the separately labelled dependency-proxy view changes
ONLY `WeightedPool`, `RandomSource`, `Random::`, and `staticRandomDouble` names.
no production body is edited and no private visibility macro is used. the proxy
random is a different dependency, NOT a subclass interception of the nonvirtual
production `RandomSource`. actual seeded `RandomSource`, `init`, global random,
and static-random tests are separate from proxy boundary/consumption tests.

`Set<size_t>` is the original ordered `std::set` wrapper; unique output order
is index order, not discovery order. desired count is clamped by pool size,
not distinct item values. seed increment wraps as unsigned 64-bit arithmetic.
actual unique retry remains unbounded. the diagnostic with weights 1e308 and
1e-308 deliberately asks for an unreachable second index; the supervising
process kills it after .25s and records that expected timeout, not a successful
native return or an algorithmic bound.

## definition map (original source/core/StarWeightedPool.hpp)

|definition|line|evidence route|
|---|---:|---|
|default constructor|54|empty/native/proxy/lazy|
|by-value container constructor|59|tracked container copies and trace|
|add|66|literal rejected/retained weights; tracked append/throw|
|clear|75|copy/reuse/lazy; observer-only destructor reentry|
|items|81|const reference/alias check|
|size|86|all corpus/structural tests|
|at|91|alias plus native range exception|
|weight|96|value plus native range exception|
|item|101|alias plus native range exception|
|empty|106|empty/default/clear checks|
|select(RandomSource&)|111|proxy no-call; real seeded consumption|
|select()|119|proxy no-call; real global consumption|
|select(uint64)|127|empty no-static-call; 128 real/reference seeds|
|selectUniques(count)|135|zero/empty still global seed consumption|
|selectUniques(count,seed)|140|duplicate values, clamp, wrap, ordered set, real/reference|
|selectIndex(RandomSource&)|153|proxy literal corpus; real empty consumption|
|selectIndex()|158|proxy empty consumption|
|selectIndex(seed)|163|128 real static seeds; empty consumption|
|selectIndex(double)|168|proxy literal <= boundary and fallback; strict-< mutant|

fields remain original `ItemsList m_items` and `double m_totalWeight`. no layout
or ownership change. tracked append observes public selection while appended
item temporary destructors run, before total-weight update. clear reentry only
observes size/empty; it does not mutate a vector during destruction. the lab
records native copies/moves/destructors, exceptions and named-list results;
it does NOT prove a future Rust ABI preserves NRVO, every prvalue/full-expression,
allocation failure, arbitrary reentry, or every lazy instantiation.

## provenance and replay

`run.py` is a one-shot producer, NOT a replay command. it admits actual flags,
113 object bytes, libraries, source/header trees, compiler resource headers,
SDK bytes/tbd interfaces, selected clang/ld/LTO/TAPI/ps/Python before compile/link.
the pinned old full-game plan selects immutable paths only; its old changed
global closure is NOT renewed. linker expansion precedes actual compilation;
actual depfiles and linker tbd map are reconciled afterward. no ar/ranlib runs.

`verify.py --report-sha <external sha>` is read-only and subprocess-free. a
completed report pins products and admission. its literal/model, missing-source,
missing-property and compiled strict-boundary semantic falsifiers must reject.
a negative compile requests `select` for a deleted-default item; the ordinary
fixture proves add/clear/inspection remain lazy for a nondefault move-only item.

## failure history and limits

first acquisition compiled/linked and both literal streams passed, but properties
terminated with SIGSEGV. fixture destructor-observer recursion was traced to
resetting the recursion guard BEFORE the selected local temporary's destructor.
attempt2 scopes that temporary before resetting the guard; it also unbuffers
stdio so partial structural output survives a failure. original binary/receipts
and exact source copies remain under `build/weighted-pool-native-r1/`.
this is one unexpected failure, not a production defect, and is not relabelled
as a passing producer. attempt2 is a separate subordinate directory under the
SAME original 64MiB/deadline budget. no cleanup/deletion is authorized here.

no game/adoption/full-module Rust completion/performance/OOM/concurrency/all39
or universal equivalence claim follows from this calibration.
