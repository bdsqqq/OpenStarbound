# framebuffer behavior lab

this is the first screenshot/state gate for the rust lighting migration, not a claim of game parity. captures use the real native client; unit fixtures only prove verifier sensitivity. inspect the expected/candidate/diff artifacts after an automated pass. the machine report deliberately leaves `parityCertified: false` pending that inspection.

```sh
# pillow is supplied by nix-shell when the current python lacks it; no pip install.
bash scripts/behavior-lab.sh self-test

# native apple silicon: build both source-bound clients first (SDKs OFF)
bash scripts/build-behavior-lab.sh

# diagnostic single run; does not certify parity
bash scripts/behavior-lab.sh --capture /absolute/client --assets /absolute/packed.pak \
  --output build/behavior-baseline-a

# repeat the single capture into build/behavior-baseline-b, then diagnose cpp repeatability
bash scripts/behavior-lab.sh compare --same-backend \
  --reference build/behavior-baseline-a/frames --candidate build/behavior-baseline-b/frames \
  --output build/behavior-baseline-repeat-check

# baseline repeats MUST pass before a candidate process starts
bash scripts/behavior-lab.sh run --reference /absolute/cpp-client \
  --candidate /absolute/rust-client --assets /absolute/packed.pak \
  --reference-repeat --output build/behavior-first-gate --timeout 180

# independent, nonwriting verifier; inputs are sealed frames/ directories
bash scripts/behavior-lab.sh compare \
  --reference build/behavior-first-gate/reference/frames \
  --repeat build/behavior-first-gate/reference-repeat/frames \
  --candidate build/behavior-first-gate/candidate/frames \
  --output build/behavior-recheck
```

all output paths must be new, non-symlink directories strictly beneath this checkout's `build/`. existing directories, the checkout's `storage/`, home, and symlink traversal are refused. each run has separate sentinel-marked storage, home, capture outputs, bootconfig and process log. no run directory is reused or cleaned automatically. only the private process group created for a launched client is terminated on timeout/interruption; processes are never selected by executable name.

## raycast-room (strict traversal gate)

`capture` and `run` accept `--scenario lighting-room|raycast-room`; lighting remains the default, including the Python `capture(..., scenario="lighting-room")` API. comparison autodetects receipts and refuses unknown/mixed scenarios. the requested scenario is sealed in the scenario configuration and its normalized manifest identity; receipts cannot silently substitute another scenario.

```sh
# traversal-only: C++ lighting in both, shared all-C++ reference
bash scripts/build-behavior-lab.sh traversal
# candidate: build/behavior/traversal/candidate/bin/starbound
# `combined` builds both Rust backends under build/behavior/combined/candidate/.
# no argument retains the original lighting-only build.
bash scripts/behavior-lab.sh run --scenario raycast-room \
  --reference /absolute/cpp-client --candidate /absolute/rust-client \
  --assets /absolute/packed.pak --output build/behavior-raycast-gate
```

ray frames are exactly `ray-clear`, `ray-blocked`, `ray-restored`, with stage indices 0/1/2 and the same three base actions as lighting. every native `SCENE_FIELDS` entry and existing stabilization/lighting/backend receipt remains required. the 128×96 room uses camera `[64,48]` at pixel ratio 2, offscreen player `[12,4]`, and the static lamp at `[52.5,33.5]`; fullbright is forbidden. changed bounds are `[62,33]`–`[70,59]`; only this scenario adds both columns x62 and x70 through y33…59. initial/restored pixels and semantic state must match exactly; blocked pixels must differ.

`metadata.raycastState` has EXACT keys `start`, `end`, `occluderColumns`, `markerEnd`, `client`, `server`. geometry is `[54.5,48.5]` → `[74.5,48.5]`, columns `[62,70]`. each side has EXACT keys `collision`, `point`, `normal`, `tiles`, `limitedTiles`, `zeroLimitTiles`, `backend`, `rustCalls`. these represent actual public world `lineTileCollision`, `lineTileCollisionPoint`, and unlimited/limit1/limit0 `collidingTilesAlongLine` queries with `DefaultCollisionSet` and `includeEdges=true`, not generated observations. `rustCalls` has exactly `collision`, `point`, `tiles`, `limitedTiles`, `zeroLimitTiles`, each an integer successful-call delta measured around that query on its executing thread.

