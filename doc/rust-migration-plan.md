# full rust migration: execution contract and handoff

## user authorization (forward verbatim to delegates)

> alright, get yourself a laboratory, prove a slice works, and rewrite one full module in rust.
> delegate heavily, use sub agents.
> use a plan,
> use whatever skills let you reach this goal.
> when i'm back, i need you to have ported something.
> you can use nixshell
> you can use cargo
> but you cannot need me back
> you can call the oracle, you can delegate, you can research.
> do your best.
> preserve your context, if you reach compaction, you're probably dead, so use sub-agents agressively.

> hm, sick. commit your changes as a checkpoint.
> always commit incrementally.
> i'll leave you running in a loop untilo you finish it all.

> i also need you to extend your validation TO ACTUAL BEHAVIOR.
> as in
> screenshot diffing of running modules…
> sketch out a FULL PLAN FOR ALL MODULES

> loop until its done, you can delegate, and your delegates can delegate too. forward my original prompts and any relevant skills.

> eh
> pause
> stop for now

> k full reign to continue and loop, good luck

latest direction resumes execution after the explicit pause; it does not erase failed-attempt budgets or safety boundaries.

these requests authorize implementation and incremental local commits, not pushes, publishing, remote account actions, or deletion of unrelated work. preserve the pre-existing untracked `storage/` and Steam install. every child must read this file, its applicable skills, and relevant source; receive a disjoint file scope, evidence requirement and bounded budget. nested delegation follows the same rule.

## continuation scheduler

user's loop request is backed by an hourly T3 continuation bound to this thread. scheduledTaskId: `scheduled-task:command:mcp:21213db0-c7a3-40b6-9e92-c41b72603197:schedule-task:rust-migration-continuation-loop-1`. paused when user said stop, then re-enabled on explicit resumption; next run returned `2026-10-24T04:53:03.373Z`. dedupe active delegated tasks/builds before starting work; work a bounded unit, update this handoff, commit verified increments. pause/disable on genuine permission-only blockers or completion; never reset repair budgets by spawning more agents.

## completion definition

first-party client/server implementation migrated to Rust, existing assets/Lua/mod/save/protocol contracts preserved, actual running behavior verified, supported-platform evidence accounted for, remaining C++ production adapters retired or explicitly justified. retained third-party libraries and frozen reference code are not silently counted as ports. finite tests do not prove universal equivalence.

## roadmap (all source areas)

0. runtime behavioral lab: isolated baseline/candidate outputs/storage, real-game scenario driver, final framebuffer captures, state/backend receipts, independent image comparator/negative controls, replay/clock/barrier work, artifact identity. close lighting's visual gap before another port.
1. core: collections/ownership/Unicode; math/geometry/spatial queries; random/noise; JSON/patches/streams; compression/hash/crypto; files/databases/caches; workers/clocks/promises/sockets/logging; images/colors/fonts/audio decoding.
2. shared services: Root/config/databases; directory/pak/memory assets/patches/reload; Lua runtime/converters/binding families/lifecycle/threads; HTTP/trust/security.
3. world: tiles/materials/sectors; terrain/biomes/dungeons/TMX/microdungeons/terraforming; celestial/system worlds; liquids/falling blocks; sky/weather/exposure; wiring.
4. gameplay: entity lifecycle/factory/map/contracts; movement/collision/forces; inventory/items/tools/crafting/economy; objects/farming/vehicles; combat/status/projectiles; AI/pathfinding/spawning/NPC/monsters/stagehands/tenants; player/tech/companions/quests/codex/collections/statistics/maps/ships.
5. sessions: network elements/deltas/interpolation/protocol/authority; universe/world orchestration/local and dedicated servers/travel/teams/chat/permissions; player/world/ship persistence/migrations/cross-engine load-play-save-reload.
6. presentation: GPU resources/atlases/buffers/effects/HDR/MSAA; world/camera/animation/layers/particles/postprocess; fonts/text/widgets/layout/focus/modal/input; every frontend screen and script pane; mixer/music/instruments/voice; SDL/app/platform/SDK adapters; client/server shells.
7. tools/release: pack/unpack/repack/versioned JSON; JSON editor/uploader offline contracts; inactive utilities/attic disposition; Cargo/CMake/Nix/CI/platform packaging; dependency/adaptor retirement; end-to-end compatibility and resource/performance qualification.

