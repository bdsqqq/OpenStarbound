# native datastream calibration

this lab calibrates the 51 out-of-line definitions in `StarDataStream.cpp`, not
all serialization, header templates, rust, or running-game behavior. its native
`Stream` subclass directly derives from the class under test and records ordered
virtual i/o, byte counts, positions, bytes, configuration and symbolic destination
identity. native strings, arrays, vtables, allocation and exceptions remain native.

run from the repository root with a fresh `oracle-*` output directory:

```sh
python3 source/lab/data-stream/run.py --output build/data-stream-lab/oracle-replay-r1 --identity-manifest build/data-stream-lab/identity/manifest.json
python3 source/lab/data-stream/verify_receipts.py --report build/data-stream-lab/oracle-replay-r1/report.json --self-test-output build/data-stream-lab/oracle-integrity-r1
```

raw cpp/header snapshots must equal revision
`9f2316a22d5abcb10ff2778b628bc3bef7de5b99` and current production source.
the reference changes identifier tokens `DataStream` and `CurrentStreamVersion`,
the cpp include, and header exception reuse only. comments, string/character
literals, templates and the version value remain unchanged. no macro class rename.
original/reference/current are separately compiled and compared with an original
repeat. independent integer byte literals supplement whole ordered equality.

native compile flags, sdk and vendor libraries come from the sealed existing
all-cpp game recipe. `-UNDEBUG` activates checks after its `-DNDEBUG`; native
optimization/fast-math flags remain. a private archive retains all existing core
objects, including original DataStream for other native dependencies. explicit
original/current definitions satisfy those symbols; reference fixture inheritance
is statically distinct from native DataStream. linker maps retain membership and
a normally exiting reference-only version mutant detects native-class bypass.

coverage map for the 51 definitions:

- constructor and seven configuration getters/setters: `default`, `version`, `rules`,
  primitive order loops and string terminated/prefixed loops (8).
- direct byte read/write including zero: `bytes/read`, `bytes/write` (2).
- twelve primitive writes and twelve reads: bool plus char/i8/u8/i16/u16/i32/u32/
  i64/u64/f32/f64, raw integer bits, signed zero, infinity, quiet NaN payloads;
  orders 0,1,2,-1,3,INT_MAX; callback order mutation and initialized partial reads (24).
- U/I/S writes, reference reads and value reads: boundaries, sentinel, malformed
  and EOF; signed extreme reads use independent literal bytes (9).
- cstring/stdstring/ByteArray/String writes, stdstring/ByteArray/String reads and
  private writeStringData: both framing modes, versions 0/20/21/UINT_MAX, empty,
  embedded NUL/invalid UTF-8, fault and callback timing, late array reallocation,
  captured string pointer with in-place mutation (8).

scripted exceptions retain a single exception_ptr, matching its caught identity
and full what(). they are counterfactual i/o failures, not real OOM evidence.
ByteArray fault inputs always use a VLQ prefix even when terminated mode is on.
ByteArray fault outputs start with 16 initialized Q bytes and only shrink; no
uninitialized grown tail is inspected. successful reads fill requested bytes.
no dangling pointer, overlap, raw class padding or uninitialized-success cases
are included. the prefetch-array mutant captures stale size but obtains a fresh
pointer, so its negative does not read freed storage.

signed VLQ writes and returned sizes cover INT64_MIN, INT64_MAX and 1<<62,
with independent zigzag byte anchors. the parent scoped C++17 shift probe at
`build/data-stream-lab/domain-signed-vlq-r1/report.json` admits these native
expressions; it is not full-Core undefined-behavior certification. unknown fixed-int ByteOrder
values are admitted: on this little-endian profile every value other than 1/2
swaps. native DataStreamFunctions ignores returned counts; native IODevice
readFull performs one read then throws after a short read. both are observed.

negative controls compile and exit normally before receiving credit. they test
wrong endian, early read-order snapshot, transactional partial read, skipped empty
i/o, stale array payload size, late stdstring clear, early String assignment,
re-read terminated mode, and VLQ partial-output timing. paired wrong executables
must agree but fail independent literals. source/reference tampering and eight
isolated receipt/artifact corruptions must be rejected.

repair ledger: oracle-r1 exposed symmetric fresh-read bytes hiding an order bug;
oracle-r2 exposed callback mutation masking early String clear. both retained,
no success reports, no negative credit for the escaped case. after two failed
broad-corpus attempts the approach changed to isolated no-callback fault probes
alongside the broader corpus. the isolated stream matched, but parent review found two negative-only
indeterminate reads: transactional-read copied a possibly uninitialized caller;
vlq-partial initialized its staging value from a possibly uninitialized output.
these earlier compiled-negative runs are UNQUALIFIED. corrected controls use
value-initialized staging without reading caller storage. parent then found
terminated-mode ByteArray fault fixtures accidentally parsed ASCII a as length97,
growing past initialized storage. both fixture families now use prefix3 for arrays;
all pre-r5 streams are UNQUALIFIED as defined-domain evidence. no earlier migration
failure budget is reset by this lab.

remaining: actual allocator/resource/destructor timing, all platform variants,
full template serialization, tcp/save/btree consumers, rust, production selection,
images/font/game execution and performance are unqualified here. prior qualified
archives and binaries are read-only inputs; this lab does not rebuild them.
