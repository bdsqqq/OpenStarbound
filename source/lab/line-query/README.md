# frozen 2d line-query calibration

run from the repository root:

```sh
python3 'source/lab/line-query/run.py'
```

all generated headers, binaries, bit observations, compile/run logs and `report.json` stay in `build/line-query-lab/`. no cmake/ninja/cargo/game invocation. the existing native reference compile database supplies the compiler, optimization, sdk, architecture, includes and platform defines; only source/output and fp policy are replaced. undefined-behavior and float-cast-overflow sanitizers are enabled, without float-divide-by-zero sanitization: floating division by zero is deliberately in scope.

## frozen boundary

`StarLine.original.hpp` is the complete byte-exact `git show a0296af5:source/core/StarLine.hpp`, frozen before candidate changes. there is NO regeneration command. the runner checks both the fixed digest and git bytes:

- raw sha256: `ca4d5810770a085611304cc6c4871e620aad6f187bbad51390ea23befb522567`
- adapted sha256: `c34fddc148c9b9f4800638ae09cbe92eceb7c496dc03d0586c8d691395e4b628`

sole allowed adaptation: replace the first `namespace Star {` with `namespace FrozenReference {\nusing namespace Star;`; retain all bytes before the exact `template <typename T, size_t N>\nstd::ostream& operator<<` suffix boundary (original lines 269–289), omit that ostream/hash/fmt suffix, append `}\n`. the suffix's `Star::hash` specialization and out-of-namespace `fmt::formatter` cannot legally specialize those templates inside an unrelated namespace. no query, constructor, member, alias or arithmetic body is edited. fixed raw/adapted hashes prevent moving this boundary or accepting a second adaptation.

actual `StarMatrix3.hpp`, `StarVector.hpp`, `StarArray.hpp`, `StarMathCommon.hpp` and `StarAlgorithm.hpp` are included, not numerical stubs. their fixed hashes are gated in `run.py` and recorded in the report. this is not a fully vendored transitive dependency closure; a future primitive change requires separate research, not changing both sides to obtain agreement. candidate source changes during a run invalidate that run.

## observations and domain

`lab.cpp:13` is the typed contract, and `Production.hpp` is the only candidate adapter seam. every query compares `intersects`, `coincides`, `glances`, the independent `intersects()` predicate, both point components, `t`, projection and distance. no set-only or hit-only comparisons. `*-observations.txt` rows contain scalar width, infinite flag, ten input bit words, then reference and candidate groups separated by ` | `. each group contains four flag digits followed by hexadecimal point.x, point.y, t, projection, distance words. all floating bits are retained, including NaN payloads, for diagnosis.

comparison is exact bits for finite numbers, infinities and signed zero. NaN-to-NaN is classification equality only: payload/sign propagation is not promised by this contract. NaN-to-number always fails. there is no epsilon/tolerance or regeneration route. bit classification uses integer masks so `-ffast-math` cannot optimize away `isnan` checks. cross-policy diagnostics separately report raw-bit differences and differences remaining after NaN classification; they are NOT cross-policy passes.

source-traced semantics that a replacement must preserve:

- `StarMathCommon.hpp:60–96`: near-zero is `2 * MIN_NORMAL`, not machine epsilon; near-equal uses relative epsilon, with the original mixed `1.0f` literal at frozen line 203.
- frozen lines 162–187: coincident selection is lexicographic and orientation-sensitive, not normalized interval geometry. point defaults to zero even for disjoint coincidence, while `t` can still be computed. `StarVector.hpp:325` and `StarArray.hpp:113–114` establish zero initialization; no uninitialized field is read.
- frozen lines 199–203: a false hit flag does not erase computed point/t. endpoints glance; near misses must not get positive hit/glance flags.
- frozen lines 216–226: projection is unbounded, finite-segment distance clamps its parameter, infinite distance does not.
- f64 is production scope: `source/game/StarCelestialDatabase.cpp:599–625` constructs `Line2D`, intersects constellation lines and uses double distance queries.

