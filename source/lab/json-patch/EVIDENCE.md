# json-patch cpp calibration — 2026-10-24

historical phase1 record below. current Rust selector, independent replay and actual Assets/game acceptance are in [CANDIDATE_EVIDENCE.md](CANDIDATE_EVIDENCE.md).

VERIFIED: calibration only. no rust backend, production edit, native rebuild, game run, screenshot, commit, or port-completion claim.

## replay

```sh
python3 source/lab/json-patch/run.py --output build/json-patch-lab/cpp-parent-r1 --reference-report build/json-patch-lab/cpp-frozen-r1/report.json
```

worker runs `cpp-frozen-r1` and `cpp-frozen-r2` passed: 52,779 cases, 105,578 checks each, 18 detected controls each. both repeat their binary and compare the complete ordered stream byte-for-byte. second run additionally checks the first run's stream hash and exact source/compiler/header/object bindings. parent must replay independently and validate sealed native object freshness before accepting this evidence.

ordered observation sha256: `456a1a938842d1013b4ecdd5b1ae866032f7d17deec8e97b9c782df366c7b017`.
calibration binary sha256: `54c0b8c2bdaac72b1957e62cfb48c9425b5aa5211854540a4035465ca5a5094c`.
archive hashes differ between runs because archive metadata is not normalized; each exact artifact is recorded in its report, not treated as a cross-run identity.

## independence and scope

- `run.py` freezes complete cpp/hpp from `b07cae00` through exact `git show` comparison. reference changes only namespace/import/include. public header and live production implementation remain byte-identical to that revision.
- all ten entry points are exercised: whole patch, dispatcher, seven direct handlers, and `findJsonMatch`. direct handler calls have no added wrapper. external dispatcher argument is deliberately nonempty and ignored.
- real allocating native json/path/maybe/string/lexical/stream/exception dependencies are linked from existing reference objects. `StarJsonPatch.cpp.o` is excluded from the private archive; current unchanged production cpp and frozen reference compile separately. no local dependency stand-ins.
- literal RFC appendix anchors cover object/array add/remove/replace/move. legacy anchors cover first match, search move overlapping source/destination, explicit null test-as-absent, merge-null preservation, array-recursion argument reversal, same-value replace, search no-match, and empty patch.
- the generated matrix covers all seven direct handlers, dispatcher and whole-patch wrappers across typed values, absent value, explicit null, searches, inverse searches, invalid traversal, roots, scalar bases, invalid operators, prefix-before-failure and immutable input. numeric type tags recurse through arrays/objects, independently of json equality.
- errors capture `printException(e,false)` in full binary-safe streams. category distinguishes test-fail (a star exception, NOT a json exception), patch exception, json exception, traversal and other exceptions. a literal inverse-existence test uses an existing embedded-NUL key, proving the FINAL error retains its suffix. production's intentional inner `e.what()` truncation is unchanged.
- source, compiler executable, compile recipe, ninja link recipe, every linked object/static library, and discovered transitive headers are hashed before/after. only explicitly owned lab files are included: reserved host prototype files are neither read nor hashed.

## falsification actually run

four source-freeze corruptions; wrong stream identity; wrong source bindings; actual controller mutants for inverse, search-first indexing, null opt semantics, replace removal, search-move overlap and missing-value access; paired controller/reference error corruption detected only by independent stream identity; an actual `StarJson.cpp` recursion mutant detected by independent legacy anchor; isolated verifier mutants for truncated error, wrong numeric type representation, wrong exception category and changed input state. every algorithm mutant compiled and ran, exiting 1 with a comparison failure; compile failures are never credited.

## phase-1 host boundary (not a Rust port)

Parent replay `build/json-patch-lab/cpp-parent-r1/report.json` independently passes the52,779case/105,578check/18control calibration above, including exact source/compiler/object/stream identity against `cpp-frozen-r2`. Existing native reference source seal passes; no production source or native build changed in this phase.

`host_contract.hpp` freezes42opcodes:39 designer primitives plus explicit FIND/HANDLER/APPLY release operations. These drop copied array/scratch/operation strings at lexical exits instead of retaining copy-on-write snapshots across later mutations. Native JSON/path operations and exact compound expressions remain C++; a lab-only C++ driver exercises the proposed future Rust control-flow/error-routing boundary. No host callback delegates a complete legacy handler. Actual retained `exception_ptr` categories, catch-body faults, native `what()` truncation, scalar publication, base immutability and all42opcodes are tested.

Replay: `python3 source/lab/json-patch/host_run.py --output build/json-patch-lab/host-prototype/NEW-NAME`. Outputs must be new and nested; the runner binds itself/prototype/header/compiler/native objects/dependencies before/after, repeats the comparison, requires42positive opcode coverage, executes a wrong-typed-handler comparison failure, and runs strict C11/C++17 ABI compile/runtime probes. Parent `host-prototype/parent-final-r2/report.json` passes52,771cases/229,656checks/all42opcodes (minimum100hits), binary SHA256`6c8c9deb777701343e377888e9c2159725f034595606e58f847c33448a0ed5b7`.

Prototype worker was interrupted after its8-minute budget; its earlier report is historical, not parent acceptance. Parent reproduced an enumerable metadata-span gap using ignored-output operations: forged wrapping output pointers returned success. `host-prototype/parent-span-negative-r1/failure.log` exits1 with the exact comparison failure, not a crash. Host and controller now reject wrapping8-byte output spans before work; the permanent regression passes. One parent replay rejected a stale expected known-fault label (the worker had changed the mutant from category to typed value); runner now checks the actual specific typed-handler failure, and final full replay passes. No production algorithm, literal result, tolerance or reference flag was changed. These are prototype/verifier repairs, not a production port.

This qualifies a finite native boundary on the tested compiler, NOT a Rust implementation, game behavior, memory allocation/fault timing or other-platform equivalence. JSON ownership remains native. Future phase2 must implement Rust decisions/loops with the same scopes, add a default-OFF production adapter/receipts, rerun the independent oracle and qualify actual Assets patch behavior before claiming migration.

## failed initial probes and limits

`cpp-r1` failed because the new verifier used `printJson` on scalar values. switched representation to the native scalar-capable `repr`, preserving recursive type tags. `cpp-r2` then rejected a mistaken NUL anchor: traversal's inner `e.what()` intentionally truncates before final formatting. these consume two failed baseline approaches; no kernel repair, tolerance, compiler flag, source-freeze or expected production behavior change was made. changed the probe mechanism to inverse existence on an existing NUL-bearing key, where production formats the raw path directly. `cpp-r3`, `cpp-final-r1`, and the final two frozen runs passed. do not reset these failed-probe counts.

competing-failure cases include merge missing path/value, invalid pointer plus absent value, and replace invalid pointer plus absent value. captured outcomes apply only to the recorded apple clang recipe; no portable sibling-operand evaluation order claim, callback/getter event tracing, allocator-fault injection, or universal-equivalence claim. retained exception-pointer/lifetime ABI behavior belongs to the separately owned host prototype and remains outside this calibration.

worker source freeze: all files named in `run.py:OWN` are frozen after `cpp-frozen-r2`; this evidence file is explanatory and excluded from executable bindings. worker has stopped all builds and makes no further writes after handoff.