clear/restored observations are false collision, null point/normal and three empty lists. blocked observations are true collision, point `[62-0.0001f,48.5]`, POSITIVE normal `[1,0]`, ordered tiles `[[62,48],[70,48]]`, limited tiles `[[62,48]]`, and empty zero-limit tiles. the point offset is intentional (`StarWorldImpl.hpp`), not x62 exactly. only the fixed expected-point assertion rounds its decimal input to f32 to accommodate C++ JSON precision; raw point numbers remain in exact cross-backend and client/server comparisons. `markerEnd` must equal the actual client point, or the endpoint when clear, for the native WorldPainter marker.

each ray PNG must also contain visible result-local marker ink, even if all compared images are identical. projection uses the frozen native camera and `TilePixels=8`: `x = width/2 + (worldX-64)*16`, `topY = height/2 - (worldY-48)*16`. the nonzero `start` → actual `markerEnd` segment must be inside the viewport, with cyan ink within 3 physical pixels of that segment (`R<=64, G>=128, B>=128, A>0`), and yellow ink within ±8 physical pixels of actual `markerEnd` (`R>=128, G>=128, B<=128, A>0`). bounded local assertion ROIs cannot be satisfied by colors elsewhere (including the distant static lamp). these are presence assertions, not a complete shape/continuity test; full-frame RGBA comparison remains exact and UNMASKED, including pixels outside these ROIs. no receipt fields are added.

historical `build/behavior/raycast-isolated-r1/candidate/frames` is rejected by this gate: `raycast marker missing cyan ink on result segment`. its earlier pixel/state pass did not prove visible marker rendering. those artifacts remain unchanged; fresh source-bound runs and inspected visible-marker evidence are recorded in [`../traversal/EVIDENCE.md`](../traversal/EVIDENCE.md).

ray primary backend receipts are each side's `backend`/`rustCalls`: cpp requires ALL zero; rust requires EACH positive. reference and repeat must be cpp; candidate must be rust. only these proof labels/counters are removed from semantic ray equality, never query results, start/end, or marker. ordinary lighting receipts are still validated; ray candidates may use cpp lighting (isolated traversal) or rust lighting (combined test). lighting-room still requires rust candidate lighting unchanged. assets/provenance/configuration, baseline independence, pixel and restoration gates are not relaxed.

unit fixtures are native-shaped synthetic verifier-sensitivity controls ONLY. they do not establish actual public API execution, replication, TLS instrumentation, marker rendering or real-game parity. the executed traversal-only/combined runtime matrix is recorded separately in [`../traversal/EVIDENCE.md`](../traversal/EVIDENCE.md); it does not imply universal gameplay parity.

## capture contract

`STAR_BEHAVIOR_LAB` names an absolute json config with `outputDirectory`, matching absolute `storageDirectory` strictly beneath that capture root, the chosen `scenario: "lighting-room"|"raycast-room"`, `maxFrames: 1800`, and `platformWrites: false`. native integration must bypass platform services under this opt-in; a json flag alone cannot disable steam/discord. the bootconfig also sets `includeUGC: false`, isolates storage, uses only the explicit packed asset source, first-party `assets/opensb` overlay and test-only `source/lab/behavior/assets` overlay, and disables window maximization.

native `<name>.json` envelopes must contain `name`, `file`, `width`, `height`, `capture.source: "final-default-framebuffer"`, `capture.stage: "after-imgui-before-swap"`, and the caller's unmodified `metadata` object. that metadata must supply:

