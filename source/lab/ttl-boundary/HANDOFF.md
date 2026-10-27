# ttl native boundary + mock — final handoff 2026-10-27 17:27 utc

**TERMINAL / review-ready / SOURCES FROZEN.** no active owned process/writer.
parent must review/replay before sending DEPENDENCYREADY to its actual-Rust
bridge agent. this unit does not send that signal or claim parent acceptance.

owned writes ONLY `source/lab/ttl-boundary/**` and `build/ttl-boundary-r1/**`.
NO Cargo/Rust/header/production/CMake/scripts/catalog/plan/game/Steam/storage/
remote edits or operations, nested agents, commits or full builds. no secondary
Rust crate/runtime. all `source/lab/ttl-cache/**` bytes remain unchanged.

## final exact replay

```sh
python3 -B source/lab/ttl-boundary/verify.py ce0a8e4ff977edd41e2be59a5ec2edd2800138d9b6b113f070198b915c8d76a0
```

VERIFIED: final acquisition and this separate read-only replay ran normally.
replay starts NO subprocesses. `run.py` performs fresh standalone acquisition,
refuses an existing report, and must not be rerun into the accepted output root.

all paths below are beneath `build/ttl-boundary-r1/`:

| artifact | sha256 |
|---|---|
| report.json | ce0a8e4ff977edd41e2be59a5ec2edd2800138d9b6b113f070198b915c8d76a0 |
| audit.json | 065a33c0723da89fe0e368765b96903aa17db36c108764dad7f977703810f7e6 |
| inputs.json | e4818376a7855ce84b3284b8541748476c756b7fb4eda5814afefbd2c7396de2 |
| native | 2283845d8964cc4725b0d749b7024c9feb9749cff4822e9225ded1858eed0c7c |
| native.o | eadac6b5de002429f99f18fd61bfc8506560912030c8e310e8f38ed69de803dd |
| native.map | a440887d13ac1123b108eff63777239496b7b86ca4c146888da1c041f6aed7e9 |
| lifecycle.stdout | ee9fed2906e6ff0db3c30f413f0f63167b3ba8aafdda72bd5783b379b854ed99 |
| controls.stdout | 28fd8c7c333e0b5a259b44c72641fee1b2d5339a744437a57bcdbb525428c655 |
| real.stdout | a7a4bd3eae3c1ebf62b12c3c3ae6efd958402fcdb831e758b064e012fdf4547b |
| coherent-controls.json | d0d3ff43e9daa3bbdda12055c5792dd1e9d1993dd574ea1a0cab4c91ae15ca41 |

canonical C11 header UNCHANGED SHA
`254cf12cb2ec798334cf0799b4344f58eb140e657dceb12d0788200cdc17332d`.
accepted native baseline report UNCHANGED pin `cba3b3c84acc2128bd043400cabd6ed2ebf35fcdde37e6d36e2a870bc7926674`.

final source pins beneath `source/lab/ttl-boundary/`:

- cache.hpp `5bb90f41a4e74f310afc580e3e9328a68217458b3967848858e694aed1a9c152`
- host.hpp `bbcb9049962e10d5488113f2267c6d92973af4e3d257f987e1045532206f76b1`
- mock.cpp `a17347e1006c17523e1348683ebd3f0ec50bd3c571b81b36c118cae9bfd46075`
- native.cpp `489e78a512d967663d6cc5681b7066aec91f1a39bf661699bd240bd3eb953b55`
- controls.inc `180a9891ec4d66cd0e272e6de7e2dc00309cfd71aee2738bc2547862d2c5420a`
- lazy.cpp `f9480fbd8c9fffd14fd73b12b97578c0bed2db2fbcf812d5dfca8a3bb8b5f5fb`
- c11.c `59020c19dc68472712fc7663699d09885d6cb264d018b4d411ae6470e4d4c63b`
- run.py `23b3126501d3456e151a161d7a79b5e1f65c0263ab85d43c745ddf36a84afa8d`
- verify.py `de4fe43baebaad7b1588b49449ac100b9168315c9963032bbfae5cb895edea46`

this final HANDOFF is postacquisition documentation, not a participating input
rewritten after acquisition. previous handoff bytes are retained in the rejected
pre-result-metadata archive, not silently retagged.

## final evidence / falsification

VERIFIED (`semantic.json`, all stdout/stderr, `audit.json`):

- four fresh ordered/hash native processes (twice each), 626 rows EACH, match the
  unchanged independent model EXACTLY. baseline model/corpus/lifecycle/header,
  domain, flags and expectations were not edited or normalized.
