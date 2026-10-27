# production ttl integration — terminal handoff

status: TERMINAL / review-ready; finite compile/configure gates PASS at 18:43 utc. parent acceptance and fresh production runtime remain next.
workspace: /Users/bdsqqq/www/OpenStarbound; base checkpoint 6630f39c.
hard stop 18:50 utc; no automatic extension. no owned process remains active.

## scope

only production writes: `source/core/StarTtlCache.hpp`, new
`source/core/StarTtlCacheHost.hpp`, `source/CMakeLists.txt`.
new harness sources: `source/lab/ttl-production/**`.
all output remains in `build/ttl-production-r1/**`; 9,708 KiB allocated at
18:43 utc (<96 mib; final budget receipt below).
parent/fixture changes elsewhere are disjoint and were not edited or discarded.
no cargo, full/core/game build, game execution, steam/storage/remote changes,
archive restoration, nested delegate, or commit. no second rust crate/runtime.

## source contract and finite evidence

VERIFIED: selecting the OFF branches reconstructs the ENTIRE original header
byte-for-byte after removing only the approved private type-only observer friend.
this covers bodies, aliases/default allocators/default arguments/access control,
field order, and absence of explicit lifecycle definitions. original bytes at
`source/lab/ttl-cache/StarTtlCache.original.hpp` remain unchanged. prior native/lab
participating-header/CMake closures are explicitly historical, not rebound.
`HISTORY.md` was written before production edits.

VERIFIED: all 19 production ON method bodies match the frozen accepted boundary
bodies modulo whitespace and production class name. the production host is an
exact derivation of the frozen host: namespace/error names, utility include,
const dispatch for MAX/SIZE/VALUES, canonical incoming reply-tag validation
(with the exact frozen Rust leaf-output sentinel allowed), and reference/list
zero-payload validation. no native whole-method controller or added cache state.
keys stays a native prvalue; values keeps its named list/NRVO with the copied
range and iterators ending in native scope before return. set retains the entire
make_pair(Time+Random,value)+LRU.set expression; get retains by-value producer,
const `[producer]` lambda and pair(0,producer(key)) at the original semicolon
before Rust refresh. native exception_ptr capture/rethrow stays inside native
owners AFTER nested Rust returns. leaf15 is VOID0/native borrow only; PTR/GET
root is REF0. new logic_error paths diagnose ABI corruption, not native errors.
these are source/compile claims, NOT a new runtime/lifetime proof.

VERIFIED on arm64/libc++ and the actual existing native flags: three fresh
object probes compile all production methods for ordered/hash aliases plus a
custom dependency whose nonconst MAX/SIZE/VALUES overloads are deleted. unused
set/value-assignment/copy constraints do not instantiate during move-only and
nonassignable construction/getters/ptr/keys/cleanup/clear. sizeof/alignment,
all four member offsets, implicit lifecycle traits and actual copy/move use
compare against an original-byte baseline with ONLY the observer friend added.
the generated observer header derivation is checked exactly; no original file
was rewritten. `sb_ttl_run` is undefined in TTL-ON objects only; combined ON also
has `sb_lru_run`. no object was linked to old Core objects or called runtime.

VERIFIED: two fresh configure-only profiles use existing offline SDK/libraries
read-only. default profile has all 27 selectors OFF without passing selector
values; only-TTL profile has TTL ON and the other 26 OFF. exactly one existing
aggregate build rule is emitted only when needed, and the TTL compile definition
propagates. no Cargo/build target ran. combined game candidate 26 ON except LINE
OFF remains a parent gate; no selector was forced ON by default.

`verify.py` replays exact source/host derivation, consumed header/tool/artifact/
stdio/receipt pins, profiles, flags and root symbols. seven isolated falsifiers
reject changed OFF write order, changed default allocator, boolean PID/exit,
extra LINE ON, missing selector schema and different optimization flags; positive
replay passes again afterward. no model, native domain, header, flags or golden
was fitted to a failure. receipt PID/start/PGID/normal completion, command argv,
environment, timeout, source/profile/artifact/stdio hashes are durable.

## coordination and retention

