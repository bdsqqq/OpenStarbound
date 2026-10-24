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

## current handoff

host/worktree: apple silicon macOS, `/Users/bdsqqq/www/OpenStarbound`, main.
last committed checkpoint: `98c63f74`; pending verified archive/oracle integration described below. preserve pre-existing untracked `storage/` and the Steam install. no pushes or external service actions.

### completed checkpoints and evidence

- `6ba80cce`: scalar/RGB CellularLightArray Rust kernel and differential lab. `e8993038`: successful-call receipts.
- `21f3ef31`: actual native framebuffer lab, isolated storage/configs, static normal-pipeline fixture asset, exact scenario/pixel/state gate, source-bound build receipts and machine-checked source catalog. first real comparison exposed one blue-channel step at pixel(117,375); no tolerance/fixture/reference changes were allowed.
- `98c63f74`: first production-ARM arithmetic repair passed the actual three-stage lighting-room gate. selection restricted to Apple clang21/aarch64/fast-math; precise entrypoint/layouts preserved. two CPP baselines and all Rust frames match exactly; CPP pixels unchanged. fourteen CPU upload channels still differ slightly, so NOT universal float/game equivalence.
- inspected artifact/source/binary identity and historical failures remain in `source/lab/behavior/EVIDENCE.md`. historical numerical evidence is explicitly historical. full migration remains OPEN.

### pending verified integration

- Terminal task `rust-ffi-archive-aggregation-r1`: one `source/rust/ffi` staticlib owns existing3 unmangled C exports; lighting is rlib only, workspace lock/release unwind profile moved to source/rust. neutral cmake/Rust.cmake owns archive; RustLighting.cmake, legacy variables/build target and star_rust_lighting alias remain compatible. NO arithmetic changes.
- Primary rebuilt BOTH clients and ran `build/behavior/aggregate-r1`: baseline repeatability, exact candidate state/pixels and restoration PASS. all nine pixel hashes AND all reference/candidate CPU upload maps match `arm-policy-r1`. source-map fingerprint/binary identities recorded in EVIDENCE.md.
- Primary reran workspace15 debug/release tests, fmt, nine numerical CTests, seed1592594996 14,734,528 channels PER mode serial/concurrent, C consumer all3exports, architecture/target-isolation negatives, 40 behavior/provenance tests. current numerical log `/tmp/openstarbound-aggregate-primary-numeric.log`.
- Primary filtered Rust targets out of common numerical-lab libraries: exactly ONE aggregate in Rust test link, NONE in CPP fallback link. CPP native Rust-OFF graph has no Rust target; old lighting archive absent from Rust-ON graph.
- Terminal task `grid-traversal-oracle-lab-r1`: new source/lab/traversal only. namespace/import-only frozen original header from f5c4da28, SHA256 c917ceeeba883c8c267b03861e0b171d0c7c3f2098b9cc419e6e463ea006d077. primary independently ran `python3 source/lab/traversal/run.py`: EACH precise/production-fast policy passes 6972 float/double cases,327977 ordered callback/abort/exception-identity/reentrancy checks with undefined-behavior/float-cast sanitizers. deliberate tie, ignored-abort, swallowed-exception and provenance mutations detected. this is CPP calibration, NOT a Rust traversal port or real-game evidence.
- Catalog currently1401files/39modules; shared ffi source explicitly runtime adapter, new oracle is harness code, neither counted as a newly ported module. eight inventory negative/drift tests and --check PASS. no remote CI run.
- no active delegates or build/game process at this handoff. last native buildPID48900 and runPID53154 finished. parent-only doc updates and all owned source pending local checkpoint; no unrelated changes discarded.

### next bounded component and dependencies

1. checkpoint the verified archive/oracle integration. then port `StarBlocksAlongLine.hpp` as a bounded traversal component, NOT the entire base.geometry catalog module.
2. five production callers are float: StarWorldImpl.hpp:115,124,204,547; WorldLuaBindings.cpp:999. existing blocks_along_line_test.cpp uses double. preserve Scalar-rounded endpoint addition BEFORE double math, negative floor, inclusive axes/zero length, corner ties advancing BOTH axes/skipping side cells, callback false including last, lazy side effects and exact exception propagation. finite alone is not the original defined domain: floor-to-int, setup-count and post-loop overflow matter; don't reject defined wide-coordinate early-abort prefixes with an arbitrary upfront length cap.
3. settle C ABI/backend receipts BEFORE parallel behavior adoption. synchronous callback + per-call opaque context, no retained pointers. C++ thunk catches ALL exceptions into exception_ptr, aborts Rust immediately, then rethrows after return; never unwind C++ through Rust. keep ordinary false distinct from invalid-input/panic statuses. per-query executing-thread receipts, not an unrelated process-global count.
4. attach Rust adapter to frozen lab without changing reference/anchors/negative controls. compare ordered cells/returns/side effects/exception object identity, precise and production flags. add adversarial non-lattice decimal/corner cases if needed to expose FMA/reassociation; existing mostly binary-grid random cases are not complete FP coverage.
5. then distinct STRICT raycast-room scenario/schema. use actual client/server lineTileCollision, lineTileCollisionPoint, collidingTilesAlongLine, NOT World::lineCollision (polygon path, not this kernel). query(54.5,48.5)->(74.5,48.5), clear/wallx62/clear; returned client hit point drives real Drawable foreground overlay. require authoritative/client agreement and replication, backend use on each executing thread, exact state/frame sequence and restoration. never weaken lighting-room validation.
6. traversal-only baseline/candidate keep CPP lighting in BOTH; rerun existing lighting gate and final both-Rust combination. primary integrates builds/evidence, source catalog and verified local commits. no traversal implementation attempted yet; repair budget0/2.

### orchestration and build boundaries

task prefix: `node:delegated-task:command%3Amcp%3A21213db0-c7a3-40b6-9e92-c41b72603197%3Adelegate-task%3A`. all earlier tasks are terminal, including fixture-r3-resume, contract-review-r2-resume, fp-diagnosis-r1, native-fixture-tests-r1, build-provenance-r1, arm-math-policy-r1/review-r1, next-slice-research-r1 and the two integration tasks above. retain new task suffixes/scopes/budgets here; don't duplicate work.

native recipe: scripts/build-behavior-lab.sh, Xcode clang/macOS27SDK, vcpkg ~/.cache/openstarbound-vcpkg, CMAKE_DISABLE_PRECOMPILE_HEADERS=ON, SDK integrations OFF, isolated outputs build/behavior/{reference,candidate}/bin. no concurrent Ninja/Cargo writers to the SAME build/target directory. numeric build/macos-arm-release currently VCPKG_MANIFEST_INSTALL=OFF after a NixSDK host-probe failure; dependencies already installed. use explicit Xcode SDK/compiler and Nix mkShellNoCC build tools.

BehaviorLab API source/application/StarBehaviorLab.hpp is stable. config STAR_BEHAVIOR_LAB must name absolute JSON; output sentinel/strictly nested declared storage and bootconfig match are mandatory. capture after final composite/before swap, PNG then nested metadata receipt. normal Asset/ObjectDatabase/UniverseClient/WorldClient/WorldPainter path, not generated replacement images. old vanilla lamp heuristic failed once and was replaced by explicit static fixture; do not revive guesses. do not run legacy gameplay tests that clear universe/player files against user storage.

skills as triggered: running-cross-cutting-migrations, producing-visual-evidence, inventorying-codebase-patterns, review, making-meaningful-contributions, git. code/tests/nearby rationale are project memory; this remains the single execution handoff.
