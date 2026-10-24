# native behavioral evidence — 2026-10-24

status: laboratory exercised; **exact rust framebuffer parity FAILED**. do not advance the migration gate or describe this as complete game equivalence.

## tested artifacts

host: apple m2 pro / arm64 macOS; GL vendor `Apple`, renderer `Apple M2 Pro`, version `4.1 Metal - 91.7`. captures are 1000×600, final default framebuffer after imgui and before swap. both clients have steam/discord integrations OFF.

current native evidence: `build/behavior/real-game-r2-diagnostic/`. both clients were rebuilt using `scripts/build-behavior-lab.sh`, with before/after build-input snapshots. their sealed manifests retain 1,411 compile inputs, tool/cache identity, binary/config/asset/overlay/receipt/pixel hashes. these are local artifacts, not uploaded evidence or reproducible-build attestations.

```text
02299ccfc7c59b8aeb8207021f8e43b83b479e5d3eaa1bbd44289af83e5621e8  reference/bin/starbound
49f1c58260d79734dab677e34931554e8ea53e65075b2ff20f35c521343eb6a3  candidate/bin/starbound
```

paths above are relative to `build/behavior/`. canonical source-map SHA256: `92b57ba79c60ccc897ac58ca959bca3f5fea4ceb5cc784cbfdff693ff0b406d3` (UTF-8 JSON of `buildProvenance.source_files`, sorted keys, separators `,` and `:`). the full maps remain in each frame manifest. current-source preflight and post-run verification both passed.

## observed behavior

VERIFIED — `reference/frames/`, `reference-repeat/frames/`, `candidate/frames/`:

- real authoritative custom world, replicated static fixture object, material room, fixed camera and offscreen player; no scripts/animation/flicker on the test light. this is synthetic scene input rendered by the actual game, not a generated replacement screenshot.
- `lit-room`: illuminated floor/background and left wall; no foreground occluder.
- `occluder-added`: actual foreground column appears; lighting beyond it changes.
- `occluder-restored`: column removed; original pixels and stable/declared scene state restored exactly, in both backends.
- two independent c++ launches match every RGBA pixel and semantic state field across all three stages.
- rust semantic state matches c++; successful rust execution counters are positive and increase between stages. source inspection found no candidate fallback. counters alone are not per-world/per-channel attribution.
- rust differs at exactly **(117,375), blue channel only: c++ 48, rust 49**, in all three frames. the unchanged zero-error gate rejects every frame. see `comparison/report.json` and diff PNGs; `report.json` has `passed: false` and `parityCertified: false`.

primary inspected all three reference PNGs from the first fixture run `real-game-r1`, then all three diagnostic-run candidate PNGs and its initial diff; independent reviewer also inspected reference stages, candidate initial and initial diff. all nine diagnostic-run pixel hashes match their first-run counterparts. the one-step diff is not meaningfully visible at ordinary scale; exact pixel extraction locates it. CPU upload bits were inspected numerically. no passing visual-parity claim is made.

## discrepancy localization, not a completed repair

VERIFIED — `metadata.lightingDiagnostics` in the diagnostic run preserves the actual uploaded 66×40 RGB float map, world minimum `(31,28)`. reference/rust differ in 513 channels initially/restored and 469 while occluded; maximum absolute difference `5.960464477539063e-8`, maximum ULP distance 20. these diagnostic values do not mask pixels or replace the exact state/framebuffer gate.

VERIFIED — isolated expression/production-assembly probe `source/lab/lighting/diagnostic/run.py`, independently rerun by primary; outputs in `build/lighting-fp/`. production ARM fast-math uses fused arithmetic, reciprocal multiplication and circular-attenuation reassociation. diagnostic rust formulas matched production-fast c++ at seven sampled expression sites (300,000 scalar outputs). this is NOT complete-kernel equivalence.

HUNCH — those compiler arithmetic differences cause the observed threshold crossing. causal replay of exact selected kernel inputs and a production arithmetic-policy repair remain OPEN. do not change fixture colors/positions, reference flags, goldens or tolerances to obtain a pass.

## verifier and numerical checks

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
