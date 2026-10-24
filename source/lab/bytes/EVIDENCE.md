# frozen byte-order differential laboratory

## scope and replay

VERIFIED on this apple-silicon macOS host by standalone compilation/execution;
not a full module/game/platform qualification. Owned files are only
`source/lab/bytes/**` and generated `build/bytes-lab/**`. No Cargo/native game,
shared build writes, commits, user-storage access, or nested workers were used.

```sh
python3 source/lab/bytes/run.py --output build/bytes-lab/cpp-final-r3
python3 source/lab/bytes/run.py --define STAR_USE_RUST_BYTES \
  --archive build/bytes-rust/target/release/libstar_engine_ffi.a \
  --output build/bytes-lab/rust-final-r3
```

Both commands passed with identical repeated observations per backend:

| backend | cases | checks | per-operation executing-thread receipts |
| --- | ---: | ---: | --- |
| C++ | 48864 | 146592 | [0,0,0,0,0,0] |
| Rust | 48864 | 195672 | [3576,15362,3577,11441,3577,11440] |

Each Rust differential invocation asserts exactly one receipt on its own public
operation. Generated reports bind the live header, checker, real local compiler
dependencies, compiler executable, compile database, adapted reference, archive,
and ABI header before/after execution. They record full commands, compiler
version, binary hashes, and primitive provenance. `-MM` covers local headers,
not every system SDK header. Reports are evidence for their recorded hashes,
not for later changes. Parent should replay after integration.

## frozen reference and independent observations

Full `git show d4a0fc3e:source/core/StarBytes.hpp` is checked byte-for-byte against
`StarBytes.original.hpp`, SHA256
`02f0e5f52b9970d5348b70a5b165bedec881fec90d1256e25dac8a365702923b`.
Only namespace/import adaptation is permitted; adapted SHA256
`29fb21fb371552579ec6f957f635a0631f0600e185bcda9efabee6aad81e696f`.
Real StarMemory/StarConfig/StarPch includes are checked against the same commit.
Compiler recipe comes from the native reference compile_commands StarDataStream
entry; existing optimization/platform flags are unchanged. Extra standalone
link stripping and undefined-behavior sanitizer options are recorded.

All six public functions, generic templates, four endian helper templates and
platformByteOrder are exercised. Initialized arrays include complete guard
regions. Lengths 0..130, offsets 0/1/7, seeded random lengths <200, both byte
orders, NoConversion and enum -1/3/INT_MAX are covered. Reversing copies include
exact/partial overlap in both directions, using sequential destructive expected
writes, not memmove or a snapshot. No overlapping memcpy branch is called as a
defined C++ test. Integer template expectations are literal 0x01020304 and
0x04030201, not only paired round trips. POD padding is transferred but never
observed; only initialized fields are checked.

Raw ABI tests independently pass both platform facts 0 and 1 (no physical Rust
host inference), all operations, unknown orders, valid/invalid metadata, null
zero-length, in-place null length1/no-op, ignored poison source pointer,
address overflow rejection, nonconverting overlap rejection, and transactional
no-mutation/no-receipt rejection. Huge public C++ NoConversion in-place calls
are legal no-access cases: unchanged operation count proves the bounds fallback
was used without inventing a huge allocation. No fake large dereference occurs.

An initial *test specification* mistake expected raw ABI SIZE_MAX NoConversion
success. The frozen ABI's bounded metadata domain requires rejection2; its C++
no-access counterpart retains fallback. The ABI no-access check was corrected
to length1024 plus separate SIZE_MAX rejection. Original frozen source,
expected byte algorithm, native flags and C++ huge no-op check were unchanged.
The corrected checker was rerun C++ first, then Rust; historical r1/r2 outputs
are superseded by final-r3.

## falsification / negative controls

Each final report records 11 passing controls: corrupt frozen source,
unauthorized adaptation, arbitrary define, unpaired archive, unpaired selector,
wrong archive, output outside allowed tree, receipt-comparison corruption,
wrong copy direction, snapshot rather than sequential copy, and ignoring
unknown enums. CLI failures must be argparse exit2. Three actual isolated C++
candidate-header algorithm mutations are compiled with the unchanged frozen
reference and must execute with exit1 and `COMPARISON`; compiler failures and
crashes do not count. Receipt comparison corruption likewise must exit1 with
`COMPARISON receipt comparison corruption`. These are not claims of Rust
mutation coverage or injected Rust panic coverage.

Limits: finite scalar/byte cases; no universal equivalence proof, allocation
validity proof, panic fault injection, all-system-header identity, big-endian
native host build, screenshot/game behavior, or out-of-domain C++ memcpy overlap
claim. Thread-local isolation and MaybeUninit safety need the separate Rust
unit tests/source review; this harness observes executing-thread increments.

## parent integration

VERIFIED — independent parent replays `build/bytes-lab/{cpp-primary-r1,rust-primary-r1}/report.json` reproduce the table and all 11 controls. Active public header SHA256 `7bf5e5bdf582cbe42e81e55ddcbca3237db5f5634750bac3a21b99f3e49c41d2`; Rust source `9218646c0b3d6b1c9810c5a7265e0d4d2234da460ee64f19e4d1c1f86c8d2526`. Frozen reference bytes/adaptation remain unchanged. Parent ran 40 workspace tests EACH debug/release, fmt, 78 behavior/provenance/proof tests and eight inventory drift controls. `bytes-abi-contract-review-r1` traced padding, aliases, metadata, fallbacks, receipts, default-OFF and aggregate linkage; no actionable finding, source-only review. No implementation repair or reference/tolerance change.

The raw ABI intentionally rejects SIZE_MAX metadata even for no-access cases; the public C++ no-access counterpart preserves its original fallback. This distinction predates testing and is not evidence of a numerical/domain repair. Native consumer evidence is in `../behavior/EVIDENCE.md`; the separately linked production PCM decoder is in `AUDIO.md`.

Rollout remains default-OFF. VERIFIED call-path observation: `source/core/StarAudio.cpp:167–168` invokes the byte bridge per decoded PCM sample, even when little-endian conversion does nothing; the decoder oracle observes the expected 17 calls. Timing impact, loading cost and whole-game performance are UNVERIFIED. Quantify these before enabling by default; a correct framebuffer or PCM buffer does not establish unchanged performance.
