# native behavioral evidence — 2026-10-24

## vlq integration

VERIFIED — `build/behavior/vlq-actual-r1/`: two independently launched C++ baselines and the VLQ-only Rust candidate pass exact full-frame RGBA, state, backend receipts and restoration for all three stages. Parent inspected all three candidate PNGs: normal room, added occluder and restored room, with the decoded asset's opaque red 64×64 foreground result visible. No masks, tolerances, reference flags or historical fixture inputs changed.

This is real normal postLoad `assets.json` → embedded binary JSON → DataStream/VLQ decoding → generated asset → WorldPainter drawing, not a synthetic verifier image. Independent literal input `0602048101048200` decodes `[-65,128]`; a separate literal length128 string decodes 128 `x` characters. Scoped Rust receipts are `[0,0,1,0,0,2]` and `[0,0,1,0,0,0]` respectively; C++ receipts are zero. A cropped seed leaves the existing lamp image unchanged.

The same native client additionally exercises real RAM-only VersionedJson/save, current/legacy Ping/Pong codecs, BTreeDatabase pages and stream EOF. Save output is **183 exact independently specified bytes**, not merely paired round-trip equality; writes `[7,0,0,3,0,0]`, reads `[0,0,7,0,0,3]`. Current packets are literal `8101`/`8200`, legacy each `00`; decoded times `[-65,128,0,0]`. Signed size(-65)=2 exercises the size entrypoint. Database values span 127/128/700 bytes, fresh-object reopen succeeds, and **2,560 raw page bytes** match both C++ baselines exactly, with scoped receipts `[6,8,8,0,0,0]`. EOF on `81` preserves EofException, consumed1 and unsigned prefix1. The separate proof checker verifies literals, types, operation counts and page bytes; 68 behavior/provenance tests include isolated corrupted-proof/receipt/pixel controls.

No claim of actual network transport: release local sockets bypass serialization. These packet methods run explicitly. No existing save, cross-backend persistence, dedicated-server gameplay, other-platform, security or whole-module claim. Assets digest length serialization is fixed-width and is NOT counted as VLQ evidence. The frozen numerical/generic-iterator oracle and one adversarial forwarding repair are documented in `../vlq/EVIDENCE.md`; all six algorithms remain default-OFF behind the existing single Rust archive.

Source-bound native binary SHA256: C++ `604cb1bee5c80ca15d82b4895d71a0de0932ba85aab701a62044735a28f5b25b`; VLQ-only `059c3c179d2d003e18e6bb52f8ca3e98cdd78e3c147e366f7f0856b74ec03d70`. Full compiler/cache/source/binary receipts remain in each capture's sealed launch manifest. Final catalog: 1,438 files / 39 modules; eight drift/negative tests pass. The full migration remains open.

VERIFIED — `build/behavior/vlq-combined-r1/` and `vlq-{lighting-room,raycast-room,encoding-room,sha256-room}-regression-r1/` each pass two independent C++ baselines, exact full RGBA/state/receipts and restoration. Combined VLQ pixels equal the three inspected isolated VLQ frames byte-for-byte; its occluded frame, ray hit marker and encoding palette were additionally inspected directly. All historical C++ baseline pixel arrays equal the preceding SHA checkpoint arrays, across all three stages of all four prior scenarios. No golden updates. Combined binary SHA256 `d4b628077437523e35604fbe7faf655ad082ea82ff4f65b3f54b750a858ee82f`. All six current native matrices share source-map fingerprint `fff1f97212f9c62f60d4b0b014ae88773095b66e1ba54a27ca969fb10dfd5923` (SHA256 of sorted compact JSON `buildProvenance.source_files`); launch manifests bind the full tool/cache identities too. Native builds and the owned capture loop completed; no owned process remains. Other-platform and broader gameplay compatibility are still unverified.

current result: **exact framebuffer/state gate PASSED for the three-stage lighting-room fixture**, on apple clang 21 / aarch64 / fast-math. this is finite scenario evidence, not universal bitwise or whole-game equivalence. the initial failure is retained below.

the subsequent traversal-only and both-Rust raycast matrix, visible result-marker inspection and retained initial visual failure are recorded in [`../traversal/EVIDENCE.md`](../traversal/EVIDENCE.md). the original lighting fixture also passed with both backends enabled, with unchanged C++ pixels.

## archive aggregation follow-up

VERIFIED — `build/behavior/aggregate-r1/`: one workspace/static FFI archive now owns the three unchanged C exports; lighting is an rlib and the legacy CMake target is an alias. only export ownership, packaging and build boundaries changed, not arithmetic. primary rebuilt both source-bound clients and reran the actual fixture: baseline repeatability, exact candidate state/pixels and restoration all PASS. all nine framebuffer hashes and all reference/candidate CPU upload maps equal the preceding `arm-policy-r1` artifacts, binding the existing inspected scene evidence to these artifacts.

```text
e89020b0ad9636392a4c95c3130a6f3132f5a661fe311617d7bbeb86f4e4f116  reference/bin/starbound
3b4407d452b53f24c8d5c4ba1cb2b70c69893707c325c669c848e32d35562f9e  candidate/bin/starbound
```

