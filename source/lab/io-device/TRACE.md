# full io-device trace: finite native calibration

parent native validation (2026-10-26 01:38–01:45 utc):
`build/io-device-lab/full-audit-r1/audit.json` is
`AUDITED_FINITE_NATIVE_IODEVICE_CALIBRATION_PASS`: all8021 frozen rows match
original/reference/current/repeat, with all22 source definitions mapped.
canonical expected digest below is unchanged from the source-only freeze.
original and reference EOF-class mutants exit normally, produce identical wrong
observations, and fail the independent contract. bounded six-case pointer/
failure-restoration controls separately pass their normal-exit detection gates.
strict duplicate-key/nonfinite checks and count/definition/acquisition corruption
checks reject. current native profile/archive/transitive/command/executable/
stdio identities are reverified; no production/header/Rust/game build changed.

commands:

    python3 -B source/lab/io-device/trace_audit.py --report build/io-device-lab/full-execute-r1/report.json --paired build/io-device-lab/full-audit-r1/report.json

this is native calibration only: no opaque ABI prototype, Rust integration,
actual-game qualification, or universal platform/resource claim. next is the
native-owned controller blueprint, preserving virtual dispatch and pending
IOException-only wrapping, not a whole legacy callback.

## historical source-only authoring record

this is a new finite contract, rooted in the actual native `IODevice` subclass,
not a repair, copy, or adoption of the closed 998-case model. no native compiler,
linker, executable, cargo, application, or game was invoked for this draft.
parent owns acquisition, staged verification, execution, and acceptance. twelve
synthetic tests do not qualify a native module or rust implementation.

source: `source/core/StarIODevice.cpp`, c233825b, sha256
`42e2230491e7cd8c93bd7b2a0ef1a188215b92dcaf91c04a91e45c44cf7a56a1`.
`trace.cpp` includes the actual header and subclasses the actual class. defining
`LAB_REFERENCE` selects `Star::IODeviceReference` and its existing whole-source
reference. it does not substitute a schema or reimplement the base algorithms.
old run/model/ledger/ledger_verify/ledger_run and stage.py remain untouched.

## callback and continuation contract

every callback emits `before`, `mutated`, then `return`; before faults emit
`before,throw`, after faults emit `before,mutated,throw`. even read-only callbacks
have an explicit unchanged mutation snapshot. each event carries operation,
per-operation occurrence, phase, pointer kind/relative offset, request length,
result count, argument, seek mode, result value, mode, cursor, initialized caller
output, sink, and known-write chunks. row keys are case/options/outcome/value plus
final mode/cursor/output/sink/writes/events. options are the fixed callback input
script; expected rows never consume observed native values.

`Primitive.call` owns effects; `Controller` owns source call continuations. a
callback writes at its ACTUAL caller-relative offset before an after fault.
throwing skips every later continuation but retains that write and cursor change.
restoration is a continuation, not automatic cleanup. the permanent second-read
witness expects `AABBQQQQ`, cursor 0, with the final event `throw`, no restore.
write counterpart retains `abcd`. before-second-read retains `AAQQQQQQ`, cursor -2.

pointer kinds: caller (initialized eight Q bytes), input (`abcdefgh`, including
live ByteArray input), temp (first live native temporary callback pointer is its
base), null, or none. raw addresses never enter the protocol. each native read
callback records only the chunk it just initialized, before throwing. failed
ByteArray temporaries and uninitialized tails are never inspected. successful
ByteArray result bytes are observed only where the source/selected full override
guarantees complete initialization. caller output is separate from temporary
writes. empty calls guard all memory access with `n>0`; no null memcpy/memset.
size-max requests return zero with no byte access or allocation, before unsafe
arithmetic. positive requests and chunks stay within actual eight-byte storage.

exception outcomes distinguish IO/EOF/OTHER and same/new/wrapped. native same
means the retained `exception_ptr`, not just an equal message. size catches IO
(including EOF), constructs a new IO exception, and retains the marker in its
cause text; OTHER remains the same exception. native open checks the actual raw
missing-closing-quote message. base deviceName checks its actual self pointer
before projection to `IODevice <SELF>`. unequal open alone calls the name
callback; reentry from that callback sets mode 4. equality remains lazy.

atEnd's left-operand-first trace is restricted to the parent's Apple native
compiler profile; the C++ source does not impose that operand order universally.
destructor value is an external derived-close override counter. its mode/cursor
snapshot is taken BEFORE deletion; it does not read destroyed fields or claim
to observe the base mode store after lifetime end. the actual base destructor is
exercised, while that internal final store remains source-traced.

## finite source exercise map

`python3 source/lab/io-device/trace_contract.py map` emits exact case IDs for all
22 definitions. this is a source exercise map, NOT compiler coverage. line/action:

