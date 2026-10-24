# phase 1 native compression calibration — frozen handoff

parent acceptance is recorded below; this remains lab-only boundary calibration, not a Rust production port.

## verified result

`python3 source/lab/compression/run.py --output build/compression-lab/calibration-03` passed on 2026-10-24 UTC, at local revision `038b6fd9ce10917cf8a3e22e9c566d2425853e85`.

- 3011 ordered cases; 1729 independent output/error anchors, including 660 full-error/partial-output anchors.
- all three controllers and seven returning/ByteArray facades exercised.
- candidate, namespaced complete frozen reference, separately compiled complete original, and repeated candidate streams identical.
- stream sha256: `bcf3f6fe8dd2f31fb896743ca555a37bc56222d18c801713b57d5296216d5582`.
- 12 controls detected: four source/adaptation drift controls; clear order, full-slab limit comparison, partial-output preservation, final-partial limit, paired corruption/independent anchor, verifier-stream corruption, wrong source provenance, wrong stream provenance.
- 1122 source/compiler/SDK/Python/fixture/object/library bindings equal before and after; eight executables hashed; nine actual execution receipts with equal binary hashes before/after. post-run independent hash scan reconfirmed every binding and executable unchanged.
- installed native zlib-ng runtime: `2.3.3`; independent Python zlib runtime: `1.2.12`.

source locations: `run.py:11` freezes originals/adaptation; `run.py:39` generates independent boundary corpus; `run.py:61` raw narrowing probes; `run.py:81` seals dependencies; `run.py:84` compiles complete modules; `run.py:99` checks independent anchors; `run.py:113` starts runtime mutation controls; `run.py:142` checks source/stream identity. `lab.cpp:8` asserts native uint32 fields; `lab.cpp:27` reserves actual ByteArray storage; `lab.cpp:42` captures native binary-safe exception text.

## binding details

original cpp sha256: `4d2390bdafa176ac739dd542f9fb0ad3f12f2820b6c3946a28557e824bda2d78`.

original hpp sha256: `3de6ea0b297dccb2ab1a28d20a3350847a4f30a66994a2c77d717a2e1b90c036`.

installed `libz-ng.a` sha256: `88db95c099486ed9b6b3ada9cc207e12b21cf158a2c3d689a2e30ecd2b9c2c42`.

private native archive sha256 for calibration-03: `bba0001b66024b67dd07eb1eb45abde97b2a4aa03211fa25ee7b563cd00db869` (archive metadata can differ on replay; native object identities and observation stream must not).

complete commands, transitive dependency hashes, native object identities, executable receipts, observations and fixtures are in `build/compression-lab/calibration-03/report.json` and adjacent artifacts. initial runs calibration-01 and calibration-02 passed before coverage/provenance additions; calibration-03 is the frozen current harness. no unsuccessful baseline/control approaches occurred.

## observed semantics and counterevidence

independent literal RFC zlib hello bytes decode to `hello` across all four zlib facades. zero/repeat/deterministic-entropy output sizes 0, 5, 32767, 32768, 32769, 65536, 65537 exercise slab/tail transitions. levels -1 and 0–9 work; invalid -2, 10, 99 produce the exact native initialization error for nonempty input. same-object compression returns empty, including nonempty inputs. nonempty sentinel output clears on empty void input; failed returning calls retain the caller's sentinel.

limit checks occur only after complete 32768-byte appends. independently predicted full-slab prefixes and full native IOException strings match for limits 1, 32767, 32768, 32769, 65536; successful partial tails can exceed limits. checksum failure retains full slabs and discards final partial bytes. dictionary input returns native `inflate_res is 2`. concatenated members and trailing bytes return only the first member. wrong zlib/gzip framing, truncation and malformed input are compared against the frozen native stream. physical input/output bytes and capacities are recorded, not just round trips.

falsification was executed: changing `>=` to `>`, enforcing final-partial limits, discarding retained error prefixes, or moving clear after the alias empty check each compiles and produces a rejected runtime stream. jointly corrupting candidate/reference final append still fails independent producer/literal anchors. no compile error is counted as a detected semantic mutation.

## explicit limits / integration boundary

this is native CPP calibration, NOT a compression Rust port, game runtime test, image producer/consumer test, screenshot, performance measurement, or universal proof. no production CPP/header/CMake/Rust/Cargo/selector/game changes were made. no commits were made. `storage/`, Steam, sealed build objects, reserved host files and `host-prototype/` were untouched.

no actual OOM injection, native End-call trace, cleanup/fault model, or exception_ptr identity observation is provided by this worker. the legacy deflate-error typo is source-frozen, not observed through forced failure. parent owns reserved host prototype and phase 2 runtime controller work.