paths relative to `build/behavior/`; canonical source-map fingerprint `6b6a41fd15f39f95f232078e048956f6a208a6074e2f16689b03add423fda028`. current checks: workspace15 tests in debug/release, fmt, nine numerical CTests and 14,734,528 channels per mode serial/concurrent (seed1592594996), C consumer invocation of all3 exports, target isolation and architecture rejection controls, 40 behavior/provenance tests. no tolerance changes. primary removed duplicate alias/global archive references from numerical lab links: the Rust lab link contains exactly one aggregate and the C++ fallback link contains none; the Rust-OFF native graph contains no Rust target. logs `/tmp/openstarbound-aggregate-{native-build,real,primary-numeric,behavior-tests}.log`.

this remains native-client fixture evidence, not a fresh dedicated-server session or other-platform certification. source/workspace receipts are unsigned local stale-build guards with the limitations recorded above/below.

## production-arm arithmetic follow-up

VERIFIED — `build/behavior/arm-policy-r1/`, rebuilt source-bound clients, first arithmetic repair attempt:

- both independent c++ baselines retain the original `21f3ef31` pixel hashes for all three stages; no reference flags, scene inputs, goldens or tolerances changed.
- rust matches c++ exactly in every RGBA pixel and semantic state field for `lit-room`, `occluder-added`, `occluder-restored`: max channel error **0**, changed pixels **0**, per 1000×600 frame. each run restores the initial frame and observed material/state exactly.
- final frame hashes bind inspection to the already inspected c++ images described below. the machine report still leaves `parityCertified: false` by design; this inspected claim is limited to the stated fixture/host.
- explicit per-invocation arithmetic policy matches traced production expressions: RGB spread FMA, RGB subtraction reciprocal multiplication, source-placement reassociation, fused distance, circular-attenuation reassociation. selection requires Apple clang major21 + aarch64 + fast-math; other callers retain the original precise entrypoint. no shared mutable math mode or C struct layout change.
- the actual production `StarCellularLighting.cpp.o` imports `_star_lighting_calculate_arm_fast`. all three candidate receipts report successful Rust execution. a separate C++ adapter fixture deliberately redirected to the old entrypoint fails with the exact arithmetic-route diagnostic (exit2), rather than merely a build/link failure.
- **14 CPU lightmap channels still differ** in each stage, max absolute difference `2.9802322387695312e-8`. Wu accumulation remains precise. complete production floating-point equivalence is NOT established; different scenes/viewports may expose other quantization boundaries.
- independent source review found no actionable defect in the five-file arithmetic diff. primary reran 14 debug +14 release Rust tests, fmt, nine native CTests, ABI/config checks, 40 behavior/provenance tests and the route negative control. fixed scalar/RGB numerical corpus: seeds `1592594996`, `1`, `4294967295`, **44,122,768 channels per mode** serially and again concurrently. precise/fallback maximum error0; fast maximum error `1.00136e-5`, budget fraction `0.216513` under the unchanged numerical gate.

native binary SHA256, relative to `build/behavior/`:

```text
bb19b6cee55f82523cd22c09f0f9b7bc4d062dbab4718e7e89750509db8d9b61  reference/bin/starbound
b544ffd294a620ac914f74b9f73bb4a2b6945b666f54f41aff602533847c9291  candidate/bin/starbound
```

source-map fingerprint (same canonical method below): `f2fa547aed2eddade15d199d9db72c43c4d6f02dd654073e7a805b6ae5921521`. full source/tool/cache receipts remain in the sealed manifests. logs: `/tmp/openstarbound-arm-policy-{build,real,numeric}-r1.log`, `/tmp/openstarbound-arm-policy-extra-seeds.log`, `/tmp/openstarbound-arm-policy-route-negative.log`.

current numerical artifacts:

```text
5ba30dcc5b534d342243ece2efd12339b163408c2d9553dd458332d62f373045  dist/lighting_lab
58300be6e09c9f5b715898b4a81f6af4d2a8b6e071675ac717e14fc32caeff66  dist/lighting_lab_fastmath
7fa4c0089ef600f5c2989c3655eb6d6f5a47d00558b8415d6fe8bb57b0268fc9  dist/lighting_lab_cpp
```

## original failure at checkpoint 21f3ef31: tested artifacts

host: apple m2 pro / arm64 macOS; GL vendor `Apple`, renderer `Apple M2 Pro`, version `4.1 Metal - 91.7`. captures are 1000×600, final default framebuffer after imgui and before swap. both clients have steam/discord integrations OFF.

current native evidence: `build/behavior/real-game-r2-diagnostic/`. both clients were rebuilt using `scripts/build-behavior-lab.sh`, with before/after build-input snapshots. their sealed manifests retain 1,411 compile inputs, tool/cache identity, binary/config/asset/overlay/receipt/pixel hashes. these are local artifacts, not uploaded evidence or reproducible-build attestations.

```text
02299ccfc7c59b8aeb8207021f8e43b83b479e5d3eaa1bbd44289af83e5621e8  reference/bin/starbound
49f1c58260d79734dab677e34931554e8ea53e65075b2ff20f35c521343eb6a3  candidate/bin/starbound
```

