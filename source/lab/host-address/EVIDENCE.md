# native host address calibration

VERIFIED on this apple silicon macOS checkout; native-only, not a Rust port or game qualification.

current parent artifacts: `build/host-address-lab/parent-domain-final-r1/` (native) and `build/host-address-lab/parent-host-final-r1/` (opaque C++ blueprint). worker `oracle-final-r1` and earlier parent430-predecessor runs bind their historical fixture versions, not the current extended fixture.

- 430 ordered records match across separately linked frozen original, renamed whole reference, current unchanged source, and original repeat.
- ordered sha256: `e9a14b9a678ad9819b4f17043ef08ccc901270dd1510d9bfcd516083454aa9b1`.
- 1,144 bound inputs,16 executables,37 successful commands rehashed by the independent receipt verifier.
- eleven compiled mutants exited normally and produced different output; two additional controls reject narrowing unknown-mode localhost behavior and incorrectly limiting public octet access to size(). the initial nine were: last recognized resolver, broadened localhost, mode-dependent hash, omitted normal free, required brackets, rejected native port overflow, early port cache, single giant endpoint insertion, compressed zero IPv6.
- separately compiled paired mode-hash corruption gives matching wrong streams but fails independent literals. isolated wrong-output fixture fails literals. raw/reference provenance corruptions fail source gates. synthetic bound/generated/binary hash corruptions fail the independent receipt verifier; `verifier-self-test.json` records them. synthetic artifacts are not execution evidence.

## observed domain

native constructors/default/copy, getters, active bytes, equality, null initialized unknown fixed-underlying enum values, localhost and zero predicates, native PL/hashCombine, expanded IPv6 and unbracketed endpoint text, lookup/Either and reconstructed exception layers, endpoint split/port overflow/sign/whitespace/NUL/Unicode, stream width/fill/base/tie, short writes, suppressed and escaping sentinel identity, endpoint mutation after initial address write and after colon write. address copy remains old while port is freshly read. exact chunk traces are compared, not misidentified as one xsputn per C++ insertion.

`lookup`, `ctor`, `lookup-port`, `parse`, and endpoint constructors use COUNTERFACTUAL vendor fixtures. these return valid native addrinfo/sockaddr records, record original hints/C-string query/list families/source free count/errno, and never resolve text externally. unknown families, ordered IPv4/IPv6 lists, all-unknown success, errno22 and errno0 errors are scripted, not libc error behavior claims.

only `real-numeric/0` and `/1` invoke libc via RTLD_NEXT, guarded by exact `127.0.0.1` and null service. original AF_UNSPEC/SOCK_STREAM/IPPROTO_TCP/AI_ADDRCONFIG retained, no AI_NUMERICHOST added. no socket bind, game, Cargo or native project build occurred.

## failed attempts and changed approach

- r1 uncovered native `OutOfRangeException` for colon-only input, which `lookupWithPort` does not catch. fixture now records this actual non-NetworkException rather than crashing or changing the algorithm.
- r2 exposed duplicate record fields from inlining localhost observations. separate records and duplicate-field rejection replaced that ambiguous schema.
- r3 rejected an incorrect verifier assumption that padded string insertion means one xsputn; libc++ emitted address and padding separately. changed approach: exact chunk comparator plus independent text/late-port literals, and compiled giant-insertion negative. mutation after colon now triggers on colon bytes, not a guessed write count.
- r4 showed missing 127.0.0.2 coverage through an escaping broaden-localhost mutant. added that independent raw address/hash/text anchor; r5 passed, then added default/two-argument endpoint construction coverage and reran final successfully.

all failed artifacts retained; no deletion or hidden golden updates. these are fixture/verifier failures, not native algorithm repairs. reference algorithms remained frozen.

## parent domain and integrity refinements

source tracing found two defined domains missing from the initial426-record corpus. `NetworkMode` has fixed underlying int; a null constructor initializes all16 bytes even for an unknown mode. removing constness from `bytes()` on the actual MUTABLE object and assigning byte15 is defined. with only byte15=1, every non-IPv4 mode takes the source's16-byte localhost branch and returns true, while size/hash remain0 and equality ignores bytes. an IPv4 null object likewise permits initialized octet15 access, even though classification/hash/equality use only the first4. no uninitialized tail or padding is inspected. independent literals and two narrowing mutants were introduced BEFORE prototype comparison; frozen original algorithms were unchanged. worker426-record SHA `040832d8e2f0030470c0190971bf43f70273dcfaf40f15bccda5562f16dd7a81` remains historical.

parent hardened `verify_receipts.py` to compare before/after binding maps and receipt copies, rehash actual executed tools, reject unexecuted binaries/duplicate records, and count records. eight isolated SYNTHETIC integrity corruptions pass: bindings/generated/binary/archive/stdout/stderr/executable-receipt/after-map. synthetic fake executables are not execution evidence.

## opaque prototype and resolver lifetime

all27 actual public/private compiled definitions are implemented through the scalar-only C++ blueprint against the unchanged native header. the final header has38 operations (0..37), including an explicit public octet-argument read; the first draft used an undocumented byte-read sentinel and was NOT protocol-qualified. pointer/class/Either results stay native. private setters use member-scope thunks; no private/public macro or layout mirror is used.

parent430-record prototype/original/repeat streams match the current independent literals. three compiled controls (hash recurrence, last resolver selection, early cached port) execute normally and differ. selected protocol tests cover custom opaque/null contexts, pending NetworkException conversion versus other-exception identity, invalid statuses, output/owner aliasing, busy/finished states, raw extents and resolver acquisition/release phases. strict c11 and actual private C++ bindings compile. an independent source-only review found no actionable remaining findings; it is not runtime certification.

parent caught an ACTUAL bridge bookkeeping defect: after normal `freeaddrinfo`, output-alias validation dereferenced the dangling current node during FINISH. preserved pre-fix source reproduces `heap-use-after-free` with address instrumentation and real numeric127.0.0.1. the fix clears bookkeeping pointers AFTER the original free and guards resolver state before any later dereference. `build/host-address-lab/asan-lifetime-r1` diagnoses the old failure and passes the fixed complete430-record stream. this diagnostic failure is NOT credited as a semantic negative/parity test. reused core/extern objects are not sanitizer-instrumented; no universal resource claim follows.

an aligned top-eight-byte output span is now rejected before exclusive-end arithmetic can wrap. selected tests also reject resolver operations before acquisition/after free, repeated acquire/free, and raw IPv4 reads beyond four input bytes. explicit source catch semantics permit ONLY NetworkException conversion into Left; if constructing that catch result throws, the new exception replaces pending as C++ does. catch-body allocation failure replacement is source-traced, not runtime-injected.

## limitations / remaining gates

parent native and blueprint replays are recorded above; they do not replace the future Rust and actual-consumer acceptance gates. whole compiled reference is retained, but finite corpus is not universal equivalence. no actual OOM, exotic locale, allocator/destructor timing, all exception sites, IPv4 inactive-tail inspection, platform universality, Rust, actual TCP consumer, screenshots or game behavior claim. native-private C ABI access belongs to the parent's reserved prototype, not this oracle.