per slice: inventory -> contract -> reference/negative tests -> Rust -> integration -> actual behavioral/visual/state/audio/save/network gates -> review -> commit. no golden updates or tolerance widening to accommodate candidate failures. exact where stable, justified frozen tolerances elsewhere. baseline-vs-baseline repeatability precedes candidate comparisons. screenshots alone do not prove invisible effects.

## current state

host/worktree: apple silicon macOS, `/Users/bdsqqq/www/OpenStarbound`, main.
starting checkpoints: `6ba80cce` (Rust CellularLightArray kernel + numerical lab), `e8993038` (successful-call receipts). numeric/integrated status passed; actual native behavioral laboratory now exposes an exact one-pixel candidate failure. see `source/lab/behavior/EVIDENCE.md`.
user storage is untracked and must stay untouched.

active iteration: behavioral laboratory. new API `source/application/StarBehaviorLab.hpp` is primary-owned/frozen contract. `STAR_BEHAVIOR_LAB` environment variable names a JSON config containing absolute outputDirectory. capture agent owns implementation + SDL capture integration. client agent owns actual world fixture/replay and queues frame names/metadata; frames are fulfilled after final composite/pre-swap and acknowledged on following update. primary owns CMake/build isolation, Rust backend call receipts, integration, verification and commits. runner agent owns Python orchestration/comparison. inventory agent owns machine-checked migration catalog.

runtime scenario must use the actual ClientApplication/UniverseClient/WorldClient/WorldPainter path, not synthetic images of numerical output. tests need explicit inWorld, meaningful scene change and Rust call receipts. reference uses same harness with Rust backend OFF. preserve original f5c4da28 reference plus namespace-only numerical oracle. CMake currently outputs to shared dist; isolate before two builds.

prior native build: build/macos-arm-release, Xcode clang/macOS SDK, vcpkg root ~/.cache/openstarbound-vcpkg, nix-shell cmake/ninja/pkg-config/python. CMAKE_DISABLE_PRECOMPILE_HEADERS=ON needed for ARM fast-math header mismatch. Cargo and Rust already available. avoid simultaneous Ninja/CMake in same build directory. runtime frame capture will use GL readback, not desktop screenshot permissions.

relevant skills: running-cross-cutting-migrations, producing-visual-evidence, inventorying-codebase-patterns, review, making-meaningful-contributions, git. load actual bodies when triggered. code/tests/nearby rationale remain project memory; this file is the single execution handoff, not a substitute for source.

### resumed state (current)

