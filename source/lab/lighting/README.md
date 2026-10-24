# cellular lighting differential lab

this executable calls the real public C++ adapter and an independently frozen C++ oracle in one process. it does not construct `Root`, load assets, launch the game, or access saves. `oracle/README.md` records source provenance.

## run

from the repository root, after the parent CMake project integrates this subdirectory:

```sh
cmake -S source -B build/macos-arm-release \
  -DSTAR_USE_RUST_LIGHTING=ON -DSTAR_BUILD_LIGHTING_LAB=ON \
  -DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON
cmake --build build/macos-arm-release --target lighting_lab lighting_lab_fastmath lighting_lab_cpp -j 4
python3 source/lab/lighting/verify_oracle.py
dist/lighting_lab --seed 1592594996 --random 128 --benchmark
dist/lighting_lab_fastmath --seed 1592594996 --random 128 --benchmark
dist/lighting_lab_cpp --seed 1592594996 --random 128 --benchmark
dist/lighting_lab --self-test
# expected exit 1; never treat this as a passing numerical comparison:
dist/lighting_lab --inject-mismatch --random 0
ctest --test-dir build/macos-arm-release/lab/lighting --output-on-failure
```

`--seed` accepts decimal or `0x` hexadecimal; random generation uses explicit mt19937 integer conversion rather than library-dependent floating distributions. a failure reports seed, case, channel, maximum normalized divergence location, full parameters, nonzero initial cells, obstacles and sources. replay with the same seed and at least the same random count. each case calculates twice without resetting; arrays persist across cases to exercise same-size clearing and resizing. initialization deliberately mixes `setLight`, mutable `cell`, and mutable `cellAtIndex` to catch adapter synchronization errors.

`lighting_lab` overrides lighting translation units to `-fno-fast-math -ffp-contract=off`; `lighting_lab_fastmath` uses production `-ffast-math`. existing linked core support objects retain their build configuration, so this is NOT a claim that the entire dependency graph uses precise math. on MSVC the respective flags are `/fp:precise` and `/fp:fast`. Rust library optimization is owned by the parent Cargo configuration. on Apple clang major21 / aarch64 / fast-math, the adapter selects the explicit `star_lighting_calculate_arm_fast` expression policy; other configurations use the unchanged precise entrypoint. an exact-bit route check runs before every lab mode, so a tolerant differential pass cannot hide selection of the wrong entrypoint. this partial production policy is not universal fast-math emulation; current native framebuffer evidence and remaining float differences are in `../behavior/EVIDENCE.md`.

`lighting_lab_cpp` compiles the production C++ fallback with precise lighting math, explicitly undefining `STAR_USE_RUST_LIGHTING` per target (`-U` or `/U`) and omitting the Rust library link. a preprocessor guard rejects accidental macro inheritance. it runs the same full corpus, expected-value assertions, concurrent check, and comparator self-tests; nine CTests cover the three targets. ABI size/alignment/member-offset assertions compile in every target: parameters 28 bytes, cell 16, spread 20, point 36, all aligned to 4 bytes.

## numerical gate

fixed gate: `abs(actual - oracle) <= 1e-5 + 1e-5 * max(abs(actual), abs(oracle))`. nonfinite values fail even under fastmath. no mismatch automatically changes this gate.

float unit roundoff is `2^-24` (about `5.96e-8`); `1e-5` corresponds to about 168 unit roundoffs near magnitude one. a scalar spread hop subtracts once; an RGB hop also divides by its maximum channel and multiplies/subtracts per channel. a point evaluation adds direction normalization, beam arithmetic, and up to one Wu segment per grid coordinate, with roughly 6 arithmetic operations per visited segment. sweep path length grows with dimensions and pass count, not merely source count. the usual `gamma(n) = n*u/(1-n*u)` bound reaches `1e-5` at about 167 dependent operations; generated multihop and obstacle paths can exceed that count. consequently this is an intentionally strict INITIAL screening gate, not a proven forward-error bound for every permitted grid. subtraction cancellation and original fastmath reassociation preclude a blanket relative-error promise. report failures for primary review; do not widen the threshold to force a pass. separate precise/fastmath runs distinguish a numerical policy issue from an indexing/algorithm issue.

## oracle-safe domain and gaps

- grids have width/height at least 3. smaller dimensions can underflow the oracle's reverse sweep indices.
- point-query rectangles are inset by one cell; accepted point sources are inset by two. Wu's original algorithm unconditionally reads both endpoint pixels, including the adjacent pixel when its weight is zero. arbitrary point positions at grid edges are therefore NOT valid oracle comparisons. out-of-grid point sources are tested only where the oracle skips them before line traversal.
- full-grid and clipped-edge coverage uses spread sources without point sources. all outputs, including cells outside the query, are compared because spread expands its working rectangle.
- inputs are finite, nonnegative lighting, positive attenuation distances, finite obstacle boost (including negative), bounded query rectangles. NaN/invalid ABI behavior, huge allocation/overflow, zero-size grids, and unsupported negative intensities require separate direct-ABI tests, not this oracle.
- coverage includes scalar/RGB, spread/point/beam, scalar beam threshold around `0.0001` versus RGB's `0`, center-distance-zero overlap, HDR, additive/max/asSpread, walls, clipping, empty sources/queries, repeated calculations and begin/resizing. seeded generation varies parameters, dimensions, source counts, obstacles and subrectangles.
- nonadditive source order is intentionally observable: A at `(3.5,3.5)` with intensity `0.5` adds at its center despite max mode; B at `(4.5,3.5)` with intensity `1`, air distance `5`, gives `0.8` at cell `(3,3)`. with zero spread passes and no obstacles, A→B must give `0.8`, B→A `1.3`; the second calculation must give `1.3` and `1.8`. scalar and every RGB channel assert these independently for both implementations, not merely against each other.
- four 83x83 fixtures exercise long shallow/steep obstructed rays, fractional and half-coordinate sources, and reverse traversal. two walls (one staggered) cross rays exceeding 70 cells; air/obstacle distances of 128 keep these long paths active. query `[2,81)` and inset sources keep both Wu endpoint pixels allocated. these use the unchanged differential gate, not an analytical ray-intensity claim.
- after serial success, two `std::launch::async` workers rerun the full corpus: one owns scalar adapter/oracle instances, the other RGB instances. only immutable inputs are shared. each compares every output, and combined counts, failures and maximum errors must equal serial statistics. this checks independent-instance concurrency, not simultaneous calls on a single array or a race-detector guarantee.
- `--self-test` perturbs one output by `0.125` and requires the real comparator to detect it. `--inject-mismatch` routes the same perturbation through the normal executable failure exit. CTest marks that known-failure case `WILL_FAIL`; self-test separately verifies that it was an actual comparison rejection.
- benchmark measures calculate only, excluding load and checksum traversal, with two warmups and eleven timed samples per implementation. it reports median microseconds and consumes every output channel in an observable checksum. one fixed 96x80, 48-point/48-spread workload is not representative of every game scene; no speed claim is implied. adapter timings include its marshalling/copy-back cost.