- 68 properties and ALL FOUR COMPLETE lifetime trace streams are BYTE-IDENTICAL
  to the frozen baseline. `lifecycle.stdout` has the same SHA as native baseline.
  this includes producer copy-on-hit/by-value/const-call, pair/list copies/moves,
  saved producer/filter exception_ptr identity, native partial assignment,
  insertion-copy unwind with unrelated-key destructor reentry, values-copy-prefix
  unwind, implicit copy/move/assignment/source retention and balanced lifetimes.
- 99 actual ABI/control rows pass. both controller ROOT-result and native host
  incoming reply require size24/version1/reserved0; entry tag/value may remain
  sentinels. distinct bad-size/version/reserved root controls return INVALID2 and
  preserve the ENTIRE result. three native bad-reply controls attempt WRITE_TTL,
  and prove INVALID2 before ANY field mutation or output-byte write.
- leaf15 is VOID0 after writing native `c.value`; ROOT PTR/GET alone return REF0.
  direct host control `native-leaf15-void-root-ref-distinction` proves that exact
  contract. final mock was compared directly with frozen Rust controller source
  (read-only) through all 31 leaf tags, 19 modes, 4 stages and metadata/status
  handling. incompatible but in-range mode/stage calls increment counters before
  rejection, matching Rust. no Rust/header workaround or waiver.
- malformed request size/version/op/reserved/arg, invalid mode/stage/nulls,
  missing borrowers, malformed host output metadata/tag, noncanonical bool,
  nonzero void, exception/invalid/panic/unknown status and unchanged outputs on
  errors pass. C11/C++ pin 24-byte POD layout/alignment/offsets. compile-only
  nonassignable AND move-only values allow construction/getters/ptr/keys/cleanup/
  clear without unnecessarily instantiating set or Value assignment.
- supplemental ordered/hash values tests compare COMPLETE original-native versus
  boundary traces for a saved exception thrown on the SECOND output append,
  after one result prefix. nested status1 returns before native rethrow; range
  and result-prefix destructors observe uncaught_exceptions()==1, and a range
  destructor reenters removal of unrelated key99. saved cleanup refresh-filter
  exception_ptr identity also passes through its nested stage. events are fully
  retained in controls.stdout, not merely booleans.
- mock omitted-borrow mutation proves PTR cannot recover its reference through
  native fallback; GET rejects missing native borrow. native return pointers are
  written ONLY by leaf15. no hidden pair-to-value fallback remains.
- all 19 modes / 4 stages / 31 leaves actually observed. full per-process counts
  and call edges are retained in each `.stderr` and semantic.json. every actual-
  ordered/scripted-ordered/actual-hash/scripted-hash lifecycle has separately
  measured boundary deltas including VALUES_LOOP and FILTER_PREDICATE. each
  real-clock alias separately records ctor1/set2/get1/ptr3/cleanup2/predicate5.
  realSmoke does NOT call values; actual-alias lifecycle DOES. scripted-only
  routes are never counted as actual Time/Random boundary evidence.
- 12 unchanged baseline semantic/output alternatives reject. coherent-controls
  injects valid-text changed public output and changed lifetime event through
  the SAME complete semantic_replay function: each fails at its named comparison
  barrier; a positive replay immediately afterward passes. files remain unchanged.
  typed returncode=False also rejects through the actual receipt validator.

finite evidence only. coherent controls are isolated overlays/mock mutation, not
compiled production-algorithm mutants. actual clock exact TTL timing boundaries
are NOT inferred from scripted calibration. actual negative-smear Random throws
remain tested with exact native StarException bytes.

## native ownership and actual-Rust integration

`cache.hpp` defines LAB BoundaryTtlCacheBase / BoundaryTtlCache /
BoundaryHashTtlCache, not a production selector. EXACT original four native fields,
order, alias allocator defaults and implicit lifecycle remain. local sizes and
alignments match original ordered120/8 and hash136/8. stack Context is mode-
specialized; no native Value or producer is eagerly copied/assigned by the frame.

`host.hpp` has no mock inclusion and calls ONLY canonical sb_ttl_run/count.
mock.cpp owns TTL method dispatch, zero/update/miss branches, values loop and
cleanup/filter policy. no active-frame TLS, cache fields, persistent mirror/map,
foreign native exception unwind or whole-method native fallback exists. mock's
internal Stop is contained before C return; original exception objects stay in
native exception_ptr slots.

SET retains whole original make_pair(Time+Random,value)+LRU.set full expression.
GET retains LRU.get+[producer]+pair(0,producer(key)); the native reference binds
at its ORIGINAL semicolon BEFORE TTL refresh. producer capture is by VALUE, not
reference. Time/Random stamp assignment remains one native expression, including
negative-smear native exception; no prevalidation. dependency LRU retains its
existing selector and is ALL OFF in this fixture.

