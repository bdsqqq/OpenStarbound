# ttl-room: frozen pre-acquisition contract

status: source/model work only; NO native compile or actual-game evidence acquired.
prior accepted bridge checkpoint 6630f39c/report 4c2e0cae... is historical,
not rebound to these edited source bytes. no production/game adoption claim.

## source matrix (frozen before acquisition)

| phase | normal consumer action | discriminating assertion | visible evidence |
|---|---|---|---|
| 0 | RootLua tenantConfig A twice → TenantDatabase → actual HashTtlCache → Assets JSON → Tenant | arbitrary initial keys retained; first may hit, second hits; timestamp refresh within real Time/Random bounds; literal metadata | metadata/phase color via Assets and WorldPainter; normal Font label |
| 1 | wait until observed phase-0 A stamp + actual TTL + 1 ms, normal cleanup then tenantConfig A | no guessed sleep; strict expiry witnessed by foreground OR maintenance cleanup; subsequent producer entry and reconstructed metadata | distinct phase color and label |
| 2 | SAME Lua invocation pcall unknown tenant then valid A | exact complete native what() first line; raw diagnostics retained; producer failure partial state; valid continuation | third color/label |

watch covers every TenantDatabase get/cleanup on all threads while armed, serialized
by the EXISTING cache mutex. `ttlLabHistory` takes that same lock; its final call
disarms the watch before copying history, so no in-flight maintenance operation
can disappear after the last receipt. raw ordered keys/timestamps/scalars, operation clocks,
producer entry/error bytes, foreground/background and exact u64 hex backend root
counters are mandatory BEFORE projection. no Value/TenantPtr snapshot copies, cache
inspection calls, clear/resize/policy changes, fake clock or Root-maintenance suppression.
clockBefore/After bracket the original operation; cleanup's internal clock is NOT
claimed identical to either extra observer read. the validator requires one possible
internal cutoff consistent with ALL raw retained/removed entries and the bracket;
expiry of A must be unambiguous (clockBefore > stamp + TTL).

## domain and comparison

normal defaults TTL=10000, smear=1000, update=true, unlimited capacity unchanged.
unknown native message: `(TenantException) No such tenant named 'behavior-ttl-unknown'`.
source semantics: original get's native return full-expression and [this] producer
capture stay intact; observer hooks allocate and may throw in a lab-only domain;
OOM/observer failure, timestamp overflow, unrelated concurrent TTL caches/counter
noise, arbitrary external invalidating callbacks are NOT universal claims.
root counters are global: Rust own operation must increment its root by AT LEAST
one, opposite counters may advance due to unrelated caches; native OFF all zero.
foreground/background transitions are explicit, interleavings/timestamps are NOT
goldens. all raw histories replay first; cross-run compares scoped outcomes, literal
metadata/error bytes and pixels only. raw snapshot prefixes cannot be rewritten.
empty tenants list proves normal Tenant construction, NOT NPC spawning.

## acquisition ownership / next gate

parent alone performs fresh global compilation AFTER both source owners terminal.
Native all 27 selectors OFF vs Rust 26 ON except LINE OFF; Native repeat BEFORE
Rust, original 180 s budget, same normal framebuffer capture path, exact pixels,
no tolerance/golden changes. use --scenario ttl-room, isolated sandbox overlay only.
installed assets/archive/user storage remain read-only. inspect ALL three actual
frames and labels; generated logical images are verifier fixtures, not game evidence.
keep source/build/toolchain/PID/manifest/capture pins bound to fresh binaries.
old receipts are immutable historical artifacts, never retagged.

logical negatives: >= expiry boundary, absent refresh, bad expiry/producer,
wrong native message/partial state, rewritten history, wrong pixel/backend.
compile/runtime/ABI/platform/OOM/performance and all actual captures remain pending.

## terminal source handoff

Python-only verification: final 303 behavior tests passed (including 14 TTL
logical, plumbing, pixel-sensitivity and PID-binding tests). Final whole-suite
replay is recorded in `/tmp/ttl-behavior-tests-01a17ea1-final303.log`.
It includes the cache-mutex terminal barrier and coherent whole-cleanup boundary
brackets, plus actual locally spawned Python fixture PID/start/exit binding checks. No C++ syntax/typecheck, Cargo,
fullbuild or game process was run by this owner. Earlier failures were logical
fixture plumbing/count assertions (retained tool logs), not failed game captures.
The final comparison fixture ingests through real `captures()` validation rather
than bypassing normalized world state; no expectations/tolerances were fitted.

Exact-boundary ambiguity: if a maintenance cleanup's observer bracket straddles
A's boundary, removal may be source-consistent but cannot supply this fixture's
unambiguous strict-expiry witness. That acquisition MUST fail closed (no guessed
clock, waived raw event or retry-budget reset). Random refresh can legitimately
repeat a prior stamp; no-refresh negative uses an old stamp outside all permitted
Time/Random bounds, not a false assertion that every hit changes the numeric stamp.