| line | action | contract |
| --- | --- | --- |
| 7 | construct | all 256 uint8 modes |
| 11 | destruct | base dispatch, live pre-delete snapshot only |
| 15 | resize | always new IO exception |
| 19 | readfull | single read even zero, short end classification |
| 31 | writefull | single write even zero, short end classification |
| 43 | open | equality lazy, unequal name/throw/reentry |
| 48 | close | mode zero |
| 52 | sync | no callback or change |
| 54 | name | actual self address before projection |
| 58 | atEnd | pos >= size, narrow compiler order |
| 62 | size | save/seek-end/pos/restore, IO-only wrapping |
| 74 | readabs | save/seek/read/restore only on success |
| 82 | writeabs | save/seek/write/restore only on success |
| 90 | readfullabs | virtual absolute loop, no end on zero progress |
| 101 | writefullabs | same continuation boundaries |
| 112 | readbytes | zero bypasses virtual full; defined success bytes |
| 122 | writebytes | empty still calls virtual full |
| 126 | readbytesabs | zero bypass, temporary offsets/known writes |
| 136 | writebytesabs | empty calls full wrapper; base then no IO |
| 140 | set | all 256 modes after reset |
| 144 | copy | actual protected base copy, all 256 modes |
| 148 | assign | actual base assignment and self-copy, all 256 modes |

corpus order is fixed in both independent fixture and contract: 256 mode matrix;
all actions; zero/four lengths × zero/two/four chunks × end bool; null zero and
size-max zero-progress calls; virtual absolute/full/size dispatch; lazy/reentrant
open; then fault action × callback × occurrences 1..6 × before/after × IO/EOF/OTHER.
unused fault sites intentionally yield unfaulted rows. overrides are selected
only where a source virtual call reaches them; direct qualified base calls bypass
their own override. full-read overrides fill the entire successful temporary.

## commands and acceptance boundary

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s source/lab/io-device -p test_trace_contract.py -v
    python3 source/lab/io-device/trace_contract.py freeze
    python3 source/lab/io-device/trace_contract.py expected
    python3 source/lab/io-device/trace_contract.py map
    python3 source/lab/io-device/trace_contract.py check parent-owned.stdout

native fixture takes NO arguments and emits the complete ordered NDJSON corpus.
there is no capsule CLI. parser enforces exact recursive types (bool != int),
keys, case IDs/order/count, initialized-byte counts, events, and duplicate-key/
nonfinite rejection. `TRACE_MATCH_ONLY` deliberately is not a receipt/native pass.
parent must bind full artifact/source/compiler/closure/execution receipts and
reject integrity corruptions before any native execution. freeze counts/digests
below precede any full-corpus native observation. do not fit expectations to a
native mismatch: first falsify against source.

synthetic tests include post-second-callback retained mutation, pre-fault effects,
write effects, restore failure, temp-only writes, IO/EOF/OTHER wrapping identity,
null/empty distinctions, lazy open/reentry, full uint8 domain, source map and
known-corrupted maps, full synthetic roundtrip, and rejected mutations of pointer,
phase, kind, numeric type, byte count, case ID, field schema, row count, duplicate
keys, and nonfinite JSON. these are synthetic verifier negatives, not native
semantic controls. no native run, compiled coverage, game image, or rust claim.

NEVER execute a whole-corpus pointer-no-advance/ignore-short mutant: it can make
readBytes return an uninitialized tail. the parent's existing bounded six-case
ledger may serve as a normal-exit semantic control capsule, or a separately
source-justified exception-classification control may still throw safely. none
was executed here. no old approach's failed-attempt budget is reset.

## frozen synthetic record

freeze values and artifact hashes follow after final source-only checks. the
parent must retain this draft if its compiler/contract checks fail; no acceptance
or replay has been earned by generating these files.

final synthetic freeze, 2026-10-26 01:32 utc: **8021 rows / 22 definitions**.
canonical expected NDJSON sha256:
`02fb99395f74f0fdd7dd7f7e68073bb098eccb4e6afda05f6672405dcece43b8`.
final unittest run: 12 tests, 33.181 seconds, OK. final tracked diff whitespace
check passed; these four new untracked files were the only files written by
this worker. concurrent parent changes were preserved. no commits or nested
workers. worker budget: hard eight minutes, stopped with draft unaccepted.

artifact sha256:

- trace.cpp: `5662d0ce50c6dc2e7d0ee5f9d1cd4fc26fc4ad14aef2c1aee89dc91595644a98`
- trace_contract.py: `4a269f80282b352b5d9b0062811f6a4dc9b454153cb585006efa7e64bf66e104`
- test_trace_contract.py: `ccc947232169703f09624ab589939e3b6ae4ae625478e1bc78183fe289904205`

next action: parent source review and staged acquisition/integrity checks. no
full22 native PASS, rust/ABI, platform, actual-game, or image claim is available.
