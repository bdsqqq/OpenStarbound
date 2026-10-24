# sha256 evidence — 2026-10-24

host/worktree: apple silicon macos, `/Users/bdsqqq/www/OpenStarbound`; frozen base `19506189e9d851b36b7c44ecf7461ebd10dfa3f6`. the initial worker pass below covered only `source/lab/sha256/**` and `build/sha256-lab/**`, without native/game execution. parent integration evidence follows separately.

## verified executions

final checker/harness revision is bound by `build/sha256-lab/{cpp,rust}-final-r2/report.json`; both repeated baselines passed identically with undefined-behavior sanitizer and real native production flags. no failed repair attempt. older artifact directories are historical, not the final evidence.

- cpp: **26,269 cases / 3,177,853 checks**, 11 rejected controls.
- rust: **26,270 cases / 4,005,844 checks**, 13 rejected controls. main-thread success counts `[152018,285522,256847,104836]` for init/update/final/oneshot; separate child thread asserts isolated init count.
- controls: unauthorized define, unpaired archive, outside output, digest tamper, semantic state tamper, wrong round constant, wrong endian load, wrong padding bit, 64-bit length carry 'correction', cached finalization, frozen provenance corruption; rust additionally receipt suppression and scoped count tamper. algorithm controls compiled and exited through `COMPARISON`, not crashes or compile failures. carry correction rejected on seeded case 26045 (see per-run log for authoritative index).
- 261 independent hashlib rows pass; published `abc` and 56-byte long-example anchors pass. official document downloaded read-only with `curl --max-time 30 --max-filesize 1048576` from https://www.rfc-editor.org/rfc/rfc6234.txt; sha256 `8f39f02a57bfd1da15634706724a585766e6223f77ecdaf243cad16cd3a1aa1b`. exact citations/extracted facts in `published.json`; document retained only under build output.

seeded legacy wrap digest: `04cef6a882b6544e0417af1704f1e98cc71c13b2e7b67ca2ff0eb3a35424bfe7`.
independent hypothetical 64-bit-length digest: `d3c418ca3cf92352ffc3dc692eeefde7a2b37aa4a05028d032913d08c220f7f5`.
this is a seeded-state counterexample, not a 512 mib real-message standard vector.

## identities

- frozen cpp `8a4d67bbbd7e6bcc54356dbc59429cf16076064a6b8c4b5427363df79beb5b3b`.
- frozen/public hpp `2f8d6ec062ad777a099ce669a60a313e7d0ffdc865496589b7810033974fec5b`.
- namespace/import-only full cpp `eca0c586bd7e7ac98c6da36d00ff847ea8763210efce798d9f1727b590b2024c`.
- checker `6829f80d2d5eae36b1a544df44e351f7cef35a52124c5353f1ec7d24f6beb69e`.
- harness `dafbb77c1fd60cf12f75afca0d735b903905fc58fed4cf95133059492d4703c7`.
- tested production cpp `a1b8c41670ad34f1912a40c4fd0dbbd2a8fc815170dd151856966585e8c60d1b`.
- linked aggregate `build/sha256-rust/cargo-target/release/libstar_engine_ffi.a`, sha256 `16bf776052cc17e42b9b033ce11d5ad1c8d2d9d096b04adc553f4e3aee7c27c8`.
- cpp executable `535f86a2e37effe1e06d98225c42dba39a3361947840208422665570fe4f8c50`.
- rust executable `0a80037fdab24018445379a1015717e4b7eb54c5c4c414fb726454eba22ceb95`.

full flags, commands and additional source/archive/manifest hashes are in each final report. replay commands and runtime/source-only limits are in `README.md`. no class allocation/ordinary utf8/bytearray facade runtime, database, actual assets/game, performance or security claim. parent owns the single migration handoff; this file records laboratory evidence, not a second task tracker. laboratory sources are fixed at handoff.

## parent integration — actual game

