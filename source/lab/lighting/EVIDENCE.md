# executed evidence

status: verified within the native macOS numerical-port scope. this is not proof of whole-game or universal bitwise equivalence.

## tested source and artifacts

base revision: `f5c4da285ba4bbb8eaf21211b8ff9d27654fed55`, plus the uncommitted port in this checkout. verification ran on Apple M2 Pro / arm64 macOS, Xcode clang 21.0.0, macOS 27 SDK, Rust/Cargo 1.97.1, CMake 3.31.6 and Ninja 1.12.1. precompiled headers disabled; native production C++ release flags include `-O3 -ffast-math`. Rust release uses its normal optimized floating-point semantics, not fast-math.

`EVIDENCE.sources.sha256` identifies the 16 code/build/test inputs, excluding documentation and generated artifacts. from the repository root:

```sh
shasum -a 256 -c "source/lab/lighting/EVIDENCE.sources.sha256"
```

combined snapshot SHA256: `f2df8e49f3682f1807e2ad4517aa561d922560f13525b11a6c7f84d27874b60b` (lexically sorted relative path, NUL, file bytes, NUL, for each manifest entry).

local tested artifact SHA256 (not a promise of reproducible hashes on other toolchains):

```text
9b67f0b11a46161e0653d77f0fde76b9c57a8a7283b83961fd4eadb8af3d5a06  dist/starbound
9fb812215450e02942279b64492e4e24e95ec460f8b6dc09fb64e7b9dd39a981  dist/starbound_server
b6b340320e358eea0347b362df1aeb8be4fdcd30073893fada839c058700b5f9  dist/lighting_lab
303036c6b74059bb3981d2d0e86472237bca8a8c7026274f9bca26444062b773  dist/lighting_lab_fastmath
e943c437b4c7e2327db03aec7702667ab4bdd0918aab17a1d0a9e3d6b4d64a93  dist/lighting_lab_cpp
49c472fdb06311002336ad4557308383dc0122945b7a9985903d4a922fe1d46d  build/macos-arm-release/rust-lighting/aarch64-apple-darwin/release/libstar_lighting.a
```

## verified: laboratory and numeric compatibility

executed the final `scripts/lighting-lab.sh` end-to-end using nix-shell build tools. log: `/tmp/openstarbound-rust-lighting-acceptance.log` on this host.

- 12 Rust unit tests passed in debug; the same 12 passed in release; formatting passed.
- all nine CTests passed: three implementations, each with differential, comparator self-test and expected-failure checks.
- `verify_oracle.py --self-test` verified the namespace-only oracle adaptation and rejected a deliberate max-to-min algorithm mutation. also passed under `python3 -O`; the gate does not depend on removable Python assertions.
- separately ran `lighting_lab --inject-mismatch --random 0`: actual output contained `MISMATCH`, with exit **1**, not merely an arbitrary nonzero exit.
- final extended corpus ran all three modes with seeds `1592594996`, `1`, `4294967295`, each with `--random 4096`: 4,121 scenario runs per seed, including 25 deterministic fixtures.
- each mode compared **44,122,768 channels** serially across those seeds, with no failures. scalar/RGB independent instances replayed the same corpus concurrently, compared another 44,122,768 channels, and matched serial error statistics.
- precise Rust versus precise oracle: maximum absolute difference **0** on this corpus.
- C++ fallback versus precise oracle: maximum absolute difference **0**.
- Rust adapter versus production fast-math oracle: maximum absolute difference **1.00136e-5**; maximum acceptance-budget fraction **0.216513**.

fixed, unchanged acceptance gate per channel:

```text
abs(actual - oracle) <= 1e-5 + 1e-5 * max(abs(actual), abs(oracle))
```

unexpected nonfinite outputs fail. the relative term explains why a difference slightly above `1e-5` can pass. the threshold was set before differential runs and never widened. it accommodates compiler arithmetic differences; it does not establish exact production floating-point compatibility.

