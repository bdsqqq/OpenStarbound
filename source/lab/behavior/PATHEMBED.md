# pathembed: finite application evidence

**verified:** both portable `StarPathEmbed.cpp` functions have default-off rust
controllers. rust owns the four-way codec selection and complete borrowed-byte
escape loop. cpp retains storage ownership, codec dependencies, native exception
construction, and prvalue returns; those dependencies are not counted as rust
codec implementations. the public header/layout remains unchanged.

## why this scene

an encode/decode round trip could preserve a shared escaping error. the
`path-embed-room` fixture instead uses a reserved frame name containing every
escaped character, an independently declared escaped literal twice, and a
normal text `.frames` alias selecting only the right half of a 32×16 image.
the excluded half is magenta; the selected half has four asymmetric quadrants
and two orientation markers.

the returned base path, crop path and label travel through real loopback
`TcpPacketSocket` packets. normal `Assets` parsing/decoding supplies the image
used by `WorldPainter`. both original base and crop `ImageConstPtr`s remain held
through painting: retaining only the alias does not retain its embedded base
across cache expiry. snapshots validate those originals after painting, not
replacement images or another ownership lookup.

only the lab observer arms the existing `image:embed('None', frames, 'text')`
body. same-lua-thread completed-count deltas are native `0/0`, rust `1/1` for
selector/escape. these count controller completion, not codec/facade success.

## accepted artifacts

local evidence; no upload or remote publication was authorized.

- code: `0197c097`; consumer/build instrumentation: `3a0f6da1`.
- final receipt: `build/behavior/path-embed-parent-composition-r1/qualification.json`
  — sha256 `4c0a9710cc91dba572b45a8e8a275c19c0a01ffca9bd52ef67a95c822b83c001`.
- composition: `build/behavior/path-embed-parent-composition-r1/report.json`
  — sha256 `bd02c12d475c2908fbedc4c1b9877c7fb544d3a3bab5614aeee0a24fddf08520`.
- `integrity-seal.json` beside those receipts binds 6,470 input files, all
  2,973 producer-tree entries and 620 supplemental-tree entries. these are
  different sets, not an additive unique-file count.
- actual game rust archive:
  `build/behavior/path-embed-combined-r1/candidate/cmake/rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a`
  — sha256 `2bc9e918abf427df265ef70dc2b7a23ec5bff38207c1ad45b54cde39c239b506`,
  exactly the separately qualified 357-row/protocol/layout kernel artifact.

21 actual matrices contain 63 independent capture processes, 189 png/receipt
stage pairs and 42 fresh comparison edges. all 60 historical file-qualified
rgba frames remain exact. all 63 current rust frames were inspected, including
the new crop's three states and occluder insertion/restoration. fresh literal
pcm and 12 cli cases passed; buffer-room retains actual file/save/btree/network
consumer checks. coherent captured-data corruptions and typed ownership,
role, stage, counter, alias, pixel and membership controls were exercised.

## why the final receipt is composed

two bounded full-ledger attempts remain **failed**, not retroactively promoted.
the second had completed 40 comparison edges before its command guard rejected
the unchanged zstd validator's local decoder. a separate bounded witness then
recorded decoder argv, stdin, stdout, stderr and executable alias/payload for
86 invocations, exercised valid/bad-input controls, and completed only the two
missing zstd edges through unchanged validators. the parent authenticated the
40 retained executions, joined the independent two-edge supplement, executed
the remaining auxiliary/negative/inspection checks, and sealed the composition.
no third full-ledger replay, decoder allowlist patch, tolerance change or new
capture was used to conceal those failures.

the original before-capture preparation remains unchanged. later diagnostic
witnesses and the composition are explicitly post-observation supplements.

## limits

finite apple-silicon macos evidence, not full-engine or other-platform
completion. no universal pointer/ownership, oom, performance, actual os deletion,
audible mixer/ogg or universe-handshake claim. before/after snapshots cannot
detect transient edit/revert; tool payload hashes do not attest every loaded
framework, decoder dylib or interpreter implementation. native platform/storage
and codec boundaries remain intentional.
