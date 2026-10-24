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

float and double run separately within each binary; precise and recorded native
`-ffast-math` policies are compiled/run independently. no cross-policy equivalence
is assumed. both add undefined-behavior and float-to-int sanitizers. logs retain
exact commands, including sdk, target, native defines, and optimization flags.

small cases are constructively bounded: integer/half-grid origins in [-2,2.5],
deltas in [-3,3]; seeded coordinates/deltas in [-16,16]; adjacent representable
grid values, all octants, axes, zero length, ties/near-ties, and f32 endpoint
rounding at 2^24. normal cases compare full ordered callbacks, then abort and both
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
sampled c++ calibration on the local native toolchain, not universal equivalence,
a rust port, game behavior evidence, or supported-platform certification.

## joining a future rust adapter

keep `Reference`, the frozen header/hash, anchors and observation contract fixed.
after abi freeze, replace/extend only `Production::operator()` with the new
adapter and link its already-built archive through this standalone runner. keep
float and double inputs distinguishable; do not widen before scalar endpoint
addition. a c callback trampoline must catch into exception_ptr, return false
immediately, and rethrow the stored exception after rust returns; never unwind
c++ through rust. retain per-index stop/exception tests, reentrancy and all negative
controls. no abi is invented here, and no rust archive is built by this lab.
