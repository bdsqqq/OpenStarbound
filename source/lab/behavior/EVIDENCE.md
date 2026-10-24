# native behavioral evidence — 2026-10-24

## compiled Unicode integration

VERIFIED — `build/behavior/unicode-actual-r1/`: independent C++/C++-repeat/Rust launches pass exact full RGBA/state/byte/receipt/restoration gates. Parent inspected all three PNGs: actual teal64×64 result, normal Font/TextPainter ASCII `UNICODE` label, occlusion and restoration. Normal Assets parsing of escaped JSON yields exact nine bytes `41c3a9f09f9880005a` (`Aé😀`, embedded NUL, `Z`) in Lua; its bytes drive the image. Actual String length5 drives drawable geometry, while sentinel length3 and UTF8 validation preserve the bounded/NUL distinction. No emoji glyph-coverage claim.

Observed Assets parse receipts `[0,18,0,52,5,0,5,0,0,0]`; normal String operations `[1,2,0,0,0,0,0,0,0,0]`. Production JSON writing yields exact16bytes `2241c3a9f09f98805c75303030305a22`; independent literal parsing returns the same nine text bytes. Write/read scopes `[0,0,0,12,0,1,0,0,0,0]` / `[0,1,0,5,1,0,1,0,0,0]`. Real RAM VersionedJson preserves its entire independently specified59-byte representation, decoded value and full consumption. Its raw binary String I/O records ZERO Unicode calls: save-byte preservation is not misrepresented as Unicode execution. C++ scopes are all zero.

Parent independently replayed the full frozen ten-function oracle, separate C++ observation stream, ABI/error/alias/guard tests and negative controls; see `../unicode/EVIDENCE.md`. Review exposed a real two-byte length-recovery read-pattern defect missed by initialized fixtures; protected-tail reproduction failed before one repair and both C++/Rust guards pass after. No frozen algorithm, expected bytes, tolerance or reference-flag changes. Public Unicode header/generic iterators remain unchanged; this is not the entire text module. Forty-four Rust tests EACHdebug/release/fmt,85behavior/provenance tests,8catalog drift controls pass; catalog1,460files/39modules.

The existing production PCM decoder oracle also passes with the fully combined native objects: `build/bytes-audio/unicode-combined-r1/report.json`, same exact PCM/channel/rate/count/EOF/seek/17byte-operation receipts and corruption control against the historical C++ reference. No audible playback, mixer, performance or whole-audio claim. Actual network transport/existing-save/cross-platform qualification remains open.

Native source-bound SHA256: C++ `9aeecbd3a8839c3ba3697cb47e54ce6705a0bfbdb87f95d84abbd848b86c6202`; Unicode-only `abda4dc71b3459036c9274fceccbfe4cc75b0b6f6c9010e2e423ac8fa0f0adcd`. Common canonical source-map SHA256 `7abb92ad8934ba0d9452f97ff5e53a33afa35d93dd3188a77611e5ef038978eb`; full compiler/cache/binary/source identities are sealed in launch manifests. Default-OFF rollout and performance qualification remain explicit gates. Full migration OPEN.

VERIFIED — `unicode-combined-r1` plus `unicode-{lighting-room,raycast-room,encoding-room,sha256-room,vlq-room,bytes-room}-regression-r1` ALL pass two C++ baselines/exact full RGBA/state/bytes/receipts/restoration. All six historical C++ pixel sequences match the previous byte-order checkpoint byte-for-byte. Combined teal-result/ASCII-label pixels equal all three inspected isolated frames; the combined occluded label/result was also inspected directly. Combined binary SHA256 `dd67fe5eba23e98539b55573c54a5b3910de04d811867de0ed5cea054a98c7ca`; all eight matrices share the source-map fingerprint above. Final reference/isolated/combined build-seal verification passed after capture (`/tmp/openstarbound-unicode-final-source.log`). The same current native objects bind the PCM replay. No owned build/capture remains; no reference inputs, tolerances, flags, goldens or masks were changed.

## byte-order integration

