# host address native oracle

```sh
python3 -B source/lab/host-address/run.py --identity-manifest build/host-address-lab/identity/manifest.json --output build/host-address-lab/parent-fresh-r1
python3 -B source/lab/host-address/verify_receipts.py --report build/host-address-lab/parent-fresh-r1/report.json --self-test-output build/host-address-lab/fresh-integrity-fixtures
python3 -B source/lab/host-address/host_run.py --values build/host-address-lab/parent-fresh-r1 --output build/host-address-lab/fresh-host-run
```

output must be fresh, owned and nonsymlink. runner never deletes prior outputs or builds the native project. uses the sealed current reference compiler, flags, SDK headers, native core/extern objects and vendor libraries; private archive excludes only StarHostAddress.cpp.o. original/reference/current are separate executables.

frozen originals come from `77e35ba8`. reference transform tokenizes strings/comments before renaming class identifiers in the same Star namespace. preserves legal native hash specializations and fmt specialization names. reuses the original NetworkException and NetworkMode definitions (removes only their duplicate declarations), inserts original header include and changes the reference cpp include. all algorithm bodies and error literals remain unchanged. exact transform gates both files and current native sources.

no public/private macro tricks, fake C++ classes, replacement native string/hash implementation or object-layout probes. only initialized bytes are read. unknown modes use null initialization; explicit initialized-storage fixtures test public octet access beyond address.size() without inspecting indeterminate tails. resolver interposition is a native API fixture, not an independent address codec; numeric libc observations are distinctly named. see `EVIDENCE.md` for actual checks and gaps.

## actual rust replay

`candidate_run.py` requires a fresh native calibration report plus explicit
parent-provided production source and canonical aggregate archive hashes. it
never runs cargo, a native project build, or the game. do not use an archive
while its owner is still writing it.

```sh
python3 -B source/lab/host-address/candidate_run.py \
  --values build/host-address-lab/FRESH_NATIVE \
  --output build/host-address-lab/FRESH_RUST \
  --rust-archive build/host-address-rust/target/release/libstar_engine_ffi.a \
  --source-sha256 PARENT_FROZEN_CORE_CPP_SHA256 \
  --archive-sha256 PARENT_FROZEN_ARCHIVE_SHA256
python3 -B source/lab/host-address/verify_candidate.py \
  --report build/host-address-lab/FRESH_RUST/report.json \
  --self-test-output build/host-address-lab/FRESH_INTEGRITY_FIXTURES
```

the generated corpus keeps the complete ordered 430 records and adds an
explicit return after renaming `main`. native production member definitions
compile as a separate translation unit. the generated protocol adapter includes
the actual private production context, never the old c++ blueprint. it omits
only the deliberate foreign c++ throw assertion; contained rust panic testing
belongs to the rust unit tests.

per-mode rust counters must match separately observed actual dispatch return
statuses. native bypass, suppressed receipt and changed constructor pending
status controls must exit normally with the same values, then fail backend
qualification. the bypass also records a positive observer inside native
`HostAddress::mode`. source/tool/dependency/archive/generated/executable/output
hashes are checked before and after. these finite gates do not qualify game
behavior, tcp consumers, other platforms, resource failure timing or performance.
