# ttl cache: native baseline and proposed rust boundary

status: **native calibration only; rust and production integration NOT implemented.**
this is a review input, not a port-completion certificate. no cargo, cmake, game,
steam, storage, catalog or production source was changed by this unit.

## evidence and limits

VERIFIED: `StarTtlCache.original.hpp` is the exact current
`source/core/StarTtlCache.hpp`, sha256
`51942575d77806e99f783f18ba0edb0595a41e634605322d06a85b03a2514081`.
all 19 written definitions and both aliases are included unchanged. falsification:
`audit.py` compares the complete bytes, counts definitions, and checks the only
five macro substitutions in `native.cpp`. this is stronger than a method-token
comparison for this fixture: no header token was edited at all.

one executable instantiates the actual production ordered/hash aliases, plus
byte-identical classes whose names and `Time`/`Random` namespace references are
substituted AFTER all prerequisite headers have been included. no private-field
access, replacement lru implementation, added cache fields, or rewritten method
body is involved. **scripted classes do not prove actual production-clock ttl
boundaries.** real mode separately calls actual `Time` and `Random`, including
seeded smear and real negative-smear exceptions in lifecycle mode. native map
providers, loaded-image uuids, compiler/profile, complete SDK interface snapshot,
actual process start/status/stdio and input/product hashes are retained.

VERIFIED: `build/ttl-cache-native-r1/report.json` (exact current pin in `HANDOFF.md`):
626 rows x ordered/hash x two repeats; 68 lifecycle properties. the independent
python model stores ordered timestamp/value records and implements observable
cache behavior, not C++ parsing or native-output ingestion. eight isolated model
alternatives discriminate strict expiry, disabled refresh, zero sentinel,
pre-eviction, captured time, omitted filter ttl mutation, refresh precedence and
set overcapacity. the original `cleanup-snapshots-ttl` alternative omits the
setter side effect, so is a weaker control than its name suggests; supplemental
`audit.py` ALSO tests a true pre-filter ttl snapshot that preserves the setter
side effect and differs in expiry state with the same observed ttl.
four valid-format output corruptions reject. these are NOT compiled algorithm
mutants; dependency exceptions and producer/filter errors are actual native runs.
`audit.py` adds pinned-report, artifact-byte and boolean-exit verifier controls
without spawning any process. inspect `semantic.json` for each first distinguishing row.

VERIFIED, local ABI only: `real.stdout` reports ordered size/alignment 120/8 and
hash 136/8 on this arm64/libc++ profile. compile-time assertions compare ordered actual
and scripted class size/alignment and implicit lifecycle availability. lifecycle
traces show implicit move construction/assignment copy the underlying map, leave
the source populated, and produce distinct value addresses. do not replace these
with Rust-owned maps or custom move/assignment/destructor definitions. neither
finite observations nor matching size prove all ABI details on other platforms.

## source contracts that shape the boundary

locations refer to the preserved original header (identical production lines).

