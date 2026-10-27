# ttl native calibration handoff — 2026-10-27 17:00 utc

**review-ready; native baseline only. no rust port or application qualification.**
parent can review/integrate now; this child has no active process, build, cargo,
game, delegate or pending writer. owned changes are ONLY `source/lab/ttl-cache/**`
and `build/ttl-cache-native-r1/**`. no commits. original user prompts and latest
cleanup direction were read FIRST from newest plan top; migration skill read.
`dig` was not applicable: source/recipe were known direct lookups, no competing
incident explanation needed. no nested agents or closed acquisition-runner import.

## replay and exact pins

from `/Users/bdsqqq/www/OpenStarbound`:

```sh
python3 -B source/lab/ttl-cache/verify.py
python3 -B source/lab/ttl-cache/audit.py cba3b3c84acc2128bd043400cabd6ed2ebf35fcdde37e6d36e2a870bc7926674
```

both independently executed after final acquisition; both PASS. these commands
spawn NO subprocesses. do not re-run `run.py` into an accepted output root: it
refuses an existing report. exact compiler/link/native argv, cwd, env, stdin,
timeout, PID/PGID/start, normal exit, tool before/after and stdio hashes are in
`build/ttl-cache-native-r1/{name}.{plan,started,receipt}.json` and stdio files.
original acquisition command was `python3 -B source/lab/ttl-cache/run.py`, with
stdout/stderr to `build/ttl-cache-native-r1/acquisition.log`.

| current artifact under `build/ttl-cache-native-r1/` | sha256 |
|---|---|
| `report.json` | `cba3b3c84acc2128bd043400cabd6ed2ebf35fcdde37e6d36e2a870bc7926674` |
| `audit.json` | `b31d58975c038fe8c9ae81515d9a150de7de2815619d0057022d09d5d3a61b64` |
| `retention.json` | `48f9adbaf8aa51e174344bd6b3611c5b6cbd9a11d20a4ec72cbed0b3ee130bac` |
| `inputs.json` | `29c56aa41279eacb31e07dc88815d40a8399f4f301cf19ffa62bfc439a2bdd4c` |
| `recipe.json` | `9639bd43c5c4b544b289835add6ef60e49481cc450bf4ba30d8a6a90fab71f1c` |
| `sdk-before.json` (after is equal) | `19ba706dd0c24cf825b38d91b013ed52799b7c31fcec1ee438fb60758e73aba5` |
| `sdk-consumed.json` | `fd1f805f92e67d695d4a042497ca2a4e507f30be583e6b5309cecf133d283fd6` |
| `native` (3,513,960 bytes) | `2d791b54d6c7acad2dd7c982462023dd7f6632cabf653ea692c0d52af3ce0e57` |
| `native.o` | `c2528aa3625e719795bca83c1361901373ed1a9803605b5dd0f968ae31ed9cd5` |
| `native.map` | `9034a5e2af4ccb78eefd91f3e9e2b01742772822fa7e763899edf79ca2e800ff` |
| `lifecycle.stdout` | `ee9fed2906e6ff0db3c30f413f0f63167b3ba8aafdda72bd5783b379b854ed99` |
| `real.stdout` | `8180f9f1dea5fffe2dcd403fcdb8afa85ffb4fb22d1af45ac922fbad664db293` |

source pins (all under `source/lab/ttl-cache/`, also report-bound):

- `StarTtlCache.original.hpp`: `51942575d77806e99f783f18ba0edb0595a41e634605322d06a85b03a2514081`
- `native.cpp`: `c996e05d918ec0aea1faf8b5e9bd44192b6fb4e8ca36c93be249ce744c1dad0c`
- `lifecycle.inc`: `ab7c1d49e8378973b97e7479e3bc2efea23d067d2e052373a832171462abb1c8`
- `model.py`: `0728fbcbda6995f48e3ed7ad2611a39493ceef60effc613987f66a3da9bb61c2`
- `run.py`: `cb016b8594339683ba7109205fd623e67d99035e9196f3809cab44f7fdaecc48`
- `verify.py`: `0d9d794b7ba4bbfecd5221cfa9b65b3231bc30e63f58012b4037617b56b1848f`
- `audit.py`: `40c7b35232abc58ef6a3253e22f3a313c95a2f843c7c3c82aad90d1dcb0923a6`
- `BLUEPRINT.md`: `5979e61d32b077859f517c0ba3581a44206a34e7f6aa11452a45a1191e8feca4`

this handoff was written AFTER acquisition; it is not retroactively added to that
input map. all participating sources above remain byte-identical to final run.

## what was actually tested

VERIFIED (`report.json`, `semantic.json`, `audit.json`):

- 626 rows x ordered/hash x two actual native processes = 2,504 exact modeled
  public-state rows. all nineteen written methods are included and exercised;
  keys/values/getters are also observed after each command. aliases use actual
  production LRU implementation; reference 26 selectors OFF.