values() keeps the named native List<Value> result/NRVO scope. VALUES_SCOPE owns
native auto&& copied range and iterator locals in a block ending BEFORE return
values. controller alone calls END/APPEND(std::move(p.second))/NEXT. nested run
returns before native execute rethrows saved exceptions INSIDE range or original
removeWhere callback owner; outer noexcept host catches before outer run returns.
VALUE_LOOP returns VOID; FILTER/CLEANUP predicates BOOL. cleanup captures Time
once even empty, reads TTL dynamically AFTER false filter, writes captured time
on refresh without smear/random. PTR promotion precedes update check; GET zero
stamp short-circuits update flag.

actual-Rust agent must use frozen cache.hpp/host.hpp. adapt ONLY its OWN driver:
this native.cpp intentionally includes mock.cpp, mock-only controls.inc and mock
counter dump hooks, so do NOT link that TU unchanged with actual Rust aggregate.
keep frozen model/lifecycle.inc and real/script alias distinctions; retain actual
sb_ttl_count per-alias coverage. parent alone sends DEPENDENCYREADY AFTER review.
no production selector until actual Rust qualification.

## processes / profile / retained history

final 19 commands all normal exit0. compile PID12127, link12901, C11 12918,
lazy12927, controls12935, real12936, lifecycle12937, ordered12943/12944,
hash12945/12946. each command has durable `.plan.json`, `.started.json`,
`.receipt.json`, stdin/stdout/stderr hashes, actual PID/PGID/start/end, timeout,
argv/cwd/environment/tool-before/after witnesses; groups gone at completion.

fresh standalone fixture links current canonical reference 113 Core/extern
objects, same recipe SHA9639bd43..., 26 selectors OFF, -O3/-ffast-math/gnu++17/
libc++ flags. no full build, source-object rebuild or archive restore. full SDK
before/after has 3,683 interfaces, 35 actual map-consumed entries; native Time,
Random and RandomSource symbol providers resolve to canonical objects. 544
loaded-image UUIDs include libc++/libSystem. finite static/runtime evidence, not
hostile-runtime attestation or dyld shared-cache byte extraction.

history preserved without relabeling:

1. attempt-1.tar.gz + manifest: initial actual commands/model/lifetimes passed,
   verifier FAILED because it wrongly required values() in realSmoke. corrected
   asserted call set, retained separate actual-lifecycle values evidence.
2. pre-borrow-action.tar.gz: earlier finite success is HISTORICAL. source review
   changed wrapper to consume authoritative native borrow action, then added
   omitted-borrow controls and reacquired. old bytes not claimed current.
3. pre-result-metadata.tar.gz: REJECTED incomplete mock ROOT-result precondition.
   prior positive/error controls used invalid metadata sentinel. parent-directed
   exact repair/fresh acquisition; previous report/source/results retained.
4. pre-leaf15-host-metadata.tar.gz: REJECTED native/mock mismatch with frozen Rust
   and missing host incoming-reply metadata guard. original receipts/source/
   controls/results retained; exact mandatory repairs above freshly acquired.

all archives have exact-member SHA manifests, were reconstructed BEFORE pruning
ONLY owned obsolete products, and final verifier reconstructs ALL FOUR again.
no historical source/path/inode receipt is rebound as current. initial acquisition
failure and subsequent parent review defects are disclosed, not erased/reset by
fresh output names. no model/domain/flags/golden fitting.

ONE current fixture/object/map. final retained output31,756,074 bytes (~30.3MiB),
all four compact archives included, below96MiB. final budget.json PASS:
archive16,413,511,680 bytes / live2,626,031,616 bytes versus16GiB/4GiB. unrelated
user data and other agent outputs untouched. no lingering owned work.

## remaining / next action

parent independent source/model/lifetime/control replay and checkpoint, THEN
explicit bridge dependency release. actual Rust bridge/game UNIMPLEMENTED HERE.
TTL+LRU ON composition, production selector/callers, game consumers, exact real-
clock boundaries, allocator/OOM/sanitizers/concurrency, arbitrary iterator-
invalidating callbacks, other platforms/performance remain unverified. native
signed-overflow/-INT_MIN UB domains stay excluded, not widened/saturated.

read original user prompts verbatim at newest plan top; migration skill; TTL
BLUEPRINT/native/model/lifecycle/run/verify/audit; production TTL/LRU/List/
OrderedMap and previous LRU lifetime sources; frozen Rust controller for final
protocol crosscheck. no nested delegation. parent owns final acceptance.
