# experimental rust buffer controllers

`STAR_USE_RUST_BUFFER` defaults **off**. this ports the 50 compiled definitions
in `StarBuffer.cpp`, not ByteArray, IODevice, device wrappers or the full engine.

## boundary

rust decides branches, ordering, copied counts, seek arithmetic and child calls.
c++ retains object layout, vtables, storage, borrows, typed temporaries, native
allocation, virtual dispatch and exception identity. the public header and native
off namespace remain byte-exact. `StarBufferHost.hpp` is the production context;
the candidate protocol executable includes it, not a second lab controller.
one aggregate `star_engine_ffi` archive owns the runtime.

native quirks remain intentional: end seek subtracts, ExternalBuffer bool means
empty, zero-length Buffer I/O precedes mode checks, ExternalBuffer writes always
throw, open branches on its original argument after setting mode, read/write
advance the *fresh* cursor after a child, self-move clears, Buffer clone resets
position, and ExternalBuffer clone retains the native logging format failure.

requested length is not physical capacity. native-defined SIZE_MAX read requests
may copy only eight bytes; huge borrowed logical lengths may be stored without
accessing them. raw copy leaves instead check the actual count, logical extent,
known aliases and non-wrapping spans before pointer arithmetic. these are selected
protocol guards, not arbitrary-pointer validation or an exhaustive automaton.

## independently replayed evidence

- native: `build/buffer-lab/oracle-buffer-rust-r1/report.json`.
- canonical archive: `build/buffer-lab/rust-parent-r1/report.json`.
- actual game-linked archive: `build/buffer-lab/rust-actual-archive-r1/report.json`.
- all replay **583** ordered records, **50** compiled definitions, digest
  `08a3143c0f6ad6dd6dbf29a5457e197fcfa05ec85a4cf4f04cde60af0edb7b38`.
- all 50 modes enter rust with balanced receipts. modes 37/39 always throw, so
  pending—not status-0 success—is required for those two. c++ return routes are
  separately observed. four normally exiting value-equivalent controls reject
  native bypass, zero receipts, wrong pending routes and getter bypass.
- native context assertions retain constructor, alias, wide-read, huge-borrow,
  copy-bound, partial-failure and reentry cases. only the c++-only foreign-throw
  invocation is removed: no c++ unwind through rust is attempted.
- 123 workspace tests per debug/release profile, fmt, strict c11 compile/link/run,
  c++ off/on syntax and selected-object symbol checks passed. panic containment
  is tested inside rust only. independent source review found no actionable
  findings; review is not runtime evidence.

canonical archive sha256:
`b79b108d421d79f6245b901a53e5b87c58c0f40df1c82f1c51081035ed5f78a9`.
actual game archive sha256:
`c879d281fb54fff17ac914213779872d3de13c3c87e994f29def5a3cecc4a46e`.
these are distinct artifacts; both have actual production-member replay.

## actual consumer gate

`build/behavior/buffer-actual-r2/report.json` passes two native runs before rust,
three exact framebuffer/state comparisons and inspected 1000×600 rust frames.
13 ordered native scopes exercise an owned loopback socket's **real typed
decoder**, a 1594-byte VersionedJson file, and multi-block ram/file BTree
commit/close/reopen/find. the raw tcp producer is an independent literal fixture,
not the normal typed sender. four sends force staged byte totals 1/5/14/20 and
packet counts 0/0/1/2; every actual receive/cursor/remaining/trim event is checked
before scheduling-dependent traces are projected. no one-read-per-send or
Universe handshake is claimed; only the accepted peer is OS-sockaddr evidence.

source-derived save sha256:
`cc477d827fe5ea55b4afe7fa957c7660bbecfd30e2acf117ca9a0fc69d5d54a9`.
its retrieved color drives normal Assets PNG rendering; decoded packet labels
`BUF-A|BUF-B` drive normal Font rendering. ram backing is initialized and bounded
before growth; padding, file bytes, independent key hash, payload and reopened
values are checked. fixture literals were frozen before actual capture.

`buffer-actual-r1` remains historical: its draft validator incorrectly required
ExternalBuffer's pointer constructor and size getter. source tracing in
`StarDataStreamDevices.cpp:130–147` shows default construction + reset and
`dataSize`, not those routes. the validator was corrected, permanent tests run,
and r2 reacquired without changing the implementation, reference, literals,
timeouts or tolerances.

fresh literal PCM decode/seek/EOF and corruption controls pass at
`build/bytes-audio/buffer-{cpp,rust}-r1/report.json`; this is not audible mixer,
Ogg, or a new Buffer-specific audio receipt claim.

**finite application qualification passed at source checkpoint `c233825b`.**
`build/behavior/buffer-actual-r2/qualification.json` binds all 19 current matrices,
18 historical sequences/54 unchanged RGBA frames, both production archives'
583-record replays, 21 actual-receipt synthetic corruptions, PCM and 12 CLI exits.
`check_qualification.py` independently replayed every current baseline/baseline
and baseline/candidate frame/state gate and all historical pixels before sealing;
its historical-count, artifact-binding and capture-input-identity corruptions
reject. current binary/assets/boot/config identities and overlays are checked
before/after; the earlier report/script remain archived beside the qualification. the previously
interrupted host-address-r1 remains unaccepted; fresh host-address-r2 and
DataStream-r1 pass. the six resumed Rust PNGs were inspected: green numeric-host
and orange STREAM consumers remain visible across occlusion/restoration.

this does not qualify the full engine, universal allocator/OOM/destructor,
performance, platform or sanitizer behavior. production selection remains off.