raw IEEE inputs, zero-length lines, infinities, quiet/signaling NaNs from raw bits, underflow and finite inputs whose intermediates overflow are included. floating nonfinites are not labeled integer UB. integer instantiations are excluded: the cross products and multiplication/subtraction at frozen lines 155–157 can overflow signed integers; those exclusions do not apply to f32/f64. transforms, line containers, rotation, angle and length are outside this four-query port contract.

## verified calibration, apple clang 21 / arm64

command above passed initially with candidate root header equal to the frozen original, then passed again after the concurrent worker added the root adapter. the primary guarded-header calibration (`build/line-query-lab/cpp-final-r4/report.json`) binds candidate header sha256 `b26945549db6f646aa2fde0738a5cdc43ab500a66b3b6766d357e2415607c676` (no backend macro or Rust archive supplied). the frozen raw/adapted bytes stayed unchanged. this is the C++ fallback calibration, not evidence that the new Rust adapter ran. each of the three policies ran **20,274 cases / 182,488 checks**, including eleven independent anchor assertions per scalar, and an identical second run with byte-exact observation files:

- uncontracted: `-fno-fast-math -ffp-contract=off`
- default non-fast contraction: `-fno-fast-math`
- recorded production fast policy: `-ffast-math`

full commands, compiler/sdk identity, binary/source hashes and shared primitive hashes are in `report.json`; zero sanitizer diagnostics and zero candidate/reference mismatches occurred. there are 10,137 cases per scalar. cases include reversal, parallel/disjoint/overlap, endpoints, near-zero, zero length, infinite queries, decimal non-lattice values and deterministic xorshift64 raw words (seed `0x6c696e6551756572`). finite decimal cases and arbitrary exponent/sign/mantissa cases alternate.

independent anchors cover true crossing, coincident selection, reversed disjoint defaults, parallel sentinel, false-hit computed fields, endpoint glancing, one-epsilon near miss, projection vs clamped distance, and infinite distance/coincidence. agreement between two copies alone is not the acceptance criterion.

**23 negative controls pass:** frozen-source corruption, unauthorized arithmetic adaptation, and seven executable mutants per policy. three are actual isolated algorithm-body mutants (negated direction, wrong coincident endpoint selection, inverted hit condition for glancing); the others damage point, t, clamp projection, or overwrite the typed distance field. every executable exits 1 through `FAIL` field comparisons; compile errors, crashes and sanitizer failures do not count as detection. mutants are generated separately and never modify `FrozenReference`.

### fp findings, not tolerance proposals

VERIFIED in `build/line-query-lab/report.json`, `cross_policy_observations`: default contraction differs from uncontracted in 9,691 rows after NaN classification (9,679 with entirely finite inputs); production fast differs in 14,184 rows (13,966 finite-input rows). the default policy's first finite case, row 62, changes point words `c3ebc928/445c9119` to `c3ebc929/445c911a`. this falsifies a single uncontracted expected-bit policy for all production modes. no tolerance was added.

production-fast zero-length row 1 returns distance `0`, where uncontracted returns NaN; row 2 returns distance `3fb504f3`, where uncontracted returns NaN. these are actual floating observations, not excluded UB. production fast assumptions/reassociation and precise IEEE behavior must be handled as distinct compiled policies. root-candidate vs frozen-reference agreement within a policy does not establish equality across policies or a portable Rust arithmetic sequence. the complete inputs and bits remain replayable in the observation files. mechanism-level attribution of each difference remains research work.

## experimental rust: production fast-math BLOCKED

keep the frozen source, adaptation, shared primitives, anchors and exact comparison policy unchanged. the production adapter now rejects `__FAST_MATH__` at compile time, including when `STAR_RUST_LINE_FP_PRECISE` is also defined. `STAR_USE_RUST_LINE_QUERY` remains default OFF. policy 1 in the C ABI is a diagnostic experiment, not compatibility support. existing native lighting/traversal/combined build recipes explicitly leave the new backend OFF.