Lru friend release: explicit user-message release from TTL-room owner; SHA256
87d72f7b1dfca06040a2f3193e7c1920280d1f358beae9bf9727c7e319097577.
final object compilation ran AFTER release: native PID29414, TTL PID29426,
combined PID29436, all normal exit0 with EMPTY compiler stderr; final read-only
pinned replay PID30835 also normal exit0. nine fresh object/dependency/symbol
commands plus the two retained fresh configure-only commands are the final
11-command witness (not 11 game/native runtime runs).
initial object probes preceded fixture task creation; their nine command receipts,
three object/dependency/symbol sets, source snapshots and initial successful
logical verification are preserved as HISTORICAL, not called final coordinated
closure. exact checkpoint Lru bytes are retrieved read-only, hash-matched to the
old dependency witness, never restored. `pre-friend-objects.tar.gz` was exact-
member/hash/size reconstructed BEFORE pruning owned originals, then rechecked
after pruning. only one current object set per required profile remains.
archive SHA256 e43a10f6bebab8a6ece1392ea924df747ceb5188021e596e69a61d0ecd181f6b.

no unexpected compiler/configure failures. configure diagnostics are retained:
optional PkgConfig absent, disabled-PCH reuse warnings, and unused explicit tool/
preset variables; these are not hidden or called warning-free configuration. one initial edit request was rejected
for nonunique oldText BEFORE mutation; corrected unique full method spans were
then applied. all older TTL outer-producer exit1/PID UNKNOWN and failed first
finalizer control remain failed and immutable. accepted old lab composition is
historical, not a renewed producer whole-run pass.

cleanup: 18:43 budget PASS: archive16,413,511,680 bytes,
live2,724,782,080 bytes versus16GiB/4GiB caps; repo19,315,488KiB.
owned provisional objects were compactly preserved/reconstructed before pruning;
there is no alternate runnable game/cache fixture. final budget/measurement
receipts are `build/ttl-production-r1/final-budget.json` and
`build/ttl-production-r1/final-measurement.json`. two small configure-only trees and three object files
are justified current evidence, not runnable game candidates. unrelated data and
all existing archive manifests/blobs untouched.

## replay and remaining gates

report `build/ttl-production-r1/report.json` SHA256 fdb0ce857e78df0f8e9affe71ffe44d1d6bbc59e7dcd0313f78fd05d7ef3534d.
verifier source SHA256 dba384b0240358ddd92b3fdb8effe69b4bfe66c235a5cf7222d656803bcfbc3c.
production source pins:
- StarTtlCache.hpp: f5e455a98035ead719fbcd7624711a3c767069c3ad75dbadc5cd5e4248f20ec0
- StarTtlCacheHost.hpp: e925f0348c0861e63a0dbd302a67d4dbfab5b6403a9082201c0e55917366203e
- source/CMakeLists.txt: f8ca245661297d1ee3f6423bc07d01f918a301de0945910eb8cd33b55235ad01

```sh
python3 -B source/lab/ttl-production/verify.py --report-sha fdb0ce857e78df0f8e9affe71ffe44d1d6bbc59e7dcd0313f78fd05d7ef3534d
```

acquisition commands, already completed (do NOT overwrite existing receipts):
`run.py prepare`, `run.py objects` (historical pre-friend), `run.py configure`,
then `refresh.py` only after explicit Lru source-stable release. normal replay is
read-only and does not acquire native/game products.

parent next: independently replay/review these sources and evidence, wait for
BOTH source writers terminal, then acquire fresh full Core/game objects and real
production TTL parity/lifetimes/actual consumer runtime. old 113 Core objects
consumed changing headers and are NOT a fresh production runtime witness.
then actual Root/Tenant/ImageMetadata/TilePainter scene plus legacy regression,
audio/save/TCP/CLI and cleanup. no production/runtime/game/platform/OOM/concurrency/
performance/universal qualification is claimed by syntax/object/configure proof.

this handoff is postacquisition documentation, not a participating input
rewritten after a compiler action. the raw pre-finalization draft in the owned
output root is an unexecuted draft, not another certificate or accepted report.
