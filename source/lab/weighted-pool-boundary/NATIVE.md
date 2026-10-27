# native continuation + c++ mock: finite lab, NOT production-ready

current accepted finite report: `build/weighted-pool-boundary-mock-r1/hardening-report.json`, sha256 `d8acc6633f4289aeb706458f632129709e72162916ac3171211a386aaf0e7c07`.

```sh
python3 -B source/lab/weighted-pool-boundary/verify.py --report-sha d8acc6633f4289aeb706458f632129709e72162916ac3171211a386aaf0e7c07
```

this replay is subprocess-free. do not rerun acquisition producers in their existing roots.

## verified

- all19 original root routes and all4 stages execute against the frozen24-byte C11 ABI. mock owns filtering, container iteration, unique retry/append loops and reciprocal-once/fma scan. native leaves own storage and full expressions.
- current combined executable reproduces all8 frozen original event traces EXACTLY, twice (continuation and native reference); scalar5 properties and original27-row rational corpus pass. real128 seeds/64 source draws compare against both current production and frozen reference.
- native exception_ptr catches ALL throws, including pointer sentinels, and rethrows only after each engine invocation returns. nested callbacks keep their own stack frames; no Item/native pointer crosses in a reply.
- current source passes lazy nondefault/move-only add/items/clear, implicit copy/move, sizeof/align/standard-layout parity, borrow aliases/native exception what, seed wrap/order, same-pool mutation after append, and cross-pool destructor reentry.
- actual19 malformed-envelope/capability controls pass. an added guard rejects a canonical BORROW result unless a native borrow callback actually ran. current combined fixture exercises its positive and isolated negative state.
- generator's OFF definitions reconstruct the exact original body after declared class-name/helper/include plumbing. original two fields remain `ItemsList m_items; double m_totalWeight;`; no lifecycle declarations or additional pool fields.
- public member/custom-sentinel containers and ADL containers run successfully.

all compiles use the same original all27OFF/-O3/-ffast-math flags; links use exact113 fresh read-only reference Core/extern objects and original libraries. compiler, linker, LTO, SDK/resource/header/provider pins precede acquisition. actual PID/PGID/OS-start/exit/reaping, stdout/stderr, -MD inputs and selected SDK traces retained. original large map filenames were decoded with surrogateescape; the final compact link uses actual `-t` SDK/provider trace instead of another symbol-heavy map.

## remaining review obligations — do NOT call this a full adapter

**verified generic gap:** private-friend-only begin/end works in the original native range-for but does NOT parse through this prototype's `using std::begin/end` continuation. actual positive original syntax and expected negative boundary compile receipts live beside `generic-gap-report.json`, sha256 `8704e53065f0174a884a2363868d86fe8ac43156fee7953febef0cccd6d02819`. the source is `friend.cpp`. production generic access/lookup must be solved, not constrained to List silently.

**source-traced protocol hardening gap:** `NativeFrame::permits` gates leaf IDs by root and validates fixed-zero/ARG arguments, but does not bound an adversarial READ_WEIGHT index. container/unique stage whitelists likewise do not reject append/next after cursor end. valid frozen mock policy never emits these requests; finite parity therefore does NOT establish arbitrary-request safety. add those native capability/state guards plus actual-adapter malformed fixtures before production/actual-Rust adoption. valid native `at()` out-of-range exceptions must remain native exceptions, not be replaced with protocol errors.

`std::function` owns lab callback closures and may allocate. no allocation/OOM equivalence or performance claim. typed nonallocating frames are preferable before production. no universal template/other-target/nonfinite arithmetic claim.

## source versions and failures retained

1. first outer acquisition was killed by the harness's10-second background timeout while lifecycle compilation was in flight. initial lifecycle.o has NO terminal compile receipt and is NOT accepted. no compiler survived the outer; a synchronous fresh-named compilation supplies accepted evidence. first outer remains failed, never relabelled.
2. synchronous producer sealed continue.stdout before appending its own REPORT line. original raw report remains unchanged; independent leaf composition checks the exact pre-REPORT prefix and binds final stdout. this is a report-sealing failure, not a native semantic failure.
3. later borrow-capability hardening changed ONLY frame.hpp; exact old bytes retained as `frame-before-borrow-guard.hpp` under the output root and pinned BEFORE editing. initial finite report/audit is historical at that source version, NOT a current-source replay. current `hardening-report.json` binds a newly compiled combined TU/current depfile, current real/proxy/lifecycle/corpus runtime, plus retained previous evidence. use `verify.py` for current replay; old `audit.py` will correctly reject live frame.hpp drift.

no production/header/CMake/Cargo/Rust/frozen native fixture edits, no commits, no game/full build, no cleanup. parent owns integration, actual Rust, catalog, Cargo, full build, game and cleanup. outputs stay under the unchanged64MiB cap; no archives or old TTL roots restored.
