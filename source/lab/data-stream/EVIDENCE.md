# native DataStream calibration

## accepted parent replay

`build/data-stream-lab/oracle-parent-r1/report.json` independently rebuilt/replayed the frozen original, renamed whole reference, unchanged current source and repeat:683 ordered records,51 source-mapped compiled definitions, SHA `5ee512e3a91027823f34c47df4d1e056753e0fd61f03a9ad70e65131900763ab`. independent verifier rehashed1102 bindings/15 binaries/35 commands; all eight isolated integrity corruptions were detected in `parent-integrity-r1`. this is native calibration only, not a Rust/opaque-host/application qualification.

parent source review found and corrected defined-domain problems BEFORE acceptance: negative-only staging read uninitialized locals, and terminated-string inputs accidentally became ByteArray length97 and exposed uninitialized growth. corrected controls value-initialize staging and use proper length3 array input over preinitialized16-byte storage. the array-prefetch control caches size only and obtains a fresh pointer, avoiding a dangling-pointer negative when its prefix callback reallocates storage. raw original/current algorithms and reference flags were not changed. pre-r5 runs remain unqualified.

full-range signed VLQ native expressions are admitted: the scoped C++17 shift diagnostic at `build/data-stream-lab/domain-signed-vlq-r1/report.json` matches independent zigzag anchors for INT64_MIN/MAX and detects its known-bad shift64 fixture. this is neither full-Core UBSan nor another copy of the old restricted signed domain. remaining alias/resource/platform gaps stay explicit; no ABI is frozen yet.

## worker calibration handoff: r5 only

VERIFIED finite native calibration at source HEAD `9f2316a22d5abcb10ff2778b628bc3bef7de5b99`.
report: `build/data-stream-lab/oracle-final-r5/report.json`
report SHA-256: `a4b1fbed71448c568498faac16e232a1d52c5343869b3115b4eff7711663d5b9`
ordered stream SHA-256: `5ee512e3a91027823f34c47df4d1e056753e0fd61f03a9ad70e65131900763ab`

683 ordered records matched original/reference/current/repeat. source-mapped calls
exercise all 51 out-of-line definitions; this is not compiler coverage instrumentation.
15 executables, 35 actual command receipts, 1,102 before/after bindings, all 202
sealed native-profile inputs unchanged. nine semantic mutants and the reference-only
class mutant exited normally and differed; paired wrong executables agreed and
failed independent literals. four provenance controls and eight isolated integrity
corruptions were rejected. independent verifier passed after r5.

native executable SHA-256:
- `original`: `10ca7d0e68fba5752076b90b0f47a5e777ba11ec81946cf2a0f2515e58b6e462`
- `reference`: `881142159d57847afdb9a0263778dcae024ae1b407353264ed9690e02e39b06f`
- `current`: `802ef61d460812554bfe14706cd4ee292bcb80203e30d949c0910d2f8f0227e7`

private native archive SHA-256: `0a559aa0d634b3932ba2d2cc579d33d289b6f14f5b6cb41766fff2d25624c6a2`
linker membership: `build/data-stream-lab/oracle-final-r5/link-membership.json`.
all commands/stdout/stderr hashes: report and adjacent receipts.json. source hashes:
adjacent source-freeze.json. this document is post-run handoff metadata.

only r5 receives defined-domain evidence credit. pre-r5 artifacts are retained with
UNQUALIFIED markers. repair ledger is in README: symmetric order inputs, masking
callbacks, negative-only indeterminate staging reads, and terminated ByteArray
fixtures accidentally growing to97 bytes. corrected controls value-initialize
staging; array fixtures always prefix length3 over preinitialized16-byte storage.
array size-prefetch mutant obtains fresh pointer after callback, avoiding UAF.
full-range signed writes and sizes are included after the parent's scoped C++17
shift probe; that probe is not full-Core sanitizer certification.

reading boundary: dig and running-cross-cutting-migrations bodies read in full;
plan lines1-120 and120-140 read, covering current unit and relevant handoff, not all
historical plan prose. full DataStream.cpp/header read across bounded chunks;
NetCompatibility header, Bytes order conversion and device IO entrypoints traced.

only new lab and owned oracle-* roots written. production/Core/Rust/CMake/native
projects/parent identity/plan/catalog/storage/Steam unchanged by this worker.
no ABI prototype, cargo, native rebuild, game launch, deletion, commit or remote action.
no owned processes remain. native-only: rust/application/platform/resource/performance
qualification is pending. parent owns fresh replay, acceptance and any local commit.

budget: original12-minute target overran while completing parent-requested
pre-acceptance domain corrections; no additional experiments planned.
