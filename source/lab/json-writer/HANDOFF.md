# json writer native calibration — blocked, budget closed

**no accepted calibration and no port.** two failed acquisitions are retained;
no third acquisition/rebuild/native execution was attempted. no `report.json`
was published. do not treat the readme's intended pipeline as a completed gate.

host/worktree: apple silicon macOS, `/Users/bdsqqq/www/OpenStarbound`, main.
base/current head: `2ca1cedbe979727e01eeb72cff8f1e0d371c86ee`.
started 2026-10-27 04:06:58 UTC; implementation/runs ended before 04:18 UTC;
remaining work was post-observation read-only provenance audit and this handoff.
no commits/delegates/cargo/full-game builds/runs/captures/remote actions. no owned
process remains active. first background controller pid 41437 terminated normally
with acquisition failure; second controller and audit commands were foreground
and terminated. parent-owned `doc/rust-migration-plan.md` was already modified
on entry and was not edited. pre-existing `storage/` was untouched.

## precise blocker

**VERIFIED:** frozen model vs original has 332 mismatching event snapshots, all
in instrumented utf-8 (`p8`). source locations:
`source/core/StarUnicode.hpp:10,250–262` casts emitted bytes to `Utf8Type`, an
alias for native `char`; `source/lab/json-writer/lab.cpp:37` accepts `char32_t`
in the shared probe proxy. high-bit native chars therefore reach this probe as
promoted/sign-extended 32-bit values. `model.py:46,77` modeled unsigned bytes in
that mode. this is a lab/probe-model disagreement, NOT a production defect.

first disagreement: expected row 177, `quirks-0 / p8 / event 7`.
expected output suffix `efbbbf`; actual suffix
`ffffffefffffffbbffffffbf`. corresponding assignment trace values differ in the
same way. ordinary byte-vector utf-8 output is exact against the independent
model. no expected byte or fixture was repaired after observing this failure.

falsification checked: the failure is not original/current drift (their complete
outputs are identical), not ordinary utf-8 encoding failure (all ordinary utf-8
rows match), and not nonzero/aborted native runs (all 14 native executions have
typed normal zero exits). the retained compiler AST and source make the probe's
conversion boundary inspectable. attribution beyond these source/trace facts is
not used to accept the failed gate.

## attempts, retained without retagging

1. `build/json-writer-native-r1/attempt-1/`: 4699 bindings frozen, dependency scans
   and both compiler ASTs completed. manual/compiler reconciliation rejected the
   template constructor name `JsonWriter<OutputIterator>` rather than the manual
   logical name `JsonWriter`. specialization records also needed explicit
   traversal for implicit native members. no objects/links/native runs happened.
   the parser was corrected before a wholly new second acquisition; the original
   frozen source copy, ASTs and failure log remain. read `producer.log`.
2. `build/json-writer-native-r1/attempt-2/`: 4699 bindings and expected corpus
   frozen before AST/object compilation/native runs. all 45 recorded child tool
   commands exited normally with integer zero; the acquisition controller exited
   1 at full-model comparison. seven fresh fixture TUs, seven links and fourteen
   native runs completed. no pass report was exposed. **budget CLOSED**.

one scope deviation: the first shell redirect briefly created the owned log
`build/json-writer-native-r1-attempt-1.log` outside the requested subtree. it was
moved without overwriting to `attempt-1/producer.log`, preserving its bytes.
no unrelated data was altered or removed.

## what the retained evidence establishes, finitely

post-observation audit:
`build/json-writer-native-r1/attempt-2/partial-audit.json`
sha256 `b805b173a789e7d81170cc292f5966dc1c13ef475a54bc3872672918d7b8cdb5`.
status `PARTIAL_NATIVE_JSON_WRITER_MODEL_MISMATCH_CLOSED_BUDGET`;
`calibration_accepted: false`. the auditor was written AFTER the failed run and
is explicitly not an acquisition-time oracle or a new native run.

- original/current compiler AST reconciles all 21 manual explicit declaration
  ranges and exact bytes. 20 implicit native special-member records are separate:
  copy/move ctor, copy/move assignment, virtual dtor across four instantiations.
  all required explicit class bodies are inventoried, not the parser/header or
  foundation serialization module. original/current full header sha256 is
  `ab19bf44ac9d72041b7c3563fca57d846bc15c5cf459a4cd868d4163af33bec4`.
- 409 finite event scenarios; 10688 observations per binary, 2672 per iterator
  mode. raw ordinary utf-32, ordinary utf-8 and raw probe each match all 2672;
  utf-8 probe matches 2340 and fails 332. original/current and every mutant repeat
  are byte-identical to their own first run.
