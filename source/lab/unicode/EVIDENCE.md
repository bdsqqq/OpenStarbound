# unicode component evidence

## parent integration and read-pattern repair

VERIFIED — final parent `build/unicode-lab/{cpp-primary-r1,rust-primary-r1}/report.json`: EACH3,382,064cases; CPP17,939,453checks/12controls, Rust17,939,657checks/14controls. Both independent observation digests remain `374ad1a283df9ab0`; the separate CPP-only stream avoids reference hex→String→candidate Unicode contamination. This is a 64-bit FNV observation checksum with finite collision risk, not a cryptographic proof. Same-process field/byte/error comparisons and independent anchors remain in addition to that checksum. Frozen source/header/adaptations unchanged.

Source review found ONE real defect that initialized-byte differential cases missed: legacy `utf8Length` with two bytes remaining can count both without reading the second. Rust repeatedly called its one-character decoder, reading that potentially uninitialized byte. Parent reproduced the unwanted read using a protected-page tail: old Rust child faults, outer fixture exits1 `COMPARISON legacy length short-tail read`. This is a detected safety failure, NOT a successful crash-based negative control. Parent restored the length-specific two-byte recovery branch. `short_tail.cpp` now runs as a required positive test for BOTH original C++ and Rust in ordinary `run.py`; both pass, and a child fault is a comparison failure. This was one bounded implementation repair; no algorithm reference, expected bytes, tolerances or flags changed. Review found no other actionable core/ABI defect; it remains source-only, not universal safety certification.

Parent44Rust tests EACHdebug/release/fmt,85behavior/provenance tests and8inventory drift controls pass. Public header/templates remain byte-identical to the frozen source. C++ allocation/hex facades and distinct generic-iterator policy remain; only the ten compiled operations are the port. Native actual-game evidence is in `../behavior/EVIDENCE.md`.

The ASCII label was moved from the worker's preliminary bottom-left coordinate to the agreed center-above-image ROI BEFORE the first build/capture; no goldens or runtime failures were used to choose its placement. Supplementary text is proved by actual Assets/Lua byte observations and a byte-driven image, not an assumed emoji glyph. Default-OFF rollout retained; per-codepoint bridge performance, other platforms and full text-module compatibility remain unverified.

## independent-observation supersession

final-r1 below is historical same-process differential evidence. its real
String/Encode dependencies can call active Unicode symbols, so namespace freezing
alone does NOT make the hex reference independent. final-r3 closes this boundary:
run CPP-only first, then Rust with `--reference-report
build/unicode-lab/cpp-final-r3/report.json`. both observation streams match digest
`374ad1a283df9ab0` (64-bit FNV; finite collision risk, not cryptographic proof),
covering raw outputs, encoded bytes and every string/error outcome; receipts and
ABI-only probes are excluded. Rust rejects a corrupted independent observation
report in an exercised negative control. original counts stay the same; Rust now
has 14 negative controls. use final-r3 reports for final checker/archive bindings.

```sh
python3 source/lab/unicode/run.py --output build/unicode-lab/cpp-final-r3
python3 source/lab/unicode/run.py --output build/unicode-lab/rust-final-r3 \
  --define STAR_USE_RUST_UNICODE \
  --archive build/unicode-rust/target/release/libstar_engine_ffi.a \
  --reference-report build/unicode-lab/cpp-final-r3/report.json
```

## earlier same-process calibration

VERIFIED: isolated compiled component comparison on apple-silicon macOS, entry
revision `b136ed4ba23e59edac204c0a18377a13ae267c24`. not game/runtime visual proof.

```sh
python3 source/lab/unicode/run.py --output build/unicode-lab/cpp-final-r1
python3 source/lab/unicode/run.py --output build/unicode-lab/rust-final-r1 \
  --define STAR_USE_RUST_UNICODE \
  --archive build/unicode-rust/target/release/libstar_engine_ffi.a
```

both final runs passed 2026-10-24 11:04 UTC, after first calibrating the frozen C++
oracle before candidate use. each binary also repeated identically.

| backend | cases | checks | negative controls |
|---|---:|---:|---:|
| cpp | 3,382,064 | 17,939,453 | 12 |
| rust | 3,382,064 | 17,939,657 | 13 |

Rust executing-thread receipts, in the frozen ten-op order:
`[2264271,2271589,2264279,7798795,3080,1813,1115964,1114114,35,1114116]`.
C++ receipts are all zero. direct ABI probes additionally require exact per-op
increments, semantic-error increments, no invalid-ABI increments, and no helper
double counting; arbitrary nonzero totals alone do not satisfy those probes.

frozen original source SHA256:
`4d18205572c287b1e0a48a7e467cc0811f6c75d30b0e451c841fe17a564edc2c`.
frozen unchanged public header SHA256:
`1a7bc2ad52d89861dac80803819a800cef3b07fa2cee72252bc425baf2b15432`.
C++ final binary SHA256:
`c8555396ee8f56403c57af7f74805f88b2cc3514a451cdd202dfe182d790db84`.
Rust final binary SHA256:
`dd00b5d7e80c96e4f2def0327cadf0ab0c92b190117866d103624797708ce73f`.
isolated native dependency archive SHA256 (both final runs):
`0b86a1ffe6eb18a909466b377f85092c9f3ff4469ebd18b8528784e0578c259b`.

`build/unicode-lab/{cpp,rust}-final-r1/report.json` contains every command, selected
Rust archive hash, actual compiler/header/dependency/object/checker bindings and
negative-control list; adjacent before/after JSONs match. a post-run reread found
zero changed inputs among 1392 C++ / 1401 Rust sealed inputs. SDK, standard-library,
vcpkg and project transitive headers come from actual compiler dependency output.

five actual algorithm mutants compiled successfully and exited 1 from comparison,
not faults or compile errors: NUL policy, replacement consumption, capacity partial
write, pair arithmetic, and real Encode invalid nibble handling. missing-receipt
comparison also exited 1. snapshot/adaptation corruption, arbitrary define,
unpaired archive and outside-output requests were independently rejected. guard
page tests are positive successes; segfaults would fail, not count as negatives.

an earlier Rust run rejected real concurrent `StarUnicode.cpp` source drift, even
though its numerical comparisons passed. it is NOT passing evidence; final runs
above replay after stable source freeze. no algorithm repair or oracle relaxation
was made in response.

limits: actual String/ByteArray/Encode facades run against pre-existing native
objects, packaged only into owned lab outputs. object bytes and current dependency
sources are bound, but native object-to-source build freshness requires the
parent's existing build seal. no shared native/Cargo rebuild, game launch,
screenshot, audio, performance, other-platform, generic-iterator port, whole text
module completion or universal equivalence claim. status-3 panic behavior is not
injected by this C++ harness; separate Rust panic tests are outside this report.
