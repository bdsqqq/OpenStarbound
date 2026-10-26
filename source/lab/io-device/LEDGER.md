# draft native partial-mutation trace witness — unexecuted

contract frozen before native execution, 2026-10-26 00:35 utc start.
source: StarIODevice.cpp:75-116. exactly six cases: read/write × none,
before-second-IO, after-second-IO. cursor 6, absolute -4, length 5, chunk 2;
initialized read output eight dots; write input abcdefgh. callback ordinals
count only leaf I/O. each pos/seek/I/O emits BEFORE and RETURN, with MUTATED
for effects and THROW for the exact retained IOException object. snapshots
include cursor, caller-relative pointer, remaining request, result count,
initialized output and sink. no raw addresses or null memory operations.

successful requests are (-4,0,5,2), (-2,2,3,2), (0,4,1,1), each saving/restoring
cursor 6. final read AABBC..., sink abcde, cursor 6. pre-second failure keeps
AA...... / ab and cursor -2; post-second failure keeps AABB.... / abcd and
cursor 0. throwing skips restore; loop pointer/offset/remaining advancement
occurs only after the entire absolute operation returns. ledger_verify.py
models only primitive callback effects against that fixed source schedule,
and independently asserts the literal final states. expectations never derive
from executable output.

mandatory normal-exit semantic controls compile whole actual source: remove
pointer advancement only in full-absolute loops; restore cursor on catch only
around leaf read/write in base absolute routines. the fixture catches errors,
records them, and exits zero. both must be rejected by the independent ledger.
synthetic event loss/order and binding corruptions are separate integrity checks.

scope: finite native witness only. not all 22 definitions exercised; no Rust,
ABI, game, native-project build, sanitizers, OOM, or universal platform claim.
old lab files, model, evidence and 998-case approach remain immutable and closed.
no nested delegation or commits. hard budget eight minutes from 00:35 utc;
parent unit deadline 00:49 utc; at most two failures per approach, no reset.

commands (fresh ledger-* output required):

    python3 source/lab/io-device/ledger_run.py --output build/io-device-lab/ledger-r1
    python3 source/lab/io-device/ledger_verify.py build/io-device-lab/ledger-r1

all generated receipts, maps, dependencies, native closure and before/after
seals are retained in that directory. report.json records the observed result.

## closed acquisition attempts

both attempts failed before executing any witness case: r1 confused 202
provenance inputs with 113 archive objects; r2 compiled/linked the original but
tried to decode non-UTF8 linker symbols. **zero cases and zero semantic controls
executed.** this monolithic acquisition approach exhausted two attempts; do not
rerun it under a new output name or repair it as a third attempt. all six-case
expectations remain untested drafts, not observed goldens or a module pass.

parent independently added/tested `../native_artifacts.py`: byte object-table
parsing and configured archive-member matching. six synthetic tests and the
actual retained map/archive tables pass; this does not execute the witness.
those helpers are deliberately not wired into this closed runner. a genuinely
different, staged acquisition/verification/execution design is required before
another native approach. full 22-definition calibration and Rust stay blocked.
