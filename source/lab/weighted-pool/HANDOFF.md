# native handoff — partial, not ready for a rust abi

**stop state:** all native/compiler/linker children terminal and normally reaped
except the deliberately killed unreachable-unique diagnostic. no cargo/full
build/game/capture/deletion/commit occurred. parent owns integration. the original
22:32 utc deadline and 64MiB cap were not widened.

## verified finite evidence

report: `build/weighted-pool-native-r1/orthogonal/report.json`

sha256: `25f7cbae4e10559bca0464593d046299920aeb0fc6ae374211062484ab3213e3`

read-only replay (executed successfully):

```sh
python3 -B source/lab/weighted-pool/audit.py --report-sha 25f7cbae4e10559bca0464593d046299920aeb0fc6ae374211062484ab3213e3
```

- original header exact raw/current view; type-name-only reference view; explicit
  dependency-name-only proxy view. no body/private/layout edits.
- independent pre-observation rational/dyadic model: 27 rows, two retained exact
  streams. empty/one/two/many, negative/signed-zero filtering, <= boundaries,
  fallback, duplicate values, count clamp, seed wrap, ordered native Set.
- eight structural properties completed before failed lifecycle gate, not the
  original planned eighteen. fifteen callback-free real dependency properties.
- 128 actual static-random seeds against literal quarter thresholds and frozen
  original reference clone; 64 actual seeded RandomSource selection/index draws.
- actual global init/selection/index/zero-and-empty-unique consumption checks.
- three native OutOfRangeException leaves, exact dynamic type and literal what().
- nondefault move-only add/clear/inspect compile/run; selecting deleted-default
  Item is an actual expected compile failure. copy/move append/select throws
  retain the exact native sentinel pointer/what; callback-free destruction
  balances. this is not an arbitrary exception/alloc-failure proof.
- actual native unique retry on extreme weights did not progress for .25s and
  was intentionally SIGKILLed/reaped. no native retry bound was inserted.
- compiled strict-< mutant differs and is rejected; five further isolated
  controls reject wrong literal, missing real property, failed-producer retag,
  changed exception text and missing consumed header.
- 23 exact leaf receipts: 7 first monolith + 7 second + 9 orthogonal. two
  properties leaves FAILED (-11, +1). nonprogress expected -9/timeout; negative
  compile expected +1. all other leaves normal zero.

## failure truth / stop condition

first monolith properties SIGSEGV: source inspection traces recursive destructor
observation to resetting an `inside` guard before the observed selected local's
destructor. second monolith scopes that temporary but its assertion FAILS: the
`saw` flag is overwritten by later parameter destruction after total update.
these are fixture findings, not production bug claims. **two failures exhausted
this monolithic callback approach. no third lifecycle compile/retry occurred.**

material redesign: stopped the observer gate and acquired orthogonal real/random,
compile/lazy/exception properties without callbacks in `supplement.cpp`, plus
previously unexecuted modes of the unchanged attempt2 binary. all nine expected
leaves succeeded. its outer Python then FAILED decoding non-UTF8 linker-map
bytes as UTF-8. `finalize.py` independently composed the already acquired bytes
with the documented filesystem `surrogateescape` policy; no native rerun or
original status rewrite. both monoliths AND orthogonal outer remain FAILED.

`run.py`, `supplement.py` are failed one-shot procedures: **do not rerun**.
`verify.py` is the original unexecuted full-lifecycle verifier draft and is NOT
an acceptance command. use only `audit.py` for the explicitly partial evidence.

## precise source map / rationale

all 19 original definition bodies are inventoried; actual original class calls
are in the callback-free supplement and original fixture, boundary observations
use the explicit proxy. source/header methods were not instrumented for route
counters. README's first fifteen line citations are one line early; corrected
original definition locations:

```text
55 default constructor       60 by-value container constructor
67 add                      76 clear
82 items                    87 size
92 at                       97 weight
102 item                    107 empty
112 select(RandomSource&)   120 select()
128 select(seed)            136 selectUniques(count)
141 selectUniques(count,seed)
153 selectIndex(RandomSource&)
158 selectIndex()           163 selectIndex(seed)
168 selectIndex(double)
50 m_items                  51 m_totalWeight
```

`StarList.hpp:435` appends its by-value element by move;
`StarList.hpp:668` supplies the native bounds exception;
`StarException_unix.cpp:78–104` constructs the exact what() string;
`StarSet.hpp:70` uses ordered std::set; `StarRandom.hpp:13` is a NONvirtual class.

## admission limits / next decision

current all27OFF 472-entry recipe, original -O3/-ffast-math, exact frozen113
core/extern object paths/bytes, libraries, source/header/include/SDK trees,
compiler resource, actual clang/ld/LTO/TAPI/ps/Python executable bytes were
admitted before native compile/link. driver expansion reconciled actual ld
before compilation, depfiles checked afterward, original linker tbd map checked
against complete SDK interface witness. no archiver invoked/admitted. the old
55a6... full-build plan selects immutable paths ONLY; its old global/catalog
closure is not renewed. SDK interfaces do not prove the host dyld shared-cache
implementation; Python interpreter executable is witnessed, not every loaded
Python runtime byte. this is not a new universal full tool/runtime certificate.

**DO NOT START RUST ABI/KERNEL from this report alone.** the native baseline is
incomplete at full-expression callback/destructor order, reentry and named-result
NRVO/temporary traces. preserve the failed bytes and redesign that observation
contract independently before native acceptance; never change production flags,
model/domain/goldens or cap/deadline to pass. the original monolithic failure
budget is exhausted and cannot be reset by another agent. no performance/OOM,
concurrency/universal/all39/game/adoption/full Rust module claim.
