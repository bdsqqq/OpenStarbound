# compression calibration laboratory

phase 1 compares native c++ only. it does not enable a rust selector, rebuild the game, invoke cargo, or call `CompressedFile` methods.

```sh
python3 source/lab/compression/run.py --output build/compression-lab/parent-replay-01
```

output must be fresh and nested under `build/compression-lab/`, with no symlinks in its path. the reserved `host-prototype/` directory belongs to the integration owner; do not use it for this runner.

the runner checks complete original source/header snapshots against commit `038b6fd9`. reference adaptation changes only the namespace, its `using namespace Star` import, and the cpp's header include. production must remain byte-identical during phase 1. all class definitions, including excluded `CompressedFile`, remain in the complete snapshots; no file methods are executed.

it uses the sealed native compiler recipe and existing core/extern objects under `build/behavior/reference/cmake`. a private archive excludes `StarCompression.cpp.o`; it is never written back to the sealed build. candidate, namespaced reference, and separately compiled complete original produce identical ordered streams. Python's independent zlib/gzip producers check payloads, limits, errors, and native compression's decoded contents; they do not impose Python-version compressed-byte goldens.

## artifacts

- `cases.tsv`: ordered id, mode (0 deflate / 1 zlib inflate / 2 gzip inflate), facade, level, alias flag, scalar input length, limit, input hex.
- `anchors.json`: independent successful-output and full-error/partial-output anchors.
- `observations.tsv`: id, error hex (`printException(false)`), final destination hex, final input hex, destination capacity, input pointer unchanged flag. fields are tab-separated; empty byte fields are significant.
- `before.json`, `after.json`: hashes of sources, transitive SDK/native headers, compiler, Python producer implementation/runtime, native objects and link libraries, fixtures, and sealed build recipes.
- `report.json`: bindings, executable hashes, before/after runtime receipts, generated mutation source receipts, commands, ordered stream hash, codec versions, explicit limits.
- individual compile/run logs contain complete ordered streams, including the separate original/reference and negative controls.

facades: deflate 0 = output reference, 1 = returning. inflate 0 = raw pointer/output reference, 1 = raw pointer/returning, 2 = ByteArray/output reference, 3 = ByteArray/returning. all ten public overloads before `CompressedFile` are exercised.

## domains deliberately kept separate

same-object deflate clears the input before the empty check and returns empty. inflate alias probes use physically identical input/output objects with 262144 bytes reserved and output at most one slab; compressed input is consumed before the slab is appended, and the input pointer must stay stable. malformed alias cases and capacity-changing aliases are excluded rather than treated as defined behavior.

synthetic `2^32+k` lengths apply only to raw-pointer void zlib/gzip controllers, backed by actual small valid buffers. only the effective `uint32_t` input extent may be accessed. no fake ByteArray size, 4 GiB input allocation, or returning-facade reserve probe is used. `avail_in` and `avail_out` native types are compile-time asserted.

limit exceptions retain full slabs already appended. returning overload failures leave the caller's destination sentinel unchanged because assignment never executes. final partial slabs are not limit checked; error paths discard only a final partial slab. each fact has independent error/output anchors, not merely round trips.

## controls and limits

runtime controls change clear order, full-slab `>=`, partial-output preservation, and final-partial limit behavior. paired candidate/reference corruption still fails independent literal/producer anchors. fixture-stream and source/stream provenance controls must fail. compilation failures never count as successful controls.

no actual allocation failure, stream lifetime tracing, resource-exhaustion equivalence, rust execution, image/game behavior, or universal equivalence is claimed. the legacy deflate error typo is preserved by complete source freezing but is not forced to occur here. host fault/leaf-trace work is separately owned.
