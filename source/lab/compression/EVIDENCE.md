# compression controllers — calibration and Rust acceptance

phase 1 below is the historical lab-only record. the production-controller extension and parent acceptance follow it; only three controllers migrate, not `CompressedFile` or vendor zlib-ng.

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

## production controller oracle extension — 2026-10-24 16:18 UTC

VERIFIED: `cpp-controller-worker-final/report.json`, `rust-controller-worker-final/report.json`, and `rust-host-worker-final/report.json` under `build/compression-lab/` all pass. These are laboratory executable observations, NOT game or screenshot acceptance.

- `run.py --backend cpp|rust --output build/compression-lab/NEW-NAME` preserves the complete 3011-case corpus, 1729 independent anchors and twelve original controls. Both streams retain SHA256 `bcf3f6fe8dd2f31fb896743ca555a37bc56222d18c801713b57d5296216d5582`. The Rust candidate compiles actual selected production `StarCompression.cpp` and its native host header, linking canonical `build/compression-rust/target/release/libstar_engine_ffi.a`; native archive excludes the old compression object.
- Full OFF reconstruction removes exactly one guarded include block and selects all three complete original bodies, then compares the WHOLE translation unit byte-for-byte. The public header, seven facades and all CompressedFile source remain byte-exact under this gate.
- Every Rust case checks all nine TLS entry/success/native-exception deltas. Five additional clean runtime controls reject selected-host clear removal, changed exception class, invalid host status, wrong controller dispatch and suppressed TLS receipts. Compilation failures never count as semantic controls. Rust has seventeen controls total.
- `candidate_host_run.py --output build/compression-lab/NEW-NAME` copies frozen host native leaves and test source into owned output; the ENTIRE phase1 C++ driver is removed and its adapter calls actual `star_compression_run`. Frozen files remain untouched. Actual Rust replay passes 1050 cases / 7510 ordinary assertions and 1050 / 8598 instrumented assertions, with all sixteen opcodes and unchanged codec Init/Step/End/Append trace, exception_ptr, partial output and full/tail append-fault comparisons.
- Five host controls detect an intentionally wrong raw ABI expectation, native-layout marker, erroneous append-failure End, missing Step receipt and corrected legacy deflate typo. `candidate_abi.cpp` additionally checks raw preflight/TLS, opaque null custom context, low32 encoding, successful raise contradiction, ignored negative End result, permitted non-full OK continuation, and no size read at limit zero. Strict C11/C++17 fixtures compile and run the PRODUCTION ABI header.
- Final reports bind sources, headers, Rust release archive, compiler, fixtures, native objects, codec libraries and dependencies before/after. Every executed test/control/header binary has before/after execution hashes; selected generated host headers have matching generation/compile hashes. Exact commands and receipts are adjacent to each report.

Failed-probe ledger: first CPP worker run was interrupted by its own ten-second tool timeout, not a credited verifier result. First Rust corpus/host attempts correctly rejected concurrent core-writer Rust-source/archive drift after their behavioral checks; no drift was waived and no algorithm repair was made. Second attempts passed, followed by the final successful executions adding complete binary receipts. No Cargo, native project build, game, commit, nested delegate, remote, Steam, storage or host-prototype mutation occurred in this worker. Native append/status fault cases remain counterfactual, NOT actual OOM or naturally occurring codec failures. Parent owns independent replay and real producer/consumer screenshot acceptance.

## parent Rust-controller acceptance

parent `cpp-primary-r2`, `rust-primary-r1` and `rust-host-primary-r1` pass independently. selected production backends each pass 3011 cases / 1729 anchors, with 12 CPP and 17 Rust controls; both retain ordered SHA256 `bcf3f6fe8dd2f31fb896743ca555a37bc56222d18c801713b57d5296216d5582`. actual Rust + frozen native host passes 1050 cases / 7510 ordinary assertions and 1050 / 8598 instrumented assertions, raw ABI checks, sixteen opcodes, full codec/append ordering and five controls. binary execution receipts are in the reports, not inferred from filenames. a post-fixture-rebuild scan reconfirmed every binding in all three parent reports unchanged.

all three production decisions/loops now select Rust behind default-OFF `STAR_USE_RUST_COMPRESSION` in the sole aggregate archive. seven allocating/forwarding facades, public header and all `CompressedFile` behavior remain native and byte-exact. vendor zlib-ng is retained, not counted as a Rust codec rewrite. native input/output ownership, native uint32 narrowing, same exception_ptr and temp lifetime stay in C++; no automatic codec End fixes the legacy append-exception behavior.

parent workspace debug/release each pass 84 tests (70 FFI + 14 lighting), fmt passes, behavior verifier 138 tests and inventory eight controls pass; catalog 1554 files / 39 modules. source-only adversarial review traced six unchanged production files against the frozen controller contract with no actionable findings; that review does not independently certify runtime/OOM behavior.

### real PNG producer and both native consumers

`compression-actual-r2` and `compression-combined-compression-room-r2` use normal `Image:embed('Zlib')` and first uncached `assets.image` loads for produced Zlib and independently fixed Gzip paths. Gzip production remains unsupported; the fixture never invokes it. embedded permission is enabled only in isolated lab boot configuration and no external HTTP is contacted.

native rows capture actual encoder PNG input, actual returned embedded path, compressed bytes, decoder PNG bytes and controller receipt deltas. Lua cannot provide those rows. successful Rust attempts/successes are unchanged predicted one-hot vectors: embed `[1,0,0]`, Zlib load `[0,1,0]`, Gzip load `[0,0,1]`; exceptions all zero; CPP vectors all zero. fixed Gzip/PNG bytes are pre-candidate literals and all PNGs independently decode to 16×16 RGBA `[96,192,224,255]`. matched producer/consumer roundtrip alone is rejected by a known-wrong-pixel verifier fixture.

the actual returned Gzip image—not a repaint or replacement—is registered as a normal Assets image and rendered with the normal Font label `COMPRESS`. parent inspection caught the first fixture's doubled projection: 128×128 instead of the pre-agreed 64×64. the former minimum-ink check had missed this. `compression-actual-r1/geometry-negative.log` records the new exact-bounds checker rejecting the old real capture before repair. a permanent wrong-128×128 test was added; only the new fixture projection changed to observed scale × 0.5 / TilePixels. no algorithm, reference, data literal or tolerance was fitted. corrected isolated/combined native checks require exactly 4096 cyan pixels in the expected centered64×64bounds. old r1 captures are historical, not final acceptance.

all 15 final native matrices pass: corrected isolated/combined plus all thirteen prior combined scenarios. baseline/candidate frames, state and receipts agree exactly; all thirteen historical decoded pixel sequences remain unchanged. parent inspected all three corrected isolated frames and the combined occluded frame. newly built CPP/combined objects pass literal mono8000Hz PCM samples `[-32768,-12345,-1,0,1,12345,32767,0]`, seek/EOF, 17 byte receipts and the corrupt-PCM comparison control. final three source/binary seals pass in `/tmp/openstarbound-compression-candidate-final-source.log`.

parent keeps explicit qualification limits: actual reserve exhaustion, universal allocator/free timing, forced Rust panic, other platforms, performance, live HTTP/network/save interoperability, audible playback and server gameplay remain unqualified. counterfactual append/status tests stay labelled as such. only three stream controllers migrated, not `CompressedFile`, all compression services or the engine.