- five normally exiting compiled semantic mutants differ from native original
  AND have frozen-model discriminating rows where original DOES match expected:
  key-nul 228; escape 16; array pretty 3288; indent 4596; container pop 924.
  `attempt-2/mutant-discrimination.json` records first identities/hashes. this
  diagnostic does not rescue the failed aggregate model gate.
- valid sentinel-backed input, controls/nul/surrogates/out-of-range raw32,
  raw numeric tokens, compact/pretty 0/1/2/7 and finite no-huge-indent UINT_MAX,
  explicit commas/whitespace, mismatched/repeated ends, assignment vs increment
  vs proxy-destructor throws and continuation, native copy/move/assign, nested
  writer, same-writer reentry and native active-writer replacement, live input
  mutation and live indentation bounds are included. no universal claim follows.
- original/current stdout sha256, including all errors/partial effects:
  `f81c077a57a9a6088f61185b648e56360c2314c0e87caa2f7ccd1fe44dfd7965`.
  expected sha256 stays
  `4043729be59e7f751d6aba6e8c9b23595ad3539823c2b0921db8cc58631bfed6`.
- 113 native core/extern objects reused READ-ONLY as prebound inputs, NOT rebuilt;
  actual Ninja ordering/recipes/dependencies, current 1495 sources and 472
  configured sources, all 25 selectors OFF, unchanged generated version inputs,
  source/dependency snapshots and all 4699 before/after bindings reconciled.
  before/after manifests both sha256
  `b962b8a91c654afb0abd947af69b25790b136d2dcd08a0023a050909c96a7ca2`.
- each link: 114 standalone objects (one fresh fixture + 113 retained), 2489
  loaded native archive members, 1433 surviving map archive members, 452 resolved
  SDK records. actual implicit driver runtime, libLTO, physical duplicate-name
  member witnesses and SDK interface/link/settings closure checked using the
  unchanged mature helpers. no unknown origins were waived. no project Rust
  aggregate is linked (abseil's native C++ rust-name demanglers are ordinary
  retained archives, not the project Rust runtime).
- 199 independently enumerated acquisition artifacts are rehashed by the partial
  auditor. seven isolated malformed/missing/false-bool/source/object audit controls
  rejected, `attempt-2/audit-controls/results.json` sha256
  `c64b4d7a2ec7162b83594bccb05cb8022cf83db8baab4840656423caf330a778`.
  full-calibration `run.py controls` was NOT run because there is no accepted
  report. audit controls must not be relabeled as full-calibration controls.
- model literal checks and an in-memory extra compiler-body negative control ran.
  tracked diff whitespace check passed; new authored files passed whitespace
  checking. the exact frozen original retains pre-existing whitespace at copied
  header line 308 and was deliberately not edited.

## independent read-only replay

```sh
python3 -B source/lab/json-writer/audit.py verify \
  --output "$PWD/build/json-writer-native-r1/attempt-2"
```

this recomputes membership from recipe/dependency/plan/source, not report keys;
checks copied inputs, all typed argv/stdin/stdout/stderr/executable receipts,
preexecution artifacts, AST reconciliation, SDK/driver/archive/map provenance,
original/current/repeat equality and the unchanged failing-model classification.
it does not compile or execute native code and does not write files. `record`
and `controls` already ran once and use exclusive output files. do not rerun
those into the existing tree. `run.py verify` has no pass report to consume.

## unresolved / next owner action

parent should independently replay the partial auditor, inspect the signed-char
probe boundary against compiler/source evidence and retain both failures as
closed. do not repair the model and call a renamed acquisition a third attempt.
a materially different, separately justified strategy or explicit new direction
is needed before any further acquisition; this unit grants none. no abi design,
consumer/selector adoption or Rust implementation follows from this partial.

unproved: native allocation/OOM; arbitrary pointer validity; universal ownership,
all allocation/temporary destruction fault timing; framework/interpreter/dylib
transitive implementations; transient edit/revert attestation; other platforms;
performance; actual application frames/audio/save/TCP. hex8/substr loops remain
source-inventoried but unreachable with the actual helper/printable domain and
have NO claimed runtime coverage. existing PathEmbed qualification, all frozen
production/helpers and default selectors were not changed.

owned sources are only `source/lab/json-writer/**`; owned acquired/supplemental
artifacts are only `build/json-writer-native-r1/**`. source hashes and the final
complete owned artifact-tree seal are in `build/json-writer-native-r1/handoff.json`.
