# terminal implementation partial — do not run

parent revision: `da2761201d99041a34b11a261bbb71b61d4f421a`.
host/worktree: macos arm64, `/Users/bdsqqq/www/OpenStarbound`.
state: **halted; global mechanical budget 2/2 closed**. zero class acquisitions,
zero compiler/linker/class/Rust/game commands, zero admitted stages. no commits
or delegates. do not repair, resume, rename, or start another conformance variant
under this effort. parent independent review is the next action.

the source is an implementation draft, not a functioning qualified acquirer.
the terminal evidence and hashes are under `build/lru-staged-native-r1/`.
`terminal.typed` and `seal.typed` are post-observation diagnostic metadata,
not native products, admission certificates, or an acceptance oracle.

## actual attempts and evidence

1. the first conformance invocation failed before any subprocess at
   `acquirer.py:189`: fixture rules accidentally used byte `b'stderr'` instead
   of string `'stderr'`. only the fixture program/bootstrap directories exist
   at `build/lru-staged-native-r1/positive-opaque/`. no contract, receipt or
   certificate. this is counted conservatively as mechanical failure one.
2. after the one correction, the fresh `controls-r2` invocation completed
   whole-plan typed freeze and started one Python fixture through the guarded
   executor. the host rejected creation of `opaque-\xff-\x93.o` with
   `OSError: [Errno 92] Illegal byte sequence`; see the retained binary stderr.
   stdout/stdin are empty. this is mechanical failure two. no change to the
   byte-domain fixture was made to fit the platform.

the executor then raised `FileNotFoundError` while snapshotting the absent
product at `acquirer.py:301`, before writing its process receipt. consequently
the child PID/PGID/exit status were not durably recorded: do not manufacture
them from the supervisor exit status. the synchronous `communicate` returned;
a later read-only process scan found no matching fixture Python processes.
the descendant-timeout test was never reached and no signals were sent.

all known-bad controls after the initial positive fixture are **unexecuted**:
false-as-zero/partial/wrong argv/env/stdin, missing/stale/replaced/symlink/hardlink
objects, escaped logs, unexpected outputs, input mutation, alias/runtime drift,
semantic-before-dependent admission, timeout/descendant reaping and corrupted
receipt/certificate reconstruction. source definitions are not evidence they
work. no positive fixture has passed live admission or reconstruction.

## implemented source, unqualified

- `acquirer.py`: unchanged shared Stage/Plan/Receipt and typed codec; explicit
  process contracts; exclusive physical file checks; identity/hash/alias
  snapshots; one Popen site; semantic admission before certificate/receipt
  credit; read-only reconstruction through the same `admit` function.
- `recipe.py`: source/configuration-derived Ninja Core/extern membership,
  compile DB/profile agreement and typed discovery manifest. it explicitly
  withholds dependency freshness/native admission. this module was imported
  but its discovery/validator functions were **not run**.
- `worker.py`: only the configured discovery worker. not executed.
- `conformance.py`: retained test draft; stops at the first positive fixture.
  its final summary emitter was never reached and is not a budget authority.

## remaining blockers and review findings

**verified:** missing-product snapshotting precedes process-receipt persistence
(`acquirer.py:294–303`), so an unsuccessful command can lose durable PID/status
evidence. reproduced by the second invocation. no repair was attempted after
budget exhaustion. falsification would require a retained strict process record;
none exists in the artifact tree.

**verified by source tracing, not executed exploit:** `check_frozen` revalidates
the shared Plan, files and aliases but does not revalidate every command field
or a separately trusted contract seal (`acquirer.py:214–220`). the serialized
dict is mutable. there is no persistent in-executor global budget gate. these
are further reasons this draft is not ready for caller-supplied plans or class
admission. no claim that a PASS dict or reconstructed certificate proves process
authenticity against deliberate rewriting of both evidence and baseline.

the complete class pipeline is **unimplemented/unexecuted**: validated discovery
to immutable next-plan generation, existing source1495/config472/dependency
witness reconciliation, SDK/tool freeze, AST12/lambda/10usedimplicits admission,
fresh original/current/isolated-mutant compilation, expanded driver/runtime and
libLTO closure, archives/SDK consumed origin, map/trace/surviving actual provider
and code edge, preexecute barrier, 640 records/both aliases/repeats/three normal
mutants, six literal groups/twelve language properties, reconstruction controls
and exclusive PASS. unknown SDK origin, ambiguous/missing archive, omitted
runtime/libLTO and wrong-dispatch/call-edge controls are not implemented here.

no old runner was imported, repaired, run or used as an acceptance source.
the original/current production header remains SHA
`b0ca8540168e7c90d375c9f7b327c568bd2e3d1d9c5df99febaee9f5658cadd7`.
no production/shared helper/old lab/model/failed artifact edits were made.
parent-owned `doc/rust-migration-plan.md` changed concurrently and was not edited
by this implementation task; pre-existing storage is untouched. no engine,
platform, SDK resolver/loaded-framework, race, OOM, ownership/ABI or Rust claim.

next: parent reviews the frozen source and retained failure evidence, reconciles
the terminal 2/2 budget, and records the outcome. this handoff does not authorize
another acquisition, class execution, or local commit by this implementation task.
