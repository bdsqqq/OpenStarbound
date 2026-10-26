# defined empty copy

zero-length append retains resize and performs no memory operation. this defines behavior for null/zero inputs formerly passed to `memcpy`; it does NOT claim equivalence on legacy undefined behavior or expand the frozen 987+14 corpus.

VERIFIED: diagnostic `build/behavior/byte-array-diagnostic-r2/run-r1/process.log` traced mode6/op12 rejection to copying an empty `NetElementDynamicGroup<NetHumanoid>` change while creating the character menu. the repair keeps COPY_IN role/offset/logical-size/capacity and context/output guards; nonzero spans and memcpy remain unchanged. Rust/archive/API/layout and COPY_OUT are unchanged.

## regression evidence

`empty_copy.cpp` and `empty_copy_leaf.cpp` were frozen before production mutation:

- public sha256 `b1f7436aa382ec384ed4be18b670143ce9a3f78d1d1f85ec2572fd2dc11f6aa0`
- leaf sha256 `db8a6d6261cf6c2b95691e5ed20e2cd1d045a595f85106fe5a5d2f6e3e432c8f`

parent execution against coherent r4 candidate: eight empty cases fail with protocol exception; self-copy and nonempty copy pass. raw zero-copy leaf fails1 while its independent existing-guards control passes. receipts: `build/behavior/empty-copy-pre-{rust,leaf}-r1/`. no old native null-memory or sanitizer equivalence credit.

fresh coherent r5 OFF/ON builds pass all ten public cases; ON leaf passes zero/no-write, positive copy and rejection guards. receipts: `build/behavior/empty-copy-post-{native,rust,leaf}-r1/`. replay using `empty_copy_run.py --cmake <profile>/cmake --output <fresh-build-path> --expect post`; add `--leaf` for the ON leaf.

fresh113-object OFF/ON compiles and independent seals pass the unchanged corpus/repeat/protocol/all56 routes/native-bypass rejection: `build/byte-array-rust/empty-copy-run-r1/report.json`. only the unchanged CMake archive b406814094cce5c17e9705eaff12facbf3a17a67083b43b8decfdbabc75fa880 is qualified against this repair; not a new two-archive claim. exact source reconstruction and malformed-repair tests retain the older empty-fill repair and all other checks.

## application remains open

r5 reference/repeat capture succeeds; candidate reaches local-server login and ship-world creation but times out at phase0/stage0 before any accepted frame (`build/behavior/byte-array-actual-r3/candidate/process.log`). no application/save/network/visual qualification. fresh PCM WAV/seek/EOF/corrupt-expectation controls and12 CLI executions pass separately. finite spans are not arbitrary-pointer/lifetime/OOM/platform/performance proof; SDK link stubs remain path-only.

sampling an already-ended process yielded no stack; a subsequent bounded live sample timed out. coherent diagnostic-r3 records hot callback backtraces in `WorldStorage::writeTileSector`/`ServerTile::write` through nested DataStream/IODevice/Buffer/ByteArray callbacks. this locates activity, not a production performance measurement or proof that it causes the timeout. instrumentation has no ordinary acceptance sidecar; capture limits remain unchanged.
