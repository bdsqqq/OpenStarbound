# finite Rust IODevice controllers

## verified boundary

all 22 compiled `StarIODevice.cpp` definitions select Rust with `STAR_USE_RUST_IO_DEVICE`; default is OFF. the public header, object layout, vtables, atomic mode and ownership remain native. Rust owns source branches, loops, offset/index/count progress, callback ordering and error selection. no entire legacy controller is hidden behind a callback. virtual full-I/O leaves are retained only where the original byte wrappers themselves dispatch virtually.

native `StarIODeviceHost.hpp` retains ByteArray/String/exception objects and catches foreign exceptions before returning to Rust. only after Rust returns does the native wrapper rethrow the saved exception. size can classify/wrap a pending IOException, including EOF, with the original native cause constructor. unrelated exceptions retain identity. invalid callback statuses and ERROR-success contradictions are rejected. status 3 means contained Rust panic, not permission for a C++ unwind through Rust.

see `StarRustIODevice.h` for all 22 mode/26 operation numbers, scalar callback shape and selected guard contracts. prepared input views and numeric exclusions survive a virtual override destroying the external ByteArray. native protocol tests retain both destruction routes and the pre-capture output-alias/no-write assertion. constructor destination mode is never loaded uninitialized; destruction uses qualified base close and a fresh context. fresh-context same-owner reentry remains legal.

this is a **finite compiled-controller qualification**, not actual-game or full-engine completion. inline headers, device implementations and vendor ownership remain C++. no universal OOM, destructor, allocator, sanitizer, performance or other-platform claim is made. atEnd operand order is the calibrated Apple left-first profile only.

## current evidence

- native blueprint accepted before production mutation: `build/io-device-rust/native-before-r1.json` preserves the completed standalone verifier result, all prior input/artifact hashes and normally exiting EOF/no-wrap/zero-call controls (8/32/20 changed rows).
- canonical sole aggregate: `build/buffer-rust/target/release/libstar_engine_ffi.a`, SHA256 `4d5c64d0707cc1e4b0e6b61eca6d811b10aa79c2430f65dd68511d55999ca375`.
- canonical acquisition/execution: `build/io-device-lab/rust-acquire-r2/acquisition.json`, `rust-execute-r1/report.json`.
- CMake-built explicit aarch64 target aggregate: `build/io-device-rust/cmake-selector-r1/on/rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a`, SHA256 `6118bf41214c71c51f417b2b5466dea2bc8f17fcec3a94c7dddf2150aeb8996d`.
- its acquisition/execution: `build/io-device-lab/rust-acquire-cmake-r1/acquisition.json`, `rust-execute-cmake-r1/report.json`.

both archives independently pass native OFF baseline, two exact **8,021-row** candidate replays, six native callback-stage traces, strict linked c11 and assertion-active native protocol executions. all 22 Rust modes have positive actual attempts; each attempt balances success/native-pending, and independently observed C++ returned statuses match. resize is always pending; no invented success requirement is applied to it. actual counters cover modes, not all branches or all native source lines. canonical frozen row digest remains `02fb99395f74f0fdd7dd7f7e68073bb098eccb4e6afda05f6672405dcece43b8`.

three normally exiting controls run for each archive. native bypass and wrong returned pending status preserve all values but fail the actual Rust/C++ route checker. an EOF opcode substitution changes exactly eight scoped exception-class observations and is rejected by the frozen independent contract. crashes, compiler failures and timeouts receive no semantic-negative credit. a copied missing-archive binding is rejected before any native execution; four isolated synthetic receipt tests reject bypass, invalid returns, bool-as-number, missing and duplicate observations.

parent reran 128 workspace tests in each debug/release profile, fmt, native artifact tests and all IODevice synthetic tests. `cmake-archive-r1.json` binds default-OFF and ON configuration outputs and the actual production Rust.cmake build. this evaluates the extracted production selection rules plus real aggregate build, **not a full native project configuration or game build**. independent source review found no actionable findings; its earlier blocked round inspected nothing and earns no review credit.

## replay and provenance

```sh
python3 -B source/lab/io-device/candidate_stage.py verify --report build/io-device-lab/rust-execute-r1/report.json
python3 -B source/lab/io-device/candidate_stage.py verify --report build/io-device-lab/rust-execute-cmake-r1/report.json
python3 -B -m unittest discover -s source/lab/io-device -p 'test_*.py' -v
```

`candidate_stage.py` never builds Cargo or the game. compiler-only acquisition and corruption gates precede native execution. the preimplementation native profile is historical after integration, not silently relabeled current: unchanged bindings are rehashed; exactly three owned changes are checked separately (byte-exact native OFF body, exact CMake option/selection delta, exact aggregate export append). all current candidate sources, transitive headers, archives, compiled objects, maps, executable identities and streams are then sealed before/after. maps exclude the legacy IODevice archive object. the native calibration's old current-source gate intentionally does not accept the wrapped production file; use the new candidate replay for this revision.

## retained failures and limits

- Rust writer retained two failed new scripted-test revisions: missing END-path coverage assertion, then an incorrect zero-versus-one request-length expectation. the corrected fixture follows the unchanged source call arguments; no frozen native row/model or Rust algorithm was changed to fit it. no further scripted-test repair loop is authorized by this checkpoint.
- compiler-only candidate acquisition r1 failed: a wrapper called renamed `main` without arguments. renaming also removes C++ main's implicit return rule. the repaired observer never calls that helper; it calls unchanged frozen `corpus()`/`run()` functions. exact failed producer source and diagnostics remain in `rust-acquire-r1`; zero native executions/semantic credit there. r2 passed.
- the first broad synthetic run exposed a line-coordinate test still indexing the wrapped production file. its assertion now reconstructs and byte-compares the exact native OFF translation unit before applying the **unchanged frozen source-map coordinates**. no expected rows, model, golden, reference or domain changed. the subsequent 26-test run passes.

actual finite application qualification subsequently passed with fixture `e0f60d24`: see `source/lab/behavior/IODEVICE.md` and `build/behavior/io-device-actual-r1/qualification.json`. 19 current matrices, 19 historical sequences / 57 unchanged RGBA frames, actual fragmented TCP/save/BTree/PNG/Assets/Font receipts, fresh PCM/12 CLI and independent replay are separately bound there. the game-linked archive matches the qualified explicit-target aggregate by byte identity. this does not turn these kernel fixtures into application evidence or certify full-engine/universal behavior. earlier Buffer artifacts remain unchanged.