- real production Time/Random smoke runs both actual aliases. scripted clock and
  random are namespace substitutions in byte-identical header, not a new TTL
  implementation. deterministic strict boundary, zero sentinel, refresh/no-refresh,
  negative TTL, smear, dynamic TTL/captured cleanup time, policy precedence, LRU
  pre-eviction and size clamp are **scripted dependency calibration**, not actual
  production-clock timing proof. `native.cpp:20–35` makes the distinction explicit.
- exact dependency calls/arguments/order, counts, producer/filter events, errors
  and post-error state are modeled. clock-before-random is observed for THIS
  clang/profile, not portable C++ sequencing. clock/random failures are scripted;
  negative-smear Random exceptions are ALSO exercised against actual Random in
  lifecycle mode. `RandomSource::randInt` actual provider is pinned by map/object.
- 68 native properties and four complete 216-event lifetime traces. actual/script
  ordered traces are exact; actual/script hash traces are exact. producer copies
  still happen on hits; actual const producer call, native pair/list copies/moves,
  argument-copy-before-body, pointer identity, copy independence, source-retaining
  implicit move/assignment, native assignment partial state, prvalue destruction,
  insertion-copy unwind/destructor reentry, values-prefix unwind and balanced
  live objects are exercised. saved exception_ptr identity survives producer and
  filter throws (`lifecycle.inc:35–66`).
- final insertion-unwind hook is gated on `std::uncaught_exceptions() > 0`.
  actual output sequence for ALL four types is `move:888,destroy:888,move:888,
  copy:888,destroy:888,unwind-destructor-reentry,destroy:90,destroy:888`.
  the callback removes unrelated key 9 WHILE unwinding failed native insertion.
- eight semantic model alternatives + four well-formed stream mutations reject.
  original `cleanup-snapshots-ttl` control name was too strong: it omitted filter
  mutation. supplemental audit uses a REAL pre-filter ttl snapshot preserving
  setter effect: row105 has ttl2 on both sides, native empty vs wrong four entries.
  report-pin, wrong-artifact and boolean-exit controls also reject at named gates.
  these controls are isolated memory/model overlays, NOT compiled native mutants.

VERIFIED provenance (`recipe.json`, 1,142 input hashes, process receipts):
canonical current `reference/cmake` 113 core/extern objects and existing offline
libraries; no source recompile beyond the ONE owned fixture TU. Apple clang21
`clang-2100.3.34.2`, arm64 macOS27.2 build26B5112a, native `-O3 -ffast-math`,
libc++, gnu++17, reference sysroot MacOSX27.0.sdk → physical MacOSX.sdk. no profile
or selector changes. 3,683 SDK interface files plus settings/symlinks captured
before and after; 35 actual map-consumed interfaces reconciled. 544 actual loaded
images have native dyld LC_UUID receipts, including loaded libc++/libSystem.
this is a local static/runtime-UUID witness, not hostile runtime attestation or
an extracted-byte hash of Apple's dyld shared cache.

final 16 actual commands all normal exit0, no timeout, no lingering owned group.
compile PID14072; link14078; real14083; lifecycle14087; four semantic runs
14090/14091/14092/14093. corresponding start receipts were written BEFORE waits.
process snapshot at16:57UTC had no compiler/native fixture/Cargo/game processes.

## ABI proposal to review (NOT implemented)

full ownership/exception rationale is in `BLUEPRINT.md`. concrete proposed POD
shape, for discussion rather than a committed ABI:

```c
struct TtlLeafReply { uint32_t status, reserved; int64_t i64; uint64_t u64; void* borrowed; };
typedef uint32_t (*TtlLeaf)(void* frame, uint32_t leaf, int64_t i64,
                          uint64_t u64, struct TtlLeafReply* out);
struct TtlRequest { uint32_t version, size, operation, reserved;
                    void* frame; TtlLeaf leaf; };
struct TtlResult { uint32_t version, size, status, reserved;
                   int64_t i64; uint64_t u64; void* borrowed; };
```

C++ callback adapter is `noexcept`; status is ok/captured-native-exception/bad-abi.
validate version/size/tags/reserved fields on BOTH sides; actual field layouts,
integer widths and offsets need C11/C++/Rust assertions before implementation.
no Value/List/pair/function/iterator/exception representation crosses this ABI.
opaque borrowed tokens never become Rust references or owned allocations.

proposed method operations: ctor, ttl read/write, smear read/write, update
read/write, max read/write, size, keys, values, ptr, set, remove, removeWhere, get,
clear, cleanup. nested operations: removeWhere predicate and cleanup predicate.

explicit native leaves (each narrow, with operation-specific stack frames):

- read/write existing scalar ttl/smear/update fields, dependency max/size, native
  setMaxSize, remove, clear; no independent C++ method-policy branch.
- `LRU_PTR` binds/promotes actual pair pointer. Rust chooses miss/update branch;
  `STAMP_PAIR` executes the exact native timestamp assignment full expression.