```sh
CARGO_TARGET_DIR="$PWD/build/line-query-rust/target" cargo build \
  --manifest-path 'source/rust/Cargo.toml' --package star-engine-ffi \
  --release --locked --offline
python3 'source/lab/line-query/run.py' --define STAR_USE_RUST_LINE_QUERY \
  --archive 'build/line-query-rust/target/release/libstar_engine_ffi.a' \
  --policy uncontracted --policy default-contract \
  --output 'build/line-query-lab/rust-supported'
```

VERIFIED sampled result: each selected policy passes 20,274 cases / 202,762 checks with 81,096 successful executing-thread Rust receipts (four per observation), plus 16 negative controls across the two policies. the extra receipt checks prevent a C++ fallback from silently satisfying the numerical gate. this is optimized apple clang 21 / arm64 calibration, not qualification of other optimization/inlining contexts. the Rust workspace's 19 tests pass debug/release; formatting passes. no game was built or launched for this component.

failed fast arithmetic remains replayable through a **lab-only direct ABI adapter**, without weakening the production compile guard or changing the frozen reference:

```sh
python3 'source/lab/line-query/run.py' --direct-abi \
  --archive 'build/line-query-rust/target/release/libstar_engine_ffi.a' \
  --output 'build/line-query-lab/abi-diagnostic'
# EXPECT exit 1: production-fast is numerically incompatible, not a pass.
```

VERIFIED `build/line-query-lab/abi-primary-r1/report.json`: precise/default each pass; production-fast has **17,485 failed field checks**, despite all 81,096 receipts being present. this differs from the worker's earlier 8,290 failures in a different compiled harness; neither is generalized into an error rate or a compatibility claim. contextual contraction/reassociation remains unresolved. the original bounded repair approach is exhausted; another round of FMA tuning is not authorized by relabeling the same approach. a new approach needs a source-traced proposal, not changed tolerances or reference flags.

`--policy` selects and reports compiled policies; it never treats one policy as equivalent to another. omitting it still runs all three, so selecting the production adapter without a policy restriction fails at the fast compile guard. arbitrary `--define` values are rejected: only the backend selector is allowed, never primitive/arithmetic redefinitions. Rust selection and its archive must be paired. reports bind before/after hashes of checker, adapter, candidate header, shared primitives and archive; changing inputs invalidates the run. isolated `--output` paths must stay beneath `build/line-query-lab`. executable mutation controls are skipped on an already-failing baseline: rejection there would not establish mutation detection.

### receipt verifier known failure

`receipt_negative.c` is an isolated fake ABI with successful statuses, incorrect zero-valued results and a permanently zero receipt. it is NOT a Rust backend or a reference. its run must exit 1 and explicitly report `FAIL four successful Rust query receipts`; numerical failures are also expected and are not counted as proof of the receipt check.

```sh
mkdir -p 'build/line-query-lab/receipt-negative'
xcrun clang -std=c11 -I'source/core' -c 'source/lab/line-query/receipt_negative.c' \
  -o 'build/line-query-lab/receipt-negative/ffi.o'
xcrun ar rcs 'build/line-query-lab/receipt-negative/stub.a' \
  'build/line-query-lab/receipt-negative/ffi.o'
python3 'source/lab/line-query/run.py' --direct-abi \
  --archive 'build/line-query-lab/receipt-negative/stub.a' \
  --output 'build/line-query-lab/receipt-negative/run'
# EXPECT exit 1; inspect all three policy logs for the receipt-specific failure.
```

remaining gaps: actual-game polygon/wrap-seam and celestial evidence, other optimization/platform contexts, universal floating equivalence, a fully frozen transitive dependency closure, and production fast-math support. this is a guarded experimental query kernel and its verifier, NOT a completed module or game equivalence.
