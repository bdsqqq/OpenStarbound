# production lru selection — implementation ready for parent integration

host/worktree: macOS arm64, `/Users/bdsqqq/www/OpenStarbound`, shared checkout at parent checkpoint `4625f732` plus the disjoint production edits below. no commits, Cargo invocations, retained-object links, game/storage/Steam writes, installs or remote operations. independent application-fixture changes were observed and preserved; no repository-wide source-membership freeze was imposed.

## delivered

- `source/core/StarLruCache.hpp`: all twelve written bodies and filter dispatch select the existing Rust controller under `STAR_USE_RUST_LRU_CACHE`. OFF retains the entire frozen native header token stream, ignoring comments/whitespace. signatures, aliases, defaults, two data members/order and implicit lifecycle remain unchanged.
- `source/core/StarLruCacheHost.hpp`: per-call frame borrowing the real map/limit, producer/filter/byvalue argument locals, and original native find/filter iterator locals. no cache-owned frame, new Value, extra snapshot move or iterator reconstruction. native storage/list/map operations remain explicit leaves, not whole-cache native algorithms.
- `source/core/StarRustLruCache.h`: canonical C11 ABI. existing exported names, structs, enum values and signatures unchanged. no production call/depth limits.
- `source/lab/lru-boundary/host_api.h`: forwarding include of that canonical ABI, avoiding duplicate enums when headers meet. mock finite limits stay solely in its existing lab implementation.
- `source/CMakeLists.txt`: default-OFF option beside PathEmbed, admission through the existing Rust.cmake OR, global compile definition. no Core CMake or Rust source changes; no second aggregate/runtime.

mandatory unwind repair is carried across: `resume` restores its stage AFTER Rust returns, then rethrows a saved native exception while the native owning full expression/iterator scope remains live. the enclosing noexcept native host catches that unwind before returning to outer Rust. borrow guards clear pair/iterator slots on both exits. get keeps `withPair({key, producer(key)})` in one native full expression. no foreign unwind or rollback.

one production-specific type compatibility issue was found during review: a single eager host instantiated set assignment/get copying even when callers only read a cache. the frame is now mode-templated; set add/assign and get insert leaves instantiate only for their owning modes. this changes no Rust protocol or runtime operation order. `lazy.cpp` exercises both real aliases with nonassignable and move-only Values; reads/constructor compile without imposing unused write requirements. a frozen initial-host negative fails on the actual deleted assignment/copy requirements, then the final OFF/ON fixtures pass.

## final verification — finite, not game qualification

command: `python3 -B source/lab/lru-production/check.py`

final root: `build/lru-production-r1/final-r2/`
report: `report.json`, SHA256 `2cbcac55a73c373c5d33b438b21a10c00e2566d82b4ecf4898da79a4db1b0057`.

21 commands have exact argv/cwd/env/stdin hashes in `*.plan.json`, actual PID/PGID/start in `*.started.json`, status/end/stdout+stderr hashes in `*.receipt.json`, and raw I/O beside them. no timeouts or unexpected command failures. known-negative compilation/guard exits are explicitly expected1. final input hashes, physical source snapshots and all raw I/O hashes were independently reread and matched after the run.

passed:

- production plus forwarding headers parse together as C11; ABI size/enumeration assertions. known bad reply-size assertion fails through the same compiler.
- unchanged `source/lab/lru-cache/native.cpp`, both aliases/all its property bodies, syntax/type instantiated OFF/ON against actual production class.
- existing lifetime fixture expressions retained, with ONLY includes/class selection changed to frozen native reference versus actual production class; real ordered/hash and decorated iterator scopes instantiate OFF/ON. generated fixture is `final-r2/lifetime.cpp`, SHA256 `d8e0462dac37fef771a466404a0f82d5af061001e92852ee14a88a14c2e8ad9d`.
- nonassignable/move-only read-body fixture OFF/ON; historical eager-host negative rejects.
- actual configured native `-O3 -ffast-math` profile used without changing its flags. four FRESH optimized fixture objects emitted, no retained objects consumed. `nm -u` shows `_sb_lru_run` in ON native/lifetime objects and absent from OFF objects.
- two FRESH full-project configurations: all26 selectors OFF by default versus ONLY LRU ON. all472 generated compilation rows consistently omit/include the LRU definition. OFF has no Rust aggregate target; ON has exactly the existing single aggregate build command. no Cargo target executed.
- unchanged shared Rust module cross/universal guards reject with their expected messages in isolated configure fixtures.
- final fixture syntax/object stderr EMPTY. CMake configuration warnings are existing disabled-PCH reuse notices plus unused explicitly supplied tool/triplet variables; logs retained, no unrelated cleanup.
- scoped `git diff --check` passes; final diff reviewed.

### source identities

```
7164a91b0572cb0a75c699f09e39fef6c6802c7631c5edc32ea7a8dabfff1ddb  source/core/StarLruCache.hpp
7dd90acffe3cedd57a67e5b23f8fe3ece0882f85caee7374919156de217a0526  source/core/StarLruCacheHost.hpp
00b03f1e3c385d79969a793c98d8ad49986900aafe7f1e8527d7dd1e0af68eff  source/core/StarRustLruCache.h
f537432c6d0f9a40f4a0aa225dc19c54f30b86fda801e62e3459c1cd505af820  source/CMakeLists.txt
2ecd7a47056542ab50e86e70e913ad2e2dbe87ca30aa6a9313d675400376235a  source/lab/lru-boundary/host_api.h
6bbc363eb86001e72f416de6fbbe0e9e7162a0610685cc048c551ec494f94c14  source/rust/ffi/src/lru_cache.rs (UNCHANGED)
```

### process identities

```
c11 71912 exit0; bad-size 71914 exit1; eager-host-negative 71916 exit1
native OFF syntax71925/object71930/nm71961 exit0
lifetime OFF syntax71962/object71966/nm71973 exit0; lazy OFF71974 exit0
native ON syntax71976/object71978/nm71984 exit0
lifetime ON syntax71985/object71987/nm71989 exit0; lazy ON71990 exit0
full-project configure default71992 / only-LRU72326 exit0
shared-module cross72837 / universal72888 exit1 (expected)
```

## historical products and next action

initial `build/lru-production-r1/report.json` is a historical syntax/configuration pass before type-laziness correction. its EXACT bound source bytes are retained under `historical-r1-source/` and were reconstructed/hash-checked against that report before writing. `final/report.json` is the subsequent historical successful type/configuration pass with constant-switch warnings. `final/source-snapshot/` preserves those exact bytes. `final-r2` is the current warning-free fixture/object/configuration result. no old reports/artifacts were edited or rebound; no failed acquisition was retagged. the deliberate historical-host negative is not an unexpected failed acquisition.

production/header/CMake changes explicitly historicalize earlier participating full-source closures, including the parent's accepted finite Rust/native bridge report. preserve that evidence as historical; do NOT run its old live-source verifier and silently waive source drift. its unchanged Rust source hash is not proof of fresh production dependency closure.

**parent remaining gates:** integrate/review; fresh full canonical native/Rust dependency closure and production/game builds after all source writers settle; actual production-class runtime parity/unwind/protocol acquisition; actual-game Dungeon/cache/state/scene/PCM/save/TCP/CLI behavior; catalog/plan/checkpoint updates. no runtime, all-Core/all-project-TU, game, other-platform, universal or universal-equivalence claim from these fixture objects/configurations. writable scope is settled and ready for parent freeze. no child compiler/CMake/Cargo task remains running.