- `SET_EXPRESSION` executes the ENTIRE original make_pair+LRU.set full expression.
- `GET_EXPRESSION` executes original LRU.get and original `[producer]` const lambda
  with `pair(0, producer(key))`; stores borrowed pair pointer AFTER correct native
  reference binding. Rust tests zero/update AFTER original semicolon/destruction.
- `PAIR_TIMESTAMP_READ`, `PAIR_TIMESTAMP_WRITE`, `PAIR_VALUE_BORROW` operate on
  that live native pair, without copy/assignment requirements on the Value.
- `KEYS_PRVALUE`: Rust selects the direct-return action; C++ then returns the
  original dependency keys prvalue. no ABI list holder or extra list move.
- `VALUES_RANGE_SCOPE`: native continuation owns original copied pair-list
  range temporary, native iterators and named result List. Rust owns loop tests,
  append choice and advance order; native leaves compare/advance iterator and
  perform exact `append(std::move(p.second))`. native original NRVO scope retained.
- `CURRENT_TIME_ONCE` captures cleanup currentTime; `FILTER_PRESENT`,
  `CALL_REFRESH_FILTER`, `CALL_MUTABLE_FILTER` invoke native function objects
  without added copies. Rust owns refresh-vs-expire branch, strict signed expiry
  comparison and dynamic post-filter TTL reads; no smear on cleanup refresh.
- `LRU_FILTER_SCOPE` enters native dependency removeWhere with original native
  capture lifetimes and nested Rust predicate route; traversal belongs to existing
  LRU component. TTL's only written traversal loop is values and MUST move to Rust.
  TTL ON/LRU OFF is disclosed native dependency mode, combined candidate also
  tests LRU ON. no forced default-ON selectors.

all native leaves catch locally and save the ORIGINAL exception_ptr; Rust returns
status; C++ rethrows AFTER Rust returns, inside the native continuation that must
unwind. nested callbacks/producer/destructor reentry require nested stack frames,
not singleton TLS and not a Rust exclusive borrow across callback. no additional
cache fields, changed member order, user-provided lifecycle methods or mirror map.

## failures, coverage correction, cleanup

- initial native/model acquisition passed608 rows. preserved exact source/report/
  executable bytes in `initial-calibration.tar.gz` (2,518,176 bytes). 18 targeted
  corpus rows were then added BEFORE enlarged acquisition to discriminate
  captured time and dynamic TTL; no old row/expectation or production/LRU model,
  header, flags or domain was fitted to native output.
- ONE unexpected runner failure: raw native map is not UTF8. native compile/link/
  smoke/68properties had passed; Python strict map decoding failed. exact evidence
  in `failed-map-decode.tar.gz` (3,166,216 bytes). fixed raw map transport to
  surrogateescape and regex spelling. next run passed; no tolerance/domain/model
  change. no repeated failed-approach budget reset.
- inspection found the first reentry hook could run during normal temporary
  destruction rather than unwind. intermediate success is preserved honestly in
  `pre-unwind-strengthening.tar.gz` (3,220,416 bytes). strengthened ONLY probe hook
  to require active unwinding, then reacquired the final current fixture. this is
  a coverage correction, not relabeling old evidence as stronger proof.
- each archive's exact members were decompressed/hash-verified BEFORE own obsolete
  files were pruned, then all309 archived members reconstructed AGAIN after final
  acquisition. no tree restoration or historical inode/ctime identity renewal.
- one live native fixture only. retained output before this handoff was
  25,172,124 bytes (~24.0MiB), allocated24,876KiB, all three archives INCLUDED,
  versus hard96MiB output cap. no gigabyte candidate generations.
- mandatory global retention gate at16:57UTC PASS: archive16,413,511,680 bytes,
  live2,424,279,040 bytes, repository19,017,292KiB. current game pair untouched.

## remaining gates / next parent action

parent read full source and actual stdout/map/receipts, independently replay and
review proposed boundary BEFORE Rust work. then implement substantive Rust
branches/policy/values traversal plus native full-expression continuations,
default OFF. repeat unchanged model/corpus/native traces against actual Rust and
selected production class, ABI negatives, nested/reentry/unwind gates; only then
actual ImageMetadataDatabase/TilePainter/TenantDatabase consumer/game evidence.

unimplemented/unverified here: Rust, production selector/adapters, actual game
consumers, real-clock exact boundary proof, compiled native algorithm mutants,
exhaustive throwing producer/filter-copy sites, cache assignment failure sites,
nonassignable/move-only instantiations, allocator/OOM, arbitrary iterator-
invalidating filter reentry, sanitizers, concurrency, other platforms and universal
performance/equivalence. no helper pass is counted as a completed TTL port or the
39-module migration. keep this bounded evidence for integration, not a new game
pair; parent owns catalog/plan/Cargo/fullbuild/checkpoint integration.