- a known chosen `scenario`, `inWorld: true`, nonempty `stage`, and the complete native flat scene schema below (an optional nonempty `worldState` supplements it, never bypasses it);
- explicit `lightingBackend`; lighting-only comparison requires cpp reference/rust candidate, while ray traversal uses its separate backend contract above;
- integer `rustLightingCalls`, zero for cpp, positive for rust.

`worldState` is the explicit semantic comparison boundary. the native flat driver schema is projected using `SCENE_FIELDS` in `behavior_lab.py`: world/player/camera identity and positions, stabilization assertions, materials, replicated light identity/position/color/type, occluder geometry/state, action, seed and stage index. all listed fields are required and compared exactly. ui-hidden, offscreen-player, completed-lighting and replicated-light assertions must be true; fullbright must be false. `replicatedSettledUpdates` must be at least 90 but, like `updateIndex`, is a scheduling diagnostic rather than an exact state field. neither is used to excuse unstable pixels. no comparison region masking/cropping, adjustable tolerance, or golden update path exists; ray marker presence uses separate bounded assertion ROIs only. exactly `lit-room`, `occluder-added`, `occluder-restored` are required. initial/restored pixels and stable/declared state MUST match; the occluded pixels MUST differ, with the expected action, stage index and observed foreground material. missing/extra/generic frame names fail in standalone comparison too.

the fixture overlay defines `behaviorlabconstantlight`, a static 8×8 sprite with one constant `[255, 210, 160]` `PointAsSpread` light (explicitly matching the normal opensb object postload patch). it has no scripts, animation configuration, particles, sounds or flicker. its single occupied tile is placed through `ObjectDatabase::createForPlacement` at `(52,33)` with a bottom anchor requiring the `smoothmetal` floor at `(52,32)`; its light center is `(52.5,33.5)`. missing assets, invalid placement, dynamic behavior or anything other than one emitted light fail rather than falling back to vanilla lamps. this is synthetic scene input, NOT a synthetic framebuffer: real object loading, authoritative world placement, replication and world rendering remain exercised. only lab-generated bootconfigs register this overlay.

the expected native stages remain `lit-room`, `occluder-added`, `occluder-restored`: initial/restored pixels should match and the occluded frame should differ. actual native execution, the original one-pixel failure and its production-arm arithmetic repair are recorded in [EVIDENCE.md](EVIDENCE.md); unit tests alone validate only the asset contract, runner isolation and verifier sensitivity.

`build_provenance.py` snapshots compile inputs before/after successful builds and seals `<binary>.behavior-build.json`. capture rejects missing/stale proof BEFORE creating outputs or launching; it rechecks after execution. manifests retain the source-bound proof, so historical comparison is explicitly about those recorded inputs, not whatever source is checked out later. these unsigned local receipts are stale-build guards, not reproducible-build attestations: external vcpkg/system SDK transitive inputs are not fully verified. document-only changes do not invalidate compiled binaries.

native envelopes also record GL vendor/renderer/version. `metadata.lightingDiagnostics` preserves the exact row-major RGB float bits uploaded for the selected lightmap, its size and world minimum. these diagnostics explain numerical discrepancies; they do not mask framebuffer pixels or widen the state gate.

manifest hashes bind binaries, packed assets, every overlay file (namespaced as `opensb/…` and `behavior-fixture/…`), boot/scenario configs and every png/receipt. comparison checks equal assets/overlay/semantic configuration, equal dimensions, exact `inWorld`/`stage`/`worldState`, backend use, and every rgba pixel. normalized config comparison removes only per-run storage/output paths, not behavioral settings. repeatability requires distinct capture identities and the same reference binary. standalone candidate comparison without `--repeat` can produce diffs but returns failure rather than imply certification. `--same-backend` is a separate baseline-only diagnostic that may pass without claiming candidate parity.

exit codes: `0` automated gates passed (inspection still required), `1` behavioral/repeatability gate failed, `2` invalid input, launch failure or timeout. partial capture failures retain logs; use a fresh output path to retry. python 3 with pillow is required; nix fallback uses `python3` and `python3Packages.pillow`.
