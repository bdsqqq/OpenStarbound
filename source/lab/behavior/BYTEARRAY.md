# bytearray application gate — OPEN

implementation: `135d6e03`, default OFF. the original r3 candidate aborted during
asset startup: `ByteArray host protocol failure`, exit -6, before fixture frames.
a coherent diagnostic traced it to moved-from empty fill (mode14/op15). the
source-defined no-op repair in `../byte-array/EMPTY_FILL.md` gets r4 through asset
and database loading; a later title-world protocol rejection is still open.
`build/behavior/byte-array-actual-r1/candidate/process.log` is authoritative.
no application qualification or candidate screenshot equivalence is claimed.

fresh full native/reference and combined-Rust builds are preserved under
`byte-array-combined`, `byte-array-combined-r2`, `byte-array-combined-r3` in
`build/behavior/`. first two attribution approaches are rejected: broad TCP
intervals credited wire/event logging, then fixture getters. their repair budget
is closed. r3 measures only production readData/receivePackets, subtracts nested
observer bookkeeping, and requires TCP append mode36 rather than any-success
(getter41 may belong to observer arguments). no Core/Rust algorithm changed.

`byte-array-bookkeeping-control-r1/report.json`: normally exiting observer-only
control has raw append calls but no net append; fixture getter success cannot
qualify it. an actual unexcluded append succeeds. not a whole-game bypass test.
PCM reports `build/bytes-audio/byte-array-{cpp,rust}-r1/report.json` pass with literal
eight-sample WAV/seek/EOF/negative comparison; no audible mixer claim. twelve real
CLI exits pass in `byte-array-cli-r1/report.json`.

reference and repeat captures exist; candidate has no accepted frames. the
35-second debugger launch did not advance beyond `run`; no throw-site diagnosis
was obtained. owned orphan debugserver was terminated, artifacts retained in
`byte-array-startup-debug-r1`. do not infer the failing mode/domain from the fatal
message. next: bounded diagnostic of the real startup failure, preserve guard and
references; qualify actual consumers/images only after its cause is established.
