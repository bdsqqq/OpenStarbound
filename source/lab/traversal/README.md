# traversal calibration lab

```sh
python3 source/lab/traversal/run.py
```

all generated headers, binaries, compiler commands, logs and `report.json` stay in
`build/traversal-lab/`. requires the existing native compile database at
`build/behavior/reference/cmake/compile_commands.json` and its cached includes/sdk;
never configures cmake or builds shared dependencies. python standard library only.

## why this oracle is frozen

`StarBlocksAlongLine.frozen.hpp` is the exact original header from
`f5c4da28:source/base/StarBlocksAlongLine.hpp`, sha256
`c917ceeeba883c8c267b03861e0b171d0c7c3f2098b9cc419e6e463ea006d077`.
there is no golden-regeneration command. each run checks both that fixed hash and
the historical git bytes. only the generated namespace declaration changes to
`TraversalReference`, with `using namespace Star;` inside it. the include,
algorithm, `Vector`, `function`, and `floor` are untouched: these resolve to real
production core headers, not lab substitutes. the normal candidate directly
includes the real production traversal header.

provenance checks reject an isolated corrupted algorithm and an unauthorized
adaptation. runtime negative builds separately omit the tie decrement, ignore
callback abort, and swallow exceptions. each must fail through a comparison
assertion, not a crash or sanitizer diagnostic. ordered-cell anchors additionally
check corner side-cell omission, negative floor, and f32 endpoint rounding.

## scope and defined domain

float and double run separately within each binary; uncontracted precise,
default non-fast contraction, and recorded native `-ffast-math` policies are
compiled/run independently. no cross-policy equivalence is assumed. all add
undefined-behavior and float-to-int sanitizers. logs retain
exact commands, including sdk, target, native defines, and optimization flags.

small cases are constructively bounded: integer/half-grid origins in [-2,2.5],
deltas in [-3,3]; seeded binary-grid and non-binary-fraction coordinates/deltas
near [-16.3,16.3]; adjacent representable grid values, all octants, axes, zero
length, ties/near-ties, f32 endpoint rounding at 2^24, and decimal corner endpoints
constructed in Scalar (including origins 0.1 and 0.3). normal cases compare full ordered callbacks, then abort and both
exception types at EVERY index (including last), plus nested traversal effects.
exception_ptr equality checks propagation of the same exception object, not only
its type/payload. callback effects are recorded before stop/throw.

wide axis cases span four billion cells but only execute three-callback prefixes;
the nonaxis long case has setup count 2,000,000,001, within int. int boundary
prefixes abort/throw before dangerous post-last-cell increments. there is no
blanket coordinate/count cap that would reject defined early-abort prefixes.
these wide cases intentionally do not run the full suffix.

`report.json` labels concrete nonfinite, finite-out-of-int-range, setup-overflow,
and post-loop-overflow examples as EXCLUDED, not compatibility passes. this is
sampled calibration/differential evidence on the local native toolchain, not
universal equivalence, game behavior evidence, or supported-platform certification.

## rust adapter

```sh
CARGO_TARGET_DIR=build/traversal-rust cargo build --manifest-path source/rust/Cargo.toml --package star-engine-ffi --release --locked --offline
python3 source/lab/traversal/run.py --rust-archive build/traversal-rust/release/libstar_engine_ffi.a --output-dir build/traversal-lab/rust
python3 source/lab/traversal/run.py --output-dir build/traversal-lab/cpp
python3 source/lab/traversal/check_cmake.py
```

`--rust-archive` links the existing aggregate and defines
`STAR_USE_RUST_BLOCKS_ALONG_LINE`; the runner does not build archives or shared
project dependencies. `Reference`, frozen bytes/hash, anchors, observation
contract and all negatives remain fixed. Rust additionally exercises the actual
C callback boundary, status validation, per-thread completion/stop receipts,
concurrent contexts, reentrant calls, and unsupported-Scalar C++ fallback.

The frozen ABI is `source/base/StarRustTraversal.h`: typed
`star_blocks_along_line_f32`, `star_blocks_along_line_f64`, and
`star_blocks_along_line_call_count`. Visitor `(void*, int32_t, int32_t)` is
synchronous and must not unwind; zero stops, nonzero continues. Status 0 completes,
1 stops, 2 rejects input/policy, 3 contains a Rust panic. Scalar endpoint addition
precedes promotion; no eager collection or retained pointers. The C++ thunk
catches ALL exceptions, returns stop, then rethrows the saved `exception_ptr`
after Rust returns. Receipts count completed/stopped calls on the executing
thread, including exceptions translated into stop; invalid/panic calls do not
count. Receipt counters must not select simulation behavior.

Policy 0 is explicitly uncontracted precise (`-ffp-contract=off`, paired with
`STAR_RUST_TRAVERSAL_FP_PRECISE`). Policy 2 models Apple clang 21 ARM's default
non-fast contraction: fused initial multiply-subtract, no reassociation. The
adapter selects 2 on that toolchain without fast math. Nonstandard contraction
flags require explicit matching policy; they are not auto-detected.
Policy 1 follows the recorded Apple clang 21 ARM
`-O3 -ffast-math` assembly: `(1-origin)+floor` positive boundary distances,
contracted multiply-subtract initial error, and hoisted `(dy-dx)` tie update.
Decimal corners exposed a mismatch when only contraction was modeled. Rust
itself is NOT compiled with fast math. The adapter selects policy 1 only for
Apple clang 21/aarch64 with `__FAST_MATH__`; other fast-math compilers are
explicitly rejected, not silently assigned an uncalibrated policy. Other native
platforms/precise compilers remain unverified. Cross/universal/unsupported
architecture builds are rejected by the shared Rust CMake module.

`STAR_USE_RUST_BLOCKS_ALONG_LINE` defaults OFF, independently of lighting. Either
backend selects the one aggregate; geometry alone does not select the lighting
macro/shim. The configure-only probe evaluates the actual selection block in
all four combinations and checks cross/multi/unsupported-architecture rejection;
it does not claim a full native build. Both OFF does not discover Cargo.

Input checks reject nonfinite values, out-of-int floors and overflowing diagonal
setup before callbacks. Defined four-billion-cell axis early-abort prefixes and
INT_MIN zero-length abort remain accepted. Safe post-loop/axis termination extends
some original undefined suffixes; those are NOT C++ compatibility evidence.
Internal panic containment is tested inside Rust, never by panicking an extern-C
callback (which would abort rather than unwind safely). Native gameplay adoption
and native-client rebuilds remain separate work.
