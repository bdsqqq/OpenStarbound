# host address native oracle

```sh
python3 -B source/lab/host-address/run.py --identity-manifest build/host-address-lab/identity/manifest.json --output build/host-address-lab/parent-fresh-r1
python3 -B source/lab/host-address/verify_receipts.py --report build/host-address-lab/parent-fresh-r1/report.json --self-test-output build/host-address-lab/fresh-integrity-fixtures
python3 -B source/lab/host-address/host_run.py --values build/host-address-lab/parent-fresh-r1 --output build/host-address-lab/fresh-host-run
```

output must be fresh, owned and nonsymlink. runner never deletes prior outputs or builds the native project. uses the sealed current reference compiler, flags, SDK headers, native core/extern objects and vendor libraries; private archive excludes only StarHostAddress.cpp.o. original/reference/current are separate executables.

frozen originals come from `77e35ba8`. reference transform tokenizes strings/comments before renaming class identifiers in the same Star namespace. preserves legal native hash specializations and fmt specialization names. reuses the original NetworkException and NetworkMode definitions (removes only their duplicate declarations), inserts original header include and changes the reference cpp include. all algorithm bodies and error literals remain unchanged. exact transform gates both files and current native sources.

no public/private macro tricks, fake C++ classes, replacement native string/hash implementation or object-layout probes. only initialized bytes are read. unknown modes use null initialization; explicit initialized-storage fixtures test public octet access beyond address.size() without inspecting indeterminate tails. resolver interposition is a native API fixture, not an independent address codec; numeric libc observations are distinctly named. see `EVIDENCE.md` for actual checks and gaps.
