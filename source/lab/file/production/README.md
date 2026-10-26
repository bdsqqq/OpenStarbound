# current production file runner

`runner.py` qualifies one explicitly selected archive against fresh current
production C++ objects. it does not run cargo, cmake, ninja, or the game. historical
host receipts authenticate only their 13 exact snapshots and layout output; their
old current-source binding dictionaries are never rebound or replayed as current.

```sh
python3 -B source/lab/file/production/test_runner.py
python3 -B source/lab/file/production/runner.py prepare --output build/file-rust/runner-worker-r1/prepared-next
python3 -B source/lab/file/production/runner.py run --output build/file-rust/runner-worker-r1/production-r1
python3 -B source/lab/file/production/runner.py verify --output build/file-rust/runner-worker-r1/production-r1
python3 -B source/lab/file/production/runner.py controls --output build/file-rust/runner-worker-r1/production-r1 --controls-output build/file-rust/runner-worker-r1/controls-r1
```

outputs must be new descendants of `build/file-rust/runner-worker-r1`. preparation
is source/plan checking only. acquisition requires both the conditional inventory
and archive before creating its output. it rebuilds 113 objects twice with at most
six compiler jobs: all native selectors OFF, then only `STAR_USE_RUST_FILE` ON for
every translation unit. source filenames determine the File and platform indices.
there is no stale object reuse. failure artifacts remain; no cleanup/retry occurs.

`--archive` also accepts exactly
`build/behavior/file-combined-r1/candidate/cmake/rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a`.
use a distinct fresh output and repeat all qualification for that artifact; the
aggregate and game archive are not assumed equivalent. the parent owns Rust-only
panic tests, source-to-archive build provenance, and application acceptance.

acceptance requires frozen ordered 139 observations, exact repeats, fixture bytes,
byte/reentry/partial-backup supplements, 34 positive balanced executing-thread
controller counters, zero native bypass counters, strict C11 compile/link/run,
protocol/TLS checks, pinned native layout, 34 compiled symbols, and actual ordered
link-map object membership. the native protocol retains its native foreign-throw
control; the Rust adaptation removes ONLY the exact invocation named by `OMITTED`.
its callback definition and non-invoking unknown-mode/null-context/null-host tests
remain. the native context captures exceptions and rethrows after Rust returns.

removal is mandatory and INSTRUMENTED: the exact one static platform remove body
is substituted, all other platform bytes preserved. six cases twice per backend
require original exception identity, descendant ordering, exact repeat, one strong
symbol, and unchanged ordinary trees. no real OS unlink is performed by this gate.

replay reconstructs complete argv, owned stdin, executable/stream/status receipts,
initial/before/after dependency closure, source snapshots, preexecution membership,
and required artifacts. dictionary omissions cannot redefine scope. `controls`
corrupts isolated report copies; it never changes the accepted receipt. unit tests
exercise construction/guard failures without claiming native execution. before/
after hashes cannot detect a transient change reverted between observations.

this is a finite controller gate under the internal unsafe-host contract: live
native typed state, valid bounded scalars and operation order, output live/aligned
and disjoint from all reachable state. numeric guards do not prove arbitrary
pointer safety. modes 0/2/3/4/5/7/33 keep native prefix setup/return expressions;
counters begin at controller entry. no game, general adversarial host, OOM,
platform-general, OS deletion, or invisible-destructor-timing claim follows.