Parent next inputs: after BOTH owners terminal and verified retention of the old
runnable pair, the existing `scripts/build-behavior-lab.sh ttl-cache-combined`
recipe uses a fresh `STAR_BEHAVIOR_TTL_GENERATION`, preinstalled offline deps,
27 OFF Native selectors / 26 ON Rust except LINE OFF, existing single aggregate,
and fresh before-configure/configured/sealed provenance. Do not reuse old game
binaries or source receipts. Then `behavior_lab.py run --reference <fresh-native>
--candidate <fresh-rust> --assets <read-only-packed.pak> --scenario ttl-room
--output <NEW-owned-build-dir>` performs Native, Native-repeat BEFORE Rust at the
unchanged 180-second budget. Repeat old22 scenes on the fresh pair; inspect all
actual TTL marker/Font frames; retain new direct process-start/process-exit pins.
Global source/tool/recipe sealing and supported-platform/native compile checks
belong to parent, not this source-only handoff. No game/evidence files were pruned
or retagged. Logical unittest stdout is the latest replay, not an immutable game
acquisition receipt.

Terminal host/worktree: `mbp-m2.local`, `/Users/bdsqqq/www/OpenStarbound`, shared
checkout over HEAD `e99aa6c506b074d4bb09173d9966d25b5e7bc81d` plus these uncommitted
owned changes. State: source REVIEW-READY / native compilation and game evidence
UNVERIFIED. No active process from this owner, no descendants, no commits. Core
Lru header separately released twice via real T3 steer; exactly one friend only.
Parent must still wait for the other owner terminal before global build freeze.

Final budget observation: archive 16,413,511,680 bytes, live build 2,724,827,136 bytes,
both under fixed 16/4 GiB caps; whole checkout 19,315,828 KiB. This owner generated
no native/Cargo/game products; synthetic test directories are unittest-managed.
The shared live count can change when the production owner finishes its probes.

### exact owned source pins (sha256)

```text
87d72f7b1dfca06040a2f3193e7c1920280d1f358beae9bf9727c7e319097577  source/core/StarLruCache.hpp
24346ab66cf6a86afae2de6b08447f3cbb581f4d476f1c6c34c161cedb932db9  source/base/StarTtlCacheLab.hpp
6f0ffd22b07bd8506c34c12f9526ea0a51c5682c197cd3be60f7b9db93ce7405  source/game/StarTenantDatabase.hpp
92ede70f667c09af853b24959b89399a14c0213266a7f15b1cdc350a1daec4c9  source/game/StarTenantDatabase.cpp
9ba40d6c235cb973164d430b124187c299e3a59a1f7524d3c7c36bf0c55f5365  source/application/StarBehaviorLab.hpp
bb59287de0920fb9ed49063b12fe26b011dd9e68ad26ca3a570c1136f018128e  source/client/StarClientApplication.cpp
8c132adf822bc5c8fed0849cf524544ce4c3e2b8003e5666e05b90eeb26a6b9f  source/lab/behavior/behavior_lab.py
0a1001474c0423ee5bb04c7320b0b56a2a6911a42591cd1761b76070ef86fd50  source/lab/behavior/ttl_proof.py
c7d14fd395a0fc23562a38cf739a2ce75b52cc0a3ca4e23da3cad427ae4c31f9  source/lab/behavior/test_ttl_proof.py
12582845862793efce9b3496ac52a3ed18c731fc6440199d95825bb399177778  source/lab/behavior/test_behavior_lab.py
c7cad75961b2a3584d93ab6eab72bb5066ebeb3acc3e0f40c0414f7ccce3ca5b  source/lab/behavior/test_lru_proof.py
df02b77cbf02bdde4e73e8c630e2cac190e26501849fa49c57608c26924e17de  source/lab/behavior/test_native_scenario_contract.py
ee6eb790ba8bb4d31858128b3e07255d512bb3a598dd1bef38b182818a6bafa1  source/lab/behavior/newttl-assets/behaviorlab/ttl-consumer.lua
1e62ec5b106dab85d2dce19f55261a84c778ae53aafe343a3f6bd9cb2b7e1cd4  source/lab/behavior/newttl-assets/behaviorlab/ttl-white.png
7fd29487d44ace1612a9ce3f64ce6ea18bf428abdd7f8db1874e90a03a5603e4  source/lab/behavior/newttl-assets/tenants/behavior-ttl-a.tenant
f26b03b64b779f9f5c272e17349e739652c7df13c6ce27881e3c7da3a2467c0a  /tmp/ttl-behavior-tests-01a17ea1-final303.log
```

This matrix/handoff file's own SHA is supplied in the terminal response, avoiding
a recursive self-hash. `StarBehaviorLab.cpp` is unchanged; the game-dependent
implementation deliberately remains in the client translation unit.
