# actual Rust idmap interop

The native frames now run against the canonical static archive from the existing
`source/rust/ffi/Cargo.toml` aggregate. No second crate/runtime or production
selector was introduced. The production IdMap header is still unchanged.

## evidence

- certificate: `build/id-map-rust-bridge-r1/certificate.json`
- sha256: `9f6b9a534b5cad5c7533ced744767831d587d9a37b1b20f181195c71f373310a`
- acquired report: `5e51c166c0443a7e55ead2cc0f75565e78eb06e63dd57b1945b2a27cf907ef46`
- independent reader: `python3 -B source/lab/id-map-boundary/verify_rust_bridge.py
  --report-sha <report sha>`.

Fifteen accepted command receipts bind the actual selected Rust compiler,
canonical staticlib, exact 113 reference objects plus each designated fixture
object, three executable images and repeated execution. No `mock.o` is linked.
The unchanged baseline/edge streams (44+12 cases, 12+6 properties across both
backends) and five typed-key/NRVO/const traces match the native/model/mock evidence.
Actual Rust counters cover all ten roots and both valid continuations. Native
exception identity, status normalization, output preservation, invalid routes,
null pointers and output alignment controls pass.

The canonical archive has unique physical run/count/Rust-personality providers.
Expanded linker commands, physical member inventories, byte-role map/trace/SDK
reconstruction and a surviving native-to-Rust call edge are retained. Live count
is required in the full API fixture; baseline/edge images may dead-strip it.
Eighteen Python schema/reader/provider tests pass, including spoofed C++ ownership,
duplicate personality, missing required count and mock-controller negatives.
A literal containing “mock” is deliberately not treated as controller code.

## preserved failure / scope

The initial producer failed closed after successful Cargo, C++ compile and
linker expansion: its link input admission omitted `libLTO.dylib`. Before any
native executable link, a new link-only admission bound the real current
libLTO/libtapi bytes against the prior frame admission. No copied tool, resolver,
waiver, changed deadline, repeated successful native leaf or relabeled producer
was used. The certificate binds the original failed logs as well as continuation
products. Read-only independent source/artifact review found no actionable defect.

This is finite native/Rust interop and **provider declarations**, not complete
surviving machine-code/data-target provenance, production adoption, gameplay,
universal integer-domain equivalence or full migration completion. Signed
bounds overflow and full-small-integer nonprogress remain unexecuted diagnostics.
Next: retain source epochs, then default-OFF production integration and its
consumer/application gates. Module-completion cleanup remains mandatory; current
outputs are retained proof, not obsolete pruning candidates.