| location | non-obvious contract | ownership proposal |
|---|---|---|
| 80–85 | native default member construction happens BEFORE constructor body; then max-size setter, ttl, smear, update writes in that order | C++ implicit member construction; Rust constructor opcode orders dependency call and scalar writes |
| 88–125, 141–143 | accessors/setters must read live fields, not persistent Rust mirrors; max-size clamp/eviction belongs to LRU | Rust method dispatch; typed native field/dependency leaves |
| 128–138 | keys is a direct native list prvalue; values first copies LRU pairs into a range temporary, then moves each `second` into another native list | Rust owns the values traversal loop; C++ owns BOTH lists, iterator objects, append/move full expression, range lifetime and return NRVO scope |
| 146–152 | LRU promotion precedes update test; a timestamp exception leaves promotion intact; miss calls neither clock nor random | Rust owns null/update branches; C++ owns typed reference and exact timestamp assignment expression |
| 156–158 | `set(Key const&, Value value)` copies argument before body; `make_pair(timestamp, value)` COPIES the named lvalue; no TTL-side size enforcement | retain signature and entire native `m_cache.set(key, make_pair(Time... + Random..., value))` leaf; Rust orders the unconditional method operation |
| 166–168 | by-value `function` parameter, captured by reference; mutation/throw/reentry delegated through LRU | native filter object/lambda lifetime; Rust invokes filter-policy route; LRU controls dependency traversal |
| 172–179 | by-value Producer AND `[producer]` copy exist even on a hit; nested lambda has const call operator; `pair<int64_t,Value>(0,producer(key))` full expression and LRU insertion/unwind must stay native | Rust invokes native LRU get expression, then owns `first == 0 || update` and timestamp decision; no Rust producer or Value |
| 182–184 | no expiry policy on clear/remove; no clock/random work | Rust method route to LRU leaf |
| 187–199 | one captured currentTime even empty; filter precedes expiry; true refresh writes captured time with NO smear/random; false filter reads current ttl dynamically; strict signed `>` | Rust owns short-circuit branches, subtraction/comparison, refresh/erase policy; C++ owns captured scalar storage, native callback scope and typed pair |

`cleanup` does not call `ptr`/`get`; refresh does not promote. `set` can grow above
maxSize; LRU `get` pre-evicts even when the requested key would have been a hit.
negative `timeSmear` is NOT an invalid fixture domain (except `INT_MIN` negation):
actual RandomSource rejects reversed bounds before sampling, with exact
`(StarException) Maximum bound in randInt must be >= minimum bound!` bytes.
get can leave an inserted zero-timestamp entry after that failure; a subsequent
update-disabled get must still stamp it. don't prevalidate smear in Rust.

C++ leaves keep `Time::monotonicMilliseconds() +
Random::randInt(-m_timeSmear, m_timeSmear)` intact, including unary negation,
compiler-selected operand evaluation, copies, assignments and exceptional partial
state. the frozen optimized compiler observed clock before random; that is NOT a
portable evaluation-order guarantee. modeled clock faults skip random on this
compiler. `currentTime - timestamp` is a Rust policy operation only on the defined
C++ arithmetic domain; use an explicitly documented signed implementation matching
that domain. signed overflow and `-INT_MIN` have undefined C++ behavior, so tests
exclude them and make no universal claim. no silent saturation/domain widening.

## proposed c abi (design only)

use one versioned C POD request/result and one `noexcept` native leaf callback.
fixed-width operation/leaf/status enums; request `abi_version`, `struct_size`,
operation, opaque context; result tagged bool/u64/i64/opaque borrowed token.
validate both sizes/versions/operation/leaf tags; no C++ layout, bool, reference,
exception, function, iterator, pair, list, allocator or producer type crosses ABI.
pointers are native-only tokens, never Rust-owned allocations/references. frame
specialization per operation must not instantiate unused copy/assignment needs.

statuses: ok / captured-native-exception / bad-abi. a stack C++ frame owns
`exception_ptr`, native borrowers and results. each leaf catches locally and
records the original exception object, Rust stops and returns status, then C++
rethrows that SAME exception_ptr **after Rust returns**. do not construct a new
exception from `what()`, `longjmp`, unwind through Rust, or defer rethrow beyond
the native full expression that must unwind. no global single active frame: a
producer, filter or destructor can synchronously reenter either controller.
Rust must not hold an exclusive borrow into native cache memory across leaves.

### native continuations, not a hidden C++ controller

- constructor/get/ptr/cleanup decisions are Rust branches, not a whole-method
  native fallback. unconditional forwarding methods still route via Rust.
- `get` leaf binds the result reference from the ORIGINAL native LRU expression
  with `[producer]` and `pair(0, producer(key))`. its lambda temporaries finish at
  the original semicolon BEFORE Rust evaluates TTL refresh. no extra producer
  copy or eager Value assignment in a generic frame.
- nested native callbacks may enter Rust filter policy; on failure, that nested
  wrapper rethrows only after its Rust call returns, so the enclosing native LRU
  expression unwinds normally. its catch contains that exception before returning
  to an outer Rust controller. this nesting preserves native destructor/reentry
  sites rather than just returning a final error later.
