# accepted finite native bytearray host

status: **FINITE_NATIVE_BYTEARRAY_HOST_PASS** in
`build/byte-array-lab/host-run-r1/report.json`.

this supersedes the earlier compiled draft only for the finite native controller
boundary. no rust implementation, production/header/CMake/game change, application
qualification, or full-engine completion is claimed.

## observed acceptance

- 987 unchanged baseline cases, 14 unchanged callback/lifetime cases, and a
  repeated baseline stream match their pre-existing independent source models.
- all 56 actual compiled/header routes have positive attempts and balanced
  success/native-pending counters, collected after the unchanged corpus returns.
- the explicit native protocol program exits zero with its required receipt.
  allocation64, realloc128 and ownership-transfer scalar-output aliases reject
  without changing initialized backing. constructor readiness, pending identity,
  same-owner fresh-context reentry, proxy conversion/cleanup and legal larger rhs/
  receiver deletion remain covered.
- growth and signed-comparison controllers both exit normally, match their exact
  source-derived wrong expectations (22 and 16 changed rows), and fail the correct
  frozen oracle. assertions/crashes/compiler failures are not their evidence.
- every native process is checked against an independent seal before execution;
  output/image/source bindings and the seal are checked again afterward.

## structural change, not a producer retry

`host_stage.py acquire` is still CLOSED and unchanged after its two earlier
failures. it was not invoked. the earlier unqualified diagnostics, compiled
objects, source snapshots and reports remain intact.

1. `host_compile.py` emits only **COMPILED_UNSEALED** evidence. it has no execution
   or symbol-count acceptance path. fresh compilation uses one VFS header/body
   selection across 113 core/extern objects plus six harness/controller objects.
2. `host_seal.py` separately reconstructs all 247 command argv/recipes and checks
   source/dependency before/after hashes, fresh archive member bytes, maps, class
   declaration/56 source routes and exact original 33 compiled ABI names. extra
   helper/inline names cannot replace a missing original ABI definition.
3. `host_execute.py` consumes only that seal, executes six fixed routes, and
   independently replays the typed streams, protocol receipt, controls and 56x3
   counters. no compiler operation is part of execution.

artifacts:

- `host-compile-r1/build.json`: compiler-only inputs/outputs/commands.
- `host-seal-r2/seal.json`: current independent sealer/test bindings.
- `host-run-r1/report.json`: actual six-process acceptance and output bindings.

all paths above are under `build/byte-array-lab/`. source-model digests remain
`05258a405c475acc6d46ec78c74ac67270d70d730ab2cf757ab2ef45f9918d8c`
(987) and `c44665b0ef232eda3e689de2cc9d736bec83d330aeb079511652a9a11f3c7464`
(14). no model, golden, domain, flags, tolerance or timeout was fitted.

## scope limits are part of the contract

**SDK linker stubs are path-checked, not content-sealed.** review traced consumed
`.tbd` files in the actual link map that are absent from before/after hash bindings
(`host_seal.py` accepts them under the configured SDK root). compiler dependency
headers that are listed in `.d` files are content-bound; this is NOT complete SDK,
external-package or loaded-system-runtime verification. the inherited build
receipt already carries that limitation. do not advertise full SDK link-input
provenance or reproducible/signed build attestation from this seal.

this explicitly resolves the review finding by narrowing the provenance claim,
not by pretending a post-link hash was a pre-link measurement. future complete
SDK qualification must bind consumed link inputs before and after linking.

numeric exclusions track storage mutations made through the current context's
INIT/ALLOC/TAKE leaves, without refreshing potentially destroyed borrowed owners.
these are selected known-context/span guards, not arbitrary-pointer validation,
cross-context allocation tracking, or exhaustive protocol automata. no universal
OOM, allocator/free, sanitizer, other-platform or performance claim is made.
full-expression destination-store versus proxy-destructor ordering remains traced
to native source, not independently instrumented by the result fixture.

## repair and review history

pre-fix guard/protocol bytes are retained in
`guard-before-allocation-repair-r1/`. source review round two found no further
repair issue in its bounded scope. its separate SDK linker-stub finding is retained
with the explicit limitation above. review agreement is not runtime evidence.

the initial sealer's synthetic tests consulted local native compile metadata.
parent changed only those tests to mock recipe data for portable CI fixtures;
sealer logic and native compiled artifacts stayed identical. seal-r1 is historical
for the old test hash; seal-r2 binds current tests. the old failed producer's
budget is not reset. existing CI runs the source/sensitivity tests only, not this
macOS build or native runtime qualification.

## replay and next step

```sh
python3 -B source/lab/byte-array/host_execute.py verify --report build/byte-array-lab/host-run-r1/report.json
python3 -B -m unittest discover -s source/lab/byte-array -p 'test_*.py' -v
```

next: implement Rust's 56-mode controller in the existing sole aggregate, retaining
native object/allocation/typed generic-step ownership and default-OFF selection.
keep headers coherent across every participating translation unit. qualify the
actual native context, both fixed corpora, route/protocol/normal controls and panic
containment before actual linked-game frame/state/save/network/audio evidence.
no C++ exception may unwind through Rust. this native pass does not qualify that
future bridge or application behavior.