VERIFIED on apple M2 Pro / apple clang 21 / macOS 27 SDK. primary independently replayed the standalone C++/Rust labs into `build/sha256-lab/{cpp,rust}-primary-r1`: the same cases/checks and all negative controls pass. primary workspace debug/release has 30 passing tests; formatting, 63 behavior/provenance/proof tests and eight catalog drift/negative tests pass. source review found no actionable ABI/legacy-state defect, not a security certification.

normal Assets construction supplied exactly **2,736,154 bytes in 97,991 ordered chunks**. these are actual sorted lowercase asset paths and serialized file/patch sizes, NOT file contents. the unmodified digest inputs are concatenated beside the actual pushes, bounded to 32 MiB, and retained outside the asset set. Python independently replays the exact transcript, verifies canonical encoding/chunk sizes, and requires reference/candidate transcript identity before digest comparison.

- actual digest: `c173c3b5bce81024975e9c1305f0a7a6c84b55bb0a3a0a459ddc22e04a6c0b51`;
- actual Rust Assets receipts: `[1,97991,1,0]` for init/update/final/oneshot; C++ all zero;
- actual RAM `BTreeSha256Database` performs seven key operations on `behaviorlab-sha256-key`, including replacement, close/reopen with a fresh database object over the same Buffer, lookup, removal and absence check. values contain embedded NUL bytes (`alpha\0one`, `beta\0two`). Rust receipts `[0,0,0,7]`; C++ all zero. observed values/counts, not fabricated expected values, enter the capture.

all five matrices passed two independent C++ baselines before candidate comparison, exact native state/full-frame pixels and restoration:

- `build/behavior/sha256-actual-r1`: SHA-only Rust, other backends C++;
- `build/behavior/sha256-combined-r1/final-comparison`: SHA plus verified lighting/traversal/encoding Rust, experimental line queries OFF;
- `build/behavior/sha256-{lighting-room,raycast-room,encoding-room}-regression-r1`: existing scene gates with all four verified backends enabled.

primary inspected the SHA-only lit/occluded/restored PNGs: normal room illumination changes and restores; the frames are visual regressions, not evidence of digest correctness by themselves. combined SHA frames equal those inspected arrays. encoding regression's colored foreground pattern was inspected; all three historical C++ reference arrays for lighting/raycast/encoding remain unchanged from the encoding checkpoint. no image masks or tolerance changes. successful `passed` reports retain automatic `parityCertified:false`; performed inspection is recorded here rather than weakening that gate.

native binaries, SHA256:

- C++ `bdfdda7264729444ff2b651faae85d3172a0d326e3555b785eaf43448327cd3c`;
- SHA-only `0e7032e44f3438cb76b50e90c10d8b8197d6e00615be42fec73579d0b6702d30`;
- combined `2d9243b9ed61c1ae2e1e80145fc1d5b5f8f2d8228fe00b50ae5c07f4dfa19b54`.

all three canonical source-map fingerprints: `523214cb9859be4cb1bc99094449798582b2536ffa83fe4f67c37800df138c2a`, SHA256 of UTF-8 `json.dumps(source_files,sort_keys=True,separators=(',',':'))`. before/after receipts bind compile inputs/compiler/cache/link identities and binaries. source was the working tree based on `19506189`; these local receipts are not reproducible-build or complete external-dependency attestations.

replay native builds with `scripts/build-behavior-lab.sh sha256` / `sha256-combined` in the Nix build-tool shell, then `scripts/behavior-lab.sh run --scenario sha256-room` with explicit packed.pak and fresh build-contained output paths. captures use the normal final framebuffer (1000×600 RGBA8, Apple OpenGL 4.1 Metal), sentinel-marked isolated storage and no remote publishing. the old pre-existing smoke process PID92430 was not touched.

limits: finite host/domain evidence, not the entire compression/crypto module. no authentication interoperability, cross-backend loading of existing databases/user saves, other-platform, huge real-message, allocator-fault, performance or cryptographic-security qualification. database reopening here is within one backend, not a cross-version persistence claim. preserve legacy 32-bit length and destructive-finalization semantics; do not silently replace them with standard-crate behavior.
