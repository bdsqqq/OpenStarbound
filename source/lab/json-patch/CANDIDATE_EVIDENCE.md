# production json-patch candidate oracle — 2026-10-24

VERIFIED: complete compiled `StarJsonPatch.cpp` control flow is selected through default-OFF `STAR_USE_RUST_JSON_PATCH`. all ten semantic functions run in the existing Rust archive; native JSON ownership and exact compound leaves remain C++. public `StarJsonPatch.hpp` and the complete OFF fallback remain byte-exact. this does not complete JSON ownership, serialization, assets or the engine migration.

## replay

```
python3 source/lab/json-patch/run.py --backend cpp --output build/json-patch-lab/NEW-CPP
python3 source/lab/json-patch/run.py --backend rust --output build/json-patch-lab/NEW-RUST
```

`--reference-report` accepts a previous report from the SAME backend and requires exact bindings and ordered observations. every run independently compiles the immutable original CPP controller into a separate binary and compares its complete ordered stream to the selected production backend; this comparison does not rely on matching two implementations inside one binary.

- original/reference cpp+hpp freezes still compare against `git show b07cae00`. live public header must remain unchanged. selector fallback reconstructs include prefix plus complete `#else` body and must equal the original bytes.
- production selected oracle retains all 52,779 cases, RFC/legacy literals, binary-safe final errors, recursive numeric type tags and original 18 negative controls. operation immutability is now checked as well as base immutability.
- Rust-selected builds check attempt/success/native-exception deltas on every top-level semantic call (including all ten entry functions). baseline logs observed 316,694 checks. CPP baseline logs observed 158,357 checks. these counts alone do not substitute for final before/after provenance acceptance.
- `candidate_abi.cpp` manually compiled and ran successfully: 272 checks. it verifies exact host opcode order/indices/unused metadata, required scalar preflight for all ten entries, null custom context, unknown entries/counter queries, output suppression, internal PATCH/APPLY/ADD/FIND counts, inverse traversal recovery, setup outside that catch, catch-body errors routed only outward, test-fail not JSON-wrapped, host protocol abort without fabricated native-exception exit, and reentrant thread-local counters. callbacks assert opcode38 is never called by Rust.
- `candidate_host.cpp` derives the phase1 native-host test by replacing its runner with the actual Rust entry and asserting reserved receipt opcode38 has zero coverage. manually compiled and ran successfully: 52,771 cases, 229,656 checks, all other41 native opcodes covered. real retained native exceptions, fault injection, typed values, metadata rejection and cleanup scopes remain exercised. final runner repeats this binary and its known wrong-typed-handler control.
- actual selected-bridge inverse mutant compiled and exited1 with comparison case11. actual receipt-suppression verifier mutant compiled and exited1 with semantic-attempt mismatch case1. final runner also requires native pending-category and adapter-dispatch mutants to fail by comparison, never compilation.
- strict C11 and C++17 production-header fixture `candidate_header.c` compiled with `-Wall -Wextra -Werror -pedantic` and both executables ran successfully. artifacts are in `production-rust-frozen-r1/header-{c11,cpp17}`; this manual check is separate from the final runner report.

## observed failed probes and qualification boundary

- first raw trace validator incorrectly required zero `n` on indexed SEARCH_ADD. fixed that validator to allow its index; the controller was unchanged. raw ABI then passed272checks.
- first pending-category mutant changed TestFail to JSON but preserved the same actual exception_ptr. the complete oracle correctly found no output difference, so the runner rejected that negative control rather than crediting it. replaced it with JsonException-to-OTHER, which bypasses the required wrapper and changes observable final exception/category.
- early development runs intentionally rejected source/compiler/dependency drift while verifier files were still changing. later obsolete owned jobs were stopped to avoid duplicate stale runs. these are not accepted reports.
- final launched worker outputs are `production-cpp-qualified` and `production-rust-qualified`; inspect their `report.json` and top-level `.log`. lack of a report is NOT a pass. parent must independently replay the frozen final sources after native-object freeze.

