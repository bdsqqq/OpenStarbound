# weightedpool game scene — implemented, NOT yet game-qualified

scene24 is `weighted-pool-room`. sandbox-only `weighted-pool-assets/` supplies a plain generic item, three treasure pools, Lua consumer and white image. normal `root.createTreasure(pool,1,17)` reaches production treasure/WeightedPool/ItemDatabase code. it still evaluates the route's eager global RNG default; no clock/RNG/cache hook changes that behavior.

repeat returns two separate kept descriptors, unique one, filtered none: nonpositive entries are dropped and the retained singleton has weight1; numeric rounds is the native singleton `(1,2)`. deduplication is TreasureDatabase descriptor logic, NOT `WeightedPool::selectUniques`. complete descriptor arrays and unknown parameters remain in receipts/comparisons; wrong names/counts/tags and perfectlygenericitem fallback fail. selected/unique descriptor counts drive Assets color and Font text. phase3 uses the same descriptors but a distinct stage channel; world restoration is checked separately.

C++ brackets ONLY the real main-thread Lua callback with actual19×4 ABI counters. constructor/add startup work is deliberately outside this bracket and not claimed as phase coverage. source-derived per-phase minima require the public empty root and seeded select/index/private-scan roots; unrelated normal work may add calls. native reports zero. overlay/label/capture all require the same prepared stage, preventing previous-phase capture races.

## current evidence

- parent ran319 behavior logical tests: PASS, including isolated descriptor/count/color/phase/config/backend/origin corruptions. these are synthetic fixtures, not running-game frames.
- source-pinned current `StarClientApplication.cpp` TYPECHECKED in native28-OFF and cumulative27-ON-except-LINE_QUERY profiles.
- actual production default-OFF executable BUILT/LINKED/RUN without Rust archive, host header or Rust/WeightedPool exports. `verify_scene.py` reconstructs the six actual native commands and two isolated falsifiers from report sha256 `d8b51ab18a196b32767e956aa02bc93d5a7251589ea0078c9066711bf7de672b`.
- prior source/client/behavior bytes retained BEFORE edits in `build/weighted-pool-scene-r1/source-versions.json`, sha256 `e7252930cc523dab1960e464ac575d7c9dd1cb1da32e30c12cc18d596dc33433`. old global source-live replay is historical, not rebound.

```sh
python3 -B source/lab/weighted-pool-production/verify_scene.py
python3 -B -m unittest discover -s source/lab/behavior -p 'test_*.py'
```

NO actual Lua callback/game counters/framebuffer/asset-normalization observation yet. complete28-selector/source/binary origins are required for this scene only; every older profile retains its previous contract. native allOFF and Rust allON except LINE_QUERY are strict. two old registry tests were updated only for TTL's fixed index22/new total24.

next: dedicated complete tool/source/game admission, projected4GiB live/16GiB archive budgets and verified prior-pair retirement BEFORE a new pair. then fresh native/native-repeat/cumulative-Rust captures, inspect all actual frames, rerun old23 +fresh PCM/CLI/TCP/save/BTree, seal finite certificate and cleanup. do not run this scene on the protected old TTL pair or claim full39 completion.
