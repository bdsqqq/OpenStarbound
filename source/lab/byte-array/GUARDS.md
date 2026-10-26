# buffer guard bookkeeping

`StarBufferHost.hpp::safeOutput` reads four current native ByteArray ranges when
ByteArray's Rust selector is on. the off branch retains public getters. this
avoids recursively running public Rust controllers merely to exclude output
aliases. logical sizes, all other exclusions, ownership and callback boundaries
are unchanged. no pointer/size snapshot survives mutation or a foreign callback.
this is bridge bookkeeping, not a native replacement for a Rust controller.

## finite evidence

- the counter-only diagnostic first observed compression phase1 at update1740.
  at most61 updates remained under the unchanged1800 cap, fewer than the required90
  settling updates. `build/behavior/byte-array-readiness-diagnostic-r1/compression-r1/diagnosis.json`
  traces this instrumented run; it does not diagnose all six r6 failures.
- the coherent guard+counter prototype passed583 frozen Buffer records, all50
  native TLS routes, repeat/model/literals, native-context protocol and normally
  exiting bypass rejection. parent independently rehashed its bindings before
  promotion. `build/buffer-lab/guard-counter-prototype-r1/report.json` is historical
  after the exact production/sealer/build-fixture changes, not rebound evidence.
- the ordinary coherent r7 build separately passed the same Buffer gate at
  `build/buffer-lab/guard-production-r1/report.json`. subsequent catalog refresh
  changes a non-compiler input in that broad receipt. final-catalog replay at
  `build/buffer-lab/guard-production-r2/report.json` passes; parent separately
  rehashed all2832 bindings/artifacts and replayed semantics.
- `build/behavior/byte-array-guard-ranges-production-r1` exercises aliases,
  logical ends, no-mutation rejection, relocation and fresh-context reentry.
  known-context/span evidence is not arbitrary-pointer or lifetime proof.
- frozen empty-fill/copy regressions pass on r7. the aggregate remains
  `732775f07a3689656dc4e500f8cb72ab6de9fa0677dd996211fcdf6c82a64cb5`;
  no Rust controller or receipt ABI changed.
- fresh113-object off/on ByteArray builds and exact seals support987+14 cases,
  repeat/protocol/all56/native-bypass at `build/byte-array-rust/guard-run-r1/report.json`.
  the producer exhausted its420s shell budget during its final verifier after
  writing the complete report. a separate staged `rust_execute.py verify` passed
  (`/tmp/openstarbound-byte-array-guard-independent-verify-r1.log`); no game or
  native execution was blindly repeated.81 ByteArray/195 behavior/8 inventory
  tests pass; current inventory1746 files/39 modules.

`rust_seal.py` reconstructs the entire original Buffer host from `67ed3547`,
checks its original digest, applies only the four range-read substitutions, and
checks the new digest. historical compiler receipts may retain the original
hash only through this reconstruction. fresh compilation must bind the new
header. isolated controls reject capacity-for-size substitution, removed guards,
unrelated header edits, unknown identities and other input drift. the build
fixture similarly reconstructs only r3→r7. there is no broad source exemption.

## finite application gate qualified on r7

production `8ac00aef`, unchanged aggregate732..., passes all19 real-game
native/repeat/candidate matrices and57 historical decodedRGBA frames at
`build/behavior/byte-array-actual-r5/qualification.json`. all14 actual TCP/save/
BTree/PNG scopes, literal PCM/seek/EOF/corrupt-expectation and12 CLI executions
are bound alongside current kernel/Buffer/guard/empty-fill/copy evidence.
3906 bindings were independently rehashed. all57 candidate frames were inspected
in labeled state triplets; raw-frame/page hashes and limitations are retained in
`build/behavior/byte-array-visual-inspection-r7-final/inspected-19.json`.

encoding's original native/repeat captures were retained byte-for-byte. a
symlink reuse attempt was correctly refused before candidate execution and is
preserved as r2; r3 uses exact plain copies with original manifests/identities,
then a fresh candidate capture. no reference rerun or receipt rebinding.

oracle review found that identical pixels could mask a wrong outer scene label.
the qualifier now requires every receipt's scenario to match its matrix row in
both qualification and existing-result verification. the isolated lighting-as-
SHA256 negative rejects;14 verifier tests pass. source-frozen verifier and
repair evidence live in `byte-array-qualification-tools-r7`; the final freeze is
`verifier-freeze-parent-r3.json`. retain the superseded freezes and all r6 failures.

the prototype still has no ordinary acceptance sidecar and contributes no
application pass. qualification is finite macOS evidence, not full-engine,
arbitrary-pointer/lifetime/OOM/platform/sanitizer/performance, audible mixer or
complete Universe-handshake proof. defaultOFF/native ownership remain intact.
