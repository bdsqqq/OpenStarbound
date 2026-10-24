# native calibration evidence

## verified finite observations — 2026-10-24

command:

```sh
python3 source/lab/option-parser/run.py --output build/option-parser-lab/oracle-live-option-qualified
```

- result: `FINITE_NATIVE_CALIBRATION_PASS`; 295 scenario ids, including 256 bounded deterministic combinations and 15 stream cases.
- complete original, namespace-only reference, current native cpp, and original repeat observations matched byte-for-byte.
- ordered observation sha256: `056b5d907385bcb6266b86623b249c1deaa862263fd2ff4bf8232864ff290e4b`.
- 1,097 bound inputs, 18 independently linked binaries, 41 recorded commands; see `build/option-parser-lab/oracle-live-option-qualified/report.json`, `before.json`, `after.json`, `artifacts.json`, and `receipts.json`.
- fixture sha256: `d38afabf05dd377079d4e04b7773f89cc8ca9957d1d764c384d195ec42f49e01`.
- runner sha256: `c60d1b90b4fa760ca555b8318c514de45b227c3d5e235cba60a61ae2ca53f8cb`.

literal anchors reject unknown/missing/duplicate parameter behavior, duplicate-value consumption, repeated end markers, required/error ordering, positional cardinality, switch deduplication, single-dash removal, exact help whitespace/chunks, metadata combinations, duplicate registration retained state, stream width/fill/tie behavior, fault prefixes, exception identity/suppression, late metadata/registration reads, and nested help. broader combinations, nul/unicode/native-invalid-utf8, copy/move, enum3, and public result state are whole-stream comparisons, not universal claims.

all 13 semantic/stream mutants compiled and exited successfully before their differing observation streams were rejected: repeated-end marker, delayed parameter consumption, duplicate acceptance, missing-required suppression, minimum cardinality, error ordering, two-dash removal, clearing failed streams, enum3 help normalization, description-loop-only snapshots, upfront metadata/collection snapshots, unformatted `ostream.write`, and character-fragmented insertion.

two separately linked paired missing-required mutants produced equal streams, then the independent literal checker rejected them. a separate known-bad observation fixture also failed the literal checker. cpp/header raw and namespace-reference provenance mismatch controls were rejected independently.

## attempted and retained failures

- `oracle-r1`: old values-only zstd seal omitted the zstd object; stopped before compilation.
- `oracle-r2`: that seal also predated the current version object; stopped before compilation. final acquisition uses matching `build/zstd-lab/cpp-postbuild-r1/before.json` plus the unchanged zstd object's historical `build/shell-lab/cpp-final-r2/before.json` seal. no reference rebuild was performed.
- `oracle-final/error-order-compile.stderr`: a mutant used unavailable `StringList::prepend`. this was NOT credited as a rejection. one repair changed it to native `insertAt(0, ...)`; subsequent successful compilation and comparison rejection are in `oracle-final-r2` and `oracle-qualified`.
- `oracle-r3` was the smaller 33-case pass; `oracle-final-r2` was a 294-case pass before incremental receipt preservation and separately linked paired-corruption acquisition were added. `oracle-qualified` binds the earlier 294-case runner. `oracle-live-option-qualified` binds the final runner after adding the parent's traced active-option-insertion contract.

## active option-loop correction

parent review identified that option order uses `LinkedList` (`StarOrderedMap.hpp:16,324–337,424–441`; `StarList.hpp:341`), not a vector. independently traced before mutation: insertion preserves the active option iterator and end. the added `stream14` callback registers one switch during the first option-description insertion; an independent literal requires its description later in the same loop, while already-emitted usage stays unchanged. the description-loop-only snapshot mutant compiles, exits normally, and fails comparison. active positional-vector append remains excluded. this corrects the earlier overly broad active-loop exclusion.

## parent replay and opaque boundary

parent independently replayed the frozen native corpus in `build/option-parser-lab/parent-native-r2`: the same 295 cases, 13 successfully compiled semantic mutants, paired-corruption literal rejection and ordered sha256 above passed. `parent-native-r1` was interrupted by the harness's ten-second background timeout; its partial artifacts remain, with NO pass credit. the fresh second run used a sufficient process timeout, not changed inputs or expected results.

`verify_receipts.py --report build/option-parser-lab/parent-native-r2/report.json --self-test-output build/option-parser-lab/receipt-negative-r1` independently rehashed 1,097 inputs, 17 source artifacts, 18 binaries and 41 command receipts. six isolated synthetic artifact corruptions were detected (bound input, generated source, binary, archive, stdout and stderr). synthetic receipt fixtures are integrity tests, NOT evidence that those fake binaries ran.

`host_run.py --values build/option-parser-lab/parent-native-r2 --output build/option-parser-lab/parent-host-final-r1` passed the C++ scalar controller through the ACTUAL eight public member definitions and private native records, without changing `StarOptionParser.hpp`. template access and const/mutable inference compiled directly, not via a toy parser. the complete 295-case stream matched the independent original exactly. the separate host executable exercised all 33 opcodes and 24 templates, literal grammar/help, real stream callbacks, native exception identity, pending preservation, source-compatible late metadata/definitions, safe active option-loop insertion, same-parser separate-context nesting, busy rejection, output guards and a nontrivial custom scalar parse script. strict c11 passed. two mutants of the final bridge (delayed value consumption and fragmented insertion) compiled, exited successfully, and differed from the native stream. earlier worker mutants precede the last owner-span guard change and are historical observations only.

parent review corrected a scalar-span off-by-one: accepting `UINTPTR_MAX-7` allowed the exclusive eight-byte end address to wrap. the final guard rejects it before dereference, and the isolated aligned-top-address negative passed. caller liveness and disjointness from arbitrary heap graphs remain preconditions; integer checks do not prove either. a final raw-status check also maps unknown callback returns to invalid-protocol status2, rather than leaking arbitrary runner status values or falsely reporting a panic. isolated statuses2/3/UINT32_MAX stop after one callback and passed. final full replay follows both fixes and EOF-whitespace cleanup; earlier host runs bind their earlier revisions. source-only independent review found no actionable control/ownership defects before this last scalar-status hardening; it is not a runtime certificate.

## sanitizer scope and retained native defect

full undefined-behavior instrumentation of the newly compiled native parser/fixture FAILED on existing `StarFlatHashTable.hpp:309`: empty `end()` computes `m_buckets.data() + m_buckets.size() - 1`, producing a null-pointer offset diagnostic. `build/option-parser-lab/enum-sanitizer-r1` and its stderr are retained. this is NOT a passing undefined-behavior check and was NOT repaired, suppressed in the reference, or included as a successful algorithm mutant.

changing the verification question to ENUM-ONLY instrumentation, `build/option-parser-lab/enum-sanitizer-r2` passed all 295 cases with the exact native stream above. only newly compiled parser/fixture translation units were instrumented; reused core/extern objects were not. this supports the finite enum-3 observation, NOT whole-engine undefined-behavior cleanliness or universal domain/resource claims. neither sanitizer configuration changes the frozen ordinary native reference flags.

## unresolved / not claimed

streambuf observations cannot prove attempted `format()` entries after failbit suppresses writes. no actual oom, universal allocator/resource/destruction timing, rust/native-host equivalence, production integration, app exit behavior, game screenshots, platform coverage, or completed module migration is claimed. parent fresh replay and boundary acceptance remain separate gates. no commits, production writes, app launches, cargo invocations, or deletion were performed by this worker.
