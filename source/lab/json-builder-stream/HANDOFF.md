# json builder stream: native calibration blocked, budget closed

**not accepted; no rust/abi/application or whole-module claim.** this handoff
and `audit.py` are AFTER-observation supplements. frozen `README.md` describes
the intended gate, NOT a completed result; its intended explicit inf/nan scalar
expectations did not match native output. do not edit those expectations, trim
tokens, fit flags, or rerun under a renamed output directory.

host/worktree: apple silicon macos, `/Users/bdsqqq/www/OpenStarbound`.
tested/current head: `990981bdb5e440ee35ed89b54b5f462f7af9e156`.
started 2026-10-27 04:38 utc; stopped on closed two-attempt budget, within 25 min.
owned scope only new `source/lab/json-builder-stream/**` and
`build/json-builder-stream-native-r1/**`. no commits/delegates/cargo/game/capture,
no core/header/cmake/rust/default-selector/old-helper mutations. the parent owns
the concurrent plan-only edit; pre-existing `storage/` was untouched.

## verified observations

- complete 20 manually reviewed bodies, cpp **6–101** (the brief's end line 100
  omits the final closing brace), reconciled to compiler AST byte ranges and
  body hashes for frozen original and fresh current cpp. the adjacent streamer
  starting at line 103 is excluded and unchanged in every mutant. class header
  bytes and native layout are unchanged. all six implicit default/copy/move/
  assignment/destructor operations are separately emitted and used in fixture
  AST (`attempt-2/implicit-fixture.json`).
- independent python state machine/literal checks/corpus/tool/source/profile
  frozen before native observations: **889 cases, 4,537 events per run**.
  all five source variants ran twice: ten normal exit-0 executions, 45,370 total
  rows. original/current raw output is EXACT, including unordered-map iteration,
  intermediate exception type/what bytes, remaining stack and lifecycle probes;
  each variant's repeat is exact. no native outputs became goldens.
- original and current each have **20 frozen-model mismatch rows**, exclusively
  five explicit double tokens: `inf`, `-inf`, `nan`, `-nan`, `nan(payload)`.
  the native observer reports float-type bits `0000000000000000` for each; the
  frozen model expects signed inf/native quiet-nan bits. each mismatch persists
  through four events (value push, next push, array close, final take). all
  4,517 other rows match the unchanged model, but this is NOT a class gate pass.
  see `diagnostic-r1.json:mismatches` and `model.py:33–40,103`.
- three normally exiting compiled semantic mutants differ from the ACTUAL
  native reference (not merely from a mismatching model): missing array reverse
  **63 rows**, object key/value pop swap **99**, sentry take default instead of
  throwing **1,766**. both repeated outputs are retained with exact receipts.
- native profile derived from actual ninja/compile database, all **25 selectors
  OFF**. all 113 original core/extern objects bound readonly; exactly the known
  builder object replaced at the same position per link, plus one fresh fixture
  object: **114 linked objects**, 112 old objects reused, no duplicate builder.
  five fresh full cpp variants and one fixture compiled; NO 113-object rebuild.
- partial read-only audit reconstructs **4,704 required bindings**, **159 required
  artifacts**, **36 exact argv/stdin/stdout/stderr/typed-normal-exit receipts**,
  original/current AST inventories, current source/dependency/recipe closure,
  expanded driver runtime/LTO, physical archive identities, loaded traces and
  surviving map origins. each link has 2,489 loaded archive members. sdk whole
  interface/settings/symlink before/after witness is unchanged, consumed origins
  reconciled with unchanged mature `path-embed-replay` helpers.
- 11 python literal/model/inventory/typed-byte-comparison tests completed.
  the diagnostic verifier's isolated source-corruption and artifact-omission
  clones were rejected through the same partial audit; fixtures retained under
  `diagnostic-controls-r1/`. these AFTER-observation checks do NOT satisfy the
  blocked acceptance verifier's before-publication corruption-control gate.

confidence: **VERIFIED** for the observations above. falsification attempted:
byte-for-byte native repeats/original-current comparison; complete independent
model comparison (which DID reject); actual exit-0 semantic mutants; isolated
source/artifact corruptions. reproducible read-only audit:

```
python3 -B source/lab/json-builder-stream/audit.py "$PWD/build/json-builder-stream-native-r1/attempt-2"
python3 -B source/lab/json-builder-stream/test_lab.py
```

**HUNCH, not diagnosed:** the frozen `-ffast-math` profile may participate in
explicit inf/nan constant handling. source text assigns native inf/nan constants
in `source/extern/fast_float.h:3588–3640`; `StarLexicalCast.hpp:50–57` forwards the
result and `StarJson.cpp:121–123` stores it. the native observer is type-aware and
copies double bits without float arithmetic. no assembly/alternate-flag/leaf
probe was executed, so neither compiler cause nor observer cause is established.
source text alone did not prove the compiled scalar behavior. do NOT normalize
nan/inf, modify flags, or update expected output from these observations.

## attempts and remaining gates

1. `attempt-1`: all AST inventory and six fresh units compiled; first link
   reconciliation threw a JSON `TypeError` on a nested byte-path list. no native
   runtime observation. one verifier fix added explicit bytes encoding, with
   positive/negative byte-list and bool/int/float distinction unit tests.
2. `attempt-2`: fresh freeze/AST/compile/link/repeats all acquired; acceptance
   stopped on `independent native model original`. model, corpus and expected
   bytes are unchanged from attempt 1. **two unsuccessful attempts CLOSED.**

both retain inputs/snapshots/logs/objects/outputs. `attempt-2/candidate.json`
remains `RAW_NATIVE_ACQUISITION_PENDING_VERIFY`; **no `report.json` exists**.
acceptance verifier corrupt-fixture controls never ran because model comparison
failed first. ABI/ownership qualification, rust, consumer/game evidence and
universal resource/platform equivalence remain unproved. semantic object oracle
sorts unordered members; only original/current native traces check raw iteration,
not independently specified insertion history or unsorted serialization.

next action: parent independently review/archive/checkpoint the partial lab and
record the closed budget. a future genuinely different contract investigation
requires its own justified scope; no third patch/replay or partial-to-port
inference is authorized here. all owned supervisor/interpreter pids
19360/19362/20849/20852 and native descendants were terminal at 04:50 utc.

## retained identities

- production/original cpp `8fde1f301b9cd47e643ab58145a33fafcc64e6a294040dd242f53c1cd0507591`
- production/original header `f201d6eab6e60a1bfd82439b0b405c8fffd825339a4b3614604b0cfeb39c6294`
- frozen model `c88def7a000dbe98a8558bb741342244042962fb75b4abcba3f976e8fb129389`
- input tsv `197af03b05a62ae17f7542a96fc8e25244ca094db4c98b6531df0856ba2f52e4`
- expected tsv `97de6374cd468850bbadea1635e0308d510452f4f4c9d1c0e5c537e413678548`
- diagnostic supplement `e280cf15d715d9b17943ad3c60b6a3e529c00d572c90f3905cb66ed141b560a5`

logs retained at `build/json-builder-stream-native-r1/attempt-{1,2}.log` and the
original `/tmp/openstarbound-json-builder-stream-native-r1-attempt-{1,2}.log`.
whole production closure/source bytes unchanged; live catalog binding will become
historical when the parent refreshes metadata, with frozen catalog copies kept.
