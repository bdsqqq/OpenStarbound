# rust grid traversal evidence — 2026-10-24

status: float/double traversal and the finite native raycast fixture pass. this advances `base.geometry`; it does NOT complete all world geometry or establish universal game equivalence.

## source and ABI scope

- original C++ header frozen from `f5c4da28`, SHA256 `c917ceeeba883c8c267b03861e0b171d0c7c3f2098b9cc419e6e463ea006d077`; namespace/import-only adaptation verified, no golden regeneration.
- Rust implementation: `source/rust/ffi/src/blocks_along_line.rs`; exported through the existing single aggregate. `StarRustTraversal.h` defines typed f32/f64 synchronous visitor entrypoints and executing-thread receipts. no retained pointers or foreign allocation ownership.
- C++ adapter preserves Scalar endpoint rounding, lazy ordered visits, early false including last, reentrancy and the exact original exception object via catch-all/exception_ptr/rethrow AFTER Rust returns. unsupported Scalar types and backend-OFF retain original C++.
- status0 completed,1 stopped,2 invalid,3 contained panic. policy0 uncontracted;1 traced Apple clang21 ARM fast math;2 default non-fast contraction. nonstandard contraction flags and other fast-math compilers are not silently assigned a policy.
- independent switch `STAR_USE_RUST_BLOCKS_ALONG_LINE`, default OFF. either Rust backend uses one aggregate; traversal-only does not select Rust lighting.

## numerical/callback and configuration evidence

primary rebuilt the aggregate and independently ran:

```sh
python3 source/lab/traversal/run.py --rust-archive build/traversal-rust/release/libstar_engine_ffi.a --output-dir build/traversal-lab/primary-rust
python3 source/lab/traversal/check_cmake.py
```

VERIFIED — each of three FP policies runs 11,037 float/double cases; checks are 771,075 uncontracted,771,165 default-contract,771,105 production-fast. all pass with C++ undefined-behavior/float-cast sanitizers. ordered callbacks, every abort/typed/nonstd exception index and exception_ptr identity, nesting, concurrent C callbacks, TLS receipts, binary/non-lattice corners, Scalar endpoint rounding and wide valid early-abort prefixes are covered. 11 negative/provenance controls are detected. the unexecuted original undefined suffixes are explicitly excluded, not equivalence passes.

workspace debug/release: 16 tests each; formatting passed. four CMake backend combinations and three platform rejection controls pass. lighting regression: nine CTests, fixed 14,734,528-channel corpus per mode serial/concurrent, ABI exports and target/platform controls pass without threshold changes. behavior/provenance/marker unit suite: 51 tests pass.

logs: `/tmp/openstarbound-traversal-primary-rust.log`, `...-primary-cmake.log`, `...-workspace-{debug,release}.log`, `...-lighting-regression.log`, `/tmp/openstarbound-raycast-final-unit.log`. report/compiler commands/negative logs: `build/traversal-lab/primary-rust/`.

## actual running-game matrix

VERIFIED — Apple M2 Pro / aarch64, clang21, macOS27 SDK, native 1000×600 final framebuffer after imgui/pre-swap; SDK integrations OFF. isolated normal Assets/ObjectDatabase/WorldClient/WorldServer/WorldPainter pipeline, not generated replacement images.

- `build/behavior/raycast-visible-r2`: C++ lighting in BOTH, C++ traversal reference versus Rust traversal candidate.
- `build/behavior/raycast-combined-r2`: C++ reference versus BOTH Rust backends.
- `build/behavior/lighting-combined-r2`: unchanged lighting scenario versus BOTH Rust backends.

all three suites: two independent C++ baselines exact, candidate state/RGBA exact, all three stages passed with max error0 and changed pixels0. initial/restored pixels and state match. original C++ lighting pixels also match the pre-traversal `aggregate-r1` captures. combined ray pixels equal inspected isolated ray pixels. the machine reports deliberately leave `parityCertified:false`; these claims are limited to the inspected fixture/host.

ray fixture: actual public client/server collision, first point/normal, unlimited tile list, cap1 and cap0 queries, from `(54.5,48.5)` to `(74.5,48.5)`. adding columns62/70 changes false/null/empty into true, point `(61.999900817871094,48.5)`, normal `[1,0]`, tiles `[[62,48],[70,48]]`, cap1 `[[62,48]]`, cap0 `[]`. every per-query receipt on each executing side is exactly1 for Rust,0 for C++; counts cannot be covered by unrelated calls. removing columns restores clear observations. the ray-only platform gap `(70,40)` keeps both target columns initially empty; lighting-room geometry is unchanged.

primary inspected clear/blocked/restored candidate PNGs: visible cyan ray/yellow endpoint reaches the actual returned client point, shortens at the first wall, and restores after removal. the overlay is rendered by WorldPainter from that same-frame public query result.

## visual failure detected before acceptance

first `raycast-isolated-r1` had exact pixels/state but an INVISIBLE result marker: width0.12 logical pixels became0.24 physical pixels. primary inspection rejected the visual claim. `WorldPainter` scales line WIDTH by camera pixel ratio, unlike endpoints by tile size; driver now uses2 logical pixels. no query inputs/colors/oracle/tolerances changed. the marker validator now requires cyan/yellow ink in result-derived screen regions while pixel comparison remains UNMASKED. primary independently revalidated the old actual dataset: rejected for missing cyan ink, with all original file hashes unchanged. one marker repair attempt, successful.

## tested artifact identities

SHA256, binaries relative to `build/behavior/`:

```text
6c1348e967f284ad578551b7529465a3172f12c94b3216275e778665c34580ef  reference/bin/starbound
57dea4b3bfb0d050bc0e2a6f467c445348655a6e8f6945858b6ac8526eee1f95  traversal/candidate/bin/starbound
5b7430dc379d6d90658fd643c8cffbe2e542798009a8ba39db35132b6e925ea9  combined/candidate/bin/starbound
```

common source-map SHA256 `7452770cc7e18760371589e22dc2d78e49810b007e0ed13f99b733d0b8b9b827` (sorted compact JSON of manifest `buildProvenance.source_files`). full source/tool/cache/config/asset/overlay/receipt/pixel hashes remain in sealed frame manifests. these are unsigned local stale-build guards, not reproducible-build attestations; external SDK/vcpkg transitive inputs are not fully verified.

native combined dedicated server built successfully (`/tmp/openstarbound-traversal-server-build.log`); no dedicated-server gameplay session claimed. no full-game sanitizer/race detector, other-platform certification, save/network/audio compatibility corpus or performance claim. no pushes/publication/Steam changes/user-save writes.
