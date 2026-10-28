# native idmap frames — finite C++ policy-double gate

The wrapper keeps the original base, public declarations and three fields.
Per-method trivial inline closures avoid imposing unused mapped-copy or stream
constraints. Fullness finishes before the original typed local is copied;
cursor scanning and insertion retain named locals and native full expressions.
Native exceptions are captured by a noexcept callback and rethrown after policy
return. Phase and completion checks reject out-of-order or skipped expressions.

## evidence

`build/id-map-boundary-r1/report.json`, sha256
`3cec725688d0326431084014c4619a2c0ca9bb64ec92a13108b46899a1f96d0a`.
Replay with `verify_frames.py --report-sha <sha>`; eight boundary Python tests pass.

- unchanged baseline/edge fixtures and literal models passed twice: 44+12 cases,
  12+6 properties across ordered/hash backends.
- five typed-key/fullness/copy/NRVO/const traces match the frozen original.
- isolated real-frame probes: 842 denied requests, 44 pending-exception barriers,
  all ten roots, 36 malformed-envelope checks; completion, null callback and
  exception identity controls passed twice.
- three expected deleted-copy compilation failures retain lazy constraints.
- exact 113 reference objects, optimized native flags, SDK before/after and
  byte-role linker-map interface reconciliation retained.

Two original procedures remain failed. The first exposed C++ base-alias hiding
of same-named template parameters; its source epoch was copied before repairing
closure parameter names. The second used an unjustified minimum of 1000 probes.
It is untouched: `probe.cpp` instead checks each request and structural count
conservation. No threshold was lowered or model/domain/flags fitted. The five
trace records preceding that failure are explicitly partial evidence, not whole
procedure acceptance. Composition has 28 accepted commands and two retained
failed commands. Read-only independent review found no actionable defects.

## next

This is a **C++ policy double**, not actual Rust interop, a canonical Rust archive
provider, production adoption, gameplay or module completion. Production IdMap,
ABI and Rust policy stayed unchanged. Next gate links the same aggregate's actual
Rust provider and repeats native corpora, typed traces and provider checks before
any production selector. Signed/default-bound overflow and full-small-integer
nonprogress remain unexecuted diagnostics. Keep current outputs as proof; module
completion cleanup remains mandatory. No game generation was added.