paths above are relative to `build/behavior/`. canonical source-map SHA256: `92b57ba79c60ccc897ac58ca959bca3f5fea4ceb5cc784cbfdff693ff0b406d3` (UTF-8 JSON of `buildProvenance.source_files`, sorted keys, separators `,` and `:`). the full maps remain in each frame manifest. current-source preflight and post-run verification both passed.

### observed behavior before repair

VERIFIED — `reference/frames/`, `reference-repeat/frames/`, `candidate/frames/`:

- real authoritative custom world, replicated static fixture object, material room, fixed camera and offscreen player; no scripts/animation/flicker on the test light. this is synthetic scene input rendered by the actual game, not a generated replacement screenshot.
- `lit-room`: illuminated floor/background and left wall; no foreground occluder.
- `occluder-added`: actual foreground column appears; lighting beyond it changes.
- `occluder-restored`: column removed; original pixels and stable/declared scene state restored exactly, in both backends.
- two independent c++ launches match every RGBA pixel and semantic state field across all three stages.
- rust semantic state matches c++; successful rust execution counters are positive and increase between stages. source inspection found no candidate fallback. counters alone are not per-world/per-channel attribution.
- rust differs at exactly **(117,375), blue channel only: c++ 48, rust 49**, in all three frames. the unchanged zero-error gate rejects every frame. see `comparison/report.json` and diff PNGs; `report.json` has `passed: false` and `parityCertified: false`.

primary inspected all three reference PNGs from the first fixture run `real-game-r1`, then all three diagnostic-run candidate PNGs and its initial diff; independent reviewer also inspected reference stages, candidate initial and initial diff. all nine diagnostic-run pixel hashes match their first-run counterparts. the one-step diff is not meaningfully visible at ordinary scale; exact pixel extraction locates it. CPU upload bits were inspected numerically. no passing visual-parity claim is made.

### discrepancy localization before repair

VERIFIED — `metadata.lightingDiagnostics` in the diagnostic run preserves the actual uploaded 66×40 RGB float map, world minimum `(31,28)`. reference/rust differ in 513 channels initially/restored and 469 while occluded; maximum absolute difference `5.960464477539063e-8`, maximum ULP distance 20. these diagnostic values do not mask pixels or replace the exact state/framebuffer gate.

VERIFIED — isolated expression/production-assembly probe `source/lab/lighting/diagnostic/run.py`, independently rerun by primary; outputs in `build/lighting-fp/`. production ARM fast-math uses fused arithmetic, reciprocal multiplication and circular-attenuation reassociation. diagnostic rust formulas matched production-fast c++ at seven sampled expression sites (300,000 scalar outputs). this is NOT complete-kernel equivalence.

HUNCH at this checkpoint — those compiler arithmetic differences cause the threshold crossing. the follow-up policy above repairs the observed pixel without changing scene/reference/tolerance; attribution to an individual expression and complete-kernel equivalence remain unproven.

### original verifier and numerical checks

- 40 Python tests passed: native-only receipt/phase validation, pixel/color/tile/alpha corruption, independent baseline, unsafe paths/storage, private timeout cleanup, overlay integrity, missing/stale build proof, source additions/deletions, build-time edits and compiler/cache mutations. synthetic unit clients do not prove native gameplay.
- eight migration-inventory tests passed; catalog check accounts for 1,397 files / 39 modules. diagnostic rust is classified as harness code, not a production port.
- `scripts/lighting-lab.sh` passed after configuring the existing native numerical build with `VCPKG_MANIFEST_INSTALL=OFF` (dependencies already installed). initial regeneration failed because a host compiler probe selected the nix SDK; that failed command is retained in `/tmp/openstarbound-lighting-resume-checks.log`. successful rerun: `/tmp/openstarbound-lighting-resume-checks-r2.log`.
- rust debug/release: 12 tests each; fmt passed. nine native CTests passed, including deliberate mismatch controls. C ABI invocation, target-dir isolation and universal-build rejection passed.
- current numerical corpus: seed `1592594996`, 4,121 cases, 14,734,528 channels PER mode, serial and independent concurrent replay. precise rust and c++ fallback maximum error zero; production-fast oracle versus rust maximum error `6.19888e-6`, budget fraction `0.165479`, under the original fixed `1e-5 + 1e-5 * max(abs(a),abs(b))` gate. this numerical tolerance does not excuse failed exact screenshots.

numerical artifacts, SHA256:

```text
ff9dbf8770567b745d6149ccd7b2681a867025935834584f8eaf4b086be86323  dist/lighting_lab
a1dbbde1b9fb2e47de0c0150c355f6e1802589d2017ef6a4aeeb3e5240d8d911  dist/lighting_lab_fastmath
b5d1010cc8511bc8d9c3ca916ad01d4cf4c0ddb69976bded6fb5fb6567143771  dist/lighting_lab_cpp
```

other platforms, moving-gameplay replay, save/network/audio parity and performance remain unverified. no pushes, publishing, Steam-install changes or user-save writes were performed. the full migration remains open.
