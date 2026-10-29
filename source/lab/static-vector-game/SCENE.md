# static-vector-room — source-only seam26

status: source controls and finite current-source **c++ syntax parsing passed**
at `f29e41d44ae6d9e79261bd112c72cc413a757f25`. **not object-built, linked,
game-built or runtime-tested.** no actual game admission or parity claim.
parent owns integration, readers, retention and commits.

## why this seam

`WorldClient::render` fills the ordinary `renderData.tiles` through its existing
`m_tileArray->tileEachTo`. that function iterates the actual return value of
`TileSectorArray::splitRect`, a `StaticList<SplitRect, 2>`. the ordinary
`WorldPainter` consumes those same tiles downstream through tile painting/drawing.
there is no scene-created vector, proxy collection, image overlay or rust policy
copy in this scene.

`StarList.hpp`'s initializer-list constructor default-constructs its base and
calls `append`, which calls `Base::push_back`, which calls `emplace_back`. for
the required two-split return, the predeclared root deltas are:

| mode | root delta |
| --- | ---: |
| default constructor (0) | 1 |
| push back (13) | 2 |
| emplace back (19) | 2 |

all 26 continuation deltas must be zero. other root modes are recorded, not
assumed zero. this is NOT the range-copy constructor. thresholds must not be
fitted to a future measurement.

## observation boundary

- `StarTileSectorArrayObserver.hpp`: null-by-default thread-local observer and
  fixed, statically asserted pod state; only arrays, scalar integers, booleans
  and an identity pointer. the observer itself adds no allocation, json, logging,
  or collection calls in the observed interval. rust count references and includes are feature-guarded;
  native-off snapshots are explicit zeroes. scope guards are noncopyable so a
  copied guard cannot duplicate a snapshot or disarm the original scope.
- `StarClientApplication.cpp`: a frame guard arms only the new scene's ready,
  non-pending ordinary `WorldClient::render` call. unwinding always disarms.
- `StarWorldClient.cpp`: a scoped guard binds the actual array identity, world
  size, client window, padded tile range and buffer at the existing callsite.
- `StarTileSectorArray.hpp`: a local split guard snapshots immediately on entry
  and during local destruction after return-value construction. original return
  expressions and loop lifetimes remain unchanged. the existing returned-split
  loop records actual ordered rects and offsets, at most two.
- column callbacks may run in parallel. no worker callback observes counters or
  tiles. after normal world rendering returns, proof preparation samples the
  real render buffer using `tileMinPosition` and `WorldGeometry::pdiff`, with
  bounds checks and comparisons against replicated world foreground/background.

proof is refreshed on EVERY ready render, including repeated renders of one
stage while lighting settles. stage is monotonic 0/1/2; queuing requires matching
stage and current render sequence. `painterSubmitted` becomes true only after
the existing ordinary `WorldPainter::render` returns for that same sequence.

## wrapped fixture

only `static-vector-room` uses `behavior-static-vector-room`. the normal 128×96
world, pixel ratio 2.0, player (12,4) and player platform (8..18,0) are retained.
room-only x coordinates shift by -64 modulo 128: room 40..88 becomes
104..127/0..24; platform 68..80 becomes 4..16; lamp (52,33) becomes (116,33).
the lamp still uses ordinary object placement, authoritative insertion and
replication; its replicated object position is checked before capture.

two authoritative regions are generated: `[0,0,40,66]` and `[96,0,128,66]`.
the camera is (0,48), allowing the geometry-equivalent x=128 representation.
there is no viewport/world shrinking or flag fitting. the observed tile range
must satisfy `0 < width < 128`, `pmod(xmin,128)+width > 128`, and the original
split domain `[-128,256]`; exactly one callsite, one split call and two returned
rects are required. failure is a failed admission, not permission to change the
fixture until it passes.

normal baseline/add/remove lighting stages and 90 replicated settled updates
are reused. only columns **126 and 2**, y=33..59, change foreground material.
both columns and background markers at x=116 and x=12 are checked against actual
render tiles. no visible label or backend-dependent pixel modification is added.
restoration may correctly match baseline: do NOT require three distinct image
hashes. native-vs-native repeatability and baseline-vs-added visual change still
need fresh actual acquisition.

## receipt contract

`staticVectorProof` accompanies the existing general frame metadata:

- `version`, `scenario`, numeric `stage`, `backend` (`native`/`rust`), `selector`;
- `frameSequence`, `scopeId`, actual route, world/window/range/buffer;
- `callsiteCalls`, `splitCalls`, `returnedRects`, ordered `splits` (`rect`, `xOffset`);
- `countersBefore`/`countersAfter`: 26×2 unsigned 64-bit values serialized as
  exactly 16 lowercase hex digits, including off-backend zeroes;
- actual `tileMinPosition`, world/render index and foreground/background samples;
- `occluderColumns`, `painterSubmitted`, complete scene `configuration`;
- pointer and thread hash under `identityNotParity`: nondeterministic identity,
  NOT cross-backend parity fields.

general metadata names the new scenario and reports the actual camera, wrapped
occluder material, adapted bounding box and explicit noncontiguous
`changedColumns`. all old scene metadata/fixture/camera branches project back to
the preserved before bytes when removing the additive scene changes.

