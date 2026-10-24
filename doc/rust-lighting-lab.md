# rust cellular-lighting migration laboratory

## outcome

**complete within the native macOS numerical-port scope.** the full scalar and RGB `CellularLightArray` calculation kernel now has a Rust implementation, used by the locally built client and server behind their existing C++ interface. the default build remains C++ until other platforms are validated.

ported: spread-source placement, in-place directional propagation, point/beam lighting, proportional color attenuation, obstacle line tracing, additive/max/hybrid modes, and their legacy ordering/threshold quirks. C++ retains the public cell storage and adapter, higher-level JSON configuration, output pixel packing, world threading and graphics. this is not a rewrite of those surrounding systems.

no commits, publication, Steam changes or user-save modifications.

## completed plan

1. [complete] freeze a C ABI and the original C++ oracle; assign disjoint ownership.
2. [complete] implement the entire numerical module in Rust and retain the C++ facade/fallback.
3. [complete] build deterministic/randomized differential tests, negative controls and benchmarks.
4. [complete] integrate Cargo/CMake; build the real native client and server with Rust selected.
5. [complete] independently review, resolve findings, verify final artifacts and record limits.

## evidence

[`source/lab/lighting/EVIDENCE.md`](../source/lab/lighting/EVIDENCE.md) binds the results to source and artifact hashes, gives executed commands, and distinguishes numerical, build and startup evidence.

- 12 Rust tests passed in debug and release; nine native CTests passed.
- 44,122,768 channel comparisons per mode over three seeds passed, plus concurrent replay. precise Rust and C++ fallback matched their precise oracle exactly on this corpus. production fast-math differences passed the unchanged absolute-plus-relative `1e-5` gate.
- deliberate numeric output corruption and deliberate oracle algorithm mutation were both detected.
- actual native client/server link Rust; isolated client startup reached the title-world initialization using separate smoke storage. gameplay/visual parity remains untested.
- measured timings do not establish a speedup; performance is not the success criterion for this first slice.

## run the laboratory

from the repository root, with `cmake`, `ninja`, `python3`, Cargo and Rust available:

```sh
bash "scripts/lighting-lab.sh"
```

it verifies oracle provenance, runs Rust debug/release tests and formatting, builds all three native lab modes, runs CTest, executes a 4,096-random-case corpus with benchmarks, and tests the Cargo/CMake boundary in isolation. no game assets or saves are required for the numerical laboratory.

for this host, build tools can be supplied without global installation:

```sh
nix-shell -E 'let pkgs = import <nixpkgs> {}; in pkgs.mkShellNoCC { packages = with pkgs; [ cmake ninja pkg-config git curl zip unzip python3 ]; }' --run 'export PATH="/usr/bin:/bin:$PATH"; unset SDKROOT DEVELOPER_DIR; bash "scripts/lighting-lab.sh"'
```

Cargo/Rust are already on this host's PATH. compiler/tool versions and all evidence limitations are in the lab evidence file.

## configure or rebuild

this checkout already has the dependencies and configured native build. from `source/`:

```sh
export VCPKG_ROOT="$HOME/.cache/openstarbound-vcpkg"
unset SDKROOT DEVELOPER_DIR
export SDKROOT="$(/usr/bin/xcrun --sdk macosx --show-sdk-path)"
cmake --preset macos-arm-release \
  -DBUILD_TESTING=OFF \
  -DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON \
  -DCMAKE_VERBOSE_MAKEFILE=OFF \
  -DCMAKE_OSX_SYSROOT="$SDKROOT" \
  -DSTAR_USE_RUST_LIGHTING=ON \
  -DSTAR_BUILD_LIGHTING_LAB=ON
cmake --build --preset macos-arm-release --parallel 8 \
  --target starbound starbound_server lighting_lab lighting_lab_fastmath lighting_lab_cpp
```

precompiled headers are disabled because the existing ARM color source uses floating-point flags incompatible with the shared header. nix-shell's SDK setting is cleared before selecting the actual Xcode SDK.

native Rust cross/universal builds are explicitly rejected rather than linking the wrong architecture. fallback configuration is `STAR_USE_RUST_LIGHTING=OFF` and `STAR_BUILD_LIGHTING_LAB=OFF`; the default build does not require Cargo. the lab separately proves the complete C++ module fallback compiles, links and matches the frozen oracle.

## implementation boundaries

- `source/rust/lighting/`: dependency-free Rust crate, C ABI validation, all numerical stages and Rust unit tests.
- `source/base/StarRustLighting.h`: borrowed, explicit-layout batch ABI; no retained foreign pointers or cross-language allocation ownership.
- `source/base/StarCellularLightArray.hpp` / `.cpp`: original public C++ interface, per-instance reusable conversion buffers and guarded original fallback.
- `cmake/RustLighting.cmake`: offline locked Cargo build, explicit native target/archive path, consistent C++ template definition.
- `source/lab/lighting/`: namespace-isolated frozen oracle, differential/negative/concurrent tests, benchmarks and evidence.
- `scripts/lighting-lab.sh`, `scripts/lighting-cmake-check.sh`: repeatable verification entry points.

## review decisions and limits

independent agents owned the Rust implementation, C++ adapter, oracle/lab, original-contract audit and integration/numerical reviews. the primary independently ran the combined checks and resolved integration findings. later lab work added source-order assertions, oblique rays, ABI offsets, concurrent replay and fallback selection proof.

resolved findings: inherited Cargo target could change the archive location; universal architecture lists could bypass native checks. both now have executed build-boundary regression probes. primary also removed an unjustified negative-obstacle-boost restriction and added its differential fixture, and made oracle provenance verification work even under Python optimization.

original tiny-grid/point-edge undefined behavior is not a compatibility target. positive finite attenuation distances and valid borrowed buffers are required; safety extensions are distinguished from equivalence evidence. no sanitizer, non-macOS build, in-world visual comparison, multiplayer replay or universal bitwise-equivalence claim.

all delegated tasks are terminal. working tree is review-ready; no manual unblock or approval is pending. next useful work is profiling the batch conversion/validation cost and broadening platform/gameplay evidence before changing the default backend.
