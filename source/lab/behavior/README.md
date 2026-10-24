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

## capture contract

`STAR_BEHAVIOR_LAB` names an absolute json config with `outputDirectory`, matching absolute `storageDirectory` strictly beneath that capture root, `scenario: "lighting-room"`, `maxFrames: 1800`, and `platformWrites: false`. native integration must bypass platform services under this opt-in; a json flag alone cannot disable steam/discord. the bootconfig also sets `includeUGC: false`, isolates storage, uses only the explicit packed asset source, first-party `assets/opensb` overlay and test-only `source/lab/behavior/assets` overlay, and disables window maximization.

native `<name>.json` envelopes must contain `name`, `file`, `width`, `height`, `capture.source: "final-default-framebuffer"`, `capture.stage: "after-imgui-before-swap"`, and the caller's unmodified `metadata` object. that metadata must supply:

- `scenario: "lighting-room"`, `inWorld: true`, nonempty `stage`, and the complete native flat scene schema below (an optional nonempty `worldState` supplements it, never bypasses it);
- `lightingBackend: "cpp"` for reference, `"rust"` for candidate;
- integer `rustLightingCalls`, zero for cpp, positive for rust.

`worldState` is the explicit semantic comparison boundary. the native flat driver schema is projected using `SCENE_FIELDS` in `behavior_lab.py`: world/player/camera identity and positions, stabilization assertions, materials, replicated light identity/position/color/type, occluder geometry/state, action, seed and stage index. all listed fields are required and compared exactly. ui-hidden, offscreen-player, completed-lighting and replicated-light assertions must be true; fullbright must be false. `replicatedSettledUpdates` must be at least 90 but, like `updateIndex`, is a scheduling diagnostic rather than an exact state field. neither is used to excuse unstable pixels. no region masking, cropping, adjustable tolerance, or golden update path exists. exactly `lit-room`, `occluder-added`, `occluder-restored` are required. initial/restored pixels and stable/declared state MUST match; the occluded pixels MUST differ, with the expected action, stage index and observed foreground material. missing/extra/generic frame names fail in standalone comparison too.

the fixture overlay defines `behaviorlabconstantlight`, a static 8×8 sprite with one constant `[255, 210, 160]` `PointAsSpread` light (explicitly matching the normal opensb object postload patch). it has no scripts, animation configuration, particles, sounds or flicker. its single occupied tile is placed through `ObjectDatabase::createForPlacement` at `(52,33)` with a bottom anchor requiring the `smoothmetal` floor at `(52,32)`; its light center is `(52.5,33.5)`. missing assets, invalid placement, dynamic behavior or anything other than one emitted light fail rather than falling back to vanilla lamps. this is synthetic scene input, NOT a synthetic framebuffer: real object loading, authoritative world placement, replication and world rendering remain exercised. only lab-generated bootconfigs register this overlay.

the expected native stages remain `lit-room`, `occluder-added`, `occluder-restored`: initial/restored pixels should match and the occluded frame should differ. actual native execution and the remaining one-pixel discrepancy are recorded in [EVIDENCE.md](EVIDENCE.md); unit tests alone validate only the asset contract, runner isolation and verifier sensitivity.

`build_provenance.py` snapshots compile inputs before/after successful builds and seals `<binary>.behavior-build.json`. capture rejects missing/stale proof BEFORE creating outputs or launching; it rechecks after execution. manifests retain the source-bound proof, so historical comparison is explicitly about those recorded inputs, not whatever source is checked out later. these unsigned local receipts are stale-build guards, not reproducible-build attestations: external vcpkg/system SDK transitive inputs are not fully verified. document-only changes do not invalidate compiled binaries.

native envelopes also record GL vendor/renderer/version. `metadata.lightingDiagnostics` preserves the exact row-major RGB float bits uploaded for the selected lightmap, its size and world minimum. these diagnostics explain numerical discrepancies; they do not mask framebuffer pixels or widen the state gate.

manifest hashes bind binaries, packed assets, every overlay file (namespaced as `opensb/…` and `behavior-fixture/…`), boot/scenario configs and every png/receipt. comparison checks equal assets/overlay/semantic configuration, equal dimensions, exact `inWorld`/`stage`/`worldState`, backend use, and every rgba pixel. normalized config comparison removes only per-run storage/output paths, not behavioral settings. repeatability requires distinct capture identities and the same reference binary. standalone candidate comparison without `--repeat` can produce diffs but returns failure rather than imply certification. `--same-backend` is a separate baseline-only diagnostic that may pass without claiming candidate parity.

exit codes: `0` automated gates passed (inspection still required), `1` behavioral/repeatability gate failed, `2` invalid input, launch failure or timeout. partial capture failures retain logs; use a fresh output path to retry. python 3 with pillow is required; nix fallback uses `python3` and `python3Packages.pillow`.