on the third acknowledged capture, completion requires stage 2, the same queued
and prepared sequence, an acknowledged frame name, no pending frame, an already
disarmed observer, and both owned columns absent in the client AND authoritative
world. completion verifies removal; it must not repair removal then call it
proved. only then is `static-vector-restoration.json` written within the already
validated private output directory, with `complete:true`, final sequence/name,
last stage, owned-column absence and disarmed state.

update/render failure handlers additionally contain cleanup exceptions, then
rethrow the original failure; diagnostics cannot replace its type or message.
update/render failures, timeout and shutdown disarm and attempt restoration via
the real authoritative dungeon writer before disconnect. ownership is marked
before mutation, retained on failed cleanup for a shutdown retry, and cleared
only after verified restoration. abort never writes a completion receipt. if
the authoritative world/connection is unavailable, no completed cleanup claim
is made; the parent must treat missing restoration evidence as failure.
existing id-map cleanup is retained.

## source checks and pending falsification

run, without creating bytecode artifacts:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 source/lab/static-vector-game/test_source.py
```

the checker pins before manifest
`31f3321d144eab0aa467b1accacac99173508378e89f5b1ec95cf9ac3b47f9ae`
and the four before DATA hashes. removing only the named header/scope/hooks
recovers the exact original tile header and world implementation; an explicit
old-branch projection recovers the exact client and old lab declarations. these
DATA bytes are comparison inputs only, never compiled source/tool/sdk replacements.
protected core/abi/host, client header, cmake, frozen old reader/test, and all 36
rust source/cargo input identities are pinned. in-memory known-bad mutations
exercise altered original return/layout/world statements, old camera, unguarded
rust counts, missing array binding/disarm/ownership/cleanup, stale sequence,
fake tiles, missing acknowledgement/painter association/authority absence and
range-copy threshold substitution. these checks are NOT a c++ parser or runtime
proof.

parent pending: current-source object/game builds, selector configuration
evaluation, actual game seam26 acquisition, independently checked
receipt/frame reader with corruption controls, native repeatability, real light
change and restored baseline comparison, current provider/origin/code binding,
old25 regressions, auxiliary behavior, failure/timeout/shutdown cleanup tests,
validated restoration output, resource/retention accounting and final cleanup.
no old native or screenshot epoch is renewed by these source checks.

## finite syntax qualification and conserved failures

composition report `99c8a041c093a2c42830fce5ad3577a06630268c752258601c3a8bbe1f8bc7a2`
records eight successful `-fsyntax-only` leaves: ClientApplication, WorldClient,
WorldServer and TilePainter, each native-off and supported-production-on. original
window: 2026-10-29 08:44–09:19 utc. no accepted native leaf was repeated.

this does **not** mean all 30 selectors are enabled. the existing production
profile in `source/lab/id-map-production/game_build_admission.py:profiles` excludes
experimental `STAR_USE_RUST_LINE_QUERY`. the extended candidate enables the other
29 selectors, including StaticVector, and retains its actual configured fast-math
flags. old reference/candidate databases selected paths/flags only; current source,
physical sdk, compiler/resources and exact argv were bound before each process.
no old source epoch, generated game or sdk copy was substituted.

retained acquisition history:

- admission `befe2689a5196f14ab0c68c8c55f5dd2848baac155495d56885af8eb94516976`
  accepted the four off parses, then its incorrectly synthetic all-30-on profile
  triggered the existing fast-math rejection in `StarLine.hpp:8`. it remains
  **FAILED_NOT_RESUMABLE**. neither the guard nor optimization flags were weakened.
- remaining-only admission
  `3d5bf27f9c59aca001cd321d47ea3ad4aa8588ffc6af4b196cd04df923041b47`
  accepted all four on parses using the actual supported role-specific recipes.
  its producer then failed a lexical dependency-name comparison: clang emitted
  `source/client/../lab/behavior/static_vector_scene.hpp`. this producer failure
  also remains failed; all four native receipts were retained, not rerun.
- the independent composition reader pins raw dependency bytes and checks their
  admitted physical identities before comparing `resolve(strict=True)` paths.
  two lexical-alias positives and five negatives pass, including a same-content,
  same-basename file outside the expected source location. source/helper/abi
  dependency requirements are not waived. an initial composition-reader metadata
  view mismatch (cached-29 bool pairs versus source-30 names) is also retained.
  unchanged pure composition replay passed; this is not a new native acquisition.

large admission/sdk metadata was conserved with reconstruction **before** pruning:
4 files, 26,075,136 unique allocated bytes; 12,576 protected identities/bytes and
38,283 outside-selected origins unchanged. parent reconstruction/protection checks
also passed. conservation completion:
`ef850db109d1c1b31625d2977baaf3a5ffa2f4796fe60c0665b6827ed1e4b550`.
manifest: `build/migration-evidence-archive/runs/20261029-static-vector-scene-syntax-metadata-r1/manifest.json`,
sha256 `85108114663a4a8246952e12e747f78e5db7659db6c9dd24fbdaa43377635964`.
compact reports, failures, raw stdio/dependencies/receipts and readers remain in
`build/behavior/static-vector-combined-r1/`. original live-path/inode/ctime/sdk
admission replay is **UNAVAILABLE_ARCHIVED**; reconstruction is DATA only, never
an executable/tool/sdk replacement. no game/runtime/restoration claim follows.