VERIFIED — `build/behavior/bytes-actual-r1/`: two independent C++ launches and the bytes-only Rust candidate pass exact full-frame RGBA/state/byte/receipt/restoration gates. Parent inspected all three candidate PNGs: blue `[64,128,192,255]` 64×64 result, normal room, occlusion and restoration. The normal Assets binary-JSON reader consumes the frozen 29-byte array `0603023fd0000000000000023fe0000000000000023fe8000000000000` → `[0.25,0.5,0.75]`, driving the actual image color. Scoped copy-from receipts `[0,0,0,0,0,3]` establish execution, independently of the screenshot.

Real PausePacket codecs decode literal current `013f000000` and legacy `01`; independent packet objects encode the same exact bytes. Values are pause=true and timescales0.5/1; the decoded current float controls normal WorldPainter drawable scale. Write/read byte receipts `[0,0,0,1,0,0]` / `[0,0,0,0,0,1]`. The packets are NOT delivered to the live session: release local sockets bypass serialization, so this is codec/consumer evidence, not transport interoperability.

Real RAM VersionedJson writes and independently reads the frozen **68-byte** `byteslab` file representation, version`0x01020304` and three binary64 values. Entire wire bytes, values and complete consumption match; scoped write/read receipts `[0,0,0,5,0,0]` / `[0,0,0,0,0,5]`. RAM BTree values span127/128/700 bytes and survive fresh-object reopen. All **2,560 raw page bytes** match both baselines; independent fixed headers assert BTreeDB5/block512/key32, not only round-trip equality. Observed scoped database receipts `[0,0,0,22,0,18]`. C++ scopes report zero. No existing-save or cross-backend persistence claim.

The separately linked production `Audio` decoder also passes literal PCM16 WAV → exact samples/channels/rate/count/EOF/seek. Parent independently reran `build/bytes-audio/{cpp-primary-r1,rust-primary-r1}/report.json`, including corrupted-PCM comparison controls; Rust receipts `[0,0,0,0,17,0]`. Both native build seals were verified before and after these object-bound decoder replays: logs `/tmp/openstarbound-bytes-audio-source-{before,after}.log`. This supplements the worker's object/source hashes with the current source-bound native build association; it remains a local stale-build guard, not a reproducible-build attestation. See `../bytes/AUDIO.md`. No audible playback, mixer/Ogg/resampling or performance claim.

The frozen full-header oracle and source-only ABI review are documented in `../bytes/EVIDENCE.md`. Parent40Rust tests EACHdebug/release/fmt,78behavior/provenance tests and8inventory drift controls pass; catalog1,448files/39modules. This is a complete bounded byte-order component, NOT the entire serialization or audio module. Default-OFF rollout retained. All baseline inputs/flags/goldens/tolerances unchanged; uninitialized padding and sequential overlap are preserved rather than 'fixed'.

Source-bound native SHA256: C++ `2ad29b7c6729bda87b28ec169f3a0c97d125d6e2d010c5e45eb5e7b6993cfda1`; bytes-only `9ebe68ca4ac02fef07ed1025ea56c67c44e858924848530c1dc02ae594c02688`. Common source-map fingerprint `782c6cab57d3436a686ebf6494c6f875caf6b33463d0f1882bfcc31958f1e671` (sorted compact JSON source_files SHA256). Full source/compiler/cache/binary identities remain in sealed launch manifests. Other platforms, performance, broader gameplay and the full migration remain open.

VERIFIED — `bytes-combined-r1` and `bytes-{lighting-room,raycast-room,encoding-room,sha256-room,vlq-room}-regression-r1` ALL pass two C++ baselines, exact full RGBA/state/byte/receipt/restoration gates. Combined blue-result pixels match every inspected isolated frame byte-for-byte; its occluded result, ray marker, encoding palette and old VLQ red result were additionally inspected directly. All three historical C++ baseline arrays for all FIVE previous scenarios are unchanged from the VLQ checkpoint. Combined binary SHA256 `398db66910c06035967dcd667335ffda892dbff684ec0560e0bff7b664fe442c`; all seven matrices share the source-map fingerprint above. Builds bg31PID93807/bg32PID18289 and capture loop bg33PID28872 completed; no owned process remains. No masks, golden updates, tolerance widening or reference-flag changes.

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