alias inflate coverage uses actual reserved identical objects, valid compressed inputs and <=32768 output bytes; no capacity-changing/dangling-buffer cases are claimed. synthetic `2^32+k` lengths use only raw void controllers and valid small input buffers; no 4 GiB ByteArray invariant or returning-facade allocation is fabricated.

## next action

## independent parent acceptance and typed boundary

parent `build/compression-lab/cpp-primary-r1` independently passes the same 3011 cases, 1729 anchors and 12 controls, with stream SHA256 `bcf3f6fe8dd2f31fb896743ca555a37bc56222d18c801713b57d5296216d5582`. the existing native reference source/binary seal passes; no shared native/Cargo/game target was rebuilt in this phase.

`host_contract.hpp` freezes sixteen leaf operations for the three controllers. native contexts retain real ByteArray ownership, zero-initialized 32-KiB temps, zng_stream, narrowing and exception_ptr. the status driver owns branches/loops and accesses only the supplied callback and opaque pointer. CLEAR carries kind and checks it before mutation; callback errors are distinct from low32-encoded signed codec statuses. seven allocating/forwarding facades remain outside the future controller. destructor cleanup must not invent codec End on an append exception.

parent found a genuine opacity gap in the worker prototype: the driver special-cased native-host identity and read native context fields. `host-prototype/parent-opaque-negative-r1.log` records the clean `OPAQUE_CONTROLLER` rejection before repair. removed those reads/identity branches; native callback/state guards now enforce their own domain. an actual nested host call tests separate-context success and same-context rejection while the outer invocation survives. the source checker also rejects an isolated known native-layout marker; it is a targeted source guard, not a formal C++ opacity proof.

replay: `python3 source/lab/compression/host_run.py --output build/compression-lab/host-prototype/NEW-NAME`. fresh nested nonsymlink outputs only; source/checker/compiler/object/library/dependency hashes are bound before/after. it runs normal and instrumented references twice, verifies four known failures, and compiles/runs strict C11/C++17 header fixtures. final parent `host-prototype/parent-final-r2/report.json` passes 1050 controller cases / 7510 assertions against the unmodified reference and 1050 / 8598 against the separately identified trace/fault reference. all sixteen opcodes execute. binaries: normal `cc39771415592b9978eb0ade2ccc5dce3472c9f99a7282eb30175470808bad36`; instrumented `cd01f446cf8435a8b84cce9e1a67f9b2c4d279c98026904c33c8b05ee162efb5`.

instrumentation is mechanically source-gated: exact append expressions and actual codec Init/Step/End call sites forward to the real native ByteArray/zlib-ng operations. normal bytes, capacities, full errors and the complete ordered codec-call/append trace agree before interpreting fault cases. native scalar getters are validated by controller/protocol tests; they are not independently traced as C API calls.

- injected full-append sentinel: identical exception_ptr, partial output, and zero controller End calls;
- injected tail-append sentinel: End already happened;
- actual erroneous End-on-append-fault control fails `COMPARISON cleanup End trace`;
- suppressing a Step receipt while still invoking the real codec fails the complete trace comparison;
- a controlled status override calls the real deflater, then returns BUF_ERROR on both paths; this exercises the exact legacy typo/error branch and End order. a compiled native-leaf mutant correcting that typo fails comparison.

the status override is counterfactual, NOT a naturally observed codec failure; the append sentinel is NOT actual OOM. bounded abandoned reference states are reclaimed by process exit, while test-only live-context reclamation occurs after controller trace assertions. persistent prototype contexts do not establish precise temp-deallocation/uncaught-exception timing. no production RAII cleanup fix was introduced. metadata rejection, pending-state rejection, actual reentry, low32 statuses, partial output, aliases and raw narrowing remain finite compiler-bound tests.

catalog 1546 files / 39 modules and eight inventory controls pass. all production C++/headers/CMake/Rust/selectors and the previously qualified native binaries remain unchanged. phase 2 must implement Rust decisions/loops with unchanged native facade/lifetime behavior, then qualify real image embed → decompress → PNG Assets consumption independently of roundtrip agreement. this phase is not that completion claim.

worker is frozen: no further writes/builds. integration owner independently replays to a fresh output directory using README's command, inspects logs and report, and compares the ordered observation hash above. source/compiler/object/codec drift or a semantic/control mismatch invalidates this evidence and must stop integration. parent may then evaluate separately owned host-contract evidence and proceed to phase 2; passing this lab alone does not authorize a Rust completion claim.
