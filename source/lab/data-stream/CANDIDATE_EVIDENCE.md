# experimental Rust DataStream controllers

## bounded contract

all 51 out-of-line definitions in `StarDataStream.cpp` select genuine Rust
controllers behind default-OFF `STAR_USE_RUST_DATA_STREAM`. native public
`StarDataStream.hpp`, vtable/layout, typed callers, containers, iterators,
temporary strings and exception objects remain C++. native OFF namespace is
byte-exact; source-gate corruptions reject altered bytes and wrapper separators.
this is not a port of header templates, DataStreamDevices or universal resources.

Rust controls framing, branches, iteration and dependency ordering through the
calibrated 51-mode/21-operation scalar ABI. native leaf callbacks contain every
exception; Rust stops on pending and the native wrapper rethrows the same object
while native temporaries remain live. no C++ foreign throw is tested through
Rust. only an internal Rust closure tests panic containment.

wide conversions remain unconditional and directional, even NoConversion/native
order. reads mutate actual caller storage before a possible exception and fetch
fresh order after IO; bool instead publishes from a native uint8 temporary only
on success. string views precede prefix callbacks; ByteArray pointer/size follow
them. null-termination mode is sampled once; zero-size virtual IO is retained.
existing Bytes/VLQ are dependencies, not newly ported DataStream algorithms.

## compiled evidence

`build/data-stream-rust/core-freeze.json` binds 117 Rust workspace tests in each
profile (103 FFI +14 lighting), including11 new DataStream tests; fmt, strictC11,
linked C consumer and C++ OFF/ON/observed-symbol syntax passed. independent
source-only review traced all51 modes and found no actionable defects; it is not
execution or universal equivalence proof.

post-project-build evidence, not the historical pre-build202 profile:

- `build/data-stream-lab/oracle-postbuild-r1/report.json`: frozen original,
  renamed whole reference, current native OFF and repeat,683 exact records;
  1102 bindings/15 executables/35 commands and8 synthetic integrity controls.
- `build/data-stream-lab/rust-postbuild-r1/report.json`: actual selected native
  member bodies/private Context and the **game's linked Rust archive**,683 exact
  records and repeat,51 positive/balanced controller rows, native exception
  returns and directional Bytes/VLQ/child-u8 routes.1143 bindings/6 executed
  binaries/29 commands. four normally exiting value-equivalent controls reject
  native bypass, suppressed receipt, wrong pending return and getter bypass.
  independent verifier rejects10 synthetic integrity/route corruptions.
- ordered SHA256: `5ee512e3a91027823f34c47df4d1e056753e0fd61f03a9ad70e65131900763ab`.
- actual linked aggregate SHA256:
  `07671916fb5ec8674ac81396a9e1e4feaf04a5b3bbcc6097d48f77a975a3a996`.
  original archive DataStream member is rejected in selected linker maps.

pre-build `rust-candidate-r2` is historical after native objects/Ninja/Version
changed; its canonical archive `edff12c1…` is not silently substituted for the
explicit-target game archive above. no source/golden/reference-flag fitting.
selected Context guards are NOT an exhaustive automaton/pointer validator.
previous scoped ASan re-scan control did not discriminate: NO sanitizer credit.

## actual consumer matrix

`build/behavior/data-stream-actual-r1/report.json` passes C++ repeatability BEFORE
Rust launch, exact three-frame/state comparison, normal Assets/Font geometry,
and actual owned outputs. all three Rust frames were inspected at1000×600:
orange64×64 image, white STREAM label, real room occlusion and restoration.

actual numeric127.0.0.1 TCP listener on owned ports40201..40232 sends/receives a
normal typed ChatSendPacket. a fixture-local, default-inactive native send-boundary
observer records only successfully sent bytes, not a shadow serialization.
independent literal frame `12120653545245414d0000` is11 bytes. rulesVersion5 is
manually configured; NOT Universe negotiation. only accepted peer is an OS
sockaddr; unpopulated client-local cache is NOT an OS-local-address observation.

normal VersionedJson file write/read and memory/file BTree commit/close/reopen
recover the independent57-byte native save literal. decoded BTree content
`[200,112,48,255]` drives the image; received TCP text drives Font. native file
bytes and paths are bound to the sentinel-owned storage before projection.
actual files and memory pages are1024 bytes and exact; ten native operation
scopes,321 Rust attempts in this observed run, no fabricated one-hot coverage.
three source-derived sparse call graphs were frozen before game execution.
16 synthetic corruptions of the actual receipt reject wire/save/EOF/database,
caller/route/OS-provenance/visual changes and escaped file paths.

parent source tracing caught a fixture domain issue before building: Buffer
resize does not initialize growth, but BTree grows a partly written header.
the NEW memory fixture seeds8192 bytes with zeros, logically truncates, and
checks it never exceeds that initialized extent. no golden or algorithm changed.
read-only follow-up is required for unused padding in three older RAM BTree
fixtures (SHA/VLQ/Bytes): their observed finite pixels/receipts do NOT establish
initialized padding. those older scene methods remain unchanged in this unit.

## accepted finite application qualification

source checkpoint **fd285405**. `build/behavior/data-stream-historical-pixels.json`
passes all17 historical scenario matrices/51 decoded-RGBA frames unchanged;
with the new scene,18 actual matrices pass C++ repeatability before Rust launch.
fresh PCM WAV decode/seek/EOF and corrupt-PCM controls pass both actual link
closures; no audible mixer/Ogg claim. `data-stream-option-cli-r1/report.json`
passes12 real client CLI literal/exit executions. current build/source seals,
actual linked archive and reports are bound in
`build/behavior/data-stream-actual-r1/qualification.json`; its verifier rejects
a known-bad historical-count fixture.169 behavior tests and catalog1637files/
39modules/eight drift controls pass. all delegated tasks and owned processes
are terminal. pre-existing storage and Steam remain untouched.

next is the explicit legacy RAM-header padding domain audit above, before another
port. no full-engine, OOM, destructor, allocator, performance, remote-DNS, Universe
handshake, sanitizer or cross-platform completion claim.
