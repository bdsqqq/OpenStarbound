# static-vector-room — source-only seam26

status: source implementation and python source controls only. **not c++ parsed,
compiled, built, or game-tested.** no actual game admission or parity claim.
parent owns fresh compilation, integration, readers, retention and commits.

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

parent pending: fresh current-source native-on/off parsing and builds, selector
configuration evaluation, actual game seam26 acquisition, independently checked
receipt/frame reader with corruption controls, native repeatability, real light
change and restored baseline comparison, current provider/origin/code binding,
old25 regressions, auxiliary behavior, failure/timeout/shutdown cleanup tests,
validated restoration output, resource/retention accounting and final cleanup.
no old native or screenshot epoch is renewed by these source checks.
