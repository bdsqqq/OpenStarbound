# native lru unwind repair — source handoff

host/worktree: apple silicon macOS, `/Users/bdsqqq/www/OpenStarbound`, shared parent checkout. owned writes ONLY `source/lab/lru-boundary/**` and `build/lru-boundary-unwind-r1/**`. old `build/lru-boundary-r1/**` is immutable; its strict pass did NOT exercise insertion-time Value copy failure and is not evidence against the confirmed defect. original source snapshot remains `build/lru-boundary-before-unwind-r1/source/**`; this repair also preserves its exact failing-acquisition source in `build/lru-boundary-unwind-r1/before-source/**`.

this source handoff is frozen BEFORE repaired acquisition so it remains a tested input. terminal status, actual report/binary/source hashes, command counts, process-group audit and final seal belong to `build/lru-boundary-unwind-r1/HANDOFF.md`; do not infer completion from this document alone.

## confirmed failure and falsification

VERIFIED by actual both-alias execution: `before/unwind-run.stdout` records native pair/producer destructors `D:70:1,D:70:1`, while the old mock records `D:70:0,D:70:0`. producer construction and move succeed; the first Value copy in real `StarOrderedMap.hpp:327` list-node insertion throws `CopyFault`, token731, exact message `list-node-copy-sentinel`. success traces agree. guarded destructor reentry removes unrelated key9 only while unwinding: native retains keys8, old mock retains9,8. neither the active input key7 nor an active node is invalidated. records are fixed-capacity/nonthrowing, including destructor observations.

failing witness was acquired BEFORE repair, never reclassified as an overall acquisition pass: after all native commands/model runs completed, acquisition verification hit an `UnboundLocalError` because a new local `witness` shadowed the tool-witness function. `before/STOP.typed`, all PID/status/I/O records and source bytes are retained. corrected by renaming that local to `unwind_lines`, not changing tests/outputs/models. first unexpected acquisition failure; do not resume/rebind this before tree. its source bindings are historical after explicit repair. this failure does not erase its recorded native/mock divergence.

second unexpected attempt: `after/` stopped BEFORE any fresh native compilation at retained full global source closure, because parent-owned Rust lib/module files changed concurrently. after these two failures, changed the provenance mechanism rather than retrying the same guard: `source_delta` permits ONLY those exact two paths, ONLY absent from all retained/fresh compile dependencies with all25 selectorsOFF. `source-closure.typed` preserves the historical map AND prebinds complete live membership, with replay/preexecute checks; boundary source membership is likewise explicit. four isolated policy controls reject changed/removed Core source, a third Rust path, and a consumed Rust delta. no original game receipt is relabeled current. `after/STOP.typed` is preserved; first repaired acquisition used fresh `after-r2/`:2874inputs/187products,25normal commands; actual640rows/12properties×4, original39controls, all six real-alias comparisons and decorated find/filter lifetime traces passed. strict audit passed6controls, but inspection showed the added wrong-marker fixture only coherently updated the product hash, not its receipt stdout hash, so it rejected at transport integrity rather than semantics. preserved `after-r2/` and exact source in `after-r2-source/`; strengthened the fixture to rehash BOTH output and receipt, then require rejection by the same marker check. also strengthened the decorated iterator test from targeted assertions to full event/state trace equality. no native repair/model/ABI/profile change. final fresh reacquisition uses `after-r3/`; these are verifier-test refinements, not a hidden semantic failure or resume.

## smallest repair

VERIFIED by source trace: `cache.hpp:52–59` restores stage AFTER `sb_lru_run` returns, then rethrows pending status1 inside the owning native frame. pair/producer full-expression temporaries now unwind before the enclosing host catch returns status to the next controller. the find/filter owning iterator scopes receive the same treatment. `Borrow` clears borrowed pair/iterator slots on normal and exceptional exits (`cache.hpp:61–66,94–102`). all host callbacks remain noexcept; `cache.hpp:120` catches before returning to any outer controller. root execute likewise rethrows only after controller return. exact exception_ptr/type/message/partial effects remain, no rollback and no foreign unwind through a controller frame.

no ABI structs/enums/signatures changed. no map/header/algorithm/model/fixture/profile/domain/snapshot-prvalue changes. constructor trimming remains: original constructor calls setMaxSize. unchanged map+limit layout and implicit lifecycle. `host_controller.cpp` is still a bounded C++ MOCK, not Rust. its1e6calls/128depth are LAB LIMITS ONLY; parent-owned production Rust must stay native-unbounded with an out-of-band test timeout.

## acceptance commands and evidence

fresh repaired acquisition uses `after-r3/`, never an old binary or resumed runner:

```sh
python3 -B source/lab/lru-boundary/acquire.py
python3 -B source/lab/lru-boundary/audit.py --controls
python3 -B source/lab/lru-boundary/audit.py
```

required terminal report: `after-r3/report.typed`, status `FINITE_LRU_MOCK_UNWIND_REPAIR_PASS`. unchanged640rows/12properties, real ordered/hash aliases twice each; existing39controls; real-alias success/copy-fault/destructor-reentry companions; supplemental decorated real ordered-map find/filter iterator-destructor controls; C11 struct-size parse. `after-r3/unwind-run.stdout` must have six exact `comparison` rows equal plus iterator and final pass markers. all events must be inspected, not just the marker. fixed-capacity test observation must not overflow.

source membership/profile/full retained113-object dependency closure and static SDK barriers precede compile; expanded runtime/plugin/archive bindings precede link. actual PID/PGID/start records precede waiting/product checks; receipts bind exact argv/env/stdin/stdout/stderr/status and explicit120s timeout. fresh main/controller symbol ownership and call edges are reconstructed from map/disassembly. no claim of loaded frameworks, race prevention or OS sandboxing.

acquisition verifier corruptions: source bytes, object bytes, bool-as-exit0 and coherently rehashed wrong unwind marker. strict audit additionally rejects omitted input/product; all6 strict controls must reject through the same verifier. report/product/source bytes are frozen; final post-observation seal also covers the preserved failed evidence and final handoff without rewriting either.

## source identities

- repaired `cache.hpp`: `9fbd1f8c720fe0172dd69d78caafccc372ccdfed0503899bcf50dcd9350a864c`
- stable `host_api.h`: `144b3d1056ef3a14efee2834c8d6074ceaac8e4dda2c237959d90a84a71b0d90`
- stable mock `host_controller.cpp`: `4668676f3290bcce8270cc08cc0d174e0fad41e3340d79c8e64c66df0fba6864`
- original native header remains `b0ca8540168e7c90d375c9f7b327c568bd2e3d1d9c5df99febaee9f5658cadd7`

## limits and next action

finite native/mock evidence ONLY: no production, Rust, selector, game, deep/huge-domain, universal generic allocator, OOM, concurrency or supported-platform qualification. decorated iterator probes supplement but do not replace mandatory real-alias insertion witnesses. no actual process-timeout injection here. no Cargo/commits/network/Steam/storage/out-of-scope logs, no nested delegation. parent owns Rust/integration/independent read-only acceptance and application gates. inspect final artifact handoff and replay strict audit before consuming this repair.
