# frozen vlq evidence

verified on apple silicon macos, parent checkout `dfc36000b3f8877f7a3629ab4110e7fa18b697fd` plus the concurrently owned vlq production adapter. lab source is frozen at this handoff; no commits or production changes by this worker.

## replay and results

```sh
python3 source/lab/vlq/run.py --output build/vlq-lab/cpp-frozen
python3 source/lab/vlq/run.py --define STAR_USE_RUST_VLQ --archive build/vlq-rust/target/release/libstar_engine_ffi.a --output build/vlq-lab/rust-frozen
```

- cpp: **94,987 cases, 701,988 checks**, 16 negative controls.
- rust-linked: **94,988 cases, 702,017 checks**, 17 negative controls.
- rust receipts, ordered write-u / size-u / read-u / write-i / size-i / read-i: `[80440,75730,80494,80336,75730,80388]`.
- each baseline passed twice with identical stdout before any negative was counted. every behavioral negative exited 1 with `COMPARISON`; no crash or compile failure counted as detection.
- scoped direct abi tests verify single public-op receipts, controlled callback-abort/exhaustion receipts and invalid-input nonreceipts. signed internal helpers must not double-count the signed public operation.
- standalone xcode clang command/SDK/vcpkg flags come from the existing reference `StarDataStream.cpp` compile-command entry; c++17, production optimization flags plus undefined-behavior sanitizer. no shared cmake/cargo/ninja writes.

full commands, per-input hashes, negative names, binary hashes and counts: `build/vlq-lab/{cpp-frozen,rust-frozen}/report.json`; before/after maps must match. earlier output directories are historical, not final evidence.

## provenance

- frozen complete original header from git `dfc36000`: `0f4cd849bf4931f1dbb8cabf02dc62083e11b48cc4b0595ec1d8ea39534159b8`.
- adapted full header: `3baea13e60d43aed47f8a68a77c695641d51d9394c7cb310ff4f588bda74b570`. only namespace replacement plus `using namespace Star`; all six bodies byte-preserved. no formula or expected-data regeneration.
- worker-tested active header (historical, superseded below): `84e65cdf37316e7fb679f451a2cb3b2d8cfbae0e854efb7196c668546d945498`.
- tested abi header: `1acd4b67f3368d32876dab2806a6430599f1f5f0b30a3ed5ee4af751e05b04e4`.
- tested rust archive: `136f4f17720a05c4576313a9e08ba3576400948200e309420adc2903b0481041`.
- final cpp executable: `fc895e2f0c3f2469450aabf4db61d38431e86bd5b0c0689dda7136576e0cd0d0`.
- final rust executable: `ad646beffbb4ca422fbe7500210790bee5956ee28d5efd4550dd0bea7a47223e`.

compiler `-MM` discovers actual local transitive includes before testing. six underlying core headers (`StarAlgorithm`, `StarMemory`, `StarConfig`, `StarException`, `StarPch`, `StarOutputProxy`) must also match their git `dfc36000` bytes. these are real primitives, not substitute mocks. source/checker/active-header/abi/archive/dependencies are rebound before and after. system SDK/compiler binaries are not recursively hashed: this is host-specific evidence, not a hermetic toolchain qualification.

## contract exercised

`lab.cpp` uses independent division/remainder byte construction, independent unsigned zigzag arithmetic and literal unsigned/signed/extreme anchors. values include 0..32767 and their complements, each power-of-two boundary +/-1 through bit63, and 10,000 deterministic mt19937_64 values. both sizes, both writers and both readers compare exact bytes/counts/results; counts span 1..10. raw pointer positions remain unchanged by value.

ordered generic-iterator traces compare root copies, postfix copies, dereferences, conversion and continuation `int` versus final `uint8_t` assignment. 48 injected event failure positions per state compare same `exception_ptr` identity, output/prefix destination, iterator position, attempts and completions. copy constructors can mutate the unsigned destination or throw; callbacks observe/mutate unsigned and signed destinations. nested same-thread writer reentrancy is exercised during a mutating read. actual `StarAlgorithm.hpp` FunctionInputIterator and FunctionOutputIterator run unsigned traces; signed forwarding/copy behavior uses the custom global iterator to avoid introducing ADL-driven changes to the frozen bodies.