coverage includes both scalar/RGB variants, every numerical stage, obstacles, additive/max/hybrid modes, distinct beam thresholds, HDR colors, negative obstacle boosts, clipped sources, query rectangles, all-cell outputs, repeated calculate, begin/reset/resizing, unconditional center addition, source-order expected values, and long shallow/steep obstructed rays. see `README.md` for the oracle-safe domain.

additional seeds were executed as:

```sh
for mode in lighting_lab lighting_lab_fastmath lighting_lab_cpp; do
  for seed in 1 4294967295; do
    "./dist/$mode" --seed "$seed" --random 4096
  done
done
```

## verified: integration and fallback

- built native ARM `starbound` and `starbound_server` with `STAR_USE_RUST_LIGHTING=ON`.
- production `StarCellularLighting.cpp.o` references `_star_lighting_calculate`; the client contains that Rust symbol. the C++ facade routes calculations to the Rust archive.
- `lighting_lab_cpp` compiled with the Rust macro explicitly undefined, with a compile-time guard against accidental Rust selection. it linked, passed the full corpus, and contains no `_star_lighting_calculate` symbol.
- isolated C11 consumer linked and invoked the Rust archive successfully; ABI sizes checked in C and sizes/offsets/alignment checked in C++ and Rust tests.
- `scripts/lighting-cmake-check.sh` passed: a conflicting inherited `CARGO_BUILD_TARGET` did not redirect the explicit native target; unsupported universal architectures failed configuration with the expected diagnostic. these fixtures build under ignored `build/` directories.
- both native executables' `-version` commands passed.

runtime startup smoke: the Rust-linked client started with isolated configuration and storage under `build/rust-lighting-smoke/`, loaded the real assets, created its OpenGL context, entered the main update loop, loaded all databases and logged a title world. log: `/tmp/openstarbound-rust-lighting-smoke.log`. this was **not an in-world gameplay/visual-parity test**. the temporary process was stopped with SIGTERM after it ignored SIGINT; no user saves were used.

## verified: stopwatch, not a speed claim

benchmark input: 96×80 cells, 48 spread and 48 point sources, randomized obstacles; seed `1592594996` after 4,096 generated cases. 13 calls per backend, first two discarded, median of 11; calculation timing includes the C++ adapter's packing and unpacking, but excludes fixture loading. output checksums are consumed outside the timed interval.

last full-run medians in microseconds:

- precise mode: Rust adapter scalar **255.709**, oracle scalar **209.042**; Rust adapter RGB **455.333**, oracle RGB **473.042**.
- production fast-math mode: Rust adapter scalar **230.042**, oracle scalar **176.041**; Rust adapter RGB **469.916**, oracle RGB **418.875**.

timings varied between runs. no optimization win or whole-game FPS improvement is claimed. the adapter's extra full-grid conversion and validation are explicit future optimization targets, not diagnosed explanations for every measured difference.

## boundaries and unverified claims

- native Apple silicon only. Linux, Windows, universal binaries and cross-compilation were not built/tested; unsupported cross/universal Rust builds fail early, and the C++ backend remains the default.
- no sanitizer/race-detector run; the concurrent check is ordinary execution, not proof of race freedom.
- no full gameplay replay, image inspection, save compatibility corpus, multiplayer parity or FPS benchmark.
- the original oracle has undefined accesses for some tiny grids/point-edge cases. those are excluded from equivalence runs; Rust's safe handling is separately unit-tested, not claimed equivalent to undefined C++ behavior.
- positive finite attenuation distances and allocated valid foreign buffers are required. pointer checks cannot prove allocation provenance. finite extreme inputs may still overflow floating-point outputs.
- panic containment is traced and release uses unwinding; the FFI status-2 panic branch was not deliberately runtime-triggered.
- no commits, publishing or Steam-install modifications. user `storage/` was pre-existing and preserved.
