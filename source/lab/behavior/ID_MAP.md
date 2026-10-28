# idmap: finite status-consumer preparation

**source preparation only; the application has not run this scene.** no capture,
certificate, backend parity, restoration receipt, or new game artifact is claimed.
new-build admission is blocked until the parent accounts for existing products;
this delegated slice neither builds nor performs cleanup.

## state matrix — fixed before capture

consumer: `status.addPersistentEffects` → `StatusController` → `StatCollection`
→ `StatSet` → `IdMap`. use the real main player's status callbacks, never a mock
or a second controller. recreate the Lua context each phase, retain controller
state across phases. the fixture stat is `behaviorLabIdMap`; the only owned
categories are `behaviorLabIdMapA` and `behaviorLabIdMapB`.

| capture / stage | action, with an immediate literal read after EACH operation | final stat | rgba | label |
| --- | --- | ---: | --- | --- |
| `lit-room` / 0 | add A 8 → 8; append A 4 → 12; set A 16 → 16; add B 2 → 18 | 18 | 72,40,60,255 | `IdMap 1/3 stat=18` |
| `occluder-added` / 1 | clear A → 2 | 2 | 8,40,120,255 | `IdMap 2/3 stat=2` |
| `occluder-restored` / 2 | add A 32 → 34 | 34 | 136,40,180,255 | `IdMap 3/3 stat=34` |
| after acknowledgement, error, or shutdown | clear ONLY A and B; assert stat 0 | 0 | not captured | not captured |

all numbers are exactly representable binary integers. assert the raw stat
before computing colors; no tolerances, fitted expectations, or integer coercion
of readbacks. Lua F64 may serialize as JSON int or float; the verifier accepts
both for stat reads, rejects bool/nonfinite/fractional/wrong values, and requires
integer color channels. `observations` contains actual stat reads, not expected
constants. its per-phase lengths are 4, 1, 1.

use the existing scene's `SCENE_FIELDS`, actions, and three stage names; they
refer to world changes, not new stat-specific stage names. camera `[64,48]`,
pixel ratio 2, centered original white 16px asset at world `[64,48]`, image scale
`2 / TilePixels`: the expected framebuffer overlay is 64×64. parent copies the
original white asset to `/behaviorlab/id-map-white.png`; Lua adds the multiply
hex directive. normal Assets/WorldPainter draws the image, normal Font/TextPainter
draws the label. `visible()` checks every central pixel and white label presence;
it does NOT perform OCR or independently prove the exact rendered text. actual
captures still need inspection. hover, focus, dismissal and narrow responsive UI
states are inapplicable to this fixed game overlay.

## receipt contract

`idMapProof` has exactly these members, matching the weighted-pool envelope:

```
version backend selector scopeThread phase countersBefore countersAfter
visual consumer imageConsumer labelConsumer configuration
```

- version `1`; backend `native` or `rust`; selector `STAR_USE_RUST_ID_MAP`.
- scope thread `lua-calling-thread`.
- consumer `normal-status.addPersistentEffects-StatusController-StatCollection-StatSet-IdMap`.
- image/label consumers `normal-Assets-WorldPainter` / `normal-Font-TextPainter`.
- configuration scenario `id-map-room`. the complete parent-owned shared runner
  configuration is retained and compared within a sequence, not restricted to a
  one-field object. unknown proof/visual fields are rejected; unrelated top-level
  scene fields and shared configuration fields remain the parent's contract.
- visual has exactly `phase observations value color label imagePath`.
- counters are 10 modes × 2 stages, each a canonical lowercase 16-hex-digit u64.
  native before/after matrices are all zero. Rust modes 2 and 4 each require
  ROOT **and** CONTINUE deltas at least 2, 0, 1 for phases 0, 1, 2 respectively
  (u64 modular subtraction). other counter modes do not establish extra coverage.

`observation()` excludes backend, counters and configuration only after
validation. snapshot validation requires strict 0/1/2 order and stable backend
and configuration. sequence validation reuses the passed `SCENE_FIELDS`, checks
restored world state and distinct image hashes. no `cleanup` field is invented:
the current envelope contains no actual cleanup acknowledgement. `restore()`'s
assertion is a requested runtime obligation, NOT proof it has executed.

## traced source and limits

**verified (source trace):** callbacks forward to the supplied controller in
`source/game/scripting/StarStatusControllerLuaBindings.cpp:197–209`.
`source/game/StarStatusController.cpp:248–283` allocates a modifier group only for
a new category; append and replacement retain that category's group, while clear
removes it. `source/game/StarStatCollection.cpp:140–141` forwards allocation;
`source/game/StarStatSet.cpp:43–48` calls `IdMap.add`. group replacement/removal
recompute immediately (`StarStatSet.cpp:65–82`). value modifiers use `amount`
(`source/game/StarStatusTypes.cpp:55–60`); absent effective stats read zero
(`StarStatSet.cpp:111–118`), and modifiers populate the effective map during
recomputation (`StarStatSet.cpp:235–262`). a wrong read at any step falsifies this
finite schedule; runtime falsification is still pending.

this scene exercises real auto-add/next-id allocation loops through modes 4/2.
category clear reaches native inherited `BaseMap::remove`, NOT IdMap mode 5
`clear`. it does not cover all 16 inherited APIs, wrap/exhaustion, serialization,
exception/lifetime edges, arbitrary modifiers, or universal equivalence. existing
finite kernel/production checks remain separate evidence, not application proof.

parent obligations: preflight absent stat/category collisions; bind real
`mainPlayer` status; retain `PlayerPtr`; call owned restoration on acknowledgement,
error and shutdown; preserve unrelated categories and user storage; bracket calls
on the Lua calling thread; prepare/render before capture; enforce artifact
admission and complete state/visual/native-vs-Rust gates. these are not implemented
or certified by these four delegated files.

## verification performed

`python3 -B -m unittest -v test_id_map_proof` from `source/lab/behavior`: **9 tests
passed**. all inputs and images are synthetic, in-memory logical fixtures. known
wrong stat values, missing mode-2/4 ROOT or CONTINUE deltas, malformed counter
shapes/hex, extra cleanup fields, missing proof/visual members, world-state drift,
and wrong pixels/missing label are rejected. source-string checks cover owned
Lua restoration and assertion-before-color ordering; Lua itself has NOT been
parsed or executed. no native command, game run, runtime golden, or artifact
output was produced. application/build/platform/audio/network/save evidence is
unverified.