- `set` retains its complete native `make_pair`/dependency-call expression. splitting
  timestamp, pair construction and LRU insertion into independent returning leaves
  can change argument evaluation, temporary destruction and partial state.
- `values` must use a C++ continuation that owns the original range temporary and
  iterators while Rust runs the loop. Rust chooses begin/end/append/advance; leaves
  perform typed iterator operations and exact `values.append(std::move(p.second))`.
  the method's named native result list keeps the original NRVO return scope.
  don't materialize another range/list in Rust or move from actual cache values.
- cleanup captures native currentTime once before entering LRU removeWhere. each
  native pair callback enters Rust cleanup-policy with live field reads. a true
  filter result bypasses expiry entirely; on false, read ttl AFTER the callback.
- dependency traversal belongs to the LRU component. TTL source has no written
  cleanup/removeWhere traversal loop; its policy is Rust, LRU traversal follows
  its existing selector. with TTL ON/LRU OFF this remains a disclosed native
  dependency, not an all-Rust cache claim. full combined candidate must also test
  LRU ON. don't force a default-ON selector or clone map traversal into TTL C++.

retain EXACTLY the original cache fields, order, access control, aliases,
allocator defaults, implicit copy/move/assignment/destruction. only stack frames
may be added. proposed Rust does not own or re-layout `m_cache`, timestamps,
values, map nodes or producer/filter storage. native keys direct prvalue and
copy/move traces remain gates, not optimization opportunities.

## remaining gates / falsification

1. parent reviews baseline source, actual outputs and this blueprint, independently
   replays `verify.py` and `audit.py`. no Rust implementation before that review.
2. implement substantial Rust method/policy/values-loop ownership and C++ native
   continuations with default-OFF integration; maintain compile-only support for
   nonassignable types and original constructor/alias contracts. this native unit
   did NOT exercise move-only/nonassignable instantiations or allocation failure.
3. actual selected-production native/Rust parity against unchanged model/corpus,
   both TTL/LRU selector combinations, all lifetime event traces and exception_ptr
   identities; test malformed ABI, nested entries, failing values/list/iterator
   operations and destructor reentry at more unwind sites. this unit has one
   insertion-copy unwind site and one values-prefix unwind site, not exhaustive
   allocator/copy-count exception-site enumeration or arbitrary filter invalidation.
4. actual game consumer fixtures (parent plans ImageMetadataDatabase, TilePainter,
   TenantDatabase), fresh production pair then real behavioral/visual/state gates.
   none of those applications were run here. no TTL boundary screenshot claim.
5. other platforms, sanitizers, OOM/concurrency, long duration, performance and
   universal equivalence remain unverified. valid non-invalidating filter reentry
   is exercised; arbitrary erase/clear of the currently traversed iterator is not
   promised valid or modeled.

## retention

one live primary executable/object/map; no alternate runnable game or cache pile.
initial 608-row success is historical in `initial-calibration.tar.gz`, exact-member
manifest `initial-archive.json`. one later UTF8-map runner failure is preserved in
`failed-map-decode.tar.gz` and `failed-map-archive.json`, including sources and
actual completed command receipts. both were decompressed/hash-verified BEFORE
owned originals were pruned. corrected map reading is surrogateescape; no model,
header, flags or accepted expectation was changed to resolve that failure.
`pre-unwind-strengthening.tar.gz` retains the intermediate 626-row acquisition:
its destructor hook could fire before exceptional unwind. final probe strengthens
that hook with `std::uncaught_exceptions() > 0`, without changing header/model/flags.
exact archive manifest is `pre-unwind-archive.json`; do not retag the earlier hook
as unwind proof. auditor takes the independent final report SHA as its argument,
so no circular post-acquisition source edit is required.
all archives and the current fixture remain below the 96MiB cap.
retain these bounded bytes for parent integration; no global archive restoration.