- All original `*-r1` tasks below finished; they are not active. `behavior-fixture-r2` was interrupted by the user's pause before making fixture edits. Owned build PGID45824 and diagnostic process54946 are stopped. No paused user game was terminated.
- Actual first C++ baseline run failed before captures: `build/behavior/diagnostic-reference-1/process.log:128`, `BehaviorLab: no stable light-producing fixture object available`. Four vanilla candidates were all rejected/unplaceable. Old heuristic approach has one failed runtime attempt; do not repeat guesses.
- Completed task `behavior-fixture-r3-resume`: explicit static `behaviorlabconstantlight` mod loaded by real Assets/ObjectDatabase at (52,33), floor anchor (52,32). Runner registers/hashes fixture + opensb overlays. Primary owns handed-back source; no active fixture worker.
- First full native run `build/behavior/real-game-r1` COMPLETE: C++ baseline twice matches exactly; each backend initial/restored PNGs match and occluder changes visible lighting. All three Rust frames differ from C++ by ONE pixel / max channel error1; state comparison passes. Exact gate correctly FAILS. Three reference PNGs inspected by primary; reviewer also inspected candidate + diff. GPU Apple M2 Pro/OpenGL4.1 Metal91.7, 1000x600. No parity certification. Parent PID3266 finished; paired native builds finished. First explicit fixture runtime attempt succeeded, first exact candidate comparison failed; no arithmetic repair attempted yet. No tolerance/fixture/reference-FP changes permitted to accommodate failure.
- Terminal `lighting-fp-diagnosis-r1`: seven sampled isolated expression sites match production ARM assembly under explicit Rust FMA/reciprocal/reassociation formulas; 300,000 scalar sampled outputs bit-exact. Primary independently reran the diagnostic. Complete-kernel/framebuffer causality remains unproven; no production arithmetic edits attempted. Reproducer `source/lab/lighting/diagnostic/run.py`.
- Review `behavior-contract-review-r2-resume` terminal: verified stale-binary/source binding gap and standalone generic-receipt downgrade. SDK caches OFF confirmed; no candidate fallback found. Primary closes downgrade: full native SCENE_FIELDS and three exact named transitions/restoration now required by every capture validation, not merely launch; declared state also must restore.
- Terminal `behavior-native-fixture-tests-r1`: adapted synthetic data and controls to strict native contract. Primary added source-proof preflight/integration negatives. Generic images/literal state no longer constitute production behavior receipts. Combined 40 behavior/provenance tests independently PASS.
- Terminal `behavior-build-provenance-r1`: before/after compile-input snapshots and binary/source/tool/cache sidecars implemented; primary integrated mandatory verification before capture outputs/launch and after run, plus recorded proof validation for standalone comparisons. Native r2 exercised the integration successfully. This is an unsigned stale-build guard, not reproducible-build attestation.
- Primary added exact selected CPU lightmap float-bit diagnostics; rebuilt BOTH clients with source-bound receipts and ran `build/behavior/real-game-r2-diagnostic` (parent PID36223 finished). Repeats exact; same one-pixel Rust failure. CPU lightmap66x40 min(31,28) differs513 channels initially/restored and469 occluded, maxabs5.960464477539063e-8, maxULP20. Diagnostics are not a new tolerance/pixel/state mask.
- Current reference/candidate paths: `build/behavior/{reference,candidate}/bin/starbound`; artifact hashes/source-map fingerprint and inspected states are in `source/lab/behavior/EVIDENCE.md`. No active build/game process remains. No production arithmetic repair started yet.
- Catalog independently accounts for 39 modules /1397 files; eight negative/drift tests and --check PASS. New diagnostic Rust is harness code, not a port. `.github/workflows/migration-inventory.yml` wires check-before-regeneration and all behavior/provenance tests via self-test; no remote CI has run.
- Current numerical rerun: debug/release12tests each, fmt, nineCTests, CABI/platform-config checks allPASS; single-seed14,734,528 channels PER mode serial+concurrent, precise maxerror0, fastmath maxerror6.19888e-6. First regeneration failed at host compiler/NixSDK selection; second used existing native dependency installation with VCPKG_MANIFEST_INSTALL=OFF in ONLY build/macos-arm-release cache and passed. Logs `/tmp/openstarbound-lighting-resume-checks{,-r2}.log`. Historical numerical EVIDENCE explicitly labeled historical, not silently refreshed to current.

### prior delegated tasks (terminal)

all share this checkout, with command prefix `node:delegated-task:command%3Amcp%3A21213db0-c7a3-40b6-9e92-c41b72603197%3Adelegate-task%3A`:

- `behavior-capture-r1`: application capture implementation and SDL pre-swap hook.
- `behavior-world-driver-r1`: ClientApplication scenario and optional client helper files.
- `behavior-runner-r1`: `source/lab/behavior/**`, `scripts/behavior-lab.sh`.
- `migration-catalog-r1`: `source/lab/migration/**`, optional inventory script.
- `behavior-contract-review-r1`: read-only determinism/safety audit.

primary changes: runtime output cache override in root CMake; capture source registration in application CMake; `BehaviorLab::enabled()` offline platform-service guard; Rust successful-call counter + ABI declaration/test; `scripts/build-behavior-lab.sh` for isolated SDK-disabled reference/candidate builds. Rust unit tests and fmt passed after counter addition. Pillow supplied via nix `python3.withPackages (ps: [ps.pillow])`, verified 11.2.1. Do not run a build until capture and client workers hand off. checkpoint `e8993038`: successful Rust backend call receipts, with debug/release unit tests and fmt passed. Historical `source/lab/lighting/EVIDENCE*` describes checkpoint 6ba80cce, not the subsequent instrumentation changes; regenerate latest evidence only after rerunning the affected checks. Capture worker completed implementation; pending client/runner/catalog/review handoffs before combined build.

## acceptance for current iteration

- reference and Rust native clients produce final framebuffer PNGs from a real in-world scene under isolated bootconfigs.
- scenario/state receipts distinguish correct scene, action transitions and actual selected/used backend.
- comparator produces inspected reference/candidate/diff images, rejects deliberate visual mutation, refuses unsafe output/storage paths, binds evidence to binaries/assets/config.
- baseline repeatability characterized honestly; remaining nondeterminism is resolved or explicitly blocks parity certification, never silently masked.
- numerical lab still passes; native app and CLI checks pass; final diff preserves unrelated changes; checkpoint committed.
- full rewrite remains OPEN after this iteration; no completion claim until all roadmap gates close.