malformed cases cover overlong encodings, unsigned overflow wrapping, tenth high payload, no terminator, early eof, max 0/1/2/9/10/11/host NPos, signed success-only assignment, unsigned prefix updates and hard 10-byte read bound leaving byte11 untouched. raw malformed inputs are padded to safe length; short stream inputs throw rather than reading outside memory. literal checks additionally assert `8000 -> 0/2`, `82 + 8*80 + 00 -> 0/10`, `81 max1 -> NPos/prefix1`, eof identity/prefix1, and zero-max behavior.

abi probes cover legitimate null contexts, read/write callback abort, status4 exhausted, status2 invalid with unchanged count/no receipt, signed/unsigned max0 behavior, and a callback overwriting the unsigned destination (result must use its new value, not a cached accumulator).

## falsification

source corruption, unauthorized adaptation, arbitrary defines, unpaired archive, and outside-output arguments are rejected. isolated genuine candidate-header algorithm mutants change group order, zigzag and overflow rejection; each fails a numeric/byte comparison. additional observation mutants corrupt group order, zigzag, overflow result, greedy-read result, unsigned failure commit, swallowed/replaced exception, copy events, and rust receipt. these latter controls test the comparison mechanisms; they are not claims that a separate broken rust implementation was compiled. the reference header is never mutated.

one initial compile failed due to ADL ambiguity when passing a Star-namespaced iterator through the independent signed wrapper. changed only that actual FunctionOutputIterator case to unsigned; signed custom-iterator coverage retained. no algorithm repair or oracle adjustment. final executions above passed.

## limits and boundaries

finite generic-iterator fixtures, not all possible user iterator implementations or allocator faults. callback aliasing is exercised through observed/mutated destinations, not arbitrary fabricated overlapping typed buffers. no real DataStream/VersionedJson/packet/BTree or gameplay claim here: parent owns those gates. fixed-width Assets sizes are not vlq; release local sockets can bypass serialization. no screenshot, security, platform-portability, performance or whole-module claim.

## parent integration and forwarding repair

VERIFIED — final `build/vlq-lab/{cpp-final-r2,rust-final-r2}/report.json`: unchanged numerical counts and receipts above; C++ 16 negative controls, Rust **19**. Final active header SHA256 `52f1b5e09ca4b90bbe10888d6c8bcccf52b454d5ba22cbadde4dbb48d96c05fb`. Frozen original/adaptation and Rust archive remain unchanged. `run.py` now also compiles/runs `forwarding_regression.cpp`, binding it in before/after input maps.

Read-only `vlq-abi-contract-review-r1` found two real C++ signed-wrapper defects that the original iterator fixtures missed: direct-initialization selected explicit copy overloads, and the forwarding copy was destroyed after signed assignment. Parent reproduced BOTH against the old adapter: exit1 `COMPARISON forwarding-copy-initialization`, and `COMPARISON forwarding-destructor ref=-65 actual=99`. The owned native build was stopped before repair. Signed wrappers now copy-initialize; signed reads decode into a private temporary, destroy the forwarding copy, then assign the public destination. Throwing destructors therefore also precede assignment. Rust algorithms were not changed.

Focused regressions cover explicit mutable-copy versus const-copy overload selection for signed read/write, forwarding-only destructor mutation, and a throwing forwarding destructor. All pass after repair. The ordinary runner compiles isolated real candidate-header regressions for each defect, requiring exit1 plus `COMPARISON`; compile failure/crash does NOT count. These are the two new negative controls, not adjustments to the reference or byte anchors. This was one bounded repair, not a restarted approach.

Parent independently ran 34 Rust workspace tests in EACH debug/release, fmt, 68 behavior/provenance/proof tests and eight inventory drift controls. Native integration is recorded in `../behavior/EVIDENCE.md`. Native, oracle and source receipts apply only to this host/revision; not arbitrary iterators, protocol interoperability, existing saves or whole-game equivalence.

only new `source/lab/vlq/**` and outputs `build/vlq-lab/**` retained by the worker. an initial temporary snapshot was immediately moved from `build/vlq-snapshot-tmp` into the owned source directory; nothing remains there. no native build/game, nested implementation, staging, commit, remote action or user storage writes.