native objects are privately archived but never rebuilt here; Rust archive is read only from `build/json-patch-rust/target/release/libstar_engine_ffi.a`. sources, compiler, recipes, linked objects/libraries, raw ABI/header/bridge/Rust source/archive, checker and transitive native dependencies are bound before/after. drift is rejected, not waived. full native freshness still requires the parent's source seals. actual bad_alloc, allocation timing, raw C++ valuePtr identity instrumentation, panic injection, performance, game behavior and screenshot evidence are NOT claimed by this worker.

## independent parent acceptance

parent replay after native/source freeze passes `cpp-primary-r2` (52,779cases/158,357checks/18controls) and `rust-primary-r1` (52,779cases/316,694checks/25controls). both complete ordered streams equal phase1 SHA256`456a1a938842d1013b4ecdd5b1ae866032f7d17deec8e97b9c782df366c7b017`. selected binaries SHA256: CPP`73acbf4c49e2cdfc9b332eed7247fc89cf1392f263fe6200314dec5fc6439301`; Rust`7bc4a068a1ddea779541e88d012481889f19507659d4c869bc500b5a56b112a5`. raw ABI272checks and real native-host52,771cases/229,656checks are rerun by the parent Rust command, not merely copied worker reports. all41 live/cleanup opcodes execute; reserved38 is deliberately zero. independent review traced six frozen production sources with no actionable findings; this is source review, not runtime certification.

parent Cargo workspace debug/release passes74tests per profile (60FFI+14lighting); fmt check passes. behavior verifier122tests and inventory8drift controls pass; catalog1524files/39modules. no production algorithm/selector/reference/tolerance repair was needed. the two candidate-verifier probe repairs above are retained, not reset.

## actual native Assets consumer

`build/behavior/jsonpatch-actual-r1` and `jsonpatch-combined-jsonpatch-room-r1` pass all three1000×600frames, exact framebuffer/state and native receipts. indexed UTF8 source plus two literal LF-terminated operation files are checked independently by `behavior/json_patch_proof.py`. normal `assets.patch` registration followed by the first uncached `assets.json` drives actual seven-handler/search/inverse execution, nested rollback and whole-patch rollback. source/result/backend/counters are captured natively around that exact JSON call, not supplied by Lua.

entry order PATCH/APPLY/FIND/TEST/REMOVE/ADD/REPLACE/MOVE/COPY/MERGE:

- attempts `[0,20,7,5,2,4,3,2,2,2]`;
- successes `[0,18,7,3,2,4,3,2,2,2]`;
- native exceptions `[0,2,0,2,0,0,0,0,0,0]`;
- all CPP receipt vectors are zero.

these are the original pre-execution predictions, unchanged after execution. actual Assets uses APPLY, NOT public PATCH; do not claim game execution for PATCH. the isolated oracle does exercise that public entry. full final JSON—not merely color—proves search results and rollback (`scale99→4`, `BAD→PATCH`, `after:true` retained). actual observed RGB64,128,192 and scale4 create a16×16normal Assets image rendered64×64; actual label renders through normal Font as `PATCH`. parent inspected all three isolated images and the combined occluded image. visible ink plus native complete-image pixel checks supplement exact frame comparison; no repainted proxy.

all eleven earlier scenarios are rerun against combined Rust and retain historical decoded pixels; total13native matrices including new isolated/combined. real PCM mono8000Hz WAV samples `[-32768,-12345,-1,0,1,12345,32767,0]`, EOF/seek and17byte receipts pass against the newly built CPP/combined native objects; corrupt-PCM control fails as required. final source/binary seals are required alongside these artifacts.

qualification remains finite and Apple-clang-bound: no universal equivalence, other-platform coverage, actual OOM timing, allocator-resource equivalence, performance, live network/save interoperability, audible playback or server gameplay claim. selectors remain default OFF. next step is the `Text::processText` scanner, not a declaration of engine completion.
